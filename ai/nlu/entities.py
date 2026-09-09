"""Entity Extraction Module for WeatherGPT NLU.

Extracts locations, relative dates, normalized time ranges,
weather variables, detected hazards, personas, and activities.
"""

import re
from typing import Optional, Tuple
from ai.models import ExtractedEntities, PersonaEnum

# Standard Indian locations mapping (English, Tamil, Hindi, transliterations)
KNOWN_LOCATIONS = {
    # Tamil Nadu
    "coimbatore": "Coimbatore",
    "கோயம்புத்தூர்": "Coimbatore",
    "கோயம்புத்தூரில்": "Coimbatore",
    "kovai": "Coimbatore",
    "कोयंबटूर": "Coimbatore",
    "chennai": "Chennai",
    "சென்னை": "Chennai",
    "சென்னையில்": "Chennai",
    "madras": "Chennai",
    "चेन्नई": "Chennai",
    "nagapattinam": "Nagapattinam",
    "நாகப்பட்டினம்": "Nagapattinam",
    "நாகப்பட்டினத்தில்": "Nagapattinam",
    "नागपट्टिनम": "Nagapattinam",
    "madurai": "Madurai",
    "மதுரை": "Madurai",
    "मदुरै": "Madurai",
    "salem": "Salem",
    "சேலம்": "Salem",
    "सलेम": "Salem",
    "tiruchirappalli": "Tiruchirappalli",
    "trichy": "Tiruchirappalli",
    "திருச்சி": "Tiruchirappalli",
    "तिरुचिरापल्ली": "Tiruchirappalli",
    "kanyakumari": "Kanyakumari",
    "கன்னியாகுமரி": "Kanyakumari",
    # Major Metros & States
    "delhi": "Delhi",
    "டெல்லி": "Delhi",
    "दिल्ली": "Delhi",
    "mumbai": "Mumbai",
    "bombay": "Mumbai",
    "மும்பை": "Mumbai",
    "मुंबई": "Mumbai",
    "bengaluru": "Bengaluru",
    "bangalore": "Bengaluru",
    "பெங்களூரு": "Bengaluru",
    "बैंगलोर": "Bengaluru",
    "hyderabad": "Hyderabad",
    "ஹைதராபாத்": "Hyderabad",
    "हैदराबाद": "Hyderabad",
    "kolkata": "Kolkata",
    "கொல்கத்தா": "Kolkata",
    "कोलकाता": "Kolkata",
    "pune": "Pune",
    "पुणे": "Pune",
    "jaipur": "Jaipur",
    "जयपुर": "Jaipur"
}


