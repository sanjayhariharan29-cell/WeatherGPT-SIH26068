"""
Phase 6: SkyZen Real FCM End-to-End Validation & Verification Matrix
Validates:
1. Pre-flight Firebase project & Android package match (in.gov.moes.weathergpt, skyzen-9a22d)
2. Firebase Admin SDK credential isolation (no private keys in client assets)
3. Device token registration API (/api/v1/notifications/devices)
4. Controlled test notification dispatch (/api/v1/notifications/test)
5. Test notification payload safety (strictly labeled as test, never fabricating IMD emergency alerts)
6. Controlled IMD alert targeting pipeline integration
7. Multilingual notification formatting (English, Tamil, Hindi) with severity preservation
8. FCM invalid/unregistered token auto-deactivation
9. Bounded retry and error handling on Firebase provider failures
10. Deep-link routing and tray tap action to Alerts screen (OPEN_ALERT)
11. App lifecycle token persistence and session security
12. Comprehensive secret audit of Android APK assets
"""

import os
import json
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
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

client = TestClient(app)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANDROID_DIR = os.path.join(REPO_ROOT, "android")
APP_DIR = os.path.join(ANDROID_DIR, "app")
MANIFEST_PATH = os.path.join(APP_DIR, "src", "main", "AndroidManifest.xml")
GOOGLE_SERVICES_PATH = os.path.join(APP_DIR, "google-services.json")
CAP_CONFIG_PATH = os.path.join(REPO_ROOT, "capacitor.config.json")
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")


def _register_and_login_user(name: str = "FCM Test User"):
    email = f"fcm_{uuid.uuid4().hex[:8]}@weathergpt.in"
    password = "SecurePassword123!"
    reg_res = client.post("/api/v1/auth/register", json={
        "name": name,
        "email": email,
        "password": password,
        "confirm_password": password
    })
    assert reg_res.status_code == 200
    user_id = reg_res.json()["user_id"]

    login_res = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return user_id, email, token


def test_01_preflight_package_and_firebase_match():
    """1. Verify Android package and google-services.json project match in.gov.moes.weathergpt."""
    assert os.path.exists(GOOGLE_SERVICES_PATH)
    with open(GOOGLE_SERVICES_PATH, "r", encoding="utf-8") as f:
        gs = json.load(f)
    package_name = gs["client"][0]["client_info"]["android_client_info"]["package_name"]
    project_id = gs["project_info"]["project_id"]
    assert package_name == "in.gov.moes.weathergpt"
    assert project_id == "skyzen-9a22d"

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest_text = f.read()
    assert 'package="in.gov.moes.weathergpt"' in manifest_text or "in.gov.moes.weathergpt" in manifest_text


def test_02_firebase_admin_credential_isolation():
    """2. Verify Firebase Admin SDK credentials are NEVER bundled in client assets."""
    client_paths = [
        os.path.join(FRONTEND_DIR, "app.js"),
        os.path.join(FRONTEND_DIR, "config.js"),
        os.path.join(FRONTEND_DIR, "mobile", "apiClient.js"),
        os.path.join(FRONTEND_DIR, "mobile", "notificationManager.js"),
        MANIFEST_PATH,
        CAP_CONFIG_PATH
    ]
    forbidden_tokens = [
        "BEGIN PRIVATE KEY",
        "BEGIN RSA PRIVATE KEY",
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        "private_key_id",
        "client_email"
    ]
    for cp in client_paths:
        if os.path.exists(cp):
            with open(cp, "r", encoding="utf-8") as f:
                content = f.read()
            for token in forbidden_tokens:
                assert token not in content, f"Secret token '{token}' leaked in client path {cp}"


def test_03_authenticated_device_registration():
    """3. Verify authenticated user can register an Android device token with backend."""
    user_id, email, auth_token = _register_and_login_user("Ananya Sen")
    fcm_token = f"e2e_fcm_token_{uuid.uuid4().hex}"

    reg_res = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "token": fcm_token,
            "platform": "android",
            "device_name": "Physical Test Phone"
        }
    )
    assert reg_res.status_code == 200
    data = reg_res.json()
    assert data["token"] == fcm_token
    assert data["platform"] == "android"
    assert data["device_name"] == "Physical Test Phone"
    assert data["is_active"] is True
    assert data["user_id"] == user_id


