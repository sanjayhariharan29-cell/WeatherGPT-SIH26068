from fastapi import APIRouter

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check():
    """Health check endpoint for deployment monitoring."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "WeatherGPT-SIH26068 Backend",
        "organization": "Ministry of Earth Sciences / IMD"
    }
