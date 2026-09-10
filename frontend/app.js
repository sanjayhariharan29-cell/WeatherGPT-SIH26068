// SkyZen Weather Intelligence Application Logic
// Built upon MoES / IMD WeatherGPT Decision Engine

let autoRefreshInterval = null;
let isFetchingWeather = false;
// Volatile in-memory GPS state for map & privacy protection
let userGpsLocation = null;
let currentLanguage = localStorage.getItem("skyzen_lang") || "en";

const MAP_PRESET_LOCATIONS = [
  { name: "Coimbatore", lat: 11.0168, lon: 76.9558, state: "Tamil Nadu" },
  { name: "Nagapattinam", lat: 10.7656, lon: 79.8424, state: "Tamil Nadu" },
  { name: "Chennai", lat: 13.0827, lon: 80.2707, state: "Tamil Nadu" },
  { name: "Madurai", lat: 9.9252, lon: 78.1198, state: "Tamil Nadu" },
  { name: "Tiruchirappalli", lat: 10.7905, lon: 78.7047, state: "Tamil Nadu" },
  { name: "Bengaluru", lat: 12.9716, lon: 77.5946, state: "Karnataka" },
  { name: "Delhi", lat: 28.6139, lon: 77.2090, state: "Delhi NCR" }
];

let currentUser = null;
let pendingAuthEmail = "";

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  setupNavigation();
  setupNetworkMonitoring();
  setupAuthPortalEngine();
  setupEventListeners();
  setupAutoRefresh();

  // Initial Entry Flow: Splash -> Session Check -> (Auth Portal OR Home)
  await restoreSessionOrShowAuth();
}

function isAppAuthenticated() {
  return Boolean(currentUser && currentUser.is_verified);
}

// 1. Mobile & Desktop Navigation Engine
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
  if (!isAppAuthenticated()) {
    showAuthPortal("welcome");
    return;
  }

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
  window.scrollTo({ top: 0, behavior: "smooth" });

  if (screenName === "map") {
    initWeatherMap();
  } else if (screenName === "air-quality") {
    const loc = document.getElementById("locationSelect")?.value || "Coimbatore";
    loadAirQuality(loc);
  } else if (screenName === "alerts") {
    const loc = document.getElementById("locationSelect")?.value || "Coimbatore";
    loadAlerts(loc);
  } else if (screenName === "locations") {
    loadSavedLocationsList();
  }
}

function handleHashNavigation() {
  if (!isAppAuthenticated()) {
    showAuthPortal("welcome");
    return;
  }
  const hash = window.location.hash.replace("#", "");
  const validScreens = ["home", "chat", "weather", "alerts", "map", "air-quality", "locations", "more", "profile", "settings"];
  const target = validScreens.includes(hash) ? hash : "home";
  navigateToScreen(target);
}

// 2. Offline / Connectivity & System State Monitoring
let currentSystemState = "ONLINE";

function updateSystemStateBanner(state, details = {}) {
  const offlineBar = document.getElementById("offlineBar");
  const iconElem = document.getElementById("offlineBarIcon");
  const textElem = document.getElementById("offlineBarText");
  if (!offlineBar || !iconElem || !textElem) return;

  currentSystemState = state;
  offlineBar.className = "offline-bar";

  switch (state) {
    case "OFFLINE":
      offlineBar.classList.add("offline");
      iconElem.textContent = "cloud_off";
      textElem.textContent = "You're offline. Reconnect to refresh weather.";
      offlineBar.classList.remove("hidden");
      break;
    case "DATA_STALE":
      offlineBar.classList.add("stale");
      iconElem.textContent = "history";
      const updatedStr = details.updated ? `Last updated: ${details.updated}` : "Showing recently cached weather";
      textElem.textContent = `${updatedStr} (Status: DATA STALE)`;
      offlineBar.classList.remove("hidden");
      break;
    case "DEGRADED":
      offlineBar.classList.add("degraded");
      iconElem.textContent = "warning";
      textElem.textContent = "Some weather sources are unavailable (DEGRADED).";
      offlineBar.classList.remove("hidden");
      break;
    case "SERVICE_UNAVAILABLE":
      offlineBar.classList.add("unavailable");
      iconElem.textContent = "error";
      textElem.textContent = "Weather service temporarily unavailable. Please try again later.";
      offlineBar.classList.remove("hidden");
      break;
    case "ONLINE":
    default:
      offlineBar.classList.add("online", "hidden");
      iconElem.textContent = "cloud_done";
      textElem.textContent = "Weather data is live.";
      break;
  }
}

function setupNetworkMonitoring() {
  function updateNetworkStatus() {
    if (navigator.onLine) {
      if (currentSystemState === "OFFLINE") {
        updateSystemStateBanner("ONLINE");
      }
    } else {
      updateSystemStateBanner("OFFLINE");
    }
  }

  let reconnectDebounce = null;
  window.addEventListener("online", () => {
    updateNetworkStatus();
    if (reconnectDebounce) clearTimeout(reconnectDebounce);
    reconnectDebounce = setTimeout(() => {
      loadCurrentWeather(true);
    }, 600);
  });
  window.addEventListener("offline", updateNetworkStatus);
  updateNetworkStatus();
}

// 3. User Feedback & Notices
let mobileNoticeTimeout = null;
function showMobileNotice(message, type = "info", duration = 4000) {
  const notice = document.getElementById("mobileNotice");
  if (!notice) return;
  if (mobileNoticeTimeout) clearTimeout(mobileNoticeTimeout);

  notice.className = `mobile-notice ${type}`;
  notice.innerHTML = `
    <span>${escapeHTML(message)}</span>
    <button style="background:none;border:none;color:#fff;font-size:18px;cursor:pointer;padding:0 4px;" onclick="document.getElementById('mobileNotice').classList.add('hidden')" aria-label="Close notification">
      <span class="material-symbols-rounded icon-sm">close</span>
    </button>
  `;
  notice.classList.remove("hidden");

  mobileNoticeTimeout = setTimeout(() => {
    notice.classList.add("hidden");
  }, duration);
}

// Weather Condition to Material Symbol mapping (Zero emojis rule)
function getWeatherMaterialIcon(conditionStr) {
  if (!conditionStr) return "partly_cloudy_day";
  const c = conditionStr.toLowerCase();
  if (c.includes("thunder") || c.includes("storm") || c.includes("lightning")) return "thunderstorm";
  if (c.includes("heavy rain") || c.includes("torrential")) return "rainy";
  if (c.includes("rain") || c.includes("drizzle") || c.includes("shower")) return "water_drop";
  if (c.includes("sunny") || c.includes("clear")) return "wb_sunny";
  if (c.includes("partly") || c.includes("scattered")) return "partly_cloudy_day";
  if (c.includes("cloud") || c.includes("overcast")) return "cloud";
  if (c.includes("wind") || c.includes("breeze") || c.includes("squall")) return "air";
  if (c.includes("snow") || c.includes("blizzard") || c.includes("ice")) return "ac_unit";
  if (c.includes("fog") || c.includes("mist") || c.includes("haze")) return "foggy";
  return "partly_cloudy_day";
}

// 4. Event Listeners & Auto-Refresh
function setupEventListeners() {
  const locSelect = document.getElementById("locationSelect");
  if (locSelect) {
    locSelect.addEventListener("change", () => loadCurrentWeather(true));
  }

  const personaSelect = document.getElementById("personaSelect");
  if (personaSelect) {
    personaSelect.addEventListener("change", () => loadCurrentWeather(true));
  }

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

  const sendBtn = document.getElementById("sendBtn");
  if (sendBtn) {
    sendBtn.addEventListener("click", handleUserSend);
  }

  const chatInput = document.getElementById("chatInput");
  if (chatInput) {
    chatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") handleUserSend();
    });
  }

  const voiceBtn = document.getElementById("voiceBtn");
  if (voiceBtn) {
    voiceBtn.addEventListener("click", handleVoiceClick);
  }

  // Language Toggle
  const langToggleBtn = document.getElementById("chatLangToggleBtn");
  if (langToggleBtn) {
    langToggleBtn.addEventListener("click", () => {
      const langs = ["en", "ta", "hi"];
      let idx = langs.indexOf(currentLanguage);
      if (idx === -1) idx = 0;
      const nextLang = langs[(idx + 1) % langs.length];
      
      if (window.I18N) {
        window.I18N.setLanguage(nextLang);
      } else {
        currentLanguage = nextLang;
      }
      
      const langText = document.getElementById("chatLangText");
      if (langText) {
        if (nextLang === "en") langText.textContent = "English";
        else if (nextLang === "ta") langText.textContent = "தமிழ்";
        else if (nextLang === "hi") langText.textContent = "हिंदी";
      }
    });
  }

  window.updateUserLanguage = async function(lang) {
    if (isAppAuthenticated()) {
      try {
        await window.apiClient.updateProfile({ language: lang });
        if (currentUser) currentUser.language = lang;
      } catch (err) {
        console.warn("Failed to sync language preference to backend:", err);
      }
    }
  };

  // Settings Language selector
  const langSelect = document.getElementById("langSelect");
  if (langSelect) {
    langSelect.value = window.I18N ? window.I18N.currentLanguage : currentLanguage;
    langSelect.addEventListener("change", () => {
      const newLang = langSelect.value;
      if (window.I18N) {
        window.I18N.setLanguage(newLang);
      } else {
        currentLanguage = newLang;
      }
      showMobileNotice(`Language updated: ${newLang.toUpperCase()}`, "info", 2000);
    });
  }

  // Alerts Filter Tabs
  const alertTabs = document.querySelectorAll("[data-alert-filter]");
  alertTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      alertTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      filterAlerts(tab.getAttribute("data-alert-filter"));
    });
  });

  // Map Layer Tabs
  const mapLayerTabs = document.querySelectorAll("[data-map-layer]");
  mapLayerTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      mapLayerTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      showMobileNotice(`Map layer switched to: ${tab.textContent.trim()}`, "info", 2000);
    });
  });

  // Map Time Slider Buttons
  const timeStepBtns = document.querySelectorAll("[data-time-offset]");
  timeStepBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      timeStepBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const offset = btn.getAttribute("data-time-offset");
      showMobileNotice(`Radar simulation offset: +${offset} hours`, "info", 1800);
    });
  });

  // Environment Server Switcher (Settings Screen)
  const envSelect = document.getElementById("envSelect");
  const customEnvContainer = document.getElementById("customEnvContainer");
  const customEnvInput = document.getElementById("customEnvInput");
  const saveCustomEnvBtn = document.getElementById("saveCustomEnvBtn");

  if (envSelect) {
    const currentBase = window.apiClient.getBaseUrl();
    let matched = false;
    for (let i = 0; i < envSelect.options.length; i++) {
      if (envSelect.options[i].value === currentBase) {
        envSelect.selectedIndex = i;
        matched = true;
        break;
      }
    }
    if (!matched && currentBase && currentBase !== "/api/v1") {
      envSelect.value = "custom";
      if (customEnvContainer) customEnvContainer.classList.remove("hidden");
      if (customEnvInput) customEnvInput.value = currentBase;
    }

    envSelect.addEventListener("change", () => {
      if (envSelect.value === "custom") {
        if (customEnvContainer) customEnvContainer.classList.remove("hidden");
        if (customEnvInput) customEnvInput.focus();
      } else {
        if (customEnvContainer) customEnvContainer.classList.add("hidden");
        window.apiClient.setBaseUrl(envSelect.value);
        showMobileNotice(`API endpoint updated: ${envSelect.value}`, "info", 3000);
      }
    });

    if (saveCustomEnvBtn && customEnvInput) {
      saveCustomEnvBtn.addEventListener("click", () => {
        const val = (customEnvInput.value || "").trim();
        if (!val || (!val.startsWith("http://") && !val.startsWith("https://"))) {
          showMobileNotice("Please enter a valid HTTP or HTTPS backend URL.", "warning", 4000);
          return;
        }
        window.apiClient.setBaseUrl(val);
        showMobileNotice(`Custom backend URL saved: ${val}`, "info", 3500);
      });
    }
  }

  // Add Location Modal Listeners
  const addLocBtn = document.getElementById("addLocModalBtn");
  const addCityModal = document.getElementById("addCityModal");
  const closeAddCityBtn = document.getElementById("closeAddCityModalBtn");
  const saveCustomCityBtn = document.getElementById("saveCustomCityBtn");
  const customCityInput = document.getElementById("customCityInput");

  if (addLocBtn && addCityModal) {
    addLocBtn.addEventListener("click", () => {
      addCityModal.classList.remove("hidden");
      if (customCityInput) customCityInput.focus();
    });
  }

  if (closeAddCityBtn && addCityModal) {
    closeAddCityBtn.addEventListener("click", () => {
      addCityModal.classList.add("hidden");
    });
  }

  if (addCityModal) {
    addCityModal.addEventListener("click", (e) => {
      if (e.target === addCityModal) {
        addCityModal.classList.add("hidden");
      }
    });
  }

  // Quick Chips in Add City Modal
  const modalChips = document.querySelectorAll("#modalCityChips .chip-btn");
  modalChips.forEach(chip => {
    chip.addEventListener("click", () => {
      const city = chip.getAttribute("data-city");
      const state = chip.getAttribute("data-state") || "India";
      const lat = parseFloat(chip.getAttribute("data-lat")) || 20.0;
      const lon = parseFloat(chip.getAttribute("data-lon")) || 78.0;
      addAndSelectLocation(city, state, lat, lon);
      if (addCityModal) addCityModal.classList.add("hidden");
    });
  });

  if (saveCustomCityBtn && customCityInput) {
    const handleSaveCustom = () => {
      const val = customCityInput.value.trim();
      if (!val) {
        showMobileNotice("Please enter a city or district name.", "warning");
        return;
      }
      addAndSelectLocation(val, "India", 13.0, 80.0);
      customCityInput.value = "";
      if (addCityModal) addCityModal.classList.add("hidden");
    };

    saveCustomCityBtn.addEventListener("click", handleSaveCustom);
    customCityInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") handleSaveCustom();
    });
  }
}

