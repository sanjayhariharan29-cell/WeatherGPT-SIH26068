"""Conversational Memory Data Models for WeatherGPT.

Defines schemas for ConversationTurn, ConversationContext, and ResolvedQueryContext.
Ensures clear separation between Session Context, User Preferences,
Conversational References, and Recent Chat History.
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class TurnTypeEnum(str, Enum):
    """Categorized conversational turn transition."""
    NEW_QUESTION = "new_question"
    FOLLOW_UP = "follow_up"
    TOPIC_CONTINUATION = "topic_continuation"
    TOPIC_CHANGE = "topic_change"
    EXPLICIT_CORRECTION = "explicit_correction"
    CLARIFICATION_RESPONSE = "clarification_response"
    AMBIGUOUS_REQUEST = "ambiguous_request"


class ClarificationState(BaseModel):
    """State tracking for required conversational clarifications."""
    needed: bool = False
    missing_type: Optional[str] = None          # e.g. "insufficient_marine_area", "missing_location"
    field: Optional[str] = None                 # e.g. "location", "date", "marine_area"
    prompt: Optional[str] = None                # e.g. "Which area are you planning to fish in?"
    options: List[str] = Field(default_factory=list) # e.g. ["Chennai", "Coimbatore"]
    pending_query: Optional[str] = None        # original user query needing disambiguation
    pending_intent: Optional[str] = None       # original domain intent to resume (e.g. "fishing_decision")
    context_snapshot: Dict[str, Any] = Field(default_factory=dict) # captured context snapshot


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
    departure_time: Optional[str] = Field(default=None, description="User scheduled departure time")
    return_time: Optional[str] = Field(default=None, description="User scheduled return time")
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
        if self.departure_time or self.return_time:
            parts.append(f"Schedule: {self.departure_time or 'N/A'} - {self.return_time or 'N/A'}")
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
    resolved_departure_time: Optional[str] = Field(default=None, description="Resolved departure schedule time")
    resolved_return_time: Optional[str] = Field(default=None, description="Resolved return schedule time")
    resolved_destination: Optional[str] = Field(default=None, description="Resolved destination location or venue")
    resolved_transport_mode: Optional[str] = Field(default=None, description="Resolved transport mode (e.g. bike, car)")
    resolved_trip_phase: Optional[str] = Field(default=None, description="Resolved trip phase (departure, return, round_trip)")
    resolved_intent: Optional[str] = Field(default=None, description="Resolved intent string")
    resolved_persona: str = Field(default="general", description="Resolved persona")
    resolved_language: str = Field(default="en", description="Resolved target language")
    resolved_topic: Optional[str] = Field(default=None, description="Resolved meteorological topic")
    resolved_activity: Optional[str] = Field(default=None, description="Resolved domain activity")
    is_ambiguous: bool = Field(default=False, description="Whether reference could not be unambiguously resolved")
    ambiguity_reason: Optional[str] = Field(default=None, description="Explanation of reference ambiguity")
    turn_type: TurnTypeEnum = Field(default=TurnTypeEnum.NEW_QUESTION, description="Classified turn transition")
    clarification: ClarificationState = Field(default_factory=ClarificationState)
    inherited_fields: List[str] = Field(default_factory=list, description="Fields inherited from memory")
    context_summary: str = Field(default="", description="Structured summary string for LLM grounding")


class ConversationState(BaseModel):
    """Personal Weather AI Persistent State Model.

    Houses deterministic, authoritative conversational state across multi-turn interactions.
    Acts as the grounding anchor so the LLM never fabricates context or safety boundaries.
    """
    conversation_id: str = Field(description="Unique conversation identifier")
    session_id: Optional[str] = Field(default=None, description="Optional client session identifier")
    user_id: Optional[str] = Field(default=None, description="Authenticated user identifier")
    turn_index: int = Field(default=0, description="Sequential turn count")
    current_intent: Optional[str] = Field(default=None, description="Currently classified intent")
    turn_type: TurnTypeEnum = Field(default=TurnTypeEnum.NEW_QUESTION, description="Categorized turn transition")

    # Active Entities & Parameters
    active_entities: Dict[str, Any] = Field(default_factory=dict, description="Active meteorological & spatial entities")
    active_location: Optional[str] = Field(default=None, description="Resolved active primary location")
    active_destination: Optional[str] = Field(default=None, description="Resolved active destination (e.g. college, office)")
    active_latitude: Optional[float] = Field(default=None)
    active_longitude: Optional[float] = Field(default=None)
    active_time: Optional[str] = Field(default=None, description="Active time of day or clock time (e.g. 5:00 PM)")
    active_departure_time: Optional[str] = Field(default=None, description="Known or active departure time")
    active_return_time: Optional[str] = Field(default=None, description="Known or active return time")
    active_date: Optional[str] = Field(default=None, description="Active calendar date or relative date (today, tomorrow)")
    active_activity: Optional[str] = Field(default=None, description="Active domain activity (commute, farming, fishing)")
    active_transport_mode: Optional[str] = Field(default=None, description="Active transport mode (bike, car, walk)")
    active_trip_phase: Optional[str] = Field(default=None, description="Active trip phase (departure, return, round_trip)")
    active_topic: Optional[str] = Field(default=None, description="Active meteorological topic (rain, temperature, safety)")
    active_vehicle_or_item: Optional[str] = Field(default=None, description="Active vehicle or item (bike, umbrella)")
    user_schedule: Dict[str, str] = Field(
        default_factory=lambda: {
            "college_departure": "08:30",
            "college_return": "17:00",
            "office_departure": "09:00",
            "office_return": "18:00",
            "commute_departure": "09:00",
            "commute_return": "18:00",
            "travel_departure": "09:00",
            "travel_return": "18:00"
        },
        description="Known or preferred user schedule anchors"
    )

    # Historical Tracking
    previous_user_question: Optional[str] = Field(default=None, description="Exact text of previous user query")
    previous_resolved_decision_context: Optional[Dict[str, Any]] = Field(default=None, description="Decision summary from previous turn")
    previous_decision: Optional[str] = Field(default=None, description="Concise summary of previous decision verdict/action")
    unresolved_references: List[str] = Field(default_factory=list, description="Unresolved pronouns or vague terms")

    # Clarification State
    clarification_state: ClarificationState = Field(default_factory=ClarificationState)

    # User Profile & Context IDs
    preferred_language: str = Field(default="en", description="Target language preference")
    persona: str = Field(default="general", description="Target user persona")
    user_preferences: Dict[str, Any] = Field(default_factory=dict, description="Stable user preferences surviving across sessions")
    relevant_user_context_ids: List[str] = Field(default_factory=list, description="Context tags, e.g. saved locations, home district")

    # Safety Critical Context Preservation (Preserves severe alerts across turns)
    safety_critical_context: Optional[Dict[str, Any]] = Field(default=None, description="Persists severe weather warnings across follow-ups")

    # Spatial disambiguation tracking
    recent_locations: List[str] = Field(default_factory=list, description="Recent distinct locations discussed (bounded to 5)")

    # Bounded Turn History (Max 10)
    turns: List[ConversationTurn] = Field(default_factory=list, description="Bounded chronological turn history")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = Field(default=1800, description="Context TTL in seconds (default 30 mins)")

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Checks whether the conversational state has exceeded its TTL."""
        now = current_time or datetime.now(timezone.utc)
        elapsed = (now - self.updated_at).total_seconds()
        return elapsed > self.ttl_seconds

    def to_bounded_context(self, max_turns: int = 2) -> str:
        """Constructs a compact, strictly bounded context representation for LLM grounding.

        Prevents prompt bloat and historical hallucination by injecting only:
        - Active location, destination, time, date, trip phase, transport, activity, topic
        - Previous decision verdict (if available)
        - Pending clarification state (if any)
        - Active safety-critical alert (if any)
        - Last 1-2 turn questions and answers (truncated)
        """
        parts = []
        if self.active_location:
            parts.append(f"Active Location: {self.active_location}")
        if self.active_destination:
            parts.append(f"Destination: {self.active_destination}")
        if self.active_date:
            parts.append(f"Target Date: {self.active_date}")
        if self.active_time:
            parts.append(f"Target Time: {self.active_time}")
        if self.active_trip_phase:
            parts.append(f"Trip Phase: {self.active_trip_phase}")
        if self.active_transport_mode:
            parts.append(f"Transport: {self.active_transport_mode}")
        if self.active_activity:
            parts.append(f"Activity: {self.active_activity}")
        if self.active_topic:
            parts.append(f"Weather Topic: {self.active_topic}")
        if self.persona and self.persona != "general":
            parts.append(f"User Persona: {self.persona}")
        if self.preferred_language and self.preferred_language != "en":
            parts.append(f"Language: {self.preferred_language}")

        # Previous decision summary (without temporary weather facts)
        if self.previous_decision:
            parts.append(f"Previous Decision: {self.previous_decision}")
        elif self.previous_resolved_decision_context:
            dec_act = (
                self.previous_resolved_decision_context.get("action")
                or self.previous_resolved_decision_context.get("verdict")
                or self.previous_resolved_decision_context.get("summary")
            )
            if dec_act:
                parts.append(f"Previous Decision: {dec_act}")

        # Clarification state
        if self.clarification_state and self.clarification_state.needed and self.clarification_state.field:
            parts.append(f"Pending Clarification: {self.clarification_state.field}")

        # Safety critical persistence
        if self.safety_critical_context and self.safety_critical_context.get("has_active_warning"):
            w_title = self.safety_critical_context.get("warning_title", "Severe Weather Warning")
            w_sev = self.safety_critical_context.get("severity", "ALERT")
            parts.append(f"ACTIVE OFFICIAL WARNING: [{w_sev}] {w_title}")

        # Bounded historical turns (last max_turns only)
        if self.turns:
            recent_turns = self.turns[-(max_turns * 2):]
            turn_lines = []
            for t in recent_turns:
                msg = t.message[:100].replace("\n", " ")
                turn_lines.append(f"{t.role.capitalize()}: {msg}")
            if turn_lines:
                parts.append("Recent Context: " + " | ".join(turn_lines))

        return " | ".join(parts) if parts else "No prior context"

    def to_dict(self) -> Dict[str, Any]:
        """Dictionary serialization for API responses."""
        return self.model_dump()


