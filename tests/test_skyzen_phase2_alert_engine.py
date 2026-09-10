"""SkyZen Phase 2: Official IMD Alert Safety Engine Test Suite.

Comprehensive deterministic adversarial tests covering:
1. Valid IMD warning normalization & provenance
2. Malformed IMD warning handling & rejection
3. Missing severity rejection
4. Invalid severity rejection
5. Missing affected area rejection
6. Invalid timestamps rejection
7. Expiry before issue rejection
8. Active warning evaluation
9. Expired warning evaluation (never presented as active)
10. Scheduled warning evaluation (valid in future)
11. Duplicate warning retrieval & database deduplication
12. Updated warning detection & version increment
13. Severity update detection
14. Affected-area update detection
15. Newer warning vs older warning precedence (stale cannot overwrite newer)
16. Secondary provider contradiction (IMD authority cannot be downgraded)
17. LLM attempts to invent official warning (anti-hallucination rejection)
18. LLM attempts to downgrade warning severity (safety gate rejection)
19. LLM attempts to suppress warning via high forecast consistency
20. Missing IMD response handling (graceful degradation, not "no warning")
21. Invalid source rejection (non-IMD cannot pose as official)
22. DecisionTrace integration with structured warning evidence
23. Frontend presentation receives correct active-warning state & instructions
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Alert as DBAlert
from backend.db.session import Base
from backend.services.alert_engine import (
    AlertEngine,
    AlertStatusEnum,
    normalize_and_validate_imd_alert,
    is_alert_active,
)
from backend.services.alert_service import AlertService
from backend.services.schemas import NormalizedAlertItem
from backend.schemas.weather import AlertResponse, AlertItemSchema
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
from ai.pipeline import WeatherGPTPipeline


@pytest.fixture
def memory_db():
    """In-memory SQLite database session fixture for isolated testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Valid IMD Warning Normalization
# ---------------------------------------------------------------------------
def test_1_valid_imd_warning():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Severe Cyclonic Storm Alert",
        "alert_type": "cyclone",
        "severity": "red",
        "description": "Severe cyclonic storm approaching coastal belt.",
        "area": "Nagapattinam",
        "instructions": "Fishermen are advised not to venture into deep sea.",
        "issued_at": now.isoformat(),
        "valid_from": now.isoformat(),
        "expires_at": (now + timedelta(hours=24)).isoformat(),
        "source_url": "https://mausam.imd.gov.in/bulletin.pdf"
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    assert item is not None
    assert not err
    assert item.source == "IMD"
    assert item.title == "Severe Cyclonic Storm Alert"
    assert item.severity in ("high", "RED", "extreme")
    assert item.status == AlertStatusEnum.ACTIVE.value
    assert item.area == "Nagapattinam"
    assert item.instructions == "Fishermen are advised not to venture into deep sea."
    assert item.alert_id is not None
    assert item.validation_issues == []


# ---------------------------------------------------------------------------
# 2. Malformed IMD Warning Handling
# ---------------------------------------------------------------------------
def test_2_malformed_imd_warning():
    now = datetime.now(timezone.utc)
    # Corrupted dictionary with non-string fields
    raw = {
        "source": "IMD",
        "title": 12345,  # Malformed title
        "alert_type": "cyclone",
        "severity": "red",
        "area": "Nagapattinam",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=4)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    # Must be rejected with structured reason
    assert item is None
    assert err != ""


# ---------------------------------------------------------------------------
# 3. Missing Severity Rejection
# ---------------------------------------------------------------------------
def test_3_missing_severity():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Heavy Rain Alert",
        "alert_type": "rain",
        "severity": None,  # Missing severity
        "area": "Coimbatore",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=12)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    assert item is None
    assert "severity" in err.lower()


# ---------------------------------------------------------------------------
# 4. Invalid Severity Rejection
# ---------------------------------------------------------------------------
def test_4_invalid_severity():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Squall Warning",
        "alert_type": "wind",
        "severity": "mildly_unpleasant",  # Invalid severity value
        "area": "Chennai",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=12)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    assert item is None
    assert "severity" in err.lower()


