#!/usr/bin/env python3
import sys
import json
import nltk
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
import sacrebleu
from typing import Optional, Dict, Any

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class QualityMetrics:
    def __init__(self):
        self.smoothing = SmoothingFunction()
    
    def calculate_bleu(self, hypothesis: str, reference: str) -> float:
        """Calculate BLEU score with proper reference formatting"""
        try:
            if not hypothesis or not reference or hypothesis.strip() == "" or reference.strip() == "":
                return 0.0
            
            # Tokenize both texts
            hyp_tokens = hypothesis.lower().split()
            ref_tokens = reference.lower().split()
            
            if not hyp_tokens or not ref_tokens:
                return 0.0
            
            # CRITICAL: BLEU expects list of lists for references
            references = [ref_tokens]  
            
            # Calculate BLEU with smoothing
            bleu_score = sentence_bleu(
                references, 
                hyp_tokens,
                smoothing_function=self.smoothing.method1
            )
            
            return max(0.0, min(1.0, bleu_score))
            
        except Exception as e:
            print(f"BLEU calculation error: {e}", file=sys.stderr)
            return 0.0
    
    def calculate_comet(self, source: str, hypothesis: str, reference: str = None) -> float:
        """Calculate COMET score with proper error handling"""
        try:
            # Try to import COMET
            from comet import download_model, load_from_checkpoint
            
            # Download and load COMET model
            model_path = download_model("wmt20-comet-da")
            model = load_from_checkpoint(model_path)
            
            # Prepare data for COMET
            if reference:
                # Reference-based COMET
                data = [{
                    "src": source,
                    "mt": hypothesis,
                    "ref": reference
                }]
            else:
                # Reference-free COMET (QE mode)
                data = [{
                    "src": source,
                    "mt": hypothesis
                }]
            
            # Get COMET score
            scores = model.predict(data, batch_size=1, gpus=0)
            
            # Handle different COMET return formats
            if isinstance(scores, dict):
                # Handle version compatibility issue from search results
                if 'mean_score' in scores:
                    return scores['mean_score'] if isinstance(scores['mean_score'], (int, float)) else 0.0
                elif 'scores' in scores:
                    score_list = scores['scores']
                    return score_list[0] if isinstance(score_list, list) and len(score_list) > 0 else 0.0
            elif isinstance(scores, list):
                return scores[0] if len(scores) > 0 else 0.0
            else:
                return float(scores) if scores is not None else 0.0
                
        except ImportError:
            print("COMET not available, skipping", file=sys.stderr)
            return None
        except Exception as e:
            print(f"COMET calculation error: {e}", file=sys.stderr)
            return None
    
    def calculate_all_metrics(self, hypothesis: str, reference: str = None, source: str = None) -> Dict[str, Any]:
        """Calculate all available metrics with proper validation"""
        metrics = {}
        
        try:
            # Validate inputs
            if not hypothesis or hypothesis.strip() == "":
                return {
                    'bleu_score': 0.0,
                    'chrf_score': 0.0,
                    'ter_score': 1.0,
                    'comet_score': None,
                    'quality_label': "EMPTY_HYPOTHESIS",
                    'error': "Empty hypothesis provided"
                }
            
            if reference and reference.strip() != "":
                # Reference-based metrics
                print(f"Calculating with reference: '{reference[:50]}...'", file=sys.stderr)
                
                # BLEU Score
                metrics['bleu_score'] = self.calculate_bleu(hypothesis, reference)
                
                # chrF Score using SacreBLEU
                try:
                    chrf = sacrebleu.sentence_chrf(hypothesis, [reference])
                    metrics['chrf_score'] = chrf.score / 100.0
                except:
                    metrics['chrf_score'] = 0.0
                
                # TER Score (simplified)
                metrics['ter_score'] = min(1.0, self.calculate_simple_ter(hypothesis, reference))
                
                # COMET Score
                if source:
                    metrics['comet_score'] = self.calculate_comet(source, hypothesis, reference)
                else:
                    metrics['comet_score'] = None
                    
            else:
                # No reference available
                print("No reference provided, skipping reference-based metrics", file=sys.stderr)
                metrics['bleu_score'] = None
                metrics['chrf_score'] = None
                metrics['ter_score'] = None
                
                # Reference-free COMET
                if source:
                    metrics['comet_score'] = self.calculate_comet(source, hypothesis)
                else:
                    metrics['comet_score'] = None
            
            # Determine quality label
            if metrics.get('bleu_score') is not None:
                bleu = metrics['bleu_score']
                if bleu >= 0.5:
                    metrics['quality_label'] = "EXCELLENT"
                elif bleu >= 0.3:
                    metrics['quality_label'] = "GOOD"
                elif bleu >= 0.15:
                    metrics['quality_label'] = "FAIR"
                else:
                    metrics['quality_label'] = "POOR"
            else:
                metrics['quality_label'] = "NO_REFERENCE"
            
        except Exception as e:
            print(f"Metrics calculation error: {e}", file=sys.stderr)
            metrics = {
                'bleu_score': 0.0,
                'chrf_score': 0.0,
                'ter_score': 1.0,
                'comet_score': None,
                'quality_label': "ERROR",
                'error': str(e)
            }
        
        return metrics
    
    def calculate_simple_ter(self, hypothesis: str, reference: str) -> float:
        """Simple TER calculation"""
        try:
            hyp_words = hypothesis.lower().split()
            ref_words = reference.lower().split()
            
            if not ref_words:
                return 1.0
            
            # Simple edit distance
            edits = abs(len(hyp_words) - len(ref_words))
            for i in range(min(len(hyp_words), len(ref_words))):
                if hyp_words[i] != ref_words[i]:
                    edits += 1
            
            return min(1.0, edits / len(ref_words))
        except:
            return 1.0

def main():
    if len(sys.argv) < 2:
        print("Usage: python quality_metrics.py <hypothesis> [reference] [source]")
        sys.exit(1)
    
    hypothesis = sys.argv[1]
    reference = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].strip() else None
    source = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3].strip() else None
    
    # Debug output
    print(f"Hypothesis: '{hypothesis}'", file=sys.stderr)
    print(f"Reference: '{reference}'", file=sys.stderr)
    print(f"Source: '{source}'", file=sys.stderr)
    
    calculator = QualityMetrics()
    metrics = calculator.calculate_all_metrics(hypothesis, reference, source)
    
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
