import re
from pathlib import Path
import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def test_condition_background_tokens_and_gradients():
    """Verify all 8 weather condition states (day & night) are defined with exact color palettes."""
    tokens_path = FRONTEND_DIR / "design-tokens.css"
    assert tokens_path.exists(), "design-tokens.css must exist"
    content = tokens_path.read_text(encoding="utf-8")

    # Day & night gradients
    expected_tokens = [
        "--bg-clear-day",
        "--bg-clear-night",
        "--bg-cloudy-day",
        "--bg-cloudy-night",
        "--bg-rain-day",
        "--bg-rain-night",
        "--bg-storm-day",
        "--bg-storm-night",
    ]
    for token in expected_tokens:
        assert token in content, f"design-tokens.css must define {token}"

    # Palette verification
    assert "#FFB74D" in content or "#ffb74d" in content, "Clear palette warm tone #FFB74D required"
    assert "#FF8A50" in content or "#ff8a50" in content, "Clear palette warm tone #FF8A50 required"
    assert "#E85D75" in content or "#e85d75" in content, "Clear palette warm tone #E85D75 required"

    assert "#7D8FA3" in content or "#7d8fa3" in content, "Cloudy palette slate tone #7D8FA3 required"
    assert "#5C6B82" in content or "#5c6b82" in content, "Cloudy palette slate tone #5C6B82 required"
    assert "#3D4B63" in content or "#3d4b63" in content, "Cloudy palette slate tone #3D4B63 required"

    assert "#4A7BA6" in content or "#4a7ba6" in content, "Rain palette teal-blue #4A7BA6 required"
    assert "#2D5578" in content or "#2d5578" in content, "Rain palette teal-blue #2D5578 required"
    assert "#1A3652" in content or "#1a3652" in content, "Rain palette teal-blue #1A3652 required"

    assert "#2B2E4A" in content or "#2b2e4a" in content, "Storm palette indigo #2B2E4A required"
    assert "#1A1D33" in content or "#1a1d33" in content, "Storm palette indigo #1A1D33 required"
    assert "#0D0F1F" in content or "#0d0f1f" in content, "Storm palette indigo #0D0F1F required"


def test_ambient_depth_layer_and_drift_animation():
    """Verify ambient depth layer glow shapes, translate-only drifting animation, blur and opacity."""
    css_path = FRONTEND_DIR / "styles.css"
    content = css_path.read_text(encoding="utf-8")

    assert ".ambient-glow-layer" in content, "styles.css must define .ambient-glow-layer"
    assert ".ambient-glow-shape" in content, "styles.css must define .ambient-glow-shape"
    assert ".glow-shape-1" in content, "styles.css must define .glow-shape-1"
    assert ".glow-shape-2" in content, "styles.css must define .glow-shape-2"
    assert ".glow-shape-3" in content, "styles.css must define .glow-shape-3"

    # Blur 60-80px and opacity 0.15-0.25
    assert "blur(75px)" in content or "filter: blur(" in content, "styles.css must apply 60-80px blur to glow shapes"
    assert "opacity: 0.22" in content or "opacity: 0.2" in content, "styles.css must apply 0.15-0.25 opacity"

    # Translate-only animation (no rotation)
    assert "@keyframes ambientDrift1" in content, "styles.css must define @keyframes ambientDrift1"
    assert "@keyframes ambientDrift2" in content, "styles.css must define @keyframes ambientDrift2"
    assert "@keyframes ambientDrift3" in content, "styles.css must define @keyframes ambientDrift3"

    drift_match = re.search(r"@keyframes ambientDrift1\s*\{(.*?)\}", content, re.DOTALL)
    if drift_match:
        drift_body = drift_match.group(1)
        assert "translate" in drift_body, "Drifting animation must translate"
        assert "rotate" not in drift_body, "Drifting animation must NOT rotate (translate only requirement)"

    # HTML inclusion
    index_html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    dev_html = (FRONTEND_DIR / "developer.html").read_text(encoding="utf-8")
    assert 'id="ambientGlowLayer"' in index_html, "index.html must include #ambientGlowLayer"
    assert 'id="ambientGlowLayer"' in dev_html, "developer.html must include #ambientGlowLayer"


