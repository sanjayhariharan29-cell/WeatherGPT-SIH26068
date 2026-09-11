"""Comprehensive Official IMD Warning & Nowcast Test Suite.

Covers all 20 required safety and integrity test scenarios:
 1. Real IMD endpoint success
 2. HTTP failure
 3. Timeout handling
 4. Malformed JSON handling
 5. Empty response handling
 6. Missing severity rejection
 7. Invalid timestamps rejection
 8. Expired warning becomes EXPIRED
 9. Active warning evaluation
10. Duplicate warning deduplication
11. Updated warning versioning & persistence
12. Multiple districts parsing & isolation
13. Location-to-district deterministic matching
14. No district match handling (zero alert invention)
15. Source provenance preservation
16. Live vs Fixture strict separation
17. Secondary provider cannot create IMD warning
18. LLM cannot create or alter IMD warning
19. Notification dispatched only from validated IMD warning
20. Expired warning cannot trigger notification
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.session import Base
from backend.db.models import (
    Alert as DBAlert,
    User,
    UserPreference,
    SavedLocation,
    DeviceToken,
    AlertDeliveryLog
)
from backend.config.settings import settings
from backend.services.imd_adapter import IMDAdapter
from backend.services.imd_district_registry import resolve_imd_district
from backend.services.imd_fixtures import (
    get_test_fixture_alerts,
    get_test_fixture_observation,
    get_test_fixture_forecast,
    assert_test_environment_allowed
)
from backend.services.alert_engine import (
    AlertEngine,
    AlertStatusEnum,
    normalize_and_validate_imd_alert,
    is_alert_active
)
from backend.services.alert_service import AlertService
from backend.services.schemas import NormalizedAlertItem
from backend.services.exceptions import ProviderError, ProviderUnavailableError, ProviderTimeoutError
from ai.models import (
    OfficialAlert as AIOfficialAlert,
    RiskLevelEnum,
    WeatherRecord as AIWeatherRecord,
    LocationInfo,
    PersonaEnum,
    ValidationCategoryEnum,
)
from ai.reasoner import WeatherReasoner
from ai.decision import DecisionEngine
from ai.validator.response_validator import ResponseValidator


@pytest.fixture
def memory_db():
    """In-memory SQLite session fixture."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Real IMD endpoint success
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_1_real_imd_endpoint_success():
    adapter = IMDAdapter(mode="live")
    mock_payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": 55,
                    "Date": "2026-09-11",
                    "District": "COIMBATORE",
                    "Day_1": "4",
                    "Day1_Color": 3,
                    "Day1_text": "Thunderstorm with rain expected.",
                    "updated_at": "2026-09-11T05:44:25Z"
                },
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[76.9, 10.9], [77.0, 10.9], [77.0, 11.0], [76.9, 10.9]]]]
                }
            }
        ]
    }
    with patch.object(adapter, "_fetch_json", new=AsyncMock(return_value=mock_payload)):
        alerts = await adapter.fetch_official_district_warnings("COIMBATORE")
        assert len(alerts) >= 1
        a = alerts[0]
        assert a.source == "IMD"
        assert a.product_type == "district_warning"
        assert a.state == "LIVE"
        assert a.severity == "medium"
        assert "COIMBATORE" in a.alert_id
        assert a.geometry is not None
        assert a.geometry["type"] == "MultiPolygon"


# ---------------------------------------------------------------------------
# 2. HTTP failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_2_http_failure():
    adapter = IMDAdapter(mode="live")
    with patch.object(adapter, "_fetch_json", side_effect=ProviderUnavailableError("IMD 503 Service Unavailable", "IMD")):
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await adapter.fetch_official_district_warnings("COIMBATORE")
        assert "IMD" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. Timeout handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_3_timeout():
    adapter = IMDAdapter(mode="live")
    with patch.object(adapter, "_fetch_json", side_effect=ProviderTimeoutError("Connection timed out after 5.0s", "IMD")):
        with pytest.raises(ProviderTimeoutError):
            await adapter.fetch_official_district_warnings("COIMBATORE")


