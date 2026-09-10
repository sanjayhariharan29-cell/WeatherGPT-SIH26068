# WeatherGPT — SIH Mobile Release & Deployment Checklist

**Project**: WeatherGPT — MoES / IMD Meteorological Assistant (SIH26068)  
**Role**: Person 3 — Frontend / Mobile / QA  
**Release Target**: Smart India Hackathon (SIH 2026) Grand Finale Demonstration  
**Version**: v1.0.0 (Capacitor 6 Android Shell / PWA)  
**Status**: Ready for SIH Demonstration  

---

## 1. APK & Packaging Readiness

- [x] **Frontend Web Assets**: Production assets validated in `frontend/` (zero compile lag, vanilla HTML5/CSS3/ES6).
- [x] **Capacitor Assets Synchronized**: 100% mirrored to `android/app/src/main/assets/public/` via `npx cap sync android`.
- [x] **Package Identifier**: `in.gov.moes.weathergpt` declared in `capacitor.config.json` and `AndroidManifest.xml`.
- [x] **Application Branding**: `SkyZen` configured across Capacitor config and `strings.xml`.
- [x] **SDK Targets**: Target SDK 34 (Android 14) / Min SDK 22 (Android 5.1 Lollipop).
- [x] **Zero Secrets / Artifact Safety**: Zero embedded API keys, tokens, or `.env` files present in mobile assets.
- [x] **Native APK Binary Compilation**: `./gradlew assembleRelease` and `./gradlew assembleDebug` passed cleanly with Gradle 8.2.1 / JDK 17 (`app-release-unsigned.apk` generated).

---

## 2. Demo Device Readiness

- [ ] **Battery Level**: Demo smartphone / tablet charged above 80%.
- [ ] **Screen Timeout**: Set display timeout to 10 minutes or "Never" during presentation.
- [ ] **Brightness**: Fixed at 70%–80% for clear readability under auditorium lighting.
- [ ] **Display Orientation**: Portrait mode locked.
- [ ] **Browser / WebView**: Chrome 110+ or Android System WebView 110+ updated.

---

## 3. Network & Connectivity Readiness

- [x] **Cleartext Traffic Enabled**: `android:usesCleartextTraffic="true"` configured for local test servers (`http://10.0.2.2:8000` / `http://localhost:8000`).
- [x] **Dynamic API Environment Switcher**: Settings screen dropdown allows instant switching between:
  1. Production Web Shell (`/api/v1`)
  2. Local Dev Server (`http://localhost:8000/api/v1`)
  3. Android Emulator Host (`http://10.0.2.2:8000/api/v1`)
- [ ] **Hotspot / Wi-Fi**: Dedicated mobile hotspot pre-paired with demo phone and laptop.

---

## 4. Mobile Permissions

- [x] **Internet & Network State**: `INTERNET`, `ACCESS_NETWORK_STATE` in `AndroidManifest.xml`.
- [x] **Location (GPS)**: `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` with graceful in-memory fallback.
- [x] **Audio (Microphone)**: `RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS` with non-blocking toast notices on denial.
- [x] **Zero Phantom Submissions**: Speech recognition errors gracefully focus the text box rather than submitting fake queries.

---

## 5. Core Feature Matrix

| Feature | Readiness | Demonstration Note |
| :--- | :--- | :--- |
| **Current Telemetry** | READY | Displays temperature, humidity, wind speed, rain probability, and model agreement. |
| **Forecast Grids** | READY | Categorized timelines for Today, Tomorrow, and Extended Future. |
| **Official Alerts** | READY | Priority banner anchored at the top with IMD attribution. |
| **Conversational Chat** | READY | Multi-turn chat with send locks and auto-scrolling message bubbles. |
| **Geospatial Map** | READY | Interactive Leaflet layer with coordinate fallback if map tiles are offline. |
| **User Profile / Auth** | READY | Guest mode active by default; optional login for saving custom hubs. |

---

## 6. Multilingual Support (SIH High Impact)

- [x] **English**: Default presentation typography.
- [x] **Tamil (`ta-IN`)**: Font fallback `Noto Sans Tamil`; line-height 1.6 prevents ligature truncation.
- [x] **Hindi (`hi-IN`)**: Font fallback `Noto Sans Devanagari` and `Nirmala UI` for clear vowel matras.
- [x] **Tanglish**: Suggestion chip query `"Naalaiku morning college pogalama?"` ready for live demo.
- [x] **Hinglish**: Conversational Hindi-English queries handled with `overflow-wrap: break-word`.

---

## 7. Warning & Safety Integrity Guarantee

- [x] **Top Priority Presentation**: Disaster alerts are placed above all weather cards.
- [x] **Zero Suppression**: Warnings cannot be dismissed, hidden, or downgraded by user actions.
- [x] **Authoritative Provenance**: Every warning explicitly states `Source: India Meteorological Department (IMD)`.
- [x] **Stale Telemetry Prevention**: Cached data is labeled `"Cached Telemetry (Offline)"` with timestamps.

---

## 8. Offline & Degraded Network Behavior

- [x] **Offline Detection**: Network drop immediately triggers red `#offlineBar`.
- [x] **Cache Fallback**: Automatically restores previously cached weather records from `localStorage`.
- [x] **Warning Safety**: Displays `"⚠️ UNVERIFIED WARNING STATE"` directing users to radio/TV emergency broadcasts.

---

## 9. Recommended 10-Step SIH Demo Sequence

1. **Launch App**: Open WeatherGPT; point out clean dark glassmorphic UI and lack of hardcoded mock numbers.
2. **Select Location**: Switch to `Nagapattinam` to display the active coastal weather telemetry.
3. **Show Official Warning**: Highlight the red pulsing `#alertBanner` citing the India Meteorological Department.
4. **Persona Switch**: Change persona from `Student` to `Fisherman` or `Farmer` to show tailored context.
5. **Ask Conversational AI**: Send query: *"What precautions should coastal fishermen take today?"*
6. **Show Multi-Day Forecast**: Open `Weather` tab; review Today, Tomorrow, and 5-Day Outlook.
7. **Demonstrate Multilingual NLU**: Switch language to Tamil or click Tanglish chip: *"Naalaiku morning college pogalama?"*.
8. **Interactive Map**: Open `Map` tab to inspect Tamil Nadu coastal monitoring stations.
9. **Simulate Network Failure**: Toggle airplane mode or disconnect Wi-Fi; show immediate `#offlineBar` and cached labeling.
10. **Recover Network**: Reconnect; show seamless return to live telemetry.

---

## 10. Emergency Fallback Plan

| Failure Scenario | Fallback Procedure |
| :--- | :--- |
| **Backend Offline / 503** | Use the cached telemetry demo mode; demonstrate UI resilience and `#dashboardErrorCard`. |
| **Microphone Hardware Fails** | Click the suggested query chips or type directly in `#chatInput`. |
| **Map Tiles Fail to Load** | Leaflet container automatically displays `#mapFallback` coordinate telemetry. |
| **Projector / Screen Contrast Issue** | High-contrast CSS tokens ensure cyan, amber, and red indicators remain legible. |
