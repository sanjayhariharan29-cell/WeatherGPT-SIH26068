"""Chat API Request and Response Schemas.

Aligned with docs/08_Api_Contracts.md and Person 1 AI pipeline requirements.
Hardened with input validation rules, bounds checking, and request correlation IDs.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class LocationPayload(BaseModel):
    """Location coordinate and name payload for chat queries."""
    name: Optional[str] = Field(default="Coimbatore", max_length=100, description="Resolved city or locality name")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Latitude in degrees (-90 to 90)")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Longitude in degrees (-180 to 180)")


class ChatRequest(BaseModel):
    """Conversational weather query request payload."""
    message: str = Field(..., min_length=1, max_length=1000, description="User question or voice transcript (1-1000 chars)")
    language: Optional[str] = Field(default="ta", description="Requested language code: ta, en, hi, tanglish, hinglish")
    persona: Optional[str] = Field(default="student", description="Target persona: student, farmer, fisherman, commuter, general")
    location: Optional[LocationPayload] = Field(default=None, description="Optional location payload")
    conversation_id: Optional[str] = Field(default=None, description="Optional conversation UUID for multi-turn history")

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty or only whitespace.")
        if len(cleaned) > 1000:
            raise ValueError("Message length exceeds maximum limit of 1000 characters.")
        return cleaned

    @field_validator("language")
    @classmethod
    def validate_language_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return "ta"
        allowed = {"ta", "en", "hi", "tanglish", "hinglish", "tamil", "english", "hindi"}
        if v.lower() not in allowed:
            raise ValueError(f"Unsupported language code '{v}'. Supported: ta, en, hi, tanglish, hinglish.")
        return v.lower()

    @field_validator("persona")
    @classmethod
    def validate_persona_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return "student"
        allowed = {"student", "farmer", "fisherman", "commuter", "general", "tourist", "event_planner"}
        if v.lower() not in allowed:
            raise ValueError(f"Unsupported persona '{v}'. Supported: student, farmer, fisherman, commuter, general.")
        return v.lower()


class RiskSummary(BaseModel):
    """Summary of meteorological risk level and source consistency."""
    level: str = Field(description="Risk level: low, medium, high, extreme")
    consistency: str = Field(description="Multi-source agreement: high, moderate, low, single_source")
    consistency_score: Optional[float] = Field(default=None, description="Composite consistency score 0.0-1.0")


class ValidationSummary(BaseModel):
    """Summary of anti-hallucination and safety validation checks."""
    passed: bool = Field(description="Whether AI response passed all safety validations")
    status: str = Field(description="Validation status: PASS, PASS_WITH_WARNING, REJECT, FALLBACK")
    violations: List[str] = Field(default_factory=list, description="Grounding or safety violations detected")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings detected")
    checked_fields: Optional[List[str]] = Field(default_factory=list, description="Metadata on verified fields")
    issues: Optional[List[Dict[str, Any]]] = Field(default=None, description="Structured violation records")


class ChatResponse(BaseModel):
    """Normalized Conversational AI API Response Contract."""
    request_id: Optional[str] = Field(default=None, description="Unique correlation UUID")
    conversation_id: str = Field(description="Session or conversation UUID")
    answer: str = Field(description="Grounded natural language response")
    tts_text: Optional[str] = Field(default=None, description="Clean speech-optimized text for TTS voice synthesis")
    language: str = Field(description="Detected or resolved response language")
    intent: str = Field(description="Classified NLU intent")
    location: str = Field(description="Resolved location name")
    persona: Optional[str] = Field(default=None, description="Resolved user persona")
    risk: RiskSummary = Field(description="Assessed meteorological risk and agreement")
    weather_summary: Optional[Dict[str, Any]] = Field(default=None, description="Live weather telemetry summary")
    forecast_count: Optional[int] = Field(default=0, description="Count of forecast items included")
    alerts: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Active official alerts")
    source: str = Field(description="Meteorological provider attribution")
    data_quality: Optional[Dict[str, Any]] = Field(default=None, description="Data availability and quality status")
    data_timestamp: str = Field(description="Observation timestamp (ISO 8601 UTC)")
    validation: Optional[ValidationSummary] = Field(default=None, description="AI safety validation report")
    decision_trace: Optional[Dict[str, Any]] = Field(default=None, description="Structured DecisionTrace explaining system factors and recommendation basis")
    why_this_answer: Optional[Dict[str, Any]] = Field(default=None, description="Structured explainability path for evidence, freshness, and sources")
    personal_decision: Optional[Dict[str, Any]] = Field(default=None, description="Deterministic personal decision result")

