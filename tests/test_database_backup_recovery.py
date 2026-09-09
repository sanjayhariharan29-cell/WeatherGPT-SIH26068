"""Phase 25 — Database Backup, Recovery & Data Safety Test Suite.

Verifies online SQLite database backup creation, snapshot integrity, atomic database restore,
non-destructive table migrations (init_db), bcrypt password hash security, and JWT revocation tracking.
"""

import os
import shutil
import pytest
from sqlalchemy.orm import Session

from backend.db.session import engine, Base, SessionLocal
from backend.db.models import User, WeatherRecord, Conversation, RevokedToken, generate_uuid
from backend.db.init_db import init_db
from backend.db.backup import (
    create_sqlite_backup,
    restore_sqlite_backup,
    verify_database_integrity,
    list_backups,
    get_sqlite_db_path
)
from backend.core.security import hash_password, verify_password


@pytest.fixture(autouse=True)
def setup_test_database():
    """Ensures test database tables exist before each test."""
    init_db()


# =============================================================================
# 1. DATABASE BACKUP & INTEGRITY
# =============================================================================
def test_01_create_sqlite_backup_and_integrity_check(tmp_path):
    """Verifies create_sqlite_backup creates a valid SQLite backup snapshot."""
    backup_dir = str(tmp_path / "backups")
    backup_path = create_sqlite_backup(backup_dir=backup_dir)

    assert os.path.exists(backup_path)
    assert os.path.getsize(backup_path) > 0
    assert verify_database_integrity(backup_path) is True


# =============================================================================
# 2. DATABASE RESTORE & DATA PARITY
# =============================================================================
def test_02_restore_sqlite_backup_and_data_parity(tmp_path):
    """Verifies restore_sqlite_backup accurately restores data from a backup snapshot."""
    db_session: Session = SessionLocal()
    unique_email = f"backup_user_{generate_uuid()[:8]}@example.com"
    try:
        # Create a test user record
        test_user = User(
            name="Backup Test User",
            email=unique_email,
            password_hash=hash_password("Secret123!"),
            role="user"
        )
        db_session.add(test_user)
        db_session.commit()

        # Create database backup
        backup_dir = str(tmp_path / "backups")
        backup_path = create_sqlite_backup(backup_dir=backup_dir)

        # Mutate current DB (delete user)
        db_session.delete(test_user)
        db_session.commit()
        assert db_session.query(User).filter(User.email == unique_email).first() is None
    finally:
        db_session.close()

    # Restore from backup snapshot
    target_db = get_sqlite_db_path()
    success = restore_sqlite_backup(backup_path, target_db_path=target_db)
    assert success is True

    # Verify user record restored
    verify_session: Session = SessionLocal()
    try:
        restored_user = verify_session.query(User).filter(User.email == unique_email).first()
        assert restored_user is not None
        assert restored_user.name == "Backup Test User"
        assert verify_password("Secret123!", restored_user.password_hash) is True
    finally:
        verify_session.close()


# =============================================================================
# 3. NON-DESTRUCTIVE MIGRATION SAFETY
# =============================================================================
def test_03_init_db_non_destructive_execution():
    """Verifies running init_db() against a populated database does not drop or alter existing records."""
    db: Session = SessionLocal()
    unique_email = f"migration_user_{generate_uuid()[:8]}@example.com"
    try:
        test_user = User(
            name="Migration Test User",
            email=unique_email,
            password_hash=hash_password("SafePassword123!"),
            role="user"
        )
        db.add(test_user)
        db.commit()

        # Re-run database initialization
        init_db()

        # Verify user record still exists intact
        user_after = db.query(User).filter(User.email == unique_email).first()
        assert user_after is not None
        assert user_after.name == "Migration Test User"
    finally:
        db.close()


# =============================================================================
# 4. PASSWORD HASHING & DATA PROTECTION
# =============================================================================
def test_04_password_hash_security():
    """Verifies passwords are encrypted using bcrypt and raw passwords are never stored."""
    raw_pwd = "MySuperSecretPassword2026!"
    hashed = hash_password(raw_pwd)

    assert raw_pwd not in hashed
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


# =============================================================================
# 5. JWT REVOCATION LIST PERSISTENCE
# =============================================================================
def test_05_jwt_revocation_list_persistence():
    """Verifies RevokedToken model records and persists revoked JWT token identifiers (JTI)."""
    db: Session = SessionLocal()
    test_jti = f"jti_{generate_uuid()}"
    try:
        revoked = RevokedToken(jti=test_jti)
        db.add(revoked)
        db.commit()

        found = db.query(RevokedToken).filter(RevokedToken.jti == test_jti).first()
        assert found is not None
        assert found.jti == test_jti
    finally:
        db.close()


# =============================================================================
# 6. BACKUP INVENTORY & AUDITING
# =============================================================================
def test_06_list_backups_inventory(tmp_path):
    """Verifies list_backups correctly lists metadata for available backup files."""
    backup_dir = str(tmp_path / "backups")
    create_sqlite_backup(backup_dir=backup_dir)

    inventory = list_backups(backup_dir=backup_dir)
    assert len(inventory) > 0
    assert "filename" in inventory[0]
    assert "size_bytes" in inventory[0]
    assert inventory[0]["size_bytes"] > 0


# =============================================================================
# 7. INVALID BACKUP ERROR HANDLING
# =============================================================================
def test_07_invalid_backup_restore_failure():
    """Verifies restoring a non-existent or corrupted backup file raises an appropriate exception."""
    with pytest.raises(FileNotFoundError):
        restore_sqlite_backup("/non_existent_path/invalid_backup.db")