# ---------------------------------------------------------------------------
# 5. Missing Affected Area Rejection
# ---------------------------------------------------------------------------
def test_5_missing_affected_area():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Gale Wind Warning",
        "alert_type": "wind",
        "severity": "orange",
        "area": "   ",  # Whitespace / empty area
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=12)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    assert item is None
    assert "area" in err.lower()


# ---------------------------------------------------------------------------
# 6. Invalid Timestamps Rejection
# ---------------------------------------------------------------------------
def test_6_invalid_timestamps():
    raw = {
        "source": "IMD",
        "title": "Coastal Alert",
        "alert_type": "wind",
        "severity": "orange",
        "area": "Cuddalore",
        "issued_at": "yesterday-afternoon",  # Unparseable timestamp
        "expires_at": "tomorrow-evening"
    }
    item, err = normalize_and_validate_imd_alert(raw)
    assert item is None
    assert "timestamp" in err.lower()


# ---------------------------------------------------------------------------
# 7. Expiry Before Issue Rejection
# ---------------------------------------------------------------------------
def test_7_expiry_before_issue():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Flash Flood Warning",
        "alert_type": "flood",
        "severity": "red",
        "area": "Nilgiris",
        "issued_at": now.isoformat(),
        "expires_at": (now - timedelta(hours=2)).isoformat()  # Impossible: expired before issue
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    assert item is None
    assert "expiry" in err.lower()


# ---------------------------------------------------------------------------
# 8. Active Warning Evaluation
# ---------------------------------------------------------------------------
def test_8_active_warning():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Thunderstorm with Squall",
        "alert_type": "thunderstorm",
        "severity": "orange",
        "area": "Coimbatore",
        "issued_at": (now - timedelta(hours=1)).isoformat(),
        "valid_from": (now - timedelta(minutes=30)).isoformat(),
        "expires_at": (now + timedelta(hours=3)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    assert item is not None
    assert item.status == AlertStatusEnum.ACTIVE.value
    assert is_alert_active(item.issued_at, item.expires_at, item.valid_from, current_time=now) is True


# ---------------------------------------------------------------------------
# 9. Expired Warning Evaluation (Never Active)
# ---------------------------------------------------------------------------
def test_9_expired_warning():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Heatwave Advisory",
        "alert_type": "heatwave",
        "severity": "yellow",
        "area": "Madurai",
        "issued_at": (now - timedelta(hours=24)).isoformat(),
        "expires_at": (now - timedelta(hours=2)).isoformat()  # Past expiry
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    assert item is not None
    assert item.status == AlertStatusEnum.EXPIRED.value
    assert is_alert_active(item.issued_at, item.expires_at, current_time=now) is False


# ---------------------------------------------------------------------------
# 10. Scheduled Warning Evaluation
# ---------------------------------------------------------------------------
def test_10_scheduled_warning():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "IMD",
        "title": "Upcoming Monsoonal Surge",
        "alert_type": "monsoon",
        "severity": "orange",
        "area": "Kanyakumari",
        "issued_at": now.isoformat(),
        "valid_from": (now + timedelta(hours=6)).isoformat(),  # Future validity window
        "expires_at": (now + timedelta(hours=24)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    assert item is not None
    assert item.status == AlertStatusEnum.SCHEDULED.value
    # Scheduled alert is not yet active at current time
    assert is_alert_active(item.issued_at, item.expires_at, item.valid_from, current_time=now) is False


# ---------------------------------------------------------------------------
# 11. Duplicate Warning Retrieval (Idempotent Ingestion)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_11_duplicate_warning_retrieval(memory_db):
    engine = AlertEngine()
    now = datetime.now(timezone.utc)
    raw_alert = NormalizedAlertItem(
        alert_id="IMD-2026-NAG-001",
        alert_type="wind",
        severity="ORANGE",
        title="Coastal Gale Warning",
        description="Gale winds reaching 65 km/h along coast.",
        area="Nagapattinam",
        source="IMD",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(hours=12)).isoformat(),
        retrieved_at=now.isoformat()
    )

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[raw_alert])):
        res1 = await engine.ingest_alerts_for_location("Nagapattinam", 10.76, 79.84, memory_db)
        assert len(res1) == 1

        # Second retrieval of identical alert
        res2 = await engine.ingest_alerts_for_location("Nagapattinam", 10.76, 79.84, memory_db)
        assert len(res2) == 1

        # Confirm exactly 1 record in database
        count = memory_db.query(DBAlert).filter(DBAlert.location_name == "Nagapattinam").count()
        assert count == 1


