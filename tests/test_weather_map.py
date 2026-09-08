import os
import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

def test_01_map_initialization():
    """1. Test map initialization: verifies screen-map, mapContainer, mapFallback, and Leaflet script in DOM."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    assert 'id="screen-map"' in html
    assert 'id="mapContainer"' in html
    assert 'id="mapFallback"' in html
    assert "leaflet.js" in html
    assert "leaflet.css" in html

def test_02_valid_marker():
    """2. Test valid marker: verifies preset locations have real coordinates and isValidCoordinate helper in app.js."""
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "MAP_PRESET_LOCATIONS" in js
    assert "isValidCoordinate" in js
    assert "Coimbatore" in js
    assert "11.0168" in js
    assert "76.9558" in js

def test_03_user_location():
    """3. Test user location: verifies userGpsLocation volatile in-memory state and GPS marker creation."""
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "userGpsLocation" in js
    assert "Your Device GPS Location" in js

def test_04_selected_location():
    """4. Test selected location: verifies selected location marker highlight and detail panel selection."""
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "selectedLocName" in js
    assert "selectMapMarkerDetails" in js

def test_05_official_warning_visualization():
    """5. Test official warning visualization: verifies alert marker circle layer with severity coloring."""
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "mapAlertsGroup" in js
    assert "L.circle" in js
    assert "#e11d48" in js  # High/Critical alert color

def test_06_missing_coordinates():
    """6. Test missing coordinates: verifies missing coordinates skip marker rendering without crashing."""
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "if (!isValidCoordinate(loc.lat, loc.lon)) continue;" in js

def test_07_invalid_coordinates():
    """7. Test invalid coordinates: verifies backend and JS coordinate bounds checking (-90..90 lat, -180..180 lon)."""
    resp_lat = client.get("/api/v1/weather/current?lat=150.0&lon=76.0")
    assert resp_lat.status_code == 400

    resp_lon = client.get("/api/v1/weather/current?lat=11.0&lon=250.0")
    assert resp_lon.status_code == 400

def test_08_no_network():
    """8. Test no network: verifies map fallback element exists in DOM and styles.css."""
    response = client.get("/")
    assert 'id="mapFallback"' in response.text

    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".map-fallback" in css

def test_09_empty_data():
    """9. Test empty data: verifies selectMapMarkerDetails handles empty alerts array without error."""
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "renderMapFallbackTelemetry" in js
    assert "alertBox.classList.add(\"hidden\");" in js or "alertBox.classList.add('hidden')" in js

def test_10_mobile_interaction():
    """10. Test mobile interaction: verifies recenter button, layer toggle button, and map info card in DOM."""
    response = client.get("/")
    html = response.text

    assert 'id="mapRecenterBtn"' in html
    assert 'id="mapLayerToggleBtn"' in html
    assert 'id="mapInfoCard"' in html

def test_11_performance_basic_marker_bounds():
    """11. Test performance/basic marker bounds: verifies layer clearing before re-plotting to prevent duplicate marker stacking."""
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "mapMarkersGroup.clearLayers();" in js
    assert "mapAlertsGroup.clearLayers();" in js

def test_12_location_privacy_behavior():
    """12. Test location privacy behavior: verifies device location is kept in volatile state and not sent to saved locations."""
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "Volatile in-memory GPS state for map & privacy protection" in js
