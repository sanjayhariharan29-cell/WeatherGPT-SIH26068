from backend.db.session import engine, Base
from backend.db import models # Ensure all models are registered

from sqlalchemy import inspect, text

def init_db():
    """Create all database tables if they do not exist and apply lightweight migrations."""
    Base.metadata.create_all(bind=engine)

    # Lightweight SQLite column migration for role and auth columns
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            if "users" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("users")]
                if "role" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))
                if "is_verified" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0"))
                if "verification_token" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN verification_token VARCHAR(255)"))
                if "verification_token_expires" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN verification_token_expires DATETIME"))
                if "reset_token" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN reset_token VARCHAR(255)"))
                if "reset_token_expires" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN reset_token_expires DATETIME"))
                conn.commit()
    except Exception:
        pass

if __name__ == "__main__":
    print("Initializing WeatherGPT Database...")
    init_db()
    print("Database initialization complete.")
