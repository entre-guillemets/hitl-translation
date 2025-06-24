#!/usr/bin/env python3
import sys
import os
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, T5Tokenizer, T5ForConditionalGeneration

def download_model(model_name, base_path):
    try:
        # Create directory
        model_dir = os.path.join(base_path, model_name.replace('/', '_'))
        os.makedirs(model_dir, exist_ok=True)
        
        print(f"Downloading {model_name}...")
        
        # Download model and tokenizer with explicit config saving
        if "t5" in model_name.lower():
            tokenizer = T5Tokenizer.from_pretrained(model_name)
            model = T5ForConditionalGeneration.from_pretrained(model_name)
        else:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        
        # Save locally with all configuration files
        tokenizer.save_pretrained(model_dir)
        model.save_pretrained(model_dir)
        
        # Verify config.json exists
        config_path = os.path.join(model_dir, 'config.json')
        if os.path.exists(config_path):
            print(f"✓ Config file verified: {config_path}")
        else:
            print(f"⚠ Warning: config.json not found in {model_dir}")
        
        print(f"Successfully downloaded {model_name} to {model_dir}")
        return 0
        
    except Exception as e:
        print(f"Error downloading {model_name}: {e}")
        return 1

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python download_model.py <model_name> <base_path>")
        sys.exit(1)
    
    model_name = sys.argv[1]
    base_path = sys.argv[2]
    
    exit_code = download_model(model_name, base_path)
    sys.exit(exit_code)
