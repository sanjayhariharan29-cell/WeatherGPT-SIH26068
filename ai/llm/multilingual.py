"""Multilingual Language Resolution & Meteorological Terminology for WeatherGPT.

Provides deterministic target language resolution, authoritative glossary mappings,
and localized phrasing across English, Tamil, Hindi, Marathi, and Telugu.
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
    2. Explicit inline language requests in query (e.g. "respond in Marathi").
    3. NLU-detected language (Tanglish -> TA, Hinglish -> HI, TA -> TA, HI -> HI, MR -> MR, TE -> TE).
    4. Safe fallback default: English.
    """
    # 1. Explicit parameter preference
    if explicit_preference in (LanguageEnum.EN, LanguageEnum.TA, LanguageEnum.HI, LanguageEnum.MR, LanguageEnum.TE):
        return explicit_preference
    if explicit_preference in (LanguageEnum.TANGLISH,):
        return LanguageEnum.TA
    if explicit_preference in (LanguageEnum.HINGLISH,):
        return LanguageEnum.HI
    if explicit_preference in (LanguageEnum.MARATHI,):
        return LanguageEnum.MR
    if explicit_preference in (LanguageEnum.TELUGU,):
        return LanguageEnum.TE

    # 2. Query string directive check
    if query_text:
        q_lower = query_text.lower()
        if re.search(r"\b(?:in hindi|hindi me|hindi mein|hindi la|hindi-la|hindi mein batao)\b", q_lower):
            return LanguageEnum.HI
        if re.search(r"\b(?:in tamil|tamilil|tamil la|tamil-la|tamil me|tamil pesu)\b", q_lower):
            return LanguageEnum.TA
        if re.search(r"\b(?:in marathi|marathi madhe|marathit|marathi me|marathi sanga)\b", q_lower):
            return LanguageEnum.MR
        if re.search(r"\b(?:in telugu|telugu lo|telugulo|telugu-lo|telugu cheppandi)\b", q_lower):
            return LanguageEnum.TE
        if re.search(r"\b(?:in english|english me|english la|english-la)\b", q_lower):
            return LanguageEnum.EN

    # 3. NLU-detected language mapping
    if nlu_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
        return LanguageEnum.TA
    if nlu_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
        return LanguageEnum.HI
    if nlu_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
        return LanguageEnum.MR
    if nlu_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
        return LanguageEnum.TE

    return LanguageEnum.EN


# -------------------------------------------------------------------
# Authoritative Meteorological Glossary (EN / TA / HI / MR / TE)
# -------------------------------------------------------------------

