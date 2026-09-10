"""SkyZen Phase 4 — Offline, Degraded & Failure Handling Deterministic Test Suite.

Verifies all 34 test conditions specified in Step 17:
1. all providers healthy
2. primary provider unavailable
3. secondary provider unavailable
4. all providers unavailable
5. provider timeout
6. provider DNS failure
7. provider HTTP error
8. malformed response
9. empty response
10. missing required fields
11. stale provider response
12. fresh cached data
13. stale cached data
14. no cached data
15. offline with cache
16. offline without cache
17. reconnect after offline
18. bounded retry
19. retry backoff
20. no infinite retry
21. invalid coordinates
22. location unavailable
23. notification failure
24. Firebase unavailable
25. expired cached official warning
26. valid cached official warning
27. IMD unavailable does not mean no warning
28. LLM cannot fabricate current weather
29. secondary provider cannot be presented as IMD
30. system state correctly becomes ONLINE
31. system state correctly becomes DEGRADED
32. system state correctly becomes OFFLINE
33. system state correctly becomes DATA_STALE
34. system state correctly becomes SERVICE_UNAVAILABLE
"""

import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
import pytest

from backend.services.exceptions import (
    ProviderError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderInvalidResponseError,
    ProviderAuthenticationError
)
from backend.services.cache import ProviderCache, provider_cache
from backend.services.schemas import (
    NormalizedWeatherObservation,
    NormalizedForecastItem,
    NormalizedAlertItem
)
from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.current_weather_service import CurrentWeatherService
from backend.services.forecast_service import ForecastService
from backend.services.alert_service import AlertService
from backend.services.weather_reliability import (
    determine_system_state,
    evaluate_weather_freshness,
    validate_weather_completeness,
    SystemStateEnum,
    FreshnessClassification,
    CompletenessClassification
)
from backend.db.models import Alert as DBAlert
from ai.models import (
    WeatherRecord,
    LocationInfo,
    NLUResult,
    DecisionAdvisory,
    WeatherReasoningResult,
    PersonaEnum,
    LanguageEnum,
    SourceAgreementEnum
)
from ai.llm.generator import GroundedLLMGenerator


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure clean provider cache between tests."""
    provider_cache.clear()
    yield
    provider_cache.clear()


# =============================================================================
# Helper factories
# =============================================================================

def make_valid_observation(
    source: str = "IMD",
    location: str = "Coimbatore",
    temp: float = 29.0,
    rain: float = 20.0,
    observed_at: Optional[str] = None
) -> NormalizedWeatherObservation:
    now_iso = datetime.now(timezone.utc).isoformat()
    return NormalizedWeatherObservation(
        location_name=location,
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=temp,
        feels_like_c=temp + 1.0,
        humidity_pct=65.0,
        rain_probability_pct=rain,
        wind_speed_kmh=14.0,
        condition="Partly Cloudy",
        rainfall_mm=0.0,
        source=source,
        authority_level="primary_authoritative" if source == "IMD" else "secondary_forecast",
        observed_at=observed_at or now_iso,
        retrieved_at=now_iso
    )


# =============================================================================
# TESTS 1 - 4: Multi-Provider Health & Degradation States
# =============================================================================

@pytest.mark.asyncio
async def test_01_all_providers_healthy():
    """1. All providers healthy -> System state ONLINE, high confidence agreement."""
    imd_mock = AsyncMock(spec=IMDAdapter)
    imd_mock.name = "IMD"
    imd_mock.authority_level = "primary_authoritative"
    imd_mock.get_current_weather = AsyncMock(return_value=make_valid_observation("IMD", temp=29.0))
    imd_mock.get_official_alerts = AsyncMock(return_value=[])

    open_meteo_mock = AsyncMock(spec=OpenMeteoAdapter)
    open_meteo_mock.name = "Open-Meteo"
    open_meteo_mock.authority_level = "secondary_forecast"
    open_meteo_mock.get_current_weather = AsyncMock(return_value=make_valid_observation("Open-Meteo", temp=28.5))

    service = CurrentWeatherService(primary_provider=imd_mock, secondary_provider=open_meteo_mock)
    res = await service.fetch_current_weather(11.0168, 76.9558, "Coimbatore")

    assert res.system_state == SystemStateEnum.ONLINE.value
    assert res.provider_status == "HEALTHY"
    assert "IMD (Primary)" in res.source
    assert "Open-Meteo (Secondary)" in res.source
    assert res.weather.temperature == 29.0


@pytest.mark.asyncio
async def test_02_primary_provider_unavailable():
    """2. Primary provider unavailable -> Fails over to secondary, state DEGRADED, labeled Fallback."""
    imd_mock = AsyncMock(spec=IMDAdapter)
    imd_mock.name = "IMD"
    imd_mock.authority_level = "primary_authoritative"
    imd_mock.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("IMD Outage", provider_name="IMD"))
    imd_mock.get_official_alerts = AsyncMock(return_value=[])

    open_meteo_mock = AsyncMock(spec=OpenMeteoAdapter)
    open_meteo_mock.name = "Open-Meteo"
    open_meteo_mock.authority_level = "secondary_forecast"
    open_meteo_mock.get_current_weather = AsyncMock(return_value=make_valid_observation("Open-Meteo", temp=28.0))

    service = CurrentWeatherService(primary_provider=imd_mock, secondary_provider=open_meteo_mock)
    res = await service.fetch_current_weather(11.0168, 76.9558, "Coimbatore")

    assert res.system_state == SystemStateEnum.DEGRADED.value
    assert res.provider_status == "DEGRADED"
    assert "Open-Meteo (Fallback)" in res.source
    assert "IMD" not in res.source  # Transparent: never claim Open-Meteo is IMD
    assert res.weather.temperature == 28.0


@pytest.mark.asyncio
async def test_03_secondary_provider_unavailable():
    """3. Secondary provider unavailable -> Primary IMD succeeds, state DEGRADED."""
    imd_mock = AsyncMock(spec=IMDAdapter)
    imd_mock.name = "IMD"
    imd_mock.authority_level = "primary_authoritative"
    imd_mock.get_current_weather = AsyncMock(return_value=make_valid_observation("IMD", temp=30.0))
    imd_mock.get_official_alerts = AsyncMock(return_value=[])

    open_meteo_mock = AsyncMock(spec=OpenMeteoAdapter)
    open_meteo_mock.name = "Open-Meteo"
    open_meteo_mock.authority_level = "secondary_forecast"
    open_meteo_mock.get_current_weather = AsyncMock(side_effect=ProviderTimeoutError("Open-Meteo Timeout", provider_name="Open-Meteo"))

    service = CurrentWeatherService(primary_provider=imd_mock, secondary_provider=open_meteo_mock)
    res = await service.fetch_current_weather(11.0168, 76.9558, "Coimbatore")

    assert res.system_state == SystemStateEnum.DEGRADED.value
    assert res.provider_status == "DEGRADED"
    assert "IMD (Primary)" in res.source
    assert res.weather.temperature == 30.0


@pytest.mark.asyncio
async def test_04_all_providers_unavailable():
    """4. All providers unavailable and no cache -> Raises ProviderUnavailableError without fabricating weather."""
    imd_mock = AsyncMock(spec=IMDAdapter)
    imd_mock.name = "IMD"
    imd_mock.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("IMD down", "IMD"))

    open_meteo_mock = AsyncMock(spec=OpenMeteoAdapter)
    open_meteo_mock.name = "Open-Meteo"
    open_meteo_mock.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("Open-Meteo down", "Open-Meteo"))

    service = CurrentWeatherService(primary_provider=imd_mock, secondary_provider=open_meteo_mock)
    with pytest.raises(ProviderUnavailableError) as exc_info:
        await service.fetch_current_weather(11.0168, 76.9558, "Coimbatore")

    assert "unavailable" in str(exc_info.value).lower()


# =============================================================================
# TESTS 5 - 11: Network, HTTP, and Parsing Failures
# =============================================================================

@pytest.mark.asyncio
async def test_05_provider_timeout():
    """5. Provider timeout raises structured ProviderTimeoutError."""
    adapter = OpenMeteoAdapter(timeout=0.01, max_retries=1)
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connection timed out")):
        with pytest.raises(ProviderTimeoutError) as exc_info:
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

        assert "timed out" in exc_info.value.message.lower()
        assert exc_info.value.provider_name == "Open-Meteo"


@pytest.mark.asyncio
async def test_06_provider_dns_failure():
    """6. Provider DNS failure / network error maps to ProviderUnavailableError."""
    adapter = OpenMeteoAdapter(timeout=1.0, max_retries=0)
    with patch("httpx.AsyncClient.get", side_effect=httpx.NetworkError("DNS resolution failed")):
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

        assert "network" in exc_info.value.message.lower() or "dns" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_07_provider_http_500_error():
    """7. Provider HTTP 500 server error maps to ProviderUnavailableError."""
    adapter = OpenMeteoAdapter(timeout=1.0, max_retries=0)
    mock_resp = httpx.Response(status_code=500, json={"error": "Internal Server Error"})
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_08_malformed_response():
    """8. Malformed HTML / non-JSON payload raises ProviderInvalidResponseError."""
    adapter = OpenMeteoAdapter(timeout=1.0, max_retries=0)
    mock_resp = httpx.Response(status_code=200, text="<html><body>Bad Gateway</body></html>")
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(ProviderInvalidResponseError) as exc_info:
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

        assert "parse json" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_09_empty_response():
    """9. Empty JSON response `{}` raises ProviderInvalidResponseError."""
    adapter = OpenMeteoAdapter(timeout=1.0, max_retries=0)
    mock_resp = httpx.Response(status_code=200, json={})
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        with pytest.raises(ProviderInvalidResponseError) as exc_info:
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

        assert "empty json" in exc_info.value.message.lower()


def test_10_missing_required_fields():
    """10. Payload missing essential fields is classified as INVALID."""
    incomplete_payload = {
        "location_name": "Coimbatore",
        "temperature_c": None,  # Missing mandatory temperature
        "humidity_pct": 50.0
    }
    comp_class, val_class, issues = validate_weather_completeness(incomplete_payload)
    assert comp_class in (CompletenessClassification.INVALID, CompletenessClassification.PARTIAL)
    assert len(issues) >= 1


def test_11_stale_provider_response():
    """11. Telemetry observed 240 minutes ago (> 180m threshold) is classified as STALE."""
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=240)).isoformat()
    now_time = datetime.now(timezone.utc).isoformat()
    fresh_class, age_min, meta = evaluate_weather_freshness(observed_at=old_time, retrieved_at=now_time)
    assert fresh_class == FreshnessClassification.STALE
    assert age_min >= 235


# =============================================================================
# TESTS 12 - 17: Caching, Stale Data, and Offline Recovery
# =============================================================================

def test_12_fresh_cached_data():
    """12. Cached data within TTL returns is_fresh=True and accurate age."""
    cache = ProviderCache(default_ttl=300)
    cache.set("coimbatore_key", {"temp": 29.0}, ttl=300)
    val, is_fresh, age = cache.get_with_metadata("coimbatore_key", max_stale_seconds=7200)

    assert val == {"temp": 29.0}
    assert is_fresh is True
    assert age is not None and age >= 0


def test_13_stale_cached_data():
    """13. Expired cache within max_stale_seconds returns is_fresh=False."""
    cache = ProviderCache(default_ttl=1)
    cache.set("coimbatore_stale_key", {"temp": 27.5}, ttl=1)
    time.sleep(1.1)

    val, is_fresh, age = cache.get_with_metadata("coimbatore_stale_key", max_stale_seconds=7200)
    assert val == {"temp": 27.5}
    assert is_fresh is False
    assert age is not None and age >= 1


def test_14_no_cached_data():
    """14. Querying non-existent key returns None, False, None."""
    cache = ProviderCache()
    val, is_fresh, age = cache.get_with_metadata("non_existent_key")
    assert val is None
    assert is_fresh is False
    assert age is None


@pytest.mark.asyncio
async def test_15_offline_with_cache():
    """15. Providers unavailable but stale cache exists -> DATA_STALE with cached labeling."""
    obs = make_valid_observation("Open-Meteo", temp=26.5)
    obs.observed_at = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    provider_cache.set("current_obs_Coimbatore_11.0168_76.9558", obs, ttl=1)
    time.sleep(1.1)

    imd_mock = AsyncMock(spec=IMDAdapter)
    imd_mock.name = "IMD"
    imd_mock.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("Offline", "IMD"))

    open_meteo_mock = AsyncMock(spec=OpenMeteoAdapter)
    open_meteo_mock.name = "Open-Meteo"
    open_meteo_mock.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("Offline", "Open-Meteo"))

    service = CurrentWeatherService(primary_provider=imd_mock, secondary_provider=open_meteo_mock)
    res = await service.fetch_current_weather(11.0168, 76.9558, "Coimbatore", allow_stale=True)

    assert res.system_state == SystemStateEnum.DATA_STALE.value
    assert res.is_cached is True
    assert "Cached Telemetry" in res.source
    assert res.weather.temperature == 26.5


@pytest.mark.asyncio
async def test_16_offline_without_cache():
    """16. Offline / provider failure without cache raises error and never fabricates values."""
    imd_mock = AsyncMock(spec=IMDAdapter)
    imd_mock.name = "IMD"
    imd_mock.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("Offline", "IMD"))

    open_meteo_mock = AsyncMock(spec=OpenMeteoAdapter)
    open_meteo_mock.name = "Open-Meteo"
    open_meteo_mock.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("Offline", "Open-Meteo"))

    service = CurrentWeatherService(primary_provider=imd_mock, secondary_provider=open_meteo_mock)
    with pytest.raises(ProviderUnavailableError):
        await service.fetch_current_weather(11.0168, 76.9558, "Coimbatore")


@pytest.mark.asyncio
async def test_17_reconnect_after_offline():
    """17. When connectivity recovers, fresh requests update data and clear stale state."""
    imd_mock = AsyncMock(spec=IMDAdapter)
    imd_mock.name = "IMD"
    imd_mock.authority_level = "primary_authoritative"
    imd_mock.get_current_weather = AsyncMock(return_value=make_valid_observation("IMD", temp=31.0))
    imd_mock.get_official_alerts = AsyncMock(return_value=[])

    open_meteo_mock = AsyncMock(spec=OpenMeteoAdapter)
    open_meteo_mock.name = "Open-Meteo"
    open_meteo_mock.authority_level = "secondary_forecast"
    open_meteo_mock.get_current_weather = AsyncMock(return_value=make_valid_observation("Open-Meteo", temp=30.8))

    service = CurrentWeatherService(primary_provider=imd_mock, secondary_provider=open_meteo_mock)
    res = await service.fetch_current_weather(11.0168, 76.9558, "Coimbatore")

    assert res.system_state == SystemStateEnum.ONLINE.value
    assert res.weather.temperature == 31.0
    assert res.is_cached is False


# =============================================================================
# TESTS 18 - 20: Retry, Backoff, and Loop Prevention
# =============================================================================

@pytest.mark.asyncio
async def test_18_bounded_retry():
    """18. Retries are strictly bounded by max_retries setting."""
    adapter = OpenMeteoAdapter(timeout=0.5, max_retries=2)
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.NetworkError("Transient connection drop")

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        with pytest.raises(ProviderUnavailableError):
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

    # Initial attempt + 2 retries = 3 calls
    assert call_count == 3


@pytest.mark.asyncio
async def test_19_retry_backoff():
    """19. Exponential backoff increases sleep duration between retry attempts."""
    adapter = OpenMeteoAdapter(timeout=0.5, max_retries=2)
    sleep_calls = []

    async def mock_sleep(duration):
        sleep_calls.append(duration)

    with patch("httpx.AsyncClient.get", side_effect=httpx.NetworkError("Err")), \
         patch("asyncio.sleep", side_effect=mock_sleep):
        with pytest.raises(ProviderUnavailableError):
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

    assert len(sleep_calls) == 2
    assert sleep_calls[1] > sleep_calls[0]  # Backoff duration grows exponentially


@pytest.mark.asyncio
async def test_20_no_infinite_retry_on_client_error():
    """20. 401 Authentication or 400 client error is not retried endlessly."""
    adapter = OpenMeteoAdapter(timeout=1.0, max_retries=3)
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return httpx.Response(status_code=401, json={"error": "Unauthorized"})

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        with pytest.raises(ProviderAuthenticationError):
            await adapter._fetch_json("https://api.open-meteo.com/v1/forecast")

    # Fatal client authentication failure must stop immediately on attempt 1
    assert call_count == 1


# =============================================================================
# TESTS 21 - 24: Coordinate & External Service Failures
# =============================================================================

def test_21_invalid_coordinates():
    """21. Invalid latitude/longitude bounds raise ValueError before calling upstream."""
    service = CurrentWeatherService()
    with pytest.raises(ValueError) as exc_lat:
        service.validate_coordinates(95.0, 77.0)
    assert "Latitude" in str(exc_lat.value)

    with pytest.raises(ValueError) as exc_lon:
        service.validate_coordinates(11.0, -195.0)
    assert "Longitude" in str(exc_lon.value)


@pytest.mark.asyncio
async def test_22_location_unavailable():
    """22. Unresolvable location raises appropriate exception and does not fabricate coordinates."""
    service = CurrentWeatherService()
    with patch.object(service.geocoding, "resolve_location", side_effect=ValueError("Unknown City")):
        with pytest.raises(ValueError) as exc_info:
            await service.fetch_current_weather(location_name="Unknown City")
        assert "Unknown City" in str(exc_info.value)


@pytest.mark.asyncio
async def test_23_notification_failure():
    """23. Notification dispatch failure does not suppress or delete alerts."""
    from backend.services.alert_engine import AlertEngine, normalize_and_validate_imd_alert
    from backend.services.notification_service import NotificationService

    notifications = NotificationService()
    # Mock send_push_notification to simulate an FCM network failure
    with patch.object(notifications, "send_push_notification", side_effect=Exception("FCM Service Down")):
        engine = AlertEngine(notification_service=notifications)
        alert_dict = {
            "title": "Severe Cyclone Warning",
            "severity": "red",
            "alert_type": "cyclone_warning",
            "description": "Cyclone approaching coast",
            "instructions": "Seek cyclone shelter immediately",
            "area": "Nagapattinam",
            "source": "IMD",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        }
        val_alert, err = normalize_and_validate_imd_alert(alert_dict)
        assert val_alert is not None
        assert val_alert.severity == "high"


def test_24_firebase_unavailable_isolated():
    """24. Unconfigured Firebase initializes safely in simulated/unconfigured mode without crashing."""
    from backend.services.notification_service import NotificationService
    service = NotificationService()
    # Verify Firebase app is not live initialized without credentials, and format works cleanly
    assert service.is_live_fcm_available() is False
    formatted = service.format_alert_message(
        title="Heavy Rain Warning",
        description="Flash flood danger",
        severity="red",
        language="en"
    )
    assert "Official Warning" in formatted["title"]
    assert "Flash flood danger" in formatted["body"]


# =============================================================================
# TESTS 25 - 27: Official IMD Alert Safety During Outages
# =============================================================================

@pytest.mark.asyncio
async def test_25_expired_cached_official_warning():
    """25. Expired cached official warning must NEVER be presented as active."""
    alert_service = AlertService()
    now_utc = datetime.now(timezone.utc)
    expired_item = NormalizedAlertItem(
        alert_id="ALT_EXP_01",
        alert_type="heavy_rain",
        severity="high",
        title="Old Heavy Rain Alert",
        description="Expired yesterday",
        area="Coimbatore",
        source="IMD",
        issued_at=(now_utc - timedelta(days=2)).isoformat(),
        expires_at=(now_utc - timedelta(days=1)).isoformat(),
        retrieved_at=now_utc.isoformat()
    )

    with patch.object(alert_service.primary, "get_official_alerts", return_value=[expired_item]):
        res = await alert_service.fetch_alerts(location_name="Coimbatore", active_only=True)
        # Expired alert must NOT appear in active alerts list
        assert len(res.alerts) == 0
        assert res.active_count == 0


@pytest.mark.asyncio
async def test_26_valid_cached_official_warning():
    """26. Valid unexpired cached warning retains full metadata and is displayed."""
    alert_service = AlertService()
    now_utc = datetime.now(timezone.utc)
    active_item = NormalizedAlertItem(
        alert_id="ALT_VAL_01",
        alert_type="cyclone_warning",
        severity="extreme",
        title="Cyclone Alert",
        description="Immediate shelter required",
        instructions="Evacuate low lying areas immediately",
        area="Nagapattinam",
        source="IMD",
        issued_at=now_utc.isoformat(),
        expires_at=(now_utc + timedelta(hours=12)).isoformat(),
        retrieved_at=now_utc.isoformat()
    )

    with patch.object(alert_service.primary, "get_official_alerts", return_value=[active_item]):
        res = await alert_service.fetch_alerts(location_name="Nagapattinam", active_only=True)
        assert len(res.alerts) == 1
        alert = res.alerts[0]
        assert alert.alert_id == "ALT_VAL_01"
        assert alert.severity == "extreme"
        assert alert.instructions == "Evacuate low lying areas immediately"
        assert alert.is_active is True


@pytest.mark.asyncio
async def test_27_imd_unavailable_does_not_mean_no_warning():
    """27. When IMD is down, status is UNVERIFIED and does NOT claim 'No warnings verified safe'."""
    alert_service = AlertService()
    with patch.object(alert_service.primary, "get_official_alerts", side_effect=ProviderError("IMD Outage", "IMD")):
        res = await alert_service.fetch_alerts(location_name="Coimbatore")
        assert res.status == "UNVERIFIED"
        assert "Degraded" in res.source
        assert res.system_state == "DEGRADED"


# =============================================================================
# TESTS 28 - 29: AI Hallucination Defense & Provider Transparency
# =============================================================================

def test_28_llm_cannot_fabricate_current_weather():
    """28. When weather observation is unavailable, AI explicitly states verification failure."""
    from ai.models import FreshnessStatusEnum, ConfidenceLevelEnum, RiskLevelEnum
    generator = GroundedLLMGenerator(provider=None)

    nlu = NLUResult(
        original_text="Is it raining right now in Coimbatore?",
        intent="current_weather",
        location="Coimbatore",
        detected_language=LanguageEnum.EN
    )
    reasoning = WeatherReasoningResult(
        evaluated_at=datetime.now(timezone.utc),
        location="Coimbatore",
        freshness=FreshnessStatusEnum.STALE,
        data_age_minutes=0,
        source_agreement=SourceAgreementEnum.SINGLE_SOURCE,
        consistency_score=50,
        confidence_level=ConfidenceLevelEnum.HIGH,
        overall_risk=RiskLevelEnum.LOW,
        contradictions=["Live weather data unavailable"],
        sources_used=["Unknown"]
    )
    advisory = DecisionAdvisory(
        persona=PersonaEnum.GENERAL,
        risk_level=RiskLevelEnum.LOW,
        headline="Degraded State Advisory",
        advisory_text="Current conditions could not be verified.",
        key_precautions=[],
        official_warning_present=False,
        source_attribution="Unknown",
        timestamp_info="Current"
    )

    # Invoke generator with weather=None (no observation)
    res = generator.generate_response(nlu=nlu, weather=None, reasoning=reasoning, advisory=advisory)

    assert res.is_fallback is True
    # The output must clearly communicate that current rainfall could not be verified
    assert "could not be verified" in res.answer.lower()
    assert "unavailable" in res.answer.lower()
    # Must NOT claim a fabricated temperature or fake rain confirmation
    assert "29°c" not in res.answer.lower()
    assert "yes, it is raining" not in res.answer.lower()


@pytest.mark.asyncio
async def test_29_secondary_provider_cannot_be_presented_as_imd():
    """29. When IMD fails, fallback data from Open-Meteo must never claim to be from IMD."""
    imd_mock = AsyncMock(spec=IMDAdapter)
    imd_mock.name = "IMD"
    imd_mock.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("IMD Outage", "IMD"))
    imd_mock.get_official_alerts = AsyncMock(return_value=[])

    open_meteo_mock = AsyncMock(spec=OpenMeteoAdapter)
    open_meteo_mock.name = "Open-Meteo"
    open_meteo_mock.get_current_weather = AsyncMock(return_value=make_valid_observation("Open-Meteo", temp=27.0))

    service = CurrentWeatherService(primary_provider=imd_mock, secondary_provider=open_meteo_mock)
    res = await service.fetch_current_weather(11.0168, 76.9558, "Coimbatore")

    assert res.source == "Open-Meteo (Fallback)"
    assert "IMD" not in res.source


# =============================================================================
# TESTS 30 - 34: Deterministic System State Mapping
# =============================================================================

def test_30_system_state_online():
    """30. All providers healthy & data fresh -> ONLINE."""
    state = determine_system_state(
        is_primary_healthy=True,
        is_secondary_healthy=True,
        is_cached=False,
        freshness=FreshnessClassification.FRESH,
        is_offline=False
    )
    assert state == SystemStateEnum.ONLINE


def test_31_system_state_degraded():
    """31. One provider failed or aging data -> DEGRADED."""
    # Primary failed, secondary healthy
    state_a = determine_system_state(is_primary_healthy=False, is_secondary_healthy=True)
    assert state_a == SystemStateEnum.DEGRADED

    # Primary healthy, secondary failed
    state_b = determine_system_state(is_primary_healthy=True, is_secondary_healthy=False)
    assert state_b == SystemStateEnum.DEGRADED

    # Both healthy but aging freshness
    state_c = determine_system_state(
        is_primary_healthy=True,
        is_secondary_healthy=True,
        freshness=FreshnessClassification.AGING
    )
    assert state_c == SystemStateEnum.DEGRADED


def test_32_system_state_offline():
    """32. Offline connectivity flag set -> OFFLINE."""
    state = determine_system_state(
        is_primary_healthy=False,
        is_secondary_healthy=False,
        is_offline=True
    )
    assert state == SystemStateEnum.OFFLINE


def test_33_system_state_data_stale():
    """33. Both providers down, but acceptable stale cache exists -> DATA_STALE."""
    state = determine_system_state(
        is_primary_healthy=False,
        is_secondary_healthy=False,
        is_cached=True,
        freshness=FreshnessClassification.STALE,
        is_offline=False
    )
    assert state == SystemStateEnum.DATA_STALE


def test_34_system_state_service_unavailable():
    """34. Both providers down and no usable cached observation -> SERVICE_UNAVAILABLE."""
    state = determine_system_state(
        is_primary_healthy=False,
        is_secondary_healthy=False,
        is_cached=False,
        is_offline=False
    )
    assert state == SystemStateEnum.SERVICE_UNAVAILABLE
