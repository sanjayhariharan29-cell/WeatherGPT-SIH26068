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

# Ambiguous spatial reference pronouns
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

# Ambiguous temporal reference pronouns
TEMPORAL_THEN_PATTERNS = [
    r"\b(?:then|at\s+that\s+time|during\s+that\s+time|then\?)\b",
    r"அப்போது",
    r"அப்ப",
    r"तब",
    r"उस\s+समय",
]

# Pronoun "it" taking/carrying/riding references
PRONOUN_IT_PATTERNS = [
    r"\b(?:should\s+i\s+take\s+it|can\s+i\s+take\s+it|take\s+it|ride\s+it|bring\s+it|carry\s+it|use\s+it|need\s+it|take\s+it\?|ride\s+it\?)\b",
    r"அதை\s*(?:எடுக்கலாமா|பயன்படுத்தலாமா)",
    r"क्या\s+इसे\s+ले\s+जाना\s+चाहिए",
]

# Trip phase patterns (departure vs return)
TRIP_PHASE_PATTERNS = {
    "departure": [
        r"\bwhen\s+(?:i\s+)?leave\b",
        r"\bleave\s+for\b",
        r"\bleaving\b",
        r"\bdeparture\b",
        r"\bhead\s+out\b",
        r"\bstart\s+for\b",
        r"கிளம்பும்போது",
        r"போகும்போது",
        r"निकलते\s+समय",
        r"जाते\s+वक्त",
    ],
    "return": [
        r"\bwhen\s+(?:i\s+)?come\s*back\b",
        r"\bcoming\s*back\b",
        r"\bcome\s*back\b",
        r"\breturn\b",
        r"\breturn\s*trip\b",
        r"\breach\s*home\b",
        r"\bback\s*home\b",
        r"திரும்பி\s*வரும்போது",
        r"வாபஸ்\s*ஆதே",
        r"वापस\s*आते\s*समय",
        r"वापस\s*आते\s*वक्त",
    ]
}

# Transport mode patterns
TRANSPORT_PATTERNS = {
    "bike": [
        r"\bbike\b", r"\bmotorcycle\b", r"\bscooter\b", r"\btwo[\s-]wheeler\b", r"\bcycle\b",
        r"பைக்", r"இருசக்கர", r"बाइक", r"स्कूटर"
    ],
    "car": [
        r"\bcar\b", r"\bdrive\b", r"\bcab\b", r"\btaxi\b", r"கார்", r"कार", r"गाड़ी"
    ],
    "bus": [
        r"\bbus\b", r"பேருந்து", r"बस"
    ],
    "train": [
        r"\btrain\b", r"\bmetro\b", r"ரயில்", r"ट्रेन"
    ]
}

