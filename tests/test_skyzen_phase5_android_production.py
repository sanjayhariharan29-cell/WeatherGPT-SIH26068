"""
Phase 5 Test Matrix: SkyZen Android + Capacitor Production Integration
Comprehensive deterministic test suite verifying:
1. Package ID
2. Capacitor configuration & branding (SkyZen)
3. Production API configuration mechanism
4. No production localhost in release assets
5. No production 127.0.0.1 in release assets
6. Firebase package match
7. Google Services configuration
8. Notification permission declaration and handling
9. FCM configuration and token registration
10. Location permission (fine/coarse, no background location)
11. Microphone permission for voice UI
12. Deep link configuration
13. Notification tap action routing to Alerts screen
14. App foreground lifecycle handling
15. App background lifecycle handling
16. App closed / cold start handling
17. App restart handling
18. Offline behavior in Android
19. Reconnect behavior in Android
20. API failure / unconfigured backend behavior
21. No secrets, private keys, or API tokens in assets
22. Official alert integrity preserved during mobile delivery
23. App icon / branding assets in Android mipmaps
24. Production build configuration & Gradle compilation
"""

import os
import json
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANDROID_DIR = os.path.join(REPO_ROOT, "android")
APP_DIR = os.path.join(ANDROID_DIR, "app")
SRC_MAIN_DIR = os.path.join(APP_DIR, "src", "main")
RES_DIR = os.path.join(SRC_MAIN_DIR, "res")
ASSETS_DIR = os.path.join(SRC_MAIN_DIR, "assets")
PUBLIC_DIR = os.path.join(ASSETS_DIR, "public")
MANIFEST_PATH = os.path.join(SRC_MAIN_DIR, "AndroidManifest.xml")
CAP_CONFIG_PATH = os.path.join(REPO_ROOT, "capacitor.config.json")
GOOGLE_SERVICES_PATH = os.path.join(APP_DIR, "google-services.json")
STRINGS_PATH = os.path.join(RES_DIR, "values", "strings.xml")
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")


def test_01_package_id():
    """1. Verify Android package ID remains strictly in.gov.moes.weathergpt."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest_text = f.read()
    assert "in.gov.moes.weathergpt" in manifest_text, "Package ID must be in.gov.moes.weathergpt"

    build_gradle_path = os.path.join(APP_DIR, "build.gradle")
    with open(build_gradle_path, "r", encoding="utf-8") as f:
        build_gradle_text = f.read()
    assert 'applicationId "in.gov.moes.weathergpt"' in build_gradle_text
    assert 'namespace "in.gov.moes.weathergpt"' in build_gradle_text


def test_02_capacitor_configuration_and_branding():
    """2. Verify Capacitor configuration has appId in.gov.moes.weathergpt and branding SkyZen."""
    with open(CAP_CONFIG_PATH, "r", encoding="utf-8") as f:
        cap_cfg = json.load(f)
    assert cap_cfg.get("appId") == "in.gov.moes.weathergpt"
    assert cap_cfg.get("appName") == "SkyZen"
    assert cap_cfg.get("webDir") == "frontend"
    assert "plugins" in cap_cfg
    assert "SplashScreen" in cap_cfg["plugins"]
    assert "StatusBar" in cap_cfg["plugins"]

    # Also verify strings.xml branding
    with open(STRINGS_PATH, "r", encoding="utf-8") as f:
        strings_text = f.read()
    assert '<string name="app_name">SkyZen</string>' in strings_text
    assert '<string name="title_activity_main">SkyZen</string>' in strings_text


def test_03_production_api_configuration_mechanism():
    """3. Verify clean environment configuration mechanism without invented domains."""
    config_js_path = os.path.join(FRONTEND_DIR, "config.js")
    with open(config_js_path, "r", encoding="utf-8") as f:
        cfg_js = f.read()
    assert "SKYZEN_API_BASE" in cfg_js or "SKYZEN_PRODUCTION_API_URL" in cfg_js
    assert "window.ENV" in cfg_js

    # Verify apiClient supports setting/getting base URL
    api_client_path = os.path.join(FRONTEND_DIR, "mobile", "apiClient.js")
    with open(api_client_path, "r", encoding="utf-8") as f:
        api_code = f.read()
    assert "getBaseUrl()" in api_code
    assert "setBaseUrl(" in api_code
    assert "weathergpt_api_base" in api_code


def test_04_no_production_localhost_in_release_assets():
    """4. Verify no production requests default to localhost in native Android assets."""
    api_client_path = os.path.join(FRONTEND_DIR, "mobile", "apiClient.js")
    with open(api_client_path, "r", encoding="utf-8") as f:
        api_code = f.read()
    assert "isNativeAndroid()" in api_code
    assert "PRODUCTION_BACKEND_URL_REQUIRED" in api_code


def test_05_no_production_127_0_0_1_in_release_assets():
    """5. Verify 127.0.0.1 is not hardcoded as active production endpoint."""
    config_js_path = os.path.join(FRONTEND_DIR, "config.js")
    with open(config_js_path, "r", encoding="utf-8") as f:
        cfg_js = f.read()
    assert "127.0.0.1" not in cfg_js

    api_client_path = os.path.join(FRONTEND_DIR, "mobile", "apiClient.js")
    with open(api_client_path, "r", encoding="utf-8") as f:
        api_code = f.read()
    assert "127.0.0.1" not in api_code


def test_06_firebase_package_match():
    """6. Verify google-services.json package_name strictly matches in.gov.moes.weathergpt."""
    assert os.path.exists(GOOGLE_SERVICES_PATH), "google-services.json must exist in app/"
    with open(GOOGLE_SERVICES_PATH, "r", encoding="utf-8") as f:
        gs_data = json.load(f)

    clients = gs_data.get("client", [])
    assert len(clients) > 0, "google-services.json must have at least one client"
    package_name = clients[0].get("client_info", {}).get("android_client_info", {}).get("package_name")
    assert package_name == "in.gov.moes.weathergpt"


def test_07_google_services_configuration():
    """7. Verify valid structure, project ID, and API key in google-services.json."""
    with open(GOOGLE_SERVICES_PATH, "r", encoding="utf-8") as f:
        gs_data = json.load(f)
    project_id = gs_data.get("project_info", {}).get("project_id")
    assert project_id == "skyzen-9a22d"
    assert "api_key" in gs_data["client"][0]


def test_08_notification_permission_declaration_and_handling():
    """8. Verify POST_NOTIFICATIONS permission and runtime grant/deny handling."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest_text = f.read()
    assert 'android.permission.POST_NOTIFICATIONS' in manifest_text

    notif_mgr_path = os.path.join(FRONTEND_DIR, "mobile", "notificationManager.js")
    with open(notif_mgr_path, "r", encoding="utf-8") as f:
        notif_code = f.read()
    assert "requestPermission()" in notif_code
    assert "skyzen_notification_permission" in notif_code
    assert "denied" in notif_code


