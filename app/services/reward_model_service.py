import logging
import torch
from typing import Dict, List, Optional, Tuple
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import numpy as np

logger = logging.getLogger(__name__)

class RewardModelService:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = "microsoft/DialoGPT-medium"  # Placeholder - use actual reward model
        self.is_loaded = False

    def load_model(self) -> bool:
        """Load reward model"""
        try:
            logger.info(f"Loading reward model: {self.model_name}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            
            self.is_loaded = True
            logger.info("✓ Reward model loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load reward model: {e}")
            self.is_loaded = False
            return False

    def calculate_reward(self, source: str, translation: str, reference: str = None) -> Dict:
        """Calculate reward score for a translation"""
        try:
            if not self.is_loaded:
                if not self.load_model():
                    return {"error": "Reward model not available"}
            
            # Prepare input for reward calculation
            if reference:
                input_text = f"Source: {source} Translation: {translation} Reference: {reference}"
            else:
                input_text = f"Source: {source} Translation: {translation}"
            
            # Tokenize
            inputs = self.tokenizer(
                input_text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Get reward score
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                
                # Convert to reward score (0-1 range)
                if logits.shape[-1] == 1:
                    reward = torch.sigmoid(logits).item()
                else:
                    # Use softmax for multi-class output
                    probs = torch.softmax(logits, dim=-1)
                    reward = probs[:, -1].item()  # Assume last class is "good"
            
            return {
                "reward_score": float(reward),
                "model": self.model_name,
                "confidence": float(reward)  # Use reward as confidence
            }
            
        except Exception as e:
            logger.error(f"Reward calculation failed: {e}")
            return {"error": str(e)}

    def rank_translations(self, source: str, translations: List[str], 
                         reference: str = None) -> List[Dict]:
        """Rank multiple translations by reward score"""
        try:
            results = []
            
            for i, translation in enumerate(translations):
                reward_data = self.calculate_reward(source, translation, reference)
                results.append({
                    "translation": translation,
                    "index": i,
                    "reward_score": reward_data.get("reward_score", 0),
                    "error": reward_data.get("error")
                })
            
            # Sort by reward score (descending)
            results.sort(key=lambda x: x["reward_score"], reverse=True)
            
            # Add ranking
            for i, result in enumerate(results):
                result["rank"] = i + 1
            
            return results
            
        except Exception as e:
            logger.error(f"Translation ranking failed: {e}")
            return []

    def compare_translations(self, source: str, translation_a: str, 
                           translation_b: str, reference: str = None) -> Dict:
        """Compare two translations and return preference"""
        try:
            reward_a = self.calculate_reward(source, translation_a, reference)
            reward_b = self.calculate_reward(source, translation_b, reference)
            
            if "error" in reward_a or "error" in reward_b:
                return {"error": "Failed to calculate rewards"}
            
            score_a = reward_a["reward_score"]
            score_b = reward_b["reward_score"]
            
            if score_a > score_b:
                preferred = "A"
                confidence = score_a - score_b
            elif score_b > score_a:
                preferred = "B"
                confidence = score_b - score_a
            else:
                preferred = "EQUAL"
                confidence = 0
            
            return {
                "preferred": preferred,
                "confidence": float(confidence),
                "score_a": float(score_a),
                "score_b": float(score_b),
                "difference": float(abs(score_a - score_b))
            }
            
        except Exception as e:
            logger.error(f"Translation comparison failed: {e}")
            return {"error": str(e)}

# Global reward model service instance
reward_model_service = RewardModelService()
