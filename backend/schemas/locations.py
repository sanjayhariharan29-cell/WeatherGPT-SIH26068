from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict

class LocationResolveRequest(BaseModel):
    """Payload for resolving location query string or coordinates."""
    query: Optional[str] = Field(None, description="Location search query")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)

    @field_validator("latitude")
    def val_lat(cls, v):
        if v is not None and (v < -90.0 or v > 90.0):
            raise ValueError("Latitude must be between -90 and +90 degrees.")
        return v

    @field_validator("longitude")
    def val_lon(cls, v):
        if v is not None and (v < -180.0 or v > 180.0):
            raise ValueError("Longitude must be between -180 and +180 degrees.")
        return v


class ReverseGeocodeRequest(BaseModel):
    """Payload for reverse geocoding device GPS coordinates."""
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy: Optional[float] = Field(None, ge=0.0, description="GPS accuracy in meters")


class LocationDetailResponse(BaseModel):
    """Response payload representing resolved location metadata."""
    name: str
    district: Optional[str] = "Coimbatore"
    state: Optional[str] = "Tamil Nadu"
    country: str = "India"
    latitude: float
    longitude: float
    timezone: str = "Asia/Kolkata"
    accuracy: Optional[float] = None
    source: str = "geocoding"

    model_config = ConfigDict(from_attributes=True)
