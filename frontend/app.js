// WeatherGPT Mobile Dashboard Application Logic

let autoRefreshInterval = null;
let isFetchingWeather = false;

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

function initApp() {
  setupNavigation();
  setupNetworkMonitoring();
  setupAuthListeners();
  setupEventListeners();
  setupAutoRefresh();
  checkAuthState();
  loadCurrentWeather();
}

// 1. Mobile Navigation & Routing
function setupNavigation() {
  const navItems = document.querySelectorAll(".nav-item");

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const targetScreen = item.getAttribute("data-screen");
      navigateToScreen(targetScreen);
    });
  });

  window.addEventListener("hashchange", handleHashNavigation);
  if (window.location.hash) {
    handleHashNavigation();
  }
}

function navigateToScreen(screenName) {
  const navItems = document.querySelectorAll(".nav-item");
  const screens = document.querySelectorAll(".screen-container");

  navItems.forEach(i => {
    if (i.getAttribute("data-screen") === screenName) {
      i.classList.add("active");
      i.setAttribute("aria-selected", "true");
    } else {
      i.classList.remove("active");
      i.setAttribute("aria-selected", "false");
    }
  });

  screens.forEach(s => {
    if (s.id === `screen-${screenName}`) {
      s.classList.add("active");
    } else {
      s.classList.remove("active");
    }
  });

  window.location.hash = screenName;
}

function handleHashNavigation() {
  const hash = window.location.hash.replace("#", "");
  const validScreens = ["home", "chat", "weather", "alerts", "profile", "settings"];
  if (validScreens.includes(hash)) {
    navigateToScreen(hash);
  }
}

// 2. Offline / Degradation Monitoring
function setupNetworkMonitoring() {
  const offlineBar = document.getElementById("offlineBar");

  function updateStatus() {
    if (navigator.onLine) {
      offlineBar.classList.add("hidden");
    } else {
      offlineBar.classList.remove("hidden");
    }
  }

  window.addEventListener("online", updateStatus);
  window.addEventListener("offline", updateStatus);
  updateStatus();
}

// 3. Event Listeners & Auto-Refresh Setup
function setupEventListeners() {
  document.getElementById("locationSelect").addEventListener("change", () => loadCurrentWeather(true));
  document.getElementById("personaSelect").addEventListener("change", () => loadCurrentWeather(true));
  
  const geoBtn = document.getElementById("geoBtn");
  if (geoBtn) {
    geoBtn.addEventListener("click", handleDeviceGeolocation);
  }

  const refreshBtn = document.getElementById("refreshBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => loadCurrentWeather(true));
  }

  const retryBtn = document.getElementById("dashboardRetryBtn");
  if (retryBtn) {
    retryBtn.addEventListener("click", () => loadCurrentWeather(true));
  }

  document.getElementById("sendBtn").addEventListener("click", handleUserSend);
  document.getElementById("chatInput").addEventListener("keypress", (e) => {
    if (e.key === "Enter") handleUserSend();
  });

  document.getElementById("voiceBtn").addEventListener("click", handleVoiceClick);
}

