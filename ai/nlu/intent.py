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

    # 1. Cyclone & Emergency Storm
    if any(k in clean for k in [
        "cyclone", "புயல்", "puyal", "storm alert", "super cyclone",
        "चक्रवात", "toofan", "tufan", "tufaan"
    ]):
        return IntentEnum.CYCLONE_INQUIRY, 0.95

    # 2. Warnings & Alerts
    if any(k in clean for k in [
        "warning", "alert", "எச்சரிக்கை", "danger", "red alert", "orange alert",
        "चेतावनी", "khatra", "khatre ki ghanti"
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
    if any(k in clean for k in ["last year", "five years", "5 years", "10 years", "history", "historical", "கடந்த ஆண்டு", "पिछले साल"]):
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
