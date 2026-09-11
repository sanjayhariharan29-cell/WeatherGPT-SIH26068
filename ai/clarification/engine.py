"""Intelligent Clarification Engine for SkyZen Personal Weather AI.

CORE PRINCIPLE:
If SkyZen does not have enough information to make a reliable answer, it must ask
for the minimum missing information. It must NEVER guess safety-critical
location/time/activity information or use raw technical data (e.g. coordinates).
"""

import re
from typing import Optional, List, Dict, Any

from ai.clarification.models import MissingInformationType, MissingInformation
from ai.models import IntentEnum, PersonaEnum
from backend.config.logging import logger

# Context-aware, natural, conversational prompts across supported languages
CLARIFICATION_PROMPTS: Dict[MissingInformationType, Dict[str, str]] = {
    MissingInformationType.INSUFFICIENT_MARINE_AREA: {
        "en": "Which area are you planning to fish in?",
        "ta": "நீங்கள் எந்தக் கடல் பகுதியில் மீன்பிடிக்கத் திட்டமிடுகிறீர்கள்?",
        "hi": "आप किस क्षेत्र में मछली पकड़ने की योजना बना रहे हैं?",
    },
    MissingInformationType.MISSING_LOCATION: {
        "en": "Where are you planning to go? Please specify your district or city.",
        "ta": "நீங்கள் எங்கு செல்ல திட்டமிட்டுள்ளீர்கள்? உங்கள் மாவட்டம் அல்லது நகரத்தை குறிப்பிடவும்.",
        "hi": "आप कहाँ जाने की योजना बना रहे हैं? कृपया अपने जिले या शहर का नाम बताएं।",
    },
    MissingInformationType.MISSING_DESTINATION: {
        "en": "Where are you heading to?",
        "ta": "நீங்கள் எங்கு செல்கிறீர்கள்?",
        "hi": "आप कहाँ जा रहे हैं?",
    },
    MissingInformationType.MISSING_DATE: {
        "en": "Which day or date are you planning for?",
        "ta": "எந்த நாள் அல்லது தேதியை நீங்கள் திட்டமிடுகிறீர்கள்?",
        "hi": "आप किस दिन या तारीख के लिए योजना बना रहे हैं?",
    },
    MissingInformationType.MISSING_TIME: {
        "en": "What time are you planning to head out?",
        "ta": "எந்த நேரத்தில் நீங்கள் புறப்பட திட்டமிடுகிறீர்கள்?",
        "hi": "आप किस समय निकलने की योजना बना रहे हैं?",
    },
    MissingInformationType.MISSING_ACTIVITY: {
        "en": "What outdoor activity are you planning?",
        "ta": "நீங்கள் என்ன வெளிப்புற செயல்பாட்டை திட்டமிடுகிறீர்கள்?",
        "hi": "आप किस गतिविधि की योजना बना रहे हैं?",
    },
    MissingInformationType.INSUFFICIENT_SAFETY_CONTEXT: {
        "en": "Which location and activity would you like me to check safety for?",
        "ta": "எந்த இடம் மற்றும் செயல்பாட்டிற்கு பாதுகாப்பை சரிபார்க்க விரும்புகிறீர்கள்?",
        "hi": "आप किस स्थान और गतिविधि के लिए सुरक्षा की जांच करना चाहते हैं?",
    },
}

# Marine coastal keywords and trigger terms
MARINE_KEYWORDS = [
    "sea", "ocean", "marine", "fish", "fishing", "boat", "coastal", "deep sea",
    "shore", "harbor", "port", "கடல்", "மீன்பிடி", "मछली", "समुद्र"
]


