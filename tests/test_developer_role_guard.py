import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.db.session import SessionLocal, get_db
from backend.db.models import User
from backend.db.init_db import init_db
from backend.core.security import create_access_token, hash_password, require_developer_role


# Isolated test app to test require_developer_role directly
test_app = FastAPI()

@test_app.get("/guarded-endpoint")
def protected_developer_endpoint(current_user: User = Depends(require_developer_role)):
    return {
        "status": "success",
        "user_id": current_user.id,
        "email": current_user.email,
        "role": current_user.role
    }


@pytest.fixture(scope="module")
def client():
    with TestClient(test_app) as c:
        yield c


@pytest.fixture(scope="module")
def role_test_users():
    """Sets up a regular user and a developer user for testing."""
    init_db()
    with SessionLocal() as db:
        emails = [
            "guard_regular_user@example.com",
            "guard_dev_user@example.com",
            "guard_admin_user@example.com"
        ]
        db.query(User).filter(User.email.in_(emails)).delete(synchronize_session=False)
        db.commit()

        regular_user = User(
            name="Regular User",
            email="guard_regular_user@example.com",
            password_hash=hash_password("Password123!"),
            role="user",
            is_verified=True
        )
        dev_user = User(
            name="Dev User",
            email="guard_dev_user@example.com",
            password_hash=hash_password("Password123!"),
            role="developer",
            is_verified=True
        )
        admin_user = User(
            name="Admin User",
            email="guard_admin_user@example.com",
            password_hash=hash_password("Password123!"),
            role="admin",
            is_verified=True
        )
        db.add_all([regular_user, dev_user, admin_user])
        db.commit()
        db.refresh(regular_user)
        db.refresh(dev_user)
        db.refresh(admin_user)

        user_token = create_access_token(data={"sub": regular_user.id, "email": regular_user.email})
        dev_token = create_access_token(data={"sub": dev_user.id, "email": dev_user.email})
        admin_token = create_access_token(data={"sub": admin_user.id, "email": admin_user.email})

        yield {
            "user": regular_user,
            "user_token": user_token,
            "dev": dev_user,
            "dev_token": dev_token,
            "admin": admin_user,
            "admin_token": admin_token
        }

        db.query(User).filter(User.email.in_(emails)).delete(synchronize_session=False)
        db.commit()


def test_user_model_role_default_and_validation():
    """Verify that User model defaults role to 'user' and validates values."""
    with SessionLocal() as db:
        # Default role when not provided
        test_u = User(
            name="Default Role Tester",
            email="default_role_test@example.com",
            password_hash=hash_password("Secret123!"),
            is_verified=True
        )
        assert test_u.role == "user"

        # Explicit developer role
        dev_u = User(
            name="Explicit Dev",
            email="explicit_dev_test@example.com",
            password_hash=hash_password("Secret123!"),
            role="developer"
        )
        assert dev_u.role == "developer"

        # Invalid role raises ValueError
        with pytest.raises(ValueError, match="Invalid user role"):
            User(
                name="Invalid Role User",
                email="invalid_role@example.com",
                password_hash=hash_password("Secret123!"),
                role="hacker"
            )


def test_guard_unauthenticated_returns_401(client):
    """Missing Authorization header must return 401 Unauthorized."""
    resp = client.get("/guarded-endpoint")
    assert resp.status_code == 401
    assert "Authentication credentials required" in resp.json().get("detail", "")


def test_guard_regular_user_returns_403(client, role_test_users):
    """Authenticated user with role='user' must receive 403 Forbidden."""
    headers = {"Authorization": f"Bearer {role_test_users['user_token']}"}
    resp = client.get("/guarded-endpoint", headers=headers)
    assert resp.status_code == 403
    assert "Developer access required" in resp.json().get("detail", "")


def test_guard_developer_user_returns_200(client, role_test_users):
    """Authenticated user with role='developer' must receive 200 OK."""
    headers = {"Authorization": f"Bearer {role_test_users['dev_token']}"}
    resp = client.get("/guarded-endpoint", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["role"] == "developer"
    assert data["email"] == "guard_dev_user@example.com"


def test_guard_admin_user_returns_200(client, role_test_users):
    """Authenticated user with role='admin' must also pass developer guard with 200 OK."""
    headers = {"Authorization": f"Bearer {role_test_users['admin_token']}"}
    resp = client.get("/guarded-endpoint", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["role"] == "admin"


def test_normal_signup_defaults_to_user_role():
    """Verify registration endpoint without role assigns role='user'."""
    from backend.main import app as main_app
    with TestClient(main_app) as main_client:
        email = "normal_signup_role_test@example.com"
        # Cleanup if exists
        with SessionLocal() as db:
            db.query(User).filter(User.email == email).delete(synchronize_session=False)
            db.commit()

        payload = {
            "name": "Normal Citizen",
            "email": email,
            "password": "Password123!",
            "confirm_password": "Password123!",
            "language": "ta",
            "persona": "student"
        }
        resp = main_client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 200, f"Register failed: {resp.text}"
        data = resp.json()
        assert data["role"] == "user"

        # Check DB directly
        with SessionLocal() as db:
            created_u = db.query(User).filter(User.email == email).first()
            assert created_u is not None
            assert created_u.role == "user"

            # Cleanup
            db.query(User).filter(User.email == email).delete(synchronize_session=False)
            db.commit()


def test_signup_with_developer_role_request_still_defaults_to_user_role():
    """Verify that attempting to self-assign role='developer' via public signup endpoint still defaults to 'user'."""
    from backend.main import app as main_app
    with TestClient(main_app) as main_client:
        email = "self_dev_signup_test@example.com"
        with SessionLocal() as db:
            db.query(User).filter(User.email == email).delete(synchronize_session=False)
            db.commit()

        payload = {
            "name": "Attacker Trying Dev Role",
            "email": email,
            "password": "Password123!",
            "confirm_password": "Password123!",
            "language": "en",
            "persona": "student",
            "role": "developer"
        }
        resp = main_client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 200, f"Register failed: {resp.text}"
        data = resp.json()
        assert data["role"] == "user", f"Expected role 'user', got '{data['role']}'"

        with SessionLocal() as db:
            created_u = db.query(User).filter(User.email == email).first()
            assert created_u is not None
            assert created_u.role == "user"

            db.query(User).filter(User.email == email).delete(synchronize_session=False)
            db.commit()

