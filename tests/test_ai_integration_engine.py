"""Unit and Integration Tests for Phase 8 — AI Integration Engine."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.main import app
from backend.db.session import get_db, Base, engine
from backend.services.chat_integration_service import ChatIntegrationService
from backend.services.weather_manager import WeatherManager
from backend.services.exceptions import ProviderError
from ai.models import (
    WeatherRecord as AIWeatherRecord,
    ForecastItem as AIForecastItem,
    OfficialAlert as AIOfficialAlert,
    LocationInfo as AILocationInfo,
    PersonaEnum,
    RiskLevelEnum
)
from ai.reasoner import WeatherReasoner
from ai.decision import DecisionEngine
from ai.pipeline import WeatherGPTPipeline

client = TestClient(app)


# Setup fixture for clean in-memory database test session
@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


def test_1_chat_with_current_weather(db_session):
    """Test 1: Chat query retrieving live current weather mapped to AIWeatherRecord."""
    service = ChatIntegrationService()
    import asyncio
    res = asyncio.run(
        service.handle_chat_request(
            message="What is the current temperature in Coimbatore?",
            location_name="Coimbatore",
            persona="student",
            language="en",
            db_session=db_session
        )
    )
    assert res["location"] == "Coimbatore"
    assert "answer" in res
    assert res["data_quality"]["is_data_available"] is True
    assert "temperature" in res["weather_summary"]


def test_2_chat_with_forecast(db_session):
    """Test 2: Chat query requesting forecast items mapped to AIForecastItem."""
    service = ChatIntegrationService()
    import asyncio
    res = asyncio.run(
        service.handle_chat_request(
            message="Will it rain tomorrow in Nagapattinam?",
            location_name="Nagapattinam",
            persona="farmer",
            language="ta",
            db_session=db_session
        )
    )
    assert res["location"] == "Nagapattinam"
    assert res["forecast_count"] > 0
    assert "answer" in res


def test_3_chat_with_official_warning(db_session):
    """Test 3: Official alerts prioritize warning severity and pass to AIOfficialAlert."""
    service = ChatIntegrationService()
    import asyncio
    with patch.object(service.weather_mgr.alert_service, "get_ai_official_alerts") as mock_alerts:
        now_dt = datetime.now(timezone.utc)
        mock_alerts.return_value = [
            AIOfficialAlert(
                type="heavy_rain_cyclone",
                severity=RiskLevelEnum.EXTREME,
                title="IMD Red Warning",
                description="Severe cyclonic storm approaching coastal Tamil Nadu.",
                source="IMD",
                issued_at=now_dt,
                expires_at=now_dt + timedelta(hours=24),
                affected_locations=["Nagapattinam"]
            )
        ]
        res = asyncio.run(
            service.handle_chat_request(
                message="Is it safe to go fishing in Nagapattinam?",
                location_name="Nagapattinam",
                persona="fisherman",
                db_session=db_session
            )
        )
        assert res["risk"]["level"] in ["high", "extreme"]
        assert len(res["alerts"]) > 0


def test_4_chat_with_detected_hazard(db_session):
    """Test 4: High wind speed triggers AI hazard evaluation."""
    service = ChatIntegrationService()
    import asyncio
    with patch.object(service.weather_mgr.current_service, "fetch_current_weather") as mock_curr:
        now_str = datetime.now(timezone.utc).isoformat()
        mock_curr.return_value = MagicMock(
            location=MagicMock(name="Chennai", latitude=13.0827, longitude=80.2707, district=None, state=None),
            weather=MagicMock(
                temperature=30.0, feels_like=32.0, humidity=85.0, rain_probability=90.0,
                wind_speed=65.0, condition="Heavy Gale", rainfall_mm=45.0,
                model_dump=lambda: {"temperature": 30.0, "humidity": 85.0, "rain_probability": 90.0, "wind_speed": 65.0, "condition": "Heavy Gale"}
            ),
            comparison=MagicMock(secondary_temperature=30.0, secondary_rain_probability=90.0, sources_agree=True),
            observed_at=now_str, retrieved_at=now_str, source="IMD Primary"
        )
        res = asyncio.run(
            service.handle_chat_request(
                message="Can I travel outside in Chennai?",
                location_name="Chennai",
                db_session=db_session
            )
        )
        assert res["risk"]["level"] in ["high", "extreme", "medium"]


def test_5_missing_weather_data_unavailable(db_session):
    """Test 5: Provider failure sets data_status='DATA_UNAVAILABLE' distinct from 'NO_HAZARD_DETECTED'."""
    service = ChatIntegrationService()
    import asyncio
    with patch.object(service.weather_mgr.current_service, "fetch_current_weather", side_effect=ProviderError("IMD down")):
        res = asyncio.run(
            service.handle_chat_request(
                message="What is the weather in Madurai?",
                location_name="Madurai",
                db_session=db_session
            )
        )
        assert res["data_quality"]["is_data_available"] is False
        assert res["data_quality"]["data_status"] == "DATA_UNAVAILABLE"


def test_6_provider_failure_resilience(db_session):
    """Test 6: Provider exceptions are safely caught without crashing the application."""
    service = ChatIntegrationService()
    import asyncio
    with patch.object(service.weather_mgr.current_service, "fetch_current_weather", side_effect=Exception("API Timeout")):
        res = asyncio.run(
            service.handle_chat_request(
                message="Weather in Salem",
                location_name="Salem",
                db_session=db_session
            )
        )
        assert "answer" in res
        assert res["data_quality"]["is_data_available"] is False


def test_7_invalid_location_coordinates():
    """Test 7: Out of bounds coordinates (-90 to +90) return HTTP 400 or 422."""
    resp = client.post(
        "/api/v1/chat",
        json={
            "message": "Weather in Invalid Location",
            "location": {"name": "Test", "latitude": 120.0, "longitude": 76.0}
        }
    )
    assert resp.status_code in [400, 422]


def test_8_source_metadata_provenance(db_session):
    """Test 8: Source attribution is preserved in response payload."""
    service = ChatIntegrationService()
    import asyncio
    res = asyncio.run(
        service.handle_chat_request(
            message="Weather report for Coimbatore",
            location_name="Coimbatore",
            db_session=db_session
        )
    )
    assert "source" in res
    assert isinstance(res["source"], str)


def test_9_temporal_metadata(db_session):
    """Test 9: ISO UTC timestamps are preserved."""
    service = ChatIntegrationService()
    import asyncio
    res = asyncio.run(
        service.handle_chat_request(
            message="Current weather update",
            location_name="Coimbatore",
            db_session=db_session
        )
    )
    assert "data_timestamp" in res
    dt = datetime.fromisoformat(res["data_timestamp"])
    assert dt is not None


def test_10_person1_reasoner_compatibility():
    """Test 10: Ensures compatibility with Person 1's WeatherReasoner."""
    now_dt = datetime.now(timezone.utc)
    obs = AIWeatherRecord(
        location=AILocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now_dt, retrieved_at=now_dt, temperature=28.0, humidity=70.0,
        rain_probability=30.0, wind_speed=12.0, weather_condition="Clear", source="IMD"
    )
    reasoning = WeatherReasoner.evaluate(primary_weather=obs)
    assert reasoning.location == "Coimbatore"
    assert reasoning.consistency_score >= 0


