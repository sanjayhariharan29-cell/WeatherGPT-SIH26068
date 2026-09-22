"""Automated tests for Skizen Proactive Severe Weather Alerts & Deduplication (Phase 3)."""

import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.session import SessionLocal
from backend.db.models import User, UserPreference, BriefingDeliveryLog
from backend.services.briefing_service import PersonalizedBriefingService
from backend.services.briefing_scheduler import (
    BriefingScheduler,
    compute_event_fingerprint,
    get_severity_rank
)
from ai.models import LanguageEnum, RiskLevelEnum


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_user(db):
    """Creates a temporary test user with severe alerts enabled."""
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        name="Test Proactive Alert User",
        email=f"alert_user_{uid[:8]}@example.com",
        password_hash="test_hash",
        persona="fisherman",
        language="en",
        role="user",
        phone_number="+919840998877",
        is_verified=True,
        onboarding_completed=True
    )
    pref = UserPreference(
        user_id=uid,
        persona="fisherman",
        daily_sms_enabled=True,
        professional_advisory_enabled=True,
        severe_alerts_enabled=True,
        briefing_time="07:00",
        last_known_location="Chennai",
        last_latitude=13.0827,
        last_longitude=80.2707
    )
    db.add(user)
    db.add(pref)
    db.commit()
    db.refresh(user)
    yield user

    # Cleanup
    db.query(BriefingDeliveryLog).filter(BriefingDeliveryLog.user_id == uid).delete()
    db.query(UserPreference).filter(UserPreference.user_id == uid).delete()
    db.query(User).filter(User.id == uid).delete()
    db.commit()


@pytest.mark.asyncio
async def test_proactive_alert_message_format_and_roles():
    """Validates urgent message header, time window, outlook, reason, and <320 char limit across EN, TA, HI."""
    service = PersonalizedBriefingService()
    roles = ["fisherman", "farmer", "commuter", "student", "outdoor_worker"]

    simulated_warning = {
        "id": "IMD-WARN-2026-TEST",
        "hazard_type": "Severe Thunderstorm & Squall",
        "severity": "HIGH",
        "title": "Severe Thunderstorm Warning",
        "description": "Squall wind speed 55-65 km/h with heavy rain",
        "valid_window": "14:00-20:00 IST",
        "location": "Chennai"
    }

    # 1. English format test
    for role in roles:
        res_en = await service.generate_proactive_alert(
            override_role=role,
            override_location="Chennai",
            override_language="en",
            active_alert_override=simulated_warning
        )
        assert res_en.character_count <= 320
        assert "🚨 SKIZEN WEATHER ALERT" in res_en.message_text
        assert "Valid: 14:00-20:00 IST" in res_en.message_text
        assert "Reason: " in res_en.message_text
        assert "Outlook: " in res_en.message_text
        assert len(res_en.reasoning_bullets) >= 3

    # 2. Tamil format test
    res_ta = await service.generate_proactive_alert(
        override_role="fisherman",
        override_location="சென்னை",
        override_language="ta",
        active_alert_override=simulated_warning
    )
    assert res_ta.character_count <= 320
    assert "🚨 SKIZEN வானிலை எச்சரிக்கை" in res_ta.message_text
    assert "காலஅளவு: 14:00-20:00 IST" in res_ta.message_text
    assert "காரணம்: " in res_ta.message_text
    assert "பார்வை: " in res_ta.message_text

    # 3. Hindi format test
    res_hi = await service.generate_proactive_alert(
        override_role="farmer",
        override_location="चेन्नई",
        override_language="hi",
        active_alert_override=simulated_warning
    )
    assert res_hi.character_count <= 320
    assert "🚨 SKIZEN मौसम चेतावनी" in res_hi.message_text
    assert "वैधता: 14:00-20:00 IST" in res_hi.message_text
    assert "कारण: " in res_hi.message_text
    assert "सलाह: " in res_hi.message_text


@pytest.mark.asyncio
async def test_proactive_alert_single_dispatch_and_deduplication(db, test_user):
    """Simulates a new warning becoming active and confirms exactly 1 alert is logged, and re-checking suppresses duplicates."""
    scheduler = BriefingScheduler()

    simulated_warning = {
        "id": "IMD-WARN-COASTAL-SQUALL-01",
        "hazard_type": "Coastal Squall & Gale",
        "severity": "HIGH",
        "title": "Coastal Gale Warning",
        "valid_window": "15:00-21:00 IST",
        "location": "Chennai"
    }

    # Step 1: Initial event trigger -> exactly one alert should be generated and logged
    res1 = await scheduler.dispatch_proactive_alert_for_user(
        user=test_user,
        db=db,
        simulated_alert=simulated_warning
    )
    assert res1["status"] == "MOCK_SMS_DELIVERY"
    assert "log_id" in res1
    assert res1["event_fingerprint"] is not None
    assert res1["character_count"] <= 320

    # Verify 1 record exists in DB
    logs_step1 = db.query(BriefingDeliveryLog).filter(
        BriefingDeliveryLog.user_id == test_user.id,
        BriefingDeliveryLog.message_type == "proactive"
    ).all()
    assert len(logs_step1) == 1
    assert logs_step1[0].event_fingerprint == res1["event_fingerprint"]
    assert logs_step1[0].delivery_status == "MOCK_SMS_DELIVERY"

    # Step 2: Re-check with the EXACT SAME ongoing warning -> MUST suppress duplicate
    res2 = await scheduler.dispatch_proactive_alert_for_user(
        user=test_user,
        db=db,
        simulated_alert=simulated_warning
    )
    assert res2["status"] == "SKIPPED"
    assert res2["reason"] == "duplicate_ongoing_event_suppressed"
    assert res2["event_fingerprint"] == res1["event_fingerprint"]

    # Verify STILL exactly 1 record exists in DB (zero duplicates written)
    logs_step2 = db.query(BriefingDeliveryLog).filter(
        BriefingDeliveryLog.user_id == test_user.id,
        BriefingDeliveryLog.message_type == "proactive"
    ).all()
    assert len(logs_step2) == 1


