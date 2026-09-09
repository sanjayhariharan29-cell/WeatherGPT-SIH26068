/**
 * WeatherGPT Global Runtime Environment Configuration
 * 
 * In production hosting (e.g. Render, Railway, AWS, Cloud Run), window.ENV.API_BASE
 * can be overridden to point to a custom API host or relative API prefix.
 */
window.ENV = window.ENV || {
  API_BASE: "/api/v1"
};
