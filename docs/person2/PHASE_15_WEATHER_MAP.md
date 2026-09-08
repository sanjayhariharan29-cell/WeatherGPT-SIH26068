# Phase 15 — Weather Map / Geospatial Visualization (Person 2)

## Overview

Phase 15 implements an interactive geospatial weather and disaster warning map for WeatherGPT. It integrates Leaflet.js open-source map rendering into the mobile frontend, displaying real coordinate weather telemetry, official IMD weather warnings, user GPS device location, and selected location markers while adhering strictly to location privacy standards and avoiding fabricated data.

---

## Architectural & Mapping Design

### 1. Mapping Library & Tiles (`frontend/index.html`, `frontend/styles.css`)
- **Mapping Engine**: Leaflet.js v1.9.4 (lightweight, zero-dependency, WCAG touch-friendly).
- **Tile Provider**: OpenStreetMap dark-theme tile layers with graceful fallback on network interruption.
- **UI Container**: `#screen-map` section featuring `#mapContainer`, `#mapRecenterBtn`, `#mapLayerToggleBtn`, and `#mapInfoCard`.

### 2. Coordinate & Marker Model (`frontend/app.js`)
- **Validation**: `isValidCoordinate(lat, lon)` strictly enforces bounds (-90.0 to +90.0 latitude, -180.0 to +180.0 longitude).
- **Weather Markers**: Preset Tamil Nadu weather station coordinates (Coimbatore, Nagapattinam, Chennai, Madurai, Tiruchirappalli, Salem, Tirunelveli) plotted using circle markers with real-time temperature and condition popups.
- **Selected Location Marker**: Highlights active user location choice in cyan (`#06b6d4`).

### 3. Official Warning & Hazard Visualization (`frontend/app.js`, `frontend/styles.css`)
- **Official Warning Markers**: Official IMD alerts (e.g. Nagapattinam coastal rain alerts) are plotted at verified warning coordinates using colored 15km alert radius circles.
- **Severity Mappings**: `#e11d48` for `CRITICAL` / `HIGH` alerts, `#f59e0b` for `MEDIUM` / `MODERATE` alerts.
- **No Fake Polygons**: Preserves exact backend warning metadata (title, description, severity, source, effective period) without fabricating geometric polygons or inferring areas from simple points.

### 4. Privacy & Device Location Handling (`frontend/app.js`)
- **Volatile GPS State**: Device GPS coordinates (`userGpsLocation`) are held strictly in-memory for map centering and marker rendering.
- **Consent Guarantee**: GPS coordinates are never stored permanently in backend database tables without explicit user consent.

### 5. Performance & Layer Management (`frontend/app.js`)
- **Layer Clearing**: `mapMarkersGroup.clearLayers()` and `mapAlertsGroup.clearLayers()` clear previous marker instances before each refresh, preventing layer stacking and memory leaks.
- **Layer Toggle**: `#mapLayerToggleBtn` allows users to toggle the official warning layer on demand.

### 6. Error & Offline Fallback Handling (`frontend/index.html`, `frontend/app.js`)
- **Library & Network Failure**: If Leaflet fails to load or the network is offline, `#mapFallback` displays a fallback banner while coordinate weather telemetry is rendered in `#mapInfoCard` without JavaScript errors.

---

## Test Verification Summary

The test suite in `tests/test_weather_map.py` verifies all 12 required Phase 15 scenarios:

1. **Map Initialization**: `#screen-map`, `#mapContainer`, `#mapFallback`, and Leaflet DOM inclusion verified.
2. **Valid Marker**: Preset locations and `isValidCoordinate()` helper verified.
3. **User Location**: `userGpsLocation` volatile state and GPS marker creation verified.
4. **Selected Location**: Selected location marker highlight and detail panel selection verified.
5. **Official Warning Visualization**: Warning circle layer creation and severity styling verified.
6. **Missing Coordinates**: Missing coordinate skip logic verified.
7. **Invalid Coordinates**: Out-of-bounds coordinate rejection verified (-90..90 lat, -180..180 lon).
8. **No Network**: `#mapFallback` container and offline styling verified.
9. **Empty Data**: Empty alert handling without crashing verified.
10. **Mobile Interaction**: Recenter button, layer toggle button, and detail panel verified.
11. **Performance & Marker Bounds**: Layer clearing before re-plotting verified.
12. **Location Privacy Behavior**: Device location volatile in-memory protection verified.

---

## Regression Test Results

Full test suite execution (`python -m pytest -v`):
- **Total Passed**: **450 / 450**
- **Failed**: **0**
- **Execution Time**: ~30s
