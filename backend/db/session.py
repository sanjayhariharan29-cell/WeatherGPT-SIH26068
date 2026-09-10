import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from pathlib import Path

# Canonical project root directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Database URL configuration (PostgreSQL or SQLite fallback for hackathon MVP)
raw_db_url = os.getenv("DATABASE_URL", "sqlite:///./weathergpt.db")
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

# SQLite specific connect_args
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
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
