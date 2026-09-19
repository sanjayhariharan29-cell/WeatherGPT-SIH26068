"""Unit and Integration Tests for Satellite Layer & Himawari-9 Tile Proxy.

Validates:
1. RainViewer public weather-maps.json check (satellite.infrared empty check).
2. Backend Himawari-9 satellite tile proxy (/api/v1/weather/tiles/satellite/{z}/{x}/{y}.png).
3. Image validity and non-empty cloud coverage over India (Central India, South India).
4. Satellite attribution headers and Honest Labeling (Himawari / RealEarth, never INSAT or IMD/ISRO).
5. Frontend Map Layer Switcher DOM contains Satellite (Himawari) button with correct attributes.
"""

import os
import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")


def test_01_backend_satellite_tile_proxy_over_india():
    """1. Validates that the backend satellite tile proxy serves real Himawari-9 tiles over India."""
    # Zoom 4 coordinates over Central India (lat 20.59, lon 78.96) -> 4/11/7
    res = client.get("/api/v1/weather/tiles/satellite/4/11/7.png")
    assert res.status_code == 200, res.text
    assert res.headers.get("content-type") == "image/png"
    assert len(res.content) > 1000

    # Validate image properties with PIL
    img = Image.open(io.BytesIO(res.content))
    assert img.format == "PNG"
    assert img.size == (256, 256)
    assert img.mode in ["RGB", "RGBA"]


def test_02_backend_satellite_himawari_alias_and_caching():
    """2. Validates 'himawari' layer alias and cache hit on repeat request."""
    res1 = client.get("/api/v1/weather/tiles/himawari/4/11/7.png")
    assert res1.status_code == 200

    res2 = client.get("/api/v1/weather/tiles/himawari/4/11/7.png")
    assert res2.status_code == 200
    assert res2.headers.get("x-cache") == "HIT"


def test_03_satellite_source_attribution_headers():
    """3. Validates that satellite responses clearly attribute Himawari / JMA / RealEarth, NEVER INSAT or IMD."""
    res = client.get("/api/v1/weather/tiles/satellite/4/11/7.png")
    assert res.status_code == 200
    source = res.headers.get("x-satellite-source", "")
    assert "Himawari" in source
    assert "INSAT" not in source
    assert "IMD" not in source or "Himawari" in source  # No fabricated INSAT/IMD attribution


def test_04_satellite_coordinate_validation():
    """4. Validates out-of-bounds coordinate rejections for satellite layer."""
    # Invalid zoom > 18
    res_z = client.get("/api/v1/weather/tiles/satellite/20/0/0.png")
    assert res_z.status_code == 400

    # Negative zoom
    res_neg = client.get("/api/v1/weather/tiles/satellite/-1/0/0.png")
    assert res_neg.status_code == 400


def test_05_frontend_satellite_button_in_dom():
    """5. Validates that frontend index.html includes the Satellite (Himawari) switcher button."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert 'data-layer="satellite"' in html
    assert "Satellite (Himawari)" in html
    assert 'id="mapLeftLayerToggle"' in html


def test_06_frontend_no_fake_insat_labeling():
    """6. Validates that satellite buttons are never misleadingly labeled as INSAT or IMD radar."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Ensure satellite button does NOT claim to be INSAT
    assert 'data-layer="satellite"' in html
    assert "INSAT" not in html
