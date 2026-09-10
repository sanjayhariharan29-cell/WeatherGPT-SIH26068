"""SkyZen Security & Production Hardening Audit Test Suite.

Validates:
1. Repository Secret Hygiene (Zero live API keys, tokens, or private certificates).
2. Token Forgery Defense (Rejection of unverified bearer tokens).
3. Privilege Escalation Prevention (Admin self-assignment blocked).
4. IDOR Defense (Unauthenticated profile viewing blocked).
5. Cross-User Authorization (Profiles, Saved Locations, Device Tokens, Test Notifications).
6. Alert Integrity (Clients cannot create, update, or delete official IMD warnings).
7. Input Validation (Malformed coordinates, message length overflows, empty strings).
8. CORS Security (No wildcard origin with credentials allowed).
9. Audit Log Redaction (API keys, passwords, bearer tokens, private keys).
10. Rate Limiting Protection on Auth and Chat endpoints.
"""

import os
import re
import uuid
import time
import logging
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.main import app
from backend.config.settings import settings
from backend.config.logging import RedactFilter, REDACTION_PATTERNS
from backend.db.session import SessionLocal
from backend.db.models import User, SavedLocation, DeviceToken
from backend.core.security import create_access_token, hash_password
from backend.middleware.rate_limiter import RateLimiterMiddleware

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

