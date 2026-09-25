"""Deterministic Evaluation Dataset for SkyZen AI Evaluation & Benchmarking (Phase 32).

Contains curated, deterministic benchmark cases covering:
- student
- farmer
- fisherman
- commuter
- disaster
- normal weather
- severe weather
- ambiguous queries
- multilingual queries (Tamil, English, Hindi, Telugu)
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class BenchmarkQueryCase(BaseModel):
    """Deterministic benchmark test item."""
    id: str
    category: str  # student, farmer, fisherman, commuter, disaster, normal_weather, severe_weather, ambiguous, multilingual
    query: str
    expected_language: str  # en, ta, hi, te
    expected_intent: str
    expected_persona: Optional[str] = None
    expected_location: Optional[str] = None
    expected_time: Optional[str] = None
    weather_fixture: Dict[str, Any]
    official_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    expected_risk: str  # LOW, MODERATE, HIGH, EXTREME
    multilingual_pair_id: Optional[str] = None
    notes: Optional[str] = None


# Deterministic evaluation dataset
DETERMINISTIC_BENCHMARK_CASES: List[BenchmarkQueryCase] = [
    # 1. STUDENT
    BenchmarkQueryCase(
        id="case_student_01",
        category="student",
        query="I have morning school tomorrow in Coimbatore. Will it rain during travel hours?",
        expected_language="en",
        expected_intent="commute_weather",
        expected_persona="student",
        expected_location="Coimbatore",
        expected_time="tomorrow morning",
        weather_fixture={
            "location_name": "Coimbatore",
            "temperature": 27.5,
            "humidity": 78.0,
            "rain_probability": 85.0,
            "wind_speed": 18.0,
            "condition": "Moderate Rain",
            "source": "IMD"
        },
        official_alerts=[{
            "type": "heavy_rain",
            "severity": "medium",
            "title": "IMD Moderate to Heavy Rainfall Warning",
            "source": "IMD"
        }],
        expected_risk="MODERATE",
        notes="Student morning commute under moderate rain"
    ),
    BenchmarkQueryCase(
        id="case_student_02",
        category="student",
        query="நாளைய கல்லூரி நேரத்திற்கு கோவையில் மழை பெய்யுமா?",
        expected_language="ta",
        expected_intent="commute_weather",
        expected_persona="student",
        expected_location="Coimbatore",
        expected_time="tomorrow",
        weather_fixture={
            "location_name": "Coimbatore",
            "temperature": 29.0,
            "humidity": 65.0,
            "rain_probability": 20.0,
            "wind_speed": 12.0,
            "condition": "Partly Cloudy",
            "source": "IMD"
        },
        official_alerts=[],
        expected_risk="LOW",
        multilingual_pair_id="pair_college_commute",
        notes="Tamil student college query"
    ),

    # 2. FARMER
    BenchmarkQueryCase(
        id="case_farmer_01",
        category="farmer",
        query="Should I irrigate my paddy fields in Thanjavur this afternoon?",
        expected_language="en",
        expected_intent="agricultural_advisory",
        expected_persona="farmer",
        expected_location="Thanjavur",
        expected_time="this afternoon",
        weather_fixture={
            "location_name": "Thanjavur",
            "temperature": 32.0,
            "humidity": 82.0,
            "rain_probability": 90.0,
            "wind_speed": 22.0,
            "condition": "Thunderstorms Likely",
            "source": "IMD"
        },
        official_alerts=[{
            "type": "heavy_rain",
            "severity": "high",
            "title": "Heavy Rain Alert for Thanjavur Delta",
            "source": "IMD"
        }],
        expected_risk="HIGH",
        notes="Farmer irrigation postponement query"
    ),
    BenchmarkQueryCase(
        id="case_farmer_02",
        category="farmer",
        query="இன்று மாலை பயிர்களுக்கு பூச்சிக்கொல்லி மருந்து அடிக்கலாமா?",
        expected_language="ta",
        expected_intent="agricultural_advisory",
        expected_persona="farmer",
        expected_location="Coimbatore",
        expected_time="today evening",
        weather_fixture={
            "location_name": "Coimbatore",
            "temperature": 30.0,
            "humidity": 55.0,
            "rain_probability": 10.0,
            "wind_speed": 8.0,
            "condition": "Dry & Clear",
            "source": "IMD"
        },
        official_alerts=[],
        expected_risk="LOW",
        notes="Farmer pesticide spraying window query"
    ),

    # 3. FISHERMAN
    BenchmarkQueryCase(
        id="case_fisherman_01",
        category="fisherman",
        query="Can we venture into the sea from Rameswaram coast tonight?",
        expected_language="en",
        expected_intent="marine_advisory",
        expected_persona="fisherman",
        expected_location="Rameswaram",
        expected_time="tonight",
        weather_fixture={
            "location_name": "Rameswaram",
            "temperature": 28.0,
            "humidity": 88.0,
            "rain_probability": 95.0,
            "wind_speed": 62.0,
            "condition": "Squally Winds & Rough Seas",
            "source": "IMD"
        },
        official_alerts=[{
            "type": "squall",
            "severity": "extreme",
            "title": "IMD Fisherman Warning: Do Not Venture Into Sea",
            "source": "IMD"
        }],
        expected_risk="EXTREME",
        notes="Official marine squall warning"
    ),
    BenchmarkQueryCase(
        id="case_fisherman_02",
        category="fisherman",
        query="மீன்பிடிக்க கடலுக்குச் செல்லலாமா?",
        expected_language="ta",
        expected_intent="marine_advisory",
        expected_persona="fisherman",
        expected_location="Chennai",
        expected_time="now",
        weather_fixture={
            "location_name": "Chennai",
            "temperature": 30.0,
            "humidity": 70.0,
            "rain_probability": 15.0,
            "wind_speed": 16.0,
            "condition": "Moderate Breeze, Calm Sea",
            "source": "IMD"
        },
        official_alerts=[],
        expected_risk="LOW",
        notes="Calm sea conditions query"
    ),

    # 4. COMMUTER
    BenchmarkQueryCase(
        id="case_commuter_01",
        category="commuter",
        query="Is there waterlogging risk on Chennai roads this evening?",
        expected_language="en",
        expected_intent="commute_weather",
        expected_persona="commuter",
        expected_location="Chennai",
        expected_time="this evening",
        weather_fixture={
            "location_name": "Chennai",
            "temperature": 26.0,
            "humidity": 92.0,
            "rain_probability": 90.0,
            "wind_speed": 35.0,
            "condition": "Persistent Heavy Showers",
            "source": "IMD"
        },
        official_alerts=[{
            "type": "heavy_rain",
            "severity": "high",
            "title": "Severe Waterlogging Alert for Urban Chennai",
            "source": "IMD"
        }],
        expected_risk="HIGH",
        notes="Commuter urban waterlogging query"
    ),

    # 5. DISASTER
    BenchmarkQueryCase(
        id="case_disaster_01",
        category="disaster",
        query="What is the official cyclone status and landfall warning for Cuddalore?",
        expected_language="en",
        expected_intent="severe_weather_alert",
        expected_persona="disaster",
        expected_location="Cuddalore",
        expected_time="current",
        weather_fixture={
            "location_name": "Cuddalore",
            "temperature": 25.0,
            "humidity": 96.0,
            "rain_probability": 100.0,
            "wind_speed": 85.0,
            "condition": "Severe Cyclonic Storm",
            "source": "IMD"
        },
        official_alerts=[{
            "type": "cyclone",
            "severity": "extreme",
            "title": "IMD RED ALERT: Severe Cyclone Landfall within 12 Hours",
            "source": "IMD"
        }],
        expected_risk="EXTREME",
        notes="Disaster management official red alert"
    ),

    # 6. NORMAL WEATHER
    BenchmarkQueryCase(
        id="case_normal_01",
        category="normal_weather",
        query="What is the temperature and humidity in Madurai today?",
        expected_language="en",
        expected_intent="current_weather",
        expected_persona="general",
        expected_location="Madurai",
        expected_time="today",
        weather_fixture={
            "location_name": "Madurai",
            "temperature": 34.2,
            "humidity": 48.0,
            "rain_probability": 5.0,
            "wind_speed": 10.0,
            "condition": "Sunny and Warm",
            "source": "IMD"
        },
        official_alerts=[],
        expected_risk="LOW",
        notes="Standard benign weather query"
    ),

    # 7. SEVERE WEATHER
    BenchmarkQueryCase(
        id="case_severe_01",
        category="severe_weather",
        query="Are there any red alerts or flash flood warnings for Nilgiris?",
        expected_language="en",
        expected_intent="severe_weather_alert",
        expected_persona="general",
        expected_location="Nilgiris",
        expected_time="current",
        weather_fixture={
            "location_name": "Nilgiris",
            "temperature": 18.0,
            "humidity": 98.0,
            "rain_probability": 95.0,
            "wind_speed": 45.0,
            "condition": "Extremely Heavy Downpour, Landslide Hazard",
            "source": "IMD"
        },
        official_alerts=[{
            "type": "landslide_rain",
            "severity": "extreme",
            "title": "RED ALERT: High Landslide & Flash Flood Threat",
            "source": "IMD"
        }],
        expected_risk="EXTREME",
        notes="Hilly region landslide threat"
    ),

    # 8. AMBIGUOUS QUERIES
    BenchmarkQueryCase(
        id="case_ambiguous_01",
        category="ambiguous",
        query="Should I go out now?",
        expected_language="en",
        expected_intent="activity_planning",
        expected_persona="general",
        expected_location=None,
        expected_time="now",
        weather_fixture={
            "location_name": "Coimbatore",
            "temperature": 27.0,
            "humidity": 60.0,
            "rain_probability": 15.0,
            "wind_speed": 12.0,
            "condition": "Fair",
            "source": "IMD"
        },
        official_alerts=[],
        expected_risk="LOW",
        notes="Ambiguous query requiring location clarification/default"
    ),
    BenchmarkQueryCase(
        id="case_ambiguous_02",
        category="ambiguous",
        query="வெளியில் செல்லலாமா?",
        expected_language="ta",
        expected_intent="activity_planning",
        expected_persona="general",
        expected_location=None,
        expected_time="now",
        weather_fixture={
            "location_name": "Coimbatore",
            "temperature": 27.0,
            "humidity": 60.0,
            "rain_probability": 15.0,
            "wind_speed": 12.0,
            "condition": "Fair",
            "source": "IMD"
        },
        official_alerts=[],
        expected_risk="LOW",
        notes="Tamil ambiguous query"
    ),

    # 9. MULTILINGUAL QUERIES (English, Tamil, Hindi, Telugu)
    BenchmarkQueryCase(
        id="case_multi_en",
        category="multilingual",
        query="Will it rain in Coimbatore tomorrow?",
        expected_language="en",
        expected_intent="forecast",
        expected_persona="general",
        expected_location="Coimbatore",
        expected_time="tomorrow",
        weather_fixture={
            "location_name": "Coimbatore",
            "temperature": 28.0,
            "humidity": 80.0,
            "rain_probability": 75.0,
            "wind_speed": 14.0,
            "condition": "Scattered Rain",
            "source": "IMD"
        },
        official_alerts=[],
        expected_risk="MODERATE",
        multilingual_pair_id="triplet_rain_tomorrow",
        notes="English forecast triplet"
    ),
    BenchmarkQueryCase(
        id="case_multi_ta",
        category="multilingual",
        query="நாளை கோவையில் மழை பெய்யுமா?",
        expected_language="ta",
        expected_intent="forecast",
        expected_persona="general",
        expected_location="Coimbatore",
        expected_time="tomorrow",
        weather_fixture={
            "location_name": "Coimbatore",
            "temperature": 28.0,
            "humidity": 80.0,
            "rain_probability": 75.0,
            "wind_speed": 14.0,
            "condition": "Scattered Rain",
            "source": "IMD"
        },
        official_alerts=[],
        expected_risk="MODERATE",
        multilingual_pair_id="triplet_rain_tomorrow",
        notes="Tamil forecast triplet"
    ),
    BenchmarkQueryCase(
        id="case_multi_hi",
        category="multilingual",
        query="क्या कल कोयंबटूर में बारिश होगी?",
        expected_language="hi",
        expected_intent="forecast",
        expected_persona="general",
        expected_location="Coimbatore",
        expected_time="tomorrow",
        weather_fixture={
            "location_name": "Coimbatore",
            "temperature": 28.0,
            "humidity": 80.0,
            "rain_probability": 75.0,
            "wind_speed": 14.0,
            "condition": "Scattered Rain",
            "source": "IMD"
        },
        official_alerts=[],
        expected_risk="MODERATE",
        multilingual_pair_id="triplet_rain_tomorrow",
        notes="Hindi forecast triplet"
    ),
    BenchmarkQueryCase(
        id="case_multi_te",
        category="multilingual",
        query="రేపు కోయంబత్తూరులో వర్షం పడుతుందా?",
        expected_language="te",
        expected_intent="forecast",
        expected_persona="general",
        expected_location="Coimbatore",
        expected_time="tomorrow",
        weather_fixture={
            "location_name": "Coimbatore",
            "temperature": 28.0,
            "humidity": 80.0,
            "rain_probability": 75.0,
            "wind_speed": 14.0,
            "condition": "Scattered Rain",
            "source": "IMD"
        },
        official_alerts=[],
        expected_risk="MODERATE",
        multilingual_pair_id="triplet_rain_tomorrow",
        notes="Telugu forecast triplet"
    )
]


def get_benchmark_dataset() -> List[BenchmarkQueryCase]:
    """Returns the immutable deterministic benchmark dataset."""
    return DETERMINISTIC_BENCHMARK_CASES
