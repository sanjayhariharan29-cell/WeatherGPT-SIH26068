# PHASE 18 — OFFLINE / DEGRADED MODE & RESILIENCE

## Core Objective
Ensure WeatherGPT degrades gracefully across network disconnections, external weather provider outages, forecast service disruptions, official warning feed failures, backend service timeouts, LLM provider failures, and temporary database lock events without fabricating weather data or falsely claiming live safety status.

---

## 1. System Degradation States

The application enforces 4 explicit operational states:

| Operational State | Connectivity | Telemetry Origin | Warning Verification | UI Display & Indicators |
| :--- | :--- | :--- | :--- | :--- |
| **`ONLINE`** | Active Internet | Authoritative IMD / Open-Meteo Live | Verified IMD Feed | `Fresh Telemetry` badge, live temperature & metrics |
| **`DEGRADED`** | Active Internet | Secondary Provider / DB Cached Fallback | Unverified / Degraded | `Partial Telemetry`, secondary source attribution |
| **`OFFLINE`** | Disconnected | Local Storage Cache | Unverified (Offline) | `Cached Telemetry (Offline)`, cached timestamp, `offlineBar` active |
| **`DATA_UNAVAILABLE`** | Any | None Available | Unverified | `Data Unavailable` card, `--` placeholders, no fake zeros |

> [!CRITICAL]
> **Warning Safety Rule**: The system strictly enforces that `OFFLINE != SAFE WEATHER`. When offline or when the warning feed cannot be verified, the application **never** displays *"No active disaster warnings"*. Instead, it renders an unverified safety banner (`⚠️ UNVERIFIED WARNING STATE`) instructing users to consult official emergency radio channels.

---

## 2. Weather & Forecast Caching Strategy

### Current Weather Cache
- Successful live weather observations are serialized into `localStorage` under `weathergpt_cache_current_<location>`.
- When offline or when provider requests fail, the application loads the cached observation and renders:
  - `cached: true`
  - Prominent badge: `Cached Telemetry (Offline)`
  - Timestamp: `Cached at HH:MM UTC (Observed: HH:MM UTC)`
  - Source tag: `IMD (Cached)`

### Forecast Cache
- Forecast items are stored in `localStorage` under `weathergpt_cache_forecast_<location>` alongside a `cachedAt` timestamp.
- In offline/degraded mode, cached forecasts render with an explicit footer indicator: `Last updated: HH:MM UTC (Cached)`.

---

## 3. Warning Safety & Unverified State Handling

1. **`AlertService` Integration**:
   - When primary IMD warning adapter encounters `ProviderError` or network timeout, `AlertResponse` returns `status="UNVERIFIED"`.
2. **Frontend Warning Banner**:
   - When `data.status === "UNVERIFIED"` or network fetch throws an error, `loadAlerts()` renders:
     - Title: `Warning Status Could Not Be Verified (Offline)`
     - Description: `You are currently offline. Official disaster warning status could not be verified from IMD. Please check official emergency channels.`
     - Severity Badge: `⚠️ UNVERIFIED WARNING STATE`

---

## 4. AI Engine & LLM Failure Fallback

- **Deterministic Grounding Fallback**:
  - When LLM generation times out or fails (API key issue/quota error), `GroundedLLMGenerator` catches the exception and invokes Person 1's `_generate_fallback()` engine.
  - The fallback generates structured, grounded natural language advice in the target language (Tamil, English, Hindi, Tanglish, Hinglish) using validated Pydantic observation facts, safety advisories, and source attribution.
- **Offline Chat Handling**:
  - If backend API is unreachable, the mobile chat UI displays a structured offline message with cached weather telemetry and a safe `🔄 Retry Send` button.

---

## 5. Retry Mechanism & Concurrency Safety

- **Safe Backoff**:
  - API retry logic incorporates linear/exponential backoff (`0.05s * attempt`) to avoid rapid loop retries or server spamming.
- **Concurrency Locks**:
  - `isSendingChatMessage` and `isFetchingWeather` boolean locks block duplicate submission clicks and concurrent auto-refreshes.

---

## 6. Service Worker & PWA Cache Safety

- **App Shell Cache (Stale-While-Revalidate)**:
  - Cache target assets: `/`, `/index.html`, `/styles.css`, `/app.js`, `/mobile/apiClient.js`, `/manifest.json`.
- **Authenticated Data Privacy**:
  - Service Worker (`sw.js`) explicitly intercepts `/api/` requests.
  - If network is unavailable, SW returns a structured `503 NETWORK_OFFLINE` JSON response.
  - **No authenticated user data (JWT tokens, user profile, chat history) is stored in the public SW Cache storage.**

---

## 7. Network Recovery & Database Resilience

- **Network Recovery (`online` Event)**:
  - When browser connectivity returns, `setupNetworkMonitoring` triggers `loadCurrentWeather(true)`, updating current weather, forecast, and warnings automatically without request duplication.
- **Database Lock Resilience**:
  - Chat integration service wraps database persistence steps in `try...except Exception:` with `db.rollback()`.
  - Temporary DB lock or transaction error logs a warning but allows the user to receive their AI response without crashing.

---

## 8. Test Methodology & Verification

12 dedicated test scenarios in `tests/test_offline_resilience.py`:
1. `test_01_offline_launch_and_indicator`: Service worker static app shell caching & offline bar.
2. `test_02_cached_weather_retrieval`: Cached observation rendering with timestamp & source tag.
3. `test_03_stale_cache_indication`: Degraded/cached badge verification (no fake live tags).
4. `test_04_forecast_cache_rendering`: Bounded cached forecast with last updated timestamp.
5. `test_05_warning_state_unverified_safety`: Unverified warning status (never "No warning").
6. `test_06_provider_failure_resilience`: Provider failover from IMD to secondary provider.
7. `test_07_llm_failure_fallback`: Grounded deterministic AI fallback on LLM failure.
8. `test_08_backend_unavailable_resilience`: Graceful 500/503/504 error response handling.
9. `test_09_safe_retry_and_backoff`: Retry backoff avoiding rapid loops or duplicates.
10. `test_10_network_recovery_refresh`: Single auto-refresh on network recovery.
11. `test_11_duplicate_send_prevention`: Concurrency locks blocking duplicate requests.
12. `test_12_authenticated_data_cache_safety`: SW public cache isolation from authenticated API endpoints.
