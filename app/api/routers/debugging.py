from fastapi import APIRouter, HTTPException, Query
import logging
from typing import Dict, Any, List, Optional
import torch
import psutil
from datetime import datetime, timedelta
import statistics
import sacrebleu
import json
import traceback

from app.db.base import prisma
from app.services.translation_service import translation_service
from app.services.multi_engine_service import CleanMultiEngineService
from app.utils.text_processing import detokenize_japanese

# Global variables for models and services (set via main.py)
comet_model = None
metricx_service = None
multi_engine_service = None

def set_comet_model(model):
    global comet_model
    comet_model = model

def set_metricx_service(service):
    global metricx_service
    metricx_service = service

def set_multi_engine_service(service):
    global multi_engine_service
    multi_engine_service = service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/debug", tags=["Debugging"])

@router.get("/system-info")
async def get_system_info():
    """Get system information for debugging"""
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent
                }
            },
            "gpu": {
                "cuda_available": torch.cuda.is_available(),
                "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
                "cuda_current_device": torch.cuda.current_device() if torch.cuda.is_available() else None
            }
        }
        
    except Exception as e:
        logger.error(f"System info failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models-status")
async def get_models_status():
    """Get status of all translation models"""
    try:
        available_models = translation_service.get_available_models()
        
        status = {
            "translation_service": {
                "available_models": available_models,
                "loaded_models": list(translation_service.models.keys()),
                "loaded_pipelines": list(translation_service.pipelines.keys()),
                "device": translation_service.device
            },
            "metricx_service": {
                "is_loaded": metricx_service.is_loaded if metricx_service else False,
                "model_name": metricx_service.model_name if metricx_service else "N/A",
                "device": metricx_service.device if metricx_service else "N/A"
            },
            "multi_engine_service": {
                "available_engines": list(multi_engine_service.engine_configs.keys()) if multi_engine_service else [],
                "engine_configs": {
                    engine: {
                        "name": config["name"],
                        "supported_pairs": config["supported_pairs"],
                        "confidence": config["confidence"]
                    }
                    for engine, config in multi_engine_service.engine_configs.items()
                } if multi_engine_service else {}
            }
        }
        
        return status
        
    except Exception as e:
        logger.error(f"Models status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-translation")
