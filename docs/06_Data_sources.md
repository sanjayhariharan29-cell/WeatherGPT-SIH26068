# WeatherGPT — Data Sources & Data Strategy

## 1. Purpose

This document defines where WeatherGPT obtains weather,
forecast, warning, historical and supporting information.

WeatherGPT must prioritize reliable and authoritative sources.

The system must never invent weather information when
data is unavailable.

---

# 2. Data Categories

WeatherGPT requires the following major data categories:

1. Current weather
2. Weather forecasts
3. Official weather warnings
4. Historical weather
5. Climate information
6. Geographic/location data
7. Weather knowledge and safety guidance
8. User/application data

---

# 3. Primary Meteorological Source — IMD

## India Meteorological Department

IMD should be treated as the primary authoritative source
for official Indian meteorological information wherever
the required data is available.

Potential data:

- Current weather
- Forecasts
- District forecasts
- Rainfall information
- Weather warnings
- Cyclone information
- Severe-weather information
- Meteorological bulletins

### Architecture

Mobile App
    ↓
FastAPI
    ↓
IMD Adapter
    ↓
IMD Data
    ↓
Normalization
    ↓
Weather Reasoner

---

# 4. IMD Adapter

We will NOT allow the rest of the application to depend
directly on IMD-specific formats.

Create an independent:

`IMDAdapter`

Responsibilities:

- Request IMD data
- Parse responses
- Validate data
- Convert data to our common schema
- Handle errors
- Record timestamps
- Handle unavailable endpoints

This allows the data source to be replaced without
changing the rest of the application.

---

# 5. Secondary Forecast Source

A secondary weather provider may be used for:

- Cross-checking forecasts
- Filling non-critical missing information
- Forecast comparison
- Demonstrating multi-source consistency

Candidate:

Open-Meteo

However, the exact provider must be validated before
production use.

---

# 6. Historical Weather Data

Candidate:

NASA POWER

Potential uses:

- Historical temperature
- Historical precipitation
- Climate analysis
- Long-term trends
- Historical comparisons

Historical data must be clearly separated from
real-time forecast information.

---

# 7. Multi-Source Comparison

Where appropriate, WeatherGPT may compare multiple
forecast sources.

Example:

IMD → Rain likely
Source B → Rain likely
Source C → Rain possible

↓

WeatherGPT:

"Forecast sources broadly agree that rain is possible."

If sources disagree:

"Forecast sources currently show disagreement."

IMPORTANT:

This is a source-consistency analysis.

It must NOT be presented as a scientifically
calibrated forecast probability.

---

# 8. Official Warning Data

Official warnings must receive the highest priority.

Potential warning information:

- Heavy rainfall
- Cyclone
- Thunderstorm
- Lightning
- Strong winds
- Heatwave
- Other severe weather

Processing:

Official Warning
      ↓
Validation
      ↓
Severity
      ↓
Location Matching
      ↓
User Notification
      ↓
AI Explanation

The LLM must never override an official warning.

---

# 9. Location Data

WeatherGPT requires location information.

Sources:

### A. Device GPS

Used when the user grants location permission.

### B. Manual Search

User searches for:

"Coimbatore"

### C. Conversational Location

Example:

"Weather there tomorrow?"

The system uses the previously identified
location when context is clear.

---

# 10. Geocoding

User location names must be converted into:

- Latitude
- Longitude
- Administrative region

Example:

Coimbatore
    ↓
Latitude
Longitude
District
State

The exact geocoding provider will be selected
after testing.

---

# 11. Weather Knowledge Base

The RAG system may contain trusted supporting
knowledge such as:

- Weather terminology
- Meteorological concepts
- Official safety guidance
- Disaster-management guidance
- Approved advisory information
- Definitions of weather alerts

This information is used for explanation.

IMPORTANT:

The knowledge base must NOT be treated as a source
of current weather conditions.

Current weather must come from live/verified
meteorological data.

---

# 12. User Data

The database may store:

### User

- User ID
- Name/optional display name
- Preferred language
- Location preference

### Preferences

