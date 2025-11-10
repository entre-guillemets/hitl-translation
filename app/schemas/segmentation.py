from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class SegmentationCreate(BaseModel):
    originalFileName: str
    mediaType: str
    segments: List[Dict[str, Any]]
    detectedLanguage: str
    wordCount: int

class SegmentationUpdate(BaseModel):
    segments: List[Dict[str, Any]]
    sourceLanguage: str
    targetLanguages: List[str]
    useMultiEngine: bool = False
    selectedEngines: Optional[List[str]] = None