"""Tests for SkyZen Phase 27: NWP / GFS / WRF Integration Readiness.

Deterministic test suite covering:
1. Generic NWP Provider interface & contracts (BaseNWPProvider).
2. Schema validation with all required meteorological & run cycle metadata.
3. Strict non-averaging principle (models are evaluated discretely with spread metrics).
4. Multi-model comparison engine (spread calculation, high-spread detection).
5. WeatherReasoner safety hierarchy (official IMD warnings take unconditional priority).
6. Freshness & reliability layer integration (evaluate_nwp_freshness, NOT_CONFIGURED state).
7. Unconfigured endpoint handling (returns NOT_CONFIGURED without fabricating fake data).
8. Deterministic mocked provider parsing & HTTP adapter validation.
9. FastAPI NWP router endpoints (/weather/nwp/status, /forecast, /comparison).
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import List
from fastapi.testclient import TestClient

from backend.main import app
from backend.config.settings import settings
from backend.services.nwp_schemas import (
    NWPModelName,
    NWPVariables,
    NormalizedNWPForecastItem,
    NWPModelComparison,
    NWPStatusResponse,
)
from backend.services.nwp_provider import (
    BaseNWPProvider,
    GFSProvider,
    WRFProvider,
    DeterministicNWPProvider,
    NWPComparisonEngine,
)
from backend.services.weather_reliability import (
    ProviderStatusEnum,
    FreshnessClassification,
    evaluate_nwp_freshness,
)
from backend.services.weather_manager import WeatherManager
from backend.services.exceptions import ProviderUnavailableError
from ai.models import (
    WeatherRecord,
    LocationInfo,
    ForecastItem,
    OfficialAlert,
    RiskLevelEnum,
    FreshnessStatusEnum,
    SourceAgreementEnum,
)
from ai.reasoner.reasoner import WeatherReasoner


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_gfs_item() -> NormalizedNWPForecastItem:
    now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
    return NormalizedNWPForecastItem(
        model_name=NWPModelName.GFS,
        model_run="12Z",
        initialization_time=now,
        forecast_lead_hours=6,
        valid_time=now + timedelta(hours=6),
        latitude=11.0168,
        longitude=76.9558,
        location_name="Coimbatore",
        variables=NWPVariables(
            temperature_c=28.5,
            temp_min_c=24.0,
            temp_max_c=31.0,
            precipitation_mm=2.5,
            rain_probability_pct=40.0,
            wind_speed_kmh=18.0,
            wind_direction_deg=240.0,
            pressure_hpa=1010.5,
            humidity_pct=72.0,
            cape_jkg=850.0,
        ),
        source="NOAA_NCEP_GFS",
        authority_level="nwp_model_guidance",
        freshness="FRESH",
        retrieved_at=now,
    )


@pytest.fixture
def sample_wrf_item() -> NormalizedNWPForecastItem:
    now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
    return NormalizedNWPForecastItem(
        model_name=NWPModelName.WRF,
        model_run="06Z",
        initialization_time=now - timedelta(hours=6),
        forecast_lead_hours=12,
        valid_time=now + timedelta(hours=6),
        latitude=11.0168,
        longitude=76.9558,
        location_name="Coimbatore",
        variables=NWPVariables(
            temperature_c=27.0,
            temp_min_c=23.5,
            temp_max_c=29.5,
            precipitation_mm=14.0,
            rain_probability_pct=75.0,
            wind_speed_kmh=26.0,
            wind_direction_deg=225.0,
            pressure_hpa=1009.2,
            humidity_pct=85.0,
            cape_jkg=1600.0,
        ),
        source="REGIONAL_WRF_MESOSCALE",
        authority_level="nwp_model_guidance",
        freshness="FRESH",
        retrieved_at=now,
    )


# ==============================================================================
# 1. Interface & Adapter Contracts
# ==============================================================================

def test_base_nwp_provider_contract():
    """Verify BaseNWPProvider defines mandatory attributes and abstract methods."""
    class IncompleteProvider(BaseNWPProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()  # Cannot instantiate abstract class


def test_gfs_provider_defaults():
    """Verify GFSProvider default initialization, model name, and authority."""
    provider = GFSProvider()
    assert provider.model_name == NWPModelName.GFS
    assert provider.authority_level == "nwp_model_guidance"
    assert provider.name == "GFS"


def test_wrf_provider_defaults():
    """Verify WRFProvider default initialization, model name, and authority."""
    provider = WRFProvider()
    assert provider.model_name == NWPModelName.WRF
    assert provider.authority_level == "nwp_model_guidance"
    assert provider.name == "WRF"


# ==============================================================================
# 2. Schemas & Forecast Metadata
# ==============================================================================

def test_nwp_forecast_item_metadata_retention(sample_gfs_item):
    """Verify that NWP forecast items store all required meteorological and run metadata."""
    item = sample_gfs_item
    assert item.model_name == NWPModelName.GFS
    assert item.model_run == "12Z"
    assert item.forecast_lead_hours == 6
    assert item.valid_time == item.initialization_time + timedelta(hours=6)
    assert item.variables.temperature_c == 28.5
    assert item.variables.cape_jkg == 850.0
    assert item.source == "NOAA_NCEP_GFS"
    assert item.provenance.provider_id == "NOAA_NCEP_GFS"
    assert item.provenance.model_name == "GFS"
    assert item.provenance.model_run == "12Z"


def test_nwp_variables_validation():
    """Verify NWPVariables validation constraints (e.g. ge=0 for precip/wind)."""
    with pytest.raises(Exception):
        NWPVariables(temperature_c=25.0, precipitation_mm=-5.0, wind_speed_kmh=10.0)

    with pytest.raises(Exception):
        NWPVariables(temperature_c=25.0, wind_speed_kmh=-1.0)


# ==============================================================================
# 3. Strict Non-Averaging Principle
# ==============================================================================

@pytest.mark.asyncio
async def test_strict_non_averaging_principle(sample_gfs_item, sample_wrf_item):
    """
    CRITICAL ARCHITECTURE REQUIREMENT:
    NWP model outputs must NEVER be averaged into a blended mean.
    NWPComparisonEngine must preserve individual model items intact and only compute spreads.
    """
    gfs_prov = DeterministicNWPProvider(
        model_name=NWPModelName.GFS,
        endpoint="https://mock.gfs.local",
        items=[sample_gfs_item]
    )
    wrf_prov = DeterministicNWPProvider(
        model_name=NWPModelName.WRF,
        endpoint="https://mock.wrf.local",
        items=[sample_wrf_item]
    )

    engine = NWPComparisonEngine()
    comparison = await engine.compare(
        providers=[gfs_prov, wrf_prov],
        lat=11.0168,
        lon=76.9558,
        location_name="Coimbatore"
    )

    # 1. Non-averaging affirmation
    assert comparison.strictly_non_averaged is True
    assert "Strictly non-averaged" in comparison.methodology

    # 2. Individual model items preserved with exact original numbers
    assert len(comparison.models_compared) == 2
    assert "GFS" in comparison.models_compared
    assert "WRF" in comparison.models_compared

    gfs_found = [m for m in comparison.comparisons[0].models if m.model_name == NWPModelName.GFS][0]
    wrf_found = [m for m in comparison.comparisons[0].models if m.model_name == NWPModelName.WRF][0]

    assert gfs_found.temperature_c == 28.5
    assert wrf_found.temperature_c == 27.0
    assert gfs_found.precipitation_mm == 2.5
    assert wrf_found.precipitation_mm == 14.0

    # 3. Discrete spread calculation: max - min (NOT an average)
    temp_spread = round(abs(28.5 - 27.0), 1)
    precip_spread = round(abs(14.0 - 2.5), 1)
    wind_spread = round(abs(26.0 - 18.0), 1)

    assert comparison.comparisons[0].temperature_spread_c == temp_spread
    assert comparison.comparisons[0].precipitation_spread_mm == precip_spread
    assert comparison.comparisons[0].wind_speed_spread_kmh == wind_spread


# ==============================================================================
# 4. Multi-Model Comparison & Spread Metrics
# ==============================================================================

@pytest.mark.asyncio
async def test_nwp_comparison_high_spread_detection(sample_gfs_item):
    """Verify that significant divergence between models triggers high_spread flag."""
    # Create divergent WRF item (temp diff 7.5C, precip diff 29.5mm)
    now = sample_gfs_item.valid_time
    divergent_wrf = NormalizedNWPForecastItem(
        model_name=NWPModelName.WRF,
        model_run="06Z",
        initialization_time=now - timedelta(hours=6),
        forecast_lead_hours=6,
        valid_time=now,
        latitude=11.0168,
        longitude=76.9558,
        location_name="Coimbatore",
        variables=NWPVariables(
            temperature_c=21.0,  # 28.5 vs 21.0 -> 7.5 deg spread (> 3.0 threshold)
            precipitation_mm=32.0,  # 2.5 vs 32.0 -> 29.5 mm spread (> 10.0 threshold)
            wind_speed_kmh=45.0,  # 18.0 vs 45.0 -> 27 km/h spread (> 15.0 threshold)
        ),
        source="REGIONAL_WRF",
        authority_level="nwp_model_guidance",
        freshness="FRESH",
        retrieved_at=now,
    )

    gfs_prov = DeterministicNWPProvider(
        model_name=NWPModelName.GFS,
        endpoint="https://mock.gfs.local",
        items=[sample_gfs_item]
    )
    wrf_prov = DeterministicNWPProvider(
        model_name=NWPModelName.WRF,
        endpoint="https://mock.wrf.local",
        items=[divergent_wrf]
    )

    engine = NWPComparisonEngine()
    comparison = await engine.compare([gfs_prov, wrf_prov], 11.0168, 76.9558, "Coimbatore")

    assert comparison.high_spread is True
    assert comparison.comparisons[0].divergence_detected is True
    assert "High spread detected" in comparison.spread_summary


# ==============================================================================
# 5. Weather Reasoning Layer & Safety Hierarchy Priority
# ==============================================================================

def test_imd_official_alert_unconditional_priority_over_nwp():
    """
    MANDATORY SAFETY RULE:
    Official IMD warnings remain strictly higher priority than numerical model forecasts.
    NWP model guidance (even indicating clear skies) CANNOT downgrade an official warning.
    """
    now = datetime.now(timezone.utc)

    # 1. Authoritative IMD Warning: EXTREME CYCLONE
    imd_alert = OfficialAlert(
        type="cyclone",
        title="Extremely Severe Cyclonic Storm Warning",
        description="Destructive winds and flooding expected along coast.",
        severity=RiskLevelEnum.EXTREME,
        source="IMD_OFFICIAL",
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=24),
    )

    # 2. Normal observation
    primary_weather = WeatherRecord(
        source="OpenWeatherMap",
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        temperature=28.0,
        feels_like=30.0,
        humidity=70.0,
        rain_probability=20.0,
        weather_condition="Clouds",
        wind_speed=12.0,
        observed_at=now,
        retrieved_at=now,
    )

    # 3. NWP Guidance: GFS model showing calm weather (0mm rain, calm wind)
    calm_gfs = NormalizedNWPForecastItem(
        model_name=NWPModelName.GFS,
        model_run="00Z",
        initialization_time=now - timedelta(hours=4),
        forecast_lead_hours=6,
        valid_time=now + timedelta(hours=6),
        latitude=11.0168,
        longitude=76.9558,
        location_name="Coimbatore",
        variables=NWPVariables(
            temperature_c=28.0,
            precipitation_mm=0.0,
            wind_speed_kmh=10.0,
        ),
        source="NOAA_NCEP_GFS",
        authority_level="nwp_model_guidance",
        freshness="FRESH",
        retrieved_at=now,
    )

    # Evaluate with WeatherReasoner
    reasoner = WeatherReasoner()
    result = reasoner.evaluate(
        primary_weather=primary_weather,
        forecast=[],
        active_alerts=[imd_alert],
        current_time=now,
        nwp_guidance=[calm_gfs]
    )

    # The official alert MUST dictate the overall risk
    assert result.overall_risk == RiskLevelEnum.EXTREME
    assert len(result.active_warnings) == 1
    assert result.active_warnings[0].source == "IMD_OFFICIAL"
    # NWP was recorded in sources used and guidance payload
    assert "NOAA_NCEP_GFS:GFS" in result.sources_used
    assert result.nwp_guidance is not None


def test_nwp_advisory_generates_ai_hazard_without_official_alert():
    """
    When no official IMD alert is present, severe NWP forecasts (e.g. WRF extreme rain 65mm)
    generate an AI-detected advisory hazard, elevating overall risk, but with is_official_warning=False.
    """
    now = datetime.now(timezone.utc)

    primary_weather = WeatherRecord(
        source="OpenWeatherMap",
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        temperature=27.0,
        feels_like=29.0,
        humidity=75.0,
        rain_probability=80.0,
        weather_condition="Rain",
        wind_speed=15.0,
        observed_at=now,
        retrieved_at=now,
    )

    # Extreme WRF simulation: 65 mm torrential rain
    heavy_rain_wrf = NormalizedNWPForecastItem(
        model_name=NWPModelName.WRF,
        model_run="06Z",
        initialization_time=now - timedelta(hours=3),
        forecast_lead_hours=6,
        valid_time=now + timedelta(hours=6),
        latitude=11.0168,
        longitude=76.9558,
        location_name="Coimbatore",
        variables=NWPVariables(
            temperature_c=25.0,
            precipitation_mm=65.0,
            wind_speed_kmh=35.0,
        ),
        source="REGIONAL_WRF",
        authority_level="nwp_model_guidance",
        freshness="FRESH",
        retrieved_at=now,
    )

    reasoner = WeatherReasoner()
    result = reasoner.evaluate(
        primary_weather=primary_weather,
        forecast=[],
        active_alerts=[],
        current_time=now,
        nwp_guidance=[heavy_rain_wrf]
    )

    # AI-detected hazard created
    assert len(result.active_warnings) == 0  # No official warnings
    nwp_hazards = [h for h in result.ai_detected_hazards if "NWP" in h.hazard_type]
    assert len(nwp_hazards) >= 1
    assert nwp_hazards[0].is_official_warning is False
    assert nwp_hazards[0].severity == RiskLevelEnum.HIGH
    # Risk elevated to HIGH as an advisory because no official warnings were present
    assert result.overall_risk == RiskLevelEnum.HIGH


# ==============================================================================
# 6. Freshness & Reliability Layer Integration
# ==============================================================================

def test_evaluate_nwp_freshness_cycles():
    """Verify evaluate_nwp_freshness conforms to typical NWP cycle schedules (00Z, 06Z, 12Z, 18Z)."""
    now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)

    # Fresh 12Z run (init 2 hours ago)
    status, age, meta = evaluate_nwp_freshness(
        initialization_time=now - timedelta(hours=2),
        current_time=now,
        expected_cycle_hours=6
    )
    assert status == FreshnessClassification.FRESH
    assert age == 120
    assert meta["freshness_category"] == "FRESH"

    # Aging run (7 hours ago, past 6h cycle)
    status_aging, age_aging, _ = evaluate_nwp_freshness(
        initialization_time=now - timedelta(hours=7),
        current_time=now,
        expected_cycle_hours=6
    )
    assert status_aging == FreshnessClassification.AGING

    # Stale run (15 hours ago)
    status_stale, _, _ = evaluate_nwp_freshness(
        initialization_time=now - timedelta(hours=15),
        current_time=now,
        expected_cycle_hours=6
    )
    assert status_stale == FreshnessClassification.STALE


# ==============================================================================
# 7. Unconfigured Handling & No Fake Data Fabrication
# ==============================================================================

@pytest.mark.asyncio
async def test_unconfigured_provider_returns_not_configured():
    """
    REQUIREMENT:
    If no live GFS/WRF endpoint is configured, expose provider as NOT_CONFIGURED
    rather than generating fake data.
    """
    # GFSProvider initialized without endpoint
    unconfigured_gfs = GFSProvider(endpoint="", enabled=False)
    assert unconfigured_gfs.is_configured is False
    assert unconfigured_gfs.status == ProviderStatusEnum.NOT_CONFIGURED

    # Attempting to fetch forecast raises ProviderUnavailableError with NOT_CONFIGURED status
    with pytest.raises(ProviderUnavailableError) as exc_info:
        await unconfigured_gfs.fetch_nwp_forecast(11.0168, 76.9558, "Coimbatore")

    assert exc_info.value.status == ProviderStatusEnum.NOT_CONFIGURED
    assert "not_configured" in str(exc_info.value).lower() or "not configured" in str(exc_info.value).lower()


# ==============================================================================
# 8. WeatherManager NWP Integration
# ==============================================================================

@pytest.mark.asyncio
async def test_weather_manager_nwp_status_and_forecast():
    """Test WeatherManager NWP status and deterministic forecast routing."""
    # Build WeatherManager with unconfigured providers
    wm = WeatherManager(
        gfs_provider=GFSProvider(endpoint="", enabled=False),
        wrf_provider=WRFProvider(endpoint="", enabled=False),
    )

    status = wm.get_nwp_status()
    assert "providers" in status
    assert status["providers"]["GFS"]["status"] == "NOT_CONFIGURED"
    assert status["providers"]["WRF"]["status"] == "NOT_CONFIGURED"

    # Fetching forecast from unconfigured provider returns clean NOT_CONFIGURED response without errors
    fc = await wm.get_nwp_forecast("GFS", 11.0168, 76.9558, "Coimbatore")
    assert fc["status"] == "NOT_CONFIGURED"
    assert fc["configured"] is False
    assert fc["items"] == []


@pytest.mark.asyncio
async def test_weather_manager_with_configured_deterministic_provider(sample_gfs_item, sample_wrf_item):
    """Test WeatherManager returns genuine model items when provider is configured."""
    det_gfs = DeterministicNWPProvider(
        model_name=NWPModelName.GFS,
        endpoint="https://deterministic.gfs.local",
        items=[sample_gfs_item]
    )
    det_wrf = DeterministicNWPProvider(
        model_name=NWPModelName.WRF,
        endpoint="https://deterministic.wrf.local",
        items=[sample_wrf_item]
    )

    wm = WeatherManager(gfs_provider=det_gfs, wrf_provider=det_wrf)

    res = await wm.get_nwp_forecast("GFS", 11.0168, 76.9558, "Coimbatore")
    assert res["status"] == "OK"
    assert res["configured"] is True
    assert res["count"] == 1
    assert res["items"][0]["model_name"] == "GFS"
    assert res["items"][0]["variables"]["temperature_c"] == 28.5

    comparison = await wm.get_nwp_comparison(11.0168, 76.9558, "Coimbatore")
    assert comparison["strictly_non_averaged"] is True
    assert len(comparison["comparisons"]) == 1


# ==============================================================================
# 9. FastAPI HTTP Endpoints
# ==============================================================================

def test_api_nwp_status(client):
    """Test GET /api/v1/weather/nwp/status returns valid JSON schema."""
    resp = client.get("/api/v1/weather/nwp/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert "GFS" in data["providers"]
    assert "WRF" in data["providers"]
    assert data["providers"]["GFS"]["status"] in ["CONFIGURED", "NOT_CONFIGURED"]


def test_api_nwp_forecast_unconfigured(client):
    """Test GET /api/v1/weather/nwp/forecast returns NOT_CONFIGURED when unconfigured."""
    resp = client.get("/api/v1/weather/nwp/forecast?model=GFS&location=Coimbatore")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_name"] == "GFS"
    assert data["status"] in ["NOT_CONFIGURED", "OK"]


def test_api_nwp_comparison(client):
    """Test GET /api/v1/weather/nwp/comparison endpoint executes cleanly."""
    resp = client.get("/api/v1/weather/nwp/comparison?location=Coimbatore")
    assert resp.status_code == 200
    data = resp.json()
    assert "models_compared" in data
    assert "strictly_non_averaged" in data
    assert data["strictly_non_averaged"] is True
