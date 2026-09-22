"""Query Domain Classifier and Hybrid Query Decomposition for WeatherGPT.

Classifies incoming user queries into one of four operational domains:
1. PURE_GREETING: Social greetings (hello, namaste, vanakkam).
2. PURE_GENERAL: Informational, scientific, definitional, or general knowledge
   (e.g., "what is monsoon season", "who wrote Hamlet", "what is photosynthesis").
3. PURE_WEATHER: Action decisions and live meteorological telemetry
   (e.g., "should I take my bike today", "do I need an umbrella", "rain in Chennai").
4. HYBRID: Combined questions containing both general knowledge and live/forecast weather
   (e.g., "what's the capital of Tamil Nadu and will it rain there today").
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
from ai.models import IntentEnum


class QueryDomain(str, Enum):
    PURE_GREETING = "pure_greeting"
    PURE_GENERAL = "pure_general"
    PURE_WEATHER = "pure_weather"
    HYBRID = "hybrid"


@dataclass
class QueryDomainResult:
    domain: QueryDomain
    general_subquery: Optional[str] = None
    weather_subquery: Optional[str] = None
    inferred_location: Optional[str] = None
    original_query: str = ""


# Known state/country capital mappings for zero-latency deterministic entity resolution
CAPITAL_MAP = {
    "tamil nadu": "Chennai",
    "tamilnadu": "Chennai",
    "karnataka": "Bengaluru",
    "kerala": "Thiruvananthapuram",
    "andhra pradesh": "Amaravati",
    "andhra": "Amaravati",
    "telangana": "Hyderabad",
    "maharashtra": "Mumbai",
    "gujarat": "Gandhinagar",
    "rajasthan": "Jaipur",
    "west bengal": "Kolkata",
    "bengal": "Kolkata",
    "uttar pradesh": "Lucknow",
    "madhya pradesh": "Bhopal",
    "bihar": "Patna",
    "punjab": "Chandigarh",
    "haryana": "Chandigarh",
    "odisha": "Bhubaneswar",
    "orissa": "Bhubaneswar",
    "assam": "Dispur",
    "goa": "Panaji",
    "delhi": "New Delhi",
    "india": "New Delhi",
    "france": "Paris",
    "united kingdom": "London",
    "uk": "London",
    "england": "London",
    "united states": "Washington, D.C.",
    "usa": "Washington, D.C.",
    "japan": "Tokyo",
    "germany": "Berlin",
    "italy": "Rome",
    "australia": "Canberra",
    "canada": "Ottawa",
    "russia": "Moscow",
    "china": "Beijing",
}

# Major cities recognized for location inference
KNOWN_CITIES = [
    "chennai", "coimbatore", "madurai", "tiruchirappalli", "trichy", "salem",
    "tirunelveli", "tiruppur", "vellore", "erode", "thoothukudi", "dindigul",
    "thanjavur", "ranipet", "sivakasi", "karur", "ooty", "kodaikanal", "hosur",
    "bengaluru", "bangalore", "delhi", "new delhi", "mumbai", "kolkata", "hyderabad",
    "kochi", "thiruvananthapuram", "pune", "ahmedabad", "jaipur", "lucknow", "kanpur",
    "nagpur", "indore", "bhopal", "patna", "vadodara", "ghaziabad", "ludhiana", "agra",
    "nashik", "faridabad", "meerut", "rajkot", "varanasi", "srinagar", "aurangabad",
    "dhanbad", "amritsar", "navi mumbai", "allahabad", "prayagraj", "howrah", "gwalior",
    "jabalpur", "vijayawada", "jodhpur", "raipur", "kota", "guwahati", "chandigarh"
]

GREETING_TOKENS = {
    "hello", "hi", "hey", "vanakkam", "வணக்கம்", "namaste", "नमस्ते",
    "good morning", "good evening", "good afternoon", "halo", "ola",
    "how are you", "who are you", "who are u", "eppadi irukinga", "kaise ho",
    "how do you do", "namaskar", "namaskaram"
}

WEATHER_ACTION_INTENTS = {
    IntentEnum.UMBRELLA_DECISION,
    IntentEnum.COLLEGE_COMMUTE,
    IntentEnum.BIKE_TRAVEL,
    IntentEnum.SPORTS_ACTIVITY,
    IntentEnum.FISHING_DECISION,
    IntentEnum.MARINE_SAFETY,
    IntentEnum.FARMING_DECISION,
    IntentEnum.CLOTHING_ADVICE,
    IntentEnum.TRAVEL_DECISION,
    IntentEnum.OUTDOOR_ACTIVITY,
    IntentEnum.RAIN_QUERY,
    IntentEnum.RAIN_FORECAST,
    IntentEnum.TEMPERATURE,
    IntentEnum.TEMPERATURE_QUERY,
    IntentEnum.WIND,
    IntentEnum.HUMIDITY,
    IntentEnum.FORECAST_QUERY,
    IntentEnum.CURRENT_WEATHER,
    IntentEnum.WEATHER_INFORMATION,
    IntentEnum.LOCATION_SPECIFIC_WEATHER,
    IntentEnum.TIME_SPECIFIC_WEATHER,
    IntentEnum.WEATHER_ALERT,
    IntentEnum.WARNING_QUERY,
    IntentEnum.AIR_QUALITY,
    IntentEnum.AQI_QUERY,
    IntentEnum.LOCATION_COMPARISON,
    IntentEnum.WEATHER_EXPLANATION,
}

WEATHER_KEYWORDS = [
    "rain", "raining", "rainy", "drizzle", "shower", "umbrella", "bike", "motorcycle",
    "commute", "travel", "college", "fishing", "marine", "sea", "rough sea", "temperature",
    "forecast", "aqi", "air quality", "wind", "humidity", "hot", "cold", "heat wave",
    "cyclone", "storm", "thunderstorm", "cloudy", "sunny", "weather",
    "மழை", "குடை", "பைக்", "வானிலை", "வெப்பநிலை", "காற்று",
    "बारिश", "छाता", "बाइक", "मौसम", "तापमान", "हवा"
]

LIVE_TEMPORAL_KEYWORDS = [
    "today", "tomorrow", "tonight", "right now", "now", "current", "currently",
    "this morning", "this evening", "this afternoon", "next few hours", "weekend",
    "இன்று", "நாளை", "இப்போது", "आज", "कल", "अभी"
]


def resolve_inferred_location(text: str) -> Optional[str]:
    """Resolves location entity from explicit names or descriptive state capital references."""
    clean = text.lower().strip()

    # 1. State capital resolution: e.g. "capital of Tamil Nadu" -> "Chennai"
    cap_match = re.search(r"capital\s+of\s+([a-zA-Z\s]+?)(?:\s+and|\s*,|\s*\?|$)", clean)
    if cap_match:
        state_candidate = cap_match.group(1).strip().lower()
        if state_candidate in CAPITAL_MAP:
            return CAPITAL_MAP[state_candidate]
        for state, cap in CAPITAL_MAP.items():
            if state in state_candidate:
                return cap

    # 2. Direct city mention in text
    for city in KNOWN_CITIES:
        pattern = r"\b" + re.escape(city) + r"\b"
        if re.search(pattern, clean):
            return city.capitalize()

    return None


def is_conceptual_definition(clean: str) -> bool:
    """Detects if a question is asking for definitions, explanations, or general science."""
    # Must not have action decisions, live temporal keywords, locations, or live weather inquiries
    has_live_temporal = any(re.search(r"\b" + re.escape(t) + r"\b", clean) for t in LIVE_TEMPORAL_KEYWORDS)
    has_action_request = any(k in clean for k in [
        "should i", "can i", "is it safe", "do i need", "pogalama", "polama", "ja sakte",
        "chahiye", "need an umbrella", "take my bike", "go to college"
    ])
    has_location_or_weather = bool(
        resolve_inferred_location(clean)
        or re.search(r"\b(?:weather|temperature|temp|forecast|rain|aqi|air quality|climate|humidity|wind)\s+(?:in|at|for|like|near)\b", clean)
        or re.search(r"\b(?:current\s+weather|current\s+temperature|current\s+temp|weather\s+today|weather\s+like|weather\s+report)\b", clean)
        or re.search(r"\b(?:in|at)\s+(?:chennai|coimbatore|madurai|delhi|mumbai|bangalore|salem|trichy|ooty|kolkata|hyderabad|pune)\b", clean)
    )
    if has_live_temporal or has_action_request or has_location_or_weather:
        return False

    # Definitional inquiries with weather terms (e.g. "monsoon season", "el nino", "greenhouse effect")
    conceptual_terms = [
        "what is monsoon", "what is a monsoon", "what is monsoon season", "what are monsoons",
        "how does monsoon work", "how do clouds form", "how do rainbows form", "what is a cyclone",
        "what is el nino", "what is la nina", "what is global warming", "what is the ozone layer"
    ]
    if any(k in clean for k in conceptual_terms):
        return True

    # Definitional starters
    conceptual_starters = (
        "what is ", "what are ", "what is a ", "what is an ", "what's a ", "what's an ",
        "define ", "definition of ", "how does ", "how do ", "how is ", "why is the ",
        "why do ", "why are ", "explain ", "what causes ", "what makes ", "history of ",
        "tell me about "
    )
    if clean.startswith(conceptual_starters):
        # Exclude queries mentioning meteorological terms
        if any(w in clean for w in ["weather", "temperature", "temp", "rain", "wind", "humidity", "aqi", "air quality", "forecast"]):
            return False
        return True

    return False


def classify_query_domain(text: str, nlu_intent: Optional[IntentEnum] = None) -> QueryDomainResult:
    """Classifies user query into PURE_GREETING, PURE_GENERAL, PURE_WEATHER, or HYBRID."""
    if not text or not text.strip():
        return QueryDomainResult(domain=QueryDomain.PURE_GREETING, original_query=text or "")

    clean = text.lower().strip()

    # 1. PURE GREETING
    intent_val = getattr(nlu_intent, "value", str(nlu_intent)) if nlu_intent else ""
    if clean in GREETING_TOKENS or intent_val == "greeting":
        return QueryDomainResult(domain=QueryDomain.PURE_GREETING, original_query=text)

    # 2. HYBRID QUERY DETECTION
    # Checks for multi-clause questions combining general knowledge + weather inquiry
    # Patterns: "... and will it rain...", "... and what is the weather...", "... also is it safe..."
    split_match = re.search(
        r"^(.*?)(?:\s*,\s*and\s+|\s+and\s+|\s*;\s*|\s*\?\s*and\s+|\s+also\s+)(.*)$",
        clean,
        re.IGNORECASE
    )
    if split_match:
        part1 = split_match.group(1).strip()
        part2 = split_match.group(2).strip()

        part1_has_weather = any(k in part1 for k in WEATHER_KEYWORDS)
        part2_has_weather = any(k in part2 for k in WEATHER_KEYWORDS)

        # One part has weather, the other part has general inquiry
        is_hybrid = False
        gen_part = None
        weather_part = None

        if not part1_has_weather and part2_has_weather:
            is_hybrid = True
            gen_part = text[:len(part1)].strip()
            weather_part = text[len(part1):].strip()
            # Clean up connector
            weather_part = re.sub(r"^(?:,\s*and\s+|and\s+|also\s+)", "", weather_part, flags=re.IGNORECASE).strip()
        elif part1_has_weather and not part2_has_weather:
            # Check if part2 is truly general knowledge (e.g. "and who founded it?")
            if any(part2.startswith(s) for s in ["who ", "what is ", "what was ", "tell me ", "why "]):
                is_hybrid = True
                weather_part = text[:len(part1)].strip()
                gen_part = text[len(part1):].strip()
                gen_part = re.sub(r"^(?:,\s*and\s+|and\s+|also\s+)", "", gen_part, flags=re.IGNORECASE).strip()

        if is_hybrid and gen_part and weather_part:
            inferred_loc = resolve_inferred_location(text)
            return QueryDomainResult(
                domain=QueryDomain.HYBRID,
                general_subquery=gen_part,
                weather_subquery=weather_part,
                inferred_location=inferred_loc,
                original_query=text
            )

    # 3. PURE GENERAL KNOWLEDGE
    # Non-weather questions OR conceptual scientific weather questions (e.g., "what is monsoon season")
    has_any_weather_word = any(k in clean for k in WEATHER_KEYWORDS)
    if not has_any_weather_word:
        return QueryDomainResult(
            domain=QueryDomain.PURE_GENERAL,
            general_subquery=text,
            original_query=text
        )

    if is_conceptual_definition(clean):
        return QueryDomainResult(
            domain=QueryDomain.PURE_GENERAL,
            general_subquery=text,
            original_query=text
        )

    # 4. PURE WEATHER QUERY
    # Action decision, live weather query, forecast, AQI, alert inquiry
    inferred_loc = resolve_inferred_location(text)
    return QueryDomainResult(
        domain=QueryDomain.PURE_WEATHER,
        weather_subquery=text,
        inferred_location=inferred_loc,
        original_query=text
    )
