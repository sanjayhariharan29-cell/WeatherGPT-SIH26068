from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import User, SavedLocation
from backend.services.geocoding_service import GeocodingService
from backend.schemas.auth import SavedLocationCreate, SavedLocationResponse
from backend.core.security import get_current_user

router = APIRouter(prefix="/locations", tags=["Locations"])
geocoding = GeocodingService()

@router.get("/search")
async def search_locations(q: str = Query("Coimbatore", description="Search query")):
    """Public endpoint: Searches for locations by name (Tamil / English)."""
    results = await geocoding.search_locations(q)
    return {"results": results}

@router.post("/saved", response_model=SavedLocationResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_location(
    req: SavedLocationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected endpoint: Saves a preferred location for the authenticated user."""
    loc = SavedLocation(
        user_id=current_user.id,
        name=req.name,
        latitude=req.latitude,
        longitude=req.longitude
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc

@router.get("/saved", response_model=List[SavedLocationResponse])
async def list_saved_locations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected endpoint: Lists saved locations owned by the authenticated user."""
    locations = db.query(SavedLocation).filter(SavedLocation.user_id == current_user.id).all()
    return locations

@router.delete("/saved/{location_id}")
async def delete_saved_location(
    location_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected endpoint: Deletes a saved location with user ownership check."""
    loc = db.query(SavedLocation).filter(SavedLocation.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Saved location not found")
    
    # User Ownership Check
    if loc.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this saved location"
        )
    
    db.delete(loc)
    db.commit()
    return {"message": "Saved location deleted successfully"}
