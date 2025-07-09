import os
import logging
from typing import Dict, List, Optional
from pathlib import Path
import requests
from tqdm import tqdm
import hashlib
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from comet import download_model, load_from_checkpoint

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, models_dir: str = "./models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)

        # Define all models used in your project
        self.model_configs = {
            "metricx": {
                "name": "MetricX-24 Hybrid Large",
                "source": "huggingface",
                "repo_id": "google/metricx-24-hybrid-large-v2p6",
                "local_path": self.models_dir / "metricx-24-hybrid-large-v2p6",
                "required_files": ["config.json", "pytorch_model.bin", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"],
                "size_gb": 4.9,
                "description": "Translation quality assessment model"
            },
            "comet": {
                "name": "COMET-22 DA",
                "source": "comet",
                "repo_id": "Unbabel/wmt22-comet-da",
                "local_path": None,  # COMET handles its own caching
                "required_files": [],
                "size_gb": 1.2,
                "description": "Reference-based translation quality metric"
            },
            "helsinki_en_fr": {
                "name": "Helsinki OPUS EN-FR",
                "source": "huggingface",
                "repo_id": "Helsinki-NLP/opus-mt-en-fr",
                "local_path": self.models_dir / "helsinki-nlp" / "opus-mt-en-fr",
                "required_files": ["config.json", "pytorch_model.bin", "tokenizer.json"],
                "size_gb": 0.3,
                "description": "English to French translation model"
            },
            "helsinki_fr_en": {
                "name": "Helsinki OPUS FR-EN",
                "source": "huggingface",
                "repo_id": "Helsinki-NLP/opus-mt-fr-en",
                "local_path": self.models_dir / "helsinki-nlp" / "opus-mt-fr-en",
                "required_files": ["config.json", "pytorch_model.bin", "tokenizer.json"],
                "size_gb": 0.3,
                "description": "French to English translation model"
            },
            "helsinki_en_jp": {
                "name": "Helsinki OPUS EN-JP",
                "source": "huggingface",
                "repo_id": "Helsinki-NLP/opus-mt-en-jap",
                "local_path": self.models_dir / "helsinki-nlp" / "opus-mt-en-jap",
                "required_files": ["config.json", "pytorch_model.bin", "tokenizer.json"],
                "size_gb": 0.3,
                "description": "English to Japanese translation model"
            },
            "nllb_200": {
                "name": "NLLB-200 Distilled",
                "source": "huggingface",
                "repo_id": "facebook/nllb-200-distilled-600M",
                "local_path": self.models_dir / "facebook" / "nllb-200-distilled-600M",
                "required_files": ["config.json", "pytorch_model.bin", "tokenizer.json"],
                "size_gb": 2.4,
                "description": "Multilingual translation model"
            }
        }

    def check_model_availability(self, model_key: str) -> Dict:
        """Check if a model is available locally"""
        if model_key not in self.model_configs:
            return {"available": False, "error": f"Unknown model: {model_key}"}
        
        config = self.model_configs[model_key]
        
        if config["source"] == "comet":
            # COMET models are handled differently
            try:
                download_model(config["repo_id"])
                return {"available": True, "path": "comet_cache"}
            except:
                return {"available": False, "error": "COMET model not available"}
        
        local_path = config["local_path"]
        if not local_path.exists():
            return {"available": False, "error": "Model directory not found"}
        
        # Check required files
        missing_files = []
        for file in config["required_files"]:
            if not (local_path / file).exists():
                missing_files.append(file)
        
        if missing_files:
            return {"available": False, "error": f"Missing files: {missing_files}"}
        
        return {"available": True, "path": str(local_path)}

    def download_model(self, model_key: str, force: bool = False) -> bool:
        """Download a specific model"""
        if model_key not in self.model_configs:
            logger.error(f"Unknown model: {model_key}")
            return False
        
        config = self.model_configs[model_key]
        
        # Check if already available
        if not force:
            status = self.check_model_availability(model_key)
            if status["available"]:
                logger.info(f"✓ {config['name']} already available")
                return True
        
        logger.info(f"📥 Downloading {config['name']} ({config['size_gb']} GB)")
        
        try:
            if config["source"] == "huggingface":
                return self._download_huggingface_model(config)
            elif config["source"] == "comet":
                return self._download_comet_model(config)
            else:
                logger.error(f"Unknown source: {config['source']}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to download {config['name']}: {e}")
            return False

    def _download_huggingface_model(self, config: Dict) -> bool:
        """Download model from Hugging Face"""
        try:
            from huggingface_hub import snapshot_download
            
            # Create local directory
            config["local_path"].parent.mkdir(parents=True, exist_ok=True)
            
            # Download model
            snapshot_download(
                repo_id=config["repo_id"],
                local_dir=config["local_path"],
                local_dir_use_symlinks=False,
                resume_download=True
            )
            
            logger.info(f"✓ Downloaded {config['name']} successfully")
            return True
            
        except ImportError:
            logger.error("huggingface_hub not installed. Run: pip install huggingface_hub")
            return False
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False

    def _download_comet_model(self, config: Dict) -> bool:
        """Download COMET model"""
        try:
            download_model(config["repo_id"])
            logger.info(f"✓ Downloaded {config['name']} successfully")
            return True
        except Exception as e:
            logger.error(f"COMET download failed: {e}")
            return False

    def download_all_models(self, skip_existing: bool = True) -> Dict:
        """Download all models used in the project"""
        results = {}
        total_size = sum(config["size_gb"] for config in self.model_configs.values())
        
        logger.info(f"📦 Downloading all models (Total: {total_size:.1f} GB)")
        logger.info("This may take 20-60 minutes depending on your internet connection...")
        
        for model_key in self.model_configs:
            if skip_existing:
                status = self.check_model_availability(model_key)
                if status["available"]:
                    results[model_key] = {"success": True, "message": "Already available"}
                    continue
            
            success = self.download_model(model_key)
            results[model_key] = {
                "success": success,
                "message": "Downloaded successfully" if success else "Download failed"
            }
        
        return results

    def get_model_status(self) -> Dict:
        """Get status of all models"""
        status = {}
        for model_key, config in self.model_configs.items():
            availability = self.check_model_availability(model_key)
            status[model_key] = {
                "name": config["name"],
                "description": config["description"],
                "size_gb": config["size_gb"],
                "available": availability["available"],
                "path": availability.get("path"),
                "error": availability.get("error")
            }
        return status

    def get_model_path(self, model_key: str) -> Optional[str]:
        """Get the local path for a model"""
        status = self.check_model_availability(model_key)
        if status["available"]:
            return status["path"]
        return None

# Global model manager instance
model_manager = ModelManager()
