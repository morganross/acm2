"""
Health Check and System Information Endpoints
"""
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring and WordPress plugin."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "service": "ACM2 API"
    }


@router.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "ACM2 - AI Content Model Evaluation System",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }
