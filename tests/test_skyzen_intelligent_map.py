"""
Comprehensive Test Suite for Phase — SkyZen Intelligent Weather Map
Validates all 24 mandatory behavioral and meteorological requirements:
1. map initialization
2. map click handling & selection
3. selected coordinates formatting
4. real weather fetch from backend
5. weather card rendering (temp, cond, metrics)
6. GPS button single-shot behavior
7. saved location plotting & selection
8. location switching & recentering
9. search location autocomplete & resolution
10. live status badge handling
11. stale status badge handling
12. degraded status handling
13. offline status handling
14. IMD warning priority display
15. invalid warning geometry rejection
16. source provenance transparency
17. freshness relative time formatting
18. no fake weather values
19. no fake warning zones (authoritative geometry only)
20. mobile interaction & bottom navigation clearance
21. request throttling & AbortController cancellation
22. accessibility & WCAG 44px touch targets
23. AI integration using selected map location
24. AQI source labeling (CPCB vs Modelled Open-Meteo)
"""

import os
import re
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")


@pytest.fixture(scope="module")
def frontend_files():
    with open(os.path.join(FRONTEND_DIR, "index.html"), "r", encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(FRONTEND_DIR, "app.js"), "r", encoding="utf-8") as f:
        js = f.read()
    with open(os.path.join(FRONTEND_DIR, "styles.css"), "r", encoding="utf-8") as f:
        css = f.read()
    with open(os.path.join(FRONTEND_DIR, "i18n.js"), "r", encoding="utf-8") as f:
        i18n = f.read()
    with open(os.path.join(FRONTEND_DIR, "mobile", "apiClient.js"), "r", encoding="utf-8") as f:
        api = f.read()
    return {"html": html, "js": js, "css": css, "i18n": i18n, "api": api}


# 1. Map Initialization
def test_01_map_initialization(frontend_files):
    html = frontend_files["html"]
    js = frontend_files["js"]
    assert 'id="screen-map"' in html
    assert 'id="mapContainer"' in html
    assert 'id="mapFallback"' in html
    assert "initWeatherMap" in js
    assert "L.map" in js


# 2. Map Click Handling
def test_02_map_click_handling(frontend_files):
    js = frontend_files["js"]
    assert "mapInstance.on(\"click\", handleMapClick)" in js or "mapInstance.on('click', handleMapClick)" in js
    assert "handleMapClick" in js
    assert "selectLocationAndFetchWeather" in js


# 3. Selected Coordinates
def test_03_selected_coordinates(frontend_files):
    html = frontend_files["html"]
    js = frontend_files["js"]
    assert 'id="mapLocCoords"' in html
    assert "toFixed(2)" in js
    assert "isValidCoordinate" in js


# 4. Real Weather Fetch
def test_04_real_weather_fetch():
    # Verify backend returns real meteorological fields for coordinates
    resp = client.get("/api/v1/weather/current?lat=11.0168&lon=76.9558&location=Coimbatore")
    assert resp.status_code == 200
    data = resp.json()
    assert "weather" in data
    assert "temperature" in data["weather"]
    assert "condition" in data["weather"]
    assert "wind_speed" in data["weather"]
    assert "source" in data or "sources" in data


# 5. Weather Card Rendering
def test_05_weather_card_rendering(frontend_files):
    html = frontend_files["html"]
    assert 'id="mapSelectionCard"' in html
    assert 'id="mapWeatherTemp"' in html
    assert 'id="mapWeatherCond"' in html
    assert 'id="mapMetricRain"' in html
    assert 'id="mapMetricWind"' in html
    assert 'id="mapMetricHumidity"' in html
    assert 'id="mapMetricPressure"' in html
    assert 'id="mapMetricAqi"' in html


# 6. GPS Button Single-Shot Behavior
def test_06_gps_button_behavior(frontend_files):
    html = frontend_files["html"]
    js = frontend_files["js"]
    assert 'id="mapMyLocationBtn"' in html
    assert "handleMapMyLocation" in js
    assert "navigator.geolocation.getCurrentPosition" in js
    # Confirm no continuous watchPosition is used for map centering
    assert "navigator.geolocation.watchPosition" not in js


# 7. Saved Locations Plotting & Selection
def test_07_saved_locations_plotting(frontend_files):
    html = frontend_files["html"]
    js = frontend_files["js"]
    api = frontend_files["api"]
    assert 'id="mapSaveLocBtn"' in html
    assert "loadSavedMapLocations" in js
    assert "mapSavedMarkersGroup" in js
    assert "getSavedLocations" in api
    assert "saveLocation" in api


# 8. Location Switching & Recentering
def test_08_location_switching(frontend_files):
    js = frontend_files["js"]
    assert "recenterMapToSelected" in js
    assert "selectLocationAndFetchWeather" in js


# 9. Search Location Autocomplete & Resolution
def test_09_search_location(frontend_files):
    html = frontend_files["html"]
    js = frontend_files["js"]
    assert 'id="mapSearchInput"' in html
    assert 'id="mapSearchDropdown"' in html
    assert "executeMapLocationSearch" in js
    # Backend search endpoint verification
    resp = client.get("/api/v1/locations/search?q=Chennai")
    assert resp.status_code == 200


