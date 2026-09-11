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
    matched_locations = []
    # Sort keys by descending length to match more specific/longer terms first
    for loc_key in sorted(KNOWN_LOCATIONS.keys(), key=len, reverse=True):
        canonical_name = KNOWN_LOCATIONS[loc_key]
        if loc_key.isascii():
            pattern = rf"\b{re.escape(loc_key)}(?:-la|la|le|mein|me|ka|ki)?\b"
            if re.search(pattern, clean):
                if canonical_name not in matched_locations:
                    matched_locations.append(canonical_name)
        else:
            # Indic / Unicode scripts: substring match naturally handles case inflections (-இல், -க்கு, में, का)
            if loc_key in clean:
                if canonical_name not in matched_locations:
                    matched_locations.append(canonical_name)

    if matched_locations:
        entities.location = matched_locations[0]
        entities.locations = matched_locations

    # Fallback: Prepositional location extraction (e.g. "in Salem", "about Madurai", "near Coimbatore")
    if not entities.location:
        prep_match = re.search(r"\b(?:in|at|for|near|about|to)\s+([A-Za-z]+)\b", text)
        if prep_match:
            candidate = prep_match.group(1).strip()
            excluded = {
                "the", "a", "an", "today", "tomorrow", "yesterday", "now", "me", "you", "us",
                "weather", "rain", "temperature", "temp", "morning", "afternoon", "evening",
                "night", "there", "it", "here", "this", "that", "college", "school", "work", "office",
                "when", "how", "what", "where", "who", "which", "why", "my", "your", "our", "his", "her", "their",
                "leave", "leaving", "come", "coming", "go", "going", "return", "trip", "bike", "car", "bus", "train", "drive",
                "sea", "ocean", "beach", "coast", "lake", "river"
            }
            if candidate.lower() not in excluded and len(candidate) >= 3:
                entities.location = candidate.capitalize()
                entities.locations = [entities.location]

    # 2. Date & Weekday Extraction
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
    else:
        # Weekday detection (English, Tamil, Hindi)
        weekday_map = {
            "monday": "Monday", "திங்கட்கிழமை": "Monday", "திங்கள்": "Monday", "सोमवार": "Monday", "somwar": "Monday",
            "tuesday": "Tuesday", "செவ்வாய்க்கிழமை": "Tuesday", "செவ்வாய்": "Tuesday", "मंगलवार": "Tuesday", "mangalwar": "Tuesday",
            "wednesday": "Wednesday", "புதன்கிழமை": "Wednesday", "புதன்": "Wednesday", "बुधवार": "Wednesday", "budhwar": "Wednesday",
            "thursday": "Thursday", "வியாழக்கிழமை": "Thursday", "வியாழன்": "Thursday", "गुरुवार": "Thursday", "guruwar": "Thursday",
            "friday": "Friday", "வெள்ளிக்கிழமை": "Friday", "வெள்ளி": "Friday", "शुक्रवार": "Friday", "shukrawar": "Friday",
            "saturday": "Saturday", "சனிக்கிழமை": "Saturday", "சனி": "Saturday", "शनिवार": "Saturday", "shaniwar": "Saturday",
            "sunday": "Sunday", "ஞாயிற்றுக்கிழமை": "Sunday", "ஞாயிறு": "Sunday", "रविवार": "Sunday", "raviwar": "Sunday"
        }
        for day_kw, day_name in weekday_map.items():
            if re.search(rf"\b{re.escape(day_kw)}\b", clean):
                entities.date = day_name
                break

    # 3. Relative Time & Time Range Normalization
    # Check for schedule pairs (e.g., "leave at 8 AM and return at 5 PM")
    dep_match = re.search(r"(?:leave|leaving|depart|departing|start|going)\s*(?:for\s+[a-z]+|from\s+[a-z]+|home)?\s*(?:at|by|around)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", clean)
    ret_match = re.search(r"(?:return|returning|come\s*back|coming\s*back|reach\s*home|leave\s*college|leave\s*office)\s*(?:at|by|around)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", clean)

    all_time_tokens = [m.group(1).upper().strip() for m in re.finditer(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", clean, re.IGNORECASE)]

    range_match = re.search(r"(?:between|from)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+(?:and|to|-)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", clean)

    if dep_match and ret_match and dep_match.group(1) and ret_match.group(1):
        entities.departure_time = dep_match.group(1).upper().strip()
        entities.return_time = ret_match.group(1).upper().strip()
        entities.time = entities.departure_time
        entities.time_range = f"{entities.departure_time}-{entities.return_time}"
    elif range_match:
        entities.departure_time = range_match.group(1).upper().strip()
        entities.return_time = range_match.group(2).upper().strip()
        entities.time = entities.departure_time
        entities.time_range = f"{entities.departure_time}-{entities.return_time}"
    elif len(all_time_tokens) >= 2:
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
    elif any(k in clean for k in ["when i come back", "when i return", "thirumbi varumbodhu", "திரும்பி வரும்போது", "wapas aate", "वापस आते"]):
        entities.time = "return window"
        entities.return_time = "return window"
        entities.time_range = "transit return"
        entities.reference_expression = "when returning"
        if not entities.person_context:
            entities.person_context = "commuter"
    else:
        # Numeric time like "at 5", "what about 5", "5 PM", "5 baje", "5 manikku"
        num_time_match = re.search(r"\b(?:what\s+about|how\s+about|at|around|by|from|till|to)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje|manikku|\?)?\b", clean)
        if num_time_match and (num_time_match.group(3) or any(k in clean for k in ["at", "about", "around", "what about 5", "5?"])):
            h = num_time_match.group(1)
            m = num_time_match.group(2) or "00"
            entities.time = f"{h}:{m}"
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

    # 5. Transport Mode Extraction
    if any(k in clean for k in ["bike", "motorcycle", "scooter", "two wheeler", "two-wheeler", "cycle", "bicycle", "பைக்", "இருசக்கர", "டூவீலர்", "बाइक", "स्कूटर", "मोटरसाइकिल"]):
        entities.transport_mode = "bike"
    elif any(k in clean for k in ["car", "cab", "taxi", "கார்", "டாக்சி", "कार", "गाड़ी"]):
        entities.transport_mode = "car"
    elif any(k in clean for k in ["bus", "பேருந்து", "बस"]):
        entities.transport_mode = "bus"
    elif any(k in clean for k in ["train", "metro", "rail", "ரயில்", "ரெயில்", "மெட்ரோ", "ट्रेन", "मेट्रो"]):
        entities.transport_mode = "train"
    elif any(k in clean for k in ["walk", "walking", "pedestrian", "நடந்து", "पैदल"]):
        entities.transport_mode = "walk"
    elif any(k in clean for k in ["boat", "ferry", "ship", "படகு", "नाव"]):
        entities.transport_mode = "boat"

    # 6. Reference Expression Extraction
    for ref_pat, ref_val in [
        (r"\bwhen\s+i\s+come\s+back\b", "when I come back"),
        (r"\bwhen\s+i\s+return\b", "when I return"),
        (r"\bwhen\s+leaving\b", "when leaving"),
        (r"\bthirumbi\s+varumbodhu\b", "when returning"),
        (r"திரும்பி\s*வரும்போது", "when returning"),
        (r"\bwapas\s+aate\s*(?:waqt|samay)?\b", "when returning"),
        (r"वापस\s*आते\s*समय", "when returning"),
        (r"\band\s+friday\??\b", "And Friday?"),
        (r"\bwhat\s+about\s+5\??\b", "What about 5?"),
        (r"\bthere\b", "there"),
        (r"\bthat\s+place\b", "that place"),
        (r"\bsame\s+place\b", "same place"),
        (r"அங்கே", "there"),
        (r"அங்க", "there"),
        (r"वहाँ", "there"),
        (r"वहां", "there")
    ]:
        if re.search(ref_pat, clean, re.IGNORECASE):
            entities.reference_expression = ref_val
            break

    # 7. Decision & Comparison Wording Extraction
    decision_kws = sorted([
        "can i go", "can i play", "can i travel", "can i ride", "can i do", "can i",
        "should i take", "should i go", "should i ride", "should i",
        "do i need", "is it safe to", "is it safe", "can we", "could i",
        "better to", "allowed to", "need to",
        "போகலாமா", "போலாமா", "விளையாடலாமா", "செல்லலாமா", "தேவையா", "வேணுமா", "எடுக்கலாமா", "செய்யலாமா",
        "क्या मैं", "क्या मुझे", "जाना चाहिए", "जा सकते हैं", "सकते हैं", "चाहिए", "खेल सकते हैं"
    ], key=len, reverse=True)
    for dec_kw in decision_kws:
        if dec_kw in clean:
            entities.decision_wording = dec_kw
            break

    for comp_kw in [
        "which is cooler", "which is warmer", "which is hotter", "compare", "versus", " vs ",
        "விட", "தவிர", "तुलना"
    ]:
        if comp_kw in clean:
            entities.comparison_wording = comp_kw
            break

    # 8. Persona & Activity Identification
    if any(k in clean for k in ["college", "school", "exam", "student", "பள்ளி", "கல்லூரி", "padhai", "padipu", "leave college", "reach college", "campus"]):
        entities.persona = PersonaEnum.STUDENT
        entities.person_context = "student"
        entities.activity = "college"
    elif any(k in clean for k in ["cricket", "football", "badminton", "match", "sports", "கிரிக்கெட்", "விளையாட", "क्रिकेट", "मैच"]):
        entities.activity = "cricket" if "cricket" in clean or "கிரிக்கெட்" in clean or "क्रिकेट" in clean else "sports"
        entities.person_context = "athlete"
    elif any(k in clean for k in ["fishing", "kadal", "marine", "boat", "மீன்பிடி", "கடல்", "fisherman", "machli", "machuara", "deep sea", "sea-safety", "coastal warning"]):
        entities.persona = PersonaEnum.FISHERMAN
        entities.person_context = "fisherman"
        entities.activity = "fishing"
    elif any(k in clean for k in ["farmer", "crop", "agriculture", "விவசாயி", "பயிர்", "irrigation", "kisan", "kheti", "fasal", "field", "spraying", "pesticide", "fertilizer", "harvest"]):
        entities.persona = PersonaEnum.FARMER
        entities.person_context = "farmer"
        entities.activity = "farming"
    elif any(k in clean for k in ["rescue", "disaster", "evacuate", "relief", "rahat", "बचाव", "emergency", "sdrf", "ndrf", "mobilization", "safety instructions"]):
        entities.persona = PersonaEnum.DISASTER_RESPONSE
        entities.person_context = "disaster_response"
        entities.activity = "disaster management"
    elif any(k in clean for k in ["bike", "ride", "scooter"]):
        entities.activity = "bike travel"
        entities.person_context = "commuter"
        entities.persona = PersonaEnum.COMMUTER
    elif any(k in clean for k in ["umbrella", "kudai", "குடை", "chhata"]):
        entities.activity = "umbrella"
        entities.person_context = "commuter"
    elif any(k in clean for k in ["office", "commute", "metro", "bus", "train", "workplace", "daily commute", "transit", "traffic", "travel period"]):
        entities.persona = PersonaEnum.COMMUTER
        entities.person_context = "commuter"
        entities.activity = "commute"
    elif any(k in clean for k in ["travel", "drive", "trip", "highway", "பயணம்", "safar", "yatra", "tour", "flight"]):
        entities.persona = PersonaEnum.TRAVELLER
        entities.person_context = "traveller"
        entities.activity = "travel"

    return entities

