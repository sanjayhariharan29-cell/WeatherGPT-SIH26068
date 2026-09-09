# WeatherGPT — SIH Mobile Demonstration Quick Guide

**Project**: WeatherGPT — MoES / IMD Meteorological Assistant (SIH26068)  
**Role**: Person 3 — Frontend / Mobile / QA  
**Audience**: SIH Grand Finale Evaluators, Jury, and Demonstrators  

---

## 1. How to Launch

### Option A: Physical Android Device / Emulator
1. Launch the installed **WeatherGPT** app from the home screen / app drawer.
2. Ensure device has active network connectivity (Wi-Fi / Mobile Data).

### Option B: Local Web / Mobile Simulation Shell
1. Serve the frontend directory:
   ```bash
   python -m http.server 8085 --directory frontend
   ```
2. Open Chrome/Edge at `http://localhost:8085`.
3. Press `F12`, toggle **Device Toolbar** (`Ctrl+Shift+M`), and select **Pixel 7** or **iPhone 14** (390x844).

---

## 2. Recommended Demo Locations

- **Primary Hub (Coastal Warning Showcase)**: `📍 Nagapattinam (Hero Alert)`  
  *Why*: Demonstrates coastal squall and rainfall warnings directly from the IMD alert engine.
- **Secondary Hub (Urban Rainfall Showcase)**: `📍 Coimbatore` or `📍 Chennai`  
  *Why*: Highlights high-density multi-model consensus and hourly timeline telemetry.

---

## 3. Recommended Conversational Demo Questions

| Language / Dialect | Suggested Query | Demonstrated AI Capability |
| :--- | :--- | :--- |
| **English** | *"What is the expected rainfall in Nagapattinam tomorrow morning?"* | Numerical reasoning & weather metrics. |
| **Tamil** | *"நாளை நாகப்பட்டினத்தில் பலத்த மழை பெய்யுமா? மீனவர்கள் கடலுக்கு செல்லலாமா?"* | Tamil regional language NLU & safety advisories. |
| **Tanglish** | *"Naalaiku morning college pogalama?"* | Colloquial youth queries & actionable recommendations. |
| **Hindi** | *"क्या कल चेन्नई में भारी बारिश की चेतावनी जारी की गई है?"* | Devanagari script processing & alert verification. |
| **Hinglish** | *"Kal weather kaisa rahega, kya travel karna safe hai?"* | Multi-dialect conversational safety advisory. |

---

## 4. Official Warning Demonstration Procedure

1. Select `Nagapattinam` from the top location dropdown.
2. Direct the jury's attention to the `#alertBanner`:
   - Note the **high-contrast pulsing red border**.
   - Point out the **authoritative provenance**: `Source: India Meteorological Department (IMD)`.
   - Emphasize that the system **never suppresses or downgrades** official disaster warnings.

---

## 5. Persona Switching Demonstration

1. In the header, click the **Persona Dropdown**:
   - Select `🎣 Fisherman`: Notice the advisory shifts to sea state, wave height, and deep-sea venture advisories.
   - Select `🌾 Farmer`: Notice the advisory focuses on soil moisture, pesticide spraying windows, and thunderstorm safety.
   - Select `🎓 Student`: Notice the advisory provides clear, practical commuting and school timing guidance.

---

## 6. Offline & Resilience Demonstration

1. Disconnect Wi-Fi / enable Airplane mode on the demonstration device.
2. Notice the instant appearance of the top `#offlineBar` (`⚠️ Network Offline. Displaying cached weather telemetry.`).
3. Point out that cached cards are tagged as `"Cached Telemetry (Offline)"` with explicit timestamps to prevent confusion with live data.
4. Reconnect network; observe instant automatic re-synchronization.

---

## 7. Emergency Fallbacks for Presenters

- **If Voice Input Fails**: Tap the pre-built prompt chips below the chat box (e.g. `"Naalaiku morning college pogalama?"`) or type directly.
- **If Backend is Latent / Slow**: The client features a 10-second timeout with an automatic retry button; cached observations are safely loaded.
- **If Map Tiles Fail to Load**: The map container gracefully falls back to the coordinate telemetry view without blanking out the screen.
