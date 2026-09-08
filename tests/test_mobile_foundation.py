import os
import json
import re
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
MOBILE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mobile")

def test_01_application_boot_and_static_mounting():
    """1. Test application boot, static files mounting, and index.html serving."""
    response = client.get("/")
    assert response.status_code == 200
    html_content = response.text
    assert "WeatherGPT" in html_content
    assert "mobile-bottom-nav" in html_content
    assert "manifest.json" in html_content
    assert "apiClient.js" in html_content


def test_02_pwa_manifest_configuration():
    """2. Test PWA manifest.json exists, is valid JSON, and has mobile standalone properties."""
    manifest_path = os.path.join(FRONTEND_DIR, "manifest.json")
    assert os.path.exists(manifest_path)
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert data["name"] == "WeatherGPT — IMD Meteorological Assistant"
    assert data["display"] == "standalone"
    assert "shortcuts" in data
    assert len(data["shortcuts"]) >= 2


def test_03_service_worker_offline_caching():
    """3. Test Service Worker (sw.js) exists and defines network-first offline strategy."""
    sw_path = os.path.join(FRONTEND_DIR, "sw.js")
    assert os.path.exists(sw_path)
    
    with open(sw_path, "r", encoding="utf-8") as f:
        sw_content = f.read()
    
    assert "CACHE_NAME" in sw_content
    assert "NETWORK_OFFLINE" in sw_content
    assert "caches.match" in sw_content


def test_04_mobile_api_client_structure():
    """4. Test centralized mobile API Client (apiClient.js) exists and implements all endpoints."""
    api_client_path = os.path.join(FRONTEND_DIR, "mobile", "apiClient.js")
    assert os.path.exists(api_client_path)
    
    with open(api_client_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "class WeatherGPTApiClient" in content
    assert "getCurrentWeather" in content
    assert "getForecast" in content
    assert "getAlerts" in content
    assert "sendChatMessage" in content
    assert "login" in content
    assert "register" in content
    assert "getSavedLocations" in content
    assert "X-Request-ID" in content
    assert "Authorization" in content


def test_05_capacitor_mobile_wrapper_config():
    """5. Test Capacitor configuration for native iOS/Android packaging."""
    cap_path = os.path.join(MOBILE_DIR, "capacitor.config.json")
    assert os.path.exists(cap_path)
    
    with open(cap_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert data["appId"] == "in.gov.moes.weathergpt"
    assert data["appName"] == "WeatherGPT"


def test_06_navigation_screens_and_accessibility():
    """6. Test all 6 mobile screens (home, chat, weather, alerts, profile, settings) exist with ARIA labels."""
    response = client.get("/")
    html = response.text

    screens = ["screen-home", "screen-chat", "screen-weather", "screen-alerts", "screen-profile", "screen-settings"]
    for s in screens:
        assert f'id="{s}"' in html

    # Check accessibility attributes
    assert 'role="navigation"' in html
    assert 'role="main"' in html
    assert 'role="alert"' in html
    assert 'aria-label=' in html


def test_07_touch_target_sizes_min_44px():
    """7. Test CSS contains WCAG 2.1 AA min-height 44px touch target rules."""
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    assert os.path.exists(css_path)

    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert "min-height: 44px" in css
    assert "touch-action: manipulation" in css
    assert ".mobile-bottom-nav" in css
    assert ".offline-bar" in css


def test_08_environment_configuration():
    """8. Test zero hardcoded production secrets in frontend/mobile JavaScript files."""
    js_files = [
        os.path.join(FRONTEND_DIR, "app.js"),
        os.path.join(FRONTEND_DIR, "mobile", "apiClient.js")
    ]

    for file_path in js_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "sk-" not in content  # No OpenAI secret keys
        assert "AIzaSy" not in content  # No Google API secret keys
        assert "super-secret" not in content


def test_09_offline_and_degraded_states():
    """9. Test offline notification bar and error card elements exist in DOM and CSS."""
    response = client.get("/")
    html = response.text
    assert 'id="offlineBar"' in html
    
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".offline-bar" in css
    assert ".error-card" in css
    assert ".spinner" in css


def test_10_authentication_mobile_ui():
    """10. Test Mobile Profile and Authentication UI elements exist in index.html."""
    response = client.get("/")
    html = response.text

    assert 'id="authEmail"' in html
    assert 'id="authPassword"' in html
    assert 'id="loginSubmitBtn"' in html
    assert 'id="registerSubmitBtn"' in html
    assert 'id="savedLocationsList"' in html
