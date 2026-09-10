"""Comprehensive Test Suite for SkyZen Phase 5: Firebase Cloud Messaging Infrastructure.
WeatherGPT-SIH26068 / MoES / IMD AI Weather Intelligence Platform.

Validates:
1. Token registration success
2. Duplicate token for same user updates timestamp and remains unique
3. Token reassignment when device switches users
4. Token deletion / deactivation
5. Unauthorized token registration rejection (401)
6. User isolation - User A cannot delete User B's token (403 Forbidden)
7. Token refresh lifecycle
8. User devices list isolation
9. Invalid token format rejection (422)
10. Controlled test notification dispatch (safe, restricted, auditable)
11. Controlled test notification unauthenticated rejection (401)
12. Controlled test notification cross-user target forbidden (403)
13. Firebase unavailable graceful fallback (mock delivery mode without crash)
14. FCM unregistered/expired token auto-deactivation
15. Android notification permission declaration (POST_NOTIFICATIONS)
"""

import os
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from backend.main import app
from backend.db.session import SessionLocal
from backend.db.models import User, DeviceToken, AlertDeliveryLog
from backend.services.notification_service import NotificationService

client = TestClient(app)


def _create_user_and_token(name: str = "Test User"):
    email = f"user_{uuid.uuid4().hex[:8]}@weathergpt.in"
    password = "SecurePassword123!"
    reg_res = client.post("/api/v1/auth/register", json={
        "name": name,
        "email": email,
        "password": password,
        "confirm_password": password
    })
    assert reg_res.status_code == 200, reg_res.text
    user_id = reg_res.json()["user_id"]

    login_res = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    return user_id, email, token


# =============================================================================
# 1. Token Registration
# =============================================================================
def test_01_token_registration_success():
    """1. Authenticated user registers an FCM device token."""
    user_id, email, auth_token = _create_user_and_token("Ravi Kumar")
    fcm_token = f"fcm_token_{uuid.uuid4().hex}_{uuid.uuid4().hex}"

    res = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "token": fcm_token,
            "platform": "android",
            "device_name": "Pixel 7 Pro"
        }
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["token"] == fcm_token
    assert data["platform"] == "android"
    assert data["device_name"] == "Pixel 7 Pro"
    assert data["is_active"] is True
    assert data["user_id"] == user_id


# =============================================================================
# 2. Duplicate Token (Same User)
# =============================================================================
def test_02_duplicate_token_same_user():
    """2. Registering duplicate token for same user updates timestamp and keeps single active record."""
    user_id, email, auth_token = _create_user_and_token("Sunita Rao")
    fcm_token = f"fcm_token_dup_{uuid.uuid4().hex}"

    # First registration
    res1 = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"token": fcm_token, "platform": "android", "device_name": "Galaxy S23"}
    )
    assert res1.status_code == 200
    id1 = res1.json()["id"]

    # Second registration with same token
    res2 = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"token": fcm_token, "platform": "android", "device_name": "Galaxy S23 Ultra"}
    )
    assert res2.status_code == 200
    id2 = res2.json()["id"]

    # Same ID updated
    assert id1 == id2
    assert res2.json()["device_name"] == "Galaxy S23 Ultra"

    # Verify only 1 record in database
    db = SessionLocal()
    try:
        count = db.query(DeviceToken).filter(DeviceToken.token == fcm_token).count()
        assert count == 1
    finally:
        db.close()


# =============================================================================
# 3. Token Reassignment (Device Transfer)
# =============================================================================
def test_03_token_reassignment_new_user():
    """3. If a physical device token is registered by User B after User A, ownership cleanly transfers to User B."""
    user_a_id, _, auth_token_a = _create_user_and_token("Alice A")
    user_b_id, _, auth_token_b = _create_user_and_token("Bob B")
    shared_device_token = f"shared_fcm_{uuid.uuid4().hex}"

    # User A registers device
    res_a = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token_a}"},
        json={"token": shared_device_token, "platform": "android"}
    )
    assert res_a.status_code == 200
    assert res_a.json()["user_id"] == user_a_id

    # User B logs in on same device and registers
    res_b = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token_b}"},
        json={"token": shared_device_token, "platform": "android"}
    )
    assert res_b.status_code == 200
    assert res_b.json()["user_id"] == user_b_id

    # Verify User A's devices list no longer has this token
    list_a = client.get("/api/v1/notifications/devices", headers={"Authorization": f"Bearer {auth_token_a}"}).json()
    assert not any(d["token"] == shared_device_token for d in list_a["devices"])