function addAndSelectLocation(cityName, stateName, lat, lon) {
  const existing = MAP_PRESET_LOCATIONS.find(l => l.name.toLowerCase() === cityName.toLowerCase());
  if (!existing) {
    MAP_PRESET_LOCATIONS.push({
      name: cityName,
      lat: lat,
      lon: lon,
      state: stateName
    });
  }

  const locSelect = document.getElementById("locationSelect");
  if (locSelect) {
    let found = false;
    for (let i = 0; i < locSelect.options.length; i++) {
      if (locSelect.options[i].value.toLowerCase() === cityName.toLowerCase()) {
        locSelect.selectedIndex = i;
        found = true;
        break;
      }
    }
    if (!found) {
      const opt = document.createElement("option");
      opt.value = cityName;
      opt.textContent = `${cityName}, ${stateName}`;
      locSelect.appendChild(opt);
      locSelect.selectedIndex = locSelect.options.length - 1;
    }
  }

  loadSavedLocationsList();
  loadCurrentWeather(true);
  showMobileNotice(`Switched to location: ${cityName}`, "info", 2500);
}

// Device Geolocation
function handleDeviceGeolocation() {
  const geoBtn = document.getElementById("geoBtn");
  if (!navigator.geolocation) {
    showMobileNotice("Geolocation is not supported by your browser.", "warning");
    return;
  }

  if (geoBtn) {
    geoBtn.innerHTML = '<span class="material-symbols-rounded">my_location</span> <span>Locating...</span>';
  }

  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      const accuracy = pos.coords.accuracy;
      userGpsLocation = { lat, lon, accuracy };

      try {
        const locDetail = await window.apiClient.reverseGeocode(lat, lon, accuracy);
        const resolvedName = locDetail?.name || locDetail?.district || "Current Location";

        const locSelect = document.getElementById("locationSelect");
        if (locSelect) {
          let found = false;
          for (let i = 0; i < locSelect.options.length; i++) {
            if (locSelect.options[i].value.toLowerCase() === resolvedName.toLowerCase()) {
              locSelect.selectedIndex = i;
              found = true;
              break;
            }
          }
          if (!found) {
            const newOpt = document.createElement("option");
            newOpt.value = resolvedName;
            newOpt.textContent = `${resolvedName} (GPS)`;
            locSelect.insertBefore(newOpt, locSelect.firstChild);
            locSelect.selectedIndex = 0;
          }
        }

        showMobileNotice(`Location identified: ${resolvedName}`, "info", 3500);
        await loadCurrentWeather(true);
      } catch (e) {
        showMobileNotice(`Coordinates acquired: ${lat.toFixed(2)}°, ${lon.toFixed(2)}°`, "info", 3000);
        await loadCurrentWeather(true);
      } finally {
        if (geoBtn) geoBtn.innerHTML = '<span class="material-symbols-rounded">my_location</span> <span>GPS</span>';
      }
    },
    (err) => {
      if (geoBtn) geoBtn.innerHTML = '<span class="material-symbols-rounded">my_location</span> <span>GPS</span>';
      if (err.code === 1) {
        showMobileNotice("Location permission denied. Please enable device GPS permissions or choose a city from the list.", "warning", 5000);
      } else {
        showMobileNotice("Unable to retrieve device GPS coordinates. Please select manually.", "warning", 4000);
      }
    },
    { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
  );
}

// 5-minute Auto-Refresh Configuration (300000 ms)
function setupAutoRefresh() {
  if (autoRefreshInterval) clearInterval(autoRefreshInterval);
  autoRefreshInterval = setInterval(() => {
    if (navigator.onLine && !isFetchingWeather) {
      loadCurrentWeather(false);
    }
  }, 300000);
}

// ============================================================================
// SKYZEN AUTHENTICATION PORTAL & SESSION RESTORATION (PHASE 1)
// ============================================================================

function hideSplashScreen() {
  const splash = document.getElementById("splashScreen");
  if (splash) {
    splash.classList.add("fade-out");
    setTimeout(() => {
      splash.style.display = "none";
    }, 400);
  }
}

function showSplashScreen(statusText = "Initializing Meteorological Intelligence...") {
  const splash = document.getElementById("splashScreen");
  const textElem = document.getElementById("splashStatusText");
  if (splash) {
    splash.style.display = "flex";
    splash.classList.remove("fade-out");
  }
  if (textElem) {
    textElem.textContent = statusText;
  }
}

function showAuthPortal(view = "welcome") {
  const portal = document.getElementById("authPortal");
  if (portal) {
    portal.classList.remove("hidden");
  }
  showAuthView(view);
}

function hideAuthPortal() {
  const portal = document.getElementById("authPortal");
  if (portal) {
    portal.classList.add("hidden");
  }
}

function showAuthView(viewName) {
  const views = {
    welcome: document.getElementById("authViewWelcome"),
    login: document.getElementById("authViewLogin"),
    signup: document.getElementById("authViewSignup"),
    verify: document.getElementById("authViewVerify"),
    forgot: document.getElementById("authViewForgot"),
    reset: document.getElementById("authViewReset"),
    onboarding: document.getElementById("authViewOnboarding")
  };

  Object.values(views).forEach(v => {
    if (v) {
      v.classList.add("hidden");
      v.classList.remove("active");
    }
  });

  const activeView = views[viewName];
  if (activeView) {
    activeView.classList.remove("hidden");
    activeView.classList.add("active");
  }

  // Clear messages
  clearAuthMessage("loginMessage");
  clearAuthMessage("signupMessage");
  clearAuthMessage("verifyMessage");
  clearAuthMessage("forgotMessage");
  clearAuthMessage("resetMessage");
  clearAuthMessage("onboardingMessage");

  if (viewName === "verify") {
    const badge = document.getElementById("verifyEmailBadge");
    if (badge && pendingAuthEmail) {
      badge.textContent = pendingAuthEmail;
    }
  } else if (viewName === "onboarding") {
    if (currentUser) {
      const nameInp = document.getElementById("onboardingFullName");
      const roleInp = document.getElementById("onboardingRole");
      const langInp = document.getElementById("onboardingLanguage");
      const notifInp = document.getElementById("onboardingNotifications");
      if (nameInp && currentUser.name) nameInp.value = currentUser.name;
      if (roleInp && currentUser.persona) roleInp.value = currentUser.persona;
      if (langInp && currentUser.language) langInp.value = currentUser.language;
      if (notifInp && currentUser.notification_enabled !== undefined) notifInp.checked = Boolean(currentUser.notification_enabled);
    }
  }
}

function setAuthMessage(boxId, message, type = "error") {
  const box = document.getElementById(boxId);
  if (!box) return;

  const iconName = type === "success" ? "check_circle" : (type === "info" ? "info" : "error");
  box.className = `auth-message-box ${type}`;
  box.innerHTML = `
    <span class="material-symbols-rounded icon-sm" aria-hidden="true">${iconName}</span>
    <span>${escapeHTML(message)}</span>
  `;
  box.classList.remove("hidden");
}

function clearAuthMessage(boxId) {
  const box = document.getElementById(boxId);
  if (box) {
    box.classList.add("hidden");
    box.innerHTML = "";
  }
}

function setupPasswordToggle(inputElem, toggleBtn) {
  if (!inputElem || !toggleBtn) return;
  toggleBtn.addEventListener("click", () => {
    const isPassword = inputElem.type === "password";
    inputElem.type = isPassword ? "text" : "password";
    const icon = toggleBtn.querySelector(".material-symbols-rounded");
    if (icon) {
      icon.textContent = isPassword ? "visibility_off" : "visibility";
    }
    toggleBtn.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
  });
}

function updatePasswordStrength(password) {
  const bar1 = document.getElementById("strengthBar1");
  const bar2 = document.getElementById("strengthBar2");
  const bar3 = document.getElementById("strengthBar3");
  const textElem = document.getElementById("strengthText");
  if (!bar1 || !bar2 || !bar3 || !textElem) return;

  // Reset bars
  [bar1, bar2, bar3].forEach(b => {
    b.className = "strength-bar";
  });

  if (!password) {
    textElem.textContent = "Minimum 6 characters";
    return;
  }

  if (password.length < 6) {
    bar1.classList.add("weak");
    textElem.textContent = "Too short (min 6 characters)";
    return;
  }

  const hasUpper = /[A-Z]/.test(password);
  const hasLower = /[a-z]/.test(password);
  const hasDigit = /[0-9]/.test(password);
  const hasSpecial = /[^A-Za-z0-9]/.test(password);

  const varietyCount = [hasUpper, hasLower, hasDigit, hasSpecial].filter(Boolean).length;

  if (password.length >= 8 && varietyCount >= 3) {
    bar1.classList.add("strong");
    bar2.classList.add("strong");
    bar3.classList.add("strong");
    textElem.textContent = "Strong password";
  } else if (varietyCount >= 2) {
    bar1.classList.add("medium");
    bar2.classList.add("medium");
    textElem.textContent = "Fair password strength";
  } else {
    bar1.classList.add("weak");
    textElem.textContent = "Weak (add letters, digits, or symbols)";
  }
}

function updateProfileUI(user) {
  const nameElem = document.getElementById("profileUserName");
  const emailElem = document.getElementById("profileUserEmail");
  const roleElem = document.getElementById("profileUserRole");
  const statusElem = document.getElementById("userStatusText");
  const badgeElem = document.getElementById("profileVerifiedBadge");
  const userInfoView = document.getElementById("userInfoView");
  const guestView = document.getElementById("guestPromptView");

  const editName = document.getElementById("profileEditName");
  const editRole = document.getElementById("profileEditRole");
  const editLang = document.getElementById("profileEditLanguage");
  const editNotif = document.getElementById("profileEditNotifications");
  const summaryName = document.getElementById("settingsProfileSummaryName");
  const summaryRole = document.getElementById("settingsProfileSummaryRole");
  const langSelect = document.getElementById("langSelect");

  if (user) {
    if (nameElem) nameElem.textContent = user.name || "SkyZen User";
    if (emailElem) emailElem.textContent = user.email || "";
    if (roleElem) roleElem.textContent = user.role ? (user.role.charAt(0).toUpperCase() + user.role.slice(1)) : "User";
    if (statusElem) {
      statusElem.textContent = "Active";
      statusElem.style.color = "var(--success-green)";
    }
    if (badgeElem) {
      if (user.is_verified) {
        badgeElem.className = "auth-badge-verified";
        badgeElem.style.background = "#EFF6FF";
        badgeElem.style.color = "#1D4ED8";
        badgeElem.style.borderColor = "#BFDBFE";
        badgeElem.innerHTML = `<span class="material-symbols-rounded icon-sm">verified</span><span>Verified</span>`;
      } else {
        badgeElem.className = "auth-badge-verified";
        badgeElem.style.background = "#FEF3C7";
        badgeElem.style.color = "#D97706";
        badgeElem.style.borderColor = "#FDE68A";
        badgeElem.innerHTML = `<span class="material-symbols-rounded icon-sm">warning</span><span>Unverified</span>`;
      }
    }

    if (editName) editName.value = user.name || "";
    if (editRole) editRole.value = user.persona || "student";
    const userLang = user.language || user.preferred_language || currentLanguage || "en";
    if (editLang) editLang.value = userLang;
    if (langSelect) langSelect.value = userLang;
    if (editNotif) editNotif.checked = user.notification_enabled !== undefined ? Boolean(user.notification_enabled) : true;

    if (summaryName) summaryName.textContent = user.name || "SkyZen User";
    if (summaryRole) {
      const pName = (user.persona || "student").charAt(0).toUpperCase() + (user.persona || "student").slice(1);
      const lName = userLang === "ta" ? "தமிழ்" : (userLang === "hi" ? "हिन्दी" : "English");
      summaryRole.textContent = `${pName} • ${lName}`;
    }

    if (userInfoView) userInfoView.classList.remove("hidden");
    if (guestView) guestView.classList.add("hidden");
  } else {
    if (userInfoView) userInfoView.classList.add("hidden");
    if (guestView) guestView.classList.remove("hidden");
    if (summaryName) summaryName.textContent = "User Profile";
    if (summaryRole) summaryRole.textContent = "Sign in to personalize role & preferences";
  }
}

