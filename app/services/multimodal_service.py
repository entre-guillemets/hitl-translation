import json
import logging
import os
import io
import mimetypes
import tempfile
import traceback
import numpy as np
import pdfplumber
from PIL import Image
from typing import Optional, Callable, List, Dict, Any
import cv2
import base64

from app.ocr_engine.language_detector import LanguageDetector
from app.ocr_engine.manga_ocr import MangaOCREngine
from app.ocr_engine.tesseract_ocr import TesseractOCREngine
from app.processors.image_processor import ImageProcessor
from app.processors.text_processor import TextProcessor
from app.services.transcreation_service import DEFAULT_MODEL

# Optional imports: Whisper
try:
    import whisper
    _HAS_WHISPER = True
except Exception:
    whisper = None  # type: ignore
    _HAS_WHISPER = False

# Optional import: Gemini
try:
    from google import genai
    from google.genai import types as genai_types
    _HAS_GENAI = True
except Exception:
    genai = None  # type: ignore
    genai_types = None  # type: ignore
    _HAS_GENAI = False

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

        # Gemini Vision client for OCR (uses same model/key as transcreation)
        self._gemini_client = None
        if _HAS_GENAI:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                try:
                    self._gemini_client = genai.Client(
                        api_key=api_key,
                        http_options=genai_types.HttpOptions(api_version='v1beta'),
                    )
                    logger.info(f"MultimodalService: Gemini Vision OCR enabled ({DEFAULT_MODEL}).")
                except Exception as e:
                    logger.warning(f"MultimodalService: Gemini client init failed — falling back to Tesseract. {e}")
            else:
                logger.info("MultimodalService: GEMINI_API_KEY not set — using Tesseract OCR only.")

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

    async def _gemini_ocr(self, image_array: np.ndarray) -> Optional[List[str]]:
        """Send the full image to Gemini Vision and return ordered text blocks.

        Returns a list of text strings (one per logical segment, in reading order),
        or None if Gemini is unavailable or the call fails.
        """
        if not self._gemini_client:
            return None
        try:
            pil_img = Image.fromarray(cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB) if len(image_array.shape) == 3 and image_array.shape[2] == 3 else image_array)
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            img_bytes = buf.getvalue()

            prompt = (
                "Extract all visible text from this image. "
                "Return a JSON array of text blocks in reading order (top-to-bottom, left-to-right). "
                "Each element should be one logical text segment — a single line or short paragraph as it visually appears. "
                "Preserve the original language and characters exactly. "
                "Do not translate, explain, or add any text outside the JSON array.\n"
                "Example: [\"First line\", \"Second block\", \"Third segment\"]"
            )

            response = self._gemini_client.models.generate_content(
                model=DEFAULT_MODEL,
                contents=[
                    genai_types.Content(role="user", parts=[
                        genai_types.Part(inline_data=genai_types.Blob(mime_type="image/png", data=img_bytes)),
                        genai_types.Part(text=prompt),
                    ])
                ],
                config=genai_types.GenerateContentConfig(max_output_tokens=2048),
            )

            raw = response.text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw.strip())
            if isinstance(parsed, list) and all(isinstance(t, str) for t in parsed):
                logger.info(f"Gemini Vision OCR: extracted {len(parsed)} text blocks.")
                return [t.strip() for t in parsed if t.strip()]
        except Exception as e:
            logger.warning(f"Gemini Vision OCR failed — falling back to Tesseract text. {e}")
        return None

    async def _extract_text_with_regions(self, image_array: np.ndarray, detected_lang: str) -> List[Dict[str, Any]]:
        """Extract text with bounding box information for image segmentation.

        Bounding boxes come from Tesseract (layout detection).
        Text content comes from Gemini Vision when available, Tesseract otherwise.
        """
        segments = []

        try:
            import pytesseract
            from pytesseract import Output

            # Map detected language to Tesseract lang pack
            tess_lang_map = {'JA': 'jpn', 'FR': 'fra', 'EN': 'eng'}
            tess_lang = tess_lang_map.get(detected_lang.upper(), 'eng')

            # Use original image for Tesseract so bbox coordinates match the displayed image.
            # Preprocessing would change pixel dimensions and invalidate the coordinates.
            # Text quality doesn't matter here — Gemini handles recognition.
            ocr_data = pytesseract.image_to_data(
                image_array,
                lang=tess_lang,
                output_type=Output.DICT,
                config='--psm 3'  # auto page segmentation — handles mixed layouts, bullets, underlines
            )

            # Group words into text blocks
            current_block = []
            current_bbox = None
            segment_id = 1
            confidence = 0

            for i in range(len(ocr_data['text'])):
                confidence = int(ocr_data['conf'][i])
                text = ocr_data['text'][i].strip()

                if confidence > 55 and text:
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
                if detected_lang == 'JA':
                    segment_text = "".join(current_block)
                else:
                    segment_text = " ".join(current_block)

                segments.append({
                    "id": segment_id,
                    "text": segment_text,
                    "confidence": confidence / 100.0,
                    "bbox": current_bbox
                })

            # If psm 3 found nothing (e.g. sparse text over a photo), retry with psm 11
            if not segments:
                logger.info("psm 3 returned 0 segments — retrying with psm 11 (sparse text).")
                ocr_data2 = pytesseract.image_to_data(
                    image_array,
                    lang=tess_lang,
                    output_type=Output.DICT,
                    config='--psm 11',
                )
                # Use same line-grouping logic as psm 3 path so word-level tokens are
                # merged into line-level segments before bbox mapping with Gemini text.
                psm11_block: list[str] = []
                psm11_bbox: dict | None = None
                psm11_conf = 0
                seg_id = 1
                for i in range(len(ocr_data2['text'])):
                    conf2 = int(ocr_data2['conf'][i])
                    text2 = ocr_data2['text'][i].strip()
                    if conf2 > 40 and text2:
                        x, y, w, h = ocr_data2['left'][i], ocr_data2['top'][i], ocr_data2['width'][i], ocr_data2['height'][i]
                        # New line when y jumps by more than 10px below current bbox
                        if psm11_block and psm11_bbox and (y - (psm11_bbox['y'] + psm11_bbox['h'])) > 10:
                            joined = ("".join(psm11_block) if detected_lang == 'JA' else " ".join(psm11_block))
                            segments.append({"id": seg_id, "text": joined, "confidence": psm11_conf / 100.0, "bbox": psm11_bbox})
                            seg_id += 1
                            psm11_block = [text2]
                            psm11_bbox = {"x": x, "y": y, "w": w, "h": h}
                        else:
                            psm11_block.append(text2)
                            psm11_conf = conf2
                            if psm11_bbox is None:
                                psm11_bbox = {"x": x, "y": y, "w": w, "h": h}
                            else:
                                right = max(psm11_bbox["x"] + psm11_bbox["w"], x + w)
                                bottom = max(psm11_bbox["y"] + psm11_bbox["h"], y + h)
                                psm11_bbox["x"] = min(psm11_bbox["x"], x)
                                psm11_bbox["y"] = min(psm11_bbox["y"], y)
                                psm11_bbox["w"] = right - psm11_bbox["x"]
                                psm11_bbox["h"] = bottom - psm11_bbox["y"]
                if psm11_block and psm11_bbox:
                    joined = ("".join(psm11_block) if detected_lang == 'JA' else " ".join(psm11_block))
                    segments.append({"id": seg_id, "text": joined, "confidence": psm11_conf / 100.0, "bbox": psm11_bbox})

            # Replace Tesseract text with Gemini Vision text (bboxes stay from Tesseract)
            gemini_texts = await self._gemini_ocr(image_array)
            img_h, img_w = image_array.shape[:2]

            if gemini_texts and not segments:
                # Tesseract found nothing but Gemini did — use Gemini text with evenly-spaced placeholder bboxes
                step = img_h // max(len(gemini_texts), 1)
                for i, text in enumerate(gemini_texts):
                    segments.append({
                        "id": i + 1,
                        "text": text,
                        "confidence": 1.0,
                        "bbox": {"x": 0, "y": i * step, "w": img_w, "h": step},
                    })
                logger.info(f"Gemini Vision OCR: Tesseract found nothing — used {len(gemini_texts)} Gemini blocks with placeholder bboxes.")
            elif gemini_texts and len(gemini_texts) == len(segments):
                # Perfect count match — substitute text directly, keep Tesseract bboxes
                for seg, gemini_text in zip(segments, gemini_texts):
                    seg["text"] = gemini_text
                    seg["confidence"] = 1.0
                logger.info(f"Gemini Vision OCR: replaced text in {len(segments)} segments.")
            elif gemini_texts:
                # Count mismatch — rebuild from Gemini text, distributing bboxes as best we can
                bboxes = [s["bbox"] for s in segments]
                new_segments = []
                for i, text in enumerate(gemini_texts):
                    bbox = bboxes[i] if i < len(bboxes) else bboxes[-1]
                    new_segments.append({"id": i + 1, "text": text, "confidence": 1.0, "bbox": bbox})
                segments = new_segments
                logger.info(f"Gemini Vision OCR: count mismatch (tess={len(bboxes)}, gemini={len(gemini_texts)}) — used Gemini text with best-effort bbox mapping.")

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