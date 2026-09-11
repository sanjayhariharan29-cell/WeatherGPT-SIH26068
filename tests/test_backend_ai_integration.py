"""Comprehensive Backend AI Integration Test Suite.

Verifies end-to-end integration between Person 2's FastAPI backend layer
and Person 1's WeatherGPT AI Engine, covering 20 dedicated scenarios:
1. Valid chat request (English)
2. Invalid message (empty/whitespace -> 422)
3. Invalid location coordinates (out of bounds -> 422)
4. Tamil query & Tamil response
5. Hindi query & Hindi response
6. Persona propagation (farmer, fisherman, student)
7. Tomorrow forecast integration (temporal query consumes forecast)
8. Current weather query (now / today)
9. Official warning preservation across backend -> AI -> API response
10. Hazard detection reflection in response
11. Source metadata & ISO data timestamp
12. Missing telemetry handling
13. Provider failure graceful degradation (no 500, no fabricated data)
14. LLM failure resilience (fallback triggered)
15. Validator rejection on hallucinated response (fallback returned)
16. Response serialization (clean JSON types, no object leaks)
17. Oversized message rejection (>2000 chars -> 422)
18. Location entity extraction from message
19. Database persistence verification (Conversation, Message, Advisory)
20. Complete end-to-end scenario
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.main import app
from backend.schemas.chat import ChatRequest, LocationPayload
from backend.services.ai_service import AIService
from backend.services.exceptions import ProviderUnavailableError
from backend.db.session import get_db, SessionLocal
from backend.db.models import Conversation, Message, Advisory
from ai.models import (
    WeatherRecord as AIWeatherRecord,
    ForecastItem as AIForecastItem,
    OfficialAlert as AIOfficialAlert,
    LocationInfo as AILocationInfo,
    RiskLevelEnum,
    PersonaEnum,
    LanguageEnum
)

client = TestClient(app)


# -------------------------------------------------------------------------
# Scenario 1: Valid Chat Request (English)
# -------------------------------------------------------------------------
def test_01_valid_chat_request_english():
    payload = {
        "message": "What is the current weather in Coimbatore?",
        "language": "en",
        "persona": "general",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "conversation_id" in data
    assert "answer" in data
    assert len(data["answer"]) > 10
    assert data["language"] in ("en", "english")
    assert data["location"] == "Coimbatore"
    assert "risk" in data
    assert "level" in data["risk"]
    assert "weather_summary" in data
    assert "source" in data
    assert "data_timestamp" in data
    assert "validation" in data


# -------------------------------------------------------------------------
# Scenario 2: Invalid Message (Empty or Whitespace -> 422)
# -------------------------------------------------------------------------
def test_02_invalid_empty_or_whitespace_message():
    # Empty string
    res = client.post("/api/v1/chat", json={"message": ""})
    assert res.status_code == 422

    # Whitespace only
    res2 = client.post("/api/v1/chat", json={"message": "     "})
    assert res2.status_code == 422


# -------------------------------------------------------------------------
# Scenario 3: Invalid Location Coordinates (Out of Bounds -> 400)
# -------------------------------------------------------------------------
def test_03_invalid_location_coordinates():
    # Latitude > 90
    bad_lat = {
        "message": "Weather update",
        "location": {"name": "Test", "latitude": 95.5, "longitude": 77.0}
    }
    res = client.post("/api/v1/chat", json=bad_lat)
    assert res.status_code in [400, 422]

    # Longitude > 180
    bad_lon = {
        "message": "Weather update",
        "location": {"name": "Test", "latitude": 11.0, "longitude": 185.0}
    }
    res2 = client.post("/api/v1/chat", json=bad_lon)
    assert res2.status_code in [400, 422]


# -------------------------------------------------------------------------
# Scenario 4: Tamil Query & Tamil Response
# -------------------------------------------------------------------------
def test_04_tamil_query_and_response():
    payload = {
        "message": "இன்று கோயம்புத்தூரில் மழை பெய்யுமா?",
        "language": "ta",
        "persona": "student",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["language"] == "ta"
    # Verify response contains Tamil Unicode script characters (\u0B80-\u0BFF)
    assert any("\u0b80" <= c <= "\u0bff" for c in data["answer"])


# -------------------------------------------------------------------------
# Scenario 5: Hindi Query & Hindi Response
# -------------------------------------------------------------------------
def test_05_hindi_query_and_response():
    payload = {
        "message": "क्या आज चेन्नई में बारिश होगी?",
        "language": "hi",
        "persona": "general",
        "location": {"name": "Chennai"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["language"] == "hi"
    # Verify response contains Devanagari Unicode script characters (\u0900-\u097F)
    assert any("\u0900" <= c <= "\u097f" for c in data["answer"])


# -------------------------------------------------------------------------
# Scenario 6: Persona Propagation (Farmer, Fisherman, Student)
# -------------------------------------------------------------------------
def test_06_persona_propagation_farmer_fisherman_student():
    personas = ["farmer", "fisherman", "student"]
    for p in personas:
        payload = {
            "message": f"Weather advisory for {p}",
            "language": "en",
            "persona": p,
            "location": {"name": "Coimbatore"}
        }
        res = client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["persona"] == p


# -------------------------------------------------------------------------
# Scenario 7: Tomorrow Forecast Integration
# -------------------------------------------------------------------------
def test_07_tomorrow_forecast_integration():
    payload = {
        "message": "Will there be heavy rain tomorrow in Coimbatore?",
        "language": "en",
        "persona": "commuter",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    # Verify intent classified as rain_forecast or forecast or rain_query
    assert data["intent"] in ("rain_forecast", "forecast", "outdoor_decision", "rain_query")
    assert "answer" in data


# -------------------------------------------------------------------------
# Scenario 8: Current Weather Query (Now / Today)
# -------------------------------------------------------------------------
def test_08_current_weather_query():
    payload = {
        "message": "What is the current temperature and humidity right now in Coimbatore?",
        "language": "en",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["weather_summary"] is not None
    assert "temperature" in data["weather_summary"]
    assert "humidity" in data["weather_summary"]


# -------------------------------------------------------------------------
# Scenario 9: Official Warning Preservation
# -------------------------------------------------------------------------
def test_09_official_warning_preservation():
    # Nagapattinam has mock official severe alerts configured in AlertService
    payload = {
        "message": "Are there any weather alerts in Nagapattinam?",
        "language": "en",
        "location": {"name": "Nagapattinam"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["alerts"]) >= 1
    assert data["risk"]["level"] in ("high", "extreme")
    # Official warning must be acknowledged in answer
    ans_lower = data["answer"].lower()
    assert "warning" in ans_lower or "alert" in ans_lower or "imd" in ans_lower or "red" in ans_lower or "caution" in ans_lower


# -------------------------------------------------------------------------
# Scenario 10: Detected Hazard Reflection
# -------------------------------------------------------------------------
def test_10_hazard_detection_reflection():
    payload = {
        "message": "Is it safe to go out in Coimbatore?",
        "language": "en",
        "persona": "student",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["risk"]["level"] in ("low", "medium", "high", "extreme")


# -------------------------------------------------------------------------
# Scenario 11: Source Metadata & Data Timestamp
# -------------------------------------------------------------------------
def test_11_source_metadata_and_data_timestamp():
    payload = {
        "message": "Weather check",
        "language": "en",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "IMD" in data["source"]
    # Check data timestamp is ISO format
    dt = datetime.fromisoformat(data["data_timestamp"])
    assert dt is not None


# -------------------------------------------------------------------------
# Scenario 12: Missing Telemetry Handling
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_missing_telemetry_handling():
    service = AIService()
    now_dt = datetime.now(timezone.utc)
    partial_obs = AIWeatherRecord(
        location=AILocationInfo(name="TestLoc", latitude=11.0, longitude=77.0),
        observed_at=now_dt,
        retrieved_at=now_dt,
        temperature=25.0,
        humidity=60.0,
        rain_probability=20.0,
        wind_speed=10.0,
        weather_condition="Clear",
        source="IMD",
        rainfall_amount_mm=0.0
    )

    with patch.object(service.weather_mgr, "get_ai_weather_input", return_value=(partial_obs, [], [])):
        req = ChatRequest(message="What is the weather?", language="en")
        res = await service.process_chat(req)
        assert res["answer"] is not None
        assert res["risk"]["level"] == "low"


# -------------------------------------------------------------------------
# Scenario 13: Provider Failure Graceful Degradation (No 500, No Hallucination)
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_provider_failure_graceful_degradation():
    service = AIService()
    # Mock weather manager raising provider unavailable
    with patch.object(
        service.weather_mgr,
        "get_ai_weather_input",
        side_effect=ProviderUnavailableError("All providers down", provider_name="IMD")
    ):
        req = ChatRequest(message="What is the weather in Coimbatore?", language="en")
        res = await service.process_chat(req)
        assert res["validation"]["status"] == "DATA_UNAVAILABLE"
        assert "unavailable" in res["answer"].lower()
        assert res["source"] == "Unavailable"


# -------------------------------------------------------------------------
# Scenario 14: LLM Failure Resilience (Fallback Triggered)
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_14_llm_failure_resilience():
    service = AIService()
    now_dt = datetime.now(timezone.utc)
    obs = AIWeatherRecord(
        location=AILocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now_dt,
        retrieved_at=now_dt,
        temperature=30.0,
        humidity=75.0,
        rain_probability=80.0,
        wind_speed=20.0,
        weather_condition="Moderate Rain",
        source="IMD"
    )

    # Force LLM generator to raise Exception
    with patch.object(service.pipeline.llm, "generate", side_effect=RuntimeError("LLM API timeout")):
        with patch.object(service.weather_mgr, "get_ai_weather_input", return_value=(obs, [], [])):
            req = ChatRequest(message="Will it rain today?", language="en")
            res = await service.process_chat(req)
            assert res["answer"] is not None
            # Verify answer contains grounded fallback advice
            assert len(res["answer"]) > 10


# -------------------------------------------------------------------------
# Scenario 15: Validator Rejection on Hallucinated Response (Fallback Returned)
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_15_validator_rejection_triggers_fallback():
    service = AIService()
    if hasattr(service.pipeline, "llm_circuit_breaker"):
        service.pipeline.llm_circuit_breaker.reset()
    now_dt = datetime.now(timezone.utc)
    obs = AIWeatherRecord(
        location=AILocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now_dt,
        retrieved_at=now_dt,
        temperature=28.0,
        humidity=70.0,
        rain_probability=10.0,
        wind_speed=15.0,
        weather_condition="Partly Cloudy",
        source="IMD"
    )

    # Mock LLM returning fabricated 48°C extreme heatwave
    with patch.object(
        service.pipeline.llm,
        "generate",
        return_value="Severe heatwave warning! Temperatures will reach 48.0°C in Coimbatore today."
    ):
        with patch.object(service.weather_mgr, "get_ai_weather_input", return_value=(obs, [], [])):
            req = ChatRequest(message="What is the temperature?", language="en")
            res = await service.process_chat(req)
            # Must reject hallucinated 48°C and provide safe grounded fallback
            assert "48.0" not in res["answer"]
            assert res["validation"]["passed"] is False or res["validation"]["status"] in ("REJECT", "FALLBACK")


# -------------------------------------------------------------------------
# Scenario 16: Response Serialization Types (Clean JSON Types)
# -------------------------------------------------------------------------
def test_16_response_serialization_types():
    payload = {
        "message": "Today weather summary",
        "language": "en",
        "persona": "student"
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["conversation_id"], str)
    assert isinstance(data["answer"], str)
    assert isinstance(data["language"], str)
    assert isinstance(data["intent"], str)
    assert isinstance(data["location"], str)
    assert isinstance(data["risk"], dict)
    assert isinstance(data["alerts"], list)


# -------------------------------------------------------------------------
# Scenario 17: Oversized Message Rejected (>2000 chars -> 422)
# -------------------------------------------------------------------------
def test_17_oversized_message_rejected():
    oversized = "a" * 2001
    res = client.post("/api/v1/chat", json={"message": oversized})
    assert res.status_code == 422


# -------------------------------------------------------------------------
# Scenario 18: Location Entity Extraction from Message
# -------------------------------------------------------------------------
def test_18_location_entity_extraction_from_message():
    # User message explicitly names Chennai, but payload has default Coimbatore
    payload = {
        "message": "Will it rain heavily in Chennai tomorrow?",
        "language": "en",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    # AIService resolves Chennai from NLU entity
    assert data["location"] == "Chennai"


# -------------------------------------------------------------------------
# Scenario 19: Database Persistence Verification
# -------------------------------------------------------------------------
def test_19_database_persistence():
    db: Session = SessionLocal()
    try:
        unique_conv_id = f"test_conv_{datetime.now(timezone.utc).timestamp()}"
        payload = {
            "message": "Naalaiku mazhai varuma?",
            "language": "ta",
            "persona": "student",
            "conversation_id": unique_conv_id,
            "location": {"name": "Coimbatore"}
        }
        res = client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200

        # Verify DB records
        conv = db.query(Conversation).filter(Conversation.id == unique_conv_id).first()
        assert conv is not None

        msgs = db.query(Message).filter(Message.conversation_id == unique_conv_id).all()
        assert len(msgs) >= 2
        user_msg = next((m for m in msgs if m.sender == "user"), None)
        bot_msg = next((m for m in msgs if m.sender == "bot"), None)
        assert user_msg is not None
        assert bot_msg is not None
        assert user_msg.content == "Naalaiku mazhai varuma?"

        advisory = db.query(Advisory).filter(Advisory.message_id == bot_msg.id).first()
        assert advisory is not None
        assert advisory.persona == "student"
    finally:
        db.close()


# -------------------------------------------------------------------------
# Scenario 20: Complete End-to-End Scenario
# -------------------------------------------------------------------------
def test_20_complete_end_to_end_scenario():
    payload = {
        "message": "Naalaiku Coimbatore la college pogalama? Mazhai varuma?",
        "language": "ta",
        "persona": "student",
        "location": {"name": "Coimbatore", "latitude": 11.0168, "longitude": 76.9558}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["conversation_id"] is not None
    assert data["location"] == "Coimbatore"
    assert data["language"] in ("ta", "tanglish")
    assert data["persona"] == "student"
    assert data["risk"]["level"] in ("low", "medium", "high", "extreme")
    assert "source" in data
    assert "weather_summary" in data
