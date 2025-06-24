import logging
import torch
from typing import Dict, Any, Optional, List
from datetime import datetime
import numpy as np
import sys
import os

logger = logging.getLogger(__name__)

class MetricXService:
    def __init__(self, model_variant: str = "metricx-24-hybrid"):
        self.model_variant = model_variant
        self.model = None
        self.tokenizer = None
        # Construct models_path relative to the project root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        self.models_path = os.path.join(project_root, "models")
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # Added explicit MPS check for Apple Silicon
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
            logger.info("MPS (Apple Silicon GPU) is available and will be used for MetricX.")
        else:
            logger.info(f"Running MetricX on CPU. CUDA: {torch.cuda.is_available()}, MPS: {torch.backends.mps.is_available()}")

        self._load_model()
    
    def _load_model(self):
        """Load MetricX model from local directory"""
        try:
            # Import transformers dynamically here to ensure it's loaded after path setup
            from transformers import AutoTokenizer, AutoModel, AutoModelForSequenceClassification 
            
            # The 'metricx-24-hybrid' variant now correctly points to the 'v2p6' folder
            model_paths = {
                "metricx-24-hybrid": os.path.join(self.models_path, "metricx-24-hybrid-large-v2p6"),              
            }
            
            # Get the exact path for the selected model variant
            # The default fallback also points to the v2p6 version
            model_path = model_paths.get(self.model_variant, os.path.join(self.models_path, "metricx-24-hybrid-large-v2p6"))
            
            logger.info(f"Attempting to load MetricX model from: {model_path}")
            
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"MetricX model directory not found at {model_path}")

            try:
                self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
            except Exception as e_seq_class:
                logger.warning(f"Failed to load MetricX as AutoModelForSequenceClassification ({e_seq_class}), falling back to AutoModel.")
                # Fallback to generic AutoModel if specific class fails
                self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
                self.model = AutoModel.from_pretrained(model_path, local_files_only=True, trust_remote_code=True)
            
            # Move model to appropriate device
            self.model.to(self.device)
            self.model.eval() # Set model to evaluation mode
            
            logger.info(f"✓ MetricX model loaded successfully from local directory on {self.device}")
            
        except Exception as e:
            logger.warning(f"Could not load local MetricX model: {e}")
            self.model = None
            self.tokenizer = None
            logger.info("Using fallback scoring method for MetricX.")
    
    def _extract_metricx_score(self, outputs) -> float:
        """Extract MetricX score from model outputs.
        This is a simplified extraction and might need adjustment based on the exact model output.
        MetricX models typically output a single quality score.
        """
        try:
            # Common pattern for sequence classification or regression models
            if hasattr(outputs, 'logits'):
                # Assuming logits for a regression task (single value) or a score-like output
                score_tensor = outputs.logits
                
                # If it's a single scalar score (e.g., [batch_size, 1])
                if score_tensor.ndim == 2 and score_tensor.shape[1] == 1:
                    score = score_tensor.squeeze(-1).mean().item()
                else: # Fallback for other output shapes, might need specific logic
                    score = score_tensor.mean().item()
                
                if score_tensor.ndim == 0: # Scalar output
                    score = score_tensor.item()
                else:
                    score = score_tensor.mean().item() # Take mean for batch output

                # MetricX scores are typically lower=better, e.g., 0-25, so we return it directly.
                # Ensure it's constrained to a reasonable range if the model can output wildly.
                return max(0.0, min(25.0, score)) # Constrain to 0-25 range
                
            elif hasattr(outputs, 'last_hidden_state'):
                # This is more for feature extraction, unlikely for direct quality score
                pooled_output = outputs.last_hidden_state.mean(dim=1)
                score = torch.sigmoid(pooled_output.mean()).item() * 25.0 # Fallback heuristic
                return max(0.0, min(25.0, score))
            else:
                logger.warning("MetricX model output structure unexpected. Returning default score.")
                return 15.0 # Fallback if output structure is truly unknown
            
        except Exception as e:
            logger.warning(f"Error extracting MetricX score: {e}. Returning default score.")
            return 15.0  # Default middle score
    
    def evaluate_translation(self, source: str, hypothesis: str, reference: str = None, 
                           source_language: str = "auto", target_language: str = "auto") -> Dict[str, Any]:
        """Evaluate translation quality using local MetricX models"""
        try:
            if not hypothesis or not hypothesis.strip():
                return self._get_error_result("Empty hypothesis")
            
            if self.model is None or self.tokenizer is None:
                return self._calculate_fallback_score(source, hypothesis, reference)
            
            # Prepare input for MetricX
            # MetricX models might use specific token separators or formats.
            # The default format `source: X hypothesis: Y reference: Z` is common.
            if reference:
                input_text = f"source: {source} hypothesis: {hypothesis} reference: {reference}"
                mode = "reference_based"
            else:
                input_text = f"source: {source} hypothesis: {hypothesis}"
                mode = "reference_free"
            
            # Tokenize and predict
            inputs = self.tokenizer(input_text, return_tensors="pt", max_length=512, 
                                   truncation=True, padding=True)
            
            # Move inputs to same device as model
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                score = self._extract_metricx_score(outputs)
            
            # Calculate confidence and quality level based on MetricX score (0-25, lower is better)
            confidence = max(0.7, min(0.95, 1.0 - (score / 25.0))) # Convert 0-25 to 0-1 confidence
            quality_level = self._get_quality_level(score)
            
            return {
                "score": score, # Raw MetricX score (0-25)
                "confidence": confidence, # Converted confidence (0-1)
                "mode": mode,
                "variant": self.model_variant,
                "quality_level": quality_level,
                "source_language": source_language,
                "target_language": target_language
            }
            
        except Exception as e:
            logger.error(f"MetricX evaluation failed: {e}")
            return self._calculate_fallback_score(source, hypothesis, reference)
    
    def _calculate_fallback_score(self, source: str, hypothesis: str, reference: str = None) -> Dict[str, Any]:
        """Fallback scoring when MetricX models are not available"""
        try:
            # Length-based heuristic scoring
            source_len = len(source.split())
            hyp_len = len(hypothesis.split())
            
            if source_len == 0:
                length_ratio = 2.0
            else:
                length_ratio = hyp_len / source_len
            
            # Base score calculation (MetricX-like: 0-25, lower is better)
            if length_ratio < 0.3 or length_ratio > 3.0:
                base_score = 20.0  # Poor quality for extreme length ratios
            elif 0.5 <= length_ratio <= 1.5:
                base_score = 8.0   # Good quality for reasonable ratios
            else:
                base_score = 15.0  # Fair quality
            
            # Adjust for very short translations
            if hyp_len < 3:
                base_score += 5.0
            
            # Reference-based adjustment
            mode = "reference_free"
            if reference:
                mode = "reference_based"
                ref_len = len(reference.split())
                if ref_len > 0:
                    ref_ratio = hyp_len / ref_len
                    if 0.8 <= ref_ratio <= 1.2:
                        base_score -= 2.0  # Bonus for similar length to reference
            
            score = max(5.0, min(25.0, base_score)) # Ensure score is within valid range
            confidence = 0.6  # Lower confidence for fallback
            quality_level = self._get_quality_level(score)
            
            return {
                "score": score,
                "confidence": confidence,
                "mode": f"{mode}_fallback",
                "variant": "fallback",
                "quality_level": quality_level,
                "source_language": "auto",
                "target_language": "auto"
            }
            
        except Exception as e:
            logger.error(f"Fallback scoring failed: {e}")
            return self._get_error_result(str(e))
    
    def _get_quality_level(self, score: float) -> str:
        """Convert MetricX score to quality level (0-25, lower is better)"""
        if score <= 7:
            return "EXCELLENT"
        elif score <= 12:
            return "GOOD"
        elif score <= 18:
            return "FAIR"
        else:
            return "POOR"
    
    def _get_error_result(self, error_message: str) -> Dict[str, Any]:
        """Return error result structure"""
        return {
            "score": 20.0, # Default to a 'POOR' score for errors
            "confidence": 0.0,
            "mode": "error",
            "variant": "error",
            "quality_level": "POOR",
            "error": error_message
        }
    
    def batch_evaluate(self, requests: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Evaluate multiple translations in batch"""
        results = []
        for request in requests:
            result = self.evaluate_translation(
                source=request.get("source", ""),
                hypothesis=request.get("hypothesis", ""),
                reference=request.get("reference"),
                source_language=request.get("source_language", "auto"),
                target_language=request.get("target_language", "auto")
            )
            results.append(result)
        return results

# Global instance for FastAPI - instantiated once on startup
metricx_service = MetricXService()

# Command line interface for testing MetricXService directly
def main():
    """Command line interface for MetricX evaluation"""
    if len(sys.argv) < 3:
        print("Usage: python metricx_service.py <source> <hypothesis> [reference]")
        sys.exit(1)
    
    source = sys.argv[1]
    hypothesis = sys.argv[2]
    reference = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Evaluate translation
    result = metricx_service.evaluate_translation(source, hypothesis, reference)
    
    # Output as JSON
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()