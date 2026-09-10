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

---

# 18. Official IMD Alert Engine Lifecycle (Phase 2)

IMD (India Meteorological Department) is the sole authoritative source for official meteorological warnings in SkyZen.

### Alert Lifecycle States:
- **`ACTIVE`**: The current UTC time falls strictly between `valid_from` (or `issued_at`) and `expires_at`.
- **`SCHEDULED`**: The current UTC time is before `valid_from` (advance warning issued for a future time window).
- **`EXPIRED`**: The current UTC time is after `expires_at`. An expired warning is **never** presented as active.
- **`INVALID`**: Alert payload failed deterministic structural validation.

### Deterministic Normalization & Validation:
1. **Source Authority Verification**: Must originate strictly from `IMD`. Payloads from unauthorized sources claiming official status are rejected.
2. **Required Safety-Critical Fields**: `title`, `alert_type`, `severity`, `area`, `issued_at`, and `expires_at` are mandatory. Alerts missing any safety-critical field are rejected with a structured error reason without guessing.
3. **Temporal Sanity**: Enforces strict ISO 8601 UTC timestamp parsing and validates that `expires_at > issued_at` (rejects impossible timestamps or inverted durations).
4. **Deduplication**: Authoritative alert fingerprints are generated via deterministic SHA-256 hashes (`source:alert_type:area:issued_at`) preventing duplicate active records during repeated polling.
5. **Update Detection & Precedence**: If an updated bulletin is received for an existing alert, the engine compares `issued_at` timestamps. Stale/older packets arriving out-of-order cannot overwrite a newer valid bulletin. When severity, description, or instructions are updated, the database record is refreshed and versioned.

---

# 19. Non-Negotiable Alert Safety Invariants & DecisionTrace

The following safety rules are deterministically enforced across the backend and AI safety gate:
1. **Zero Secondary Downgrade**: Secondary weather providers (Open-Meteo, OpenWeather, etc.) reporting clear skies or low rain cannot downgrade or cancel an active IMD warning.
2. **Anti-Hallucination Gate**: The LLM cannot invent phantom official alerts when none exist in ground truth (`FABRICATED_DATA` violation).
3. **Severity Invariance**: The LLM cannot modify or downgrade IMD severity (e.g. claiming a red alert is minor or safe).
4. **Instruction Integrity**: Response guidance must not contradict official IMD emergency instructions (e.g. advising outdoor gatherings or marine ventures during a cyclone warning).
5. **Response Priority Order (Phase 10)**: Official warnings must be presented in strict order: 1. Status -> 2. Area -> 3. Action -> 4. Explanation.
6. **Explainable DecisionTrace**: DecisionTrace captures structured warning facts (`exists`, `source`, `id`, `severity`, `affected_area`, `issued_at`, `valid_from`, `expires_at`, `status`, `validation_state`, `affected_final_recommendation`) without exposing internal chain-of-thought.

---

# 20. Real IMD Data Source Status (Step 14 Audit)

- **Current Implementation**: `backend/services/imd_adapter.py` currently serves deterministic district bulletins (e.g. Nagapattinam coastal storm bulletin, Coimbatore thunderstorm bulletin, and simulated expired notices for automated regression testing) with dynamic UTC validity windows and deterministic SHA-256 fingerprints.
- **Live Feed Prerequisite**: IMD's official Common Alerting Protocol (CAP) and RSS/XML bulletin endpoints require government agency API whitelisting and production credentials.
- **Strict Policy**: In compliance with Step 14, SkyZen **does not** claim live real-time connection to IMD CAP servers until official production credentials and IP whitelisting are provisioned. Under no circumstances are mock endpoints or invented URLs masqueraded as live feeds. All warnings carry explicit provenance and verification status.

---

# 21. Automatic IMD Alert Targeting & Notification Pipeline (Phase 3)

The automated notification pipeline safely routes validated official IMD warnings to affected authenticated users and their registered active devices:

```
IMD Bulletin
    ↓
Validated IMD Alert Engine (Phase 2)
    ↓
Active / Valid Alert Gating (Lifecycle Check: strictly ACTIVE only)
    ↓
Affected Geographic Area Determination (Coordinates <= 60km, District, Zone)
    ↓
User Location Matching (Saved Locations, Default Location, Ownership Isolation)
    ↓
User Notification Preference Check (`UserPreference.notification_enabled`)
    ↓
User Language Selection (`en`, `ta`, `hi`)
    ↓
Update-Aware Deduplication (`source:type:area:severity:issued_at:version`)
    ↓
Multi-Device Selection (`DeviceToken.user_id == user.id, is_active == True`)
    ↓
FCM Dispatch (`NotificationService.send_push_notification`)
    ↓
Android System Notification & In-App Foreground Banner
    ↓
SkyZen Alert / Warning Screen (`navigateToScreen('alerts')`)
```

### Safety & Lifecycle Invariants:
1. **Authoritative Gating**: Only validated `ACTIVE` IMD alerts enter the pipeline. `SCHEDULED` future alerts do not dispatch immediate notifications. `EXPIRED` and `INVALID` alerts are strictly barred from notification dispatch.
2. **Deterministic Targeting**: Relies on Haversine coordinate proximity ($\le 60\text{ km}$), exact district containment, or curated meteorological zones (coastal belt, delta, Nilgiris/Western Ghats). Never uses LLMs or fuzzy guessing to determine affected users.
3. **User Location Ownership Isolation**: Users are targeted strictly based on locations they own (`SavedLocation.user_id == user.id`). No user can trigger or view notifications for another user's private locations.
4. **Multi-Device Support**: Dispatches to all active devices of an eligible user. An invalid or unregistered token deactivates that specific token (`is_active = False`) without blocking sibling devices.
5. **Translation Preservation**: English, Tamil, and Hindi formatting strictly preserves severity (`LOW`, `MEDIUM`, `HIGH`, `EXTREME`), timing, areas, numbers, units, and official instructions. Danger is never softened, invented, or removed.
6. **Non-Destructive FCM Failures**: FCM outages, invalid tokens, or network failures are recorded in `AlertDeliveryLog` as `FAILED`, but **never** delete or suppress the official IMD warning inside SkyZen.
