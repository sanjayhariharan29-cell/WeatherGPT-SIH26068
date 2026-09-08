# WeatherGPT — SIH26068: Person 2 Phase 2 Database Foundation Report

**Date:** 2026-09-08  
**Repository:** `WeatherGPT-SIH26068`  
**Branch:** `main`  
**Author:** Person 2 (Backend / Database / Weather Data / Mobile / Deployment)  
**Status:** COMPLETE  

---

## 1. Executive Summary
Phase 2 Database Foundation establishes a hardened, validated, and indexed relational database layer for WeatherGPT using SQLAlchemy 2.0 ORM (`backend/db/models.py`), supporting both SQLite (local development/MVP) and PostgreSQL (production).

---

## 2. Relational Database Models & Schema
All 9 core entities required by the system are fully defined and validated:
1. **`User` (`users`):** Stores user ID (UUID), name, unique email, SHA-256 password hash, preferred language, default persona, and timezone-aware `created_at`.
2. **`UserPreference` (`user_preferences`):** Stores user settings (units, persona, notification flags) linked with cascading foreign key `ondelete="CASCADE"`.
3. **`Location` (`locations`):** Stores geographic metadata with latitude validation (-90 to +90) and longitude validation (-180 to +180).
4. **`WeatherRecord` (`weather_records`):** Stores current observations with indexed composite (`location_name`, `observed_at`) and validation.
5. **`Forecast` (`forecasts`):** Distinguishes forecast target time (`forecast_time`) from retrieval time (`retrieved_at`) with composite index (`location_name`, `forecast_time`).
6. **`Alert` (`alerts`):** Stores official disaster warnings with severity index and expiration tracking (`location_name`, `expires_at`).
7. **`Conversation` (`conversations`):** Tracks chat sessions linked to `User` (`ondelete="SET NULL"`).
8. **`Message` (`messages`):** Stores chat history with intent, language, risk level, and composite index (`conversation_id`, `created_at`) with cascading deletion.
9. **`Advisory` (`advisories`):** Stores persona-tailored actionable recommendations linked to `Message` with cascading deletion.

---

## 3. Key Enhancements Implemented in Phase 2
- **Coordinate Validation:** Added `@validates` validators preventing illegal latitude (< -90 or > 90) or longitude (< -180 or > 180) inputs.
- **Index Optimization:** Added composite indexes (`idx_weather_loc_observed`, `idx_forecast_loc_time`, `idx_alert_loc_expires`, `idx_msg_conv_created`) to optimize query speeds.
- **Cascading Foreign Keys:** Explicit `ondelete="CASCADE"` rules ensuring referential integrity without destroying global historical weather records.
- **Timezone Awareness:** All datetime fields default to UTC timezone awareness via `datetime.now(timezone.utc)`.
- **Database Foundation Test Suite (`tests/test_db_foundation.py`):** Added 5 unit tests covering validation errors, timezone awareness, cascading deletions, and index verification.

---

## 4. Files Created & Modified
- [backend/db/models.py](file:///c:/WeatherGPT-SIH26068/backend/db/models.py)
- [tests/test_db_foundation.py](file:///c:/WeatherGPT-SIH26068/tests/test_db_foundation.py)
- [docs/person2/PHASE_2_DATABASE_FOUNDATION.md](file:///c:/WeatherGPT-SIH26068/docs/person2/PHASE_2_DATABASE_FOUNDATION.md)

---

## 5. Test Results
Executed `python -m pytest`:
- **81 passed, 0 failed, 1 warning in 11.16s** (100% pass rate across 11 test suites).

---

## 6. Intentionally Left Untouched
- Weather adapter provider implementation (Preserved for Phase 3).
- Person 1's AI engine (`ai/`) (Preserved completely).
