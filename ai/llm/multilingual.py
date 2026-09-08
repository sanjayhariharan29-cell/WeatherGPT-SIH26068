"""Multilingual Language Resolution & Meteorological Terminology for WeatherGPT.

Provides deterministic target language resolution, authoritative glossary mappings,
and localized phrasing across English, Tamil, and Hindi for Phase 8.
"""

import re
from typing import Dict, Optional
from ai.models import LanguageEnum


# -------------------------------------------------------------------
# Target Language Resolution
# -------------------------------------------------------------------

def resolve_target_language(
    nlu_lang: LanguageEnum,
    query_text: Optional[str] = None,
    explicit_preference: Optional[LanguageEnum] = None
) -> LanguageEnum:
    """Resolves the output response language deterministically.

    Priority:
    1. Explicit user language preference parameter (if valid).
    2. Explicit inline language requests in query (e.g. "respond in Hindi").
    3. NLU-detected language (Tanglish -> TA, Hinglish -> HI, TA -> TA, HI -> HI).
    4. Safe fallback default: English.
    """
    # 1. Explicit parameter preference
    if explicit_preference in (LanguageEnum.EN, LanguageEnum.TA, LanguageEnum.HI):
        return explicit_preference
    if explicit_preference in (LanguageEnum.TANGLISH,):
        return LanguageEnum.TA
    if explicit_preference in (LanguageEnum.HINGLISH,):
        return LanguageEnum.HI

    # 2. Query string directive check
    if query_text:
        q_lower = query_text.lower()
        if re.search(r"\b(?:in hindi|hindi me|hindi mein|hindi la|hindi-la|hindi mein batao)\b", q_lower):
            return LanguageEnum.HI
        if re.search(r"\b(?:in tamil|tamilil|tamil la|tamil-la|tamil me|tamil pesu)\b", q_lower):
            return LanguageEnum.TA
        if re.search(r"\b(?:in english|english me|english la|english-la)\b", q_lower):
            return LanguageEnum.EN

    # 3. NLU-detected language mapping
    if nlu_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
        return LanguageEnum.TA
    if nlu_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
        return LanguageEnum.HI

    return LanguageEnum.EN


# -------------------------------------------------------------------
# Authoritative Meteorological Glossary (EN / TA / HI)
# -------------------------------------------------------------------

WEATHER_CONDITION_MAP: Dict[str, Dict[str, str]] = {
    "rain": {"en": "Rain", "ta": "மழை", "hi": "बारिश"},
    "heavy rain": {"en": "Heavy Rain", "ta": "கனமழை", "hi": "भारी बारिश"},
    "moderate rain": {"en": "Moderate Rain", "ta": "மிதமான மழை", "hi": "मध्यम बारिश"},
    "light rain": {"en": "Light Rain", "ta": "லேசான மழை", "hi": "हल्की बारिश"},
    "thunderstorm": {"en": "Thunderstorm", "ta": "இடியுடன் கூடிய மழை", "hi": "गरज के साथ बारिश"},
    "cyclone": {"en": "Cyclone", "ta": "புயல்", "hi": "चक्रवात"},
    "sunny": {"en": "Sunny", "ta": "வெயில்", "hi": "धूप"},
    "clear": {"en": "Clear", "ta": "தெளிவான வானிலை", "hi": "साफ मौसम"},
    "cloudy": {"en": "Cloudy", "ta": "மேகமூட்டம்", "hi": "बादल छाए रहेंगे"},
    "partly cloudy": {"en": "Partly Cloudy", "ta": "பகுதி மேகமூட்டம்", "hi": "आंशिक रूप से बादल"},
    "fog": {"en": "Fog / Low Visibility", "ta": "பனிமூட்டம்", "hi": "कोहरा / धुंध"},
    "windy": {"en": "Windy", "ta": "பலத்த காற்று", "hi": "तेज हवा"},
    "heatwave": {"en": "Heatwave", "ta": "வெப்ப அலை", "hi": "लू / भीषण गर्मी"},
    "coldwave": {"en": "Coldwave", "ta": "குளிர் அலை", "hi": "शीत लहर"},
}


def translate_condition(condition: Optional[str], target_lang: LanguageEnum) -> str:
    """Translates weather condition safely, returning original text if unmapped."""
    if not condition or condition.lower() == "unknown":
        if target_lang == LanguageEnum.TA:
            return "தெரியவில்லை"
        elif target_lang == LanguageEnum.HI:
            return "उपलब्ध नहीं"
        return "Unknown"

    c_key = condition.lower().strip()
    entry = WEATHER_CONDITION_MAP.get(c_key)
    if entry:
        lang_key = "ta" if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH) else "hi" if target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH) else "en"
        return entry.get(lang_key, condition)

    return condition
