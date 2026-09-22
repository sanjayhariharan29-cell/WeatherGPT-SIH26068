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
                # Ensure all existing users have role set to 'user' if NULL
                conn.execute(text("UPDATE users SET role = 'user' WHERE role IS NULL"))
                if "is_verified" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0"))
                if "onboarding_completed" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0"))
                if "verification_token" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN verification_token VARCHAR(255)"))
                if "verification_token_expires" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN verification_token_expires DATETIME"))
                if "reset_token" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN reset_token VARCHAR(255)"))
                if "reset_token_expires" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN reset_token_expires DATETIME"))
                if "phone_number" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN phone_number VARCHAR(20)"))

            if "user_preferences" in inspector.get_table_names():
                pref_columns = [c["name"] for c in inspector.get_columns("user_preferences")]
                if "notification_enabled" not in pref_columns:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN notification_enabled BOOLEAN DEFAULT 1"))
                if "daily_sms_enabled" not in pref_columns:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN daily_sms_enabled BOOLEAN DEFAULT 1"))
                if "professional_advisory_enabled" not in pref_columns:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN professional_advisory_enabled BOOLEAN DEFAULT 1"))
                if "severe_alerts_enabled" not in pref_columns:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN severe_alerts_enabled BOOLEAN DEFAULT 1"))
                if "briefing_time" not in pref_columns:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN briefing_time VARCHAR(10) DEFAULT '07:00'"))
                if "last_known_location" not in pref_columns:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN last_known_location VARCHAR(100)"))
                if "last_latitude" not in pref_columns:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN last_latitude FLOAT"))
                if "last_longitude" not in pref_columns:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN last_longitude FLOAT"))
                if "last_location_source" not in pref_columns:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN last_location_source VARCHAR(50) DEFAULT 'manual'"))
                if "last_location_updated_at" not in pref_columns:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN last_location_updated_at DATETIME"))

            if "briefing_delivery_logs" in inspector.get_table_names():
                log_columns = [c["name"] for c in inspector.get_columns("briefing_delivery_logs")]
                if "event_fingerprint" not in log_columns:
                    conn.execute(text("ALTER TABLE briefing_delivery_logs ADD COLUMN event_fingerprint VARCHAR(64)"))

            conn.commit()
    except Exception:
        pass

if __name__ == "__main__":
    print("Initializing WeatherGPT Database...")
    init_db()
    print("Database initialization complete.")
