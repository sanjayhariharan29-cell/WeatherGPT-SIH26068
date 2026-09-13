import sys
import subprocess
import pytest
from backend.db.session import SessionLocal
from backend.db.models import User
from backend.core.security import hash_password
from scripts.promote_developer import promote_user, list_users


@pytest.fixture
def temp_user():
    """Create a temporary user with 'user' role for testing promotion."""
    with SessionLocal() as db:
        # Clean up any leftover test user
        db.query(User).filter(User.email == "test_promo_user@example.com").delete(synchronize_session=False)
        db.commit()

        user = User(
            name="Promo Test User",
            email="test_promo_user@example.com",
            password_hash=hash_password("Pass123!"),
            role="user",
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
        user_email = user.email

        yield {"id": user_id, "email": user_email}

        # Cleanup
        db.query(User).filter(User.email == "test_promo_user@example.com").delete(synchronize_session=False)
        db.commit()


def test_promote_user_by_email(temp_user):
    """Verifies promoting a user by email to developer."""
    result = promote_user(identifier=temp_user["email"], by="email", target_role="developer")
    assert result["success"] is True
    assert result["user_id"] == temp_user["id"]
    assert result["previous_role"] == "user"
    assert result["new_role"] == "developer"
    assert result["updated"] is True

    # Check persistence in DB
    with SessionLocal() as db:
        u = db.query(User).filter(User.id == temp_user["id"]).first()
        assert u.role == "developer"


def test_promote_user_by_id(temp_user):
    """Verifies promoting a user by ID to developer."""
    result = promote_user(identifier=temp_user["id"], by="id", target_role="developer")
    assert result["success"] is True
    assert result["user_id"] == temp_user["id"]
    assert result["new_role"] == "developer"
    assert result["updated"] is True

    # Check persistence in DB
    with SessionLocal() as db:
        u = db.query(User).filter(User.id == temp_user["id"]).first()
        assert u.role == "developer"


def test_promote_user_idempotent(temp_user):
    """Verifies that running promotion on an already-promoted user is safe and idempotent."""
    promote_user(identifier=temp_user["email"], by="email", target_role="developer")
    second_run = promote_user(identifier=temp_user["email"], by="email", target_role="developer")
    assert second_run["success"] is True
    assert second_run["previous_role"] == "developer"
    assert second_run["new_role"] == "developer"
    assert second_run["updated"] is False
    assert "already has role 'developer'" in second_run["message"]


def test_promote_user_non_existent_email():
    """Verifies appropriate error when user email is not found."""
    with pytest.raises(ValueError, match="User not found"):
        promote_user(identifier="nonexistent_email_12345@example.com", by="email", target_role="developer")


def test_promote_user_invalid_role(temp_user):
    """Verifies rejection of invalid roles."""
    with pytest.raises(ValueError, match="Invalid role"):
        promote_user(identifier=temp_user["email"], by="email", target_role="superhero")


def test_list_users():
    """Verifies that list_users retrieves user records."""
    users = list_users()
    assert isinstance(users, list)
    if users:
        assert "email" in users[0]
        assert "role" in users[0]


def test_cli_execution_by_email(temp_user):
    """Verifies CLI subprocess invocation with --email."""
    proc = subprocess.run(
        [sys.executable, "scripts/promote_developer.py", "--email", temp_user["email"]],
        capture_output=True,
        text=True
    )
    assert proc.returncode == 0
    assert "[SUCCESS] Role Assignment Completed" in proc.stdout
    assert temp_user["email"] in proc.stdout


def test_cli_execution_list():
    """Verifies CLI subprocess invocation with --list."""
    proc = subprocess.run(
        [sys.executable, "scripts/promote_developer.py", "--list"],
        capture_output=True,
        text=True
    )
    assert proc.returncode == 0
    assert "Registered Users" in proc.stdout
