from fastapi import APIRouter
from app.services import model_service
from app.schemas.models import ModelConfigResponse

router = APIRouter(prefix="/models", tags=["models"])

@router.get("", response_model=ModelConfigResponse)
async def get_models():
    """
    Returns the hardcoded list of models and their supported sections.
    Source: app/config/models.yaml
    """
    data = model_service.get_model_config()
    return ModelConfigResponse(models=data)
