import os
import logging
from typing import Dict, List, Optional, Union
from pathlib import Path
import requests
from tqdm import tqdm
import hashlib
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import comet

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, models_dir: str = "./models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)

        self.model_configs = {
            "metricx": {
                "name": "MetricX-24 Hybrid Large",
                "source": "huggingface",
                "repo_id": "google/metricx-24-hybrid-large-v2p6",
                "local_path": self.models_dir / "metricx-24-hybrid-large-v2p6",
                "required_files": ["config.json", "pytorch_model.bin"],
                "size_gb": 4.9,
                "description": "Translation quality assessment model"
            },
            "comet": {
                "name": "COMET-22 DA",
                "source": "comet",
                "repo_id": "Unbabel/wmt22-comet-da",
                "local_path": None, 
                "required_files": [], 
                "size_gb": 1.2,
                "description": "Reference-based translation quality metric"
            },
            "helsinki_en_fr": {
                "name": "Helsinki OPUS EN-FR",
                "source": "huggingface",
                "repo_id": "Helsinki-NLP/opus-mt-en-fr",
                "local_path": self.models_dir / "Helsinki-NLP_opus-mt-en-fr",
                "required_files": ["config.json", "pytorch_model.bin", "vocab.json", "source.spm", "target.spm"],
                "size_gb": 0.3,
                "description": "English to French translation model"
            },
            "mt5_multilingual": {
                "name": "mT5 Base Multilingual",
                "source": "huggingface",
                "repo_id": "google/mt5-base",
                "local_path": self.models_dir / "google-mt5_mt5-base",
                "required_files": ["config.json", "pytorch_model.bin", "spiece.model"],
                "size_gb": 1.2,
                "description": "Multilingual T5 model"
            },
            "helsinki_fr_en": {
                "name": "Helsinki OPUS FR-EN",
                "source": "huggingface",
                "repo_id": "Helsinki-NLP/opus-mt-fr-en",
                "local_path": self.models_dir / "Helsinki-NLP_opus-mt-fr-en",
                "required_files": ["config.json", "pytorch_model.bin", "vocab.json", "source.spm", "target.spm"],
                "size_gb": 0.3,
                "description": "French to English translation model"
            },
            "helsinki_en_jp": {
                "name": "Helsinki OPUS EN-JP",
                "source": "huggingface",
                "repo_id": "Helsinki-NLP/opus-mt-en-jap",
                "local_path": self.models_dir / "Helsinki-NLP_opus-mt-en-jap",
                "required_files": ["config.json", "pytorch_model.bin", "vocab.json", "source.spm", "target.spm"],
                "size_gb": 0.3,
                "description": "English to Japanese translation model"
            },
            "nllb_200": {
                "name": "NLLB-200 Distilled",
                "source": "huggingface",
                "repo_id": "facebook/nllb-200-distilled-600M",
                "local_path": self.models_dir / "nllb-200-distilled-600M",
                "required_files": ["config.json", "pytorch_model.bin", "tokenizer.json", "sentencepiece.bpe.model"],
                "size_gb": 2.4,
                "description": "Multilingual translation model"
            },
            "elan_ja_en": {
                "name": "ELAN MT JP-EN",
                "source": "huggingface",
                "repo_id": "Mitsua/elan-mt-bt-ja-en",
                "local_path": self.models_dir / "Mitsua_elan-mt-bt-ja-en",
                "required_files": ["config.json", "model.safetensors", "vocab.json", "source.spm", "target.spm"],
                "size_gb": 0.3,
                "description": "Japanese to English translation model (ELAN)"
            },
            "opus_ja_en": {
                "name": "Helsinki OPUS JA-EN",
                "source": "huggingface",
                "repo_id": "Helsinki-NLP/opus-mt-ja-en",
                "local_path": self.models_dir / "opus-mt-ja-en", 
                "required_files": ["config.json", "pytorch_model.bin", "vocab.json", "source.spm", "target.spm"],
                "size_gb": 0.3,
                "description": "Japanese to English translation model (OPUS)"
            }
        }

    def check_model_availability(self, model_key: str) -> Dict[str, Union[bool, str]]:
        """Check if a model is available locally"""
        if model_key not in self.model_configs:
            return {"available": False, "error": f"Unknown model: {model_key}"}

        config = self.model_configs[model_key]

        if config["source"] == "comet":
            try:
                # Check if COMET model is in cache without downloading
                cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
                model_cache_name = f"models--{config['repo_id'].replace('/', '--')}"
                model_cache_path = cache_dir / model_cache_name
                
                if model_cache_path.exists():
                    # Find the actual model checkpoint
                    snapshots_dir = model_cache_path / "snapshots"
                    if snapshots_dir.exists():
                        for snapshot in snapshots_dir.iterdir():
                            checkpoint_path = snapshot / "checkpoints" / "model.ckpt"
                            if checkpoint_path.exists():
                                return {"available": True, "path": str(checkpoint_path)}
                
                return {"available": False, "error": "COMET model not in cache"}
                
            except Exception as e:
                return {"available": False, "error": f"COMET model check failed: {e}"}

        local_path = config["local_path"]
        if not local_path.exists():
            return {"available": False, "error": "Model directory not found"}

        # Check required files for Hugging Face models
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

        # Check if already available (unless force download is requested)
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

    def _download_huggingface_model_manual(self, config: Dict) -> bool:
        """Download model files individually from Hugging Face"""
        try:
            from huggingface_hub import hf_hub_download
            import time
            
            config["local_path"].mkdir(parents=True, exist_ok=True)
            
            # Essential files for mT5
            essential_files = [
                "config.json",
                "pytorch_model.bin", 
                "spiece.model",
                "tokenizer.json",
                "tokenizer_config.json",
                "generation_config.json"
            ]
            
            print(f"Downloading {len(essential_files)} essential files for {config['repo_id']}...")
            
            downloaded_count = 0
            for filename in essential_files:
                try:
                    print(f"Downloading {filename}...")
                    start_time = time.time()
                    
                    file_path = hf_hub_download(
                        repo_id=config["repo_id"],
                        filename=filename,
                        local_dir=str(config["local_path"]),
                        local_dir_use_symlinks=False
                    )
                    
                    elapsed = time.time() - start_time
                    if Path(file_path).exists():
                        size_mb = Path(file_path).stat().st_size / (1024*1024)
                        print(f"  ✓ {filename}: {size_mb:.1f} MB in {elapsed:.1f}s")
                        downloaded_count += 1
                    
                except Exception as e:
                    print(f"  ⚠️  Could not download {filename}: {e}")
                    continue
            
            if downloaded_count >= 3:  # At least config, model, and tokenizer
                print(f"✓ Downloaded {downloaded_count}/{len(essential_files)} files successfully")
                return True
            else:
                print(f"❌ Only downloaded {downloaded_count}/{len(essential_files)} files")
                return False
                
        except Exception as e:
            print(f"Manual download failed: {e}")
            return False

    def _download_huggingface_model(self, config: Dict) -> bool:
        """Download model from Hugging Face"""
        try:
            from huggingface_hub import hf_hub_download
            
            config["local_path"].mkdir(parents=True, exist_ok=True)
            
            # Just download the 3 essential files
            files_to_download = ["config.json", "pytorch_model.bin", "spiece.model"]
            
            for filename in files_to_download:
                print(f"Downloading {filename}...")
                try:
                    hf_hub_download(
                        repo_id=config["repo_id"],
                        filename=filename,
                        local_dir=str(config["local_path"]),
                        local_dir_use_symlinks=False
                    )
                    print(f"✓ {filename} downloaded")
                except Exception as e:
                    print(f"✗ {filename} failed: {e}")
                    return False
            
            print("✓ All essential files downloaded")
            return True
            
        except Exception as e:
            print(f"Download failed: {e}")
            return False

    def _download_comet_model(self, config: Dict) -> bool:
        """Download COMET model"""
        try:
            model_path = comet.download_model(config["repo_id"])
            logger.info(f"✓ Downloaded {config['name']} successfully to {model_path}")
            return True
        except Exception as e:
            logger.error(f"COMET download failed for {config['name']}: {e}")
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
        """Get the local path for a model. This will also trigger a download if not available."""
        status = self.check_model_availability(model_key)
        if status["available"]:
            return status["path"]
        return None