// Device Geolocation Handler (GPS / Mobile Location)
function handleDeviceGeolocation() {
  const geoBtn = document.getElementById("geoBtn");
  if (!navigator.geolocation) {
    alert("Geolocation is not supported by your browser or device. Please select location manually.");
    return;
  }

  if (geoBtn) geoBtn.textContent = "🛰️ Locating...";

  navigator.geolocation.getCurrentPosition(
    async (position) => {
      if (geoBtn) geoBtn.textContent = "📍 GPS";
      const lat = position.coords.latitude;
      const lon = position.coords.longitude;
      const accuracy = position.coords.accuracy;

      try {
        const locDetail = await window.apiClient.reverseGeocode(lat, lon, accuracy);
        const locSelect = document.getElementById("locationSelect");
        
        // Check if option already exists
        let optionExists = false;
        for (let i = 0; i < locSelect.options.length; i++) {
          if (locSelect.options[i].value.toLowerCase() === locDetail.name.toLowerCase()) {
            locSelect.selectedIndex = i;
            optionExists = true;
            break;
          }
        }

        if (!optionExists) {
          const newOpt = document.createElement("option");
          newOpt.value = locDetail.name;
          newOpt.textContent = `📍 ${locDetail.name} (GPS)`;
          locSelect.appendChild(newOpt);
          locSelect.value = locDetail.name;
        }

        loadCurrentWeather(true);
      } catch (err) {
        alert(`Location resolved to (${lat.toFixed(2)}, ${lon.toFixed(2)}). Loading weather telemetry.`);
        loadCurrentWeather(true);
      }
    },
    (error) => {
      if (geoBtn) geoBtn.textContent = "📍 GPS";
      switch (error.code) {
        case error.PERMISSION_DENIED:
          alert("Location permission denied. Please select location manually from the dropdown.");
          break;
        case error.TIMEOUT:
          alert("Device location request timed out. Please select location manually.");
          break;
        case error.POSITION_UNAVAILABLE:
          alert("Location information unavailable on this device. Please select location manually.");
          break;
        default:
          alert("Could not determine device location. Using manual location selection.");
          break;
      }
    },
    { timeout: 8000, enableHighAccuracy: true }
  );
}

function setupAutoRefresh() {
  // Clear any existing timer
  if (autoRefreshInterval) clearInterval(autoRefreshInterval);

  // Background Auto-Refresh every 5 minutes (300,000 ms) respecting backend TTL
  autoRefreshInterval = setInterval(() => {
    if (document.visibilityState === "visible" && !isFetchingWeather) {
      loadCurrentWeather(false);
    }
  }, 300000);
}

// 4. Authentication UI & State
function setupAuthListeners() {
  const loginBtn = document.getElementById("loginSubmitBtn");
  const registerBtn = document.getElementById("registerSubmitBtn");
  const logoutBtn = document.getElementById("logoutBtn");

  loginBtn.addEventListener("click", async () => {
    const email = document.getElementById("authEmail").value.trim();
    const password = document.getElementById("authPassword").value.trim();
    if (!email || !password) {
      alert("Please enter email and password.");
      return;
    }
    try {
      await window.apiClient.login(email, password);
      await checkAuthState();
      document.getElementById("authPassword").value = "";
    } catch (err) {
      alert(err.message || "Login failed.");
    }
  });

  registerBtn.addEventListener("click", async () => {
    const email = document.getElementById("authEmail").value.trim();
    const password = document.getElementById("authPassword").value.trim();
    const persona = document.getElementById("personaSelect").value;
    if (!email || !password) {
      alert("Please enter email and password.");
      return;
    }
    try {
      await window.apiClient.register({
        name: email.split("@")[0] || "User",
        email,
        password,
        persona,
        language: "ta"
      });
      await window.apiClient.login(email, password);
      await checkAuthState();
      document.getElementById("authPassword").value = "";
    } catch (err) {
      alert(err.message || "Registration failed.");
    }
  });

  logoutBtn.addEventListener("click", async () => {
    await window.apiClient.logout();
    await checkAuthState();
  });
}

async function checkAuthState() {
  const statusText = document.getElementById("userStatusText");
  const emailText = document.getElementById("userEmailText");
  const authForm = document.getElementById("authForm");
  const logoutBtn = document.getElementById("logoutBtn");

  if (window.apiClient.isAuthenticated()) {
    try {
      const profile = await window.apiClient.getProfile();
      statusText.textContent = `Signed In: ${profile.name || profile.email}`;
      emailText.textContent = `Email: ${profile.email} | Role: ${profile.role || 'user'}`;
      authForm.style.display = "none";
      logoutBtn.classList.remove("hidden");
      loadSavedLocations();
    } catch (err) {
      window.apiClient.removeToken();
      statusText.textContent = "Guest Mode";
      emailText.textContent = "Sign in to save preferred locations and conversation history.";
      authForm.style.display = "flex";
      logoutBtn.classList.add("hidden");
    }
  } else {
    statusText.textContent = "Guest Mode";
    emailText.textContent = "Sign in to save preferred locations and conversation history.";
    authForm.style.display = "flex";
    logoutBtn.classList.add("hidden");
  }
}

