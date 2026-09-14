import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_01_bottom_nav_and_sidebar_have_i18n_keys():
    """Verify all navigation items have data-i18n attributes."""
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Bottom nav labels
    assert '<span class="nav-label" data-i18n="nav.home">Home</span>' in html
    assert '<span class="nav-label" data-i18n="nav.radar">Radar</span>' in html
    assert '<span class="nav-label" data-i18n="nav.alerts">Alerts</span>' in html
    assert '<span class="nav-label" data-i18n="nav.forecast">Forecast</span>' in html
    assert '<span class="nav-label" data-i18n="nav.ai">AI</span>' in html
    assert '<span class="nav-label" data-i18n="nav.aqi">AQI</span>' in html
    assert '<span class="nav-label" data-i18n="nav.settings">Settings</span>' in html

    # Desktop sidebar labels
    assert '<span class="nav-label" data-i18n="nav.home">Home</span>' in html
    assert '<span class="nav-label" data-i18n="nav.radar_map">Radar Map</span>' in html
    assert '<span class="nav-label" data-i18n="nav.forecast">Forecast</span>' in html
    assert '<span class="nav-label" data-i18n="nav.alerts">Alerts</span>' in html
    assert '<span class="nav-label" data-i18n="nav.ai">SkyZen AI</span>' in html
    assert '<span class="nav-label" data-i18n="nav.aqi">Air Quality</span>' in html
    assert '<span class="nav-label" data-i18n="nav.settings">Settings</span>' in html


def test_02_home_dashboard_chips_and_cards_have_i18n():
    """Verify Visibility, Nowcast, Chips, and AQI Title in index.html have data-i18n."""
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert '<span class="metric-label" data-i18n="dashboard.visibility">Visibility</span>' in html
    assert '<span data-i18n="dashboard.now">Now</span>' in html
    assert 'data-i18n="chip.all"' in html
    assert 'data-i18n="chip.commute"' in html
    assert 'data-i18n="chip.farmer"' in html
    assert 'data-i18n="chip.fitness"' in html
    assert 'data-i18n="chip.home_daily"' in html
    assert '<span data-i18n="aqi.title">Air Quality Index</span>' in html


def test_03_i18n_dictionary_has_all_required_keys():
    """Verify i18n.js has all required Tamil and Hindi translations."""
    with open("frontend/i18n.js", "r", encoding="utf-8") as f:
        js = f.read()

    required_keys = [
        "dashboard.now",
        "chat.reasoning",
        "lifestyle.unavailable",
        "lifestyle.cat_home_daily",
        "lifestyle.cat_agriculture",
        "lifestyle.cat_commute",
        "lifestyle.cat_transit",
        "lifestyle.cat_fitness",
        "lifestyle.cat_farming",
        "lifestyle.cat_daily_life",
        "lifestyle.title_laundry",
        "lifestyle.title_spray",
        "lifestyle.title_bike",
        "lifestyle.title_flood",
        "lifestyle.title_fitness",
        "lifestyle.title_harvest",
        "lifestyle.title_umbrella",
        "lifestyle.status_fast_dry",
        "lifestyle.status_indoor_drying",
        "lifestyle.status_slow_dry",
        "lifestyle.status_ideal_spray",
        "lifestyle.status_no_spray",
        "lifestyle.status_drift_caution",
        "lifestyle.status_smooth_ride",
        "lifestyle.status_skid_risk",
        "lifestyle.status_wet_asphalt",
        "lifestyle.status_clear_roads",
        "lifestyle.status_waterlogging",
        "lifestyle.status_spot_puddles",
        "lifestyle.status_great_workout",
        "lifestyle.status_indoor_cardio",
        "lifestyle.status_hydration_caution",
        "lifestyle.status_safe_harvest",
        "lifestyle.status_delay_harvest",
        "lifestyle.status_monitor_grain",
        "lifestyle.status_not_needed",
        "lifestyle.status_keep_in_bag",
        "lifestyle.status_must_carry",
        "lifestyle.metric_drying_index",
        "lifestyle.metric_wind_runoff",
        "lifestyle.metric_road_traction",
        "lifestyle.metric_drainage_risk",
        "lifestyle.metric_heat_index",
        "lifestyle.metric_solar_radiation",
        "lifestyle.metric_rain_prob",
        "lifestyle.unit_hrs",
        "lifestyle.unit_rain",
        "lifestyle.unit_wind",
        "lifestyle.unit_hum",
        "lifestyle.val_high_severe",
        "lifestyle.val_normal",
        "lifestyle.desc_laundry_opt",
        "lifestyle.desc_laundry_rain",
        "lifestyle.desc_laundry_slow",
        "lifestyle.desc_spray_opt",
        "lifestyle.desc_spray_rain",
        "lifestyle.desc_spray_caution",
        "lifestyle.desc_commute_opt",
        "lifestyle.desc_commute_rain",
        "lifestyle.desc_commute_caution",
        "lifestyle.desc_flood_opt",
        "lifestyle.desc_flood_alert",
        "lifestyle.desc_flood_heavy",
        "lifestyle.desc_flood_caution",
        "lifestyle.desc_fitness_opt",
        "lifestyle.desc_fitness_heat",
        "lifestyle.desc_fitness_caution",
        "lifestyle.desc_harvest_opt",
        "lifestyle.desc_harvest_rain",
        "lifestyle.desc_harvest_caution",
        "lifestyle.desc_umbrella_low",
        "lifestyle.desc_umbrella_mid",
        "lifestyle.desc_umbrella_high",
    ]

    for k in required_keys:
        assert f'"{k}":' in js, f"Missing key {k} in i18n.js"


def test_04_backend_chat_greeting_respects_tamil_language():
    """Verify backend chat integration returns Tamil greeting when language='ta'."""
    payload = {
        "message": "வணக்கம்",
        "persona": "student",
        "language": "ta",
        "location": {"name": "Chennai"}
    }
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "ta"
    assert "வணக்கம்" in data["answer"]
    assert "ஸ்கைசென்" in data["answer"]


def test_05_backend_chat_greeting_respects_hindi_language():
    """Verify backend chat integration returns Hindi greeting when language='hi'."""
    payload = {
        "message": "नमस्ते",
        "persona": "student",
        "language": "hi",
        "location": {"name": "Delhi"}
    }
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "hi"
    assert "नमस्ते" in data["answer"]
    assert "स्काईज़ेन" in data["answer"]
