from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from typing import Optional, List, Dict
from datetime import datetime
import logging
import json
import asyncio
from typing import List, Optional, Dict, Any
from prisma import Json 

from app.schemas.translation import (
    TranslationRequestCreate,
    MultiEngineTranslationRequestCreate,
    TranslationStringUpdate,
    EngineSelectionData
)
from app.schemas.quality import AnnotationCreate
from app.db.base import prisma
from app.services.translation_service import translation_service
from app.utils.text_processing import detokenize_japanese, get_model_for_language_pair, split_text_into_sentences
from app.services.multimodal_service import multimodal_service as multimodal_service_instance
from starlette.concurrency import run_in_threadpool
from app.dependencies import get_fuzzy_matcher, get_multi_engine_service, get_multimodal_service

def map_language_to_prisma_enum(language_code: str) -> str:
    """Convert frontend language codes to Prisma SourceLanguage enum values"""
    language_mapping = {
        "EN": "EN",
        "JA": "JP",  # Fixed: Changed from "JA" to "JP" to match schema
        "FR": "FR"
    }
    return language_mapping.get(language_code.upper(), language_code)

def normalize_language_for_engines(language_code: str) -> str:
    """Convert any language code to the format expected by engines (lowercase)"""
    language_mapping = {
        "EN": "en",
        "JA": "ja", 
        "JP": "ja",
        "FR": "fr"
    }
    return language_mapping.get(language_code.upper(), language_code.lower())

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/translation-requests", tags=["Translation Requests"])

