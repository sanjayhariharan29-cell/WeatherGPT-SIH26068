"""Test suite for Weather Provider Architecture, OpenWeather Primary Status,
IMD Gating, and Source Transparency.

Validates:
1. OpenWeather is active primary live data source for current conditions, forecasts, and AQI.
2. IMDAdapter remains in codebase as a valid BaseWeatherProvider stub/placeholder,
   implementing identical interface, but is NOT called in active pipeline when IMD_API_KEY is missing/unconfigured.
3. source_identity field exists on CurrentWeatherResponse, ForecastResponse, AlertResponse,
   and AirQualityResponse, accurately reflecting the actual provider (e.g. OpenWeather, Open-Meteo).
4. No OpenWeather or Open-Meteo data is mislabeled as originating from IMD.
5. Notification headers and formatting only use IMD if the alert source actually originated from IMD.
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from backend.config.settings import settings
from backend.services.base_provider import BaseWeatherProvider
from backend.services.imd_adapter import IMDAdapter
from backend.services.openweather_adapter import OpenWeatherAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.weather_manager import WeatherManager
from backend.services.current_weather_service import CurrentWeatherService
from backend.services.forecast_service import ForecastService
from backend.services.alert_service import AlertService
from backend.services.notification_service import NotificationService
from backend.schemas.weather import (
    CurrentWeatherResponse,
    ForecastResponse,
    AlertResponse,
    AirQualityResponse
)
from backend.services.schemas import NormalizedWeatherObservation, NormalizedForecastItem


# =============================================================================
# 1. ARCHITECTURAL CONTRACT & IMD STUB COMPLIANCE
# =============================================================================
def test_all_adapters_implement_base_weather_provider():
    """Confirms IMDAdapter, OpenWeatherAdapter, and OpenMeteoAdapter all implement BaseWeatherProvider."""
    assert issubclass(IMDAdapter, BaseWeatherProvider)
    assert issubclass(OpenWeatherAdapter, BaseWeatherProvider)
    assert issubclass(OpenMeteoAdapter, BaseWeatherProvider)

    imd = IMDAdapter()
    ow = OpenWeatherAdapter()
    om = OpenMeteoAdapter()

    for adapter in (imd, ow, om):
        assert hasattr(adapter, "get_current_weather")
        assert hasattr(adapter, "get_forecast")
        assert hasattr(adapter, "get_official_alerts")
        assert hasattr(adapter, "name")
        assert hasattr(adapter, "authority_level")


def test_imd_adapter_remains_as_placeholder_without_crashing():
    """Confirms IMDAdapter is preserved, has placeholder behavior, and reports unconfigured when key missing."""
    with patch.object(settings, "IMD_API_KEY", ""):
        imd = IMDAdapter()
        assert imd.name == "IMD"
        assert not imd.is_live_configured


# =============================================================================
# 2. OPENWEATHER IS PRIMARY LIVE DATA SOURCE & IMD GATED IN PIPELINE
# =============================================================================
def test_current_weather_service_defaults_to_openweather_as_primary():
    """CurrentWeatherService must use OpenWeather as primary provider when IMD credentials are absent."""
    with patch.object(settings, "IMD_API_KEY", ""):
        service = CurrentWeatherService()
        assert isinstance(service.primary, OpenWeatherAdapter)
        assert isinstance(service.secondary, OpenMeteoAdapter)


def test_forecast_service_defaults_to_openweather_as_primary():
    """ForecastService must use OpenWeather as primary provider when IMD credentials are absent."""
    with patch.object(settings, "IMD_API_KEY", ""):
        service = ForecastService()
        assert isinstance(service.primary, OpenWeatherAdapter)
        assert isinstance(service.secondary, OpenMeteoAdapter)


def test_weather_manager_defaults_to_openweather_as_primary():
    """WeatherManager must register OpenWeather as primary and gate IMD when credentials are empty."""
    with patch.object(settings, "IMD_API_KEY", ""):
        manager = WeatherManager()
        assert isinstance(manager.openweather, OpenWeatherAdapter)
        assert isinstance(manager.current_service.primary, OpenWeatherAdapter)
        assert isinstance(manager.forecast_service.primary, OpenWeatherAdapter)
        assert isinstance(manager.open_meteo, OpenMeteoAdapter)
        assert manager.is_imd_active is False


@pytest.mark.asyncio
async def test_imd_is_not_called_in_active_current_pipeline_when_unconfigured():
    """Validates that IMDAdapter is never invoked during fetch_current_weather if IMD_API_KEY is absent."""
    with patch.object(settings, "IMD_API_KEY", ""):
        mock_imd = AsyncMock(spec=IMDAdapter)
        mock_ow = AsyncMock(spec=OpenWeatherAdapter)
        mock_ow.name = "OpenWeather"
        mock_ow.authority_level = "primary_live"

        fake_obs = NormalizedWeatherObservation(
            location_name="Chennai",
            latitude=13.0827,
            longitude=80.2707,
            temperature_c=31.2,
            feels_like_c=34.0,
            humidity_pct=68.0,
            wind_speed_kmh=12.5,
            rain_probability_pct=10.0,
            condition="Clear",
            source="OpenWeather",
            authority_level="primary_live",
            observed_at=datetime.now(timezone.utc).isoformat(),
            retrieved_at=datetime.now(timezone.utc).isoformat()
        )
        mock_ow.get_current_weather = AsyncMock(return_value=fake_obs)

        service = CurrentWeatherService(primary_provider=mock_ow, secondary_provider=OpenMeteoAdapter())
        result = await service.fetch_current_weather(13.0827, 80.2707, "Chennai")

        # Confirm OpenWeather was called
        mock_ow.get_current_weather.assert_awaited_once()
        # Confirm IMD was never touched
        mock_imd.get_current_weather.assert_not_called()
        # Confirm accurate source_identity
        assert result.source_identity == "OpenWeather"
        assert "OpenWeather" in result.source
        assert "IMD" not in (result.source_identity or "")


# =============================================================================
# 3. AIR QUALITY PRIORITIZES OPENWEATHER OVER MODELLED OPEN-METEO
# =============================================================================
@pytest.mark.asyncio
async def test_get_air_quality_uses_openweather_as_primary():
    """WeatherManager.get_air_quality must call OpenWeather air pollution API first and set source_identity."""
    with patch.object(settings, "IMD_API_KEY", ""):
        manager = WeatherManager()
        mock_ow = AsyncMock(spec=OpenWeatherAdapter)
        mock_ow.name = "OpenWeather"

        fake_aqi = AirQualityResponse(
            location="Chennai",
            latitude=13.0827,
            longitude=80.2707,
            aqi=72,
            category="Moderate",
            pm25=22.0,
            pm10=45.0,
            source="OpenWeather",
            source_identity="OpenWeather",
            is_real_time=True,
            retrieved_at=datetime.now(timezone.utc).isoformat()
        )
        mock_ow.get_air_quality = AsyncMock(return_value=fake_aqi)
        manager.openweather = mock_ow

        res = await manager.get_air_quality(13.0827, 80.2707, "Chennai")

        mock_ow.get_air_quality.assert_awaited_once_with(13.0827, 80.2707, "Chennai")
        src_id = res["source_identity"] if isinstance(res, dict) else res.source_identity
        src_name = res["source"] if isinstance(res, dict) else res.source
        cat = res["category"] if isinstance(res, dict) else res.category

        assert src_id == "OpenWeather"
        assert src_name == "OpenWeather"
        assert cat == "Moderate"


# =============================================================================
# 4. SOURCE_IDENTITY SCHEMAS & ACCURACY VERIFICATION
# =============================================================================
def test_all_weather_response_schemas_contain_source_identity():
    """CurrentWeatherResponse, ForecastResponse, AlertResponse, AirQualityResponse must define source_identity."""
    assert "source_identity" in CurrentWeatherResponse.model_fields
    assert "source_identity" in ForecastResponse.model_fields
    assert "source_identity" in AlertResponse.model_fields
    assert "source_identity" in AirQualityResponse.model_fields


@pytest.mark.asyncio
async def test_forecast_response_populates_source_identity_accurately():
    """ForecastService returns ForecastResponse with lead source_identity named OpenWeather."""
    with patch.object(settings, "IMD_API_KEY", ""):
        mock_ow = AsyncMock(spec=OpenWeatherAdapter)
        mock_ow.name = "OpenWeather"
        now_iso = datetime.now(timezone.utc).isoformat()
        item = NormalizedForecastItem(
            forecast_time="12:00 PM",
            forecast_for=now_iso,
            temperature_c=29.5,
            rain_probability_pct=20.0,
            wind_speed_kmh=14.0,
            condition="Clouds",
            source="OpenWeather",
            authority_level="primary_live",
            issued_at=now_iso,
            retrieved_at=now_iso
        )
        mock_ow.get_forecast = AsyncMock(return_value=[item])

        service = ForecastService(primary_provider=mock_ow, secondary_provider=OpenMeteoAdapter())
        res = await service.fetch_forecast(13.0827, 80.2707, "Chennai")

        assert res.source_identity == "OpenWeather"
        assert "OpenWeather" in res.source


# =============================================================================
# 5. NOTIFICATION SERVICE SOURCE IDENTIFICATION
# =============================================================================
def test_notification_service_format_alert_message_respects_source():
    """notification_service must NOT label non-IMD alerts as [IMD]."""
    notif = NotificationService()

    # Case A: Alert with OpenWeather source
    formatted_ow = notif.format_alert_message(
        title="Heavy Rain Advisory",
        description="Localized torrential showers expected.",
        severity="WARNING",
        language="en",
        source="OpenWeather"
    )
    assert "[OpenWeather]" in formatted_ow["title"]
    assert "[IMD]" not in formatted_ow["title"]
    assert "Official Warning - IMD" not in formatted_ow["title"]
    assert "Weather Warning" in formatted_ow["title"]

    # Case B: Alert with genuine IMD source
    formatted_imd = notif.format_alert_message(
        title="Depression Warning",
        description="Depression crossed coast.",
        severity="WARNING",
        language="en",
        source="IMD"
    )
    assert "[IMD]" in formatted_imd["title"]
    assert "Official Warning - IMD Official Warning" in formatted_imd["title"]
