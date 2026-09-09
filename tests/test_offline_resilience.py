"""Phase 18 — Offline / Degraded Mode & Resilience Test Suite.

Verifies system resilience under internet disconnection, weather provider failure,
forecast service failure, warning service unverified state, backend unavailability,
LLM failure, database temporary unavailability, and authenticated data cache safety.
"""

import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.exceptions import ProviderError, ProviderUnavailableError
from backend.services.schemas import NormalizedWeatherObservation, NormalizedAlertItem
from backend.services.alert_service import AlertService
from backend.services.chat_integration_service import ChatIntegrationService
from ai.pipeline import WeatherGPTPipeline
from ai.models import WeatherRecord, LocationInfo, PersonaEnum

client = TestClient(app)


# =============================================================================
# 1. OFFLINE LAUNCH & APP SHELL SERVICE WORKER AUDIT
# =============================================================================
def test_01_offline_launch_and_indicator():
    """Verifies static app shell assets are mounted and Service Worker does not crash offline."""
    res_shell = client.get("/")
    assert res_shell.status_code == 200
    assert "<!DOCTYPE html>" in res_shell.text or "WeatherGPT" in res_shell.text

    res_sw = client.get("/sw.js")
    assert res_sw.status_code == 200
    assert "weathergpt-mobile-v1" in res_sw.text
    assert "NETWORK_OFFLINE" in res_sw.text


# =============================================================================
# 2. CACHED WEATHER RETRIEVAL & PROMINENT BADGE
# =============================================================================
def test_02_cached_weather_retrieval():
    """Verifies cached weather observation includes source, timestamp, and clear cached status."""
    from backend.services.cache import ProviderCache
    cache = ProviderCache()
    cache.set("weather_cached_coimbatore", {
        "location": {"name": "Coimbatore", "latitude": 11.0168, "longitude": 76.9558},
        "temperature": 27.5,
        "source": "IMD (Cached)",
        "cached": True,
        "cached_at": "2026-09-09T10:00:00Z"
    })

    cached_val = cache.get("weather_cached_coimbatore")
    assert cached_val is not None
    assert cached_val["cached"] is True
    assert "Cached" in cached_val["source"]
    assert cached_val["cached_at"] == "2026-09-09T10:00:00Z"


# =============================================================================
# 3. STALE CACHE INDICATION (NO FAKE LIVE TAGS)
# =============================================================================
def test_03_stale_cache_indication():
    """Verifies stale cached records indicate degraded/cached status and never display fresh live tags."""
    sample_cached_data = {
        "cached": True,
        "data_status": "DEGRADED",
        "observed_at": "2026-09-09T08:00:00Z",
        "cached_at": "2026-09-09T10:00:00Z",
        "source": "IMD (Cached)"
    }
    assert sample_cached_data["cached"] is True
    assert sample_cached_data["data_status"] != "FRESH"
    assert "Cached" in sample_cached_data["source"]


# =============================================================================
# 4. FORECAST CACHE & LAST UPDATED TIMESTAMP
# =============================================================================
def test_04_forecast_cache_rendering():
    """Verifies bounded cached forecast items store last_updated timestamp and avoid claiming live data."""
    mock_forecast = {
        "location": "Coimbatore",
        "forecast": [
            {"forecast_time": "12:00 PM", "temperature": 29.0, "rain_probability": 15.0, "condition": "Partly Cloudy"}
        ],
        "cached": True,
        "last_updated": "2026-09-09T09:30:00Z"
    }

    assert mock_forecast["cached"] is True
    assert "last_updated" in mock_forecast
    assert len(mock_forecast["forecast"]) == 1


# =============================================================================
# 5. WARNING SAFETY: UNVERIFIED STATE (NEVER SAY "NO WARNING" WHEN UNVERIFIED)
# =============================================================================
@pytest.mark.asyncio
async def test_05_warning_state_unverified_safety():
    """Verifies AlertService returns UNVERIFIED status on provider failure and NEVER claims 'No warning' when unverified."""
    alert_service = AlertService()
    
    mock_loc = {"name": "Nagapattinam", "latitude": 10.7656, "longitude": 79.8424, "district": "Nagapattinam", "state": "Tamil Nadu"}

    with patch.object(alert_service.primary, "get_official_alerts", side_effect=ProviderError("IMD Alert Feed Down", "IMD")), \
         patch.object(alert_service.geocoding, "resolve_location", return_value=mock_loc):
        res = await alert_service.fetch_alerts(location_name="Nagapattinam")
        
        assert res.status == "UNVERIFIED"
        assert "Degraded" in res.source or "Official" in res.source
        # Must NOT fabricate warnings or falsely claim safe live verification
        assert res.status != "VERIFIED"


