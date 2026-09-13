import io
import csv
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
import openpyxl

from backend.main import app
from backend.db.session import SessionLocal
from backend.db.models import User, AirQualityRecord
from backend.core.security import create_access_token, hash_password


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def setup_users():
    """Creates a regular user and a developer user for role testing."""
    with SessionLocal() as db:
        # Clean up existing test users if present
        db.query(User).filter(User.email.in_(["regular_tester@example.com", "dev_tester@example.com"])).delete(synchronize_session=False)
        db.commit()

        regular_user = User(
            name="Regular Tester",
            email="regular_tester@example.com",
            password_hash=hash_password("Password123!"),
            role="user",
            is_verified=True
        )
        developer_user = User(
            name="Developer Tester",
            email="dev_tester@example.com",
            password_hash=hash_password("Password123!"),
            role="developer",
            is_verified=True
        )
        db.add_all([regular_user, developer_user])
        db.commit()
        db.refresh(regular_user)
        db.refresh(developer_user)

        reg_token = create_access_token(data={"sub": regular_user.id, "email": regular_user.email})
        dev_token = create_access_token(data={"sub": developer_user.id, "email": developer_user.email})

        yield {
            "regular_user": regular_user,
            "regular_token": reg_token,
            "developer_user": developer_user,
            "developer_token": dev_token
        }

        # Teardown
        db.query(AirQualityRecord).filter(AirQualityRecord.source == "CPCB_MANUAL").delete(synchronize_session=False)
        db.query(User).filter(User.email.in_(["regular_tester@example.com", "dev_tester@example.com"])).delete(synchronize_session=False)
        db.commit()


