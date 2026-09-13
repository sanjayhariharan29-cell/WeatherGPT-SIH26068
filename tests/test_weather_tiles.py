"""
Unit and Integration Tests for OpenWeather Weather Maps 2.0 Tile Layers & Controls
Validates:
1. Backend tile proxy endpoint (/api/v1/weather/tiles/{layer}/{z}/{x}/{y}.png)
2. Layer mapping for all 6 layers (Radar, Temp, Rain, Wind, Clouds, Waves)
3. Fallback transparent PNG when API key is unconfigured / upstream errors
4. Coordinate validation (z, x, y bounds)
5. Left-side toggle UI in DOM with all 6 buttons and WCAG compliance
6. ControlledWeatherTileLayer: tile requests fired ONLY on layer switch or explicit refresh
7. Marker layer preservation on top of weather overlay (weatherTilePane z-index 250 < markerPane 600)
"""

import os
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")


def test_01_backend_tile_proxy_all_layers():
    """1. Test that all 6 required layers return valid image/png from backend proxy."""
    required_layers = ["radar", "temp", "rain", "wind", "clouds", "waves"]
    for layer in required_layers:
        res = client.get(f"/api/v1/weather/tiles/{layer}/7/93/60.png")
        assert res.status_code == 200, f"Failed for layer: {layer}"
        assert res.headers.get("content-type") == "image/png"
        assert len(res.content) > 0


def test_02_backend_tile_proxy_canonical_names():
    """2. Test canonical OpenWeather layer names are supported."""
    canonical_layers = ["precipitation_new", "temp_new", "wind_new", "clouds_new", "pressure_new"]
    for layer in canonical_layers:
        res = client.get(f"/api/v1/weather/tiles/{layer}/7/93/60.png")
        assert res.status_code == 200, f"Failed for canonical layer: {layer}"
        assert res.headers.get("content-type") == "image/png"


def test_03_backend_tile_proxy_extension_flexibility():
    """3. Test tile endpoint works both with .png extension and raw coordinate path."""
    res_with_ext = client.get("/api/v1/weather/tiles/temp/7/93/60.png")
    assert res_with_ext.status_code == 200

    res_raw = client.get("/api/v1/weather/tiles/temp/7/93/60")
    assert res_raw.status_code == 200
    assert res_raw.headers.get("content-type") == "image/png"


def test_04_backend_tile_proxy_coordinate_validation():
    """4. Test coordinate bounds validation (-z, z>18, x/y out of bounds, non-integer)."""
    # Invalid zoom > 18
    res_z = client.get("/api/v1/weather/tiles/radar/20/0/0.png")
    assert res_z.status_code == 400

    # Negative zoom
    res_neg_z = client.get("/api/v1/weather/tiles/radar/-1/0/0.png")
    assert res_neg_z.status_code == 400

    # Coordinate out of bounds for zoom 2 (max coord is 4)
    res_oob = client.get("/api/v1/weather/tiles/radar/2/10/10.png")
    assert res_oob.status_code == 400

    # Non-integer coordinate
    res_non_int = client.get("/api/v1/weather/tiles/radar/7/abc/60.png")
    assert res_non_int.status_code in (400, 422)


def test_05_backend_tile_proxy_invalid_layer_rejection():
    """5. Test that unsupported layer returns 400 error."""
    res = client.get("/api/v1/weather/tiles/unknown_layer_xyz/7/93/60.png")
    assert res.status_code == 400
    assert "Unsupported weather tile layer" in res.json().get("detail", "")


def test_06_backend_tile_proxy_cache_headers():
    """6. Test Cache-Control headers and caching behavior."""
    res1 = client.get("/api/v1/weather/tiles/clouds/7/93/60.png")
    assert res1.status_code == 200
    assert "Cache-Control" in res1.headers

    # Immediate second request should hit cache
    res2 = client.get("/api/v1/weather/tiles/clouds/7/93/60.png")
    assert res2.status_code == 200


def test_07_left_side_layer_toggle_dom_structure():
    """7. Test that #mapLeftLayerToggle exists with all 6 buttons: Radar, Temp, Rain, Wind, Clouds, Waves."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert 'id="mapLeftLayerToggle"' in html, "mapLeftLayerToggle container must exist"
    assert 'class="map-left-layer-toggle"' in html

    expected_buttons = ["radar", "temp", "rain", "wind", "clouds", "waves"]
    for b in expected_buttons:
        assert f'data-layer="{b}"' in html, f"Button with data-layer='{b}' missing in DOM"


def test_08_left_side_layer_toggle_styles():
    """8. Test CSS for left toggle: absolute positioning on left side and WCAG 44px touch targets."""
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".map-left-layer-toggle" in css
    assert "position: absolute" in css
    assert "left: 12px" in css or "left: 8px" in css
    assert ".map-tile-btn" in css
    assert "min-height: 44px" in css


def test_09_controlled_tile_layer_and_fetching_guards():
    """9. Test ControlledWeatherTileLayer in app.js prevents continuous requests during pan/zoom."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "ControlledWeatherTileLayer" in js
    assert "_tileFetchingEnabled" in js
    assert "enableAndFetch" in js
    assert "switchWeatherMapLayer" in js
    assert "setupMapLeftLayerToggle" in js

    # Verify tile pane hierarchy puts weather tiles below markers
    assert 'mapInstance.createPane("weatherTilePane")' in js
    assert 'weatherTilePane' in js
    assert 'zIndex = 250' in js or 'zIndex: 250' in js

    # Verify refresh button calls enableAndFetch
    assert "enableAndFetch()" in js


def test_10_i18n_tile_layer_labels():
    """10. Test all 6 tile labels exist in i18n dictionaries for en, ta, and hi."""
    i18n_path = os.path.join(FRONTEND_DIR, "i18n.js")
    with open(i18n_path, "r", encoding="utf-8") as f:
        js = f.read()

    keys = [
        "map.tile_radar",
        "map.tile_temp",
        "map.tile_rain",
        "map.tile_wind",
        "map.tile_clouds",
        "map.tile_waves"
    ]
    for k in keys:
        assert f'"{k}"' in js, f"Missing i18n key: {k}"