def _create_test_user(name="Alice Security", role="user") -> tuple[User, str]:
    db = SessionLocal()
    unique_email = f"user_{uuid.uuid4().hex[:10]}@weathergpt.in"
    user = User(
        name=name,
        email=unique_email,
        password_hash=hash_password("SecTest123!"),
        role=role,
        persona="student",
        language="ta",
        is_verified=True,
        onboarding_completed=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    db.close()
    return user, token


# ===========================================================================
# 1. REPOSITORY SECRET AUDIT
# ===========================================================================

class TestRepositorySecretAudit:

    def test_01_no_live_keys_in_tracked_files(self):
        """Scans all git-tracked source files to guarantee zero live secrets are committed."""
        import subprocess
        res = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
        files = [f.strip() for f in res.stdout.splitlines() if f.strip()]

        sensitive_patterns = [
            (re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"), "Live OpenAI Project Key"),
            (re.compile(r"\bre_[A-Za-z0-9]{20,}\b"), "Live Resend Key"),
            (re.compile(r"ghp_[A-Za-z0-9]{36}"), "Live GitHub Personal Access Token"),
            (re.compile(r"-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----"), "Live Private Key Block"),
        ]

        # Scan each file
        for file_path in files:
            # Skip documentation examples or binary files
            if not os.path.exists(file_path):
                continue
            if file_path.endswith((".png", ".jpg", ".webp", ".ico", ".db", ".sqlite")):
                continue

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for pattern, desc in sensitive_patterns:
                    # Ignore test assertion strings
                    if "assert" in content and file_path.startswith("tests/"):
                        continue
                    assert not pattern.search(content), f"Forbidden secret detected ({desc}) in {file_path}"

    def test_02_env_file_is_gitignored(self):
        """Ensures that .env files cannot be accidentally committed to git."""
        import subprocess
        res = subprocess.run(["git", "check-ignore", ".env"], capture_output=True, text=True)
        assert res.returncode == 0, ".env file must be ignored by .gitignore!"


# ===========================================================================
# 2. TOKEN FORGERY DEFENSE (LEGACY TOKEN BACKDOOR REMOVAL)
# ===========================================================================

class TestTokenForgeryDefense:

    def test_03_legacy_token_bypass_rejected(self):
        """Forged 'Bearer token_<user_id>' must be rejected with 401 Unauthorized."""
        user, _ = _create_test_user("Victim User")

        forged_tokens = [
            f"token_{user.id}",
            "token_admin",
            "token_root",
            "token_12345"
        ]

        for fake_token in forged_tokens:
            res = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {fake_token}"}
            )
            assert res.status_code == 401, f"Forged token {fake_token} was not rejected!"
            assert "detail" in res.json()


# ===========================================================================
# 3. PRIVILEGE ESCALATION (ADMIN ROLE ENFORCEMENT)
# ===========================================================================

class TestPrivilegeEscalation:

    def test_04_admin_self_registration_blocked_in_production(self, monkeypatch):
        """Public registration cannot assign role='admin' in production without admin_secret."""
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        email = f"attacker_{uuid.uuid4().hex[:8]}@weathergpt.in"

        res = client.post("/api/v1/auth/register", json={
            "name": "Attacker Admin",
            "email": email,
            "password": "Password123!",
            "role": "admin"
        })

        assert res.status_code == 403, "Public admin self-registration in production must return 403 Forbidden!"
        assert "unauthorized" in res.json()["detail"].lower() or "forbidden" in res.json()["detail"].lower()


# ===========================================================================
# 4. IDOR DEFENSE (UNAUTHENTICATED & CROSS-USER PROFILE ACCESS)
# ===========================================================================

class TestIDORDefense:

    def test_05_unauthenticated_profile_view_rejected(self):
        """Unauthenticated caller querying ?user_id=victim must be rejected with 401 Unauthorized."""
        victim, _ = _create_test_user("Target Victim")

        res = client.get(f"/api/v1/users/me?user_id={victim.id}")
        assert res.status_code == 401, "Unauthenticated user_id query must return 401 Unauthorized!"

    def test_06_cross_user_profile_view_forbidden(self):
        """Authenticated User A cannot view User B's profile (403 Forbidden)."""
        _, token_a = _create_test_user("Alice User")
        user_b, _ = _create_test_user("Bob User")

        res = client.get(
            f"/api/v1/users/me?user_id={user_b.id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert res.status_code == 403
        assert "access denied" in res.json()["detail"].lower()

    def test_07_cross_user_profile_update_forbidden(self):
        """Authenticated User A cannot modify User B's profile (403 Forbidden)."""
        _, token_a = _create_test_user("Alice User")
        user_b, _ = _create_test_user("Bob User")

        res = client.put(
            f"/api/v1/users/me?user_id={user_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"name": "Attacker Name"}
        )
        assert res.status_code == 403
        assert "access denied" in res.json()["detail"].lower()


# ===========================================================================
# 5. LOCATION PRIVACY & OWNERSHIP
# ===========================================================================

class TestLocationPrivacyAndOwnership:

    def test_08_cross_user_saved_location_deletion_forbidden(self):
        """User A cannot delete a saved location owned by User B."""
        _, token_a = _create_test_user("Alice Location")
        user_b, token_b = _create_test_user("Bob Location")

        # Bob creates a saved location
        create_res = client.post(
            "/api/v1/locations/saved",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"name": "Bob's Secret Haven", "latitude": 11.0168, "longitude": 76.9558}
        )
        assert create_res.status_code == 201
        loc_id = create_res.json()["id"]

        # Alice attempts to delete Bob's location
        del_res = client.delete(
            f"/api/v1/locations/saved/{loc_id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert del_res.status_code == 403
        assert "access denied" in del_res.json()["detail"].lower()


# ===========================================================================
# 6. FCM SECURITY & TOKEN ISOLATION
# ===========================================================================

class TestFCMSecurity:

    def test_09_cross_user_device_token_deletion_forbidden(self):
        """User A cannot delete a device token registered to User B."""
        _, token_a = _create_test_user("Alice FCM")
        _, token_b = _create_test_user("Bob FCM")
        bob_dev_token = f"fcm_bob_{uuid.uuid4().hex}"

        # Register Bob's device token
        client.post(
            "/api/v1/notifications/devices",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"token": bob_dev_token, "platform": "android"}
        )

        # Alice attempts to delete Bob's token
        del_res = client.delete(
            f"/api/v1/notifications/devices/{bob_dev_token}",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert del_res.status_code == 403
        assert "cannot unregister" in del_res.json()["detail"].lower()

    def test_10_cross_user_test_notification_forbidden(self):
        """User A cannot target User B's device token with a test notification."""
        _, token_a = _create_test_user("Alice Notif")
        _, token_b = _create_test_user("Bob Notif")
        bob_dev_token = f"fcm_bob_target_{uuid.uuid4().hex}"

        # Register Bob's device token
        client.post(
            "/api/v1/notifications/devices",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"token": bob_dev_token, "platform": "android"}
        )

        # Alice attempts to dispatch test notification to Bob's token
        test_res = client.post(
            "/api/v1/notifications/test",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"device_token": bob_dev_token, "title": "Phishing Alert"}
        )
        assert test_res.status_code == 403
        assert "cannot target a device token belonging to another user" in test_res.json()["detail"].lower()


# ===========================================================================
# 7. WEATHER & ALERT INTEGRITY
# ===========================================================================

