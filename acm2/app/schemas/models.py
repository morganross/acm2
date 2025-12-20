from pydantic import BaseModel
from typing import List, Dict

class ModelConfigResponse(BaseModel):
    models: Dict[str, List[str]]