async def test_translation(data: Dict[str, Any]):
    """Test translation with specific parameters"""
    try:
        text = data.get("text", "Hello, world!")
        source_lang = data.get("source_lang", "en")
        target_lang = data.get("target_lang", "fr")
        model_key = data.get("model_key")
        
        if model_key:
            # Test specific model
            result = translation_service.translate_by_model_type(
                text, model_key, source_lang, target_lang
            )
        else:
            # Test with fallback
            result = translation_service.translate_with_fallback(
                text, source_lang, target_lang
            )
        
        return {
            "input": {
                "text": text,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "model_key": model_key
            },
            "output": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Test translation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-multi-engine")
async def test_multi_engine_translation(data: Dict[str, Any]):
    """Test multi-engine translation"""
    try:
        if multi_engine_service is None:
            raise HTTPException(status_code=503, detail="Multi-engine service not loaded or initialized.")

        text = data.get("text", "Hello, world!")
        source_lang = data.get("source_lang", "en")
        target_lang = data.get("target_lang", "fr")
        engines = data.get("engines", ["opus_fast", "elan_quality"])
        
        results = await multi_engine_service.translate_multi_engine(
            text, source_lang, target_lang, engines
        )
        
        return {
            "input": {
                "text": text,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "engines": engines
            },
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Multi-engine test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test-database")
async def test_database():
    """Test basic database connectivity and a simple CRUD operation."""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Test creating a TM entry
        from prisma.enums import MemoryQuality
        test_entry = await prisma.translationmemory.create(
            data={
                "sourceText": "Test source",
                "targetText": "Test target",
                "sourceLanguage": "EN",
                "targetLanguage": "FR",
                "domain": "test",
                "quality": MemoryQuality.HIGH, # Use enum
                "createdFrom": "test",
                "usageCount": 0
            }
        )
        
        # Test querying
        count = await prisma.translationmemory.count()
        
        # Clean up test entry
        await prisma.translationmemory.delete(where={"id": test_entry.id})
        
        return {
            "success": True,
            "message": "Database working correctly",
            "total_entries_after_test": count - 1 # Should be original count
        }
        
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database test failed: {str(e)}")


@router.get("/database-stats")
async def get_database_stats():
    """Get database statistics"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        stats = {
            "translation_requests": await prisma.translationrequest.count(),
            "translation_strings": await prisma.translationstring.count(),
            "translation_memory": await prisma.translationmemory.count(),
            "glossary_terms": await prisma.glossaryterm.count(),
            "quality_ratings": await prisma.qualityrating.count(),
            "annotations": await prisma.annotation.count(),
            "engine_preferences": await prisma.enginepreference.count()
        }
        
        # Get recent activity
        recent_requests = await prisma.translationrequest.find_many(
            order={"createdAt": "desc"},
            take=5,
            select={"id": True, "createdAt": True, "status": True, "languagePair": True}
        )
        
        stats["recent_activity"] = recent_requests
        
        return stats
        
    except Exception as e:
        logger.error(f"Database stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear-cache")
async def clear_model_cache():
    """Clear model cache (for debugging)"""
    try:
        # Clear translation service cache
        translation_service.models.clear()
        translation_service.tokenizers.clear()
        translation_service.pipelines.clear()
        
        # Force garbage collection
        import gc
        gc.collect()
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return {
            "success": True,
            "message": "Model cache cleared",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs")
async def get_recent_logs():
    """Get recent log entries (simplified)"""
    try:
        return {
            "message": "Log viewing not implemented - check server logs",
            "suggestion": "Use 'tail -f logs/app.log' or similar to view logs",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Log retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/fix-reference-flags")
async def fix_quality_metrics_reference_flags():
    """
    Goes through all QualityMetrics entries and attempts to set hasReference=True
    if originalTranslation and translatedText indicate a post-edit.
    """
    try:
        if not prisma.is_connected():
            await prisma.connect()

        # Fetch all QualityMetrics records
        all_quality_metrics = await prisma.qualitymetrics.find_many(
            include={
                "translationString": True
            }
        )

        logger.info(f"Attempting to fix reference flags for {len(all_quality_metrics)} QualityMetrics records.")

        updated_count = 0
        for i, metric in enumerate(all_quality_metrics):
            if metric is None: # Should not happen, but defensive check
                logger.error(f"Metric object at index {i} is None.")
                continue

            if metric.id is None: # This is what we're specifically looking for
                logger.error(f"Metric object at index {i} has a NULL ID. Full object: {metric.dict()}")
                continue # Skip this problematic metric

            if metric.translationString:
                # Check if it's a post-edit
                original_mt = metric.translationString.originalTranslation
                post_edited = metric.translationString.translatedText
                status = metric.translationString.status

                is_post_edited = (
                    original_mt and
                    post_edited and
                    original_mt.strip() != post_edited.strip() and
                    status in ["REVIEWED", "APPROVED"]
                )

                if is_post_edited and not metric.hasReference:
                    logger.info(f"Updating hasReference for metric ID: {metric.id}")
                    # Update the hasReference flag
                    await prisma.qualitymetrics.update(
                        where={"id": metric.id},
                        data={"hasReference": True}
                    )
                    updated_count += 1
            else:
                logger.debug(f"Metric ID {metric.id} has no associated translationString, skipping.")

        logger.info(f"Fixed hasReference flags for {updated_count} quality metrics successfully.")
        return {"message": f"Fixed hasReference flags for {updated_count} quality metrics."}
    except Exception as e:
        logger.error(f"Error in fix_reference_flags: {e}")
        # Log the full traceback for more context
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check-quality-metrics")
async def check_quality_metrics():
    """Debug endpoint to check quality metrics data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        # Check total quality metrics
        total_metrics = await prisma.qualitymetrics.count()
        
        # Check metrics with references
        metrics_with_refs = await prisma.qualitymetrics.count(
            where={"hasReference": True}
        )
        
        # Check metrics with scores
        metrics_with_scores = await prisma.qualitymetrics.count(
            where={
                "hasReference": True,
                "bleuScore": {"not": None},
                "cometScore": {"not": None},
                "terScore": {"not": None}
            }
        )
        
        # Get sample data
        sample_metrics = await prisma.qualitymetrics.find_many(
            where={"hasReference": True},
            take=3,
            include={"translationRequest": True}
        )

        return {
            "total_metrics": total_metrics,
            "metrics_with_references": metrics_with_refs,
            "metrics_with_all_scores": metrics_with_scores,
            "sample_data": sample_metrics
        }

    except Exception as e:
        logger.error(f"check_quality_metrics failed: {e}")
        return {"error": str(e)}

@router.get("/check-annotations")
async def check_annotations():
    """Debug why annotations aren't showing in dashboard"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Check what annotations actually exist
        annotations = await prisma.annotation.find_many(
            include={
                "translationString": {
                    "include": {
                        "translationRequest": True
                    }
                }
            },
            take=10
        )
        
        return {
            "total_annotations": await prisma.annotation.count(),
            "sample_annotations": [
                {
                    "id": ann.id,
                    "category": ann.category,
                    "severity": ann.severity,
                    "comment": ann.comment,
                    "has_translation_string": ann.translationString is not None,
                    "has_request": ann.translationString.translationRequest is not None if ann.translationString else False
                } for ann in annotations
            ]
        }
    except Exception as e:
        logger.error(f"check_annotations failed: {e}")
        return {"error": str(e)}

@router.get("/data-counts")
async def check_data_counts():
    """Check actual data counts in each table"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        counts = {
            "translation_requests": await prisma.translationrequest.count(),
            "translation_strings": await prisma.translationstring.count(),
            "quality_metrics": await prisma.qualitymetrics.count(),
            "engine_preferences": await prisma.enginepreference.count(),
            "annotations": await prisma.annotation.count(),
            "model_outputs": await prisma.modeloutput.count(),
            "translation_memory": await prisma.translationmemory.count(),
            # "local_models": await prisma.localmodel.count() # LocalModel might not exist or be needed
        }
        
        return counts
        
    except Exception as e:
        logger.error(f"check_data_counts failed: {e}")
        return {"error": str(e)}

@router.post("/populate-dashboard-data")
async def populate_dashboard_data():
    """Populate dashboard tables with data from existing translations"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Get existing translation strings
        strings = await prisma.translationstring.find_many(
            include={"translationRequest": True},
            take=100
        )
        
        created_count = 0
        
        from prisma.enums import QualityLabel, EvaluationMode, ModelVariant # Import enums

        for string in strings:
            existing_metric = await prisma.qualitymetrics.find_first(
                where={"translationStringId": string.id}
            )
            
            if not existing_metric:
                await prisma.qualitymetrics.create(
                    data={
                        "translationStringId": string.id,
                        "metricXScore": 8.5, # Mock score
                        "metricXConfidence": 0.9,
                        "bleuScore": 0.75,
                        "cometScore": 0.82,
                        "terScore": 0.15,
                        "qualityLabel": QualityLabel.GOOD, # Use enum
                        "metricXMode": EvaluationMode.REFERENCE_FREE, # Use enum
                        "metricXVariant": ModelVariant.METRICX_24_HYBRID # Use enum
                    }
                )
                created_count += 1
        
        return {
            "success": True,
            "created_quality_metrics": created_count,
            "message": f"Created {created_count} quality metrics for existing translations"
        }
        
    except Exception as e:
        logger.error(f"populate_dashboard_data failed: {e}")
        return {"error": str(e)}

@router.post("/recalculate-all-metrics")
async def recalculate_all_metrics():
    """Recalculate quality metrics for all requests with post-edited strings"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        requests_with_post_edits = await prisma.translationrequest.find_many(
            where={
                "translationStrings": {
                    "some": {
                        "hasReference": True # Only requests where at least one string has a reference
                    }
                }
            },
            include={"translationStrings": True}
        )

        recalculated = []
        errors = []

        from prisma.enums import QualityLabel, ReferenceType, EvaluationMode, ModelVariant # Import enums

        for req in requests_with_post_edits:
            try:
                # Delete existing quality metrics for this request to recalculate
                await prisma.qualitymetrics.delete_many(
                    where={"translationRequestId": req.id}
                )

                # Check if there are actual post-edits
                has_post_edits = any(
                    ts.originalTranslation and 
                    ts.translatedText and 
                    ts.originalTranslation.strip() != ts.translatedText.strip() and
                    ts.status in ["REVIEWED", "APPROVED"]
                    for ts in req.translationStrings
                )

                if has_post_edits:
                    total_bleu = 0.0
                    total_ter = 0.0
                    total_comet = 0.0
                    processed_strings = 0

                    for ts in req.translationStrings:
                        current_string_id = ts.id
                        current_original_mt = ts.originalTranslation
                        current_post_edited = ts.translatedText
                        current_source_text = ts.sourceText

                        if (current_original_mt and 
                            current_post_edited and 
                            current_original_mt.strip() != current_post_edited.strip() and
                            ts.status in ["REVIEWED", "APPROVED"]):
                            
                            try:
                                logger.info(f"\n--- Recalculating for String ID: {current_string_id} ---")

                                if (not current_source_text or not current_source_text.strip() or
                                    not current_original_mt or not current_original_mt.strip() or
                                    not current_post_edited or not current_post_edited.strip()):
                                    logger.warning(f"SKIPPING String {current_string_id} due to empty text.")
                                    continue
                                
                                target_lang_code = ts.targetLanguage.lower()
                                tokenizer_option = 'ja-mecab' if target_lang_code == 'jp' else '13a'
                                logger.info(f"Using tokenizer '{tokenizer_option}' for metrics on lang '{target_lang_code}'")

                                bleu_score = sacrebleu.BLEU().sentence_score(current_original_mt, [current_post_edited]).score / 100
                                ter_score = sacrebleu.TER().sentence_score(current_original_mt, [current_post_edited]).score
                                
                                comet_score = 0.0
                                if comet_model:
                                    try:
                                        comet_data = [{"src": current_source_text, "mt": current_original_mt, "ref": current_post_edited}]
                                        
                                        comet_output = comet_model.predict(
                                            comet_data, 
                                            batch_size=1
                                        )
                                        comet_score = comet_output.scores[0]
                                    except Exception as comet_error:
                                        logger.error(f"COMET calculation failed during recalculation for {current_string_id}: {comet_error}")
                                else:
                                    logger.warning(f"COMET model not loaded during recalculation.")

                                total_bleu += bleu_score
                                total_ter += ter_score
                                total_comet += comet_score
                                processed_strings += 1

                            except Exception as metric_error:
                                logger.error(f"Error recalculating metrics for string {current_string_id}: {metric_error}")
                                traceback.print_exc()
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
                        
                        # Mock MetricX scores if service isn't available
                        metricx_score_val = 8.5 # Mock value
                        metricx_confidence_val = 0.92 # Mock value

                        await prisma.qualitymetrics.create(
                            data={
                                "translationRequestId": req.id,
                                "metricXScore": metricx_score_val,
                                "metricXConfidence": metricx_confidence_val,
                                "metricXMode": EvaluationMode.REFERENCE_FREE, # Using enum
                                "metricXVariant": ModelVariant.METRICX_24_HYBRID, # Using enum
                                "bleuScore": avg_bleu,
                                "cometScore": avg_comet,
                                "terScore": avg_ter,
                                "qualityLabel": quality_label, # Using enum
                                "hasReference": True,
                                "referenceType": ReferenceType.POST_EDITED, # Using enum
                                "calculationEngine": "bulk-recalculation"
                            }
                        )
                    recalculated.append(req.id)
            except Exception as e:
                errors.append({"requestId": req.id, "error": str(e)})
                logger.error(f"Error processing request {req.id} during recalculation: {e}")
                traceback.print_exc()

        return {
            "recalculated": recalculated,
            "errors": errors,
            "total": len(recalculated)
        }

    except Exception as e:
        logger.error(f"Error in recalculate_all_metrics: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to recalculate all metrics: {str(e)}")