# ---------------------------------------------------------------------------
# 4. Malformed JSON handling
# ---------------------------------------------------------------------------
def test_4_malformed_json():
    # Test completely empty or corrupted payload
    item, err = normalize_and_validate_imd_alert({})
    assert item is None
    assert "Empty or corrupted alert payload" in err

    # Malformed non-dict payload
    item2, err2 = normalize_and_validate_imd_alert("corrupted_json")  # type: ignore
    assert item2 is None


# ---------------------------------------------------------------------------
# 5. Empty response handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_5_empty_response():
    adapter = IMDAdapter(mode="live")
    with patch.object(adapter, "_fetch_json", new=AsyncMock(return_value={"type": "FeatureCollection", "features": []})):
        alerts = await adapter.fetch_official_district_warnings("COIMBATORE")
        assert alerts == []


# ---------------------------------------------------------------------------
# 6. Missing severity rejection
# ---------------------------------------------------------------------------
def test_6_missing_severity():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Alert Without Severity",
        "alert_type": "heavy_rain",
        "area": "Coimbatore",
        "severity": "",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=6)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw)
    assert item is None
    assert "Invalid severity" in err


# ---------------------------------------------------------------------------
# 7. Invalid timestamps rejection
# ---------------------------------------------------------------------------
def test_7_invalid_timestamps():
    now = datetime.now(timezone.utc)
    # Expiry before issuance
    raw_reversed = {
        "source": "IMD",
        "title": "Reversed Timestamps",
        "alert_type": "thunderstorm",
        "area": "Coimbatore",
        "severity": "medium",
        "issued_at": now.isoformat(),
        "expires_at": (now - timedelta(hours=2)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw_reversed)
    assert item is None
    assert "Expiry timestamp" in err and "must be strictly after issuance" in err


# ---------------------------------------------------------------------------
# 8. Expired warning becomes EXPIRED
# ---------------------------------------------------------------------------
def test_8_expired_warning():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Expired Notice",
        "alert_type": "heatwave",
        "area": "Coimbatore",
        "severity": "low",
        "issued_at": (now - timedelta(days=2)).isoformat(),
        "expires_at": (now - timedelta(hours=5)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    assert item is not None
    assert item.status == AlertStatusEnum.EXPIRED.value
    assert is_alert_active(item.issued_at, item.expires_at, current_time=now) is False


# ---------------------------------------------------------------------------
# 9. Active warning evaluation
# ---------------------------------------------------------------------------
def test_9_active_warning():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Active Cyclone Warning",
        "alert_type": "cyclone",
        "area": "Nagapattinam",
        "severity": "red",
        "issued_at": (now - timedelta(hours=1)).isoformat(),
        "expires_at": (now + timedelta(hours=12)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    assert item is not None
    assert item.status == AlertStatusEnum.ACTIVE.value
    assert is_alert_active(item.issued_at, item.expires_at, current_time=now) is True


# ---------------------------------------------------------------------------
# 10. Duplicate warning deduplication
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_10_duplicate_warning(memory_db):
    engine = AlertEngine()
    now = datetime.now(timezone.utc)
    alert_item = NormalizedAlertItem(
        alert_id="IMD-COIMBATORE-TEST-1",
        alert_type="heavy_rain",
        severity="high",
        title="Heavy Rain Warning",
        description="Heavy rain expected.",
        area="Coimbatore",
        source="IMD",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(hours=10)).isoformat(),
        retrieved_at=now.isoformat(),
        status="ACTIVE"
    )

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[alert_item])):
        first_run = await engine.ingest_alerts_for_location("Coimbatore", 11.0168, 76.9558, memory_db)
        assert len(first_run) == 1

        # Second identical run
        second_run = await engine.ingest_alerts_for_location("Coimbatore", 11.0168, 76.9558, memory_db)
        assert len(second_run) == 1

        total_in_db = memory_db.query(DBAlert).count()
        assert total_in_db == 1


