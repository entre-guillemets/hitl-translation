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
        """
        try:
            # Revert to a single, multilingual OCR pass on the full image for reliability.
            # The 'multilingual' profile will attempt to detect all languages at once.
            text = self.tesseract_engine.recognize(image_array, "multilingual")
            
            if not text.strip():
                # If still no text, the image is likely not a text image.
                logger.info("Language detection returned no text, defaulting to English.")
                return "EN"
            
            # Now, use a reliable library to detect the language from the extracted text.
            detected_lang = detect(text)
            
            # Override with a higher confidence check for Japanese characters.
            # This handles cases where langdetect might misclassify a small snippet.
            jp_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text))
            if jp_chars > 3 and self._detect_coherence(text):
                return "JA"
            
            return detected_lang.upper()
            
        except Exception as e:
            logger.warning(f"Language detection failed, defaulting to English: {e}")
            return "EN"