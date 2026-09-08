"""AI Chat API Router.

Exposes conversational AI weather decision endpoint connected to
Person 1's NLU, Weather Reasoner, Hazard Detection, Advisory Engine, RAG, and Grounded LLM.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.services.chat_integration_service import ChatIntegrationService

router = APIRouter(tags=["AI Chat"])
chat_service = ChatIntegrationService()


class LocationPayload(BaseModel):
    name: str = "Coimbatore"
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    language: str = "ta"
    persona: str = "student"
    location: Optional[LocationPayload] = None
    conversation_id: Optional[str] = None

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty or only whitespace.")
        return cleaned


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    """Main WeatherGPT Conversational Decision Engine Endpoint."""
    loc_name = req.location.name if req.location else "Coimbatore"
    lat = req.location.latitude if req.location else None
    lon = req.location.longitude if req.location else None

    if lat is not None and (lat < -90.0 or lat > 90.0):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and +90 degrees.")

    if lon is not None and (lon < -180.0 or lon > 180.0):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and +180 degrees.")

    return await chat_service.handle_chat_request(
        message=req.message,
        location_name=loc_name,
        lat=lat,
        lon=lon,
        persona=req.persona,
        language=req.language,
        conversation_id=req.conversation_id,
        db_session=db
    )