class IntelligentClarificationEngine:
    """Evaluates context completeness and deterministically formulates clarification prompts."""

    @classmethod
    def get_prompt(
        cls,
        missing_type: MissingInformationType,
        language: str = "en",
        options: Optional[List[str]] = None
    ) -> str:
        """Retrieves conversational, language-appropriate prompt text."""
        lang_code = (language or "en").lower()
        if any(t in lang_code for t in ["ta", "tamil", "tanglish"]):
            lang_key = "ta"
        elif any(h in lang_code for h in ["hi", "hindi", "hinglish"]):
            lang_key = "hi"
        else:
            lang_key = "en"

        if missing_type == MissingInformationType.AMBIGUOUS_LOCATION and options:
            opts_str = " or ".join(options[:2])
            if lang_key == "ta":
                return f"எந்த இடத்தை நீங்கள் குறிப்பிட்டீர்கள்: {opts_str}?"
            elif lang_key == "hi":
                return f"आप किस स्थान की बात कर रहे थे: {opts_str}?"
            return f"Which area did you mean: {opts_str}?"

        prompts_by_lang = CLARIFICATION_PROMPTS.get(missing_type, {})
        return prompts_by_lang.get(lang_key, prompts_by_lang.get("en", "Could you provide more details?"))

    def evaluate_clarification_needed(
        self,
        query: str,
        nlu_result: Any,
        current_state: Any,
        explicit_location: Optional[str] = None,
        language: str = "en"
    ) -> Optional[MissingInformation]:
        """Evaluates whether minimum safety-critical context is present or clarification is needed."""
        clean = query.strip()
        lower = clean.lower()

        # Check explicit location or active state location
        extracted_loc = getattr(nlu_result.entities, 'location', None)
        if extracted_loc and extracted_loc.lower() in ["sea", "ocean", "beach", "unspecified"]:
            extracted_loc = None

        has_active_loc = bool(
            (explicit_location and explicit_location.lower() not in ["unspecified"])
            or extracted_loc
            or (current_state and getattr(current_state, 'active_location', None) and getattr(current_state, 'active_location').lower() not in ["unspecified", "sea", "ocean"])
        )
        has_active_date = bool(
            getattr(nlu_result.entities, 'date', None)
            or (current_state and getattr(current_state, 'active_date', None))
        )
        has_active_time = bool(
            getattr(nlu_result.entities, 'time', None)
            or (current_state and getattr(current_state, 'active_time', None))
            or (current_state and getattr(current_state, 'active_departure_time', None))
        )
        has_active_activity = bool(
            getattr(nlu_result.entities, 'activity', None)
            or (current_state and getattr(current_state, 'active_activity', None))
        )

        nlu_intent = getattr(nlu_result, 'intent', None)
        intent_val = nlu_intent.value if hasattr(nlu_intent, 'value') else str(nlu_intent)

        # 1. Marine Safety & Fishing Decisions (Safety-Critical)
        is_marine_query = (
            intent_val in [IntentEnum.FISHING_DECISION.value, IntentEnum.MARINE_SAFETY.value]
            or any(k in lower for k in ["go to sea", "into the sea", "to sea", "venture out to sea", "fishing", "deep sea"])
            or any(k in clean for k in MARINE_KEYWORDS)
            or (nlu_result.entities and getattr(nlu_result.entities, 'activity', None) == "fishing")
        )
        if is_marine_query:
            # Marine safety requires a coastal location
            has_marine_loc = bool(extracted_loc or (explicit_location and explicit_location.lower() not in ["unspecified", "coimbatore"]))
            if not has_marine_loc:
                prompt_text = self.get_prompt(MissingInformationType.INSUFFICIENT_MARINE_AREA, language=language)
                return MissingInformation(
                    missing_type=MissingInformationType.INSUFFICIENT_MARINE_AREA,
                    field="marine_area",
                    severity="safety_critical",
                    reason="Marine safety analysis requires verified coastal or sea area coordinates.",
                    prompt=prompt_text,
                    intent_to_resume=IntentEnum.FISHING_DECISION.value,
                    original_query=clean,
                    context_snapshot={"activity": "fishing", "persona": "fisherman"}
                )

        # 2. College Commute (Direct answer if context exists, minimal clarification if missing)
        is_college_query = (
            intent_val == IntentEnum.COLLEGE_COMMUTE.value
            or any(k in lower for k in ["college", "lecture", "campus"])
        )
        if is_college_query:
            # If system already has current location + known college context, answer directly!
            if has_active_loc:
                return None
            else:
                prompt_text = self.get_prompt(MissingInformationType.MISSING_LOCATION, language=language)
                return MissingInformation(
                    missing_type=MissingInformationType.MISSING_LOCATION,
                    field="location",
                    severity="safety_critical",
                    reason="College commute advice requires knowing departure city or college location.",
                    prompt=prompt_text,
                    intent_to_resume=IntentEnum.COLLEGE_COMMUTE.value,
                    original_query=clean,
                    context_snapshot={"activity": "college", "destination": "college"}
                )

        # 3. Travel Decision / Destination (Commute or trip)
        is_travel_query = (
            intent_val in [IntentEnum.TRAVEL_DECISION.value, IntentEnum.BIKE_TRAVEL.value]
            or any(k in lower for k in ["can i travel", "should i drive", "can i drive", "commute safe"])
        )
        if is_travel_query:
            if not has_active_loc and not getattr(current_state, 'active_destination', None):
                prompt_text = self.get_prompt(MissingInformationType.MISSING_DESTINATION, language=language)
                return MissingInformation(
                    missing_type=MissingInformationType.MISSING_DESTINATION,
                    field="destination",
                    severity="safety_critical",
                    reason="Travel safety analysis requires target destination or travel route.",
                    prompt=prompt_text,
                    intent_to_resume=intent_val,
                    original_query=clean,
                    context_snapshot={"activity": "travel"}
                )

        # 4. Farming Operations (Pesticides, harvest, sowing)
        is_farming_query = (
            intent_val == IntentEnum.FARMING_DECISION.value
            or any(k in lower for k in ["spray", "fertilizer", "pesticide", "harvest", "sow", "crops"])
        )
        if is_farming_query:
            if not has_active_loc:
                prompt_text = self.get_prompt(MissingInformationType.MISSING_LOCATION, language=language)
                return MissingInformation(
                    missing_type=MissingInformationType.MISSING_LOCATION,
                    field="location",
                    severity="safety_critical",
                    reason="Agricultural advisory requires farm district or location.",
                    prompt=prompt_text,
                    intent_to_resume=IntentEnum.FARMING_DECISION.value,
                    original_query=clean,
                    context_snapshot={"activity": "farming", "persona": "farmer"}
                )
            if not has_active_date and any(k in lower for k in ["spray", "harvest", "sow"]):
                # If neither today, tomorrow, nor active_date exists
                prompt_text = self.get_prompt(MissingInformationType.MISSING_DATE, language=language)
                return MissingInformation(
                    missing_type=MissingInformationType.MISSING_DATE,
                    field="date",
                    severity="standard",
                    reason="Pesticide spraying and harvesting effectiveness depends on exact application date.",
                    prompt=prompt_text,
                    intent_to_resume=IntentEnum.FARMING_DECISION.value,
                    original_query=clean,
                    context_snapshot={"activity": "farming", "location": getattr(current_state, 'active_location', None)}
                )

        # 5. Sports / Outdoor Events
        is_sports_query = (
            intent_val == IntentEnum.SPORTS_ACTIVITY.value
            or any(k in lower for k in ["cricket", "match", "football", "picnic", "jogging", "marathon"])
        )
        if is_sports_query:
            if not has_active_loc:
                prompt_text = self.get_prompt(MissingInformationType.MISSING_LOCATION, language=language)
                return MissingInformation(
                    missing_type=MissingInformationType.MISSING_LOCATION,
                    field="location",
                    severity="safety_critical",
                    reason="Outdoor sports advisory requires venue or city location.",
                    prompt=prompt_text,
                    intent_to_resume=IntentEnum.SPORTS_ACTIVITY.value,
                    original_query=clean,
                    context_snapshot={"activity": "sports"}
                )

        # 6. Insufficient Safety Context ("Is it safe?", "Can I go?")
        is_bare_safety_query = bool(
            re.search(r"^\s*(?:is\s+it\s+safe\??|is\s+it\s+safe\s+to\s+go\??|can\s+i\s+go\??|safe\??)\s*$", lower)
        )
        if is_bare_safety_query and not has_active_loc and not has_active_activity:
            prompt_text = self.get_prompt(MissingInformationType.INSUFFICIENT_SAFETY_CONTEXT, language=language)
            return MissingInformation(
                missing_type=MissingInformationType.INSUFFICIENT_SAFETY_CONTEXT,
                field="safety_context",
                severity="safety_critical",
                reason="Safety query contains no location, activity, or prior context.",
                prompt=prompt_text,
                intent_to_resume=IntentEnum.WEATHER_INFORMATION.value,
                original_query=clean,
                context_snapshot={}
            )

        # 7. General Weather without Location
        is_general_weather = (
            intent_val in [
                IntentEnum.WEATHER_INFORMATION.value, IntentEnum.RAIN_QUERY.value,
                IntentEnum.UMBRELLA_DECISION.value, IntentEnum.TEMPERATURE_QUERY.value,
                IntentEnum.FORECAST_QUERY.value, IntentEnum.WARNING_QUERY.value,
                IntentEnum.AQI_QUERY.value, IntentEnum.CLOTHING_ADVICE.value
            ]
            or any(k in lower for k in ["weather", "rain", "temperature", "temp", "umbrella", "forecast", "aqi"])
        )
        if is_general_weather and not has_active_loc and intent_val != IntentEnum.GREETING.value:
            prompt_text = self.get_prompt(MissingInformationType.MISSING_LOCATION, language=language)
            return MissingInformation(
                missing_type=MissingInformationType.MISSING_LOCATION,
                field="location",
                severity="safety_critical",
                reason="Weather forecast cannot be retrieved without target district or city.",
                prompt=prompt_text,
                intent_to_resume=intent_val,
                original_query=clean,
                context_snapshot={"topic": getattr(nlu_result.entities, 'weather_variable', None)}
            )

        return None


# Global engine instance
clarification_engine = IntelligentClarificationEngine()
