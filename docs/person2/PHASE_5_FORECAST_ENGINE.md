# WeatherGPT — SIH26068: Person 2 Phase 5 Forecast Engine Report

**Date:** 2026-09-08  
**Repository:** `WeatherGPT-SIH26068`  
**Branch:** `main`  
**Author:** Person 2 (Backend / Database / Weather Data / Mobile / Deployment)  
**Status:** COMPLETE  

---

## 1. Executive Summary
Phase 5 implements a robust, normalized, and multi-granularity Forecast Engine for WeatherGPT. The engine supports hourly sub-daily forecasts and aggregated daily summaries (min/max temperatures, peak rain probability, total daily precipitation, max wind speed), strict numeric coordinate validation (-90 to +90 lat, -180 to +180 lon), primary-to-secondary provider failover (IMD primary -> Open-Meteo fallback), explicit time semantics (`issued_at` vs `forecast_for` target timestamps in ISO 8601 UTC), database snapshotting into `Forecast` (`forecasts`) with deduplication, seamless conversion to Person 1's AI models (`AIForecastItem`), and OpenAPI response contract compliance (`ForecastResponse`).

---

## 2. Forecast Engine Architecture & Service Layer
- **Dedicated Service Layer (`ForecastService`):** Located in `backend/services/forecast_service.py`, encapsulating coordinate validation, hourly forecast normalization, daily aggregation, provider failover, database persistence, and AI model conversion.
- **Hourly & Daily Multi-Granularity:**
  - **Hourly Forecast:** Normalized sub-daily forecast items returning `forecast_time`, `forecast_for`, `temperature`, `rain_probability`, `rainfall_mm`, `wind_speed`, `condition`, `source`, `issued_at`, and `retrieved_at`.
  - **Daily Forecast:** Aggregated daily summaries returning `date` (YYYY-MM-DD), `temperature_min`, `temperature_max`, `rain_probability` (peak), `total_rainfall_mm`, `max_wind_speed`, `condition` (dominant condition), `source`, and `issued_at`.
- **Time Semantics & Provenance:**
  - `issued_at`: Timestamp when the forecast model was executed/issued by the meteorological authority.
  - `forecast_for`: ISO 8601 UTC target timestamp representing the future forecast window.
  - `retrieved_at`: Timestamp when data was retrieved by WeatherGPT.
- **Provider Failover Strategy:** Primary forecast is requested from `IMDAdapter`. If IMD raises a `ProviderError` or network failure occurs, the engine automatically fails over to `OpenMeteoAdapter`, tagging the response source accurately (`Open-Meteo (Fallback)`).
- **Database Snapshotting & Deduplication:** When a database session is provided, forecast items are saved to `Forecast` (`forecasts`). The engine checks if a record for the same location and target forecast time (`forecast_time`) exists, preventing redundant database rows.
- **Person 1 AI Integration:** `ForecastService.get_ai_forecast_items()` produces a list of valid `AIForecastItem` Pydantic models for Person 1's Weather Reasoner without altering AI reasoning logic.

---

## 3. Standardized Units Matrix

| Forecast Metric | Standardized Unit | Pydantic Schema Key |
|---|---|---|
| Temperature | °C (Celsius) | `temperature` / `temp_min` / `temp_max` |
| Relative Humidity | % (Percentage) | `humidity` |
| Rain Probability | % (Percentage) | `rain_probability` |
| Wind Speed | km/h (Kilometers per hour) | `wind_speed` / `max_wind_speed` |
| Rainfall Amount | mm (Millimeters) | `rainfall_mm` / `total_rainfall_mm` |

---

## 4. API Endpoint Contract
- **Endpoint:** `GET /api/v1/weather/forecast`
- **Query Parameters:**
  - `lat` (Optional float, -90.0 to +90.0)
  - `lon` (Optional float, -180.0 to +180.0)
  - `location` (String, default: "Coimbatore")
  - `days` (Integer 1-7, default: 7)
- **Validation Errors:** Returns `HTTP 400 Bad Request` if coordinates exceed valid geographical boundaries.

---

## 5. Files Created & Modified
- [backend/schemas/__init__.py](file:///c:/WeatherGPT-SIH26068/backend/schemas/__init__.py)
- [backend/schemas/weather.py](file:///c:/WeatherGPT-SIH26068/backend/schemas/weather.py)
- [backend/services/forecast_service.py](file:///c:/WeatherGPT-SIH26068/backend/services/forecast_service.py)
- [backend/services/weather_manager.py](file:///c:/WeatherGPT-SIH26068/backend/services/weather_manager.py)
- [backend/services/__init__.py](file:///c:/WeatherGPT-SIH26068/backend/services/__init__.py)
- [backend/api/weather.py](file:///c:/WeatherGPT-SIH26068/backend/api/weather.py)
- [tests/test_forecast_engine.py](file:///c:/WeatherGPT-SIH26068/tests/test_forecast_engine.py)
- [docs/person2/PHASE_5_FORECAST_ENGINE.md](file:///c:/WeatherGPT-SIH26068/docs/person2/PHASE_5_FORECAST_ENGINE.md)

---

## 6. Test Results
Executed `python -m pytest`:
- **139 passed, 0 failed, 1 warning in 9.03s** (100% pass rate across 15 test suites).

---

## 7. Intentionally Left Untouched
- Official disaster alert engine & emergency warnings (Preserved for Phase 6).
- Person 1's AI reasoning engines (`ai/`) (Preserved completely).

---

## 8. Next Recommended Phase
- **Phase 6 — Official Warnings & Alerts Engine**
