"""Phase 22 — Production Deployment & Configuration Verification Test Suite.

Verifies health endpoints (/health, /health/liveness, /health/readiness), CORS settings,
frontend environment configuration (/config.js), Docker $PORT support, production Compose rules,
and environment template safety.
"""

import os
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config.settings import Settings

client = TestClient(app)


def test_01_health_endpoints_liveness_and_readiness():
    """Verifies GET /api/v1/health, /health/liveness, and /health/readiness endpoints."""
    # 1. Base health check
    res_base = client.get("/api/v1/health")
    assert res_base.status_code == 200
    data_base = res_base.json()
    assert data_base["status"] == "ok"
    assert "version" in data_base

    # 2. Liveness probe
    res_live = client.get("/api/v1/health/liveness")
    assert res_live.status_code == 200
    data_live = res_live.json()
    assert data_live["status"] == "alive"

    # 3. Readiness probe
    res_ready = client.get("/api/v1/health/readiness")
    assert res_ready.status_code == 200
    data_ready = res_ready.json()
    assert data_ready["status"] == "ready"
    assert data_ready["database"] == "connected"


def test_02_cors_origin_configuration():
    """Verifies CORS headers respond appropriately to allowed origins."""
    headers = {"Origin": "https://weathergpt.moes.gov.in"}
    res = client.get("/api/v1/health", headers=headers)
    assert res.status_code == 200
    # Check CORS access control header
    assert "access-control-allow-origin" in res.headers


def test_03_frontend_config_file_exists():
    """Verifies frontend/config.js exists and defines window.ENV object."""
    assert os.path.exists("frontend/config.js")
    with open("frontend/config.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert "window.ENV" in content
    assert "API_BASE" in content


def test_04_index_html_includes_config_js():
    """Verifies frontend/index.html includes config.js script before apiClient.js."""
    assert os.path.exists("frontend/index.html")
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        content = f.read()
    assert '<script src="/config.js"></script>' in content
    config_idx = content.find('<script src="/config.js"></script>')
    client_idx = content.find('<script src="/mobile/apiClient.js"></script>')
    assert config_idx < client_idx, "config.js must be loaded before apiClient.js"


def test_05_dockerfile_dynamic_port_support():
    """Verifies Dockerfile CMD and HEALTHCHECK dynamically evaluate $PORT environment variable."""
    assert os.path.exists("Dockerfile")
    with open("Dockerfile", "r", encoding="utf-8") as f:
        content = f.read()
    assert "${PORT:-8000}" in content
    assert "/api/v1/health" in content


def test_06_docker_compose_prod_validity():
    """Verifies docker-compose.prod.yml defines production backend container and .env.production file."""
    assert os.path.exists("docker-compose.prod.yml")
    with open("docker-compose.prod.yml", "r", encoding="utf-8") as f:
        content = f.read()
    assert "backend:" in content
    assert ".env.production" in content
    assert "healthcheck:" in content


def test_07_env_production_example_structure():
    """Verifies .env.production.example contains necessary production environment variables."""
    assert os.path.exists(".env.production.example")
    with open(".env.production.example", "r", encoding="utf-8") as f:
        content = f.read()

    required_keys = [
        "APP_NAME", "ENVIRONMENT", "DEBUG", "LOG_LEVEL", "PORT",
        "DATABASE_URL", "ALLOWED_ORIGINS", "SECRET_KEY",
        "IMD_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"
    ]
    for key in required_keys:
        assert f"{key}=" in content, f"Missing {key} in .env.production.example"


def test_08_environment_settings_override():
    """Verifies HOST, PORT, and ENVIRONMENT settings load correctly from environment overrides."""
    os.environ["HOST"] = "127.0.0.1"
    os.environ["PORT"] = "9000"
    os.environ["ENVIRONMENT"] = "production"

    try:
        test_settings = Settings()
        assert test_settings.HOST == "127.0.0.1"
        assert test_settings.PORT == 9000
        assert test_settings.ENVIRONMENT == "production"
    finally:
        os.environ.pop("HOST", None)
        os.environ.pop("PORT", None)
        os.environ.pop("ENVIRONMENT", None)
