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
    "tirunelveli": "Tirunelveli",
    "திருநெல்வேலி": "Tirunelveli",
    "तिरुनेलवेली": "Tirunelveli",
    "ooty": "Ooty",
    "ஊட்டி": "Ooty",
    "ऊटी": "Ooty",
    "udagamandalam": "Ooty",
    "vellore": "Vellore",
    "வேலூர்": "Vellore",
    "thanjavur": "Thanjavur",
    "தஞ்சாவூர்": "Thanjavur",
    "erode": "Erode",
    "ஈரோடு": "Erode",
    "dindigul": "Dindigul",
    "திண்டுக்கல்": "Dindigul",
    "kodaikanal": "Kodaikanal",
    "கொடைக்கானல்": "Kodaikanal",
    "cuddalore": "Cuddalore",
    "கடலூர்": "Cuddalore",
    "thoothukudi": "Thoothukudi",
    "tuticorin": "Thoothukudi",
    "தூத்துக்குடி": "Thoothukudi",
    "tiruppur": "Tiruppur",
    "திருப்பூர்": "Tiruppur",
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

    # Fallback: Prepositional location extraction (e.g. "in Salem", "about Madurai", "near Coimbatore")
    if not entities.location:
        prep_match = re.search(r"\b(?:in|at|for|near|about|to)\s+([A-Za-z]+)\b", text)
        if prep_match:
            candidate = prep_match.group(1).strip()
            excluded = {
                "the", "a", "an", "today", "tomorrow", "yesterday", "now", "me", "you", "us",
                "weather", "rain", "temperature", "temp", "morning", "afternoon", "evening",
                "night", "there", "it", "here", "this", "that"
            }
            if candidate.lower() not in excluded and len(candidate) >= 3:
                entities.location = candidate.capitalize()

    # 2. Relative Date Extraction
    year_match = re.search(r"\b(?:in|during|year)\s+(19\d\d|20[0-2]\d)\b", clean)
    if year_match:
        entities.date = year_match.group(1)
    elif any(k in clean for k in ["last year", "கடந்த ஆண்டு", "पिछले साल"]):
        entities.date = "last year"
    elif any(k in clean for k in ["previous years", "past years", "முந்தைய ஆண்டுகள்", "पिछले वर्षों"]):
        entities.date = "previous years"
    elif any(k in clean for k in ["last month", "கடந்த மாதம்", "पिछले महीने"]):
        entities.date = "last month"
    elif any(k in clean for k in ["this month", "இந்த மாதம்", "इस महीने"]):
        entities.date = "this month"
    elif any(k in clean for k in ["day after tomorrow", "parso", "நாளை மறுநாள்", "परसों"]):
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
    # Check for schedule pairs (e.g., "leave at 8 AM and return at 5 PM")
    dep_match = re.search(r"(?:leave|leaving|depart|departing|start|going)\s*(?:for\s+[a-z]+|from\s+[a-z]+|home)?\s*(?:at|by|around)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", clean)
    ret_match = re.search(r"(?:return|returning|come\s*back|coming\s*back|reach\s*home|leave\s*college|leave\s*office)\s*(?:at|by|around)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", clean)

    all_time_tokens = [m.group(1).upper().strip() for m in re.finditer(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", clean, re.IGNORECASE)]

    if dep_match and ret_match and dep_match.group(1) and ret_match.group(1):
        entities.departure_time = dep_match.group(1).upper().strip()
        entities.return_time = ret_match.group(1).upper().strip()
        entities.time = entities.departure_time
        entities.time_range = f"{entities.departure_time}-{entities.return_time}"
    elif len(all_time_tokens) >= 2 and any(k in clean for k in ["leave", "return", "commute", "college", "office", "back"]):
        entities.departure_time = all_time_tokens[0]
        entities.return_time = all_time_tokens[1]
        entities.time = entities.departure_time
        entities.time_range = f"{entities.departure_time}-{entities.return_time}"
    elif len(all_time_tokens) == 1:
        single_t = all_time_tokens[0]
        if any(k in clean for k in ["return", "leave college", "leave office", "come back"]):
            entities.return_time = single_t
            entities.time = single_t
            entities.time_range = single_t
        else:
            entities.time = single_t
            entities.time_range = single_t
    else:
        time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", clean)
        if time_match and any(x in clean for x in ["am", "pm", ":"]):
            entities.time = time_match.group(1).upper().strip()
            entities.time_range = entities.time
        elif any(k in clean for k in ["leave college", "leaving college", "after college"]):
            entities.time = "evening"
            entities.time_range = "17:00-21:00"
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
    if any(k in clean for k in ["rain", "mazhai", "மழை", "barish", "baarish", "बारिश", "drizzle", "umbrella"]):
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
        "college", "school", "exam", "student", "பள்ளி", "கல்லூரி", "padhai", "padipu",
        "leave college", "reach college", "campus"
    ]):
        entities.persona = PersonaEnum.STUDENT
        entities.activity = "college/school commute"
    elif any(k in clean for k in [
        "fishing", "kadal", "marine", "boat", "மீன்பிடி", "கடல்", "fisherman", "machli", "machuara",
        "deep sea", "sea-safety", "coastal warning"
    ]):
        entities.persona = PersonaEnum.FISHERMAN
        entities.activity = "marine fishing trip"
    elif any(k in clean for k in [
        "farmer", "crop", "agriculture", "விவசாயி", "பயிர்", "irrigation", "kisan", "kheti", "fasal",
        "field", "spraying", "pesticide", "fertilizer", "harvest"
    ]):
        entities.persona = PersonaEnum.FARMER
        entities.activity = "farming & irrigation"
    elif any(k in clean for k in [
        "rescue", "disaster", "evacuate", "relief", "rahat", "बचाव", "emergency", "sdrf", "ndrf",
        "mobilization", "safety instructions"
    ]):
        entities.persona = PersonaEnum.DISASTER_RESPONSE
        entities.activity = "disaster management"
    elif any(k in clean for k in [
        "office", "commute", "metro", "bus", "train", "workplace", "daily commute", "transit",
        "traffic", "travel period"
    ]):
        entities.persona = PersonaEnum.COMMUTER
        entities.activity = "daily commute"
    elif any(k in clean for k in [
        "travel", "drive", "trip", "highway", "பயணம்", "safar", "yatra", "tour", "flight"
    ]):
        entities.persona = PersonaEnum.TRAVELLER
        entities.activity = "travel"

    return entities

