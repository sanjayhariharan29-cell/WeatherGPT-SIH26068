import uuid
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "WeatherGPT" in data["service"]

def test_auth_flow():
    unique_email = f"user_{uuid.uuid4().hex[:8]}@weathergpt.in"
    reg_payload = {
        "name": "Test User",
        "email": unique_email,
        "password": "Password123!",
        "persona": "student",
        "language": "ta"
    }
    res_reg = client.post("/api/v1/auth/register", json=reg_payload)
    assert res_reg.status_code == 200
    assert "user_id" in res_reg.json()

    login_payload = {
        "email": unique_email,
        "password": "Password123!"
    }
    res_login = client.post("/api/v1/auth/login", json=login_payload)
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()

def test_current_weather_endpoint():
    res = client.get("/api/v1/weather/current?location=Coimbatore")
    assert res.status_code == 200
    data = res.json()
    assert "weather" in data
    assert data["location"]["name"] == "Coimbatore"

def test_forecast_endpoint():
    res = client.get("/api/v1/weather/forecast?location=Coimbatore&date=tomorrow")
    assert res.status_code == 200
    data = res.json()
    assert "forecast" in data

def test_alerts_endpoint():
    res = client.get("/api/v1/weather/alerts?location=Nagapattinam")
    assert res.status_code == 200
    data = res.json()
    assert len(data["alerts"]) >= 1

def test_chat_endpoint_hero_tanglish():
    chat_payload = {
        "message": "Naalaiku morning college pogalama?",
        "language": "ta",
        "persona": "student",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=chat_payload)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "risk" in data
    assert data["location"] == "Coimbatore"

def test_voice_query_endpoint():
    voice_payload = {
        "transcript": "Naalaiku morning college pogalama?",
        "language": "ta",
        "persona": "student",
        "location_name": "Coimbatore"
    }
    res = client.post("/api/v1/voice/query", data=voice_payload)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert data["transcript"] == "Naalaiku morning college pogalama?"
