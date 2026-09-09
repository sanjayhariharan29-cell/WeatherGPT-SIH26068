"""WeatherGPT Database Backup & Recovery Utility Module.

Provides online atomic SQLite database backups using native sqlite3 backup API,
restore procedures, backup verification, and backup artifact inventory management.
"""

import os
import sqlite3
import shutil
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.config.settings import settings

logger = logging.getLogger("weathergpt.db.backup")


def get_sqlite_db_path() -> str:
    """Extracts local SQLite database file path from DATABASE_URL setting."""
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "")
        return os.path.abspath(path)
    return os.path.abspath("weathergpt.db")


def create_sqlite_backup(
    source_db_path: Optional[str] = None,
    backup_dir: str = "backups"
) -> str:
    """Creates a consistent, online atomic backup snapshot of the SQLite database.
    
    Uses Python's native sqlite3.connect().backup() API to ensure zero table locking
    or connection interruption during live operational queries.
    """
    src_path = os.path.abspath(source_db_path) if source_db_path else get_sqlite_db_path()
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Source database file not found at: {src_path}")

    abs_backup_dir = os.path.abspath(backup_dir)
    os.makedirs(abs_backup_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"weathergpt_backup_{timestamp}.db"
    backup_path = os.path.join(abs_backup_dir, backup_filename)

    # Perform atomic online SQLite backup
    src_conn = sqlite3.connect(src_path)
    dst_conn = sqlite3.connect(backup_path)

    try:
        with dst_conn:
            src_conn.backup(dst_conn)
        logger.info(f"Database online backup successfully created: {backup_path}")
    finally:
        dst_conn.close()
        src_conn.close()

    # Integrity verification
    verify_database_integrity(backup_path)
    return backup_path


def restore_sqlite_backup(
    backup_path: str,
    target_db_path: Optional[str] = None
) -> bool:
    """Restores a verified backup snapshot into the target SQLite database file."""
    abs_backup_path = os.path.abspath(backup_path)
    if not os.path.exists(abs_backup_path):
        raise FileNotFoundError(f"Backup snapshot file not found at: {abs_backup_path}")

    # Integrity verification before restoring
    verify_database_integrity(abs_backup_path)

    dst_path = os.path.abspath(target_db_path) if target_db_path else get_sqlite_db_path()
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    # Perform atomic online restore
    src_conn = sqlite3.connect(abs_backup_path)
    dst_conn = sqlite3.connect(dst_path)

    try:
        with dst_conn:
            src_conn.backup(dst_conn)
        logger.info(f"Database successfully restored from snapshot {abs_backup_path} to {dst_path}")
        return True
    finally:
        dst_conn.close()
        src_conn.close()


def verify_database_integrity(db_path: str) -> bool:
    """Executes PRAGMA quick_check to confirm SQLite database file structural integrity."""
    abs_path = os.path.abspath(db_path)
    conn = sqlite3.connect(abs_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA quick_check")
        result = cursor.fetchone()
        if result and result[0] == "ok":
            return True
        raise ValueError(f"Database integrity check failed for {db_path}: {result}")
    finally:
        conn.close()


def list_backups(backup_dir: str = "backups") -> List[Dict[str, Any]]:
    """Audits and lists all available database backup files in the backup directory."""
    abs_dir = os.path.abspath(backup_dir)
    if not os.path.exists(abs_dir):
        return []

    backups = []
    for fname in sorted(os.listdir(abs_dir), reverse=True):
        if fname.endswith(".db"):
            fpath = os.path.join(abs_dir, fname)
            stat = os.stat(fpath)
            backups.append({
                "filename": fname,
                "path": fpath,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
            })
    return backups
