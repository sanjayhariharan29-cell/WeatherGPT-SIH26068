import os
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.session import SessionLocal
from backend.db.models import User, AirQualityRecord
from backend.core.security import create_access_token, hash_password


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def dashboard_users():
    """Sets up a regular user and a developer user for testing."""
    with SessionLocal() as db:
        db.query(User).filter(User.email.in_(["dash_user@example.com", "dash_dev@example.com"])).delete(synchronize_session=False)
        db.commit()

        user = User(
            name="Regular User",
            email="dash_user@example.com",
            password_hash=hash_password("Password123!"),
            role="user",
            is_verified=True
        )
        dev = User(
            name="Developer User",
            email="dash_dev@example.com",
            password_hash=hash_password("Password123!"),
            role="developer",
            is_verified=True
        )
        db.add_all([user, dev])
        db.commit()
        db.refresh(user)
        db.refresh(dev)

        user_token = create_access_token(data={"sub": user.id, "email": user.email})
        dev_token = create_access_token(data={"sub": dev.id, "email": dev.email})

        yield {
            "user": user,
            "user_token": user_token,
            "dev": dev,
            "dev_token": dev_token
        }

        # Cleanup
        db.query(User).filter(User.email.in_(["dash_user@example.com", "dash_dev@example.com"])).delete(synchronize_session=False)
        db.commit()


class TestDeveloperDashboardPageAndApiSecurity:
    """Verifies that the developer dashboard page and its API routes are strictly blocked for normal user role."""

    def test_01_dashboard_page_unauthenticated_returns_401(self, client):
        """Unauthenticated request to the dashboard route must be rejected with 401."""
        for path in ("/developer", "/dashboard/developer", "/developer.html", "/api/v1/developer/dashboard"):
            resp = client.get(path)
            assert resp.status_code == 401, f"Expected 401 on {path}, got {resp.status_code}"
            assert "Authentication credentials required" in resp.json().get("detail", "")

    def test_02_dashboard_page_normal_user_returns_403(self, client, dashboard_users):
        """Normal user with role='user' must receive 403 Forbidden when accessing developer dashboard page."""
        token = dashboard_users["user_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for path in ("/developer", "/dashboard/developer", "/developer.html", "/api/v1/developer/dashboard"):
            resp = client.get(path, headers=headers)
            assert resp.status_code == 403, f"Expected 403 on {path}, got {resp.status_code}"
            assert "Developer access required" in resp.json().get("detail", "")

    def test_03_dashboard_page_developer_returns_200_html(self, client, dashboard_users):
        """Developer user with role='developer' receives 200 OK and the dashboard HTML."""
        token = dashboard_users["dev_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for path in ("/developer", "/dashboard/developer", "/developer.html", "/api/v1/developer/dashboard"):
            resp = client.get(path, headers=headers)
            assert resp.status_code == 200, f"Expected 200 on {path}, got {resp.status_code}"
            assert "text/html" in resp.headers.get("content-type", "")
            html = resp.text
            # Confirm critical dashboard components are present in the HTML
            assert "SkyZen Developer Console" in html
            assert "Upload Manual CPCB Station Telemetry" in html
            assert "Recent Manual Data Uploads" in html
            assert "403 — Developer Access Required" in html
            assert "station" in html.lower()
            assert "timestamp" in html.lower()
            assert "cpcb_manual" in html.lower()

    def test_04_api_records_route_blocked_for_normal_user(self, client, dashboard_users):
        """GET /developer/aqi/records is blocked (403) for normal user."""
        token = dashboard_users["user_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/v1/developer/aqi/records", headers=headers)
        assert resp.status_code == 403
        assert "Developer access required" in resp.json().get("detail", "")

    def test_05_api_upload_route_blocked_for_normal_user(self, client, dashboard_users):
        """POST /developer/aqi/upload is blocked (403) for normal user."""
        token = dashboard_users["user_token"]
        headers = {"Authorization": f"Bearer {token}"}
        csv_data = b"station,timestamp,pm2_5\nSIDCO Kurichi,2026-09-12 10:00:00,35.0\n"
        files = {"file": ("test.csv", csv_data, "text/csv")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 403
        assert "Developer access required" in resp.json().get("detail", "")

    def test_06_api_routes_allowed_for_developer(self, client, dashboard_users):
        """GET /developer/aqi/records is allowed (200) for developer role."""
        token = dashboard_users["dev_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/v1/developer/aqi/records", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "records" in data

    def test_07_developer_html_static_file_exists_and_contains_guard(self):
        """Static developer.html exists in frontend and contains client-side role guard."""
        frontend_html = os.path.join("frontend", "developer.html")
        assert os.path.exists(frontend_html)
        with open(frontend_html, "r", encoding="utf-8") as f:
            content = f.read()

        # Check client-side guard logic
        assert "user.role !== \"developer\"" in content
        assert "403 — Developer Access Required" in content
        assert "handleFileUpload" in content
        assert "loadManualRecords" in content
        assert "recordsTableBody" in content
        assert "fileInput" in content
        assert "Station" in content
        assert "Observation Timestamp" in content
        assert "Uploaded Timestamp" in content
        assert "Source Tag" in content

    def test_08_spa_navigation_guards_developer_route(self):
        """frontend/app.js contains role checks preventing normal users from accessing developer screen."""
        app_js = os.path.join("frontend", "app.js")
        assert os.path.exists(app_js)
        with open(app_js, "r", encoding="utf-8") as f:
            content = f.read()

        assert "currentUser.role !== \"developer\"" in content
        assert "Access Denied: Developer role required" in content
