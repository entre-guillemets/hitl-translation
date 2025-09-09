import logging
import numpy as np
import cv2
from PIL import Image
from manga_ocr import MangaOcr

logger = logging.getLogger(__name__)

class MangaOCREngine:
    def __init__(self):
        try:
            self.manga_ocr = MangaOcr()
            logger.info("Manga OCR initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Manga OCR: {e}")
            self.manga_ocr = None

    def recognize(self, image_array: np.ndarray) -> str:
        """
        Recognizes Japanese text in an image using Manga OCR.
        """
        if not self.manga_ocr:
            logger.warning("Manga OCR is not available.")
            return ""

        try:
            # Manga OCR requires a PIL Image
            if image_array.ndim == 2:
                pil_image = Image.fromarray(image_array, mode='L')
            else:
                pil_image = Image.fromarray(cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB))
            
            result = self.manga_ocr(pil_image)
            return result.strip()
        except Exception as e:
            logger.error(f"Manga OCR failed: {e}")
            return ""