WEATHER_CONDITION_MAP: Dict[str, Dict[str, str]] = {
    "rain": {"en": "Rain", "ta": "மழை", "hi": "बारिश", "mr": "पाऊस", "te": "వర్షం"},
    "heavy rain": {"en": "Heavy Rain", "ta": "கனமழை", "hi": "भारी बारिश", "mr": "मुसळधार पाऊस", "te": "భారీ వర్షం"},
    "moderate rain": {"en": "Moderate Rain", "ta": "மிதமான மழை", "hi": "मध्यम बारिश", "mr": "मध्यम पाऊस", "te": "మధ్యస్థ వర్షం"},
    "light rain": {"en": "Light Rain", "ta": "லேசான மழை", "hi": "हल्की बारिश", "mr": "हलका पाऊस", "te": "తేలికపాటి వర్షం"},
    "thunderstorm": {"en": "Thunderstorm", "ta": "இடியுடன் கூடிய மழை", "hi": "गरज के साथ बारिश", "mr": "विजांच्या कडकडाटासह वादळ", "te": "ఉరుములతో కూడిన వర్షం"},
    "cyclone": {"en": "Cyclone", "ta": "புயல்", "hi": "चक्रवात", "mr": "चक्रीवादळ", "te": "తుఫాను"},
    "sunny": {"en": "Sunny", "ta": "வெயில்", "hi": "धूप", "mr": "सूर्यप्रकाश", "te": "ఎండగా"},
    "clear": {"en": "Clear", "ta": "தெளிவான வானிலை", "hi": "साफ मौसम", "mr": "निरभ्र आकाश", "te": "నిర్మలమైన వాతావరణం"},
    "clear skies": {"en": "Clear Skies", "ta": "தெளிவான வானம்", "hi": "साफ़ आसमान", "mr": "निरभ्र आकाश", "te": "నిర్మలమైన ఆకాశం"},
    "clear sky": {"en": "Clear Sky", "ta": "தெளிவான வானம்", "hi": "साफ़ आसमान", "mr": "निरभ्र आकाश", "te": "నిర్మలమైన ఆకాశం"},
    "cloudy": {"en": "Cloudy", "ta": "மேகமூட்டம்", "hi": "बादल छाए रहेंगे", "mr": "ढगाळ वातावरण", "te": "మేఘావృతం"},
    "clouds": {"en": "Clouds", "ta": "மேகமூட்டம்", "hi": "बादल", "mr": "ढगाळ", "te": "మేఘాలు"},
    "partly cloudy": {"en": "Partly Cloudy", "ta": "பகுதி மேகமூட்டம்", "hi": "आंशिक रूप से बादल", "mr": "अंशतः ढगाळ", "te": "పాక్షికంగా మేఘావృతం"},
    "scattered clouds": {"en": "Scattered Clouds", "ta": "சிதறிய மேகங்கள்", "hi": "बिखरे हुए बादल", "mr": "विखुरलेले ढग", "te": "చెల్లాచెదురుగా మేఘాలు"},
    "broken clouds": {"en": "Broken Clouds", "ta": "சிதறிய மேகமூட்டம்", "hi": "खंडित बादल", "mr": "खंडित ढग", "te": "విడిపోయిన మేఘాలు"},
    "overcast clouds": {"en": "Overcast Clouds", "ta": "முழு மேகமூட்டம்", "hi": "घने बादल", "mr": "पूर्ण ढगाळ", "te": "పూర్తిగా మేఘావృతం"},
    "overcast": {"en": "Overcast", "ta": "முழு மேகமூட்டம்", "hi": "घने बादल", "mr": "पूर्ण ढगाळ", "te": "పూర్తిగా మేఘావృతం"},
    "few clouds": {"en": "Few Clouds", "ta": "லேசான மேகங்கள்", "hi": "हल्के बादल", "mr": "अंशतः ढगाळ", "te": "కొద్దిగా మేఘాలు"},
    "drizzle": {"en": "Drizzle", "ta": "தூறல்", "hi": "बूंदाबांदी", "mr": "रिमझिम पाऊस", "te": "చినుకులు"},
    "fog": {"en": "Fog / Low Visibility", "ta": "பனிமூட்டம்", "hi": "कोहरा / धुंध", "mr": "धुकं / कमी दृश्यमानता", "te": "పొగమంచు / తక్కువ దృశ్యమానత"},
    "mist": {"en": "Mist", "ta": "பனிமூட்டம்", "hi": "धुंध", "mr": "धुकं", "te": "పొగమంచు"},
    "haze": {"en": "Haze", "ta": "புகைமூட்டம்", "hi": "धुंध", "mr": "धुरकट हवामान", "te": "మసక"},
    "smoke": {"en": "Smoke", "ta": "புகைமூட்டம்", "hi": "धुआं", "mr": "धूर", "te": "పొగ"},
    "dust": {"en": "Dust", "ta": "தூசிப் புயல்", "hi": "धूल", "mr": "धुळीचे वादळ", "te": "ధూళి"},
    "windy": {"en": "Windy", "ta": "பலத்த காற்று", "hi": "तेज हवा", "mr": "जोरदार वारा", "te": "తీవ్రమైన గాలి"},
    "heatwave": {"en": "Heatwave", "ta": "வெப்ப அலை", "hi": "लू / भीषण गर्मी", "mr": "उष्णतेची लाट", "te": "వడगాల్పులు"},
    "coldwave": {"en": "Coldwave", "ta": "குளிர் அலை", "hi": "शीत लहर", "mr": "थंडीची लाट", "te": "శీతల గాలులు"},
    "snow": {"en": "Snow", "ta": "பனிப்பொழிவு", "hi": "बर्फबारी", "mr": "बर्फवृष्टी", "te": "మంచు"},
    "squall": {"en": "Squall", "ta": "திடீர் சூறாவளி", "hi": "झक्कड़", "mr": "वादळी वारे", "te": "తీవ్రమైన ఈదురుగాలి"},
}


def translate_condition(condition: Optional[str], target_lang: LanguageEnum) -> str:
    """Translates weather condition safely, returning original text if unmapped."""
    if not condition or condition.lower() == "unknown":
        if target_lang == LanguageEnum.TA:
            return "தெரியவில்லை"
        elif target_lang == LanguageEnum.HI:
            return "उपलब्ध नहीं"
        elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
            return "माहित नाही"
        elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
            return "తెలియదు"
        return "Unknown"

    c_key = condition.lower().strip()
    entry = WEATHER_CONDITION_MAP.get(c_key)
    if entry:
        if target_lang in (LanguageEnum.TA, LanguageEnum.TANGLISH):
            lang_key = "ta"
        elif target_lang in (LanguageEnum.HI, LanguageEnum.HINGLISH):
            lang_key = "hi"
        elif target_lang in (LanguageEnum.MR, LanguageEnum.MARATHI):
            lang_key = "mr"
        elif target_lang in (LanguageEnum.TE, LanguageEnum.TELUGU):
            lang_key = "te"
        else:
            lang_key = "en"
        return entry.get(lang_key, condition)

    return condition
