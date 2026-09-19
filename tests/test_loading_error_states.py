"""
Test suite verifying loading skeleton shimmers, friendly error states,
and retry mechanisms across Home, Forecast, Radar Map, Alerts, AQI, and Chat.
"""

import pytest
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
INDEX_HTML = REPO_ROOT / "frontend" / "index.html"
STYLES_CSS = REPO_ROOT / "frontend" / "styles.css"
APP_JS = REPO_ROOT / "frontend" / "app.js"
ANDROID_APP_JS = REPO_ROOT / "android" / "app" / "src" / "main" / "assets" / "public" / "app.js"
ANDROID_INDEX_HTML = REPO_ROOT / "android" / "app" / "src" / "main" / "assets" / "public" / "index.html"
ANDROID_STYLES_CSS = REPO_ROOT / "android" / "app" / "src" / "main" / "assets" / "public" / "styles.css"


def test_html_markup_contains_all_loading_and_error_elements():
    """Verify all screens have proper skeleton and error containers with retry buttons."""
    content = INDEX_HTML.read_text(encoding="utf-8")

    # 1. Home Weather Hero
    assert 'id="dashboardSkeleton"' in content
    assert 'hero-skeleton-card' in content
    assert 'id="dashboardStaleNotice"' in content
    assert 'id="dashboardStaleRetryBtn"' in content
    assert 'id="dashboardErrorCard"' in content
    assert 'id="dashboardRetryBtn"' in content

    # 2. Forecast Screen
    assert 'id="forecastErrorCard"' in content
    assert 'id="forecastRetryBtn"' in content
    assert "Couldn't load forecast data" in content

    # 3. Radar & Map Screen
    assert 'id="mapTileStatusChip"' in content
    assert 'id="mapTileRetryBtn"' in content
    assert 'id="mapCardErrorContainer"' in content
    assert 'id="mapCardRetryBtn"' in content
    assert 'id="mapCardBody"' in content

    # 4. Air Quality Screen
    assert 'id="aqiSkeleton"' in content
    assert 'id="aqiErrorCard"' in content
    assert 'id="aqiRetryBtn"' in content
    assert 'id="aqiContentContainer"' in content


