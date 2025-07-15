# app/api/routers/quality_assessment.py

from fastapi import APIRouter, HTTPException, Query
import logging
from typing import List, Dict, Any
import sacrebleu
import statistics
import traceback
import os
from datetime import datetime, timedelta
from collections import defaultdict

from app.schemas.quality import (
    QualityRating,
    PreferenceComparison,
    QualityMetricsCalculate,
    AnnotationCreate,
    MetricXRequest,
    BatchMetricXRequest
)

from app.db.base import prisma
from app.services.human_feedback_service import human_feedback_service

# Fix tokenizer warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quality-assessment", tags=["Quality Assessment"])

comet_model = None
metricx_service = None

def set_comet_model(model):
    global comet_model
    comet_model = model

def set_metricx_service(service):
    global metricx_service
    metricx_service = service

def get_comet_quality_label(comet_score: float) -> str:
    """Convert COMET score to quality label"""
    if comet_score >= 0.8:
        return "EXCELLENT"
    elif comet_score >= 0.6:
        return "GOOD"
    elif comet_score >= 0.4:
        return "FAIR"
    elif comet_score >= 0.2:
        return "POOR"
    else:
        return "CRITICAL"

@router.post("/comet-score")
async def calculate_comet_score(request: Dict[str, Any]):
    """Calculate COMET score for translation quality"""
    try:
        global comet_model
        if comet_model is None:
            raise HTTPException(status_code=503, detail="COMET model not available")

        source = request.get("source", "")
        hypothesis = request.get("hypothesis", "")
        reference = request.get("reference", "")

        if not source or not hypothesis or not reference:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: source, hypothesis, and reference"
            )

        data = [{
            "src": source,
            "mt": hypothesis,
            "ref": reference
        }]

        model_output = comet_model.predict(
            data,
            batch_size=1,
            gpus=0,
            num_workers=1,
            progress_bar=False
        )

        return {
            "score": float(model_output.scores[0]),
            "system_score": float(model_output.system_score),
            "model": "COMET-22-DA",
            "score_range": "Higher scores indicate better quality",
            "reference_based": True
        }

    except Exception as e:
        logger.error(f"COMET scoring failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch-comet-score")
async def calculate_batch_comet_scores(request: Dict[str, Any]):
    """Calculate COMET scores for multiple translations"""
    try:
        global comet_model
        if comet_model is None:
            raise HTTPException(status_code=503, detail="COMET model not available")

        translations = request.get("translations", [])
        if not translations:
            raise HTTPException(status_code=400, detail="No translations provided")

        data = []
        for item in translations:
            data.append({
                "src": item.get("source", ""),
                "mt": item.get("hypothesis", ""),
                "ref": item.get("reference", "")
            })

        model_output = comet_model.predict(
            data,
            batch_size=8,
            gpus=0,
            num_workers=1,
            progress_bar=False
        )

        results = []
        for i, score in enumerate(model_output.scores):
            results.append({
                "translation_id": translations[i].get("id", i),
                "score": float(score),
                "source": data[i]["src"],
                "hypothesis": data[i]["mt"],
                "reference": data[i]["ref"]
            })

        return {
            "results": results,
            "system_score": float(model_output.system_score),
            "total_translations": len(results),
            "model": "COMET-22-DA"
        }

    except Exception as e:
        logger.error(f"Batch COMET scoring failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/predict-quality")