# Weekday tokens & mapping
WEEKDAY_PATTERNS = {
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
    "saturday": "Saturday",
    "sunday": "Sunday",
    "திங்கட்கிழமை": "Monday",
    "செவ்வாய்க்கிழமை": "Tuesday",
    "புதன்கிழமை": "Wednesday",
    "வியாழக்கிழமை": "Thursday",
    "வெள்ளிக்கிழமை": "Friday",
    "சனிக்கிழமை": "Saturday",
    "ஞாயிற்றுக்கிழமை": "Sunday",
    "velli": "Friday",
    "vellikkizhamai": "Friday",
    "शुक्रवार": "Friday",
    "shukrawar": "Friday",
    "somwar": "Monday",
    "mangalwar": "Tuesday",
    "budhwar": "Wednesday",
    "guruwar": "Thursday",
    "shaniwar": "Saturday",
    "raviwar": "Sunday",
}

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
    "college": [
        "college", "campus", "lecture", "exam", "கல்லூரி", "कॉलेज"
    ],
    "office": [
        "office", "work", "job", "workplace", "leave for work", "அலுவலகம்", "दफ्तर"
    ],
    "commute": [
        "commute", "travel", "school",
        "reach home", "drive", "driving", "transit", "umbrella", "ride", "bus"
    ],
    "farming": [
        "spray", "spraying", "fertilizer", "pesticide", "harvest", "harvesting",
        "sow", "sowing", "irrigation", "irrigate", "crop", "crops", "field", "farm", "விவசாயம்", "பயிர்", "खेती"
    ],
    "fishing": [
        "fish", "fishing", "boat", "sea", "ocean", "coastal", "marine", "deep sea", "nets", "மீன்பிடி", "கடல்", "मछली"
    ],
    "outdoor_event": [
        "cricket", "match", "wedding", "outdoor", "picnic", "party", "jogging", "walk", "play", "running", "விளையாட", "खेल"
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

    @classmethod
    def extract_weekday(cls, text: str) -> Optional[str]:
        lower = text.lower()
        for pat, day_name in WEEKDAY_PATTERNS.items():
            if re.search(rf"\b{re.escape(pat)}\b", lower):
                return day_name
        return None

    @classmethod
    def extract_trip_phase(cls, text: str) -> Optional[str]:
        lower = text.lower()
        for pat in TRIP_PHASE_PATTERNS["departure"]:
            if re.search(pat, lower):
                return "departure"
        for pat in TRIP_PHASE_PATTERNS["return"]:
            if re.search(pat, lower):
                return "return"
        return None

    @classmethod
    def extract_transport_mode(cls, text: str) -> Optional[str]:
        lower = text.lower()
        for mode, patterns in TRANSPORT_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, lower):
                    return mode
        return None

    @classmethod
    def extract_specific_clock_time(cls, text: str, trip_phase: Optional[str] = None) -> Optional[str]:
        lower = text.lower()
        time_match = re.search(r"\b(?:at|by|around|about)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lower)
        if time_match:
            h_str = time_match.group(1)
            h = int(h_str)
            m = time_match.group(2) or "00"
            ampm = (time_match.group(3) or "").lower()
            if ampm == "pm":
                return f"{h if h == 12 else h+12:02d}:{m}"
            elif ampm == "am":
                return f"{0 if h == 12 else h:02d}:{m}"
            elif trip_phase == "return" or any(k in lower for k in ["evening", "back", "night", "coming back", "return", "at 5", "about 5", "5?"]):
                if h < 12 and h in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
                    return f"{h+12:02d}:{m}"
                return f"{h:02d}:{m}"
            elif h in [4, 5, 6, 7] and not any(k in lower for k in ["morning", "early"]):
                return f"{h+12:02d}:{m}"
            elif h < 24:
                return f"{h:02d}:{m}"
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

        # 1. Linguistic & Dimension Extraction
        extracted_loc = nlu.entities.location
        extracted_date = self.extract_weekday(clean_msg) or nlu.entities.date
        extracted_trip_phase = self.extract_trip_phase(clean_msg)
        extracted_transport = self.extract_transport_mode(clean_msg) or getattr(nlu.entities, 'transport_mode', None)
        extracted_act = self.extract_activity(clean_msg) or getattr(nlu.entities, 'activity', None)

        # Specific clock time (e.g. "at 5" -> "17:00")
        extracted_time = (
            self.extract_specific_clock_time(clean_msg, trip_phase=extracted_trip_phase or current_state.active_trip_phase)
            or self.extract_time_of_day(clean_msg)
            or nlu.entities.time
        )

        has_loc_ref = self.has_location_reference(clean_msg)
        has_temporal_then = any(re.search(p, lower_msg) for p in TEMPORAL_THEN_PATTERNS)
        has_pronoun_it = any(re.search(p, lower_msg) for p in PRONOUN_IT_PATTERNS)
        is_safety_inquiry = bool(re.search(r"\b(?:is\s+it\s+safe|safe\s+to\s+go|is\s+it\s+safe\?|safe\?|safety)\b", lower_msg))
        is_corr = self.is_explicit_correction(clean_msg)
        was_clarification_pending = bool(current_state.clarification_state and current_state.clarification_state.needed)

        # 2. Turn Type Classification
        turn_type = TurnTypeEnum.NEW_QUESTION
        if was_clarification_pending:
            turn_type = TurnTypeEnum.CLARIFICATION_RESPONSE
        elif is_corr:
            turn_type = TurnTypeEnum.EXPLICIT_CORRECTION
        elif current_state.turn_index == 0:
            turn_type = TurnTypeEnum.NEW_QUESTION
        elif extracted_loc and current_state.active_location and extracted_loc.lower() != current_state.active_location.lower():
            # If user mentions destination or origin in travel context, keep follow-up
            if any(k in lower_msg for k in ["from", "to", "reach", "destination"]):
                turn_type = TurnTypeEnum.FOLLOW_UP
            else:
                turn_type = TurnTypeEnum.TOPIC_CHANGE
        elif (
            has_loc_ref
            or has_temporal_then
            or has_pronoun_it
            or is_safety_inquiry
            or extracted_date
            or extracted_time
            or extracted_act
            or extracted_transport
            or extracted_trip_phase
            or any(k in lower_msg for k in ["what about", "and ", "how about", "will it", "is it", "should i", "can i"])
        ):
            turn_type = TurnTypeEnum.FOLLOW_UP
        elif current_state.active_location:
            turn_type = TurnTypeEnum.TOPIC_CONTINUATION

        # 3. Location Resolution & Ambiguity Handling
        resolved_location: Optional[str] = None
        if is_corr and extracted_loc:
            resolved_location = extracted_loc
        elif was_clarification_pending:
            if extracted_loc:
                resolved_location = extracted_loc
            elif len(clean_msg.split()) <= 3 and not any(k in lower_msg for k in ["rain", "wind", "temp"]):
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
            unique_recent = list(dict.fromkeys(current_state.recent_locations))
            if len(unique_recent) > 1 and not current_state.active_location:
                is_ambiguous = True
                ambiguity_reason = "Multiple locations discussed recently without a single active anchor."
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
                is_ambiguous = True
                ambiguity_reason = "Spatial reference used without prior location in conversation state."
                clarification = ClarificationState(
                    needed=True,
                    field="location",
                    prompt="Which district or city would you like the weather forecast for?",
                    pending_query=clean_msg
                )
                turn_type = TurnTypeEnum.AMBIGUOUS_REQUEST
                resolved_location = "Unspecified"
        elif current_state.active_location:
            resolved_location = current_state.active_location
            inherited_fields.append("location")
        elif explicit_location:
            resolved_location = explicit_location
        else:
            resolved_location = None

        if not resolved_location and nlu.intent != IntentEnum.GREETING:
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

        # 4. Date Resolution (Isolated dimension change)
        resolved_date = extracted_date
        if not resolved_date and turn_type in (TurnTypeEnum.FOLLOW_UP, TurnTypeEnum.TOPIC_CONTINUATION):
            if current_state.active_date:
                resolved_date = current_state.active_date
                inherited_fields.append("date")

        # 5. Activity Resolution (Preserves active activity unless explicitly updated)
        resolved_activity = extracted_act
        if turn_type in (TurnTypeEnum.FOLLOW_UP, TurnTypeEnum.TOPIC_CONTINUATION):
            if current_state.active_activity and (not resolved_activity or (resolved_activity in ["travel", "commute", "bike travel", "bike"] and current_state.active_activity in ["office", "college"])):
                resolved_activity = current_state.active_activity
                inherited_fields.append("activity")
        elif not resolved_activity and current_state.active_activity:
            resolved_activity = current_state.active_activity
            inherited_fields.append("activity")

        # Destination resolution
        resolved_destination = current_state.active_destination
        if resolved_activity == "college":
            resolved_destination = "college"
        elif resolved_activity == "office":
            resolved_destination = "office"

        # 6. Trip Phase Resolution
        resolved_trip_phase = extracted_trip_phase
        if not resolved_trip_phase and turn_type in (TurnTypeEnum.FOLLOW_UP, TurnTypeEnum.TOPIC_CONTINUATION):
            if current_state.active_trip_phase:
                resolved_trip_phase = current_state.active_trip_phase
                inherited_fields.append("trip_phase")

        # 7. Time & Schedule Anchor Resolution
        resolved_time: Optional[str] = None
        resolved_departure_time = current_state.active_departure_time
        resolved_return_time = current_state.active_return_time

        if resolved_trip_phase == "departure":
            if extracted_time:
                resolved_departure_time = extracted_time
                resolved_time = extracted_time
            elif current_state.active_departure_time:
                resolved_departure_time = current_state.active_departure_time
                resolved_time = current_state.active_departure_time
                inherited_fields.append("departure_time")
            else:
                # User's known/usual college or commute departure time
                sched_key = f"{resolved_activity}_departure" if resolved_activity else "college_departure"
                sched_time = current_state.user_schedule.get(sched_key) or current_state.user_schedule.get("college_departure", "08:30")
                resolved_departure_time = sched_time
                resolved_time = sched_time
                inherited_fields.append("departure_time")
        elif resolved_trip_phase == "return":
            if extracted_time:
                resolved_return_time = extracted_time
                resolved_time = extracted_time
            elif current_state.active_return_time:
                resolved_return_time = current_state.active_return_time
                resolved_time = current_state.active_return_time
                inherited_fields.append("return_time")
            else:
                # User's known/usual return time
                sched_key = f"{resolved_activity}_return" if resolved_activity else "college_return"
                sched_time = current_state.user_schedule.get(sched_key) or current_state.user_schedule.get("college_return", "17:00")
                resolved_return_time = sched_time
                resolved_time = sched_time
                inherited_fields.append("return_time")
        elif extracted_time:
            resolved_time = extracted_time
        elif turn_type in (TurnTypeEnum.FOLLOW_UP, TurnTypeEnum.TOPIC_CONTINUATION) and current_state.active_time:
            resolved_time = current_state.active_time
            inherited_fields.append("time")

        # 8. Temporal Reference ("then") Resolution & Ambiguity Check
        if has_temporal_then:
            if resolved_time:
                inherited_fields.append("time")
            elif resolved_date:
                inherited_fields.append("date")
            elif not current_state.active_time and not current_state.active_date:
                is_ambiguous = True
                ambiguity_reason = "Temporal reference 'then' used without active time or date in conversation context."
                clarification = ClarificationState(
                    needed=True,
                    field="time_or_date",
                    prompt="Which day or time would you like me to check?",
                    pending_query=clean_msg
                )
                turn_type = TurnTypeEnum.AMBIGUOUS_REQUEST

        # 9. Transport Mode & Pronoun "it" Resolution
        resolved_transport_mode = extracted_transport
        resolved_intent: Optional[str] = None

        if resolved_transport_mode:
            resolved_intent = IntentEnum.BIKE_TRAVEL.value if resolved_transport_mode == "bike" else current_state.current_intent
        elif has_pronoun_it:
            # Resolve antecedent for "it" from prior transport or vehicle/item in state
            if current_state.active_transport_mode:
                resolved_transport_mode = current_state.active_transport_mode
                resolved_intent = IntentEnum.BIKE_TRAVEL.value if resolved_transport_mode == "bike" else current_state.current_intent
                inherited_fields.append("transport_mode")
            elif current_state.active_vehicle_or_item == "bike":
                resolved_transport_mode = "bike"
                resolved_intent = IntentEnum.BIKE_TRAVEL.value
                inherited_fields.append("transport_mode")
            elif current_state.active_vehicle_or_item == "umbrella" or (current_state.active_topic and "umbrella" in current_state.active_topic):
                resolved_activity = "umbrella"
                resolved_intent = IntentEnum.UMBRELLA_DECISION.value
                inherited_fields.append("activity")
            else:
                # Genuinely ambiguous: no vehicle or item antecedent exists
                is_ambiguous = True
                ambiguity_reason = "Pronoun 'it' referenced without a prior vehicle or item in conversation context."
                clarification = ClarificationState(
                    needed=True,
                    field="vehicle_or_item",
                    prompt="Are you asking about taking your bike or carrying an umbrella?",
                    options=["bike", "umbrella"],
                    pending_query=clean_msg
                )
                turn_type = TurnTypeEnum.AMBIGUOUS_REQUEST
        elif turn_type in (TurnTypeEnum.FOLLOW_UP, TurnTypeEnum.TOPIC_CONTINUATION) and current_state.active_transport_mode:
            resolved_transport_mode = current_state.active_transport_mode
            inherited_fields.append("transport_mode")

        # 10. Weather Topic Resolution
        resolved_topic: Optional[str] = None
        if any(k in lower_msg for k in ["rain", "raining", "drizzle", "shower", "மழை", "barish"]):
            resolved_topic = "rain"
        elif any(k in lower_msg for k in ["umbrella", "kudai", "குடை", "chhata"]):
            resolved_topic = "umbrella"
        elif any(k in lower_msg for k in ["temp", "temperature", "hot", "cold"]):
            resolved_topic = "temperature"
        elif any(k in lower_msg for k in ["aqi", "air quality", "pollution"]):
            resolved_topic = "aqi"
        elif any(k in lower_msg for k in ["warning", "alert", "cyclone"]):
            resolved_topic = "warning"
        elif getattr(nlu.entities, 'weather_variable', None):
            resolved_topic = nlu.entities.weather_variable
        elif turn_type in (TurnTypeEnum.FOLLOW_UP, TurnTypeEnum.TOPIC_CONTINUATION) and current_state.active_topic:
            resolved_topic = current_state.active_topic
            inherited_fields.append("topic")

        # 11. Intent Mapping
        if not resolved_intent:
            if nlu.intent.value in [
                IntentEnum.COLLEGE_COMMUTE.value, IntentEnum.BIKE_TRAVEL.value,
                IntentEnum.UMBRELLA_DECISION.value, IntentEnum.FISHING_DECISION.value,
                IntentEnum.SPORTS_ACTIVITY.value, IntentEnum.FARMING_DECISION.value
            ]:
                resolved_intent = nlu.intent.value
            elif resolved_transport_mode == "bike":
                resolved_intent = IntentEnum.BIKE_TRAVEL.value
            elif resolved_activity == "college" and resolved_trip_phase == "departure":
                resolved_intent = IntentEnum.COLLEGE_COMMUTE.value
            elif turn_type in (TurnTypeEnum.FOLLOW_UP, TurnTypeEnum.TOPIC_CONTINUATION) and current_state.current_intent:
                resolved_intent = current_state.current_intent
            else:
                resolved_intent = nlu.intent.value

        # 12. Persona & Language Resolution
        resolved_persona = explicit_persona or current_state.persona or "general"
        resolved_language = explicit_language or current_state.preferred_language or nlu.detected_language.value

        # 13. Build Disambiguated / Enriched Grounded Query
        resolved_message = clean_msg
        if has_loc_ref and resolved_location and resolved_location != "Unspecified":
            for pat in LOCATION_REFERENCE_PATTERNS:
                resolved_message = re.sub(pat, resolved_location, resolved_message, flags=re.IGNORECASE)

        # 14. Bounded Context Construction
        context_summary = current_state.to_bounded_context(max_turns=2)

        return ResolvedQueryContext(
            original_message=clean_msg,
            resolved_message=resolved_message,
            resolved_location=resolved_location,
            resolved_date=resolved_date,
            resolved_time=resolved_time,
            resolved_departure_time=resolved_departure_time,
            resolved_return_time=resolved_return_time,
            resolved_destination=resolved_destination,
            resolved_transport_mode=resolved_transport_mode,
            resolved_trip_phase=resolved_trip_phase,
            resolved_intent=resolved_intent,
            resolved_persona=resolved_persona,
            resolved_language=resolved_language,
            resolved_topic=resolved_topic,
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

            # Update isolated or new dimensions
            if resolved_ctx.resolved_destination:
                state.active_destination = resolved_ctx.resolved_destination
            if resolved_ctx.resolved_date:
                state.active_date = resolved_ctx.resolved_date
            if resolved_ctx.resolved_time:
                state.active_time = resolved_ctx.resolved_time
            if resolved_ctx.resolved_departure_time:
                state.active_departure_time = resolved_ctx.resolved_departure_time
            if resolved_ctx.resolved_return_time:
                state.active_return_time = resolved_ctx.resolved_return_time
            if resolved_ctx.resolved_trip_phase:
                state.active_trip_phase = resolved_ctx.resolved_trip_phase
            if resolved_ctx.resolved_transport_mode:
                state.active_transport_mode = resolved_ctx.resolved_transport_mode
                state.active_vehicle_or_item = resolved_ctx.resolved_transport_mode
            if resolved_ctx.resolved_activity:
                state.active_activity = resolved_ctx.resolved_activity
                if resolved_ctx.resolved_activity == "umbrella":
                    state.active_vehicle_or_item = "umbrella"
            if resolved_ctx.resolved_topic:
                state.active_topic = resolved_ctx.resolved_topic
            if resolved_ctx.resolved_intent:
                state.current_intent = resolved_ctx.resolved_intent
            if resolved_ctx.resolved_persona:
                state.persona = resolved_ctx.resolved_persona
            if resolved_ctx.resolved_language:
                state.preferred_language = resolved_ctx.resolved_language

            # Sync active_entities dictionary
            state.active_entities.update({
                k: v for k, v in [
                    ("location", state.active_location),
                    ("destination", state.active_destination),
                    ("date", state.active_date),
                    ("time", state.active_time),
                    ("departure_time", state.active_departure_time),
                    ("return_time", state.active_return_time),
                    ("transport_mode", state.active_transport_mode),
                    ("trip_phase", state.active_trip_phase),
                    ("activity", state.active_activity),
                    ("topic", state.active_topic),
                ] if v is not None
            })

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
