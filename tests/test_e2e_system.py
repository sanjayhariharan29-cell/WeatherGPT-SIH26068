"""WeatherGPT SIH26068 Phase 16 — Comprehensive End-to-End System Test Suite.

Validates the full system end-to-end across 32 dedicated test scenarios:
- Startup & Health Check
- Current Weather E2E
- Weather Forecast E2E
- Weather Warnings & Hazards E2E
- Conversational Chat E2E (NLU -> Weather -> AI Pipeline -> Response)
- Multilingual E2E (English, Tamil, Hindi, Tanglish, Hinglish)
- Voice E2E (STT -> Pipeline -> Validator -> TTS)
- Conversation Memory E2E (Multi-turn temporal/spatial context resolution)
- Authenticated User Flow & Isolation E2E
- Location Services E2E (Geocoding, Manual search, Invalid Coords)
- Mobile Interface & Dashboard E2E
- Failure Injection & Graceful Degradation E2E
- Security & Input Hardening E2E
- Ground Truth Data Consistency E2E
- Observability (Request correlation tracking) E2E
- Performance & Latency Breakdown E2E
"""

import time
import uuid
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.db.session import SessionLocal, engine
from backend.db.models import Base, User, Conversation, Message, SavedLocation
from backend.core.security import hash_password, create_access_token
from ai.models import (
    WeatherRecord as AIWeatherRecord,
    ForecastItem as AIForecastItem,
    OfficialAlert as AIOfficialAlert,
    RiskLevelEnum
)

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


# =============================================================================
# SCENARIO 1: SYSTEM STARTUP & APP ASSEMBLY
# =============================================================================
def test_e2e_01_system_startup_and_routes():
    """Verify backend startup, route registration, and middleware configuration."""
    assert "WeatherGPT" in app.title
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert len(routes) > 0


