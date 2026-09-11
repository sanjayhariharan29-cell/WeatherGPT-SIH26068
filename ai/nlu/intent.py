"""Intent Classification Module for WeatherGPT NLU.

Classifies natural language weather queries in English, Tamil, Hindi,
Tanglish, and Hinglish into canonical intents according to docs/09_AI_Design.md.
"""

import re
from typing import Tuple
from ai.models import IntentEnum


def classify_intent(text: str) -> Tuple[IntentEnum, float]:
    """Classifies user query into an IntentEnum with an interpretation confidence score.
    
    Identifies what the user is trying to DO (commute, ride bike, carry umbrella, play sports,
    fish, farm, travel) rather than merely detecting weather keywords.
    Supports English, Tamil, Tanglish, Hindi, and Hinglish.
    """
    if not text or not text.strip():
        return IntentEnum.GENERAL_WEATHER_QUESTION, 0.5

    clean = text.lower().strip()

    # 0. Pure Greetings & General Social Conversation
    if clean in [
        "hello", "hi", "hey", "vanakkam", "வணக்கம்", "namaste", "नमस्ते",
        "good morning", "good evening", "good afternoon", "halo", "ola",
        "how are you", "who are you", "who are u", "eppadi irukinga", "kaise ho"
    ]:
        return IntentEnum.GENERAL_CONVERSATION, 0.98

    # 0a. Clarification Affirmation / Response
    if any(clean.startswith(k) or clean == k for k in [
        "yes", "yeah", "yep", "correct", "right", "exactly", "that's what i meant", "thats what i meant",
        "aama", "aamanga", "haan", "sahi hai", "sahi", "wahi"
    ]):
        return IntentEnum.CLARIFICATION_RESPONSE, 0.95

    # 0b. Ambiguous / Clarification Needed ("weather there?", "how is it there?")
    if re.search(r"\b(weather\s+there|how\s+is\s+it\s+there|kaisa\s+hai\s+wahan|anga\s+epdi\s+iruku|there\?)\b", clean) and not any(
        c in clean for c in ["chennai", "coimbatore", "delhi", "bangalore", "madurai", "mumbai", "salem", "trichy", "ooty"]
    ):
        return IntentEnum.CLARIFICATION_NEEDED, 0.95

    # 0b. Why / Explanation Inquiries
    if clean in ["why", "why?", "yen", "yen?", "kyun", "kyun?"] or any(
        k in clean for k in ["why umbrella", "why is confidence", "why confidence low", "why disagree", "why are sources", "why the warning", "reason for"]
    ):
        return IntentEnum.WEATHER_EXPLANATION, 0.96

    # 0c. Location Comparison
    if any(k in clean for k in ["compare", "cooler", "warmer", "hotter", "which is cooler", "which is warmer", "which is hotter", "versus", " vs "]):
        return IntentEnum.LOCATION_COMPARISON, 0.94

    # 0d. Air Quality (AQI)
    if any(k in clean for k in ["aqi", "air quality", "air-quality", "pollution", "pm2.5", "pm10", "smog", "காற்றின் தரம்", "hawa ki quality"]):
        return IntentEnum.AQI_QUERY, 0.94

    # =========================================================================
    # 1. ACTION & GOAL INTENTS (What the user is TRYING TO DO)
    # =========================================================================

    # 1a. Umbrella Decision ("Do I need an umbrella?")
    if any(k in clean for k in [
        "umbrella", "kudai", "குடை", "chhata", "chatha", "छाता", "छतरी"
    ]):
        if any(k in clean for k in [
            "need", "take", "carry", "should", "do i", "venuma", "theva", "thevai", "thevaipattuma",
            "eduthu", "eduthukalama", "zaroori", "chahiye", "lena", "தேவை", "வேண்டுமா", "வேணுமா",
            "எடுக்கலாமா", "लेना", "चाहिए", "ज़रूरी", "जरूरी"
        ]) or clean.endswith("umbrella?") or clean.endswith("umbrella"):
            return IntentEnum.UMBRELLA_DECISION, 0.96

    # 1b. College / School Commute Decision ("Can I go to college?")
    if any(k in clean for k in [
        "college", "school", "exam", "campus", "கல்லூரி", "பள்ளி", "कॉलेज", "स्कूल"
    ]):
        if any(k in clean for k in [
            "go", "pogalama", "poga", "polama", "mudiyuma", "safe", "leave", "reach", "open", "attend",
            "ja sakte", "ja sakta", "jaana", "jana", "chahiye", "போகலாமா", "போலாமா", "செல்லலாமா",
            "முடியுமா", "जाना चाहिए", "जा सकते", "जा सकता", "जाना"
        ]) or clean.endswith("college?") or clean.endswith("college pogalama?") or clean.endswith("college polama?"):
            return IntentEnum.COLLEGE_COMMUTE, 0.95

    # 1c. Bike / Two-Wheeler Travel ("Should I take my bike?")
    if any(k in clean for k in [
        "bike", "motorcycle", "two wheeler", "two-wheeler", "scooter", "ride",
        "பைக்", "டூவீலர்", "இருசக்கர", "बाइक", "स्कूटर", "मोटरसाइकिल"
    ]):
        if any(k in clean for k in [
            "take", "ride", "drive", "safe", "should", "can i", "pogalama", "poga", "polama",
            "mudiyuma", "se jaana", "ja sakte", "ja sakta", "le jana", "chahiye",
            "போகலாமா", "போலாமா", "ஓட்டலாமா", "செல்லலாமா", "ले जाना", "जाना चाहिए", "जा सकते", "जा सकता"
        ]) or clean.endswith("bike?") or clean.endswith("bike pogalama?"):
            return IntentEnum.BIKE_TRAVEL, 0.95

    # 1d. Sports Activity Decision ("Can I play cricket?")
    if any(k in clean for k in [
        "cricket", "football", "match", "badminton", "tennis", "play", "game",
        "விளையாட", "கிரிக்கெட்", "விளையாட்டு", "क्रिकेट", "फुटबॉल", "खेल", "मैच"
    ]):
        if any(k in clean for k in [
            "can i play", "play", "khel sakte", "khel sakta", "khelna", "vilayada", "vilayadalama",
            "nadakkuma", "होगा", "நடக்குமா", "விளையாடலாமா", "खेल सकते", "खेल सकता", "खेलना", "खेल"
        ]):
            return IntentEnum.SPORTS_ACTIVITY, 0.95

    # 1e. Fishing Decision & Marine Trip ("Can I go fishing?", "Can fishermen venture out?")
    if any(k in clean for k in [
        "fishing", "fish", "meen", "மீன்", "மீன்பிடி", "machhli", "machli", "मछली", "fisherman", "fishermen"
    ]):
        if any(k in clean for k in [
            "can i", "go", "pogalama", "polama", "pakadne", "ja sakte", "ja sakta", "mudiyuma", "trip", "venture",
            "போகலாமா", "போலாமா", "செல்லலாமா", "पकड़ने", "पकड़ना", "जा सकते", "जा सकता"
        ]) or clean.startswith("can fishermen") or "venture" in clean:
            return IntentEnum.FISHING_DECISION, 0.95

    # 1f. Marine Safety & Coastal Warnings ("Is the sea safe?")
    if any(k in clean for k in [
        "marine", "sea", "ocean", "kadal", "கடல்", "கடலுக்கு", "கடலில்", "கடல", "samundar", "समुद्र", "coastal", "port signal"
    ]):
        if any(k in clean for k in [
            "safe", "rough", "wave", "waves", "seetram", "alert", "warning", "khatra", "சீற்றம்", "அலை", "खतरा"
        ]):
            return IntentEnum.MARINE_SAFETY, 0.94
        if any(k in clean for k in ["pogalama", "polama", "go", "ja sakte", "செல்லலாமா", "போகலாமா", "போலாமா", "venture", "fishermen", "fisherman"]):
            return IntentEnum.FISHING_DECISION, 0.93

    # 1g. Farming / Agriculture Decision ("Can I spray pesticide?")
    if any(k in clean for k in [
        "spray", "spraying", "pesticide", "fertilizer", "harvest", "harvesting", "sow",
        "sowing", "irrigation", "irrigate", "crop", "crops", "field", "farm", "farmer",
        "விவசாயம்", "பயிர்", "மருந்து", "தெளிக்கலாமா", "அறுவடை", "பாசனம்",
        "खेती", "दवाई", "छिड़काव", "सिंचाई", "फसल", "किसान"
    ]):
        return IntentEnum.FARMING_DECISION, 0.94

    # 1h. Clothing Advice ("What should I wear?")
    if any(k in clean for k in [
        "wear", "clothes", "jacket", "sweater", "raincoat", "warm clothes",
        "அணிய", "ஜாகெட்", "சுவெட்டர்", "ரெயின்கோட்", "உடை", "पहनना", "जैकेट", "स्वेटर", "रेनकोट"
    ]):
        return IntentEnum.CLOTHING_ADVICE, 0.93

    # 1i. Travel / Outstation Road Trip Decision ("Safe to travel?")
    if any(k in clean for k in [
        "travel", "trip", "drive to", "highway", "payanam", "பயணம்", "safar", "yatra", "यात्रा"
    ]):
        if any(k in clean for k in [
            "safe", "can i", "should i", "pogalama", "polama", "mudiyuma", "ja sakte", "jaana", "போகலாமா", "போலாமா"
        ]):
            return IntentEnum.TRAVEL_DECISION, 0.93

    # 1j. Outdoor Activity / General Going Out ("Can I go outside?")
    if any(k in clean for k in [
        "pogalama", "poga mudiyuma", "pogalaama", "polama", "can i go", "should i go",
        "safe to go", "go outside", "go out", "போகலாமா", "போலாமா", "செல்லலாமா",
        "ja sakte hain", "jaana chahiye", "bahar ja sakte", "jaana safe hai",
        "trip kar sakte", "बाहर जा सकते", "जाना चाहिए", "picnic", "பிக்னிக்"
    ]):
        return IntentEnum.OUTDOOR_ACTIVITY, 0.92

    # =========================================================================
    # 2. TIME-SPECIFIC WEATHER ("Will it rain when I come back?", "What about 5?")
    # =========================================================================
    is_time_query = (
        any(k in clean for k in [
            "when i come back", "when i return", "when returning", "when leaving", "come back",
            "return time", "reach home", "leave college", "leaving college", "during my commute",
            "office time", "when i leave", "thirumbi varumbodhu", "thirumbi varum pothu", "திரும்பி வரும்போது",
            "wapas aate", "वापस आते", "wapas aate waqt", "manikku", "baje"
        ])
        or bool(re.search(r"\b(?:what\s+about|how\s+about|around|at)?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.|baje|manikku|\?)\b", clean))
        or bool(re.search(r"\b\d{1,2}\s*(?:am|pm|baje|manikku)\b", clean))
    )
    if is_time_query:
        return IntentEnum.TIME_SPECIFIC_WEATHER, 0.94

    # 3. Cyclone & Emergency Alerts / Warning Query
    if any(k in clean for k in [
        "cyclone", "புயல்", "puyal", "storm alert", "super cyclone",
        "चक्रवात", "toofan", "tufan", "tufaan", "warning", "alert", "எச்சரிக்கை",
        "danger", "red alert", "orange alert", "चेतावनी", "khatra", "imd warning", "imd alert"
    ]):
        return IntentEnum.WARNING_QUERY, 0.94

    # 4. Historical & Climate Trends
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

    # 5. Rain & Precipitation Query
    if any(k in clean for k in [
        "rain", "raining", "drizzle", "shower", "மழை", "mazhai", "malai", "mazha",
        "baarish", "barish", "barsaat", "बारिश", "बरसात", "वर्षा"
    ]):
        return IntentEnum.RAIN_QUERY, 0.92

    # 6. Temperature & Heat Query
    if any(k in clean for k in [
        "temp", "temperature", "hot", "cold", "heat", "வெப்பநிலை", "veyil", "veiyil",
        "kulir", "garmi", "thand", "thandi", "sardi", "तापमान", "गर्मी", "ठंड"
    ]):
        return IntentEnum.TEMPERATURE_QUERY, 0.90

    # 7. Wind
    if any(k in clean for k in [
        "wind", "gust", "காற்று", "kaathu", "katru", "hawa", "हवा", "आंधी", "aandhi"
    ]):
        return IntentEnum.WIND, 0.88

    # 8. Humidity
    if any(k in clean for k in [
        "humidity", "humid", "ஈரப்பதம்", "eerapadham", "sweaty", "nami", "umas", "उमस", "नमी"
    ]):
        return IntentEnum.HUMIDITY, 0.88

    # 9. General Forecast Query (Tomorrow, Friday, Weekend)
    weekday_tokens = [
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "வெள்ளிக்கிழமை", "திங்கட்கிழமை", "செவ்வாய்க்கிழமை", "புதன்கிழமை", "வியாழக்கிழமை", "சனிக்கிழமை", "ஞாயிற்றுக்கிழமை",
        "velli", "vellikkizhamai", "thingal", "sevvai", "budhan", "vyazhan", "sani", "nyayiru",
        "शुक्रवार", "सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शनिवार", "रविवार",
        "shukrawar", "somwar", "mangalwar", "budhwar", "guruwar", "shaniwar", "raviwar"
    ]
    if any(k in clean for k in weekday_tokens) or any(k in clean for k in [
        "tomorrow", "naalaiku", "nalaiku", "நாளை", "next week", "forecast", "weekend",
        "kal", "parso", "agle hafte", "कल", "परसों"
    ]):
        return IntentEnum.FORECAST_QUERY, 0.88

    # 10. General Weather Information explicitly asked
    if "general weather" in clean or "overview" in clean:
        return IntentEnum.WEATHER_INFORMATION, 0.92

    # 11. Location-Specific Weather ("Weather in Chennai", "Weather conditions specifically in Tambaram")
    if any(k in clean for k in ["specifically in", "specifically at", "conditions specifically", "conditions in"]) or bool(re.search(r"\b(?:weather\s+in|forecast\s+for)\s+[A-Za-z]+", clean)):
        return IntentEnum.LOCATION_SPECIFIC_WEATHER, 0.88

    # 12. Current Weather / Weather Information (Now, Today, Kaisa hai, Epdi iruku)
    if any(k in clean for k in [
        "now", "right now", "today", "current", "இன்று", "inniku", "iniku", "ippo",
        "aaj", "abhi", "kaisa", "epdi", "आज", "अभी", "कैसा", "weather"
    ]):
        return IntentEnum.WEATHER_INFORMATION, 0.86

    return IntentEnum.GENERAL_WEATHER_QUESTION, 0.60
