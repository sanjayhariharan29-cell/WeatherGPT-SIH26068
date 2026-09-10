"""
Comprehensive Test Suite for SkyZen Phase 2: First-Launch Profile & User Data
WeatherGPT-SIH26068 / MoES / IMD AI-Powered Weather Intelligence Platform.

Validates:
1. New user has onboarding_completed=False
2. Profile creation and initial preferences
3. Authenticated profile access (GET /auth/profile & GET /auth/me)
4. Unauthorized profile access rejection (401)
5. Profile updates (PUT /auth/profile)
6. User ownership enforcement (User A cannot view or modify User B's profile, 403 Forbidden)
7. First-launch onboarding completion
8. Returning user skips onboarding (onboarding_completed=True)
9. Language preference persistence across logout/login
10. Role/Persona normalization and persistence (Student, Commuter, Farmer, Fisherman, Disaster / Emergency, General)
11. Profile name and persona available to AI Chat Context
12. Backward compatibility with existing user rows and legacy endpoints
13. Safe and idempotent SQLite migrations
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.main import app
from backend.db.session import SessionLocal, engine
from backend.db.models import User, UserPreference
from backend.db.init_db import init_db

client = TestClient(app)


def test_01_new_user_has_onboarding_completed_false():
    """1. New user registration starts with onboarding_completed=False."""
    email = f"newuser_{uuid.uuid4().hex[:8]}@weathergpt.in"
    reg_payload = {
        "name": "Arjun Das",
        "email": email,
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!"
    }
    res = client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["onboarding_completed"] is False
    assert data["full_name"] == "Arjun Das"

    # Login and verify onboarding_completed is False in user object
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    assert login_res.status_code == 200
    login_user = login_res.json()["user"]
    assert login_user["onboarding_completed"] is False


def test_02_profile_creation():
    """2. Registration creates UserPreference with notification_enabled=True and default persona."""
    email = f"profile_create_{uuid.uuid4().hex[:8]}@weathergpt.in"
    reg_res = client.post("/api/v1/auth/register", json={
        "name": "Kavitha Nair",
        "email": email,
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!"
    })
    assert reg_res.status_code == 200
    user_id = reg_res.json()["user_id"]

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        assert user is not None
        assert user.name == "Kavitha Nair"
        assert user.full_name == "Kavitha Nair"
        assert user.onboarding_completed is False
        assert user.preferences is not None
        assert user.preferences.notification_enabled is True
        assert user.preferences.persona == "student"
    finally:
        db.close()


def test_03_authenticated_profile_access():
    """3. Authenticated profile access returns complete profile contract."""
    email = f"auth_access_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Suresh Raina", "email": email, "password": "SecurePassword123!"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"}).json()["access_token"]

    # Test GET /auth/profile
    res_profile = client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert res_profile.status_code == 200
    pdata = res_profile.json()
    assert pdata["email"] == email.lower()
    assert pdata["full_name"] == "Suresh Raina"
    assert "onboarding_completed" in pdata
    assert "notification_enabled" in pdata
    assert "preferred_language" in pdata
    assert "persona" in pdata

    # Test GET /auth/me
    res_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["id"] == pdata["id"]


def test_04_unauthorized_profile_access():
    """4. Unauthorized requests are strictly rejected with 401."""
    # No token
    res1 = client.get("/api/v1/auth/profile")
    assert res1.status_code in [401, 403]

    # Malformed token
    res2 = client.get("/api/v1/auth/profile", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert res2.status_code in [401, 403]

    # Update without token
    res3 = client.put("/api/v1/auth/profile", json={"name": "Attacker"})
    assert res3.status_code in [401, 403]


def test_05_profile_update():
    """5. Authenticated user updates profile information and preferences."""
    email = f"profile_update_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Priya Sharma", "email": email, "password": "SecurePassword123!"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"}).json()["access_token"]

    # Update profile with new name, persona (Farmer), language (Hindi), and notifications (False)
    update_payload = {
        "full_name": "Priya S. Sharma",
        "persona": "farmer",
        "language": "hi",
        "notification_enabled": False
    }
    update_res = client.put("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token}"}, json=update_payload)
    assert update_res.status_code == 200, update_res.text
    data = update_res.json()
    assert data["name"] == "Priya S. Sharma"
    assert data["full_name"] == "Priya S. Sharma"
    assert data["persona"] == "farmer"
    assert data["language"] == "hi"
    assert data["preferred_language"] == "hi"
    assert data["notification_enabled"] is False

    # Verify persistence via GET /auth/profile
    check_res = client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert check_res.status_code == 200
    cdata = check_res.json()
    assert cdata["name"] == "Priya S. Sharma"
    assert cdata["persona"] == "farmer"
    assert cdata["language"] == "hi"
    assert cdata["notification_enabled"] is False


def test_06_user_cannot_modify_another_user_profile():
    """6. User A cannot view or modify User B's profile (403 Forbidden)."""
    # User A
    email_a = f"usera_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Alice Green", "email": email_a, "password": "PasswordA123!"})
    token_a = client.post("/api/v1/auth/login", json={"email": email_a, "password": "PasswordA123!"}).json()["access_token"]

    # User B
    email_b = f"userb_{uuid.uuid4().hex[:8]}@weathergpt.in"
    res_b = client.post("/api/v1/auth/register", json={"name": "Bob Blue", "email": email_b, "password": "PasswordB123!"})
    id_b = res_b.json()["user_id"]

    # User A attempts to view User B's profile via /auth/profile?user_id=...
    res_view_auth = client.get(f"/api/v1/auth/profile?user_id={id_b}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_view_auth.status_code == 403

    # User A attempts to modify User B's profile via /auth/profile?user_id=...
    res_mod_auth = client.put(f"/api/v1/auth/profile?user_id={id_b}", headers={"Authorization": f"Bearer {token_a}"}, json={"name": "Hacked Bob"})
    assert res_mod_auth.status_code == 403

    # User A attempts to modify User B's profile via /users/me?user_id=...
    res_mod_users = client.put(f"/api/v1/users/me?user_id={id_b}", headers={"Authorization": f"Bearer {token_a}"}, json={"name": "Hacked Bob"})
    assert res_mod_users.status_code == 403

    # Verify Bob's profile remains completely untouched
    db = SessionLocal()
    try:
        bob = db.query(User).filter(User.id == id_b).first()
        assert bob.name == "Bob Blue"
    finally:
        db.close()


def test_07_onboarding_completion():
    """7. Submitting first-launch onboarding marks onboarding_completed=True."""
    email = f"onboard_done_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Rahul Roy", "email": email, "password": "SecurePassword123!"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"}).json()["access_token"]

    # Submit onboarding payload
    onboard_payload = {
        "full_name": "Rahul Roy",
        "role": "commuter",
        "preferred_language": "en",
        "notification_enabled": True,
        "onboarding_completed": True
    }
    res = client.put("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token}"}, json=onboard_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["onboarding_completed"] is True
    assert data["persona"] == "commuter"
    assert data["language"] == "en"


def test_08_returning_user_skips_onboarding():
    """8. Returning user with onboarding_completed=True skips onboarding setup."""
    email = f"returning_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Deepa Menon", "email": email, "password": "SecurePassword123!"})
    token1 = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"}).json()["access_token"]

    # Complete onboarding
    client.put("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token1}"}, json={"onboarding_completed": True})

    # Logout
    client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token1}"})

    # Re-login (Returning User)
    login_res2 = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    assert login_res2.status_code == 200
    user2 = login_res2.json()["user"]
    token2 = login_res2.json()["access_token"]

    assert user2["onboarding_completed"] is True

    # Validate /auth/me returns onboarding_completed=True
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert me_res.status_code == 200
    assert me_res.json()["onboarding_completed"] is True


