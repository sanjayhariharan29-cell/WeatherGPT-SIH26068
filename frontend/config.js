/**
 * SkyZen Global Runtime Environment Configuration
 * 
 * - Web Deployments (Cloud Run, Docker, Reverse Proxy):
 *   Defaults to relative "/api/v1" communicating with same-origin backend.
 * 
 * - Native Android / Capacitor (Physical Phone / Emulator):
 *   Set window.SKYZEN_API_BASE or window.SKYZEN_PRODUCTION_API_URL to your deployed
 *   production backend URL (e.g., https://api.skyzen.gov.in/api/v1).
 *   Alternatively, configure dynamically via in-app Settings > API Environment Server.
 */
// Centralized Backend URL for SkyZen / WeatherGPT
const DEPLOYED_BACKEND_URL = "https://major-shirts-sleep.loca.lt/api/v1";

window.ENV = window.ENV || {
  API_BASE: (typeof window !== "undefined" && (window.SKYZEN_API_BASE || window.SKYZEN_PRODUCTION_API_URL)) || DEPLOYED_BACKEND_URL,
  PRODUCTION_API_BASE: (typeof window !== "undefined" && (window.SKYZEN_PRODUCTION_API_URL || window.SKYZEN_API_BASE)) || DEPLOYED_BACKEND_URL,
  DEMO_MODE: false
};


