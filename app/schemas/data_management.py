from pydantic import BaseModel
from typing import List, Optional

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
