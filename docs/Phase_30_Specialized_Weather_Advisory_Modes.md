# SkyZen Phase 30: Specialized Weather Advisory Modes

## Executive Summary

SkyZen Phase 30 extends SkyZen's persona-aware advisory system into six specialized domain decision modes:
1. **Farmer Mode**: Rainfall advisory, irrigation timing guidance, heat/stress awareness, and weather-sensitive activity planning.
2. **Fisherman / Marine Mode**: Wind conditions, wave-related information (strictly verified without fabrication), precipitation, and departure/activity advisories with absolute official marine warning priority.
3. **Aviation Mode**: Airport/location weather, wind, visibility (strictly verified without fabrication), precipitation, thunderstorms, and convective hazards with clear non-certification disclaimers.
4. **Commuter / Student Mode**: Departure and return times, transit rain risk, heat stress, wind crosswind cautions, umbrella recommendations, clothing advice, and corridor delay buffers.
5. **Disaster Mode**: Active official warning summaries, affected locations, composite severity, emergency action guidance, and push notification status.
6. **Smart City Mode**: Location-based rainfall, urban heat island effects, AQI (strictly verified without fabrication), infrastructure weather hazards, and civic action items.

---

## Cardinal Architecture Principles

1. **Safety Hierarchy Invariant**: Official warnings issued by the India Meteorological Department (IMD) unconditionally supersede all model forecasts and sensor telemetry. Official marine or cyclone alerts immediately force `NO_GO` verdicts and cannot be overridden.
2. **No Fabrication of Domain Measurements**: Missing domain-specific parameters (e.g. offshore wave height, aerodrome runway visibility, or urban AQI) are never guessed or fabricated. When telemetry is unavailable, the system explicitly reports `is_available: False` and directs users to official specialized bulletins.
3. **Advisory Interface Boundary**: These modes are advisory interfaces to support personal and operational awareness, NOT certified professional decision systems (e.g., not an ICAO flight clearance, not an agronomic prescription, not a Coast Guard vessel clearance).
4. **Reuse of Core Reasoner**: Reuses the deterministic `WeatherReasoner`, `DecisionEngine`, and `PersonalDecisionEngine` rather than duplicating reasoning logic.
5. **Deterministic Multilingual Localization**: Complete native translations for headlines, advisories, action guidance, and concise answers across **English**, **Tamil**, **Hindi**, **Marathi**, and **Telugu**.

---

## Specialized Advisory Modes

### 1. Farmer Mode (`FarmerAdvisoryResult`)
- **Rainfall Advisory**: Rain probability (%), expected precipitation volume (mm), and rain time windows.
- **Irrigation Timing Guidance**:
  - *Rain Expected / Official Warning*: "Suspend irrigation immediately. Natural precipitation is adequate to prevent soil moisture deficit. Avoid root-zone waterlogging, soil aeration loss, and nutrient leaching."
  - *High Heat (>35°C) & Dry*: "Provide light, frequent irrigation strictly during early morning (before 08:00) or late evening (after 18:00) to minimize evaporative loss and thermal shock."
  - *Moderate Rain (30-40%)*: "Defer scheduled watering cycle and monitor topsoil moisture depth."
  - *Normal/Calm*: "Proceed with routine crop-specific irrigation schedule."
- **Heat & Stress Awareness**:
  - Detects severe heatwave stress (>40°C), moderate thermal stress (35-40°C), and cold stress (<12°C).
  - Supplies physiological mitigation advice (organic mulching, windbreak barriers).
- **Weather-Sensitive Activity Planning**:
  - *Spraying*: Postponed if wind speed > 20 km/h (drift hazard) or rain probability >= 40% (wash-off hazard).
  - *Harvesting*: Protect harvested produce and threshing floors with tarpaulins if rain probability >= 40% or rain >= 5.0 mm.
  - *Staking*: Provide earthing-up or mechanical staking for tall crops (banana, sugarcane, maize) when wind gusts >= 25 km/h.
- **Agronomic Disclaimer**: "Advisory interface based strictly on verified atmospheric observations. Does not provide certified agronomic prescriptions or crop-specific treatment guarantees."

---

### 2. Fisherman / Marine Mode (`MarineAdvisoryResult`)
- **Wind Conditions**: Sustained wind speed (km/h and knots), wind direction, and Beaufort squall classification ("Calm", "Moderate Breeze", "Squally / Rough", "Gale / Storm").
- **Wave Information**:
  - Reported when verified in telemetry (wave height in meters, wave period in seconds).
  - When absent from coastal telemetry, strictly flagged: `is_available: False`, `summary: "Direct wave telemetry unavailable for this coastal station. Refer to official INCOIS/IMD sea state bulletins."` (NEVER FABRICATED).
