import os
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

load_dotenv()

class MetricXService:
    def __init__(self):
        self.metricx_hf_id = "google/metricx-24-hybrid-large-v2p6"
        self.local_folder_name = "metricx-24-hybrid-large-v2p6"

        # Setup local model path
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_script_dir)
        models_path = os.path.join(project_root, "models")
        self.local_save_path = os.path.join(models_path, self.local_folder_name)

        self.tokenizer = None
        self.model = None

    def download_and_save_model(self):
        """Download and save the MetricX model and tokenizer locally"""
        os.makedirs(self.local_save_path, exist_ok=True)
        print(f"Downloading and saving model '{self.metricx_hf_id}' to: {self.local_save_path}")

        try:
            print("➡️ Downloading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.metricx_hf_id, trust_remote_code=True)
            print(f"✅ Tokenizer type: {type(self.tokenizer)}")

            print("➡️ Downloading model...")
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.metricx_hf_id)
            print(f"✅ Model type: {type(self.model)}")

            print("➡️ Saving tokenizer...")
            self.tokenizer.save_pretrained(self.local_save_path)

            print("➡️ Saving model...")
            self.model.save_pretrained(self.local_save_path)

            print("✅ Successfully saved model and tokenizer.")
            return True

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"❌ ERROR: Failed to download/save MetricX model: {e}")
            return False

    def load_model(self):
        """Load the MetricX model from local path, or download if necessary"""
        try:
            # Check if the folder exists and contains expected files
            required_files = ["config.json", "pytorch_model.bin", "tokenizer_config.json", "tokenizer.json"]
            if os.path.exists(self.local_save_path) and all(os.path.isfile(os.path.join(self.local_save_path, f)) for f in required_files):
                print(f"📦 Loading model from local path: {self.local_save_path}")
                self.tokenizer = AutoTokenizer.from_pretrained(self.local_save_path, use_fast=False, trust_remote_code=True)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(self.local_save_path)
            else:
                print("🛰️ Local model incomplete or missing. Downloading from Hugging Face...")
                if not self.download_and_save_model():
                    raise Exception("Download failed.")

            print("✅ MetricX model loaded successfully.")
            return True
        except Exception as e:
            print(f"❌ ERROR: Failed to load MetricX model: {e}")
            return False

    def evaluate_with_reference(self, source, translation, reference):
        """Evaluate translation quality with reference"""
        if not self.model or not self.tokenizer:
            raise Exception("Model not loaded. Call load_model() first.")

        input_text = f"source: {source} translation: {translation} reference: {reference}"
        inputs = self.tokenizer(input_text, return_tensors="pt", max_length=512, truncation=True)

        with torch.no_grad():
            outputs = self.model.generate(**inputs, max_length=10, num_beams=1)

        score = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return float(score)

    def evaluate_without_reference(self, source, translation):
        """Evaluate translation quality without reference"""
        if not self.model or not self.tokenizer:
            raise Exception("Model not loaded. Call load_model() first.")

        input_text = f"source: {source} translation: {translation}"
        inputs = self.tokenizer(input_text, return_tensors="pt", max_length=512, truncation=True)

        with torch.no_grad():
            outputs = self.model.generate(**inputs, max_length=10, num_beams=1)

        score = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return float(score)

# Optional: test it when run directly
if __name__ == "__main__":
    service = MetricXService()
    if service.load_model():
        src = "The cat sat on the mat."
        hyp = "El gato se sentó en la alfombra."
        ref = "El gato estaba sentado sobre la alfombra."

        score1 = service.evaluate_with_reference(src, hyp, ref)
        score2 = service.evaluate_without_reference(src, hyp)

        print(f"\n📝 Score (with reference): {score1}")
        print(f"📝 Score (no reference): {score2}")
