"""
API Router - Combines all route modules.
"""
from fastapi import APIRouter

from .routes import documents, generation, runs, presets, evaluation, models, contents, github_connections, rate_limits

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


# Health check at API level
@api_router.get("/health")
async def health_check() -> dict:
    """API health check."""
    return {"status": "ok", "version": "2.0.0"}
