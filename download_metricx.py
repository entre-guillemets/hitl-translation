# download_metricx_xxl.py
from transformers import AutoTokenizer, AutoModel
import os
import torch # Import torch for bfloat16

# The exact Hugging Face model ID for the XXL bfloat16 variant
metricx_hf_id = "google/metricx-24-hybrid-xxl-v2p6-bfloat16"

# Your desired local folder name within 'models' for this specific variant
local_folder_name = "metricx-24-hybrid-xxl-v2p6-bfloat16"

# Construct the absolute path to your models directory
# Adjust 'current_script_dir' based on where you save this Python script
# If this script is in your project root:
project_root_path = os.path.dirname(os.path.abspath(__file__))
models_path = os.path.join(project_root_path, "models")
# If this script is in your 'backend' folder:
# current_script_dir = os.path.dirname(os.path.abspath(__file__))
# project_root_path = os.path.dirname(current_script_dir)
# models_path = os.path.join(project_root_path, "models")


local_save_path = os.path.join(models_path, local_folder_name)

os.makedirs(local_save_path, exist_ok=True)
print(f"Downloading MetricX model from {metricx_hf_id} to {local_save_path}...")

try:
    # Load the tokenizer
    tokenizer = AutoTokenizer.from_pretrained(metricx_hf_id, trust_remote_code=True)

    # Load the model with bfloat16 dtype and trust_remote_code
    # You might also want device_map="auto" here if you were trying to offload earlier,
    # but save_pretrained usually works best with models loaded to CPU initially.
    model = AutoModel.from_pretrained(metricx_hf_id, torch_dtype=torch.bfloat16, trust_remote_code=True)

    # Save them to your specified local directory
    tokenizer.save_pretrained(local_save_path)
    model.save_pretrained(local_save_path)

    print("MetricX model (XXL bfloat16) re-saved locally successfully.")

except Exception as e:
    print(f"ERROR: Failed to re-download/save MetricX model (XXL bfloat16): {e}")
    print("This error can be caused by network issues during download of large files, or environment/dependency conflicts.")