def test_css_styles_contain_skeleton_and_error_tokens():
    """Verify CSS has skeleton animations, error cards, and floating status chip styles."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert "hero-skeleton-card" in css
    assert "skeletonShimmer" in css
    assert "forecast-skeleton-card" in css
    assert "daily-skeleton-row" in css
    assert "alert-skeleton-card" in css
    assert "aqi-skeleton-container" in css
    assert "inline-error-card" in css
    assert "inline-retry-btn" in css
    assert "stale-cache-banner" in css
    assert "map-tile-status-chip" in css


def test_app_js_loading_and_error_functions_exist():
    """Verify app.js contains all required helper functions and error handling."""
    js = APP_JS.read_text(encoding="utf-8")

    # Helper functions
    assert "function renderForecastLoadingSkeletons()" in js
    assert "function renderForecastErrorState(" in js
    assert "function renderAlertsLoadingSkeletons()" in js
    assert "function renderAlertsErrorState()" in js
    assert "function renderAqiLoadingSkeleton()" in js
    assert "function renderAqiErrorState(" in js

    # Home Weather
    assert "dashboardStaleNotice" in js
    assert "Couldn't load weather data" in js
    assert "dashboardRetryBtn" in js

    # Forecast
    assert "renderForecastLoadingSkeletons()" in js
    assert "renderForecastErrorState(" in js

    # Alerts
    assert "renderAlertsLoadingSkeletons()" in js
    assert "renderAlertsErrorState()" in js
    assert "Couldn't load active weather alerts" in js

    # AQI
    assert "renderAqiLoadingSkeleton()" in js
    assert "renderAqiErrorState(" in js
    assert "Couldn't load air quality telemetry" in js

    # Climate
    assert "Retry Climate Archive" in js

    # Map Selection
    assert "mapCardErrorContainer" in js
    assert "mapCardBody" in js
    assert "mapCardRetryBtn" in js

    # Radar & Weather Tile Status Chip
    assert "mapTileStatusChip" in js
    assert "mapTileRetryBtn" in js

    # Chat Assistant
    assert "Couldn't send message" in js
    assert "Retry Send" in js


def test_android_assets_are_synchronized():
    """Verify that Android public assets are 100% in sync with frontend/."""
    assert INDEX_HTML.read_text(encoding="utf-8") == ANDROID_INDEX_HTML.read_text(encoding="utf-8")
    assert APP_JS.read_text(encoding="utf-8") == ANDROID_APP_JS.read_text(encoding="utf-8")
    assert STYLES_CSS.read_text(encoding="utf-8") == ANDROID_STYLES_CSS.read_text(encoding="utf-8")


def test_explicit_five_features_loading_and_retry_states():
    """Explicitly verify that each of the 5 data-fetching features has:
    (1) a skeleton/spinner loading state
    (2) a specific retry-able error state (no blank or frozen UI)
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    # ---------------------------------------------------------
    # Feature 1: Current Weather (Home Hero Card)
    # ---------------------------------------------------------
    # (1) Loading: skeleton shimmer card while request is in flight
    assert 'id="dashboardSkeleton"' in html
    assert 'hero-skeleton-card' in html
    assert 'hero-skeleton-card' in css
    assert 'skeletonShimmer' in css
    assert 'skeleton.classList.remove("hidden")' in js
    # (2) Error: retry-able error message + button on fetch failure
    assert 'id="dashboardErrorCard"' in html
    assert 'id="dashboardRetryBtn"' in html
    assert "Couldn't load weather data — check your connection." in js
    assert 'retryBtn.onclick = () => loadCurrentWeather(true, true)' in js
    # Also stale fallback cache banner with retry
    assert 'id="dashboardStaleNotice"' in html
    assert 'id="dashboardStaleRetryBtn"' in html

    # ---------------------------------------------------------
    # Feature 2: Forecast (Hourly & 7-Day)
    # ---------------------------------------------------------
    # (1) Loading: hourly and daily skeleton cards + chart shimmer
    assert 'forecast-skeleton-card' in css
    assert 'daily-skeleton-row' in css
    assert 'function renderForecastLoadingSkeletons()' in js
    assert 'renderForecastLoadingSkeletons();' in js
    # (2) Error: inline error cards and screen error card with retry
    assert 'id="forecastErrorCard"' in html
    assert 'id="forecastRetryBtn"' in html
    assert 'function renderForecastErrorState(' in js
    assert "Couldn't load hourly forecast — check your connection" in js
    assert "Couldn't load 7-day forecast — check your connection" in js
    assert 'Retry Forecast' in js

    # ---------------------------------------------------------
    # Feature 3: Alerts (Severe Weather Warnings)
    # ---------------------------------------------------------
    # (1) Loading: alert skeleton shimmer cards
    assert 'alert-skeleton-card' in css
    assert 'function renderAlertsLoadingSkeletons()' in js
    # (2) Error: inline error card with specific retry button
    assert 'function renderAlertsErrorState()' in js
    assert "Couldn't load active weather alerts — check your connection" in js
    assert 'Retry Alerts' in js
    assert 'onclick="loadAllAlerts()"' in js

    # ---------------------------------------------------------
    # Feature 4: Air Quality (AQI Telemetry & Climate Archive)
    # ---------------------------------------------------------
    # (1) Loading: AQI gauge & pollutant skeleton grid + climate spinner
    assert 'id="aqiSkeleton"' in html
    assert 'aqi-skeleton-container' in css
    assert 'function renderAqiLoadingSkeleton()' in js
    assert 'progress_activity' in js  # Climate loading spinner
    assert 'animation: spin 1s linear infinite' in js
    # (2) Error: AQI error card + Climate retry button
    assert 'id="aqiErrorCard"' in html
    assert 'id="aqiRetryBtn"' in html
    assert 'function renderAqiErrorState(' in js
    assert "Couldn't load air quality telemetry — check your connection" in js
    assert 'Retry Climate Archive' in js

    # ---------------------------------------------------------
    # Feature 5: Conversational AI Chat (SkyZen Assistant)
    # ---------------------------------------------------------
    # (1) Loading: Bot typing indicator with reasoning status & animated dots
    assert 'function showTypingIndicator()' in js
    assert 'smart_toy' in js
    assert 'typing-dot' in js
    assert 'setButtonLoading(sendBtn, true, "Sending...")' in js
    # (2) Error: Specific retry-able error bubble with failed message resend
    assert 'function appendFailedMessage(' in js
    assert 'function retryFailedMessage(' in js
    assert "Couldn't send message — check your connection." in js
    assert 'Retry Send' in js
    assert 'msg-retry-btn' in js

