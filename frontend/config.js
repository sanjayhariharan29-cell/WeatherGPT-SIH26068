/**
 * SkyZen Global Runtime Environment Configuration
 * 
 * - Centralized Production API Base URL for SkyZen / WeatherGPT.
 * - Used across Mobile Web, Native Android WebView, and Capacitor bundles.
 */
const API_BASE_URL = "https://skyzen-backend.onrender.com/api/v1";
const DEPLOYED_BACKEND_URL = API_BASE_URL;

window.API_BASE_URL = API_BASE_URL;
window.DEPLOYED_BACKEND_URL = DEPLOYED_BACKEND_URL;

window.ENV = window.ENV || {
  API_BASE: (typeof window !== "undefined" && (window.SKYZEN_API_BASE || window.SKYZEN_PRODUCTION_API_URL)) || API_BASE_URL,
  PRODUCTION_API_BASE: (typeof window !== "undefined" && (window.SKYZEN_PRODUCTION_API_URL || window.SKYZEN_API_BASE)) || API_BASE_URL,
  DEMO_MODE: false
};
