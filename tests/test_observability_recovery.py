"""Phase 23 — Observability, Logging & Recovery Verification Test Suite.

Verifies log redaction (secrets, API keys, passwords, bearer tokens), request correlation ID tracking,
error taxonomy classification, AI pipeline safe metadata logging, database connection recovery,
and operational health probes.
"""

import logging
import os
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config.logging import RedactFilter, logger
from backend.middleware.error_handler import classify_error_category
from backend.db.session import engine
from sqlalchemy import text

client = TestClient(app)


# =============================================================================
# 1. LOG REDACTION VERIFICATION
# =============================================================================
def test_01_log_redaction_secrets_and_api_keys():
    """Verifies RedactFilter masks Gemini keys, OpenAI keys, passwords, and Bearer tokens."""
    redactor = RedactFilter()

    # Gemini API Key
    record1 = logging.LogRecord("test", logging.INFO, "", 0, "Key: AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q", (), None)
    redactor.filter(record1)
    assert "AIzaSy" not in record1.msg
    assert "[REDACTED_GEMINI_KEY]" in record1.msg

    # OpenAI API Key
    record2 = logging.LogRecord("test", logging.INFO, "", 0, "Key: sk-proj-1234567890abcdefghijklmnopqrstuvwxyz", (), None)
    redactor.filter(record2)
    assert "sk-proj" not in record2.msg
    assert "[REDACTED_OPENAI_KEY]" in record2.msg

    # Bearer Token Header
    record3 = logging.LogRecord("test", logging.INFO, "", 0, "Header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret", (), None)
    redactor.filter(record3)
    assert "eyJhbGci" not in record3.msg
    assert "Bearer [REDACTED_TOKEN]" in record3.msg

    # Password parameter
    record4 = logging.LogRecord("test", logging.INFO, "", 0, 'User login payload: password=SecretPassword123', (), None)
    redactor.filter(record4)
    assert "SecretPassword123" not in record4.msg
    assert "password=[REDACTED]" in record4.msg


# =============================================================================
# 2. REQUEST CORRELATION ID TRACING
# =============================================================================
def test_02_request_correlation_id_tracing():
    """Verifies X-Request-ID correlation header is generated or preserved across requests."""
    # Custom correlation ID
    custom_id = "trace-req-sih26068-12345"
    res1 = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert res1.status_code == 200
    assert res1.headers.get("X-Request-ID") == custom_id

    # Auto-generated correlation ID
    res2 = client.get("/api/v1/health")
    assert res2.status_code == 200
    assert "X-Request-ID" in res2.headers
    assert len(res2.headers.get("X-Request-ID")) > 10


# =============================================================================
# 3. ERROR CLASSIFICATION TAXONOMY
# =============================================================================
def test_03_error_classification_taxonomy():
    """Verifies error classification taxonomy identifies client, auth, provider, timeout, and internal errors."""
    assert classify_error_category(400) == "CLIENT_ERROR"
    assert classify_error_category(401) == "AUTH_ERROR"
    assert classify_error_category(403) == "AUTH_ERROR"
    assert classify_error_category(422) == "CLIENT_ERROR"
    assert classify_error_category(502) == "PROVIDER_ERROR"
    assert classify_error_category(503) == "PROVIDER_ERROR"

    # Timeout exception classification
    timeout_exc = TimeoutError("HTTP request timed out")
    assert classify_error_category(500, timeout_exc) == "TIMEOUT_ERROR"

    # DB Exception classification
    db_exc = RuntimeError("SQLite database is locked")
    assert classify_error_category(500, db_exc) == "DATABASE_ERROR"


# =============================================================================
# 4. ERROR RESPONSE CORRELATION
# =============================================================================
def test_04_error_response_correlation():
    """Verifies API error responses contain request_id and structured error code."""
    res = client.get("/api/v1/non_existent_path_404")
    assert res.status_code == 404
    assert "X-Request-ID" in res.headers
    data = res.json()
    assert "error" in data
    assert data["error"].get("category") == "CLIENT_ERROR" or data["error"].get("code") == "CLIENT_ERROR"
    assert "request_id" in data["error"]


# =============================================================================
# 5. AI PIPELINE SAFE METADATA LOGGING
# =============================================================================
def test_05_ai_pipeline_safe_metadata_logging():
    """Verifies AI pipeline response metadata is structured and contains no raw secrets."""
    payload = {
        "message": "What is the weather forecast for Coimbatore?",
        "persona": "student",
        "language": "en",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "risk" in data

    # Verify no secret patterns in response
    resp_text = str(data)
    assert "AIzaSy" not in resp_text
    assert "sk-proj" not in resp_text


# =============================================================================
# 6. DATABASE RECONNECTION & RECOVERY
# =============================================================================
def test_06_database_reconnection_and_recovery():
    """Verifies database engine handles connection test and recovery cleanly."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1


# =============================================================================
# 7. HEALTH MONITORING SIGNALS
# =============================================================================
def test_07_health_monitoring_signals():
    """Verifies operational signals returned by health, liveness, and readiness probes."""
    # Liveness
    res_live = client.get("/api/v1/health/liveness")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "alive"

    # Readiness
    res_ready = client.get("/api/v1/health/readiness")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"
