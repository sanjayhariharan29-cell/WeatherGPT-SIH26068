"""Conversational Context Resolver for WeatherGPT.

Implements reference resolution ("there", "that place", "it"), entity inheritance
(location, date, time-of-day, persona, language), topic continuation,
multi-location ambiguity detection, and context summarization.
"""

import re
from typing import Optional, List, Tuple
from datetime import datetime, timezone

from ai.memory.models import ConversationContext, ResolvedQueryContext
from ai.nlu import parse_query
from ai.models import LanguageEnum, NLUResult

# Regex patterns for location reference pronouns across English, Tamil, and Hindi
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

# Time of day keywords
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

# Meteorological topic keywords
TOPIC_KEYWORDS = {
    "rain": ["rain", "raining", "rainfall", "shower", "precipitation", "mazhai", "மழை", "बारिश", "बरसात"],
    "wind": ["wind", "windy", "breeze", "gust", "kaatru", "காற்று", "हवा", "आंधी"],
    "temperature": ["temperature", "temp", "hot", "cold", "heat", "warm", "சூடு", "குளிர்", "तापमान", "गर्मी", "सर्दी"],
    "humidity": ["humidity", "humid", "ஈரப்பதம்", "नमी"],
    "cyclone": ["cyclone", "storm", "புயல்", "तूफान", "चक्रवात"],
    "flood": ["flood", "flooding", "வெள்ளம்", "बाढ़"],
    "forecast": ["forecast", "வானிலை அறிக்கை", "पूर्वानुमान"]
}


