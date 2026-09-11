"""Voice AI Data Models for WeatherGPT.

Strictly defines schemas for Audio Validation, Speech-to-Text (STT),
Text-to-Speech (TTS), and Multilingual Voice Responses.
Aligned with docs/08_Api_Contracts.md and Person 1 Voice Architecture.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class AudioValidationResult(BaseModel):
    """Result of audio stream inspection and safety verification."""
    is_valid: bool = Field(description="Whether audio passed size, format, and corruption checks")
    detected_format: Optional[str] = Field(default=None, description="Inferred audio container format e.g. wav, mp3")
    size_bytes: int = Field(default=0, description="Total audio stream size in bytes")
    error_code: Optional[str] = Field(default=None, description="Error code if validation failed")
    error_message: Optional[str] = Field(default=None, description="Descriptive validation failure message")


class STTResult(BaseModel):
    """Normalized output from Speech-to-Text transcription."""
    transcript: str = Field(description="Raw transcribed user speech query")
    detected_language: str = Field(default="en", description="Detected language code e.g. en, ta, hi")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Transcription confidence score")
    duration_sec: float = Field(default=0.0, description="Estimated or reported audio duration in seconds")
    provider: str = Field(default="mock", description="STT provider attribution")


class TTSResult(BaseModel):
    """Normalized output from Text-to-Speech audio synthesis."""
    audio_bytes: Optional[bytes] = Field(default=None, description="Raw audio bytes (if binary synthesis)")
    audio_url: Optional[str] = Field(default=None, description="Accessible URL or streaming path for synthesized audio")
    audio_format: str = Field(default="mp3", description="Synthesized audio format e.g. mp3, wav")
    duration_sec: float = Field(default=0.0, description="Duration of synthesized speech in seconds")
    success: bool = Field(default=True, description="Whether speech synthesis succeeded")
    provider: str = Field(default="mock", description="TTS provider attribution")
    error_message: Optional[str] = Field(default=None, description="Error description if TTS synthesis failed")


class VoiceResponse(BaseModel):
    """Complete voice query processing result conforming to API contract."""
    transcript: str = Field(description="Recognized voice query transcript")
    answer: str = Field(description="Validated natural language answer from AI engine")
    language: str = Field(description="Resolved response language e.g. ta, hi, en")
    input_language: str = Field(description="Language detected from user voice query")
    intent: str = Field(description="Classified NLU intent")
    location: str = Field(description="Resolved query location")
    persona: str = Field(description="Resolved persona advisory context")
    risk: Dict[str, Any] = Field(description="Assessed meteorological risk and consistency")
    audio_available: bool = Field(default=True, description="Whether TTS audio synthesis succeeded")
    audio_url: Optional[str] = Field(default="simulated_tts_audio.mp3", description="Generated audio output reference")
    validation_status: str = Field(default="PASS", description="Validation status from Phase 9 guard")
    data_timestamp: str = Field(description="Observation data timestamp")
    conversation_id: Optional[str] = Field(default=None, description="Conversation session UUID for conversational state continuity")
    why_this_answer: Optional[Dict[str, Any]] = Field(default=None, description="Structured explainability path for evidence, freshness, and sources")
    personal_decision: Optional[Dict[str, Any]] = Field(default=None, description="Deterministic personal decision result")
    decision_trace: Optional[Dict[str, Any]] = Field(default=None, description="Detailed decision factors and reasoning trace")
    clarification: Optional[Dict[str, Any]] = Field(default=None, description="Clarification state if more information needed")
