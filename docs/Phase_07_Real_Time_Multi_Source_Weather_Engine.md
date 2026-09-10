# Phase 7 — SkyZen Real-Time Multi-Source Weather Engine

## 1. Overview & Architecture

SkyZen's Real-Time Multi-Source Weather Engine is designed to ingest real meteorological data from multiple independent providers, normalize observations into a canonical schema, compute strict provenance, evaluate freshness and completeness, assess cross-provider agreement deterministically, and feed verified data directly to the SkyZen intelligence pipeline without blind averaging or synthetic hallucination.

```
REAL PROVIDERS (Open-Meteo, OpenWeather, IMD)
       ↓
Provider Adapters (Isolated failure boundaries)
       ↓
Source Manager / CurrentWeatherService
       ↓
Validation & Normalization (Canonical Schema)
       ↓
Freshness & Completeness Check
       ↓
Provider Agreement (Deterministic, No Blind Averaging)
       ↓
Authority Hierarchy Enforcement (Official IMD Warnings Overrule)
       ↓
DecisionTrace / Reasoner / AI Pipeline / UI
```

---

## 2. Provider Classification & Reality Check

Every provider integrated into SkyZen is explicitly classified. Provider status is never misrepresented:

| Provider | Integration Type | Current Status | Authority Level | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Open-Meteo** | Live HTTP REST API | **LIVE** | Secondary Independent (`secondary`) | Live API requests to `https://api.open-meteo.com/v1/forecast` fetching real-time temperature, apparent temperature, humidity, surface pressure, wind speed, wind direction, and WMO weather codes. No API key required. |
| **OpenWeather** | Live HTTP REST API | **CONFIGURABLE** | Secondary Independent (`secondary`) | Live API requests to `https://api.openweathermap.org/data/2.5/weather`. Requires `OPENWEATHER_API_KEY` configured in `backend/.env`. When unconfigured, reports `LIVE PROVIDER CREDENTIALS NOT CONFIGURED` and fails gracefully. |
| **IMD (India Meteorological Department)** | Official Government Warning & Observation Gateway | **CONFIGURABLE / FIXTURE** | Primary Authoritative (`primary_authoritative`) | When live official endpoint credentials (`IMD_API_KEY` / `IMD_BASE_URL`) are provided, performs live authenticated fetch. When credentials/network access are not configured, reports `IMD LIVE ACCESS NOT CONFIGURED` and operates within an explicit deterministic reference boundary. **Official IMD alerts and warnings remain strictly authoritative.** |

---

## 3. Authority Hierarchy

The system enforces a deterministic authority hierarchy:

```
OFFICIAL IMD WARNINGS
       >
VERIFIED LIVE WEATHER DATA
       >
DETERMINISTIC REASONER
       >
HAZARD ENGINE
       >
ADVISORY
       >
RAG
       >
LLM LANGUAGE
```

### Safety Principles:
1. **IMD Sole Warning Authority**: Secondary providers (Open-Meteo, OpenWeather) NEVER issue or overwrite official government warnings. Their alert arrays remain empty (`[]`).
2. **No False IMD Labeling**: Secondary provider data is never relabeled as IMD data.
3. **No Synthetic Live Data**: Fallback or fixture data is never presented as `is_real_time: true`.
4. **LLM Invariant**: The LLM is never permitted to choose which provider is correct, nor to fabricate missing sensor metrics.

---

## 4. Canonical Schema & Provenance