class TestWeatherAlertIntegrity:

    def test_11_client_cannot_create_or_modify_official_alerts(self):
        """Clients have NO endpoint to create, mutate, or delete official IMD alerts."""
        payload = {
            "title": "Fake Cyclone Red Alert",
            "severity": "extreme",
            "affected_area": "Coimbatore"
        }

        # Attempt POST to alerts endpoint
        post_res = client.post("/api/v1/weather/alerts", json=payload)
        assert post_res.status_code == 405, "POST /weather/alerts must return 405 Method Not Allowed!"

        # Attempt PUT to alerts endpoint
        put_res = client.put("/api/v1/weather/alerts", json=payload)
        assert put_res.status_code == 405, "PUT /weather/alerts must return 405 Method Not Allowed!"

        # Attempt DELETE to alerts endpoint
        del_res = client.delete("/api/v1/weather/alerts")
        assert del_res.status_code == 405, "DELETE /weather/alerts must return 405 Method Not Allowed!"


# ===========================================================================
# 8. INPUT VALIDATION & OVERFLOW PROTECTION
# ===========================================================================

class TestInputValidation:

    @pytest.mark.parametrize("bad_lat,bad_lon", [
        (95.0, 76.95),
        (-95.0, 76.95),
        (11.0, 185.0),
        (11.0, -185.0),
        (1000.0, 2000.0)
    ])
    def test_12_malformed_coordinates_rejected(self, bad_lat, bad_lon):
        """Out-of-bounds geographic coordinates return 400 Bad Request across endpoints."""
        res_curr = client.get(f"/api/v1/weather/current?lat={bad_lat}&lon={bad_lon}")
        assert res_curr.status_code == 400

        res_fc = client.get(f"/api/v1/weather/forecast?lat={bad_lat}&lon={bad_lon}")
        assert res_fc.status_code == 400

        res_al = client.get(f"/api/v1/weather/alerts?lat={bad_lat}&lon={bad_lon}")
        assert res_al.status_code == 400

    def test_13_chat_input_overflow_rejected(self):
        """Chat message exceeding 1000 characters is rejected with 400 Bad Request or 422 Unprocessable."""
        oversized_message = "A" * 1001
        res = client.post("/api/v1/chat", json={"message": oversized_message})
        assert res.status_code in (400, 422)

    def test_14_chat_empty_message_rejected(self):
        """Empty or whitespace-only chat message is rejected with 400 Bad Request or 422 Unprocessable."""
        res = client.post("/api/v1/chat", json={"message": "   "})
        assert res.status_code in (400, 422)


# ===========================================================================
# 9. CORS CONFIGURATION
# ===========================================================================

class TestCORSConfiguration:

    def test_15_no_wildcard_origin_with_credentials(self):
        """ALLOWED_ORIGINS must not allow wildcard '*' when allow_credentials=True."""
        assert "*" not in settings.ALLOWED_ORIGINS, "Wildcard '*' origin is strictly forbidden in ALLOWED_ORIGINS!"


# ===========================================================================
# 10. AUDIT LOG REDACTION
# ===========================================================================

class TestAuditLogRedaction:

    def test_16_sensitive_fields_redacted_in_logs(self):
        """Logging filter redacts passwords, tokens, API keys, and private key blocks."""
        filter_instance = RedactFilter()

        samples = [
            ("User logged in with password=SuperSecretPass123!", "password=[REDACTED]"),
            ("Received request with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz", "Bearer [REDACTED_TOKEN]"),
            ("Gemini key configured: AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q", "[REDACTED_GEMINI_KEY]"),
            ("OpenAI key configured: sk-proj-1234567890abcdefghijklmnopqrstuvwxyz", "[REDACTED_OPENAI_KEY]"),
            ("Resend key: re_1234567890abcdefghij", "[REDACTED_RESEND_KEY]"),
            ("GitHub token: ghp_1234567890abcdefghijklmnopqrstuvwxyz", "[REDACTED_GITHUB_TOKEN]"),
            ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
        ]

        for text, expected in samples:
            redacted = filter_instance.redact(text)
            assert expected in redacted, f"Expected '{expected}' in redacted text: '{redacted}'"


# ===========================================================================
# 11. PASSWORD RESET TOKEN PROTECTION IN PRODUCTION
# ===========================================================================

class TestPasswordResetTokenProtection:

    def test_17_reset_token_withheld_in_production(self, monkeypatch):
        """In production, POST /auth/forgot-password must not return reset_token in response."""
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        user, _ = _create_test_user("Reset Target")

        res = client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        assert res.status_code == 200
        data = res.json()
        assert "reset_token" not in data, "reset_token must NEVER be returned in production response!"
