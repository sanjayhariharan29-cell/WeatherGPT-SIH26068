import logging
from sqlalchemy import inspect, text
from backend.db.session import engine, Base
from backend.db import models  # Ensure all models are registered

logger = logging.getLogger("weathergpt.db.init_db")

# Table schema migrations: (table_name, column_name, pg_type, sqlite_type)
SCHEMA_MIGRATIONS = [
    # Table: users
    ("users", "role", "VARCHAR(20) DEFAULT 'user'", "VARCHAR(20) DEFAULT 'user'"),
    ("users", "is_verified", "BOOLEAN DEFAULT FALSE", "BOOLEAN DEFAULT 0"),
    ("users", "onboarding_completed", "BOOLEAN DEFAULT FALSE", "BOOLEAN DEFAULT 0"),
    ("users", "verification_token", "VARCHAR(255)", "VARCHAR(255)"),
    ("users", "verification_token_expires", "TIMESTAMP WITH TIME ZONE", "DATETIME"),
    ("users", "reset_token", "VARCHAR(255)", "VARCHAR(255)"),
    ("users", "reset_token_expires", "TIMESTAMP WITH TIME ZONE", "DATETIME"),
    ("users", "phone_number", "VARCHAR(20)", "VARCHAR(20)"),
    ("users", "created_at", "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP"),

    # Table: user_preferences
    ("user_preferences", "preferred_units", "VARCHAR(20) DEFAULT 'metric'", "VARCHAR(20) DEFAULT 'metric'"),
    ("user_preferences", "persona", "VARCHAR(50) DEFAULT 'student'", "VARCHAR(50) DEFAULT 'student'"),
    ("user_preferences", "notification_enabled", "BOOLEAN DEFAULT TRUE", "BOOLEAN DEFAULT 1"),
    ("user_preferences", "daily_sms_enabled", "BOOLEAN DEFAULT TRUE", "BOOLEAN DEFAULT 1"),
    ("user_preferences", "professional_advisory_enabled", "BOOLEAN DEFAULT TRUE", "BOOLEAN DEFAULT 1"),
    ("user_preferences", "severe_alerts_enabled", "BOOLEAN DEFAULT TRUE", "BOOLEAN DEFAULT 1"),
    ("user_preferences", "briefing_time", "VARCHAR(10) DEFAULT '07:00'", "VARCHAR(10) DEFAULT '07:00'"),
    ("user_preferences", "last_known_location", "VARCHAR(100)", "VARCHAR(100)"),
    ("user_preferences", "last_latitude", "FLOAT", "FLOAT"),
    ("user_preferences", "last_longitude", "FLOAT", "FLOAT"),
    ("user_preferences", "last_location_source", "VARCHAR(50) DEFAULT 'manual'", "VARCHAR(50) DEFAULT 'manual'"),
    ("user_preferences", "last_location_updated_at", "TIMESTAMP WITH TIME ZONE", "DATETIME"),
    ("user_preferences", "updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP"),

    # Table: briefing_delivery_logs
    ("briefing_delivery_logs", "message_type", "VARCHAR(20) DEFAULT 'daily'", "VARCHAR(20) DEFAULT 'daily'"),
    ("briefing_delivery_logs", "event_fingerprint", "VARCHAR(64)", "VARCHAR(64)"),
    ("briefing_delivery_logs", "location_name", "VARCHAR(100)", "VARCHAR(100)"),
    ("briefing_delivery_logs", "role", "VARCHAR(50)", "VARCHAR(50)"),
    ("briefing_delivery_logs", "phone_number", "VARCHAR(20)", "VARCHAR(20)"),
    ("briefing_delivery_logs", "risk_level", "VARCHAR(20)", "VARCHAR(20)"),
    ("briefing_delivery_logs", "risk_status_label", "VARCHAR(100)", "VARCHAR(100)"),
    ("briefing_delivery_logs", "delivery_status", "VARCHAR(30) DEFAULT 'MOCK_SMS_DELIVERY'", "VARCHAR(30) DEFAULT 'MOCK_SMS_DELIVERY'"),
    ("briefing_delivery_logs", "data_source", "VARCHAR(100) DEFAULT 'OpenWeather / Open-Meteo / IMD'", "VARCHAR(100) DEFAULT 'OpenWeather / Open-Meteo / IMD'"),
    ("briefing_delivery_logs", "data_freshness", "VARCHAR(20) DEFAULT 'fresh'", "VARCHAR(20) DEFAULT 'fresh'"),
    ("briefing_delivery_logs", "message_text", "TEXT", "TEXT"),
    ("briefing_delivery_logs", "character_count", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0"),
    ("briefing_delivery_logs", "reasoning_bullets", "TEXT", "TEXT"),
    ("briefing_delivery_logs", "error_reason", "VARCHAR(255)", "VARCHAR(255)"),
    ("briefing_delivery_logs", "delivered_at", "TIMESTAMP WITH TIME ZONE", "DATETIME"),
    ("briefing_delivery_logs", "created_at", "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP"),

    # Table: alert_delivery_logs
    ("alert_delivery_logs", "alert_fingerprint", "VARCHAR(64)", "VARCHAR(64)"),
    ("alert_delivery_logs", "channel", "VARCHAR(20) DEFAULT 'fcm'", "VARCHAR(20) DEFAULT 'fcm'"),
    ("alert_delivery_logs", "status", "VARCHAR(20)", "VARCHAR(20)"),
    ("alert_delivery_logs", "reason", "VARCHAR(100)", "VARCHAR(100)"),
    ("alert_delivery_logs", "language", "VARCHAR(10) DEFAULT 'ta'", "VARCHAR(10) DEFAULT 'ta'"),
    ("alert_delivery_logs", "payload_preview", "VARCHAR(255)", "VARCHAR(255)"),
    ("alert_delivery_logs", "delivered_at", "TIMESTAMP WITH TIME ZONE", "DATETIME"),
    ("alert_delivery_logs", "created_at", "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP"),

    # Table: device_tokens
    ("device_tokens", "platform", "VARCHAR(20) DEFAULT 'android'", "VARCHAR(20) DEFAULT 'android'"),
    ("device_tokens", "device_name", "VARCHAR(100)", "VARCHAR(100)"),
    ("device_tokens", "is_active", "BOOLEAN DEFAULT TRUE", "BOOLEAN DEFAULT 1"),
    ("device_tokens", "created_at", "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
    ("device_tokens", "updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
]


def init_db():
    """Create all database tables if they do not exist and apply dialect-safe migrations."""
    logger.info("Running database table creation (create_all)...")
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.error(f"Error during Base.metadata.create_all: {exc}")

    # Inspect existing tables and columns
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        is_postgres = engine.dialect.name == "postgresql"

        # Cache existing columns per table
        table_columns = {}
        for table in existing_tables:
            try:
                table_columns[table] = {col["name"].lower() for col in inspector.get_columns(table)}
            except Exception as e:
                logger.warning(f"Could not inspect columns for table '{table}': {e}")
                table_columns[table] = set()

        for table_name, column_name, pg_type, sqlite_type in SCHEMA_MIGRATIONS:
            if table_name not in existing_tables:
                continue

            existing_cols = table_columns.get(table_name, set())
            if column_name.lower() in existing_cols:
                continue

            col_type = pg_type if is_postgres else sqlite_type
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {col_type}"

            # Execute in an isolated transaction to prevent transaction block aborts
            try:
                with engine.begin() as conn:
                    conn.execute(text(sql))
                logger.info(f"Schema migrated: added {table_name}.{column_name} ({col_type})")
                existing_cols.add(column_name.lower())
            except Exception as add_err:
                logger.warning(f"Could not add column {table_name}.{column_name}: {add_err}")

        # Post-migration fixup: ensure NULL roles are populated
        if "users" in existing_tables:
            try:
                with engine.begin() as conn:
                    conn.execute(text("UPDATE users SET role = 'user' WHERE role IS NULL"))
            except Exception as update_err:
                logger.debug(f"Role update check: {update_err}")

        logger.info("Database schema verification and migrations completed successfully.")
    except Exception as exc:
        logger.error(f"Error during lightweight migration pass: {exc}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Initializing WeatherGPT Database...")
    init_db()
    print("Database initialization complete.")

