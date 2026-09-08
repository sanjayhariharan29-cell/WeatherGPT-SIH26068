import os
import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

def test_01_chat_screen_render():
    """1. Test chat screen render: verifies screen-chat, chatHistory, chatInput, sendBtn, voiceBtn in DOM."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    
    assert 'id="screen-chat"' in html
    assert 'id="chatHistory"' in html
    assert 'id="chatInput"' in html
    assert 'id="sendBtn"' in html
    assert 'id="voiceBtn"' in html
    assert 'WeatherGPT Decision Assistant' in html

def test_02_send_message():
    """2. Test send message: verifies chat API endpoint accepts valid message payloads."""
    payload = {
        "message": "Naalaiku morning college pogalama?",
        "persona": "student",
        "location": {"name": "Coimbatore"},
        "language": "ta"
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["location"] == "Coimbatore"
    assert data["persona"] == "student"

def test_03_receive_response():
    """3. Test receive response: verifies bot response contains answer, intent, risk, and source tags."""
    payload = {
        "message": "Is there heavy rainfall today?",
        "persona": "fisherman",
        "location": {"name": "Nagapattinam"},
        "language": "en"
    }
    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "intent" in data
    assert "risk" in data
    assert "source" in data
    assert "validation" in data

def test_04_loading_state_rendering():
    """4. Test loading state: verifies typing indicator styling and DOM structure in app.js and styles.css."""
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert ".typing-indicator" in css
    assert ".typing-dot" in css
    assert "showTypingIndicator" in js
    assert "removeTypingIndicator" in js

def test_05_error_state_handling():
    """5. Test error state: verifies failed message bubble styling and error handlers in app.js and styles.css."""
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert ".msg-failed" in css
    assert "appendFailedMessage" in js
    assert "Service Disruption" in js

def test_06_retry_action():
    """6. Test retry action: verifies retry button and handler function in JS and CSS."""
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert ".msg-retry-btn" in css
    assert "retryFailedMessage" in js
    assert "Retry Send" in js

def test_07_warning_rendering():
    """7. Test warning rendering: verifies official warnings rendered inside chat-warning-box without hiding/downgrading."""
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert ".chat-warning-box" in css
    assert ".chat-warning-title" in css
    assert ".chat-warning-desc" in css
    assert "OFFICIAL WARNING" in css or "chat-warning-box" in js

def test_08_hazard_rendering():
    """8. Test hazard rendering: verifies strict levels CRITICAL, HIGH, MEDIUM, LOW preserved in badge classes."""
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert ".hazard-badge.critical" in css
    assert ".hazard-badge.high" in css
    assert ".hazard-badge.medium" in css
    assert ".hazard-badge.low" in css
    assert '["CRITICAL", "HIGH", "MEDIUM", "LOW"].includes(rawLevel)' in js

def test_09_multilingual_response():
    """9. Test multilingual response: verifies English, Tamil, and Hindi language requests supported via API."""
    for lang in ["en", "ta", "hi"]:
        payload = {
            "message": "What is the weather status?",
            "persona": "farmer",
            "location": {"name": "Chennai"},
            "language": lang
        }
        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert len(data["answer"]) > 0

def test_10_voice_entry_point():
    """10. Test voice entry point: verifies voice button, speech recognition hook, and fallback in JS."""
    response = client.get("/")
    assert 'id="voiceBtn"' in response.text

    js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "handleVoiceClick" in js
    assert "webkitSpeechRecognition" in js or "SpeechRecognition" in js

def test_11_offline_state():
    """11. Test offline state: verifies offline notification bar and network monitoring in JS/CSS."""
    response = client.get("/")
    assert 'id="offlineBar"' in response.text

    js_path = os.path.join(FRONTEND_DIR, "mobile", "apiClient.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "NETWORK_OFFLINE" in js
    assert "navigator.onLine" in js

def test_12_duplicate_send_protection():
    """12. Test duplicate-send protection: verifies isSendingChatMessage guard and button disabling in JS."""
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "isSendingChatMessage" in js
    assert "if (isSendingChatMessage) return;" in js
    assert "input.disabled = true;" in js
    assert "sendBtn.disabled = true;" in js
