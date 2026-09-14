"""Integration tests for Developer-Declared Manual Alert System & City-Scoping.

Verifies:
1. If no developer alert is active for a city (e.g. Coimbatore), 0 alerts are returned.
2. An alert declared via developer API for City A (e.g. Chennai) is visible when viewing City A.
3. Viewing City B (e.g. Coimbatore) returns 0 alerts even when City A has an active alert.
4. Global alert endpoint (all_cities=True or /weather/alerts/all) returns all active developer alerts.
5. AI official alert grounding only retrieves alerts for the target location.
6. Deleting/revoking an alert removes it immediately.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.alert_service import AlertService
from backend.db.session import SessionLocal, Base, engine
from backend.db.models import Alert as DBAlert, User
from backend.core.security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_clean_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Clean any developer alerts from prior runs
    db.query(DBAlert).delete()
    # Ensure test developer exists
    db.query(User).filter(User.email == "alert_dev@example.com").delete()
    dev_user = User(
        name="Alert Dev",
        email="alert_dev@example.com",
        password_hash=hash_password("DevPass123!"),
        role="developer",
        is_verified=True
    )
    db.add(dev_user)
    db.commit()
    db.refresh(dev_user)
    db.close()

    yield

    db = SessionLocal()
    db.query(DBAlert).delete()
    db.query(User).filter(User.email == "alert_dev@example.com").delete()
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def dev_headers():
    db = SessionLocal()
    dev = db.query(User).filter(User.email == "alert_dev@example.com").first()
    token = create_access_token(data={"sub": dev.id, "email": dev.email})
    db.close()
    return {"Authorization": f"Bearer {token}"}


def test_coimbatore_zero_alert_when_no_developer_entry():
    """Verify Coimbatore returns 0 alerts when no alert has been declared."""
    resp = client.get("/api/v1/weather/alerts?location=Coimbatore")
    assert resp.status_code == 200
    data = resp.json()
    assert data["location"] == "Coimbatore"
    assert len(data["alerts"]) == 0
    assert data["active_count"] == 0


@pytest.mark.asyncio
async def test_ai_official_alerts_zero_for_coimbatore():
    """Verify AI grounding returns empty list when no alert is active for location."""
    service = AlertService()
    ai_alerts = await service.get_ai_official_alerts(location_name="Coimbatore")
    assert ai_alerts == []


def test_developer_declare_alert_for_chennai(dev_headers):
    """Verify developer manual alert creation for Chennai."""
    payload = {
        "location_name": "Chennai",
        "alert_type": "heavy_rain",
        "severity": "red",
        "title": "Red Alert: Severe Torrential Rain",
        "description": "Very heavy rainfall exceeding 200mm expected across Chennai district.",
        "instructions": "Avoid waterlogged subways and stay indoors.",
        "duration_hours": 12
    }
    resp = client.post("/api/v1/developer/alerts", json=payload, headers=dev_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["alert"]["location_name"] == "Chennai"
    assert data["alert"]["severity"] == "high"
    assert data["alert"]["title"] == "Red Alert: Severe Torrential Rain"
    alert_id = data["alert"]["id"]

    # 1. Verify Coimbatore STILL sees 0 alerts
    resp_coim = client.get("/api/v1/weather/alerts?location=Coimbatore")
    assert resp_coim.status_code == 200
    assert len(resp_coim.json()["alerts"]) == 0

    # 2. Verify Chennai sees the active alert
    resp_chn = client.get("/api/v1/weather/alerts?location=Chennai")
    assert resp_chn.status_code == 200
    chn_data = resp_chn.json()
    assert len(chn_data["alerts"]) == 1
    assert chn_data["alerts"][0]["title"] == "Red Alert: Severe Torrential Rain"
    assert chn_data["alerts"][0]["severity"] == "high"  # Normalized from red
    assert chn_data["alerts"][0]["is_official"] is True

    # 3. Verify Global Alerts endpoint returns the Chennai alert
    resp_global = client.get("/api/v1/weather/alerts/all")
    assert resp_global.status_code == 200
    global_data = resp_global.json()
    assert len(global_data["alerts"]) == 1
    assert global_data["alerts"][0]["area"] == "Chennai"

    # 4. Verify Developer list endpoint
    resp_dev_list = client.get("/api/v1/developer/alerts", headers=dev_headers)
    assert resp_dev_list.status_code == 200
    dev_data = resp_dev_list.json()
    assert dev_data["count"] >= 1
    assert dev_data["alerts"][0]["id"] == alert_id

    # 5. Revoke/Delete the alert
    del_resp = client.delete(f"/api/v1/developer/alerts/{alert_id}", headers=dev_headers)
    assert del_resp.status_code == 200

    # 6. Verify Chennai now has 0 alerts
    resp_chn_after = client.get("/api/v1/weather/alerts?location=Chennai")
    assert resp_chn_after.status_code == 200
    assert len(resp_chn_after.json()["alerts"]) == 0