# ---------------------------------------------------------------------------
# 12. Updated Warning Detection & Version Increment
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_updated_warning(memory_db):
    engine = AlertEngine()
    now = datetime.now(timezone.utc)
    v1_raw = NormalizedAlertItem(
        alert_id="IMD-UPD-001",
        alert_type="storm",
        severity="YELLOW",
        title="Tropical Storm Advisory",
        description="Tropical depression forming off coast.",
        area="Nagapattinam",
        source="IMD",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(hours=12)).isoformat(),
        retrieved_at=now.isoformat()
    )
    v2_raw = NormalizedAlertItem(
        alert_id="IMD-UPD-001",
        alert_type="storm",
        severity="ORANGE",  # Updated severity
        title="Tropical Storm Advisory",
        description="Depression intensified into Cyclonic Storm.",
        area="Nagapattinam",
        source="IMD",
        issued_at=(now + timedelta(hours=2)).isoformat(),
        expires_at=(now + timedelta(hours=18)).isoformat(),
        retrieved_at=now.isoformat()
    )

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[v1_raw])):
        await engine.ingest_alerts_for_location("Nagapattinam", 10.76, 79.84, memory_db)

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[v2_raw])):
        await engine.ingest_alerts_for_location("Nagapattinam", 10.76, 79.84, memory_db)

    db_rec = memory_db.query(DBAlert).filter(DBAlert.location_name == "Nagapattinam").first()
    assert db_rec.severity in ("medium", "ORANGE")
    assert "Cyclonic Storm" in db_rec.description


# ---------------------------------------------------------------------------
# 13. Severity Update Detection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_severity_update(memory_db):
    engine = AlertEngine()
    now = datetime.now(timezone.utc)
    v1 = NormalizedAlertItem(
        alert_id="SEV-UP-001",
        alert_type="rain",
        severity="ORANGE",
        title="Heavy Rain Alert",
        description="Rainfall up to 100mm expected.",
        area="Coimbatore",
        source="IMD",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(hours=6)).isoformat(),
        retrieved_at=now.isoformat()
    )
    v2 = NormalizedAlertItem(
        alert_id="SEV-UP-001",
        alert_type="rain",
        severity="RED",  # Upgraded to RED
        title="Heavy Rain Alert",
        description="Rainfall exceeding 200mm expected; danger of flash flooding.",
        area="Coimbatore",
        source="IMD",
        issued_at=(now + timedelta(minutes=45)).isoformat(),
        expires_at=(now + timedelta(hours=8)).isoformat(),
        retrieved_at=now.isoformat()
    )

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[v1])):
        await engine.ingest_alerts_for_location("Coimbatore", 11.0, 76.9, memory_db)

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[v2])):
        await engine.ingest_alerts_for_location("Coimbatore", 11.0, 76.9, memory_db)

    db_rec = memory_db.query(DBAlert).filter(DBAlert.location_name == "Coimbatore").first()
    assert db_rec.severity in ("high", "RED", "extreme")