def extract_entities(text: str) -> ExtractedEntities:
    """Extracts structured entities from user query string."""
    clean = text.lower().strip()
    entities = ExtractedEntities()

    # 1. Location Candidate Extraction
    # Sort keys by descending length to match more specific/longer terms first
    for loc_key in sorted(KNOWN_LOCATIONS.keys(), key=len, reverse=True):
        canonical_name = KNOWN_LOCATIONS[loc_key]
        if loc_key.isascii():
            pattern = rf"\b{re.escape(loc_key)}(?:-la|la|le|mein|me|ka|ki)?\b"
            if re.search(pattern, clean):
                entities.location = canonical_name
                break
        else:
            # Indic / Unicode scripts: substring match naturally handles case inflections (-இல், -க்கு, में, का)
            if loc_key in clean:
                entities.location = canonical_name
                break

    # 2. Relative Date Extraction
    if any(k in clean for k in ["day after tomorrow", "parso", "நாளை மறுநாள்", "परसों"]):
        entities.date = "day after tomorrow"
    elif any(k in clean for k in ["tomorrow", "naalaiku", "nalaiku", "naalaikku", "நாளை", "kal", "कल"]):
        entities.date = "tomorrow"
    elif any(k in clean for k in ["today", "inniku", "iniku", "இன்று", "இன்னைக்கு", "aaj", "आज", "now", "ippo", "abhi"]):
        entities.date = "today"
    elif any(k in clean for k in ["yesterday", "netru", "நேற்று", "beeta kal", "बीता कल"]):
        entities.date = "yesterday"
    elif any(k in clean for k in ["this weekend", "weekend", "hafte ke ant"]):
        entities.date = "this weekend"
    elif any(k in clean for k in ["next week", "adutha vaaram", "agle hafte", "अगले हफ्ते"]):
        entities.date = "next week"

    # 3. Relative Time & Time Range Normalization
    time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", clean)
    if time_match and any(x in clean for x in ["am", "pm", ":"]):
        entities.time = time_match.group(1).upper()
        entities.time_range = entities.time
    elif any(k in clean for k in ["morning", "kaalai", "காலை", "subah", "सुबह"]):
        entities.time = "morning"
        entities.time_range = "06:00-12:00"
    elif any(k in clean for k in ["afternoon", "madhiyam", "மதியம்", "dophar", "दोपहर"]):
        entities.time = "afternoon"
        entities.time_range = "12:00-17:00"
    elif any(k in clean for k in ["evening", "maalai", "மாலை", "shaam", "sham", "शाम"]):
        entities.time = "evening"
        entities.time_range = "17:00-21:00"
    elif any(k in clean for k in ["night", "iravu", "இரவு", "raat", "रात"]):
        entities.time = "night"
        entities.time_range = "21:00-06:00"

    # 4. Weather Variable & Specific Hazard Extraction
    if any(k in clean for k in ["rain", "mazhai", "மழை", "barish", "baarish", "बारिश", "drizzle"]):
        entities.weather_variable = "rainfall"
    elif any(k in clean for k in ["wind", "katru", "காற்று", "hawa", "हवा", "gust"]):
        entities.weather_variable = "wind"
    elif any(k in clean for k in ["temp", "heat", "hot", "cold", "வெப்பநிலை", "garmi", "thand", "तापमान"]):
        entities.weather_variable = "temperature"
    elif any(k in clean for k in ["humidity", "ஈரப்பதம்", "nami", "umas", "नमी"]):
        entities.weather_variable = "humidity"

    if any(k in clean for k in ["cyclone", "puyal", "புயல்", "chakravaat", "toofan", "चक्रवात"]):
        entities.hazard = "cyclone"
    elif any(k in clean for k in ["heavy rain", "flood", "vellam", "கனமழை", "बाढ़", "भारी बारिश"]):
        entities.hazard = "heavy_rainfall"
    elif any(k in clean for k in ["heatwave", "loo", "வெப்ப அலை", "लू"]):
        entities.hazard = "heatwave"
    elif any(k in clean for k in ["thunder", "lightning", "இடி", "மின்னல்", "बिजली"]):
        entities.hazard = "thunderstorm"

    # 5. Persona & Activity Identification
    if any(k in clean for k in [
        "college", "school", "exam", "student", "பள்ளி", "கல்லூரி", "padhai", "padipu"
    ]):
        entities.persona = PersonaEnum.STUDENT
        entities.activity = "college/school commute"
    elif any(k in clean for k in [
        "fishing", "kadal", "marine", "boat", "மீன்பிடி", "கடல்", "fisherman", "machli", "machuara"
    ]):
        entities.persona = PersonaEnum.FISHERMAN
        entities.activity = "marine fishing trip"
    elif any(k in clean for k in [
        "farmer", "crop", "agriculture", "விவசாயி", "பயிர்", "irrigation", "kisan", "kheti", "fasal"
    ]):
        entities.persona = PersonaEnum.FARMER
        entities.activity = "farming & irrigation"
    elif any(k in clean for k in [
        "travel", "drive", "trip", "highway", "பயணம்", "safar", "yatra", "tour"
    ]):
        entities.persona = PersonaEnum.TRAVELLER
        entities.activity = "travel"
    elif any(k in clean for k in [
        "rescue", "disaster", "evacuate", "relief", "rahat", "बचाव"
    ]):
        entities.persona = PersonaEnum.DISASTER_RESPONSE
        entities.activity = "disaster management"
    elif any(k in clean for k in [
        "office", "commute", "metro", "bus", "train", "workplace", "daily commute"
    ]):
        entities.persona = PersonaEnum.COMMUTER
        entities.activity = "daily commute"

    return entities

