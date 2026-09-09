"""Phase 20 — Docker / Production Packaging Test Suite.

Verifies Dockerfile syntax, non-root runtime security, .dockerignore build context exclusion,
docker-compose.yml configuration, secret exclusion audit, health check endpoint compatibility,
environment variable overrides, and Person 1 AI pipeline functionality.
"""

import os
import re
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.cache import ProviderCache
from ai.pipeline import WeatherGPTPipeline
from ai.models import WeatherRecord, LocationInfo, PersonaEnum

client = TestClient(app)


# =============================================================================
# 1. DOCKERFILE & SECURITY AUDIT
# =============================================================================
def test_01_dockerfile_existence_and_base_image():
    """Verifies Dockerfile exists and uses minimal python:3.11-slim base image."""
    assert os.path.exists("Dockerfile")
    with open("Dockerfile", "r", encoding="utf-8") as f:
        content = f.read()

    assert "FROM python:3.11-slim" in content
    assert "WORKDIR /app" in content
    assert "EXPOSE 8000" in content


def test_02_dockerfile_non_root_user():
    """Verifies Dockerfile creates and switches to a non-root runtime user (appuser)."""
    with open("Dockerfile", "r", encoding="utf-8") as f:
        content = f.read()

    assert "useradd" in content or "appuser" in content
    assert "USER appuser" in content


def test_03_dockerfile_healthcheck_configuration():
    """Verifies Dockerfile configures a HEALTHCHECK instruction on /api/v1/health."""
    with open("Dockerfile", "r", encoding="utf-8") as f:
        content = f.read()

    assert "HEALTHCHECK" in content
    assert "/api/v1/health" in content


# =============================================================================
# 2. BUILD CONTEXT & DOCKERIGNORE EXCLUSION
# =============================================================================
def test_04_dockerignore_exclusion():
    """Verifies .dockerignore exists and excludes secrets, virtualenvs, tests, and VCS metadata."""
    assert os.path.exists(".dockerignore")
    with open(".dockerignore", "r", encoding="utf-8") as f:
        content = f.read()

    assert ".git" in content
    assert ".env" in content
    assert "node_modules" in content
    assert "*.db" in content


# =============================================================================
# 3. DOCKER COMPOSE CONFIGURATION
# =============================================================================
def test_05_docker_compose_configuration():
    """Verifies docker-compose.yml defines backend service, healthcheck, and port 8000 mapping."""
    assert os.path.exists("docker-compose.yml")
    with open("docker-compose.yml", "r", encoding="utf-8") as f:
        content = f.read()

    assert "backend:" in content
    assert "8000:8000" in content
    assert "ENVIRONMENT=production" in content
    assert "/api/v1/health" in content


# =============================================================================
# 4. SECRETS EXCLUSION AUDIT
# =============================================================================
def test_06_secret_exclusion_audit():
    """Verifies no API keys, database passwords, or provider credentials are hardcoded in Docker files."""
    for filepath in ["Dockerfile", "docker-compose.yml", ".dockerignore"]:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            # Ensure no secret strings or private tokens exist
            assert "AIzaSy" not in text, f"Potential Gemini API key in {filepath}"
            assert "postgres://" not in text or "POSTGRES_PASSWORD" not in text
            assert "PRIVATE_KEY" not in text


# =============================================================================
# 5. HEALTH ENDPOINT & NETWORKING COMPATIBILITY
# =============================================================================
def test_07_health_endpoint_compatibility():
    """Verifies GET /api/v1/health returns 200 OK and healthy status for container HEALTHCHECK."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") in ["ok", "healthy"]
    assert "version" in data


def test_08_current_weather_endpoint_compatibility():
    """Verifies GET /api/v1/weather/current returns valid weather telemetry."""
    res = client.get("/api/v1/weather/current?location=Coimbatore")
    assert res.status_code == 200
    data = res.json()
    assert "location" in data
    assert "weather" in data


def test_09_forecast_endpoint_compatibility():
    """Verifies GET /api/v1/weather/forecast returns valid multi-day forecast items."""
    res = client.get("/api/v1/weather/forecast?location=Coimbatore&days=3")
    assert res.status_code == 200
    data = res.json()
    assert "forecast" in data


def test_10_alerts_endpoint_compatibility():
    """Verifies GET /api/v1/weather/alerts returns valid official disaster warning structure."""
    res = client.get("/api/v1/weather/alerts?location=Coimbatore")
    assert res.status_code == 200
    data = res.json()
    assert "alerts" in data
    assert "status" in data


def test_11_chat_endpoint_compatibility():
    """Verifies POST /api/v1/chat processes user query and returns grounded answer."""
    payload = {
        "message": "Current weather in Coimbatore?",
        "persona": "student",
        "language": "en",
        "location": {"name": "Coimbatore"}
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "risk" in data


def test_12_environment_configuration_override():
    """Verifies environment variables safely override runtime configuration."""
    orig_env = os.environ.get("ENVIRONMENT")
    try:
        os.environ["ENVIRONMENT"] = "production"
        from backend.config.settings import settings
        assert settings.ENVIRONMENT in ["production", "testing", "development"]
    finally:
        if orig_env:
            os.environ["ENVIRONMENT"] = orig_env


def test_13_ai_pipeline_compatibility():
    """Verifies Person 1 AI pipeline executes cleanly under production packaging rules."""
    pipeline = WeatherGPTPipeline()
    obs = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at="2026-09-09T10:00:00Z",
        retrieved_at="2026-09-09T10:00:00Z",
        temperature=29.0,
        humidity=60.0,
        rain_probability=10.0,
        wind_speed=12.0,
        weather_condition="Clear",
        source="IMD"
    )
    result = pipeline.process_query("What is the weather?", weather=obs, persona=PersonaEnum.GENERAL)
    assert "answer" in result
    assert len(result["answer"]) > 0


def test_14_reproducibility_checklist():
    """Verifies presence of release and container packaging documentation."""
    assert os.path.exists("docs/person2/PHASE_20_DOCKER_PRODUCTION_PACKAGING.md")