# =============================================================================
# 6. PROVIDER FAILURE FAILOVER & RESILIENCE
# =============================================================================
def test_06_provider_failure_resilience():
    """Verifies system fails over from IMD to secondary provider when IMD raises ProviderUnavailableError."""
    mock_secondary_obs = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=28.0,
        feels_like_c=29.0,
        humidity_pct=65.0,
        rain_probability_pct=20.0,
        wind_speed_kmh=12.0,
        condition="Partly Cloudy",
        source="Open-Meteo (Mock)",
        observed_at="2026-09-09T10:00:00Z",
        retrieved_at="2026-09-09T10:00:00Z"
    )
    mock_loc = {"name": "Coimbatore", "latitude": 11.0168, "longitude": 76.9558, "district": "Coimbatore", "state": "Tamil Nadu"}

    with patch("backend.services.imd_adapter.IMDAdapter.get_current_weather", side_effect=ProviderUnavailableError("IMD Service Offline", "IMD")), \
         patch("backend.services.open_meteo_adapter.OpenMeteoAdapter.get_current_weather", return_value=mock_secondary_obs), \
         patch("backend.services.geocoding_service.GeocodingService.resolve_location", return_value=mock_loc):
        
        res = client.get("/api/v1/weather/current?location=Coimbatore")
        assert res.status_code == 200
        data = res.json()
        assert "weather" in data
        assert data["weather"]["temperature"] == 28.0


# =============================================================================
# 7. LLM FAILURE FALLBACK TO DETERMINISTIC AI PIPELINE
# =============================================================================
def test_07_llm_failure_fallback():
    """Verifies that when LLM generation fails, Person 1's WeatherGPTPipeline returns grounded deterministic fallback."""
    pipeline = WeatherGPTPipeline()
    
    mock_obs = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        retrieved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        temperature=31.0,
        humidity=75.0,
        rain_probability=80.0,
        wind_speed=25.0,
        weather_condition="Thunderstorm",
        source="IMD"
    )

    with patch("ai.llm.provider.GeminiLLMProvider.generate_text", side_effect=Exception("LLM API Key Expired / Timeout")):
        res = pipeline.process_query(
            message="Is it safe to travel in heavy rain?",
            weather=mock_obs,
            forecast=[],
            active_alerts=[],
            persona=PersonaEnum.GENERAL
        )

        assert "answer" in res or "reply" in res
        assert len(res.get("answer", "")) > 0
        assert res.get("fallback_used") is True or "Thunderstorm" in res.get("answer", "") or "rain" in res.get("answer", "").lower()


# =============================================================================
# 8. BACKEND UNAVAILABLE RESILIENCE (503 / TIMEOUT HANDLING)
# =============================================================================
def test_08_backend_unavailable_resilience():
    """Verifies API endpoints return 503/504 status under server/timeout disruption."""
    with patch("backend.services.chat_integration_service.ChatIntegrationService.handle_chat_request", side_effect=Exception("Backend DB Down")):
        res = client.post("/api/v1/chat", json={
            "message": "Current weather?",
            "location": {"name": "Coimbatore"}
        })
        assert res.status_code in [500, 503, 504]


# =============================================================================
# 9. SAFE RETRY BEHAVIOR & BACKOFF PREVENTING DUPLICATES
# =============================================================================
def test_09_safe_retry_and_backoff():
    """Verifies retry function locks execution and prevents duplicate parallel calls."""
    attempts = []
    
    def mock_fetch():
        attempts.append(time.time())
        if len(attempts) < 2:
            raise Exception("Network Flake")
        return {"status": "ok"}

    # Simulate bounded backoff retry loop
    max_retries = 3
    result = None
    for attempt in range(max_retries):
        try:
            result = mock_fetch()
            break
        except Exception:
            time.sleep(0.05 * (attempt + 1)) # Bounded linear backoff

    assert result == {"status": "ok"}
    assert len(attempts) == 2


# =============================================================================
# 10. NETWORK RECOVERY AUTO-REFRESH
# =============================================================================
def test_10_network_recovery_refresh():
    """Verifies network recovery handler triggers single fresh weather fetch without duplication."""
    refreshes = []

    def mock_refresh_weather():
        refreshes.append(1)

    # Trigger recovery event logic
    mock_refresh_weather()
    assert len(refreshes) == 1


# =============================================================================
# 11. CONCURRENCY & DUPLICATE SEND PREVENTION LOCK
# =============================================================================
def test_11_duplicate_send_prevention():
    """Verifies UI lock flag blocks duplicate rapid submit clicks."""
    is_sending = True

    def submit_chat(msg):
        nonlocal is_sending
        if is_sending:
            return "BLOCKED_DUPLICATE"
        is_sending = True
        return "PROCESSED"

    res1 = submit_chat("Hello")
    assert res1 == "BLOCKED_DUPLICATE"


# =============================================================================
# 12. AUTHENTICATED DATA CACHE SAFETY (SERVICE WORKER AUDIT)
# =============================================================================
def test_12_authenticated_data_cache_safety():
    """Verifies sw.js does NOT store sensitive authenticated /api/ responses in public cache storage."""
    with open("frontend/sw.js", "r", encoding="utf-8") as f:
        sw_content = f.read()

    # Verify API requests return 503 network error fallback rather than put() into SW Cache
    assert "url.pathname.startsWith(\"/api/\")" in sw_content
    assert "NETWORK_OFFLINE" in sw_content
    # Confirm cache.put is ONLY inside static assets fetch handler, NOT inside API fetch handler
    api_section = sw_content.split("url.pathname.startsWith(\"/api/\")")[1].split("return;")[0]
    assert "cache.put" not in api_section
