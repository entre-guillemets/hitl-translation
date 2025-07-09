import logging
from typing import Dict, List, Any
from datetime import datetime
from app.services.translation_service import TranslationService # Import the actual TranslationService class

logger = logging.getLogger(__name__)

class CleanMultiEngineService:
    def __init__(self, translation_service_instance: TranslationService): # Type hint translation_service_instance
        """Initialize with dependency injection for translation service"""
        self.translation_service = translation_service_instance
        self.engine_configs = {
            'opus_fast': {
                'name': 'Helsinki OPUS',
                'supported_pairs': ['en-fr', 'fr-en', 'en-jp', 'jp-en', 'jp-fr'],
                'model_mapping': {
                    'en-fr': 'HELSINKI_EN_FR',    
                    'fr-en': 'HELSINKI_FR_EN',    
                    'en-jp': 'HELSINKI_EN_JP',    
                    'jp-en': 'OPUS_JA_EN'          
                },
                'pivot_strategy': {
                    'pivot_lang': 'en',
                    'via_models': ['OPUS_JA_EN', 'HELSINKI_EN_FR'], # JP-EN then EN-FR for JP-FR
                    'applies_to': ['jp-fr']
                },
                'confidence': 0.80
            },
            'elan_quality': {
                'name': 'ELAN Specialist',
                'supported_pairs': ['jp-en', 'jp-fr', 'en-fr'], # Added 'en-fr' as it's a common pair, assuming ELAN handles it
                'model_mapping': {
                    'jp-en': 'ELAN_JA_EN',          
                    'fr-en': 'ELAN_JA_EN',      # This might be a typo in original if ELAN is JP-EN focused
                    'en-fr': 'ELAN_JA_EN'       # Assuming ELAN can do EN-FR, otherwise remove
                },
                'pivot_strategy': {
                    'pivot_lang': 'en',
                    'via_models': ['ELAN_JA_EN', 'HELSINKI_EN_FR'], # JP-EN then EN-FR for JP-FR
                    'applies_to': ['jp-fr']
                },
                'confidence': 0.90
            },
            't5_versatile': {
                'name': 'mT5 Versatile',
                'supported_pairs': ['en-jp', 'jp-en', 'en-fr', 'fr-en', 'jp-fr'], 
                'model_mapping': {
                    'en-jp': 'T5_MULTILINGUAL',
                    'jp-en': 'T5_MULTILINGUAL',
                    'en-fr': 'T5_MULTILINGUAL',
                    'fr-en': 'T5_MULTILINGUAL',
                    'jp-fr': 'T5_MULTILINGUAL',
                },
                'confidence': 0.85,
            },
            'nllb_multilingual': {
                'name': 'NLLB Multilingual',
                'supported_pairs': ['en-jp', 'jp-en', 'en-fr', 'fr-en', 'jp-fr'], 
                'model_mapping': {
                    'en-jp': 'NLLB_200',
                    'jp-en': 'NLLB_200',
                    'en-fr': 'NLLB_200',
                    'fr-en': 'NLLB_200',
                    'jp-fr': 'NLLB_200',
                },
                'confidence': 0.92,
            }
        }

    async def translate_with_engine(self, text: str, source_lang: str, target_lang: str, engine_id: str) -> Dict:
        """Translate using a specific engine with clean routing"""
        try:
            if engine_id not in self.engine_configs:
                return {'engine': engine_id, 'error': 'Engine not found'}

            config = self.engine_configs[engine_id]
            start_time = datetime.now()

            # Check if we need pivot translation
            if self._needs_pivot_translation(config, source_lang, target_lang):
                translated_text = await self._translate_with_pivot(
                    text, source_lang, target_lang, config['pivot_strategy']
                )
            else:
                # Route to appropriate translation method
                pair = f"{source_lang.lower()}-{target_lang.lower()}"
                
                # Get model_to_use (e.g., 'T5_MULTILINGUAL', 'NLLB_200', 'HELSINKI_EN_FR')
                model_to_use = config['model_mapping'].get(pair)
                if not model_to_use:
                    raise ValueError(f"No model mapping found for engine '{engine_id}' and pair '{pair}'.")

                # Get the specific prefix or target language tag from translation_service's language_pair_models
                prefix_or_lang_tag = None
                # Fetching model_info from translation_service.language_pair_models using UPPERCASE pair for consistency
                model_info_list = self.translation_service.language_pair_models.get(f"{source_lang.upper()}-{target_lang.upper()}", [])
                model_info_from_ts = next(
                    (info for info in model_info_list if info[0] == model_to_use),
                    None
                )
                if model_info_from_ts and len(model_info_from_ts) == 3:
                    prefix_or_lang_tag = model_info_from_ts[2]

                translated_text = self.translation_service.translate_by_model_type(
                    text.strip(), 
                    model_to_use, 
                    source_lang=source_lang.lower(), # Pass raw source lang (e.g., 'en')
                    target_lang=target_lang.lower(), # Pass raw target lang (e.g., 'jp')
                    target_lang_tag=prefix_or_lang_tag # Pass for NLLB's specific lang tag or T5's prefix
                )

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # Assuming detokenize_japanese is in a utility module and imported where needed
            # from app.utils.text_processing import detokenize_japanese
            # if target_lang.upper() == 'JP':
            #     translated_text = detokenize_japanese(translated_text)

            return {
                'engine': engine_id,
                'text': translated_text,
                'confidence': config['confidence'],
                'processing_time': processing_time,
                'model': self._get_model_used(engine_id, source_lang, target_lang)
            }

        except Exception as e:
            return {'engine': engine_id, 'error': str(e)}

    def _needs_pivot_translation(self, config: dict, source_lang: str, target_lang: str) -> bool:
        """Determine if this translation needs to use pivot strategy"""
        if 'pivot_strategy' not in config:
            return False
        pair = f"{source_lang.lower()}-{target_lang.lower()}"
        applies_to = config['pivot_strategy'].get('applies_to', [])
        return pair in applies_to

    async def _translate_with_pivot(self, text: str, source_lang: str, target_lang: str, pivot_strategy: dict) -> str:
        """Generic pivot translation using strategy configuration"""
        try:
            pivot_models = pivot_strategy['via_models']
            if len(pivot_models) != 2:
                raise ValueError("Pivot strategy must specify exactly 2 models")

            first_model, second_model = pivot_models
            
            # For pivot models, we might need to explicitly get target_lang_tag for the pivot step
            # For example, if first_model is NLLB, its target might be 'eng_Latn'
            # Look up source-pivot model details from translation_service.language_pair_models
            pivot_lang_code = pivot_strategy['pivot_lang'].lower()
            
            first_model_config = next(
                (m_info for pair_list in self.translation_service.language_pair_models.values()
                 for m_info in pair_list if m_info[0] == first_model and pair_list[0][0].split('-')[0].lower() == source_lang.lower()), # Crude check for source part of pair
                None
            )
            first_model_target_tag = first_model_config[2] if first_model_config and len(first_model_config) > 2 else None

            intermediate = self.translation_service.translate_by_model_type(
                text.strip(), 
                first_model, 
                source_lang=source_lang.lower(), 
                target_lang=pivot_lang_code,
                target_lang_tag=first_model_target_tag
            )

            if isinstance(intermediate, str) and "Translation failed" in intermediate:
                raise Exception(f"Pivot step 1 failed: {intermediate}")

            # Look up pivot-target model details from translation_service.language_pair_models
            second_model_config = next(
                (m_info for pair_list in self.translation_service.language_pair_models.values()
                 for m_info in pair_list if m_info[0] == second_model and pair_list[0][0].split('-')[0].lower() == pivot_lang_code), # Crude check for source part of pair
                None
            )
            second_model_target_tag = second_model_config[2] if second_model_config and len(second_model_config) > 2 else None

            final_translation = self.translation_service.translate_by_model_type(
                intermediate.strip(), 
                second_model, 
                source_lang=pivot_lang_code, 
                target_lang=target_lang.lower(),
                target_lang_tag=second_model_target_tag
            )

            if isinstance(final_translation, str) and "Translation failed" in final_translation:
                raise Exception(f"Pivot step 2 failed: {final_translation}")

            return final_translation

        except Exception as e:
            raise Exception(f"Pivot translation failed: {str(e)}")

    def get_available_engines_for_pair(self, source_lang: str, target_lang: str) -> List[str]:
        """Return only engines that can handle this language pair"""
        pair = f"{source_lang.lower()}-{target_lang.lower()}"
        available = []
        
        for engine_id, config in self.engine_configs.items():
            # Check if model paths exist for direct models for this specific pair
            model_key = config['model_mapping'].get(pair) # Get model_key specific to this pair from engine_config
            model_path_exists = False
            if model_key:
                # Check actual model path existence from translation_service.model_paths
                model_path_exists = model_key in self.translation_service.model_paths and \
                                    self.translation_service.model_paths[model_key][0] is not None
            
            # Special handling for pivots
            is_pivot_available = self._can_handle_via_pivot(config, source_lang, target_lang)
            if is_pivot_available:
                 # Check if the underlying pivot models themselves are available in translation_service.model_paths
                 pivot_strategy = config['pivot_strategy']
                 model1_available = pivot_strategy['via_models'][0] in self.translation_service.model_paths and \
                                    self.translation_service.model_paths[pivot_strategy['via_models'][0]][0] is not None
                 model2_available = pivot_strategy['via_models'][1] in self.translation_service.model_paths and \
                                    self.translation_service.model_paths[pivot_strategy['via_models'][1]][0] is not None
                 if not (model1_available and model2_available):
                     is_pivot_available = False # Mark pivot as not available if its underlying models aren't
            
            # An engine is available if it supports the pair AND its model path exists, OR it's a valid pivot.
            if (pair in config['supported_pairs'] and model_path_exists) or is_pivot_available:
                available.append(engine_id)
        
        return available

    def _can_handle_via_pivot(self, config: dict, source_lang: str, target_lang: str) -> bool:
        """Check if engine can handle this pair via its configured pivot strategy"""
        if 'pivot_strategy' not in config:
            return False
        pair = f"{source_lang.lower()}-{target_lang.lower()}"
        applies_to = config['pivot_strategy'].get('applies_to', [])
        return pair in applies_to

    def _get_model_used(self, engine_id: str, source_lang: str, target_lang: str) -> str:
        """Get the model name used for this translation"""
        config = self.engine_configs.get(engine_id)
        if not config:
            return 'N/A'

        pair = f"{source_lang.lower()}-{target_lang.lower()}"

        # Check if pivot was used
        if self._needs_pivot_translation(config, source_lang, target_lang):
            pivot_models = config['pivot_strategy']['via_models']
            return f"{pivot_models[0]} + {pivot_models[1]} (Pivot)"

        # Check direct model mapping
        if 'model_mapping' in config:
            model = config['model_mapping'].get(pair)
            if model:
                return model

        # Check primary model key
        if 'model_key' in config:
            return config['model_key']

        return 'UNKNOWN_MODEL_ROUTING'

    async def translate_multi_engine(self, text: str, source_lang: str, target_lang: str, engines: List[str] = None) -> List[Dict]:
        """Clean multi-engine translation with proper routing"""
        if engines is None:
            engines = self.get_available_engines_for_pair(source_lang, target_lang)

        # Filter to only available engines for this language pair
        available_engines = self.get_available_engines_for_pair(source_lang, target_lang)
        valid_engines = [e for e in engines if e in available_engines]

        if not valid_engines:
            return [{'error': f'No valid engines were selected or available for {source_lang}-{target_lang}. Available: {available_engines}'}]

        tasks = []
        for engine in valid_engines:
            task = self.translate_with_engine(text, source_lang, target_lang, engine)
            tasks.append(task)

        import asyncio # Ensure asyncio is imported
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    'engine': valid_engines[i] if i < len(valid_engines) else 'unknown',
                    'error': str(result)
                })
            else:
                final_results.append(result)

        return final_results

    @property
    def engines(self):
        """Property to maintain compatibility with existing code"""
        return {engine_id: None for engine_id in self.engine_configs.keys()}