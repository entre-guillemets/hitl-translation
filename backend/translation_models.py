# backend/translation_models.py
from transformers import MarianMTModel, MarianTokenizer, pipeline
import torch # Import torch for device check

class LocalTranslationService:
    def __init__(self):
        self.models = {
            'en-fr': 'Helsinki-NLP/opus-mt-en-fr',
            'fr-en': 'Helsinki-NLP/opus-mt-fr-en',
            'en-jp': 'Helsinki-NLP/opus-mt-en-jap', # Note: Often 'en-ja' is used for actual models
            'jp-en': 'Mitsua/elan-mt-bt-ja-en',
            # For JP-FR, use pivot translation via English
        }
        self.loaded_models = {}

    def translate(self, text: str, source_lang: str, target_lang: str):
        pair = f"{source_lang}-{target_lang}"

        if pair == 'jp-fr':
            # Pivot through English
            jp_en = self.translate(text, 'jp', 'en')
            return self.translate(jp_en, 'en', 'fr')

        model_name = self.models.get(pair)
        if not model_name:
            raise ValueError(f"Unsupported language pair: {pair}")

        # Load model if not cached
        if pair not in self.loaded_models:
            # Check for CUDA availability and set device accordingly
            device = 0 if torch.cuda.is_available() else -1
            self.loaded_models[pair] = pipeline(
                'translation',
                model=model_name,
                device=device
            )

        result = self.loaded_models[pair](text)
        return result[0]['translation_text']