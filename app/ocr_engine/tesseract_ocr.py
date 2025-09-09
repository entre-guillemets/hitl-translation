import pytesseract
import numpy as np
import cv2
from PIL import Image
import re
import logging

logger = logging.getLogger(__name__)

class TesseractOCREngine:
    def __init__(self):
        self.lang_mappings = {
            "english": "eng",
            "french": "fra", 
            "japanese": "jpn",
            "japanese+english": "jpn+eng",
            "multilingual": "eng+fra+jpn",            
            "EN": "eng",
            "FR": "fra", 
            "JA": "jpn",
            "en": "eng",
            "fr": "fra",
            "ja": "jpn"
        }

    def _fix_japanese_spacing(self, text: str) -> str:
        """Removes spaces inserted by Tesseract in Japanese text."""
        if not text:
            return text
        # Regex to remove spaces between specific character ranges
        text = re.sub(r'(?<=[ぁ-ヿ])\s+(?=[ぁ-ヿ])', '', text) # Hiragana, Katakana
        text = re.sub(r'(?<=[一-龯])\s+(?=[一-龯])', '', text) # Kanji
        text = re.sub(r'(?<=[ぁ-ヿ一-龯])\s+(?=[ぁ-ヿ一-龯])', '', text) # Mixed
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def recognize(self, image_array: np.ndarray, lang: str) -> str:
        """
        Recognizes text using Tesseract with a specific language profile.
        """
        tesseract_lang = self.lang_mappings.get(lang, "english")

        try:
            if image_array.ndim == 2:
                pil_image = Image.fromarray(image_array, mode='L')
            else:
                pil_image = Image.fromarray(cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB))
            
            results = []
            
            # Use multiple PSM modes to find the best result
            if "jpn" in tesseract_lang:
                configs = ['--oem 1 --psm 6', '--oem 1 --psm 8', '--oem 1 --psm 13']
            else:
                configs = ['--oem 1 --psm 3']
                
            for config in configs:
                result = pytesseract.image_to_string(pil_image, lang=tesseract_lang, config=config).strip()
                if result:
                    results.append(result)
            
            if not results:
                return ""
            
            best_text = results[0]
            if "jpn" in tesseract_lang:
                # For Japanese, select the result with the most Japanese characters
                best_text = max(results, key=lambda x: len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', x)))
                return self._fix_japanese_spacing(best_text)
            
            return best_text
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return ""