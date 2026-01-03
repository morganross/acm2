import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional

# Path to the models.yaml file
# acm2/app/services/model_service.py -> acm2/app/config/models.yaml
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "models.yaml"


def get_model_config() -> Dict[str, Dict[str, Any]]:
    """
    Reads the models.yaml file and returns the configuration.
    
    Returns dict of model_key -> {sections: [...], max_output_tokens: int}
    
    Handles both old format (model: [sections]) and new format 
    (model: {sections: [...], max_output_tokens: int}).
    """
    if not CONFIG_PATH.exists():
        print(f"Warning: Model config not found at {CONFIG_PATH}")
        return {}
    
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        if not data:
            return {}
        
        result = {}
        for model_key, model_data in data.items():
            if isinstance(model_data, list):
                # Old format: model: [sections]
                result[model_key] = {
                    "sections": model_data,
                    "max_output_tokens": None,
                }
            elif isinstance(model_data, dict):
                # New format: model: {sections: [...], max_output_tokens: int}
                result[model_key] = {
                    "sections": model_data.get("sections", []),
                    "max_output_tokens": model_data.get("max_output_tokens"),
                }
            else:
                print(f"Warning: Unknown format for model {model_key}: {type(model_data)}")
                continue
        
        return result
    except Exception as e:
        print(f"Error reading model config: {e}")
        return {}
