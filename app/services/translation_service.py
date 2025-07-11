import logging
from typing import Dict, List, Any
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import os

from app.core.config import settings

logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self):
        self.models = {}
        self.tokenizers = {}
        self.pipelines = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"TranslationService initialized. Using device: {self.device}")

        self.model_paths = {
            'HELSINKI_EN_FR': ('Helsinki-NLP_opus-mt-en-fr', None),
            'HELSINKI_FR_EN': ('Helsinki-NLP_opus-mt-fr-en', None),
            'HELSINKI_EN_JP': ('Helsinki-NLP_opus-mt-en-jap', None),
            'OPUS_JA_EN': ('opus-mt-ja-en', None),
            'ELAN_JA_EN': ('Mitsua/elan-mt-bt-ja-en', None),
            'T5_MULTILINGUAL': ('google-t5_t5-base', None), # Changed to None
            'NLLB_200': ('nllb-200-distilled-600M', 'jpn_Jpan'),
        }

        self.language_pair_models = {
            'EN-FR': [
                ('HELSINKI_EN_FR', self.model_paths['HELSINKI_EN_FR'][0], None),
                ('NLLB_200', self.model_paths['NLLB_200'][0], 'fra_Latn'),
                ('T5_MULTILINGUAL', self.model_paths['T5_MULTILINGUAL'][0], 'translate English to French: ')
            ],
            'FR-EN': [
                ('HELSINKI_FR_EN', self.model_paths['HELSINKI_FR_EN'][0], None),
                ('NLLB_200', self.model_paths['NLLB_200'][0], 'eng_Latn'),
                ('T5_MULTILINGUAL', self.model_paths['T5_MULTILINGUAL'][0], 'translate French to English: ')
            ],
            'EN-JP': [
                ('HELSINKI_EN_JP', self.model_paths['HELSINKI_EN_JP'][0], None),
                ('NLLB_200', self.model_paths['NLLB_200'][0], 'jpn_Jpan'),
                ('T5_MULTILINGUAL', self.model_paths['T5_MULTILINGUAL'][0], 'translate English to Japanese: ')
            ],
            'JP-EN': [
                ('OPUS_JA_EN', self.model_paths['OPUS_JA_EN'][0], None),
                ('ELAN_JA_EN', self.model_paths['ELAN_JA_EN'][0], None),
                ('NLLB_200', self.model_paths['NLLB_200'][0], 'eng_Latn'),
                ('T5_MULTILINGUAL', self.model_paths['T5_MULTILINGUAL'][0], 'translate Japanese to English: ')
            ],
            'JP-FR': [
                ('PIVOT_JP_EN_FR', None, None),
                ('NLLB_200', self.model_paths['NLLB_200'][0], 'fra_Latn'),
                ('T5_MULTILINGUAL', self.model_paths['T5_MULTILINGUAL'][0], 'translate Japanese to French: ')
            ],
        }

    def _load_model(self, model_key: str):
        """Internal method to load a model and its tokenizer/pipeline."""
        if model_key in self.models:
            return self.models[model_key], self.tokenizers[model_key], self.pipelines[model_key]

        model_path_info = self.model_paths.get(model_key)
        if not model_path_info:
            for pair_models in self.language_pair_models.values():
                for info in pair_models:
                    if info[0] == model_key:
                        model_path_info = (info[1], info[2]) # Get path and potential tag
                        break
                if model_path_info:
                    break

        if model_key.startswith('PIVOT'):
            logger.info(f"Skipping direct load for pivot model key: {model_key}. Handled by multi-engine service.")
            return None, None, None

        if not model_path_info or not model_path_info[0]:
            raise ValueError(f"Model key '{model_key}' not found in configured model_paths or language_pair_models, or no valid path/Hub ID provided.")

        model_name_or_path = model_path_info[0]

        logger.info(f"Attempting to load model '{model_name_or_path}' for key '{model_key}' using cache_dir='{settings.MODEL_CACHE_DIR}'...")
        try:
            full_local_path = os.path.join(settings.MODEL_CACHE_DIR, model_name_or_path)

            if os.path.isdir(full_local_path):
                # Load from local directory if it exists
                logger.info(f"Loading from local path: {full_local_path}")
                tokenizer = AutoTokenizer.from_pretrained(full_local_path)
                model = AutoModelForSeq2SeqLM.from_pretrained(full_local_path).to(self.device)
            else:
                # Otherwise, assume it's a Hugging Face Hub ID and let HF handle downloading/caching
                logger.info(f"Loading from Hugging Face Hub: {model_name_or_path}")
                tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, cache_dir=settings.MODEL_CACHE_DIR)
                model = AutoModelForSeq2SeqLM.from_pretrained(model_name_or_path, cache_dir=settings.MODEL_CACHE_DIR).to(self.device)

            pipe = None

            if not model_key.startswith('T5'):
                pipe = pipeline(
                    "translation",
                    model=model,
                    tokenizer=tokenizer,
                    device=0 if self.device == "cuda" else -1
                )
            else:
                logger.info(f"Skipping pipeline creation for T5 model '{model_key}'. Will use model.generate directly.")

            self.models[model_key] = model
            self.tokenizers[model_key] = tokenizer
            self.pipelines[model_key] = pipe
            logger.info(f"Model '{model_key}' loaded successfully. Device set to use {self.device}")
            return model, tokenizer, pipe
        except Exception as e:
            logger.error(f"Error loading model {model_name_or_path} for key {model_key}: {e}")
            raise

    def translate_by_model_type(self, text: str, model_key: str, source_lang: str = None, target_lang: str = None, target_lang_tag: str = None) -> str:
        """Translate text using a specific model identified by its key."""
        try:
            if model_key.startswith('PIVOT'):
                return f"Translation failed: Pivot model '{model_key}' should be routed via multi-engine service."

            model, tokenizer, pipe = self._load_model(model_key)
            if not model:
                return "Translation failed: Model not loaded or directly translatable."

            if model_key.startswith('T5'):
                if target_lang_tag is None:
                    lang_map = {
                        "en": "English", "fr": "French", "jp": "Japanese",
                        "ja": "Japanese", "fra": "French", "eng": "English"
                    }
                    src_lang_full = lang_map.get(source_lang.lower(), source_lang)
                    tgt_lang_full = lang_map.get(target_lang.lower(), target_lang)
                    prompt = f"translate {src_lang_full} to {tgt_lang_full}: "
                    logger.info(f"Using auto-derived T5 prompt: {prompt}")
                    text_to_translate = prompt + text
                else:
                    text_to_translate = target_lang_tag + text

                logger.info(f"T5 Input - text_to_translate: '{text_to_translate}'")
                logger.info(f"T5 Input - source_lang: '{source_lang}', target_lang: '{target_lang}', target_lang_tag: '{target_lang_tag}'")

                inputs = tokenizer(text_to_translate, return_tensors="pt").to(self.device)

                logger.info(f"T5 Input - tokenizer output (input_ids shape): {inputs['input_ids'].shape}")
                logger.info(f"T5 Input - tokenizer output (input_ids): {inputs['input_ids']}")

                translated_tokens = model.generate(
                    **inputs,
                    max_length=512
                )
                logger.info(f"T5 Output - generated_tokens shape: {translated_tokens.shape}")
                logger.info(f"T5 Output - generated_tokens: {translated_tokens}")

                translated = tokenizer.decode(translated_tokens[0], skip_special_tokens=True)
                logger.info(f"T5 Output - decoded_text: '{translated}'")

            elif model_key.startswith('NLLB'):
                # NLLB models require specific target_lang tag to be passed to generate
                if target_lang_tag is None:
                    nllb_lang_tags = {
                        "en": "eng_Latn", "fr": "fra_Latn", "jp": "jpn_Jpan",
                        "ja": "jpn_Jpan", "fra": "fra_Latn", "eng": "eng_Latn"
                    }
                    target_lang_tag = nllb_lang_tags.get(target_lang.lower(), None)
                    if target_lang_tag is None:
                        raise ValueError(f"NLLB model '{model_key}' requires a 'target_lang_tag' for translation. Could not determine for {target_lang}.")

                forced_bos_token_id = None
                if hasattr(tokenizer, 'get_lang_id'):
                    forced_bos_token_id = tokenizer.get_lang_id(target_lang_tag)
                elif hasattr(tokenizer, 'lang_code_to_id') and target_lang_tag in tokenizer.lang_code_to_id:
                    forced_bos_token_id = tokenizer.lang_code_to_id[target_lang_tag]
                elif target_lang_tag in tokenizer.vocab:
                     # This means target_lang_tag is a string like '__jpn_Jpan__' which is in the vocab
                    forced_bos_token_id = tokenizer.convert_tokens_to_ids(target_lang_tag)
                else:
                    logger.warning(f"NLLB: Could not find explicit lang_id for '{target_lang_tag}'. Attempting generic conversion (may fail).")
                    forced_bos_token_id = tokenizer.convert_tokens_to_ids(target_lang_tag)

                if forced_bos_token_id is None:
                    raise ValueError(f"NLLB: Failed to determine forced_bos_token_id for tag '{target_lang_tag}'.")

                inputs = tokenizer(text, return_tensors="pt").to(self.device)
                translated_tokens = model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos_token_id,
                    max_length=512
                )
                translated = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
            else:
                if pipe is None:
                    raise RuntimeError(f"Pipeline not initialized for model key: {model_key}. This should not happen for non-T5 models.")
                translated = pipe(text, max_length=512)[0]['translation_text']

            return translated
        except Exception as e:
            logger.error(f"Translation failed for model {model_key}: {e}")
            return f"Translation failed: {str(e)}"

    def translate_with_fallback(self, text: str, source_lang: str, target_lang: str) -> str:
        """Attempt translation with primary model, fallback to other configured models in order."""
        pair = f"{source_lang.upper()}-{target_lang.upper()}"

        if pair in self.language_pair_models and self.language_pair_models[pair]:
            for model_config in self.language_pair_models[pair]:
                current_model_key = model_config[0]
                target_lang_tag_for_current = model_config[2] if len(model_config) > 2 else None

                logger.info(f"Attempting translation with {current_model_key} for {source_lang}-{target_lang}...")
                translated_text = self.translate_by_model_type(text, current_model_key, source_lang, target_lang, target_lang_tag_for_current)

                if not translated_text.startswith("Translation failed"):
                    return translated_text
                else:
                    logger.warning(f"Translation with {current_model_key} failed: {translated_text}")

        logger.error(f"All configured models failed for {source_lang}-{target_lang}. No translation available.")
        return f"Translation failed: No models could translate from {source_lang} to {target_lang}."

    def get_available_models(self) -> List[str]:
        """Returns a list of all configured model keys."""
        return list(self.model_paths.keys())

# Initialize the translation service (singleton pattern)
translation_service = TranslationService()