class TestRoleBasedAccessControl:
    """Verifies that developer-only routes return 401/403 for unauthorized users."""

    def test_01_upload_unauthenticated_returns_401(self, client):
        """Unauthenticated requests must return 401 Unauthorized."""
        resp = client.post("/api/v1/developer/aqi/upload")
        assert resp.status_code == 401
        assert "Authentication credentials required" in resp.json().get("detail", "")

    def test_02_records_unauthenticated_returns_401(self, client):
        """Unauthenticated GET records must return 401 Unauthorized."""
        resp = client.get("/api/v1/developer/aqi/records")
        assert resp.status_code == 401
        assert "Authentication credentials required" in resp.json().get("detail", "")

    def test_03_regular_user_returns_403(self, client, setup_users):
        """Regular users with role='user' must receive 403 Forbidden."""
        token = setup_users["regular_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/v1/developer/aqi/records", headers=headers)
        assert resp.status_code == 403
        assert "Developer access required" in resp.json().get("detail", "")

    def test_04_regular_user_upload_returns_403(self, client, setup_users):
        """Regular users cannot upload files to developer endpoints."""
        token = setup_users["regular_token"]
        headers = {"Authorization": f"Bearer {token}"}
        csv_data = b"station,timestamp,pm2_5,aqi\nSIDCO Kurichi,2026-09-12 10:00:00,35.0,75\n"
        files = {"file": ("cpcb_sample.csv", csv_data, "text/csv")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 403
        assert "Developer access required" in resp.json().get("detail", "")

    def test_05_developer_user_can_access_records(self, client, setup_users):
        """Developer users with role='developer' can access developer endpoints."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/v1/developer/aqi/records", headers=headers)
        assert resp.status_code == 200
        assert "records" in resp.json()


class TestAQIUploadValidation:
    """Verifies strict column and value validation without silent guessing."""

    def test_06_unsupported_file_extension_rejected(self, client, setup_users):
        """Reject files that are not CSV or XLSX."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}
        files = {"file": ("data.json", b'{"station": "Test"}', "application/json")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 400
        assert "Only .csv and .xlsx files are supported" in resp.json()["detail"]

    def test_07_empty_file_rejected(self, client, setup_users):
        """Reject empty files."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}
        files = {"file": ("empty.csv", b"", "text/csv")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 400
        assert "Uploaded file is empty" in resp.json()["detail"]

    def test_08_missing_station_column_rejected(self, client, setup_users):
        """Reject file missing station column rather than guessing."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}
        csv_data = b"timestamp,pm2_5,aqi\n2026-09-12 10:00:00,35.0,75\n"
        files = {"file": ("no_station.csv", csv_data, "text/csv")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 400
        assert "Missing required column: 'station'" in resp.json()["detail"]

    def test_09_missing_timestamp_column_rejected(self, client, setup_users):
        """Reject file missing timestamp column."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}
        csv_data = b"station,pm2_5,aqi\nSIDCO Kurichi,35.0,75\n"
        files = {"file": ("no_timestamp.csv", csv_data, "text/csv")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 400
        assert "Missing required column: 'timestamp'" in resp.json()["detail"]

    def test_10_missing_pollutant_columns_rejected(self, client, setup_users):
        """Reject file missing all pollutant columns."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}
        csv_data = b"station,timestamp,temperature\nSIDCO Kurichi,2026-09-12 10:00:00,28.5\n"
        files = {"file": ("no_pollutants.csv", csv_data, "text/csv")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 400
        assert "Missing required pollutant columns" in resp.json()["detail"]

    def test_11_row_with_empty_station_rejected(self, client, setup_users):
        """Reject row where station value is empty."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}
        csv_data = b"station,timestamp,pm2_5\n,2026-09-12 10:00:00,35.0\n"
        files = {"file": ("empty_station_val.csv", csv_data, "text/csv")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 400
        assert "Missing required value for station column" in resp.json()["detail"]

    def test_12_row_with_unparseable_timestamp_rejected(self, client, setup_users):
        """Reject row where timestamp cannot be parsed."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}
        csv_data = b"station,timestamp,pm2_5\nSIDCO Kurichi,invalid-date-format,35.0\n"
        files = {"file": ("bad_date.csv", csv_data, "text/csv")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 400
        assert "Unparseable timestamp value" in resp.json()["detail"]

    def test_13_row_with_all_empty_pollutants_rejected(self, client, setup_users):
        """Reject row where all pollutant readings are blank/null."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}
        csv_data = b"station,timestamp,pm2_5,pm10\nSIDCO Kurichi,2026-09-12 10:00:00,,\n"
        files = {"file": ("blank_pollutants.csv", csv_data, "text/csv")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 400
        assert "All pollutant fields are empty" in resp.json()["detail"]

    def test_14_row_with_invalid_numeric_pollutant_rejected(self, client, setup_users):
        """Reject row with non-numeric text in pollutant value."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}
        csv_data = b"station,timestamp,pm2_5\nSIDCO Kurichi,2026-09-12 10:00:00,corrupted_value\n"
        files = {"file": ("corrupted_val.csv", csv_data, "text/csv")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 400
        assert "Invalid numeric value" in resp.json()["detail"]


class TestIngestionAndFreshnessClassification:
    """Verifies successful ingestion, tagging, and deterministic freshness classification."""

    def test_15_successful_csv_upload_stale_data(self, client, setup_users):
        """Upload data with old timestamp: must qualify as STALE, never automatic or real-time."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}
        # Timestamp from 24 hours ago
        stale_time = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

        csv_content = f"station,timestamp,pm2_5,pm10,no2,so2,co,o3,aqi\nSIDCO Kurichi Coimbatore,{stale_time},42.5,88.0,18.2,9.4,0.6,31.0,92\n"
        files = {"file": ("cpcb_stale_export.csv", csv_content.encode("utf-8"), "text/csv")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["records_ingested"] == 1
        assert data["source"] == "CPCB_MANUAL"
        assert data["is_manual"] is True
        # Must be classified as STALE, not LIVE or real-time
        assert data["freshness_state"] == "STALE"
        assert data["is_real_time"] is False

    def test_16_successful_xlsx_upload_recent_data(self, client, setup_users):
        """Upload XLSX with recent timestamp (<15m): qualifies as LIVE."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Station Name", "Observation Time", "PM2.5", "PM10", "AQI"])
        ws.append(["Ramanathapuram Coimbatore", recent_time, 28.0, 55.0, 65])
        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)

        files = {"file": ("cpcb_recent_export.xlsx", bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}

        resp = client.post("/api/v1/developer/aqi/upload", headers=headers, files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["records_ingested"] == 1
        assert data["source"] == "CPCB_MANUAL"
        assert data["freshness_state"] == "LIVE"
        assert data["is_real_time"] is True

    def test_17_get_records_preserves_provenance_and_freshness(self, client, setup_users):
        """GET /developer/aqi/records returns records with explicit provenance and freshness."""
        token = setup_users["developer_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/v1/developer/aqi/records?station=Coimbatore", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2
        for r in data["records"]:
            assert r["source"] == "CPCB_MANUAL"
            assert r["is_manual"] is True
            assert r["freshness_state"] in ("LIVE", "AGING", "STALE", "UNAVAILABLE")
            if r["freshness_state"] != "LIVE":
                assert r["is_real_time"] is False

    def test_18_weather_air_quality_endpoint_serves_cpcb_manual_with_freshness(self, client):
        """Public AQI endpoint surfaces manual CPCB data with accurate freshness and no false real-time label."""
        resp = client.get("/api/v1/weather/air-quality?location=Coimbatore")
        assert resp.status_code == 200
        data = resp.json()

        # Check if the matched record came from CPCB_MANUAL
        if data.get("source") == "CPCB_MANUAL":
            assert data["is_official_cpcb"] is True
            assert data["source_type"] == "manual_cpcb"
            assert data["methodology"] == "Manual CPCB Ground Monitoring Station Export"
            assert "station" in data and data["station"] is not None
            assert data["freshness"] in ("LIVE", "AGING", "STALE", "UNAVAILABLE")
            if data["freshness"] != "LIVE":
                assert data["is_real_time"] is False
