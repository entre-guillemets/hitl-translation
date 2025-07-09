import logging
import torch
import os
import glob
from typing import List, Dict, Optional
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import numpy as np
from app.services.model_manager import model_manager

logger = logging.getLogger(__name__)

class MetricXService:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = None
        self.is_loaded = False

        # Try to find the model path
        self._find_model_path()

    def _find_model_path(self):
        """Find MetricX model path using multiple strategies"""
        
        # Strategy 1: Try model manager first
        try:
            self.model_name = model_manager.get_model_path("metricx")
            if self.model_name and os.path.exists(str(self.model_name)):
                logger.info(f"✅ Found MetricX model via model_manager: {self.model_name}")
                return
        except Exception as e:
            logger.warning(f"⚠️ Model manager failed: {e}")

        # Strategy 2: Check models_dir from model_manager
        try:
            models_dir = getattr(model_manager, 'models_dir', None)
            if models_dir:
                possible_paths = [
                    os.path.join(models_dir, "metricx"),
                    os.path.join(models_dir, "MetricX-24-Hybrid-Large"),
                    os.path.join(models_dir, "metricx-24-hybrid-large-v2p6"),
                ]
                
                for path in possible_paths:
                    if os.path.exists(path) and self._is_valid_model_dir(path):
                        logger.info(f"✅ Found MetricX model in models_dir: {path}")
                        self.model_name = path
                        return
        except Exception as e:
            logger.warning(f"⚠️ Models dir check failed: {e}")

        # Strategy 3: Search HuggingFace cache
        cache_patterns = [
            "/Users/davidheston/.cache/huggingface/hub/models--google--MetricX-24-Hybrid-Large",
            os.path.expanduser("~/.cache/huggingface/hub/models--google--MetricX-24-Hybrid-Large"),
            os.path.expanduser("~/.cache/huggingface/hub/models--google--metricx-24-hybrid-large"),
        ]
        
        for cache_path in cache_patterns:
            if os.path.exists(cache_path):
                # Look for snapshots directory
                snapshots_dir = os.path.join(cache_path, "snapshots")
                if os.path.exists(snapshots_dir):
                    # Get the latest snapshot
                    snapshot_dirs = [d for d in os.listdir(snapshots_dir) if os.path.isdir(os.path.join(snapshots_dir, d))]
                    if snapshot_dirs:
                        # Sort by modification time, get the latest
                        snapshot_dirs.sort(key=lambda x: os.path.getmtime(os.path.join(snapshots_dir, x)), reverse=True)
                        model_path = os.path.join(snapshots_dir, snapshot_dirs[0])
                        if self._is_valid_model_dir(model_path):
                            logger.info(f"✅ Found MetricX model in HF cache: {model_path}")
                            self.model_name = model_path
                            return

        # Strategy 4: Search entire HuggingFace cache for any MetricX model
        try:
            hf_cache_base = os.path.expanduser("~/.cache/huggingface/hub")
            if os.path.exists(hf_cache_base):
                # Look for any directory containing "metricx" (case insensitive)
                for item in os.listdir(hf_cache_base):
                    if "metricx" in item.lower():
                        item_path = os.path.join(hf_cache_base, item)
                        if os.path.isdir(item_path):
                            snapshots_dir = os.path.join(item_path, "snapshots")
                            if os.path.exists(snapshots_dir):
                                snapshot_dirs = [d for d in os.listdir(snapshots_dir) if os.path.isdir(os.path.join(snapshots_dir, d))]
                                if snapshot_dirs:
                                    model_path = os.path.join(snapshots_dir, snapshot_dirs[0])
                                    if self._is_valid_model_dir(model_path):
                                        logger.info(f"✅ Found MetricX model via search: {model_path}")
                                        self.model_name = model_path
                                        return
        except Exception as e:
            logger.warning(f"⚠️ HF cache search failed: {e}")

        # Strategy 5: Try to download and find again
        if self.model_name is None:
            logger.warning("⚠️ MetricX model path not found. Attempting download...")
            try:
                result = model_manager.download_model("metricx")
                logger.info(f"📥 Download result: {result}")
                
                # After download, try to find it again
                self._find_model_path_post_download()
                
            except Exception as e:
                logger.error(f"❌ Download failed: {e}")

        if self.model_name is None:
            logger.error("❌ Could not find or download MetricX model")

    def _find_model_path_post_download(self):
        """Try to find model path after download"""
        # Wait a moment for filesystem to update
        import time
        time.sleep(1)
        
        # Check the most likely download locations
        possible_locations = [
            # Model manager's models directory
            getattr(model_manager, 'models_dir', None),
            # Current working directory
            os.getcwd(),
            # Common model directories
            "models",
            "./models",
            # HuggingFace cache (refresh check)
            os.path.expanduser("~/.cache/huggingface/hub"),
        ]
        
        for base_location in possible_locations:
            if base_location and os.path.exists(base_location):
                # Look for MetricX related directories
                try:
                    for item in os.listdir(base_location):
                        if "metricx" in item.lower():
                            item_path = os.path.join(base_location, item)
                            if os.path.isdir(item_path) and self._is_valid_model_dir(item_path):
                                logger.info(f"✅ Found MetricX model post-download: {item_path}")
                                self.model_name = item_path
                                return
                            # If it's a hub cache directory, check snapshots
                            elif os.path.isdir(item_path) and "snapshots" in os.listdir(item_path):
                                snapshots_dir = os.path.join(item_path, "snapshots")
                                if os.path.exists(snapshots_dir):
                                    snapshot_dirs = [d for d in os.listdir(snapshots_dir) if os.path.isdir(os.path.join(snapshots_dir, d))]
                                    if snapshot_dirs:
                                        model_path = os.path.join(snapshots_dir, snapshot_dirs[0])
                                        if self._is_valid_model_dir(model_path):
                                            logger.info(f"✅ Found MetricX model in snapshots: {model_path}")
                                            self.model_name = model_path
                                            return
                except Exception as e:
                    logger.warning(f"⚠️ Error checking {base_location}: {e}")

    def _is_valid_model_dir(self, path: str) -> bool:
        """Check if directory contains a valid MetricX model"""
        # Convert to string if it's a Path object
        path_str = str(path)
        
        required_files = ['config.json']
        optional_files = ['pytorch_model.bin', 'model.safetensors']
        
        if not os.path.isdir(path_str):
            return False
            
        # Check for required files
        for file in required_files:
            if not os.path.exists(os.path.join(path_str, file)):
                return False
        
        # Check for at least one model file
        has_model_file = any(os.path.exists(os.path.join(path_str, file)) for file in optional_files)
        
        return has_model_file

    def load_model(self) -> bool:
        """Load MetricX model"""
        try:
            if self.model_name is None:
                logger.error("❌ MetricX model path is not set")
                return False

            # Ensure path is a string (handle Path objects)
            model_path = str(self.model_name)
            logger.info(f"📦 Loading MetricX model from: {model_path}")
            logger.info(f"🔍 Model path type: {type(self.model_name)}")

            # Verify model files exist
            if not self._is_valid_model_dir(model_path):
                logger.error(f"❌ Invalid model directory: {model_path}")
                return False

            # Debug: Check what files exist in the model directory
            try:
                files = os.listdir(model_path)
                logger.info(f"🔍 Files in model directory: {files}")
                
                # Check for tokenizer files specifically
                tokenizer_files = [f for f in files if any(t in f.lower() for t in ['tokenizer', 'vocab', 'spiece'])]
                logger.info(f"🔍 Tokenizer-related files: {tokenizer_files}")
            except Exception as e:
                logger.warning(f"⚠️ Could not list directory contents: {e}")

            # Load tokenizer with explicit string conversion
            logger.info("📦 Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                str(model_path),  # Explicit string conversion
                local_files_only=True,
                trust_remote_code=True
            )
            logger.info("✅ Tokenizer loaded successfully")

            # Load model
            logger.info("📦 Loading model...")
            self.model = AutoModelForSequenceClassification.from_pretrained(
                str(model_path),  # Explicit string conversion
                local_files_only=True,
                trust_remote_code=True
            )
            logger.info("✅ Model loaded successfully")

            self.model.to(self.device)
            self.model.eval()

            self.is_loaded = True
            logger.info("✅ MetricX model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to load MetricX model: {e}")
            logger.error(f"Model path: {self.model_name}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            self.is_loaded = False
            return False

    def calculate_score(self, source: str, hypothesis: str, reference: str = None) -> Dict:
        """Calculate MetricX score"""
        try:
            if not self.is_loaded:
                if not self.load_model():
                    return {"error": "MetricX model not available"}

            input_text = f"source: {source} hypothesis: {hypothesis}"
            if reference:
                input_text += f" reference: {reference}"

            inputs = self.tokenizer(
                input_text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits

                if logits.shape[-1] == 1:
                    score = torch.sigmoid(logits).item()
                else:
                    probs = torch.softmax(logits, dim=-1)
                    score = probs[:, 1].item() if probs.shape[-1] > 1 else probs.item()

            return {
                "score": float(score),
                "model": self.model_name,
                "reference_based": reference is not None
            }

        except Exception as e:
            logger.error(f"❌ MetricX scoring failed: {e}")
            return {"error": str(e)}

    def batch_calculate_scores(self, requests: List[Dict]) -> List[Dict]:
        """Calculate scores for multiple requests"""
        results = []
        for req in requests:
            result = self.calculate_score(
                source=req.get("source", ""),
                hypothesis=req.get("hypothesis", ""),
                reference=req.get("reference")
            )
            result.update({
                "source_language": req.get("source_language", "unknown"),
                "target_language": req.get("target_language", "unknown")
            })
            results.append(result)

        return results

# Global MetricX service instance
metricx_service = MetricXService()