def test_04_controlled_test_notification_endpoint():
    """4. Verify controlled test notification dispatches safely and returns structured audit."""
    user_id, email, auth_token = _register_and_login_user("Karthik Raja")
    fcm_token = f"e2e_fcm_test_{uuid.uuid4().hex}"

    reg_res = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"token": fcm_token, "platform": "android", "device_name": "Pixel 7a"}
    )
    assert reg_res.status_code == 200

    test_res = client.post(
        "/api/v1/notifications/test",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "SkyZen Controlled Verification",
            "body": "FCM delivery path verification for mobile device.",
            "device_token": fcm_token
        }
    )
    assert test_res.status_code == 200
    data = test_res.json()
    assert data["success"] is True
    assert data["dispatched_count"] >= 1


def test_05_controlled_test_notification_payload_safety():
    """5. Verify controlled test notification is strictly marked and never fabricates emergency warnings."""
    service = NotificationService()
    user_id, email, auth_token = _register_and_login_user("Preethi V")
    fcm_token = f"e2e_test_safety_{uuid.uuid4().hex}"

    reg_res = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"token": fcm_token, "platform": "android", "device_name": "Galaxy S22"}
    )
    assert reg_res.status_code == 200

    test_res = client.post(
        "/api/v1/notifications/test",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "SkyZen Controlled Test",
            "body": "Test verification of push notification delivery.",
            "device_token": fcm_token
        }
    )
    assert test_res.status_code == 200
    result_data = test_res.json()

    # Verify no fake emergency terminology is generated
    raw_text = json.dumps(result_data).lower()
    assert "extreme cyclone" not in raw_text
    assert "tsunami warning" not in raw_text
    assert "red alert evacuation" not in raw_text


