"""
Automated QA Test Suite: Comprehensive Tappable Controls, Active Feedback & Button Loading Audit
Confirms that all buttons, toggles, nav items, and tappable controls give immediate visual feedback on tap,
and that in-flight loading indicators are rendered for all noticeable actions across SkyZen & Developer Console.
"""
import re
import pytest

def test_styles_has_universal_active_feedback():
    with open("frontend/styles.css", "r", encoding="utf-8") as f:
        css = f.read()

    # Must contain universal active rules
    assert "button:active" in css
    assert '[role="button"]:active' in css
    
    # Check all key tappable control classes
    required_active_selectors = [
        ".nav-item:active",
        ".map-tile-btn:active",
        ".map-layer-pill:active",
        ".map-action-btn:active",
        ".map-control-btn:active",
        ".chip-btn:active",
        ".speech-btn:active",
        ".lifestyle-chip:active",
        ".why-answer-toggle-btn:active",
        ".icon-btn:active",
        ".loc-btn:active",
        ".tab-btn:active",
        ".auth-btn:active",
        ".auth-primary-btn:active",
        ".auth-secondary-btn:active",
        ".auth-icon-back-btn:active",
        ".sub-screen-back-btn:active",
        ".password-toggle-btn:active",
        ".auth-text-link:active",
        ".auth-link-btn:active",
        ".pwa-install-btn-primary:active",
        ".pwa-install-btn-secondary:active",
        ".retry-btn:active",
        ".inline-retry-btn:active",
        ".tile-retry-btn:active",
        ".msg-retry-btn:active",
        ".send-btn:active",
        "#themeToggleBtn:active"
    ]
    for sel in required_active_selectors:
        assert sel in css, f"Missing active feedback selector: {sel}"

    # Must contain button loading state rules
    assert ".btn-loading" in css
    assert ".spin-anim" in css
    assert "@keyframes spin" in css

def test_developer_console_active_and_loading_feedback():
    with open("frontend/developer.html", "r", encoding="utf-8") as f:
        html = f.read()

    # CSS tap feedback
    assert ".dev-btn:active" in html
    assert ".spin-anim" in html
    assert "@keyframes spin" in html
    assert ".btn-loading" in html

    # Actions loading states
    assert "btn.classList.add(\"btn-loading\")" in html or "btnSubmit.classList.add(\"btn-loading\")" in html
    assert "btnSubmit.classList.add(\"btn-loading\")" in html
    assert "btn.classList.add(\"btn-loading\")" in html
    assert "btnEl.classList.add(\"btn-loading\")" in html
    assert "progress_activity" in html

def test_app_js_set_button_loading_implementation():
    with open("frontend/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    # Helper function definition
    assert "function setButtonLoading(btn, isLoading, loadingText" in js

    # Chat send button in-flight loading
    assert "setButtonLoading(sendBtn, true" in js
    assert "setButtonLoading(sendBtn, false)" in js

    # Top GPS location button in-flight loading
    assert "setButtonLoading(geoBtn, true, \"Locating...\")" in js
    assert "setButtonLoading(geoBtn, false)" in js

    # Map GPS location button in-flight loading
    assert "setButtonLoading(myLocBtn, true, \"Locating...\")" in js
    assert "setButtonLoading(myLocBtn, false)" in js

    # Map save location button in-flight loading
    assert "setButtonLoading(saveBtn, true, \"Saving...\")" in js
    assert "setButtonLoading(saveBtn, false)" in js

    # Auth Login submit button in-flight loading
    assert "setButtonLoading(submitBtn, true, \"Signing In...\")" in js

    # Auth Register submit button in-flight loading
    assert "setButtonLoading(submitBtn, true, \"Creating Account...\")" in js

    # Auth Verify Email submit button in-flight loading
    assert "setButtonLoading(submitBtn, true, \"Verifying...\")" in js

    # Auth Resend Code button in-flight loading
    assert "setButtonLoading(verifyResendBtn, true, \"Resending...\")" in js

    # Auth Forgot Password submit button in-flight loading
    assert "setButtonLoading(submitBtn, true, \"Generating Code...\")" in js

    # Auth Reset Password submit button in-flight loading
    assert "setButtonLoading(submitBtn, true, \"Updating...\")" in js

    # Onboarding Profile submit button in-flight loading
    assert "setButtonLoading(submitBtn, true, \"Saving Profile...\")" in js

    # Profile Settings Save button in-flight loading
    assert "setButtonLoading(submitBtn, true, \"Saving...\")" in js

    # Controlled Test Push Notification button in-flight loading
    assert "setButtonLoading(sendTestNotificationBtn, true, \"Dispatching...\")" in js
    assert "setButtonLoading(sendTestNotificationBtn, false)" in js

    # Saved location delete button in-flight loading
    assert "deleteSavedLoc(id, btn)" in js
    assert "setButtonLoading(btn, true, \"\")" in js

def test_android_assets_are_synchronized():
    for filename in ["styles.css", "app.js", "developer.html"]:
        with open(f"frontend/{filename}", "rb") as f_front:
            front_data = f_front.read()
        with open(f"android/app/src/main/assets/public/{filename}", "rb") as f_asset:
            asset_data = f_asset.read()
        assert front_data == asset_data, f"Android asset {filename} is out of sync with frontend/{filename}"