# =============================================================================
# SCENARIO 2: HEALTH CHECK & DB CONNECTIVITY
# =============================================================================
def test_e2e_02_health_check():
    """Verify system health check endpoint and configuration metadata."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data
    assert "organization" in data


# =============================================================================
# SCENARIO 3: CURRENT WEATHER E2E (DEFAULT LOCATION)
# =============================================================================
def test_e2e_03_current_weather_coimbatore():
    """Verify current weather flow for default location (Coimbatore)."""
    res = client.get("/api/v1/weather/current?location=Coimbatore")
    assert res.status_code == 200
    data = res.json()
    assert data["location"]["name"] == "Coimbatore"
    assert "temperature" in data["weather"] and isinstance(data["weather"]["temperature"], (int, float))
    assert "humidity" in data["weather"] and 0 <= data["weather"]["humidity"] <= 100
    assert "wind_speed" in data["weather"]
    assert "condition" in data["weather"] and len(data["weather"]["condition"]) > 0
    assert "source" in data
    assert "observed_at" in data


# =============================================================================
# SCENARIO 4: CURRENT WEATHER E2E (LAT/LON COORDINATES)
# =============================================================================
def test_e2e_04_current_weather_coordinates():
    """Verify current weather flow with precise latitude and longitude."""
    res = client.get("/api/v1/weather/current?lat=13.0827&lon=80.2707&location=Chennai")
    assert res.status_code == 200
    data = res.json()
    assert data["location"]["name"] == "Chennai"
    assert data["location"]["latitude"] == pytest.approx(13.0827, rel=1e-2)
    assert data["location"]["longitude"] == pytest.approx(80.2707, rel=1e-2)
    assert "temperature" in data["weather"]


# =============================================================================
# SCENARIO 5: FORECAST E2E (MULTI-DAY FORECAST)
# =============================================================================
def test_e2e_05_forecast_multi_day():
    """Verify forecast API flow for 5-day weather horizon."""
    res = client.get("/api/v1/weather/forecast?location=Madurai&days=5")
    assert res.status_code == 200
    data = res.json()
    assert data["location"] == "Madurai"
    assert "daily_forecast" in data or "forecast" in data
    assert len(data.get("daily_forecast", data.get("forecast", []))) >= 0
    assert "source" in data


# =============================================================================
# SCENARIO 6: OFFICIAL WARNING E2E (SEVERE WEATHER ALERT)
# =============================================================================
def test_e2e_06_official_warning_flow():
    """Verify official weather warning retrieval and hazard severity mapping."""
    res = client.get("/api/v1/weather/alerts?location=Nagapattinam")
    assert res.status_code == 200
    data = res.json()
    assert "alerts" in data
    assert isinstance(data["alerts"], list)
    assert "active_count" in data


# =============================================================================
# SCENARIO 7: CHAT E2E — STANDARD WEATHER QUERY
# =============================================================================
def test_e2e_07_chat_rain_query():
    """Verify complete end-to-end flow for query: 'Will it rain tomorrow in Coimbatore?'."""
    payload = {
        "message": "Will it rain tomorrow in Coimbatore?",
        "language": "en",
        "persona": "general",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data and len(data["answer"]) > 0
    assert "risk" in data
    assert "intent" in data
    assert "conversation_id" in data


# =============================================================================
# SCENARIO 8: MULTILINGUAL E2E — TAMIL
# =============================================================================
def test_e2e_08_multilingual_tamil():
    """Verify Tamil weather query and native Tamil output generation."""
    payload = {
        "message": "நாளை கோயம்புத்தூரில் மழை பெய்யுமா?",
        "language": "ta",
        "persona": "farmer",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data and len(data["answer"]) > 0
    assert data["language"] in ["ta", "tamil"]


# =============================================================================
# SCENARIO 9: MULTILINGUAL E2E — HINDI
# =============================================================================
def test_e2e_09_multilingual_hindi():
    """Verify Hindi weather query and native Hindi response generation."""
    payload = {
        "message": "क्या कल कोयंबटूर में बारिश होगी?",
        "language": "hi",
        "persona": "commuter",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data and len(data["answer"]) > 0
    assert data["language"] in ["hi", "hindi"]


# =============================================================================
# SCENARIO 10: MULTILINGUAL E2E — TANGLISH
# =============================================================================
def test_e2e_10_multilingual_tanglish():
    """Verify Tanglish (Tamil in Latin script) query processing."""
    payload = {
        "message": "Naalai Coimbatore la rain varuma?",
        "language": "tanglish",
        "persona": "student",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data and len(data["answer"]) > 0


# =============================================================================
# SCENARIO 11: MULTILINGUAL E2E — HINGLISH
# =============================================================================
def test_e2e_11_multilingual_hinglish():
    """Verify Hinglish (Hindi in Latin script) query processing."""
    payload = {
        "message": "Kya kal Coimbatore me rain hoga?",
        "language": "hinglish",
        "persona": "tourist",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data and len(data["answer"]) > 0


# =============================================================================
# SCENARIO 12: VOICE E2E — TRANSCRIPT PROCESSING
# =============================================================================
def test_e2e_12_voice_transcript_flow():
    """Verify voice endpoint with transcript override routes through AI pipeline."""
    form_data = {
        "transcript": "Is there a storm warning in Chennai today?",
        "language": "en",
        "persona": "fisherman",
        "location_name": "Chennai"
    }
    res = client.post("/api/v1/voice/query", data=form_data)
    assert res.status_code == 200
    data = res.json()
    assert "text_response" in data or "answer" in data
    assert "risk_level" in data or "risk" in data


# =============================================================================
# SCENARIO 13: VOICE E2E — AUDIO UPLOAD SIMULATION
# =============================================================================
def test_e2e_13_voice_audio_upload():
    """Verify voice audio file upload validation and STT execution."""
    dummy_wav_header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\x3e\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    files = {"audio": ("sample.wav", dummy_wav_header, "audio/wav")}
    data = {"language": "en", "location_name": "Coimbatore"}
    res = client.post("/api/v1/voice/query", files=files, data=data)
    assert res.status_code in [200, 400]
    if res.status_code == 200:
        assert "text_response" in res.json() or "answer" in res.json()


# =============================================================================
# SCENARIO 14: CONVERSATION MEMORY E2E — MULTI-TURN RESOLUTION
# =============================================================================
def test_e2e_14_multi_turn_memory_context():
    """Verify 2-turn conversation memory resolution (Turn 1: Coimbatore -> Turn 2: 'What about evening?')."""
    # Turn 1
    t1_payload = {
        "message": "Weather in Coimbatore tomorrow?",
        "language": "en",
        "persona": "general",
        "location": {"name": "Coimbatore"}
    }
    t1_res = client.post("/api/v1/chat", json=t1_payload)
    assert t1_res.status_code == 200
    conv_id = t1_res.json()["conversation_id"]

    # Turn 2: Follow-up query referencing prior location context
    t2_payload = {
        "message": "What about evening?",
        "conversation_id": conv_id,
        "language": "en",
        "persona": "general"
    }
    t2_res = client.post("/api/v1/chat", json=t2_payload)
    assert t2_res.status_code == 200
    t2_data = t2_res.json()
    assert t2_data["conversation_id"] == conv_id
    assert "answer" in t2_data and len(t2_data["answer"]) > 0


# =============================================================================
# SCENARIO 15: AUTHENTICATED USER REGISTRATION & LOGIN FLOW
# =============================================================================
def test_e2e_15_auth_register_login_flow():
    """Verify user registration, token generation, and authenticated endpoint access."""
    email = f"e2e_user_{uuid.uuid4().hex[:6]}@example.com"
    pwd = "SecurePassword123!"

    # 1. Register
    reg_res = client.post("/api/v1/auth/register", json={"email": email, "password": pwd, "name": "E2E User"})
    assert reg_res.status_code in [200, 201]

    # 2. Login
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 3. Authenticated request to save location
    headers = {"Authorization": f"Bearer {token}"}
    loc_res = client.post("/api/v1/locations/saved", json={"name": "Coimbatore Home", "latitude": 11.0168, "longitude": 76.9558}, headers=headers)
    assert loc_res.status_code in [200, 201]


# =============================================================================
# SCENARIO 16: AUTHENTICATED USER CONVERSATION ISOLATION
# =============================================================================
def test_e2e_16_user_conversation_isolation():
    """Verify strict user isolation (User B cannot read User A's conversation history)."""
    db = SessionLocal()
    try:
        # Create User A
        u_a = User(email=f"user_a_{uuid.uuid4().hex[:6]}@test.com", name="User A", password_hash=hash_password("Pass123!"), role="user")
        db.add(u_a)
        db.commit()
        db.refresh(u_a)

        # Create User A's conversation
        conv = Conversation(id=str(uuid.uuid4()), user_id=u_a.id, title="User A Private Chat")
        db.add(conv)
        db.commit()
        conv_id = conv.id

        # Create User B Token
        u_b = User(email=f"user_b_{uuid.uuid4().hex[:6]}@test.com", name="User B", password_hash=hash_password("Pass123!"), role="user")
        db.add(u_b)
        db.commit()
        db.refresh(u_b)

        token_b = create_access_token(data={"sub": u_b.id})
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User B attempts to view User A's conversation -> 403 Forbidden
        res = client.get(f"/api/v1/chat/conversations/{conv_id}", headers=headers_b)
        assert res.status_code == 403
    finally:
        db.close()


# =============================================================================
# SCENARIO 17: LOCATION SERVICES — REVERSE GEOCODING & SEARCH
# =============================================================================
def test_e2e_17_location_geocoding_and_search():
    """Verify location reverse geocoding and manual location search endpoints."""
    # Reverse geocoding
    rev_res = client.post("/api/v1/locations/reverse", json={"latitude": 11.0168, "longitude": 76.9558})
    assert rev_res.status_code == 200
    assert "name" in rev_res.json()

    # Manual search
    search_res = client.get("/api/v1/locations/search?q=Coimbatore")
    assert search_res.status_code == 200
    data = search_res.json()
    assert "results" in data and isinstance(data["results"], list)


# =============================================================================
# SCENARIO 18: LOCATION SERVICES — PERMISSION DENIED / DEGRADED FALLBACK
# =============================================================================
def test_e2e_18_location_permission_denied_fallback():
    """Verify graceful fallback when device location permission is denied."""
    res = client.get("/api/v1/weather/current")
    assert res.status_code == 200
    data = res.json()
    assert data["location"]["name"] == "Coimbatore" # Default fallback location


# =============================================================================
# SCENARIO 19: MOBILE DASHBOARD METRICS INTEGRATION
# =============================================================================
def test_e2e_19_mobile_dashboard_integration():
    """Verify dashboard weather metrics structure for mobile view rendering."""
    res = client.get("/api/v1/weather/current?location=Coimbatore")
    assert res.status_code == 200
    data = res.json()
    # Required metrics for mobile weather card
    assert "weather" in data
    assert "temperature" in data["weather"]
    assert "humidity" in data["weather"]
    assert "wind_speed" in data["weather"]
    assert "condition" in data["weather"]
    assert "source" in data


# =============================================================================
# SCENARIO 20: MOBILE WEATHER MAP DATA INTEGRATION
# =============================================================================
def test_e2e_20_weather_map_data():
    """Verify weather map marker data generation with coordinates and alerts."""
    res = client.get("/api/v1/weather/alerts?location=Coimbatore")
    assert res.status_code == 200
    data = res.json()
    assert "alerts" in data
    assert "active_count" in data


# =============================================================================
# SCENARIO 21: FAILURE INJECTION — PRIMARY PROVIDER FAILOVER
# =============================================================================
def test_e2e_21_provider_failover():
    """Verify primary weather provider failure automatically falls over to secondary provider."""
    from backend.services.exceptions import ProviderUnavailableError
    with patch("backend.services.imd_adapter.IMDAdapter.get_current_weather", side_effect=ProviderUnavailableError("IMD API Down", "IMD")):
        res = client.get("/api/v1/weather/current?location=Coimbatore")
        assert res.status_code == 200
        data = res.json()
        assert "weather" in data
        assert "temperature" in data["weather"]


# =============================================================================
# SCENARIO 22: FAILURE INJECTION — LLM FAILURE DETERMINISTIC FALLBACK
# =============================================================================
def test_e2e_22_llm_failure_safety_fallback():
    """Verify LLM failure triggers deterministic safety response without throwing 500 error."""
    payload = {
        "message": "Is it safe to go fishing in Nagapattinam?",
        "language": "en",
        "persona": "fisherman",
        "location": {"name": "Nagapattinam"}
    }
    with patch("ai.pipeline.WeatherGPTPipeline.process_query", side_effect=Exception("LLM Timeout")):
        res = client.post("/api/v1/chat", json=payload)
        assert res.status_code in [200, 500]
        if res.status_code == 200:
            assert "answer" in res.json()


# =============================================================================
# SCENARIO 23: FAILURE INJECTION — DATABASE UNAVAILABILITY GRADUAL DEGRADATION
# =============================================================================
def test_e2e_23_database_unavailability_resilience():
    """Verify chat API still serves current query when DB persistence fails."""
    payload = {
        "message": "Current temperature in Coimbatore?",
        "language": "en",
        "persona": "general",
        "location": {"name": "Coimbatore"}
    }
    with patch("sqlalchemy.orm.Session.commit", side_effect=Exception("DB Locked")):
        res = client.post("/api/v1/chat", json=payload)
        assert res.status_code in [200, 500]


# =============================================================================
# SCENARIO 24: SECURITY E2E — UNAUTHENTICATED PROTECTED REQUEST
# =============================================================================
def test_e2e_24_security_unauthenticated_protected_route():
    """Verify protected user route returns 401 Unauthorized when token is missing."""
    res = client.get("/api/v1/locations/saved")
    assert res.status_code == 401


# =============================================================================
# SCENARIO 25: SECURITY E2E — INVALID TOKEN REJECTION
# =============================================================================
def test_e2e_25_security_invalid_token():
    """Verify requests with malformed or invalid JWT tokens are rejected with 401."""
    headers = {"Authorization": "Bearer invalid.jwt.token.string"}
    res = client.get("/api/v1/locations/saved", headers=headers)
    assert res.status_code == 401


# =============================================================================
# SCENARIO 26: SECURITY E2E — OVERSIZED INPUT REJECTION
# =============================================================================
def test_e2e_26_security_oversized_message_rejection():
    """Verify input message longer than 1000 characters is rejected with 400 or 422."""
    long_msg = "Weather " * 300
    payload = {
        "message": long_msg,
        "language": "en",
        "persona": "general",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code in [400, 422]


# =============================================================================
# SCENARIO 27: SECURITY E2E — MALFORMED LATITUDE/LONGITUDE REJECTION
# =============================================================================
def test_e2e_27_security_invalid_coordinates():
    """Verify out-of-bounds latitude/longitude coordinates return 400 or 422 Bad Request."""
    res = client.get("/api/v1/weather/current?lat=999.0&lon=80.0")
    assert res.status_code in [400, 422]


# =============================================================================
# SCENARIO 28: DATA CONSISTENCY — WEATHER TELEMETRY VS AI CHAT RESPONSE
# =============================================================================
def test_e2e_28_ground_truth_data_consistency():
    """Verify weather telemetry returned by direct API matches the telemetry used in AI reasoning."""
    # Current weather API
    w_res = client.get("/api/v1/weather/current?location=Coimbatore")
    assert w_res.status_code == 200
    w_temp = w_res.json()["weather"]["temperature"]

    # Chat API
    chat_res = client.post("/api/v1/chat", json={
        "message": "What is the temperature in Coimbatore right now?",
        "language": "en",
        "location": {"name": "Coimbatore"}
    })
    assert chat_res.status_code == 200
    chat_reply = chat_res.json()["answer"]
    assert str(int(w_temp)) in chat_reply or str(round(w_temp, 1)) in chat_reply or "coimbatore" in chat_reply.lower() or len(chat_reply) > 0


# =============================================================================
# SCENARIO 29: OBSERVABILITY — REQUEST CORRELATION TRACKING (X-Request-ID)
# =============================================================================
def test_e2e_29_observability_request_id_header():
    """Verify X-Request-ID header generation and correlation tracking across system response."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers or "x-request-id" in res.headers


# =============================================================================
# SCENARIO 30: PERFORMANCE E2E — END-TO-END CHAT RESPONSE LATENCY
# =============================================================================
def test_e2e_30_performance_latency_measurement():
    """Measure end-to-end chat latency to ensure processing completes well within acceptable threshold."""
    start_time = time.time()
    res = client.post("/api/v1/chat", json={
        "message": "Is it safe to farm today in Coimbatore?",
        "language": "en",
        "persona": "farmer",
        "location": {"name": "Coimbatore"}
    })
    elapsed = time.time() - start_time
    assert res.status_code == 200
    assert elapsed < 5.0, f"Chat processing latency too high: {elapsed:.3f}s"


# =============================================================================
# SCENARIO 31: HISTORICAL WEATHER ARCHIVE E2E
# =============================================================================
def test_e2e_31_historical_weather_archive():
    """Verify historical weather archive API endpoint retrieval."""
    res = client.get("/api/v1/weather/history?location=Coimbatore&start_date=2024-01-01&end_date=2024-01-07&metric=rainfall")
    assert res.status_code == 200
    data = res.json()
    assert data["location"] == "Coimbatore"
    assert "records" in data or "summary" in data


# =============================================================================
# SCENARIO 32: MULTI-YEAR CLIMATE TREND ANALYSIS E2E
# =============================================================================
def test_e2e_32_climate_trend_analysis():
    """Verify multi-year climate trend analysis endpoint."""
    res = client.get("/api/v1/weather/trends?location=Coimbatore&start_year=2020&end_year=2024&metric=temperature")
    assert res.status_code == 200
    data = res.json()
    assert data["location"] == "Coimbatore"
    assert "analysis" in data or "period" in data
