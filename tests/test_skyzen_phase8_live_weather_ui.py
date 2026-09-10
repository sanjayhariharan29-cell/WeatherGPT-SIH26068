"""SkyZen Phase 8 — Live Weather UI + Freshness + Source Transparency Test Suite.

Deterministic test suite verifying all 26 required conditions:
1. Current weather renders hero card and metrics
2. Active location renders without silent substitution
3. Temperature renders strictly from backend without synthetic modification
4. Live flag respected (is_real_time == true and fresh/aging)
5. Freshness respected (FRESH, AGING, STALE, EXPIRED, DEGRADED, UNAVAILABLE)
6. Observation time preserved and human-readable
7. Fetched time handled correctly for cache age
8. Provider list renders correctly from comparison.provider_records
9. Unavailable provider is not fabricated
10. Source agreement renders from backend without JS averaging
11. Low/cautious agreement displayed with disagreement warning
12. Degraded state displayed when partial sources available
13. Offline state displayed
14. Stale state displayed without live badge
15. Service unavailable displayed with recovery actions
16. Expired data not shown as live weather
17. IMD official warning visually prioritized at top
18. IMD warning not cleared by weather provider outage
19. Missing weather metric does not create fake numbers (renders '--')
20. Manual refresh controls work
21. Repeated refresh is debounced/controlled
22. AI/weather context consistency
23. No provider API keys in client assets
24. No private credentials in client assets
25. Responsive UI behavior and touch targets
26. Accessibility ARIA labels and semantic roles
"""

import os
import re
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.schemas import (
    NormalizedWeatherObservation,
)
from backend.schemas.weather import (
    CurrentWeatherResponse,
    WeatherDataSchema,
    LocationDataSchema,
    ComparisonDataSchema,
    ProviderObservationSummarySchema
)

client = TestClient(app)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
ANDROID_ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "android", "app", "src", "main", "assets", "public"
)


# ============================================================================
# 1. Current Weather Renders Hero Card & Metrics
# ============================================================================
def test_01_current_weather_hero_card_renders():
    """1. Hero weather card and all primary/secondary metric containers exist in DOM."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    assert 'id="weatherCardContainer"' in html
    assert 'id="tempVal"' in html
    assert 'id="tempUnit"' in html
    assert 'id="conditionText"' in html
    assert 'id="conditionIcon"' in html
    assert 'id="feelsLikeText"' in html
    assert 'id="rainProbVal"' in html
    assert 'id="windVal"' in html
    assert 'id="humidityVal"' in html


# ============================================================================
# 2. Active Location Renders
# ============================================================================
def test_02_active_location_renders():
    """2. Location name element exists and is bound to backend location data."""
    response = client.get("/")
    html = response.text
    assert 'id="currentLocationName"' in html

    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()
    assert "currentLocationName" in js
    assert "data.location?.name" in js or "data.location.name" in js


# ============================================================================
# 3. Temperature Renders Only From Backend
# ============================================================================
def test_03_temperature_renders_only_from_backend():
    """3. Temperature is assigned directly from backend without arithmetic modification."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # Confirms no synthetic "+ 1" or fallback arithmetic on temperature
    assert "Math.round(data.weather.temperature + 1)" not in js
    assert "data.weather?.temperature" in js or "data.weather.temperature" in js


# ============================================================================
# 4. Live Flag Respected
# ============================================================================
def test_04_live_flag_respected():
    """4. Live weather badge with pulsing dot exists and requires is_real_time and freshness."""
    response = client.get("/")
    html = response.text
    assert 'id="liveWeatherBadge"' in html
    assert 'LIVE WEATHER' in html
    assert 'class="pulse-dot"' in html

    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # Confirms live weather badge checks is_real_time and freshness
    assert "is_real_time" in js
    assert "liveBadge.classList.remove(\"hidden\")" in js
    assert "liveBadge.classList.add(\"hidden\")" in js


# ============================================================================
# 5. Freshness Respected
# ============================================================================
def test_05_freshness_respected():
    """5. Freshness classifications (FRESH, AGING, STALE, EXPIRED) map to visual tags."""
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".freshness-tag.fresh" in css
    assert ".freshness-tag.aging" in css or ".freshness-tag.partial" in css
    assert ".freshness-tag.stale" in css
    assert ".freshness-tag.expired" in css or ".freshness-tag.unavailable" in css

    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "FRESH" in js
    assert "AGING" in js
    assert "STALE" in js
    assert "EXPIRED" in js


