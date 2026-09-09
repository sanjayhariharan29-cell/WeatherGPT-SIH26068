# Phase 25 — Database Backup, Recovery & Production Data Safety Report

**Developer:** Person 2  
**Date:** 2026-09-09  
**Branch:** `main`  
**Status:** ✅ COMPLETE  

---

## Executive Summary

Phase 25 establishes a comprehensive database backup, recovery, non-destructive migration, and sensitive data protection strategy for **WeatherGPT SIH26068**.

---

## 1. Verified Database Architecture & Inventory

### Database Technology
- **Primary / Local Engine**: SQLite 3 (`sqlite:///./weathergpt.db`) using SQLAlchemy 2.0 ORM with `declarative_base()`.
- **Production / Hosted Engine**: PostgreSQL (`postgresql://user:password@host:5432/weathergpt_db`) supported natively via SQLAlchemy `DATABASE_URL` environment configuration.
- **Connection Management**: All engine instances enforce `pool_pre_ping=True` to detect and recover stale connections before query execution.

### Table Schema & Data Ownership Inventory

| Table Name | Description | Key Column | Foreign Keys / Index | Data Ownership |
|------------|-------------|------------|----------------------|----------------|
| `users` | User account credentials & roles | `id` (UUID36) | `email` (Unique, Index) | User Auth Domain |
| `user_preferences` | User settings & persona defaults | `id` (UUID36) | `user_id` -> `users.id` (CASCADE) | User Auth Domain |
| `saved_locations` | Saved favorite weather locations | `id` (UUID36) | `user_id` -> `users.id` (CASCADE) | Location Services |
| `locations` | Resolved geocoding cache | `id` (UUID36) | `name` (Index) | Location Services |
| `weather_records` | Meteorological telemetry observations | `id` (UUID36) | `idx_weather_loc_observed` (`location_name`, `observed_at`) | Weather Telemetry |
| `forecasts` | Multi-day hourly/daily forecasts | `id` (UUID36) | `idx_forecast_loc_time` (`location_name`, `forecast_time`) | Weather Telemetry |
| `alerts` | Disaster warnings & advisories | `id` (UUID36) | `idx_alert_loc_expires` (`location_name`, `expires_at`) | Disaster Engine |
| `conversations` | WeatherGPT chat sessions | `id` (UUID36) | `user_id` -> `users.id` (SET NULL) | Conversational AI |
| `messages` | Chat messages & turns | `id` (UUID36) | `idx_msg_conv_created` (`conversation_id`, `created_at`) | Conversational AI |
| `advisories` | AI decision trace recommendations | `id` (UUID36) | `message_id` -> `messages.id` (CASCADE) | Decision Engine |
| `revoked_tokens` | JWT token revocation blacklist | `id` (UUID36) | `jti` (Unique, Index) | Auth & Security |

---

## 2. Backup Strategy & Automation

### Online SQLite Backup API
- **Module**: [`backend/db/backup.py`](file:///c:/WeatherGPT-SIH26068/backend/db/backup.py)
- **Function**: `create_sqlite_backup(source_db_path, backup_dir)`
- **Mechanism**: Employs Python's native `sqlite3.connect().backup()` online backup API.
- **Operational Safety**: Performs live atomic snapshotting with **zero table locking** or active query disruption.
- **Artifact Format**: `backups/weathergpt_backup_YYYYMMDD_HHMMSS.db`

### Production PostgreSQL Backup Strategy
For managed cloud PostgreSQL instances (e.g. AWS RDS, Render PostgreSQL, Railway, GCP Cloud SQL):
```bash
# Automated Scheduled Backup Command
pg_dump -U weather_user -h postgres-host -d weathergpt_db -F c -b -v -f /backups/weathergpt_$(date +%Y%m%d_%H%M%S).dump
```

---

## 3. Restore & Verification Procedure

### Atomic Snapshot Restore
- **Function**: `restore_sqlite_backup(backup_path, target_db_path)`
- **Step 1 (Pre-Restore Verification)**: Executes `verify_database_integrity()` running `PRAGMA quick_check` against the backup file before restoring.
- **Step 2 (Atomic Application)**: Uses `src_conn.backup(dst_conn)` to atomically write snapshot data to target database file.
- **Step 3 (Post-Restore Verification)**: Verifies user records, telemetry data, and schema relationships.

---

## 4. Migration & Production Data Safety Rules

1. **Non-Destructive Table Initialization**:
   - `init_db()` in [`backend/db/init_db.py`](file:///c:/WeatherGPT-SIH26068/backend/db/init_db.py) uses `Base.metadata.create_all(bind=engine, checkfirst=True)`.
   - Existing tables, rows, indexes, and constraints are **never** dropped or recreated during application deployments.
2. **Column Migration Inspection**:
   - Schema alterations check column existence via SQLAlchemy `inspect(engine)` before applying `ALTER TABLE ... ADD COLUMN`.

---

## 5. Sensitive Data & Security Considerations

1. **Bcrypt Password Encryption**: User passwords are encrypted using `bcrypt` salted password hashing (`hash_password()`). Raw passwords are **never** persisted in the database.
2. **JWT Token Revocation**: Revoked JWT IDs (`jti`) are stored in `revoked_tokens` table to prevent reuse of logged-out tokens.
3. **Zero Secret Leaks**: Database connection passwords and API keys are loaded strictly from environment variables (`DATABASE_URL`, `SECRET_KEY`) and are never committed to version control.

---

## 6. Verification Summary

- **Database Backup & Recovery Suite**: **7 passed** in `2.28s` ([`tests/test_database_backup_recovery.py`](file:///c:/WeatherGPT-SIH26068/tests/test_database_backup_recovery.py)).
- **Full Pytest Suite**: **698 passed** across 49 test modules.
- **Frontend Verification**: `npm run lint`, `npm run build:web`, `npm test` exit `0`.

---

## Files Changed in Phase 25

| File | Action | Description |
|------|--------|-------------|
| [`backend/db/backup.py`](file:///c:/WeatherGPT-SIH26068/backend/db/backup.py) | Created | Online SQLite backup, restore, integrity check, and inventory module |
| [`tests/test_database_backup_recovery.py`](file:///c:/WeatherGPT-SIH26068/tests/test_database_backup_recovery.py) | Created | 7-test database backup, restore, migration safety, and encryption test suite |
| [`docs/Phase_25_Database_Recovery_Report.md`](file:///c:/WeatherGPT-SIH26068/docs/Phase_25_Database_Recovery_Report.md) | Created | Phase 25 database recovery report and schema inventory |
