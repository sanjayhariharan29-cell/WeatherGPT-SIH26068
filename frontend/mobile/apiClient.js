/**
 * Centralized WeatherGPT Mobile API Client
 * 
 * Supports Environment Config, JWT Authentication, Request ID Correlation,
 * Timeout Handling, Network Offline Detection, and Structured Error Responses.
 */

class WeatherGPTApiClient {
  constructor() {
    let savedBase = typeof localStorage !== "undefined" ? localStorage.getItem("weathergpt_api_base") : null;
    const envBase = (typeof window !== "undefined" && window.ENV && (window.ENV.API_BASE || window.ENV.PRODUCTION_API_BASE)) || null;

    // Auto-migrate dead/stale tunnel URLs from previous sessions
    if (savedBase && (savedBase.includes("shaggy-candies-serve") || (savedBase.includes(".loca.lt") && envBase && !envBase.includes("shaggy-candies-serve") && savedBase !== envBase.trim().replace(/\/+$/, "")))) {
      savedBase = envBase;
      if (typeof localStorage !== "undefined" && envBase) {
        localStorage.setItem("weathergpt_api_base", envBase.trim().replace(/\/+$/, ""));
      }
    }

    if (savedBase) {
      this.baseUrl = savedBase.trim().replace(/\/+$/, "");
    } else if (envBase && envBase !== "/api/v1") {
      this.baseUrl = envBase.trim().replace(/\/+$/, "");
    } else {
      this.baseUrl = "/api/v1";
    }
    this.tokenKey = "weathergpt_auth_token";
    this.timeoutMs = 35000;
    this.inFlightRequests = new Map();
    this.responseCache = new Map();
    this.CACHE_TTL_MS = 30000;
    this.refreshPromise = null;
  }

  // Cache and In-Flight Deduplication Key Generator
  getDedupKey(endpoint, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    if (method === "GET") {
      return `GET:${this.baseUrl}${endpoint}`;
    }
    // Idempotent read-like POST queries (e.g. reverse geocoding)
    if (method === "POST" && endpoint.includes("/locations/reverse")) {
      const bodyStr = typeof options.body === "string" ? options.body : JSON.stringify(options.body || {});
      return `POST:${this.baseUrl}${endpoint}:${bodyStr}`;
    }
    return null;
  }

  // Clear memory cache and in-flight tracking
  clearCache() {
    this.responseCache.clear();
    this.inFlightRequests.clear();
  }

