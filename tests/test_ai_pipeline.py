"""End-to-End Tests for WeatherGPT AI Pipeline & RAG Integration."""

from datetime import datetime, timedelta, timezone
import pytest
from ai import (
    LocationInfo,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    WeatherGPTPipeline,
    WeatherRecord,
    retrieve_safety_guidance,
)


@pytest.fixture
def coimbatore_weather():
    now = datetime.now(timezone.utc)
    return WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now - timedelta(minutes=10),
        retrieved_at=now - timedelta(minutes=5),
        temperature=29.0,
        humidity=72.0,
        rain_probability=70.0,
        wind_speed=18.0,
        weather_condition="Rain",
        source="IMD"
    )


@pytest.fixture
def nagapattinam_cyclone():
    now = datetime.now(timezone.utc)
    weather = WeatherRecord(
        location=LocationInfo(name="Nagapattinam", latitude=10.7656, longitude=79.8424),
        observed_at=now - timedelta(minutes=15),
        retrieved_at=now - timedelta(minutes=5),
        temperature=26.0,
        humidity=95.0,
        rain_probability=90.0,
        wind_speed=65.0,
        weather_condition="Severe Cyclonic Storm",
        source="IMD"
    )
    alert = OfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Cyclone Red Alert",
        description="Squally wind speeds exceeding 65 km/h along coastal regions",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=18)
    )
    return weather, alert


def test_rag_safety_retrieval():
    # Cyclone guidance
    cyclone_notes = retrieve_safety_guidance(["OFFICIAL_WARNING_CYCLONE"], language="en")
    assert len(cyclone_notes) > 0
    assert "shelter" in cyclone_notes[0].lower() or "radio" in cyclone_notes[0].lower()

    # Tamil heavy rain guidance
    rain_notes_ta = retrieve_safety_guidance(["HEAVY_RAINFALL"], language="ta")
    assert len(rain_notes_ta) > 0
    assert "வடிகால்" in rain_notes_ta[0] or "மின்" in rain_notes_ta[0]


def test_hero_scenario_student_tanglish(coimbatore_weather):
    pipeline = WeatherGPTPipeline()
    result = pipeline.process_query(
        message="Naalaiku college pogalama?",
        weather=coimbatore_weather,
        persona=PersonaEnum.STUDENT,
        conversation_id="test-conv-01"
    )

    assert result["conversation_id"] == "test-conv-01"
    assert result["location"] == "Coimbatore"
    assert result["persona"] == "student"
    assert result["intent"] == "outdoor_decision"
    assert result["language"] == "tanglish"
    assert "Coimbatore" in result["answer"]
    assert "29°C" in result["answer"] or "29" in result["answer"]
    # Check that safety rules and precautions are embedded
    assert "ஆலோசனை" in result["answer"] or "Advisory" in result["answer"]


def test_hero_scenario_fisherman_tamil(nagapattinam_cyclone):
    weather, alert = nagapattinam_cyclone
    pipeline = WeatherGPTPipeline()

    result = pipeline.process_query(
        message="நாளைக்கு கடலுக்கு போகலாமா?",
        weather=weather,
        active_alerts=[alert],
        persona=PersonaEnum.FISHERMAN,
        conversation_id="test-marine-02"
    )

    assert result["language"] == "ta"
    assert result["persona"] == "fisherman"
    assert result["risk"]["level"] == "extreme"
    # Response must highlight official alert and advise staying ashore
    assert "எச்சரிக்கை" in result["answer"] or "Alert" in result["answer"]
    assert "கடல்" in result["answer"] or "Sea" in result["answer"]


def test_english_query_pipeline(coimbatore_weather):
    pipeline = WeatherGPTPipeline()
    result = pipeline.process_query(
        message="What is the weather in Coimbatore right now?",
        weather=coimbatore_weather,
        conversation_id="test-en-03"
    )

    assert result["language"] == "en"
    assert result["source"] == "IMD"
    assert "29" in result["answer"]
    assert result["validation"]["passed"] is True
