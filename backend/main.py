from __future__ import annotations

import os
from dotenv import load_dotenv
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import subprocess
import json
import uuid
import re
import asyncio
from difflib import SequenceMatcher
from prisma import Prisma
from prisma import Json
import torch
from datetime import datetime, timedelta
import statistics
import sacrebleu
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import traceback
import logging
import sys
from prisma.enums import QualityLabel, ReferenceType, EvaluationMode, ModelVariant
from comet import download_model, load_from_checkpoint
from metricx_service import MetricXService

comet_model = None
metricx_service = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

print(f"--- PYTHON EXECUTABLE: {sys.executable}")
print(f"--- SACREBLEU VERSION: {sacrebleu.__version__}")

# Get the directory of the current script (main.py)
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the absolute path to .env assuming it's in the project root (one level up)
dotenv_path = os.path.join(current_script_dir, '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- Service Imports ---
from metricx_service import MetricXService 
from translation_service import translation_service
from reward_model_service import reward_model_service 
from human_feedback_service import enhanced_feedback_service 

app = FastAPI(swagger_ui_parameters={"operationsSorter": "method"})

tags_metadata = [
    {
        "name": "Health & Status",
        "description": "System health and status endpoints",
    },
    {
        "name": "Translation Requests", 
        "description": "Create and manage translation requests",
    },
    {
        "name": "Data Management",
        "description": "Translation memory, glossary, DNT management and fuzzy matching",
    },
    {
        "name": "WMT Benchmarks",
        "description": "WMT benchmark creation and results",
    },
    {
        "name": "Quality Assessment",
        "description": "Translation quality metrics and analysis",
    },    
    {
        "name": "Debugging",
        "description": "Generating mock data and issue triage",
    }
]

app = FastAPI(
    title="Translation Management API",
    openapi_tags=tags_metadata,
    swagger_ui_parameters={"operationsSorter": "method"}
)

# Enhanced CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Initialize Prisma client
prisma = Prisma()

# Pydantic models
class MetricXRequest(BaseModel):
    source: str
    hypothesis: str
    reference: Optional[str] = None
    source_language: str = "en"
    target_language: str = "es"
    model: Optional[str] = "MetricX-24-Hybrid"

class BatchMetricXRequest(BaseModel):
    requests: List[MetricXRequest]

class TranslationRequestCreate(BaseModel):
    sourceLanguage: str
    targetLanguages: List[str]
    languagePair: str
    wordCount: int
    fileName: str
    mtModel: str
    sourceTexts: Optional[List[str]] = []

class MultiEngineTranslationRequestCreate(BaseModel):
    sourceLanguage: str
    targetLanguages: List[str]
    languagePair: str
    wordCount: int
    fileName: str
    sourceTexts: Optional[List[str]] = []
    engines: Optional[List[str]] = ["opus_fast", "elan_specialist"] 

class QualityRating(BaseModel):
    translationStringId: str
    qualityScore: float  # 1-5 scale
    annotations: Optional[List[dict]] = []

class PreferenceComparison(BaseModel):
    sourceText: str
    translationA: str
    translationB: str
    preferred: str  # 'A' or 'B'
    referenceText: Optional[str] = None

class RLHFTrainingTrigger(BaseModel):
    force_retrain: bool = False

class QualityMetricsCalculate(BaseModel):
    requestId: str

class TranslationStringUpdate(BaseModel):
    translatedText: str
    status: str

class AnnotationCreate(BaseModel):
    category: str
    severity: str
    comment: str
    reviewer: Optional[str] = None

class EngineSelectionData(BaseModel):
    engine: str
    rating: int
    comments: Optional[str] = ""

# WMT Benchmark models 
class WMTRequestCreate(BaseModel):
    language_pair: str
    sample_size: int = 10

class WMTBenchmarkResult(BaseModel):
    source_text: str
    reference_text: str
    mt_translation: str
    bleu_score: float
    language_pair: str

# Command Center data models
class TranslationMemoryCreate(BaseModel):
    sourceText: str
    targetText: str
    sourceLanguage: str
    targetLanguage: str
    domain: str
    quality: str

class GlossaryTermCreate(BaseModel):
    term: str
    translation: str
    sourceLanguage: str
    targetLanguage: str
    domain: str
    definition: str

class DoNotTranslateCreate(BaseModel):
    text: str
    category: str
    languages: List[str]
    notes: str

class OffensiveWordCreate(BaseModel):
    word: str
    language: str
    severity: str
    category: str
    alternatives: Optional[str] = ""

# Database lifecycle management 
async def initialize_database():
    """Initialize database connection"""
    try:
        await prisma.connect()
        print("✓ Database connected successfully")

        # Test basic query
        count = await prisma.translationmemory.count()
        print(f"✓ Found {count} existing TM entries")

    except Exception as e:
        print(f"⚠ Database connection failed: {e}")
        print("⚠ Running without database - some features will be limited")

async def cleanup_database():
    """Cleanup database"""
    try:
        await prisma.disconnect()
        print("✓ Database disconnected")
    except Exception as e:
        print(f"⚠ Error disconnecting: {e}")

# Database startup/shutdown events
@app.on_event("startup")
async def startup():
    await initialize_database()

@app.on_event("startup")
async def startup_event():
    global metricx_service, comet_model    
    
    # Load COMET model
    try:
        print("Loading COMET model (cached)...")
        model_path = download_model("Unbabel/wmt22-comet-da")  
        comet_model = load_from_checkpoint(model_path)
        print(f"✓ COMET model loaded successfully: {type(comet_model)}")
    except Exception as e:
        print(f"❌ Failed to load COMET model: {e}")
        comet_model = None
    
    # Load MetricX model
    try:
        print("Loading MetricX model...")
        metricx_service = MetricXService()
        if metricx_service.load_model():
            print("✓ MetricX model loaded successfully")
        else:
            print("❌ Failed to load MetricX model")
            metricx_service = None
    except Exception as e:
        print(f"❌ MetricX initialization failed: {e}")
        metricx_service = None
    
    print("Model loading complete")

@app.on_event("shutdown")
async def shutdown():
    await cleanup_database()

# Enhanced Japanese detokenization function 
def detokenize_japanese(text: str) -> str:
    """Remove unnecessary spaces from Japanese text output"""
    text = re.sub(r'(?<=[\u3040-\u30FF\u4E00-\u9FFF])\s+(?=[\u3040-\u30FF\u4E00-\u9FFF])', '', text)
    text = text.replace(' .', '。').replace(' ,', '、')
    text = text.replace(' ・', '・')
    text = text.replace(' ！', '！').replace(' ？', '？')
    text = re.sub(r'\s+(?=[。、・！？])', '', text)
    text = re.sub(r'\s*（\s*', '（', text)
    text = re.sub(r'\s*）\s*', '）', text)
    return text.strip()

# Fuzzy Matching Service with database integration 
class FuzzyMatchingService:
    def __init__(self, threshold=0.7):
        self.threshold = threshold

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using SequenceMatcher"""
        return SequenceMatcher(None, text1.lower().strip(), text2.lower().strip()).ratio()

    async def find_fuzzy_matches(self, source_text: str, target_language: str, source_language: str) -> List[Dict]:
        """Find fuzzy matches in translation memory using database"""
        try:
            if not prisma.is_connected():
                await prisma.connect()

            # Get all TM entries for the language pair from database
            tm_entries = await prisma.translationmemory.find_many(
                where={
                    "sourceLanguage": source_language,
                    "targetLanguage": target_language
                }
            )

            matches = []
            for tm_entry in tm_entries:
                similarity = self.calculate_similarity(source_text, tm_entry.sourceText)

                if similarity >= self.threshold:
                    match_percentage = int(similarity * 100)
                    matches.append({
                        "tm_id": tm_entry.id,
                        "source_text": tm_entry.sourceText,
                        "target_text": tm_entry.targetText,
                        "similarity": similarity,
                        "match_percentage": match_percentage,
                        "domain": tm_entry.domain,
                        "quality": tm_entry.quality.lower(),
                        "last_used": tm_entry.lastUsed.isoformat() if tm_entry.lastUsed else None
                    })

            matches.sort(key=lambda x: x["similarity"], reverse=True)
            return matches[:5]

        except Exception as e:
            print(f"Error in fuzzy matching: {e}")
            return []

# Initialize fuzzy matching service
fuzzy_matcher = FuzzyMatchingService(threshold=0.6)

class CleanMultiEngineService:
    def __init__(self, translation_service_instance):
        """Initialize with dependency injection for translation service"""
        self.translation_service = translation_service_instance
        self.engine_configs = {
            'opus_fast': {
                'name': 'Helsinki OPUS',
                'supported_pairs': ['en-fr', 'fr-en', 'en-jp', 'jp-en', 'jp-fr'],
                'model_mapping': {
                    'en-fr': 'HELSINKI_EN_FR',      
                    'fr-en': 'HELSINKI_FR_EN',      
                    'en-jp': 'HELSINKI_EN_JP',      
                    'jp-en': 'OPUS_JA_EN'           
                },
                'pivot_strategy': {
                    'pivot_lang': 'en',
                    'via_models': ['OPUS_JA_EN', 'HELSINKI_EN_FR'],
                    'applies_to': ['jp-fr']
                },
                'confidence': 0.80
            },
            'elan_quality': {
                'name': 'ELAN Specialist',
                'supported_pairs': ['jp-en', 'jp-fr', 'fr-en'], 
                'model_mapping': {
                    'jp-en': 'ELAN_JA_EN',          
                    'fr-en': 'ELAN_JA_EN'      
                },
                'pivot_strategy': {
                    'pivot_lang': 'en',
                    'via_models': ['ELAN_JA_EN', 'HELSINKI_EN_FR'],
                    'applies_to': ['jp-fr']
                },
                'confidence': 0.90
            },

            't5_versatile': {
                'name': 'mT5 Versatile',
                'supported_pairs': ['en-jp', 'jp-en', 'en-fr', 'fr-en', 'jp-fr'], 
                'model_mapping': {
                    'en-jp': 'T5_MULTILINGUAL',
                    'jp-en': 'T5_MULTILINGUAL',
                    'en-fr': 'T5_MULTILINGUAL',
                    'fr-en': 'T5_MULTILINGUAL',
                    'jp-fr': 'T5_MULTILINGUAL',
                },
                'confidence': 0.85,
            },
            'nllb_multilingual': {
                'name': 'NLLB Multilingual',
                'supported_pairs': ['en-jp', 'jp-en', 'en-fr', 'fr-en', 'jp-fr'], 
                'model_mapping': {
                    'en-jp': 'NLLB_200',
                    'jp-en': 'NLLB_200',
                    'en-fr': 'NLLB_200',
                    'fr-en': 'NLLB_200',
                    'jp-fr': 'NLLB_200',
                },
                'confidence': 0.92,
            }
        }

    async def translate_with_engine(self, text: str, source_lang: str, target_lang: str, engine_id: str) -> Dict:
        """Translate using a specific engine with clean routing"""
        try:
            if engine_id not in self.engine_configs:
                return {'engine': engine_id, 'error': 'Engine not found'}

            config = self.engine_configs[engine_id]
            start_time = datetime.now()

            # Check if we need pivot translation
            if self._needs_pivot_translation(config, source_lang, target_lang):
                translated_text = await self._translate_with_pivot(
                    text, source_lang, target_lang, config['pivot_strategy']
                )
            else:
                # Route to appropriate translation method
                pair = f"{source_lang.lower()}-{target_lang.lower()}"
                
                # Get model_to_use (e.g., 'T5_MULTILINGUAL', 'NLLB_200', 'HELSINKI_EN_FR')
                model_to_use = config['model_mapping'].get(pair)
                if not model_to_use:
                    raise ValueError(f"No model mapping found for engine '{engine_id}' and pair '{pair}'.")

                # Get the specific prefix or target language tag from translation_service's language_pair_models
                # This is essential for T5 (prefix) and NLLB (target_lang_tag)
                prefix_or_lang_tag = None
                # Fetching model_info from translation_service.language_pair_models using UPPERCASE pair for consistency
                model_info_from_ts = next(
                    (info for info in translation_service.language_pair_models.get(f"{source_lang.upper()}-{target_lang.upper()}", []) 
                     if info[0] == model_to_use),
                    None
                )
                if model_info_from_ts and len(model_info_from_ts) == 3: # Check if prefix/tag exists in tuple
                    prefix_or_lang_tag = model_info_from_ts[2]

                translated_text = translation_service.translate_by_model_type(
                    text.strip(), 
                    model_to_use, 
                    source_lang=source_lang.lower(), # Pass raw source lang (e.g., 'en')
                    target_lang=target_lang.lower(), # Pass raw target lang (e.g., 'jp')
                    target_lang_tag=prefix_or_lang_tag # Pass for NLLB's specific lang tag or T5's prefix
                )

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            if target_lang.upper() == 'JP':
                translated_text = detokenize_japanese(translated_text)

            return {
                'engine': engine_id,
                'text': translated_text,
                'confidence': config['confidence'],
                'processing_time': processing_time,
                'model': self._get_model_used(engine_id, source_lang, target_lang)
            }

        except Exception as e:
            return {'engine': engine_id, 'error': str(e)}

    def _needs_pivot_translation(self, config: dict, source_lang: str, target_lang: str) -> bool:
        """Determine if this translation needs to use pivot strategy"""
        if 'pivot_strategy' not in config:
            return False
        pair = f"{source_lang.lower()}-{target_lang.lower()}"
        applies_to = config['pivot_strategy'].get('applies_to', [])
        return pair in applies_to

    async def _translate_with_pivot(self, text: str, source_lang: str, target_lang: str, pivot_strategy: dict) -> str:
        """Generic pivot translation using strategy configuration"""
        try:
            pivot_models = pivot_strategy['via_models']
            if len(pivot_models) != 2:
                raise ValueError("Pivot strategy must specify exactly 2 models")

            first_model, second_model = pivot_models
            pivot_lang = pivot_strategy['pivot_lang']

            # First step: source -> pivot language (Marian models, no special lang args needed here)
            intermediate = self.translation_service.translate_by_model_type(text.strip(), first_model)

            if isinstance(intermediate, str) and "Translation failed" in intermediate:
                raise Exception(f"Pivot step 1 failed: {intermediate}")

            # Second step: pivot language -> target (Marian models, no special lang args needed here)
            final_translation = self.translation_service.translate_by_model_type(intermediate.strip(), second_model)

            if isinstance(final_translation, str) and "Translation failed" in final_translation:
                raise Exception(f"Pivot step 2 failed: {final_translation}")

            return final_translation

        except Exception as e:
            raise Exception(f"Pivot translation failed: {str(e)}")

    def get_available_engines_for_pair(self, source_lang: str, target_lang: str) -> List[str]:
        """Return only engines that can handle this language pair"""
        pair = f"{source_lang.lower()}-{target_lang.lower()}"
        available = []
        
        for engine_id, config in self.engine_configs.items():
            # Check if model paths exist for direct models for this specific pair
            model_key = config['model_mapping'].get(pair) # Get model_key specific to this pair from engine_config
            model_path_exists = False
            if model_key:
                # Check actual model path existence from translation_service
                model_path_exists = os.path.exists(self.translation_service.model_paths.get(model_key, ""))
            
            # Special handling for pivots
            is_pivot_available = self._can_handle_via_pivot(config, source_lang, target_lang)
            if is_pivot_available:
                 # Check if the underlying pivot models themselves are available
                 pivot_strategy = config['pivot_strategy']
                 model1_available = os.path.exists(self.translation_service.model_paths.get(pivot_strategy['via_models'][0], ""))
                 model2_available = os.path.exists(self.translation_service.model_paths.get(pivot_strategy['via_models'][1], ""))
                 if not (model1_available and model2_available):
                     is_pivot_available = False # Mark pivot as not available if its underlying models aren't
            
            # An engine is available if it supports the pair AND its model path exists, OR it's a valid pivot.
            if (pair in config['supported_pairs'] and model_path_exists) or is_pivot_available:
                available.append(engine_id)
        
        return available

    def _can_handle_via_pivot(self, config: dict, source_lang: str, target_lang: str) -> bool:
        """Check if engine can handle this pair via its configured pivot strategy"""
        if 'pivot_strategy' not in config:
            return False
        pair = f"{source_lang.lower()}-{target_lang.lower()}"
        applies_to = config['pivot_strategy'].get('applies_to', [])
        return pair in applies_to

    def _get_model_used(self, engine_id: str, source_lang: str, target_lang: str) -> str:
        """Get the model name used for this translation"""
        config = self.engine_configs.get(engine_id)
        if not config:
            return 'N/A'

        pair = f"{source_lang.lower()}-{target_lang.lower()}"

        # Check if pivot was used
        if self._needs_pivot_translation(config, source_lang, target_lang):
            pivot_models = config['pivot_strategy']['via_models']
            return f"{pivot_models[0]} + {pivot_models[1]} (Pivot)"

        # Check direct model mapping
        if 'model_mapping' in config:
            model = config['model_mapping'].get(pair)
            if model:
                return model

        # Check primary model key
        if 'model_key' in config:
            return config['model_key']

        return 'UNKNOWN_MODEL_ROUTING'

    async def translate_multi_engine(self, text: str, source_lang: str, target_lang: str, engines: List[str] = None) -> List[Dict]:
        """Clean multi-engine translation with proper routing"""
        if engines is None:
            engines = self.get_available_engines_for_pair(source_lang, target_lang)

        # Filter to only available engines for this language pair
        available_engines = self.get_available_engines_for_pair(source_lang, target_lang)
        valid_engines = [e for e in engines if e in available_engines]

        if not valid_engines:
            return [{'error': f'No valid engines were selected or available for {source_lang}-{target_lang}. Available: {available_engines}'}]

        tasks = []
        for engine in valid_engines:
            task = self.translate_with_engine(text, source_lang, target_lang, engine)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    'engine': valid_engines[i] if i < len(valid_engines) else 'unknown',
                    'error': str(result)
                })
            else:
                final_results.append(result)

        return final_results

    @property
    def engines(self):
        """Property to maintain compatibility with existing code"""
        return {engine_id: None for engine_id in self.engine_configs.keys()}

# Helper function to get the correct model for each language pair
def get_model_for_language_pair(source_lang: str, target_lang: str) -> str:
    """Get the appropriate model for a language pair with consistent mapping."""
    pair = f"{source_lang.lower()}-{target_lang.lower()}"
    
    # This mapping is used for SINGLE_ENGINE requests.
    # It should reflect a good default or primary model for each pair.
    model_mapping = {
        'en-jp': 'HELSINKI_EN_JP', # Default single for EN-JP
        'jp-en': 'ELAN_JA_EN', # Default single for JP-EN
        'en-fr': 'HELSINKI_EN_FR',
        'fr-en': 'HELSINKI_FR_EN',
        'jp-fr': 'PIVOT_ELAN_HELSINKI',  # Default single for JP-FR
        
        # WMT variants
        'jpn-eng': 'ELAN_JA_EN',
        'eng-jpn': 'HELSINKI_EN_JP',
        'eng-fra': 'HELSINKI_EN_FR',
        'fra-eng': 'HELSINKI_FR_EN',
    }
    
    # Fallback to a common Marian model if no specific mapping,
    # or the first model defined in language_pair_models in translation_service.
    return model_mapping.get(pair, 'HELSINKI_EN_FR')

# Initialize the multi-engine service instance
multi_engine_service = CleanMultiEngineService(translation_service)

class HumanFeedbackService:
    def process_translation_edit(self, original_translation: str, human_edit: str, source_text: str, string_id: str, reference: Optional[str] = None):
        print(f"Processed human edit feedback for string {string_id}")

    def process_annotation(self, source: str, translation: str, quality_score: float, annotations: List[dict]):
        print(f"Processed annotation feedback for source: {source}")


feedback_service = HumanFeedbackService()

# --- FastAPI Endpoints ---

@app.middleware("http")
async def database_middleware(request: Request, call_next):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        response = await call_next(request)
        return response
    except Exception as e:
        logging.error(f"Middleware caught error: {e}")
        raise e

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to catch all unhandled exceptions"""
    
    # Log the full error with traceback
    logging.error(f"Global exception handler caught: {exc}")
    logging.error(f"Request: {request.method} {request.url}")
    logging.error(f"Traceback: {traceback.format_exc()}")
    
    # Handle specific exception types
    if "prisma" in str(exc).lower() or "database" in str(exc).lower():
        return JSONResponse(
            status_code=500,
            content={
                "error": "Database operation failed",
                "detail": "A database error occurred. Please try again later.",
                "type": "database_error"
            }
        )
    
    # Handle Prisma connection errors
    if "not connected" in str(exc).lower():
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service temporarily unavailable",
                "detail": "Database connection issue. Please try again later.",
                "type": "connection_error"
            }
        )
    
    # Handle enum/validation errors
    if "enum" in str(exc).lower() or "AttributeError" in str(type(exc).__name__):
        return JSONResponse(
            status_code=400,
            content={
                "error": "Invalid data",
                "detail": "The provided data contains invalid values.",
                "type": "validation_error"
            }
        )
    
    # Generic error for everything else
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Please try again later.",
            "type": "server_error"
        }
    )

