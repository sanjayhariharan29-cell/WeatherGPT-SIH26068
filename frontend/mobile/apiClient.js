/**
 * Centralized WeatherGPT Mobile API Client
 * 
 * Supports Environment Config, JWT Authentication, Request ID Correlation,
 * Timeout Handling, Network Offline Detection, and Structured Error Responses.
 */

class WeatherGPTApiClient {
  constructor() {
    const savedBase = typeof localStorage !== "undefined" ? localStorage.getItem("weathergpt_api_base") : null;
    this.baseUrl = savedBase || (window.ENV && window.ENV.API_BASE) || "/api/v1";
    this.tokenKey = "weathergpt_auth_token";
    this.timeoutMs = 10000;
  }

  // Dynamic Base URL for Android WebView / Local Dev / Prod
  getBaseUrl() {
    return this.baseUrl;
  }

  setBaseUrl(url) {
    if (url) {
      this.baseUrl = url.replace(/\/+$/, "");
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

  isAuthenticated() {
    return Boolean(this.getToken());
  }

  // Request Headers Helper
  getHeaders(customHeaders = {}) {
    const headers = {
      "Content-Type": "application/json",
      "X-Request-ID": `mob_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
      ...customHeaders
    };

    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    return headers;
  }

  // Generic Fetch with Timeout & Error Handling
  async request(endpoint, options = {}) {
    if (!navigator.onLine) {
      throw new Error("NETWORK_OFFLINE: You are currently offline. Please check your internet connection.");
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    const config = {
      ...options,
      headers: this.getHeaders(options.headers),
      signal: controller.signal
    };

    try {
      const url = `${this.baseUrl}${endpoint}`;
      const response = await fetch(url, config);
      clearTimeout(timeoutId);

      const isJson = response.headers.get("content-type")?.includes("application/json");
      const data = isJson ? await response.json() : null;

      if (!response.ok) {
        const errorMsg = data?.detail || data?.error?.message || `HTTP ${response.status} Error`;
        const error = new Error(errorMsg);
        error.status = response.status;
        error.data = data;
        throw error;
      }

      return data;
    } catch (err) {
      clearTimeout(timeoutId);
      if (err.name === "AbortError") {
        throw new Error("REQUEST_TIMEOUT: Request timed out. Backend took too long to respond.");
      }
      throw err;
    }
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

  async getProfile() {
    return await this.request("/users/me");
  }

  async updateProfile(payload) {
    return await this.request("/users/me", {
      method: "PUT",
      body: JSON.stringify(payload)
    });
  }

  async getPreferences() {
    return await this.request("/users/preferences");
  }

  async updatePreferences(payload) {
    return await this.request("/users/preferences", {
      method: "PUT",
      body: JSON.stringify(payload)
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
  async getCurrentWeather(locationName) {
    return await this.request(`/weather/current?location=${encodeURIComponent(locationName)}`);
  }

  async getForecast(locationName, date = "tomorrow") {
    return await this.request(`/weather/forecast?location=${encodeURIComponent(locationName)}&date=${encodeURIComponent(date)}`);
  }

  async getAlerts(locationName) {
    return await this.request(`/weather/alerts?location=${encodeURIComponent(locationName)}`);
  }

  async getHistory(locationName, startDate, endDate) {
    return await this.request(`/weather/history?location=${encodeURIComponent(locationName)}&start_date=${startDate}&end_date=${endDate}`);
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
  async sendChatMessage(message, persona = "student", locationName = "Coimbatore", conversationId = null, language = "ta") {
    const payload = {
      message,
      persona,
      language,
      location: { name: locationName }
    };
    if (conversationId) {
      payload.conversation_id = conversationId;
    }
    return await this.request("/chat", {
      method: "POST",
      body: JSON.stringify(payload)
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
}

// Export singleton instance
const apiClient = new WeatherGPTApiClient();
if (typeof window !== "undefined") {
  window.apiClient = apiClient;
}