@router.get("/")
async def get_translation_requests(
    include: Optional[str] = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Get translation requests with optional includes and pagination"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        include_parts = include.split(',') if include else []

        include_obj = {}

        if 'strings' in include_parts:
            include_obj["translationStrings"] = True

        if 'qualityMetrics' in include_parts:
            if "translationStrings" in include_obj:
                include_obj["translationStrings"] = {
                    "include": {
                        "annotations": True,
                        "qualityMetrics": True
                    }
                }
            else:
                include_obj["translationStrings"] = {
                    "include": {"qualityMetrics": True}
                }

        if 'qualityMetrics' in include_parts:
            include_obj["qualityMetrics"] = True

        requests = await prisma.translationrequest.find_many(
            include=include_obj if include_obj else {
                "translationStrings": {
                    "include": {
                        "annotations": True,
                        "qualityMetrics": True
                    }
                },
                "qualityMetrics": True
            },
            order={"createdAt": "desc"},
            take=limit,
            skip=offset,
        )

        return requests

    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

@router.post("/")
async def create_translation_request(
    request_data: TranslationRequestCreate,
    fuzzy_matcher=Depends(get_fuzzy_matcher),
    multi_engine_service=Depends(get_multi_engine_service),
):
    """Create a new translation request"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        logger.info(f"Processing translation request for targets: {request_data.targetLanguages}")

        if not request_data.sourceTexts:
            raise ValueError("No source texts provided for translation")
        
        from prisma.enums import MTModel
        
        model_mapping = {
            'HELSINKI_EN_FR': MTModel.MARIAN_MT_EN_FR,
            'HELSINKI_FR_EN': MTModel.MARIAN_MT_FR_EN, 
            'HELSINKI_EN_JA': MTModel.MARIAN_MT_EN_JP,
            'OPUS_JA_EN': MTModel.OPUS_MT_JA_EN,
            'ELAN_QUALITY': MTModel.ELAN_MT_JP_EN,
            'T5_VERSATILE': MTModel.T5_MULTILINGUAL,
            'NLLB_MULTILINGUAL': MTModel.NLLB_MULTILINGUAL,
            'PIVOT_ELAN_HELSINKI': MTModel.PIVOT_ELAN_HELSINKI,
            'MT5_BASE': MTModel.MT5_BASE,
            'MT5_MULTILINGUAL': MTModel.MT5_MULTILINGUAL,
        }
        
        if hasattr(request_data, 'mtModel') and request_data.mtModel:
            mt_model_enum = model_mapping.get(request_data.mtModel, MTModel.T5_MULTILINGUAL)
        else:
            language_pair = f"{request_data.sourceLanguage}-{','.join(request_data.targetLanguages)}"
            if language_pair.startswith('EN-FR'):
                mt_model_enum = MTModel.MARIAN_MT_EN_FR
            elif language_pair.startswith('FR-EN'):
                mt_model_enum = MTModel.MARIAN_MT_FR_EN
            elif language_pair.startswith('EN-JA'):
                mt_model_enum = MTModel.MARIAN_MT_EN_JP
            elif language_pair.startswith('JA-EN'):
                mt_model_enum = MTModel.OPUS_MT_JA_EN
            else:
                mt_model_enum = MTModel.T5_MULTILINGUAL
        
        logger.info(f"Using MT model: {mt_model_enum}")
            
        db_request = await prisma.translationrequest.create(
            data={
                "sourceLanguage": map_language_to_prisma_enum(request_data.sourceLanguage),
                "targetLanguages": request_data.targetLanguages,  # Fixed: no enum mapping
                "languagePair": f"{request_data.sourceLanguage}-{','.join(request_data.targetLanguages)}",
                "wordCount": request_data.wordCount,
                "fileName": request_data.fileName,
                "mtModel": mt_model_enum,
                "status": "IN_PROGRESS",
                "requestType": "SINGLE_ENGINE"
            }
        )

        total_processing_time = 0

        for target_lang in request_data.targetLanguages:
            source_lang_code = normalize_language_for_engines(request_data.sourceLanguage)
            target_lang_code = normalize_language_for_engines(target_lang)
            
            model_to_use_for_single_engine = get_model_for_language_pair(source_lang_code, target_lang_code)

            for i, source_text in enumerate(request_data.sourceTexts):
                start_time = datetime.now()
                try:
                    logger.info(f"Translating text {i+1}/{len(request_data.sourceTexts)} to {target_lang} using {model_to_use_for_single_engine}")

                    fuzzy_matches = await fuzzy_matcher.find_fuzzy_matches(
                        source_text, target_lang, request_data.sourceLanguage
                    )

                    suggested_translation = None
                    if fuzzy_matches and len(fuzzy_matches) > 0 and fuzzy_matches[0]["similarity"] > 0.9:
                        suggested_translation = fuzzy_matches[0]["target_text"]

                    translated_text = ""

                    prefix_or_lang_tag_for_single = None
                    model_info_from_ts_single = next(
                        (info for info in translation_service.language_pair_models.get(f"{request_data.sourceLanguage.upper()}-{target_lang.upper()}", [])
                        if info[0] == model_to_use_for_single_engine),
                        None
                    )
                    if model_info_from_ts_single and len(model_info_from_ts_single) == 3:
                        prefix_or_lang_tag_for_single = model_info_from_ts_single[2]

                    if model_to_use_for_single_engine == 'PIVOT_ELAN_HELSINKI':
                        translated_text = await multi_engine_service._translate_with_pivot(
                            source_text.strip(), source_lang_code, target_lang_code,
                            multi_engine_service.engine_configs['elan_quality']['pivot_strategy']
                        )
                    else:
                        translated_text = translation_service.translate_by_model_type(
                            source_text.strip(),
                            model_to_use_for_single_engine,
                            source_lang=source_lang_code,
                            target_lang=target_lang_code,
                            target_lang_tag=prefix_or_lang_tag_for_single
                        )

                    if target_lang.upper() == 'JP':
                        translated_text = detokenize_japanese(translated_text)

                    processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                    total_processing_time += processing_time

                    await prisma.translationstring.create(
                        data={
                            "sourceText": source_text.strip(),
                            "translatedText": translated_text,
                            "targetLanguage": target_lang,  # Fixed: keep as string, no enum mapping
                            "status": "REVIEWED",
                            "isApproved": False,
                            "processingTimeMs": processing_time,
                            "translationRequestId": db_request.id,
                            "fuzzyMatches": Json(fuzzy_matches) if fuzzy_matches else Json([]),
                            "suggestedTranslation": suggested_translation
                        }
                    )

                except Exception as e:
                    logger.error(f"Translation failed: {e}")
                    processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                    total_processing_time += processing_time

                    await prisma.translationstring.create(
                        data={
                            "sourceText": source_text.strip(),
                            "translatedText": f"Translation failed: {str(e)}",
                            "targetLanguage": target_lang,  # Fixed: keep as string, no enum mapping
                            "status": "DRAFT",
                            "isApproved": False,
                            "processingTimeMs": processing_time,
                            "translationRequestId": db_request.id,
                            "fuzzyMatches": Json([]),
                            "suggestedTranslation": None
                        }
                    )

        updated_request = await prisma.translationrequest.update(
            where={"id": db_request.id},
            data={
                "status": "COMPLETED",
                "totalProcessingTimeMs": total_processing_time
            },
            include={
                "translationStrings": {
                    "include": {
                        "annotations": True
                    }
                }
            }
        )

        logger.info(f"✅ Translation request {db_request.id} completed")
        return updated_request

    except Exception as e:
        logger.error(f"❌ Failed to create translation request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create translation request: {str(e)}")

@router.post("/multi-engine")
async def create_multi_engine_translation_request(
    request_data: MultiEngineTranslationRequestCreate,
    fuzzy_matcher=Depends(get_fuzzy_matcher),
    multi_engine_service=Depends(get_multi_engine_service),
):
    """Create translation request with multiple local engines"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        logger.info(f"Processing multi-engine translation request for targets: {request_data.targetLanguages}")

        if not request_data.sourceTexts:
            raise ValueError("No source texts provided for translation")

        from prisma.enums import MTModel
        from prisma import Json

        db_request = await prisma.translationrequest.create(
            data={
                "sourceLanguage": map_language_to_prisma_enum(request_data.sourceLanguage),
                "targetLanguages": request_data.targetLanguages,  # Fixed: no enum mapping
                "languagePair": f"{request_data.sourceLanguage}-{','.join(request_data.targetLanguages)}",
                "wordCount": request_data.wordCount,
                "fileName": request_data.fileName,
                "mtModel": MTModel.MULTI_ENGINE,
                "status": "MULTI_ENGINE_REVIEW",
                "requestType": "MULTI_ENGINE",
                "selectedEngines": request_data.engines
            }
        )

        for target_lang in request_data.targetLanguages:
            for i, source_text in enumerate(request_data.sourceTexts):
                logger.info(f"Getting multi-engine translations for text {i+1}/{len(request_data.sourceTexts)} to {target_lang}")

                fuzzy_matches = await fuzzy_matcher.find_fuzzy_matches(
                    source_text, target_lang, request_data.sourceLanguage
                )

                suggested_translation = None
                if fuzzy_matches and len(fuzzy_matches) > 0 and fuzzy_matches[0]["similarity"] > 0.9:
                    suggested_translation = fuzzy_matches[0]["target_text"]

                engine_results = await multi_engine_service.translate_multi_engine(
                    source_text, 
                    normalize_language_for_engines(request_data.sourceLanguage), 
                    normalize_language_for_engines(target_lang), 
                    request_data.engines
                )
                if target_lang.upper() == 'JP':
                    for result in engine_results:
                        if isinstance(result, dict) and 'text' in result:
                            result['text'] = detokenize_japanese(result['text'])

                await prisma.translationstring.create(
                    data={
                        "sourceText": source_text.strip(),
                        "translatedText": "",
                        "targetLanguage": target_lang,  # Fixed: keep as string, no enum mapping
                        "status": "MULTI_ENGINE_REVIEW",
                        "isApproved": False,
                        "processingTimeMs": int(sum(r.get('processing_time', 0) for r in engine_results if isinstance(r, dict) and 'processing_time' in r)),
                        "translationRequestId": db_request.id,
                        "engineResults": Json(engine_results) if engine_results else Json([]),
                        "fuzzyMatches": Json(fuzzy_matches) if fuzzy_matches else Json([]),
                        "suggestedTranslation": suggested_translation
                    }
                )

        complete_request = await prisma.translationrequest.find_unique(
            where={"id": db_request.id},
            include={
                "translationStrings": {
                    "include": {
                        "annotations": True
                    }
                }
            }
        )

        logger.info(f"✅ Multi-engine translation request {db_request.id} completed")
        return complete_request

    except Exception as e:
        logger.error(f"❌ Failed to create multi-engine request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create multi-engine request: {str(e)}")

@router.post("/triple-output")
async def create_triple_output_translation_request(
    request_data: TranslationRequestCreate,
    fuzzy_matcher=Depends(get_fuzzy_matcher),
    multi_engine_service=Depends(get_multi_engine_service),
):
    """Create translation request with exactly 3 outputs per language pair"""
    try:
        engines_per_pair_preference = {
            'en-jp': ['opus_fast', 't5_versatile', 'nllb_multilingual', 'elan_quality'],
            'jp-en': ['opus_fast', 'elan_quality', 't5_versatile', 'nllb_multilingual'],
            'en-fr': ['opus_fast', 't5_versatile', 'nllb_multilingual', 'elan_quality'],
            'fr-en': ['opus_fast', 't5_versatile', 'nllb_multilingual', 'elan_quality'],
            'jp-fr': ['opus_fast', 'elan_quality', 't5_versatile', 'nllb_multilingual']
        }

        all_possible_engines = multi_engine_service.get_available_engines_for_pair(
            normalize_language_for_engines(request_data.sourceLanguage), 
            normalize_language_for_engines(request_data.targetLanguages[0])
        )

        selected_engines_for_triple = sorted(
            all_possible_engines,
            key=lambda x: engines_per_pair_preference.get(request_data.languagePair.lower(), []).index(x)
            if x in engines_per_pair_preference.get(request_data.languagePair.lower(), []) else float('inf')
        )[:3]

        if not selected_engines_for_triple:
            raise HTTPException(status_code=400, detail=f"No suitable engines found for {request_data.languagePair} for triple output.")

        multi_request = MultiEngineTranslationRequestCreate(
            sourceLanguage=request_data.sourceLanguage,
            targetLanguages=request_data.targetLanguages,
            languagePair=request_data.languagePair,
            wordCount=request_data.wordCount,
            fileName=request_data.fileName,
            sourceTexts=request_data.sourceTexts,
            engines=selected_engines_for_triple
        )

        return await create_multi_engine_translation_request(
            multi_request,
            fuzzy_matcher=fuzzy_matcher,
            multi_engine_service=multi_engine_service,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create triple-output request: {str(e)}")

@router.put("/translation-strings/{string_id}")
async def update_translation_string(string_id: str, update_data: TranslationStringUpdate, request: Request):
    """Update a translation string and automatically calculate quality metrics"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        existing_string = await prisma.translationstring.find_unique(
            where={"id": string_id},
            include={"translationRequest": True}
        )

        if not existing_string:
            raise HTTPException(status_code=404, detail="Translation string not found")

        original_translation_for_comparison = existing_string.originalTranslation
        if original_translation_for_comparison is None:
            original_translation_for_comparison = existing_string.translatedText

        final_text = update_data.translatedText if update_data.translatedText is not None else existing_string.translatedText

        if existing_string.targetLanguage.upper() in ['JP', 'JA']:
            final_text = detokenize_japanese(final_text)

        update_payload = {
            "translatedText": final_text,
            "status": update_data.status,
            "isApproved": (update_data.status == 'APPROVED'),
            "lastModified": datetime.now()
        }

        if update_data.annotatorId:
            try:
                from prisma.enums import HumanAnnotator
                update_payload["annotatorId"] = HumanAnnotator[update_data.annotatorId]
            except KeyError:
                pass  # unknown value — leave existing annotatorId unchanged

        if original_translation_for_comparison != final_text:
            update_payload["hasReference"] = True
            if existing_string.originalTranslation is None:
                update_payload["originalTranslation"] = original_translation_for_comparison

        updated_string = await prisma.translationstring.update(
            where={"id": string_id},
            data=update_payload,
            include={"annotations": True}
        )

        # Commit to TM if approved
        if update_data.status == 'APPROVED':
            try:
                from prisma.enums import MemoryQuality
                await prisma.translationmemory.create(
                    data={
                        "sourceText": existing_string.sourceText,
                        "targetText": final_text,
                        "sourceLanguage": existing_string.translationRequest.sourceLanguage,
                        "targetLanguage": existing_string.targetLanguage,
                        "domain": "auto_generated",
                        "quality": MemoryQuality.HIGH,
                        "createdFrom": f"qa_approval_{string_id}",
                        "usageCount": 0
                    }
                )
                logger.info(f"✅ Created TM entry for approved translation: {string_id}")
            except Exception as tm_error:
                logger.error(f"⚠ Failed to create TM entry: {tm_error}")

        # AUTOMATIC QUALITY METRICS CALCULATION
        # Calculate metrics if approved/reviewed AND post-edited
        if update_data.status in ['APPROVED', 'REVIEWED'] and update_payload.get("hasReference"):
            try:
                # Import the helper function
                from app.api.routers.quality_assessment import calculate_metrics_for_string

                # Calculate metrics in background (non-blocking)
                asyncio.create_task(calculate_metrics_for_string(
                    string_id,
                    comet_model=getattr(request.app.state, "comet_model", None),
                ))
                logger.info(f"✅ Scheduled automatic metrics calculation for string: {string_id}")

            except Exception as metrics_error:
                # Don't fail the save if metrics calculation fails
                logger.warning(f"⚠ Failed to schedule metrics calculation: {metrics_error}")

        return {
            "success": True,
            "message": "Translation string updated successfully",
            "updatedString": updated_string,
            "metricsScheduled": update_data.status in ['APPROVED', 'REVIEWED'] and update_payload.get("hasReference", False)
        }

    except Exception as e:
        logger.error(f"Error updating translation string {string_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update translation string: {str(e)}")

@router.post("/translation-strings/{string_id}/select-engine")
async def select_preferred_engine(string_id: str, selection_data: EngineSelectionData):
    """Record user's engine preference and set as primary translation"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        existing_string = await prisma.translationstring.find_unique(
            where={"id": string_id},
            include={"translationRequest": True}
        )

        if not existing_string:
            raise HTTPException(status_code=404, detail="Translation string not found")

        engine_results = existing_string.engineResults
        if hasattr(engine_results, 'to_dict'):
            engine_results = engine_results.to_dict()
        elif isinstance(engine_results, str):
            import json
            engine_results = json.loads(engine_results)

        selected_result = None
        for result in engine_results:
            if result.get("engine") == selection_data.engine:
                selected_result = result
                break

        if not selected_result:
            raise HTTPException(status_code=400, detail="Selected engine not found")

        final_translated_text = selected_result["text"]

        if existing_string.targetLanguage.upper() == 'JP':
            final_translated_text = detokenize_japanese(final_translated_text)

        updated_string = await prisma.translationstring.update(
            where={"id": string_id},
            data={
                "translatedText": final_translated_text,
                "originalTranslation": final_translated_text,
                "selectedEngine": selection_data.engine,
                "status": "REVIEWED"
            }
        )

        return {"success": True, "selectedEngine": selection_data.engine, "updatedString": updated_string}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to select engine: {str(e)}")

@router.get("/fuzzy-matches")
async def get_fuzzy_matches(
    source_text: str,
    source_language: str,
    target_language: str,
    threshold: float = 0.6,
    fuzzy_matcher=Depends(get_fuzzy_matcher),
):
    """Get fuzzy matches for a source text"""
    try:
        fuzzy_matcher.threshold = threshold
        matches = await fuzzy_matcher.find_fuzzy_matches(source_text, target_language, source_language)

        return {
            "source_text": source_text,
            "language_pair": f"{source_language}-{target_language}",
            "threshold": threshold,
            "matches": matches,
            "total_matches": len(matches)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find fuzzy matches: {str(e)}")

@router.post("/translation-preferences")
async def track_translation_preference(preference_data: Dict):
    """Track which translation engine was preferred by the user"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        translation_string = await prisma.translationstring.find_unique(
            where={"id": preference_data["translationStringId"]},
            include={"translationRequest": True}
        )

        if not translation_string:
            raise HTTPException(status_code=404, detail="Translation string not found")

        await prisma.translationstring.update(
            where={"id": preference_data["translationStringId"]},
            data={
                "selectedEngine": preference_data["selectedEngine"],
                "selectedAt": datetime.now(),
                "selectionMethod": preference_data.get("selectionMethod", "UNKNOWN")
            }
        )

        await prisma.enginepreference.create(
            data={
                "translationStringId": preference_data["translationStringId"],
                "selectedEngine": preference_data["selectedEngine"],
                "sourceLanguage": preference_data.get("sourceLanguage", translation_string.translationRequest.sourceLanguage),
                "targetLanguage": preference_data.get("targetLanguage", translation_string.targetLanguage),
                "rating": preference_data.get("rating"),
                "preferenceReason": preference_data.get("preferenceReason"),
                "selectionMethod": preference_data.get("selectionMethod", "UNKNOWN"),
                "requestId": translation_string.translationRequestId
            }
        )

        return {"status": "success"}

    except Exception as e:
        logger.error(f"Error in translation-preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/translation-strings/{string_id}/annotations")
async def create_annotation(string_id: str, annotation_data: AnnotationCreate):
    """Create an annotation for a translation string"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        existing_string = await prisma.translationstring.find_unique(
            where={"id": string_id}
        )

        if not existing_string:
            raise HTTPException(status_code=404, detail="Translation string not found")

        # If selectedEngine is not yet set, backfill from the most recent EnginePreference
        # for this string so that annotations are attributed to the correct engine.
        if not existing_string.selectedEngine:
            ep = await prisma.enginepreference.find_first(
                where={"translationStringId": string_id},
                order={"createdAt": "desc"},
            )
            if ep and ep.selectedEngine:
                await prisma.translationstring.update(
                    where={"id": string_id},
                    data={"selectedEngine": ep.selectedEngine},
                )

        from prisma.enums import AnnotationCategory, AnnotationSeverity

        try:
            category_enum_val = getattr(AnnotationCategory, annotation_data.category.upper())
        except AttributeError:
            category_enum_val = AnnotationCategory.OTHER

        try:
            severity_enum_val = getattr(AnnotationSeverity, annotation_data.severity.upper())
        except AttributeError:
            severity_enum_val = AnnotationSeverity.MEDIUM

        new_annotation = await prisma.annotation.create(
            data={
                "category": category_enum_val,
                "severity": severity_enum_val,
                "comment": annotation_data.comment,
                "reviewer": annotation_data.reviewer or "anonymous",
                "translationStringId": string_id
            }
        )

        return {"success": True, "annotation": new_annotation}
    except Exception as e:
        logger.error(f"Error creating annotation for string {string_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to create annotation: {str(e)}")

@router.get("/{request_id}")
async def get_translation_request(request_id: str):
    """Get a specific translation request by ID"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        translation_request = await prisma.translationrequest.find_unique(
            where={"id": request_id},
            include={
                "translationStrings": {
                    "include": {
                        "annotations": True
                    }
                }
            }
        )

        if not translation_request:
            raise HTTPException(
                status_code=404,
                detail=f"Translation request {request_id} not found"
            )

        return translation_request

    except Exception as e:
        logger.error(f"Failed to get translation request {request_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detect-language")
async def detect_language_endpoint(
    file: UploadFile = File(...),
    multimodal_service=Depends(get_multimodal_service),
):
    """Detects the language of a file (text, audio, etc.)."""
    try:
        # Read the file content into memory ONCE
        file_content = await file.read()

        # Pass the content (bytes) and filename to the service
        detected_language = await multimodal_service.detect_language(
            file_content,
            file.filename
        )

        if not detected_language:
            raise HTTPException(status_code=400, detail="Could not detect language from file.")

        return {"language": detected_language.upper()}

    except Exception as e:
        logger.error(f"Error detecting language: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to detect language: {str(e)}")
        
def create_translation_request_object(
    sourceLanguage: str,
    targetLanguages: List[str],
    wordCount: int,
    fileName: str,
    sourceTexts: List[str],
    mtModel: Optional[str] = 'NLLB_200'
):
    """
    Creates a TranslationRequestCreate object from individual fields.
    This avoids the issue of trying to parse a Pydantic model directly from form data.
    """
    return TranslationRequestCreate(
        sourceLanguage=sourceLanguage,
        targetLanguages=targetLanguages,
        languagePair=f"{sourceLanguage}-{','.join(targetLanguages)}",
        wordCount=wordCount,
        fileName=fileName,
        sourceTexts=sourceTexts,
        mtModel=mtModel
    )

@router.post("/file-single-engine")
async def create_single_engine_from_file(
    file: UploadFile = File(...),
    sourceLanguage: str = Form(...),
    targetLanguages: List[str] = Form(...),
    multimodal_service=Depends(get_multimodal_service),
    fuzzy_matcher=Depends(get_fuzzy_matcher),
    multi_engine_service=Depends(get_multi_engine_service),
):
    """Creates a new single-engine translation request from an uploaded file."""
    try:
        # Read the file content once
        file_content = await file.read()
        file_name = file.filename

        extracted_text = await multimodal_service.extract_text_from_file(file_content, file_name)

        if not extracted_text:
            raise HTTPException(status_code=400, detail="Could not extract text from file.")

        sentences = split_text_into_sentences(extracted_text, sourceLanguage)
        word_count = len(extracted_text.split())

        request_data = create_translation_request_object(
            sourceLanguage=sourceLanguage,
            targetLanguages=targetLanguages,
            wordCount=word_count,
            fileName=file.filename,
            sourceTexts=sentences,
            mtModel='NLLB_200'
        )

        return await create_translation_request(
            request_data,
            fuzzy_matcher=fuzzy_matcher,
            multi_engine_service=multi_engine_service,
        )

    except Exception as e:
        logger.error(f"Failed to create single-engine request from file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create request: {str(e)}")

def create_multi_engine_request_object(
    sourceLanguage: str,
    targetLanguages: List[str],
    wordCount: int,
    fileName: str,
    sourceTexts: List[str],
    engines: List[str]
):
    """
    Creates a MultiEngineTranslationRequestCreate object from individual fields.
    """
    return MultiEngineTranslationRequestCreate(
        sourceLanguage=sourceLanguage,
        targetLanguages=targetLanguages,
        languagePair=f"{sourceLanguage}-{','.join(targetLanguages)}",
        wordCount=wordCount,
        fileName=fileName,
        sourceTexts=sourceTexts,
        engines=engines
    )

@router.post("/file-multi-engine")
async def create_multi_engine_from_file(
    file: UploadFile = File(...),
    sourceLanguage: str = Form(...),
    targetLanguages: List[str] = Form(...),
    engines: List[str] = Form(...),
    multimodal_service=Depends(get_multimodal_service),
    fuzzy_matcher=Depends(get_fuzzy_matcher),
    multi_engine_service=Depends(get_multi_engine_service),
):
    """Creates a new multi-engine translation request from an uploaded file."""
    try:
        # Read the file content once
        file_content = await file.read()
        file_name = file.filename

        extracted_text = await multimodal_service.extract_text_from_file(file_content, file_name)

        if not extracted_text:
            raise HTTPException(status_code=400, detail="Could not extract text from file.")

        sentences = split_text_into_sentences(extracted_text, sourceLanguage)
        word_count = len(extracted_text.split())

        request_data = create_multi_engine_request_object(
            sourceLanguage=sourceLanguage,
            targetLanguages=targetLanguages,
            wordCount=word_count,
            fileName=file.filename,
            sourceTexts=sentences,
            engines=engines
        )

        return await create_multi_engine_translation_request(
            request_data,
            fuzzy_matcher=fuzzy_matcher,
            multi_engine_service=multi_engine_service,
        )

    except Exception as e:
        logger.error(f"Failed to create multi-engine request from file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create request: {str(e)}")

@router.post("/file-preprocessing")
async def preprocess_file_for_segmentation(
    file: UploadFile = File(...),
    multimodal_service=Depends(get_multimodal_service),
):
    """
    Preprocess file and return segmentation data for the UI editor.
    This is the first step before translation - allows user to edit segments.
    """
    try:
        # Read the file content once
        file_content = await file.read()
        file_name = file.filename

        # Extract with segmentation data
        segmentation_data = await multimodal_service.extract_text_from_file_with_segmentation(
            file_content, file_name
        )
        
        if not segmentation_data["segments"]:
            raise HTTPException(status_code=400, detail="Could not extract any text segments from file.")
        
        # Calculate word count
        total_words = sum(
            len(segment["text"].split()) for segment in segmentation_data["segments"]
        )
        
        return {
            "success": True,
            "segmentationId": f"seg_{hash(file_name + str(len(file_content)))}",  # Simple ID generation
            "segments": segmentation_data["segments"],
            "mediaType": segmentation_data["media_type"],
            "mediaData": segmentation_data["media_data"],
            "detectedLanguage": segmentation_data["detected_language"],
            "wordCount": total_words,
            "fileName": file_name
        }
        
    except Exception as e:
        logger.error(f"Failed to preprocess file for segmentation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to preprocess file: {str(e)}")

@router.post("/segmentation/{segmentation_id}/save")
async def save_segmentation_edits(
    segmentation_id: str,
    segmentation_data: Dict[str, Any],
    fuzzy_matcher=Depends(get_fuzzy_matcher),
    multi_engine_service=Depends(get_multi_engine_service),
):
    """
    Save user's segmentation edits and proceed with translation.
    This replaces the segments with user-edited versions.
    """
    try:
        # In a real implementation, you might want to store this in a temporary cache
        # For now, we'll process it directly
        
        segments = segmentation_data.get("segments", [])
        if not segments:
            raise HTTPException(status_code=400, detail="No segments provided")
        
        # Extract just the text from segments for translation
        source_texts = [segment["text"].strip() for segment in segments if segment["text"].strip()]
        
        if not source_texts:
            raise HTTPException(status_code=400, detail="No valid text segments found")
        
        # Create the appropriate translation request based on the type
        request_type = segmentation_data.get("requestType", "single")
        source_language = segmentation_data.get("sourceLanguage")
        target_languages = segmentation_data.get("targetLanguages", [])
        file_name = segmentation_data.get("fileName", "segmented_file")
        word_count = sum(len(text.split()) for text in source_texts)
        
        if request_type == "multi":
            engines = segmentation_data.get("engines", [])
            request_data = create_multi_engine_request_object(
                sourceLanguage=source_language,
                targetLanguages=target_languages,
                wordCount=word_count,
                fileName=file_name,
                sourceTexts=source_texts,
                engines=engines
            )
            return await create_multi_engine_translation_request(
                request_data,
                fuzzy_matcher=fuzzy_matcher,
                multi_engine_service=multi_engine_service,
            )
        else:
            request_data = create_translation_request_object(
                sourceLanguage=source_language,
                targetLanguages=target_languages,
                wordCount=word_count,
                fileName=file_name,
                sourceTexts=source_texts
            )
            return await create_translation_request(
                request_data,
                fuzzy_matcher=fuzzy_matcher,
                multi_engine_service=multi_engine_service,
            )

    except Exception as e:
        logger.error(f"Failed to save segmentation and create translation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process segmentation: {str(e)}")

@router.get("/segmentation/{segmentation_id}")
async def get_segmentation_data(segmentation_id: str):
    """
    Retrieve cached segmentation data. In a real implementation,
    this would fetch from a cache/database.
    """
    try:
        # This is a placeholder - in reality you'd fetch from cache
        # For now, return an empty response indicating the data needs to be regenerated
        return {
            "success": False,
            "message": "Segmentation data expired. Please reprocess the file.",
            "expired": True
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve segmentation data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve segmentation: {str(e)}")

# Update the existing file upload endpoints to optionally support segmentation
@router.post("/file-single-engine-with-segmentation")
async def create_single_engine_with_optional_segmentation(
    file: UploadFile = File(...),
    sourceLanguage: str = Form(...),
    targetLanguages: List[str] = Form(...),
    useSegmentation: bool = Form(default=False),
    multimodal_service=Depends(get_multimodal_service),
    fuzzy_matcher=Depends(get_fuzzy_matcher),
    multi_engine_service=Depends(get_multi_engine_service),
):
    """
    Creates single-engine request with optional segmentation step.
    If useSegmentation=True, returns segmentation data instead of processing directly.
    """
    try:
        if useSegmentation:
            # Return segmentation data for UI editing
            return await preprocess_file_for_segmentation(file, multimodal_service=multimodal_service)
        else:
            # Process directly as before
            return await create_single_engine_from_file(
                file, sourceLanguage, targetLanguages,
                multimodal_service=multimodal_service,
                fuzzy_matcher=fuzzy_matcher,
                multi_engine_service=multi_engine_service,
            )

    except Exception as e:
        logger.error(f"Failed to create single-engine request: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create request: {str(e)}")

@router.post("/file-multi-engine-with-segmentation")
async def create_multi_engine_with_optional_segmentation(
    file: UploadFile = File(...),
    sourceLanguage: str = Form(...),
    targetLanguages: List[str] = Form(...),
    engines: List[str] = Form(...),
    useSegmentation: bool = Form(default=False),
    multimodal_service=Depends(get_multimodal_service),
    fuzzy_matcher=Depends(get_fuzzy_matcher),
    multi_engine_service=Depends(get_multi_engine_service),
):
    """
    Creates multi-engine request with optional segmentation step.
    If useSegmentation=True, returns segmentation data instead of processing directly.
    """
    try:
        if useSegmentation:
            # Return segmentation data for UI editing
            return await preprocess_file_for_segmentation(file, multimodal_service=multimodal_service)
        else:
            # Process directly as before
            return await create_multi_engine_from_file(
                file, sourceLanguage, targetLanguages, engines,
                multimodal_service=multimodal_service,
                fuzzy_matcher=fuzzy_matcher,
                multi_engine_service=multi_engine_service,
            )

    except Exception as e:
        logger.error(f"Failed to create multi-engine request: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create request: {str(e)}")