@pytest.mark.asyncio
async def test_proactive_alert_escalation(db, test_user):
    """Verifies that duplicate suppression allows an alert if warning severity escalates."""
    scheduler = BriefingScheduler()

    # Initial MODERATE warning
    warning_moderate = {
        "id": "IMD-WARN-MONSOON-SURGE",
        "hazard_type": "Monsoon Surge",
        "severity": "MODERATE",
        "title": "Moderate Surge Warning",
        "valid_window": "12:00-18:00 IST",
        "location": "Chennai"
    }

    # 1. Dispatch initial MODERATE
    res1 = await scheduler.dispatch_proactive_alert_for_user(
        user=test_user, db=db, simulated_alert=warning_moderate
    )
    assert res1["status"] == "MOCK_SMS_DELIVERY"
    assert res1["escalated"] is False

    # 2. Re-check same MODERATE -> Suppressed
    res2 = await scheduler.dispatch_proactive_alert_for_user(
        user=test_user, db=db, simulated_alert=warning_moderate
    )
    assert res2["status"] == "SKIPPED"

    # 3. Warning ESCALATES to HIGH
    warning_high = {
        "id": "IMD-WARN-MONSOON-SURGE",
        "hazard_type": "Monsoon Surge",
        "severity": "HIGH",
        "title": "Severe Monsoon Surge & Squall",
        "valid_window": "12:00-18:00 IST",
        "location": "Chennai"
    }

    res3 = await scheduler.dispatch_proactive_alert_for_user(
        user=test_user, db=db, simulated_alert=warning_high
    )
    assert res3["status"] == "MOCK_SMS_DELIVERY"
    assert res3["escalated"] is True
    assert "[ESCALATED]" in res3["message_text"]

    # Verify DB has 2 records (1 initial + 1 escalated)
    logs = db.query(BriefingDeliveryLog).filter(
        BriefingDeliveryLog.user_id == test_user.id,
        BriefingDeliveryLog.message_type == "proactive"
    ).all()
    assert len(logs) == 2


@pytest.mark.asyncio
async def test_proactive_skips_when_severe_alerts_disabled(db, test_user):
    """Verifies proactive alerts are skipped when severe_alerts_enabled is False."""
    test_user.preferences.severe_alerts_enabled = False
    db.commit()

    scheduler = BriefingScheduler()
    simulated_warning = {
        "id": "IMD-WARN-CYCLONE-01",
        "hazard_type": "Cyclone Warning",
        "severity": "HIGH",
        "title": "Cyclone Warning",
        "valid_window": "10:00-16:00 IST",
        "location": "Chennai"
    }

    res = await scheduler.dispatch_proactive_alert_for_user(
        user=test_user, db=db, simulated_alert=simulated_warning
    )
    assert res["status"] == "SKIPPED"
    assert res["reason"] == "severe_alerts_disabled"


def test_proactive_check_api_endpoint(client, test_user):
    """Tests POST /api/v1/briefing/proactive/check endpoint."""
    simulated_warning = {
        "id": "IMD-WARN-API-TEST-99",
        "hazard_type": "Thunderstorm",
        "severity": "HIGH",
        "title": "Severe Thunderstorm",
        "valid_window": "16:00-22:00 IST",
        "location": "Chennai"
    }

    payload = {
        "user_id": test_user.id,
        "simulated_warning": simulated_warning
    }

    # Run 1: Should trigger proactive alert
    resp1 = client.post("/api/v1/briefing/proactive/check", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["alerts_triggered"] == 1
    assert data1["results"][0]["status"] == "MOCK_SMS_DELIVERY"

    # Run 2: Immediate re-check -> Duplicate suppressed!
    resp2 = client.post("/api/v1/briefing/proactive/check", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["alerts_triggered"] == 0
    assert data2["results"][0]["status"] == "SKIPPED"
    assert data2["results"][0]["reason"] == "duplicate_ongoing_event_suppressed"