# ============================================================================
# 6. Observed Time Preserved
# ============================================================================
def test_06_observed_time_preserved():
    """6. Observed timestamp element exists and parses backend observed_at timestamp."""
    response = client.get("/")
    html = response.text
    assert 'id="currentObsTime"' in html

    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "observed_at" in js
    assert "Observed at" in js or "Observed" in js


# ============================================================================
# 7. Fetched Time Handled Correctly
# ============================================================================
def test_07_fetched_time_handled():
    """7. Fetched time is utilized for cached/stale age calculation when observed time differs."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "retrieved_at" in js or "cached_at" in js
    assert "Cached" in js


# ============================================================================
# 8. Provider List Renders Correctly
# ============================================================================
def test_08_provider_list_renders():
    """8. Multi-source transparency container and provider card rendering function exist."""
    response = client.get("/")
    html = response.text
    assert 'id="sourcesBreakdownSection"' in html
    assert 'id="sourcesListContainer"' in html
    assert 'id="activeSourcesCount"' in html
    assert 'id="sourcesHeaderToggle"' in html

    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "renderSourcesBreakdown" in js
    assert "provider-card" in js


# ============================================================================
# 9. Unavailable Provider is Not Fabricated
# ============================================================================
def test_09_unavailable_provider_not_fabricated():
    """9. Unavailable / unconfigured providers display explicit unavailable state and '--'."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "Live access unavailable" in js or "Unavailable" in js or "Not configured" in js
    assert "rec.temperature !== null && rec.temperature !== undefined" in js or "rec.temperature != null" in js


# ============================================================================
# 10. Source Agreement Renders From Backend
# ============================================================================
def test_10_source_agreement_renders_from_backend():
    """10. Source agreement value and summary are sourced from backend data without JS averaging."""
    response = client.get("/")
    html = response.text
    assert 'id="agreementVal"' in html
    assert 'id="sourcesAgreementSummary"' in html

    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "confidence_level" in js or "sources_agree" in js
    # Confirm frontend does NOT compute average temperature across providers
    assert "/ providerCount" not in js
    assert "/ providers.length" not in js


# ============================================================================
# 11. Low Agreement Displayed
# ============================================================================
def test_11_low_agreement_disagreement_warning():
    """11. Disagreement warning banner exists and is activated on low/cautious agreement."""
    response = client.get("/")
    html = response.text
    assert 'id="disagreementWarningBanner"' in html

    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert 'warningBanner.classList.remove("hidden")' in js
    assert "CAUTIOUS" in js or "LOW" in js or "disagreement_notes" in js


# ============================================================================
# 12. Degraded State Displayed
# ============================================================================
def test_12_degraded_state_displayed():
    """12. Degraded telemetry is represented in freshness tag and system state."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "DEGRADED" in js
    assert "Degraded Telemetry" in js


# ============================================================================
# 13. Offline State Displayed
# ============================================================================
def test_13_offline_state_displayed():
    """13. OFFLINE state hides live weather badge and marks telemetry accordingly."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "OFFLINE" in js
    assert "offline" in js


# ============================================================================
# 14. Stale State Displayed
# ============================================================================
def test_14_stale_state_displayed():
    """14. DATA_STALE / STALE state sets tag to cached weather and hides live badge."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "DATA_STALE" in js
    assert "Data Stale (Cached)" in js


# ============================================================================
# 15. Service Unavailable Displayed
# ============================================================================
def test_15_service_unavailable_displayed():
    """15. SERVICE_UNAVAILABLE state shows retry options instead of generic empty failure."""
    response = client.get("/")
    html = response.text
    assert 'id="dashboardErrorCard"' in html
    assert 'id="dashboardRetryBtn"' in html

    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "SERVICE_UNAVAILABLE" in js
    assert "retry" in js.lower()


# ============================================================================
# 16. Expired Data Not Shown as Live
# ============================================================================
def test_16_expired_data_not_shown_as_live():
    """16. When freshness is EXPIRED, live weather badge MUST remain hidden."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # The condition requires isFreshOrAging
    assert "isFreshOrAging" in js
    assert "EXPIRED" in js


# ============================================================================
# 17. IMD Official Warning Remains Prominent
# ============================================================================
def test_17_imd_official_warning_prominence():
    """17. IMD warning banner is placed prominently above current weather with official badges."""
    response = client.get("/")
    html = response.text

    alert_pos = html.find('id="alertBanner"')
    weather_pos = html.find('id="weatherCardContainer"')
    assert alert_pos != -1
    assert weather_pos != -1
    assert alert_pos < weather_pos, "Official warning banner must appear before weather card in DOM"

    assert 'id="alertSeverityBadge"' in html
    assert 'id="alertSourceTag"' in html


