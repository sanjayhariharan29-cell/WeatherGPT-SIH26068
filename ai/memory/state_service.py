"""Personal Weather AI Conversation State Service.

Orchestrates multi-turn state transitions, reference and temporal resolution,
activity identification, clarification triggering, and safety-critical context preservation.
Ensures that the LLM is never the source of truth, never invents facts,
and operates strictly within bounded context windows.
"""

import re
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from backend.config.logging import logger
from ai.memory.models import (
    ConversationState,
    ConversationTurn,
    ClarificationState,
    ResolvedQueryContext,
    TurnTypeEnum,
)
from ai.nlu import parse_query
from ai.models import IntentEnum


# Correction markers
CORRECTION_PATTERNS = [
    r"^(?:no|not|actually|i meant|i mean|rather than|instead of)\b",
    r"\b(?:no,\s*i meant|not\s+[a-z]+,\s*(?:i meant|actually))\b",
    r"(?:இல்லை|மாறாக|நான் சொன்னது)",
    r"(?:नहीं|मेरा मतलब|बल्कि)",
]

# Ambiguous reference pronouns
LOCATION_REFERENCE_PATTERNS = [
    r"\bthere\b",
    r"\bthat place\b",
    r"\bsame place\b",
    r"\bsame location\b",
    r"\bin that city\b",
    r"\bthere too\b",
    r"அங்கே",
    r"அங்க",
    r"அங்கு",
    r"वहाँ",
    r"वहां",
    r"उसी जगह",
]

# Time keywords
TIME_OF_DAY_KEYWORDS = {
    "morning": "morning",
    "afternoon": "afternoon",
    "evening": "evening",
    "night": "night",
    "noon": "afternoon",
    "காலை": "morning",
    "மதியம்": "afternoon",
    "மாலை": "evening",
    "இரவு": "night",
    "सुबह": "morning",
    "दोपहर": "afternoon",
    "शाम": "evening",
    "रात": "night",
}

# Meteorological domain activities
ACTIVITY_PATTERNS = {
    "commute": [
        "commute", "travel", "office", "college", "school", "leave for work",
        "reach home", "drive", "driving", "transit", "umbrella", "ride", "bus"
    ],
    "farming": [
        "spray", "spraying", "fertilizer", "pesticide", "harvest", "harvesting",
        "sow", "sowing", "irrigation", "irrigate", "crop", "crops", "field", "farm"
    ],
    "fishing": [
        "fish", "fishing", "boat", "sea", "ocean", "coastal", "marine", "deep sea", "nets"
    ],
    "outdoor_event": [
        "cricket", "match", "wedding", "outdoor", "picnic", "party", "jogging", "walk", "play", "running"
    ],
}