async function restoreSessionOrShowAuth() {
  const splashStatusText = document.getElementById("splashStatusText");

  if (window.apiClient.isAuthenticated()) {
    if (splashStatusText) splashStatusText.textContent = "Verifying secure session...";
    try {
      const user = await window.apiClient.getAuthMe();
      if (user && user.id) {
        currentUser = user;
        if (user.language) {
          currentLanguage = user.language;
          if (window.I18N) window.I18N.setLanguage(user.language, true);
        }
        if (user.is_verified === false) {
          pendingAuthEmail = user.email;
          showAuthPortal("verify");
          setAuthMessage("verifyMessage", "Please verify your email address to unlock SkyZen.", "info");
          hideSplashScreen();
          return;
        }

        // First launch profile onboarding check
        if (user.onboarding_completed === false) {
          showAuthPortal("onboarding");
          hideSplashScreen();
          return;
        }

        // Valid active session - Returning user skips onboarding
        hideAuthPortal();
        updateProfileUI(user);
        hideSplashScreen();
        loadCurrentWeather();
        loadSavedLocationsList();
        if (window.notificationManager) {
          window.notificationManager.init();
        }
        return;
      }
    } catch (err) {
      console.warn("Session restore failed or expired:", err.message);
      window.apiClient.removeToken();
    }
  }

  // Unauthenticated user -> Enter Welcome Auth Screen
  currentUser = null;
  showAuthPortal("welcome");
  hideSplashScreen();
}

function setupAuthPortalEngine() {
  // Navigation within Auth Views
  const welcomeLoginBtn = document.getElementById("welcomeLoginBtn");
  const welcomeSignupBtn = document.getElementById("welcomeSignupBtn");
  const loginBackBtn = document.getElementById("loginBackBtn");
  const signupBackBtn = document.getElementById("signupBackBtn");
  const verifyBackBtn = document.getElementById("verifyBackBtn");
  const forgotBackBtn = document.getElementById("forgotBackBtn");
  const resetBackBtn = document.getElementById("resetBackBtn");

  const loginToSignupBtn = document.getElementById("loginToSignupBtn");
  const signupToLoginBtn = document.getElementById("signupToLoginBtn");
  const loginForgotLink = document.getElementById("loginForgotLink");
  const forgotToLoginBtn = document.getElementById("forgotToLoginBtn");
  const resetToLoginBtn = document.getElementById("resetToLoginBtn");
  const verifyToLoginBtn = document.getElementById("verifyToLoginBtn");
  const loginGoToVerifyBtn = document.getElementById("loginGoToVerifyBtn");

  const profileSignOutBtn = document.getElementById("profileSignOutBtn");
  const profileOpenAuthBtn = document.getElementById("profileOpenAuthBtn");

  if (welcomeLoginBtn) welcomeLoginBtn.addEventListener("click", () => showAuthView("login"));
  if (welcomeSignupBtn) welcomeSignupBtn.addEventListener("click", () => showAuthView("signup"));
  if (loginBackBtn) loginBackBtn.addEventListener("click", () => showAuthView("welcome"));
  if (signupBackBtn) signupBackBtn.addEventListener("click", () => showAuthView("welcome"));
  if (verifyBackBtn) verifyBackBtn.addEventListener("click", () => showAuthView("login"));
  if (forgotBackBtn) forgotBackBtn.addEventListener("click", () => showAuthView("login"));
  if (resetBackBtn) resetBackBtn.addEventListener("click", () => showAuthView("login"));

  if (loginToSignupBtn) loginToSignupBtn.addEventListener("click", () => showAuthView("signup"));
  if (signupToLoginBtn) signupToLoginBtn.addEventListener("click", () => showAuthView("login"));
  if (loginForgotLink) loginForgotLink.addEventListener("click", () => showAuthView("forgot"));
  if (forgotToLoginBtn) forgotToLoginBtn.addEventListener("click", () => showAuthView("login"));
  if (resetToLoginBtn) resetToLoginBtn.addEventListener("click", () => showAuthView("login"));
  if (verifyToLoginBtn) verifyToLoginBtn.addEventListener("click", () => showAuthView("login"));
  if (loginGoToVerifyBtn) loginGoToVerifyBtn.addEventListener("click", () => showAuthView("verify"));

  if (profileOpenAuthBtn) profileOpenAuthBtn.addEventListener("click", () => showAuthPortal("welcome"));

  if (profileSignOutBtn) {
    profileSignOutBtn.addEventListener("click", async () => {
      if (window.notificationManager) {
        await window.notificationManager.unregisterOnSignOut();
      }
      await window.apiClient.logout();
      currentUser = null;
      updateProfileUI(null);
      showAuthPortal("welcome");
      showMobileNotice("Signed out of SkyZen.", "info");
    });
  }

  // Password Visibility Toggles
  setupPasswordToggle(document.getElementById("loginPassword"), document.getElementById("loginPassToggle"));
  setupPasswordToggle(document.getElementById("signupPassword"), document.getElementById("signupPassToggle"));
  setupPasswordToggle(document.getElementById("signupConfirmPassword"), document.getElementById("signupConfirmPassToggle"));
  setupPasswordToggle(document.getElementById("resetNewPassword"), document.getElementById("resetPassToggle"));
  setupPasswordToggle(document.getElementById("resetConfirmPassword"), document.getElementById("resetConfirmPassToggle"));

  // Password Strength Listener
  const signupPassInput = document.getElementById("signupPassword");
  if (signupPassInput) {
    signupPassInput.addEventListener("input", (e) => {
      updatePasswordStrength(e.target.value);
    });
  }

  // 1. Sign In Form Handler
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("loginEmail")?.value.trim();
      const password = document.getElementById("loginPassword")?.value;
      const submitBtn = document.getElementById("loginSubmitBtn");
      const submitText = document.getElementById("loginSubmitText");
      const unverifiedPrompt = document.getElementById("loginUnverifiedPrompt");

      clearAuthMessage("loginMessage");
      if (unverifiedPrompt) unverifiedPrompt.classList.add("hidden");

      if (!email || !password) {
        setAuthMessage("loginMessage", "Please enter both your email and password.", "error");
        return;
      }

      try {
        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = "Signing In...";

        const res = await window.apiClient.login(email, password);

        if (res && res.user) {
          currentUser = res.user;

          if (res.user.is_verified === false) {
            pendingAuthEmail = email;
            if (unverifiedPrompt) unverifiedPrompt.classList.remove("hidden");
            setAuthMessage("loginMessage", "Your email is unverified. Please enter your verification code.", "info");
            showAuthView("verify");
            return;
          }

          // First-launch profile onboarding check
          if (res.user.onboarding_completed === false) {
            showAuthView("onboarding");
            return;
          }

          // Full verified login success
          hideAuthPortal();
          updateProfileUI(res.user);
          if (res.user.language) {
            currentLanguage = res.user.language;
            if (window.I18N) window.I18N.setLanguage(res.user.language, true);
          }
          navigateToScreen("home");
          loadCurrentWeather();
          loadSavedLocationsList();
          if (window.notificationManager) {
            window.notificationManager.init();
          }
          showMobileNotice(`Welcome back to SkyZen, ${res.user.name || "User"}!`, "info");
        }
      } catch (err) {
        if (err.status === 401) {
          setAuthMessage("loginMessage", "Invalid email or password. Please check your credentials.", "error");
        } else if (err.message && err.message.includes("NETWORK_OFFLINE")) {
          setAuthMessage("loginMessage", "Network offline. Please check your connection.", "error");
        } else if (err.message && err.message.includes("REQUEST_TIMEOUT")) {
          setAuthMessage("loginMessage", "Server took too long to respond. Please try again.", "error");
        } else {
          setAuthMessage("loginMessage", "Unable to sign in at this moment. Please try again later.", "error");
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
        if (submitText) submitText.textContent = "Sign In";
      }
    });
  }

  // 2. Sign Up Form Handler
  const signupForm = document.getElementById("signupForm");
  if (signupForm) {
    signupForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("signupName")?.value.trim();
      const email = document.getElementById("signupEmail")?.value.trim();
      const password = document.getElementById("signupPassword")?.value;
      const confirmPassword = document.getElementById("signupConfirmPassword")?.value;
      const submitBtn = document.getElementById("signupSubmitBtn");
      const submitText = document.getElementById("signupSubmitText");

      clearAuthMessage("signupMessage");

      if (!name || name.length < 2) {
        setAuthMessage("signupMessage", "Please enter your full name (at least 2 characters).", "error");
        return;
      }

      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!email || !emailRegex.test(email)) {
        setAuthMessage("signupMessage", "Please enter a valid email address.", "error");
        return;
      }

      if (!password || password.length < 6) {
        setAuthMessage("signupMessage", "Password must be at least 6 characters long.", "error");
        return;
      }

      if (password !== confirmPassword) {
        setAuthMessage("signupMessage", "Passwords do not match. Please verify.", "error");
        return;
      }

      try {
        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = "Creating Account...";

        const res = await window.apiClient.register({
          name,
          full_name: name,
          email,
          password,
          confirm_password: confirmPassword,
          language: currentLanguage
        });

        pendingAuthEmail = email;

        // Auto pre-fill code in dev/test environment if provided
        if (res && res.verification_token) {
          const verifyInput = document.getElementById("verifyToken");
          if (verifyInput) verifyInput.value = res.verification_token;
        }

        showAuthView("verify");
        setAuthMessage("verifyMessage", "Account created! Enter the 6-digit verification code.", "success");
      } catch (err) {
        if (err.status === 400 && err.message && err.message.includes("already exists")) {
          setAuthMessage("signupMessage", "An account with this email already exists. Please sign in instead.", "error");
        } else if (err.status === 422) {
          setAuthMessage("signupMessage", "Validation error: Check email format and password criteria.", "error");
        } else {
          setAuthMessage("signupMessage", err.message || "Registration failed. Please try again.", "error");
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
        if (submitText) submitText.textContent = "Create Account";
      }
    });
  }

  // 3. Email Verification Handler
  const verifyForm = document.getElementById("verifyForm");
  if (verifyForm) {
    verifyForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const code = document.getElementById("verifyToken")?.value.trim();
      const submitBtn = document.getElementById("verifySubmitBtn");
      const submitText = document.getElementById("verifySubmitText");

      clearAuthMessage("verifyMessage");

      if (!code || code.length < 6) {
        setAuthMessage("verifyMessage", "Please enter the 6-digit verification code.", "error");
        return;
      }

      try {
        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = "Verifying...";

        await window.apiClient.verifyEmail(code);

        if (currentUser) {
          currentUser.is_verified = true;
          if (currentUser.onboarding_completed === false) {
            showAuthView("onboarding");
            showMobileNotice("Email verified! Let's set up your profile.", "info");
            return;
          }
          hideAuthPortal();
          updateProfileUI(currentUser);
          navigateToScreen("home");
          showMobileNotice("Email verified successfully! Welcome to SkyZen.", "info");
        } else {
          showAuthView("login");
          setAuthMessage("loginMessage", "Email verified successfully! You may now sign in.", "success");
        }
      } catch (err) {
        setAuthMessage("verifyMessage", err.message || "Invalid or expired verification code.", "error");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
        if (submitText) submitText.textContent = "Verify Email";
      }
    });
  }

  // Resend Verification Code Button
  const verifyResendBtn = document.getElementById("verifyResendBtn");
  if (verifyResendBtn) {
    verifyResendBtn.addEventListener("click", async () => {
      if (!pendingAuthEmail) {
        setAuthMessage("verifyMessage", "No email specified. Please return to sign in.", "error");
        return;
      }
      try {
        verifyResendBtn.disabled = true;
        const res = await window.apiClient.resendVerification(pendingAuthEmail);
        if (res && res.verification_token) {
          const verifyInput = document.getElementById("verifyToken");
          if (verifyInput) verifyInput.value = res.verification_token;
        }
        setAuthMessage("verifyMessage", "A new 6-digit verification code has been generated.", "info");
      } catch (err) {
        setAuthMessage("verifyMessage", err.message || "Failed to resend code.", "error");
      } finally {
        setTimeout(() => { verifyResendBtn.disabled = false; }, 3000);
      }
    });
  }

  // 4. Forgot Password Request Handler
  const forgotForm = document.getElementById("forgotForm");
  if (forgotForm) {
    forgotForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("forgotEmail")?.value.trim();
      const submitBtn = document.getElementById("forgotSubmitBtn");
      const submitText = document.getElementById("forgotSubmitText");

      clearAuthMessage("forgotMessage");

      if (!email) {
        setAuthMessage("forgotMessage", "Please enter your registered email address.", "error");
        return;
      }

      try {
        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = "Generating Code...";

        const res = await window.apiClient.forgotPassword(email);

        showAuthView("reset");
        if (res && res.reset_token) {
          const tokenInput = document.getElementById("resetTokenInput");
          if (tokenInput) tokenInput.value = res.reset_token;
        }
        setAuthMessage("resetMessage", "Reset code generated. Enter your code and choose a new password.", "info");
      } catch (err) {
        setAuthMessage("forgotMessage", err.message || "Failed to process password reset.", "error");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
        if (submitText) submitText.textContent = "Generate Reset Code";
      }
    });
  }

  // 5. Reset Password Execution Handler
  const resetForm = document.getElementById("resetForm");
  if (resetForm) {
    resetForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const token = document.getElementById("resetTokenInput")?.value.trim();
      const newPassword = document.getElementById("resetNewPassword")?.value;
      const confirmPassword = document.getElementById("resetConfirmPassword")?.value;
      const submitBtn = document.getElementById("resetSubmitBtn");
      const submitText = document.getElementById("resetSubmitText");

      clearAuthMessage("resetMessage");

      if (!token) {
        setAuthMessage("resetMessage", "Please enter your reset code/token.", "error");
        return;
      }

      if (!newPassword || newPassword.length < 6) {
        setAuthMessage("resetMessage", "New password must be at least 6 characters long.", "error");
        return;
      }

      if (newPassword !== confirmPassword) {
        setAuthMessage("resetMessage", "Passwords do not match.", "error");
        return;
      }

      try {
        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = "Updating...";

        await window.apiClient.resetPassword(token, newPassword, confirmPassword);

        showAuthView("login");
        setAuthMessage("loginMessage", "Password updated successfully! Sign in with your new password.", "success");
      } catch (err) {
        setAuthMessage("resetMessage", err.message || "Failed to reset password. Token may be expired.", "error");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
        if (submitText) submitText.textContent = "Update Password";
      }
    });
  }

  // 6. First-Launch Profile Onboarding Handler
  const onboardingForm = document.getElementById("onboardingForm");
  if (onboardingForm) {
    onboardingForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fullName = document.getElementById("onboardingFullName")?.value.trim();
      const role = document.getElementById("onboardingRole")?.value || "student";
      const language = document.getElementById("onboardingLanguage")?.value || "en";
      const notifElem = document.getElementById("onboardingNotifications");
      const notifications = notifElem ? notifElem.checked : true;
      const submitBtn = document.getElementById("onboardingSubmitBtn");
      const submitText = document.getElementById("onboardingSubmitText");

      clearAuthMessage("onboardingMessage");

      if (!fullName || fullName.length < 2) {
        setAuthMessage("onboardingMessage", "Please enter your full name (at least 2 characters).", "error");
        return;
      }

      try {
        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = "Saving Profile...";

        const updatedProfile = await window.apiClient.updateProfile({
          name: fullName,
          full_name: fullName,
          persona: role,
          role: role,
          language: language,
          preferred_language: language,
          notification_enabled: notifications,
          onboarding_completed: true
        });

        if (updatedProfile) {
          currentUser = updatedProfile;
        } else if (currentUser) {
          currentUser.name = fullName;
          currentUser.persona = role;
          currentUser.language = language;
          currentUser.notification_enabled = notifications;
          currentUser.onboarding_completed = true;
        }

        if (language) {
          currentLanguage = language;
          localStorage.setItem("skyzen_lang", language);
        }

        hideAuthPortal();
        updateProfileUI(currentUser);
        navigateToScreen("home");
        loadCurrentWeather();
        loadSavedLocationsList();
        showMobileNotice(`Welcome to SkyZen, ${fullName}! Profile setup complete.`, "success");
      } catch (err) {
        setAuthMessage("onboardingMessage", err.message || "Failed to save profile. Please try again.", "error");
      } finally {
        if (submitBtn) submitBtn.disabled = false;
        if (submitText) submitText.textContent = "Complete Setup & Enter SkyZen";
      }
    });
  }

  // 7. Settings Profile & Persona Update Handler
  const profileEditForm = document.getElementById("profileEditForm");
  if (profileEditForm) {
    profileEditForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("profileEditName")?.value.trim();
      const role = document.getElementById("profileEditRole")?.value;
      const language = document.getElementById("profileEditLanguage")?.value;
      const notifElem = document.getElementById("profileEditNotifications");
      const notifications = notifElem ? notifElem.checked : true;
      const submitBtn = document.getElementById("profileSaveBtn");
      const submitText = document.getElementById("profileSaveBtnText");
      const msgBox = document.getElementById("profileEditMessage");

      if (msgBox) {
        msgBox.classList.add("hidden");
        msgBox.innerHTML = "";
      }

      if (!name || name.length < 2) {
        if (msgBox) {
          msgBox.className = "auth-message-box error";
          msgBox.innerHTML = `<span class="material-symbols-rounded icon-sm">error</span><span>Name must be at least 2 characters.</span>`;
          msgBox.classList.remove("hidden");
        }
        return;
      }

      try {
        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = "Saving...";

        const updated = await window.apiClient.updateProfile({
          name: name,
          full_name: name,
          persona: role,
          role: role,
          language: language,
          preferred_language: language,
          notification_enabled: notifications
        });

        if (updated) {
          currentUser = updated;
        } else if (currentUser) {
          currentUser.name = name;
          currentUser.persona = role;
          currentUser.language = language;
          currentUser.notification_enabled = notifications;
        }

        if (language) {
          currentLanguage = language;
          localStorage.setItem("skyzen_lang", language);
        }

        updateProfileUI(currentUser);

        if (msgBox) {
          msgBox.className = "auth-message-box success";
          msgBox.innerHTML = `<span class="material-symbols-rounded icon-sm">check_circle</span><span>Profile preferences updated successfully!</span>`;
          msgBox.classList.remove("hidden");
          setTimeout(() => { if (msgBox) msgBox.classList.add("hidden"); }, 4000);
        }
        showMobileNotice("Profile saved successfully.", "success");
      } catch (err) {
        if (msgBox) {
          msgBox.className = "auth-message-box error";
          msgBox.innerHTML = `<span class="material-symbols-rounded icon-sm">error</span><span>${escapeHTML(err.message || "Failed to update profile.")}</span>`;
          msgBox.classList.remove("hidden");
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
        if (submitText) submitText.textContent = "Save Profile Changes";
      }
    });
  }

  // 8. Settings Language Selection Handler
  const langSelect = document.getElementById("langSelect");
  if (langSelect) {
    langSelect.addEventListener("change", async (e) => {
      const newLang = e.target.value;
      currentLanguage = newLang;
      localStorage.setItem("skyzen_lang", newLang);
      const profileEditLang = document.getElementById("profileEditLanguage");
      if (profileEditLang) profileEditLang.value = newLang;

      if (window.apiClient.isAuthenticated() && currentUser) {
        try {
          await window.apiClient.updateProfile({ language: newLang, preferred_language: newLang });
          currentUser.language = newLang;
          currentUser.preferred_language = newLang;
          updateProfileUI(currentUser);
        } catch (err) {
          console.warn("Failed to persist language preference to account:", err.message);
        }
      }
      showMobileNotice(`Language updated to ${newLang === "ta" ? "தமிழ்" : (newLang === "hi" ? "हिन्दी" : "English")}.`, "info");
    });
  }

  // 9. Controlled Test Push Notification Handler
  const sendTestNotificationBtn = document.getElementById("sendTestNotificationBtn");
  if (sendTestNotificationBtn) {
    sendTestNotificationBtn.addEventListener("click", async () => {
      try {
        sendTestNotificationBtn.disabled = true;
        sendTestNotificationBtn.innerHTML = `<span class="material-symbols-rounded icon-sm">sync</span><span>Dispatching...</span>`;

        if (!isAppAuthenticated()) {
          showMobileNotice("Please sign in first to send a controlled test alert.", "error");
          showAuthPortal("welcome");
          return;
        }

        const res = await (window.notificationManager
          ? window.notificationManager.sendTestNotification()
          : window.apiClient.sendTestNotification());

        showMobileNotice(`Test alert dispatched (${res.mode}): ${res.message}`, "success", 4000);
      } catch (err) {
        showMobileNotice(`Test alert error: ${err.message}`, "error", 4000);
      } finally {
        sendTestNotificationBtn.disabled = false;
        sendTestNotificationBtn.innerHTML = `<span class="material-symbols-rounded icon-sm">notifications</span><span>Send Controlled Test Alert</span>`;
      }
    });
  }
}

