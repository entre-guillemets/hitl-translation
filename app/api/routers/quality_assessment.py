# app/api/routers/quality_assessment.py

from fastapi import APIRouter, Depends, HTTPException, Query
import logging
from typing import List, Dict, Any
import sacrebleu
import statistics
import traceback
import os
from datetime import datetime, timedelta
from collections import defaultdict
import torch.utils.data
from torch.utils.data import DataLoader, Dataset # <-- Ensure Dataset is imported

from app.schemas.quality import (
    QualityRating,
    PreferenceComparison,
    QualityMetricsCalculate,
    AnnotationCreate,
    MetricXRequest,
    BatchMetricXRequest
)

# REMOVED: from comet.models.utils import CometDataModule (and all prior failed imports)

# --- START FINAL FIX: Custom DataModule Class Definition ---
class CustomCometDataset(Dataset):
    """Wraps the raw COMET samples list for the DataLoader."""
    def __init__(self, samples):
        self.samples = samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]

class CustomCometDataModule:
    """Minimal implementation of LightningDataModule needed for comet_model.predict(datamodule=...)"""
    def __init__(self, samples, batch_size=8, num_workers=0):
        self.samples = samples
        self.batch_size = batch_size
        self.num_workers = num_workers

    def predict_dataloader(self):
        # COMET's internal predict_dataloader needs a DataLoader that yields the raw dict samples.
        return DataLoader(
            CustomCometDataset(self.samples),
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            shuffle=False,
            # Use default_collate for raw dictionaries.
            collate_fn=torch.utils.data.dataloader.default_collate 
        )
# --- END FINAL FIX: Custom DataModule Class Definition ---


from app.db.base import prisma
from app.services.human_feedback_service import human_feedback_service
from app.dependencies import get_comet_model, get_metricx_service
_original_dataloader_init = torch.utils.data.DataLoader.__init__

def safe_dataloader_init(self, *args, **kwargs):
    if kwargs.get("num_workers", 0) == 0:
        kwargs.pop("multiprocessing_context", None)
        kwargs.pop("persistent_workers", None)
    _original_dataloader_init(self, *args, **kwargs)

torch.utils.data.DataLoader.__init__ = safe_dataloader_init

os.environ["TOKENIZERS_PARALLELISM"] = "false"

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quality-assessment", tags=["Quality Assessment"])

def get_comet_quality_label(comet_score: float) -> str:
    """Convert COMET score to quality label"""
    from prisma.enums import QualityLabel
    if comet_score >= 0.8:
        return str(QualityLabel.EXCELLENT)
    elif comet_score >= 0.6:
        return str(QualityLabel.GOOD)
    elif comet_score >= 0.4:
        return str(QualityLabel.FAIR)
    elif comet_score >= 0.2:
        return str(QualityLabel.POOR)
    else:
        return str(QualityLabel.CRITICAL)

