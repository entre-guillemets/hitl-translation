# backend/wmt_data_service.py
import os
import json
import pandas as pd
from typing import List, Dict, Any

class WMTDataService:
    def __init__(self, data_dir: str = "./wmt_data"):
        self.data_dir = data_dir
    
    def load_wmt_dataset(self, language_pair: str, split: str = "test") -> List[Dict[str, str]]:
        """Load WMT dataset for a language pair"""
        try:
            # WMT data typically comes as parallel files
            src_lang, tgt_lang = language_pair.split('-')
            
            src_file = f"{self.data_dir}/{language_pair}/{split}.{src_lang}"
            tgt_file = f"{self.data_dir}/{language_pair}/{split}.{tgt_lang}"
            
            if not os.path.exists(src_file) or not os.path.exists(tgt_file):
                raise FileNotFoundError(f"WMT files not found for {language_pair}")
            
            with open(src_file, 'r', encoding='utf-8') as f:
                source_lines = f.readlines()
            
            with open(tgt_file, 'r', encoding='utf-8') as f:
                target_lines = f.readlines()
            
            # Create dataset entries
            dataset = []
            for i, (src, tgt) in enumerate(zip(source_lines, target_lines)):
                dataset.append({
                    "id": f"wmt-{language_pair}-{i}",
                    "sourceText": src.strip(),
                    "referenceText": tgt.strip(),
                    "sourceLanguage": src_lang.upper(),
                    "targetLanguage": tgt_lang.upper(),
                    "dataset": f"WMT22-{language_pair}",
                    "split": split
                })
            
            return dataset
            
        except Exception as e:
            print(f"Error loading WMT dataset: {e}")
            return []
    
    def create_translation_request_from_wmt(self, language_pair: str, sample_size: int = 100) -> Dict[str, Any]:
        """Create a translation request using WMT test data"""
        dataset = self.load_wmt_dataset(language_pair, "test")
        
        if not dataset:
            raise ValueError(f"No WMT data available for {language_pair}")
        
        # Sample subset for testing
        sample_data = dataset[:sample_size]
        
        src_lang, tgt_lang = language_pair.split('-')
        
        return {
            "sourceLanguage": src_lang.upper(),
            "targetLanguages": [tgt_lang.upper()],
            "languagePair": language_pair,
            "wordCount": sum(len(item["sourceText"].split()) for item in sample_data),
            "fileName": f"wmt22_{language_pair}_test_{sample_size}.txt",
            "mtModel": self.get_model_for_pair(src_lang, tgt_lang),
            "sourceTexts": [item["sourceText"] for item in sample_data],
            "referenceTexts": [item["referenceText"] for item in sample_data], 
            "dataset_info": {
                "source": "WMT22",
                "language_pair": language_pair,
                "sample_size": sample_size
            }
        }
    
    def get_model_for_pair(self, src: str, tgt: str) -> str:
        """Get appropriate model for language pair"""
        mapping = {
            ('ja', 'en'): 'ELAN_MT_JP_EN',
            ('en', 'ja'): 'MARIAN_MT_EN_JP',
            ('en', 'fr'): 'MARIAN_MT_EN_FR',
            ('fr', 'en'): 'MARIAN_MT_FR_EN'
        }
        return mapping.get((src, tgt), 'T5_MULTILINGUAL')

wmt_service = WMTDataService()