async function loadSavedLocations() {
  const container = document.getElementById("savedLocationsList");
  try {
    const locations = await window.apiClient.getSavedLocations();
    container.innerHTML = "";
    if (locations && locations.length > 0) {
      locations.forEach(loc => {
        const item = document.createElement("div");
        item.className = "saved-loc-item";
        item.innerHTML = `
          <span>📍 <strong>${loc.name}</strong> (${loc.latitude.toFixed(2)}, ${loc.longitude.toFixed(2)})</span>
          <button class="icon-btn" onclick="deleteSavedLoc('${loc.id}')" title="Delete">🗑️</button>
        `;
        container.appendChild(item);
      });
    } else {
      container.innerHTML = "<p style='font-size:12px; color:var(--text-muted);'>No saved locations yet.</p>";
    }
  } catch (err) {
    container.innerHTML = `<p style='font-size:12px; color:var(--alert-red);'>Failed to load saved locations.</p>`;
  }
}

async function deleteSavedLoc(id) {
  try {
    await window.apiClient.deleteSavedLocation(id);
    loadSavedLocations();
  } catch (err) {
    alert("Could not delete saved location.");
  }
}

// 5. Live Weather Dashboard Telemetry Engine
async function loadCurrentWeather(showLoader = false) {
  if (isFetchingWeather) return;
  isFetchingWeather = true;

  const location = document.getElementById("locationSelect").value;
  const refreshBtn = document.getElementById("refreshBtn");
  const skeleton = document.getElementById("dashboardSkeleton");
  const errorCard = document.getElementById("dashboardErrorCard");
  const cardContainer = document.getElementById("weatherCardContainer");

  if (showLoader && skeleton) {
    skeleton.classList.remove("hidden");
  }
  if (refreshBtn) {
    refreshBtn.style.animation = "spin 1s linear infinite";
  }

  try {
    const data = await window.apiClient.getCurrentWeather(location);
    if (errorCard) errorCard.classList.add("hidden");
    if (cardContainer) cardContainer.classList.remove("hidden");

    renderWeatherCard(data);
    await loadForecast(location);
    await loadAlerts(location);
  } catch (err) {
    console.error("Dashboard weather telemetry fetch error:", err);
    if (errorCard) {
      document.getElementById("dashboardErrorText").textContent = err.message || "Failed to connect to weather backend.";
      errorCard.classList.remove("hidden");
    }
  } finally {
    isFetchingWeather = false;
    if (skeleton) skeleton.classList.add("hidden");
    if (refreshBtn) refreshBtn.style.animation = "none";
  }
}

