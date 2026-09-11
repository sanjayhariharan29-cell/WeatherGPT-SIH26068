"""Intent Classification Module for WeatherGPT NLU.

Classifies natural language weather queries in English, Tamil, Hindi,
Tanglish, and Hinglish into canonical intents according to docs/09_AI_Design.md.
"""

import re
from typing import Tuple
from ai.models import IntentEnum


def classify_intent(text: str) -> Tuple[IntentEnum, float]:
    """Classifies user query into an IntentEnum with an interpretation confidence score."""
    if not text or not text.strip():
        return IntentEnum.GENERAL_WEATHER_QUESTION, 0.5

    clean = text.lower().strip()

    # 0. Pure Greetings (No Weather Query)
    if clean in ["hello", "hi", "hey", "vanakkam", "வணக்கம்", "namaste", "नमस्ते", "good morning", "good evening", "good afternoon", "halo", "ola"]:
        return IntentEnum.GREETING, 0.98

    # 0a. Ambiguous / Clarification Needed ("weather there?", "how is it there?")
    if re.search(r"\b(weather\s+there|how\s+is\s+it\s+there|kaisa\s+hai\s+wahan|anga\s+epdi\s+iruku)\b", clean) and not any(c in clean for c in ["chennai", "coimbatore", "delhi", "bangalore", "madurai", "mumbai"]):
        return IntentEnum.CLARIFICATION_NEEDED, 0.95

    # 0b. Why / Explanation Inquiries
    if clean in ["why", "why?", "yen", "yen?", "kyun", "kyun?"] or any(k in clean for k in ["why umbrella", "why is confidence", "why confidence low", "why disagree", "why are sources", "why the warning", "reason for"]):
        return IntentEnum.WEATHER_EXPLANATION, 0.96

    # 0c. Location Comparison
    if any(k in clean for k in ["compare", "cooler", "warmer", "hotter", "which is cooler", "which is warmer", "which is hotter", "versus", " vs "]):
        return IntentEnum.LOCATION_COMPARISON, 0.94

    # 0d. Air Quality (AQI)
    if any(k in clean for k in ["aqi", "air quality", "air-quality", "pollution", "pm2.5", "pm10", "smog", "காற்றின் தரம்", "hawa ki quality"]):
        return IntentEnum.AIR_QUALITY, 0.94

    # 0e. Time-Specific Schedule Forecast ("at 5 PM", "when I leave college", "during commute", "between 4 and 6 PM")
    if any(k in clean for k in ["leave college", "leaving college", "during my commute", "at college", "office time", "when i leave"]) or bool(re.search(r"\b(?:at|around|between|by)\s+\d{1,2}\s*(?:am|pm|a\.m\.|p\.m\.|:\d{2})", clean)):
        return IntentEnum.TIME_SPECIFIC_FORECAST, 0.93

    # 1. Cyclone & Emergency Storm
    if any(k in clean for k in [
        "cyclone", "புயல்", "puyal", "storm alert", "super cyclone",
        "चक्रवात", "toofan", "tufan", "tufaan"
    ]):
        return IntentEnum.CYCLONE_INQUIRY, 0.95

    # 2. Warnings & Alerts
    if any(k in clean for k in [
        "warning", "alert", "எச்சரிக்கை", "danger", "red alert", "orange alert",
        "चेतावनी", "khatra", "khatre ki ghanti", "imd warning", "imd alert"
    ]):
        return IntentEnum.WEATHER_ALERT, 0.92

    # 3. Outdoor Decision & Commute / Travel Safety
    if any(k in clean for k in [
        "pogalama", "poga mudiyuma", "pogalaama", "can i go", "should i go",
        "safe to travel", "safe to go", "போகலாமா", "செல்லலாமா", "safely travel",
        "ja sakte hain", "jaana chahiye", "bahar ja sakte", "jaana safe hai",
        "trip kar sakte", "बाहर जा सकते", "जाना चाहिए"
    ]):
        return IntentEnum.OUTDOOR_DECISION, 0.92

    # 4. Agricultural Advisory
    if any(k in clean for k in [
        "farmer", "crop", "agriculture", "விவசாயம்", "பயிர்", "irrigation",
        "vivasayam", "vivasayi", "kheti", "kisan", "fasal", "sinchai",
        "किसान", "फसल", "खेती", "सिंचाई"
    ]):
        return IntentEnum.AGRICULTURE_ADVISORY, 0.90

    # 5. Historical & Climate Trends
    if any(k in clean for k in [
        "last year", "five years", "5 years", "10 years", "history", "historical",
        "previous years", "past years", "compared with previous years", "compared to previous years",
        "unusual compared", "typical temperature", "typical rainfall", "typical weather", "typical this month",
        "normal temperature", "normal rainfall", "in the past", "last month", "last summer", "last monsoon",
        "கடந்த ஆண்டு", "முந்தைய ஆண்டுகள்", "வழக்கமான வெப்பநிலை", "வழக்கமான மழை",
        "पिछले साल", "पिछले वर्षों", "सामान्य तापमान", "सामान्य बारिश"
    ]) or bool(re.search(r"\b(in|during)\s+(19\d\d|20[0-2]\d)\b", clean)):
        if any(k in clean for k in ["trend", "climate change", "hotter over", "increasing", "மாற்றம்", "बदलाव", "परिवर्तन"]):
            return IntentEnum.CLIMATE_TREND, 0.88
        return IntentEnum.HISTORICAL_WEATHER, 0.88

    # 6. Rain & Precipitation
    if any(k in clean for k in [
        "rain", "raining", "drizzle", "shower", "மழை", "mazhai", "malai", "mazha",
        "baarish", "barish", "barsaat", "बारिश", "बरसात", "वर्षा", "umbrella"
    ]):
        return IntentEnum.RAIN_FORECAST, 0.92

    # 7. Temperature & Heat
    if any(k in clean for k in [
        "temp", "temperature", "hot", "cold", "heat", "வெப்பநிலை", "veyil", "veiyil",
        "kulir", "garmi", "thand", "thandi", "sardi", "तापमान", "गर्मी", "ठंड"
    ]):
        return IntentEnum.TEMPERATURE, 0.88

    # 8. Wind
    if any(k in clean for k in [
        "wind", "gust", "காற்று", "kaathu", "katru", "hawa", "हवा", "आंधी", "aandhi"
    ]):
        return IntentEnum.WIND, 0.88

    # 9. Humidity
    if any(k in clean for k in [
        "humidity", "humid", "ஈரப்பதம்", "eerapadham", "sweaty", "nami", "umas", "उमस", "नमी"
    ]):
        return IntentEnum.HUMIDITY, 0.88

    # 10. General Forecast (Tomorrow, Future, Weekend)
    if any(k in clean for k in [
        "tomorrow", "naalaiku", "nalaiku", "நாளை", "next week", "forecast", "weekend",
        "kal", "parso", "agle hafte", "कल", "परसों"
    ]):
        return IntentEnum.FORECAST, 0.86

    # 11. Current Weather (Now, Today, Kaisa hai, Epdi iruku)
    if any(k in clean for k in [
        "now", "right now", "today", "current", "இன்று", "inniku", "iniku", "ippo",
        "aaj", "abhi", "kaisa", "epdi", "आज", "अभी", "कैसा"
    ]):
        return IntentEnum.CURRENT_WEATHER, 0.85

    return IntentEnum.GENERAL_WEATHER_QUESTION, 0.60
