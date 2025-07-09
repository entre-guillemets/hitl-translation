from fastapi import APIRouter, HTTPException
import logging
from typing import List, Optional

from app.schemas.data_management import ( # Changed import path
    TranslationMemoryCreate,
    GlossaryTermCreate,
    DoNotTranslateCreate,
    OffensiveWordCreate
)
from app.db.base import prisma

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Data Management"])

# Command Center endpoints with database operations
@router.post("/translation-memory")
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
        
        logger.info(f"Creating TM entry: quality '{tm_data.quality}' -> {quality_enum_val}")

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
        logger.error(f"TM Creation Error: {e}")
        logger.error(f"TM Data received: {tm_data}")
        from prisma.enums import MemoryQuality # Re-import for error message
        logger.error(f"Available enum values: {list(MemoryQuality.__members__.keys())}")
        raise HTTPException(status_code=500, detail=f"Failed to create translation memory: {str(e)}")

@router.get("/translation-memory")
async def get_translation_memory():
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        tm_entries = await prisma.translationmemory.find_many()
        # Sort in Python
        tm_entries.sort(key=lambda x: x.lastUsed if x.lastUsed else datetime.min, reverse=True) # Handle None for lastUsed
        return tm_entries
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

@router.delete("/translation-memory/{tm_id}")
async def delete_translation_memory(tm_id: str):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        await prisma.translationmemory.delete(where={"id": tm_id})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete translation memory: {str(e)}")

@router.post("/glossary")
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

@router.get("/glossary")
async def get_glossary():
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        glossary_terms = await prisma.glossaryterm.find_many()
        # Sort in Python
        glossary_terms.sort(key=lambda x: x.term)
        return glossary_terms
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

@router.delete("/glossary/{term_id}")
async def delete_glossary_term(term_id: str):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        await prisma.glossaryterm.delete(where={"id": term_id})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete glossary term: {str(e)}")

@router.post("/do-not-translate")
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

@router.get("/do-not-translate")
async def get_dnt_items():
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        dnt_items = await prisma.donottranslateitem.find_many()
        # Sort in Python
        dnt_items.sort(key=lambda x: x.text)
        return dnt_items
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

@router.delete("/do-not-translate/{dnt_id}")
async def delete_dnt_item(dnt_id: str):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        await prisma.donottranslateitem.delete(where={"id": dnt_id})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete do-not-translate item: {str(e)}")

@router.post("/offensive-words")
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

@router.get("/offensive-words")
async def get_offensive_words():
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        offensive_words = await prisma.offensiveword.find_many()
        # Sort in Python
        offensive_words.sort(key=lambda x: x.word)
        return offensive_words
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

@router.delete("/offensive-words/{word_id}")
async def delete_offensive_word(word_id: str):
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        await prisma.offensiveword.delete(where={"id": word_id})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete offensive word: {str(e)}")