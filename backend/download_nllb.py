# download_nllb.py
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import os

# Define the model ID from Hugging Face
hf_model_id = "facebook/nllb-200-distilled-600M"

current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_script_dir, '..')

local_folder_name = "nllb-200-distilled-600M"
local_save_path = os.path.join(project_root, "models", local_folder_name)

# Create the directory if it doesn't exist
os.makedirs(local_save_path, exist_ok=True)

print(f"Downloading and saving model '{hf_model_id}' to: {local_save_path}")

try:
    # Download the model and tokenizer from Hugging Face Hub
    # This will save directly to local_save_path
    tokenizer = AutoTokenizer.from_pretrained(hf_model_id)
    model = AutoModelForSeq2SeqLM.from_pretrained(hf_model_id) # NLLB is a Seq2Seq model

    tokenizer.save_pretrained(local_save_path)
    model.save_pretrained(local_save_path)

    print(f"Successfully saved {hf_model_id} to {local_save_path}")

except Exception as e:
    print(f"Error saving model to local directory: {e}")