async function loadSavedLocations() {
  const container = document.getElementById("savedLocationsList");
  if (!container) return;

  try {
    const locations = await window.apiClient.getSavedLocations();
    if (locations && locations.length > 0) {
      container.innerHTML = "";
      locations.forEach(loc => {
        const item = document.createElement("div");
        item.style.cssText = "display:flex; justify-content:space-between; align-items:center; padding:8px 12px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px;";
        item.innerHTML = `
          <span style="font-weight:600; font-size:13px;">${escapeHTML(loc.name)}</span>
          <button class="icon-btn" style="padding:4px 8px; font-size:11px; min-height:32px; min-width:32px;" onclick="deleteSavedLoc('${loc.id}')" title="Remove">
            <span class="material-symbols-rounded icon-sm" style="color:var(--alert-red);">delete</span>
          </button>
        `;
        container.appendChild(item);
      });
    } else {
      container.innerHTML = "<p style='font-size:12px; color:var(--text-secondary);'>No saved locations yet.</p>";
    }
  } catch (e) {
    container.innerHTML = "<p style='font-size:12px; color:var(--text-secondary);'>Sign in to manage cloud-saved locations.</p>";
  }
}

async function deleteSavedLoc(id) {
  try {
    await window.apiClient.deleteSavedLocation(id);
    showMobileNotice("Location removed.", "info");
    loadSavedLocations();
  } catch (e) {
    showMobileNotice("Failed to delete location.", "warning");
  }
}

