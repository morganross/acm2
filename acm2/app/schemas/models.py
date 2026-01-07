from pydantic import BaseModel
from typing import List, Dict, Optional


class ModelInfo(BaseModel):
    """Information about a model including sections and limits."""
    sections: List[str]
    max_output_tokens: Optional[int] = None
    dr_native: bool = False  # Deep Research native models (autonomous research, not token-priced)


class ModelConfigResponse(BaseModel):
    """Response containing model configurations."""
    models: Dict[str, ModelInfo]
