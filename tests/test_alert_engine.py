"""Phase 6 Official Weather Warnings & Alert Engine Tests.

Verifies coordinate validation, official warning retrieval, severity normalization,
active vs expired alert filtering, source authority preservation (IMD), database persistence,
deduplication, Person 1 AI model conversion, and FastAPI API contracts.
"""

from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.alert_service import AlertService
from backend.services.exceptions import ProviderError, ProviderUnavailableError
from backend.schemas.weather import AlertResponse, AlertItemSchema
from backend.db.session import SessionLocal, engine, Base
from backend.db.models import Alert as DBAlert
from ai.models import OfficialAlert as AIOfficialAlert, RiskLevelEnum

client = TestClient(app)


@pytest.fixture(scope="module")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def test_alert_coordinate_validation_valid():
    """Verify valid coordinates pass validation."""
    service = AlertService()
    service.validate_coordinates(11.0168, 76.9558)
    service.validate_coordinates(-89.9, 179.9)


def test_alert_coordinate_validation_invalid_latitude():
    """Verify invalid latitude raises ValueError."""
    service = AlertService()
    with pytest.raises(ValueError) as exc_info:
        service.validate_coordinates(95.0, 76.9558)
    assert "Latitude must be between -90 and +90" in str(exc_info.value)


def test_alert_coordinate_validation_invalid_longitude():
    """Verify invalid longitude raises ValueError."""
    service = AlertService()
    with pytest.raises(ValueError) as exc_info:
        service.validate_coordinates(11.0168, 200.0)
    assert "Longitude must be between -180 and +180" in str(exc_info.value)


def test_alert_severity_normalization():
    """Verify severity normalization mappings."""
    service = AlertService()
    assert service.normalize_severity("yellow") == "low"
    assert service.normalize_severity("orange") == "medium"
    assert service.normalize_severity("red") == "high"
    assert service.normalize_severity("extreme") == "extreme"
    assert service.normalize_severity("high") == "high"


def test_alert_active_vs_expired_filtering():
    """Verify active vs expired alert timestamp logic."""
    service = AlertService()
    now = datetime.now(timezone.utc)

    past = (now - timedelta(hours=5)).isoformat()
    future_expire = (now + timedelta(hours=5)).isoformat()
    past_expire = (now - timedelta(hours=1)).isoformat()

    assert service.is_alert_active(past, future_expire) is True
    assert service.is_alert_active(past, past_expire) is False


@pytest.mark.asyncio
async def test_alert_service_nagapattinam_hero_warning():
    """Verify Nagapattinam alert returns official heavy rain cyclone warning from IMD."""
    service = AlertService()
    res = await service.fetch_alerts(location_name="Nagapattinam", active_only=True)

    assert isinstance(res, AlertResponse)
    assert res.location == "Nagapattinam"
    assert len(res.alerts) >= 1

    alert = res.alerts[0]
    assert isinstance(alert, AlertItemSchema)
    assert alert.source == "IMD"
    assert alert.is_official is True
    assert alert.is_active is True
    assert "Heavy Rain" in alert.title
    assert "Fishermen" in alert.description
    assert alert.area == "Nagapattinam Coastal Zone"


@pytest.mark.asyncio
async def test_alert_service_failover_degraded_state():
    """Verify graceful degraded status when primary provider fails."""
    service = AlertService()
    service.primary.get_official_alerts = AsyncMock(side_effect=ProviderUnavailableError("IMD Alerts Unreachable"))

    res = await service.fetch_alerts(location_name="Coimbatore")
    assert isinstance(res, AlertResponse)
    assert "Degraded" in res.source
    assert res.active_count == 0


@pytest.mark.asyncio
async def test_alert_db_persistence_and_deduplication(test_db):
    """Verify alert items are persisted to DBAlert table with deduplication."""
    service = AlertService()

    # Clear existing test records for Nagapattinam
    test_db.query(DBAlert).filter(DBAlert.location_name == "Nagapattinam").delete()
    test_db.commit()

    # First fetch with db_session
    res1 = await service.fetch_alerts(location_name="Nagapattinam", db_session=test_db)
    count1 = test_db.query(DBAlert).filter(DBAlert.location_name == "Nagapattinam").count()
    assert count1 >= 1

    # Immediate second fetch -> deduplication prevents duplicate rows
    res2 = await service.fetch_alerts(location_name="Nagapattinam", db_session=test_db)
    count2 = test_db.query(DBAlert).filter(DBAlert.location_name == "Nagapattinam").count()
    assert count2 == count1


@pytest.mark.asyncio
async def test_alert_ai_official_alert_conversion():
    """Verify conversion to Person 1's AIOfficialAlert list."""
    service = AlertService()
    ai_alerts = await service.get_ai_official_alerts(location_name="Nagapattinam")

    assert isinstance(ai_alerts, list)
    assert len(ai_alerts) >= 1

    ai_alert = ai_alerts[0]
    assert isinstance(ai_alert, AIOfficialAlert)
    assert ai_alert.source == "IMD"
    assert ai_alert.severity in (RiskLevelEnum.HIGH, RiskLevelEnum.EXTREME, RiskLevelEnum.MEDIUM)
    assert len(ai_alert.affected_locations) >= 1


def test_api_alerts_endpoint_success():
    """Verify GET /api/v1/weather/alerts returns HTTP 200 with schema compliance."""
    resp = client.get("/api/v1/weather/alerts?location=Nagapattinam")
    assert resp.status_code == 200

    data = resp.json()
    assert data["location"] == "Nagapattinam"
    assert "alerts" in data
    assert len(data["alerts"]) >= 1
    assert data["alerts"][0]["source"] == "IMD"
    assert data["alerts"][0]["is_official"] is True


def test_api_alerts_endpoint_invalid_lat_lon():
    """Verify GET /api/v1/weather/alerts with invalid lat/lon returns HTTP 400 Bad Request."""
    resp1 = client.get("/api/v1/weather/alerts?lat=120.0")
    assert resp1.status_code == 400
    assert "Latitude must be between -90 and +90" in resp1.json()["error"]["message"]

    resp2 = client.get("/api/v1/weather/alerts?lon=-250.0")
    assert resp2.status_code == 400
    assert "Longitude must be between -180 and +180" in resp2.json()["error"]["message"]
