# SkyZen Phase 27: NWP / GFS / WRF Integration Readiness

## Executive Summary
SkyZen Phase 27 establishes the Numerical Weather Prediction (NWP) integration architecture, preparing SkyZen to ingest, normalize, and reason over global and mesoscale atmospheric models—specifically NOAA's **Global Forecast System (GFS)** and India's MoES/NCMRWF **Weather Research and Forecasting (WRF)** models.

This readiness layer is built with strict adherence to two cardinal principles:
1. **The Strict Non-Averaging Principle**: Numerical weather models operate on distinct dynamical cores and parameterizations; they are never blended or arithmetically averaged.
2. **Authoritative Safety Precedence**: Official India Meteorological Department (IMD) warnings take unconditional priority over all model simulations and can never be downgraded by numerical predictions.

---

## Architecture & Components

```
+-----------------------------------------------------------------------------------+
|                            SkyZen WeatherManager                                  |
+-----------------------------------------------------------------------------------+
        |                                                   |
        v                                                   v
+-------------------------------+           +-------------------------------+
|      Observation Pipeline     |           |     NWP Integration Pipeline  |
|  - OpenWeather (Primary Live) |           |  - GFSProvider (NOAA NCEP)    |
|  - Open-Meteo (Secondary)     |           |  - WRFProvider (Regional)     |
|  - IMD Alerts (Authoritative) |           |  - DeterministicNWPProvider   |
+-------------------------------+           +-------------------------------+
        |                                                   |
        +-------------------------+-------------------------+
                                  |
                                  v
                    +---------------------------+
                    |    NWPComparisonEngine    |
                    | (Strictly Non-Averaged)   |
                    | - Discrete Model Spreads  |
                    | - Divergence Detection    |
                    +---------------------------+
                                  |
                                  v
                    +---------------------------+
                    |      WeatherReasoner      |
                    | - IMD Alert Priority      |
                    | - Model Provenance Track  |
                    | - Advisory Hazard Signal  |
                    +---------------------------+
```

### 1. Generic NWP Provider Contract (`BaseNWPProvider`)
Located in [`backend/services/nwp_provider.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/backend/services/nwp_provider.py), inheriting from `BaseWeatherProvider`:
- Abstract property `model_name -> NWPModelName`
- Authority level: `"nwp_model_guidance"`
- Status tracking: `NOT_CONFIGURED` when unconfigured, `HEALTHY` when configured
- Methods: `fetch_model_forecast()`, `fetch_nwp_forecast()`, `get_model_metadata()`

### 2. GFS & WRF Adapters
- **`GFSProvider`**: Configured for 0.25° GFS global model runs (00Z, 06Z, 12Z, 18Z).
- **`WRFProvider`**: Configured for regional high-resolution 3km–9km mesoscale model outputs.
- **`DeterministicNWPProvider`**: Predictable test harness allowing offline execution and deterministic mock testing.

### 3. NWP Schemas & Metadata Retention
Located in [`backend/services/nwp_schemas.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/backend/services/nwp_schemas.py):
- **`NWPModelName`**: Enum (`GFS`, `WRF`, `ECMWF`, `NCUM`).
- **`NWPVariables`**: Complete physical parameters:
  - 2m Temperature (`temperature_c`, `temp_min_c`, `temp_max_c`)
  - Precipitation (`precipitation_mm`, `precip_total_mm`, `precip_1h_mm`)
  - Rain probability (`rain_probability_pct`)
  - 10m Wind (`wind_speed_kmh`, `wind_gust_kmh`, `wind_direction_deg`)
  - Atmospheric pressure (`pressure_hpa`)
  - Relative humidity (`humidity_pct`, `relative_humidity_pct`)
  - Convective Available Potential Energy (`cape_jkg`)
  - Derived conditions (`condition`)
- **`NWPProvenance`**: Retains ingesting provider, model name, model run cycle, initialization time, grid resolution, and ingestion timestamp.
- **`NormalizedNWPForecastItem`**: Valid time, lead hours, coordinates, variables, provenance, and freshness.

---

## Strict Non-Averaging Principle

### Meteorological Rationale
Numerical weather prediction models differ fundamentally in their mathematical formulations:
- GFS utilizes a hydrostatic global spectral core with Zhao-Carr microphysics.
- WRF utilizes a non-hydrostatic Eulerian mass coordinate system with complex convective-permitting schemes (e.g. Morrison, WSM6).

Averaging their outputs produces physically impossible hybrid atmospheric states (e.g. smearing an intense convective storm with a clear-sky simulation).

### Implementation
[`NWPComparisonEngine`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/backend/services/nwp_provider.py) guarantees:
1. Individual model items are preserved intact with original values.
2. Timesteps from different model cycles are aligned by `valid_time`.
3. Discrete model spreads are calculated as:
   $$\text{Spread} = \max(\text{Model Values}) - \min(\text{Model Values})$$
