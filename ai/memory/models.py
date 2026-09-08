"""Conversational Memory Data Models for WeatherGPT.

Defines schemas for ConversationTurn, ConversationContext, and ResolvedQueryContext.
Ensures clear separation between Session Context, User Preferences,
Conversational References, and Recent Chat History.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    """Represents a single user or assistant exchange in conversation history."""
    role: str = Field(description="'user' or 'assistant'")
    message: str = Field(description="Raw message text")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    intent: Optional[str] = Field(default=None, description="Classified NLU intent")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted meteorological and spatial entities")
    language: Optional[str] = Field(default=None, description="Language code e.g. ta, hi, en")
    location: Optional[str] = Field(default=None, description="Associated location name if any")
    risk_level: Optional[str] = Field(default=None, description="Assessed risk level if applicable")


class ConversationContext(BaseModel):
    """Structured short-term conversational context."""
    conversation_id: str = Field(description="Unique conversation identifier")
    location: Optional[str] = Field(default=None, description="Most recent primary location context")
    latitude: Optional[float] = Field(default=None, description="Latitude of location context")
    longitude: Optional[float] = Field(default=None, description="Longitude of location context")
    language: Optional[str] = Field(default=None, description="User's active language preference")
    persona: Optional[str] = Field(default=None, description="Active user persona e.g. farmer, student, fisherman")
    date_context: Optional[str] = Field(default=None, description="Active temporal date context e.g. tomorrow, today")
    time_context: Optional[str] = Field(default=None, description="Active temporal time context e.g. evening, morning")
    last_intent: Optional[str] = Field(default=None, description="Most recent user intent")
    active_topic: Optional[str] = Field(default=None, description="Active meteorological topic e.g. rain, wind, temperature")
    recent_entities: Dict[str, Any] = Field(default_factory=dict, description="Recent entities merged across turns")
    recent_locations: List[str] = Field(default_factory=list, description="Recent distinct locations discussed (for ambiguity checks)")
    turns: List[ConversationTurn] = Field(default_factory=list, description="Bounded chronological turn history")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = Field(default=1800, description="Context TTL in seconds (default 30 mins)")

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Checks whether the conversational context has exceeded its TTL."""
        now = current_time or datetime.now(timezone.utc)
        elapsed = (now - self.updated_at).total_seconds()
        return elapsed > self.ttl_seconds

    def to_summary(self) -> str:
        """Produces a compact structured summary for LLM grounding without leaking stale weather data."""
        parts = []
        if self.location:
            parts.append(f"Location: {self.location}")
        if self.date_context:
            parts.append(f"Date: {self.date_context}")
        if self.time_context:
            parts.append(f"Time: {self.time_context}")
        if self.active_topic:
            parts.append(f"Topic: {self.active_topic}")
        if self.persona:
            parts.append(f"Persona: {self.persona}")
        if self.language:
            parts.append(f"Language: {self.language}")
        return " | ".join(parts) if parts else "No prior context"


class ResolvedQueryContext(BaseModel):
    """Result of combining incoming user query with conversational memory context."""
    original_message: str = Field(description="Raw user query")
    resolved_message: str = Field(description="Disambiguated or enriched message query")
    resolved_location: str = Field(default="Coimbatore", description="Resolved location name")
    resolved_date: Optional[str] = Field(default=None, description="Resolved date context")
    resolved_time: Optional[str] = Field(default=None, description="Resolved time-of-day context")
    resolved_persona: str = Field(default="general", description="Resolved persona")
    resolved_language: str = Field(default="en", description="Resolved target language")
    resolved_topic: Optional[str] = Field(default=None, description="Resolved meteorological topic")
    is_ambiguous: bool = Field(default=False, description="Whether reference could not be unambiguously resolved")
    ambiguity_reason: Optional[str] = Field(default=None, description="Explanation of reference ambiguity")
    inherited_fields: List[str] = Field(default_factory=list, description="Fields inherited from memory")
    context_summary: str = Field(default="", description="Structured summary string for LLM grounding")
