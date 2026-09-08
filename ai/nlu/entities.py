"""Entity Extraction Module for WeatherGPT.

Extracts location, date, time, weather variables, persona,
and activity from natural language queries (English, Tamil, Tanglish).
"""

import re
from typing import Optional
from ai.models import ExtractedEntities, PersonaEnum

# Standard Indian city mappings
KNOWN_LOCATIONS = {
    "coimbatore": "Coimbatore",
    "கோயம்புத்தூர்": "Coimbatore",
    "kovai": "Coimbatore",
    "chennai": "Chennai",
    "சென்னை": "Chennai",
    "madras": "Chennai",
    "nagapattinam": "Nagapattinam",
    "நாகப்பட்டினம்": "Nagapattinam",
    "madurai": "Madurai",
    "மதுரை": "Madurai",
    "salem": "Salem",
    "சேலம்": "Salem",
    "tiruchirappalli": "Tiruchirappalli",
    "trichy": "Tiruchirappalli",
    "திருச்சி": "Tiruchirappalli",
    "delhi": "Delhi",
    "mumbai": "Mumbai",
    "bengaluru": "Bengaluru",
    "bangalore": "Bengaluru",
    "hyderabad": "Hyderabad",
    "kolkata": "Kolkata",
    "kanyakumari": "Kanyakumari"
}


def extract_entities(text: str) -> ExtractedEntities:
    """Extracts entities from user query string."""
    clean = text.lower()
    entities = ExtractedEntities()

    # 1. Location Extraction
    for loc_key, canonical_name in KNOWN_LOCATIONS.items():
        if re.search(rf"\b{re.escape(loc_key)}(?:-la|la|le)?\b", clean):
            entities.location = canonical_name
            break

    # 2. Date Extraction
    if any(k in clean for k in ["tomorrow", "naalaiku", "nalaiku", "நாளை", "kal"]):
        entities.date = "tomorrow"
    elif any(k in clean for k in ["today", "inniku", "iniku", "இன்று", "aaj", "now", "ippo"]):
        entities.date = "today"
    elif any(k in clean for k in ["yesterday", "netru", "நேற்று"]):
        entities.date = "yesterday"

    # 3. Time Extraction
    time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", clean)
    if time_match and any(x in clean for x in ["am", "pm", ":"]):
        entities.time = time_match.group(1).upper()
    elif any(k in clean for k in ["morning", "kaalai", "காலை", "subah"]):
        entities.time = "morning"
    elif any(k in clean for k in ["afternoon", "madhiyam", "மதியம்"]):
        entities.time = "afternoon"
    elif any(k in clean for k in ["evening", "maalai", "மாலை", "shaam"]):
        entities.time = "evening"
    elif any(k in clean for k in ["night", "iravu", "இரவு", "raat"]):
        entities.time = "night"

    # 4. Persona & Activity
    if any(k in clean for k in ["college", "school", "exam", "student", "பள்ளி", "கல்லூரி"]):
        entities.persona = PersonaEnum.STUDENT
        entities.activity = "college/school commute"
    elif any(k in clean for k in ["fishing", "kadal", "marine", "boat", "மீன்பிடி", "கடல்", "fisherman"]):
        entities.persona = PersonaEnum.FISHERMAN
        entities.activity = "marine fishing trip"
    elif any(k in clean for k in ["farmer", "crop", "agriculture", "விவசாயி", "பயிர்", "irrigation"]):
        entities.persona = PersonaEnum.FARMER
        entities.activity = "farming & irrigation"
    elif any(k in clean for k in ["travel", "drive", "trip", "highway", "பயணம்"]):
        entities.persona = PersonaEnum.TRAVELLER
        entities.activity = "travel"
    elif any(k in clean for k in ["rescue", "disaster", "evacuate", "relief"]):
        entities.persona = PersonaEnum.DISASTER_RESPONSE
        entities.activity = "disaster management"

    # 5. Weather Variable
    if any(k in clean for k in ["rain", "mazhai", "மழை", "shower"]):
        entities.weather_variable = "rainfall"
    elif any(k in clean for k in ["wind", "katru", "காற்று", "gust"]):
        entities.weather_variable = "wind"
    elif any(k in clean for k in ["temp", "heat", "hot", "cold", "வெப்பநிலை"]):
        entities.weather_variable = "temperature"
    elif any(k in clean for k in ["humidity", "ஈரப்பதம்"]):
        entities.weather_variable = "humidity"

    return entities