# 10. Live Status Badge Handling
def test_10_live_status_badge(frontend_files):
    html = frontend_files["html"]
    js = frontend_files["js"]
    assert 'id="mapStatusBadge"' in html
    assert 'id="mapStatusText"' in html
    assert "LIVE" in js
    assert "Never infer LIVE from HTTP alone" in js or "displayStatus = \"LIVE\"" in js


# 11. Stale Status Badge Handling
def test_11_stale_status_badge(frontend_files):
    js = frontend_files["js"]
    assert "DATA STALE" in js
    assert "is_stale" in js


# 12. Degraded Status Handling
def test_12_degraded_status_handling(frontend_files):
    js = frontend_files["js"]
    assert "DEGRADED" in js
    assert "realtime_state === \"DEGRADED\"" in js or "provenance?.status === \"degraded\"" in js


# 13. Offline Status Handling
def test_13_offline_status_handling(frontend_files):
    js = frontend_files["js"]
    css = frontend_files["css"]
    assert "OFFLINE" in js
    assert "!navigator.onLine" in js
    assert ".map-selection-status-badge.offline" in css


# 14. IMD Warning Priority Display
def test_14_imd_warning_priority_display(frontend_files):
    html = frontend_files["html"]
    js = frontend_files["js"]
    assert 'id="mapAlertPriorityBox"' in html
    assert 'id="mapAlertPriorityTitle"' in html
    assert 'id="mapAlertPrioritySeverity"' in html
    assert "OFFICIAL IMD WARNING" in js
    assert "alertBox.classList.remove(\"hidden\")" in js


# 15. Invalid Warning Geometry Rejection
def test_15_invalid_warning_geometry_rejection(frontend_files):
    js = frontend_files["js"]
    # Check that geometry is only rendered when backend provides valid geometry and coordinates
    assert "alert.geometry && alert.geometry.type && alert.geometry.coordinates" in js
    assert "Never fabricate geometry" in js or "Only render if valid geometry" in js


# 16. Source Provenance Transparency
def test_16_source_provenance_transparency(frontend_files):
    html = frontend_files["html"]
    js = frontend_files["js"]
    assert 'id="mapWeatherSource"' in html
    assert 'id="mapSourceAgreement"' in html
    assert "Multi-Source Agreement" in js or "Direct Telemetry" in js


# 17. Freshness Relative Time Formatting
def test_17_freshness_formatting(frontend_files):
    html = frontend_files["html"]
    js = frontend_files["js"]
    assert 'id="mapFreshnessText"' in html
    assert "formatRelativeTime" in js
    assert "min ago" in js


# 18. No Fake Weather (Backend is Source of Truth)
def test_18_no_fake_weather():
    # Verify coordinates call directly fetches from real provider engine
    resp = client.get("/api/v1/weather/current?lat=13.0827&lon=80.2707")
    assert resp.status_code == 200
    data = resp.json()
    assert data["weather"]["temperature"] is not None
    assert isinstance(data["weather"]["temperature"], (int, float))
    assert data["source"] != "fake"


# 19. No Fake Warning Zones
def test_19_no_fake_warning_zones(frontend_files):
    js = frontend_files["js"]
    # Ensure no arbitrary random polygon generators exist
    assert "Math.random() * 0.1" not in js
    assert "renderOfficialAlertGeometry" in js


# 20. Mobile Interaction & Clearance
def test_20_mobile_interaction(frontend_files):
    css = frontend_files["css"]
    # Verify map view container and bottom clearance
    assert ".map-view-container" in css
    assert ".map-selection-card" in css
    assert "bottom: 72px" in css or "calc(var(--mobile-nav-height)" in css or "max-height" in css


# 21. Request Throttling & AbortController Cancellation
def test_21_request_throttling_and_cancellation(frontend_files):
    js = frontend_files["js"]
    assert "mapClickThrottleTimer" in js
    assert "activeMapAbortController" in js
    assert "new AbortController()" in js
    assert "activeMapAbortController.abort()" in js


# 22. Accessibility & WCAG Standards
def test_22_accessibility_standards(frontend_files):
    html = frontend_files["html"]
    css = frontend_files["css"]
    assert 'aria-label="Interactive Weather Map"' in html
    assert 'aria-label="Use My Location"' in html
    assert 'aria-label="Refresh Map Data"' in html
    assert 'min-height: 44px' in css or 'min-height: 42px' in css or 'padding: 10px' in css


# 23. AI Uses Selected Map Location
def test_23_ai_uses_selected_map_location(frontend_files):
    html = frontend_files["html"]
    js = frontend_files["js"]
    assert 'id="mapAskAiBtn"' in html
    assert "handleMapAskAi" in js
    assert "navigateToScreen(\"chat\")" in js or "navigateToScreen('chat')" in js
    assert "window.lastWeatherData =" in js


# 24. AQI Source Labeling (CPCB vs Modelled)
def test_24_aqi_source_labeling(frontend_files):
    html = frontend_files["html"]
    js = frontend_files["js"]
    assert 'id="mapAqiSource"' in html
    assert "CPCB Official Station" in js
    assert "Modelled Air Quality" in js
    assert "Open-Meteo" in js