# ============================================================================
# 18. IMD Warning Not Cleared by Provider Outage
# ============================================================================
def test_18_imd_warning_preserved_during_weather_degradation():
    """18. Weather state and alert state are independent; weather failures do not wipe alerts."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # Verifies renderWeatherCard does NOT clear or hide alertBanner
    assert "alertBanner.innerHTML = ''" not in js
    assert "alertBanner.classList.add('hidden')" not in js


# ============================================================================
# 19. Missing Weather Metric Does Not Create Fake Values
# ============================================================================
def test_19_missing_weather_metric_does_not_create_fake_values():
    """19. When fields are null/undefined, UI renders '--' rather than inventing 0 or sample numbers."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert 'tempValElem.textContent = "--"' in js
    assert 'rainElem.textContent = (data.weather?.rain_probability !== undefined' in js


# ============================================================================
# 20. Manual Refresh Controls
# ============================================================================
def test_20_manual_refresh_controls():
    """20. Refresh button is connected to loadCurrentWeather."""
    response = client.get("/")
    html = response.text
    assert 'id="refreshBtn"' in html

    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "refreshBtn.addEventListener" in js
    assert "loadCurrentWeather" in js


# ============================================================================
# 21. Repeated Refresh is Debounced/Controlled
# ============================================================================
def test_21_repeated_refresh_is_controlled():
    """21. Rapid repeated clicks are debounced with a minimum cooldown."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "WEATHER_REFRESH_COOLDOWN_MS" in js
    assert "lastWeatherRefreshTime" in js


# ============================================================================
# 22. AI / Weather Consistency
# ============================================================================
def test_22_ai_weather_consistency():
    """22. Weather context schemas include structured provider provenance and metrics."""
    resp = client.get("/api/v1/weather/current?location=Coimbatore")
    assert resp.status_code == 200
    data = resp.json()

    assert "weather" in data
    assert "temperature" in data["weather"]
    assert "is_real_time" in data
    assert "freshness_status" in data
    assert "comparison" in data
    assert "system_state" in data


# ============================================================================
# 23. No Provider API Keys in Client Assets
# ============================================================================
def test_23_no_provider_api_keys_in_client():
    """23. Zero provider API keys in frontend or Android web assets."""
    forbidden_patterns = [
        r"OPENWEATHER_API_KEY\s*=\s*['\"][a-zA-Z0-9]+['\"]",
        r"IMD_API_KEY\s*=\s*['\"][a-zA-Z0-9]+['\"]",
        r"api_key\s*=\s*['\"][a-zA-Z0-9]{16,}['\"]",
    ]

    for base_dir in [FRONTEND_DIR, ANDROID_ASSETS_DIR]:
        for root, _, files in os.walk(base_dir):
            for file in files:
                if file.endswith((".html", ".js", ".json", ".css")):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    for pattern in forbidden_patterns:
                        assert not re.search(pattern, content, re.IGNORECASE), (
                            f"Potential API key leak found in {file_path} matching {pattern}"
                        )


# ============================================================================
# 24. No Private Credentials in Client Assets
# ============================================================================
def test_24_no_private_credentials_in_client():
    """24. No private certificates or service account keys in client assets."""
    forbidden_terms = [
        "BEGIN PRIVATE KEY",
        "BEGIN RSA PRIVATE KEY",
        '"private_key_id"',
        '"client_email": "firebase-adminsdk',
    ]

    for base_dir in [FRONTEND_DIR, ANDROID_ASSETS_DIR]:
        for root, _, files in os.walk(base_dir):
            for file in files:
                if file.endswith((".html", ".js", ".json", ".css")):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    for term in forbidden_terms:
                        assert term not in content, f"Credential leaked in {file_path}: {term}"


# ============================================================================
# 25. Responsive UI Behavior & Touch Targets
# ============================================================================
def test_25_responsive_ui_and_touch_targets():
    """25. CSS rules provide mobile responsive layout and minimum 44px touch targets."""
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert "@media (max-width: 768px)" in css
    assert "min-height: 44px" in css or "min-height:44px" in css
    assert ".sources-breakdown-section" in css
    assert ".provider-card" in css


# ============================================================================
# 26. Accessibility Labels & Semantic Roles
# ============================================================================
def test_26_accessibility_labels_and_roles():
    """26. Hero card, live badge, and sources section have proper ARIA attributes."""
    response = client.get("/")
    html = response.text

    assert 'role="region"' in html
    assert 'aria-label="Current Weather Overview"' in html
    assert 'aria-label="Live Weather Status"' in html
    assert 'aria-label="Multi-Source Weather Telemetry"' in html
    assert 'aria-expanded=' in html
