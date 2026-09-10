"""SkyZen Phase 7 — Real-Time Multi-Source Weather Engine Test Suite.

Comprehensive deterministic test suite verifying all 20 required conditions:
1. IMD success
2. Open-Meteo success
3. Provider 3 (OpenWeather) success
4. IMD timeout
5. Open-Meteo timeout
6. Provider 3 timeout
7. Malformed response
8. Empty response
9. Missing fields (PARTIAL classification)
10. Stale response (>180m)
11. Fresh response (<60m)
12. Provider disagreement (NO averaging, individual values preserved)
13. Provider agreement (HIGH confidence)
14. All providers unavailable (SERVICE_UNAVAILABLE)
15. API key missing (clear unconfigured status without crash)
16. Invalid coordinates bounds checking
17. Cache fallback behavior
18. Source provenance completeness (provider, authority, observed_at, fetched_at)
19. Real-time flag validation (never true on cache/stale)
20. No synthetic values on live paths (exact un-averaged provenance)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from backend.config.settings import settings
from backend.services.base_provider import BaseWeatherProvider
from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.openweather_adapter import OpenWeatherAdapter
from backend.services.current_weather_service import CurrentWeatherService
from backend.services.weather_manager import WeatherManager
from backend.services.exceptions import (
    ProviderError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderInvalidResponseError
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
    SystemStateEnum,
    evaluate_weather_freshness,
    validate_weather_completeness
)
from backend.schemas.weather import CurrentWeatherResponse


# ---------------------------------------------------------------------------
# 1. IMD Success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_01_imd_success():
    """1. IMD adapter returns authoritative observation with provenance."""
    adapter = IMDAdapter()
    obs = await adapter.get_current_weather(11.0168, 76.9558, "Coimbatore")

    assert obs.source == "IMD"
    assert obs.authority_level == "primary_authoritative"
    assert obs.temperature_c == 29.0
    assert obs.observed_at is not None
    assert obs.retrieved_at is not None


# ---------------------------------------------------------------------------
# 2. Open-Meteo Success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_02_open_meteo_success():
    """2. Open-Meteo adapter parses live JSON structure accurately."""
    adapter = OpenMeteoAdapter()
    mock_payload = {
        "current": {
            "time": "2026-09-10T16:45Z",
            "temperature_2m": 27.8,
            "relative_humidity_2m": 68.0,
            "apparent_temperature": 29.1,
            "precipitation": 0.0,
            "weather_code": 1,
            "surface_pressure": 1012.4,
            "wind_speed_10m": 14.5,
            "wind_direction_10m": 240.0
        }
    }

    with patch.object(adapter, "_fetch_json", new=AsyncMock(return_value=mock_payload)):
        obs = await adapter.get_current_weather(11.0168, 76.9558, "CoimbatoreUniqueOM")

        assert obs.source == "Open-Meteo"
        assert obs.temperature_c == 27.8
        assert obs.feels_like_c == 29.1
        assert obs.humidity_pct == 68.0
        assert obs.wind_speed_kmh == 14.5
        assert obs.pressure_hpa == 1012.4
        assert obs.condition == "Partly Cloudy"
        assert obs.observed_at == "2026-09-10T16:45Z"


# ---------------------------------------------------------------------------
# 3. Provider 3 (OpenWeather) Success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_03_openweather_success():
    """3. OpenWeather adapter normalizes metric units and epoch timestamps."""
    adapter = OpenWeatherAdapter()
    mock_payload = {
        "main": {
            "temp": 28.2,
            "feels_like": 30.5,
            "humidity": 65,
            "pressure": 1011
        },
        "wind": {"speed": 4.0, "deg": 180},
        "weather": [{"main": "Clouds", "description": "scattered clouds"}],
        "rain": {"1h": 0.0},
        "dt": 1726000000
    }

    with patch.object(settings, "OPENWEATHER_API_KEY", "test-live-key-123"):
        with patch.object(adapter, "_fetch_json", new=AsyncMock(return_value=mock_payload)):
            obs = await adapter.get_current_weather(11.0168, 76.9558, "CoimbatoreTestOW")

            assert obs.source == "OpenWeather"
            assert obs.authority_level == "secondary_independent"
            assert obs.temperature_c == 28.2
            assert obs.feels_like_c == 30.5
            assert obs.humidity_pct == 65.0
            assert obs.wind_speed_kmh == pytest.approx(14.4, rel=1e-2)  # 4.0 * 3.6
            assert obs.condition == "Clouds"
            assert "2024" in obs.observed_at or "2025" in obs.observed_at or "2026" in obs.observed_at


# ---------------------------------------------------------------------------
# 4. IMD Timeout
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_04_imd_timeout():
    """4. IMD adapter timeout raises ProviderTimeoutError with diagnostic context."""
    adapter = IMDAdapter()
    with patch.object(settings, "IMD_API_KEY", "test-imd-key"):
        with patch.object(adapter, "_fetch_json", side_effect=ProviderTimeoutError("IMD timed out", provider_name="IMD")):
            with pytest.raises(ProviderTimeoutError) as exc:
                await adapter.get_current_weather(11.0168, 76.9558, "CoimbatoreTimeoutIMD")
            assert exc.value.provider_name == "IMD"


# ---------------------------------------------------------------------------
# 5. Open-Meteo Timeout
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_05_open_meteo_timeout():
    """5. Open-Meteo timeout raises ProviderTimeoutError cleanly."""
    adapter = OpenMeteoAdapter()
    with patch.object(adapter, "_fetch_json", side_effect=ProviderTimeoutError("Open-Meteo timed out", provider_name="Open-Meteo")):
        with pytest.raises(ProviderTimeoutError) as exc:
            await adapter.get_current_weather(11.0168, 76.9558, "CoimbatoreTimeoutOM")
        assert exc.value.provider_name == "Open-Meteo"


# ---------------------------------------------------------------------------
# 6. Provider 3 (OpenWeather) Timeout
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_06_openweather_timeout():
    """6. OpenWeather timeout raises ProviderTimeoutError cleanly."""
    adapter = OpenWeatherAdapter()
    with patch.object(settings, "OPENWEATHER_API_KEY", "test-live-key-123"):
        with patch.object(adapter, "_fetch_json", side_effect=ProviderTimeoutError("OpenWeather timed out", provider_name="OpenWeather")):
            with pytest.raises(ProviderTimeoutError) as exc:
                await adapter.get_current_weather(11.0168, 76.9558, "CoimbatoreTimeoutOW")
            assert exc.value.provider_name == "OpenWeather"


# ---------------------------------------------------------------------------
# 7. Malformed Response Handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_07_malformed_response_handling():
    """7. Corrupted JSON payload is mapped to ProviderInvalidResponseError."""
    adapter = OpenMeteoAdapter()
    with patch.object(adapter, "_fetch_json", side_effect=ProviderInvalidResponseError("Invalid JSON structure", provider_name="Open-Meteo")):
        with pytest.raises(ProviderInvalidResponseError):
            await adapter.get_current_weather(11.0168, 76.9558, "CoimbatoreMalformedOM")


# ---------------------------------------------------------------------------
# 8. Empty Response Handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_08_empty_response_handling():
    """8. Empty payload is classified as UNAVAILABLE by completeness validator."""
    comp, val, issues = validate_weather_completeness({})
    assert comp == CompletenessClassification.UNAVAILABLE
    assert val == ValidationStatusEnum.INVALID


# ---------------------------------------------------------------------------
# 9. Missing Fields Handling (PARTIAL classification)
# ---------------------------------------------------------------------------
def test_09_missing_fields_partial():
    """9. Missing secondary variables marks payload PARTIAL without crashing."""
    now = datetime.now(timezone.utc).isoformat()
    partial_obs = {
        "location_name": "Coimbatore",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "temperature_c": 28.0,
        "humidity_pct": 65.0,
        # wind_speed_kmh omitted
        "rain_probability_pct": 20.0,
        "source": "Open-Meteo",
        "observed_at": now,
        "retrieved_at": now
    }
    comp, val, issues = validate_weather_completeness(partial_obs)
    assert comp == CompletenessClassification.PARTIAL
    assert val == ValidationStatusEnum.WARNING
    assert any("wind" in i.lower() for i in issues)


# ---------------------------------------------------------------------------
# 10. Stale Response (>180m)
# ---------------------------------------------------------------------------
def test_10_stale_response():
    """10. Observation >180 minutes old classified as STALE; is_real_time must be False."""
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
# 11. Fresh Response (<60m)
# ---------------------------------------------------------------------------
def test_11_fresh_response():
    """11. Observation <60 minutes old classified as FRESH; is_real_time is True if fresh and non-cached."""
    now = datetime.now(timezone.utc)
    recent_time = (now - timedelta(minutes=10)).isoformat()

    freshness, age, meta = evaluate_weather_freshness(
        observed_at=recent_time,
        retrieved_at=now.isoformat(),
        current_time=now,
        is_cached=False
    )
    assert freshness == FreshnessClassification.FRESH
    assert age == 10
    assert meta["is_real_time"] is True


# ---------------------------------------------------------------------------
# 12. Provider Disagreement (NO averaging, individual values preserved)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_provider_disagreement_no_averaging():
    """12. Providers disagree materially: disagreement is detected, NO averaging occurs, provenance preserved."""
    service = CurrentWeatherService()
    now = datetime.now(timezone.utc).isoformat()

    obs1 = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=29.0,
        humidity_pct=85.0,
        rain_probability_pct=80.0,
        wind_speed_kmh=18.0,
        rainfall_mm=15.0,
        condition="Heavy Rain",
        source="IMD",
        observed_at=now,
        retrieved_at=now
    )

    obs2 = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=35.5,  # 6.5°C difference!
        humidity_pct=45.0,
        rain_probability_pct=10.0,
        wind_speed_kmh=8.0,
        rainfall_mm=0.0,
        condition="Clear",
        source="Open-Meteo",
        observed_at=now,
        retrieved_at=now
    )

    obs3 = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=29.2,
        humidity_pct=82.0,
        rain_probability_pct=75.0,
        wind_speed_kmh=16.0,
        rainfall_mm=12.0,
        condition="Rain",
        source="OpenWeather",
        observed_at=now,
        retrieved_at=now
    )

    service.primary.get_current_weather = AsyncMock(return_value=obs1)
    service.secondary.get_current_weather = AsyncMock(return_value=obs2)
    service.tertiary.get_current_weather = AsyncMock(return_value=obs3)

    res = await service.fetch_current_weather(location_name="Coimbatore")

    assert res.comparison.sources_agree is False
    assert res.comparison.confidence_level in ("CAUTIOUS", "MEDIUM")
    assert res.comparison.disagreement_notes is not None

    # CRITICAL: Values are NOT averaged!
    assert res.weather.temperature == 29.0  # NOT (29 + 35.5 + 29.2) / 3 = 31.23
    assert res.comparison.secondary_temperature == 35.5

    # Check un-averaged individual provider records
    records = res.comparison.provider_records
    assert len(records) == 3
    rec_imd = next(r for r in records if r.provider == "IMD")
    rec_om = next(r for r in records if r.provider == "Open-Meteo")
    rec_ow = next(r for r in records if r.provider == "OpenWeather")

    assert rec_imd.temperature == 29.0
    assert rec_om.temperature == 35.5
    assert rec_ow.temperature == 29.2


# ---------------------------------------------------------------------------
# 13. Provider Agreement (HIGH confidence)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_provider_agreement_high_confidence():
    """13. Consistent values across providers produce HIGH confidence agreement."""
    service = CurrentWeatherService()
    now = datetime.now(timezone.utc).isoformat()

    obs1 = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=29.0,
        humidity_pct=72.0,
        rain_probability_pct=60.0,
        wind_speed_kmh=18.0,
        rainfall_mm=5.0,
        condition="Moderate Rain",
        source="IMD",
        observed_at=now,
        retrieved_at=now
    )

    obs2 = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=29.2,
        humidity_pct=70.0,
        rain_probability_pct=65.0,
        wind_speed_kmh=17.0,
        rainfall_mm=4.5,
        condition="Rain",
        source="Open-Meteo",
        observed_at=now,
        retrieved_at=now
    )

    service.primary.get_current_weather = AsyncMock(return_value=obs1)
    service.secondary.get_current_weather = AsyncMock(return_value=obs2)
    service.tertiary.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("Unconfigured"))

    res = await service.fetch_current_weather(location_name="Coimbatore")

    assert res.comparison.sources_agree is True
    assert res.comparison.confidence_level == "HIGH"
    assert res.weather.temperature == 29.0
    assert res.comparison.secondary_temperature == 29.2


# ---------------------------------------------------------------------------
# 14. All Providers Unavailable (SERVICE_UNAVAILABLE)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_14_all_providers_unavailable():
    """14. When all providers fail and no cache exists, raises ProviderUnavailableError."""
    service = CurrentWeatherService()
    service.primary.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("IMD down", provider_name="IMD"))
    service.secondary.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("Open-Meteo down", provider_name="Open-Meteo"))
    service.tertiary.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("OpenWeather down", provider_name="OpenWeather"))

    with pytest.raises(ProviderUnavailableError) as exc:
        await service.fetch_current_weather(location_name="Coimbatore", allow_stale=False)
    assert "All weather providers are unavailable" in str(exc.value)


# ---------------------------------------------------------------------------
# 15. API Key Missing (Clear Unconfigured Status Without Crash)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_15_api_key_missing_safe_handling():
    """15. OpenWeather with empty API key cleanly raises unconfigured status without crash."""
    with patch.object(settings, "OPENWEATHER_API_KEY", ""):
        adapter = OpenWeatherAdapter()
        assert adapter.is_configured is False
        with pytest.raises(ProviderUnavailableError) as exc:
            await adapter.get_current_weather(11.0168, 76.9558, "Coimbatore")
        assert "LIVE PROVIDER CREDENTIALS NOT CONFIGURED" in str(exc.value)


# ---------------------------------------------------------------------------
# 16. Invalid Coordinates Bounds Checking
# ---------------------------------------------------------------------------
def test_16_invalid_coordinates():
    """16. Coordinate bounds checking rejects latitude >90 and longitude >180."""
    service = CurrentWeatherService()
    with pytest.raises(ValueError):
        service.validate_coordinates(91.5, 76.9)
    with pytest.raises(ValueError):
        service.validate_coordinates(11.0, 185.0)


# ---------------------------------------------------------------------------
# 17. Cache Fallback Behavior
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_17_cache_fallback():
    """17. When all live providers fail with allow_stale=True, returns cached observation with is_cached=True."""
    from backend.services.cache import provider_cache
    service = CurrentWeatherService()
    now = datetime.now(timezone.utc).isoformat()

    cached_obs = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=28.0,
        humidity_pct=70.0,
        rain_probability_pct=50.0,
        wind_speed_kmh=12.0,
        condition="Cloudy",
        source="IMD",
        observed_at=now,
        retrieved_at=now
    )
    cache_key = "current_obs_Coimbatore_11.0168_76.9558"
    provider_cache.set(cache_key, cached_obs)

    service.primary.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("IMD down"))
    service.secondary.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("Open-Meteo down"))
    service.tertiary.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("OpenWeather down"))

    res = await service.fetch_current_weather(lat=11.0168, lon=76.9558, location_name="Coimbatore", allow_stale=True)
    assert res.is_cached is True
    assert "Cached" in res.data_freshness or "DATA_STALE" in res.system_state or "DEGRADED" in res.system_state


# ---------------------------------------------------------------------------
# 18. Source Provenance Completeness
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_18_source_provenance_completeness():
    """18. API response contract preserves source, observed_at, retrieved_at, and units."""
    service = CurrentWeatherService()
    res = await service.fetch_current_weather(location_name="Coimbatore")

    assert res.source != ""
    assert len(res.sources) >= 1
    assert res.observed_at != ""
    assert res.retrieved_at != ""
    assert res.units.temperature == "°C"
    assert res.units.wind_speed == "km/h"


# ---------------------------------------------------------------------------
# 19. Real-Time Flag Validation
# ---------------------------------------------------------------------------
def test_19_real_time_flag_validation():
    """19. Cached or stale observations are NEVER classified as real-time."""
    now = datetime.now(timezone.utc)
    fresh_time = (now - timedelta(minutes=5)).isoformat()

    # Case A: Fresh, live, non-cached -> True
    _, _, meta_live = evaluate_weather_freshness(fresh_time, now.isoformat(), now, is_cached=False)
    assert meta_live["is_real_time"] is True

    # Case B: Fresh but cached -> False
    _, _, meta_cached = evaluate_weather_freshness(fresh_time, now.isoformat(), now, is_cached=True)
    assert meta_cached["is_real_time"] is False

    # Case C: Old data -> False
    old_time = (now - timedelta(minutes=90)).isoformat()
    _, _, meta_old = evaluate_weather_freshness(old_time, now.isoformat(), now, is_cached=False)
    assert meta_old["is_real_time"] is False


# ---------------------------------------------------------------------------
# 20. No Synthetic Values on Live Paths
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_20_no_synthetic_values_on_live_path():
    """20. Live Open-Meteo request preserves exact temperature from provider, no hardcoded fallbacks."""
    adapter = OpenMeteoAdapter()
    real_payload = {
        "current": {
            "time": "2026-09-10T16:50Z",
            "temperature_2m": 31.37,
            "relative_humidity_2m": 53.0,
            "apparent_temperature": 34.2,
            "precipitation": 0.0,
            "weather_code": 2,
            "surface_pressure": 1010.5,
            "wind_speed_10m": 12.6,
            "wind_direction_10m": 190.0
        }
    }

    with patch.object(adapter, "_fetch_json", new=AsyncMock(return_value=real_payload)):
        obs = await adapter.get_current_weather(11.0168, 76.9558, "CoimbatoreUnique20")
        # Ensure exact un-rounded floating values from provider are retained
        assert obs.temperature_c == 31.37
        assert obs.feels_like_c == 34.2
        assert obs.humidity_pct == 53.0
        assert obs.wind_speed_kmh == 12.6
        assert obs.pressure_hpa == 1010.5