# =============================================================================
# 4. Token Deletion / Deactivation
# =============================================================================
def test_04_token_deletion_and_deactivation():
    """4. Authenticated user deletes device token; status becomes inactive."""
    user_id, email, auth_token = _create_user_and_token("Dev User")
    token_to_del = f"fcm_del_{uuid.uuid4().hex}"

    client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"token": token_to_del, "platform": "android"}
    )

    # Delete via DELETE /devices/{token}
    res_del = client.delete(
        f"/api/v1/notifications/devices/{token_to_del}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # Check that it no longer appears in active list
    list_res = client.get("/api/v1/notifications/devices", headers={"Authorization": f"Bearer {auth_token}"}).json()
    assert not any(d["token"] == token_to_del for d in list_res["devices"])

    # Verify DB flag is_active=False
    db = SessionLocal()
    try:
        rec = db.query(DeviceToken).filter(DeviceToken.token == token_to_del).first()
        assert rec is not None
        assert rec.is_active is False
    finally:
        db.close()


# =============================================================================
# 5. Unauthorized Token Registration Rejection
# =============================================================================
def test_05_unauthorized_token_registration():
    """5. Unauthenticated request (no JWT or invalid JWT) is rejected with 401."""
    # No auth header
    res1 = client.post("/api/v1/notifications/devices", json={"token": "valid_token_1234567890"})
    assert res1.status_code == 401

    # Invalid token
    res2 = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": "Bearer invalid.jwt.signature"},
        json={"token": "valid_token_1234567890"}
    )
    assert res2.status_code in [401, 403]


# =============================================================================
# 6. User Isolation (Cross-User Deletion Forbidden)
# =============================================================================
def test_06_user_isolation_cannot_delete_other_user_token():
    """6. User A cannot delete User B's device token (strictly rejected with 403 Forbidden)."""
    user_a_id, _, auth_token_a = _create_user_and_token("User A")
    user_b_id, _, auth_token_b = _create_user_and_token("User B")
    user_b_token = f"user_b_fcm_{uuid.uuid4().hex}"

    # User B registers token
    client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token_b}"},
        json={"token": user_b_token, "platform": "android"}
    )

    # User A attempts to delete User B's token
    res_attack = client.delete(
        f"/api/v1/notifications/devices/{user_b_token}",
        headers={"Authorization": f"Bearer {auth_token_a}"}
    )
    assert res_attack.status_code == 403
    assert "another user" in res_attack.json()["detail"].lower()

    # Verify User B's token remains completely active
    db = SessionLocal()
    try:
        rec = db.query(DeviceToken).filter(DeviceToken.token == user_b_token).first()
        assert rec is not None
        assert rec.is_active is True
        assert rec.user_id == user_b_id
    finally:
        db.close()


# =============================================================================
# 7. Token Refresh Lifecycle
# =============================================================================
def test_07_token_refresh_lifecycle():
    """7. Token refresh updates device metadata and timestamp cleanly."""
    user_id, email, auth_token = _create_user_and_token("Refreshed User")
    fcm_token = f"refresh_fcm_{uuid.uuid4().hex}"

    # Initial register
    r1 = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"token": fcm_token, "platform": "android", "device_name": "OnePlus 11"}
    ).json()

    # Re-register / refresh after token refresh event
    r2 = client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"token": fcm_token, "platform": "android", "device_name": "OnePlus 11 5G"}
    ).json()

    assert r1["id"] == r2["id"]
    assert r2["device_name"] == "OnePlus 11 5G"


# =============================================================================
# 8. User Devices List Isolation
# =============================================================================
def test_08_list_devices_isolation():
    """8. User A only sees their own active devices; User B's devices are completely hidden."""
    _, _, auth_token_a = _create_user_and_token("Owner A")
    _, _, auth_token_b = _create_user_and_token("Owner B")

    tok_a = f"token_a_{uuid.uuid4().hex}"
    tok_b = f"token_b_{uuid.uuid4().hex}"

    client.post("/api/v1/notifications/devices", headers={"Authorization": f"Bearer {auth_token_a}"}, json={"token": tok_a})
    client.post("/api/v1/notifications/devices", headers={"Authorization": f"Bearer {auth_token_b}"}, json={"token": tok_b})

    list_a = client.get("/api/v1/notifications/devices", headers={"Authorization": f"Bearer {auth_token_a}"}).json()
    assert list_a["total_count"] == 1
    assert list_a["devices"][0]["token"] == tok_a
    assert not any(d["token"] == tok_b for d in list_a["devices"])


# =============================================================================
# 9. Invalid Token Format Rejection
# =============================================================================
def test_09_invalid_token_format_rejection():
    """9. Malformed tokens (empty, whitespace, too short, invalid chars) are rejected with 422."""
    _, _, auth_token = _create_user_and_token("Validation User")

    # Empty token
    res1 = client.post("/api/v1/notifications/devices", headers={"Authorization": f"Bearer {auth_token}"}, json={"token": ""})
    assert res1.status_code == 422

    # Too short
    res2 = client.post("/api/v1/notifications/devices", headers={"Authorization": f"Bearer {auth_token}"}, json={"token": "12345"})
    assert res2.status_code == 422

    # Injection characters
    res3 = client.post("/api/v1/notifications/devices", headers={"Authorization": f"Bearer {auth_token}"}, json={"token": "<script>alert(1)</script>"})
    assert res3.status_code == 422

    # Unsupported platform
    res4 = client.post("/api/v1/notifications/devices", headers={"Authorization": f"Bearer {auth_token}"}, json={"token": "valid_token_1234567890", "platform": "blackberry"})
    assert res4.status_code == 422


