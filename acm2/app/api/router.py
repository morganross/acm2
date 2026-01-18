"""
API Router - Combines all route modules.
"""
from fastapi import APIRouter

from .routes import (
    documents, generation, runs, presets, evaluation, models,
    contents, github_connections, rate_limits, health, users, provider_keys,
    settings
)

# Main API router
api_router = APIRouter(prefix="/api/v1")

# Include all route modules
api_router.include_router(documents.router)
api_router.include_router(generation.router)
api_router.include_router(runs.router)
api_router.include_router(presets.router)
api_router.include_router(evaluation.router)
api_router.include_router(models.router)
api_router.include_router(contents.router)
api_router.include_router(github_connections.router)
api_router.include_router(rate_limits.router)
api_router.include_router(health.router)
api_router.include_router(users.router)
api_router.include_router(provider_keys.router)
api_router.include_router(settings.router)


# Legacy health check (kept for backwards compatibility)
@api_router.get("/health-legacy")
async def health_check_legacy() -> dict:
    """API health check (legacy endpoint)."""
    return {"status": "ok", "version": "2.0.0"}
