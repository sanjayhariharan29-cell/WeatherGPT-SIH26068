from fastapi import APIRouter, Query
from backend.services.geocoding_service import GeocodingService

router = APIRouter(prefix="/locations", tags=["Locations"])
geocoding = GeocodingService()

@router.get("/search")
async def search_locations(q: str = Query("Coimbatore", description="Search query")):
    """Searches for locations by name (Tamil / English)."""
    results = await geocoding.search_locations(q)
    return {"results": results}