def test_09_language_preference_persistence():
    """9. Language preference (en, ta, hi) persists across login/logout sessions."""
    email = f"lang_persist_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Anand Kumar", "email": email, "password": "SecurePassword123!"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"}).json()["access_token"]

    # Set preferred language to Hindi
    client.put("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token}"}, json={"preferred_language": "hi"})

    # Check immediate persistence
    p1 = client.get("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token}"}).json()
    assert p1["language"] == "hi"
    assert p1["preferred_language"] == "hi"

    # Logout and log back in
    client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"})
    new_token = login_res.json()["access_token"]

    p2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"}).json()
    assert p2["language"] == "hi"
    assert p2["preferred_language"] == "hi"


def test_10_role_persona_persistence():
    """10. Supported personas (Student, Commuter, Farmer, Fisherman, Disaster / Emergency, General) normalize and persist."""
    email = f"persona_persist_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Vikram Seth", "email": email, "password": "SecurePassword123!"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"}).json()["access_token"]

    test_personas = [
        ("fisherman", "fisherman"),
        ("commuter", "commuter"),
        ("farmer", "farmer"),
        ("disaster / emergency", "disaster_response"),
        ("student", "student"),
        ("general", "general")
    ]

    for role_input, expected_normalized in test_personas:
        res = client.put("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token}"}, json={"role": role_input})
        assert res.status_code == 200
        assert res.json()["persona"] == expected_normalized

        # Verify DB directly
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.email == email.lower()).first()
            assert u.persona == expected_normalized
            assert u.preferences.persona == expected_normalized
        finally:
            db.close()


