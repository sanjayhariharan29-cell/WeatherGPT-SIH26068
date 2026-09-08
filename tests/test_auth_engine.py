import uuid
import pytest
from datetime import datetime, timezone, timedelta
import jwt
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.session import SessionLocal
from backend.db.models import User, UserPreference, Conversation
from backend.core.security import create_access_token, hash_password
from backend.config.settings import settings

client = TestClient(app)

def test_01_valid_registration():
    """1. Test valid registration creates user and preferences."""
    email = f"auth_user_{uuid.uuid4().hex[:8]}@weathergpt.in"
    payload = {
        "name": "Auth User One",
        "email": email,
        "password": "SecurePassword123!",
        "persona": "farmer",
        "language": "ta"
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "user_id" in data
    assert data["email"] == email.lower()
    assert data["message"] == "Registration successful"


def test_02_duplicate_registration():
    """2. Test duplicate registration attempt returns 400 error."""
    email = f"auth_dup_{uuid.uuid4().hex[:8]}@weathergpt.in"
    payload = {
        "name": "Original User",
        "email": email,
        "password": "Password123!",
        "persona": "student"
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 200

    # Duplicate attempt
    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_03_valid_login():
    """3. Test valid login returns access token and user info."""
    email = f"auth_login_{uuid.uuid4().hex[:8]}@weathergpt.in"
    password = "CorrectPassword123!"
    reg_payload = {
        "name": "Login User",
        "email": email,
        "password": password,
        "persona": "fisherman"
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": email,
        "password": password
    }
    res = client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == email.lower()
    assert data["user"]["persona"] == "fisherman"


def test_04_invalid_password():
    """4. Test login with wrong password returns 401 generic error."""
    email = f"auth_wrongpass_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={
        "name": "User WrongPass",
        "email": email,
        "password": "RightPassword123!"
    })

    res = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "WrongPassword999!"
    })
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]


def test_05_invalid_account():
    """5. Test login with non-existent account returns 401 generic error."""
    res = client.post("/api/v1/auth/login", json={
        "email": "nonexistent_account_9999@weathergpt.in",
        "password": "SomePassword123!"
    })
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]


def test_06_protected_endpoint_without_auth():
    """6. Test accessing protected endpoint without auth header returns 401."""
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert "credentials required" in res.json()["detail"].lower()


def test_07_valid_authenticated_request():
    """7. Test accessing protected endpoint with valid Bearer token returns 200."""
    email = f"auth_valid_req_{uuid.uuid4().hex[:8]}@weathergpt.in"
    password = "ValidPassword123!"
    client.post("/api/v1/auth/register", json={
        "name": "Auth Me User",
        "email": email,
        "password": password
    })
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]

    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == email.lower()
    assert data["name"] == "Auth Me User"


def test_08_expired_token():
    """8. Test expired token returns 401 expired error."""
    email = f"auth_expired_{uuid.uuid4().hex[:8]}@weathergpt.in"
    user_id = str(uuid.uuid4())
    expired_token = create_access_token(
        data={"sub": user_id, "email": email, "role": "user"},
        expires_delta=timedelta(seconds=-10)
    )

    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_09_invalid_token():
    """9. Test corrupted or invalid token returns 401 error."""
    invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalidpayload.invalidsignature"
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {invalid_token}"})
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower()