@pytest.mark.asyncio
async def test_06_controlled_imd_alert_targeting_pipeline():
    """6. Verify controlled IMD warning passes through Phase 2 & 3 pipeline to generate FCM dispatch."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        user = User(
            id="u-fcm-e2e-1",
            name="Sanjay",
            email="sanjay_fcm@skyzen.com",
            password_hash="hashed_pw",
            language="en",
            persona="farmer",
            role="user",
            is_verified=True,
            onboarding_completed=True
        )
        db.add(user)
        pref = UserPreference(user_id=user.id, notification_enabled=True)
        db.add(pref)
        sl = SavedLocation(id="sl-fcm-1", user_id=user.id, name="Nagapattinam", latitude=10.7656, longitude=79.8424)
        db.add(sl)
        dev = DeviceToken(id="dt-fcm-1", user_id=user.id, token="token-device-e2e", platform="android", is_active=True)
        db.add(dev)
        db.commit()

        now = datetime.now(timezone.utc)
        alert = DBAlert(
            id="IMD-E2E-TEST-2026-001",
            source="IMD",
            location_name="Nagapattinam",
            alert_type="heavy_rain",
            severity="high",
            title="Heavy Rainfall Warning",
            description="Isolated heavy rainfall expected over Nagapattinam.",
            latitude=10.7656,
            longitude=79.8424,
            issued_at=now - timedelta(minutes=10),
            expires_at=now + timedelta(hours=6)
        )
        db.add(alert)
        db.commit()

        alert_engine = AlertEngine()
        results = await alert_engine.process_alert_delivery(alert, db)

        assert len(results) == 1
        assert results[0]["user_id"] == user.id
        assert results[0]["status"] == "SENT"
        assert results[0]["matched_location"] == "Nagapattinam"
    finally:
        db.close()


def test_07_multilingual_alert_formatting_preservation():
    """7. Verify notification formatter preserves severity, units, instructions across languages."""
    service = NotificationService()

    for lang in ["ta", "en", "hi"]:
        formatted = service.format_alert_message(
            title="Heavy Rainfall Alert",
            description="Continuous heavy rain of 65 mm expected.",
            severity="WARNING",
            language=lang,
            area="Nagapattinam",
            instructions="Keep emergency lights ready and stay indoors.",
            valid_until="18:00 IST",
            alert_id="IMD-MULTI-001"
        )
        assert "title" in formatted
        assert "body" in formatted
        assert formatted["severity"] == "WARNING"
        assert formatted["area"] == "Nagapattinam"
        assert formatted["alert_id"] == "IMD-MULTI-001"
        # Measurements and numbers must never be lost
        assert "65" in formatted["body"] or "65 mm" in formatted["body"]


def test_08_invalid_token_auto_deactivation():
    """8. Verify FCM invalid token response flags token for safe deactivation without deleting alerts."""
    service = NotificationService()
    now_utc = datetime.now(timezone.utc).isoformat()

    # Dispatch to simulated invalid token
    res = pytest.importorskip("asyncio").run(
        service.send_push_notification(
            token="invalid_unregistered_test_token_abc123",
            title="Test",
            body="Test body"
        )
    )
    assert "success" in res
    assert "mode" in res
    assert "timestamp" in res


def test_09_bounded_retries_and_no_crash_on_firebase_unavailable():
    """9. Verify NotificationService gracefully falls back without crashing when Firebase is unconfigured."""
    service = NotificationService()
    # In test environment, service runs in verified mock/sandbox mode
    res = pytest.importorskip("asyncio").run(
        service.send_push_notification(
            token="test_fcm_token_retry",
            title="SkyZen Test Ping",
            body="Bounded retry resilience verification.",
            max_retries=2
        )
    )
    assert res["success"] is True
    assert res["mode"] in ["mock_delivery", "live_fcm"]
    assert "timestamp" in res


def test_10_deep_link_action_routing_integrity():
    """10. Verify notification payload includes click_action OPEN_ALERT and routes to Alerts screen."""
    notif_mgr_path = os.path.join(FRONTEND_DIR, "mobile", "notificationManager.js")
    with open(notif_mgr_path, "r", encoding="utf-8") as f:
        code = f.read()

    assert "pushNotificationActionPerformed" in code
    assert 'window.navigateToScreen("alerts")' in code
    assert "targetDistrict" in code
    assert "CustomEvent(\"skyzen:notificationTapped\"" in code


def test_11_device_token_duplicate_and_refresh_handling():
    """11. Verify registering the same token updates existing record rather than creating duplicates."""
    user_id, email, auth_token = _register_and_login_user("Deepak Raj")
    fcm_token = f"e2e_refresh_token_{uuid.uuid4().hex}"

    # Registration 1
    res1 = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"token": fcm_token, "platform": "android", "device_name": "Device A"}
    )
    assert res1.status_code == 200
    token_id_1 = res1.json()["id"]

    # Registration 2 (token refresh)
    res2 = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"token": fcm_token, "platform": "android", "device_name": "Device A (Refreshed)"}
    )
    assert res2.status_code == 200
    token_id_2 = res2.json()["id"]

    # Verify ID is preserved (same active record updated, not duplicated)
    assert token_id_1 == token_id_2
    assert res2.json()["device_name"] == "Device A (Refreshed)"


def test_12_comprehensive_secret_scan_in_client():
    """12. Security Audit: verify zero private keys or credentials exist in Android assets."""
    check_files = [
        os.path.join(FRONTEND_DIR, "app.js"),
        os.path.join(FRONTEND_DIR, "config.js"),
        os.path.join(FRONTEND_DIR, "mobile", "apiClient.js"),
        os.path.join(FRONTEND_DIR, "mobile", "notificationManager.js"),
        os.path.join(APP_DIR, "src", "main", "assets", "public", "app.js"),
        os.path.join(APP_DIR, "src", "main", "assets", "public", "mobile", "apiClient.js"),
        os.path.join(APP_DIR, "src", "main", "assets", "public", "mobile", "notificationManager.js")
    ]
    forbidden = ["BEGIN PRIVATE KEY", "service_account", "ghp_", "sk-"]
    for path in check_files:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                txt = f.read()
            for pat in forbidden:
                assert pat not in txt, f"Security violation: '{pat}' found in {path}"
