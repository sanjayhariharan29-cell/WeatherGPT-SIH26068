"""Automated tests for Skizen Daily Briefing Scheduler, Mock Delivery, and History (Phase 2)."""

import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.session import SessionLocal
from backend.db.models import User, UserPreference, BriefingDeliveryLog
from backend.services.sms.mock_provider import MockSMSProvider
from backend.services.briefing_scheduler import BriefingScheduler, scheduler_service
from backend.core.security import create_access_token


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
    """Creates a temporary test user with preferences for scheduler testing."""
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        name="Test Fisherman User",
        email=f"fisherman_{uid[:8]}@example.com",
        password_hash="test_hash",
        persona="fisherman",
        language="en",
        role="user",
        phone_number="+919840112233",
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
async def test_mock_sms_provider():
    """Validates honest mock SMS delivery logging and status."""
    provider = MockSMSProvider()
    result = await provider.send_sms(
        to_phone="+919840112233",
        message="📍 Chennai | 🟢 LOW (Skizen)\nWind: 15 km/h.\nUpdated: 07:00 IST",
        metadata={"role": "fisherman", "location_name": "Chennai", "risk_level": "LOW"}
    )
    assert result.success is True
    assert result.delivery_status == "MOCK_SMS_DELIVERY"
    assert result.provider == "mock_logger"
    assert result.character_count > 0
    assert result.message_id is not None


@pytest.mark.asyncio
async def test_scheduler_dispatch_single_user(db, test_user):
    """Verifies that the scheduler generates a briefing, mock-delivers it, and writes history."""
    scheduler = BriefingScheduler()
    res = await scheduler.dispatch_user_briefing(user=test_user, db=db, message_type="daily")

    assert res["status"] == "MOCK_SMS_DELIVERY"
    assert res["user_id"] == test_user.id
    assert res["character_count"] <= 320
    assert "log_id" in res

    # Verify database persistence in briefing_delivery_logs
    log = db.query(BriefingDeliveryLog).filter(BriefingDeliveryLog.id == res["log_id"]).first()
    assert log is not None
    assert log.delivery_status == "MOCK_SMS_DELIVERY"
    assert log.role == "fisherman"
    assert log.location_name == "Chennai"
    assert log.message_text == res["message_text"]
    assert log.character_count <= 320


@pytest.mark.asyncio
async def test_scheduler_skips_disabled_user(db, test_user):
    """Verifies that users with daily_sms_enabled=False are skipped unless forced."""
    test_user.preferences.daily_sms_enabled = False
    db.commit()

    scheduler = BriefingScheduler()
    res = await scheduler.dispatch_user_briefing(user=test_user, db=db, message_type="daily", force_override=False)
    assert res["status"] == "SKIPPED"
    assert res["reason"] == "daily_sms_disabled"


def test_briefing_history_api(client, db, test_user):
    """Verifies GET /api/v1/briefing/history returns persisted log items with parsed bullets."""
    # Seed a log entry
    log_id = str(uuid.uuid4())
    log_entry = BriefingDeliveryLog(
        id=log_id,
        user_id=test_user.id,
        message_type="daily",
        location_name="Chennai",
        role="fisherman",
        phone_number="+919840112233",
        risk_level="HIGH",
        risk_status_label="🔴 HIGH RISK (Skizen-derived assessment)",
        delivery_status="MOCK_SMS_DELIVERY",
        data_source="OpenWeather / Open-Meteo / IMD",
        data_freshness="fresh",
        message_text="📍 Chennai | 🔴 HIGH (Skizen)\nWind: 28 km/h.\nUpdated: 07:00 IST",
        character_count=65,
        reasoning_bullets='["Your registered profile is Fisherman.", "Wind gusts exceed caution threshold."]',
        delivered_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)
    )
    db.add(log_entry)
    db.commit()

    resp = client.get(f"/api/v1/briefing/history?user_id={test_user.id}&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1
    item = data["items"][0]
    assert item["delivery_status"] == "MOCK_SMS_DELIVERY"
    assert item["role"] == "fisherman"
    assert len(item["reasoning_bullets"]) == 2
    assert "Fisherman" in item["reasoning_bullets"][0]


def test_scheduler_trigger_api(client, test_user):
    """Verifies POST /api/v1/briefing/scheduler/trigger dispatches briefings on-demand."""
    payload = {
        "user_id": test_user.id,
        "force_all": True
    }
    resp = client.post("/api/v1/briefing/scheduler/trigger", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["dispatched_count"] >= 1
    first_res = data["results"][0]
    assert first_res["status"] == "MOCK_SMS_DELIVERY"
    assert first_res["character_count"] <= 320


def test_briefing_settings_api(client, test_user):
    """Verifies authenticated GET and PUT /api/v1/briefing/settings endpoints."""
    token = create_access_token({"sub": test_user.id, "email": test_user.email, "role": test_user.role})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. GET settings
    get_resp = client.get("/api/v1/briefing/settings", headers=headers)
    assert get_resp.status_code == 200
    settings = get_resp.json()
    assert settings["daily_sms_enabled"] is True
    assert settings["briefing_time"] == "07:00"

    # 2. PUT settings
    update_payload = {
        "daily_sms_enabled": True,
        "professional_advisory_enabled": True,
        "severe_alerts_enabled": True,
        "briefing_time": "08:30",
        "phone_number": "+919876500000"
    }
    put_resp = client.put("/api/v1/briefing/settings", json=update_payload, headers=headers)
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["briefing_time"] == "08:30"
    assert updated["phone_number"] == "+919876500000"
