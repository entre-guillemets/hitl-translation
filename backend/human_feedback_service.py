# backend/human_feedback_service.py
import uuid
import json
import os
from datetime import datetime
from typing import Dict, List, Any
from reward_model_service import reward_model_service

class EnhancedHumanFeedbackService:
    """Enhanced feedback service with RLHF integration"""
    
    def __init__(self):
        self.feedback_data = []
        self.preference_pairs = []
        self.load_feedback_data()
    
    def process_translation_edit(self, original_translation: str, human_edit: str, 
                               source_text: str, string_id: str, reference: str = None):
        """Process human edits and collect preference data for RLHF"""
        
        # Calculate human preference score based on edit distance
        edit_distance = self.calculate_edit_distance(original_translation, human_edit)
        max_length = max(len(original_translation), len(human_edit))
        
        # Convert edit distance to preference score (0-1, higher is better)
        if max_length == 0:
            preference_score = 1.0
        else:
            similarity = 1.0 - (edit_distance / max_length)
            preference_score = max(0.0, min(1.0, similarity))
        
        # Store feedback for reward model training
        feedback_entry = {
            "id": str(uuid.uuid4()),
            "type": "translation_edit",
            "string_id": string_id,
            "source_text": source_text,
            "original_translation": original_translation,
            "human_edit": human_edit,
            "reference": reference,
            "preference_score": preference_score,
            "edit_distance": edit_distance,
            "timestamp": datetime.now().isoformat()
        }
        
        self.feedback_data.append(feedback_entry)
        
        # Create preference pair for RLHF
        preference_pair = {
            "source": source_text,
            "reference": reference,
            "worse_translation": original_translation,
            "better_translation": human_edit,
            "preference_strength": 1.0 - preference_score  # How much better the edit is
        }
        
        self.preference_pairs.append(preference_pair)
        
        # Collect feedback for reward model
        reward_model_service.collect_human_feedback(
            source=source_text,
            translation=human_edit,
            human_score=preference_score,
            reference=reference
        )
        
        self.save_feedback_data()
        print(f"Processed edit feedback: preference_score={preference_score:.3f}")
    
    def process_quality_rating(self, source: str, translation: str, quality_score: float,
                             reference: str = None, annotations: List[Dict] = None):
        """Process direct quality ratings from human annotators"""
        
        # Normalize quality score to 0-1 range
        normalized_score = max(0.0, min(1.0, quality_score / 5.0))
        
        feedback_entry = {
            "id": str(uuid.uuid4()),
            "type": "quality_rating",
            "source_text": source,
            "translation": translation,
            "reference": reference,
            "quality_score": normalized_score,
            "annotations": annotations or [],
            "timestamp": datetime.now().isoformat()
        }
        
        self.feedback_data.append(feedback_entry)
        
        # Collect feedback for reward model
        reward_model_service.collect_human_feedback(
            source=source,
            translation=translation,
            human_score=normalized_score,
            reference=reference,
            annotations=annotations
        )
        
        self.save_feedback_data()
        print(f"Processed quality rating: score={normalized_score:.3f}")
    
    def process_preference_comparison(self, source: str, translation_a: str, translation_b: str,
                                   preferred: str, reference: str = None):
        """Process pairwise preference comparisons"""
        
        if preferred not in ['A', 'B']:
            print("Invalid preference. Must be 'A' or 'B'")
            return
        
        better_translation = translation_a if preferred == 'A' else translation_b
        worse_translation = translation_b if preferred == 'A' else translation_a
        
        # Create preference pair
        preference_pair = {
            "source": source,
            "reference": reference,
            "better_translation": better_translation,
            "worse_translation": worse_translation,
            "preference_strength": 1.0  # Strong preference
        }
        
        self.preference_pairs.append(preference_pair)
        
        # Collect feedback for both translations
        reward_model_service.collect_human_feedback(
            source=source,
            translation=better_translation,
            human_score=0.8,  # Higher score for preferred
            reference=reference
        )
        
        reward_model_service.collect_human_feedback(
            source=source,
            translation=worse_translation,
            human_score=0.3,  # Lower score for non-preferred
            reference=reference
        )
        
        self.save_feedback_data()
        print(f"Processed preference comparison: preferred {preferred}")
    
    def calculate_edit_distance(self, str1: str, str2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if len(str1) < len(str2):
            return self.calculate_edit_distance(str2, str1)
        
        if len(str2) == 0:
            return len(str1)
        
        previous_row = list(range(len(str2) + 1))
        for i, c1 in enumerate(str1):
            current_row = [i + 1]
            for j, c2 in enumerate(str2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def get_training_data_for_rlhf(self) -> Dict[str, List]:
        """Get formatted training data for RLHF"""
        return {
            "feedback_data": self.feedback_data,
            "preference_pairs": self.preference_pairs
        }
    
    def trigger_reward_model_training(self):
        """Trigger reward model retraining with collected feedback"""
        try:
            reward_model_service.train_from_human_feedback()
            print("Reward model training triggered successfully")
        except Exception as e:
            print(f"Error training reward model: {e}")
    
    def save_feedback_data(self):
        """Save feedback data to file"""
        data_path = "./data/human_feedback.json"
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump({
                "feedback_data": self.feedback_data,
                "preference_pairs": self.preference_pairs
            }, f, ensure_ascii=False, indent=2)
    
    def load_feedback_data(self):
        """Load existing feedback data"""
        data_path = "./data/human_feedback.json"
        if os.path.exists(data_path):
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.feedback_data = data.get("feedback_data", [])
                self.preference_pairs = data.get("preference_pairs", [])
            print(f"Loaded {len(self.feedback_data)} feedback entries")

# Global enhanced feedback service
enhanced_feedback_service = EnhancedHumanFeedbackService()