def test_11_person1_hazard_compatibility():
    """Test 11: Direct verification of Person 1's hazard detection."""
    now_dt = datetime.now(timezone.utc)
    obs = AIWeatherRecord(
        location=AILocationInfo(name="Nagapattinam", latitude=10.7656, longitude=79.8424),
        observed_at=now_dt, retrieved_at=now_dt, temperature=28.0, humidity=90.0,
        rain_probability=95.0, wind_speed=55.0, weather_condition="Cyclonic Rain", source="IMD"
    )
    reasoning = WeatherReasoner.evaluate(primary_weather=obs)
    assert len(reasoning.detected_hazards) > 0


def test_12_person1_advisory_compatibility():
    """Test 12: Direct verification of Person 1's DecisionEngine advisory generation."""
    from ai.nlu import parse_query
    from ai.llm.multilingual import LanguageEnum
    now_dt = datetime.now(timezone.utc)
    obs = AIWeatherRecord(
        location=AILocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now_dt, retrieved_at=now_dt, temperature=28.0, humidity=70.0,
        rain_probability=20.0, wind_speed=10.0, weather_condition="Clear", source="IMD"
    )
    nlu = parse_query("Can I go outside?")
    reasoning = WeatherReasoner.evaluate(primary_weather=obs)
    advisory = DecisionEngine.generate_advisory(
        reasoning=reasoning, persona=PersonaEnum.STUDENT, target_language=LanguageEnum.EN, nlu=nlu, weather=obs
    )
    assert advisory.persona == PersonaEnum.STUDENT
    assert advisory.headline != ""


def test_13_llm_failure_fallback(db_session):
    """Test 13: Exception during LLM generation triggers deterministic fallback."""
    service = ChatIntegrationService()
    import asyncio
    with patch.object(service.ai_pipeline.llm, "generate", side_effect=Exception("LLM Timeout")):
        res = asyncio.run(
            service.handle_chat_request(
                message="Is it raining?",
                location_name="Coimbatore",
                db_session=db_session
            )
        )
        assert "answer" in res
        assert len(res["answer"]) > 0


def test_14_complete_successful_pipeline():
    """Test 14: API endpoint POST /api/v1/chat returns full structured payload."""
    resp = client.post(
        "/api/v1/chat",
        json={
            "message": "Naalaiku morning college pogalama?",
            "language": "ta",
            "persona": "student",
            "location": {"name": "Coimbatore"}
        }
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["location"] == "Coimbatore"
    assert "answer" in body
    assert "risk" in body
    assert "intent" in body


def test_15_no_fabricated_warning_on_backend_failure(db_session):
    """Test 15: Backend provider failure does NOT produce fake weather warnings."""
    service = ChatIntegrationService()
    import asyncio
    with patch.object(service.weather_mgr.alert_service, "get_ai_official_alerts", side_effect=ProviderError("No connection")):
        res = asyncio.run(
            service.handle_chat_request(
                message="Are there any severe cyclone warnings?",
                location_name="Coimbatore",
                db_session=db_session
            )
        )
        assert len(res["alerts"]) == 0


def test_16_e2e_coimbatore_heavy_rain_tomorrow(db_session):
    """Step 18 E2E Domain Test: 'Will there be heavy rain tomorrow in Coimbatore?'."""
    service = ChatIntegrationService()
    import asyncio
    res = asyncio.run(
        service.handle_chat_request(
            message="Will there be heavy rain tomorrow in Coimbatore?",
            location_name="Coimbatore",
            persona="student",
            language="en",
            db_session=db_session
        )
    )
    assert res["location"] == "Coimbatore"
    assert "answer" in res
    assert "intent" in res
    assert res["forecast_count"] > 0
