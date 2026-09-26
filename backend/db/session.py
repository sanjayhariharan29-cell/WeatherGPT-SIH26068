import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from pathlib import Path

# Canonical project root directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Database URL configuration (PostgreSQL or SQLite fallback for hackathon MVP)
raw_db_url = os.getenv("DATABASE_URL", "sqlite:///./weathergpt.db")
# Render / Heroku compatibility: SQLAlchemy 2.0+ requires postgresql+psycopg2:// when psycopg2 is installed
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+"):
    raw_db_url = raw_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

if raw_db_url.startswith("sqlite:///") and not raw_db_url.startswith("sqlite:////"):
    after_prefix = raw_db_url[10:]
    if not (len(after_prefix) >= 2 and after_prefix[1] == ":"):
        db_filename = raw_db_url.replace("sqlite:///", "").lstrip("./")
        abs_db_path = (BASE_DIR / db_filename).resolve()
        DATABASE_URL = f"sqlite:///{abs_db_path.as_posix()}"
    else:
        DATABASE_URL = raw_db_url
else:
    DATABASE_URL = raw_db_url

# Ensure parent directory exists for SQLite files (especially on persistent volumes like /data)
if DATABASE_URL.startswith("sqlite:///"):
    try:
        path_part = DATABASE_URL.replace("sqlite:///", "")
        # On Windows, path_part might be C:/path/to/file.db, on Linux /data/file.db
        Path(path_part).parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

# Initialize engine with graceful fallback if PostgreSQL connection/driver fails
try:
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True
    )
    # Validate DBAPI connection immediately
    with engine.connect() as conn:
        pass
except Exception as e:
    import logging
    logging.getLogger("weathergpt.db").warning(
        f"Failed to connect to primary database ({DATABASE_URL}): {e}. Initializing local SQLite fallback."
    )
    fallback_path = (BASE_DIR / "weathergpt.db").resolve()
    DATABASE_URL = f"sqlite:///{fallback_path.as_posix()}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator:
    """Dependency for obtaining a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
