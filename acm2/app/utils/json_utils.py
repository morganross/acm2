from datetime import datetime
from enum import Enum
from typing import Any

def serialize_for_ws(data: Any) -> Any:
    """
    Recursively serialize data for WebSocket transmission.
    Handles datetime objects (ISO format) and Enums (value).
    """
    if isinstance(data, dict):
        return {k: serialize_for_ws(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_for_ws(v) for v in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, Enum):
        return data.value
    else:
        return data