class ContextResolver:
    """Combines previous ConversationContext with new query for coherent follow-ups."""

    @classmethod
    def has_location_reference(cls, text: str) -> bool:
        """Checks if text contains pronouns referring back to a previously mentioned location."""
        lower = text.lower()
        for pat in LOCATION_REFERENCE_PATTERNS:
            if re.search(pat, lower, re.IGNORECASE):
                return True
        return False

    @classmethod
    def extract_time_of_day(cls, text: str) -> Optional[str]:
        """Identifies time-of-day mentions (morning, afternoon, evening, night)."""
        lower = text.lower()
        for kw, normalized in TIME_OF_DAY_KEYWORDS.items():
            if kw in lower:
                return normalized
        return None

    @classmethod
    def extract_topic(cls, text: str) -> Optional[str]:
        """Identifies primary weather topic discussed."""
        lower = text.lower()
        for topic, kws in TOPIC_KEYWORDS.items():
            for kw in kws:
                if kw in lower:
                    return topic
        return None

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
    def resolve_query(
        cls,
        message: str,
        context: Optional[ConversationContext],
        explicit_location: Optional[str] = None,
        explicit_language: Optional[str] = None,
        explicit_persona: Optional[str] = None
    ) -> ResolvedQueryContext:
        """Merges incoming message and explicit parameters with past conversation context.
        
        Strictly follows priority hierarchy:
        EXPLICIT USER INPUT > CURRENT NLU > RECENT CONVERSATION CONTEXT > DEFAULTS.
        """
        inherited_fields: List[str] = []
        is_ambiguous = False
        ambiguity_reason: Optional[str] = None

        # If user explicitly requests a reset, ignore previous context
        if cls.is_reset_query(message):
            context = None

        # Parse current message through Phase 2 NLU
        nlu = parse_query(message)

        # 1. Location Resolution & Ambiguity Detection
        resolved_location = "Coimbatore"
        curr_extracted_location = nlu.entities.location
        has_ref = cls.has_location_reference(message)

        # Check explicit location parameter first
        if explicit_location and explicit_location.strip().lower() != "coimbatore":
            resolved_location = explicit_location.strip()
        elif curr_extracted_location:
            # Explicit location found in current user query overrides everything
            resolved_location = curr_extracted_location
        elif has_ref:
            # Query has "there" / "that place" reference
            if context and context.recent_locations:
                # Ambiguity Check: If multiple distinct locations were recently discussed
                unique_recent_locs = list(dict.fromkeys(context.recent_locations))
                if len(unique_recent_locs) > 1 and not curr_extracted_location:
                    is_ambiguous = True
                    ambiguity_reason = (
                        f"Ambiguous reference: multiple locations discussed recently ({', '.join(unique_recent_locs)}). "
                        f"Please specify which location you mean."
                    )
                    resolved_location = unique_recent_locs[-1]
                else:
                    resolved_location = context.location or "Coimbatore"
                    inherited_fields.append("location")
            elif context and context.location:
                resolved_location = context.location
                inherited_fields.append("location")
            else:
                resolved_location = "Coimbatore"
        elif context and context.location:
            # Inherit previous location if current query did not specify one
            resolved_location = context.location
            inherited_fields.append("location")
        elif explicit_location:
            resolved_location = explicit_location.strip()

        # 2. Temporal Context Resolution (Date & Time-of-day / Schedule)
        curr_date = nlu.entities.date  # e.g. "tomorrow", "today", "yesterday"
        curr_time_of_day = nlu.entities.time or cls.extract_time_of_day(message)

        # Schedule Resolution
        curr_dep = nlu.entities.departure_time
        curr_ret = nlu.entities.return_time
        resolved_dep = curr_dep or (context.departure_time if context else None)
        resolved_ret = curr_ret or (context.return_time if context else None)
        if not curr_dep and context and context.departure_time:
            inherited_fields.append("departure_time")
        if not curr_ret and context and context.return_time:
            inherited_fields.append("return_time")

        # Check if query asks about leaving college/office/work
        is_leave_commute = any(k in message.lower() for k in [
            "leave college", "leaving college", "after college", "from college",
            "leave office", "leaving office", "after office", "return home", "come back"
        ])
        if is_leave_commute:
            if resolved_ret:
                curr_time_of_day = resolved_ret
            else:
                curr_time_of_day = "5:00 PM"

        resolved_date: Optional[str] = None
        resolved_time: Optional[str] = None

        if curr_date:
            # Explicit date in current query overrides
            resolved_date = curr_date
            resolved_time = curr_time_of_day
        elif curr_time_of_day:
            # User specified only time-of-day ("What about evening?" or "What about when I leave college?")
            # -> Inherit previous date context
            resolved_time = curr_time_of_day
            if context and context.date_context:
                resolved_date = context.date_context
                inherited_fields.append("date_context")
            else:
                resolved_date = "today"
        elif context and context.date_context:
            # Neither date nor time in current query -> Inherit past temporal context
            resolved_date = context.date_context
            resolved_time = context.time_context
            inherited_fields.append("date_context")
            if context.time_context:
                inherited_fields.append("time_context")
        else:
            resolved_date = "today"

        # 3. Meteorological Topic Resolution
        curr_topic = cls.extract_topic(message)
        resolved_topic: Optional[str] = None
        if curr_topic:
            resolved_topic = curr_topic
        elif context and context.active_topic:
            resolved_topic = context.active_topic
            inherited_fields.append("active_topic")

        # 4. Persona Resolution
        resolved_persona = "general"
        if explicit_persona and explicit_persona.strip():
            cand_persona = explicit_persona.strip().lower()
            # If candidate is default "student", but user message does not mention student and context has a specific persona (e.g. farmer):
            if cand_persona == "student" and context and context.persona and context.persona != "student" and "student" not in message.lower():
                resolved_persona = context.persona
                inherited_fields.append("persona")
            else:
                resolved_persona = cand_persona
        elif nlu.entities.persona:
            resolved_persona = nlu.entities.persona.value
        elif context and context.persona:
            resolved_persona = context.persona
            inherited_fields.append("persona")

        # 5. Language Resolution
        resolved_language = "en"
        # Check explicit request override first (e.g., user says "tell me in Tamil" or caller passed language)
        if explicit_language and explicit_language.strip():
            resolved_language = explicit_language.strip().lower()
        elif nlu.detected_language and nlu.detected_language.value in ("ta", "hi"):
            resolved_language = nlu.detected_language.value
        elif context and context.language:
            resolved_language = context.language
            inherited_fields.append("language")
        else:
            resolved_language = "en"

        # 6. Reconstruct Enriched Query Message for Downstream Grounding
        # When reference pronouns like "there" are present, substitute the resolved location
        enriched_message = message
        if has_ref and resolved_location:
            enriched_message = re.sub(r"\bthere\b", resolved_location, enriched_message, flags=re.IGNORECASE)
            enriched_message = re.sub(r"\bthat place\b", resolved_location, enriched_message, flags=re.IGNORECASE)
            enriched_message = re.sub(r"\bsame place\b", resolved_location, enriched_message, flags=re.IGNORECASE)
            enriched_message = re.sub(r"\bsame location\b", resolved_location, enriched_message, flags=re.IGNORECASE)

        # 7. Generate Compact Structured Context Summary for LLM Grounding
        summary_parts = []
        summary_parts.append(f"Location: {resolved_location}")
        if resolved_date:
            summary_parts.append(f"Date: {resolved_date}")
        if resolved_time:
            summary_parts.append(f"Time: {resolved_time}")
        if resolved_dep or resolved_ret:
            summary_parts.append(f"Schedule: {resolved_dep or 'N/A'} - {resolved_ret or 'N/A'}")
        if resolved_topic:
            summary_parts.append(f"Topic: {resolved_topic}")
        if resolved_persona and resolved_persona != "general":
            summary_parts.append(f"Persona: {resolved_persona}")
        if inherited_fields:
            summary_parts.append(f"InheritedFromHistory: {', '.join(inherited_fields)}")

        context_summary = " | ".join(summary_parts)

        return ResolvedQueryContext(
            original_message=message,
            resolved_message=enriched_message,
            resolved_location=resolved_location,
            resolved_date=resolved_date,
            resolved_time=resolved_time,
            resolved_departure_time=resolved_dep,
            resolved_return_time=resolved_ret,
            resolved_persona=resolved_persona,
            resolved_language=resolved_language,
            resolved_topic=resolved_topic,
            is_ambiguous=is_ambiguous,
            ambiguity_reason=ambiguity_reason,
            inherited_fields=inherited_fields,
            context_summary=context_summary
        )
