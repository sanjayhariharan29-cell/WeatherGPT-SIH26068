"""SkyZen Phase 3: Automatic IMD Alert Targeting & Notification Pipeline Test Suite.

Comprehensive deterministic test suite covering all 28 required safety scenarios:
 1. Active IMD warning targets affected user
 2. Active warning does not target unaffected user
 3. Multiple affected users
 4. Multiple saved locations
 5. Current or default location targeting
 6. Location ownership isolation
 7. Invalid geographic data handling
 8. Notification preference disabled
 9. Notification preference enabled
10. English notification payload
11. Tamil notification payload
12. Hindi notification payload
13. Severity preserved during translation
14. Affected area preserved during translation
15. Timing preserved during translation
16. Official instruction preserved during translation
17. Duplicate retrieval does not duplicate notification
18. Updated warning generates appropriate update notification
19. Expired warning does not notify
20. Invalid warning does not notify
21. Multiple devices all receive notifications
22. Invalid FCM token marked inactive
23. One device failure does not block another
24. FCM provider failure handled gracefully
25. Alert remains available inside SkyZen after notification failure
26. LLM cannot trigger official notification
27. Secondary provider cannot trigger official notification
28. DecisionTrace and audit history remain consistent
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.session import Base
from backend.db.models import (
    User,
    UserPreference,
    SavedLocation,
    DeviceToken,
    Alert as DBAlert,
    AlertDeliveryLog,
)
from backend.services.alert_engine import (
    AlertEngine,
    normalize_and_validate_imd_alert,
    is_alert_active,
)
from backend.services.notification_service import NotificationService


@pytest.fixture
def memory_db():
    """In-memory SQLite session fixture for fully isolated deterministic testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def create_test_user(
    db,
    user_id: str = "user-1",
    name: str = "Ravi Kumar",
    email: str = "ravi@skyzen.com",
    language: str = "ta",
    notification_enabled: bool = True
) -> User:
    """Helper to create an authenticated user with preferences in the test database."""
    user = User(
        id=user_id,
        name=name,
        email=email,
        password_hash="hashed_pw",
        language=language,
        persona="farmer",
        role="user",
        is_verified=True,
        onboarding_completed=True
    )
    db.add(user)
    pref = UserPreference(
        user_id=user_id,
        notification_enabled=notification_enabled
    )
    db.add(pref)
    db.commit()
    db.refresh(user)
    return user


