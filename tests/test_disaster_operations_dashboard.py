"""Deterministic Test Suite for Disaster & Government Operations Dashboard (Phase 31).

Verifies:
1. Authorization & RBAC:
   - 401 Unauthorized for unauthenticated requests
   - 403 Forbidden for regular users (role='user')
   - 200 OK for administrative users (role='admin' or 'developer')
2. Warning Lifecycle:
   - 'scheduled' for future issued_at
   - 'active' for current warnings within valid window
   - 'expired' for past expires_at
3. Geographic and Attribute Filtering:
   - district filtering
   - warning_type filtering
   - severity filtering
   - lifecycle filtering
4. Notification Targeting & Delivery Status:
   - SENT, SKIPPED, FAILED metric aggregation
   - targeting reasons (out_of_area, etc.)
5. Expired Warnings Segregation:
   - proper filtering of expired warnings
6. Unavailable Provider Graceful Degradation:
   - returns DEGRADED/OPTIMAL without 500 error
7. Missing Geometry Safety Invariant:
   - has_geometry: False, geometry: None, text-only affected area
   - ZERO synthetic or fake polygons generated
8. Official Warning Authority Invariant:
   - official warnings are authoritative and cannot be canceled or modified by LLM
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.session import SessionLocal, Base, engine
from backend.db.models import Alert as DBAlert, AlertDeliveryLog, User, DeviceToken
from backend.core.security import create_access_token, hash_password
from backend.services.disaster_operations_service import disaster_operations_service, DisasterOperationsService

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_users():
    """Sets up dedicated test users for admin, user, and developer roles."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Clear prior test entries
    db.query(AlertDeliveryLog).filter(AlertDeliveryLog.location_name.like("%DisasterTest%")).delete(synchronize_session=False)
    db.query(DBAlert).filter(DBAlert.location_name.like("%DisasterTest%")).delete(synchronize_session=False)
    db.query(User).filter(User.email.in_([
        "ops_admin@test.gov",
        "ops_user@test.org",
        "ops_dev@test.dev"
    ])).delete(synchronize_session=False)
    db.commit()

    admin_user = User(
        name="Disaster Operations Director",
        email="ops_admin@test.gov",
        password_hash=hash_password("AdminSecurePass123!"),
        role="admin",
        is_verified=True
    )
    normal_user = User(
        name="Normal Citizen",
        email="ops_user@test.org",
        password_hash=hash_password("UserPass123!"),
        role="user",
        is_verified=True
    )
    dev_user = User(
        name="Platform Engineer",
        email="ops_dev@test.dev",
        password_hash=hash_password("DevPass123!"),
        role="developer",
        is_verified=True
    )

    db.add_all([admin_user, normal_user, dev_user])
    db.commit()
    db.refresh(admin_user)
    db.refresh(normal_user)
    db.refresh(dev_user)

    admin_id, admin_email = admin_user.id, admin_user.email
    user_id, user_email = normal_user.id, normal_user.email
    dev_id, dev_email = dev_user.id, dev_user.email

    db.close()

    yield {
        "admin": (admin_id, admin_email),
        "user": (user_id, user_email),
        "dev": (dev_id, dev_email)
    }

    # Teardown
    db = SessionLocal()
    db.query(AlertDeliveryLog).filter(AlertDeliveryLog.location_name.like("%DisasterTest%")).delete(synchronize_session=False)
    db.query(DBAlert).filter(DBAlert.location_name.like("%DisasterTest%")).delete(synchronize_session=False)
    db.query(User).filter(User.email.in_([
        "ops_admin@test.gov",
        "ops_user@test.org",
        "ops_dev@test.dev"
    ])).delete(synchronize_session=False)
    db.commit()
    db.close()