# ---------------------------------------------------------------------------
# 11. Updated warning versioning & persistence
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_11_updated_warning(memory_db):
    engine = AlertEngine()
    now = datetime.now(timezone.utc)
    v1 = NormalizedAlertItem(
        alert_id="IMD-COIMBATORE-TEST-1",
        alert_type="heavy_rain",
        severity="medium",
        title="Heavy Rain Warning",
        description="Moderate to heavy rain.",
        area="Coimbatore",
        source="IMD",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(hours=10)).isoformat(),
        retrieved_at=now.isoformat(),
        status="ACTIVE"
    )

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[v1])):
        await engine.ingest_alerts_for_location("Coimbatore", 11.0168, 76.9558, memory_db)

    # v2: Severity elevated to high with newer issuance
    v2 = NormalizedAlertItem(
        alert_id="IMD-COIMBATORE-TEST-1",
        alert_type="heavy_rain",
        severity="high",
        title="Heavy Rain Warning",
        description="Extremely heavy rain expected.",
        area="Coimbatore",
        source="IMD",
        issued_at=(now + timedelta(minutes=30)).isoformat(),
        expires_at=(now + timedelta(hours=12)).isoformat(),
        retrieved_at=(now + timedelta(minutes=30)).isoformat(),
        status="ACTIVE"
    )

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[v2])):
        updated = await engine.ingest_alerts_for_location("Coimbatore", 11.0168, 76.9558, memory_db)
        assert len(updated) == 1
        assert updated[0].severity == "high"
        assert "Extremely heavy" in updated[0].description


# ---------------------------------------------------------------------------
# 12. Multiple districts parsing & isolation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_multiple_districts():
    adapter = IMDAdapter(mode="live")
    mock_cbe = {
        "features": [{
            "properties": {
                "District": "COIMBATORE", "Date": "2026-09-11", "Day_1": "4", "Day1_Color": 3, "Day1_text": ""
            }
        }]
    }
    mock_ngp = {
        "features": [{
            "properties": {
                "District": "NAGAPATTINAM", "Date": "2026-09-11", "Day_1": "2", "Day1_Color": 4, "Day1_text": "Squall"
            }
        }]
    }

    async def mock_fetch(url, params=None, headers=None):
        if "COIMBATORE" in str(params.get("cql_filter", "")):
            return mock_cbe
        return mock_ngp

    with patch.object(adapter, "_fetch_json", side_effect=mock_fetch):
        cbe_alerts = await adapter.fetch_official_district_warnings("COIMBATORE")
        ngp_alerts = await adapter.fetch_official_district_warnings("NAGAPATTINAM")

        assert len(cbe_alerts) >= 1
        assert len(ngp_alerts) >= 1
        assert cbe_alerts[0].matched_district == "COIMBATORE"
        assert ngp_alerts[0].matched_district == "NAGAPATTINAM"
        assert cbe_alerts[0].severity == "medium"
        assert ngp_alerts[0].severity == "high"


# ---------------------------------------------------------------------------
# 13. Location-to-district deterministic matching
# ---------------------------------------------------------------------------
def test_13_location_to_district_match():
    # Direct and Tamil alias matching
    assert resolve_imd_district("Coimbatore") == "COIMBATORE"
    assert resolve_imd_district("கோயம்புத்தூர்") == "COIMBATORE"
    assert resolve_imd_district("Nagapattinam") == "NAGAPATTINAM"
    assert resolve_imd_district("நாகப்பட்டினம்") == "NAGAPATTINAM"
    assert resolve_imd_district("Chennai") == "CHENNAI"

    # Coordinate proximity matching (Coimbatore GPS: 11.0168, 76.9558)
    assert resolve_imd_district(None, 11.0168, 76.9558) == "COIMBATORE"
    # Nagapattinam GPS: 10.7656, 79.8424
    assert resolve_imd_district(None, 10.7656, 79.8424) == "NAGAPATTINAM"


# ---------------------------------------------------------------------------
# 14. No district match handling (zero alert invention)
# ---------------------------------------------------------------------------
def test_14_no_district_match():
    # Non-Indian or non-registered location
    assert resolve_imd_district("Paris, France") is None
    # Null island coordinates
    assert resolve_imd_district(None, 0.0, 0.0) is None


# ---------------------------------------------------------------------------
# 15. Source provenance preservation
# ---------------------------------------------------------------------------
def test_15_source_provenance():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Severe Cyclone Warning",
        "alert_type": "cyclone",
        "area": "Nagapattinam District",
        "severity": "red",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=24)).isoformat(),
        "source_url": "https://mausam.imd.gov.in/responsive/districtWiseWarningGIS.php",
        "product_type": "district_warning",
        "state": "LIVE",
        "matched_district": "NAGAPATTINAM"
    }
    item, err = normalize_and_validate_imd_alert(raw)
    assert item is not None
    assert item.source == "IMD"
    assert item.product_type == "district_warning"
    assert item.state == "LIVE"
    assert item.matched_district == "NAGAPATTINAM"
    assert item.source_url == "https://mausam.imd.gov.in/responsive/districtWiseWarningGIS.php"


