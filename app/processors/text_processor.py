import logging
import re
from typing import Optional, Callable

logger = logging.getLogger(__name__)

class TextProcessor:
    def __init__(self, llm_cleanup_fn: Optional[Callable[[str, Optional[str]], str]] = None):
        self.llm_cleanup_fn = llm_cleanup_fn

    def post_process_ocr_text(self, text: str, detected_lang: Optional[str] = None) -> str:
        """
        Applies rules-based cleanup to OCR text.
        """
        if not text:
            return text
        
        # Simple whitespace normalization
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Add more specific rules if needed, e.g., for French spacing
        if detected_lang and detected_lang.lower() in ["fr", "french"]:
            text = re.sub(r"([a-z])\s+([,;:!?])", r"\1\2", text)
        
        return text

    def llm_cleanup(self, text: str, detected_lang: Optional[str]) -> str:
        """
        Calls an optional LLM for advanced text cleanup.
        """
        if not text or self.llm_cleanup_fn is None:
            return text
        
        try:
            return self.llm_cleanup_fn(text, detected_lang).strip()
        except Exception as e:
            logger.warning(f"LLM cleanup failed: {e}")
            return text