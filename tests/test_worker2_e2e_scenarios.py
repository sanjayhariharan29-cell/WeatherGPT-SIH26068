"""Worker 2 Full End-to-End Regression & Release QA Test Suite.

Validates all 15 critical production scenarios:
1. Normal weather request.
2. Source disagreement.
3. IMD warning active.
4. Expired IMD warning.
5. User in affected area.
6. User outside affected area.
7. Notification disabled.
8. FCM unavailable.
9. Backend unavailable.
10. App offline resilience.
11. App closed notification payload compatibility.
12. Android notification permissions.
13. Multilingual alert formatting (ta, en, hi).
14. No hallucinated warning.
15. No warning severity modification.
"""

import os
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.session import SessionLocal, Base, engine
from backend.db.models import (
    User,
    UserPreference,
    SavedLocation,
    Alert as DBAlert,
    AlertDeliveryLog
)
from backend.services.alert_engine import AlertEngine
from backend.services.alert_service import AlertService
from backend.services.notification_service import NotificationService
from backend.services.imd_adapter import IMDAdapter
from backend.services.current_weather_service import CurrentWeatherService
from backend.services.schemas import NormalizedAlertItem, NormalizedWeatherObservation
from backend.services.exceptions import ProviderUnavailableError
from backend.core.security import hash_password

client = TestClient(app)


@pytest.fixture(scope="module")
def e2e_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


# =============================================================================
# SCENARIO 1: Normal weather request
# =============================================================================
def test_scenario_01_normal_weather_request():
    """1. Normal weather request returns structured schema with official provenance."""
    resp = client.get("/api/v1/weather/current?location=Coimbatore")
    assert resp.status_code == 200

    data = resp.json()
    assert data["location"]["name"] == "Coimbatore"
    assert "weather" in data
    assert data["weather"]["temperature"] is not None
    assert data["weather"]["humidity"] is not None
    assert "comparison" in data
    assert "source" in data
    assert "IMD" in data["source"]
    assert data["data_freshness"] == "FRESH"


# =============================================================================
# SCENARIO 2: Source disagreement
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_02_source_disagreement():
    """2. Source disagreement lowers confidence and documents discrepancy."""
    service = CurrentWeatherService()
    now_utc = datetime.now(timezone.utc).isoformat()

    # IMD primary reports 24°C, 95% rain
    service.primary.get_current_weather = AsyncMock(return_value=NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=24.0,
        humidity_pct=90.0,
        rain_probability_pct=95.0,
        wind_speed_kmh=20.0,
        rainfall_mm=30.0,
        condition="Heavy Rain",
        source="IMD",
        authority_level="primary_authoritative",
        observed_at=now_utc,
        retrieved_at=now_utc
    ))

    # Open-Meteo secondary reports 35°C, 10% rain (divergence > 4°C and > 20% rain)
    service.secondary.get_current_weather = AsyncMock(return_value=NormalizedWeatherObservation(
        location_name="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        temperature_c=35.0,
        humidity_pct=40.0,
        rain_probability_pct=10.0,
        wind_speed_kmh=10.0,
        rainfall_mm=0.0,
        condition="Sunny",
        source="Open-Meteo",
        authority_level="secondary_verification",
        observed_at=now_utc,
        retrieved_at=now_utc
    ))

    res = await service.fetch_current_weather(location_name="Coimbatore")
    assert res.comparison.sources_agree is False
    assert res.comparison.confidence_level == "CAUTIOUS"
    assert "High variance between providers" in res.comparison.disagreement_notes
    assert "Prioritizing authoritative IMD" in res.comparison.disagreement_notes


# =============================================================================
# SCENARIO 3: IMD warning active
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_03_imd_warning_active():
    """3. Active IMD warning has valid expiration window and active status."""
    service = AlertService()
    res = await service.fetch_alerts(location_name="Nagapattinam", active_only=True)

    assert res.active_count >= 1
    assert len(res.alerts) >= 1
    hero = res.alerts[0]
    assert hero.is_official is True
    assert hero.is_active is True
    assert hero.source == "IMD"
    assert "Nagapattinam" in hero.area


# =============================================================================
# SCENARIO 4: Expired IMD warning
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_04_expired_imd_warning():
    """4. Expired warning is NEVER presented as active."""
    adapter = IMDAdapter()
    engine = AlertEngine(imd_adapter=adapter)

    # 1. Past expiration timestamp
    now = datetime.now(timezone.utc)
    iss_dt = (now - timedelta(days=2)).isoformat()
    exp_dt = (now - timedelta(hours=2)).isoformat()

    assert engine.is_alert_active(iss_dt, exp_dt) is False

    # 2. Fetching with expired alert returns active_count == 0 when active_only=True
    service = AlertService()
    service.primary.get_official_alerts = AsyncMock(return_value=[
        NormalizedAlertItem(
            alert_type="heatwave_warning",
            severity="medium",
            title="IMD Expired Heatwave Notice",
            description="Historic heatwave advisory now expired.",
            area="Salem District",
            source="IMD",
            issued_at=(now - timedelta(days=2)).isoformat(),
            expires_at=(now - timedelta(hours=2)).isoformat(),
            retrieved_at=now.isoformat()
        )
    ])
    res = await service.fetch_alerts(location_name="Salem", active_only=True)
    assert res.active_count == 0
    assert len(res.alerts) == 0

    # When active_only=False, expired alert can be audited but marked is_active=False
    res_all = await service.fetch_alerts(location_name="Salem", active_only=False)
    assert len(res_all.alerts) == 1
    assert res_all.alerts[0].is_active is False



