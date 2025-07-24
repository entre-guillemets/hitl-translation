from fastapi import APIRouter, HTTPException, Query 
import logging
import random
from typing import List, Dict, Any 
from datetime import datetime 
import sacrebleu 

from app.schemas.wmt import WMTRequestCreate, WMTBenchmarkResult
from app.db.base import prisma
from app.services.translation_service import translation_service
from app.utils.text_processing import get_model_for_language_pair, detokenize_japanese 

# Import multi_engine_service globally and provide setter functions
multi_engine_service = None

def set_multi_engine_service(service):
    global multi_engine_service
    multi_engine_service = service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wmt", tags=["WMT Benchmarks"])

# Sample WMT data 
WMT_SAMPLE_DATA = {
    "en-fr": [
        {"source": "The cat sits on the mat.", "reference": "Le chat est assis sur le tapis."},
        {"source": "Hello, how are you today?", "reference": "Bonjour, comment allez-vous aujourd'hui ?"},
        {"source": "Machine translation has improved significantly.", "reference": "La traduction automatique s'est considérablement améliorée."},
        {"source": "The weather is beautiful today.", "reference": "Le temps est magnifique aujourd'hui."},
        {"source": "I would like to order a coffee.", "reference": "Je voudrais commander un café."}
    ],
    "fr-en": [
        {"source": "Le chat est assis sur le tapis.", "reference": "The cat sits on the on the mat."},
        {"source": "Bonjour, comment allez-vous ?", "reference": "Hello, how are you?"},
        {"source": "La traduction automatique s'améliore.", "reference": "Machine translation is improving."},
        {"source": "Il fait beau aujourd'hui.", "reference": "The weather is nice today."},
        {"source": "Je voudrais un café, s'il vous plaît.", "reference": "I would like a coffee, please."}
    ],
    "en-jp": [
        {"source": "The cat sits on the mat.", "reference": "猫がマットの上に座っています。"},
        {"source": "Hello, how are you?", "reference": "こんにちは、元気ですか？"},
        {"source": "Machine translation technology is advancing.", "reference": "機械翻訳技術が進歩しています。"},
        {"source": "Today is a beautiful day.", "reference": "今日は美しい日です。"},
        {"source": "I want to learn Japanese.", "reference": "日本語を学びたいです。"}
    ],
    "jp-en": [
        {"source": "猫がマットの上に座っています。", "reference": "The cat sits on the mat."},
        {"source": "こんにちは、元気ですか？", "reference": "Hello, how are you?"},
        {"source": "機械翻訳が向上しています。", "reference": "Machine translation is improving."},
        {"source": "今日はいい天気です。", "reference": "The weather is nice today."},
        {"source": "コーヒーを注文したいです。", "reference": "I would like to order coffee."}
    ]
}

@router.post("/run-benchmark")
async def run_wmt_benchmark(request: WMTRequestCreate):
    """Run WMT benchmark test"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        language_pair = request.language_pair.lower()
        
        # Get sample data
        if language_pair not in WMT_SAMPLE_DATA:
            raise HTTPException(
                status_code=400, 
                detail=f"Language pair {language_pair} not supported. Available: {list(WMT_SAMPLE_DATA.keys())}"
            )
        
        sample_data = WMT_SAMPLE_DATA[language_pair]
        
        # Select random samples
        selected_samples = random.sample(sample_data, min(request.sample_size, len(sample_data)))
        
        # Get model for this language pair
        source_lang, target_lang = language_pair.split('-')
        model_to_use = get_model_for_language_pair(source_lang, target_lang)
        
        results = []
        
        for sample in selected_samples:
            try:
                # Translate using the model
                mt_translation = translation_service.translate_by_model_type(
                    sample["source"],
                    model_to_use,
                    source_lang=source_lang,
                    target_lang=target_lang
                )
                
                # Calculate BLEU score (simplified)
                bleu_score = calculate_simple_bleu(mt_translation, sample["reference"])
                
                result = WMTBenchmarkResult(
                    source_text=sample["source"],
                    reference_text=sample["reference"],
                    mt_translation=mt_translation,
                    bleu_score=bleu_score,
                    language_pair=language_pair
                )
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Translation failed for sample: {e}")
                results.append(WMTBenchmarkResult(
                    source_text=sample["source"],
                    reference_text=sample["reference"],
                    mt_translation=f"Translation failed: {str(e)}",
                    bleu_score=0.0,
                    language_pair=language_pair
                ))
        
        # Calculate average BLEU score
        avg_bleu = sum(r.bleu_score for r in results) / len(results) if results else 0
        
        # Store benchmark results
        benchmark_record = await prisma.wmtbenchmark.create(
            data={
                "languagePair": language_pair,
                "sampleSize": len(results),
                "averageBleuScore": avg_bleu,
                "modelUsed": model_to_use,
                "results": [r.dict() for r in results]
            }
        )
        
        return {
            "benchmark_id": benchmark_record.id,
            "language_pair": language_pair,
            "sample_size": len(results),
            "average_bleu_score": avg_bleu,
            "model_used": model_to_use,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"WMT benchmark failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/benchmarks")
async def get_benchmark_history():
    """Get benchmark history"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        benchmarks = await prisma.wmtbenchmark.find_many(
            order={"createdAt": "desc"},
            take=50
        )
        
        return {"benchmarks": benchmarks, "total": len(benchmarks)}
        
    except Exception as e:
        logger.error(f"Failed to get benchmarks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/benchmarks/{benchmark_id}")
