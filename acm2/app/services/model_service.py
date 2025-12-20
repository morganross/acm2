import yaml
from pathlib import Path
from typing import Dict, List

# Path to the models.yaml file
# acm2/app/services/model_service.py -> acm2/app/config/models.yaml
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "models.yaml"

def get_model_config() -> Dict[str, List[str]]:
    """Reads the models.yaml file and returns the configuration."""
    if not CONFIG_PATH.exists():
        # Fallback or error logging could go here
        print(f"Warning: Model config not found at {CONFIG_PATH}")
        return {}
    
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not data:
            return {}
            
        return data
    except Exception as e:
        print(f"Error reading model config: {e}")
        return {}