# =============================================================================
# SCENARIO 5: User in affected area
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_05_user_in_affected_area(e2e_db):
    """5. User located in affected region receives targeted notification."""
    engine = AlertEngine()

    # Create test user in Nagapattinam
    user_naga = User(
        name="Kavitha Naga",
        email=f"kavitha_{uuid.uuid4().hex[:8]}@skyzen.moes.gov.in",
        password_hash=hash_password("Pass123!"),
        language="ta"
    )
    e2e_db.add(user_naga)
    e2e_db.commit()

    pref = UserPreference(user_id=user_naga.id, notification_enabled=True)
    loc = SavedLocation(user_id=user_naga.id, name="Nagapattinam Port", latitude=10.76, longitude=79.84)
    e2e_db.add(pref)
    e2e_db.add(loc)
    e2e_db.commit()

    # Create official alert for Nagapattinam
    alert = DBAlert(
        location_name="Nagapattinam Coastal Zone",
        latitude=10.76,
        longitude=79.84,
        alert_type="cyclone_surge",
        severity="high",
        title="Cyclone Storm Warning",
        description="Squally winds reaching 85 kmph expected.",
        source="IMD",
        issued_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    e2e_db.add(alert)
    e2e_db.commit()

    results = await engine.process_alert_delivery(alert, e2e_db)
    user_results = [r for r in results if r["user_id"] == user_naga.id]

    assert len(user_results) == 1
    assert user_results[0]["status"] == "SENT"
    assert user_results[0]["reason"] == "eligible_in_affected_area"


# =============================================================================
# SCENARIO 6: User outside affected area
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_06_user_outside_affected_area(e2e_db):
    """6. User outside affected area is NOT broadcasted to (status: SKIPPED out_of_area)."""
    engine = AlertEngine()

    # Create test user in Coimbatore
    user_cbe = User(
        name="Ramesh Coimbatore",
        email=f"ramesh_{uuid.uuid4().hex[:8]}@skyzen.moes.gov.in",
        password_hash=hash_password("Pass123!"),
        language="en"
    )
    e2e_db.add(user_cbe)
    e2e_db.commit()

    pref = UserPreference(user_id=user_cbe.id, notification_enabled=True)
    loc = SavedLocation(user_id=user_cbe.id, name="Coimbatore North", latitude=11.01, longitude=76.95)
    e2e_db.add(pref)
    e2e_db.add(loc)
    e2e_db.commit()

    # Create Nagapattinam coastal alert
    alert = DBAlert(
        location_name="Nagapattinam Coastal Zone",
        latitude=10.76,
        longitude=79.84,
        alert_type="marine_gale",
        severity="high",
        title="High Seas Marine Advisory",
        description="Rough sea conditions for fishermen.",
        source="IMD",
        issued_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=18)
    )
    e2e_db.add(alert)
    e2e_db.commit()

    results = await engine.process_alert_delivery(alert, e2e_db)
    user_results = [r for r in results if r["user_id"] == user_cbe.id]

    assert len(user_results) == 1
    assert user_results[0]["status"] == "SKIPPED"
    assert user_results[0]["reason"] == "out_of_area"


