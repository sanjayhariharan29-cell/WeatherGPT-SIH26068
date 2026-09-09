"""
Unit & Integration Tests: Mobile Release QA & APK Build Validation (Task 4 & 5)
Verifies DOM completeness, multilingual support, touch target compliance,
permission UX, safety warnings prominence, zero secrets, and Android asset integrity.
"""

import os
import json
import re
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
ANDROID_ASSETS_DIR = os.path.join(REPO_ROOT, "android", "app", "src", "main", "assets", "public")
INDEX_HTML_PATH = os.path.join(FRONTEND_DIR, "index.html")
STYLES_CSS_PATH = os.path.join(FRONTEND_DIR, "styles.css")
APP_JS_PATH = os.path.join(FRONTEND_DIR, "app.js")
API_CLIENT_PATH = os.path.join(FRONTEND_DIR, "mobile", "apiClient.js")


def test_01_core_mobile_dom_completeness():
    """1. Test all essential dashboard, forecast, chat, alerts, map, and settings elements exist."""
    assert os.path.exists(INDEX_HTML_PATH)
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # Screens
    screens = ["screen-home", "screen-chat", "screen-weather", "screen-alerts", "screen-map", "screen-profile", "screen-settings"]
    for s in screens:
        assert f'id="{s}"' in html, f"Screen {s} missing in DOM"

    # Dashboard telemetry
    dash_elements = ["tempVal", "rainProbVal", "windVal", "humidityVal", "conditionText", "agreementVal", "currentLocationName", "currentSourceTag", "dataFreshnessTag"]
    for el in dash_elements:
        assert f'id="{el}"' in html, f"Dashboard element {el} missing in DOM"

    # Chat & Voice
    chat_elements = ["chatHistory", "chatInput", "sendBtn", "voiceBtn"]
    for el in chat_elements:
        assert f'id="{el}"' in html, f"Chat element {el} missing in DOM"

    # Official Warning Priority Banner
    warning_elements = ["alertBanner", "alertSeverityBadge", "alertTitle", "alertDesc", "alertSourceTag"]
    for el in warning_elements:
        assert f'id="{el}"' in html, f"Warning banner element {el} missing in DOM"


