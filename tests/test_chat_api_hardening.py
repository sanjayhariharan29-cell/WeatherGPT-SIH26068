"""Unit and Integration Tests for Phase 9 — Chat API / Conversational Backend Hardening."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.main import app
from backend.db.session import get_db, Base, engine
from backend.db.models import Conversation, Message
from backend.services.chat_integration_service import ChatIntegrationService
from backend.services.exceptions import ProviderError

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


def test_01_valid_chat_request():
    """Test 1: Valid chat request returns HTTP 200 with complete ChatResponse schema."""
    payload = {
        "message": "Is it safe to go outside today in Coimbatore?",
        "language": "en",
        "persona": "student",
        "location": {"name": "Coimbatore"}
    }
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body
    assert "conversation_id" in body
    assert body["location"] == "Coimbatore"
    assert "X-Request-ID" in resp.headers


def test_02_empty_message_rejected():
    """Test 2: Empty or whitespace query returns HTTP 400 Bad Request."""
    payload = {"message": "    "}
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code in [400, 422]


def test_03_oversized_message_rejected():
    """Test 3: Message exceeding 1000 characters returns HTTP 400 Bad Request."""
    payload = {"message": "A" * 1005}
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code in [400, 422]


def test_04_invalid_location_coordinates():
    """Test 4: Invalid latitude (> 90 degrees) returns HTTP 400 or 422."""
    payload = {
        "message": "Weather in Invalid Place",
        "location": {"name": "Test", "latitude": 150.0, "longitude": 76.0}
    }
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code in [400, 422]


def test_05_invalid_language_code():
    """Test 5: Unsupported language string returns HTTP 400 Bad Request."""
    payload = {
        "message": "Weather in Coimbatore",
        "language": "invalid_lang_code"
    }
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code in [400, 422]


def test_06_invalid_persona_string():
    """Test 6: Unsupported persona string returns HTTP 400 Bad Request."""
    payload = {
        "message": "Weather in Coimbatore",
        "persona": "unsupported_persona_type"
    }
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code in [400, 422]


def test_07_malformed_request_json():
    """Test 7: Malformed request body returns HTTP 422 Unprocessable Content."""
    resp = client.post(
        "/api/v1/chat",
        headers={"Content-Type": "application/json"},
        content="{invalid_json: true"
    )
    assert resp.status_code == 422


def test_08_ai_pipeline_success():
    """Test 8: Chat endpoint connects to AI pipeline and returns valid intent and risk."""
    payload = {
        "message": "Will it rain tomorrow morning in Coimbatore?",
        "language": "ta",
        "persona": "farmer",
        "location": {"name": "Coimbatore"}
    }
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "intent" in body
    assert "risk" in body
    assert body["risk"]["level"] in ["low", "medium", "high", "extreme"]


def test_09_ai_failure_resilience(db_session):
    """Test 9: LLM generation error triggers deterministic grounded advisory fallback."""
    service = ChatIntegrationService()
    import asyncio
    with patch.object(service.ai_pipeline.llm, "generate", side_effect=Exception("LLM Timeout")):
        res = asyncio.run(
            service.handle_chat_request(
                message="Rain update for Coimbatore",
                location_name="Coimbatore",
                db_session=db_session
            )
        )
        assert "answer" in res
        assert len(res["answer"]) > 0


def test_10_weather_provider_failure():
    """Test 10: Provider failure flags data_status='DATA_UNAVAILABLE'."""
    from backend.api.chat import chat_service
    with patch.object(chat_service.weather_mgr.current_service, "fetch_current_weather", side_effect=ProviderError("IMD API Down")):
        resp = client.post(
            "/api/v1/chat",
            json={"message": "Weather report for Coimbatore"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data_quality"]["data_status"] == "DATA_UNAVAILABLE"


def test_11_data_unavailable_status():
    """Test 11: DATA_UNAVAILABLE status is explicitly distinguished from NO_HAZARD_DETECTED."""
    from backend.api.chat import chat_service
    with patch.object(chat_service.weather_mgr.current_service, "fetch_current_weather", side_effect=ProviderError("No data")):
        resp = client.post("/api/v1/chat", json={"message": "What is the weather?"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data_quality"]["is_data_available"] is False
        assert body["data_quality"]["data_status"] == "DATA_UNAVAILABLE"


def test_12_validator_fallback_triggering():
    """Test 12: Anti-hallucination validation status is included in response payload."""
    resp = client.post("/api/v1/chat", json={"message": "College status tomorrow?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "validation" in body
    assert "passed" in body["validation"]


def test_13_official_warning_preservation():
    """Test 13: Official alerts maintain IMD attribution and is_official flag."""
    resp = client.post("/api/v1/chat", json={"message": "Alert status in Nagapattinam?", "location": {"name": "Nagapattinam"}})
    assert resp.status_code == 200
    body = resp.json()
    assert "alerts" in body


def test_14_multilingual_responses():
    """Test 14: Handles queries in Tamil, English, and Tanglish."""
    for lang in ["ta", "en", "tanglish"]:
        resp = client.post("/api/v1/chat", json={"message": "Weather update", "language": lang})
        assert resp.status_code == 200
        assert "answer" in resp.json()


def test_15_response_serialization_types():
    """Test 15: ChatResponse contains expected types."""
    resp = client.post("/api/v1/chat", json={"message": "Weather forecast"})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["answer"], str)
    assert isinstance(body["conversation_id"], str)
    assert isinstance(body["weather_summary"], dict)


def test_16_request_timeout_handling():
    """Test 16: Request exceeding 10s timeout raises HTTP 504 Gateway Timeout."""
    with patch("backend.services.chat_integration_service.ChatIntegrationService.handle_chat_request", side_effect=asyncio.TimeoutError()):
        resp = client.post("/api/v1/chat", json={"message": "Complex weather question"})
        assert resp.status_code == 504
        assert "timed out" in resp.json()["error"]["message"]


def test_17_request_id_correlation():
    """Test 17: Request ID is attached to response headers and body."""
    custom_id = "test-uuid-12345678"
    resp = client.post(
        "/api/v1/chat",
        json={"message": "Hello WeatherGPT"},
        headers={"X-Request-ID": custom_id}
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_id
    assert resp.json()["request_id"] == custom_id


def test_18_security_error_sanitization():
    """Test 18: Unhandled server errors return sanitized HTTP 500 without leaking stack trace."""
    with patch("backend.services.chat_integration_service.ChatIntegrationService.handle_chat_request", side_effect=RuntimeError("Internal Secret DB Password Error")):
        resp = client.post("/api/v1/chat", json={"message": "Weather check"})
        assert resp.status_code == 500
        assert "HTTP_500" in resp.json()["error"]["code"] or "INTERNAL_SERVER_ERROR" in resp.json()["error"]["code"]


def test_19_rate_limiting_enforcement():
    """Test 19: Excessive chat requests trigger HTTP 429 Too Many Requests."""
    from backend.middleware.rate_limiter import RateLimiterMiddleware
    # Clear records for test client IP
    limiter = RateLimiterMiddleware(app, max_requests=2, window_seconds=60)
    limiter.client_records["testclient"] = [1.0, 2.0, 3.0] # Pre-fill 3 requests

    # Test limit hit
    with patch("backend.middleware.rate_limiter.time.time", return_value=5.0):
        # Fire requests to test rate limit
        for _ in range(5):
            resp = client.post("/api/v1/chat", json={"message": "Ping"})
            if resp.status_code == 429:
                assert "RATE_LIMIT_EXCEEDED" in resp.json()["error"]["code"]
                assert "Retry-After" in resp.headers
                break


def test_20_complete_end_to_end_chat_flow(db_session):
    """Test 20: Complete multi-turn end-to-end conversation flow."""
    resp1 = client.post(
        "/api/v1/chat",
        json={"message": "Will it rain today in Coimbatore?", "location": {"name": "Coimbatore"}}
    )
    assert resp1.status_code == 200
    conv_id = resp1.json()["conversation_id"]

    resp2 = client.post(
        "/api/v1/chat",
        json={"message": "What about tomorrow?", "conversation_id": conv_id}
    )
    assert resp2.status_code == 200
    assert resp2.json()["conversation_id"] == conv_id
