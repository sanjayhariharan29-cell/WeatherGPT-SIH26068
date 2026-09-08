"""Multilingual NLU Regression and Depth Test Suite for WeatherGPT (Phase 2).

Tests English, Tamil, Tanglish, Hindi, Hinglish, relative date/time parsing,
ambiguity handling, and edge cases per Phase 2 Roadmap.
"""

import pytest
from ai.models import IntentEnum, LanguageEnum, PersonaEnum
from ai.nlu import (
    classify_intent,
    detect_language,
    extract_entities,
    normalize_query,
    parse_query,
)


# ==========================================
# 1. Language Detection Depth Tests
# ==========================================

def test_language_detection_matrix():
    # English
    assert detect_language("What is the weather in Coimbatore?") == LanguageEnum.EN
    assert detect_language("Will it rain tomorrow in Chennai?") == LanguageEnum.EN

    # Tamil Script
    assert detect_language("நாளைக்கு கோயம்புத்தூரில் மழை வருமா?") == LanguageEnum.TA
    assert detect_language("சென்னையில் இன்று வானிலை எப்படி?") == LanguageEnum.TA

    # Tanglish (Tamil Transliteration)
    assert detect_language("naalaiku Coimbatore la mazha varuma?") == LanguageEnum.TANGLISH
    assert detect_language("coimbatore la inniku weather epdi?") == LanguageEnum.TANGLISH
    assert detect_language("naalaiku college pogalama?") == LanguageEnum.TANGLISH

    # Hindi Script
    assert detect_language("कल चेन्नई में बारिश होगी क्या?") == LanguageEnum.HI
    assert detect_language("आज दिल्ली का मौसम कैसा है?") == LanguageEnum.HI

    # Hinglish (Hindi Transliteration)
    assert detect_language("kal Chennai mein barish hogi kya?") == LanguageEnum.HINGLISH
    assert detect_language("aaj Delhi ka weather kaisa hai?") == LanguageEnum.HINGLISH
    assert detect_language("kal subah Chennai mein weather kaisa rahega?") == LanguageEnum.HINGLISH
    assert detect_language("Delhi ka mausam kal kaisa rahega?") == LanguageEnum.HINGLISH


# ==========================================
# 2. Canonical Intent Classification Multilingual Tests
# ==========================================

def test_multilingual_intent_equivalence():
    # Rain forecast across 5 linguistic modalities
    queries_rain = [
        "Will it rain tomorrow in Chennai?",
        "நாளைக்கு சென்னையில் மழை பெய்யுமா?",
        "naalaiku Chennai la mazha varuma?",
        "कल चेन्नई में बारिश होगी क्या?",
        "kal Chennai mein barish hogi kya?"
    ]
    for q in queries_rain:
        intent, conf = classify_intent(q)
        assert intent == IntentEnum.RAIN_FORECAST, f"Failed for query: {q}"
        assert conf >= 0.85

    # Current weather across modalities
    queries_current = [
        "What is the weather in Delhi right now?",
        "இன்று டெல்லியில் வானிலை எப்படி?",
        "inniku Delhi la weather epdi?",
        "आज दिल्ली का मौसम कैसा है?",
        "aaj Delhi ka weather kaisa hai?"
    ]
    for q in queries_current:
        intent, conf = classify_intent(q)
        assert intent == IntentEnum.CURRENT_WEATHER, f"Failed for query: {q}"


# ==========================================
# 3. Relative Date & Time Parsing Tests
# ==========================================

def test_relative_date_parsing():
    # Today
    assert extract_entities("Coimbatore weather today").date == "today"
    assert extract_entities("Coimbatore la inniku mazhai").date == "today"
    assert extract_entities("aaj Delhi ka mausam").date == "today"
    assert extract_entities("இன்று வானிலை").date == "today"

    # Tomorrow
    assert extract_entities("Will it rain tomorrow?").date == "tomorrow"
    assert extract_entities("naalaiku mazhai varuma?").date == "tomorrow"
    assert extract_entities("kal barish hogi?").date == "tomorrow"
    assert extract_entities("நாளை மழை வருமா?").date == "tomorrow"

    # Day after tomorrow
    assert extract_entities("weather day after tomorrow").date == "day after tomorrow"
    assert extract_entities("parso barish hogi kya?").date == "day after tomorrow"
    assert extract_entities("நாளை மறுநாள் மழை வருமா?").date == "day after tomorrow"


