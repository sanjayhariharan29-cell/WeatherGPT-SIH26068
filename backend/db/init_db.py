from backend.db.session import engine, Base
from backend.db import models # Ensure all models are registered

from sqlalchemy import inspect, text

def init_db():
    """Create all database tables if they do not exist and apply lightweight migrations."""
    Base.metadata.create_all(bind=engine)

    # Lightweight SQLite column migration for role column
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            if "users" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("users")]
                if "role" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))
                    conn.commit()
    except Exception:
        pass

if __name__ == "__main__":
    print("Initializing WeatherGPT Database...")
    init_db()
    print("Database initialization complete.")