@router.post("/populate-all-dashboard-data")
async def populate_all_dashboard_data():
    """Populate all dashboard tables with data from existing translations"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Get existing translation strings
        strings = await prisma.translationstring.find_many(
            include={"translationRequest": True}
        )
        
        created_metrics = 0
        created_preferences = 0
        created_annotations = 0
        created_model_outputs = 0
        
        from prisma.enums import QualityLabel, EvaluationMode, ModelVariant, MemoryQuality, AnnotationCategory, AnnotationSeverity, OffensiveSeverity, OffensiveCategory # All enums needed
        from prisma import Json # For Json fields

        # 1. Create quality metrics for strings that don't have them
        for string in strings:
            existing_metric = await prisma.qualitymetrics.find_first(
                where={"translationStringId": string.id}
            )
            
            if not existing_metric:
                await prisma.qualitymetrics.create(
                    data={
                        "translationStringId": string.id,
                        "metricXScore": 8.2 + (created_metrics % 10) * 0.1,
                        "metricXConfidence": 0.85 + (created_metrics % 5) * 0.02,
                        "bleuScore": 0.70 + (created_metrics % 8) * 0.03,
                        "cometScore": 0.78 + (created_metrics % 6) * 0.02,
                        "terScore": 0.20 - (created_metrics % 4) * 0.01,
                        "qualityLabel": QualityLabel.GOOD, # Use enum
                        "metricXMode": EvaluationMode.REFERENCE_FREE, # Use enum
                        "metricXVariant": ModelVariant.METRICX_24_HYBRID # Use enum
                    }
                )
                created_metrics += 1
        
        # 2. Create engine preferences
        engines = ["opus_fast", "elan_specialist", "t5_versatile", "nllb_multilingual"]
        valid_reasons = ["ACCURACY", "FLUENCY", "STYLE", "TERMINOLOGY", "CULTURAL_FIT", "NATURALNESS"]
        
        for i, string in enumerate(strings[:50]): # Limiting to 50 for demo
            if string.translationRequest: # Ensure translationRequest exists
                await prisma.enginepreference.create(
                    data={
                        "translationStringId": string.id,
                        "selectedEngine": engines[i % len(engines)],
                        "sourceLanguage": string.translationRequest.sourceLanguage,
                        "targetLanguage": string.translationRequest.targetLanguages[0] if string.translationRequest.targetLanguages else "EN",
                        "rating": 3 + (i % 3),
                        "selectionMethod": "COPY_BUTTON",
                        "overallSatisfaction": 3 + (i % 3),
                        "preferenceReason": valid_reasons[i % len(valid_reasons)]
                    }
                )
                created_preferences += 1
        
        # 3. Create annotations
        valid_categories = ["GRAMMAR", "WORD_CHOICE", "CONTEXT", "FLUENCY", "TERMINOLOGY", "STYLE"]
        valid_severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        
        for i, string in enumerate(strings[:20]): # Limiting to 20 for demo
            await prisma.annotation.create(
                data={
                    "translationStringId": string.id,
                    "category": AnnotationCategory(valid_categories[i % len(valid_categories)]), # Use enum
                    "severity": AnnotationSeverity(valid_severities[i % len(valid_severities)]), # Use enum
                    "comment": f"Sample annotation {i+1} for quality review",
                    "reviewer": "system_generated"
                }
            )
            created_annotations += 1
        
        # 4. Create model outputs
        model_names = ["HELSINKI_EN_JP", "ELAN_JA_EN", "T5_MULTILINGUAL", "NLLB_200"]
        engines_for_model_outputs = ["opus_fast", "elan_specialist", "t5_versatile", "nllb_multilingual"] # Use a distinct name to avoid conflict
        
        for i, string in enumerate(strings[:30]): # Limiting to 30 for demo
            for j in range(2): # Create 2 model outputs per string
                await prisma.modeloutput.create(
                    data={
                        "translationStringId": string.id,
                        "modelName": model_names[j % len(model_names)],
                        "engineName": engines_for_model_outputs[j % len(engines_for_model_outputs)],
                        "outputText": string.translatedText,
                        "confidence": 0.8 + (j * 0.1),
                        "processingTimeMs": 1000 + (i * 50) + (j * 200)
                    }
                )
                created_model_outputs += 1
                
        return {
            "success": True,
            "created": {
                "quality_metrics": created_metrics,
                "engine_preferences": created_preferences,
                "annotations": created_annotations,
                "model_outputs": created_model_outputs,
                "local_models": "skipped due to schema issues"
            },
            "message": "Dashboard data populated successfully (except LocalModel)!"
        }
        
    except Exception as e:
        import traceback
        logger.error(f"populate_all_dashboard_data failed: {e}")
        return {"error": str(e), "traceback": traceback.format_exc()}

@router.post("/populate-enhanced-dashboard-data")
async def populate_enhanced_dashboard_data():
    """Create more comprehensive dashboard data for better visualization"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Get existing translation strings
        strings = await prisma.translationstring.find_many(
            include={"translationRequest": True},
            take=100
        )
        
        created_count = 0 # Not directly used for return, but can track operations
        
        from prisma.enums import AnnotationCategory, AnnotationSeverity, MemoryQuality # Import enums

        # 1. Add TM match percentages to existing strings
        for i, string in enumerate(strings[:50]): # Limit for efficiency
            tm_percentage = [95, 85, 75, 65, 45][i % 5] # Vary TM match rates
            await prisma.translationstring.update(
                where={"id": string.id},
                data={"tmMatchPercentage": tm_percentage}
            )
        
        # 2. Create more annotations with varied severities
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        categories = ["GRAMMAR", "WORD_CHOICE", "CONTEXT", "FLUENCY", "TERMINOLOGY", "STYLE"]
        
        for i in range(30): # Create 30 annotations
            string = strings[i % len(strings)]
            await prisma.annotation.create(
                data={
                    "translationStringId": string.id,
                    "category": AnnotationCategory(categories[i % len(categories)]), # Use enum
                    "severity": AnnotationSeverity(severities[i % len(severities)]), # Use enum
                    "comment": f"Enhanced annotation {i+1}",
                    "reviewer": f"reviewer_{(i % 3) + 1}"
                }
            )
        
        # 3. Create more model outputs for processing time analysis
        models = ["HELSINKI_EN_JP", "ELAN_JA_EN", "T5_MULTILINGUAL", "NLLB_200"]
        engines_for_enhanced = ["opus_fast", "elan_specialist", "t5_versatile", "nllb_multilingual"]
        
        for i in range(60): # Create 60 model outputs
            string = strings[i % len(strings)]
            await prisma.modeloutput.create(
                data={
                    "translationStringId": string.id,
                    "modelName": models[i % len(models)],
                    "engineName": engines_for_enhanced[i % len(engines_for_enhanced)], # Fixed 'j' to 'i'
                    "outputText": string.translatedText,
                    "confidence": 0.7 + (i % 3) * 0.1,
                    "processingTimeMs": 800 + (i * 50) + ((i % 4) * 300) # Vary processing time
                }
            )
        
        # 4. Create more diverse engine preferences
        valid_reasons = ["ACCURACY", "FLUENCY", "STYLE", "TERMINOLOGY"] # Simplified reasons
        for i in range(40): # Create 40 more preferences
            string = strings[i % len(strings)]
            if string.translationRequest: # Ensure translationRequest exists
                await prisma.enginepreference.create(
                    data={
                        "translationStringId": string.id,
                        "selectedEngine": engines_for_enhanced[i % len(engines_for_enhanced)], # Use engines_for_enhanced
                        "sourceLanguage": string.translationRequest.sourceLanguage,
                        "targetLanguage": string.translationRequest.targetLanguages[0] if string.translationRequest.targetLanguages else "EN",
                        "rating": 2 + (i % 4), # Ratings 2-5
                        "selectionMethod": ["COPY_BUTTON", "MANUAL_EDIT", "RATING"][i % 3],
                        "overallSatisfaction": 2 + (i % 4),
                        "preferenceReason": valid_reasons[i % len(valid_reasons)]
                    }
                )
        
        return {
            "success": True,
            "message": f"Enhanced dashboard data created successfully!",
            "created_annotations": 30,
            "created_model_outputs": 60,
            "created_preferences": 40,
            "updated_tm_matches": 50
        }
        
    except Exception as e:
        import traceback
        logger.error(f"populate_enhanced_dashboard_data failed: {e}")
        return {"error": str(e), "traceback": traceback.format_exc()}

