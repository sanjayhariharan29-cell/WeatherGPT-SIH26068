from fastapi import APIRouter
from backend.config.settings import settings

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check():
    """Health check endpoint for process survival monitoring."""
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
        "organization": "Ministry of Earth Sciences / IMD"
    }