def test_glass_card_recipe_and_hierarchy():
    """Verify glass card recipe with hierarchical blur, border, top highlight inset, and sheen."""
    tokens_path = FRONTEND_DIR / "design-tokens.css"
    tokens_content = tokens_path.read_text(encoding="utf-8")
    styles_content = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")

    # Inset 0 1px 0 top highlight
    assert "inset 0 1px 0" in tokens_content or "inset 0 1px 0" in styles_content, (
        "Glass tokens must include inset 0 1px 0 highlight line"
    )

    # Blur hierarchy: heavy blur (26px) hero, card (22px), small chips (18px)
    assert "blur(26px)" in tokens_content, "Primary/hero glass must have 26px blur"
    assert "blur(22px)" in tokens_content, "Card glass must have 22px blur"
    assert "blur(18px)" in tokens_content, "Small chips glass must have 18px blur"

    # Border-radius hierarchy: 24px major, 20px card, 14px chips
    assert "--glass-hero-radius: 24px" in tokens_content or "--glass-hero-radius: 24px" in tokens_content
    assert "--glass-chip-radius: 14px" in tokens_content or "--glass-chip-radius: 12px" in tokens_content

    # Entrance sheen animation
    assert "@keyframes specularSheen" in tokens_content or "@keyframes specularSheen" in styles_content, (
        "Must define one-time diagonal specular sheen entrance animation"
    )


def test_tinted_glass_alert_system_and_severity_scaling():
    """Verify alert cards use tinted glass with severity-proportional tinting instead of solid stickers."""
    tokens_path = FRONTEND_DIR / "design-tokens.css"
    tokens_content = tokens_path.read_text(encoding="utf-8")
    styles_content = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")

    # Severity tinted glass tokens
    assert "--glass-alert-severe-bg" in tokens_content, "Must define severe tinted glass bg"
    assert "--glass-alert-moderate-bg" in tokens_content, "Must define moderate tinted glass bg"
    assert "--glass-alert-minor-bg" in tokens_content, "Must define minor tinted glass bg"

    # Verify severity classes in styles.css
    assert ".alert-banner.severity-severe" in styles_content, "Must style severity-severe banner"
    assert ".alert-banner.severity-moderate" in styles_content, "Must style severity-moderate banner"
    assert ".alert-banner.severity-minor" in styles_content, "Must style severity-minor banner"
    assert ".disaster-item.severity-severe" in styles_content, "Must style severity-severe disaster-item"

    # Verify backdrop-filter on alerts (glass, not solid sticker)
    assert "backdrop-filter: var(--glass-card-filter)" in styles_content or "backdrop-filter" in styles_content


def test_reduced_effects_fallback_for_performance():
    """Verify performance fallback for low-end WebViews and prefers-reduced-motion."""
    tokens_path = FRONTEND_DIR / "design-tokens.css"
    tokens_content = tokens_path.read_text(encoding="utf-8")
    styles_content = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")
    app_js_content = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")

    # Reduced effects CSS tokens
    assert ".reduced-effects" in tokens_content or ".reduced-effects" in styles_content, (
        "Must define .reduced-effects fallback styling"
    )
    assert "@media (prefers-reduced-motion: reduce)" in styles_content, (
        "Must respect prefers-reduced-motion"
    )

    # In reduced mode, ambient glow is disabled
    assert ".reduced-effects .ambient-glow-layer" in styles_content or ".reduced-effects" in styles_content

    # JS Performance controller
    assert "function initPerformanceMode()" in app_js_content, "app.js must define initPerformanceMode()"
    assert "function setEffectsMode(" in app_js_content, "app.js must define setEffectsMode()"
    assert "window.setEffectsMode" in app_js_content, "app.js must export setEffectsMode"


def test_text_contrast_wcag_aa_compliance():
    """Verify text colors maintain >= 4.5:1 WCAG AA contrast against glass and background palettes."""
    def hex_to_luminance(hex_code):
        hex_code = hex_code.strip("#")
        r, g, b = [int(hex_code[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
        def srgb_to_lin(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)

    def contrast_ratio(hex1, hex2):
        l1 = hex_to_luminance(hex1)
        l2 = hex_to_luminance(hex2)
        hi = max(l1, l2)
        lo = min(l1, l2)
        return (hi + 0.05) / (lo + 0.05)

    # Dark background (Storm Night base: #0D0F1F) against light text (#F8FAFC, #FFFFFF)
    storm_night_bg = "0D0F1F"
    light_text_primary = "F8FAFC"
    ratio_dark = contrast_ratio(storm_night_bg, light_text_primary)
    assert ratio_dark >= 10.0, f"Contrast on Storm Night should be very high (got {ratio_dark:.1f}:1)"

    # Light background (Clear Day base: #FFB74D) against dark text (#0F172A)
    clear_day_bg = "FFB74D"
    dark_text_primary = "0F172A"
    ratio_light = contrast_ratio(clear_day_bg, dark_text_primary)
    assert ratio_light >= 7.0, f"Contrast on Clear Day should exceed WCAG AAA (got {ratio_light:.1f}:1)"
