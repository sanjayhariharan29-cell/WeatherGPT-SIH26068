"""FastAPI Voice Interaction Route.

Provides voice query endpoint supporting speech uploads (WAV, MP3, OGG, WebM)
and text transcripts across English, Tamil, Hindi, Tanglish, and Hinglish.
Delegates to VoiceAIService while preserving Person 2's API contract.
"""

from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.config.logging import logger
from backend.db.session import get_db
from ai.voice import (
    VoiceAIService,
    VoiceError,
    AudioValidationError,
    EmptyAudioError,
    STTError,
    STTTimeoutError,
    STTNoSpeechError
)

router = APIRouter(prefix="/voice", tags=["Voice Interaction"])

# Default singleton service for the route
_voice_service = VoiceAIService()


@router.post("/query")
async def voice_query(
    audio: Optional[UploadFile] = File(None),
    transcript: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    persona: str = Form("student"),
    location_name: str = Form("Coimbatore"),
    db: Session = Depends(get_db)
):
    """Processes voice audio or speech transcripts through the AI intelligence pipeline."""
    audio_bytes: Optional[bytes] = None
    filename: Optional[str] = None
    content_type: Optional[str] = None

    if audio is not None:
        try:
            audio_bytes = await audio.read()
            filename = audio.filename
            content_type = audio.content_type
        except Exception as read_err:
            logger.error("Failed to read uploaded audio stream: %s", read_err)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to read uploaded audio stream."
            )

    try:
        voice_result = await _voice_service.process_voice_query(
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
            transcript_override=transcript,
            language=language,
            persona=persona,
            location_name=location_name,
            db=db
        )
        return voice_result.model_dump()
    except (EmptyAudioError, AudioValidationError) as val_err:
        logger.warning("Voice audio validation rejected request: %s", val_err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except (STTTimeoutError, STTNoSpeechError, STTError) as stt_err:
        logger.warning("Voice speech recognition failed: %s", stt_err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sorry, I couldn't understand the voice input. {stt_err}"
        )
    except Exception as exc:
        logger.error("Unexpected error in voice query pipeline: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the voice query."
        )
