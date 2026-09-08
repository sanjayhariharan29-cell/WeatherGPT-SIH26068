"""Intent Classification Module for WeatherGPT.

Classifies natural language weather queries in English, Tamil, Hindi,
and Tanglish into canonical intents according to docs/09_AI_Design.md.
"""

import re
from typing import Tuple
from ai.models import IntentEnum


def classify_intent(text: str) -> Tuple[IntentEnum, float]:
    """Classifies user query into an IntentEnum with a confidence score."""
    if not text or not text.strip():
        return IntentEnum.GENERAL_WEATHER_QUESTION, 0.5

    clean = text.lower().strip()

    # Cyclone & Emergency Storm
    if any(k in clean for k in ["cyclone", "புயல்", "puyal", "storm alert", "super cyclone"]):
        return IntentEnum.CYCLONE_INQUIRY, 0.95

    # Warnings & Alerts
    if any(k in clean for k in ["warning", "alert", "எச்சரிக்கை", "danger", "red alert", "orange alert"]):
        return IntentEnum.WEATHER_ALERT, 0.92

    # Outdoor Decision (e.g. "college pogalama?", "can i go outside?", "should i travel?")
    if any(k in clean for k in [
        "pogalama", "poga mudiyuma", "pogalaama", "can i go", "should i go",
        "safe to travel", "safe to go", "போகலாமா", "செல்லலாமா", "safely travel",
        "outdoor", "trip pogalama"
    ]):
        return IntentEnum.OUTDOOR_DECISION, 0.92

    # Agricultural Advisory
    if any(k in clean for k in [
        "farmer", "crop", "agriculture", "விவசாயம்", "பயிர்", "irrigation",
        "vivasayam", "vivasayi", "kheti", "harvest"
    ]):
        return IntentEnum.AGRICULTURE_ADVISORY, 0.90

    # Historical & Trends
    if any(k in clean for k in ["last year", "five years", "5 years", "10 years", "history", "historical", "கடந்த ஆண்டு"]):
        if any(k in clean for k in ["trend", "climate change", "hotter over", "increasing", "மாற்றம்"]):
            return IntentEnum.CLIMATE_TREND, 0.88
        return IntentEnum.HISTORICAL_WEATHER, 0.88

    # Rain & Precipitation
    if any(k in clean for k in [
        "rain", "raining", "drizzle", "shower", "மழை", "mazhai", "malai",
        "baarish", "barish", "precipitation", "umbrella"
    ]):
        return IntentEnum.RAIN_FORECAST, 0.90

    # Temperature & Heat
    if any(k in clean for k in ["temp", "temperature", "hot", "cold", "heat", "வெப்பநிலை", "veyil", "veiyil", "kulir"]):
        return IntentEnum.TEMPERATURE, 0.88

    # Wind
    if any(k in clean for k in ["wind", "gust", "காற்று", "kaathu", "katru", "hawa"]):
        return IntentEnum.WIND, 0.88

    # Humidity
    if any(k in clean for k in ["humidity", "humid", "ஈரப்பதம்", "eerapadham", "sweaty"]):
        return IntentEnum.HUMIDITY, 0.88

    # General Forecast vs Current Weather
    if any(k in clean for k in ["tomorrow", "naalaiku", "nalaiku", "நாளை", "next week", "forecast", "weekend"]):
        return IntentEnum.FORECAST, 0.85

    if any(k in clean for k in ["now", "right now", "today", "current", "இன்று", "inniku", "iniku", "ippo", "aaj"]):
        return IntentEnum.CURRENT_WEATHER, 0.85

    return IntentEnum.GENERAL_WEATHER_QUESTION, 0.60