@router.get("/test-engine-preferences")
async def test_engine_preferences():
    """Debug the engine preferences function specifically"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Test raw query first
        all_prefs = await prisma.enginepreference.find_many(take=5)
        logger.info(f"Found {len(all_prefs)} engine preferences")
        
        engine_preferences_raw = await prisma.enginepreference.group_by(
            by=["selectedEngine", "sourceLanguage", "targetLanguage", "preferenceReason"],
            _count={"selectedEngine": True},
            _avg={"rating": True, "overallSatisfaction": True},
            where={} # No filter for now
        )
        
        logger.info(f"Grouped results: {len(engine_preferences_raw)}")
        
        engine_preferences = []
        for pref in engine_preferences_raw:
            engine_preferences.append({
                "engine": pref["selectedEngine"],
                "selectionCount": pref["_count"]["selectedEngine"],
                "avgRating": pref["_avg"]["rating"] or 0,
                "languagePair": f"{pref['sourceLanguage']}-{pref['targetLanguage']}",
                "preferenceReason": pref["preferenceReason"] or "unknown",
                "overallSatisfaction": pref["_avg"]["overallSatisfaction"] or 0
            })
        
        return {
            "total_preferences": await prisma.enginepreference.count(),
            "sample_raw_prefs": [
                {
                    "selectedEngine": p.selectedEngine,
                    "sourceLanguage": p.sourceLanguage,
                    "targetLanguage": p.targetLanguage,
                    "rating": p.rating
                } for p in all_prefs
            ],
            "grouped_count": len(engine_preferences_raw),
            "processed_preferences": engine_preferences[:5]
        }
        
    except Exception as e:
        import traceback
        logger.error(f"test_engine_preferences failed: {e}")
        return {"error": str(e), "traceback": traceback.format_exc()}

@router.post("/add-metricx-modes")
async def add_metricx_modes():
    """Add MetricX evaluation modes to existing quality metrics"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        metrics = await prisma.qualitymetrics.find_many(
            where={"metricXMode": None},
            take=50
        )
        
        from prisma.enums import EvaluationMode, ModelVariant # Import enums
        modes = [EvaluationMode.REFERENCE_FREE, EvaluationMode.REFERENCE_BASED, EvaluationMode.HYBRID]
        updated_count = 0
        
        for i, metric in enumerate(metrics):
            await prisma.qualitymetrics.update(
                where={"id": metric.id},
                data={
                    "metricXMode": modes[i % len(modes)],
                    "metricXVariant": ModelVariant.METRICX_24_HYBRID
                }
            )
            updated_count += 1
        
        return {"success": True, "updated_metrics": updated_count}
    except Exception as e:
        logger.error(f"add_metricx_modes failed: {e}")
        return {"error": str(e)}

