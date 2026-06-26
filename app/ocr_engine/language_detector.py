import logging
import pytesseract
import re
import cv2
import numpy as np
from PIL import Image
from langdetect import detect, DetectorFactory
from typing import Optional

logger = logging.getLogger(__name__)

# To ensure consistent language detection results across runs
DetectorFactory.seed = 0

class LanguageDetector:
    def __init__(self, tesseract_engine):
        self.tesseract_engine = tesseract_engine
    
    def _detect_coherence(self, text: str) -> bool:
        """
        Checks for the presence of coherent character sequences.
        """
        if not text:
            return False
        # Looks for at least two consecutive Japanese characters
        japanese_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]{2,}')
        return bool(japanese_pattern.search(text))
    
    def detect_image_language(self, image_array: np.ndarray) -> str:
        """
        Performs a fast, initial language guess on the entire image.
        Falls back to Japanese-specific OCR when multilingual returns too little text
        (common with complex images: speech bubbles, coloured backgrounds, decorative layouts).
        Note: _extract_text_with_regions also runs Gemini first and can override this
        result via its own language detection on Gemini's output.
        """
        try:
            text = self.tesseract_engine.recognize(image_array, "multilingual")

            # Japanese check on multilingual output first
            jp_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text))
            if jp_chars > 3 and self._detect_coherence(text):
                return "JA"

            if not text.strip() or len(text.strip()) < 15:
                # Multilingual Tesseract failed on this image (complex layout, coloured bg, etc.)
                # Try a Japanese-specific pass \u2014 kanji/kana are very distinctive even in partial reads
                try:
                    text_jpn = self.tesseract_engine.recognize(image_array, "JA")
                    jp_chars_jpn = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text_jpn))
                    if jp_chars_jpn > 3:
                        return "JA"
                except Exception:
                    pass
                if not text.strip():
                    logger.info("Language detection returned no text, defaulting to English.")
                    return "EN"

            detected_lang = detect(text)
            return detected_lang.upper()

        except Exception as e:
            logger.warning(f"Language detection failed, defaulting to English: {e}")
            return "EN"