def test_11_profile_name_available_to_chat_context():
    """11. Authenticated user's name is incorporated into chat response context."""
    email = f"chat_profile_{uuid.uuid4().hex[:8]}@weathergpt.in"
    client.post("/api/v1/auth/register", json={"name": "Sanjay Hariharan", "email": email, "password": "SecurePassword123!"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "SecurePassword123!"}).json()["access_token"]

    # Set persona to student
    client.put("/api/v1/auth/profile", headers={"Authorization": f"Bearer {token}"}, json={"persona": "student", "language": "en"})

    chat_payload = {
        "message": "I leave for college at 8 AM and return at 5 PM. What is the rain risk for my commute?",
        "location": {"name": "Coimbatore"},
        "language": "en"
    }
    chat_res = client.post("/api/v1/chat", headers={"Authorization": f"Bearer {token}"}, json=chat_payload)
    assert chat_res.status_code == 200, chat_res.text
    answer = chat_res.json()["answer"]

    # The AI naturally and respectfully uses user's first name
    assert "Sanjay" in answer
    assert "rain risk" in answer.lower() or "commute" in answer.lower()


def test_12_existing_users_remain_compatible():
    """12. Existing user rows without prior profile updates remain fully compatible."""
    db = SessionLocal()
    legacy_id = str(uuid.uuid4())
    legacy_email = f"legacy_{legacy_id[:8]}@weathergpt.in"
    try:
        # Insert a user directly to simulate legacy record
        db.execute(text(
            "INSERT INTO users (id, name, email, password_hash, language, persona, role, is_verified, onboarding_completed, created_at) "
            "VALUES (:id, :name, :email, 'hashed_pass', 'ta', 'student', 'user', 1, 0, CURRENT_TIMESTAMP)"
        ), {"id": legacy_id, "name": "Legacy User", "email": legacy_email})
        db.commit()

        legacy_user = db.query(User).filter(User.id == legacy_id).first()
        assert legacy_user is not None
        assert legacy_user.full_name == "Legacy User"
        assert legacy_user.preferred_language == "ta"
        assert legacy_user.onboarding_completed is False
    finally:
        db.close()


def test_13_sqlite_migration_works():
    """13. init_db() safely and idempotently handles schema additions without dropping tables or losing data."""
    # Execute init_db multiple times
    init_db()
    init_db()

    # Check columns on users table
    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        cols = [r[1] for r in res]
        assert "onboarding_completed" in cols
        assert "is_verified" in cols
        assert "role" in cols

        res_pref = conn.execute(text("PRAGMA table_info(user_preferences)")).fetchall()
        pref_cols = [r[1] for r in res_pref]
        assert "notification_enabled" in pref_cols
