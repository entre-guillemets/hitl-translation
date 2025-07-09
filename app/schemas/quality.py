from pydantic import BaseModel
from typing import List, Optional

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

class QualityMetricsCalculate(BaseModel):
    requestId: str

class AnnotationCreate(BaseModel):
    category: str
    severity: str
    comment: str
    reviewer: Optional[str] = None

class MetricXRequest(BaseModel):
    source: str
    hypothesis: str
    reference: Optional[str] = None
    source_language: str = "en"
    target_language: str = "es"
    model: Optional[str] = "MetricX-24-Hybrid"

class BatchMetricXRequest(BaseModel):
    requests: List[MetricXRequest]
