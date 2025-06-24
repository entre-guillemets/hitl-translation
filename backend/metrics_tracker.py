from typing import Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MetricsTracker:
    def __init__(self):
        self.baseline_metrics = {}
        self.experiment_metrics = []
    
    def record_baseline(self, language_pair: str, metrics: Dict[str, float]):
        """Record baseline metrics for a language pair"""
        self.baseline_metrics[language_pair] = {
            "bleu": metrics.get("bleu_score", 0),
            "comet": metrics.get("chrf_score", 0),
            "ter": metrics.get("ter_score", 1),
            "metricx": metrics.get("metricx_score", 20),
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"Recorded baseline metrics for {language_pair}")
    
    def record_experiment(self, experiment_name: str, language_pair: str, metrics: Dict[str, float], context_data: Dict[str, Any]):
        """Record metrics for an experiment with context data"""
        experiment = {
            "name": experiment_name,
            "language_pair": language_pair,
            "metrics": {
                "bleu": metrics.get("bleu_score", 0),
                "comet": metrics.get("chrf_score", 0),
                "ter": metrics.get("ter_score", 1),
                "metricx": metrics.get("metricx_score", 20)
            },
            "context_data": context_data,  # TM/Glossary/DNT usage
            "improvement": self.calculate_improvement(language_pair, metrics),
            "timestamp": datetime.now().isoformat()
        }
        self.experiment_metrics.append(experiment)
        logger.info(f"Recorded experiment {experiment_name} for {language_pair}")
        return experiment
    
    def calculate_improvement(self, language_pair: str, current_metrics: Dict[str, float]) -> Dict[str, float]:
        """Calculate improvement over baseline"""
        if language_pair not in self.baseline_metrics:
            return {"status": "no_baseline"}
        
        baseline = self.baseline_metrics[language_pair]
        
        improvements = {
            "bleu_improvement": (current_metrics.get("bleu_score", 0) - baseline["bleu"]) * 100,
            "comet_improvement": (current_metrics.get("chrf_score", 0) - baseline["comet"]) * 100,
            "ter_improvement": (baseline["ter"] - current_metrics.get("ter_score", 1)) * 100,  # Lower TER is better
            "metricx_improvement": baseline["metricx"] - current_metrics.get("metricx_score", 20)  # Lower MetricX is better
        }
        
        return improvements
    
    def get_experiment_summary(self, language_pair: str = None) -> Dict[str, Any]:
        """Get summary of experiments for a language pair or all experiments"""
        if language_pair:
            experiments = [exp for exp in self.experiment_metrics if exp["language_pair"] == language_pair]
        else:
            experiments = self.experiment_metrics
        
        if not experiments:
            return {"message": "No experiments found"}
        
        # Calculate average improvements
        total_experiments = len(experiments)
        avg_improvements = {
            "bleu": sum(exp["improvement"].get("bleu_improvement", 0) for exp in experiments) / total_experiments,
            "comet": sum(exp["improvement"].get("comet_improvement", 0) for exp in experiments) / total_experiments,
            "ter": sum(exp["improvement"].get("ter_improvement", 0) for exp in experiments) / total_experiments,
            "metricx": sum(exp["improvement"].get("metricx_improvement", 0) for exp in experiments) / total_experiments
        }
        
        return {
            "total_experiments": total_experiments,
            "language_pair": language_pair or "all",
            "average_improvements": avg_improvements,
            "latest_experiment": experiments[-1] if experiments else None
        }

# Global instance
metrics_tracker = MetricsTracker()
