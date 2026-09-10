"""Phase 1 Weather Reliability & Source Validation Test Suite.

Deterministic tests covering the 15 Phase 1 requirements:
1. Valid provider response with full source provenance (provider, timestamps, location, units, status)
2. Provider timeout handling & diagnostics preservation
3. Provider HTTP failure handling & error mapping
4. Malformed response handling
5. Empty response handling
6. Stale data detection (>180 mins)
7. Aging data detection (60-180 mins)
8. Missing required field handling (PARTIAL classification without crashing)
9. Impossible numeric values detection (physical atmospheric bounds)
10. Invalid coordinates detection
11. Multiple providers agreeing (no averaging, provenance preserved, HIGH consistency)
12. Multiple providers disagreeing (disagreement detected, individual values preserved, no averaging)
13. One provider failing while another succeeds (failover + diagnostics preserved)
14. All providers failing (graceful degradation)
15. IMD warning remaining authoritative & API secrets protected
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
import httpx

from backend.services.base_provider import BaseWeatherProvider
from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.current_weather_service import CurrentWeatherService
from backend.services.exceptions import (
    ProviderError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderAuthenticationError
)
from backend.services.schemas import (
    NormalizedWeatherObservation,
    NormalizedForecastItem,
    NormalizedAlertItem
)
from backend.services.weather_reliability import (
    FreshnessClassification,
    CompletenessClassification,
    ProviderStatusEnum,
    ValidationStatusEnum,
    PhysicalBounds,
    evaluate_weather_freshness,
    validate_weather_completeness
)
from backend.schemas.weather import CurrentWeatherResponse
from backend.config.settings import settings
from ai.models import RiskLevelEnum, SourceAgreementEnum, WeatherRecord as AIWeatherRecord


# ---------------------------------------------------------------------------
# 1. Valid provider response with full source provenance
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_01_valid_provider_response_provenance():
    """1. Valid provider response preserves provider, timestamps, location, variables, units, status."""
    service = CurrentWeatherService()
    res = await service.fetch_current_weather(location_name="Coimbatore")

    assert isinstance(res, CurrentWeatherResponse)
    assert res.location.name == "Coimbatore"
    assert res.location.latitude == pytest.approx(11.0168, rel=1e-2)
    assert res.location.longitude == pytest.approx(76.9558, rel=1e-2)

    # Core weather variables
    assert res.weather.temperature > -90.0
    assert 0.0 <= res.weather.humidity <= 100.0
    assert 0.0 <= res.weather.rain_probability <= 100.0
    assert res.weather.wind_speed >= 0.0
    assert res.weather.condition != ""

    # Provenance
    assert "IMD" in res.source
    assert res.observed_at is not None
    assert res.retrieved_at is not None
    assert res.units.temperature == "°C"
    assert res.units.humidity == "%"
    assert res.units.wind_speed == "km/h"

    # Reliability status
    assert res.freshness_status == FreshnessClassification.FRESH.value
    assert res.completeness_status == CompletenessClassification.COMPLETE.value
    assert res.validation_status == ValidationStatusEnum.VALID.value
    assert res.provider_status == ProviderStatusEnum.HEALTHY.value


# ---------------------------------------------------------------------------
# 2. Provider timeout handling & diagnostics preservation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_02_provider_timeout_diagnostics():
    """2. Simulated provider timeout raises ProviderTimeoutError with diagnostic context."""
    adapter = OpenMeteoAdapter(timeout=0.01, max_retries=0)

    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timed out")):
        with pytest.raises(ProviderTimeoutError) as exc_info:
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

        err = exc_info.value
        assert "timed out" in err.message.lower()
        assert err.provider_name == "Open-Meteo"
        assert "diagnostics" in dir(err)
        assert err.diagnostics["timeout"] == 0.01
        assert "attempt" in err.diagnostics


# ---------------------------------------------------------------------------
# 3. Provider HTTP failure handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_03_provider_http_failure_mapping():
    """3. Simulated HTTP 500/502 raises ProviderUnavailableError with status_code and diagnostics."""
    adapter = OpenMeteoAdapter(timeout=1.0, max_retries=0)

    mock_resp = httpx.Response(status_code=503, request=httpx.Request("GET", "https://api.open-meteo.com"))
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

        err = exc_info.value
        assert err.status_code == 503
        assert err.provider_name == "Open-Meteo"
        assert "503" in err.message


# ---------------------------------------------------------------------------
# 4. Malformed JSON response
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_04_malformed_json_response():
    """4. Unparseable non-JSON payload raises ProviderInvalidResponseError with diagnostics."""
    adapter = OpenMeteoAdapter(timeout=1.0, max_retries=0)

    mock_resp = httpx.Response(
        status_code=200,
        content=b"<html><body>502 Bad Gateway</body></html>",
        headers={"content-type": "text/html"},
        request=httpx.Request("GET", "https://api.open-meteo.com")
    )

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(ProviderInvalidResponseError) as exc_info:
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

        err = exc_info.value
        assert "Failed to parse JSON" in err.message or "Invalid" in str(err)
        assert err.status_code == 200
        assert err.diagnostics is not None


# ---------------------------------------------------------------------------
# 5. Empty response handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_05_empty_json_response():
    """5. Empty JSON response `{}` is detected as invalid response."""
    adapter = OpenMeteoAdapter(timeout=1.0, max_retries=0)

    mock_resp = httpx.Response(
        status_code=200,
        json={},
        request=httpx.Request("GET", "https://api.open-meteo.com")
    )

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(ProviderInvalidResponseError) as exc_info:
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

        assert "empty" in exc_info.value.message.lower()


# ---------------------------------------------------------------------------
# 6. Stale data detection (>180 mins)
# ---------------------------------------------------------------------------
def test_06_stale_data_detection():
    """6. Observation older than 180 minutes classified as STALE; never called real-time."""
    now = datetime.now(timezone.utc)
    old_time = (now - timedelta(minutes=240)).isoformat()

    freshness, age, meta = evaluate_weather_freshness(
        observed_at=old_time,
        retrieved_at=now.isoformat(),
        current_time=now
    )

    assert freshness == FreshnessClassification.STALE
    assert age == 240
    assert meta["is_real_time"] is False


# ---------------------------------------------------------------------------
# 7. Aging data detection (60-180 mins)
# ---------------------------------------------------------------------------
def test_07_aging_data_detection():
    """7. Observation between 60 and 180 minutes classified as AGING."""
    now = datetime.now(timezone.utc)
    aging_time = (now - timedelta(minutes=90)).isoformat()

    freshness, age, meta = evaluate_weather_freshness(
        observed_at=aging_time,
        retrieved_at=now.isoformat(),
        current_time=now
    )

    assert freshness == FreshnessClassification.AGING
    assert age == 90
    assert meta["is_real_time"] is False


# ---------------------------------------------------------------------------
# 8. Missing required field handling (PARTIAL classification)
# ---------------------------------------------------------------------------
def test_08_missing_required_field_partial():
    """8. Missing secondary field (e.g. pressure or wind) marks record PARTIAL without crash."""
    now = datetime.now(timezone.utc).isoformat()
    obs = {
        "location_name": "Coimbatore",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "temperature_c": 28.0,
        "humidity_pct": 70.0,
        # wind_speed_kmh is missing
        "rain_probability_pct": 20.0,
        "source": "IMD",
        "observed_at": now,
        "retrieved_at": now
    }

    comp, val, issues = validate_weather_completeness(obs)
    assert comp == CompletenessClassification.PARTIAL
    assert val == ValidationStatusEnum.WARNING
    assert any("wind" in issue.lower() for issue in issues)


# ---------------------------------------------------------------------------
# 9. Impossible numeric values detection (physical atmospheric bounds)
# ---------------------------------------------------------------------------
def test_09_impossible_numeric_values():
    """9. Impossible temperature or humidity triggers INVALID classification."""
    now = datetime.now(timezone.utc).isoformat()

    # Temperature 120°C (impossible)
    obs_bad_temp = {
        "location_name": "Coimbatore",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "temperature_c": 120.0,
        "humidity_pct": 60.0,
        "wind_speed_kmh": 15.0,
        "rain_probability_pct": 10.0,
        "source": "IMD",
        "observed_at": now,
        "retrieved_at": now
    }
    comp1, val1, issues1 = validate_weather_completeness(obs_bad_temp)
    assert comp1 == CompletenessClassification.INVALID
    assert val1 == ValidationStatusEnum.INVALID
    assert any("temperature" in i.lower() for i in issues1)

    # Humidity 150% (impossible)
    obs_bad_hum = {
        "location_name": "Coimbatore",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "temperature_c": 25.0,
        "humidity_pct": 150.0,
        "wind_speed_kmh": 15.0,
        "rain_probability_pct": 10.0,
        "source": "IMD",
        "observed_at": now,
        "retrieved_at": now
    }
    comp2, val2, issues2 = validate_weather_completeness(obs_bad_hum)
    assert comp2 == CompletenessClassification.INVALID
    assert val2 == ValidationStatusEnum.INVALID
    assert any("humidity" in i.lower() for i in issues2)


# ---------------------------------------------------------------------------
# 10. Invalid coordinates detection
# ---------------------------------------------------------------------------
def test_10_invalid_coordinates_detection():
    """10. Coordinates outside [-90, 90] and [-180, 180] rejected."""
    service = CurrentWeatherService()
    with pytest.raises(ValueError) as exc1:
        service.validate_coordinates(95.0, 77.0)
    assert "Latitude must be between -90 and +90" in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        service.validate_coordinates(11.0, -200.0)
    assert "Longitude must be between -180 and +180" in str(exc2.value)


# ---------------------------------------------------------------------------
# 11. Multiple providers agreeing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_11_multiple_providers_agreeing():
    """11. Providers agreeing yields HIGH confidence; preserves individual values without averaging."""
    service = CurrentWeatherService()

    now = datetime.now(timezone.utc).isoformat()
    obs_primary = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=29.0,
        humidity_pct=72.0,
        rain_probability_pct=65.0,
        wind_speed_kmh=18.0,
        rainfall_mm=10.0,
        condition="Moderate Rain",
        source="IMD",
        observed_at=now,
        retrieved_at=now
    )

    obs_secondary = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=28.5,
        humidity_pct=70.0,
        rain_probability_pct=60.0,
        wind_speed_kmh=16.0,
        rainfall_mm=8.0,
        condition="Rain",
        source="Open-Meteo",
        observed_at=now,
        retrieved_at=now
    )

    service.primary.get_current_weather = AsyncMock(return_value=obs_primary)
    service.secondary.get_current_weather = AsyncMock(return_value=obs_secondary)

    res = await service.fetch_current_weather(location_name="Coimbatore")
    assert res.comparison.sources_agree is True
    assert res.comparison.confidence_level == "HIGH"
    # Unaveraged values preserved
    assert res.weather.temperature == 29.0
    assert res.comparison.secondary_temperature == 28.5
    assert res.weather.rain_probability == 65.0
    assert res.comparison.secondary_rain_probability == 60.0


# ---------------------------------------------------------------------------
# 12. Multiple providers disagreeing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_multiple_providers_disagreeing():
    """12. Providers disagreeing: disagreement detected, NO averaging, individual values kept."""
    service = CurrentWeatherService()

    now = datetime.now(timezone.utc).isoformat()
    obs_primary = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=32.0,
        humidity_pct=85.0,
        rain_probability_pct=85.0,
        wind_speed_kmh=35.0,
        rainfall_mm=25.0,
        condition="Heavy Rain",
        source="IMD",
        observed_at=now,
        retrieved_at=now
    )

    obs_secondary = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=24.0,
        humidity_pct=40.0,
        rain_probability_pct=10.0,
        wind_speed_kmh=10.0,
        rainfall_mm=0.0,
        condition="Clear",
        source="Open-Meteo",
        observed_at=now,
        retrieved_at=now
    )

    service.primary.get_current_weather = AsyncMock(return_value=obs_primary)
    service.secondary.get_current_weather = AsyncMock(return_value=obs_secondary)

    res = await service.fetch_current_weather(location_name="Coimbatore")
    assert res.comparison.sources_agree is False
    assert res.comparison.confidence_level in ("CAUTIOUS", "MEDIUM")
    assert res.comparison.disagreement_notes is not None

    # Crucial check: NOT averaged!
    assert res.weather.temperature == 32.0  # NOT (32+24)/2 = 28.0
    assert res.comparison.secondary_temperature == 24.0
    assert res.weather.rain_probability == 85.0  # NOT (85+10)/2 = 47.5
    assert res.comparison.secondary_rain_probability == 10.0


# ---------------------------------------------------------------------------
# 13. One provider failing while another succeeds (Failover & Diagnostics)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_provider_failover_resilience():
    """13. Primary provider fails, secondary succeeds; status DEGRADED and failure diagnostic logged."""
    service = CurrentWeatherService()

    now = datetime.now(timezone.utc).isoformat()
    obs_secondary = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=28.0,
        humidity_pct=70.0,
        rain_probability_pct=40.0,
        wind_speed_kmh=14.0,
        rainfall_mm=0.0,
        condition="Cloudy",
        source="Open-Meteo",
        observed_at=now,
        retrieved_at=now
    )

    service.primary.get_current_weather = AsyncMock(
        side_effect=ProviderUnavailableError("IMD server unreachable", provider_name="IMD", status_code=502)
    )
    service.secondary.get_current_weather = AsyncMock(return_value=obs_secondary)

    res = await service.fetch_current_weather(location_name="Coimbatore")
    assert res.provider_status == "DEGRADED"
    assert "Fallback" in res.source or "Open-Meteo" in res.source
    assert res.weather.temperature == 28.0
    assert res.provider_diagnostics is not None
    assert res.provider_diagnostics["failed_provider"] == "IMD"
    assert "IMD server unreachable" in res.provider_diagnostics["error_message"]


# ---------------------------------------------------------------------------
# 14. All providers failing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_14_all_providers_failing():
    """14. When all providers fail, a clean ProviderError is propagated with diagnostics."""
    service = CurrentWeatherService()

    service.primary.get_current_weather = AsyncMock(
        side_effect=ProviderTimeoutError("IMD timeout", provider_name="IMD")
    )
    service.secondary.get_current_weather = AsyncMock(
        side_effect=ProviderUnavailableError("Open-Meteo down", provider_name="Open-Meteo")
    )

    with pytest.raises(ProviderError) as exc_info:
        await service.fetch_current_weather(location_name="Coimbatore")

    assert "Open-Meteo" in str(exc_info.value) or "IMD" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 15. IMD warning remaining authoritative & API secrets protected
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_15_imd_warning_authority_and_secrets():
    """15. Official IMD alert is authoritative; ensures API secrets are NEVER exposed."""
    service = CurrentWeatherService()

    now = datetime.now(timezone.utc).isoformat()
    alert = NormalizedAlertItem(
        alert_type="cyclone",
        severity="extreme",
        title="Cyclone Warning",
        description="Severe cyclonic storm making landfall.",
        instructions="Evacuate coastal areas immediately.",
        area="Nagapattinam",
        source="IMD",
        issued_at=now,
        expires_at=now,
        retrieved_at=now
    )

    # Even if secondary provider thinks it's calm, IMD alert is present
    service.primary.get_official_alerts = AsyncMock(return_value=[alert])

    res = await service.fetch_current_weather(location_name="Nagapattinam")
    assert len(res.alerts) == 1
    assert res.alerts[0]["severity"] == "extreme"
    assert res.alerts[0]["source"] == "IMD"
    assert "Evacuate" in res.alerts[0]["instructions"]

    # Security check: Ensure secret keys are never present in response model or serialization
    serialized = res.model_dump_json()
    assert settings.SECRET_KEY not in serialized
    assert settings.JWT_ALGORITHM not in serialized
    assert "SECRET" not in serialized.upper() or "weathergpt-super-secret" not in serialized
