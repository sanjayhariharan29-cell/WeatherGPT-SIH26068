import os
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

def test_01_current_weather_dashboard_elements():
    """1. Test current weather card elements, temperature, rain prob, wind, humidity, condition display."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    assert 'id="tempVal"' in html
    assert 'id="rainProbVal"' in html
    assert 'id="windVal"' in html
    assert 'id="humidityVal"' in html
    assert 'id="conditionText"' in html
    assert 'id="agreementVal"' in html


def test_02_forecast_timelines():
    """2. Test forecast timelines for Today, Tomorrow, and Extended Future forecasts."""
    response = client.get("/")
    html = response.text

    assert 'id="forecastGridToday"' in html
    assert 'id="forecastGridTomorrow"' in html
    assert 'id="forecastGridFuture"' in html


def test_03_official_warning_priority_banner():
    """3. Test official warning banner is prioritized visually with severity and source tags."""
    response = client.get("/")
    html = response.text

    assert 'id="alertBanner"' in html
    assert 'id="alertSeverityBadge"' in html
    assert 'id="alertTitle"' in html
    assert 'id="alertDesc"' in html
    assert 'id="alertSourceTag"' in html


def test_04_source_attribution():
    """4. Test source metadata tags (IMD / Open-Meteo) are rendered on current weather and alerts."""
    response = client.get("/")
    html = response.text

    assert 'id="currentSourceTag"' in html
    assert 'Source: IMD' in html


def test_05_data_freshness_badges():
    """5. Test data freshness badge (Fresh / Stale / Partial / Unavailable) elements and CSS rules."""
    response = client.get("/")
    html = response.text
    assert 'id="dataFreshnessTag"' in html

    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".freshness-tag.fresh" in css
    assert ".freshness-tag.stale" in css
    assert ".freshness-tag.partial" in css
    assert ".freshness-tag.unavailable" in css


def test_06_missing_fields_no_fake_zeros():
    """6. Test JavaScript app.js handles null/missing fields with '--' instead of fake zero '0'."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert '"--"' in js
    assert "undefined" in js or "null" in js


def test_07_unavailable_data_handling():
    """7. Test DATA_UNAVAILABLE state sets freshness tag to 'unavailable'."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "DATA_UNAVAILABLE" in js
    assert "freshnessTag.textContent = \"Data Unavailable\"" in js


def test_08_refresh_controls_and_auto_refresh():
    """8. Test refresh button element and 5-minute auto-refresh interval configuration."""
    response = client.get("/")
    html = response.text
    assert 'id="refreshBtn"' in html

    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "setInterval" in js
    assert "300000" in js  # 5 minutes in ms


def test_09_loading_skeleton_and_spinner():
    """9. Test loading skeleton and spinner elements exist in dashboard HTML and CSS."""
    response = client.get("/")
    html = response.text
    assert 'id="dashboardSkeleton"' in html

    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".spinner" in css


def test_10_dashboard_error_card_and_retry():
    """10. Test error card and retry button elements exist in DOM."""
    response = client.get("/")
    html = response.text
    assert 'id="dashboardErrorCard"' in html
    assert 'id="dashboardRetryBtn"' in html


def test_11_mobile_responsive_rendering_and_accessibility():
    """11. Test mobile responsive layout, touch target size, ARIA attributes, and viewport meta tag."""
    response = client.get("/")
    html = response.text

    assert 'name="viewport"' in html
    assert 'viewport-fit=cover' in html
    assert 'aria-live="polite"' in html
    assert 'role="main"' in html

    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert "@media (max-width: 768px)" in css
    assert "min-height: 44px" in css
