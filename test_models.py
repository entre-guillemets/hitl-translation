# Create a simple test file: test_models.py
import os
from pathlib import Path

# Check what models you actually have
models_dir = Path("models")
print("Models in local directory:")
for item in models_dir.iterdir():
    if item.is_dir():
        print(f"  ✓ {item.name}")

# Check COMET cache
cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
comet_cache = cache_dir / "models--Unbabel--wmt22-comet-da"
print(f"\nCOMET cache exists: {comet_cache.exists()}")
if comet_cache.exists():
    print(f"COMET cache path: {comet_cache}")
    snapshots = comet_cache / "snapshots"
    if snapshots.exists():
        for snapshot in snapshots.iterdir():
            checkpoint = snapshot / "checkpoints" / "model.ckpt"
            print(f"  Checkpoint exists: {checkpoint.exists()} - {checkpoint}")