@app.get("/", tags=["Health & Status"])
async def root():
    return {"message": "Translation Management API is running", "status": "healthy"}

@app.post("/api/translation-preferences", tags=["Translation Requests"])
async def track_translation_preference(preference_data: dict):
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
        print(f"Error in translation-preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_human_preferences_data(date_filter, lang_filter):
    """Get human preference data - FIXED for Python Prisma"""
    try:
        # Get all engine preferences (no group_by with aggregations)
        all_prefs = await prisma.enginepreference.find_many(where={**date_filter})
        
        # Manual aggregation in Python
        engine_stats = {}
        for pref in all_prefs:
            key = f"{pref.selectedEngine}_{pref.sourceLanguage}_{pref.targetLanguage}_{pref.preferenceReason or 'unknown'}"
            if key not in engine_stats:
                engine_stats[key] = {
                    "engine": pref.selectedEngine,
                    "sourceLanguage": pref.sourceLanguage,
                    "targetLanguage": pref.targetLanguage,
                    "preferenceReason": pref.preferenceReason or "unknown",
                    "count": 0,
                    "ratings": [],
                    "satisfactions": []
                }
            
            engine_stats[key]["count"] += 1
            if pref.rating: engine_stats[key]["ratings"].append(pref.rating)
            if pref.overallSatisfaction: engine_stats[key]["satisfactions"].append(pref.overallSatisfaction)
        
        # Convert to expected format
        engine_preferences = []
        for stats in engine_stats.values():
            avg_rating = sum(stats["ratings"]) / len(stats["ratings"]) if stats["ratings"] else 0
            avg_satisfaction = sum(stats["satisfactions"]) / len(stats["satisfactions"]) if stats["satisfactions"] else 0
            
            engine_preferences.append({
                "engine": stats["engine"],
                "selectionCount": stats["count"],
                "avgRating": avg_rating,
                "languagePair": f"{stats['sourceLanguage']}-{stats['targetLanguage']}",
                "preferenceReason": stats["preferenceReason"],
                "overallSatisfaction": avg_satisfaction
            })
        
        # Get reviewer behavior
        all_strings = await prisma.translationstring.find_many(
            where={**date_filter, "reviewerExpertise": {"not": None}}
        )
        
        reviewer_stats = {}
        for string in all_strings:
            key = f"{string.reviewerExpertise}_{string.approvalType or 'unknown'}"
            if key not in reviewer_stats:
                reviewer_stats[key] = {
                    "reviewerExpertise": string.reviewerExpertise,
                    "approvalType": string.approvalType or "unknown",
                    "times": [],
                    "cognitive_loads": [],
                    "count": 0
                }
            
            reviewer_stats[key]["count"] += 1
            if string.timeToReview: reviewer_stats[key]["times"].append(string.timeToReview)
            if string.cognitiveLoad: reviewer_stats[key]["cognitive_loads"].append(string.cognitiveLoad)
        
        reviewer_behavior = []
        for stats in reviewer_stats.values():
            avg_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
            avg_cognitive = sum(stats["cognitive_loads"]) / len(stats["cognitive_loads"]) if stats["cognitive_loads"] else 0
            
            reviewer_behavior.append({
                "reviewerExpertise": stats["reviewerExpertise"],
                "avgTimeToReview": avg_time,
                "avgCognitiveLoad": avg_cognitive,
                "approvalType": stats["approvalType"],
                "count": stats["count"]
            })
        
        # Get preference reasons
        reason_stats = {}
        for pref in all_prefs:
            if pref.preferenceReason:
                reason = pref.preferenceReason
                if reason not in reason_stats:
                    reason_stats[reason] = {"count": 0, "satisfactions": []}
                reason_stats[reason]["count"] += 1
                if pref.overallSatisfaction:
                    reason_stats[reason]["satisfactions"].append(pref.overallSatisfaction)
        
        preference_reasons = []
        for reason, data in reason_stats.items():
            avg_satisfaction = sum(data["satisfactions"]) / len(data["satisfactions"]) if data["satisfactions"] else 0
            preference_reasons.append({
                "reason": reason,
                "count": data["count"],
                "avgSatisfaction": avg_satisfaction
            })
        
        return {
            "enginePreferences": engine_preferences,
            "reviewerBehavior": reviewer_behavior,
            "preferenceReasons": preference_reasons
        }
        
    except Exception as e:
        logger.error(f"Error fetching human preferences data: {e}")
        return {"enginePreferences": [], "reviewerBehavior": [], "preferenceReasons": []}

async def get_annotations_data(date_filter, lang_filter):
    """Get annotation data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Get all annotations
        all_annotations = await prisma.annotation.find_many(
            include={
                "translationString": {
                    "include": {
                        "translationRequest": True,
                        "modelOutputs": True
                    }
                }
            }
        )
        
        logger.info(f"Found {len(all_annotations)} annotations for dashboard")
        
        # Manual aggregation for error heatmap
        error_stats = {}
        severity_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        
        for annotation in all_annotations:
            # Count severity
            if annotation.severity in severity_counts:
                severity_counts[annotation.severity] += 1
            
            # Get model name
            model_name = "unknown"
            if annotation.translationString and annotation.translationString.translationRequest:
                if annotation.translationString.translationRequest.mtModel:
                    model_name = str(annotation.translationString.translationRequest.mtModel)
            
            if annotation.translationString and annotation.translationString.modelOutputs:
                if len(annotation.translationString.modelOutputs) > 0:
                    model_name = annotation.translationString.modelOutputs[0].modelName
            
            # Error heatmap
            error_type = getattr(annotation, 'errorType', None) or 'general'
            key = f"{model_name}_{annotation.category}_{error_type}_{annotation.severity}"
            
            if key not in error_stats:
                error_stats[key] = {
                    "model": model_name,
                    "category": annotation.category,
                    "errorType": error_type,
                    "severity": annotation.severity,
                    "count": 0
                }
            error_stats[key]["count"] += 1
        
        logger.info(f"Severity counts: {severity_counts}")
        logger.info(f"Error stats keys: {len(error_stats)}")
        
        # Calculate pain index
        severity_weights = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        error_heatmap = []
        for stats in error_stats.values():
            pain_index = stats["count"] * severity_weights.get(stats["severity"], 1)
            error_heatmap.append({
                **stats,
                "painIndex": pain_index
            })
        
        # Severity breakdown 
        severity_breakdown = []
        for severity, count in severity_counts.items():
            if count > 0:  # Only include severities that have data
                severity_breakdown.append({
                    "severity": severity,
                    "count": count,
                    "model": "all"
                })
        
        logger.info(f"Returning {len(severity_breakdown)} severity items and {len(error_heatmap)} heatmap items")
        
        return {
            "errorHeatmap": error_heatmap,
            "severityBreakdown": severity_breakdown,
            "spanAnalysis": []  # Keep empty for now
        }
        
    except Exception as e:
        logger.error(f"Error in get_annotations_data: {e}")
        import traceback
        traceback.print_exc()
        return {"errorHeatmap": [], "severityBreakdown": [], "spanAnalysis": []}

async def get_multi_engine_data(date_filter, lang_filter):
    """Get multi-engine and pivot translation data"""
    try:
        # Selection trends
        selection_trends_raw = await prisma.enginepreference.group_by(
            by=["selectionMethod", "modelCombination"],
            _count={"id": True},
            where={**date_filter, **lang_filter}
        )
        
        selection_trends = []
        for trend in selection_trends_raw:
            selection_trends.append({
                "date": datetime.now().strftime("%Y-%m-%d"),  # Simplified for now
                "selectionMethod": trend["selectionMethod"] or "unknown",
                "count": trend["_count"]["id"],
                "modelCombination": trend["modelCombination"] or "single"
            })
        
        # Pivot quality analysis
        pivot_strings = await prisma.translationstring.find_many(
            where={
                **date_filter,
                "translationType": "PIVOT",
                "intermediateTranslation": {"not": None}
            },
            include={"qualityMetrics": True}
        )
        
        pivot_quality = []
        for string in pivot_strings:
            if string.qualityMetrics:
                for metric in string.qualityMetrics:
                    pivot_quality.append({
                        "modelCombination": string.selectedModelCombination or "unknown",
                        "directQuality": 0,  # Would need direct comparison
                        "pivotQuality": metric.metricXScore or 0,
                        "intermediateQuality": 0  # Would need intermediate evaluation
                    })
        
        # Inter-rater agreement (simplified)
        inter_rater_raw = await prisma.annotation.group_by(
            by=["reviewer"],
            _count={"id": True},
            where={**date_filter, "reviewer": {"not": None}}
        )
        
        inter_rater = []
        for rater in inter_rater_raw:
            inter_rater.append({
                "annotatorPair": f"{rater['reviewer']}-system",
                "agreement": 0.8,  # Placeholder - would need complex calculation
                "category": "overall"
            })
        
        return {
            "selectionTrends": selection_trends,
            "pivotQuality": pivot_quality,
            "interRaterAgreement": inter_rater
        }
    except Exception as e:
        logger.error(f"Error fetching multi-engine data: {e}")
        return {"selectionTrends": [], "pivotQuality": [], "interRaterAgreement": []}

async def get_quality_scores_data(date_filter, lang_filter):
    """Get quality scores data with actual correlations"""
    try:
        # Get quality metrics with actual scores
        quality_metrics = await prisma.qualitymetrics.find_many(
            where={
                **date_filter,
                "hasReference": True,
                "bleuScore": {"not": None},
                "cometScore": {"not": None},
                "terScore": {"not": None}
            }
        )

        if not quality_metrics:
            return {
                "evaluationModes": [],
                "correlationMatrix": [],
                "scoreDistribution": []
            }

        # Calculate actual correlations
        import statistics
        
        # Extract scores for correlation calculation
        bleu_scores = [m.bleuScore for m in quality_metrics if m.bleuScore is not None]
        comet_scores = [m.cometScore for m in quality_metrics if m.cometScore is not None]
        ter_scores = [m.terScore for m in quality_metrics if m.terScore is not None]
        metricx_scores = [m.metricXScore for m in quality_metrics if m.metricXScore is not None]

        correlations = []
        
        # Calculate correlations between metrics
        def calculate_correlation(x_vals, y_vals):
            if len(x_vals) < 2 or len(y_vals) < 2:
                return 0.0
            
            # Simple Pearson correlation
            mean_x = statistics.mean(x_vals)
            mean_y = statistics.mean(y_vals)
            
            numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
            sum_sq_x = sum((x - mean_x) ** 2 for x in x_vals)
            sum_sq_y = sum((y - mean_y) ** 2 for y in y_vals)
            
            denominator = (sum_sq_x * sum_sq_y) ** 0.5
            return numerator / denominator if denominator != 0 else 0.0

        # Calculate all metric pairs
        metric_pairs = [
            ("BLEU", "COMET", bleu_scores, comet_scores),
            ("BLEU", "TER", bleu_scores, ter_scores),
            ("COMET", "TER", comet_scores, ter_scores),
            ("BLEU", "MetricX", bleu_scores, metricx_scores),
            ("COMET", "MetricX", comet_scores, metricx_scores),
            ("TER", "MetricX", ter_scores, metricx_scores)
        ]

        for metric1, metric2, scores1, scores2 in metric_pairs:
            if scores1 and scores2:
                correlation = calculate_correlation(scores1, scores2)
                correlations.append({
                    "metric1": metric1,
                    "metric2": metric2,
                    "correlation": correlation,
                    "pValue": 0.05  # Placeholder
                })

        return {
            "evaluationModes": [
                {"mode": "Reference-based", "count": len(quality_metrics), "avgScore": statistics.mean(bleu_scores) if bleu_scores else 0},
                {"mode": "Reference-free", "count": len(metricx_scores), "avgScore": statistics.mean(metricx_scores) if metricx_scores else 0}
            ],
            "correlationMatrix": correlations,
            "scoreDistribution": [
                {"metric": "BLEU", "scores": bleu_scores},
                {"metric": "COMET", "scores": comet_scores},
                {"metric": "TER", "scores": ter_scores}
            ]
        }

    except Exception as e:
        print(f"Error in get_quality_scores_data: {e}")
        return {
            "evaluationModes": [],
            "correlationMatrix": [],
            "scoreDistribution": []
        }

async def get_operational_data(date_filter, lang_filter):
    """Get operational data - FIXED for Python Prisma"""
    try:
        # Get all model outputs
        all_outputs = await prisma.modeloutput.find_many(where={**date_filter})
        
        # Manual aggregation for processing times
        processing_stats = {}
        for output in all_outputs:
            key = f"{output.modelName}_{output.engineName}"
            if key not in processing_stats:
                processing_stats[key] = {
                    "model": output.modelName,
                    "engineType": output.engineName,
                    "times": [],
                    "count": 0
                }
            
            processing_stats[key]["count"] += 1
            if output.processingTimeMs:
                processing_stats[key]["times"].append(output.processingTimeMs)
        
        processing_times = []
        for stats in processing_stats.values():
            avg_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
            processing_times.append({
                "model": stats["model"],
                "engineType": stats["engineType"],
                "wordCountBucket": "medium",
                "avgProcessingTime": avg_time,
                "count": stats["count"]
            })
        
        # System health and model utilization (empty for now since local_models is 0)
        return {
            "processingTimes": processing_times,
            "systemHealth": [],
            "modelUtilization": []
        }
        
    except Exception as e:
        logger.error(f"Error fetching operational data: {e}")
        return {"processingTimes": [], "systemHealth": [], "modelUtilization": []}

async def get_tm_glossary_data(date_filter, lang_filter):
    """Get translation memory and glossary data"""
    try:
        # TM impact analysis
        tm_strings = await prisma.translationstring.find_many(
            where={**date_filter, "tmMatchPercentage": {"not": None}},
            include={"qualityMetrics": True}
        )
        
        tm_impact = {}
        for string in tm_strings:
            match_bucket = "high" if string.tmMatchPercentage >= 90 else "medium" if string.tmMatchPercentage >= 70 else "low"
            if match_bucket not in tm_impact:
                tm_impact[match_bucket] = {
                    "matchPercentage": match_bucket,
                    "avgQualityScore": 0,
                    "timeSaved": 0,
                    "approvalRate": 0,
                    "count": 0,
                    "approved": 0
                }
            
            tm_impact[match_bucket]["count"] += 1
            if string.isApproved:
                tm_impact[match_bucket]["approved"] += 1
            
            if string.qualityMetrics:
                for metric in string.qualityMetrics:
                    if metric.metricXScore:
                        tm_impact[match_bucket]["avgQualityScore"] += metric.metricXScore
        
        # Calculate averages and rates
        for bucket in tm_impact.values():
            if bucket["count"] > 0:
                bucket["avgQualityScore"] /= bucket["count"]
                bucket["approvalRate"] = bucket["approved"] / bucket["count"]
                bucket["timeSaved"] = bucket["count"] * 30  # Estimated seconds saved
        
        # Glossary usage
        glossary_usage_raw = await prisma.glossaryterm.group_by(
            by=["term"],
            _count={"id": True},
            where={"isActive": True, "usageCount": {"gt": 0}},
            order_by={"usageCount": "desc"},
            take=20
        )
        
        glossary_usage = []
        for usage in glossary_usage_raw:
            glossary_usage.append({
                "term": usage["term"],
                "usageCount": usage["_count"]["id"],
                "overrideRate": 0.1,  # Placeholder
                "qualityImpact": 0.05  # Placeholder
            })
        
        # Term overrides (placeholder)
        term_overrides = []
        
        return {
            "tmImpact": list(tm_impact.values()),
            "glossaryUsage": glossary_usage,
            "termOverrides": term_overrides
        }
    except Exception as e:
        logger.error(f"Error fetching TM/glossary data: {e}")
        return {"tmImpact": [], "glossaryUsage": [], "termOverrides": []}

async def get_model_performance_data(date_filter, lang_filter):
    """Get actual model performance leaderboard and trends from database"""
    try:
        # Get quality metrics with translation request data
        quality_metrics = await prisma.qualitymetrics.find_many(
            where={
                **date_filter,
                "hasReference": True,  # Only post-edited translations
                "bleuScore": {"not": None}
            },
            include={
                "translationRequest": {
                    "include": {
                        "translationStrings": True
                    }
                }
            }
        )

        model_stats = {}
        performance_over_time = []
        
        for metric in quality_metrics:
            if metric.translationRequest:
                model_name = str(metric.translationRequest.mtModel) if metric.translationRequest.mtModel else "unknown"
                
                # Collect stats for leaderboard
                if model_name not in model_stats:
                    model_stats[model_name] = {
                        "bleu_scores": [],
                        "comet_scores": [],
                        "ter_scores": [],
                        "metricx_scores": [],
                        "total_translations": 0
                    }

                model_stats[model_name]["total_translations"] += 1
                if metric.bleuScore: model_stats[model_name]["bleu_scores"].append(metric.bleuScore)
                if metric.cometScore: model_stats[model_name]["comet_scores"].append(metric.cometScore)
                if metric.terScore: model_stats[model_name]["ter_scores"].append(metric.terScore)
                if metric.metricXScore: model_stats[model_name]["metricx_scores"].append(metric.metricXScore)
                
                # Collect performance over time data
                performance_over_time.append({
                    "date": metric.createdAt.strftime("%Y-%m-%d"),
                    "model": model_name,
                    "bleuScore": metric.bleuScore or 0,
                    "cometScore": metric.cometScore or 0,
                    "metricXScore": metric.metricXScore or 0,
                    "translationCount": 1,
                    "requestId": metric.translationRequestId
                })

        # Build leaderboard
        leaderboard = []
        for model, stats in model_stats.items():
            if stats["total_translations"] > 0:
                avg_bleu = sum(stats["bleu_scores"]) / len(stats["bleu_scores"]) if stats["bleu_scores"] else 0
                avg_comet = sum(stats["comet_scores"]) / len(stats["comet_scores"]) if stats["comet_scores"] else 0
                avg_ter = sum(stats["ter_scores"]) / len(stats["ter_scores"]) if stats["ter_scores"] else 0
                avg_metricx = sum(stats["metricx_scores"]) / len(stats["metricx_scores"]) if stats["metricx_scores"] else 0

                leaderboard.append({
                    "model": model,
                    "engineType": get_engine_type_from_model(model),
                    "avgBleu": avg_bleu,
                    "avgComet": avg_comet,
                    "avgTer": avg_ter,
                    "avgMetricX": avg_metricx,
                    "totalTranslations": stats["total_translations"],
                    "confidenceInterval": {
                        "bleuLow": max(0, avg_bleu - 0.05),
                        "bleuHigh": min(1, avg_bleu + 0.05),
                        "cometLow": max(0, avg_comet - 0.05),
                        "cometHigh": min(1, avg_comet + 0.05)
                    }
                })

        return {
            "leaderboard": sorted(leaderboard, key=lambda x: x["avgMetricX"], reverse=True),
            "performanceOverTime": performance_over_time[-50:],  # Last 50 entries
            "modelComparison": []
        }

    except Exception as e:
        logger.error(f"Error fetching model performance data: {e}")
        return {"leaderboard": [], "performanceOverTime": [], "modelComparison": []}

def get_engine_type_from_model(model_name):
    """Map model name to engine type"""
    engine_mapping = {
        "HELSINKI_EN_JP": "opus_fast",
        "OPUS_EN_JP": "opus_fast", 
        "ELAN_JA_EN": "elan_specialist",
        "NLLB_200": "nllb_multilingual", 
        "T5_BASE": "t5_versatile", 
        "T5_MULTILINGUAL": "t5_versatile", 
        "PIVOT_JP_EN_FR": "pivot_elan_helsinki",
    }
    return engine_mapping.get(model_name, "unknown")

def process_leaderboard_data(leaderboard_query):
    """Process raw leaderboard data into expected format"""
    processed = []
    for item in leaderboard_query:
        processed.append({
            "model": item["translationString"]["translationRequest"]["mtModel"],
            "engineType": "unknown",  # Would need to map from model to engine type
            "avgBleu": item["_avg"]["bleuScore"] or 0,
            "avgComet": item["_avg"]["cometScore"] or 0,
            "avgTer": item["_avg"]["terScore"] or 0,
            "avgMetricX": item["_avg"]["metricXScore"] or 0,
            "totalTranslations": item["_count"]["id"],
            "confidenceInterval": {
                "bleuLow": (item["_avg"]["bleuScore"] or 0) - 0.05,
                "bleuHigh": (item["_avg"]["bleuScore"] or 0) + 0.05,
                "cometLow": (item["_avg"]["cometScore"] or 0) - 0.05,
                "cometHigh": (item["_avg"]["cometScore"] or 0) + 0.05
            }
        })
    return processed

def process_time_series_data(time_series_query):
    """Process time series data for performance over time"""
    processed = []
    for item in time_series_query:
        processed.append({
            "date": item["createdAt"].strftime("%Y-%m-%d"),
            "model": item["translationString"]["translationRequest"]["mtModel"],
            "bleuScore": item["bleuScore"] or 0,
            "cometScore": item["cometScore"] or 0,
            "metricXScore": item["metricXScore"] or 0,
            "translationCount": 1
        })
    return processed

@app.post("/api/translation-requests/triple-output", tags=["Translation Requests"])
async def create_triple_output_translation_request(request_data: TranslationRequestCreate):
    """Create translation request with exactly 3 outputs per language pair"""
    try:
        # Define preferred engines for triple output, including T5 and NLLB
        # Order matters here for selection
        engines_per_pair_preference = {
            'en-jp': ['opus_fast', 't5_versatile', 'nllb_multilingual', 'elan_quality'], # Example preference order
            'jp-en': ['opus_fast', 'elan_quality', 't5_versatile', 'nllb_multilingual'],
            'en-fr': ['opus_fast', 't5_versatile', 'nllb_multilingual', 'elan_quality'],
            'fr-en': ['opus_fast', 't5_versatile', 'nllb_multilingual', 'elan_quality'],
            'jp-fr': ['opus_fast', 'elan_quality', 't5_versatile', 'nllb_multilingual'] # Adjust if pivot is primary
        }

        # Get all engines that *actually support* the given pair and whose models exist
        all_possible_engines = multi_engine_service.get_available_engines_for_pair(
            request_data.sourceLanguage, request_data.targetLanguages[0] # Assuming only one target for triple-output
        )
        
        # Sort these by the preferred order and take up to the first 3 that are available
        selected_engines_for_triple = sorted(
            all_possible_engines, 
            key=lambda x: engines_per_pair_preference.get(request_data.languagePair.lower(), []).index(x) 
            if x in engines_per_pair_preference.get(request_data.languagePair.lower(), []) else float('inf') # Put non-preferred at end
        )[:3] # Take top 3 after sorting

        if not selected_engines_for_triple:
            raise HTTPException(status_code=400, detail=f"No suitable engines found for {request_data.languagePair} for triple output.")

        multi_request = MultiEngineTranslationRequestCreate(
            sourceLanguage=request_data.sourceLanguage,
            targetLanguages=request_data.targetLanguages,
            languagePair=request_data.languagePair,
            wordCount=request_data.wordCount,
            fileName=request_data.fileName,
            sourceTexts=request_data.sourceTexts,
            engines=selected_engines_for_triple # Use the selected 3 engines
        )

        return await create_multi_engine_translation_request(multi_request)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create triple-output request: {str(e)}")

@app.get("/api/health", tags=["Health & Status"])
async def health_check():
    try:
        if prisma.is_connected():
            count = await prisma.translationmemory.count()
            db_status = f"Connected - {count} TM entries"
        else:
            await prisma.connect() # Attempt to connect if not connected
            count = await prisma.translationmemory.count()
            db_status = f"Connected - {count} TM entries"
    except Exception as e:
        db_status = f"Error: {str(e)}"

    return {
        "status": "healthy",
        "metricx_available": metricx_service is not None,
        "translation_service_available": translation_service is not None,
        "local_engines_available": True, # Always true as CleanMultiEngineService is instantiated
        "database_status": db_status,
        "endpoints": {
            "metricx": True,
            "translation_requests": True,
            "quality_metrics": True,
            "translation_processing": True,
            "human_feedback": True,
            "command_center": True,
            "multi_engine": True,
            "fuzzy_matching": True,
            "wmt_benchmark": True
        },
        "available_engines": list(multi_engine_service.engines.keys()) # Dynamically get from CleanMultiEngineService
    }

# Test database endpoint 
@app.get("/api/test-database", tags=["Debugging"])
async def test_database():
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Test creating a TM entry
        from prisma.enums import QualityLabel as QualityEnum
        test_entry = await prisma.translationmemory.create(
            data={
                "sourceText": "Test source",
                "targetText": "Test target",
                "sourceLanguage": "EN",
                "targetLanguage": "FR",
                "domain": "test",
                "quality": QualityEnum.HIGH, # Use enum
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
            "total_entries": count - 1
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

@app.post("/api/wmt/create-request", tags=["WMT Benchmarks"])
async def create_wmt_benchmark_request(
    language_pair: str = Query(...),
    sample_size: int = Query(10)
):
    """Create a WMT benchmark translation request"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        print(f"Creating WMT benchmark request for {language_pair} with {sample_size} samples")
        
        from prisma.enums import MTModel
        
        # Map language pairs to models
        model_mapping_enum = {
            'jpn-eng': MTModel.ELAN_MT_JP_EN,
            'eng-jpn': MTModel.MARIAN_MT_EN_JP,
            'eng-fra': MTModel.MARIAN_MT_EN_FR,
            'fra-eng': MTModel.MARIAN_MT_FR_EN,
            'jpn-fra': MTModel.PIVOT_JP_EN_FR
        }
        
        mt_model_enum_val = model_mapping_enum.get(language_pair, MTModel.MARIAN_MT_EN_FR) # Changed default fallback
        
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
                "wordCount": sample_size * 20,  # Estimate
                "fileName": f"wmt_benchmark_{language_pair}_{sample_size}.txt",
                "mtModel": mt_model_enum_val,
                "status": "IN_PROGRESS",
                "requestType": "WMT_BENCHMARK"
            }
        )
        
        # Create sample WMT test data (using static list for example)
        sample_texts = [
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
        for i, source_text in enumerate(sample_texts[:sample_size]):
            try:
                # Use get_model_for_language_pair to get the model string key
                model_key_for_wmt = get_model_for_language_pair(source_lang, target_lang)

                translated_text = ""
                # Special handling for JP-FR for pivot
                if model_key_for_wmt == 'PIVOT_ELAN_HELSINKI':
                    translated_text = multi_engine_service._translate_pivot_elan_helsinki(source_text.strip())
                else:
                    # Direct translation using the specified model
                    # Ensure source_text is stripped for consistency with other methods
                    src_lang_code_for_ts = source_lang.lower()
                    tgt_lang_code_for_ts = target_lang.lower()
                    
                    # Fetch prefix/lang_tag from translation_service.language_pair_models if available
                    prefix_or_lang_tag = None
                    model_info_from_ts = next(
                        (info for info in translation_service.language_pair_models.get(f"{source_lang.upper()}-{target_lang.upper()}", []) 
                        if info[0] == model_key_for_wmt),
                        None
                    )
                    if model_info_from_ts and len(model_info_from_ts) == 3:
                        prefix_or_lang_tag = model_info_from_ts[2]

                    translated_text = translation_service.translate_by_model_type(
                        source_text.strip(), 
                        model_key_for_wmt,
                        source_lang=src_lang_code_for_ts, # Pass lowercase for NLLB
                        target_lang=tgt_lang_code_for_ts, # Pass lowercase for NLLB
                        target_lang_tag=prefix_or_lang_tag # Pass for NLLB/T5 prefixing in translation_service
                    )
                
                if target_lang_code == 'JP':
                    translated_text = detokenize_japanese(translated_text)
                
                # Create translation string
                await prisma.translationstring.create(
                    data={
                        "sourceText": source_text,
                        "translatedText": translated_text,
                        "targetLanguage": target_lang_code,
                        "status": "REVIEWED",
                        "isApproved": False,
                        "processingTimeMs": 1000,  # Mock processing time
                        "translationRequestId": wmt_request.id,
                        "fuzzyMatches": "[]"
                    }
                )
                
            except Exception as e:
                print(f"Failed to translate WMT sample {i}: {e}")
                # Create failed translation
                await prisma.translationstring.create(
                    data={
                        "sourceText": source_text,
                        "translatedText": f"Translation failed: {str(e)}",
                        "targetLanguage": target_lang_code,
                        "status": "DRAFT",
                        "isApproved": False,
                        "processingTimeMs": 0,
                        "translationRequestId": wmt_request.id,
                        "fuzzyMatches": "[]"
                    }
                )
        
        # Update request status
        await prisma.translationrequest.update(
            where={"id": wmt_request.id},
            data={"status": "COMPLETED"}
        )
        
        return {
            "success": True,
            "request_id": wmt_request.id,
            "language_pair": language_pair,
            "sample_size": sample_size,
            "message": f"WMT benchmark request created for {language_pair}"
        }
        
    except Exception as e:
        print(f"Failed to create WMT request: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create WMT benchmark request: {str(e)}")

@app.get("/api/wmt/requests", tags=["WMT Benchmarks"])
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
        print(f"Failed to fetch WMT requests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch WMT requests: {str(e)}")

@app.get("/api/wmt/results/{request_id}", tags=["WMT Benchmarks"])
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
        print(f"Failed to fetch WMT results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch WMT results: {str(e)}")

# Fuzzy matching endpoint with database 
@app.get("/api/translation-memory/fuzzy-matches", tags=["Translation Requests"])
async def get_fuzzy_matches(
    source_text: str, 
    source_language: str, 
    target_language: str,
    threshold: float = 0.6
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

# Command Center endpoints with database operations
@app.post("/api/translation-memory", tags=["Data Management"])
async def create_translation_memory(tm_data: TranslationMemoryCreate):
    try:
        if not prisma.is_connected():
            await prisma.connect()

        from prisma.enums import MemoryQuality
        
        quality_mapping = {
            'high': MemoryQuality.HIGH,
            'medium': MemoryQuality.MEDIUM, 
            'low': MemoryQuality.LOW,
            'HIGH': MemoryQuality.HIGH,
            'MEDIUM': MemoryQuality.MEDIUM,
            'LOW': MemoryQuality.LOW
        }
        
        # Safe enum conversion with fallback
        quality_key = tm_data.quality.strip()
        quality_enum_val = quality_mapping.get(quality_key, MemoryQuality.MEDIUM)
        
        print(f"Creating TM entry: quality '{tm_data.quality}' -> {quality_enum_val}")

        tm_entry = await prisma.translationmemory.create(
            data={
                "sourceText": tm_data.sourceText,
                "targetText": tm_data.targetText,
                "sourceLanguage": tm_data.sourceLanguage.upper(),
                "targetLanguage": tm_data.targetLanguage.upper(),
                "domain": tm_data.domain or "general",
                "quality": quality_enum_val,
                "createdFrom": "manual",
                "usageCount": 0
            }
        )

        return {"success": True, "data": tm_entry}
        
    except Exception as e:
        print(f"TM Creation Error: {e}")
        print(f"TM Data received: {tm_data}")
        print(f"Available enum values: {list(MemoryQuality.__members__.keys())}")
        raise HTTPException(status_code=500, detail=f"Failed to create translation memory: {str(e)}")

@app.get("/api/translation-memory", tags=["Data Management"])
async def get_translation_memory():
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        tm_entries = await prisma.translationmemory.find_many()
        # Sort in Python
        tm_entries.sort(key=lambda x: x.lastUsed if x.lastUsed else datetime.min, reverse=True) # Handle None for lastUsed
        return tm_entries
    except Exception as e:
        print(f"Database error: {e}")
        return []

@app.delete("/api/translation-memory/{tm_id}", tags=["Data Management"])
async def delete_translation_memory(tm_id: str):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        await prisma.translationmemory.delete(where={"id": tm_id})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete translation memory: {str(e)}")

@app.post("/api/glossary", tags=["Data Management"])
async def create_glossary_term(term_data: GlossaryTermCreate):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        glossary_entry = await prisma.glossaryterm.create(
            data={
                "term": term_data.term,
                "translation": term_data.translation,
                "sourceLanguage": term_data.sourceLanguage,
                "targetLanguage": term_data.targetLanguage,
                "domain": term_data.domain,
                "definition": term_data.definition,
                "usageCount": 0
            }
        )
        
        return {"success": True, "data": glossary_entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create glossary term: {str(e)}")

@app.get("/api/glossary", tags=["Data Management"])
async def get_glossary():
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        glossary_terms = await prisma.glossaryterm.find_many()
        # Sort in Python
        glossary_terms.sort(key=lambda x: x.term)
        return glossary_terms
    except Exception as e:
        print(f"Database error: {e}")
        return []

@app.delete("/api/glossary/{term_id}", tags=["Data Management"])
async def delete_glossary_term(term_id: str):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        await prisma.glossaryterm.delete(where={"id": term_id})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete glossary term: {str(e)}")

@app.post("/api/do-not-translate", tags=["Data Management"])
async def create_dnt_item(dnt_data: DoNotTranslateCreate):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Convert category to enum format
        from prisma.enums import DoNotTranslateCategory
        category_enum_val = DoNotTranslateCategory(dnt_data.category.upper().replace(' ', '_')) if dnt_data.category.upper().replace(' ', '_') in DoNotTranslateCategory.__members__ else DoNotTranslateCategory.OTHER

        dnt_entry = await prisma.donottranslateitem.create(
            data={
                "text": dnt_data.text,
                "category": category_enum_val, # Use enum value
                "languages": dnt_data.languages,
                "notes": dnt_data.notes,
                "usageCount": 0
            }
        )
        
        return {"success": True, "data": dnt_entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create do-not-translate item: {str(e)}")

@app.get("/api/do-not-translate", tags=["Data Management"])
async def get_dnt_items():
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        dnt_items = await prisma.donottranslateitem.find_many()
        # Sort in Python
        dnt_items.sort(key=lambda x: x.text)
        return dnt_items
    except Exception as e:
        print(f"Database error: {e}")
        return []

@app.delete("/api/do-not-translate/{dnt_id}", tags=["Data Management"])
async def delete_dnt_item(dnt_id: str):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        await prisma.donottranslateitem.delete(where={"id": dnt_id})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete do-not-translate item: {str(e)}")

@app.post("/api/offensive-words", tags=["Data Management"])
async def create_offensive_word(word_data: OffensiveWordCreate):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Convert severity and category to enum format
        from prisma.enums import SeverityLevel, OffensiveWordCategory
        severity_enum_val = SeverityLevel(word_data.severity.upper()) if word_data.severity.upper() in SeverityLevel.__members__ else SeverityLevel.MEDIUM
        category_enum_val = OffensiveWordCategory(word_data.category.upper().replace(' ', '_')) if word_data.category.upper().replace(' ', '_') in OffensiveWordCategory.__members__ else OffensiveWordCategory.OTHER

        word_entry = await prisma.offensiveword.create(
            data={
                "word": word_data.word,
                "language": word_data.language,
                "severity": severity_enum_val, # Use enum value
                "category": category_enum_val, # Use enum value
                "alternatives": word_data.alternatives, # `alternatives` is a list, needs direct assignment
                "detectionCount": 0
            }
        )
        
        return {"success": True, "data": word_entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create offensive word: {str(e)}")

@app.get("/api/offensive-words", tags=["Data Management"])
async def get_offensive_words():
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        offensive_words = await prisma.offensiveword.find_many()
        # Sort in Python
        offensive_words.sort(key=lambda x: x.word)
        return offensive_words
    except Exception as e:
        print(f"Database error: {e}")
        return []

@app.delete("/api/offensive-words/{word_id}", tags=["Data Management"])
async def delete_offensive_word(word_id: str):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        await prisma.offensiveword.delete(where={"id": word_id})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete offensive word: {str(e)}")

# Translation request endpoints
@app.get("/api/translation-requests", tags=["Translation Requests"])
async def get_translation_requests(include: Optional[str] = Query(None)):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Parse include parameter
        include_metrics = include and 'metrics' in include
        include_strings = include and 'strings' in include
        
        # Build include object based on parameters
        include_obj = {}
        if include_strings:
            include_obj["translationStrings"] = {
                "include": {"annotations": True}
            }
        if include_metrics:
            include_obj["qualityMetrics"] = True
        
        requests = await prisma.translationrequest.find_many(
            include=include_obj if include_obj else {
                "translationStrings": {
                    "include": {"annotations": True}
                },
                "qualityMetrics": True
            }
        )
        
        # Sort in Python
        requests.sort(key=lambda x: x.createdAt, reverse=True)
        
        return requests
    except Exception as e:
        print(f"Database error: {e}")
        return []

@app.post("/api/translation-requests", tags=["Translation Requests"])
async def create_translation_request(request_data: TranslationRequestCreate):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        print(f"Processing translation request for targets: {request_data.targetLanguages}")
        
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
            'T5_BASE': MTModel.T5_BASE, # Added T5_BASE to mapping
            'T5_MULTILINGUAL': MTModel.T5_BASE, # Assuming T5_MULTILINGUAL uses the same enum variant
            'NLLB_200': MTModel.NLLB_200, # Added NLLB_200 to mapping
            'CUSTOM_MODEL': MTModel.CUSTOM_MODEL,
            'MULTI_ENGINE': MTModel.MULTI_ENGINE,
            'PIVOT_JP_EN_FR': MTModel.PIVOT_JP_EN_FR,
        }
        
        mt_model_enum = mt_model_mapping.get(request_data.mtModel, MTModel.MARIAN_MT_EN_FR) # Changed default to Marian
        
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
                    print(f"Translating text {i+1}/{len(request_data.sourceTexts)} to {target_lang} using {model_to_use_for_single_engine}")
                    
                    # Get fuzzy matches from database
                    fuzzy_matches = await fuzzy_matcher.find_fuzzy_matches(
                        source_text, target_lang, request_data.sourceLanguage
                    )
                    
                    suggested_translation = None
                    if fuzzy_matches and len(fuzzy_matches) > 0 and fuzzy_matches[0]["similarity"] > 0.9:
                        suggested_translation = fuzzy_matches[0]["target_text"]
                    
                    translated_text = ""

                    # Determine prefix/lang_tag for T5/NLLB for single-engine path
                    prefix_or_lang_tag_for_single = None
                    # Get model_info from translation_service.language_pair_models for this specific single model
                    model_info_from_ts_single = next(
                        (info for info in translation_service.language_pair_models.get(f"{request_data.sourceLanguage.upper()}-{target_lang.upper()}", []) 
                        if info[0] == model_to_use_for_single_engine),
                        None
                )
                    if model_info_from_ts_single and len(model_info_from_ts_single) == 3:
                        prefix_or_lang_tag_for_single = model_info_from_ts_single[2]
                    
                    # Perform translation based on the model_to_use_for_single_engine
                    if model_to_use_for_single_engine == 'PIVOT_ELAN_HELSINKI':
                        # Explicit pivot for single engine JP-FR
                        translated_text = multi_engine_service._translate_pivot_elan_helsinki(source_text.strip())
                    else:
                        # Direct translation using the specified model
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
                    print(f"Translation failed: {e}")
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
        
        print(f"✓ Translation request {db_request.id} completed")
        return updated_request
        
    except Exception as e:
        print(f"✗ Failed to create translation request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create translation request: {str(e)}")

@app.post("/api/quality-metrics/calculate", tags=["Quality Assessment"])
async def calculate_quality_metrics(request_data: QualityMetricsCalculate):
    try:
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
                        
                        if not current_source_text or not current_source_text.strip():
                            logger.warning(f"SKIPPING METRICS for string {current_string_id}: Source text is empty or None.")
                        if not current_original_mt or not current_original_mt.strip():
                            logger.warning(f"SKIPPING METRICS for string {current_string_id}: Original MT (hypothesis) is empty or None.")
                        if not current_post_edited or not current_post_edited.strip():
                            logger.warning(f"SKIPPING METRICS for string {current_string_id}: Post-edited text (reference) is empty or None.")
                        
                        continue
                    
                    target_lang_code = translation_string.targetLanguage.lower()
                    tokenizer_option = 'ja-mecab' if target_lang_code == 'jp' else '13a'
                    logger.info(f"Using tokenizer '{tokenizer_option}' for metrics on lang '{target_lang_code}'")

                    bleu_score = sacrebleu.sentence_bleu(current_original_mt, [current_post_edited], tokenize=tokenizer_option).score / 100
                    ter_score = sacrebleu.TER(tokenize=tokenizer_option).sentence_score(current_original_mt, [current_post_edited]).score
                    logger.info(f"Calculated Metrics for {current_string_id}: TER={ter_score:.2f}")

                    if comet_model:
                        try:
                            comet_data = [{"src": current_source_text, "mt": current_original_mt, "ref": current_post_edited}]
                            
                            comet_output = comet_model.predict(
                                comet_data,
                                batch_size=1
                            )
                            comet_score = comet_output.scores[0]
                        except Exception as comet_error:
                            logger.error(f"COMET calculation failed for {current_string_id}: {comet_error}")
                            comet_score = 0.0
                    else:
                        logger.warning(f"COMET model not loaded. COMET score for string {current_string_id} set to 0.0.")
                        comet_score = 0.0

                    total_bleu += bleu_score
                    total_ter += ter_score
                    total_comet += comet_score
                    processed_strings += 1

                except Exception as metric_error:
                    logger.error(f"Error calculating metrics for string {current_string_id}: {metric_error}")
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

            quality_metrics = await prisma.qualitymetrics.create(
                data={
                    "translationRequestId": request_data.requestId,
                    "metricXScore": 8.5,
                    "metricXConfidence": 0.92,
                    "metricXMode": EvaluationMode.REFERENCE_FREE,
                    "metricXVariant": ModelVariant.METRICX_24_HYBRID,
                    "bleuScore": avg_bleu,
                    "cometScore": avg_comet,
                    "terScore": avg_ter,
                    "qualityLabel": quality_label,
                    "hasReference": has_any_reference,
                    "referenceType": ReferenceType.POST_EDITED if has_any_reference else None,
                    "calculationEngine": "post-editing-metrics"
                }
            )

            logger.info(f"✓ Quality metrics calculated for request {request_data.requestId}: BLEU={avg_bleu:.2f}, COMET={avg_comet:.2f}, TER={avg_ter:.2f}, Processed Strings={processed_strings}")
            return {
                "success": True,
                "message": f"Post-editing quality metrics calculated for {processed_strings} strings",
                "metrics": quality_metrics
            }
        else:
            logger.warning(f"No valid post-edited strings found to calculate metrics for request {request_data.requestId}.")
            return {
                "success": False,
                "message": "No valid post-edited strings found to calculate metrics.",
                "metrics": None
            }

    except Exception as e:
        logger.error(f"Error calculating quality metrics for request {request_data.requestId}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to calculate quality metrics: {str(e)}")

@app.post("/api/debug/fix-reference-flags", tags=["Debugging"])
async def fix_reference_flags():
    """Fix hasReference flags for existing translations"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        strings = await prisma.translationstring.find_many()

        updated_count = 0
        for string in strings:
            # Check if translation was actually edited
            if (string.originalTranslation and 
                string.translatedText and 
                string.originalTranslation.strip() != string.translatedText.strip()):
                
                await prisma.translationstring.update(
                    where={"id": string.id},
                    data={"hasReference": True}
                )
                updated_count += 1

        all_metrics = await prisma.qualitymetrics.find_many()
        
        metrics_updated = 0
        for metric in all_metrics:
            # Get the translation request to check if it has references
            request = await prisma.translationrequest.find_unique(
                where={"id": metric.translationRequestId},
                include={"translationStrings": True}
            )
            
            if request:
                has_references = any(
                    ts.hasReference for ts in request.translationStrings
                )
                
                if has_references and not metric.hasReference:
                    await prisma.qualitymetrics.update(
                        where={"id": metric.id},
                        data={
                            "hasReference": True,
                            "referenceType": "POST_EDITED"
                        }
                    )
                    metrics_updated += 1

        return {
            "success": True,
            "updated_strings": updated_count,
            "updated_metrics": metrics_updated
        }

    except Exception as e:
        print(f"Error in fix_reference_flags: {e}")
        return {"error": str(e)}

@app.post("/api/translation-strings/{string_id}/select-engine", tags=["Translation Requests"])
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
        if isinstance(engine_results, Json):
            engine_results = engine_results.to_dict()
        elif isinstance(engine_results, str):
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
                "originalTranslation": final_translated_text,  # Store as baseline for quality metrics
                "selectedEngine": selection_data.engine,
                "status": "REVIEWED"
            }
        )

        return {"success": True, "selectedEngine": selection_data.engine, "updatedString": updated_string}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to select engine: {str(e)}")

@app.put("/api/translation-strings/{string_id}", tags=["Translation Requests"])
async def update_translation_string(string_id: str, update_data: TranslationStringUpdate):
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
                print(f"✓ Created TM entry for approved translation: {string_id}")
            except Exception as tm_error:
                print(f"⚠ Failed to create TM entry: {tm_error}")
        
        if update_data.status == 'APPROVED' and update_payload.get("hasReference"):
            try:
                import asyncio
                asyncio.create_task(calculate_quality_metrics(QualityMetricsCalculate(requestId=existing_string.translationRequestId)))
                print(f"✓ Triggered auto-calculation of quality metrics for request: {existing_string.translationRequestId}")
            except Exception as metrics_error:
                print(f"⚠ Failed to auto-calculate quality metrics: {metrics_error}")
        
        return {"success": True, "message": "Translation string updated successfully", "updatedString": updated_string}
        
    except Exception as e:
        print(f"Error updating translation string {string_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update translation string: {str(e)}")

@app.post("/api/translation-strings/{string_id}/annotations", tags=["Translation Requests"])
async def create_annotation(string_id: str, annotation_data: AnnotationCreate):
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
        print(f"Error creating annotation for string {string_id}: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to create annotation: {str(e)}")


# Multi-engine endpoints 
@app.post("/api/translation-requests/multi-engine", tags=["Translation Requests"])
async def create_multi_engine_translation_request(request_data: MultiEngineTranslationRequestCreate):
    """Create translation request with multiple local engines"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        print(f"Processing multi-engine translation request for targets: {request_data.targetLanguages}")
        
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
                print(f"Getting multi-engine translations for text {i+1}/{len(request_data.sourceTexts)} to {target_lang}")
                
                # Get fuzzy matches from database
                fuzzy_matches = await fuzzy_matcher.find_fuzzy_matches(
                    source_text, target_lang, request_data.sourceLanguage
                )
                
                suggested_translation = None
                if fuzzy_matches and len(fuzzy_matches) > 0 and fuzzy_matches[0]["similarity"] > 0.9:
                    suggested_translation = fuzzy_matches[0]["target_text"]
                
                # Get translations from all local engines using CleanMultiEngineService
                engine_results = await multi_engine_service.translate_multi_engine(
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
        
        print(f"✓ Multi-engine translation request {db_request.id} completed")
        return complete_request
        
    except Exception as e:
        print(f"✗ Failed to create multi-engine request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create multi-engine request: {str(e)}")

# Analytics endpoint
@app.get("/api/analytics/engine-preferences", tags=["Quality Assessment"])
async def get_engine_preference_analytics():
    """Get analytics on engine preferences over time"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        preferences = await prisma.enginepreference.find_many()
        
        # Sort in Python
        preferences.sort(key=lambda x: x.createdAt, reverse=True)
        
        # Calculate statistics
        total_preferences = len(preferences)
        engine_counts = {}
        engine_ratings = {}
        
        for pref in preferences:
            engine = pref.selectedEngine
            engine_counts[engine] = engine_counts.get(engine, 0) + 1
            
            if engine not in engine_ratings:
                engine_ratings[engine] = []
            engine_ratings[engine].append(pref.rating)
        
        # Calculate average ratings
        avg_ratings = {}
        for engine, ratings in engine_ratings.items():
            avg_ratings[engine] = sum(ratings) / len(ratings) if ratings else 0
        
        return {
            "totalPreferences": total_preferences,
            "engineCounts": engine_counts,
            "averageRatings": avg_ratings,
            "preferences": preferences[:50]  # Return recent 50 for display
        }
        
    except Exception as e:
        print(f"Database error: {e}")
        return {
            "totalPreferences": 0,
            "engineCounts": {},
            "averageRatings": {},
            "preferences": []
        }

@app.get("/api/dashboard/post-edit-metrics", tags=["Quality Assessment"])
async def get_post_edit_metrics(
    language_pair: Optional[str] = Query("all"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get post-editing metrics for dashboard"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        metrics = await prisma.qualitymetrics.find_many(
            where={
                "hasReference": True,
                "bleuScore": {"not": None},
                "cometScore": {"not": None},
                "terScore": {"not": None}
            },
            include={
                "translationRequest": {
                    "include": {
                        "translationStrings": {
                            "where": {
                                "hasReference": True
                            }
                        }
                    }
                }
            }
        )

        # Group by language pair
        language_pair_metrics = {}
        correlation_data = []
        
        for metric in metrics:
            if metric.translationRequest and metric.translationRequest.translationStrings:
                source_lang = metric.translationRequest.sourceLanguage
                
                # Get target language from post-edited strings
                for ts in metric.translationRequest.translationStrings:
                    target_lang = ts.targetLanguage
                    pair = f"{source_lang}-{target_lang}"
                    
                    if language_pair != "all" and pair != language_pair:
                        continue
                    
                    if pair not in language_pair_metrics:
                        language_pair_metrics[pair] = {
                            "languagePair": pair,
                            "bleuScores": [],
                            "cometScores": [],
                            "terScores": [],
                            "count": 0
                        }
                    
                    language_pair_metrics[pair]["bleuScores"].append(metric.bleuScore)
                    language_pair_metrics[pair]["cometScores"].append(metric.cometScore)
                    language_pair_metrics[pair]["terScores"].append(metric.terScore)
                    language_pair_metrics[pair]["count"] += 1
                    
                    correlation_data.append({
                        "bleu": metric.bleuScore,
                        "comet": metric.cometScore,
                        "ter": metric.terScore,
                        "metricx": metric.metricXScore or 0
                    })

        # Calculate averages for bar chart
        bar_chart_data = []
        for pair, data in language_pair_metrics.items():
            if data["count"] > 0:
                bar_chart_data.append({
                    "languagePair": pair,
                    "avgBleu": sum(data["bleuScores"]) / len(data["bleuScores"]) * 100,
                    "avgComet": sum(data["cometScores"]) / len(data["cometScores"]) * 100,
                    "avgTer": sum(data["terScores"]) / len(data["terScores"]),
                    "count": data["count"]
                })

        print(f"Returning {len(bar_chart_data)} language pairs for dashboard")

        return {
            "languagePairMetrics": bar_chart_data,
            "correlationMatrix": [
                {"metric1": "BLEU", "metric2": "COMET", "correlation": 0.75, "pValue": 0.05},
                {"metric1": "BLEU", "metric2": "TER", "correlation": -0.65, "pValue": 0.05},
                {"metric1": "COMET", "metric2": "TER", "correlation": -0.70, "pValue": 0.05},
                {"metric1": "BLEU", "metric2": "METRICX", "correlation": 0.80, "pValue": 0.05}
            ],
            "totalPostEdits": len(correlation_data)
        }

    except Exception as e:
        print(f"Error getting post-edit metrics: {e}")
        return {
            "languagePairMetrics": [],
            "correlationMatrix": [],
            "totalPostEdits": 0
        }

@app.get("/api/dashboard/analytics", tags=["Quality Assessment"])
async def get_dashboard_analytics(
    language_pair: Optional[str] = Query(None) 
):
    """Get comprehensive analytics data for the dashboard"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        lang_filter = {} if language_pair == "all" else {"languagePair": language_pair}

        translation_requests = await prisma.translationrequest.find_many(
            include={
                "translationStrings": True,
                "qualityMetrics": True
            }
        )
        
        quality_metrics = await prisma.qualitymetrics.find_many(
            where={"hasReference": True}
        )
        
        engine_preferences = await prisma.enginepreference.find_many()
        
        annotations = await prisma.annotation.find_many()

        # Pass empty filters to helper functions (or remove filter parameters entirely)
        model_performance = await get_model_performance_data({}, lang_filter)
        quality_scores = await get_quality_scores_data({}, lang_filter)
        human_preferences = await get_human_preferences_data({}, lang_filter)
        annotations_data = await get_annotations_data({}, lang_filter)
        operational_data = await get_operational_data({}, lang_filter)

        return {
            "modelPerformance": model_performance,
            "humanPreferences": human_preferences,
            "annotations": annotations_data,
            "multiEngine": {"selectionTrends": [], "pivotQuality": [], "interRaterAgreement": []},
            "qualityScores": quality_scores,
            "operational": operational_data,
            "tmGlossary": {"tmImpact": [], "glossaryUsage": [], "termOverrides": []}
        }

    except Exception as e:
        print(f"Dashboard analytics error: {e}")
        return {
            "modelPerformance": {"leaderboard": [], "performanceOverTime": [], "modelComparison": []},
            "humanPreferences": {"enginePreferences": [], "reviewerBehavior": [], "preferenceReasons": []},
            "annotations": {"errorHeatmap": [], "severityBreakdown": [], "spanAnalysis": []},
            "multiEngine": {"selectionTrends": [], "pivotQuality": [], "interRaterAgreement": []},
            "qualityScores": {"evaluationModes": [], "correlationMatrix": [], "scoreDistribution": []},
            "operational": {"processingTimes": [], "systemHealth": [], "modelUtilization": []},
            "tmGlossary": {"tmImpact": [], "glossaryUsage": [], "termOverrides": []}
        }


@app.get("/api/rlhf/analytics", tags=["Quality Assessment"])
async def get_rlhf_analytics():
    """Get RLHF analytics data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        preferences = await prisma.enginepreference.find_many()
        
        total_feedback = len(preferences)
        preference_pairs = sum(1 for p in preferences if p.rating >= 4)
        
        feedback_types = {}
        for pref in preferences:
            engine = pref.selectedEngine
            feedback_types[engine] = feedback_types.get(engine, 0) + 1
        
        avg_quality_scores = {}
        engine_ratings = {}
        for pref in preferences:
            engine = pref.selectedEngine
            if engine not in engine_ratings:
                engine_ratings[engine] = []
            engine_ratings[engine].append(pref.rating)
        
        for engine, ratings in engine_ratings.items():
            avg_quality_scores[engine] = sum(ratings) / len(ratings) if ratings else 0
        
        return {
            "total_feedback_entries": total_feedback,
            "total_preference_pairs": preference_pairs,
            "feedback_types": feedback_types,
            "average_quality_scores": avg_quality_scores,
            "training_data_available": total_feedback > 0
        }
        
    except Exception as e:
        return {
            "total_feedback_entries": 0,
            "total_preference_pairs": 0,
            "feedback_types": {},
            "average_quality_scores": {},
            "training_data_available": False
        }

@app.get("/api/human-feedback/analytics", tags=["Quality Assessment"])
async def get_human_feedback_analytics():
    """Get human feedback analytics data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        annotations = await prisma.annotation.find_many()
        
        total_entries = len(annotations)
        
        feedback_distribution = {}
        for annotation in annotations:
            category = annotation.category.value # Access enum value
            feedback_distribution[category] = feedback_distribution.get(category, 0) + 1
        
        severity_distribution = {}
        for annotation in annotations:
            severity = annotation.severity.value # Access enum value
            severity_distribution[severity] = severity_distribution.get(severity, 0) + 1
        
        return {
            "total_entries": total_entries,
            "feedback_distribution": feedback_distribution,
            "quality_metrics": {
                "severity_distribution": severity_distribution,
                "categories_covered": len(feedback_distribution),
                "average_feedback_per_request": total_entries / max(1, prisma.translationrequest.count()) # Divide by total requests if possible
            }
        }
        
    except Exception as e:
        print(f"Error fetching human feedback analytics: {e}")
        return {
            "total_entries": 0,
            "feedback_distribution": {},
            "quality_metrics": {}
        }

@app.post("/api/rlhf/quality-rating", tags=["Quality Assessment"])
async def submit_quality_rating(rating: QualityRating):
    try:
        return {"success": True, "message": "Quality rating submitted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit rating: {str(e)}")

@app.get("/api/debug/check-quality-metrics", tags=["Quality Assessment"])
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
        return {"error": str(e)}

@app.post("/api/metricx/evaluate", tags=["Quality Assessment"])
async def evaluate_translation(request: MetricXRequest):
    try:
        result = metricx_service.evaluate_translation(
            source=request.source,
            hypothesis=request.hypothesis,
            reference=request.reference,
            source_language=request.source_language,
            target_language=request.target_language
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug/check-annotations", tags=["Debugging"])
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
        return {"error": str(e)}

@app.get("/api/debug/data-counts", tags=["Debugging"])
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
            "local_models": await prisma.localmodel.count()
        }
        
        return counts
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/populate-dashboard-data", tags=["Debugging"])
async def populate_dashboard_data():
    """Populate dashboard tables with data from existing translations"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Get existing translation strings
        strings = await prisma.translationstring.find_many(
            include={"translationRequest": True},
            take=10  # Start with just 10 for testing
        )
        
        created_count = 0
        
        for string in strings:
            # Create quality metrics if they don't have them
            existing_metric = await prisma.qualitymetrics.find_first(
                where={"translationStringId": string.id}
            )
            
            if not existing_metric:
                await prisma.qualitymetrics.create(
                    data={
                        "translationStringId": string.id,
                        "metricXScore": 8.5,  # Mock score
                        "metricXConfidence": 0.9,
                        "bleuScore": 0.75,
                        "cometScore": 0.82,
                        "terScore": 0.15,
                        "qualityLabel": "GOOD"
                    }
                )
                created_count += 1
        
        return {
            "success": True,
            "created_quality_metrics": created_count,
            "message": f"Created {created_count} quality metrics for existing translations"
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/recalculate-all-metrics", tags=["Debugging"])
async def recalculate_all_metrics():
    """Recalculate quality metrics for all requests with post-edited strings"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        requests_with_post_edits = await prisma.translationrequest.find_many(
            where={
                "translationStrings": {
                    "some": {
                        "hasReference": True
                    }
                }
            },
            include={"translationStrings": True}
        )

        recalculated = []
        errors = []

        for req in requests_with_post_edits:
            try:
                await prisma.qualitymetrics.delete_many(
                    where={"translationRequestId": req.id}
                )

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

                        await prisma.qualitymetrics.create(
                            data={
                                "translationRequestId": req.id,
                                "metricXScore": 8.5,
                                "metricXConfidence": 0.92,
                                "metricXMode": EvaluationMode.REFERENCE_FREE,      
                                "metricXVariant": ModelVariant.METRICX_24_HYBRID,  
                                "bleuScore": avg_bleu,
                                "cometScore": avg_comet,
                                "terScore": avg_ter,
                                "qualityLabel": quality_label,                     
                                "hasReference": True,
                                "referenceType": ReferenceType.POST_EDITED,        
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

@app.post("/api/debug/populate-all-dashboard-data", tags=["Debugging"])
async def populate_all_dashboard_data():
    """Populate all dashboard tables with data from existing translations"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Get existing translation strings with requests
        strings = await prisma.translationstring.find_many(
            include={"translationRequest": True}
        )
        
        created_metrics = 0
        created_preferences = 0
        created_annotations = 0
        created_model_outputs = 0
        
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
                        "qualityLabel": "GOOD"
                    }
                )
                created_metrics += 1
        
        # 2. Create engine preferences
        engines = ["opus_fast", "elan_specialist", "t5_versatile", "nllb_multilingual"] # Now includes T5 and NLLB
        valid_reasons = ["ACCURACY", "FLUENCY", "STYLE", "TERMINOLOGY", "CULTURAL_FIT", "NATURALNESS"]
        
        for i, string in enumerate(strings[:50]):
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
        
        for i, string in enumerate(strings[:20]):
            await prisma.annotation.create(
                data={
                    "translationStringId": string.id,
                    "category": valid_categories[i % len(valid_categories)],
                    "severity": valid_severities[i % len(valid_severities)],
                    "comment": f"Sample annotation {i+1} for quality review",
                    "reviewer": "system_generated"
                }
            )
            created_annotations += 1
        
        # 4. Create model outputs
        model_names = ["HELSINKI_EN_JP", "ELAN_JA_EN", "T5_MULTILINGUAL", "NLLB_200"] # Includes T5 and NLLB
        engines = ["opus_fast", "elan_specialist", "t5_versatile", "nllb_multilingual"] # Includes T5 and NLLB
        
        for i, string in enumerate(strings[:30]):
            for j in range(2):
                await prisma.modeloutput.create(
                    data={
                        "translationStringId": string.id,
                        "modelName": model_names[j % len(model_names)],
                        "engineName": engines[j % len(engines)],
                        "outputText": string.translatedText,
                        "confidence": 0.8 + (j * 0.1),
                        "processingTimeMs": 1000 + (i * 50) + (j * 200)
                    }
                )
                created_model_outputs += 1
        
        # SKIP LocalModel creation for now
        
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
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.post("/api/debug/populate-enhanced-dashboard-data", tags=["Debugging"])
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
        
        created_count = 0
        
        # 1. Add TM match percentages to existing strings
        for i, string in enumerate(strings[:50]):
            tm_percentage = [95, 85, 75, 65, 45][i % 5]  # Vary TM match rates
            await prisma.translationstring.update(
                where={"id": string.id},
                data={"tmMatchPercentage": tm_percentage}
            )
        
        # 2. Create more annotations with varied severities
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        categories = ["GRAMMAR", "WORD_CHOICE", "CONTEXT", "FLUENCY", "TERMINOLOGY", "STYLE"]
        
        for i in range(30):  # Create 30 annotations
            string = strings[i % len(strings)]
            await prisma.annotation.create(
                data={
                    "translationStringId": string.id,
                    "category": categories[i % len(categories)],
                    "severity": severities[i % len(severities)],
                    "comment": f"Enhanced annotation {i+1}",
                    "reviewer": f"reviewer_{(i % 3) + 1}"
                }
            )
            created_count += 1
        
        # 3. Create more model outputs for processing time analysis
        models = ["HELSINKI_EN_JP", "ELAN_JA_EN", "T5_MULTILINGUAL", "NLLB_200"] # Includes T5 and NLLB
        engines = ["opus_fast", "elan_specialist", "t5_versatile", "nllb_multilingual"] # Includes T5 and NLLB
        
        for i in range(60):  # Create 60 model outputs
            string = strings[i % len(strings)]
            await prisma.modeloutput.create(
                data={
                    "translationStringId": string.id,
                    "modelName": models[i % len(models)],
                    "engineName": engines[j % len(engines)],
                    "outputText": string.translatedText,
                    "confidence": 0.7 + (i % 3) * 0.1,
                    "processingTimeMs": 800 + (i * 50) + ((i % 4) * 300)  # Vary processing time
                }
            )
        
        # 4. Create more diverse engine preferences
        for i in range(40):  # Create 40 more preferences
            string = strings[i % len(strings)]
            await prisma.enginepreference.create(
                data={
                    "translationStringId": string.id,
                    "selectedEngine": engines[i % len(engines)],
                    "sourceLanguage": string.translationRequest.sourceLanguage,
                    "targetLanguage": string.translationRequest.targetLanguages[0] if string.translationRequest.targetLanguages else "EN",
                    "rating": 2 + (i % 4),  # Ratings 2-5
                    "selectionMethod": ["COPY_BUTTON", "MANUAL_EDIT", "RATING"][i % 3],
                    "overallSatisfaction": 2 + (i % 4),
                    "preferenceReason": ["ACCURACY", "FLUENCY", "STYLE", "TERMINOLOGY"][i % 4]
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
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.get("/api/debug/test-engine-preferences", tags=["Debugging"])
async def test_engine_preferences():
    """Debug the engine preferences function specifically"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        # Test raw query first
        all_prefs = await prisma.enginepreference.find_many(take=5)
        print(f"Found {len(all_prefs)} engine preferences")
        
        engine_preferences_raw = await prisma.enginepreference.group_by(
            by=["selectedEngine", "sourceLanguage", "targetLanguage", "preferenceReason"],
            _count={"selectedEngine": True},
            _avg={"rating": True, "overallSatisfaction": True},
            where={}  
        )
        
        print(f"Grouped results: {len(engine_preferences_raw)}")
        
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
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.post("/api/debug/add-metricx-modes", tags=["Debugging"])
async def add_metricx_modes():
    """Add MetricX evaluation modes to existing quality metrics"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        metrics = await prisma.qualitymetrics.find_many(
            where={"metricXMode": None},
            take=50
        )
        
        modes = ["REFERENCE_FREE", "REFERENCE_BASED", "HYBRID"]
        updated_count = 0
        
        for i, metric in enumerate(metrics):
            await prisma.qualitymetrics.update(
                where={"id": metric.id},
                data={
                    "metricXMode": modes[i % len(modes)],
                    "metricXVariant": "METRICX_24_HYBRID"
                }
            )
            updated_count += 1
        
        return {"success": True, "updated_metrics": updated_count}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/debug/add-tm-matches", tags=["Debugging"])
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
        return {"error": str(e)}

@app.put("/api/translation-strings/{string_id}", tags=["Translation Requests"])
async def update_translation_string(string_id: str, update_data: TranslationStringUpdate):
    """Update translation string and commit to TM if approved"""
    try:
        # Update the translation string
        updated_string = await prisma.translationstring.update(
            where={"id": string_id},
            data={
                "translatedText": update_data.translatedText,
                "status": update_data.status
            },
            include={"translationRequest": True}
        )
        
        # If approved, commit to translation memory
        if update_data.status == "APPROVED":
            await commit_to_translation_memory(updated_string)
        
        return updated_string
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def commit_to_translation_memory(translation_string):
    """Commit approved translation to TM"""
    try:
        # Check if TM entry already exists
        existing_tm = await prisma.translationmemory.find_first(
            where={
                "sourceText": translation_string.sourceText,
                "targetText": translation_string.translatedText,
                "sourceLanguage": translation_string.translationRequest.sourceLanguage,
                "targetLanguage": translation_string.targetLanguage
            }
        )
        
        if not existing_tm:
            await prisma.translationmemory.create(
                data={
                    "sourceText": translation_string.sourceText,
                    "targetText": translation_string.translatedText,
                    "sourceLanguage": translation_string.translationRequest.sourceLanguage,
                    "targetLanguage": translation_string.targetLanguage,
                    "quality": QualityLabel.EXCELLENT,
                    "domain": "general",
                    "createdFrom": f"qa_approval_{string_id}",
                    "originalRequestId": translation_string.translationRequestId,
                    "approvedBy": "qa_reviewer",
                    "usageCount": 0
                }
            )
            logger.info(f"Committed approved translation to TM: {translation_string.id}")
        
    except Exception as e:
        logger.error(f"Failed to commit to TM: {e}")

@app.get("/api/debug/check-specific-metrics", tags=["Debugging"])
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
        return {"error": str(e)}

@app.get("/api/metricx/test", tags=["Quality Assessment"])
async def test_metricx():
    if metricx_service is None:
        raise HTTPException(status_code=503, detail="MetricX service not loaded")

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
        raise HTTPException(status_code=500, detail=f"MetricX test failed: {str(e)}")

@app.get("/api/dashboard/translator-impact", tags=["Quality Assessment"])
async def get_translator_impact_data(language_pair: Optional[str] = Query("all")):
    """Get translator impact analysis data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        translations = await prisma.translationstring.find_many(
            where={
                "originalTranslation": {"not": None},               
                "translatedText": {"not": ""}, # Filter out empty strings explicitly
                "status": {"in": ["REVIEWED", "APPROVED"]}, # Only return metrics for reviewed/approved strings
            },
            include={
                "translationRequest": True,
                "qualityMetrics": True
            }
        )

        logger.info(f"Found {len(translations)} translation strings for translator impact analysis.") # Changed print to logger.info

        if not translations:
            return {"comparisons": [], "summary": []}

        comparisons = []
        for translation in translations:
            # Add explicit checks to ensure both are valid strings before using them
            if not translation.originalTranslation or not translation.originalTranslation.strip():
                logger.warning(f"Skipping string {translation.id} in translator impact: originalTranslation is empty or null.")
                continue
            if not translation.translatedText or not translation.translatedText.strip():
                logger.warning(f"Skipping string {translation.id} in translator impact: translatedText is empty or null.")
                continue

            # Check if we have both original and edited versions that are different
            if translation.originalTranslation.strip() != translation.translatedText.strip():
                
                edit_distance = calculate_edit_distance(
                    translation.originalTranslation, 
                    translation.translatedText
                )
                
                # Ensure sourceText is not None for improvement score calculation
                source_text_for_improvement = translation.sourceText if translation.sourceText else "" 

                improvement_score = calculate_improvement_score(
                    translation.originalTranslation,
                    translation.translatedText,
                    source_text_for_improvement
                )
                
                edit_type = classify_edit_type(edit_distance, len(translation.originalTranslation.strip())) # Use strip() length
                
                comparisons.append({
                    "id": translation.id,
                    "sourceText": translation.sourceText,
                    "originalMT": translation.originalTranslation,
                    "humanEdited": translation.translatedText,
                    "languagePair": f"{translation.translationRequest.sourceLanguage}-{translation.targetLanguage}",
                    "jobId": translation.translationRequest.id,
                    "jobName": translation.translationRequest.fileName,
                    "editDistance": edit_distance,
                    "improvementScore": improvement_score,
                    "editType": edit_type,
                    "timestamp": translation.updatedAt.isoformat() if translation.updatedAt else None, # Handle None timestamp
                })

        logger.info(f"Created {len(comparisons)} comparisons for translator impact.") # Changed print to logger.info

        # Calculate summary statistics
        summary = calculate_translator_summary(comparisons)

        return {
            "comparisons": comparisons,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"Error fetching translator impact data: {e}") # Changed print to logger.error
        import traceback
        traceback.print_exc()
        return {"comparisons": [], "summary": []}

def calculate_edit_distance(original: str, edited: str) -> float:
    """Calculate normalized edit distance between two strings"""
    import difflib
    return 1 - difflib.SequenceMatcher(None, original, edited).ratio()

def calculate_improvement_score(original: str, edited: str, source: str) -> float:
    """Calculate improvement score based on various metrics"""
    original_words = set(original.lower().split())
    edited_words = set(edited.lower().split())
    source_words = set(source.lower().split())
    
    original_overlap = len(original_words & source_words) / len(source_words) if source_words else 0
    edited_overlap = len(edited_words & source_words) / len(source_words) if source_words else 0
    
    return max(0, edited_overlap - original_overlap)

def classify_edit_type(edit_distance: float, text_length: int) -> str:
    """Classify edit type based on distance and text length"""
    if edit_distance < 0.1:
        return "minor"
    elif edit_distance < 0.3:
        return "moderate"
    else:
        return "major"

def calculate_translator_summary(comparisons: list) -> list:
    """Calculate summary statistics for translators"""
    if not comparisons:
        return []
    
    # Group by language pair since we don't have translator IDs
    language_pairs = {}
    for comp in comparisons:
        pair = comp["languagePair"]
        if pair not in language_pairs:
            language_pairs[pair] = {
                "translatorId": f"Translator-{pair}",
                "totalEdits": 0,
                "improvementScores": [],
                "editDistances": [],
                "languagePairs": [pair],
                "editTypes": {"minor": 0, "moderate": 0, "major": 0}
            }
        
        language_pairs[pair]["totalEdits"] += 1
        language_pairs[pair]["improvementScores"].append(comp["improvementScore"])
        language_pairs[pair]["editDistances"].append(comp["editDistance"])
        language_pairs[pair]["editTypes"][comp["editType"]] += 1
    
    summary = []
    for pair_data in language_pairs.values():
        summary.append({
            "translatorId": pair_data["translatorId"],
            "totalEdits": pair_data["totalEdits"],
            "avgImprovementScore": sum(pair_data["improvementScores"]) / len(pair_data["improvementScores"]),
            "avgEditDistance": sum(pair_data["editDistances"]) / len(pair_data["editDistances"]),
            "languagePairs": pair_data["languagePairs"],
            "editTypes": pair_data["editTypes"]
        })
    
    return summary

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
