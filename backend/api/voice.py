from fastapi import APIRouter, UploadFile, File, Form, Depends
from typing import Optional
from backend.api.chat import chat_endpoint, ChatRequest, LocationPayload
from sqlalchemy.orm import Session
from backend.db.session import get_db

router = APIRouter(prefix="/voice", tags=["Voice Interaction"])

@router.post("/query")
async def voice_query(
    audio: Optional[UploadFile] = File(None),
    transcript: Optional[str] = Form(None),
    language: str = Form("ta"),
    persona: str = Form("student"),
    location_name: str = Form("Coimbatore"),
    db: Session = Depends(get_db)
):
    """Voice query processing endpoint (Tamil / Tanglish / English)."""
    text_query = transcript if transcript else "Naalaiku morning college pogalama?"

    req = ChatRequest(
        message=text_query,
        language=language,
        persona=persona,
        location=LocationPayload(name=location_name)
    )

    chat_resp = await chat_endpoint(req, db)

    return {
        "transcript": text_query,
        "answer": chat_resp["answer"],
        "language": chat_resp["language"],
        "intent": chat_resp["intent"],
        "location": chat_resp["location"],
        "risk": chat_resp["risk"],
        "audio_url": "simulated_tts_audio.mp3"
    }
