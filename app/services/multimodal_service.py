import logging
import os
import io
import mimetypes
import tempfile
import numpy as np
import pdfplumber
from PIL import Image
from typing import Optional, Callable

from app.ocr_engine.language_detector import LanguageDetector
from app.ocr_engine.manga_ocr import MangaOCREngine
from app.ocr_engine.tesseract_ocr import TesseractOCREngine
from app.processors.image_processor import ImageProcessor
from app.processors.text_processor import TextProcessor

# Optional imports: Whisper
try:
    import whisper
    _HAS_WHISPER = True
except Exception:
    whisper = None  # type: ignore
    _HAS_WHISPER = False

logger = logging.getLogger(__name__)

# This is the single, complete MultimodalService class.
class MultimodalService:
    def __init__(self, llm_cleanup_fn: Optional[Callable[[str, Optional[str]], str]] = None):
        # Initialize component classes
        self.tesseract_engine = TesseractOCREngine()
        self.manga_ocr_engine = MangaOCREngine()
        self.language_detector = LanguageDetector(tesseract_engine=self.tesseract_engine)
        self.image_processor = ImageProcessor()
        self.text_processor = TextProcessor(llm_cleanup_fn=llm_cleanup_fn)
        self.whisper_model = whisper.load_model("base") if _HAS_WHISPER else None

    # The method to extract text from files (images, audio, etc.)
    async def extract_text_from_file(self, file_content: bytes, file_name: str) -> str:
        file_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

        if file_type.startswith("text/"):
            return file_content.decode("utf-8", errors="ignore")

        elif file_type.startswith("application/pdf"):
            raw_text = self._extract_text_from_pdf_bytes(file_content)
            processed_text = self.text_processor.post_process_ocr_text(raw_text)
            return self.text_processor.llm_cleanup(processed_text, None)

        elif file_type.startswith("image/"):
            try:
                image_array = self.image_processor.load_from_bytes(file_content)
                detected_lang = self.language_detector.detect_image_language(image_array)
                preprocessed_image = self.image_processor.preprocess_for_ocr(image_array)

                if detected_lang == "JA":
                    raw_text = self.manga_ocr_engine.recognize(preprocessed_image)
                    if not raw_text:
                        raw_text = self.tesseract_engine.recognize(preprocessed_image, "japanese")
                else:
                    raw_text = self.tesseract_engine.recognize(preprocessed_image, detected_lang)

                processed_text = self.text_processor.post_process_ocr_text(raw_text, detected_lang)
                return self.text_processor.llm_cleanup(processed_text, detected_lang)
            except Exception as e:
                logger.error(f"Image processing failed: {e}")
                return "Text extraction failed."

        elif file_type.startswith("audio/"):
            if not self.whisper_model:
                return "Transcription failed: Whisper model not available."
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                    tmp.write(file_content)
                    tmp_path = tmp.name
                try:
                    result = self.whisper_model.transcribe(tmp_path)
                    transcribed = result.get("text", "")
                finally:
                    os.unlink(tmp_path)
                
                processed_text = self.text_processor.post_process_ocr_text(transcribed)
                return self.text_processor.llm_cleanup(processed_text, None)
            except Exception as e:
                logger.error(f"Audio transcription failed: {e}")
                return "Transcription failed."

        return ""

    # The method to detect language, which was previously a duplicate
    async def detect_language(self, file_content: bytes, file_name: str) -> str:
        """
        Public method to detect the language of a file.
        """
        file_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

        if file_type.startswith("image/"):
            image_array = self.image_processor.load_from_bytes(file_content)
            return self.language_detector.detect_image_language(image_array)

        elif file_type.startswith("audio/"):
            if not self.whisper_model:
                raise ValueError("Whisper model not available.")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name
                
                result = self.whisper_model.transcribe(tmp_path)
                return result.get("language", "EN").upper()

        elif file_type.startswith("text/"):
            from langdetect import detect
            text = file_content.decode("utf-8", errors="ignore")
            if not text:
                return "EN"
            return detect(text).upper()

        return "EN"
    
    # Updated helper method for PDF extraction using pdfplumber
    def _extract_text_from_pdf_bytes(self, file_content: bytes) -> str:
        """
        Extracts text from PDFs, using OCR on scanned pages.
        """
        out_text_parts = []
        
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                # Try to extract text directly first
                page_text = page.extract_text() or ""
                
                if len(page_text.strip()) > 50:
                    out_text_parts.append(page_text)
                    continue

                # Page is likely a scan, perform OCR
                try:
                    # Convert page to image for OCR
                    img = page.to_image(resolution=300)
                    image_array = np.array(img.original)
                    
                    # Use a combined OCR approach for scans
                    lang = self.language_detector.detect_image_language(image_array)
                    if lang == "JA":
                        ocr_text = self.manga_ocr_engine.recognize(image_array)
                        if not ocr_text:
                            ocr_text = self.tesseract_engine.recognize(image_array, "japanese")
                    else:
                        ocr_text = self.tesseract_engine.recognize(image_array, "multilingual")
                        
                    out_text_parts.append(ocr_text)
                except Exception as e:
                    logger.warning(f"PDF page OCR failed: {e}")

        return "\n".join(out_text_parts).strip()

# Create a global instance
multimodal_service = MultimodalService()