// WeatherGPT Frontend Client Application

const API_BASE = "/api/v1";

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

function initApp() {
  setupTabs();
  setupEventListeners();
  loadCurrentWeather();
}

function setupTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      tab.classList.add("active");
      const targetId = tab.getAttribute("data-tab");
      document.getElementById(targetId).classList.add("active");
    });
  });
}

function setupEventListeners() {
  document.getElementById("locationSelect").addEventListener("change", loadCurrentWeather);
  document.getElementById("personaSelect").addEventListener("change", loadCurrentWeather);

  document.getElementById("sendBtn").addEventListener("click", handleUserSend);
  document.getElementById("chatInput").addEventListener("keypress", (e) => {
    if (e.key === "Enter") handleUserSend();
  });

  document.getElementById("voiceBtn").addEventListener("click", handleVoiceClick);
}

async function loadCurrentWeather() {
  const location = document.getElementById("locationSelect").value;
  const persona = document.getElementById("personaSelect").value;

  try {
    const res = await fetch(`${API_BASE}/weather/current?location=${encodeURIComponent(location)}`);
    if (!res.ok) throw new Error("Failed to fetch weather");

    const data = await res.json();
    renderWeatherCard(data);
    loadForecast(location);
    loadAlerts(location);
  } catch (err) {
    console.error("Error loading weather data:", err);
  }
}

function renderWeatherCard(data) {
  document.getElementById("currentLocationName").textContent = `${data.location.name}, TN`;
  document.getElementById("currentSourceTag").textContent = `Authoritative Source: ${data.source}`;
  document.getElementById("currentObsTime").textContent = `Observed: ${data.observed_at.split("T")[1].slice(0, 5)} UTC`;

  document.getElementById("tempVal").textContent = Math.round(data.weather.temperature);
  document.getElementById("conditionText").textContent = data.weather.condition;
  document.getElementById("rainProbVal").textContent = `${data.weather.rain_probability}%`;
  document.getElementById("windVal").textContent = `${data.weather.wind_speed} km/h`;
  document.getElementById("humidityVal").textContent = `${data.weather.humidity}%`;

  const agreeElement = document.getElementById("agreementVal");
  if (data.comparison.sources_agree) {
    agreeElement.textContent = "High Agreement (IMD & Open-Meteo)";
    agreeElement.className = "metric-val agreement-high";
  } else {
    agreeElement.textContent = "Disagreement Detected";
    agreeElement.className = "metric-val";
  }
}

async function loadForecast(location) {
  try {
    const res = await fetch(`${API_BASE}/weather/forecast?location=${encodeURIComponent(location)}`);
    if (!res.ok) return;

    const data = await res.json();
    const grid = document.getElementById("forecastGrid");
    grid.innerHTML = "";

    data.forecast.forEach(item => {
      const card = document.createElement("div");
      card.className = "forecast-card";
      card.innerHTML = `
        <span class="fc-time">${item.forecast_time}</span>
        <span class="fc-temp">${item.temperature}°C</span>
        <span class="fc-rain">☔ ${item.rain_probability}%</span>
        <span class="fc-cond">${item.condition}</span>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    console.error("Forecast error:", err);
  }
}

async function loadAlerts(location) {
  try {
    const res = await fetch(`${API_BASE}/weather/alerts?location=${encodeURIComponent(location)}`);
    if (!res.ok) return;

    const data = await res.json();
    const banner = document.getElementById("alertBanner");
    const disasterList = document.getElementById("disasterList");
    disasterList.innerHTML = "";

    if (data.alerts && data.alerts.length > 0) {
      const heroAlert = data.alerts[0];
      document.getElementById("alertTitle").textContent = heroAlert.title;
      document.getElementById("alertDesc").textContent = heroAlert.description;
      banner.classList.remove("hidden");

      data.alerts.forEach(a => {
        const item = document.createElement("div");
        item.className = `disaster-item ${a.severity}`;
        item.innerHTML = `
          <strong>${a.title}</strong> (${a.source})
          <p style="font-size:12px; margin-top:4px;">${a.description}</p>
        `;
        disasterList.appendChild(item);
      });
    } else {
      banner.classList.add("hidden");
      disasterList.innerHTML = "<p style='font-size:13px; color:#94a3b8;'>No active disaster warnings for this location.</p>";
    }
  } catch (err) {
    console.error("Alerts error:", err);
  }
}

function sendQuickQuery(queryText) {
  document.getElementById("chatInput").value = queryText;
  handleUserSend();
}

async function handleUserSend() {
  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  if (!text) return;

  const location = document.getElementById("locationSelect").value;
  const persona = document.getElementById("personaSelect").value;

  appendMessage("user", text);
  input.value = "";

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        persona: persona,
        location: { name: location }
      })
    });

    if (!res.ok) throw new Error("Chat request failed");
    const data = await res.json();
    appendMessage("bot", data.answer, data.intent, data.risk.level);

    // Speak response if Web Speech API available
    speakText(data.answer);
  } catch (err) {
    appendMessage("bot", "I apologize, weather services are temporarily unavailable. Please try again shortly.");
  }
}

function appendMessage(sender, text, intent = null, risk = null) {
  const history = document.getElementById("chatHistory");
  const bubble = document.createElement("div");
  bubble.className = `msg-bubble ${sender}-msg`;

  if (sender === "bot") {
    const riskTag = risk ? ` • Risk: ${risk.toUpperCase()}` : '';
    bubble.innerHTML = `
      <div class="msg-author">
        <span>🌤️ WeatherGPT Engine</span>
        <span class="msg-tag">${intent || 'Response'}${riskTag}</span>
      </div>
      <p>${text}</p>
    `;
  } else {
    bubble.innerHTML = `<p>${text}</p>`;
  }

  history.appendChild(bubble);
  history.scrollTop = history.scrollHeight;
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
    // Fallback simulation for unsupported browsers
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