# ---------------------------------------------------------------------------
# 16. Live vs Fixture strict separation
# ---------------------------------------------------------------------------
def test_16_live_fixture_separation():
    # Production adapter must not return fixtures
    live_adapter = IMDAdapter(mode="live")
    assert live_adapter.mode == "live"

    # Test fixtures can only be accessed when explicitly permitted
    with patch.object(settings, "IMD_ENVIRONMENT", "production"):
        with patch.object(settings, "ENVIRONMENT", "production"):
            with pytest.raises(RuntimeError) as exc_info:
                get_test_fixture_alerts("Nagapattinam")
            assert "Test fixtures cannot be accessed in production environment" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 17. Secondary provider cannot create IMD warning
# ---------------------------------------------------------------------------
def test_17_secondary_provider_cannot_create_imd_warning():
    now = datetime.now(timezone.utc)
    # Attempting to ingest an alert claiming to be Open-Meteo or other secondary provider
    raw = {
        "source": "Open-Meteo",
        "title": "Simulated Severe Warning",
        "alert_type": "rain",
        "area": "Chennai",
        "severity": "high",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=6)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw)
    assert item is None
    assert "Unauthorized alert source 'Open-Meteo'" in err


# ---------------------------------------------------------------------------
# 18. LLM cannot create or alter IMD warning
# ---------------------------------------------------------------------------
def test_18_llm_cannot_create_imd_warning():
    now = datetime.now(timezone.utc)
    weather = AIWeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now,
        retrieved_at=now,
        temperature=28.0,
        humidity=65.0,
        rain_probability=10.0,
        weather_condition="Clear Sky",
        wind_speed=12.0,
        rainfall_amount_mm=0.0
    )
    # Ground truth official alerts: empty list
    reasoning = WeatherReasoner.evaluate(weather, active_alerts=[])
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL)

    # LLM hallucinates an official red alert
    llm_output = "Official IMD Red Alert issued for Coimbatore today. Evacuate immediately."
    result = ResponseValidator.validate_response(
        response_text=llm_output,
        reasoning=reasoning,
        weather=weather,
        advisory=advisory
    )
    assert result.is_valid is False
    assert ValidationCategoryEnum.FABRICATED_DATA.value in result.violation_categories


# ---------------------------------------------------------------------------
# 19. Notification dispatched only from validated IMD warning
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_19_notification_only_from_validated_imd_alert(memory_db):
    engine = AlertEngine()
    now = datetime.now(timezone.utc)
    # Attempt notification from a non-IMD source
    fake_alert = DBAlert(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        alert_type="fake_alert",
        severity="high",
        title="Unauthorized Alert",
        description="Fake alert from unknown source.",
        source="NonOfficialSource",
        issued_at=now,
        expires_at=now + timedelta(hours=6)
    )
    memory_db.add(fake_alert)
    memory_db.commit()

    results = await engine.process_alert_delivery(fake_alert, memory_db)
    assert len(results) >= 1
    assert results[0]["status"] == "REJECTED"
    assert results[0]["reason"] == "unauthorized_source"


# ---------------------------------------------------------------------------
# 20. Expired warning cannot notify
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_20_expired_warning_cannot_notify(memory_db):
    engine = AlertEngine()
    now = datetime.now(timezone.utc)
    expired_alert = DBAlert(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        alert_type="heatwave",
        severity="medium",
        title="Expired Heatwave",
        description="This alert expired earlier.",
        source="IMD",
        issued_at=now - timedelta(days=2),
        expires_at=now - timedelta(hours=1)
    )
    memory_db.add(expired_alert)
    memory_db.commit()

    results = await engine.process_alert_delivery(expired_alert, memory_db)
    assert len(results) >= 1
    assert results[0]["status"] == "SKIPPED"
    assert results[0]["reason"] == "expired_alert"
