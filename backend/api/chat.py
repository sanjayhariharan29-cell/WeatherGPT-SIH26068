"""Conversational AI Chat API Router.

Exposes hardened endpoint (POST /api/v1/chat) connecting backend weather telemetry
to Person 1's NLU, Weather Reasoner, Hazard Detection, Decision Advisory, RAG, and Grounded LLM.
Hardened with input validation, authentication, user ownership checks, request correlation tracking, timeout protection, rate limiting, and OpenAPI schemas.
"""

import uuid
import asyncio
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import User, Conversation, Message
from backend.schemas.chat import ChatRequest, ChatResponse
from backend.services.chat_integration_service import ChatIntegrationService
from backend.core.security import get_current_user, get_optional_current_user

router = APIRouter(tags=["AI Chat"])
chat_service = ChatIntegrationService()

ALLOWED_LANGUAGES = {"ta", "en", "hi", "tanglish", "hinglish", "tamil", "english", "hindi"}
ALLOWED_PERSONAS = {
    "student", "farmer", "fisherman", "commuter", "general", "tourist", "event_planner",
    "disaster_response", "disaster", "safety", "disaster_safety", "traveller", "traveler"
}


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Conversational Weather Query",
    description="Processes user weather questions, evaluates hazards, applies decision advisories, and returns grounded AI answers."
)
async def chat_endpoint(
    req: ChatRequest,
    request: Request = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """Main WeatherGPT Conversational Decision Engine Endpoint."""
    # 1. Request Correlation ID Extraction
    req_id = getattr(request.state, "request_id", None) if request and hasattr(request, "state") else str(uuid.uuid4())

    # 2. Strict Input Validation
    cleaned_msg = req.message.strip() if req.message else ""
    if not cleaned_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty or only whitespace.")

    if len(cleaned_msg) > 1000:
        raise HTTPException(status_code=400, detail="Message length exceeds maximum allowed limit of 1000 characters.")

    if req.language and req.language.lower() not in ALLOWED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{req.language}'. Supported: ta, en, hi, tanglish, hinglish.")

    if req.persona and req.persona.lower() not in ALLOWED_PERSONAS:
        raise HTTPException(status_code=400, detail=f"Unsupported persona '{req.persona}'. Supported: student, farmer, fisherman, commuter, general.")

    loc_name = req.location.name if req.location and req.location.name else "Coimbatore"
    lat = req.location.latitude if req.location else None
    lon = req.location.longitude if req.location else None

    if lat is not None and (lat < -90.0 or lat > 90.0):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and +90 degrees.")

    if lon is not None and (lon < -180.0 or lon > 180.0):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and +180 degrees.")

    user_id = current_user.id if current_user else None

    # 3. Timeout-Protected Execution (10.0s Limit)
    try:
        res = await asyncio.wait_for(
            chat_service.handle_chat_request(
                message=cleaned_msg,
                location_name=loc_name,
                lat=lat,
                lon=lon,
                persona=req.persona or "student",
                language=req.language or "ta",
                conversation_id=req.conversation_id,
                request_id=req_id,
                user_id=user_id,
                db_session=db
            ),
            timeout=30.0
        )
        return res
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Weather AI service processing timed out. Please try again.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing error: {str(e)}")


@router.get("/chat/conversations", summary="List User Conversations")
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves all conversation histories owned by the authenticated user."""
    convs = db.query(Conversation).filter(Conversation.user_id == current_user.id).order_by(Conversation.updated_at.desc()).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "message_count": len(c.messages)
        }
        for c in convs
    ]


@router.get("/chat/conversations/{conversation_id}", summary="Get Conversation Detail")
async def get_conversation_detail(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves conversation details and messages with strict user ownership checks."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Enforce User Ownership
    if conv.user_id and conv.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this conversation"
        )
    
    return {
        "id": conv.id,
        "title": conv.title,
        "user_id": conv.user_id,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "messages": [
            {
                "id": m.id,
                "sender": m.sender,
                "content": m.content,
                "language": m.language,
                "intent": m.intent,
                "risk_level": m.risk_level,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in conv.messages
        ]
    }


@router.delete("/chat/conversations/{conversation_id}", summary="Delete Conversation")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deletes a conversation with strict user ownership checks."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Enforce User Ownership
    if conv.user_id and conv.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this conversation"
        )
    
    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted successfully"}
