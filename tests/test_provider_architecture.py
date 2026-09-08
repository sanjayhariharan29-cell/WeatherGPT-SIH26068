"""Phase 3 Weather Provider Architecture Tests.

Verifies provider abstraction contract, normalized data models, exception hierarchy,
source metadata preservation, TTL caching, HTTP retry mapping, and Person 1 AI model compatibility.
"""

import time
import pytest
from unittest.mock import AsyncMock, patch
import httpx

from backend.services.base_provider import BaseWeatherProvider
from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.nasa_power_adapter import NasaPowerAdapter
from backend.services.weather_manager import WeatherManager
from backend.services.cache import ProviderCache
from backend.services.exceptions import (
    ProviderError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderRateLimitedError,
    ProviderAuthenticationError,
    ProviderInvalidResponseError
)
from backend.services.schemas import (
    NormalizedWeatherObservation,
    NormalizedForecastItem,
    NormalizedAlertItem,
    NormalizedHistoricalWeather,
    NormalizedClimateTrend
)
from ai.models import WeatherRecord as AIWeatherRecord, OfficialAlert as AIOfficialAlert


def test_provider_inheritance():
    """Verify all adapters inherit from BaseWeatherProvider and fulfill properties."""
    imd = IMDAdapter()
    open_meteo = OpenMeteoAdapter()
    nasa = NasaPowerAdapter()

    assert isinstance(imd, BaseWeatherProvider)
    assert isinstance(open_meteo, BaseWeatherProvider)
    assert isinstance(nasa, BaseWeatherProvider)

    assert imd.name == "IMD"
    assert imd.authority_level == "primary_authoritative"

    assert open_meteo.name == "Open-Meteo"
    assert open_meteo.authority_level == "secondary_forecast"

    assert nasa.name == "NASA POWER"
    assert nasa.authority_level == "historical_climate"


@pytest.mark.asyncio
async def test_normalized_observation_schemas():
    """Verify normalized weather observation fields, provenance, and dict compatibility."""
    imd = IMDAdapter()
    obs = await imd.get_current_weather(11.0168, 76.9558, "Coimbatore")

    assert isinstance(obs, NormalizedWeatherObservation)
    assert obs.location_name == "Coimbatore"
    assert obs.temperature_c == 29.0
    assert obs.source == "IMD"
    assert obs.authority_level == "primary_authoritative"
    assert obs.observed_at is not None
    assert obs.retrieved_at is not None

    # Test backward compatibility subscription
    assert obs["temperature"] == 29.0
    assert obs["rain_probability"] == 65.0
    assert "temperature" in obs
    assert obs.get("humidity") == 72.0


@pytest.mark.asyncio
async def test_ai_model_conversion():
    """Verify clean conversion from normalized models to Person 1's AI models."""
    imd = IMDAdapter()
    obs = await imd.get_current_weather(10.7656, 79.8424, "Nagapattinam")
    alerts = await imd.get_official_alerts(10.7656, 79.8424, "Nagapattinam")

    ai_obs = obs.to_ai_weather_record()
    assert isinstance(ai_obs, AIWeatherRecord)
    assert ai_obs.location.name == "Nagapattinam"
    assert ai_obs.temperature == 27.5
    assert ai_obs.source == "IMD"

    assert len(alerts) >= 1
    ai_alert = alerts[0].to_ai_official_alert()
    assert isinstance(ai_alert, AIOfficialAlert)
    assert ai_alert.source == "IMD"
    assert "Heavy Rain" in ai_alert.title


def test_provider_cache_ttl():
    """Verify in-memory TTL caching behavior."""
    cache = ProviderCache(default_ttl=1)
    cache.set("key1", "val1")

    assert cache.get("key1") == "val1"
    time.sleep(1.1)
    assert cache.get("key1") is None


@pytest.mark.asyncio
async def test_weather_manager_ai_input():
    """Verify WeatherManager provides Pydantic input models for Weather Reasoner."""
    manager = WeatherManager()
    ai_obs, ai_forecasts, ai_alerts = await manager.get_ai_weather_input(11.0168, 76.9558, "Coimbatore")

    assert isinstance(ai_obs, AIWeatherRecord)
    assert isinstance(ai_forecasts, list)
    assert isinstance(ai_alerts, list)
    assert ai_obs.location.name == "Coimbatore"


@pytest.mark.asyncio
async def test_http_exception_mapping():
    """Verify HTTP error status mapping to custom Provider exception hierarchy."""
    provider = OpenMeteoAdapter(timeout=1.0, max_retries=0)

    # Test 401 Auth Error
    mock_resp_401 = AsyncMock()
    mock_resp_401.status_code = 401

    with patch("httpx.AsyncClient.get", return_value=mock_resp_401):
        with pytest.raises(ProviderAuthenticationError) as exc_info:
            await provider._fetch_json("https://dummy.url")
        assert exc_info.value.provider_name == "Open-Meteo"

    # Test 429 Rate Limit Error
    mock_resp_429 = AsyncMock()
    mock_resp_429.status_code = 429

    with patch("httpx.AsyncClient.get", return_value=mock_resp_429):
        with pytest.raises(ProviderRateLimitedError):
            await provider._fetch_json("https://dummy.url")

    # Test 500 Server Error
    mock_resp_500 = AsyncMock()
    mock_resp_500.status_code = 500

    with patch("httpx.AsyncClient.get", return_value=mock_resp_500):
        with pytest.raises(ProviderUnavailableError):
            await provider._fetch_json("https://dummy.url")

    # Test Timeout Error
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(ProviderTimeoutError):
            await provider._fetch_json("https://dummy.url")