async def predict_translation_quality(request_id: str = Query(..., description="Translation request ID")):
    """Predict quality using COMET for a translation request"""
    try:
        global comet_model
        if comet_model is None:
            raise HTTPException(status_code=503, detail="COMET model not available")

        if not prisma.is_connected():
            await prisma.connect()

        # Get translation request with strings
        # MODIFIED: Include translationRequest for each translationString
        translation_request = await prisma.translationrequest.find_unique(
            where={"id": request_id},
            include={
                "translationStrings": {
                    "include": {"translationRequest": True} # <--- MODIFIED HERE
                }
            }
        )

        if not translation_request:
            raise HTTPException(status_code=404, detail="Translation request not found")

        predictions = []
        for translation_string in translation_request.translationStrings:
            # Use COMET for quality prediction (reference-free mode)
            comet_data = [{
                "src": translation_string.sourceText,
                "mt": translation_string.translatedText,
                "ref": translation_string.sourceText  # Use source as reference for prediction mode
            }]

            model_output = comet_model.predict(
                comet_data,
                batch_size=1,
                gpus=0,
                num_workers=1,
                progress_bar=False
            )

            comet_score = float(model_output.scores[0])
            quality_label = get_comet_quality_label(comet_score)
            
            # Log before database save
            logger.info(f"Saving quality metrics for string {translation_string.id}: score={comet_score}, label={quality_label}")

            # Create quality prediction record
            # MODIFIED: Ensure translationRequestId is explicitly added
            quality_prediction = await prisma.qualitymetrics.create(
                data={
                    "translationStringId": translation_string.id,
                    "translationRequestId": translation_string.translationRequest.id, # <--- MODIFIED HERE
                    "cometScore": comet_score,
                    "qualityLabel": quality_label,
                    "hasReference": False,
                    "calculationEngine": "comet-prediction"
                }
            )
            
            # Log after successful save
            logger.info(f"Quality metrics saved successfully: {quality_prediction.id}")

            predictions.append({
                "translationStringId": translation_string.id,
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

    except Exception as e:
        logger.error(f"Failed to predict quality: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/predict-quality-batch")
async def predict_quality_batch(request_ids: List[str]):
    """Predict quality for multiple translation requests"""
    try:
        global comet_model
        if comet_model is None:
            raise HTTPException(status_code=503, detail="COMET model not available")

        if not prisma.is_connected():
            await prisma.connect()

        results = []
        for request_id in request_ids:
            try:
                # Get translation request with strings
                # MODIFIED: Include translationRequest for each translationString
                translation_request = await prisma.translationrequest.find_unique(
                    where={"id": request_id},
                    include={
                        "translationStrings": { # Include translation strings
                            "include": {"translationRequest": True} # <--- MODIFIED HERE
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

                predictions = []
                for translation_string in translation_request.translationStrings:
                    # Skip if already has quality metrics
                    existing_metrics = await prisma.qualitymetrics.find_first(
                        where={"translationStringId": translation_string.id}
                    )
                    
                    if existing_metrics:
                        logger.info(f"Quality metrics already exist for string {translation_string.id}")
                        continue

                    # Use COMET for quality prediction
                    comet_data = [{
                        "src": translation_string.sourceText,
                        "mt": translation_string.translatedText,
                        "ref": translation_string.sourceText
                    }]

                    model_output = comet_model.predict(
                        comet_data,
                        batch_size=1,
                        gpus=0,
                        num_workers=1,
                        progress_bar=False
                    )

                    comet_score = float(model_output.scores[0])
                    quality_label = get_comet_quality_label(comet_score)

                    # Create quality prediction record
                    # MODIFIED: Ensure translationRequestId is explicitly added
                    quality_prediction = await prisma.qualitymetrics.create(
                        data={
                            "translationStringId": translation_string.id,
                            "translationRequestId": translation_string.translationRequest.id, # <--- MODIFIED HERE
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

    except Exception as e:
        logger.error(f"Batch quality prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-all-pending")
async def process_all_pending_quality_assessments():
    """Process quality assessment for all translation requests without quality metrics"""
    try:
        global comet_model
        if comet_model is None:
            raise HTTPException(status_code=503, detail="COMET model not available")

        if not prisma.is_connected():
            await prisma.connect()

        # Get all translation strings without quality metrics
        # MODIFIED: Include translationRequest for each translationString
        pending_strings = await prisma.translationstring.find_many(
            where={
                "qualityMetrics": {
                    "none": {}
                }
            },
            include={
                "translationRequest": True
            }
        )

        if not pending_strings:
            return {
                "message": "No pending translation strings found",
                "totalProcessed": 0
            }

        processed_count = 0
        errors = []

        # Process in batches for better performance
        batch_size = 10
        for i in range(0, len(pending_strings), batch_size):
            batch = pending_strings[i:i + batch_size]
            
            # Prepare batch data for COMET
            comet_data = []
            for translation_string in batch:
                comet_data.append({
                    "src": translation_string.sourceText,
                    "mt": translation_string.translatedText,
                    "ref": translation_string.sourceText
                })

            try:
                # Process batch with COMET
                model_output = comet_model.predict(
                    comet_data,
                    batch_size=len(comet_data),
                    gpus=0,
                    num_workers=1,
                    progress_bar=False
                )

                # Save results for each string in the batch
                for j, translation_string in enumerate(batch):
                    try:
                        comet_score = float(model_output.scores[j])
                        quality_label = get_comet_quality_label(comet_score)

                        # MODIFIED: Ensure translationRequestId is explicitly added
                        await prisma.qualitymetrics.create(
                            data={
                                "translationStringId": translation_string.id,
                                "translationRequestId": translation_string.translationRequest.id, # <--- MODIFIED HERE
                                "cometScore": comet_score,
                                "qualityLabel": quality_label,
                                "hasReference": False,
                                "calculationEngine": "comet-batch-prediction"
                            }
                        )
                        processed_count += 1

                    except Exception as e:
                        error_msg = f"Failed to save metrics for string {translation_string.id}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)

            except Exception as e:
                error_msg = f"Failed to process batch starting at index {i}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return {
            "message": f"Processed {processed_count} translation strings",
            "totalProcessed": processed_count,
            "totalPending": len(pending_strings),
            "errors": errors if errors else None
        }

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

        # Get quality metrics with related data
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

        # Process data based on grouping
        if group_by == "language_pair":
            trends = process_language_pair_trends(metrics)
        elif group_by == "model":
            trends = process_model_trends(metrics)
        else:  # date
            trends = process_date_trends(metrics)

        return {
            "trends": trends,
            "period": f"{days} days",
            "groupBy": group_by,
            "totalDataPoints": len(metrics)
        }

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
            "averageCometScore": sum(scores) / len(scores),
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
            "averageCometScore": sum(scores) / len(scores),
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
            "averageCometScore": sum(scores) / len(scores),
            "totalTranslations": len(scores),
            "minScore": min(scores),
            "maxScore": max(scores)
        })

    return trends

@router.post("/calculate-metrics")
async def calculate_quality_metrics(request_data: QualityMetricsCalculate):
    """Calculate quality metrics using COMET, BLEU, and TER"""
    try:
        global comet_model
        if not prisma.is_connected():
            await prisma.connect()

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
        total_comet = 0.0
        processed_strings = 0
        has_any_reference = False

        from prisma.enums import QualityLabel, ReferenceType, EvaluationMode, ModelVariant

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
                    comet_score = 0.0

                    if (not current_source_text or not current_source_text.strip() or
                        not current_original_mt or not current_original_mt.strip() or
                        not current_post_edited or not current_post_edited.strip()):
                        continue

                    target_lang_code = translation_string.targetLanguage.lower()
                    tokenizer_option = 'ja-mecab' if target_lang_code == 'jp' else '13a'

                    bleu_score = sacrebleu.sentence_bleu(current_original_mt, [current_post_edited], tokenize=tokenizer_option).score / 100
                    ter_score = sacrebleu.TER(tokenize=tokenizer_option).sentence_score(current_original_mt, [current_post_edited]).score

                    if comet_model:
                        try:
                            comet_data = [{"src": current_source_text, "mt": current_original_mt, "ref": current_post_edited}]
                            comet_output = comet_model.predict(
                                comet_data,
                                batch_size=1,
                                num_workers=1,
                                progress_bar=False
                            )
                            comet_score = comet_output.scores[0]
                        except Exception as comet_error:
                            logger.error(f"COMET calculation failed for {current_string_id}: {comet_error}")
                            comet_score = 0.0

                    total_bleu += bleu_score
                    total_ter += ter_score
                    total_comet += comet_score
                    processed_strings += 1

                except Exception as metric_error:
                    logger.error(f"Error calculating metrics for string {current_string_id}: {metric_error}")
                    continue

        if processed_strings > 0:
            avg_bleu = total_bleu / processed_strings
            avg_ter = total_ter / processed_strings
            avg_comet = total_comet / processed_strings

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

    except Exception as e:
        traceback.print_exc()
        logger.error(f"MetricX test failed: {e}")
        raise HTTPException(status_code=500, detail=f"MetricX test failed: {str(e)}")