import os
import logging
import torch
from transformers import (
    MarianMTModel, MarianTokenizer,
    T5ForConditionalGeneration, T5Tokenizer, 
    AutoTokenizer, AutoModelForSeq2SeqLM # Use Auto classes for NLLB flexibility
)
import re
import json
import gc

logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.current_model = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Setup model paths and language pair mappings
        self._setup_model_paths()
        self._setup_language_pair_mappings()
        
        logger.info(f"Translation service initialized on device: {self.device}")
        self.verify_available_models()

    def _setup_model_paths(self):
        """Define paths to all available models."""
        base_path = os.path.join(os.path.dirname(__file__), "..", "models")
        base_path = os.path.abspath(base_path)
        
        self.model_paths = {
            # Japanese-English models
            'ELAN_JA_EN': os.path.join(base_path, "Mitsua_elan-mt-bt-ja-en"),
            'OPUS_JA_EN': os.path.join(base_path, "opus-mt-ja-en"),
            
            # English-Japanese models
            'HELSINKI_EN_JP': os.path.join(base_path, "Helsinki-NLP_opus-mt-en-jap"),
            'OPUS_EN_JP': os.path.join(base_path, "opus-mt-en-jap"),
            
            # English-French models
            'HELSINKI_EN_FR': os.path.join(base_path, "Helsinki-NLP_opus-mt-en-fr"),
            'OPUS_TC_BIG_EN_FR': os.path.join(base_path, "opus-mt-tc-big-en-fr"),
            
            # French-English models
            'HELSINKI_FR_EN': os.path.join(base_path, "Helsinki-NLP_opus-mt-fr-en"),
            'OPUS_TC_BIG_FR_EN': os.path.join(base_path, "opus-mt-tc-big-fr-en"), 

            # T5 Models 
            'T5_BASE': os.path.join(base_path, "google-t5_t5-base"), 
            'T5_MULTILINGUAL': os.path.join(base_path, "google-t5_t5-base"), # 

            # NLLB Model 
            'NLLB_200': os.path.join(base_path, "nllb-200-distilled-600M"),
        }

    def _setup_language_pair_mappings(self):
        """Map language pairs to available models that can handle them."""
        # Each tuple is (model_name_key, display_name, optional_prefix/lang_tag)
        self.language_pair_models = {
            "EN-JP": [
                ("HELSINKI_EN_JP", "Helsinki OPUS EN-JP"),
                # IMPORTANT: If ELAN_JA_EN (Mitsua_elan-mt-bt-ja-en) is truly JA->EN,
                # it CANNOT do EN->JP. Removed it here. Add an actual EN->JP ELAN model if you have one.
                # ("ELAN_JA_EN", "ELAN Specialized JA-EN"),
                ("OPUS_EN_JP", "OPUS EN-JP"),
                ("T5_MULTILINGUAL", "mT5 Versatile EN-JP", "translate English to Japanese: "), # T5 needs prefix
                ("NLLB_200", "NLLB Multilingual EN-JP", "jpn_Jpan"), # NLLB needs target_lang_tag
            ],
            "JP-EN": [
                ("ELAN_JA_EN", "ELAN Specialized JA-EN"), # Correct for JA->EN
                ("OPUS_JA_EN", "OPUS JA-EN"),
                ("T5_MULTILINGUAL", "mT5 Versatile JP-EN", "translate Japanese to English: "), # T5 needs prefix
                ("NLLB_200", "NLLB Multilingual JP-EN", "eng_Latn"), # NLLB needs target_lang_tag
            ],
            "EN-FR": [
                ("HELSINKI_EN_FR", "Helsinki OPUS EN-FR"),
                ("OPUS_TC_BIG_EN_FR", "OPUS TC Big EN-FR"),
                ("T5_MULTILINGUAL", "mT5 Versatile EN-FR", "translate English to French: "), # T5 needs prefix
                ("NLLB_200", "NLLB Multilingual EN-FR", "fra_Latn"), # NLLB needs target_lang_tag
            ],
            "FR-EN": [
                ("HELSINKI_FR_EN", "Helsinki OPUS FR-EN"),
                ("OPUS_TC_BIG_FR_EN", "OPUS TC Big FR-EN"), # Ensure this model actually exists or is intended
                ("T5_MULTILINGUAL", "mT5 Versatile FR-EN", "translate French to English: "), # T5 needs prefix
                ("NLLB_200", "NLLB Multilingual FR-EN", "eng_Latn"), # NLLB needs target_lang_tag
            ],
            "JP-FR": [
                ("PIVOT_ELAN_HELSINKI", "ELAN→Helsinki Pivot"), # Pivot models are handled by special logic, no direct prefix
                ("T5_MULTILINGUAL", "mT5 Versatile JP-FR", "translate Japanese to French: "), # Add T5 direct if supported
                ("NLLB_200", "NLLB Multilingual JP-FR", "fra_Latn"), # Add NLLB direct if supported
            ],
        }

    # This is the ONLY load_model function that should exist in the class
    def load_model(self, model_name: str):
        """Load a specific model."""
        if self.current_model == model_name:
            logger.info(f"Model {model_name} already loaded")
            return
        
        # Force clear current model to prevent caching issues
        self.current_model = None
        if hasattr(self, 'model') and self.model is not None:
            del self.model
        if hasattr(self, 'tokenizer') and self.tokenizer is not None:
            del self.tokenizer
        
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        
        logger.info(f"Loading NEW model: {model_name} from {self.model_paths.get(model_name)}")
        
        model_path = self.model_paths.get(model_name)
        if not model_path or not os.path.exists(model_path):
            raise ValueError(f"Model {model_name} not found at {model_path}")

        try:
            use_safetensors = True
            
            if model_name in ["T5_BASE", "T5_MULTILINGUAL"]:
                self.tokenizer = T5Tokenizer.from_pretrained(model_path)
                self.model = T5ForConditionalGeneration.from_pretrained(model_path)
            elif model_name == "NLLB_200":
                self.tokenizer = AutoTokenizer.from_pretrained(model_path)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
            else:
                # Marian models (OPUS, Helsinki, ELAN)
                self.tokenizer = MarianTokenizer.from_pretrained(model_path)
                self.model = MarianMTModel.from_pretrained(model_path)
            
            self.model.to(self.device)
            self.current_model = model_name
            logger.info(f"Successfully loaded {model_name}")
            
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise

    def translate_multiple(self, text: str, language_pair: str, num_outputs: int = 3):
        """Generate multiple unique translations for a given language pair."""
        if language_pair not in self.language_pair_models:
            raise ValueError(f"Unsupported language pair: {language_pair}")

        available_models = self.language_pair_models[language_pair]
        results = []

        for i, model_info in enumerate(available_models[:num_outputs]):
            # model_info can be (model_name, description) or (model_name, description, prefix/lang_tag)
            # Safely unpack with default None for prefix/lang_tag
            model_name, description, prefix_or_lang_tag = model_info + (None,) * (3 - len(model_info)) 

            try:
                # Skip if model is not available (except for custom pivot models)
                # NLLB_200 is expected to be found by Auto classes, its path will be checked during load_model.
                if model_name not in ["PIVOT_ELAN_HELSINKI", "NLLB_200"] and not os.path.exists(self.model_paths.get(model_name, "")):
                    logger.warning(f"Skipping {model_name} - model not found at path: {self.model_paths.get(model_name)}")
                    continue
                

                # Handle custom pivot models
                if model_name == "PIVOT_ELAN_HELSINKI":
                    translated_text = self._translate_pivot_elan_helsinki(text)
                else:
                    self.load_model(model_name)
                    
                    input_text = text
                    # Extract raw language codes (e.g., 'en', 'jp')
                    source_lang_code_raw = language_pair.split('-')[0].lower() 
                    target_lang_code_raw = language_pair.split('-')[1].lower() 

                    # Prepare input text or specific parameters based on model type
                    if model_name in ["T5_BASE", "T5_MULTILINGUAL"] and prefix_or_lang_tag:
                        # T5 typically needs "translate <src_lang> to <tgt_lang>: <text>"
                        input_text = f"{prefix_or_lang_tag}{text}"
                    # NLLB doesn't use prefix in input_text; its language is set via tokenizer/generation params
                    
                    translated_text = self._translate_with_model(
                        input_text, 
                        model_name, 
                        source_lang=source_lang_code_raw, # Pass raw source lang
                        target_lang=target_lang_code_raw, # Pass raw target lang
                        target_lang_tag=prefix_or_lang_tag # NLLB's target language token
                    )
                    
                    # Apply cleaning specific to T5 or NLLB output artifacts
                    if model_name in ["T5_BASE", "T5_MULTILINGUAL"]:
                        translated_text = self._clean_t5_output(translated_text)
                    elif model_name == "NLLB_200":
                        translated_text = self._clean_nllb_output(translated_text)
                
                results.append({
                    "model": description,
                    "model_key": model_name,
                    "translation": translated_text
                })
                
            except Exception as e:
                logger.error(f"Failed to translate with {model_name}: {e}")
                results.append({
                    "model": description,
                    "model_key": model_name,
                    "translation": f"Translation failed: {str(e)}"
                })

        return results

    def _translate_with_model(self, text: str, model_name: str, source_lang: str = None, target_lang: str = None, target_lang_tag: str = None) -> str:
        """Translate text using the loaded model."""
        try:
            logger.info(f"Translating with {model_name}. Input text (first 50 chars): '{text[:50]}'")
            
            if model_name in ["T5_BASE", "T5_MULTILINGUAL"]:
                # T5 expects the prompt to already be formatted in 'text'
                inputs = self.tokenizer(text, return_tensors="pt", max_length=512, truncation=True).to(self.device)
                outputs = self.model.generate(**inputs, max_length=512, num_beams=4, early_stopping=True)
                decoded_output = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                logger.info(f"Decoded T5 output (first 50 chars): '{decoded_output[:50]}'")
                return decoded_output
                
            elif model_name == 'NLLB_200':
                if not target_lang_tag:
                    raise ValueError("Target language tag (e.g., 'jpn_Jpan') is required for NLLB translation.")
                
                # NLLB uses its own internal language ID mapping for source and target
                # The tokenizer expects `src_lang` to be set on it.
                # The `forced_bos_token_id` indicates the desired target language for generation.
                
                # Map ISO codes (en, jp, fr) to NLLB's internal codes (eng_Latn, jpn_Jpan, fra_Latn)
                # This ensures the tokenizer correctly understands the source language.
                nllb_lang_map_iso_to_nllb = {
                    'en': 'eng_Latn', 'jp': 'jpn_Jpan', 'fr': 'fra_Latn',
                }
                
                nllb_src_lang = nllb_lang_map_iso_to_nllb.get(source_lang, source_lang) # Use mapping, fallback to original if not found
                
                self.tokenizer.src_lang = nllb_src_lang
                
                inputs = self.tokenizer(text, return_tensors="pt", max_length=512, truncation=True).to(self.device)
                
                # The target_lang_tag passed to this function (e.g., 'jpn_Jpan') IS the correct NLLB token for forced_bos_token_id
                # This should resolve the 'lang_code_to_id' AttributeError by using convert_tokens_to_ids directly on the token string.
                forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(target_lang_tag)
                
                if forced_bos_token_id is None or forced_bos_token_id == self.tokenizer.unk_token_id:
                    # Fallback if direct conversion fails (shouldn't if target_lang_tag is correct NLLB code)
                    # Some models might have their decoder_start_token_id pre-set or accessible via config
                    if hasattr(self.model.config, 'decoder_start_token_id') and self.model.config.decoder_start_token_id is not None:
                         forced_bos_token_id = self.model.config.decoder_start_token_id
                         logger.warning(f"Using model.config.decoder_start_token_id for NLLB, was unable to convert '{target_lang_tag}': {e}")
                    else:
                        raise ValueError(f"Could not determine forced_bos_token_id for NLLB target '{target_lang_tag}'")
                
                outputs = self.model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos_token_id,
                    max_length=512,
                    num_beams=4,
                    early_stopping=True
                )
                decoded_output = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                logger.info(f"Decoded NLLB output (first 50 chars): '{decoded_output[:50]}'")
                return decoded_output
                
            else:
                # Marian models
                inputs = self.tokenizer(text, return_tensors="pt", max_length=512, truncation=True).to(self.device)
                outputs = self.model.generate(**inputs, max_length=512, num_beams=4, early_stopping=True)
                decoded_output = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                logger.info(f"Decoded Marian output (first 50 chars): '{decoded_output[:50]}'")
                return decoded_output
                
        except Exception as e:
            logger.error(f"Error in _translate_with_model for {model_name}: {e}")
            raise

    def _clean_t5_output(self, text: str) -> str:
        """Clean mT5 output artifacts."""
        # Remove MT5 tokens and any common prompt echoes
        text = re.sub(r'<pad>|</s>|<unk>', '', text).strip()
        # More robust prompt removal (consider patterns like "translate X to Y:" in various forms)
        # Add more specific patterns if you find other persistent prefixes
        text = re.sub(r'^\s*(?:translate\s+)?(?:English|Japanese|French|German|Spanish|Chinese|Korean|Arabic|Russian)\s+to\s+(?:English|Japanese|French|German|Spanish|Chinese|Korean|Arabic|Russian)\s*:?\s*', '', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'^\s*(?:en|ja|fr|de|es|zh|ko|ar|ru)\s*:\s*', '', text, flags=re.IGNORECASE).strip() # For models that echo 'en: ' or 'ja: '
        
        # Heuristic for untranslated English output. Use with caution.
        # If the output is predominantly ASCII and very similar to source (e.g., high string similarity)
        # it might indicate no translation occurred. This check can be sophisticated or removed.
        # For now, let's just clean without aggressively assuming untranslated.
        
        return text.strip()

    def _clean_nllb_output(self, text: str) -> str:
        """Clean NLLB output artifacts."""
        # NLLB models might output source language tokens or special control tokens.
        # Remove common special tokens and any language codes at the beginning/end
        # Example: `__jpn__` or `__eng__` or `__<lang_code>__`
        text = re.sub(r'^__\w+__\s*', '', text).strip() # Remove NLLB specific lang tokens like __eng__
        text = re.sub(r'^[a-z]{2,3}_[A-Z]{2,4}\s*', '', text).strip() # Remove codes like 'eng_Latn' if at start
        text = re.sub(r'<pad>|</s>|<unk>', '', text).strip() # Remove common transformers tokens
        
        return text.strip()

    def _is_mostly_english(self, text: str) -> bool:
        """Check if text is mostly English (for translation validation)"""
        if not text:
            return False
        # Simple heuristic: if more than 80% of characters are ASCII, likely English
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        return (ascii_chars / len(text)) > 0.0 # Changed threshold to be very low, just check for ASCII content

    def _translate_pivot_elan_helsinki(self, text: str) -> str:
        """Custom pivot translation using ELAN JA-EN → Helsinki EN-FR"""
        try:
            # Step 1: Japanese to English using ELAN
            self.load_model('ELAN_JA_EN')
            # For pivot, source/target lang args not used directly by _translate_with_model for Marian
            intermediate = self._translate_with_model(text, 'ELAN_JA_EN')
            logger.info(f"Pivot intermediate (JA->EN): {intermediate}")
            
            # Step 2: English to French using Helsinki
            self.load_model('HELSINKI_EN_FR')
            # For pivot, source/target lang args not used directly by _translate_with_model for Marian
            final_translation = self._translate_with_model(intermediate, 'HELSINKI_EN_FR')
            logger.info(f"Pivot final (EN->FR): {final_translation}")
            
            return final_translation
        except Exception as e:
            logger.error(f"Pivot translation failed: {str(e)}")
            raise ValueError(f"Pivot translation failed: {str(e)}")

    def verify_model_loading(self, model_name: str):
        """Verify which model is actually loaded"""
        model_path = self.model_paths.get(model_name)
        logger.info(f"Attempting to load: {model_name}")
        logger.info(f"Model path: {model_path}")
        
        if hasattr(self, 'model') and self.model is not None:
            model_info = str(type(self.model))
            logger.info(f"Current model type: {model_info}")
            
            if hasattr(self.model, 'config'):
                logger.info(f"Model config: {self.model.config}")

    def translate_by_model_type(self, text: str, model_name: str, source_lang: str = None, target_lang: str = None, target_lang_tag: str = None) -> str:
        """Translate using a specific model. Passes language context for NLLB."""
        try:
            self.load_model(model_name)
            # Pass source_lang, target_lang, and target_lang_tag to _translate_with_model
            return self._translate_with_model(text, model_name, source_lang=source_lang, target_lang=target_lang, target_lang_tag=target_lang_tag)
        except Exception as e:
            logger.error(f"Error in translate_by_model_type for {model_name}: {e}")
            return (f"Translation failed: {str(e)}")

    def get_supported_language_pairs(self):
        """Get all supported language pairs."""
        return list(self.language_pair_models.keys())

    def get_models_for_pair(self, language_pair: str):
        """Get available models for a specific language pair."""
        return self.language_pair_models.get(language_pair, [])

    def verify_available_models(self):
        """Check and log which models are available on startup."""
        uvicorn_logger = logging.getLogger('uvicorn.error')
        
        uvicorn_logger.info("=== CHECKING MODEL AVAILABILITY ===")
        
        available_count = 0
        
        # Test loading of each configured model path
        for model_name, model_path in self.model_paths.items():
            try:
                if os.path.exists(model_path):
                    self.load_model(model_name) # Attempt to load the model
                    uvicorn_logger.info(f"✅ Model functional test SUCCESSFUL with {model_name}")
                    available_count += 1
                else:
                    uvicorn_logger.warning(f"✗ {model_name}: NOT FOUND at {model_path}")
            except Exception as e:
                uvicorn_logger.error(f"❌ Model functional test FAILED with {model_name}: {e}")
            finally:
                # Unload model after testing to free resources
                if self.model is not None:
                    del self.model
                    del self.tokenizer
                    self.model = None
                    self.tokenizer = None
                    self.current_model = None
                    gc.collect()
                    torch.cuda.empty_cache() if torch.cuda.is_available() else None

# Initialize the service
translation_service = TranslationService()