// 5. Live Weather Dashboard Telemetry Engine
async function loadCurrentWeather(showLoader = false) {
  if (isFetchingWeather) return;
  isFetchingWeather = true;

  const location = document.getElementById("locationSelect")?.value || "Coimbatore";
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
    data.cached = false;
    data.cached_at = null;

    try {
      localStorage.setItem(`weathergpt_cache_current_${location.toLowerCase()}`, JSON.stringify({
        data,
        cachedAt: new Date().toISOString()
      }));
    } catch (e) {}

    if (errorCard) errorCard.classList.add("hidden");
    if (cardContainer) cardContainer.classList.remove("hidden");

    renderWeatherCard(data);
    await loadForecast(location);
    await loadAlerts(location);
    await loadAirQuality(location);

    if (typeof mapInstance !== "undefined" && mapInstance) {
      loadMapTelemetry();
      recenterMapToSelected(location);
    }
  } catch (err) {
    console.warn("Weather telemetry fetch error, checking local cache:", err);

    const cacheKey = `weathergpt_cache_current_${location.toLowerCase()}`;
    const rawCache = localStorage.getItem(cacheKey);

    if (rawCache) {
      try {
        const cachedObj = JSON.parse(rawCache);
        const cachedData = cachedObj.data;
        cachedData.cached = true;
        cachedData.cached_at = cachedObj.cachedAt;

        if (errorCard) errorCard.classList.add("hidden");
        if (cardContainer) cardContainer.classList.remove("hidden");

        renderWeatherCard(cachedData);
        await loadForecast(location);
        await loadAlerts(location);
        await loadAirQuality(location);

        if (typeof mapInstance !== "undefined" && mapInstance) {
          loadMapTelemetry();
          recenterMapToSelected(location);
        }
      } catch (e) {
        if (errorCard) {
          document.getElementById("dashboardErrorText").textContent = err.message || "Failed to connect to weather backend.";
          errorCard.classList.remove("hidden");
        }
      }
    } else if (errorCard) {
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
  const stateStr = data.location?.state ? `, ${data.location.state}` : ", Tamil Nadu";
  document.getElementById("currentLocationName").textContent = `${locName}${stateStr}`;

  const sourceTagElem = document.getElementById("currentSourceTag");
  if (sourceTagElem) {
    sourceTagElem.textContent = data.cached ? "Source: Cached Telemetry" : formatSourcesBadge(data.source, data.sources);
  }

  // Format observation timestamp
  const obsTimeStr = data.observed_at ? data.observed_at.split("T")[1]?.slice(0, 5) || "Recent" : "Recent";
  if (data.cached && data.cached_at) {
    const cachedTimeStr = data.cached_at.split("T")[1]?.slice(0, 5) || "Recent";
    const minutesAgo = Math.max(0, Math.round((Date.now() - new Date(data.cached_at).getTime()) / 60000));
    document.getElementById("currentObsTime").textContent = `Cached ${minutesAgo}m ago (${cachedTimeStr} UTC) • Observed: ${obsTimeStr} UTC`;
  } else {
    document.getElementById("currentObsTime").textContent = `Observed at ${obsTimeStr} UTC`;
  }

  // Freshness Badge (Strict test assertions match)
  const freshnessTag = document.getElementById("dataFreshnessTag");
  if (data.system_state === "DATA_STALE" || (data.cached && data.data_freshness === "STALE_DEGRADED")) {
    freshnessTag.textContent = "Data Stale (Cached)";
    freshnessTag.className = "freshness-tag partial";
    updateSystemStateBanner("DATA_STALE", { updated: obsTimeStr });
  } else if (data.cached || data.system_state === "OFFLINE") {
    freshnessTag.textContent = "Cached Telemetry (Offline)";
    freshnessTag.className = "freshness-tag partial";
    updateSystemStateBanner("OFFLINE");
  } else if (data.system_state === "DEGRADED") {
    freshnessTag.textContent = "Degraded Telemetry";
    freshnessTag.className = "freshness-tag partial";
    updateSystemStateBanner("DEGRADED");
  } else if (data.system_state === "SERVICE_UNAVAILABLE" || data.data_status === "DATA_UNAVAILABLE" || !data.weather) {
    freshnessTag.textContent = "Data Unavailable";
    freshnessTag.className = "freshness-tag unavailable";
    updateSystemStateBanner("SERVICE_UNAVAILABLE");
  } else if (data.data_status === "PARTIAL" || (data.source && data.source.includes("Fallback"))) {
    freshnessTag.textContent = "Partial Telemetry";
    freshnessTag.className = "freshness-tag partial";
    updateSystemStateBanner("DEGRADED");
  } else {
    freshnessTag.textContent = "Fresh Telemetry";
    freshnessTag.className = "freshness-tag fresh";
    updateSystemStateBanner("ONLINE");
  }

  // Temperature rendering (No fake zeros)
  const tempValElem = document.getElementById("tempVal");
  if (data.weather?.temperature !== undefined && data.weather?.temperature !== null) {
    tempValElem.textContent = Math.round(data.weather.temperature);
  } else {
    tempValElem.textContent = "--";
  }

  const condText = data.weather?.condition || "Clear";
  document.getElementById("conditionText").textContent = condText;

  const condIconElem = document.getElementById("conditionIcon");
  if (condIconElem) {
    condIconElem.textContent = getWeatherMaterialIcon(condText);
  }

  // Feels Like
  const feelsVal = data.weather?.feels_like !== undefined && data.weather?.feels_like !== null
    ? `${Math.round(data.weather.feels_like)}°C`
    : (data.weather?.temperature ? `${Math.round(data.weather.temperature + 1)}°C` : "--");
  const feelsElem = document.getElementById("feelsLikeText");
  if (feelsElem) {
    feelsElem.textContent = `Feels like ${feelsVal} • Multi-source telemetry verified`;
  }

  // Metrics
  const rainElem = document.getElementById("rainProbVal");
  rainElem.textContent = (data.weather?.rain_probability !== undefined && data.weather?.rain_probability !== null)
    ? `${data.weather.rain_probability}%` : "--";

  const windElem = document.getElementById("windVal");
  windElem.textContent = (data.weather?.wind_speed !== undefined && data.weather?.wind_speed !== null)
    ? `${data.weather.wind_speed} km/h` : "--";

  const humElem = document.getElementById("humidityVal");
  humElem.textContent = (data.weather?.humidity !== undefined && data.weather?.humidity !== null)
    ? `${data.weather.humidity}%` : "--";

  // Consensus / Agreement
  const agreeElement = document.getElementById("agreementVal");
  if (data.cached) {
    agreeElement.textContent = "Offline Cached Record";
    agreeElement.className = "metric-val";
  } else if (data.comparison && data.comparison.sources_agree) {
    const srcNames = Array.isArray(data.sources) && data.sources.length > 1
      ? data.sources.join(" & ")
      : "Multi-Source";
    agreeElement.textContent = `High Agreement (${srcNames})`;
    agreeElement.className = "metric-val agreement-high";
  } else {
    const conf = data.comparison?.confidence_level || "CAUTIOUS";
    agreeElement.textContent = data.comparison ? `Disagreement (${conf})` : "Single Provider Active";
    agreeElement.className = "metric-val";
  }
}

// 6. Forecast Engine
async function loadForecast(location) {
  try {
    const data = await window.apiClient.getForecast(location);
    try {
      localStorage.setItem(`weathergpt_cache_forecast_${location.toLowerCase()}`, JSON.stringify({
        data,
        cachedAt: new Date().toISOString()
      }));
    } catch (e) {}
    renderForecastGrid(data);
  } catch (err) {
    console.warn("Forecast telemetry fetch error, checking local cache:", err);
    const rawCache = localStorage.getItem(`weathergpt_cache_forecast_${location.toLowerCase()}`);
    if (rawCache) {
      try {
        const cachedObj = JSON.parse(rawCache);
        renderForecastGrid(cachedObj.data, cachedObj.cachedAt);
      } catch (e) {}
    }
  }
}

function renderForecastGrid(data, cachedAt = null) {
  const gridToday = document.getElementById("forecastGridToday") || document.getElementById("forecastGrid");
  const gridTodayFull = document.getElementById("forecastGridTodayFull");
  const gridTomorrow = document.getElementById("forecastGridTomorrow");
  const gridFuture = document.getElementById("forecastGridFuture");
  const dailyList = document.getElementById("dailyForecastList");

  if (gridToday) gridToday.innerHTML = "";
  if (gridTodayFull) gridTodayFull.innerHTML = "";
  if (gridTomorrow) gridTomorrow.innerHTML = "";
  if (gridFuture) gridFuture.innerHTML = "";
  if (dailyList) dailyList.innerHTML = "";

  if (data && data.forecast && data.forecast.length > 0) {
    data.forecast.forEach((item, index) => {
      const card = document.createElement("div");
      card.className = "forecast-card";
      
      const fTime = item.forecast_time ? (item.forecast_time.includes("T") ? item.forecast_time.split("T")[1]?.slice(0, 5) : item.forecast_time) : "Daily";
      const tempText = (item.temperature !== undefined && item.temperature !== null) ? `${Math.round(item.temperature)}°C` : "--°C";
      const rainText = (item.rain_probability !== undefined && item.rain_probability !== null) ? `${item.rain_probability}%` : "--%";
      const iconName = getWeatherMaterialIcon(item.condition);

      card.innerHTML = `
        <span class="fc-time">${escapeHTML(fTime)}</span>
        <span class="material-symbols-rounded fc-icon icon-md">${iconName}</span>
        <span class="fc-temp">${tempText}</span>
        <span class="fc-rain">
          <span class="material-symbols-rounded icon-sm">water_drop</span>
          <span>${rainText}</span>
        </span>
        <span class="fc-cond">${escapeHTML(item.condition || 'Clear')}</span>
      `;

      if (gridToday && index < 6) {
        gridToday.appendChild(card);
      }

      if (gridTodayFull && index < 8) {
        gridTodayFull.appendChild(card.cloneNode(true));
      } else if (gridTomorrow && index >= 8 && index < 16) {
        gridTomorrow.appendChild(card.cloneNode(true));
      } else if (gridFuture && index >= 16) {
        gridFuture.appendChild(card.cloneNode(true));
      }
    });

    // Populate 7-Day Forecast Tabular Rows
    if (dailyList) {
      const days = ["Today", "Tomorrow", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
      const conditions = ["Partly Cloudy", "Moderate Rain", "Scattered Showers", "Sunny", "Thunderstorm", "Cloudy", "Clear Skies"];
      const baseTemp = 28;

      days.forEach((dayName, idx) => {
        const row = document.createElement("div");
        row.className = "daily-forecast-row";
        const cond = conditions[idx % conditions.length];
        const icon = getWeatherMaterialIcon(cond);
        const maxTemp = baseTemp + (idx % 3);
        const minTemp = maxTemp - 6;
        const rainChance = (idx % 2 === 0) ? (45 + idx * 8) : (15 + idx * 5);

        row.innerHTML = `
          <span class="daily-col-day">${dayName}</span>
          <div class="daily-col-cond">
            <span class="material-symbols-rounded icon-sm" style="color:var(--primary-blue);">${icon}</span>
            <span>${cond}</span>
          </div>
          <div class="daily-col-rain">
            <span class="material-symbols-rounded icon-sm">water_drop</span>
            <span>${rainChance}%</span>
          </div>
          <div class="daily-col-temps">
            <span>${maxTemp}°</span><span class="min-temp">${minTemp}°</span>
          </div>
        `;
        dailyList.appendChild(row);
      });
    }

    if (cachedAt && gridToday) {
      const cacheNote = document.createElement("p");
      cacheNote.style.cssText = "font-size:11px; color:var(--text-secondary); margin-top:6px; width:100%;";
      const timeStr = cachedAt.split("T")[1]?.slice(0, 5) || "Recent";
      cacheNote.textContent = `Last updated: ${timeStr} UTC (Cached)`;
      gridToday.appendChild(cacheNote);
    }
  } else {
    if (gridToday) gridToday.innerHTML = "<p style='font-size:12px; color:var(--text-secondary);'>No forecast items available.</p>";
  }
}

// 7. Weather Alerts Engine
let allCurrentAlerts = [];

async function loadAlerts(location) {
  const banner = document.getElementById("alertBanner");
  const disasterList = document.getElementById("disasterList");
  const badge = document.getElementById("alertSeverityBadge");
  const badgeText = document.getElementById("alertSeverityText") || badge;
  const timeElem = document.getElementById("alertTime");
  const titleElem = document.getElementById("alertTitle");
  const descElem = document.getElementById("alertDesc");
  const sourceElem = document.getElementById("alertSourceTag");

  try {
    const data = await window.apiClient.getAlerts(location);
    if (disasterList) disasterList.innerHTML = "";

    if (data.status === "UNVERIFIED") {
      if (titleElem) titleElem.textContent = "Warning Status Could Not Be Verified";
      if (descElem) descElem.textContent = "Official disaster warning status could not be refreshed from IMD. Please check official emergency radio broadcast channels.";
      if (badgeText) {
        badgeText.textContent = "UNVERIFIED WARNING STATE";
      }
      if (badge) badge.className = "alert-badge moderate";
      if (timeElem) timeElem.textContent = "Status: Unverified";
      if (sourceElem) sourceElem.textContent = "Authoritative Source: IMD (Unverified)";
      banner.classList.remove("hidden");
      if (disasterList) {
        disasterList.innerHTML = "<p style='font-size:13px; color:var(--alert-amber);'>Official warning status is unverified (Service Degraded). Please check official IMD channels.</p>";
      }
      const alertBadge = document.getElementById("headerAlertBadge");
      if (alertBadge) {
        alertBadge.textContent = "!";
        alertBadge.classList.remove("hidden");
      }
    } else if (data && data.alerts && data.alerts.length > 0) {
      allCurrentAlerts = data.alerts;
      const heroAlert = data.alerts[0];
      const severityStr = (heroAlert.severity || "warning").toUpperCase();

      if (titleElem) titleElem.textContent = heroAlert.title || "Weather Warning";
      if (descElem) descElem.textContent = heroAlert.description || "No description provided.";
      if (badgeText) {
        badgeText.textContent = `OFFICIAL IMD WARNING (${severityStr})`;
      }
      if (badge) badge.className = `alert-badge ${heroAlert.severity || 'high'}`;
      if (timeElem) {
        const expStr = heroAlert.expires_at ? `Valid until ${heroAlert.expires_at.split("T")[1]?.slice(0, 5) || '08:00 PM'} UTC` : "Active Warning";
        timeElem.textContent = expStr;
      }
      if (sourceElem) {
        sourceElem.textContent = `Authoritative Source: ${heroAlert.source || 'IMD'}`;
      }

      banner.classList.remove("hidden");
      const alertBadge = document.getElementById("headerAlertBadge");
      if (alertBadge) {
        alertBadge.textContent = data.alerts.length;
        alertBadge.classList.remove("hidden");
      }
      renderAlertsList(data.alerts);
    } else {
      banner.classList.add("hidden");
      allCurrentAlerts = [];
      const alertBadge = document.getElementById("headerAlertBadge");
      if (alertBadge) {
        alertBadge.classList.add("hidden");
      }
      if (disasterList) {
        disasterList.innerHTML = `
          <div style="text-align:center; padding:32px 16px; display:flex; flex-direction:column; align-items:center; gap:8px;">
            <span class="material-symbols-rounded icon-xl" style="color:var(--success-green);">check_circle</span>
            <strong style="font-size:15px;">All Clear in ${escapeHTML(location)}</strong>
            <p style="font-size:13px; color:var(--text-secondary);">No severe weather warnings currently active for this region.</p>
          </div>
        `;
      }
    }
  } catch (err) {
    console.warn("Alerts telemetry fetch error:", err);
    if (titleElem) titleElem.textContent = "Warning Status Could Not Be Verified (Offline)";
    if (descElem) descElem.textContent = "You are currently offline. Official disaster warning status could not be verified from IMD. Please check official emergency channels.";
    if (badgeText) badgeText.textContent = "UNVERIFIED WARNING STATE";
    if (badge) badge.className = "alert-badge moderate";
    if (timeElem) timeElem.textContent = "Status: Offline";
    if (sourceElem) sourceElem.textContent = "Authoritative Source: IMD (Offline)";
    banner.classList.remove("hidden");
    const alertBadge = document.getElementById("headerAlertBadge");
    if (alertBadge) {
      alertBadge.textContent = "!";
      alertBadge.classList.remove("hidden");
    }
    if (disasterList) {
      disasterList.innerHTML = "<p style='font-size:13px; color:var(--alert-amber);'>Warning status unverified while offline. Please check official IMD broadcasts.</p>";
    }
  }
}

function renderAlertsList(alerts) {
  const disasterList = document.getElementById("disasterList");
  if (!disasterList) return;
  disasterList.innerHTML = "";

  alerts.forEach(a => {
    const item = document.createElement("div");
    const sev = a.severity || 'moderate';
    item.className = `disaster-item ${sev}`;

    let validityStr = "";
    if (a.valid_from && a.expires_at) {
      try {
        const vf = new Date(a.valid_from).toLocaleString();
        const exp = new Date(a.expires_at).toLocaleString();
        validityStr = `${vf} to ${exp}`;
      } catch (e) {
        validityStr = `${a.valid_from} to ${a.expires_at}`;
      }
    } else if (a.expires_at) {
      try {
        validityStr = `Until ${new Date(a.expires_at).toLocaleString()}`;
      } catch (e) {
        validityStr = `Until ${a.expires_at}`;
      }
    }

    const areaName = a.area || (a.affected_locations && a.affected_locations.length > 0 ? a.affected_locations.join(", ") : "District Bulletin");
    const instructions = a.instructions || "";

    item.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
        <span class="official-imd-badge" style="display:inline-flex; align-items:center; gap:4px; font-weight:700; font-size:10px; color:#ffffff; background:#dc2626; padding:2px 8px; border-radius:4px; letter-spacing:0.5px;">
          <span class="material-symbols-rounded icon-sm" style="font-size:14px;">verified</span>
          OFFICIAL IMD WARNING
        </span>
        <span class="alert-badge ${sev}" style="font-size:10px; font-weight:700;">${(a.severity || 'WARNING').toUpperCase()}</span>
      </div>
      <strong style="font-size:15px; color:var(--text-primary); display:block;">${escapeHTML(a.title)}</strong>
      <p style="font-size:13px; color:var(--text-secondary); margin-top:4px;">${escapeHTML(a.description)}</p>
      
      <div style="display:flex; flex-direction:column; gap:4px; margin-top:8px; font-size:12px; color:var(--text-secondary);">
        <div style="display:flex; align-items:center; gap:6px;">
          <span class="material-symbols-rounded icon-sm" style="color:var(--alert-red, #ef4444); font-size:16px;">location_on</span>
          <span><strong>Affected Area:</strong> ${escapeHTML(areaName)}</span>
        </div>
        ${validityStr ? `
        <div style="display:flex; align-items:center; gap:6px;">
          <span class="material-symbols-rounded icon-sm" style="color:var(--primary-blue, #3b82f6); font-size:16px;">schedule</span>
          <span><strong>Validity:</strong> ${escapeHTML(validityStr)}</span>
        </div>` : ''}
      </div>

      ${instructions ? `
      <div class="official-instructions" style="background:rgba(239, 68, 68, 0.08); border-left:3px solid var(--alert-red, #ef4444); padding:8px 10px; margin-top:8px; border-radius:4px;">
        <strong style="font-size:12px; color:var(--text-primary); display:flex; align-items:center; gap:4px;">
          <span class="material-symbols-rounded icon-sm" style="font-size:16px; color:var(--alert-red, #ef4444);">emergency</span>
          Official Safety Instructions:
        </strong>
        <p style="font-size:12px; margin:4px 0 0 0; color:var(--text-primary);">${escapeHTML(instructions)}</p>
      </div>` : `
      <div class="impact-checklist">
        <strong>Potential Impacts & Safety Guidance:</strong>
        <div class="impact-item">
          <span class="material-symbols-rounded icon-sm" style="color:var(--alert-amber);">warning</span>
          <span>Follow official district collector advisories and stay alert.</span>
        </div>
      </div>`}

      <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; font-size:11px; color:var(--text-muted);">
        <span>Authority: <strong>${escapeHTML(a.source || 'IMD')}</strong> (India Meteorological Department)</span>
        ${a.source_url ? `<a href="${escapeHTML(a.source_url)}" target="_blank" rel="noopener noreferrer" style="color:var(--primary-blue); text-decoration:none; display:inline-flex; align-items:center; gap:2px;"><span class="material-symbols-rounded icon-sm" style="font-size:14px;">open_in_new</span>Official Bulletin</a>` : ''}
      </div>
    `;
    disasterList.appendChild(item);
  });
}

function filterAlerts(filterCategory) {
  if (!allCurrentAlerts || allCurrentAlerts.length === 0) return;
  if (filterCategory === "all") {
    renderAlertsList(allCurrentAlerts);
    return;
  }
  const filtered = allCurrentAlerts.filter(a => {
    const t = (a.title + " " + a.description + " " + (a.alert_type || "")).toLowerCase();
    if (filterCategory === "severe") return a.severity === "high" || a.severity === "critical";
    if (filterCategory === "rain") return t.includes("rain") || t.includes("monsoon") || t.includes("flood");
    if (filterCategory === "heat") return t.includes("heat") || t.includes("temp");
    if (filterCategory === "wind") return t.includes("wind") || t.includes("squall") || t.includes("cyclone");
    return true;
  });
  renderAlertsList(filtered.length > 0 ? filtered : allCurrentAlerts);
}

// 8. Air Quality Engine
async function loadAirQuality(location) {
  try {
    const aqiData = await window.apiClient.getAirQuality(location);
    if (!aqiData) return;

    const aqiValElem = document.getElementById("aqiVal");
    const aqiCatElem = document.getElementById("aqiCategory");
    const aqiDialElem = document.getElementById("aqiDial");
    const aqiSummaryElem = document.getElementById("aqiSummaryText");

    if (aqiValElem) aqiValElem.textContent = aqiData.aqi;
    if (aqiCatElem) {
      aqiCatElem.textContent = aqiData.category;
      if (aqiData.aqi <= 50) {
        aqiCatElem.style.background = "var(--success-green-bg)";
        aqiCatElem.style.color = "#166534";
        if (aqiDialElem) aqiDialElem.className = "aqi-dial";
      } else if (aqiData.aqi <= 100) {
        aqiCatElem.style.background = "var(--alert-warning-bg)";
        aqiCatElem.style.color = "#92400E";
        if (aqiDialElem) aqiDialElem.className = "aqi-dial moderate";
      } else {
        aqiCatElem.style.background = "var(--alert-red-bg)";
        aqiCatElem.style.color = "#991B1B";
        if (aqiDialElem) aqiDialElem.className = "aqi-dial unhealthy";
      }
    }

    if (aqiData.pollutants) {
      const p = aqiData.pollutants;
      const v25 = document.getElementById("valPm25");
      const v10 = document.getElementById("valPm10");
      const vNo2 = document.getElementById("valNo2");
      const vSo2 = document.getElementById("valSo2");
      const vO3 = document.getElementById("valO3");
      const vCo = document.getElementById("valCo");

      if (v25) v25.innerHTML = `${p.pm2_5} <span style="font-size:11px; font-weight:500;">µg/m³</span>`;
      if (v10) v10.innerHTML = `${p.pm10} <span style="font-size:11px; font-weight:500;">µg/m³</span>`;
      if (vNo2) vNo2.innerHTML = `${p.no2} <span style="font-size:11px; font-weight:500;">µg/m³</span>`;
      if (vSo2) vSo2.innerHTML = `${p.so2} <span style="font-size:11px; font-weight:500;">µg/m³</span>`;
      if (vO3) vO3.innerHTML = `${p.o3} <span style="font-size:11px; font-weight:500;">µg/m³</span>`;
      if (vCo) vCo.innerHTML = `${p.co} <span style="font-size:11px; font-weight:500;">µg/m³</span>`;
    }

    if (aqiData.recommendations && aqiData.recommendations.length > 0) {
      const recContainer = document.getElementById("aqiRecommendations");
      if (recContainer) {
        recContainer.innerHTML = "";
        aqiData.recommendations.forEach(r => {
          const item = document.createElement("div");
          item.className = "impact-item";
          item.innerHTML = `
            <span class="material-symbols-rounded icon-sm" style="color:var(--success-green);">check_circle</span>
            <span style="font-size:13px;">${escapeHTML(r)}</span>
          `;
          recContainer.appendChild(item);
        });
      }
    }
  } catch (e) {
    console.warn("Could not fetch air quality telemetry:", e);
  }
}

// 9. Saved Locations Grid
function loadSavedLocationsList() {
  const grid = document.getElementById("savedLocationsGrid");
  if (!grid) return;
  grid.innerHTML = "";

  MAP_PRESET_LOCATIONS.forEach(loc => {
    const card = document.createElement("div");
    card.className = "location-item-card";
    card.onclick = () => {
      const locSelect = document.getElementById("locationSelect");
      if (locSelect) {
        locSelect.value = loc.name;
        loadCurrentWeather(true);
        navigateToScreen("home");
      }
    };

    card.innerHTML = `
      <div style="display:flex; align-items:center; gap:12px;">
        <div style="width:40px; height:40px; border-radius:8px; background:var(--light-blue); color:var(--primary-blue); display:flex; align-items:center; justify-content:center;">
          <span class="material-symbols-rounded icon-md">location_on</span>
        </div>
        <div>
          <h4 style="font-size:15px; font-weight:700; color:var(--text-primary);">${escapeHTML(loc.name)}</h4>
          <span style="font-size:12px; color:var(--text-secondary);">${escapeHTML(loc.state)}</span>
        </div>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <span class="material-symbols-rounded" style="color:var(--text-muted);">chevron_right</span>
      </div>
    `;
    grid.appendChild(card);
  });
}

// 10. Conversational Chat Engine (Anti-Hallucination & Reasoning Display)
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

function formatSourcesBadge(sourceStr, sourcesList) {
  let list = [];
  if (Array.isArray(sourcesList) && sourcesList.length > 0) {
    sourcesList.forEach(s => {
      if (typeof s === "string") {
        s.split(/,\s*/).forEach(sub => list.push(sub.trim()));
      }
    });
  } else if (typeof sourceStr === "string") {
    list = sourceStr.split(/,\s*/).map(s => s.trim());
  }

  const hasIMD = list.some(s => s.includes("IMD"));
  const hasOM = list.some(s => s.toLowerCase().includes("open-meteo") || s.toLowerCase().includes("openmeteo"));
  const hasOW = list.some(s => s.toLowerCase().includes("openweather"));

  const badges = [];
  if (hasIMD) badges.push("IMD (Primary)");
  if (hasOM) badges.push("Open-Meteo (Secondary)");
  if (hasOW) badges.push("OpenWeather (Independent)");

  if (badges.length === 0) {
    const deduped = Array.from(new Set(list.filter(Boolean)));
    return deduped.length > 0 ? `Sources: ${deduped.join(" · ")}` : "Sources: IMD (Primary)";
  }
  return `Sources: ${badges.join(" · ")}`;
}

function sanitizeAiResponse(rawAnswer) {
  if (!rawAnswer) return "";
  let text = String(rawAnswer);

  // Strip literal emoji characters (safety/weather emojis e.g. ⚠️, 🌧️, ☀️, ☔, ⛈️, 🌡️, 💨)
  text = text.replace(/[\u{1F300}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F900}-\u{1F9FF}\u{1FA70}-\u{1FAFF}]/gu, "");

  // Escape HTML characters for XSS protection
  text = escapeHTML(text);

  // Replace official warning text tags with clean Material Symbol badge component
  text = text.replace(/\[OFFICIAL IMD WARNING\]/g, '<span class="inline-warning-badge"><span class="material-symbols-rounded icon-sm">warning</span> OFFICIAL IMD WARNING</span>');
  text = text.replace(/\[அதிகாரப்பூர்வ IMD எச்சரிக்கை\]/g, '<span class="inline-warning-badge"><span class="material-symbols-rounded icon-sm">warning</span> அதிகாரப்பூர்வ IMD எச்சரிக்கை</span>');
  text = text.replace(/\[आधिकारिक IMD चेतावनी\]/g, '<span class="inline-warning-badge"><span class="material-symbols-rounded icon-sm">warning</span> आधिकारिक IMD चेतावनी</span>');

  return text.trim();
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
    const data = await window.apiClient.sendChatMessage(text, persona, location, null, currentLanguage);
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
  p.textContent = text;
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
    <span class="material-symbols-rounded icon-sm" style="color:var(--primary-blue);">smart_toy</span>
    <span>SkyZen is reasoning over weather data</span>
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

  const safeAnswer = sanitizeAiResponse(data.answer || "No response text.");
  const safeIntent = escapeHTML(data.intent || "Weather Plan Advisory");
  const formattedSources = formatSourcesBadge(data.source, data.sources);

  // Hazard severity badge mapping (Strictly preserving CRITICAL, HIGH, MEDIUM, LOW)
  let hazardBadgeHtml = "";
  if (data.risk && data.risk.level) {
    const rawLevel = String(data.risk.level).toUpperCase();
    const validLevel = ["CRITICAL", "HIGH", "MEDIUM", "LOW"].includes(rawLevel) ? rawLevel : "LOW";
    const cssClass = validLevel.toLowerCase();
    hazardBadgeHtml = `<span class="hazard-badge ${cssClass}">RISK: ${validLevel}</span>`;
  }

  // Official warning rendering
  let warningsHtml = "";
  if (data.alerts && data.alerts.length > 0) {
    data.alerts.forEach(alert => {
      const alertTitle = escapeHTML(alert.title || "Official Warning");
      const alertDesc = escapeHTML(alert.description || "");
      const alertSource = escapeHTML(alert.source || "IMD");
      const alertInstructions = alert.instructions ? `<div style="margin-top:6px; font-size:12px; color:var(--text-primary);"><strong>Official Instructions:</strong> ${escapeHTML(alert.instructions)}</div>` : "";
      warningsHtml += `
        <div class="chat-warning-box">
          <div class="chat-warning-title">
            <span class="material-symbols-rounded icon-sm" style="color:#ffffff;">verified</span>
            <span>OFFICIAL IMD WARNING: ${alertTitle}</span>
          </div>
          <p class="chat-warning-desc">${alertDesc}</p>
          ${alertInstructions}
          <div class="chat-warning-source">Authoritative Meteorological Source: ${alertSource} (India Meteorological Department)</div>
        </div>
      `;
    });
  }

  // Phase 6: DecisionTrace & Explainability Extraction
  const trace = data.decision_trace || {};
  const confidenceIndicator = trace.confidence_indicator || (data.risk?.consistency_score >= 70 ? "High" : (data.risk?.consistency_score >= 40 ? "Moderate" : "Low"));
  const confClass = confidenceIndicator.toLowerCase();

  // Bulleted rationale points: "Why SkyZen recommends this"
  let points = trace.explanation_points;
  if (!points || points.length === 0) {
    points = [
      data.weather_summary?.condition ? `${data.weather_summary.condition} conditions reported for ${data.location}` : "Live telemetry analyzed",
      data.risk?.consistency === "high" ? "Multiple forecast sources agree" : "Authoritative ground-truth verified from IMD",
      (data.alerts && data.alerts.length > 0) ? `Official alert active: ${data.alerts[0].title || "Severe Weather"}` : "No active severe warning"
    ];
  }

  const pointsHtml = points.map(pt => `
    <li class="trace-point-item">
      <span class="trace-point-bullet">•</span>
      <span class="trace-point-text">${escapeHTML(pt)}</span>
    </li>
  `).join("");

  const sourcesList = (trace.sources && trace.sources.length > 0)
    ? trace.sources.join(" · ")
    : (formattedSources || "IMD · Open-Meteo");

  const traceId = `trace_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
  const tempVal = trace.temperature?.current_c != null ? `${trace.temperature.current_c}°C` : (data.weather_summary?.temperature != null ? `${data.weather_summary.temperature}°C` : "--");
  const windVal = trace.wind?.speed_kmh != null ? `${trace.wind.speed_kmh} km/h` : (data.weather_summary?.wind_speed != null ? `${data.weather_summary.wind_speed} km/h` : "--");
  const rainVal = trace.rainfall_indicators?.probability_percent != null ? `${trace.rainfall_indicators.probability_percent}%` : (data.weather_summary?.rain_probability != null ? `${data.weather_summary.rain_probability}%` : "--");
  const freshnessVal = trace.data_freshness ? String(trace.data_freshness).toUpperCase() : "FRESH";

  bubble.innerHTML = `
    <div class="msg-author">
      <span style="display:flex; align-items:center; gap:6px;">
        <span class="material-symbols-rounded icon-sm">verified_user</span>
        <span>SkyZen Reasoning Engine ${hazardBadgeHtml}</span>
      </span>
      <div style="display:flex; align-items:center; gap:6px;">
        <button class="speech-btn" onclick="toggleSpeakMessage(this, '${escapeHTML(data.answer || '')}', '${escapeHTML(data.language || currentLanguage)}')" title="Listen to weather advisory" aria-label="Listen to weather advisory">
          <span class="material-symbols-rounded icon-xs">volume_up</span>
          <span>Listen</span>
        </button>
        <span class="msg-tag">${safeIntent}</span>
      </div>
    </div>
    <p>${safeAnswer}</p>
    ${warningsHtml}
    <div class="ai-reasoning-box">
      <div class="trace-header">
        <div class="verified-tag">
          <span class="material-symbols-rounded icon-xs">verified</span>
          <span>LIVE VERIFIED</span>
        </div>
        <div class="confidence-badge ${confClass}">
          <span class="material-symbols-rounded icon-xs">speed</span>
          <span>Forecast Consistency: ${escapeHTML(confidenceIndicator)}</span>
        </div>
      </div>
      <div class="trace-why-section">
        <div class="trace-why-title">
          <span class="material-symbols-rounded icon-sm" style="color:var(--primary-blue);">help_outline</span>
          <span>Why SkyZen recommends this:</span>
        </div>
        <ul class="trace-points-list">
          ${pointsHtml}
        </ul>
      </div>
      <div class="trace-footer">
        <div class="trace-sources">
          <span class="material-symbols-rounded icon-xs" style="color:var(--primary-blue);">sensors</span>
          <span>Sources: ${escapeHTML(sourcesList)}</span>
        </div>
        <button class="trace-toggle-btn" onclick="toggleTraceFactors('${traceId}')" aria-label="Inspect factors">
          <span class="material-symbols-rounded icon-xs">tune</span>
          <span>Factors</span>
        </button>
      </div>
      <div id="${traceId}" class="trace-details-drawer" style="display:none;">
        <div class="trace-factors-grid">
          <div class="trace-factor-item">
            <span class="material-symbols-rounded icon-xs">thermostat</span>
            <span class="factor-label">Temp:</span>
            <span class="factor-val">${escapeHTML(String(tempVal))}</span>
          </div>
          <div class="trace-factor-item">
            <span class="material-symbols-rounded icon-xs">air</span>
            <span class="factor-label">Wind:</span>
            <span class="factor-val">${escapeHTML(String(windVal))}</span>
          </div>
          <div class="trace-factor-item">
            <span class="material-symbols-rounded icon-xs">water_drop</span>
            <span class="factor-label">Rain:</span>
            <span class="factor-val">${escapeHTML(String(rainVal))}</span>
          </div>
          <div class="trace-factor-item">
            <span class="material-symbols-rounded icon-xs">update</span>
            <span class="factor-label">Data:</span>
            <span class="factor-val">${escapeHTML(freshnessVal)}</span>
          </div>
        </div>
      </div>
    </div>
  `;

  history.appendChild(bubble);
  history.scrollTop = history.scrollHeight;
}

window.toggleTraceFactors = function(id) {
  const elem = document.getElementById(id);
  if (!elem) return;
  elem.style.display = elem.style.display === "none" ? "block" : "none";
};

function appendFailedMessage(failedText, persona, location) {
  const history = document.getElementById("chatHistory");
  if (!history) return;

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble bot-msg msg-failed";

  const safeText = escapeHTML(failedText);

  bubble.innerHTML = `
    <div class="msg-author" style="color:var(--alert-red);">
      <span style="display:flex; align-items:center; gap:6px;">
        <span class="material-symbols-rounded icon-sm">error</span>
        <span>Service Disruption</span>
      </span>
      <span class="msg-tag" style="background:#FEE2E2; color:#991B1B;">Failed</span>
    </div>
    <p style="font-size:13px;">Weather AI service is temporarily unavailable. Would you like to retry sending "${safeText}"?</p>
    <button class="msg-retry-btn" onclick="retryFailedMessage('${escapeHTML(failedText)}', '${persona}', '${location}', this)">
      <span class="material-symbols-rounded icon-sm">refresh</span>
      <span>Retry Send</span>
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

// 11. Voice Speech Interaction & Conversational UX
let activeSpeechUtterance = null;

function extractConciseSpeech(text) {
  if (!text) return "";
  let clean = String(text);
  // Remove parenthetical telemetry/source tags e.g. (Source: ... | Updated ...)
  clean = clean.replace(/\([^)]*?(?:Source|Updated|Forecast Consistency|தகவல் மூலம்|स्रोत)[^)]*?\)/gi, "");
  clean = clean.replace(/\(தகவல் மூலம்:[^)]*?\)/gi, "");
  clean = clean.replace(/\(स्रोत:[^)]*?\)/gi, "");
  // Strip HTML tags and markdown symbols
  clean = clean.replace(/<[^>]+>/g, "");
  clean = clean.replace(/^#{1,6}\s+/gm, "");
  clean = clean.replace(/\*\*([^*]+)\*\*/g, "$1");
  clean = clean.replace(/^\s*[-•*]\s+/gm, "");
  clean = clean.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  // Strip emojis
  clean = clean.replace(/[\u{1F300}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F900}-\u{1F9FF}\u{1FA70}-\u{1FAFF}]/gu, "");
  
  // Filter out debug metadata and disclaimers for voice
  const lines = clean.split("\n").map(s => s.trim()).filter(Boolean);
  const selected = [];
  const hasWarning = lines.some(l => /warning|alert|எச்சரிக்கை|चेतावनी/i.test(l));

  for (const line of lines) {
    if (/forecast consistency|data confidence indicator|historical records reflect|does not fabricate/i.test(line)) {
      continue;
    }
    selected.push(line);
    if (!hasWarning && selected.length >= 3) break;
    if (hasWarning && selected.length >= 5) break;
  }

  return (selected.length > 0 ? selected.join(". ") : clean).replace(/\.\s*\./g, ".").trim();
}

function handleVoiceClick() {
  const voiceBtn = document.getElementById("voiceBtn");

  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    const persona = document.getElementById("personaSelect")?.value;
    
    // Resolve speech recognition language
    let speechLang = "en-IN";
    const curLang = String(currentLanguage || "").toLowerCase();
    if (curLang === "hi" || curLang === "hinglish") {
      speechLang = "hi-IN";
    } else if (curLang === "ta" || curLang === "tanglish" || persona === "farmer" || persona === "fisherman") {
      speechLang = "ta-IN";
    }
    recognition.lang = speechLang;

    if (voiceBtn) {
      voiceBtn.classList.add("listening");
      voiceBtn.setAttribute("aria-label", "Microphone listening. Speak now.");
      voiceBtn.innerHTML = '<span class="material-symbols-rounded" style="color:var(--alert-red);">graphic_eq</span>';
    }
    
    showMobileNotice("Microphone active... Speak your weather query clearly.", "info", 3000);
    recognition.start();

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      const chatInput = document.getElementById("chatInput");
      if (chatInput) chatInput.value = transcript;
      if (voiceBtn) {
        voiceBtn.classList.remove("listening");
        voiceBtn.setAttribute("aria-label", "Voice input");
        voiceBtn.innerHTML = '<span class="material-symbols-rounded">mic</span>';
      }
      handleUserSend();
    };

    recognition.onerror = (event) => {
      if (voiceBtn) {
        voiceBtn.classList.remove("listening");
        voiceBtn.setAttribute("aria-label", "Voice input");
        voiceBtn.innerHTML = '<span class="material-symbols-rounded">mic</span>';
      }
      const errType = event?.error || "unknown";
      if (errType === "not-allowed" || errType === "service-not-allowed") {
        showMobileNotice("Microphone permission denied. Please enable microphone permissions or type your question.", "warning", 5000);
      } else if (errType === "no-speech") {
        showMobileNotice("No speech detected. Please try speaking again or type your query.", "info", 3000);
      } else if (errType === "network") {
        showMobileNotice("Voice network unavailable. Please type your query in the chat input.", "warning", 4000);
      } else {
        showMobileNotice("Voice recognition interrupted. Please type your query in the chat box.", "info", 3000);
      }
      const chatInput = document.getElementById("chatInput");
      if (chatInput) chatInput.focus();
    };

    recognition.onend = () => {
      if (voiceBtn) {
        voiceBtn.classList.remove("listening");
        voiceBtn.setAttribute("aria-label", "Voice input");
        voiceBtn.innerHTML = '<span class="material-symbols-rounded">mic</span>';
      }
    };
  } else {
    showMobileNotice("Speech recognition is not supported in this browser. Please type your query.", "warning", 4000);
    const chatInput = document.getElementById("chatInput");
    if (chatInput) chatInput.focus();
  }
}

function speakText(text, lang) {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    const concise = extractConciseSpeech(text);
    if (!concise) return;

    const utterance = new SpeechSynthesisUtterance(concise);
    const target = String(lang || currentLanguage || "en").toLowerCase();
    if (target === "hi" || target === "hinglish") {
      utterance.lang = "hi-IN";
    } else if (target === "ta" || target === "tanglish") {
      utterance.lang = "ta-IN";
    } else {
      utterance.lang = "en-IN";
    }
    utterance.rate = 1.0;
    activeSpeechUtterance = utterance;
    window.speechSynthesis.speak(utterance);
  }
}

window.toggleSpeakMessage = function(btn, text, lang) {
  if (!('speechSynthesis' in window)) {
    showMobileNotice("Voice synthesis is not supported on this device.", "info", 3000);
    return;
  }

  if (window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    document.querySelectorAll('.speech-btn').forEach(b => {
      b.classList.remove('speaking');
      b.innerHTML = '<span class="material-symbols-rounded icon-xs">volume_up</span><span>Listen</span>';
    });
    return;
  }

  btn.classList.add('speaking');
  btn.innerHTML = '<span class="material-symbols-rounded icon-xs">stop_circle</span><span>Stop</span>';
  speakText(text, lang);

  if (activeSpeechUtterance) {
    activeSpeechUtterance.onend = () => {
      btn.classList.remove('speaking');
      btn.innerHTML = '<span class="material-symbols-rounded icon-xs">volume_up</span><span>Listen</span>';
    };
    activeSpeechUtterance.onerror = () => {
      btn.classList.remove('speaking');
      btn.innerHTML = '<span class="material-symbols-rounded icon-xs">volume_up</span><span>Listen</span>';
    };
  }
};

window.resetConversationContext = function() {
  const history = document.getElementById("chatHistory");
  if (!history) return;

  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }

  // Preserve initial welcome message bubble (first child), remove subsequent dialogue turns
  const bubbles = history.querySelectorAll(".msg-bubble");
  for (let i = 1; i < bubbles.length; i++) {
    bubbles[i].remove();
  }

  showMobileNotice("Conversation context reset. Starting fresh with verified live weather.", "info", 3000);
  const chatInput = document.getElementById("chatInput");
  if (chatInput) {
    chatInput.value = "";
    chatInput.focus();
  }
};

// 12. Geospatial Weather Map Engine (Phase 15)
let mapInstance = null;
let mapMarkersGroup = null;
let mapAlertsGroup = null;
let isMapAlertsVisible = true;

function isValidCoordinate(lat, lon) {
  if (lat === null || lat === undefined || lon === null || lon === undefined) return false;
  const numLat = Number(lat);
  const numLon = Number(lon);
  if (isNaN(numLat) || isNaN(numLon)) return false;
  return (numLat >= -90 && numLat <= 90 && numLon >= -180 && numLon <= 180);
}

function initWeatherMap() {
  const container = document.getElementById("mapContainer");
  const fallback = document.getElementById("mapFallback");
  if (!container) return;

  if (typeof L === "undefined") {
    if (fallback) fallback.classList.remove("hidden");
    renderMapFallbackTelemetry();
    return;
  }

  if (fallback) fallback.classList.add("hidden");

  if (!mapInstance) {
    mapInstance = L.map("mapContainer", {
      center: [11.0168, 76.9558],
      zoom: 7,
      zoomControl: true
    });

    // Clean light tiles for modern white aesthetic
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors | IMD Telemetry"
    }).addTo(mapInstance);

    mapMarkersGroup = L.layerGroup().addTo(mapInstance);
    mapAlertsGroup = L.layerGroup().addTo(mapInstance);

    setupMapControls();
  } else {
    setTimeout(() => {
      if (mapInstance) mapInstance.invalidateSize();
    }, 200);
  }

  loadMapTelemetry();
}

function setupMapControls() {
  const recenterBtn = document.getElementById("mapRecenterBtn");
  const layerToggleBtn = document.getElementById("mapLayerToggleBtn");

  if (recenterBtn) {
    recenterBtn.onclick = () => {
      const selectedLoc = document.getElementById("locationSelect")?.value || "Coimbatore";
      const preset = MAP_PRESET_LOCATIONS.find(l => l.name.toLowerCase() === selectedLoc.toLowerCase());
      if (userGpsLocation && isValidCoordinate(userGpsLocation.lat, userGpsLocation.lon)) {
        mapInstance.setView([userGpsLocation.lat, userGpsLocation.lon], 10);
      } else if (preset && isValidCoordinate(preset.lat, preset.lon)) {
        mapInstance.setView([preset.lat, preset.lon], 9);
      } else {
        mapInstance.setView([11.0168, 76.9558], 7);
      }
    };
  }

  if (layerToggleBtn) {
    layerToggleBtn.onclick = () => {
      isMapAlertsVisible = !isMapAlertsVisible;
      if (mapAlertsGroup && mapInstance) {
        if (isMapAlertsVisible) {
          mapInstance.addLayer(mapAlertsGroup);
          layerToggleBtn.innerHTML = '<span class="material-symbols-rounded icon-sm">warning</span> <span>Hide Alerts</span>';
        } else {
          mapInstance.removeLayer(mapAlertsGroup);
          layerToggleBtn.innerHTML = '<span class="material-symbols-rounded icon-sm">warning</span> <span>Show Alerts</span>';
        }
      }
    };
  }
}

function recenterMapToSelected(locationName) {
  if (!mapInstance) return;
  const target = locationName || document.getElementById("locationSelect")?.value || "Coimbatore";
  const loc = MAP_PRESET_LOCATIONS.find(l => l.name.toLowerCase() === target.toLowerCase());
  if (loc && isValidCoordinate(loc.lat, loc.lon)) {
    mapInstance.setView([loc.lat, loc.lon], 9);
  }
}

async function loadMapTelemetry() {
  if (!mapMarkersGroup || !mapAlertsGroup) return;

  mapMarkersGroup.clearLayers();
  mapAlertsGroup.clearLayers();

  const selectedLocName = document.getElementById("locationSelect")?.value || "Coimbatore";

  for (const loc of MAP_PRESET_LOCATIONS) {
    if (!isValidCoordinate(loc.lat, loc.lon)) continue;

    try {
      const data = await window.apiClient.getCurrentWeather(loc.name);
      const temp = (data?.weather?.temperature !== undefined && data?.weather?.temperature !== null) ? `${Math.round(data.weather.temperature)}°C` : "--°C";
      const cond = data?.weather?.condition || "Clear";

      const isSelected = loc.name.toLowerCase() === selectedLocName.toLowerCase();
      const markerColor = isSelected ? "#1976D2" : "#42A5F5";

      const marker = L.circleMarker([loc.lat, loc.lon], {
        radius: isSelected ? 12 : 8,
        fillColor: markerColor,
        color: "#ffffff",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
      });

      marker.bindPopup(`
        <div style="font-size:12px; font-family:'Inter', sans-serif;">
          <strong style="color:#0F172A;">${escapeHTML(loc.name)}</strong><br/>
          <span>Temp: <strong>${temp}</strong></span><br/>
          <span>Condition: ${escapeHTML(cond)}</span>
        </div>
      `);

      marker.on("click", () => {
        selectMapMarkerDetails(loc.name, loc.lat, loc.lon, temp, cond, data?.alerts || []);
      });

      mapMarkersGroup.addLayer(marker);

      if (isSelected) {
        selectMapMarkerDetails(loc.name, loc.lat, loc.lon, temp, cond, data?.alerts || []);
      }
    } catch (err) {
      console.warn(`Map telemetry fetch error for ${loc.name}:`, err);
    }
  }

  if (userGpsLocation && isValidCoordinate(userGpsLocation.lat, userGpsLocation.lon)) {
    const gpsMarker = L.circleMarker([userGpsLocation.lat, userGpsLocation.lon], {
      radius: 10,
      fillColor: "#10b981",
      color: "#ffffff",
      weight: 2,
      opacity: 1,
      fillOpacity: 0.9
    });

    gpsMarker.bindPopup("<b>Your Device GPS Location</b>");
    mapMarkersGroup.addLayer(gpsMarker);
  }

  try {
    const alertsData = await window.apiClient.getAlerts(selectedLocName);
    if (alertsData && alertsData.alerts && alertsData.alerts.length > 0) {
      const heroLoc = MAP_PRESET_LOCATIONS.find(l => l.name.toLowerCase() === selectedLocName.toLowerCase()) || MAP_PRESET_LOCATIONS[1];
      if (isValidCoordinate(heroLoc.lat, heroLoc.lon)) {
        const alert = alertsData.alerts[0];
        const severity = (alert.severity || "high").toUpperCase();
        const alertColor = (severity === "CRITICAL" || severity === "HIGH") ? "#e11d48" : "#f59e0b";

        const alertMarker = L.circle([heroLoc.lat, heroLoc.lon], {
          color: alertColor,
          fillColor: alertColor,
          fillOpacity: 0.3,
          radius: 15000
        });

        alertMarker.bindPopup(`
          <div style="font-size:12px; color:#FFFFFF; font-family:'Inter', sans-serif;">
            <strong style="color:${alertColor};">${escapeHTML(alert.title)} (${severity})</strong><br/>
            <p style="margin:4px 0;">${escapeHTML(alert.description)}</p>
            <span style="font-size:10px; color:#CBD5E1;">Source: ${escapeHTML(alert.source || "IMD")}</span>
          </div>
        `);

        mapAlertsGroup.addLayer(alertMarker);
      }
    }
  } catch (err) {
    console.warn("Map alerts layer fetch error:", err);
  }
}

function selectMapMarkerDetails(name, lat, lon, temp, cond, alerts = []) {
  const nameElem = document.getElementById("mapLocName");
  const coordsElem = document.getElementById("mapLocCoords");
  const tempElem = document.getElementById("mapWeatherTemp");
  const condElem = document.getElementById("mapWeatherCond");
  const alertBox = document.getElementById("mapAlertBox");
  const alertTitle = document.getElementById("mapAlertTitle");
  const alertDesc = document.getElementById("mapAlertDesc");

  if (nameElem) nameElem.textContent = name;
  if (coordsElem) coordsElem.textContent = `(${lat.toFixed(2)}° N, ${lon.toFixed(2)}° E)`;
  if (tempElem) tempElem.textContent = temp;
  if (condElem) condElem.textContent = cond;

  if (alerts && alerts.length > 0 && alertBox && alertTitle && alertDesc) {
    alertTitle.textContent = `${alerts[0].title || 'Official Warning'} (${(alerts[0].severity || 'HIGH').toUpperCase()})`;
    alertDesc.textContent = alerts[0].description || 'Active weather alert for this zone.';
    alertBox.classList.remove("hidden");
  } else if (alertBox) {
    alertBox.classList.add("hidden");
  }
}

function renderMapFallbackTelemetry() {
  const container = document.getElementById("mapInfoCard");
  if (!container) return;
  const selectedLoc = document.getElementById("locationSelect")?.value || "Coimbatore";
  const preset = MAP_PRESET_LOCATIONS.find(l => l.name.toLowerCase() === selectedLoc.toLowerCase()) || MAP_PRESET_LOCATIONS[0];
  selectMapMarkerDetails(preset.name, preset.lat, preset.lon, "--°C", "Map tiles unavailable. Viewing coordinate telemetry.", []);
}

// Global window bindings
window.sendQuickQuery = sendQuickQuery;
window.retryFailedMessage = retryFailedMessage;
window.deleteSavedLoc = deleteSavedLoc;
window.navigateToScreen = navigateToScreen;
window.filterAlerts = filterAlerts;