# =============================================================================
# 10. Controlled Test Notification
# =============================================================================
def test_10_controlled_test_notification():
    """10. Controlled test notification sends safely, auditable in AlertDeliveryLog, without sending real IMD alert."""
    user_id, email, auth_token = _create_user_and_token("Test Runner")
    fcm_tok = f"test_run_fcm_{uuid.uuid4().hex}"

    # Register device
    client.post("/api/v1/notifications/devices", headers={"Authorization": f"Bearer {auth_token}"}, json={"token": fcm_tok})

    # Dispatch test notification
    res = client.post(
        "/api/v1/notifications/test",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Cyclone Preparedness Test",
            "body": "System test alert message."
        }
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["dispatched_count"] == 1
    assert data["mode"] in ["live_fcm", "mock_delivery"]

    # Verify audit trail in AlertDeliveryLog
    db = SessionLocal()
    try:
        logs = db.query(AlertDeliveryLog).filter(
            AlertDeliveryLog.user_id == user_id,
            AlertDeliveryLog.channel == "test_fcm"
        ).all()
        assert len(logs) >= 1
        assert logs[-1].reason == "user_initiated_test"
        assert logs[-1].alert_fingerprint == "controlled_test_fcm"
    finally:
        db.close()


# =============================================================================
# 11. Controlled Test Notification Unauthorized
# =============================================================================
def test_11_controlled_test_notification_unauthorized():
    """11. Unauthenticated users cannot trigger test notifications (401)."""
    res = client.post("/api/v1/notifications/test", json={"title": "Unauthorized Test"})
    assert res.status_code == 401


# =============================================================================
# 12. Controlled Test Notification Cross-User Forbidden
# =============================================================================
def test_12_controlled_test_notification_cross_user_forbidden():
    """12. User A cannot target User B's device token in test notification (403)."""
    _, _, auth_token_a = _create_user_and_token("Test User A")
    _, _, auth_token_b = _create_user_and_token("Test User B")

    tok_b = f"tok_b_{uuid.uuid4().hex}"
    client.post("/api/v1/notifications/devices", headers={"Authorization": f"Bearer {auth_token_b}"}, json={"token": tok_b})

    # User A tries to send test notification targeting User B's token
    res = client.post(
        "/api/v1/notifications/test",
        headers={"Authorization": f"Bearer {auth_token_a}"},
        json={"title": "Exploit", "device_token": tok_b}
    )
    assert res.status_code == 403


# =============================================================================
# 13. Firebase Unavailable Fallback
# =============================================================================
@pytest.mark.asyncio
async def test_13_fcm_unavailable_fallback():
    """13. NotificationService gracefully falls back to mock delivery mode when Firebase Admin SDK is unconfigured."""
    notif = NotificationService(fcm_server_key="")
    # Explicitly verify that without live credentials, it never raises an unhandled exception
    res = await notif.send_push_notification(
        token="simulated_token_1234567890",
        title="Test Alert",
        body="Simulated meteorological bulletin."
    )
    assert res["success"] is True
    assert res["mode"] == "mock_delivery"
    assert "mock_fcm_" in res["message_id"]


# =============================================================================
# 14. FCM Unregistered/Expired Token Deactivation
# =============================================================================
@pytest.mark.asyncio
async def test_14_fcm_unregistered_token_deactivation():
    """14. When FCM reports token as unregistered / expired, token is marked inactive."""
    user_id, email, auth_token = _create_user_and_token("Expired Device User")
    bad_token = f"bad_token_{uuid.uuid4().hex}"

    # Register bad token
    client.post(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"token": bad_token, "platform": "android"}
    )

    # Mock send_multicast to simulate FCM UnregisteredError
    with patch.object(
        NotificationService,
        "send_multicast",
        return_value={
            "success": False,
            "dispatched_count": 1,
            "success_count": 0,
            "failure_count": 1,
            "unregistered_tokens": [bad_token],
            "delivery_results": [{"token": bad_token, "success": False, "error": "Requested entity was not found (Unregistered)"}],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    ):
        res = client.post(
            "/api/v1/notifications/test",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"device_token": bad_token}
        )
        assert res.status_code == 200

    # Verify bad token was automatically marked is_active=False in DB
    db = SessionLocal()
    try:
        dev = db.query(DeviceToken).filter(DeviceToken.token == bad_token).first()
        assert dev is not None
        assert dev.is_active is False
    finally:
        db.close()


# =============================================================================
# 15. Android Notification Permission Declaration
# =============================================================================
def test_15_android_notification_permission_declared():
    """15. AndroidManifest.xml declares POST_NOTIFICATIONS for Android 13+ support."""
    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "android", "app", "src", "main", "AndroidManifest.xml"
    )
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "android.permission.POST_NOTIFICATIONS" in content