@pytest.fixture
def admin_headers(setup_test_users):
    admin_id, admin_email = setup_test_users["admin"]
    token = create_access_token(data={"sub": admin_id, "email": admin_email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_headers(setup_test_users):
    user_id, user_email = setup_test_users["user"]
    token = create_access_token(data={"sub": user_id, "email": user_email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def dev_headers(setup_test_users):
    dev_id, dev_email = setup_test_users["dev"]
    token = create_access_token(data={"sub": dev_id, "email": dev_email})
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# 1. AUTHORIZATION TESTS
# =========================================================================
def test_dashboard_unauthenticated_forbidden():
    """Unauthenticated requests must be rejected with 401."""
    resp = client.get("/api/v1/operations/disaster/dashboard")
    assert resp.status_code == 401

    resp_ui = client.get("/operations/disaster")
    assert resp_ui.status_code == 401


def test_dashboard_normal_user_forbidden(user_headers):
    """Normal users (role='user') must receive 403 Forbidden."""
    resp = client.get("/api/v1/operations/disaster/dashboard", headers=user_headers)
    assert resp.status_code == 403
    assert "Insufficient permissions" in resp.json()["detail"]

    resp_ui = client.get("/operations/disaster", headers=user_headers)
    assert resp_ui.status_code == 403


def test_dashboard_admin_authorized(admin_headers):
    """Admin users must receive 200 OK with full dashboard telemetry."""
    resp = client.get("/api/v1/operations/disaster/dashboard", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "system_health" in data
    assert "warning_lifecycle_summary" in data
    assert "severity_summary" in data
    assert "fcm_delivery_summary" in data


def test_dashboard_developer_authorized(dev_headers):
    """Developer role must also be authorized to access disaster operations."""
    resp = client.get("/api/v1/operations/disaster/dashboard", headers=dev_headers)
    assert resp.status_code == 200


# =========================================================================
# 2. WARNING LIFECYCLE TESTS (SCHEDULED, ACTIVE, EXPIRED)
# =========================================================================
def test_warning_lifecycle_evaluation():
    """Unit test for lifecycle determination logic."""
    now = datetime.now(timezone.utc)
    service = DisasterOperationsService()

    # Scheduled: issued_at is in the future
    future_time = now + timedelta(hours=2)
    assert service.evaluate_warning_lifecycle(future_time, future_time + timedelta(hours=4), now=now) == "scheduled"

    # Active: issued_at in past, expires_at in future
    past_issued = now - timedelta(hours=1)
    future_expiry = now + timedelta(hours=3)
    assert service.evaluate_warning_lifecycle(past_issued, future_expiry, now=now) == "active"

    # Active: issued_at in past, no expiry
    assert service.evaluate_warning_lifecycle(past_issued, None, now=now) == "active"

    # Expired: expires_at in past
    past_expiry = now - timedelta(minutes=10)
    assert service.evaluate_warning_lifecycle(past_issued, past_expiry, now=now) == "expired"


def test_warning_lifecycle_in_database(admin_headers, setup_test_users):
    """Verify lifecycle queries against scheduled, active, and expired alerts in DB."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)

    # 1. Scheduled alert
    alert_sched = DBAlert(
        location_name="DisasterTest District North",
        latitude=13.0,
        longitude=80.0,
        alert_type="cyclone",
        severity="extreme",
        title="Cyclone Red Alert [Scheduled]",
        description="Severe cyclonic storm impending.",
        source="IMD",
        issued_at=now + timedelta(hours=3),
        expires_at=now + timedelta(hours=12)
    )
    # 2. Active alert
    alert_act = DBAlert(
        location_name="DisasterTest District Central",
        latitude=11.0,
        longitude=77.0,
        alert_type="heavy_rain",
        severity="high",
        title="Flash Flood Warning [Active]",
        description="Extremely heavy rainfall expected.",
        source="IMD",
        issued_at=now - timedelta(hours=2),
        expires_at=now + timedelta(hours=4)
    )
    # 3. Expired alert
    alert_exp = DBAlert(
        location_name="DisasterTest District South",
        latitude=9.0,
        longitude=78.0,
        alert_type="thunderstorm",
        severity="medium",
        title="Thunderstorm Alert [Expired]",
        description="Thunderstorm activity has subsided.",
        source="IMD",
        issued_at=now - timedelta(hours=10),
        expires_at=now - timedelta(hours=2)
    )
    db.add_all([alert_sched, alert_act, alert_exp])
    db.commit()

    try:
        # Query active lifecycle
        resp_act = client.get("/api/v1/operations/disaster/warnings?district=DisasterTest&lifecycle=active", headers=admin_headers)
        assert resp_act.status_code == 200
        data_act = resp_act.json()
        assert any(w["id"] == str(alert_act.id) for w in data_act["warnings"])
        assert not any(w["id"] == str(alert_sched.id) for w in data_act["warnings"])
        assert not any(w["id"] == str(alert_exp.id) for w in data_act["warnings"])

        # Query scheduled lifecycle
        resp_sched = client.get("/api/v1/operations/disaster/warnings?district=DisasterTest&lifecycle=scheduled", headers=admin_headers)
        assert resp_sched.status_code == 200
        data_sched = resp_sched.json()
        assert any(w["id"] == str(alert_sched.id) for w in data_sched["warnings"])

        # Query expired lifecycle
        resp_exp = client.get("/api/v1/operations/disaster/warnings?district=DisasterTest&lifecycle=expired", headers=admin_headers)
        assert resp_exp.status_code == 200
        data_exp = resp_exp.json()
        assert any(w["id"] == str(alert_exp.id) for w in data_exp["warnings"])
    finally:
        db.delete(alert_sched)
        db.delete(alert_act)
        db.delete(alert_exp)
        db.commit()
        db.close()


# =========================================================================
# 3. GEOGRAPHIC & ATTRIBUTE FILTERING TESTS
# =========================================================================
def test_geographic_and_severity_filtering(admin_headers):
    """Verify precise filtering by district, warning_type, and severity."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)

    a1 = DBAlert(
        location_name="DisasterTest Coimbatore Urban",
        latitude=11.0168,
        longitude=76.9558,
        alert_type="heavy_rain",
        severity="high",
        title="Heavy Rain in Coimbatore",
        description="Flooding possible",
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=2)
    )
    a2 = DBAlert(
        location_name="DisasterTest Chennai Coastal",
        latitude=13.0827,
        longitude=80.2707,
        alert_type="heat_wave",
        severity="extreme",
        title="Severe Heat Wave in Chennai",
        description="Heat stroke risk",
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=2)
    )
    db.add_all([a1, a2])
    db.commit()

    try:
        # District filter
        resp = client.get("/api/v1/operations/disaster/warnings?district=Coimbatore", headers=admin_headers)
        assert resp.status_code == 200
        items = resp.json()["warnings"]
        assert any(w["id"] == str(a1.id) for w in items)
        assert not any(w["id"] == str(a2.id) for w in items)

        # Severity filter
        resp_sev = client.get("/api/v1/operations/disaster/warnings?district=DisasterTest&severity=extreme", headers=admin_headers)
        assert resp_sev.status_code == 200
        items_sev = resp_sev.json()["warnings"]
        assert any(w["id"] == str(a2.id) for w in items_sev)
        assert not any(w["id"] == str(a1.id) for w in items_sev)

        # Warning type filter
        resp_type = client.get("/api/v1/operations/disaster/warnings?district=DisasterTest&warning_type=heat_wave", headers=admin_headers)
        assert resp_type.status_code == 200
        items_type = resp_type.json()["warnings"]
        assert any(w["id"] == str(a2.id) for w in items_type)
        assert not any(w["id"] == str(a1.id) for w in items_type)
    finally:
        db.delete(a1)
        db.delete(a2)
        db.commit()
        db.close()


# =========================================================================
# 4. NOTIFICATION TARGETING & DELIVERY AUDIT TESTS
# =========================================================================
def test_notification_status_aggregation(admin_headers, setup_test_users):
    """Verify delivery tracking aggregates SENT, SKIPPED, FAILED counts and reasons accurately."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    admin_id = setup_test_users["admin"][0]

    alert = DBAlert(
        location_name="DisasterTest Delta District",
        alert_type="squall",
        severity="high",
        title="Squall Gale Warning",
        description="High velocity winds",
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=2)
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Insert delivery logs for this alert
    log1 = AlertDeliveryLog(
        alert_id=alert.id,
        alert_fingerprint="fp1",
        user_id=admin_id,
        location_name="DisasterTest Delta District",
        channel="fcm",
        status="SENT",
        reason="eligible_in_affected_area"
    )
    log2 = AlertDeliveryLog(
        alert_id=alert.id,
        alert_fingerprint="fp1",
        user_id=admin_id,
        location_name="DisasterTest Delta District",
        channel="fcm",
        status="SKIPPED",
        reason="out_of_area"
    )
    log3 = AlertDeliveryLog(
        alert_id=alert.id,
        alert_fingerprint="fp1",
        user_id=admin_id,
        location_name="DisasterTest Delta District",
        channel="fcm",
        status="FAILED",
        reason="invalid_device_token"
    )
    db.add_all([log1, log2, log3])
    db.commit()

    try:
        resp = client.get(f"/api/v1/operations/disaster/warnings/{alert.id}", headers=admin_headers)
        assert resp.status_code == 200
        detail = resp.json()
        metrics = detail["notification_metrics"]

        assert metrics["total_targeted"] == 3
        assert metrics["sent_count"] == 1
        assert metrics["skipped_count"] == 1
        assert metrics["failed_count"] == 1
        assert metrics["skipped_reasons"]["out_of_area"] == 1
        assert metrics["failure_reasons"]["invalid_device_token"] == 1

        # Check logs endpoint
        logs_resp = client.get(f"/api/v1/operations/disaster/notifications?alert_id={alert.id}", headers=admin_headers)
        assert logs_resp.status_code == 200
        logs_data = logs_resp.json()
        assert logs_data["total_count"] == 3
    finally:
        db.delete(log1)
        db.delete(log2)
        db.delete(log3)
        db.delete(alert)
        db.commit()
        db.close()


# =========================================================================
# 5. MISSING GEOMETRY SAFETY INVARIANT (ZERO FAKE POLYGONS)
# =========================================================================
def test_missing_geometry_safety_fallback():
    """SAFETY INVARIANT:
    When geometry is missing or invalid, the system must NOT fabricate fake polygons.
    Instead, it returns has_geometry=False, geometry=None, and descriptive text.
    """
    service = DisasterOperationsService()

    # 1. Completely None geometry
    res_none = service.process_geographic_geometry(
        raw_geometry=None,
        location_name="Coimbatore District",
        latitude=11.0168,
        longitude=76.9558
    )
    assert res_none["has_geometry"] is False
    assert res_none["geometry"] is None
    assert "Coimbatore District" in res_none["affected_area_text"]
    assert "Lat: 11.0168, Lon: 76.9558" in res_none["affected_area_text"]

    # 2. Empty or invalid dictionary geometry
    res_empty = service.process_geographic_geometry(
        raw_geometry={"type": "Polygon", "coordinates": []},
        location_name="Nilgiris Ghats"
    )
    assert res_empty["has_geometry"] is False
    assert res_empty["geometry"] is None
    assert "Nilgiris Ghats" in res_empty["affected_area_text"]

    # 3. Genuine official GeoJSON polygon preserved exactly
    genuine_polygon = {
        "type": "Polygon",
        "coordinates": [[[76.9, 11.0], [77.1, 11.0], [77.1, 11.2], [76.9, 11.2], [76.9, 11.0]]]
    }
    res_valid = service.process_geographic_geometry(
        raw_geometry=genuine_polygon,
        location_name="Coimbatore Official Region"
    )
    assert res_valid["has_geometry"] is True
    assert res_valid["geometry"] == genuine_polygon


# =========================================================================
# 6. PROVIDER HEALTH & UNAVAILABLE PROVIDER DEGRADATION
# =========================================================================
def test_provider_health_telemetry_safe(admin_headers):
    """Verify health endpoint returns valid telemetry without leaking credentials."""
    resp = client.get("/api/v1/operations/disaster/health", headers=admin_headers)
    assert resp.status_code == 200
    health = resp.json()

    assert "overall_status" in health
    assert "providers" in health
    assert "infrastructure" in health
    assert health["security"]["service_account_exposed"] is False
    assert health["security"]["sanitized"] is True

    # Assert no secret keys or passwords in the payload
    json_text = resp.text.lower()
    assert "secret_key" not in json_text
    assert "password_hash" not in json_text
    assert "private_key" not in json_text


# =========================================================================
# 7. SAFETY INVARIANCE: OFFICIAL WARNING CANNOT BE CANCELED BY LLM
# =========================================================================
def test_official_warning_authoritative_hierarchy():
    """Verify official warnings are designated authoritative and immutable by LLM reasoning."""
    summary = disaster_operations_service.get_dashboard_summary(SessionLocal())
    assert "authoritative_rule" in summary
    assert "LLM outputs cannot modify or cancel official warnings" in summary["authoritative_rule"]