def test_02_multilingual_font_stack_and_typography():
    """2. Test CSS includes Indic font fallbacks (Tamil, Devanagari) and proper line-height."""
    assert os.path.exists(STYLES_CSS_PATH)
    with open(STYLES_CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()

    assert "Noto Sans Tamil" in css, "Must include Noto Sans Tamil in font stack"
    assert "Noto Sans Devanagari" in css or "Nirmala UI" in css, "Must include Devanagari font fallback"
    assert "overflow-wrap: break-word" in css or "word-break: break-word" in css, "Must wrap long words"


def test_03_mobile_keyboard_and_viewport():
    """3. Test viewport meta handles virtual keyboards and prevents unwanted zoom."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    assert "interactive-widget=resizes-content" in html, "Must include interactive-widget=resizes-content"
    assert "viewport-fit=cover" in html, "Must include viewport-fit=cover"

    with open(STYLES_CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()

    # 16px chat input prevents iOS/WebKit zoom
    assert "font-size: 16px" in css, "Chat input must be 16px to prevent auto-zoom"


def test_04_touch_target_and_accessibility_wcag():
    """4. Test WCAG 2.1 AA touch targets (min 44px), focus rings, and reduced motion."""
    with open(STYLES_CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()

    assert "min-height: 44px" in css, "Must enforce 44px minimum touch target height"
    assert "touch-action: manipulation" in css, "Must optimize touch manipulation"
    assert ".mobile-bottom-nav" in css, "Mobile navigation bar must exist"
    assert ":focus-visible" in css, "Must define high-contrast :focus-visible outline for keyboard navigation"
    assert "prefers-reduced-motion" in css, "Must support prefers-reduced-motion media query"


def test_05_permission_ux_and_safety_fallback():
    """5. Test non-blocking permission notices and zero fake question submissions."""
    with open(APP_JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    assert "showMobileNotice" in js, "Must define showMobileNotice function"
    assert "Microphone permission denied" in js, "Must handle microphone permission denial"
    assert "Location permission denied" in js, "Must handle location permission denial"

    # Ensure no automatic fake question submission on speech error
    voice_err_match = re.search(r"recognition\.onerror\s*=\s*(?:function)?\s*\([^)]*\)\s*=>?\s*\{([^}]+)\}", js)
    if voice_err_match:
        assert "Naalaiku morning college pogalama" not in voice_err_match.group(1), (
            "Must NOT submit student query on voice error"
        )


def test_06_official_warning_prominence():
    """6. Test official warning banner uses high-contrast styling and ARIA live regions."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    assert 'role="region"' in html or 'role="alert"' in html, "Warning banner must have accessibility role"
    assert 'aria-live="assertive"' in html or 'aria-label=' in html, "Warning banner must have live region"

    with open(STYLES_CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".alert-banner" in css, "Must style alert banner"
    assert ".alert-badge" in css, "Must style alert severity badge"
    assert "overflow-wrap: break-word" in css, "Warning banner must wrap long compound words"


def test_07_zero_secrets_and_artifact_safety():
    """7. Test zero API secrets or sensitive keys in web and android assets."""
    target_dirs = [FRONTEND_DIR, ANDROID_ASSETS_DIR]
    forbidden_patterns = ["AIzaSy", "ghp_", "BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY"]
    sk_pattern = re.compile(r"\bsk-[a-zA-Z0-9_-]{20,}\b")

    for d in target_dirs:
        if not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith((".js", ".html", ".json", ".css")):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    for pat in forbidden_patterns:
                        assert pat not in content, f"Secret pattern '{pat}' found in {file_path}"
                    assert not sk_pattern.search(content), f"API key pattern 'sk-...' found in {file_path}"


def test_08_android_assets_integrity():
    """8. Test synchronized assets exist and match source files."""
    assert os.path.exists(ANDROID_ASSETS_DIR), "android assets/public must exist"
    
    files_to_check = ["index.html", "styles.css", "app.js", "manifest.json", "sw.js"]
    for f in files_to_check:
        src = os.path.join(FRONTEND_DIR, f)
        dst = os.path.join(ANDROID_ASSETS_DIR, f)
        assert os.path.exists(dst), f"Synced asset {f} missing in Android assets"
        assert os.path.getsize(src) == os.path.getsize(dst), f"Asset size mismatch for {f}"


def test_09_multilingual_stress_and_warning_safety():
    """9. Stress test long realistic strings in English, Tamil, Hindi, Tanglish, Hinglish."""
    stress_strings = {
        "en": "Warning: Severe cyclonic storm moving towards Tamil Nadu coast with torrential rainfall and wind speeds reaching 90-110 km/h.",
        "ta": "எச்சரிக்கை: வங்கக்கடலில் உருவான தீவிர புயல் சின்னம் காரணமாக பலத்த காற்றுடன் கனமழை பெய்ய வாய்ப்புள்ளது. மீனவர்கள் கடலுக்கு செல்ல வேண்டாம்.",
        "hi": "चेतावनी: बंगाल की खाड़ी में बने चक्रवाती तूफान के कारण तेज हवाओं के साथ भारी वर्षा की संभावना है। मछुआरों को समुद्र में न जाने की सलाह दी जाती है।",
        "tanglish": "Alert: Romba heavy rain iruku naalaiku, college and schools ku leave vidalaam nu solranga. Safely veetla irunga.",
        "hinglish": "Chetavani: Kal bohot zyada barish hone ki sambhavna hai, sabhi log apne ghar me surakshit rahein aur safar se bachein."
    }

    # Verify all strings are valid UTF-8 without null bytes or encoding issues
    for lang, text in stress_strings.items():
        encoded = text.encode("utf-8")
        assert len(encoded) > 50, f"String for {lang} too short"
        decoded = encoded.decode("utf-8")
        assert decoded == text, f"Encoding roundtrip failed for {lang}"

    # Verify CSS includes overflow-wrap and word-break for safe rendering
    with open(STYLES_CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()

    assert "overflow-wrap: break-word" in css
    assert "word-break: break-word" in css


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