async def get_benchmark_details(benchmark_id: str):
    """Get detailed benchmark results"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        benchmark = await prisma.wmtbenchmark.find_unique(
            where={"id": benchmark_id}
        )
        
        if not benchmark:
            raise HTTPException(status_code=404, detail="Benchmark not found")
        
        return benchmark
        
    except Exception as e:
        logger.error(f"Failed to get benchmark details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def calculate_simple_bleu(hypothesis: str, reference: str) -> float:
    """Calculate simplified BLEU score"""
    try:
        # Simple word-level BLEU calculation
        hyp_words = hypothesis.lower().split()
        ref_words = reference.lower().split()
        
        if not hyp_words or not ref_words:
            return 0.0
        
        # Count matching words
        matches = 0
        for word in hyp_words:
            if word in ref_words:
                matches += 1
        
        # Simple precision calculation
        precision = matches / len(hyp_words) if hyp_words else 0
        
        # Length penalty
        length_penalty = min(1.0, len(hyp_words) / len(ref_words)) if ref_words else 0
        
        return precision * length_penalty
        
    except Exception as e:
        logger.error(f"BLEU calculation failed: {e}")
        return 0.0

@router.post("/create-request")
async def create_wmt_benchmark_request( #
    language_pair: str = Query(...),
    sample_size: int = Query(100)
):
    """Create a WMT benchmark translation request"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        logger.info(f"Creating WMT benchmark request for {language_pair} with {sample_size} samples")
        
        from prisma.enums import MTModel
        from prisma import Json # Needed for fuzzyMatches as Json
        
        # Map language pairs to models
        model_mapping_enum = { #
            'jpn-eng': MTModel.ELAN_MT_JP_EN,
            'eng-jpn': MTModel.MARIAN_MT_EN_JP,
            'eng-fra': MTModel.MARIAN_MT_EN_FR,
            'fra-eng': MTModel.MARIAN_MT_FR_EN,
            'jpn-fra': MTModel.PIVOT_JP_EN_FR
        }
        
        mt_model_enum_val = model_mapping_enum.get(language_pair, MTModel.MARIAN_MT_EN_FR) 
        
        # Parse language pair
        source_lang, target_lang = language_pair.split('-')
        source_lang_code = source_lang.upper()[:2]
        target_lang_code = target_lang.upper()[:2]
        
        # Create WMT benchmark request
        wmt_request = await prisma.translationrequest.create(
            data={
                "sourceLanguage": source_lang_code,
                "targetLanguages": [target_lang_code],
                "languagePair": language_pair,
                "wordCount": sample_size * 20, # Estimate
                "fileName": f"wmt_benchmark_{language_pair}_{sample_size}.txt",
                "mtModel": mt_model_enum_val,
                "status": "IN_PROGRESS",
                "requestType": "WMT_BENCHMARK"
            }
        )
        
        # Create sample WMT test data (using static list for example)
        sample_texts = [ #
            "This is a sample sentence for WMT benchmark testing.",
            "Machine translation quality has improved significantly over the years.",
            "Evaluation metrics help us understand translation performance.",
            "Neural machine translation models show promising results.",
            "Benchmark datasets are essential for comparing different systems.",
            "Quality estimation is an important aspect of translation evaluation.",
            "Human evaluation remains the gold standard for translation quality.",
            "Automatic metrics provide quick feedback during development.",
            "Cross-lingual understanding is crucial for global communication.",
            "Translation technology continues to evolve rapidly."
        ]
        
        # Create translation strings for benchmark
        for i, source_text in enumerate(sample_texts[:sample_size]): #
            try: #
                # Use get_model_for_language_pair to get the model string key
                model_key_for_wmt = get_model_for_language_pair(source_lang, target_lang) #

                translated_text = "" #
                # Special handling for JP-FR for pivot
                if model_key_for_wmt == 'PIVOT_ELAN_HELSINKI': #
                    if multi_engine_service is None:
                        raise HTTPException(status_code=500, detail="Multi-engine service not initialized for pivot translation.")
                    translated_text = await multi_engine_service._translate_with_pivot(source_text.strip(), source_lang_code, target_lang_code, multi_engine_service.engine_configs['elan_quality']['pivot_strategy']) #
                else: #
                    # Direct translation using the specified model
                    # Ensure source_text is stripped for consistency with other methods
                    src_lang_code_for_ts = source_lang.lower() #
                    tgt_lang_code_for_ts = target_lang.lower() #
                    
                    # Fetch prefix/lang_tag from translation_service.language_pair_models if available
                    prefix_or_lang_tag = None #
                    model_info_from_ts = next( #
                        (info for info in translation_service.language_pair_models.get(f"{source_lang.upper()}-{target_lang.upper()}", []) 
                        if info[0] == model_key_for_wmt),
                        None
                    )
                    if model_info_from_ts and len(model_info_from_ts) == 3: #
                        prefix_or_lang_tag = model_info_from_ts[2] #

                    translated_text = translation_service.translate_by_model_type( #
                        source_text.strip(), 
                        model_key_for_wmt,
                        source_lang=src_lang_code_for_ts, 
                        target_lang=tgt_lang_code_for_ts, 
                        target_lang_tag=prefix_or_lang_tag 
                    )
                
                if target_lang_code == 'jp': #
                    translated_text = detokenize_japanese(translated_text) #
                
                # Create translation string
                await prisma.translationstring.create( #
                    data={
                        "sourceText": source_text,
                        "translatedText": translated_text,
                        "targetLanguage": target_lang_code,
                        "status": "REVIEWED",
                        "isApproved": False,
                        "processingTimeMs": 1000, # Mock processing time
                        "translationRequestId": wmt_request.id,
                        "fuzzyMatches": Json("[]") # Added Json for fuzzyMatches as empty array
                    }
                )
                
            except Exception as e:
                logger.error(f"Failed to translate WMT sample {i}: {e}") #
                # Create failed translation
                await prisma.translationstring.create( #
                    data={
                        "sourceText": source_text,
                        "translatedText": f"Translation failed: {str(e)}",
                        "targetLanguage": target_lang_code,
                        "status": "DRAFT",
                        "isApproved": False,
                        "processingTimeMs": 0,
                        "translationRequestId": wmt_request.id,
                        "fuzzyMatches": Json("[]") # Added Json for fuzzyMatches as empty array
                    }
                )
        
        # Update request status
        await prisma.translationrequest.update( #
            where={"id": wmt_request.id},
            data={"status": "COMPLETED"}
        )
        
        return { #
            "success": True,
            "request_id": wmt_request.id,
            "language_pair": language_pair,
            "sample_size": sample_size,
            "message": f"WMT benchmark request created for {language_pair}"
        }
        
    except Exception as e:
        logger.error(f"Failed to create WMT request: {e}") #
        raise HTTPException(status_code=500, detail=f"Failed to create WMT benchmark request: {str(e)}")

@router.get("/requests")
async def get_wmt_requests():
    """Get all WMT benchmark requests"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        wmt_requests = await prisma.translationrequest.find_many(
            where={"requestType": "WMT_BENCHMARK"},
            include={
                "translationStrings": True,
                "qualityMetrics": True
            }
        )
        
        # Sort in Python
        wmt_requests.sort(key=lambda x: x.createdAt, reverse=True)
        
        return wmt_requests
        
    except Exception as e:
        logger.error(f"Failed to fetch WMT requests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch WMT requests: {str(e)}")

@router.get("/results/{request_id}")
async def get_wmt_results(request_id: str):
    """Get WMT benchmark results for a specific request"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        wmt_request = await prisma.translationrequest.find_unique(
            where={"id": request_id},
            include={
                "translationStrings": True,
                "qualityMetrics": True
            }
        )
        
        if not wmt_request:
            raise HTTPException(status_code=404, detail="WMT request not found")
        
        return wmt_request
        
    except Exception as e:
        logger.error(f"Failed to fetch WMT results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch WMT results: {str(e)}")