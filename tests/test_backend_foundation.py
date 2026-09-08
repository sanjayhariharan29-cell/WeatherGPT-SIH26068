import pytest
from fastapi.testclient import TestClient
from backend.config.settings import settings
from backend.main import app

client = TestClient(app)

def test_settings_loading():
    assert settings.APP_NAME == "WeatherGPT-SIH26068"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert isinstance(settings.ALLOWED_ORIGINS, list)
    assert len(settings.ALLOWED_ORIGINS) >= 1

def test_health_check_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "WeatherGPT-SIH26068"
    assert "environment" in data

def test_cors_headers():
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

def test_sanitized_404_error_handler():
    response = client.get("/api/v1/non_existent_route_12345")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_404"
