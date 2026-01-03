"""
Runs API Routes.

Endpoints for managing evaluation runs (presets, executions).
This module assembles all run-related routers into a single unified router.
"""
from fastapi import APIRouter

from .crud import router as crud_router
from .execution import router as execution_router
from .evaluation import router as evaluation_router
from .artifacts import router as artifacts_router
from .websocket import router as websocket_router

# Create the main router with tags (prefix is added by api_router)
router = APIRouter(tags=["runs"])

# Include all sub-routers (they have their own path definitions)
router.include_router(crud_router)
router.include_router(execution_router)
router.include_router(evaluation_router)
router.include_router(artifacts_router)
router.include_router(websocket_router)

# Re-export helpers for backwards compatibility
from .helpers import (
    serialize_dataclass,
    calculate_progress,
    to_summary,
    to_detail,
    get_fpf_stats_from_summary,
)

# Re-export active executors for cancellation support
from .execution import _active_executors

__all__ = [
    "router",
    "serialize_dataclass",
    "calculate_progress", 
    "to_summary",
    "to_detail",
    "get_fpf_stats_from_summary",
    "_active_executors",
]