Each provider's observation is normalized without inventing values:
- `provider`: Provider identifier (`imd`, `open-meteo`, `openweather`)
- `source`: Display label (`IMD`, `Open-Meteo`, `OpenWeather`)
- `latitude` & `longitude`: Exact queried coordinates
- `temperature`, `feels_like`, `humidity`, `pressure`, `wind_speed`, `wind_direction`, `precipitation`, `precipitation_probability`, `weather_condition`, `visibility`: Metric units. Unprovided fields remain `None` / `null` rather than fabricated.
- `observed_at`: Exact timestamp provided by the source station/model.
- `fetched_at`: UTC timestamp when SkyZen retrieved the observation.
- `age_minutes`: Elapsed duration from observation to retrieval.
- `freshness`: `FRESH` (≤ 60m), `STALE` (60m–180m), or `EXPIRED` (> 180m).
- `completeness`: `COMPLETE` (all core fields present), `PARTIAL` (some present), or `INCOMPLETE`.
- `is_real_time`: Boolean flag set only when fetched from live endpoints.

---

## 5. Provider Agreement & Conflict Handling

SkyZen compares compatible variables (temperature, humidity, wind, pressure) across fresh provider responses without blindly averaging them:

- **High Agreement**: Providers differ by ≤ 2.0°C in temperature and have consistent conditions. Confidence is marked `HIGH`.
- **Moderate Agreement**: Providers differ by ≤ 4.0°C. Confidence is marked `MODERATE`.
- **Disagreement / Conflict**: When temperature variance exceeds 4.0°C or conditions contradict materially (e.g., Heavy Rain vs Clear):
  - Disagreement is explicitly exposed in `agreement.notes` (`"High variance between providers: ..."`).
  - Confidence is marked `CAUTIOUS` or `LOW`.
  - Individual provider observations are preserved intact in `provider_records`.
  - Authoritative IMD observation is prioritized for the primary display while the UI and Reasoner present the conflict transparently to the user.

---

## 6. Offline, Degraded, and Error States

In accordance with Phase 4 resiliency architecture:
- **ONLINE**: All configured providers respond successfully with fresh observations.
- **DEGRADED**: One provider fails or times out, but at least one verified live provider succeeds (e.g. Open-Meteo is live while OpenWeather is unconfigured). The app continues operating with source transparency.
- **SERVICE_UNAVAILABLE**: All providers fail and no cache is available.
- **DATA_STALE**: Network unavailable, cached data served with stale indicators.

---

## 7. Security & Credential Isolation

- Provider API keys (`OPENWEATHER_API_KEY`, `IMD_API_KEY`) reside exclusively in backend server environments (`backend/.env`).
- Provider secrets are never passed to:
  - Frontend client JavaScript bundles (`frontend/app.js`)
  - Android assets or Capacitor configurations
  - Client-facing API responses or telemetry logs
- The frontend receives only normalized weather records, source names, and agreement status.

---

## 8. Live Weather Smoke Testing

SkyZen includes a dedicated CLI smoke test tool to verify real provider connectivity on demand:

```powershell
python backend/scripts/live_weather_smoke.py
```

### Smoke Test Output Sample:
```
============================================================
SKYZEN REAL-TIME MULTI-SOURCE WEATHER SMOKE TEST
============================================================
Target Location: Coimbatore (Lat: 11.0168, Lon: 76.9558)

1. Testing Provider: Open-Meteo (Real-Time API)...
   Status: PASS [HTTP 200]
   Temperature: 25.2°C (Feels like: None°C)
   Humidity: 50.0% | Wind: 10.7 km/h | Condition: Overcast
   Observed At: 2026-09-10T16:45Z (Age: 12m, Freshness: FRESH)
   Completeness: COMPLETE | Validation: VALID

2. Testing Provider: OpenWeather (Configurable Live API)...
   Status: LIVE PROVIDER CREDENTIALS NOT CONFIGURED
   Notice: Set OPENWEATHER_API_KEY in backend/.env to activate live requests.

3. Testing Provider: IMD (India Meteorological Department)...
   Status: IMD LIVE ACCESS NOT CONFIGURED
   Notice: Authorized IMD endpoint key not present. Operating in deterministic reference boundary.
   Deterministic Fixture Value: 29.0°C (Moderate Rain)
   Authority: primary_authoritative (Official Warnings Authoritative)

============================================================
SMOKE TEST COMPLETE: Zero secrets exposed in output.
============================================================
```