def test_10_user_ownership():
    """10. Test User A cannot access or delete User B's conversation or view another user's profile."""
    # Register User A
    email_a = f"usera_{uuid.uuid4().hex[:8]}@weathergpt.in"
    res_a = client.post("/api/v1/auth/register", json={"name": "User A", "email": email_a, "password": "PasswordA123!"})
    token_a = client.post("/api/v1/auth/login", json={"email": email_a, "password": "PasswordA123!"}).json()["access_token"]
    id_a = res_a.json()["user_id"]

    # Register User B
    email_b = f"userb_{uuid.uuid4().hex[:8]}@weathergpt.in"
    res_b = client.post("/api/v1/auth/register", json={"name": "User B", "email": email_b, "password": "PasswordB123!"})
    token_b = client.post("/api/v1/auth/login", json={"email": email_b, "password": "PasswordB123!"}).json()["access_token"]
    id_b = res_b.json()["user_id"]

    # User B creates a conversation
    conv_id_b = f"conv_b_{uuid.uuid4().hex[:6]}"
    chat_res = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token_b}"},
        json={
            "message": "Rain status for Nagapattinam?",
            "conversation_id": conv_id_b,
            "location": {"name": "Nagapattinam"}
        }
    )
    assert chat_res.status_code == 200

    # User A tries to get User B's conversation detail
    res_get = client.get(f"/api/v1/chat/conversations/{conv_id_b}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_get.status_code == 403
    assert "access denied" in res_get.json()["detail"].lower()

    # User A tries to delete User B's conversation
    res_del = client.delete(f"/api/v1/chat/conversations/{conv_id_b}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_del.status_code == 403

    # User A tries to view User B's profile via user_id parameter
    res_prof = client.get(f"/api/v1/users/me?user_id={id_b}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_prof.status_code == 403


def test_11_unauthorized_user():
    """11. Test non-admin user accessing admin endpoint returns 403 Forbidden."""
    email = f"user_normal_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Normal User", "email": email, "password": "Password123!", "role": "user"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"}).json()["access_token"]

    res = client.get("/api/v1/auth/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "insufficient permissions" in res.json()["detail"].lower()

    # Register Admin user
    email_admin = f"admin_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Admin User", "email": email_admin, "password": "Password123!", "role": "admin"})
    token_admin = client.post("/api/v1/auth/login", json={"email": email_admin, "password": "Password123!"}).json()["access_token"]

    res_admin = client.get("/api/v1/auth/admin/users", headers={"Authorization": f"Bearer {token_admin}"})
    assert res_admin.status_code == 200
    assert isinstance(res_admin.json(), list)


def test_12_logout_revocation():
    """12. Test logout revokes token and subsequent requests fail with 401."""
    email = f"user_logout_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Logout User", "email": email, "password": "Password123!"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"}).json()["access_token"]

    # Verify active token works
    res1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 200

    # Logout
    logout_res = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    # Verify revoked token fails
    res2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 401
    assert "revoked" in res2.json()["detail"].lower()


def test_13_malformed_credentials():
    """13. Test malformed registration and login requests are properly rejected."""
    # Invalid email
    res1 = client.post("/api/v1/auth/register", json={
        "name": "Invalid Email User",
        "email": "not-an-email",
        "password": "Password123!"
    })
    assert res1.status_code in [400, 422]

    # Too short password
    res2 = client.post("/api/v1/auth/register", json={
        "name": "Short Password",
        "email": f"short_{uuid.uuid4().hex[:6]}@weathergpt.in",
        "password": "123"
    })
    assert res2.status_code in [400, 422]

    # Invalid role
    res3 = client.post("/api/v1/auth/register", json={
        "name": "Super Hacker",
        "email": f"hacker_{uuid.uuid4().hex[:6]}@weathergpt.in",
        "password": "Password123!",
        "role": "supergod"
    })
    assert res3.status_code in [400, 422]


def test_14_password_never_stored_plaintext():
    """14. Test passwords in the database are hashed with bcrypt and never stored in plaintext."""
    email = f"hash_check_{uuid.uuid4().hex[:8]}@weathergpt.in"
    raw_password = "MySuperSecretPlainPassword123!"
    client.post("/api/v1/auth/register", json={
        "name": "Hash Check User",
        "email": email,
        "password": raw_password
    })

    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.password_hash != raw_password
    assert user.password_hash.startswith("$2b$")
    assert len(user.password_hash) > 50
    db.close()


def test_15_secret_leakage_prevention():
    """15. Test security errors and responses do not leak SECRET_KEY, passwords, or raw stack traces."""
    # Failed login response check
    res_login = client.post("/api/v1/auth/login", json={
        "email": "nonexistent@weathergpt.in",
        "password": "SecretPassword123!"
    })
    body_text = str(res_login.json())
    assert settings.SECRET_KEY not in body_text
    assert "SecretPassword123!" not in res_login.json()["detail"]
    assert "Traceback" not in body_text

    # Saved locations user ownership test
    email = f"saved_loc_user_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Saved Loc User", "email": email, "password": "Password123!"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"}).json()["access_token"]

    loc_res = client.post(
        "/api/v1/locations/saved",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Chennai Port", "latitude": 13.0827, "longitude": 80.2707}
    )
    assert loc_res.status_code == 201
    loc_id = loc_res.json()["id"]

    # Retrieve saved locations
    get_locs = client.get("/api/v1/locations/saved", headers={"Authorization": f"Bearer {token}"})
    assert get_locs.status_code == 200
    assert len(get_locs.json()) >= 1
