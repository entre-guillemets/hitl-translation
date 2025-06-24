# backend/reward_model_service.py
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel
import numpy as np
from typing import List, Dict, Any, Tuple
import json
import pickle
import os
from datetime import datetime

class RewardModel(nn.Module):
    """Reward model that learns from human feedback to predict translation quality"""
    
    def __init__(self, model_name="bert-base-multilingual-cased"):
        super().__init__()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.encoder = AutoModel.from_pretrained(model_name)
        self.reward_head = nn.Sequential(
            nn.Linear(self.encoder.config.hidden_size, 512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 1)  # Single scalar reward
        )
    
    def forward(self, input_ids, attention_mask):
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.pooler_output
        reward = self.reward_head(pooled_output)
        return reward.squeeze(-1)

class RewardModelService:
    """Service for training and using reward models for RLHF"""
    
    def __init__(self, model_path="./models/reward_model.pt"):
        self.model_path = model_path
        self.model = None
        self.training_data = []
        self.load_model()
    
    def load_model(self):
        """Load existing reward model or create new one"""
        try:
            if os.path.exists(self.model_path):
                self.model = RewardModel()
                self.model.load_state_dict(torch.load(self.model_path, map_location='cpu'))
                self.model.eval()
                print("Loaded existing reward model")
            else:
                self.model = RewardModel()
                print("Created new reward model")
        except Exception as e:
            print(f"Error loading reward model: {e}")
            self.model = RewardModel()
    
    def prepare_input(self, source: str, translation: str, reference: str = None) -> str:
        """Prepare input text for reward model"""
        if reference:
            # Include reference for comparison
            input_text = f"Source: {source}\nTranslation: {translation}\nReference: {reference}"
        else:
            input_text = f"Source: {source}\nTranslation: {translation}"
        return input_text
    
    def predict_reward(self, source: str, translation: str, reference: str = None) -> float:
        """Predict reward score for a translation"""
        if self.model is None:
            return 0.5  # Default neutral score
        
        try:
            input_text = self.prepare_input(source, translation, reference)
            
            # Tokenize input
            inputs = self.model.tokenizer(
                input_text,
                return_tensors="pt",
                max_length=512,
                truncation=True,
                padding=True
            )
            
            # Get reward prediction
            with torch.no_grad():
                reward = self.model(inputs['input_ids'], inputs['attention_mask'])
                # Convert to 0-1 range using sigmoid
                reward_score = torch.sigmoid(reward).item()
            
            return reward_score
            
        except Exception as e:
            print(f"Error predicting reward: {e}")
            return 0.5
    
    def collect_human_feedback(self, source: str, translation: str, human_score: float, 
                             reference: str = None, annotations: List[Dict] = None):
        """Collect human feedback for training the reward model"""
        feedback_entry = {
            "source": source,
            "translation": translation,
            "reference": reference,
            "human_score": human_score,  # 0-1 scale
            "annotations": annotations or [],
            "timestamp": datetime.now().isoformat()
        }
        
        self.training_data.append(feedback_entry)
        
        # Save training data
        self.save_training_data()
        
        print(f"Collected feedback: score={human_score:.3f}")
    
    def train_from_human_feedback(self, batch_size=16, epochs=10, learning_rate=1e-5):
        """Train reward model from collected human feedback"""
        if len(self.training_data) < 10:
            print("Not enough training data. Need at least 10 examples.")
            return
        
        print(f"Training reward model on {len(self.training_data)} examples...")
        
        # Prepare training data
        inputs = []
        targets = []
        
        for entry in self.training_data:
            input_text = self.prepare_input(
                entry["source"], 
                entry["translation"], 
                entry.get("reference")
            )
            inputs.append(input_text)
            targets.append(entry["human_score"])
        
        # Tokenize all inputs
        tokenized = self.model.tokenizer(
            inputs,
            return_tensors="pt",
            max_length=512,
            truncation=True,
            padding=True
        )
        
        targets = torch.tensor(targets, dtype=torch.float32)
        
        # Training setup
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate)
        criterion = nn.MSELoss()
        
        self.model.train()
        
        # Training loop
        for epoch in range(epochs):
            total_loss = 0
            num_batches = 0
            
            for i in range(0, len(inputs), batch_size):
                batch_input_ids = tokenized['input_ids'][i:i+batch_size]
                batch_attention_mask = tokenized['attention_mask'][i:i+batch_size]
                batch_targets = targets[i:i+batch_size]
                
                optimizer.zero_grad()
                
                # Forward pass
                predictions = self.model(batch_input_ids, batch_attention_mask)
                predictions = torch.sigmoid(predictions)  # Ensure 0-1 range
                
                # Calculate loss
                loss = criterion(predictions, batch_targets)
                
                # Backward pass
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
                num_batches += 1
            
            avg_loss = total_loss / num_batches
            print(f"Epoch {epoch+1}/{epochs}, Average Loss: {avg_loss:.4f}")
        
        # Save trained model
        self.save_model()
        self.model.eval()
        
        print("Reward model training completed!")
    
    def save_model(self):
        """Save the trained reward model"""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        torch.save(self.model.state_dict(), self.model_path)
        print(f"Saved reward model to {self.model_path}")
    
    def save_training_data(self):
        """Save training data for future use"""
        data_path = "./data/reward_training_data.json"
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(self.training_data, f, ensure_ascii=False, indent=2)
    
    def load_training_data(self):
        """Load existing training data"""
        data_path = "./data/reward_training_data.json"
        if os.path.exists(data_path):
            with open(data_path, 'r', encoding='utf-8') as f:
                self.training_data = json.load(f)
            print(f"Loaded {len(self.training_data)} training examples")

# Global reward model service
reward_model_service = RewardModelService()
