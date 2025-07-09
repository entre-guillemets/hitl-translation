from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict
from datetime import datetime
import logging
import json # Added for parsing engineResults from JSON
import asyncio # Added for create_multi_engine_translation_request

from app.schemas.translation import (
    TranslationRequestCreate, 
    MultiEngineTranslationRequestCreate,
    TranslationStringUpdate,
    EngineSelectionData
)
from app.schemas.quality import AnnotationCreate # Import AnnotationCreate
from app.db.base import prisma
from app.services.translation_service import translation_service # Keep this import
from app.utils.text_processing import detokenize_japanese, get_model_for_language_pair

# Import fuzzy_matcher and multi_engine_service globally and provide setter functions
fuzzy_matcher = None
multi_engine_service = None

def set_fuzzy_matcher(service):
    global fuzzy_matcher
    fuzzy_matcher = service

def set_multi_engine_service(service):
    global multi_engine_service
    multi_engine_service = service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/translation-requests", tags=["Translation Requests"])

@router.get("/")
@router.get("/")
async def get_translation_requests(include: Optional[str] = Query(None)):
    """Get all translation requests with optional includes"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        # Parse include parameter
        include_parts = include.split(',') if include else []
        
        # Build include object based on parameters
        include_obj = {}
        
        if 'strings' in include_parts:
            include_obj["translationStrings"] = True
            
        if 'qualityMetrics' in include_parts:
            # Include quality metrics nested within translation strings
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

        # Also include request-level quality metrics if needed
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
            }
        )
        
        # Sort in Python
        requests.sort(key=lambda x: x.createdAt, reverse=True)
        return requests
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

@router.post("/")
async def create_translation_request(request_data: TranslationRequestCreate):
    """Create a new translation request"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        logger.info(f"Processing translation request for targets: {request_data.targetLanguages}")
        
        if not request_data.sourceTexts:
            raise ValueError("No source texts provided for translation")
        
        # Import the MTModel enum from Prisma
        from prisma.enums import MTModel
        from prisma import Json
        
        # Convert mtModel string to proper enum value
        mt_model_mapping = {
            'HELSINKI_EN_FR': MTModel.MARIAN_MT_EN_FR,
            'HELSINKI_FR_EN': MTModel.MARIAN_MT_FR_EN,
            'HELSINKI_EN_JP': MTModel.MARIAN_MT_EN_JP,
            'ELAN_JA_EN': MTModel.ELAN_MT_JP_EN,
            'OPUS_JA_EN': MTModel.ELAN_MT_JP_EN,
            'OPUS_EN_JP': MTModel.MARIAN_MT_EN_JP,
            'T5_BASE': MTModel.T5_BASE,
            'T5_MULTILINGUAL': MTModel.T5_BASE,
            'NLLB_200': MTModel.NLLB_200,
            'CUSTOM_MODEL': MTModel.CUSTOM_MODEL,
            'MULTI_ENGINE': MTModel.MULTI_ENGINE,
            'PIVOT_JP_EN_FR': MTModel.PIVOT_JP_EN_FR,
        }
        
        mt_model_enum = mt_model_mapping.get(request_data.mtModel, MTModel.MARIAN_MT_EN_FR)
        
        # Create the translation request in database
        db_request = await prisma.translationrequest.create(
            data={
                "sourceLanguage": request_data.sourceLanguage,
                "targetLanguages": request_data.targetLanguages,
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
            source_lang_code = request_data.sourceLanguage.lower()
            target_lang_code = target_lang.lower()
            
            # Determine the model string name to pass to translation_service
            model_to_use_for_single_engine = get_model_for_language_pair(source_lang_code, target_lang_code)
            
            for i, source_text in enumerate(request_data.sourceTexts):
                start_time = datetime.now()
                try:
                    logger.info(f"Translating text {i+1}/{len(request_data.sourceTexts)} to {target_lang} using {model_to_use_for_single_engine}")
                    
                    # Get fuzzy matches from database
                    if fuzzy_matcher is None:
                        raise HTTPException(status_code=500, detail="Fuzzy matching service not initialized.")
                    
                    fuzzy_matches = await fuzzy_matcher.find_fuzzy_matches( #
                        source_text, target_lang, request_data.sourceLanguage
                    )
                    
                    suggested_translation = None
                    if fuzzy_matches and len(fuzzy_matches) > 0 and fuzzy_matches[0]["similarity"] > 0.9:
                        suggested_translation = fuzzy_matches[0]["target_text"]
                    
                    translated_text = ""
                    
                    # Determine prefix/lang_tag for T5/NLLB for single-engine path
                    prefix_or_lang_tag_for_single = None #
                    # Get model_info from translation_service.language_pair_models for this specific single model
                    model_info_from_ts_single = next( #
                        (info for info in translation_service.language_pair_models.get(f"{request_data.sourceLanguage.upper()}-{target_lang.upper()}", []) 
                        if info[0] == model_to_use_for_single_engine),
                        None
                    )
                    if model_info_from_ts_single and len(model_info_from_ts_single) == 3: #
                        prefix_or_lang_tag_for_single = model_info_from_ts_single[2] #

                    # Perform translation based on the model_to_use_for_single_engine
                    if model_to_use_for_single_engine == 'PIVOT_ELAN_HELSINKI': #
                        # Explicit pivot for single engine JP-FR
                        if multi_engine_service is None:
                            raise HTTPException(status_code=500, detail="Multi-engine service not initialized for pivot translation.")
                        translated_text = await multi_engine_service._translate_with_pivot( #
                            source_text.strip(), source_lang_code, target_lang_code, 
                            multi_engine_service.engine_configs['elan_quality']['pivot_strategy'] # Assuming elan_quality has the pivot strategy for JP-FR
                        )
                    else:
                        # Direct translation using the specified model
                        translated_text = translation_service.translate_by_model_type( #
                            source_text.strip(), 
                            model_to_use_for_single_engine,
                            source_lang=source_lang_code, 
                            target_lang=target_lang_code, 
                            target_lang_tag=prefix_or_lang_tag_for_single 
                        )
                    
                    if target_lang.upper() == 'JP': #
                        translated_text = detokenize_japanese(translated_text) #
                    
                    processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                    total_processing_time += processing_time
                    
                    # Create translation string in database with proper JSON handling
                    await prisma.translationstring.create(
                        data={
                            "sourceText": source_text.strip(),
                            "translatedText": translated_text,
                            "targetLanguage": target_lang,
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
                    
                    # Create failed translation string
                    await prisma.translationstring.create(
                        data={
                            "sourceText": source_text.strip(),
                            "translatedText": f"Translation failed: {str(e)}",
                            "targetLanguage": target_lang,
                            "status": "DRAFT",
                            "isApproved": False,
                            "processingTimeMs": processing_time,
                            "translationRequestId": db_request.id,
                            "fuzzyMatches": Json([]),
                            "suggestedTranslation": None
                        }
                    )
        
        # Update request status and total processing time
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
        
        logger.info(f"✓ Translation request {db_request.id} completed")
        return updated_request
        
    except Exception as e:
        logger.error(f"✗ Failed to create translation request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create translation request: {str(e)}")

@router.post("/multi-engine")
async def create_multi_engine_translation_request(request_data: MultiEngineTranslationRequestCreate):
    """Create translation request with multiple local engines"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        logger.info(f"Processing multi-engine translation request for targets: {request_data.targetLanguages}")
        
        if not request_data.sourceTexts:
            raise ValueError("No source texts provided for translation")
        
        from prisma.enums import MTModel
        from prisma import Json
        
        # Create the translation request in database
        db_request = await prisma.translationrequest.create(
            data={
                "sourceLanguage": request_data.sourceLanguage,
                "targetLanguages": request_data.targetLanguages,
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
                
                # Get fuzzy matches from database
                if fuzzy_matcher is None:
                    raise HTTPException(status_code=500, detail="Fuzzy matching service not initialized.")
                fuzzy_matches = await fuzzy_matcher.find_fuzzy_matches( #
                    source_text, target_lang, request_data.sourceLanguage
                )
                
                suggested_translation = None
                if fuzzy_matches and len(fuzzy_matches) > 0 and fuzzy_matches[0]["similarity"] > 0.9:
                    suggested_translation = fuzzy_matches[0]["target_text"]
                
                # Get translations from all local engines using CleanMultiEngineService
                if multi_engine_service is None:
                    raise HTTPException(status_code=500, detail="Multi-engine service not initialized.")
                engine_results = await multi_engine_service.translate_multi_engine( #
                    source_text, request_data.sourceLanguage, target_lang, request_data.engines
                )
                
                # Create translation string in database
                await prisma.translationstring.create(
                    data={
                        "sourceText": source_text.strip(),
                        "translatedText": "",  # Will be set when user selects preferred
                        "targetLanguage": target_lang,
                        "status": "MULTI_ENGINE_REVIEW",
                        "isApproved": False,
                        "processingTimeMs": int(sum(r.get('processing_time', 0) for r in engine_results if isinstance(r, dict) and 'processing_time' in r)),
                        "translationRequestId": db_request.id,
                        "engineResults": Json(engine_results) if engine_results else Json([]),
                        "fuzzyMatches": Json(fuzzy_matches) if fuzzy_matches else Json([]),
                        "suggestedTranslation": suggested_translation
                    }
                )
        
        # Get the complete request with strings
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
        
        logger.info(f"✓ Multi-engine translation request {db_request.id} completed")
        return complete_request
        
    except Exception as e:
        logger.error(f"✗ Failed to create multi-engine request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create multi-engine request: {str(e)}")

@router.post("/triple-output")
async def create_triple_output_translation_request(request_data: TranslationRequestCreate):
    """Create translation request with exactly 3 outputs per language pair"""
    try:
        if multi_engine_service is None:
            raise HTTPException(status_code=500, detail="Multi-engine service not initialized.")

        # Define preferred engines for triple output
        engines_per_pair_preference = { #
            'en-jp': ['opus_fast', 't5_versatile', 'nllb_multilingual', 'elan_quality'],
            'jp-en': ['opus_fast', 'elan_quality', 't5_versatile', 'nllb_multilingual'],
            'en-fr': ['opus_fast', 't5_versatile', 'nllb_multilingual', 'elan_quality'],
            'fr-en': ['opus_fast', 't5_versatile', 'nllb_multilingual', 'elan_quality'],
            'jp-fr': ['opus_fast', 'elan_quality', 't5_versatile', 'nllb_multilingual']
        }
        
        # Get all engines that actually support the given pair
        all_possible_engines = multi_engine_service.get_available_engines_for_pair( #
            request_data.sourceLanguage, request_data.targetLanguages[0]
        )
        
        # Sort these by the preferred order and take up to the first 3
        selected_engines_for_triple = sorted( #
            all_possible_engines,
            key=lambda x: engines_per_pair_preference.get(request_data.languagePair.lower(), []).index(x)
            if x in engines_per_pair_preference.get(request_data.languagePair.lower(), []) else float('inf')
        )[:3]
        
        if not selected_engines_for_triple: #
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
        
        return await create_multi_engine_translation_request(multi_request)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create triple-output request: {str(e)}")

@router.put("/translation-strings/{string_id}")
async def update_translation_string(string_id: str, update_data: TranslationStringUpdate):
    """Update a translation string and commit to TM if approved"""
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
        
        if existing_string.targetLanguage.upper() == 'JP':
            final_text = detokenize_japanese(final_text)
        
        update_payload = {
            "translatedText": final_text,
            "status": update_data.status,
            "isApproved": (update_data.status == 'APPROVED'),
            "lastModified": datetime.now()
        }
        
        if original_translation_for_comparison != final_text:
            update_payload["hasReference"] = True
            if existing_string.originalTranslation is None:
                update_payload["originalTranslation"] = original_translation_for_comparison
        
        updated_string = await prisma.translationstring.update(
            where={"id": string_id},
            data=update_payload,
            include={"annotations": True}
        )
        
        # If approved, create TM entry
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
                logger.info(f"✓ Created TM entry for approved translation: {string_id}")
            except Exception as tm_error:
                logger.error(f"⚠ Failed to create TM entry: {tm_error}")

        # If approved AND hasReference, trigger quality metrics calculation
        if update_data.status == 'APPROVED' and update_payload.get("hasReference"): #
            try: #
                from app.api.routers.quality_assessment import calculate_quality_metrics # Import the function
                from app.schemas.quality import QualityMetricsCalculate # Import the schema
                asyncio.create_task(calculate_quality_metrics(QualityMetricsCalculate(requestId=existing_string.translationRequestId))) #
                logger.info(f"✓ Triggered auto-calculation of quality metrics for request: {existing_string.translationRequestId}") #
            except Exception as metrics_error: #
                logger.error(f"⚠ Failed to auto-calculate quality metrics: {metrics_error}") #
        
        return {"success": True, "message": "Translation string updated successfully", "updatedString": updated_string}
        
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
        
        # Get engine results
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
    threshold: float = 0.6
):
    """Get fuzzy matches for a source text"""
    try:
        if fuzzy_matcher is None:
            raise HTTPException(status_code=500, detail="Fuzzy matching service not initialized.")
        fuzzy_matcher.threshold = threshold #
        matches = await fuzzy_matcher.find_fuzzy_matches(source_text, target_language, source_language) #
        
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
        
        # Find the translation string to get context
        translation_string = await prisma.translationstring.find_unique(
            where={"id": preference_data["translationStringId"]},
            include={"translationRequest": True}
        )
        
        if not translation_string:
            raise HTTPException(status_code=404, detail="Translation string not found")
        
        # Update the TranslationString with selection info
        await prisma.translationstring.update(
            where={"id": preference_data["translationStringId"]},
            data={
                "selectedEngine": preference_data["selectedEngine"],
                "selectedAt": datetime.now(),
                "selectionMethod": preference_data.get("selectionMethod", "UNKNOWN")
            }
        )
        
        # Create EnginePreference record
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

        # Verify string exists
        existing_string = await prisma.translationstring.find_unique(
            where={"id": string_id}
        )

        if not existing_string:
            raise HTTPException(status_code=404, detail="Translation string not found")

        # Import enums properly
        from prisma.enums import AnnotationCategory, AnnotationSeverity

        # Convert to enum values
        try:
            category_enum_val = getattr(AnnotationCategory, annotation_data.category.upper())
        except AttributeError:
            category_enum_val = AnnotationCategory.OTHER

        try:
            severity_enum_val = getattr(AnnotationSeverity, annotation_data.severity.upper())
        except AttributeError:
            severity_enum_val = AnnotationSeverity.MEDIUM

        # Create annotation in database
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
                        "qualityRatings": True,
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