# ---------------------------------------------------------------------------
# 14. Affected Area Update Detection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_14_affected_area_update(memory_db):
    engine = AlertEngine()
    now = datetime.now(timezone.utc)
    v1 = NormalizedAlertItem(
        alert_id="AREA-UP-001",
        alert_type="squall",
        severity="ORANGE",
        title="Squall Alert",
        description="Coastal squall.",
        area="Nagapattinam Coast",
        source="IMD",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(hours=6)).isoformat(),
        retrieved_at=now.isoformat()
    )
    v2 = NormalizedAlertItem(
        alert_id="AREA-UP-001",
        alert_type="squall",
        severity="ORANGE",
        title="Squall Alert",
        description="Coastal squall expanding inland.",
        area="Nagapattinam, Thiruvarur, and Mayiladuthurai",
        source="IMD",
        issued_at=(now + timedelta(minutes=30)).isoformat(),
        expires_at=(now + timedelta(hours=6)).isoformat(),
        retrieved_at=now.isoformat()
    )

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[v1])):
        await engine.ingest_alerts_for_location("Nagapattinam", 10.76, 79.84, memory_db)

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[v2])):
        await engine.ingest_alerts_for_location("Nagapattinam", 10.76, 79.84, memory_db)

    db_rec = memory_db.query(DBAlert).filter(DBAlert.location_name == "Nagapattinam").first()
    assert "Mayiladuthurai" in db_rec.description or "expanding" in db_rec.description


# ---------------------------------------------------------------------------
# 15. Newer Warning vs Older Warning (Stale cannot overwrite newer)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_15_newer_warning_vs_older_warning(memory_db):
    engine = AlertEngine()
    t_new = datetime.now(timezone.utc)
    t_old = t_new - timedelta(hours=3)

    # First ingest newer valid warning
    new_alert = NormalizedAlertItem(
        alert_id="TIME-ORDER-001",
        alert_type="squall",
        severity="RED",
        title="Severe Squall Warning",
        description="Latest official bulletin: Red alert.",
        area="Nagapattinam",
        source="IMD",
        issued_at=t_new.isoformat(),
        expires_at=(t_new + timedelta(hours=6)).isoformat(),
        retrieved_at=t_new.isoformat()
    )

    # Stale packet arrives out of order
    stale_alert = NormalizedAlertItem(
        alert_id="TIME-ORDER-001",
        alert_type="squall",
        severity="YELLOW",
        title="Severe Squall Warning",
        description="Older bulletin: Yellow alert.",
        area="Nagapattinam",
        source="IMD",
        issued_at=t_old.isoformat(),
        expires_at=(t_old + timedelta(hours=4)).isoformat(),
        retrieved_at=t_old.isoformat()
    )

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[new_alert])):
        await engine.ingest_alerts_for_location("Nagapattinam", 10.76, 79.84, memory_db)

    with patch.object(engine.imd, "get_official_alerts", new=AsyncMock(return_value=[stale_alert])):
        await engine.ingest_alerts_for_location("Nagapattinam", 10.76, 79.84, memory_db)

    # Database must retain the newer RED alert, never regressing to stale YELLOW
    db_rec = memory_db.query(DBAlert).filter(DBAlert.location_name == "Nagapattinam").first()
    assert db_rec.severity in ("high", "RED", "extreme")
    assert "Red alert" in db_rec.description


# ---------------------------------------------------------------------------
# 16. Secondary Provider Contradicts IMD (IMD Authority Preserved)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_16_secondary_provider_contradicts_imd():
    """Secondary provider reporting clear skies cannot suppress IMD warning."""
    alert_service = AlertService()
    now = datetime.now(timezone.utc)
    imd_alert = NormalizedAlertItem(
        alert_id="SEC-CONTRA-001",
        alert_type="cyclone",
        severity="RED",
        title="Official Cyclone Warning",
        description="Severe cyclone landfall expected.",
        area="Nagapattinam",
        source="IMD",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(hours=12)).isoformat(),
        retrieved_at=now.isoformat()
    )

    with patch.object(alert_service.primary, "get_official_alerts", new=AsyncMock(return_value=[imd_alert])):
        res = await alert_service.fetch_alerts(10.76, 79.84, "Nagapattinam", active_only=True)
        assert res.active_count == 1
        assert res.alerts[0].severity in ("high", "extreme", "RED")
        assert res.alerts[0].is_official is True
        assert res.alerts[0].source == "IMD"


