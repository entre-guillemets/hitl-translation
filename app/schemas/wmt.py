from pydantic import BaseModel

class WMTRequestCreate(BaseModel):
    language_pair: str
    sample_size: int = 10

class WMTBenchmarkResult(BaseModel):
    source_text: str
    reference_text: str
    mt_translation: str
    bleu_score: float
    language_pair: str
