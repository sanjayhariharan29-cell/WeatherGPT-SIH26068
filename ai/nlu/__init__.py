"""NLU Engine Package for WeatherGPT.

Provides unified parse_query function returning NLUResult.
"""

from ai.models import NLUResult
from ai.nlu.language import detect_language
from ai.nlu.intent import classify_intent
from ai.nlu.entities import extract_entities


def parse_query(text: str) -> NLUResult:
    """Parses natural language query into detected language, intent, and entities."""
    language = detect_language(text)
    intent, confidence = classify_intent(text)
    entities = extract_entities(text)

    return NLUResult(
        original_text=text,
        detected_language=language,
        intent=intent,
        entities=entities,
        confidence=confidence
    )


__all__ = ["parse_query", "detect_language", "classify_intent", "extract_entities"]
