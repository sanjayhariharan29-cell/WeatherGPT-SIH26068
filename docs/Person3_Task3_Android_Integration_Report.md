# Person 3: Android / Capacitor Integration & Mobile Shell Readiness Report

**Project**: WeatherGPT — MoES / IMD Meteorological Assistant (SIH26068)  
**Role**: Person 3 — Frontend / Mobile / QA  
**Task**: TASK 3 ONLY — Android / Capacitor Integration & Mobile Shell Readiness  
**Date**: September 9, 2026  
**Status**: Completed & Verified  

---

## 1. Executive Summary

As Person 3, the objective for Task 3 was to prepare and verify the existing WeatherGPT frontend and Capacitor mobile configuration for native Android integration, ensuring rock-solid WebView compatibility, proper mobile permissions UX, responsive shell readiness, and asset synchronization without modifying backend contracts, AI pipelines, database schemas, or CI/CD pipelines.

---

## 2. Android Architecture & Environment Found

| Component | Status | Details |
| :--- | :--- | :--- |
| **Mobile Architecture** | **Capacitor Hybrid Container** | Vanilla HTML5 / CSS3 / ES6 single-page app wrapped inside a native Android `BridgeActivity`. |
| **Android Project Root** | **`android/`** | Standard Capacitor Android project with Gradle wrapper (`gradlew`, `gradlew.bat`). |
| **Application ID / Package** | **`in.gov.moes.weathergpt`** | Consistent across `capacitor.config.json`, `android/app/build.gradle`, `AndroidManifest.xml`, and `strings.xml`. |
| **Android SDK Configuration** | **`compileSdk: 34`, `targetSdk: 34`, `minSdk: 22`** | Defined in `android/variables.gradle`. Supports Android 5.1 (Lollipop) up to Android 14. |
| **Entry Activity** | **`MainActivity.java`** | Extends `com.getcapacitor.BridgeActivity`. Package: `in.gov.moes.weathergpt`. |
| **Asset Directory** | **`android/app/src/main/assets/public/`** | Configured as the destination for web asset bundling. |

---

## 3. Capacitor Configuration Audit

Inspected both `capacitor.config.json` (root) and `mobile/capacitor.config.json`:

- **App ID**: `in.gov.moes.weathergpt` (verified)
- **App Name**: `WeatherGPT` (verified)
- **Web Directory**: `frontend` (root) / `../frontend` (mobile)
- **Server Scheme**: `androidScheme: "https"`, `cleartext: true` (verified)
- **Configured Plugins**:
  - `SplashScreen`: `launchShowDuration: 2000`, `backgroundColor: "#0f172a"` (dark slate blue)
  - `StatusBar`: `style: "DARK"`, `backgroundColor: "#0f172a"`
- **Dependencies (`package.json`)**:
  - `@capacitor/core`: `^6.0.0`
  - `@capacitor/android`: `^6.0.0`
  - `@capacitor/cli`: `^6.0.0`

---

## 4. Issues Discovered & Fixes Made

During the Android and WebView audit, 5 critical integration issues were identified and resolved:

### Issue 1: Missing Android Permissions in `AndroidManifest.xml` (CRITICAL)
- **Defect**: `android/app/src/main/AndroidManifest.xml` only declared `<uses-permission android:name="android.permission.INTERNET" />`. Crucial permissions for device geolocation (`ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`), voice input (`RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS`), and connectivity monitoring (`ACCESS_NETWORK_STATE`) were completely absent.
- **Impact**: On real Android devices, WebViews would unconditionally deny GPS location queries and microphone voice inputs.
- **Fix**: Declared all necessary permissions in `AndroidManifest.xml` with optional GPS hardware requirement (`<uses-feature android:name="android.hardware.location.gps" android:required="false" />`) to maintain broad tablet compatibility.

### Issue 2: Missing Cleartext Traffic Permission for Local Testing (HIGH)
- **Defect**: Android 9+ (API 28+) disables unencrypted HTTP connections by default. When developers/testers run local dev servers or point to localhost/LAN backend instances, all requests fail with `ERR_CLEARTEXT_NOT_PERMITTED`.
- **Impact**: Local development and emulator testing against `http://10.0.2.2:8000` or `http://localhost:8000` completely blocked.
- **Fix**: Added `android:usesCleartextTraffic="true"` to `<application>` in `AndroidManifest.xml`.

### Issue 3: Hardcoded Absolute Web Asset Paths in `index.html` (HIGH)
- **Defect**: `frontend/index.html` used root-absolute paths (`/styles.css`, `/manifest.json`, `/app.js`, `/mobile/apiClient.js`, `/sw.js`).
- **Impact**: In file-backed WebViews or non-root local servers, root-absolute paths resolve to filesystem roots (`file:///styles.css`), breaking CSS and JS loading.
- **Fix**: Converted all asset links and script inclusions to relative paths (`./styles.css`, `./manifest.json`, `./app.js`, `./mobile/apiClient.js`, `./sw.js`).

### Issue 4: Inflexible API Base URL & Missing Android Emulator Host Option (HIGH)
- **Defect**: `WeatherGPTApiClient` initialized `this.baseUrl` to `"/api/v1"`. In native Android WebViews (`https://localhost/`), relative `/api/v1` routes to `https://localhost/api/v1` which has no running backend on the phone. Furthermore, `#envSelect` in Settings lacked dynamic binding.
- **Impact**: App could not connect to local host machines (`10.0.2.2:8000`) or custom test servers from an Android emulator or device.
- **Fix**: 
  1. Added `getBaseUrl()` and `setBaseUrl(url)` with `localStorage` persistence (`weathergpt_api_base`) in `frontend/mobile/apiClient.js`.
  2. Added the Android Emulator Host option (`http://10.0.2.2:8000/api/v1`) to `#envSelect` in `frontend/index.html`.
  3. Bound `#envSelect` change events in `frontend/app.js` to dynamically update `window.apiClient` and persist across reloads.