def create_test_alert(
    db,
    alert_id: str = "alert-1",
    source: str = "IMD",
    location_name: str = "Chennai",
    alert_type: str = "cyclone",
    severity: str = "high",
    title: str = "Cyclone Alert",
    description: str = "Severe cyclone approaching coast.",
    lat: float = 13.0827,
    lon: float = 80.2707,
    offset_hours_expiry: int = 24,
    offset_hours_issue: int = 0,
    version: int = 1
) -> DBAlert:
    """Helper to create a DBAlert record in the test database."""
    now = datetime.now(timezone.utc)
    iss_dt = now + timedelta(hours=offset_hours_issue)
    exp_dt = now + timedelta(hours=offset_hours_expiry)
    alert = DBAlert(
        id=alert_id,
        location_name=location_name,
        latitude=lat,
        longitude=lon,
        alert_type=alert_type,
        severity=severity,
        title=title,
        description=description,
        source=source,
        issued_at=iss_dt,
        expires_at=exp_dt
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


# ===========================================================================
# 1. Active IMD Warning Targets Affected User
# ===========================================================================
@pytest.mark.asyncio
async def test_01_active_imd_warning_targets_affected_user(memory_db):
    user = create_test_user(memory_db, user_id="u-1", name="Sanjay", language="en")
    sl = SavedLocation(id="sl-1", user_id=user.id, name="Chennai", latitude=13.0827, longitude=80.2707)
    memory_db.add(sl)
    dev = DeviceToken(id="dt-1", user_id=user.id, token="token-device-1", platform="android", is_active=True)
    memory_db.add(dev)
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-1", location_name="Chennai", severity="high")

    engine = AlertEngine()
    results = await engine.process_alert_delivery(alert, memory_db)

    assert len(results) == 1
    assert results[0]["user_id"] == user.id
    assert results[0]["status"] == "SENT"
    assert results[0]["matched_location"] == "Chennai"


# ===========================================================================
# 2. Active Warning Does Not Target Unaffected User
# ===========================================================================
@pytest.mark.asyncio
async def test_02_active_warning_does_not_target_unaffected_user(memory_db):
    user = create_test_user(memory_db, user_id="u-2", name="Karthik", language="en")
    sl = SavedLocation(id="sl-2", user_id=user.id, name="Coimbatore", latitude=11.0168, longitude=76.9558)
    memory_db.add(sl)
    dev = DeviceToken(id="dt-2", user_id=user.id, token="token-device-2", platform="android", is_active=True)
    memory_db.add(dev)
    memory_db.commit()

    alert = create_test_alert(
        memory_db,
        alert_id="a-2",
        location_name="Nagapattinam",
        lat=10.7656,
        lon=79.8424,
        severity="extreme"
    )

    engine = AlertEngine()
    results = await engine.process_alert_delivery(alert, memory_db)

    assert len(results) == 1
    assert results[0]["user_id"] == user.id
    assert results[0]["status"] == "SKIPPED"
    assert results[0]["reason"] == "out_of_area"


# ===========================================================================
# 3. Multiple Affected Users
# ===========================================================================
@pytest.mark.asyncio
async def test_03_multiple_affected_users(memory_db):
    u1 = create_test_user(memory_db, user_id="u-3a", name="User 1", email="u1@test.com")
    u2 = create_test_user(memory_db, user_id="u-3b", name="User 2", email="u2@test.com")
    u3 = create_test_user(memory_db, user_id="u-3c", name="User 3", email="u3@test.com")

    memory_db.add(SavedLocation(id="sl-3a", user_id=u1.id, name="Chennai", latitude=13.08, longitude=80.27))
    memory_db.add(SavedLocation(id="sl-3b", user_id=u2.id, name="Tiruvallur", latitude=13.14, longitude=79.91))
    memory_db.add(SavedLocation(id="sl-3c", user_id=u3.id, name="Madurai", latitude=9.92, longitude=78.11))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-3", location_name="Chennai", lat=13.08, lon=80.27)

    engine = AlertEngine()
    results = await engine.process_alert_delivery(alert, memory_db)

    delivered_users = [r["user_id"] for r in results if r["status"] == "SENT"]
    skipped_users = [r["user_id"] for r in results if r["status"] == "SKIPPED"]

    assert u1.id in delivered_users
    assert u2.id in delivered_users
    assert u3.id in skipped_users


# ===========================================================================
# 4. Multiple Saved Locations
# ===========================================================================
@pytest.mark.asyncio
async def test_04_multiple_saved_locations(memory_db):
    user = create_test_user(memory_db, user_id="u-4")
    memory_db.add(SavedLocation(id="sl-4a", user_id=user.id, name="Home (Salem)", latitude=11.66, longitude=78.14))
    memory_db.add(SavedLocation(id="sl-4b", user_id=user.id, name="College (Madurai)", latitude=9.92, longitude=78.11))
    memory_db.add(SavedLocation(id="sl-4c", user_id=user.id, name="Farm (Cuddalore)", latitude=11.75, longitude=79.76))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-4", location_name="Cuddalore Coastal Belt", lat=11.75, lon=79.76)

    engine = AlertEngine()
    results = await engine.process_alert_delivery(alert, memory_db)

    assert len(results) == 1
    assert results[0]["status"] == "SENT"
    assert results[0]["matched_location"] == "Farm (Cuddalore)"


# ===========================================================================
# 5. Current / Default Location Targeting
# ===========================================================================
@pytest.mark.asyncio
async def test_05_current_or_default_location_targeting(memory_db):
    user = create_test_user(memory_db, user_id="u-5")

    alert = create_test_alert(memory_db, alert_id="a-5", location_name="Coimbatore", lat=11.0168, lon=76.9558)

    engine = AlertEngine()
    results = await engine.process_alert_delivery(alert, memory_db)

    assert len(results) == 1
    assert results[0]["status"] == "SENT"
    assert results[0]["matched_location"] == "Coimbatore"


# ===========================================================================
# 6. Location Ownership Isolation
# ===========================================================================
@pytest.mark.asyncio
async def test_06_location_ownership_isolation(memory_db):
    u_alice = create_test_user(memory_db, user_id="u-alice", email="alice@test.com")
    u_bob = create_test_user(memory_db, user_id="u-bob", email="bob@test.com")

    memory_db.add(SavedLocation(id="sl-a", user_id=u_alice.id, name="Chennai", latitude=13.08, longitude=80.27))
    memory_db.add(SavedLocation(id="sl-b", user_id=u_bob.id, name="Madurai", latitude=9.92, longitude=78.11))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-6", location_name="Chennai", lat=13.08, lon=80.27)

    engine = AlertEngine()
    results = await engine.process_alert_delivery(alert, memory_db)

    alice_res = [r for r in results if r["user_id"] == u_alice.id][0]
    bob_res = [r for r in results if r["user_id"] == u_bob.id][0]

    assert alice_res["status"] == "SENT"
    assert bob_res["status"] == "SKIPPED"
    assert bob_res["reason"] == "out_of_area"


# ===========================================================================
# 7. Invalid Geographic Data Handling
# ===========================================================================
@pytest.mark.asyncio
async def test_07_invalid_geographic_data(memory_db):
    user = create_test_user(memory_db, user_id="u-7")
    memory_db.add(SavedLocation(id="sl-7", user_id=user.id, name="XYZUnknownArea", latitude=999.0, longitude=-999.0))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-7", location_name="Chennai", lat=13.08, lon=80.27)

    engine = AlertEngine()
    results = await engine.process_alert_delivery(alert, memory_db)

    assert results[0]["status"] == "SKIPPED"
    assert results[0]["reason"] == "out_of_area"


# ===========================================================================
# 8. Notification Preference Disabled
# ===========================================================================
@pytest.mark.asyncio
async def test_08_notification_preference_disabled(memory_db):
    user = create_test_user(memory_db, user_id="u-8", notification_enabled=False)
    memory_db.add(SavedLocation(id="sl-8", user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-8", location_name="Chennai")

    engine = AlertEngine()
    results = await engine.process_alert_delivery(alert, memory_db)

    assert len(results) == 1
    assert results[0]["status"] == "SKIPPED"
    assert results[0]["reason"] == "notification_disabled"


# ===========================================================================
# 9. Notification Preference Enabled
# ===========================================================================
@pytest.mark.asyncio
async def test_09_notification_preference_enabled(memory_db):
    user = create_test_user(memory_db, user_id="u-9", notification_enabled=True)
    memory_db.add(SavedLocation(id="sl-9", user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-9", location_name="Chennai")

    engine = AlertEngine()
    results = await engine.process_alert_delivery(alert, memory_db)

    assert len(results) == 1
    assert results[0]["status"] == "SENT"


# ===========================================================================
# 10. English Notification Payload
# ===========================================================================
def test_10_english_notification_payload():
    service = NotificationService()
    msg = service.format_alert_message(
        title="Severe Flood Alert",
        description="Water level rising rapidly in Adyar river basin.",
        severity="high",
        language="en",
        area="Chennai",
        instructions="Move to higher ground immediately.",
        valid_until="2026-09-11T12:00:00Z"
    )

    assert "[IMD] Official Warning" in msg["title"]
    assert "HIGH" in msg["title"]
    assert "Area: Chennai" in msg["body"]
    assert "Move to higher ground immediately." in msg["body"]
    assert msg["language"] == "en"


# ===========================================================================
# 11. Tamil Notification Payload
# ===========================================================================
def test_11_tamil_notification_payload():
    service = NotificationService()
    msg = service.format_alert_message(
        title="கனமழை எச்சரிக்கை",
        description="அடுத்த 24 மணி நேரத்தில் மிக கனமழை பெய்யக்கூடும்.",
        severity="extreme",
        language="ta",
        area="நாகப்பட்டினம்",
        instructions="மீனவர்கள் கடலுக்கு செல்ல வேண்டாம்.",
        valid_until="2026-09-11T12:00:00Z"
    )

    assert "[IMD] அதிகாரப்பூர்வ வானிலை எச்சரிக்கை" in msg["title"]
    assert "EXTREME" in msg["title"]
    assert "பகுதி: நாகப்பட்டினம்" in msg["body"]
    assert "மீனவர்கள் கடலுக்கு செல்ல வேண்டாம்." in msg["body"]
    assert msg["language"] == "ta"


# ===========================================================================
# 12. Hindi Notification Payload
# ===========================================================================
def test_12_hindi_notification_payload():
    service = NotificationService()
    msg = service.format_alert_message(
        title="भारी वर्षा चेतावनी",
        description="तटीय क्षेत्रों में अत्यधिक भारी वर्षा की संभावना।",
        severity="high",
        language="hi",
        area="चेन्नई",
        instructions="सुरक्षित स्थानों पर रहें।",
        valid_until="2026-09-11T12:00:00Z"
    )

    assert "[IMD] आधिकारिक मौसम चेतावनी" in msg["title"]
    assert "HIGH" in msg["title"]
    assert "क्षेत्र: चेन्नई" in msg["body"]
    assert "सुरक्षित स्थानों पर रहें।" in msg["body"]
    assert msg["language"] == "hi"


# ===========================================================================
# 13. Severity Preserved During Translation
# ===========================================================================
@pytest.mark.parametrize("sev", ["low", "medium", "high", "extreme"])
def test_13_severity_preserved_during_translation(sev):
    service = NotificationService()
    for lang in ["en", "ta", "hi"]:
        msg = service.format_alert_message(
            title="Storm Alert",
            description="High velocity winds.",
            severity=sev,
            language=lang
        )
        assert sev.upper() in msg["title"], f"Severity {sev} not preserved in language {lang}"
        assert msg["severity"] == sev


# ===========================================================================
# 14. Affected Area Preserved During Translation
# ===========================================================================
def test_14_affected_area_preserved_during_translation():
    service = NotificationService()
    area = "Nagapattinam and Thanjavur Coastal Delta"
    for lang in ["en", "ta", "hi"]:
        msg = service.format_alert_message(
            title="Warning",
            description="Heavy rain.",
            severity="high",
            language=lang,
            area=area
        )
        assert area in msg["body"]
        assert msg["area"] == area


# ===========================================================================
# 15. Timing Preserved During Translation
# ===========================================================================
def test_15_timing_preserved_during_translation():
    service = NotificationService()
    expiry = "2026-09-11T18:00:00+00:00"
    for lang in ["en", "ta", "hi"]:
        msg = service.format_alert_message(
            title="Warning",
            description="Heavy rain.",
            severity="high",
            language=lang,
            valid_until=expiry
        )
        assert expiry in msg["body"]
        assert msg["valid_until"] == expiry


# ===========================================================================
# 16. Official Instruction Preserved During Translation
# ===========================================================================
def test_16_official_instruction_preserved_during_translation():
    service = NotificationService()
    instructions = "Evacuate within 2 hours. Rainfall exceeding 240mm expected with 75km/h wind."
    for lang in ["en", "ta", "hi"]:
        msg = service.format_alert_message(
            title="Warning",
            description="Details",
            severity="extreme",
            language=lang,
            instructions=instructions
        )
        assert "240mm" in msg["body"]
        assert "75km/h" in msg["body"]
        assert instructions in msg["body"]


# ===========================================================================
# 17. Duplicate Retrieval Does Not Duplicate Notification
# ===========================================================================
@pytest.mark.asyncio
async def test_17_duplicate_retrieval_does_not_duplicate_notification(memory_db):
    user = create_test_user(memory_db, user_id="u-17")
    memory_db.add(SavedLocation(id="sl-17", user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-17", location_name="Chennai")

    engine = AlertEngine()
    # Cycle 1: First dispatch
    res1 = await engine.process_alert_delivery(alert, memory_db)
    assert res1[0]["status"] == "SENT"

    # Cycle 2: Second identical polling cycle within quiet period
    res2 = await engine.process_alert_delivery(alert, memory_db)
    assert res2[0]["status"] == "SKIPPED"
    assert res2[0]["reason"] == "already_delivered"


# ===========================================================================
# 18. Updated Warning Generates Appropriate Update Notification
# ===========================================================================
@pytest.mark.asyncio
async def test_18_updated_warning_generates_new_notification(memory_db):
    user = create_test_user(memory_db, user_id="u-18")
    memory_db.add(SavedLocation(id="sl-18", user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-18", location_name="Chennai", severity="medium")

    engine = AlertEngine()
    res1 = await engine.process_alert_delivery(alert, memory_db)
    assert res1[0]["status"] == "SENT"

    # Authoritative IMD update: severity upgraded from medium -> extreme
    alert.severity = "extreme"
    alert.version = 2
    memory_db.commit()

    res2 = await engine.process_alert_delivery(alert, memory_db)
    assert res2[0]["status"] == "SENT"
    assert res2[0]["reason"] == "eligible_in_affected_area"


# ===========================================================================
# 19. Expired Warning Does Not Notify
# ===========================================================================
@pytest.mark.asyncio
async def test_19_expired_warning_does_not_notify(memory_db):
    user = create_test_user(memory_db, user_id="u-19")
    memory_db.add(SavedLocation(id="sl-19", user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-19", location_name="Chennai", offset_hours_expiry=-2)

    engine = AlertEngine()
    results = await engine.process_alert_delivery(alert, memory_db)

    assert len(results) == 1
    assert results[0]["status"] == "SKIPPED"
    assert results[0]["reason"] == "expired_alert"


# ===========================================================================
# 20. Invalid Warning Does Not Notify
# ===========================================================================
def test_20_invalid_warning_does_not_notify():
    # Test case A: Missing alert_type
    raw_a = {
        "source": "IMD",
        "title": "Invalid Alert",
        "severity": "high",
        "area": "Chennai",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
    }
    normalized_a, reason_a = normalize_and_validate_imd_alert(raw_a)
    assert normalized_a is None
    assert "alert_type" in reason_a.lower()

    # Test case B: Missing / blank affected area
    raw_b = {
        "source": "IMD",
        "title": "Invalid Alert",
        "alert_type": "flood",
        "severity": "high",
        "area": "",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
    }
    normalized_b, reason_b = normalize_and_validate_imd_alert(raw_b)
    assert normalized_b is None
    assert "affected area" in reason_b.lower()


# ===========================================================================
# 21. Multiple Devices All Receive Notifications
# ===========================================================================
@pytest.mark.asyncio
async def test_21_multiple_devices_all_receive(memory_db):
    user = create_test_user(memory_db, user_id="u-21")
    memory_db.add(SavedLocation(id="sl-21", user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27))

    d1 = DeviceToken(id="dt-21a", user_id=user.id, token="token-phone", platform="android", is_active=True)
    d2 = DeviceToken(id="dt-21b", user_id=user.id, token="token-tablet", platform="android", is_active=True)
    memory_db.add(d1)
    memory_db.add(d2)
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-21", location_name="Chennai")

    engine = AlertEngine()
    results = await engine.process_alert_delivery(alert, memory_db)

    assert len(results) == 2
    device_ids = [r["device_id"] for r in results]
    assert "dt-21a" in device_ids
    assert "dt-21b" in device_ids
    assert all(r["status"] == "SENT" for r in results)


# ===========================================================================
# 22. Invalid FCM Token Marked Inactive
# ===========================================================================
@pytest.mark.asyncio
async def test_22_invalid_fcm_token_marked_inactive(memory_db):
    user = create_test_user(memory_db, user_id="u-22")
    memory_db.add(SavedLocation(id="sl-22", user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27))
    dev = DeviceToken(id="dt-22", user_id=user.id, token="bad-token-unregistered", platform="android", is_active=True)
    memory_db.add(dev)
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-22", location_name="Chennai")

    mock_notifications = NotificationService()
    mock_notifications.send_push_notification = AsyncMock(return_value={
        "success": False,
        "error": "The registration token is not registered",
        "should_deactivate": True
    })

    engine = AlertEngine(notification_service=mock_notifications)
    results = await engine.process_alert_delivery(alert, memory_db)

    assert results[0]["status"] == "FAILED"
    refreshed_dev = memory_db.query(DeviceToken).filter(DeviceToken.id == "dt-22").first()
    assert refreshed_dev.is_active is False


# ===========================================================================
# 23. One Device Failure Does Not Block Another
# ===========================================================================
@pytest.mark.asyncio
async def test_23_one_device_failure_does_not_block_another(memory_db):
    user = create_test_user(memory_db, user_id="u-23")
    memory_db.add(SavedLocation(id="sl-23", user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27))

    d_bad = DeviceToken(id="dt-bad", user_id=user.id, token="token-bad", platform="android", is_active=True)
    d_good = DeviceToken(id="dt-good", user_id=user.id, token="token-good", platform="android", is_active=True)
    memory_db.add(d_bad)
    memory_db.add(d_good)
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-23", location_name="Chennai")

    mock_notifications = NotificationService()
    async def mock_dispatch(token, title, body, data=None):
        if token == "token-bad":
            return {"success": False, "error": "unregistered", "should_deactivate": True}
        return {"success": True, "mode": "mock_delivery"}

    mock_notifications.send_push_notification = AsyncMock(side_effect=mock_dispatch)

    engine = AlertEngine(notification_service=mock_notifications)
    results = await engine.process_alert_delivery(alert, memory_db)

    assert len(results) == 2
    bad_res = [r for r in results if r["device_id"] == "dt-bad"][0]
    good_res = [r for r in results if r["device_id"] == "dt-good"][0]

    assert bad_res["status"] == "FAILED"
    assert good_res["status"] == "SENT"

    assert memory_db.query(DeviceToken).filter(DeviceToken.id == "dt-bad").first().is_active is False
    assert memory_db.query(DeviceToken).filter(DeviceToken.id == "dt-good").first().is_active is True


# ===========================================================================
# 24. FCM Provider Failure Handled Gracefully
# ===========================================================================
@pytest.mark.asyncio
async def test_24_fcm_provider_failure_handled_gracefully(memory_db):
    user = create_test_user(memory_db, user_id="u-24")
    memory_db.add(SavedLocation(id="sl-24", user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-24", location_name="Chennai")

    mock_notifications = NotificationService()
    mock_notifications.send_push_notification = AsyncMock(side_effect=ConnectionResetError("FCM socket timeout"))

    engine = AlertEngine(notification_service=mock_notifications)
    results = await engine.process_alert_delivery(alert, memory_db)

    assert len(results) == 1
    assert results[0]["status"] == "FAILED"
    assert "FCM socket timeout" in results[0]["reason"]


# ===========================================================================
# 25. Alert Remains Available After Notification Failure
# ===========================================================================
@pytest.mark.asyncio
async def test_25_alert_remains_available_after_notification_failure(memory_db):
    user = create_test_user(memory_db, user_id="u-25")
    memory_db.add(SavedLocation(id="sl-25", user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-25", location_name="Chennai")

    mock_notifications = NotificationService()
    mock_notifications.send_push_notification = AsyncMock(return_value={
        "success": False,
        "error": "fcm_service_unavailable",
        "should_deactivate": False
    })

    engine = AlertEngine(notification_service=mock_notifications)
    results = await engine.process_alert_delivery(alert, memory_db)
    assert results[0]["status"] == "FAILED"

    # The DBAlert record MUST still exist and remain untouched
    persisted_alert = memory_db.query(DBAlert).filter(DBAlert.id == "a-25").first()
    assert persisted_alert is not None
    assert persisted_alert.severity == "high"
    assert persisted_alert.title == "Cyclone Alert"


# ===========================================================================
# 26. LLM Cannot Trigger Official Notification
# ===========================================================================
def test_26_llm_cannot_trigger_official_notification():
    llm_alert_payload = {
        "source": "OpenAI-GPT4",
        "title": "Severe Cyclone Warning Hallucinated by LLM",
        "alert_type": "cyclone",
        "severity": "extreme",
        "area": "Chennai",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
    }

    normalized, reason = normalize_and_validate_imd_alert(llm_alert_payload)
    assert normalized is None
    assert "Unauthorized alert source" in reason


# ===========================================================================
# 27. Secondary Provider Cannot Trigger Official Notification
# ===========================================================================
@pytest.mark.asyncio
async def test_27_secondary_provider_cannot_trigger_official_notification(memory_db):
    open_meteo_alert = create_test_alert(
        memory_db,
        alert_id="a-openmeteo",
        source="Open-Meteo",
        location_name="Chennai"
    )

    engine = AlertEngine()
    results = await engine.process_alert_delivery(open_meteo_alert, memory_db)

    assert len(results) == 1
    assert results[0]["status"] == "REJECTED"
    assert results[0]["reason"] == "unauthorized_source"


# ===========================================================================
# 28. DecisionTrace and Audit History Remain Consistent
# ===========================================================================
@pytest.mark.asyncio
async def test_28_decision_trace_and_audit_history_consistent(memory_db):
    user = create_test_user(memory_db, user_id="u-28")
    memory_db.add(SavedLocation(id="sl-28", user_id=user.id, name="Chennai", latitude=13.08, longitude=80.27))
    memory_db.commit()

    alert = create_test_alert(memory_db, alert_id="a-28", location_name="Chennai")

    engine = AlertEngine()
    await engine.process_alert_delivery(alert, memory_db)

    logs = memory_db.query(AlertDeliveryLog).filter(AlertDeliveryLog.alert_id == "a-28").all()
    assert len(logs) >= 1
    log = logs[0]

    assert log.alert_id == "a-28"
    assert log.user_id == user.id
    assert log.channel == "fcm"
    assert log.status == "SENT"
    assert log.reason == "eligible_in_affected_area"
    assert log.delivered_at is not None
    assert log.alert_fingerprint is not None