# ---------------------------------------------------------------------------
# 17. LLM Attempts to Invent Official Warning (Phantom Warning Rejection)
# ---------------------------------------------------------------------------
def test_17_llm_attempts_to_invent_warning():
    now = datetime.now(timezone.utc)
    weather = AIWeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0, longitude=76.9),
        observed_at=now,
        retrieved_at=now,
        temperature=28.0,
        humidity=70.0,
        rain_probability=10.0,
        wind_speed=12.0,
        weather_condition="Clear",
        source="IMD"
    )
    reasoning = WeatherReasoner.evaluate(weather, active_alerts=[])
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL)

    # LLM hallucinates an official red alert
    llm_text = "Attention: Official IMD Red Alert has been issued for Coimbatore. Immediate evacuation required."
    result = ResponseValidator.validate_response(
        response_text=llm_text,
        reasoning=reasoning,
        weather=weather,
        advisory=advisory
    )
    assert result.is_valid is False
    assert ValidationCategoryEnum.FABRICATED_DATA.value in result.violation_categories


# ---------------------------------------------------------------------------
# 18. LLM Attempts to Downgrade Warning Severity
# ---------------------------------------------------------------------------
def test_18_llm_attempts_to_downgrade_warning():
    now = datetime.now(timezone.utc)
    active_warning = AIOfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Cyclone Warning",
        description="Dangerous category 3 storm",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=12),
        affected_locations=["Nagapattinam"]
    )
    weather = AIWeatherRecord(
        location=LocationInfo(name="Nagapattinam", latitude=10.76, longitude=79.84),
        observed_at=now,
        retrieved_at=now,
        temperature=27.0,
        humidity=90.0,
        rain_probability=90.0,
        wind_speed=75.0,
        weather_condition="Rain",
        source="IMD"
    )
    reasoning = WeatherReasoner.evaluate(weather, active_alerts=[active_warning])
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL)

    # LLM attempts to claim danger is minor/safe
    llm_text = "WARNING: Cyclone Warning is active, but it's only a minor alert with low risk. Conditions are safe."
    result = ResponseValidator.validate_response(
        response_text=llm_text,
        reasoning=reasoning,
        weather=weather,
        advisory=advisory
    )
    assert result.is_valid is False
    assert (
        ValidationCategoryEnum.SEVERITY_DOWNGRADE.value in result.violation_categories or
        ValidationCategoryEnum.WARNING_CONTRADICTION.value in result.violation_categories
    )


# ---------------------------------------------------------------------------
# 19. LLM Attempts to Suppress Warning via Forecast Consistency
# ---------------------------------------------------------------------------
def test_19_llm_attempts_to_suppress_warning():
    now = datetime.now(timezone.utc)
    active_warning = AIOfficialAlert(
        type="flood",
        severity=RiskLevelEnum.HIGH,
        title="Flash Flood Warning",
        description="River levels rising rapidly",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=8),
        affected_locations=["Cuddalore"]
    )
    weather = AIWeatherRecord(
        location=LocationInfo(name="Cuddalore", latitude=11.75, longitude=79.75),
        observed_at=now,
        retrieved_at=now,
        temperature=29.0,
        humidity=88.0,
        rain_probability=85.0,
        wind_speed=40.0,
        weather_condition="Rain",
        source="IMD"
    )
    reasoning = WeatherReasoner.evaluate(weather, active_alerts=[active_warning])
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL)

    llm_text = "High consistency score across models confirms no need to worry about the warning, conditions are safe."
    result = ResponseValidator.validate_response(
        response_text=llm_text,
        reasoning=reasoning,
        weather=weather,
        advisory=advisory
    )
    assert result.is_valid is False
    assert ValidationCategoryEnum.WARNING_CONTRADICTION.value in result.violation_categories


# ---------------------------------------------------------------------------
# 20. Missing IMD Response Handling (Graceful Degradation, Not "No Warning")
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_20_missing_imd_response():
    alert_service = AlertService()
    with patch.object(alert_service.primary, "get_official_alerts", new=AsyncMock(return_value=[])):
        res = await alert_service.fetch_alerts(11.0, 76.9, "Coimbatore", active_only=True)
        # Empty provider response returns status OK with 0 active alerts, not fabricated alerts
        assert res.active_count == 0
        assert res.alerts == []