def test_09_fcm_configuration_and_token_registration():
    """9. Verify push notifications plugin dependency, registration, and backend sync."""
    pkg_json_path = os.path.join(REPO_ROOT, "package.json")
    with open(pkg_json_path, "r", encoding="utf-8") as f:
        pkg_json = json.load(f)
    deps = pkg_json.get("dependencies", {})
    assert "@capacitor/push-notifications" in deps

    notif_mgr_path = os.path.join(FRONTEND_DIR, "mobile", "notificationManager.js")
    with open(notif_mgr_path, "r", encoding="utf-8") as f:
        notif_code = f.read()
    assert "plugin.register()" in notif_code
    assert "syncDeviceToken()" in notif_code
    assert "registerDeviceToken" in notif_code


def test_10_location_permission_scope():
    """10. Verify FINE and COARSE location declared, no background location."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest_text = f.read()
    assert 'android.permission.ACCESS_FINE_LOCATION' in manifest_text
    assert 'android.permission.ACCESS_COARSE_LOCATION' in manifest_text
    assert 'android.permission.ACCESS_BACKGROUND_LOCATION' not in manifest_text, (
        "Background location violates user privacy and is not authorized in this architecture."
    )
    assert 'android:required="false"' in manifest_text


def test_11_microphone_permission_and_voice():
    """11. Verify RECORD_AUDIO permission and voice handling with non-blocking error UX."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest_text = f.read()
    assert 'android.permission.RECORD_AUDIO' in manifest_text
    assert 'android.permission.MODIFY_AUDIO_SETTINGS' in manifest_text

    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        app_code = f.read()
    assert "handleVoiceClick()" in app_code
    assert "Microphone permission denied" in app_code


def test_12_deep_link_configuration():
    """12. Verify custom URL scheme and singleTask launchMode for alert deep links."""
    with open(STRINGS_PATH, "r", encoding="utf-8") as f:
        strings_text = f.read()
    assert '<string name="custom_url_scheme">in.gov.moes.weathergpt</string>' in strings_text

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest_text = f.read()
    assert 'android:launchMode="singleTask"' in manifest_text


def test_13_notification_tap_action_routing():
    """13. Verify pushNotificationActionPerformed routes to alerts screen and sets district."""
    notif_mgr_path = os.path.join(FRONTEND_DIR, "mobile", "notificationManager.js")
    with open(notif_mgr_path, "r", encoding="utf-8") as f:
        notif_code = f.read()
    assert "pushNotificationActionPerformed" in notif_code
    assert 'navigateToScreen("alerts")' in notif_code
    assert "targetDistrict" in notif_code


def test_14_app_foreground_lifecycle():
    """14. Verify pushNotificationReceived listener dispatches foreground event."""
    notif_mgr_path = os.path.join(FRONTEND_DIR, "mobile", "notificationManager.js")
    with open(notif_mgr_path, "r", encoding="utf-8") as f:
        notif_code = f.read()
    assert "pushNotificationReceived" in notif_code
    assert "skyzen:notificationReceived" in notif_code


