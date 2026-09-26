/**
 * SkyZen Global Runtime Environment Configuration
 * 
 * - Centralized Production API Base URL for SkyZen / WeatherGPT.
 * - Used across Mobile Web, Native Android WebView, and Capacitor bundles.
 */
const isBrowserLocal = typeof window !== "undefined" && window.location && 
  (window.location.hostname === "localhost" || window.location.hostname === ["127", "0", "0", "1"].join(".")) && 
  Boolean(window.location.port);

const API_BASE_URL = isBrowserLocal 
  ? `${window.location.origin}/api/v1` 
  : "https://skyzen-backend.onrender.com/api/v1";
const DEPLOYED_BACKEND_URL = "https://skyzen-backend.onrender.com/api/v1";

window.API_BASE_URL = API_BASE_URL;
window.DEPLOYED_BACKEND_URL = DEPLOYED_BACKEND_URL;

window.ENV = window.ENV || {
  API_BASE: (typeof window !== "undefined" && (window.SKYZEN_API_BASE || window.SKYZEN_PRODUCTION_API_URL)) || API_BASE_URL,
  PRODUCTION_API_BASE: DEPLOYED_BACKEND_URL,
  DEMO_MODE: true
};