- **Precipitation**: Rain probability, squall expected flags, and thunderstorm detection.
- **Official Warning Priority**:
  - Active IMD coastal/marine warnings force `departure_verdict = "NO_GO"`, with strict prohibition text: *"Fishermen are strictly advised NOT to venture into the sea off {location} due to an active official marine warning."*
- **Departure Verdicts**:
  - `NO_GO`: Official warning active, wind >= 40 km/h, or convective thunderstorm.
  - `CAUTION`: Moderate squall conditions (wind 25-39 km/h); remain within coastal VHF range with mandatory life jackets.
  - `GO`: Favorable sea state (< 25 km/h wind); standard marine life safety gear required.

---

### 3. Aviation Mode (`AviationAdvisoryResult`)
- **Airport / Location Binding**: Target aerodrome name or ICAO/IATA identifier (e.g. `VOBL`, `VOCB`).
- **Wind**: Surface speed (km/h and knots), wind direction, crosswind hazard indicator (>= 28 km/h), and gust potential.
- **Visibility**:
  - Reported when verified in surface telemetry (visibility in km and meters, low-visibility flag for < 5.0 km).
  - When absent, strictly flagged: `is_available: False`, `visibility_km: None`, `note: "Direct runway visibility / transmissometer telemetry unavailable. Refer to official aerodrome METAR/ATIS."` (NEVER FABRICATED).
- **Convective Activity & Thunderstorms**: Thunderstorm cell detection, lightning risk, and convective cloud alerts.
- **Flight Category Indicator**:
  - `HAZARDOUS`: Active thunderstorm, official warning, or surface winds >= 45 km/h.
  - `MARGINAL_VFR`: Reduced visibility (< 5.0 km), fog, or winds 30-44 km/h.
  - `VFR_FAVORABLE`: Calm convective profile and winds < 30 km/h.
- **Aviation Disclaimer**: "Advisory interface based on surface meteorological telemetry. NOT a certified aviation meteorological briefing (METAR/TAF/SIGMET) and cannot be used for regulatory flight planning."

---

### 4. Commuter / Student Mode (`CommuterStudentAdvisoryResult`)
- **Schedule Windows**: Explicit support for `departure_time` (e.g. 08:30 AM) and `return_time` (e.g. 05:30 PM).
- **Rain Risk**: Distinct probabilities evaluated for departure window, return window, and peak precipitation period.
- **Heat & Hydration**: Ambient temperature, heat stress classification ("comfortable", "high_heat", "extreme"), and oral rehydration guidance.
- **Wind & Crosswind**: Crosswind hazard alert for two-wheeler commuters navigating flyovers, bridges, and elevated corridors when winds >= 25 km/h.
- **Umbrella Decision**: Clear `True`/`False` recommendation with deterministic meteorological rationale.
- **Clothing Guidance**: Light breathable cotton for high heat; water-resistant gear and waterproof commuter bag covers for precipitation.
- **Transit Delay Buffer**: Delay buffer recommendation (+15 to +30 minutes) based on waterlogging risk and roadway slowdowns.

---

### 5. Disaster Mode (`DisasterAdvisoryResult`)
- **Active Warning Summary**: Complete catalog of active institutional alerts with title, severity, category, source, effective validity window, and affected locations.
- **Affected Location**: Target municipal or administrative jurisdiction.
- **Composite Severity**: `extreme`, `high`, `medium`, or `low`.
- **Action Guidance**:
  - Standby mobilization of municipal disaster control rooms.
  - Heavy dewatering pump and rescue boat pre-positioning at recognized low-lying flood corridors.
  - Community relief shelter preparation with dry rations and drinking water.
  - Precautionary relocation advisories for vulnerable populations along riverbanks.
- **Notification Status**: Tracks whether emergency push broadcasts (`FCM_EMERGENCY_BROADCAST`) were dispatched.
- **Safety Precedence**: Official IMD/NDMA directives are preserved without modification.

---

### 6. Smart City Mode (`SmartCityAdvisoryResult`)
- **Location Name**: Urban ward or metropolitan area.
- **Rainfall & Drainage Watch**:
  - `drainage_watch_status`: `NORMAL`, `WATCH`, `WARNING`, `ALERT`.
  - Assesses urban waterlogging bottlenecks, subway underpasses, and arterial drain capacities.
