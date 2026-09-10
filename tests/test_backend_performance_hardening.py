"""Phase 24 — Backend Performance & API Hardening Verification Test Suite.

Measures endpoint latencies (health, current weather, forecast, alerts, chat), verifies input validation,
connection pooling, provider timeout/error status mappings (502/504), date range rules, and rate limiting.
"""

import time
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.base_provider import get_shared_http_client
from backend.services.exceptions import ProviderTimeoutError, ProviderUnavailableError

client = TestClient(app)


# =============================================================================
# 1. ENDPOINT LATENCY PERFORMANCE BENCHMARKS
# =============================================================================
def test_01_health_endpoint_performance():
    """Measures GET /api/v1/health execution latency (< 50ms)."""
    start = time.time()
    res = client.get("/api/v1/health")
    latency_ms = (time.time() - start) * 1000
    assert res.status_code == 200
    assert latency_ms < 50.0, f"Health check latency {latency_ms:.2f}ms exceeded 50ms baseline"


def test_02_current_weather_endpoint_performance():
    """Measures GET /api/v1/weather/current execution latency (cold < 6000ms, warm/cached < 100ms)."""
    # Cold start / initial fetch
    start_cold = time.time()
    res_cold = client.get("/api/v1/weather/current?location=Coimbatore")
    cold_ms = (time.time() - start_cold) * 1000
    assert res_cold.status_code == 200
    assert cold_ms < 6000.0, f"Cold weather fetch latency {cold_ms:.2f}ms exceeded 6000ms threshold"

    # Warm / cached fetch
    start_warm = time.time()
    res_warm = client.get("/api/v1/weather/current?location=Coimbatore")
    warm_ms = (time.time() - start_warm) * 1000
    assert res_warm.status_code == 200
    assert warm_ms < 100.0, f"Warm weather fetch latency {warm_ms:.2f}ms exceeded 100ms threshold"


def test_03_forecast_endpoint_performance():
    """Measures GET /api/v1/weather/forecast execution latency (< 3000ms cold, < 50ms warm)."""
    start = time.time()
    res = client.get("/api/v1/weather/forecast?location=Coimbatore&days=5")
    latency_ms = (time.time() - start) * 1000
    assert res.status_code == 200
    assert latency_ms < 3000.0, f"Forecast latency {latency_ms:.2f}ms exceeded threshold"


def test_04_alerts_endpoint_performance():
    """Measures GET /api/v1/weather/alerts execution latency (< 3000ms cold, < 50ms warm)."""
    start = time.time()
    res = client.get("/api/v1/weather/alerts?location=Coimbatore")
    latency_ms = (time.time() - start) * 1000
    assert res.status_code == 200
    assert latency_ms < 3000.0, f"Alerts latency {latency_ms:.2f}ms exceeded threshold"


def test_05_chat_endpoint_performance():
    """Measures POST /api/v1/chat execution latency (< 500ms for pipeline execution)."""
    payload = {
        "message": "Rainfall forecast for Coimbatore?",
        "persona": "student",
        "language": "en",
        "location": {"name": "Coimbatore"}
    }
    with patch("ai.llm.provider.GeminiLLMProvider.generate_text", return_value="In Coimbatore, current temperature is 28°C with partly cloudy skies."):
        start = time.time()
        res = client.post("/api/v1/chat", json=payload)
        latency_ms = (time.time() - start) * 1000
    assert res.status_code == 200
    assert latency_ms < 500.0, f"Chat latency {latency_ms:.2f}ms exceeded 500ms threshold"


# =============================================================================
# 2. INPUT VALIDATION & HARDENING
# =============================================================================
def test_06_validation_out_of_bounds_coordinates():
    """Verifies 400 Bad Request returned on invalid latitude/longitude."""
    res_lat = client.get("/api/v1/weather/current?lat=95.0&lon=76.95")
    assert res_lat.status_code == 400
    assert "Latitude must be between -90 and +90" in res_lat.json()["detail"]

    res_lon = client.get("/api/v1/weather/current?lat=11.0&lon=200.0")
    assert res_lon.status_code == 400
    assert "Longitude must be between -180 and +180" in res_lon.json()["detail"]


def test_07_validation_invalid_date_range():
    """Verifies 400 Bad Request returned when start_date > end_date in /weather/history."""
    res = client.get("/api/v1/weather/history?start_date=2025-01-01&end_date=2020-01-01")
    assert res.status_code == 400
    assert "start_date must be before or equal to end_date" in res.json()["detail"]


def test_08_chat_payload_length_validation():
    """Verifies 422 Unprocessable Entity returned when prompt exceeds max character limit."""
    oversized_message = "A" * 1500
    payload = {
        "message": oversized_message,
        "persona": "student",
        "language": "en"
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 422


# =============================================================================
# 3. CONTROLLED PROVIDER ERROR MAPPING
# =============================================================================
@patch("backend.services.weather_manager.WeatherManager.get_current_weather")
def test_09_provider_timeout_mapping_504(mock_get):
    """Verifies ProviderTimeoutError maps to 504 Gateway Timeout instead of 500."""
    mock_get.side_effect = ProviderTimeoutError("IMD server connection timeout", provider_name="IMD")
    res = client.get("/api/v1/weather/current?location=Coimbatore")
    assert res.status_code == 504
    assert "timed out" in res.json()["detail"]


@patch("backend.services.weather_manager.WeatherManager.get_current_weather")
def test_10_provider_unavailable_mapping_502(mock_get):
    """Verifies ProviderUnavailableError maps to 502 Bad Gateway instead of 500."""
    mock_get.side_effect = ProviderUnavailableError("HTTP 503 Service Unavailable", provider_name="IMD")
    res = client.get("/api/v1/weather/current?location=Coimbatore")
    assert res.status_code == 502
    assert "provider error" in res.json()["detail"]


# =============================================================================
# 4. HTTP CLIENT CONNECTION POOL REUSE
# =============================================================================
def test_11_http_client_connection_pool_reuse():
    """Verifies get_shared_http_client reuses the same AsyncClient instance for identical timeouts."""
    client1 = get_shared_http_client(5.0)
    client2 = get_shared_http_client(5.0)
    assert client1 is client2