async def calculate_metrics_for_string(translation_string_id: str, comet_model=None):
    """Calculate BLEU/TER/ChrF/COMET metrics for a single translation string automatically"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        translation_string = await prisma.translationstring.find_unique(
            where={"id": translation_string_id},
            include={"translationRequest": True}
        )

        if not translation_string:
            logger.warning(f"Translation string {translation_string_id} not found")
            return None

        original_mt = translation_string.originalTranslation
        post_edited = translation_string.translatedText
        source = translation_string.sourceText

        is_post_edited = (
            original_mt and 
            post_edited and 
            original_mt.strip() != post_edited.strip() and
            translation_string.status in ["REVIEWED", "APPROVED"]
        )

        if not is_post_edited:
            logger.info(f"String {translation_string_id} not post-edited, skipping metrics")
            return None
        
        target_lang = translation_string.targetLanguage.lower()
        tokenizer_option = 'ja-mecab' if target_lang in ['jp', 'ja'] else '13a'
        logger.info(f"Using tokenizer '{tokenizer_option}' for metrics on lang '{target_lang}'")

        bleu_score = 0.5
        ter_score = 50.0
        chrf_score = 0.0
        comet_score = 0.0

        try:
            bleu_score = sacrebleu.sentence_bleu(
                original_mt,
                [post_edited],
                tokenize=tokenizer_option
            ).score / 100
            
            ter_result = sacrebleu.sentence_ter(
                original_mt, 
                [post_edited],
                tokenize=tokenizer_option
            )
            ter_score = min(100.0, ter_result.score)
            
            chrf_result = sacrebleu.sentence_chrf(original_mt, [post_edited])
            chrf_score = chrf_result.score
            
            if comet_model:
                try:
                    comet_model.eval()
                    
                    src_lang = translation_string.translationRequest.sourceLanguage.lower() if translation_string.translationRequest else 'en'
                    tgt_lang = target_lang
                    
                    comet_data = [{
                            "src": source,
                            "mt": original_mt,
                            "ref": post_edited,
                            "src_lang": src_lang, 
                            "tgt_lang": tgt_lang 
                    }]
                    
                    # 1. Create the DataModule
                    data_module = CustomCometDataModule(
                        comet_data,
                        batch_size=1,
                        num_workers=0,
                    )

                    # 2. Call predict with the created DataModule
                    comet_output = comet_model.predict(
                        datamodule=data_module, 
                        gpus=0,
                        progress_bar=False
                    )
                    
                    # Safely extract score
                    if comet_output and comet_output[0] and hasattr(comet_output[0], 'scores') and len(comet_output[0].scores) > 0:
                        comet_score = float(comet_output[0].scores[0])
                    # --- END FIX ---
                    else:
                        logger.warning(f"COMET returned invalid output for {translation_string_id}")
                        comet_score = 0.0
                        
                except Exception as comet_error:
                    logger.error(f"COMET calculation failed for {translation_string_id}: {comet_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    comet_score = 0.0
            else:
                logger.warning(f"COMET model not available for string {translation_string_id}")
                comet_score = 0.0
            
        except Exception as scoring_error:
            logger.error(f"Error calculating metrics for {translation_string_id}: {scoring_error}")
            pass

        from prisma.enums import QualityLabel
        if ter_score <= 20.0:
            quality_label = QualityLabel.EXCELLENT
        elif ter_score <= 30.0:
            quality_label = QualityLabel.GOOD
        elif ter_score <= 50.0:
            quality_label = QualityLabel.FAIR
        else:
            quality_label = QualityLabel.POOR

        await prisma.qualitymetrics.delete_many(
            where={"translationStringId": translation_string_id}
        )

        from prisma.enums import ReferenceType
        metrics = await prisma.qualitymetrics.create(
            data={
                "translationStringId": translation_string_id,
                "translationRequestId": translation_string.translationRequest.id,
                "bleuScore": bleu_score,
                "cometScore": comet_score,
                "chrfScore": chrf_score,
                "terScore": ter_score,
                "qualityLabel": quality_label,
                "hasReference": True,
                "referenceType": ReferenceType.POST_EDITED,
                "calculationEngine": "auto-calculate"
            }
        )
        logger.info(f"âœ… Recalculated metrics for {translation_string_id}: BLEU={bleu_score:.3f}, COMET={comet_score:.3f}, TER={ter_score:.2f}, ChrF={chrf_score:.2f}")

        return metrics

    except Exception as e:
        logger.error(f"Failed to calculate metrics for string {translation_string_id}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

@router.post("/comet-score")
async def calculate_comet_score(
    request: Dict[str, Any],
    comet_model=Depends(get_comet_model),
):
    """Calculate COMET score for translation quality"""
    try:
        if comet_model is None:
            raise HTTPException(status_code=503, detail="COMET model not available")

        source = request.get("source", "")
        hypothesis = request.get("hypothesis", "")
        reference = request.get("reference", "")
        source_lang = request.get("source_lang", "en").lower() 
        target_lang = request.get("target_lang", "fr").lower()

        if not source or not hypothesis or not reference:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: source, hypothesis, and reference"
            )

        # --- START FIX: Use CustomCometDataModule ---
        data = [{
            "src": source,
            "mt": hypothesis,
            "ref": reference,
            "src_lang": source_lang,
            "tgt_lang": target_lang
        }]
        
        data_module = CustomCometDataModule(
            data,
            batch_size=1,
            num_workers=0,
        )

        model_output = comet_model.predict(
            datamodule=data_module,
            gpus=0,
            progress_bar=False
        )
        
        # Safely extract score
        score = float(model_output[0].scores[0])
        system_score = float(model_output[0].system_score)
        # --- END FIX ---


        return {
            "score": score,
            "system_score": system_score,
            "model": "COMET-22-DA",
            "score_range": "Higher scores indicate better quality",
            "reference_based": True
        }

    except Exception as e:
        logger.error(f"COMET scoring failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch-comet-score")
async def calculate_batch_comet_scores(
    request: Dict[str, Any],
    comet_model=Depends(get_comet_model),
):
    """Calculate COMET scores for multiple translations"""
    try:
        if comet_model is None:
            raise HTTPException(status_code=503, detail="COMET model not available")

        translations = request.get("translations", [])
        if not translations:
            raise HTTPException(status_code=400, detail="No translations provided")

        data = []
        for item in translations:
            source_lang = item.get("source_lang", "en").lower()
            target_lang = item.get("target_lang", "fr").lower()
            data.append({
                "src": item.get("source", ""),
                "mt": item.get("hypothesis", ""),
                "ref": item.get("reference", ""),
                "src_lang": source_lang,
                "tgt_lang": target_lang
            })
        
        # --- START FIX: Use CustomCometDataModule ---
        data_module = CustomCometDataModule(
            data,
            batch_size=8,
            num_workers=0,
        )

        model_output = comet_model.predict(
            datamodule=data_module,
            gpus=0,
            progress_bar=False
        )
        
        # Flatten the list of lists output from predict()
        scores = [item for sublist in model_output for item in sublist.scores]
        # --- END FIX ---

        results = []
        for i, score in enumerate(scores):
            results.append({
                "translation_id": translations[i].get("id", i),
                "score": float(score),
                "source": data[i]["src"],
                "hypothesis": data[i]["mt"],
                "reference": data[i]["ref"]
            })

        return {
            "results": results,
            # system_score is typically the mean of all scores
            "system_score": statistics.mean(scores),
            "total_translations": len(results),
            "model": "COMET-22-DA"
        }

    except Exception as e:
        logger.error(f"Batch COMET scoring failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/predict-quality")
async def predict_translation_quality(
    request_id: str = Query(..., description="Translation request ID"),
    comet_model=Depends(get_comet_model),
):
    """Predict quality using COMET for a translation request"""
    try:
        if comet_model is None:
            raise HTTPException(status_code=503, detail="COMET model not available")

        if not prisma.is_connected():
            await prisma.connect()

        translation_request = await prisma.translationrequest.find_unique(
            where={"id": request_id},
            include={
                "translationStrings": {
                    "include": {"translationRequest": True}
                }
            }
        )

        if not translation_request:
            raise HTTPException(status_code=404, detail="Translation request not found")

        predictions = []
        
        # Prepare batch data for prediction
        batch_data = []
        string_ids = []
        
        for translation_string in translation_request.translationStrings:
            src_lang = translation_string.translationRequest.sourceLanguage.lower() if translation_string.translationRequest else 'en'
            tgt_lang = translation_string.targetLanguage.lower()
            
            # Use source as reference for reference-free prediction
            batch_data.append({
                "src": translation_string.sourceText,
                "mt": translation_string.translatedText,
                "ref": translation_string.sourceText,
                "src_lang": src_lang,
                "tgt_lang": tgt_lang
            })
            string_ids.append(translation_string.id)

        # --- START FIX: Use CustomCometDataModule ---
        data_module = CustomCometDataModule(
            batch_data,
            batch_size=8,
            num_workers=0,
        )

        model_output = comet_model.predict(
            datamodule=data_module,
            gpus=0,
            progress_bar=False
        )
        
        # Flatten the output scores
        scores = [item for sublist in model_output for item in sublist.scores]
        # --- END FIX ---
        
        for i, comet_score in enumerate(scores):
            comet_score = float(comet_score)
            quality_label = get_comet_quality_label(comet_score)
            string_id = string_ids[i]
            translation_string = translation_request.translationStrings[i]

            logger.info(f"Saving quality metrics for string {string_id}: score={comet_score}, label={quality_label}")

            quality_prediction = await prisma.qualitymetrics.create(
                data={
                    "translationStringId": string_id,
                    "translationRequestId": translation_string.translationRequest.id,
                    "cometScore": comet_score,
                    "qualityLabel": quality_label,
                    "hasReference": False,
                    "calculationEngine": "comet-prediction"
                }
            )
            
            logger.info(f"Quality metrics saved successfully: {quality_prediction.id}")

            predictions.append({
                "translationStringId": string_id,
                "cometScore": comet_score,
                "qualityLabel": quality_label,
                "targetLanguage": translation_string.targetLanguage
            })

        logger.info(f"Completed quality prediction for request {request_id}: {len(predictions)} strings processed")
        
        return {
            "requestId": request_id,
            "predictions": predictions,
            "totalStrings": len(predictions)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to predict quality: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# Continuation of quality_assessment.py - remaining functions

@router.post("/predict-quality-batch")
async def predict_quality_batch(
    request_ids: List[str],
    comet_model=Depends(get_comet_model),
):
    """Predict quality for multiple translation requests"""
    try:
        if comet_model is None:
            raise HTTPException(status_code=503, detail="COMET model not available")

        if not prisma.is_connected():
            await prisma.connect()

        results = []
        for request_id in request_ids:
            try:
                translation_request = await prisma.translationrequest.find_unique(
                    where={"id": request_id},
                    include={
                        "translationStrings": {
                            "include": {"translationRequest": True}
                        }
                    }
                )

                if not translation_request:
                    results.append({
                        "requestId": request_id,
                        "status": "error",
                        "error": "Translation request not found"
                    })
                    continue
                
                # --- Batching for all strings in the request ---
                batch_data = []
                string_to_save = [] # List to hold strings that need saving metrics

                for translation_string in translation_request.translationStrings:
                    existing_metrics = await prisma.qualitymetrics.find_first(
                        where={"translationStringId": translation_string.id}
                    )
                    
                    if existing_metrics:
                        continue # Skip if metrics already exist

                    src_lang = translation_string.translationRequest.sourceLanguage.lower() if translation_string.translationRequest else 'en'
                    tgt_lang = translation_string.targetLanguage.lower()
                    
                    batch_data.append({
                        "src": translation_string.sourceText,
                        "mt": translation_string.translatedText,
                        "ref": translation_string.sourceText,
                        "src_lang": src_lang,
                        "tgt_lang": tgt_lang
                    })
                    string_to_save.append(translation_string)

                if not batch_data:
                    results.append({
                        "requestId": request_id,
                        "status": "success",
                        "predictions": [],
                        "totalStrings": 0
                    })
                    continue

                # --- START FIX: Use CustomCometDataModule ---
                data_module = CustomCometDataModule(
                    batch_data,
                    batch_size=8,
                    num_workers=0,
                )

                model_output = comet_model.predict(
                    datamodule=data_module,
                    gpus=0,
                    progress_bar=False
                )
                
                scores = [item for sublist in model_output for item in sublist.scores]
                # --- END FIX ---
                
                predictions = []

                for i, comet_score in enumerate(scores):
                    comet_score = float(comet_score)
                    quality_label = get_comet_quality_label(comet_score)
                    translation_string = string_to_save[i]

                    quality_prediction = await prisma.qualitymetrics.create(
                        data={
                            "translationStringId": translation_string.id,
                            "translationRequestId": translation_string.translationRequest.id,
                            "cometScore": comet_score,
                            "qualityLabel": quality_label,
                            "hasReference": False,
                            "calculationEngine": "comet-prediction"
                        }
                    )

                    predictions.append({
                        "translationStringId": translation_string.id,
                        "cometScore": comet_score,
                        "qualityLabel": quality_label,
                        "targetLanguage": translation_string.targetLanguage
                    })

                results.append({
                    "requestId": request_id,
                    "status": "success",
                    "predictions": predictions,
                    "totalStrings": len(predictions)
                })

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to process request {request_id}: {e}")
                results.append({
                    "requestId": request_id,
                    "status": "error",
                    "error": str(e)
                })

        return {
            "results": results,
            "totalRequests": len(request_ids),
            "successfulRequests": len([r for r in results if r["status"] == "success"])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch quality prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-all-pending")
async def process_all_pending_quality_assessments(comet_model=Depends(get_comet_model)):
    """Process quality assessment for all translation requests without quality metrics"""
    try:
        if comet_model is None:
            raise HTTPException(status_code=503, detail="COMET model not available")

        if not prisma.is_connected():
            await prisma.connect()

        pending_strings = await prisma.translationstring.find_many(
            where={"qualityMetrics": {"none": {}}},
            include={"translationRequest": True}
        )

        if not pending_strings:
            return {"message": "No pending translation strings found", "totalProcessed": 0}
        
        # --- Batching preparation ---
        batch_data = []
        string_lookup = {}
        
        for translation_string in pending_strings:
            src = translation_string.sourceText
            mt = translation_string.translatedText
            
            if not src or not src.strip() or not mt or not mt.strip():
                logger.warning(f"Skipping string {translation_string.id}: Missing source or translation text.")
                continue

            src_lang = translation_string.translationRequest.sourceLanguage.lower() if translation_string.translationRequest else 'en'
            tgt_lang = translation_string.targetLanguage.lower()

            batch_data.append({
                "src": src, 
                "mt": mt, 
                "ref": src, # Reference-free mode uses src as ref
                "src_lang": src_lang, 
                "tgt_lang": tgt_lang
            })
            string_lookup[len(batch_data) - 1] = translation_string # Index -> object lookup

        if not batch_data:
            return {"message": "No valid pending strings found after filtering", "totalProcessed": 0}
        
        # --- START FIX: Use CustomCometDataModule ---
        data_module = CustomCometDataModule(
            batch_data,
            batch_size=8,
            num_workers=0,
        )

        model_output = comet_model.predict(
            datamodule=data_module, 
            gpus=0,
            progress_bar=False
        )
        
        scores = [item for sublist in model_output for item in sublist.scores]
        # --- END FIX ---

        processed_count = 0
        errors = []
        
        for i, comet_score in enumerate(scores):
            translation_string = string_lookup.get(i)
            if not translation_string:
                continue
                
            try:
                comet_score = float(comet_score)
                quality_label = get_comet_quality_label(comet_score)

                await prisma.qualitymetrics.create(
                    data={
                        "translationStringId": translation_string.id,
                        "translationRequestId": translation_string.translationRequest.id,
                        "cometScore": comet_score,
                        "qualityLabel": quality_label,
                        "hasReference": False,
                        "calculationEngine": "comet-single-prediction"
                    }
                )
                processed_count += 1

            except Exception as e:
                error_msg = f"Failed to process and save metrics for string {translation_string.id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return {
            "message": f"Processed {processed_count} translation strings",
            "totalProcessed": processed_count,
            "totalPending": len(pending_strings),
            "errors": errors if errors else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process all pending quality assessments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/comet-trends")
async def get_comet_trends(
    days: int = Query(30, description="Number of days to analyze"),
    group_by: str = Query("language_pair", description="Group by: language_pair, model, or date")
):
    """Get COMET score trends over time"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        metrics = await prisma.qualitymetrics.find_many(
            where={
                "createdAt": {
                    "gte": start_date,
                    "lte": end_date
                },
                "cometScore": {"not": None}
            },
            include={
                "translationString": {
                    "include": {
                        "translationRequest": True
                    }
                }
            },
            order={"createdAt": "asc"}
        )

        if group_by == "language_pair":
            trends = process_language_pair_trends(metrics)
        elif group_by == "model":
            trends = process_model_trends(metrics)
        else:
            trends = process_date_trends(metrics)

        return {
            "trends": trends,
            "period": f"{days} days",
            "groupBy": group_by,
            "totalDataPoints": len(metrics)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get COMET trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def process_language_pair_trends(metrics):
    """Process metrics data to show trends by language pair"""
    language_pairs = defaultdict(list)

    for metric in metrics:
        if metric.translationString and metric.translationString.translationRequest:
            source_lang = metric.translationString.translationRequest.sourceLanguage
            target_lang = metric.translationString.targetLanguage
            pair = f"{source_lang}-{target_lang}"
            language_pairs[pair].append(metric.cometScore)

    trends = []
    for pair, scores in language_pairs.items():
        trends.append({
            "label": pair,
            "averageCometScore": statistics.mean(scores),
            "totalTranslations": len(scores),
            "minScore": min(scores),
            "maxScore": max(scores)
        })

    return sorted(trends, key=lambda x: x["averageCometScore"], reverse=True)

def process_model_trends(metrics):
    """Process metrics data to show trends by MT model"""
    models = defaultdict(list)

    for metric in metrics:
        if metric.translationString and metric.translationString.translationRequest:
            model = metric.translationString.translationRequest.mtModel or "Unknown"
            models[model].append(metric.cometScore)

    trends = []
    for model, scores in models.items():
        trends.append({
            "label": model,
            "averageCometScore": statistics.mean(scores),
            "totalTranslations": len(scores),
            "minScore": min(scores),
            "maxScore": max(scores)
        })

    return sorted(trends, key=lambda x: x["averageCometScore"], reverse=True)

def process_date_trends(metrics):
    """Process metrics data to show trends over time"""
    dates = defaultdict(list)

    for metric in metrics:
        date_key = metric.createdAt.strftime("%Y-%m-%d")
        dates[date_key].append(metric.cometScore)

    trends = []
    for date, scores in sorted(dates.items()):
        trends.append({
            "label": date,
            "averageCometScore": statistics.mean(scores),
            "totalTranslations": len(scores),
            "minScore": min(scores),
            "maxScore": max(scores)
        })

    return trends

@router.post("/calculate-metrics")
async def calculate_quality_metrics(
    request_data: QualityMetricsCalculate,
    comet_model=Depends(get_comet_model),
):
    """Calculate quality metrics using COMET, BLEU, and TER"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        if not request_data.requestId:
            raise HTTPException(status_code=400, detail="Missing required field: requestId")

        translation_request = await prisma.translationrequest.find_unique(
            where={"id": request_data.requestId},
            include={"translationStrings": True}
        )

        if not translation_request:
            raise HTTPException(status_code=404, detail="Translation request not found")

        existing_metrics = await prisma.qualitymetrics.find_first(
            where={"translationRequestId": request_data.requestId}
        )

        if existing_metrics:
            logger.info(f"Quality metrics already calculated for request {request_data.requestId}.")
            return {
                "success": True,
                "message": "Quality metrics already calculated",
                "metrics": existing_metrics
            }

        total_bleu = 0.0
        total_ter = 0.0
        processed_strings = 0
        has_any_reference = False
        
        # Batch preparation for COMET
        comet_batch_data = []
        string_lookup = {}
        comet_processed_count = 0

        from prisma.enums import QualityLabel, ReferenceType

        for translation_string in translation_request.translationStrings:
            current_string_id = translation_string.id
            current_original_mt = translation_string.originalTranslation
            current_post_edited = translation_string.translatedText
            current_source_text = translation_string.sourceText

            is_post_edited = (
                current_original_mt and
                current_post_edited and
                current_original_mt.strip() != current_post_edited.strip() and
                translation_string.status in ["REVIEWED", "APPROVED"]
            )

            if is_post_edited:
                has_any_reference = True

                try:
                    bleu_score = 0.0
                    ter_score = 0.0

                    if (not current_source_text or not current_source_text.strip() or
                        not current_original_mt or not current_original_mt.strip() or
                        not current_post_edited or not current_post_edited.strip()):
                        continue

                    target_lang_code = translation_string.targetLanguage.lower()
                    tokenizer_option = 'char' if target_lang_code in ['jp', 'ja'] else '13a'
                    bleu_score = sacrebleu.sentence_bleu(current_original_mt, [current_post_edited], tokenize=tokenizer_option).score / 100
                    
                    if target_lang_code in ['jp', 'ja']:
                        original_chars = ' '.join(list(current_original_mt.replace(' ', '')))
                        edited_chars = ' '.join(list(current_post_edited.replace(' ', '')))
                        ter_score = min(100.0, sacrebleu.TER().sentence_score(original_chars, [edited_chars]).score)
                    else:
                        ter_score = min(100.0, sacrebleu.TER(tokenize=tokenizer_option).sentence_score(current_original_mt, [current_post_edited]).score)

                    total_bleu += bleu_score
                    total_ter += ter_score
                    processed_strings += 1

                    # Prepare for COMET batching
                    if comet_model:
                        src_lang = translation_request.sourceLanguage.lower()
                        tgt_lang = target_lang_code
                        comet_batch_data.append({
                            "src": current_source_text, 
                            "mt": current_original_mt, 
                            "ref": current_post_edited,
                            "src_lang": src_lang, 
                            "tgt_lang": tgt_lang
                        })
                        string_lookup[comet_processed_count] = current_string_id
                        comet_processed_count += 1


                except Exception as metric_error:
                    logger.error(f"Error calculating metrics for string {current_string_id}: {metric_error}")
                    continue
        
        # --- COMET Calculation (Batched) ---
        comet_scores = {}
        avg_comet = 0.0
        
        if comet_model and comet_batch_data:
            try:
                # --- START FIX: Use CustomCometDataModule ---
                data_module = CustomCometDataModule(
                    comet_batch_data,
                    batch_size=8,
                    num_workers=0,
                )
                
                comet_output = comet_model.predict(
                    datamodule=data_module,
                    gpus=0,
                    progress_bar=False
                )
                
                scores = [item for sublist in comet_output for item in sublist.scores]
                # --- END FIX ---
                
                for i, score in enumerate(scores):
                    string_id = string_lookup[i]
                    comet_scores[string_id] = float(score)

                avg_comet = statistics.mean(scores)

            except Exception as comet_error:
                logger.error(f"COMET batch calculation failed: {comet_error}")
                avg_comet = 0.0
        
        # --- Final Metric Calculation and Saving ---

        if processed_strings > 0:
            avg_bleu = total_bleu / processed_strings
            avg_ter = total_ter / processed_strings
            
            # The individual string COMET score saving is skipped here, but the request-level average is calculated.

            if avg_ter <= 20.0:
                quality_label = QualityLabel.EXCELLENT
            elif avg_ter <= 30.0:
                quality_label = QualityLabel.GOOD
            elif avg_ter <= 50.0:
                quality_label = QualityLabel.FAIR
            else:
                quality_label = QualityLabel.POOR

            quality_metrics_record = await prisma.qualitymetrics.create(
                data={
                    "translationRequestId": request_data.requestId,
                    "bleuScore": avg_bleu,
                    "cometScore": avg_comet,
                    "terScore": avg_ter,
                    "qualityLabel": quality_label,
                    "hasReference": has_any_reference,
                    "referenceType": ReferenceType.POST_EDITED if has_any_reference else None,
                    "calculationEngine": "post-editing-metrics"
                }
            )

            return {
                "success": True,
                "message": f"Post-editing quality metrics calculated for {processed_strings} strings",
                "metrics": quality_metrics_record
            }
        else:
            return {
                "success": False,
                "message": "No valid post-edited strings found to calculate metrics.",
                "metrics": None
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating quality metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rate-quality")
async def rate_translation_quality(rating: QualityRating):
    """Rate translation quality"""
    try:
        result = await human_feedback_service.record_quality_rating(
            translation_string_id=rating.translationStringId,
            rating=rating.qualityScore,
            comments=f"Annotations: {rating.annotations}" if rating.annotations else None
        )
        return result
    except Exception as e:
        logger.error(f"Quality rating failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/preference-comparison")
async def record_preference_comparison(comparison: PreferenceComparison):
    """Record preference between two translations"""
    try:
        language_pair = "unknown"
        result = await human_feedback_service.record_preference_comparison(
            source_text=comparison.sourceText,
            translation_a=comparison.translationA,
            translation_b=comparison.translationB,
            preferred=comparison.preferred,
            language_pair=language_pair
        )
        return result
    except Exception as e:
        logger.error(f"Preference comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quality-summary/{request_id}")
async def get_quality_summary(request_id: str):
    """Get quality assessment summary for a translation request"""
    try:
        summary = await human_feedback_service.get_feedback_summary(request_id)
        if "error" in summary:
            raise HTTPException(status_code=500, detail=summary["error"])
        return summary
    except Exception as e:
        logger.error(f"Quality summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/metricx/evaluate")
async def evaluate_translation(request: MetricXRequest):
    """Evaluate translation using MetricX"""
    try:
        if metricx_service is None:
            raise HTTPException(status_code=503, detail="MetricX service not loaded or initialized.")

        result = metricx_service.evaluate_translation(
            source=request.source,
            hypothesis=request.hypothesis,
            reference=request.reference,
            source_language=request.source_language,
            target_language=request.target_language
        )
        return result
    except Exception as e:
        logger.error(f"MetricX evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metricx/test")
async def test_metricx():
    """Test MetricX service availability and basic functionality"""
    if metricx_service is None:
        raise HTTPException(status_code=503, detail="MetricX service not loaded or initialized")

    try:
        test_score = metricx_service.evaluate_without_reference(
            source="Hello world",
            translation="Hola mundo"
        )

        return {
            "status": "success",
            "test_score": test_score,
            "message": "MetricX is working correctly"
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        logger.error(f"MetricX test failed: {e}")
        raise HTTPException(status_code=500, detail=f"MetricX test failed: {str(e)}")

@router.post("/auto-calculate/{translation_string_id}")
async def auto_calculate_metrics(translation_string_id: str):
    """
    Automatically calculate metrics for a single translation string.
    Called automatically after saving approved/reviewed translations.
    """
    try:
        if not prisma.is_connected():
            await prisma.connect()

        metrics = await calculate_metrics_for_string(translation_string_id)

        if metrics:
            return {
                "success": True,
                "message": "Metrics calculated successfully",
                "metrics": {
                    "bleuScore": metrics.bleuScore,
                    "terScore": metrics.terScore,
                    "chrfScore": metrics.chrfScore,
                    "qualityLabel": str(metrics.qualityLabel)
                }
            }
        else:
            return {
                "success": False,
                "message": "No metrics calculated (string not post-edited or missing data)"
            }

    except Exception as e:
        logger.error(f"Auto-calculate failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/calculate-all-approved")
async def calculate_all_approved_metrics():
    """Calculate metrics for all approved/reviewed strings without metrics"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        strings = await prisma.translationstring.find_many(
            where={
                "status": {"in": ["REVIEWED", "APPROVED"]},
            },
            include={"translationRequest": True}
        )
        
        logger.info(f"Found {len(strings)} approved/reviewed strings to process")
        
        processed = 0
        errors = []
        skipped = 0
        
        for string in strings:
            try:
                if not string.originalTranslation or not string.translatedText:
                    skipped += 1
                    continue
                
                if string.originalTranslation.strip() == string.translatedText.strip():
                    skipped += 1
                    continue
                    
                metrics = await calculate_metrics_for_string(string.id)
                if metrics:
                    processed += 1
                    
            except Exception as e:
                logger.error(f"Error processing string {string.id}: {e}")
                errors.append({"id": string.id, "error": str(e)})
        
        return {
            "success": True,
            "processed": processed,
            "skipped": skipped,
            "total": len(strings),
            "errors": errors if errors else None,
            "message": f"Successfully calculated metrics for {processed} strings (skipped {skipped})"
        }
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))