function renderWeatherCard(data) {
  if (!data) return;

  const locName = data.location?.name || "Coimbatore";
  document.getElementById("currentLocationName").textContent = `${locName}, TN`;

  const sourceName = data.source || "IMD";
  document.getElementById("currentSourceTag").textContent = `Authoritative Source: ${sourceName}`;

  // Formatting timestamp & freshness
  const obsTimeStr = data.observed_at ? data.observed_at.split("T")[1]?.slice(0, 5) || "Recent" : "Recent";
  document.getElementById("currentObsTime").textContent = `Observed: ${obsTimeStr} UTC`;

  const freshnessTag = document.getElementById("dataFreshnessTag");
  if (data.data_status === "DATA_UNAVAILABLE" || !data.weather) {
    freshnessTag.textContent = "Data Unavailable";
    freshnessTag.className = "freshness-tag unavailable";
  } else if (data.data_status === "PARTIAL" || data.source !== "IMD") {
    freshnessTag.textContent = "Partial Telemetry";
    freshnessTag.className = "freshness-tag partial";
  } else {
    freshnessTag.textContent = "Fresh Telemetry";
    freshnessTag.className = "freshness-tag fresh";
  }

  // Temperature rendering — prevent fake zeros!
  const tempValElem = document.getElementById("tempVal");
  if (data.weather?.temperature !== undefined && data.weather?.temperature !== null) {
    tempValElem.textContent = Math.round(data.weather.temperature);
  } else {
    tempValElem.textContent = "--";
  }

  document.getElementById("conditionText").textContent = data.weather?.condition || "Condition N/A";

  // Metrics rendering — prevent fake zeros!
  const rainElem = document.getElementById("rainProbVal");
  rainElem.textContent = (data.weather?.rain_probability !== undefined && data.weather?.rain_probability !== null)
    ? `${data.weather.rain_probability}%` : "--";

  const windElem = document.getElementById("windVal");
  windElem.textContent = (data.weather?.wind_speed !== undefined && data.weather?.wind_speed !== null)
    ? `${data.weather.wind_speed} km/h` : "--";

  const humElem = document.getElementById("humidityVal");
  humElem.textContent = (data.weather?.humidity !== undefined && data.weather?.humidity !== null)
    ? `${data.weather.humidity}%` : "--";

  // Multi-Source Agreement
  const agreeElement = document.getElementById("agreementVal");
  if (data.comparison && data.comparison.sources_agree) {
    agreeElement.textContent = "High Agreement (IMD & Open-Meteo)";
    agreeElement.className = "metric-val agreement-high";
  } else {
    agreeElement.textContent = "Disagreement Detected";
    agreeElement.className = "metric-val";
  }
}

async function loadForecast(location) {
  try {
    const data = await window.apiClient.getForecast(location);
    const gridToday = document.getElementById("forecastGridToday") || document.getElementById("forecastGrid");
    const gridTomorrow = document.getElementById("forecastGridTomorrow");
    const gridFuture = document.getElementById("forecastGridFuture");

    if (gridToday) gridToday.innerHTML = "";
    if (gridTomorrow) gridTomorrow.innerHTML = "";
    if (gridFuture) gridFuture.innerHTML = "";

    if (data && data.forecast && data.forecast.length > 0) {
      data.forecast.forEach((item, index) => {
        const card = document.createElement("div");
        card.className = "forecast-card";
        
        const fTime = item.forecast_time ? item.forecast_time.split("T")[1]?.slice(0, 5) || item.forecast_time : "Daily";
        const tempText = (item.temperature !== undefined && item.temperature !== null) ? `${item.temperature}°C` : "--°C";
        const rainText = (item.rain_probability !== undefined && item.rain_probability !== null) ? `${item.rain_probability}%` : "--%";

        card.innerHTML = `
          <span class="fc-time">${fTime}</span>
          <span class="fc-temp">${tempText}</span>
          <span class="fc-rain">☔ ${rainText}</span>
          <span class="fc-cond">${item.condition || 'N/A'}</span>
        `;

        if (index < 4 && gridToday) {
          gridToday.appendChild(card);
        } else if (index < 8 && gridTomorrow) {
          gridTomorrow.appendChild(card);
        } else if (gridFuture) {
          gridFuture.appendChild(card.cloneNode(true));
        } else if (gridToday) {
          gridToday.appendChild(card);
        }
      });
    } else {
      if (gridToday) gridToday.innerHTML = "<p style='font-size:12px; color:var(--text-muted);'>No forecast items available.</p>";
    }
  } catch (err) {
    console.error("Forecast telemetry error:", err);
  }
}