def test_time_period_and_range_normalization():
    # Morning
    res_morning = extract_entities("tomorrow morning in Coimbatore")
    assert res_morning.time == "morning"
    assert res_morning.time_range == "06:00-12:00"

    # Afternoon
    res_noon = extract_entities("dophar mein barish hogi?")
    assert res_noon.time == "afternoon"
    assert res_noon.time_range == "12:00-17:00"

    # Evening
    res_evening = extract_entities("Coimbatore weather this evening")
    assert res_evening.time == "evening"
    assert res_evening.time_range == "17:00-21:00"

    # Night
    res_night = extract_entities("aaj raat ko barish hogi?")
    assert res_night.time == "night"
    assert res_night.time_range == "21:00-06:00"

    # Specific timestamp
    res_specific = extract_entities("rain at 7:30 AM in Coimbatore")
    assert res_specific.time == "7:30 AM"


# ==========================================
# 4. Location Extraction Multilingual Tests
# ==========================================

def test_location_extraction_multilingual():
    assert extract_entities("weather in Coimbatore").location == "Coimbatore"
    assert extract_entities("Coimbatore la epdi iruku").location == "Coimbatore"
    assert extract_entities("கோயம்புத்தூரில் மழை வருமா").location == "Coimbatore"
    assert extract_entities("कोयंबटूर में बारिश").location == "Coimbatore"

    assert extract_entities("Chennai mein barish hogi kya").location == "Chennai"
    assert extract_entities("சென்னையில் மழை பெய்யுமா").location == "Chennai"
    assert extract_entities("चेन्नई का मौसम").location == "Chennai"

    assert extract_entities("Nagapattinam cyclone update").location == "Nagapattinam"
    assert extract_entities("நாகப்பட்டினத்தில் புயல்").location == "Nagapattinam"
    assert extract_entities("नागपट्टिनम में चक्रवात").location == "Nagapattinam"

    assert extract_entities("Delhi ka mausam kaisa hai").location == "Delhi"
    assert extract_entities("दिल्ली में मौसम").location == "Delhi"


# ==========================================
# 5. Ambiguity & Missing Location Handling
# ==========================================

def test_ambiguity_handling():
    # Location missing: must flag ambiguity rather than hallucinating a location
    result_missing = parse_query("Will it rain tomorrow?")
    assert result_missing.intent == IntentEnum.RAIN_FORECAST
    assert result_missing.entities.location is None
    assert result_missing.ambiguity == "Location not specified in query."

    # Location present: no ambiguity
    result_present = parse_query("Will it rain tomorrow in Coimbatore?")
    assert result_present.entities.location == "Coimbatore"
    assert result_present.ambiguity is None


# ==========================================
# 6. Edge & Malformed Input Handling
# ==========================================

def test_edge_and_malformed_inputs():
    # Empty query
    res_empty = parse_query("")
    assert res_empty.intent == IntentEnum.GENERAL_WEATHER_QUESTION
    assert res_empty.confidence == 0.0
    assert res_empty.ambiguity == "Empty query provided."

    # Whitespace only
    res_ws = parse_query("     ")
    assert res_ws.intent == IntentEnum.GENERAL_WEATHER_QUESTION
    assert res_ws.confidence == 0.0

    # Punctuation only
    res_punct = parse_query("??? !!! ...")
    assert res_punct.intent == IntentEnum.GENERAL_WEATHER_QUESTION

    # Normalization preserves original
    res_norm = parse_query("  Naalaikku   COIMBATORE-LA   Mazha   varuma???  ")
    assert res_norm.original_text == "  Naalaikku   COIMBATORE-LA   Mazha   varuma???  "
    assert "coimbatore" in res_norm.normalized_text
    assert res_norm.entities.location == "Coimbatore"
    assert res_norm.entities.date == "tomorrow"
