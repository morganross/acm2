import json
from pathlib import Path
from typing import Any, List

from fastapi import APIRouter
from app.services import model_service
from app.schemas.models import ModelConfigResponse

router = APIRouter(prefix="/models", tags=["models"])


def _get_pricing_index_path() -> Path:
    """Get path to FPF's pricing_index.json."""
    # Path: models.py -> routes -> api -> app -> acm2 (inner) -> FilePromptForge/pricing
    current_dir = Path(__file__).resolve().parent
    fpf_pricing = current_dir.parent.parent.parent.parent / "FilePromptForge" / "pricing" / "pricing_index.json"
    return fpf_pricing


@router.get("", response_model=ModelConfigResponse)
async def get_models():
    """
    Returns the hardcoded list of models and their supported sections.
    Source: app/config/models.yaml
    """
    data = model_service.get_model_config()
    return ModelConfigResponse(models=data)


@router.get("/pricing")
async def get_pricing() -> List[Any]:
    """
    Returns model pricing data from FPF's pricing_index.json.
    Each entry includes input/output prices per million tokens.
    """
    pricing_path = _get_pricing_index_path()
    if not pricing_path.exists():
        return []
    try:
        with open(pricing_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
