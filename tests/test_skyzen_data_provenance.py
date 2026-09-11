"""Comprehensive Provenance and Authenticity Test Suite for SkyZen Weather Engine.

Verifies all 10 Real Weather Data Provenance Rules:
1. No hardcoded weather presented as current.
2. No synthetic temperature presented as provider data.
3. No fake precipitation percentages.
4. No Open-Meteo data labeled IMD.
5. No non-CPCB data labeled CPCB.
6. No expired warning labeled active.
7. No stale value labeled LIVE.
8. No unavailable provider represented as successful.
9. No LLM-generated weather fact.
10. If data cannot be verified, display unavailable/degraded state.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from backend.services.cache import provider_cache
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.nasa_power_adapter import NasaPowerAdapter
from backend.services.weather_manager import WeatherManager
from backend.services.current_weather_service import CurrentWeatherService
from backend.services.forecast_service import ForecastService
from backend.services.alert_service import AlertService
from backend.services.exceptions import ProviderUnavailableError, ProviderError
from backend.services.schemas import NormalizedWeatherObservation, NormalizedForecastItem
from backend.services.weather_reliability import FreshnessClassification, evaluate_weather_freshness
from ai.validator.response_validator import ResponseValidator
from ai.tools import WeatherTools
from ai.models import (
    WeatherReasoningResult,
    WeatherRecord,
    LocationInfo,
    SourceAgreementEnum,
    FreshnessStatusEnum,
    ValidationCategoryEnum,
    RiskLevelEnum,
)


@pytest.mark.asyncio
async def test_rule_1_no_hardcoded_current_weather_nasa_power():
    """Rule 1 & 8: NASA POWER dataset is an archive and must NOT return hardcoded weather as current."""
    adapter = NasaPowerAdapter()
    with pytest.raises(ProviderUnavailableError) as exc_info:
        await adapter.get_current_weather(11.0168, 76.9558, "Coimbatore")
    assert "archive" in str(exc_info.value).lower()
    assert "NASA POWER" in str(exc_info.value)


@pytest.mark.asyncio
async def test_rule_2_no_synthetic_data_when_aqi_provider_fails():
    """Rule 2 & 10: When air quality provider fails, return unavailable state, NOT hardcoded 54 AQI."""
    mgr = WeatherManager()

    # Simulate httpx failure (e.g. timeout or network outage)
    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection refused")):
        aq_data = await mgr.get_air_quality(11.0168, 76.9558, "Coimbatore")

    assert aq_data["is_available"] is False
    assert aq_data["status"] == "UNAVAILABLE"
    assert aq_data["aqi"] is None
    assert aq_data["category"] == "Unavailable"
    assert aq_data["primary_pollutant"] is None
    assert aq_data["is_official_cpcb"] is False
    assert "not configured" in aq_data["cpcb_status"].lower()


@pytest.mark.asyncio
async def test_rule_3_no_fake_precipitation_percentages():
    """Rule 3: Open-Meteo current weather must extract real model hourly probability, not ternary heuristic."""
    adapter = OpenMeteoAdapter()
    provider_cache.clear()

    fake_payload = {
        "current": {
            "time": "2026-09-11T12:00",
            "temperature_2m": 31.4,
            "apparent_temperature": 34.0,
            "relative_humidity_2m": 68.0,
            "wind_speed_10m": 14.5,
            "wind_direction_10m": 120.0,
            "surface_pressure": 1010.5,
            "precipitation": 0.0,
            "weather_code": 3  # Overcast: previously hardcoded to 20.0%
        },
        "hourly": {
            "time": ["2026-09-11T11:00", "2026-09-11T12:00", "2026-09-11T13:00"],
            "precipitation_probability": [15.0, 42.0, 65.0]  # Real hourly model output
        }
    }

    with patch.object(adapter, "_fetch_json", new_callable=AsyncMock, return_value=fake_payload):
        obs = await adapter.get_current_weather(11.0168, 76.9558, "Coimbatore")

    # The rain probability should be the exact 42.0% from the model, NOT 20.0% or 80.0%
    assert obs.rain_probability_pct == 42.0
    assert obs.condition == "Overcast"
    assert obs.temperature_c == 31.4


@pytest.mark.asyncio
async def test_rule_4_no_open_meteo_data_labeled_imd_in_forecast():
    """Rule 4: When IMD is unavailable and failover to Open-Meteo occurs, source must be labeled Open-Meteo (Fallback)."""
    imd_mock = MagicMock()
    imd_mock.name = "IMD"
    imd_mock.get_forecast = AsyncMock(side_effect=ProviderUnavailableError("IMD down", provider_name="IMD"))

    om_items = [
        NormalizedForecastItem(
            forecast_time="2026-09-12",
            forecast_for="2026-09-12",
            temperature_c=29.0,
            temp_min_c=22.0,
            temp_max_c=32.0,
            rain_probability_pct=30.0,
            wind_speed_kmh=12.0,
            condition="Partly Cloudy",
            source="Open-Meteo",
            issued_at=datetime.now(timezone.utc).isoformat(),
            retrieved_at=datetime.now(timezone.utc).isoformat()
        )
    ]
    om_mock = MagicMock()
    om_mock.name = "Open-Meteo"
    om_mock.get_forecast = AsyncMock(return_value=om_items)

    service = ForecastService(primary_provider=imd_mock, secondary_provider=om_mock)
    response = await service.fetch_forecast(11.0168, 76.9558, "Coimbatore")

    assert "Open-Meteo" in response.source
    assert "Fallback" in response.source
    assert response.source != "IMD"


def test_rule_4_response_validator_flags_false_imd_attribution():
    """Rule 4: ResponseValidator flags responses claiming IMD observations when IMD was not used."""
    now_utc = datetime.now(timezone.utc)
    reasoning = WeatherReasoningResult(
        evaluated_at=now_utc,
        location="Coimbatore",
        primary_factors=["Clear skies"],
        sources_used=["Open-Meteo"],  # Only Open-Meteo, NO IMD
        source_agreement=SourceAgreementEnum.SINGLE_SOURCE,
        freshness=FreshnessStatusEnum.FRESH,
        data_age_minutes=5,
        consistency_score=100,
        overall_risk=RiskLevelEnum.LOW,
        active_warnings=[],
        detected_hazards=[]
    )
    weather = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0, longitude=76.9),
        observed_at=now_utc,
        retrieved_at=now_utc,
        temperature=28.0,
        humidity=60.0,
        rain_probability=10.0,
        wind_speed=12.0,
        weather_condition="Clear",
        source="Open-Meteo"
    )

    hallucinated_text = "According to IMD observations, the temperature is 28°C in Coimbatore today."
    res = ResponseValidator.validate_response(
        response_text=hallucinated_text,
        reasoning=reasoning,
        weather=weather
    )
    assert not res.is_valid
    assert ValidationCategoryEnum.UNSUPPORTED_SOURCE.value in res.violation_categories
    assert any("Misleading Attribution: IMD cited" in v for v in res.violations)


@pytest.mark.asyncio
async def test_rule_5_no_non_cpcb_data_labeled_cpcb():
    """Rule 5: Air quality sourced from Open-Meteo model must NOT be labeled official CPCB."""
    mgr = WeatherManager()
    fake_aqi = {
        "current": {
            "pm2_5": 22.5,
            "pm10": 45.0,
            "carbon_monoxide": 350.0,
            "nitrogen_dioxide": 12.0,
            "sulphur_dioxide": 5.0,
            "ozone": 25.0,
            "us_aqi": 68
        }
    }

    mock_resp = MagicMock(status_code=200, json=lambda: fake_aqi)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        aq_data = await mgr.get_air_quality(11.0168, 76.9558, "Coimbatore")

    assert aq_data["is_available"] is True
    assert aq_data["is_official_cpcb"] is False
    assert aq_data["source"] == "Air-quality model: Open-Meteo"
    assert "NOT CONFIGURED" in aq_data["cpcb_status"]
    assert aq_data["aqi"] == 68


def test_rule_6_no_expired_warning_labeled_active():
    """Rule 6: Expired meteorological alerts must evaluate to is_active=False."""
    alert_service = AlertService()
    now_utc = datetime.now(timezone.utc)

    expired_issued = (now_utc - timedelta(hours=10)).isoformat()
    expired_expires = (now_utc - timedelta(hours=2)).isoformat()

    # An alert that expired 2 hours ago must NOT be active
    assert alert_service.is_alert_active(expired_issued, expired_expires) is False

    active_issued = (now_utc - timedelta(hours=1)).isoformat()
    active_expires = (now_utc + timedelta(hours=4)).isoformat()
    assert alert_service.is_alert_active(active_issued, active_expires) is True


@pytest.mark.asyncio
async def test_rule_7_no_stale_value_labeled_live():
    """Rule 7: Stale cached telemetry (>180m) must have is_real_time=False and freshness_status=STALE."""
    now_utc = datetime.now(timezone.utc)
    stale_obs_time = (now_utc - timedelta(minutes=240)).isoformat()

    fresh_class, age_min, meta = evaluate_weather_freshness(
        observed_at=stale_obs_time,
        retrieved_at=now_utc.isoformat(),
        is_cached=True,
        cache_age_seconds=14400
    )
    assert fresh_class == FreshnessClassification.STALE
    assert age_min >= 240

    stale_obs = NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=26.0,
        humidity_pct=70.0,
        rain_probability_pct=20.0,
        wind_speed_kmh=10.0,
        condition="Cloudy",
        source="Open-Meteo",
        authority_level="secondary_forecast",
        observed_at=stale_obs_time,
        retrieved_at=now_utc.isoformat(),
        is_cached=True,
        cache_age_seconds=14400
    )

    primary_mock = MagicMock()
    primary_mock.name = "IMD"
    primary_mock.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("IMD down", provider_name="IMD"))

    secondary_mock = MagicMock()
    secondary_mock.name = "Open-Meteo"
    secondary_mock.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("Open-Meteo down", provider_name="Open-Meteo"))

    service = CurrentWeatherService(primary_provider=primary_mock, secondary_provider=secondary_mock)

    # Patch provider_cache to return stale_obs
    with patch("backend.services.current_weather_service.provider_cache.get_with_metadata", return_value=(stale_obs, False, 14400)):
        res = await service.fetch_current_weather(11.0168, 76.9558, "Coimbatore", allow_stale=True)

    assert res.is_real_time is False
    assert res.is_cached is True
    assert res.freshness_status == "STALE"
    assert res.data_freshness == "STALE_DEGRADED"


@pytest.mark.asyncio
async def test_rule_8_unavailable_provider_not_represented_as_successful():
    """Rule 8: An unavailable provider must raise ProviderUnavailableError or return degraded state."""
    adapter = NasaPowerAdapter()
    with pytest.raises(ProviderUnavailableError):
        await adapter.get_current_weather(11.0, 76.9, "Coimbatore")

    tools = WeatherTools()
    with patch.object(tools.weather_mgr, "get_air_quality", return_value={"is_available": False, "aqi": None}):
        tool_res = await tools.get_air_quality("Coimbatore", 11.0, 76.9)
    assert tool_res["status"] == "UNAVAILABLE"
    assert tool_res["aqi"] is None


def test_rule_9_no_llm_generated_weather_fact():
    """Rule 9: ResponseValidator catches hallucinated meteorological claims not in ground truth."""
    now_utc = datetime.now(timezone.utc)
    reasoning = WeatherReasoningResult(
        evaluated_at=now_utc,
        location="Coimbatore",
        primary_factors=["Clear skies"],
        sources_used=["Open-Meteo"],
        source_agreement=SourceAgreementEnum.HIGH,
        freshness=FreshnessStatusEnum.FRESH,
        data_age_minutes=5,
        consistency_score=100,
        overall_risk=RiskLevelEnum.LOW,
        active_warnings=[],
        detected_hazards=[]
    )
    weather = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0, longitude=76.9),
        observed_at=now_utc,
        retrieved_at=now_utc,
        temperature=28.0,
        humidity=60.0,
        rain_probability=10.0,
        wind_speed=12.0,
        weather_condition="Clear",
        source="Open-Meteo"
    )

    # Hallucinated temperature 39°C (ground truth is 28°C)
    hallucinated_temp = "The temperature right now in Coimbatore is 39°C with strong heat."
    res = ResponseValidator.validate_response(
        response_text=hallucinated_temp,
        reasoning=reasoning,
        weather=weather
    )
    assert not res.is_valid
    assert ValidationCategoryEnum.UNSUPPORTED_NUMBER.value in res.violation_categories
    assert any("Unsupported Temperature: Claimed 39.0°C" in v for v in res.violations)


@pytest.mark.asyncio
async def test_rule_10_degraded_state_displayed_when_unverifiable():
    """Rule 10: AI weather tools return degraded UNAVAILABLE structure when data is unverified."""
    tools = WeatherTools()
    with patch.object(tools.open_meteo, "get_forecast", side_effect=ProviderError("Connection timeout", provider_name="Open-Meteo")):
        fc_res = await tools.get_forecast("Coimbatore", 11.0, 76.9)
    assert fc_res["status"] == "UNAVAILABLE"
    assert "unavailable" in fc_res["message"].lower()