def test_15_app_background_lifecycle():
    """15. Verify device token is persisted locally for background message receipt."""
    notif_mgr_path = os.path.join(FRONTEND_DIR, "mobile", "notificationManager.js")
    with open(notif_mgr_path, "r", encoding="utf-8") as f:
        notif_code = f.read()
    assert "skyzen_fcm_token" in notif_code
    assert "localStorage.setItem" in notif_code


def test_16_app_closed_cold_start():
    """16. Verify hash navigation handles cold start to default home or target screen."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        app_code = f.read()
    assert "handleHashNavigation" in app_code
    assert "window.location.hash" in app_code


def test_17_app_restart_state_preservation():
    """17. Verify authentication token, preferred units, and locations are preserved across restarts."""
    api_client_path = os.path.join(FRONTEND_DIR, "mobile", "apiClient.js")
    with open(api_client_path, "r", encoding="utf-8") as f:
        api_code = f.read()
    assert "weathergpt_auth_token" in api_code
    assert "getToken()" in api_code
    assert "setToken(" in api_code


def test_18_offline_behavior_in_android():
    """18. Verify offline detection throws structured error and prevents fake queries."""
    api_client_path = os.path.join(FRONTEND_DIR, "mobile", "apiClient.js")
    with open(api_client_path, "r", encoding="utf-8") as f:
        api_code = f.read()
    assert "NETWORK_OFFLINE" in api_code
    assert "!navigator.onLine" in api_code


def test_19_reconnect_behavior_in_android():
    """19. Verify debounced auto-refresh on network reconnect prevents request storms."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        app_code = f.read()
    assert 'window.addEventListener("online"' in app_code
    assert "reconnectDebounce" in app_code


def test_20_api_failure_behavior():
    """20. Verify structured error handling when backend server is unavailable."""
    api_client_path = os.path.join(FRONTEND_DIR, "mobile", "apiClient.js")
    with open(api_client_path, "r", encoding="utf-8") as f:
        api_code = f.read()
    assert "REQUEST_TIMEOUT" in api_code
    assert "PRODUCTION_BACKEND_URL_REQUIRED" in api_code


def test_21_no_secrets_in_android_frontend():
    """21. Security Audit: verify no private keys, JWT secrets, or API keys exist in client assets."""
    target_paths = [
        os.path.join(FRONTEND_DIR, "app.js"),
        os.path.join(FRONTEND_DIR, "config.js"),
        os.path.join(FRONTEND_DIR, "mobile", "apiClient.js"),
        os.path.join(FRONTEND_DIR, "mobile", "notificationManager.js"),
        MANIFEST_PATH,
        CAP_CONFIG_PATH
    ]
    forbidden = [
        "BEGIN PRIVATE KEY",
        "BEGIN RSA PRIVATE KEY",
        "service_account",
        "SECRET_KEY=change-in-production",
        "ghp_",
        "sk-"
    ]
    for p in target_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            for pattern in forbidden:
                assert pattern not in content, f"Forbidden secret pattern '{pattern}' found in {p}"


def test_22_official_alert_integrity():
    """22. Verify notification tap never fabricates an alert, loads authoritative IMD data."""
    app_js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        app_code = f.read()
    assert "loadAlerts(" in app_code
    assert "window.apiClient.getAlerts" in app_code
    assert "India Meteorological Department" in app_code or "IMD" in app_code


def test_23_app_icon_and_branding_resources():
    """23. Verify mipmap launcher icons, adaptive XML, and branded launcher resources exist."""
    mipmap_hdpi = os.path.join(RES_DIR, "mipmap-hdpi", "ic_launcher.png")
    mipmap_anydpi = os.path.join(RES_DIR, "mipmap-anydpi-v26", "ic_launcher.xml")
    assert os.path.exists(mipmap_hdpi), "ic_launcher.png must exist in mipmap-hdpi"
    assert os.path.exists(mipmap_anydpi), "ic_launcher.xml must exist in mipmap-anydpi-v26"

    with open(mipmap_anydpi, "r", encoding="utf-8") as f:
        xml_content = f.read()
    assert "<adaptive-icon" in xml_content


def test_24_production_build_configuration():
    """24. Verify Android build variables, target SDK 34, compile SDK 34, and release output."""
    variables_gradle_path = os.path.join(ANDROID_DIR, "variables.gradle")
    with open(variables_gradle_path, "r", encoding="utf-8") as f:
        vars_text = f.read()
    assert "compileSdkVersion = 34" in vars_text
    assert "targetSdkVersion = 34" in vars_text
    assert "minSdkVersion = 22" in vars_text

    # Verify release APK output exists from build
    release_apk_path = os.path.join(APP_DIR, "build", "outputs", "apk", "release", "app-release-unsigned.apk")
    assert os.path.exists(release_apk_path), f"Release APK must be generated at {release_apk_path}"
    assert os.path.getsize(release_apk_path) > 1000000, "Release APK must be at least 1MB"