class ConversationStateService:
    """Thread-safe conversation state manager for Personal Weather AI."""

    def __init__(self, ttl_seconds: int = 1800, max_turns: int = 10):
        self.ttl_seconds = ttl_seconds
        self.max_turns = max_turns
        self._states: Dict[str, ConversationState] = {}
        self._lock = threading.RLock()

    def get_state(self, conversation_id: str, user_id: Optional[str] = None) -> ConversationState:
        """Retrieves active conversation state, or creates a new one if missing or expired."""
        with self._lock:
            now = datetime.now(timezone.utc)
            if conversation_id in self._states:
                state = self._states[conversation_id]
                if state.is_expired(now):
                    logger.info("Conversation state %s expired (TTL=%ds). Resetting.", conversation_id, self.ttl_seconds)
                    del self._states[conversation_id]
                else:
                    if user_id and not state.user_id:
                        state.user_id = user_id
                    return state

            new_state = ConversationState(
                conversation_id=conversation_id,
                user_id=user_id,
                ttl_seconds=self.ttl_seconds,
                created_at=now,
                updated_at=now
            )
            self._states[conversation_id] = new_state
            return new_state

    @classmethod
    def is_reset_query(cls, text: str) -> bool:
        """Detects whether user explicitly asks to start a new topic or clear context."""
        lower = text.strip().lower()
        reset_tokens = [
            "start over", "start a new topic", "new topic", "clear context", "clear",
            "reset conversation", "reset", "reset context", "forget previous", "start fresh",
            "புது தலைப்பு", "மீண்டும் தொடங்கு", "नए सिरे से", "नया विषय", "सब रीसेट करो"
        ]
        for token in reset_tokens:
            if token == lower or re.search(rf"\b{re.escape(token)}\b", lower):
                return True
        return False

    @classmethod
    def has_location_reference(cls, text: str) -> bool:
        lower = text.lower()
        for pat in LOCATION_REFERENCE_PATTERNS:
            if re.search(pat, lower, re.IGNORECASE):
                return True
        return False

    @classmethod
    def is_explicit_correction(cls, text: str) -> bool:
        lower = text.lower().strip()
        for pat in CORRECTION_PATTERNS:
            if re.search(pat, lower, re.IGNORECASE):
                return True
        return False

    @classmethod
    def extract_time_of_day(cls, text: str) -> Optional[str]:
        lower = text.lower()
        for kw, normalized in TIME_OF_DAY_KEYWORDS.items():
            if kw in lower:
                return normalized
        return None

    @classmethod
    def extract_activity(cls, text: str) -> Optional[str]:
        lower = text.lower()
        for act, keywords in ACTIVITY_PATTERNS.items():
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", lower):
                    return act
        return None

    def analyze_turn(
        self,
        message: str,
        current_state: ConversationState,
        explicit_location: Optional[str] = None,
        explicit_language: Optional[str] = None,
        explicit_persona: Optional[str] = None
    ) -> ResolvedQueryContext:
        """Analyzes conversational turn transition and resolves parameters deterministically."""
        clean_msg = message.strip()
        lower_msg = clean_msg.lower()
        inherited_fields: List[str] = []
        is_ambiguous = False
        ambiguity_reason: Optional[str] = None
        clarification = ClarificationState()

        # Parse NLU
        nlu = parse_query(clean_msg)

        # 0. Check explicit reset
        if self.is_reset_query(clean_msg):
            turn_type = TurnTypeEnum.NEW_QUESTION
            resolved_loc = explicit_location or nlu.entities.location or None
            resolved_date = nlu.entities.date
            resolved_time = nlu.entities.time or self.extract_time_of_day(clean_msg)
            resolved_act = self.extract_activity(clean_msg)
            return ResolvedQueryContext(
                original_message=clean_msg,
                resolved_message=clean_msg,
                resolved_location=resolved_loc or "Unspecified",
                resolved_date=resolved_date,
                resolved_time=resolved_time,
                resolved_persona=explicit_persona or current_state.persona or "general",
                resolved_language=explicit_language or current_state.preferred_language or "en",
                resolved_topic=getattr(nlu.entities, 'weather_variable', None) or getattr(nlu.entities, 'hazard', None),
                resolved_activity=resolved_act,
                turn_type=turn_type,
                context_summary="Context reset by user."
            )

        # 1. Detect Turn Type
        extracted_loc = nlu.entities.location
        extracted_date = nlu.entities.date
        extracted_time = nlu.entities.time or self.extract_time_of_day(clean_msg)
        extracted_act = self.extract_activity(clean_msg)

        has_loc_ref = self.has_location_reference(clean_msg)
        is_corr = self.is_explicit_correction(clean_msg)
        was_clarification_pending = bool(current_state.clarification_state and current_state.clarification_state.needed)

        turn_type = TurnTypeEnum.NEW_QUESTION

        if was_clarification_pending:
            turn_type = TurnTypeEnum.CLARIFICATION_RESPONSE
        elif is_corr:
            turn_type = TurnTypeEnum.EXPLICIT_CORRECTION
        elif has_loc_ref:
            turn_type = TurnTypeEnum.FOLLOW_UP
        elif current_state.turn_index == 0:
            turn_type = TurnTypeEnum.NEW_QUESTION
        elif extracted_loc and current_state.active_location and extracted_loc.lower() != current_state.active_location.lower():
            turn_type = TurnTypeEnum.TOPIC_CHANGE
        elif extracted_date or extracted_time or extracted_act or any(k in lower_msg for k in ["what about", "and ", "how about", "will it", "is it"]):
            turn_type = TurnTypeEnum.FOLLOW_UP
        elif current_state.active_location:
            turn_type = TurnTypeEnum.TOPIC_CONTINUATION

        # 2. Location Resolution & Clarification Detection
        resolved_location: Optional[str] = None

        if is_corr and extracted_loc:
            # Explicit correction overrides
            resolved_location = extracted_loc
        elif was_clarification_pending:
            # User answered clarification (e.g. provided location name)
            if extracted_loc:
                resolved_location = extracted_loc
            elif len(clean_msg.split()) <= 3 and not any(k in lower_msg for k in ["rain", "wind", "temp"]):
                # Short single word response like "Coimbatore" or "Chennai"
                resolved_location = clean_msg.title()
            elif explicit_location:
                resolved_location = explicit_location
            else:
                resolved_location = current_state.active_location
        elif explicit_location and explicit_location.lower() != "coimbatore":
            resolved_location = explicit_location
        elif extracted_loc:
            resolved_location = extracted_loc
        elif has_loc_ref:
            # Check for multiple recent locations (ambiguity)
            unique_recent = list(dict.fromkeys(current_state.recent_locations))
            if len(unique_recent) > 1 and not extracted_loc:
                is_ambiguous = True
                ambiguity_reason = f"Multiple locations discussed recently ({', '.join(unique_recent)}). Please specify which location you mean."
                clarification = ClarificationState(
                    needed=True,
                    field="location",
                    prompt=f"Which location did you mean: {' or '.join(unique_recent[:2])}?",
                    options=unique_recent[:3],
                    pending_query=clean_msg
                )
                turn_type = TurnTypeEnum.AMBIGUOUS_REQUEST
                resolved_location = unique_recent[-1]
            elif current_state.active_location:
                resolved_location = current_state.active_location
                inherited_fields.append("location")
            else:
                resolved_location = None
        elif current_state.active_location:
            # Follow-up inherits previous active location
            resolved_location = current_state.active_location
            inherited_fields.append("location")
        elif explicit_location:
            resolved_location = explicit_location
        else:
            resolved_location = None

        # Check for genuinely ambiguous weather query without location
        is_weather_inquiry = nlu.intent != IntentEnum.GREETING
        if not resolved_location and is_weather_inquiry:
            is_ambiguous = True
            ambiguity_reason = "No target location specified in query or active conversation context."
            turn_type = TurnTypeEnum.AMBIGUOUS_REQUEST
            clarification = ClarificationState(
                needed=True,
                field="location",
                prompt="Which district or city would you like the weather forecast for?",
                pending_query=clean_msg
            )
            resolved_location = "Unspecified"

        resolved_location = resolved_location or "Coimbatore"

        # 3. Temporal Resolution
        resolved_date = extracted_date or (current_state.active_date if turn_type in (TurnTypeEnum.FOLLOW_UP, TurnTypeEnum.TOPIC_CONTINUATION) else None)
        if not extracted_date and resolved_date:
            inherited_fields.append("date")

        resolved_time = extracted_time or (current_state.active_time if turn_type in (TurnTypeEnum.FOLLOW_UP, TurnTypeEnum.TOPIC_CONTINUATION) else None)
        if not extracted_time and resolved_time:
            inherited_fields.append("time")

        # 4. Activity Resolution
        resolved_activity = extracted_act or (current_state.active_activity if turn_type in (TurnTypeEnum.FOLLOW_UP, TurnTypeEnum.TOPIC_CONTINUATION) else None)
        if not extracted_act and resolved_activity:
            inherited_fields.append("activity")

        # 5. Persona & Language Resolution
        resolved_persona = explicit_persona or current_state.persona or "general"
        resolved_language = explicit_language or current_state.preferred_language or nlu.detected_language.value

        # 6. Build Disambiguated / Enriched Message
        resolved_message = clean_msg
        if has_loc_ref and resolved_location and resolved_location != "Unspecified":
            for pat in LOCATION_REFERENCE_PATTERNS:
                resolved_message = re.sub(pat, resolved_location, resolved_message, flags=re.IGNORECASE)

        # 7. Bounded Context Construction
        context_summary = current_state.to_bounded_context(max_turns=2)

        return ResolvedQueryContext(
            original_message=clean_msg,
            resolved_message=resolved_message,
            resolved_location=resolved_location,
            resolved_date=resolved_date,
            resolved_time=resolved_time,
            resolved_persona=resolved_persona,
            resolved_language=resolved_language,
            resolved_topic=getattr(nlu.entities, 'weather_variable', None) or getattr(nlu.entities, 'hazard', None),
            resolved_activity=resolved_activity,
            is_ambiguous=is_ambiguous,
            ambiguity_reason=ambiguity_reason,
            turn_type=turn_type,
            clarification=clarification,
            inherited_fields=inherited_fields,
            context_summary=context_summary
        )

    def update_state(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        resolved_ctx: ResolvedQueryContext,
        decision_context: Optional[Dict[str, Any]] = None,
        safety_alerts: Optional[List[Dict[str, Any]]] = None
    ) -> ConversationState:
        """Commits turn transition to persistent conversation state."""
        with self._lock:
            state = self.get_state(conversation_id)
            now = datetime.now(timezone.utc)
            state.updated_at = now
            state.turn_index += 1
            state.previous_user_question = user_message
            state.turn_type = resolved_ctx.turn_type

            # Update location
            if resolved_ctx.resolved_location and resolved_ctx.resolved_location != "Unspecified":
                state.active_location = resolved_ctx.resolved_location
                if not state.recent_locations or state.recent_locations[-1] != state.active_location:
                    state.recent_locations.append(state.active_location)
                    if len(state.recent_locations) > 5:
                        state.recent_locations = state.recent_locations[-5:]

            if resolved_ctx.resolved_date:
                state.active_date = resolved_ctx.resolved_date
            if resolved_ctx.resolved_time:
                state.active_time = resolved_ctx.resolved_time
            if resolved_ctx.resolved_activity:
                state.active_activity = resolved_ctx.resolved_activity
            if resolved_ctx.resolved_persona:
                state.persona = resolved_ctx.resolved_persona
            if resolved_ctx.resolved_language:
                state.preferred_language = resolved_ctx.resolved_language

            # Clarification state lifecycle
            if resolved_ctx.clarification and resolved_ctx.clarification.needed:
                state.clarification_state = resolved_ctx.clarification
            else:
                state.clarification_state = ClarificationState(needed=False)

            # Decision context
            if decision_context:
                state.previous_resolved_decision_context = decision_context

            # Safety-critical context preservation (preserve severe alerts across follow-ups)
            if safety_alerts and len(safety_alerts) > 0:
                highest_alert = safety_alerts[0]
                sev = highest_alert.get("severity", "medium").upper()
                state.safety_critical_context = {
                    "has_active_warning": True,
                    "warning_title": highest_alert.get("title", "Official Weather Warning"),
                    "severity": sev,
                    "area": highest_alert.get("area", state.active_location),
                    "instructions": highest_alert.get("instructions", ""),
                    "timestamp": now.isoformat()
                }
            elif resolved_ctx.turn_type == TurnTypeEnum.TOPIC_CHANGE:
                # If topic changed to a different location, reset previous location's safety context
                state.safety_critical_context = None

            # Append turns to history
            u_turn = ConversationTurn(
                role="user",
                message=user_message,
                location=state.active_location,
                language=state.preferred_language,
                timestamp=now
            )
            a_turn = ConversationTurn(
                role="assistant",
                message=assistant_message,
                location=state.active_location,
                language=state.preferred_language,
                timestamp=now
            )
            state.turns.append(u_turn)
            state.turns.append(a_turn)
            if len(state.turns) > self.max_turns:
                state.turns = state.turns[-self.max_turns:]

            self._states[conversation_id] = state
            return state

    def reset_state(self, conversation_id: str) -> None:
        """Explicitly purges conversation state."""
        with self._lock:
            if conversation_id in self._states:
                del self._states[conversation_id]


# Singleton default state service instance
state_service = ConversationStateService()