async function loadAlerts(location) {
  try {
    const data = await window.apiClient.getAlerts(location);
    const banner = document.getElementById("alertBanner");
    const disasterList = document.getElementById("disasterList");
    const badge = document.getElementById("alertSeverityBadge");
    const timeElem = document.getElementById("alertTime");
    const titleElem = document.getElementById("alertTitle");
    const descElem = document.getElementById("alertDesc");
    const sourceElem = document.getElementById("alertSourceTag");

    disasterList.innerHTML = "";

    if (data && data.alerts && data.alerts.length > 0) {
      const heroAlert = data.alerts[0];
      const severityStr = (heroAlert.severity || "warning").toUpperCase();

      if (titleElem) titleElem.textContent = heroAlert.title || "Weather Warning";
      if (descElem) descElem.textContent = heroAlert.description || "No description provided.";
      if (badge) {
        badge.textContent = `⚠️ OFFICIAL IMD WARNING (${severityStr})`;
        badge.className = `alert-badge ${heroAlert.severity || 'high'}`;
      }
      if (timeElem) {
        const expStr = heroAlert.expires_at ? `Valid until ${heroAlert.expires_at.split("T")[1]?.slice(0, 5) || '08:00 PM'} UTC` : "Active Warning";
        timeElem.textContent = expStr;
      }
      if (sourceElem) {
        sourceElem.textContent = `Authoritative Source: ${heroAlert.source || 'IMD'}`;
      }

      banner.classList.remove("hidden");

      data.alerts.forEach(a => {
        const item = document.createElement("div");
        item.className = `disaster-item ${a.severity || 'moderate'}`;
        item.innerHTML = `
          <strong>${a.title}</strong> (${a.source || 'IMD'})
          <p style="font-size:12px; margin-top:4px;">${a.description}</p>
        `;
        disasterList.appendChild(item);
      });
    } else {
      banner.classList.add("hidden");
      disasterList.innerHTML = "<p style='font-size:13px; color:#94a3b8;'>No active disaster warnings for this location.</p>";
    }
  } catch (err) {
    console.error("Alerts telemetry error:", err);
  }
}

let isSendingChatMessage = false;