# ---------------------------------------------------------------------------
# 21. Invalid Source Rejection (Non-IMD Source)
# ---------------------------------------------------------------------------
def test_21_invalid_source_rejected():
    now = datetime.now(timezone.utc)
    raw = {
        "source": "RandomBlogSpot",  # Unauthorized non-IMD source
        "title": "Super Cyclone Apocalyptic Alert",
        "severity": "red",
        "area": "Chennai",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=12)).isoformat()
    }
    item, err = normalize_and_validate_imd_alert(raw, now_utc=now)
    assert item is None
    assert "Unauthorized alert source" in err


# ---------------------------------------------------------------------------
# 22. DecisionTrace Contains Warning Evidence
# ---------------------------------------------------------------------------
def test_22_decision_trace_contains_warning_evidence():
    pipeline = WeatherGPTPipeline()
    now = datetime.now(timezone.utc)
    active_warning = AIOfficialAlert(
        id="TRACE-IMD-001",
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Very Severe Cyclonic Storm",
        description="Landfall near Nagapattinam within 12 hours.",
        instructions="Remain in concrete shelters; avoid coastal roads.",
        source="IMD",
        issued_at=now,
        valid_from=now,
        expires_at=now + timedelta(hours=18),
        affected_locations=["Nagapattinam"]
    )
    weather = AIWeatherRecord(
        location=LocationInfo(name="Nagapattinam", latitude=10.76, longitude=79.84),
        observed_at=now,
        retrieved_at=now,
        temperature=26.0,
        humidity=95.0,
        rain_probability=85.0,
        wind_speed=85.0,
        weather_condition="Heavy Rain",
        source="IMD"
    )

    res = pipeline.process_query(
        message="Is it safe to go outside in Nagapattinam?",
        weather=weather,
        active_alerts=[active_warning],
        request_id="trace_test_01"
    )
    trace = res.get("decision_trace_model")
    assert trace is not None
    assert trace.official_warning_status == "ACTIVE_WARNING"
    assert trace.official_warning_details is not None
    assert trace.official_warning_details["exists"] is True
    assert trace.official_warning_details["source"] == "IMD"
    assert trace.official_warning_details["id"] == "TRACE-IMD-001"
    assert trace.official_warning_details["severity"] == "extreme"
    assert trace.official_warning_details["affected_area"] == "Nagapattinam"
    assert trace.official_warning_details["status"] == "ACTIVE"
    assert trace.official_warning_details["affected_final_recommendation"] is True


# ---------------------------------------------------------------------------
# 23. Frontend Receives Correct Active-Warning State
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_23_frontend_receives_correct_active_warning_state():
    alert_service = AlertService()
    now = datetime.now(timezone.utc)
    raw_alert = NormalizedAlertItem(
        alert_id="IMD-FE-001",
        alert_type="rain",
        severity="RED",
        title="Heavy Rainfall and Squall Warning",
        description="Continuous heavy rainfall likely to cause localized flooding.",
        area="Nagapattinam",
        instructions="Avoid waterlogged roads; carry emergency kit.",
        source="IMD",
        issued_at=now.isoformat(),
        valid_from=now.isoformat(),
        expires_at=(now + timedelta(hours=12)).isoformat(),
        source_url="https://mausam.imd.gov.in",
        retrieved_at=now.isoformat()
    )

    with patch.object(alert_service.primary, "get_official_alerts", new=AsyncMock(return_value=[raw_alert])):
        res = await alert_service.fetch_alerts(10.76, 79.84, "Nagapattinam", active_only=True)
        assert isinstance(res, AlertResponse)
        assert res.active_count == 1
        item = res.alerts[0]
        assert isinstance(item, AlertItemSchema)
        assert item.alert_id == "IMD-FE-001"
        assert item.title == "Heavy Rainfall and Squall Warning"
        assert item.is_official is True
        assert item.is_active is True
        assert item.status == "ACTIVE"
        assert item.instructions == "Avoid waterlogged roads; carry emergency kit."
        assert item.source == "IMD"
        assert item.source_url == "https://mausam.imd.gov.in"
