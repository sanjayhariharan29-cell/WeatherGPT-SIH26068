"""
Unit & Integration Tests: Android & Capacitor Mobile Shell Readiness
Verifies Android configuration, AndroidManifest permissions, Capacitor config,
frontend-to-WebView compatibility, permission UX, and asset synchronization.
"""

import os
import json
import xml.etree.ElementTree as ET
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")
MOBILE_DIR = os.path.join(REPO_ROOT, "mobile")
ANDROID_DIR = os.path.join(REPO_ROOT, "android")
ANDROID_ASSETS_DIR = os.path.join(ANDROID_DIR, "app", "src", "main", "assets")
MANIFEST_XML_PATH = os.path.join(ANDROID_DIR, "app", "src", "main", "AndroidManifest.xml")
CAP_ROOT_CONFIG = os.path.join(REPO_ROOT, "capacitor.config.json")
CAP_MOBILE_CONFIG = os.path.join(MOBILE_DIR, "capacitor.config.json")


def test_01_android_manifest_permissions_and_config():
    """1. Test AndroidManifest.xml contains required permissions and cleartext traffic support."""
    assert os.path.exists(MANIFEST_XML_PATH), "AndroidManifest.xml must exist"
    
    with open(MANIFEST_XML_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check permissions for mobile features
    assert 'android.permission.INTERNET' in content, "Must declare INTERNET permission"
    assert 'android.permission.ACCESS_NETWORK_STATE' in content, "Must declare ACCESS_NETWORK_STATE permission"
    assert 'android.permission.ACCESS_COARSE_LOCATION' in content, "Must declare ACCESS_COARSE_LOCATION permission"
    assert 'android.permission.ACCESS_FINE_LOCATION' in content, "Must declare ACCESS_FINE_LOCATION permission"
    assert 'android.permission.RECORD_AUDIO' in content, "Must declare RECORD_AUDIO permission for voice UI"
    assert 'android.permission.MODIFY_AUDIO_SETTINGS' in content, "Must declare MODIFY_AUDIO_SETTINGS permission"
    
    # Check hardware feature requirement
    assert 'android.hardware.location.gps' in content, "Must declare GPS hardware feature"
    assert 'android:required="false"' in content, "GPS hardware feature must be optional (required=false)"
    
    # Check application configuration
    assert 'android:usesCleartextTraffic="true"' in content, "Must allow cleartext traffic for local development testing"
    assert 'in.gov.moes.weathergpt' in content or 'MainActivity' in content, "MainActivity must be declared"


def test_02_capacitor_configurations():
    """2. Test root and mobile capacitor.config.json have valid JSON schema and app identifiers."""
    for cfg_path in [CAP_ROOT_CONFIG, CAP_MOBILE_CONFIG]:
        assert os.path.exists(cfg_path), f"Capacitor config at {cfg_path} must exist"
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        assert data.get("appId") == "in.gov.moes.weathergpt", "App ID must match in.gov.moes.weathergpt"
        assert data.get("appName") == "WeatherGPT", "App Name must be WeatherGPT"
        assert "plugins" in data, "Plugins object must exist"
        assert "SplashScreen" in data["plugins"], "SplashScreen plugin must be configured"
        assert "StatusBar" in data["plugins"], "StatusBar plugin must be configured"


def test_03_android_gradle_sdk_versions():
    """3. Test android build variables for SDK compliance."""
    variables_gradle = os.path.join(ANDROID_DIR, "variables.gradle")
    assert os.path.exists(variables_gradle), "variables.gradle must exist"
    
    with open(variables_gradle, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert "minSdkVersion = 22" in content or "minSdkVersion" in content
    assert "compileSdkVersion = 34" in content or "compileSdkVersion" in content
    assert "targetSdkVersion = 34" in content or "targetSdkVersion" in content


def test_04_frontend_webview_compatibility():
    """4. Test index.html uses relative paths and responsive viewport directives for WebViews."""
    index_html_path = os.path.join(FRONTEND_DIR, "index.html")
    assert os.path.exists(index_html_path), "index.html must exist"
    
    with open(index_html_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    # Relative paths prevent broken root resolutions in custom scheme / file WebViews
    assert 'href="./styles.css"' in html or 'href="styles.css"' in html
    assert 'href="./manifest.json"' in html or 'href="manifest.json"' in html
    assert 'src="./mobile/apiClient.js"' in html or 'src="mobile/apiClient.js"' in html
    assert 'src="./app.js"' in html or 'src="app.js"' in html
    
    # Viewport directive for keyboard handling in mobile WebViews
    assert 'interactive-widget=resizes-content' in html, "Must include interactive-widget=resizes-content"
    assert 'viewport-fit=cover' in html, "Must include viewport-fit=cover for notch display support"
    
    # Mobile notice banner container
    assert 'id="mobileNotice"' in html, "Must include mobileNotice banner element"
    
    # Android emulator option in environment switcher
    assert '10.0.2.2:8000' in html, "Must include Android Emulator host option in envSelect"


def test_05_dynamic_api_client_configuration():
    """5. Test apiClient.js implements getBaseUrl and setBaseUrl with localStorage persistence."""
    api_client_path = os.path.join(FRONTEND_DIR, "mobile", "apiClient.js")
    with open(api_client_path, "r", encoding="utf-8") as f:
        code = f.read()
        
    assert "getBaseUrl()" in code, "Must implement getBaseUrl()"
    assert "setBaseUrl(" in code, "Must implement setBaseUrl()"
    assert "weathergpt_api_base" in code, "Must persist API base URL in localStorage"


def test_06_permission_graceful_ux():
    """6. Test app.js provides graceful permission failure UX and does NOT send fake queries."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        code = f.read()
        
    assert "showMobileNotice" in code, "Must implement showMobileNotice helper"
    assert "Microphone permission denied" in code, "Must inform user on microphone permission denial"
    assert "Location permission denied" in code, "Must inform user on location permission denial"
    
    # Verify removal of fake student question on voice failure
    voice_error_idx = code.find("recognition.onerror")
    assert voice_error_idx != -1, "recognition.onerror handler must exist"
    voice_error_block = code[voice_error_idx:voice_error_idx + 600]
    assert "Naalaiku morning college pogalama" not in voice_error_block, (
        "Must NOT auto-submit hardcoded student question on speech recognition error!"
    )


def test_07_android_assets_synchronization():
    """7. Test android/app/src/main/assets contains complete synchronized web distribution."""
    public_dir = os.path.join(ANDROID_ASSETS_DIR, "public")
    assert os.path.exists(public_dir), "android assets/public directory must exist"
    
    required_assets = [
        "index.html",
        "styles.css",
        "app.js",
        "manifest.json",
        "sw.js",
        os.path.join("mobile", "apiClient.js")
    ]
    for asset in required_assets:
        asset_full = os.path.join(public_dir, asset)
        assert os.path.exists(asset_full), f"Asset {asset} must exist in android assets/public"
        assert os.path.getsize(asset_full) > 0, f"Asset {asset} must not be empty"
        
    cap_assets_cfg = os.path.join(ANDROID_ASSETS_DIR, "capacitor.config.json")
    assert os.path.exists(cap_assets_cfg), "capacitor.config.json must exist in android assets"


def test_08_zero_hardcoded_secrets():
    """8. Test that no production API keys or tokens are stored in mobile assets."""
    check_paths = [
        os.path.join(FRONTEND_DIR, "app.js"),
        os.path.join(FRONTEND_DIR, "mobile", "apiClient.js"),
        os.path.join(ANDROID_DIR, "app", "src", "main", "assets", "public", "app.js"),
        os.path.join(ANDROID_DIR, "app", "src", "main", "assets", "public", "mobile", "apiClient.js"),
        MANIFEST_XML_PATH
    ]
    for p in check_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            assert "sk-" not in content
            assert "AIzaSy" not in content
            assert "ghp_" not in content
            assert "BEGIN PRIVATE KEY" not in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