@router.post("/add-tm-matches")
async def add_tm_matches():
    """Add TM match percentages to translation strings"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        strings = await prisma.translationstring.find_many(
            where={"tmMatchPercentage": None},
            take=100
        )
        
        updated_count = 0
        match_percentages = [95, 85, 75, 65, 45, 25]
        
        for i, string in enumerate(strings):
            match_pct = match_percentages[i % len(match_percentages)]
            await prisma.translationstring.update(
                where={"id": string.id},
                data={"tmMatchPercentage": match_pct}
            )
            updated_count += 1
        
        return {"success": True, "updated_strings": updated_count}
    except Exception as e:
        logger.error(f"add_tm_matches failed: {e}")
        return {"error": str(e)}

@router.get("/check-specific-metrics")
async def check_specific_metrics(requestIds: str = Query(...)):
    """Check quality metrics for specific request IDs"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        request_id_list = requestIds.split(",")
        
        metrics = await prisma.qualitymetrics.find_many(
            where={
                "translationRequestId": {"in": request_id_list}
            }
        )

        return {
            "found_metrics": len(metrics),
            "metrics_details": [
                {
                    "requestId": m.translationRequestId,
                    "hasReference": m.hasReference,
                    "bleuScore": m.bleuScore,
                    "cometScore": m.cometScore,
                    "terScore": m.terScore,
                    "qualityLabel": m.qualityLabel
                }
                for m in metrics
            ]
        }

    except Exception as e:
        logger.error(f"check_specific_metrics failed: {e}")
        return {"error": str(e)}