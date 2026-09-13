import re
from pathlib import Path
import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def test_html_structure_for_theme_and_hero_atmosphere():
    """Verify HTML contains theme toggle button, atmosphere canvas container, and theme settings selector."""
    html_path = FRONTEND_DIR / "index.html"
    assert html_path.exists(), "index.html must exist"
    content = html_path.read_text(encoding="utf-8")

    # Theme toggle button in header
    assert 'id="themeToggleBtn"' in content, "index.html must have #themeToggleBtn"
    assert 'id="themeToggleIcon"' in content, "index.html must have #themeToggleIcon"

    # Hero atmosphere container, ambient background, and canvas inside weatherCardContainer
    assert 'id="weatherCardContainer"' in content, "index.html must have #weatherCardContainer"
    assert 'id="heroAtmosphereContainer"' in content, "index.html must have #heroAtmosphereContainer"
    assert 'id="heroAtmosphereAmbient"' in content, "index.html must have #heroAtmosphereAmbient"
    assert 'id="heroAtmosphereCanvas"' in content, "index.html must have #heroAtmosphereCanvas"

    # Theme appearance dropdown in Settings screen
    assert 'id="themeSelect"' in content, "index.html must have #themeSelect dropdown"
    assert 'value="system"' in content, "themeSelect must include system option"
    assert 'value="dark"' in content, "themeSelect must include dark option"
    assert 'value="light"' in content, "themeSelect must include light option"


def test_css_tokens_and_hero_atmosphere_styling():
    """Verify CSS has dark mode tokens, condition ambient gradients, and proper z-indexing."""
    css_path = FRONTEND_DIR / "styles.css"
    assert css_path.exists(), "styles.css must exist"
    content = css_path.read_text(encoding="utf-8")

    # Dark Theme tokens
    assert '[data-theme="dark"]' in content, "styles.css must define [data-theme='dark'] tokens"
    assert "@media (prefers-color-scheme: dark)" in content, "styles.css must support prefers-color-scheme: dark"

    # Atmosphere container & canvas positioning
    assert ".hero-atmosphere-container" in content, "styles.css must define .hero-atmosphere-container"
    assert ".hero-atmosphere-ambient" in content, "styles.css must define .hero-atmosphere-ambient"
    assert ".hero-atmosphere-canvas" in content, "styles.css must define .hero-atmosphere-canvas"

    # Ensure hero content sits above canvas (z-index layering for glassmorphic contrast)
    assert ".hero-weather-card > *:not(.hero-atmosphere-container)" in content, (
        "styles.css must ensure card content sits above atmosphere canvas (z-index >= 2)"
    )

    # Condition ambient classes (Light & Dark)
    for cls in ["ambient-clear-day", "ambient-clear-night", "ambient-rain", "ambient-cloudy", "ambient-storm"]:
        assert f".{cls}" in content, f"styles.css must define .{cls}"
        assert f'[data-theme="dark"] .{cls}' in content or f'[data-theme="dark"]' in content, (
            f"styles.css must define dark variant for .{cls}"
        )


def test_app_js_theme_management_and_hero_engine():
    """Verify frontend/app.js implements theme system and condition-reactive HeroAtmosphereEngine."""
    app_js_path = FRONTEND_DIR / "app.js"
    assert app_js_path.exists(), "app.js must exist"
    content = app_js_path.read_text(encoding="utf-8")

    # Theme functions
    assert "function initAppTheme()" in content, "app.js must define initAppTheme()"
    assert "function setAppTheme(" in content, "app.js must define setAppTheme()"
    assert "function toggleAppTheme()" in content, "app.js must define toggleAppTheme()"
    assert "function resolveEffectiveTheme(" in content, "app.js must define resolveEffectiveTheme()"
    assert "function applyResolvedTheme(" in content, "app.js must define applyResolvedTheme()"

    # Hero Atmosphere functions and class
    assert "function initHeroWeatherAtmosphere()" in content, "app.js must define initHeroWeatherAtmosphere()"
    assert "function updateHeroWeatherAtmosphere(" in content, "app.js must define updateHeroWeatherAtmosphere()"
    assert "class HeroAtmosphereEngine" in content, "app.js must define class HeroAtmosphereEngine"

    # Condition reactions
    assert "normalizeCondition(" in content, "HeroAtmosphereEngine must have normalizeCondition()"
    assert "STORM" in content, "Must support STORM condition"
    assert "RAIN" in content, "Must support RAIN condition"
    assert "CLOUDY" in content, "Must support CLOUDY condition"
    assert "CLEAR" in content, "Must support CLEAR condition"

    # Performance, lifecycle & accessibility guards
    assert "checkReducedMotion()" in content, "HeroAtmosphereEngine must check prefers-reduced-motion"
    assert "prefers-reduced-motion" in content, "Must query prefers-reduced-motion media query"
    assert "visibilitychange" in content, "Must pause rendering when tab is hidden"

    # Integration hooks
    assert "initAppTheme();" in content, "initApp() must invoke initAppTheme()"
    assert "initHeroWeatherAtmosphere();" in content, "initApp() must invoke initHeroWeatherAtmosphere()"
    assert "updateHeroWeatherAtmosphere(data);" in content, "renderWeatherCard() must invoke updateHeroWeatherAtmosphere()"
    assert "heroAtmosphereEngine.resume()" in content, "navigateToScreen('home') must resume heroAtmosphereEngine"
    assert "heroAtmosphereEngine.pause()" in content, "navigateToScreen(other) must pause heroAtmosphereEngine"


def test_i18n_has_theme_keys():
    """Verify i18n.js has theme translation keys for EN, TA, and HI."""
    i18n_path = FRONTEND_DIR / "i18n.js"
    assert i18n_path.exists(), "i18n.js must exist"
    content = i18n_path.read_text(encoding="utf-8")

    assert '"settings.theme": "Appearance Theme"' in content, "EN must have settings.theme"
    assert '"settings.themeDesc": "Choose Light, Dark, or System theme"' in content, "EN must have settings.themeDesc"

    assert '"settings.theme": "தோற்ற தீம்"' in content, "TA must have settings.theme"
    assert '"settings.theme": "दिखावट थीम"' in content, "HI must have settings.theme"
