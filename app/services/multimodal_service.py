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
                
                # Get segmented OCR results with bounding boxes.
                # effective_lang may be corrected from Gemini's output (overrides pre-detected lang).
                segments, effective_lang = await self._extract_text_with_regions(image_array, detected_lang)
                result["segments"] = segments
                # Normalize: langdetect returns 'JA' but frontend/DB uses 'JP'
                _lang_map = {"JA": "JP"}
                result["detected_language"] = _lang_map.get(effective_lang.upper(), effective_lang.upper())
                
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

    async def _gemini_ocr(self, image_array: np.ndarray) -> Optional[List[Dict[str, Any]]]:
        """Send the full image to Gemini Vision.

        Returns a list of {text, bbox} dicts where bbox is {x, y, w, h} expressed as
        percentages of the image dimensions (0-100), or None on failure.
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
                "Return a JSON array in reading order (top-to-bottom, left-to-right). "
                "Each element must be a JSON object with exactly two keys:\n"
                "  \"text\": one complete semantic unit — a full heading or sentence. "
                "Merge text that belongs to the same heading even if it spans multiple visual lines. "
                "Do NOT split one heading or sentence into separate elements.\n"
                "  \"bbox\": the bounding box of that text as "
                "{\"x\": <left %>, \"y\": <top %>, \"w\": <width %>, \"h\": <height %>} "
                "where each value is a percentage of the image width or height (0-100).\n"
                "Preserve the original language and characters exactly. "
                "Return ONLY the JSON array — no markdown, no explanation.\n"
                "Example: [{\"text\": \"Main heading\", \"bbox\": {\"x\": 10, \"y\": 5, \"w\": 80, \"h\": 12}}, "
                "{\"text\": \"Body sentence.\", \"bbox\": {\"x\": 15, \"y\": 22, \"w\": 70, \"h\": 8}}]"
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
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw.strip())
            if isinstance(parsed, list) and all(isinstance(t, dict) and "text" in t for t in parsed):
                results = [{"text": t["text"].strip(), "bbox": t.get("bbox")} for t in parsed if t.get("text", "").strip()]
                has_bboxes = sum(1 for r in results if r.get("bbox") is not None)
                logger.info(f"Gemini Vision OCR: extracted {len(results)} blocks, {has_bboxes} with bboxes. First bbox: {results[0].get('bbox') if results else None}")
                return results
        except Exception as e:
            logger.warning(f"Gemini Vision OCR failed — falling back to Tesseract. {e}")
        return None

    async def _extract_text_with_regions(self, image_array: np.ndarray, detected_lang: str) -> tuple:
        """Extract text with bounding box information for image segmentation.

        Gemini Vision is the primary path: it returns both text AND bboxes so the
        segmentation editor overlay actually reflects where text lives in the image.
        Tesseract is a pure fallback for when Gemini is unavailable.
        Returns (segments, effective_lang).
        """
        import re as _re

        # Initialize before try so the return is always safe even if an exception fires early.
        effective_lang = detected_lang
        segments = []
        img_h, img_w = image_array.shape[:2]

        try:
            # ── Gemini path: text + real bboxes ──────────────────────────────────────
            gemini_results = await self._gemini_ocr(image_array)

            if gemini_results:
                # Detect language from Gemini's text (much more reliable than Tesseract on complex images)
                all_text = ' '.join(r["text"] for r in gemini_results)
                jp_chars = len(_re.findall(r'[぀-ゟ゠-ヿ一-龯]', all_text))
                if jp_chars > 3:
                    effective_lang = 'JA'
                elif not _re.search(r'[^\x00-\x7F]', all_text):
                    try:
                        from langdetect import detect as _ld
                        effective_lang = _ld(all_text).upper()
                    except Exception:
                        pass

                if effective_lang != detected_lang:
                    logger.info(f"Language overridden from Gemini text: {detected_lang} → {effective_lang}")

                # Convert Gemini bboxes to pixel coordinates.
                # Gemini native format: list [ymin, xmin, ymax, xmax] in 0-1000 units.
                # Fallback: dict {"x", "y", "w", "h"} in 0-100 percentage (from explicit prompt).
                for i, r in enumerate(gemini_results):
                    pixel_bbox = None
                    b = r.get("bbox")
                    if b:
                        if isinstance(b, list) and len(b) >= 4:
                            ymin, xmin, ymax, xmax = b[0], b[1], b[2], b[3]
                            pixel_bbox = {
                                "x": max(0, int(xmin * img_w / 1000)),
                                "y": max(0, int(ymin * img_h / 1000)),
                                "w": max(1, min(img_w, int((xmax - xmin) * img_w / 1000))),
                                "h": max(1, min(img_h, int((ymax - ymin) * img_h / 1000))),
                            }
                        elif isinstance(b, dict):
                            pixel_bbox = {
                                "x": max(0, int(b.get("x", 0) * img_w / 100)),
                                "y": max(0, int(b.get("y", 0) * img_h / 100)),
                                "w": max(1, min(img_w, int(b.get("w", 80) * img_w / 100))),
                                "h": max(1, min(img_h, int(b.get("h", 10) * img_h / 100))),
                            }
                    segments.append({
                        "id": i + 1,
                        "text": r["text"],
                        "confidence": 1.0,
                        "bbox": pixel_bbox,
                    })

                return segments, effective_lang

            # ── Tesseract fallback (Gemini unavailable) ───────────────────────────────
            import pytesseract
            from pytesseract import Output

            tess_lang_map = {'JA': 'jpn', 'FR': 'fra', 'EN': 'eng'}
            tess_lang = tess_lang_map.get(detected_lang.upper(), 'eng')

            ocr_data = pytesseract.image_to_data(
                image_array, lang=tess_lang, output_type=Output.DICT, config='--psm 3'
            )

            current_block: list = []
            current_bbox = None
            segment_id = 1
            confidence = 0

            for i in range(len(ocr_data['text'])):
                confidence = int(ocr_data['conf'][i])
                word = ocr_data['text'][i].strip()
                if confidence > 55 and word:
                    x, y, w, h = (ocr_data['left'][i], ocr_data['top'][i],
                                  ocr_data['width'][i], ocr_data['height'][i])
                    if current_block and (y - (current_bbox['y'] + current_bbox['h'])) > 10:
                        seg_text = "".join(current_block) if detected_lang == 'JA' else " ".join(current_block)
                        segments.append({"id": segment_id, "text": seg_text,
                                         "confidence": confidence / 100.0, "bbox": current_bbox})
                        segment_id += 1
                        current_block = [word]
                        current_bbox = {"x": x, "y": y, "w": w, "h": h}
                    else:
                        current_block.append(word)
                        if current_bbox:
                            right = max(current_bbox["x"] + current_bbox["w"], x + w)
                            bottom = max(current_bbox["y"] + current_bbox["h"], y + h)
                            current_bbox["x"] = min(current_bbox["x"], x)
                            current_bbox["y"] = min(current_bbox["y"], y)
                            current_bbox["w"] = right - current_bbox["x"]
                            current_bbox["h"] = bottom - current_bbox["y"]
                        else:
                            current_bbox = {"x": x, "y": y, "w": w, "h": h}

            if current_block and current_bbox:
                seg_text = "".join(current_block) if detected_lang == 'JA' else " ".join(current_block)
                segments.append({"id": segment_id, "text": seg_text,
                                 "confidence": confidence / 100.0, "bbox": current_bbox})

            # psm 3 found nothing — retry with psm 11 (sparse text layouts)
            if not segments:
                logger.info("psm 3 returned 0 segments — retrying with psm 11.")
                ocr_data2 = pytesseract.image_to_data(
                    image_array, lang=tess_lang, output_type=Output.DICT, config='--psm 11'
                )
                block: list = []
                bbx = None
                conf11 = 0
                sid = 1
                for i in range(len(ocr_data2['text'])):
                    c = int(ocr_data2['conf'][i])
                    w2 = ocr_data2['text'][i].strip()
                    if c > 40 and w2:
                        x, y, w, h = (ocr_data2['left'][i], ocr_data2['top'][i],
                                      ocr_data2['width'][i], ocr_data2['height'][i])
                        if block and bbx and (y - (bbx['y'] + bbx['h'])) > 10:
                            joined = "".join(block) if detected_lang == 'JA' else " ".join(block)
                            segments.append({"id": sid, "text": joined,
                                             "confidence": conf11 / 100.0, "bbox": bbx})
                            sid += 1
                            block = [w2]
                            bbx = {"x": x, "y": y, "w": w, "h": h}
                        else:
                            block.append(w2)
                            conf11 = c
                            if bbx is None:
                                bbx = {"x": x, "y": y, "w": w, "h": h}
                            else:
                                right = max(bbx["x"] + bbx["w"], x + w)
                                bottom = max(bbx["y"] + bbx["h"], y + h)
                                bbx["x"] = min(bbx["x"], x)
                                bbx["y"] = min(bbx["y"], y)
                                bbx["w"] = right - bbx["x"]
                                bbx["h"] = bottom - bbx["y"]
                if block and bbx:
                    joined = "".join(block) if detected_lang == 'JA' else " ".join(block)
                    segments.append({"id": sid, "text": joined,
                                     "confidence": conf11 / 100.0, "bbox": bbx})

        except Exception as e:
            logger.error(f"Region extraction failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            try:
                if detected_lang == 'JA':
                    text = self.manga_ocr_engine.recognize(image_array)
                else:
                    text = self.tesseract_engine.recognize(image_array, lang=detected_lang)
                segments = [{"id": 1, "text": text, "confidence": 0.5,
                             "bbox": {"x": 0, "y": 0, "w": img_w, "h": img_h}}]
                logger.info("Using fallback extraction, created 1 segment covering entire image")
            except Exception as fallback_error:
                logger.error(f"Fallback extraction also failed: {fallback_error}")
                segments = []

        return segments, effective_lang

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
                        ocr_segments, _ = await self._extract_text_with_regions(image_array, lang)

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

        text = text.strip()
        # Double newline = paragraph boundary; single newline = visual line wrap (join with space)
        text = re.sub(r'\n{2,}', '\x00', text)
        text = re.sub(r'\n', ' ', text)
        text = re.sub(r' {2,}', ' ', text)

        paragraphs = [p.strip() for p in text.split('\x00') if p.strip()]

        segments = []
        for para in paragraphs:
            # Split at sentence endings only when followed by a space and an uppercase/CJK start
            sents = re.split(r'(?<=[.!?。！？])\s+(?=[A-ZÀ-Üa-zà-üぁ-鿿])', para)
            for s in sents:
                s = s.strip()
                if s and len(s) > 3:
                    segments.append(s)

        return segments if segments else [text]

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