- Preferred units
- Preferred language
- Notification settings
- Persona

### Persona

Possible values:

- Student
- Farmer
- Fisherman
- Traveller
- Disaster Response

Only necessary personal information should be stored.

---

# 13. Weather Data Schema

All external weather sources should eventually
be converted into a common internal structure.

Example:

```json
{
  "location": {
    "name": "Coimbatore",
    "latitude": 11.0168,
    "longitude": 76.9558
  },
  "observed_at": "2026-09-08T10:00:00Z",
  "temperature": 29.0,
  "humidity": 72.0,
  "rain_probability": 65.0,
  "wind_speed": 18.0,
  "weather_condition": "Rain",
  "source": "IMD",
  "retrieved_at": "2026-09-08T10:05:00Z",
  "freshness_status": "FRESH",
  "completeness_status": "COMPLETE",
  "provider_status": "HEALTHY",
  "validation_status": "VALID"
}
```

---

# 14. Data Reliability & Freshness Model (Phase 1)

Every meteorological observation distinguishes **station observation timestamp (`observed_at`)** from **backend retrieval timestamp (`retrieved_at`)**. Old cached data is never described as "real-time".

### Freshness Classification:
1. **`FRESH`**: Observation timestamp is $< 60$ minutes old.
2. **`AGING`**: Observation timestamp is between $60$ and $180$ minutes old (acceptable operational telemetry).
3. **`STALE`**: Observation timestamp exceeds $180$ minutes.
4. **`UNAVAILABLE`**: Observation timestamp missing, unparseable, or payload empty.

Cache awareness: responses served from the internal TTL cache carry `is_cached=True` and `cache_age_seconds`. Observations $>15$ minutes old or served from cache are explicitly marked `is_real_time=False`.

---

# 15. Completeness & Physical Boundary Validation

Observations undergo deterministic range and physical consistency validation:
- **Latitude**: $-90.0^\circ$ to $+90.0^\circ$
- **Longitude**: $-180.0^\circ$ to $+180.0^\circ$
- **Temperature**: $-90.0^\circ\text{C}$ to $+60.0^\circ\text{C}$
- **Humidity**: $0.0\%$ to $100.0\%$
- **Wind Speed**: $0.0$ to $400.0\text{ km/h}$
- **Rain Probability**: $0.0\%$ to $100.0\%$
- **Atmospheric Pressure**: $800.0$ to $1100.0\text{ hPa}$ (when present)

### Completeness Classification:
- **`COMPLETE`**: All required and core fields are present and physically valid.
- **`PARTIAL`**: Core observations present (temperature, condition), but secondary metrics (e.g. pressure, wind direction) omitted without halting the pipeline.
- **`INVALID`**: Values violate physical boundaries or impossible numbers.
- **`UNAVAILABLE`**: Primary data payload missing or empty.

---

# 16. Multi-Source Disagreement & Averaging Policy

When primary (IMD) and secondary (Open-Meteo) providers return differing values:
1. **Zero Blind Averaging**: The system **never** averages divergent metrics (e.g. IMD $32^\circ\text{C}$ and Open-Meteo $24^\circ\text{C}$ are **never** averaged to $28^\circ\text{C}$).
2. **Preserve Individual Values**: Both `primary_temperature` and `secondary_temperature` are preserved in `ComparisonDataSchema`.
3. **Canonical Agreement Reasoner**: Divergence is classified via `ai/reasoner/agreement.py` (`HIGH`, `MEDIUM`, `CAUTIOUS`), reporting explicit delta diagnostics to the user.

---

# 17. Provider Failure & IMD Authority Invariant

1. **Failure Isolation**: Provider errors (`ProviderTimeoutError`, `ProviderUnavailableError`, etc.) capture rich diagnostics (`status_code`, `timeout`, `url`, `error_type`) without corrupting valid data from secondary providers.
2. **IMD Warning Authority**: Official severe weather alerts from IMD unconditionally govern overall hazard levels and emergency precautions. Secondary providers (Open-Meteo, Tomorrow.io, etc.) cannot override, downgrade, or clear an official IMD warning.