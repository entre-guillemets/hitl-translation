import logging
import os
import io
import mimetypes
import tempfile
import numpy as np
import pdfplumber
from PIL import Image
from typing import Optional, Callable, List, Dict, Any, Tuple
import cv2
import base64

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

class MultimodalService:
    def __init__(self, llm_cleanup_fn: Optional[Callable[[str, Optional[str]], str]] = None):
        # Initialize component classes
        self.tesseract_engine = TesseractOCREngine()
        self.manga_ocr_engine = MangaOCREngine()
        self.language_detector = LanguageDetector(tesseract_engine=self.tesseract_engine)
        self.image_processor = ImageProcessor()
        self.text_processor = TextProcessor(llm_cleanup_fn=llm_cleanup_fn)
        self.whisper_model = whisper.load_model("base") if _HAS_WHISPER else None

    async def extract_text_from_file_with_segmentation(self, file_content: bytes, file_name: str) -> Dict[str, Any]:
        file_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        
        result = {
            "segments": [],
            "media_type": None,
            "media_data": None,
            "detected_language": "EN"
        }

        if file_type.startswith("text/"):
            text = file_content.decode("utf-8", errors="ignore")
            sentences = self._split_text_into_sentences(text)
            result["segments"] = [
                {
                    "id": i + 1,
                    "text": sentence.strip(),
                    "confidence": 1.0,
                    "bbox": None,
                    "timestamp": None
                }
                for i, sentence in enumerate(sentences) if sentence.strip()
            ]
            result["media_type"] = "text"

        elif file_type.startswith("image/"):
            try:
                image_array = self.image_processor.load_from_bytes(file_content)
                detected_lang = self.language_detector.detect_image_language(image_array)
                result["detected_language"] = detected_lang
                result["media_type"] = "image"
                
                # Store image data for frontend display
                base64_data = base64.b64encode(file_content).decode()
                result["media_data"] = base64_data
                
                # Get segmented OCR results with bounding boxes
                segments = await self._extract_text_with_regions(image_array, detected_lang)
                result["segments"] = segments
                
            except Exception as e:
                logger.error(f"Image processing failed: {e}")
                result["segments"] = [{"id": 1, "text": "Text extraction failed.", "confidence": 0.0}]

        elif file_type.startswith("audio/"):
            if not self.whisper_model:
                result["segments"] = [{"id": 1, "text": "Transcription failed: Whisper model not available.", "confidence": 0.0}]
                return result
                
            base64_data = base64.b64encode(file_content).decode()
            result["media_type"] = "audio"
            result["media_data"] = base64_data
            
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                    tmp.write(file_content)
                    tmp_path = tmp.name
                
                try:
                    whisper_result = self.whisper_model.transcribe(
                        tmp_path, 
                        word_timestamps=True,
                        verbose=True
                    )
                    
                    result["detected_language"] = whisper_result.get("language", "EN").upper()
                    
                    segments = []
                    for i, segment in enumerate(whisper_result.get("segments", [])):
                        segments.append({
                            "id": i + 1,
                            "text": segment["text"].strip(),
                            "confidence": segment.get("avg_logprob", 0.0),
                            "bbox": None,
                            "timestamp": {
                                "start": segment["start"],
                                "end": segment["end"]
                            }
                        })
                    result["segments"] = segments
                    
                finally:
                    os.unlink(tmp_path)
                    
            except Exception as e:
                logger.error(f"Audio transcription failed: {e}")
                result["segments"] = [{"id": 1, "text": "Transcription failed.", "confidence": 0.0}]

            
        elif file_type.startswith("application/pdf"):
            segments = await self._extract_pdf_with_regions(file_content)
            result["segments"] = segments
            result["media_type"] = "pdf"

        return result

    async def _extract_text_with_regions(self, image_array: np.ndarray, detected_lang: str) -> List[Dict[str, Any]]:
        """Extract text with bounding box information for image segmentation"""
        segments = []

        try:
            import pytesseract
            from pytesseract import Output

            # Get word-level data with bounding boxes
            ocr_data = pytesseract.image_to_data(
                image_array,
                lang='jpn' if detected_lang == 'JA' else 'eng',
                output_type=Output.DICT,
                config='--psm 6'
            )

            # Group words into text blocks
            current_block = []
            current_bbox = None
            segment_id = 1
            confidence = 0

            for i in range(len(ocr_data['text'])):
                confidence = int(ocr_data['conf'][i])
                text = ocr_data['text'][i].strip()

                if confidence > 30 and text:
                    x, y, w, h = (
                        ocr_data['left'][i],
                        ocr_data['top'][i],
                        ocr_data['width'][i],
                        ocr_data['height'][i]
                    )

                    # Check if this is a new line (y position significantly different)
                    if current_block and (y - (current_bbox['y'] + current_bbox['h'])) > 10:
                        # Save the current block before starting a new one
                        if current_block:
                            # ✅ FIX: Remove spaces for Japanese, keep them for other languages
                            if detected_lang == 'JA':
                                segment_text = "".join(current_block)  # No spaces for Japanese
                            else:
                                segment_text = " ".join(current_block)  # Spaces for other languages

                            segments.append({
                                "id": segment_id,
                                "text": segment_text,
                                "confidence": confidence / 100.0,
                                "bbox": current_bbox
                            })
                            segment_id += 1

                        # Start new block
                        current_block = [text]
                        current_bbox = {"x": x, "y": y, "w": w, "h": h}
                    else:
                        # Add to current block
                        current_block.append(text)

                        # Expand bounding box to include this text
                        if current_bbox:
                            right = max(current_bbox["x"] + current_bbox["w"], x + w)
                            bottom = max(current_bbox["y"] + current_bbox["h"], y + h)
                            current_bbox["x"] = min(current_bbox["x"], x)
                            current_bbox["y"] = min(current_bbox["y"], y)
                            current_bbox["w"] = right - current_bbox["x"]
                            current_bbox["h"] = bottom - current_bbox["y"]
                        else:
                            current_bbox = {"x": x, "y": y, "w": w, "h": h}

            # Add the last segment
            if current_block and current_bbox:
                # ✅ FIX: Same logic for the last segment
                if detected_lang == 'JA':
                    segment_text = "".join(current_block)  # No spaces for Japanese
                else:
                    segment_text = " ".join(current_block)  # Spaces for other languages

                segments.append({
                    "id": segment_id,
                    "text": segment_text,
                    "confidence": confidence / 100.0,
                    "bbox": current_bbox
                })

        except Exception as e:
            logger.error(f"Region extraction failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Fallback: Extract text without regions using Tesseract or Manga OCR
            try:
                if detected_lang == 'JA':
                    # Use Manga OCR for Japanese as fallback
                    text = self.manga_ocr_engine.extract_text(image_array)
                else:
                    # Use standard Tesseract for other languages
                    text = self.tesseract_engine.extract_text(image_array, lang=detected_lang)

                # Create a single segment covering the whole image
                h, w = image_array.shape[:2]
                segments = [{
                    "id": 1,
                    "text": text,
                    "confidence": 0.5,  # Lower confidence for fallback
                    "bbox": {"x": 0, "y": 0, "w": w, "h": h}
                }]

                logger.info(f"Using fallback extraction, created 1 segment covering entire image")

            except Exception as fallback_error:
                logger.error(f"Fallback extraction also failed: {fallback_error}")
                # Return empty segments if everything fails
                segments = []

        return segments

    async def _extract_pdf_with_regions(self, file_content: bytes) -> List[Dict[str, Any]]:
        """Extract PDF text with page information"""
        segments = []
        segment_id = 1
        
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                
                if len(page_text.strip()) > 50:
                    # Text-based PDF
                    sentences = self._split_text_into_sentences(page_text)
                    for sentence in sentences:
                        if sentence.strip():
                            segments.append({
                                "id": segment_id,
                                "text": sentence.strip(),
                                "confidence": 1.0,
                                "bbox": None,
                                "page": page_num + 1
                            })
                            segment_id += 1
                else:
                    # Scanned PDF - use OCR
                    try:
                        img = page.to_image(resolution=300)
                        image_array = np.array(img.original)
                        
                        lang = self.language_detector.detect_image_language(image_array)
                        ocr_segments = await self._extract_text_with_regions(image_array, lang)
                        
                        for segment in ocr_segments:
                            segment["id"] = segment_id
                            segment["page"] = page_num + 1
                            segments.append(segment)
                            segment_id += 1
                            
                    except Exception as e:
                        logger.warning(f"PDF page {page_num + 1} OCR failed: {e}")

        return segments

    def _split_text_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences for segmentation"""
        import re
        
        # Simple sentence splitting - you might want to use a more sophisticated library like spaCy
        sentences = re.split(r'[.!?。！？]\s*', text.strip())
        
        # Clean up and filter empty sentences
        clean_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 3:  # Filter very short fragments
                clean_sentences.append(sentence)
        
        return clean_sentences

    # Keep existing methods unchanged
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

    async def detect_language(self, file_content: bytes, file_name: str) -> str:
        """Public method to detect the language of a file."""
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
                # Removed the unnecessary `base64` reference here
                return result.get("language", "EN").upper()

        elif file_type.startswith("text/"):
            from langdetect import detect
            text = file_content.decode("utf-8", errors="ignore")
            if not text:
                return "EN"
            return detect(text).upper()

        return "EN"
    
    def _extract_text_from_pdf_bytes(self, file_content: bytes) -> str:
        """Extracts text from PDFs, using OCR on scanned pages."""
        out_text_parts = []
        
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                
                if len(page_text.strip()) > 50:
                    out_text_parts.append(page_text)
                    continue

                try:
                    img = page.to_image(resolution=300)
                    image_array = np.array(img.original)
                    
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