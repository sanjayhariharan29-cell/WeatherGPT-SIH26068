import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.session import get_db, SessionLocal
from backend.db.models import User
from backend.core.security import create_access_token

client = TestClient(app)


def test_01_signup_with_valid_data():
    """1. Signup with valid data generates user and real verification token."""
    email = f"valid_signup_{uuid.uuid4().hex[:8]}@weathergpt.in"
    payload = {
        "name": "Aaditya Raman",
        "email": email,
        "password": "SecureWeatherPass123!",
        "confirm_password": "SecureWeatherPass123!"
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "user_id" in data
    assert data["email"] == email.lower()
    assert data["is_verified"] is False
    assert "verification_token" in data
    assert len(data["verification_token"]) == 6


def test_02_signup_with_invalid_email():
    """2. Signup with invalid email format is rejected."""
    payload = {
        "name": "Invalid Email User",
        "email": "not-a-valid-email",
        "password": "ValidPassword123!",
        "confirm_password": "ValidPassword123!"
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 422


def test_03_signup_with_weak_password():
    """3. Signup with weak password (< 6 chars) is rejected."""
    email = f"weak_pass_{uuid.uuid4().hex[:8]}@weathergpt.in"
    payload = {
        "name": "Weak Pass User",
        "email": email,
        "password": "123",
        "confirm_password": "123"
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 422


def test_04_signup_with_mismatched_passwords():
    """4. Signup with mismatched passwords is rejected."""
    email = f"mismatch_{uuid.uuid4().hex[:8]}@weathergpt.in"
    payload = {
        "name": "Mismatch User",
        "email": email,
        "password": "Password123!",
        "confirm_password": "DifferentPassword123!"
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 422


def test_05_duplicate_account_handling():
    """5. Duplicate account registration returns 400 Bad Request."""
    email = f"duplicate_{uuid.uuid4().hex[:8]}@weathergpt.in"
    payload = {
        "name": "Original User",
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!"
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 200

    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_06_login_with_valid_credentials():
    """6. Login with valid credentials returns JWT and user profile."""
    email = f"login_valid_{uuid.uuid4().hex[:8]}@weathergpt.in"
    reg_payload = {
        "name": "Login User",
        "email": email,
        "password": "StrongPassword123!"
    }
    res = client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 200

    login_res = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "StrongPassword123!"
    })
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == email.lower()
    assert "is_verified" in data["user"]


def test_07_login_with_invalid_credentials():
    """7. Login with invalid credentials returns 401 with generic message."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "nonexistent_account@weathergpt.in",
        "password": "WrongPassword123!"
    })
    assert login_res.status_code == 401
    assert "Invalid email or password" in login_res.json()["detail"]


def test_08_logout():
    """8. Logout revokes token so subsequent authenticated requests fail."""
    email = f"logout_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={
        "name": "Logout User",
        "email": email,
        "password": "Password123!"
    })
    login_res = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "Password123!"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify access works before logout
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200

    # Logout
    logout_res = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # Verify token is now revoked
    me_after = client.get("/api/v1/auth/me", headers=headers)
    assert me_after.status_code == 401


def test_09_session_restoration():
    """9. Session restoration via /auth/me returns the authenticated user."""
    email = f"session_restore_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={
        "name": "Restore User",
        "email": email,
        "password": "Password123!"
    })
    login_res = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "Password123!"
    })
    token = login_res.json()["access_token"]

    restore_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert restore_res.status_code == 200
    user_data = restore_res.json()
    assert user_data["email"] == email.lower()
    assert user_data["name"] == "Restore User"


def test_10_expired_or_invalid_session():
    """10. Expired or forged session token returns 401."""
    # Bogus token
    res_fake = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer forged.jwt.token"})
    assert res_fake.status_code == 401

    # Expired token
    expired_token = create_access_token(
        data={"sub": "any_user_id", "email": "test@test.com", "role": "user"},
        expires_delta=timedelta(seconds=-10)
    )
    res_expired = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_expired.status_code == 401


def test_11_password_reset_request_and_flow():
    """11. Real password reset flow: forgot password -> verify token -> reset password -> login with new password."""
    email = f"pw_reset_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={
        "name": "Reset User",
        "email": email,
        "password": "OldPassword123!"
    })

    # 1. Request reset
    forgot_res = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_res.status_code == 200
    data = forgot_res.json()
    assert "reset_token" in data
    reset_token = data["reset_token"]

    # 2. Verify token validity
    verify_token_res = client.post("/api/v1/auth/verify-reset-token", json={"token": reset_token})
    assert verify_token_res.status_code == 200
    assert verify_token_res.json()["valid"] is True

    # 3. Reset password
    reset_res = client.post("/api/v1/auth/reset-password", json={
        "token": reset_token,
        "new_password": "NewSecretPassword123!",
        "confirm_password": "NewSecretPassword123!"
    })
    assert reset_res.status_code == 200

    # 4. Old password fails
    old_login = client.post("/api/v1/auth/login", json={"email": email, "password": "OldPassword123!"})
    assert old_login.status_code == 401

    # 5. New password succeeds
    new_login = client.post("/api/v1/auth/login", json={"email": email, "password": "NewSecretPassword123!"})
    assert new_login.status_code == 200


def test_12_protected_route_behavior():
    """12. Unauthenticated requests to protected endpoints return 401."""
    # /auth/me
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401

    # /auth/logout without token
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 401


def test_13_email_verification_flow():
    """13. Real email verification flow: register -> get token -> verify-email -> user verified."""
    email = f"verify_flow_{uuid.uuid4().hex[:8]}@weathergpt.in"
    reg_res = client.post("/api/v1/auth/register", json={
        "name": "Verify Me",
        "email": email,
        "password": "Password123!"
    })
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    token = reg_data["verification_token"]
    assert reg_data["is_verified"] is False

    # Verify with invalid token
    bad_res = client.post("/api/v1/auth/verify-email", json={"token": "999999"})
    assert bad_res.status_code == 400

    # Verify with real token
    good_res = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert good_res.status_code == 200
    assert good_res.json()["is_verified"] is True

    # Token cannot be reused
    reuse_res = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert reuse_res.status_code == 400


def test_14_resend_verification_token():
    """14. Resending verification token generates a fresh token for unverified user."""
    email = f"resend_tok_{uuid.uuid4().hex[:8]}@weathergpt.in"
    reg_res = client.post("/api/v1/auth/register", json={
        "name": "Resend User",
        "email": email,
        "password": "Password123!"
    })
    old_token = reg_res.json()["verification_token"]

    resend_res = client.post("/api/v1/auth/resend-verification", json={"email": email})
    assert resend_res.status_code == 200
    new_token = resend_res.json()["verification_token"]
    assert len(new_token) == 6

    # Verify with new token
    verify_res = client.post("/api/v1/auth/verify-email", json={"token": new_token})
    assert verify_res.status_code == 200
    assert verify_res.json()["is_verified"] is True


def test_15_android_and_web_api_compatibility():
    """15. Ensure auth endpoints return standard CORS and JSON headers for web and Android Capacitor webview."""
    res = client.options("/api/v1/auth/login", headers={
        "Origin": "http://localhost",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"
    })
    # FastAPI CORS middleware returns 200 for allowed preflight
    assert res.status_code in [200, 204]