- **Urban Heat Island**: Thermal load evaluation, asphalt heat absorption index, and municipal cooling center recommendations during heatwaves.
- **AQI Summary**:
  - When verified: Index value, category (Good, Satisfactory, Moderate, Poor, Very Poor, Severe), primary pollutant (PM2.5, PM10), and sensitive group recommendations.
  - When absent: `is_available: False`, `note: "Air quality index telemetry currently unavailable for this civic station node. Environmental sensors offline or unconfigured."` (NEVER FABRICATED).
- **Civic Action Items**: Practical municipal maintenance items (deploy mobile pump sets, issue digital variable message sign detours, clear storm drain trash grates, open public cooling centers).

---

## API & Integration Surface

### REST API: `GET /api/v1/weather/advisory`
- **Query Parameters**:
  - `mode`: `farmer`, `fisherman` (or `marine`), `aviation`, `commuter` (or `student`), `disaster`, `smart_city`, `general`.
  - `location`: City name (default: "Coimbatore").
  - `lat`, `lon`: Optional geographic coordinates.
  - `language`: `en`, `ta`, `hi`, `mr`, `te`.
  - `departure_time`: Commute departure string (e.g. "08:00 AM").
  - `return_time`: Commute return string (e.g. "05:00 PM").
  - `airport_code`: ICAO/IATA aerodrome identifier (e.g. "VOBL").
- **Response**: `SpecializedModeResponse` containing unified metadata, localized answers, key precautions, source attribution, and domain-specific `details` payload.

---

## Testing & Verification

Comprehensive deterministic tests in [`tests/test_specialized_advisory_modes.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/tests/test_specialized_advisory_modes.py):

| Test Case | Mode / Target | Result |
|:---|:---|:---:|
| `test_farmer_mode_rain_suspends_irrigation` | Farmer Mode: Rain irrigation suspension, harvest protection, spraying hold | PASSED |
| `test_farmer_mode_heat_stress_guidance` | Farmer Mode: Heatwave (>40°C) awareness, morning/evening irrigation | PASSED |
| `test_farmer_mode_high_winds_postpones_spraying` | Farmer Mode: High winds (>20 km/h) spray postponement, staking advice | PASSED |
| `test_marine_mode_official_warning_forces_no_go` | Marine Mode: Official IMD warning forces `NO_GO` verdict unconditionally | PASSED |
| `test_marine_mode_wave_telemetry_grounding` | Marine Mode: Wave telemetry presence vs absence without fabrication | PASSED |
| `test_marine_mode_wind_thresholds` | Marine Mode: Wind velocity thresholds (`GO`, `CAUTION`, `NO_GO`) | PASSED |
| `test_aviation_mode_visibility_grounding` | Aviation Mode: Runway visibility presence vs absence without fabrication | PASSED |
| `test_aviation_mode_thunderstorm_hazard` | Aviation Mode: Thunderstorm convective hazard detection (`HAZARDOUS`) | PASSED |
| `test_commuter_student_mode_schedule_and_umbrella` | Commuter Mode: Departure/return times, return rain risk, delay buffer | PASSED |
| `test_commuter_student_mode_crosswind_two_wheeler_caution` | Commuter Mode: Bridge crosswinds (>25 km/h) two-wheeler warning | PASSED |
| `test_disaster_mode_active_alert_mobilization` | Disaster Mode: Warning summary, severity, dewatering mobilization, FCM flag | PASSED |
| `test_smart_city_mode_waterlogging_and_aqi` | Smart City Mode: Urban drainage watch, AQI presence vs absence | PASSED |
| `test_unified_evaluate_mode_multilingual` | Unified Dispatcher: Localization across English, Tamil, Hindi | PASSED |
| `test_decision_engine_embeds_specialized_advisory` | DecisionEngine: Embedding specialized payload into `DecisionAdvisory` | PASSED |
| `test_api_weather_advisory_endpoint` | REST API: FastAPI `/weather/advisory` endpoint for all modes | PASSED |

**Full Regression**: 107 tests passed across `test_specialized_advisory_modes.py`, `test_realtime_ingestion.py`, `test_skyzen_phase7_personalization.py`, `test_skyzen_personal_decisions.py`, `test_skyzen_fisherman_decision.py`, `test_skyzen_college_commute.py`, and `test_skyzen_imd_warning_safety.py`.