# =============================================================================
# SCENARIO 7: Notification disabled
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_07_notification_disabled(e2e_db):
    """7. User in affected area with notifications disabled is skipped."""
    engine = AlertEngine()

    user_optout = User(
        name="Priya OptOut",
        email=f"priya_{uuid.uuid4().hex[:8]}@skyzen.moes.gov.in",
        password_hash=hash_password("Pass123!"),
        language="ta"
    )
    e2e_db.add(user_optout)
    e2e_db.commit()

    # notification_enabled = False
    pref = UserPreference(user_id=user_optout.id, notification_enabled=False)
    loc = SavedLocation(user_id=user_optout.id, name="Nagapattinam", latitude=10.76, longitude=79.84)
    e2e_db.add(pref)
    e2e_db.add(loc)
    e2e_db.commit()

    alert = DBAlert(
        location_name="Nagapattinam Coastal Zone",
        latitude=10.76,
        longitude=79.84,
        alert_type="flood_warning",
        severity="high",
        title="Riverine Flood Alert",
        description="Cauvery delta water discharge rising.",
        source="IMD",
        issued_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    e2e_db.add(alert)
    e2e_db.commit()

    results = await engine.process_alert_delivery(alert, e2e_db)
    user_results = [r for r in results if r["user_id"] == user_optout.id]

    assert len(user_results) == 1
    assert user_results[0]["status"] == "SKIPPED"
    assert user_results[0]["reason"] == "notification_disabled"


# =============================================================================
# SCENARIO 8: FCM unavailable
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_08_fcm_unavailable():
    """8. When FCM is unavailable, system gracefully logs mock delivery without crashing."""
    notif = NotificationService(fcm_server_key="")
    res = await notif.send_push_notification(
        token=None,
        title="Test Alert",
        body="Emergency alert simulated."
    )
    assert res["success"] is True
    assert res["mode"] == "mock_delivery"
    assert "mock_fcm_" in res["message_id"]


# =============================================================================
# SCENARIO 9: Backend unavailable
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_09_backend_unavailable():
    """9. Provider outage returns degraded UNVERIFIED state without crashing."""
    service = AlertService()
    service.primary.get_official_alerts = AsyncMock(side_effect=ProviderUnavailableError("IMD Gateway 503"))

    res = await service.fetch_alerts(location_name="Coimbatore")
    assert res.status == "UNVERIFIED"
    assert "Degraded" in res.source
    assert res.active_count == 0


# =============================================================================
# SCENARIO 10: App offline resilience
# =============================================================================
def test_scenario_10_app_offline():
    """10. Frontend shell and service worker cache offline assets safely."""
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "NETWORK_OFFLINE" in resp.text


# =============================================================================
# SCENARIO 11: App closed notification compatibility
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_11_app_closed_notification_payload():
    """11. Notification payload contains priority and data keys for app-closed tray display."""
    notif = NotificationService()
    msg = notif.format_alert_message(
        title="Severe Cyclone Notice",
        description="Landfall expected near Cuddalore.",
        severity="extreme",
        language="en"
    )
    res = await notif.send_push_notification(
        token=None,
        title=msg["title"],
        body=msg["body"],
        data={"priority": "high", "alert_type": "cyclone", "click_action": "OPEN_ALERT"}
    )
    payload = res.get("payload", {})
    assert "title" in payload
    assert "body" in payload
    assert payload["data"]["priority"] == "high"


# =============================================================================
# SCENARIO 12: Android notification permission
# =============================================================================
def test_scenario_12_android_notification_permission():
    """12. AndroidManifest.xml declares POST_NOTIFICATIONS for Android 13+ support."""
    manifest_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "android", "app", "src", "main", "AndroidManifest.xml")
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "android.permission.POST_NOTIFICATIONS" in content


# =============================================================================
# SCENARIO 13: Multilingual alert
# =============================================================================
def test_scenario_13_multilingual_alert():
    """13. Notifications format accurately in Tamil, Hindi, and English."""
    notif = NotificationService()

    # Tamil
    msg_ta = notif.format_alert_message("கனமழை எச்சரிக்கை", "அடுத்த 24 மணி நேரத்திற்கு கனமழை பெய்யும்.", "high", "ta")
    assert "அதிகாரப்பூர்வ வானிலை எச்சரிக்கை" in msg_ta["title"]
    assert msg_ta["language"] == "ta"

    # Hindi
    msg_hi = notif.format_alert_message("भारी बारिश की चेतावनी", "अगले 24 घंटों में भारी बारिश होगी।", "high", "hi")
    assert "आधिकारिक मौसम चेतावनी" in msg_hi["title"]
    assert msg_hi["language"] == "hi"

    # English
    msg_en = notif.format_alert_message("Heavy Rainfall Alert", "Heavy rain expected over coastal belt.", "high", "en")
    assert "IMD Official Warning" in msg_en["title"]
    assert msg_en["language"] == "en"


# =============================================================================
# SCENARIO 14: No hallucinated warning
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_14_no_hallucinated_warning():
    """14. System never hallucinates or invents disaster warnings for safe weather locations."""
    service = AlertService()
    # Query location with no warnings (e.g. Ooty / Madurai / Non-warning city)
    res = await service.fetch_alerts(location_name="Madurai", active_only=True)
    assert res.active_count == 0
    assert len(res.alerts) == 0


# =============================================================================
# SCENARIO 15: No warning severity modification
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_15_no_warning_severity_modification():
    """15. Official IMD severity is never altered or downgraded."""
    service = AlertService()
    res = await service.fetch_alerts(location_name="Nagapattinam", active_only=True)
    assert len(res.alerts) >= 1
    alert = res.alerts[0]
    # Official IMD warning is High — cannot be downgraded
    assert alert.severity == "high"
    assert alert.is_official is True
    assert alert.source == "IMD"
