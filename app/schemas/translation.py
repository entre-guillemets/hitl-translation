from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class TranslationRequestCreate(BaseModel):
    sourceLanguage: str
    targetLanguages: List[str]
    languagePair: str
    wordCount: int
    fileName: str
    mtModel: str
    sourceTexts: Optional[List[str]] = []
    advertiserProfileId: Optional[str] = None

class MultiEngineTranslationRequestCreate(BaseModel):
    sourceLanguage: str
    targetLanguages: List[str]
    languagePair: str
    wordCount: int
    fileName: str
    sourceTexts: Optional[List[str]] = []
    engines: Optional[List[str]] = ["opus_fast", "elan_specialist"]
    advertiserProfileId: Optional[str] = None

class TranslationStringUpdate(BaseModel):
    translatedText: str
    status: str
    annotatorId: Optional[str] = None  # e.g. "REVIEWER_1"

class EngineSelectionData(BaseModel):
    engine: str
    rating: int
    comments: Optional[str] = ""
