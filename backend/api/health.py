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

@router.get("/health/metrics")
async def get_observability_metrics():
    """Returns comprehensive real-time telemetry: API latencies, provider availability, error rates, and cache stats."""
    from backend.services.observability_service import observability_service
    return observability_service.get_telemetry_snapshot()

@router.get("/health/detailed")
async def detailed_health_check(response: Response):
    """Deep multi-subsystem operational health probe without exposing internal credentials."""
    import time
    from backend.services.observability_service import observability_service
    from backend.services.cache import provider_cache

    t0 = time.perf_counter()
    db_ok = False
    db_latency = 0.0
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
        db_latency = round((time.perf_counter() - t0) * 1000, 2)
    except Exception:
        db_ok = False

    # Cache status
    cache_entries = len(getattr(provider_cache, "_cache", {}))

    # FCM status
    fcm_status = "CONFIGURED" if getattr(settings, "FIREBASE_CREDENTIALS_PATH", None) or getattr(settings, "FCM_SERVER_KEY", None) else "MOCK_MODE"

    # Overall degradation state
    state = "OPTIMAL" if db_ok else "DEGRADED"
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": state,
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "subsystems": {
            "database": {
                "status": "HEALTHY" if db_ok else "UNHEALTHY",
                "latency_ms": db_latency
            },
            "cache": {
                "status": "HEALTHY",
                "active_keys": cache_entries
            },
            "fcm_gateway": {
                "status": fcm_status
            }
        },
        "telemetry_summary": observability_service.get_telemetry_snapshot()
    }