function escapeHTML(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function sendQuickQuery(queryText) {
  navigateToScreen("chat");
  const input = document.getElementById("chatInput");
  if (input) input.value = queryText;
  handleUserSend();
}

async function handleUserSend() {
  if (isSendingChatMessage) return; // Anti-duplicate send protection

  const input = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const text = input ? input.value.trim() : "";
  if (!text) return;

  const location = document.getElementById("locationSelect")?.value || "Coimbatore";
  const persona = document.getElementById("personaSelect")?.value || "student";

  // Lock UI to prevent duplicate submission
  isSendingChatMessage = true;
  if (input) input.disabled = true;
  if (sendBtn) sendBtn.disabled = true;

  appendUserMessage(text);
  if (input) input.value = "";

  const typingId = showTypingIndicator();

  try {
    const data = await window.apiClient.sendChatMessage(text, persona, location);
    removeTypingIndicator(typingId);
    appendBotMessage(data);
    if (data.answer) speakText(data.answer);
  } catch (err) {
    removeTypingIndicator(typingId);
    appendFailedMessage(text, persona, location);
  } finally {
    isSendingChatMessage = false;
    if (input) {
      input.disabled = false;
      input.focus();
    }
    if (sendBtn) sendBtn.disabled = false;
  }
}

function appendUserMessage(text) {
  const history = document.getElementById("chatHistory");
  if (!history) return;

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble user-msg";
  
  const p = document.createElement("p");
  p.textContent = text; // Safe text rendering
  bubble.appendChild(p);

  history.appendChild(bubble);
  history.scrollTop = history.scrollHeight;
}

function showTypingIndicator() {
  const history = document.getElementById("chatHistory");
  if (!history) return null;

  const indicator = document.createElement("div");
  const id = `typing_${Date.now()}`;
  indicator.id = id;
  indicator.className = "msg-bubble bot-msg typing-indicator";
  indicator.innerHTML = `
    <span>🌤️ WeatherGPT is thinking</span>
    <div class="typing-dot"></div>
    <div class="typing-dot"></div>
  `;

  history.appendChild(indicator);
  history.scrollTop = history.scrollHeight;
  return id;
}

function removeTypingIndicator(id) {
  if (!id) return;
  const elem = document.getElementById(id);
  if (elem) elem.remove();
}

function appendBotMessage(data) {
  const history = document.getElementById("chatHistory");
  if (!history) return;

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble bot-msg";

  const safeAnswer = escapeHTML(data.answer || "No response text.");
  const safeIntent = escapeHTML(data.intent || "Weather Query");
  const safeSource = escapeHTML(data.source || "IMD Grounded");

  // Hazard severity badge mapping (Strictly preserving CRITICAL, HIGH, MEDIUM, LOW)
  let hazardBadgeHtml = "";
  if (data.risk && data.risk.level) {
    const rawLevel = String(data.risk.level).toUpperCase();
    const validLevel = ["CRITICAL", "HIGH", "MEDIUM", "LOW"].includes(rawLevel) ? rawLevel : "LOW";
    const cssClass = validLevel.toLowerCase();
    hazardBadgeHtml = `<span class="hazard-badge ${cssClass}">RISK: ${validLevel}</span>`;
  }

  let warningsHtml = "";
  if (data.alerts && data.alerts.length > 0) {
    data.alerts.forEach(alert => {
      const alertTitle = escapeHTML(alert.title || "Official Warning");
      const alertDesc = escapeHTML(alert.description || "");
      const alertSource = escapeHTML(alert.source || "IMD");
      warningsHtml += `
        <div class="chat-warning-box">
          <div class="chat-warning-title">⚠️ ${alertTitle}</div>
          <p class="chat-warning-desc">${alertDesc}</p>
          <div class="chat-warning-source">Authoritative Source: ${alertSource}</div>
        </div>
      `;
    });
  }

  bubble.innerHTML = `
    <div class="msg-author">
      <span>🌤️ WeatherGPT Engine ${hazardBadgeHtml}</span>
      <span class="msg-tag">${safeIntent} • ${safeSource}</span>
    </div>
    <p>${safeAnswer}</p>
    ${warningsHtml}
  `;

  history.appendChild(bubble);
  history.scrollTop = history.scrollHeight;
}

function appendFailedMessage(failedText, persona, location) {
  const history = document.getElementById("chatHistory");
  if (!history) return;

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble bot-msg msg-failed";

  const safeText = escapeHTML(failedText);

  bubble.innerHTML = `
    <div class="msg-author" style="color:var(--alert-red);">
      <span>⚠️ Service Disruption</span>
      <span class="msg-tag">Failed</span>
    </div>
    <p style="font-size:13px;">Weather AI service is temporarily unavailable. Would you like to retry sending "${safeText}"?</p>
    <button class="msg-retry-btn" onclick="retryFailedMessage('${escapeHTML(failedText)}', '${persona}', '${location}', this)">
      🔄 Retry Send
    </button>
  `;

  history.appendChild(bubble);
  history.scrollTop = history.scrollHeight;
}

async function retryFailedMessage(text, persona, location, btnElem) {
  if (btnElem) btnElem.disabled = true;
  const input = document.getElementById("chatInput");
  if (input) input.value = text;
  await handleUserSend();
}

function handleVoiceClick() {
  const voiceBtn = document.getElementById("voiceBtn");

  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = "ta-IN";

    voiceBtn.textContent = "🔴 Listening...";
    recognition.start();

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      document.getElementById("chatInput").value = transcript;
      voiceBtn.textContent = "🎙️";
      handleUserSend();
    };

    recognition.onerror = () => {
      voiceBtn.textContent = "🎙️";
      sendQuickQuery("Naalaiku morning college pogalama?");
    };
  } else {
    sendQuickQuery("Naalaiku morning college pogalama?");
  }
}

function speakText(text) {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ta-IN";
    window.speechSynthesis.speak(utterance);
  }
}
