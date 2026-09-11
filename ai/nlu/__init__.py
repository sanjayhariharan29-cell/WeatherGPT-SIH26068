"""NLU Engine Package for WeatherGPT.

Provides unified parse_query function returning structured NLUResult.
"""

from ai.models import IntentEnum, NLUResult
from ai.nlu.entities import extract_entities
from ai.nlu.intent import classify_intent
from ai.nlu.language import detect_language
from ai.nlu.normalization import normalize_query


def parse_query(text: str) -> NLUResult:
    """Parses natural language query into detected language, intent, entities, and ambiguity status."""
    if not text or not text.strip():
        return NLUResult(
            original_text=text or "",
            normalized_text="",
            detected_language=detect_language(""),
            intent=IntentEnum.GENERAL_WEATHER_QUESTION,
            entities=extract_entities(""),
            confidence=0.0,
            ambiguity="Empty query provided."
        )

    normalized = normalize_query(text)
    language = detect_language(normalized)
    intent, confidence = classify_intent(normalized)
    entities = extract_entities(normalized)

    # Ambiguity Detection (Step 12): Flag missing location when forecast/weather requires it
    ambiguity = None
    location_dependent_intents = {
        IntentEnum.CURRENT_WEATHER,
        IntentEnum.FORECAST,
        IntentEnum.RAIN_FORECAST,
        IntentEnum.TEMPERATURE,
        IntentEnum.WIND,
        IntentEnum.HUMIDITY,
        IntentEnum.WEATHER_ALERT,
        IntentEnum.OUTDOOR_DECISION,
        IntentEnum.WEATHER_INFORMATION,
        IntentEnum.RAIN_QUERY,
        IntentEnum.TEMPERATURE_QUERY,
        IntentEnum.FORECAST_QUERY,
        IntentEnum.LOCATION_SPECIFIC_WEATHER,
        IntentEnum.TIME_SPECIFIC_WEATHER,
        IntentEnum.WARNING_QUERY,
    }

    if intent in location_dependent_intents and not entities.location:
        ambiguity = "Location not specified in query."

    return NLUResult(
        original_text=text,
        normalized_text=normalized,
        detected_language=language,
        intent=intent,
        entities=entities,
        confidence=confidence,
        ambiguity=ambiguity
    )


__all__ = [
    "parse_query",
    "detect_language",
    "classify_intent",
    "extract_entities",
    "normalize_query"
]