### Issue 5: Improper Permission Denial Handling & Fake Voice Query Fallback (MEDIUM)
- **Defect**: In `frontend/app.js`, when voice recognition failed or was denied, `handleVoiceClick()` silently submitted a fake student question (`"Naalaiku morning college pogalama?"`). Additionally, location errors used blocking `alert()`.
- **Impact**: Confusing user experience; permission denials triggered unwanted AI chat queries.
- **Fix**:
  1. Created `#mobileNotice` non-blocking toast banner with ARIA live region support.
  2. Replaced `alert()` in `handleDeviceGeolocation()` with informative, dismissible mobile notices explaining why permission is needed and providing graceful fallbacks to the location dropdown.
  3. Eliminated the automatic hardcoded question submission in `handleVoiceClick()`. Now displays a helpful notice ("Microphone permission denied" or "Voice recognition not supported") and automatically focuses the chat input field.

---

## 5. Asset Synchronization Pipeline

Because Capacitor requires web assets inside `android/app/src/main/assets/public/` for native packaging:

- Created `mobile/sync_assets.py` to synchronize `frontend/` into `android/app/src/main/assets/public/` and deploy `capacitor.config.json` to `android/app/src/main/assets/`.
- Executed `python mobile/sync_assets.py`, successfully synchronizing all HTML, CSS, JS, manifest, and configuration files into the native Android shell directory.

---

## 6. Verification & Test Results

Executed automated test suite `tests/test_android_integration.py` (8/8 tests passing):

```
============================= test session starts =============================
platform win32 -- Python 3.15.0b3, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\visha\Documents\GitHub\WeatherGPT-SIH26068

tests/test_android_integration.py::test_01_android_manifest_permissions_and_config PASSED [ 12%]
tests/test_android_integration.py::test_02_capacitor_configurations PASSED [ 25%]
tests/test_android_integration.py::test_03_android_gradle_sdk_versions PASSED [ 37%]
tests/test_android_integration.py::test_04_frontend_webview_compatibility PASSED [ 50%]
tests/test_android_integration.py::test_05_dynamic_api_client_configuration PASSED [ 62%]
tests/test_android_integration.py::test_06_permission_graceful_ux PASSED [ 75%]
tests/test_android_integration.py::test_07_android_assets_synchronization PASSED [ 87%]
tests/test_android_integration.py::test_08_zero_hardcoded_secrets PASSED [100%]

============================== 8 passed in 0.22s ==============================
```

JSON Configuration Schema Validations:
- `capacitor.config.json`: **PASS** (Valid JSON, appId: `in.gov.moes.weathergpt`)
- `mobile/capacitor.config.json`: **PASS** (Valid JSON, appId: `in.gov.moes.weathergpt`)
- `frontend/manifest.json`: **PASS** (Valid JSON, standalone display, shortcuts configured)

---

## 7. Operational Classification & Readiness Matrix

| Feature / Artifact | Status | Responsible Party | Notes |
| :--- | :--- | :--- | :--- |
| **Android Project Shell** | **VERIFIED** | Person 3 | Manifest permissions, cleartext, SDK targets complete. |
| **Web Asset Sync** | **VERIFIED** | Person 3 | `mobile/sync_assets.py` syncs web distribution to Android assets. |
| **Permission UX & Fallbacks** | **VERIFIED** | Person 3 | Geolocation & microphone denial handled gracefully. |
| **WebView Asset Linking** | **VERIFIED** | Person 3 | Relative paths & keyboard viewport adjustments in place. |
| **Local Node / NPM** | **NOT AVAILABLE** | Host Environment | Node/npm not installed in this Windows host; automated via Python. |
| **Local Android SDK / Java** | **NOT AVAILABLE** | Host Environment | Java/Gradle binaries not present on host; compilation deferred to Person 4 / CI. |
| **Native APK Compilation** | **PERSON 4 SETUP** | Person 4 | Requires Android Studio / JDK 17+ on builder workstation. |
| **Production Key Signing** | **RELEASE WORK** | Person 4 / Release | Keystore generation and release signing reserved for final release phase. |

---

## 8. Summary of Files Changed

- `android/app/src/main/AndroidManifest.xml`: Declared mobile permissions (`INTERNET`, `ACCESS_NETWORK_STATE`, `ACCESS_COARSE_LOCATION`, `ACCESS_FINE_LOCATION`, `RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS`, GPS feature) and `usesCleartextTraffic="true"`.
- `frontend/index.html`: Converted asset paths to relative, added `interactive-widget=resizes-content`, added `#mobileNotice` banner, and added Android Emulator option to `#envSelect`.
- `frontend/styles.css`: Added styles for `.mobile-notice` toast notifications.
- `frontend/mobile/apiClient.js`: Added `getBaseUrl()`, `setBaseUrl()` with `localStorage` persistence.
- `frontend/app.js`: Wired up `#envSelect`, added `showMobileNotice`, improved GPS/voice permission UX, removed fake question auto-send, and resolved empty hash navigation.
- `mobile/sync_assets.py`: Automated asset synchronizer script for Capacitor Android.
- `tests/test_android_integration.py`: Integration test suite for Android readiness.
- `docs/Person3_Task3_Android_Integration_Report.md`: Full task report.

*(Zero changes made to `ai/`, `backend/`, `requirements.txt`, or database/auth files.)*