4. Significant divergence (temperature spread $> 4.0^\circ\text{C}$, precipitation spread $> 15\,\text{mm}$, wind spread $> 25\,\text{km/h}$) triggers `high_spread = True`, which feeds into the reasoning layer as a forecast uncertainty notice.

---

## Safety Precedence & Reasoner Integration

### The IMD Safety Rule
> **MANDATORY**: Official warnings from the India Meteorological Department (IMD) unconditionally supersede all NWP model forecasts. Numerical predictions must never downgrade or dismiss an active official alert.

In [`ai/reasoner/reasoner.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/ai/reasoner/reasoner.py):
1. If `valid_active_alerts` are present, `overall_risk` is determined exclusively by the official warning severity (e.g., `EXTREME` or `HIGH`). Even if GFS/WRF model outputs forecast zero rain and calm winds, the risk remains `EXTREME`.
2. When no official alert is active, extreme NWP signals (e.g. WRF rainfall $\ge 50\,\text{mm}$ or wind $\ge 75\,\text{km/h}$) create an AI advisory hazard with `is_official_warning = False` and can elevate advisory risk.
3. Provenance tags (`NOAA_NCEP_GFS:GFS`, `REGIONAL_WRF:WRF`) are recorded in `sources_used`.

---

## Configuration & Reliability Layer

### Configuration Parameters
In [`backend/config/settings.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/backend/config/settings.py) and [`.env.example`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/.env.example):
```bash
# Phase 27: NWP / GFS / WRF Integration Readiness
NWP_ENABLED=false
NWP_GFS_ENDPOINT=
NWP_WRF_ENDPOINT=
NWP_HTTP_TIMEOUT_SECONDS=10.0
NWP_CACHE_TTL_SECONDS=1800
```

### Unconfigured State Policy
If `NWP_ENABLED=false` or an endpoint URL is blank:
- Provider status reports `ProviderStatusEnum.NOT_CONFIGURED`.
- API endpoints return status `NOT_CONFIGURED` with a clear explanation rather than fabricating synthetic live data.
- Calls to `fetch_model_forecast()` raise `ProviderUnavailableError` with diagnostic status `NOT_CONFIGURED`.

### Freshness Classification (`evaluate_nwp_freshness`)
Models run on 6-hour synoptic cycles ($00\text{Z}, 06\text{Z}, 12\text{Z}, 18\text{Z}$):
- **FRESH**: Age $< 6$ hours ($< 360$ minutes).
- **AGING**: Age $6$ to $12$ hours ($360$ to $720$ minutes).
- **STALE**: Age $> 12$ hours ($> 720$ minutes).

---

## API Endpoints

### 1. `GET /api/v1/weather/nwp/status`
Returns configuration readiness and provider availability for all supported NWP models without calling external networks.

### 2. `GET /api/v1/weather/nwp/forecast?model=GFS&location=Coimbatore&hours=72`
Returns normalized forecast timesteps for a specific numerical model. Returns `status: "NOT_CONFIGURED"` if unconfigured.

### 3. `GET /api/v1/weather/nwp/comparison?location=Coimbatore`
Runs multi-model spread analysis across configured NWP models without blending, returning discrete model spreads and consensus notes.

---

## Implementation vs. Future Live Data Sources

| Feature / Capability | Status | Implementation Details |
|---|---|---|
| **Base NWP Contract** | **Fully Implemented** | `BaseNWPProvider` with abstract methods and authority classification |
| **GFS Integration Adapter** | **Fully Implemented** | `GFSProvider` with 0.25° GFS parser, run cycle detection, and error mapping |
| **WRF Integration Adapter** | **Fully Implemented** | `WRFProvider` with mesoscale high-res parser, CAPE instability ingestion |
| **Provenance Tracking** | **Fully Implemented** | `NWPProvenance` retaining model, run, institution, grid, timestamp |
| **Non-Averaging Engine** | **Fully Implemented** | `NWPComparisonEngine` with max-min spreads across aligned valid times |
| **Safety Precedence Rule** | **Fully Implemented** | `WeatherReasoner` guarantees IMD alerts cannot be downgraded by NWP |
| **FastAPI Endpoints** | **Fully Implemented** | `/nwp/status`, `/nwp/forecast`, `/nwp/comparison` |
| **Deterministic Testing** | **Fully Implemented** | 16 deterministic tests covering schemas, contracts, safety, and API |
| **Live NOAA NOMADS Feed** | *Requires Credentials* | Awaiting live NOAA NOMADS or AWS Open Data GFS endpoint configuration |
| **Live NCMRWF WRF Feed** | *Requires Institutional Access* | Awaiting MoES / NCMRWF India dedicated mesoscale API endpoint |

---

## Verification
All NWP tests run deterministically via:
```bash
pytest tests/test_nwp_readiness.py -v
```
No fake live data is ever returned when endpoints are unconfigured, ensuring 100% compliance with meteorological integrity standards.
