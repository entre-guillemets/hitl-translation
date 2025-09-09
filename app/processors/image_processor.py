import cv2
import numpy as np
from PIL import Image
import logging
import io

logger = logging.getLogger(__name__)

class ImageProcessor:
    def load_from_bytes(self, file_content: bytes) -> np.ndarray:
        """
        Loads image bytes into a NumPy array.
        """
        image = Image.open(io.BytesIO(file_content))
        return np.array(image)

    def preprocess_for_ocr(self, image_array: np.ndarray) -> np.ndarray:
        """
        Applies a standardized preprocessing pipeline.
        """
        try:
            if image_array.ndim == 3:
                image_array = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)

            # Resize to a consistent DPI (e.g., 300 DPI) for better OCR
            h, w = image_array.shape
            scale = 1200 / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            image_array = cv2.resize(image_array, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

            # Standard Otsu's thresholding for binarization
            _, binary_image = cv2.threshold(image_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return binary_image
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return image_array