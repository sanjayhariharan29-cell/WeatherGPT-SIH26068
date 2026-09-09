from fastapi import APIRouter, Response, status
from sqlalchemy import text
from backend.config.settings import settings
from backend.db.session import engine

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

@router.get("/health/liveness")
async def liveness_check():
    """Liveness probe to confirm backend container process survival."""
    return {
        "status": "alive",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT
    }

@router.get("/health/readiness")
async def readiness_check(response: Response):
    """Readiness probe to confirm database & service readiness before routing traffic."""
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unready",
            "database": "disconnected",
            "service": settings.APP_NAME
        }

    return {
        "status": "ready",
        "database": "connected",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT
    }