  // Quick Health Check for Connection Diagnostics
  async checkHealth(timeoutMs = 4000) {
    if (typeof AbortController === "undefined") return true;
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(`${this.baseUrl}/health`, {
        method: "GET",
        headers: { "Bypass-Tunnel-Reminder": "true" },
        signal: controller.signal
      });
      clearTimeout(id);
      return res.ok;
    } catch (e) {
      clearTimeout(id);
      return false;
    }
  }

  isNativeAndroid() {
    return Boolean(
      (typeof window !== "undefined" && window.Capacitor && window.Capacitor.isNativePlatform()) ||
      (typeof window !== "undefined" && window.location && window.location.protocol === "https:" && window.location.hostname === "localhost" && !window.location.port)
    );
  }

  hasConfiguredBackend() {
    if (this.isNativeAndroid()) {
      return Boolean(this.baseUrl && this.baseUrl !== "/api/v1" && !this.baseUrl.includes("localhost"));
    }
    return true;
  }

  // Dynamic Base URL for Android WebView / Local Dev / Prod
  getBaseUrl() {
    return this.baseUrl;
  }

  setBaseUrl(url) {
    if (url) {
      this.baseUrl = url.trim().replace(/\/+$/, "");
      if (typeof localStorage !== "undefined") {
        localStorage.setItem("weathergpt_api_base", this.baseUrl);
      }
    }
  }

  // Token Management
  getToken() {
    return localStorage.getItem(this.tokenKey) || "";
  }

  setToken(token) {
    if (token) {
      localStorage.setItem(this.tokenKey, token);
    } else {
      localStorage.removeItem(this.tokenKey);
    }
  }

  removeToken() {
    localStorage.removeItem(this.tokenKey);
  }

  isTokenExpired(token = null, bufferSeconds = 5) {
    const t = token || this.getToken();
    if (!t) return true;
    try {
      const parts = t.split(".");
      if (parts.length !== 3) return false;
      const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
      if (!payload.exp) return false;
      return (Date.now() / 1000) >= (payload.exp - bufferSeconds);
    } catch (e) {
      return false;
    }
  }

  checkAndProactivelyRefreshToken() {
    const token = this.getToken();
    if (!token) return;
    try {
      const parts = token.split(".");
      if (parts.length !== 3) return;
      const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
      if (!payload.exp) return;
      const nowSec = Date.now() / 1000;
      // If token expires within 15 minutes (900s), refresh proactively in background
      if (payload.exp > nowSec && (payload.exp - nowSec) < 900) {
        if (!this.refreshPromise) {
          this.refreshToken().catch(err => {
            console.debug("[Auth] Proactive background refresh notice:", err.message);
          });
        }
      }
    } catch (e) {}
  }

  isAuthenticated() {
    const token = this.getToken();
    if (!token) return false;
    return true;
  }

  // Request Headers Helper
  getHeaders(customHeaders = {}, isFormData = false) {
    this.checkAndProactivelyRefreshToken();

    const headers = {
      "X-Request-ID": `mob_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
      "Bypass-Tunnel-Reminder": "true",
      ...customHeaders
    };
    if (!isFormData && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    return headers;
  }

  // Generic Fetch with Timeout, In-Flight Deduplication, Short-Term Caching & Error Handling
  async request(endpoint, options = {}) {
    if (!navigator.onLine) {
      throw new Error("NETWORK_OFFLINE: You are currently offline. Please check your internet connection.");
    }

    // Guard against unconfigured relative /api/v1 on native Android
    if (this.isNativeAndroid() && (!this.baseUrl || this.baseUrl === "/api/v1")) {
      throw new Error("PRODUCTION_BACKEND_URL_REQUIRED: Production backend URL is not configured. Please set your SkyZen API server in Settings.");
    }

    const dedupKey = this.getDedupKey(endpoint, options);
    const bypassCache = Boolean(options.bypassCache || options.noCache);

    // 1. Check Short-Term Memory Cache (for idempotent reads when not bypassed)
    if (dedupKey && !bypassCache && this.responseCache.has(dedupKey)) {
      const entry = this.responseCache.get(dedupKey);
      const now = Date.now();
      const ttl = options.cacheTtlMs || this.CACHE_TTL_MS;
      if (now - entry.timestamp < ttl) {
        return entry.data ? JSON.parse(JSON.stringify(entry.data)) : entry.data;
      } else {
        this.responseCache.delete(dedupKey);
      }
    }

    // 2. In-Flight Request Deduplication: Share pending promise if identical query is already in-flight
    if (dedupKey && !options._isRetryAfterRefresh && this.inFlightRequests.has(dedupKey)) {
      const existingPromise = this.inFlightRequests.get(dedupKey);
      if (options.signal) {
        return new Promise((resolve, reject) => {
          if (options.signal.aborted) {
            return reject(new DOMException("Aborted", "AbortError"));
          }
          const onAbort = () => reject(new DOMException("Aborted", "AbortError"));
          options.signal.addEventListener("abort", onAbort, { once: true });
          existingPromise.then(
            (res) => {
              options.signal.removeEventListener("abort", onAbort);
              resolve(res ? JSON.parse(JSON.stringify(res)) : res);
            },
            (err) => {
              options.signal.removeEventListener("abort", onAbort);
              reject(err);
            }
          );
        });
      }
      const sharedRes = await existingPromise;
      return sharedRes ? JSON.parse(JSON.stringify(sharedRes)) : sharedRes;
    }

    // 3. Initiate New Network Request
    const executeFetch = async () => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

      const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
      
      let callerAbortListener = null;
      if (options.signal) {
        if (options.signal.aborted) {
          clearTimeout(timeoutId);
          throw new DOMException("Aborted", "AbortError");
        }
        callerAbortListener = () => controller.abort();
        options.signal.addEventListener("abort", callerAbortListener, { once: true });
      }

      const config = {
        ...options,
        headers: this.getHeaders(options.headers, isFormData),
        signal: controller.signal
      };

      try {
        const url = `${this.baseUrl}${endpoint}`;
        const response = await fetch(url, config);
        clearTimeout(timeoutId);
        if (callerAbortListener && options.signal) {
          options.signal.removeEventListener("abort", callerAbortListener);
        }

        const isJson = response.headers.get("content-type")?.includes("application/json");
        const data = isJson ? await response.json() : null;

        if (!response.ok) {
          if (response.status === 401 && endpoint !== "/auth/login" && endpoint !== "/auth/register" && endpoint !== "/auth/refresh") {
            const hasToken = Boolean(this.getToken());
            if (hasToken && !options._isRetryAfterRefresh) {
              try {
                const refreshed = await this.refreshToken();
                if (refreshed && refreshed.access_token) {
                  if (dedupKey) {
                    this.inFlightRequests.delete(dedupKey);
                    this.responseCache.delete(dedupKey);
                  }
                  // Retry the original request once with fresh credentials
                  return await this.request(endpoint, {
                    ...options,
                    _isRetryAfterRefresh: true,
                    bypassCache: true,
                    headers: {
                      ...(options.headers || {}),
                      "Authorization": `Bearer ${refreshed.access_token}`
                    }
                  });
                }
              } catch (refreshErr) {
                // Refresh failed; legitimately clear token and signal session expiration
                this.removeToken();
                if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
                  window.dispatchEvent(new CustomEvent("skyzen:auth_expired", { detail: { message: data?.detail || "Session expired" } }));
                }
              }
            } else {
              this.removeToken();
              if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
                window.dispatchEvent(new CustomEvent("skyzen:auth_expired", { detail: { message: data?.detail || "Session expired" } }));
              }
            }
          }
          const errorMsg = data?.detail || data?.error?.message || `HTTP ${response.status} Error`;
          const error = new Error(errorMsg);
          error.status = response.status;
          error.data = data;
          throw error;
        }

        if (dedupKey && !bypassCache) {
          this.responseCache.set(dedupKey, {
            data: data ? JSON.parse(JSON.stringify(data)) : data,
            timestamp: Date.now()
          });
        }

        return data;
      } catch (err) {
        clearTimeout(timeoutId);
        if (callerAbortListener && options.signal) {
          options.signal.removeEventListener("abort", callerAbortListener);
        }
        if (err.name === "AbortError") {
          throw new Error("REQUEST_TIMEOUT: Request timed out. Backend took too long to respond.");
        }
        throw err;
      }
    };

    const fetchPromise = executeFetch();

    if (dedupKey) {
      this.inFlightRequests.set(dedupKey, fetchPromise);
      fetchPromise.finally(() => {
        this.inFlightRequests.delete(dedupKey);
      });
    }

    return await fetchPromise;
  }

  // Authentication API Methods
  async register(payload) {
    const res = await this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    return res;
  }

  async login(email, password) {
    const res = await this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
    if (res && res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  async demoLogin() {
    const res = await this.request("/auth/demo", {
      method: "POST",
      body: JSON.stringify({})
    });
    if (res && res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  async refreshToken() {
    if (this.refreshPromise) {
      return await this.refreshPromise;
    }

    const token = this.getToken();
    if (!token) {
      throw new Error("No session token available to refresh");
    }

    this.refreshPromise = (async () => {
      try {
        const url = `${this.baseUrl}/auth/refresh`;
        const headers = {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
          "Bypass-Tunnel-Reminder": "true"
        };
        const response = await fetch(url, {
          method: "POST",
          headers,
          body: JSON.stringify({})
        });
        const isJson = response.headers.get("content-type")?.includes("application/json");
        const data = isJson ? await response.json() : null;

        if (!response.ok) {
          const errMsg = data?.detail || `HTTP ${response.status} Error on token refresh`;
          throw new Error(errMsg);
        }

        if (data && data.access_token) {
          this.setToken(data.access_token);
        }
        return data;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return await this.refreshPromise;
  }

  async verifyEmail(token) {
    return await this.request("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token })
    });
  }

  async resendVerification(email) {
    return await this.request("/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ email })
    });
  }

  async forgotPassword(email) {
    return await this.request("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email })
    });
  }

  async verifyResetToken(token) {
    return await this.request("/auth/verify-reset-token", {
      method: "POST",
      body: JSON.stringify({ token })
    });
  }

  async resetPassword(token, newPassword, confirmPassword = null) {
    return await this.request("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({
        token,
        new_password: newPassword,
        confirm_password: confirmPassword || newPassword
      })
    });
  }

  async getAuthMe() {
    return await this.request("/auth/me");
  }

  async getProfile() {
    return await this.request("/auth/profile");
  }

  async updateProfile(profileData) {
    return await this.request("/auth/profile", {
      method: "PUT",
      body: JSON.stringify(profileData)
    });
  }

  async logout() {
    try {
      if (this.isAuthenticated()) {
        await this.request("/auth/logout", { method: "POST" });
      }
    } catch (e) {
      console.warn("Logout request failed:", e.message);
    } finally {
      this.removeToken();
    }
  }

  async getUserMe() {
    return await this.request("/users/me");
  }

  async updateUserMe(payload) {
    return await this.request("/users/me", {
      method: "PUT",
      body: JSON.stringify(payload)
    });
  }

  async getPreferences() {
    return await this.request("/users/preferences");
  }

  async updatePreferences(payload) {
    return new Promise((resolve, reject) => {
      if (this._updatePreferencesTimer) {
        clearTimeout(this._updatePreferencesTimer);
      }
      this._pendingPreferences = { ...(this._pendingPreferences || {}), ...payload };
      this._updatePreferencesResolvers = this._updatePreferencesResolvers || [];
      this._updatePreferencesResolvers.push({ resolve, reject });

      this._updatePreferencesTimer = setTimeout(async () => {
        const finalPayload = this._pendingPreferences;
        const resolvers = this._updatePreferencesResolvers;
        this._pendingPreferences = null;
        this._updatePreferencesResolvers = null;
        this._updatePreferencesTimer = null;

        try {
          const res = await this.request("/users/preferences", {
            method: "PUT",
            body: JSON.stringify(finalPayload)
          });
          if (resolvers) resolvers.forEach(r => r.resolve(res));
        } catch (err) {
          if (resolvers) resolvers.forEach(r => r.reject(err));
        }
      }, 400);
    });
  }

  // Saved Locations API Methods
  async getSavedLocations() {
    return await this.request("/locations/saved");
  }

  async saveLocation(name, latitude, longitude) {
    return await this.request("/locations/saved", {
      method: "POST",
      body: JSON.stringify({ name, latitude, longitude })
    });
  }

  async deleteSavedLocation(id) {
    return await this.request(`/locations/saved/${id}`, {
      method: "DELETE"
    });
  }

  // Weather & Locations API Methods
  async getCurrentWeather(locationName, lat = null, lon = null, options = {}) {
    let endpoint = `/weather/current?location=${encodeURIComponent(locationName || 'Selected Location')}`;
    if (lat !== null && lon !== null && lat !== undefined && lon !== undefined) {
      endpoint += `&lat=${lat}&lon=${lon}`;
    }
    return await this.request(endpoint, options);
  }

  async getForecast(locationName, date = "tomorrow", lat = null, lon = null) {
    let endpoint = `/weather/forecast?location=${encodeURIComponent(locationName)}&date=${encodeURIComponent(date)}`;
    if (lat !== null && lon !== null && lat !== undefined && lon !== undefined) {
      endpoint += `&lat=${lat}&lon=${lon}`;
    }
    return await this.request(endpoint);
  }

  async getAlerts(locationName, lat = null, lon = null, options = {}) {
    if (options && options.all_cities) {
      return await this.request('/weather/alerts?all_cities=true', options);
    }
    let endpoint = `/weather/alerts?location=${encodeURIComponent(locationName || 'Selected Location')}`;
    if (lat !== null && lon !== null && lat !== undefined && lon !== undefined) {
      endpoint += `&lat=${lat}&lon=${lon}`;
    }
    return await this.request(endpoint, options);
  }

  async getAllAlerts(options = {}) {
    return await this.request('/weather/alerts?all_cities=true', options);
  }

  async getAirQuality(locationName, lat = null, lon = null) {
    let endpoint = `/weather/air-quality?location=${encodeURIComponent(locationName)}`;
    if (lat !== null && lon !== null) {
      endpoint += `&lat=${lat}&lon=${lon}`;
    }
    return await this.request(endpoint);
  }

  async getHistory(locationName, startDate, endDate) {
    return await this.request(`/weather/history?location=${encodeURIComponent(locationName)}&start_date=${startDate}&end_date=${endDate}`);
  }

  async getClimateTrends(locationName, lat = null, lon = null, startYear = 2015, endYear = 2025) {
    let endpoint = `/weather/trends?location=${encodeURIComponent(locationName)}&start_year=${startYear}&end_year=${endYear}`;
    if (lat !== null && lon !== null && lat !== undefined && lon !== undefined) {
      endpoint += `&lat=${lat}&lon=${lon}`;
    }
    return await this.request(endpoint);
  }

  async searchLocations(query) {
    return await this.request(`/locations/search?q=${encodeURIComponent(query)}`);
  }

  async resolveLocation(query = null, latitude = null, longitude = null) {
    return await this.request("/locations/resolve", {
      method: "POST",
      body: JSON.stringify({ query, latitude, longitude })
    });
  }

  async reverseGeocode(latitude, longitude, accuracy = null) {
    return await this.request("/locations/reverse", {
      method: "POST",
      body: JSON.stringify({ latitude, longitude, accuracy })
    });
  }

  // Conversational Chat API Methods
  async sendChatMessage(message, persona = "student", locationInput = null, conversationId = null, language = "ta") {
    let locPayload = null;
    if (typeof locationInput === "object" && locationInput !== null) {
      locPayload = {
        name: locationInput.name || null,
        latitude: locationInput.latitude ?? locationInput.lat ?? null,
        longitude: locationInput.longitude ?? locationInput.lon ?? null,
        source_type: locationInput.source_type || locationInput.type || "manual",
        accuracy: locationInput.accuracy ?? null,
        is_stale: Boolean(locationInput.isStale || locationInput.is_stale)
      };
    } else if (typeof locationInput === "string" && locationInput.trim()) {
      locPayload = { name: locationInput.trim() };
    }

    const payload = {
      message,
      persona,
      language,
      location: locPayload
    };
    if (conversationId) {
      payload.conversation_id = conversationId;
    }
    return await this.request("/chat", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  async sendVoiceQuery(formData) {
    return await this.request("/voice/query", {
      method: "POST",
      body: formData
    });
  }

  async getConversations() {
    return await this.request("/chat/conversations");
  }

  async getConversationDetail(id) {
    return await this.request(`/chat/conversations/${id}`);
  }

  async deleteConversation(id) {
    return await this.request(`/chat/conversations/${id}`, {
      method: "DELETE"
    });
  }

  // Push Notification Device Token APIs
  async registerDeviceToken(token, platform = "android", deviceName = null) {
    return await this.request("/notifications/devices", {
      method: "POST",
      body: JSON.stringify({ token, platform, device_name: deviceName })
    });
  }

  async unregisterDeviceToken(token) {
    return await this.request(`/notifications/devices/${encodeURIComponent(token)}`, {
      method: "DELETE"
    });
  }

  async listDeviceTokens() {
    return await this.request("/notifications/devices", {
      method: "GET"
    });
  }

  async sendTestNotification(title = null, body = null, deviceToken = null) {
    return await this.request("/notifications/test", {
      method: "POST",
      body: JSON.stringify({ title, body, device_token: deviceToken })
    });
  }

  // Developer APIs
  async uploadManualAqi(file) {
    const formData = new FormData();
    formData.append("file", file);
    return await this.request("/developer/aqi/upload", {
      method: "POST",
      body: formData
    });
  }

  async getDeveloperAqiRecords(station = null, limit = 50) {
    let endpoint = `/developer/aqi/records?limit=${limit}`;
    if (station) {
      endpoint += `&station=${encodeURIComponent(station)}`;
    }
    return await this.request(endpoint);
  }

  async createDeveloperAlert(alertData) {
    return await this.request('/developer/alerts', {
      method: 'POST',
      body: JSON.stringify(alertData)
    });
  }

  async getDeveloperAlerts(location = null, activeOnly = false) {
    let url = '/developer/alerts?';
    if (location) url += `location=${encodeURIComponent(location)}&`;
    if (activeOnly) url += 'active_only=true&';
    return await this.request(url);
  }

  async deleteDeveloperAlert(alertId) {
    return await this.request(`/developer/alerts/${encodeURIComponent(alertId)}`, {
      method: 'DELETE'
    });
  }
}


// Export singleton instance
const apiClient = new WeatherGPTApiClient();
if (typeof window !== "undefined") {
  window.apiClient = apiClient;
}