# Global model manager instance
model_manager = ModelManager()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Model Manager for Translation App")
    parser.add_argument("--download-all", action="store_true", help="Download all models")
    parser.add_argument("--download", type=str, help="Download specific model by key")
    parser.add_argument("--status", action="store_true", help="Show status of all models")
    parser.add_argument("--list", action="store_true", help="List all available models")
    
    args = parser.parse_args()
    
    if args.status:
        print("=== Model Status ===")
        status = model_manager.get_model_status()
        for key, info in status.items():
            status_icon = "✓" if info['available'] else "✗"
            print(f"{status_icon} {key}: {info['name']} ({info['size_gb']} GB)")
            if not info['available'] and info.get('error'):
                print(f"    Error: {info['error']}")
        
    elif args.list:
        print("=== Available Models ===")
        for key, config in model_manager.model_configs.items():
            print(f"- {key}: {config['name']} ({config['size_gb']} GB)")
            print(f"  {config['description']}")
        
    elif args.download:
        print(f"Downloading {args.download}...")
        success = model_manager.download_model(args.download)
        if success:
            print(f"✓ Successfully downloaded {args.download}")
        else:
            print(f"✗ Failed to download {args.download}")
            
    elif args.download_all:
        print("Downloading all models...")
        results = model_manager.download_all_models()
        
        print("\n=== Download Results ===")
        for model_key, result in results.items():
            status_icon = "✓" if result['success'] else "✗"
            print(f"{status_icon} {model_key}: {result['message']}")
    
    else:
        print("=== Model Status ===")
        status = model_manager.get_model_status()
        total_available = sum(1 for info in status.values() if info['available'])
        total_models = len(status)
        
        print(f"Models available: {total_available}/{total_models}")
        print()
        
        for key, info in status.items():
            status_icon = "✓" if info['available'] else "✗"
            print(f"{status_icon} {key}: {info['name']} ({info['size_gb']} GB)")
            if not info['available'] and info.get('error'):
                print(f"    Error: {info['error']}")
        
        print(f"\nUsage:")
        print(f"  python model_manager.py --status          # Show model status")
        print(f"  python model_manager.py --download-all     # Download all models")
        print(f"  python model_manager.py --download mt5_multilingual  # Download specific model")
        print(f"  python model_manager.py --list            # List all available models")
