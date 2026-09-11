import os
from pathlib import Path

def get_data_dir() -> Path:
    env_dir = os.getenv("EMILE_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    
    # Fallback default
    default_dir = Path("data/processed")
    if default_dir.exists():
        return default_dir
        
    raise FileNotFoundError(
        "Data directory not found. Please set EMILE_DATA_DIR env var "
        "or ensure 'data/processed' exists at project root."
    )

DATA_DIR = get_data_dir()
