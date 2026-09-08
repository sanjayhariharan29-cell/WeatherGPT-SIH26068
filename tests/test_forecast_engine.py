"""Phase 5 Forecast Engine Tests.

Verifies coordinate validation, hourly forecast normalization, daily forecast aggregation,
time semantics (issued_at vs forecast_for), provider failover, database persistence,
Person 1 AI model conversion, and FastAPI API contracts.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.forecast_service import ForecastService
from backend.services.exceptions import ProviderError, ProviderUnavailableError
from backend.schemas.weather import ForecastResponse, DailyForecastItemSchema
from backend.db.session import SessionLocal, engine, Base
from backend.db.models import Forecast as DBForecast
from ai.models import ForecastItem as AIForecastItem

client = TestClient(app)


@pytest.fixture(scope="module")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def test_forecast_coordinate_validation_valid():
    """Verify valid coordinates pass validation."""
    service = ForecastService()
    service.validate_coordinates(11.0168, 76.9558)
    service.validate_coordinates(-89.9, 179.9)


def test_forecast_coordinate_validation_invalid_latitude():
    """Verify invalid latitude raises ValueError."""
    service = ForecastService()
    with pytest.raises(ValueError) as exc_info:
        service.validate_coordinates(95.0, 76.9558)
    assert "Latitude must be between -90 and +90" in str(exc_info.value)


def test_forecast_coordinate_validation_invalid_longitude():
    """Verify invalid longitude raises ValueError."""
    service = ForecastService()
    with pytest.raises(ValueError) as exc_info:
        service.validate_coordinates(11.0168, 200.0)
    assert "Longitude must be between -180 and +180" in str(exc_info.value)


@pytest.mark.asyncio
async def test_forecast_service_hourly_and_daily_nagapattinam():
    """Verify Nagapattinam forecast returns hourly and aggregated daily items."""
    service = ForecastService()
    res = await service.fetch_forecast(location_name="Nagapattinam")

    assert isinstance(res, ForecastResponse)
    assert res.location == "Nagapattinam"
    assert len(res.hourly_forecast) >= 2
    assert len(res.forecast) == len(res.hourly_forecast)
    assert len(res.daily_forecast) >= 1

    daily_item = res.daily_forecast[0]
    assert isinstance(daily_item, DailyForecastItemSchema)
    assert daily_item.temperature_min <= daily_item.temperature_max
    assert daily_item.rain_probability >= 80.0
    assert daily_item.total_rainfall_mm > 0.0


@pytest.mark.asyncio
async def test_forecast_service_time_semantics():
    """Verify forecast explicitly demarcates issued_at from target forecast_for timestamp."""
    service = ForecastService()
    res = await service.fetch_forecast(location_name="Coimbatore")

    assert res.issued_at is not None
    for item in res.hourly_forecast:
        assert item.issued_at is not None
        assert item.forecast_for is not None


@pytest.mark.asyncio
async def test_forecast_service_failover_on_primary_failure():
    """Verify failover to secondary provider when primary IMD provider fails."""
    service = ForecastService()
    service.primary.get_forecast = AsyncMock(side_effect=ProviderUnavailableError("IMD Forecast Down"))

    res = await service.fetch_forecast(location_name="Coimbatore")
    assert isinstance(res, ForecastResponse)
    assert "Fallback" in res.source or "Open-Meteo" in res.source
    assert len(res.hourly_forecast) >= 1


@pytest.mark.asyncio
async def test_forecast_db_persistence_and_snapshotting(test_db):
    """Verify forecast items are persisted to DBForecast table with deduplication."""
    service = ForecastService()

    # Clear existing test records for Coimbatore
    test_db.query(DBForecast).filter(DBForecast.location_name == "Coimbatore").delete()
    test_db.commit()

    # First fetch with db_session
    res1 = await service.fetch_forecast(location_name="Coimbatore", db_session=test_db)
    count1 = test_db.query(DBForecast).filter(DBForecast.location_name == "Coimbatore").count()
    assert count1 >= 1

    # Immediate second fetch -> deduplication prevents duplicate rows for same forecast target time
    res2 = await service.fetch_forecast(location_name="Coimbatore", db_session=test_db)
    count2 = test_db.query(DBForecast).filter(DBForecast.location_name == "Coimbatore").count()
    assert count2 == count1


@pytest.mark.asyncio
async def test_forecast_ai_items_conversion():
    """Verify conversion to Person 1's AIForecastItem list."""
    service = ForecastService()
    ai_items = await service.get_ai_forecast_items(location_name="Coimbatore")

    assert isinstance(ai_items, list)
    assert len(ai_items) >= 1
    assert isinstance(ai_items[0], AIForecastItem)
    assert ai_items[0].temperature > 0


def test_api_forecast_endpoint_success():
    """Verify GET /api/v1/weather/forecast returns HTTP 200 with schema compliance."""
    resp = client.get("/api/v1/weather/forecast?location=Coimbatore")
    assert resp.status_code == 200

    data = resp.json()
    assert data["location"] == "Coimbatore"
    assert "hourly_forecast" in data
    assert "daily_forecast" in data
    assert "forecast" in data  # Frontend alias
    assert len(data["forecast"]) >= 1
    assert data["units"]["temperature"] == "°C"


def test_api_forecast_endpoint_invalid_lat_lon():
    """Verify GET /api/v1/weather/forecast with invalid lat/lon returns HTTP 400 Bad Request."""
    resp1 = client.get("/api/v1/weather/forecast?lat=120.0")
    assert resp1.status_code == 400
    assert "Latitude must be between -90 and +90" in resp1.json()["error"]["message"]

    resp2 = client.get("/api/v1/weather/forecast?lon=-250.0")
    assert resp2.status_code == 400
    assert "Longitude must be between -180 and +180" in resp2.json()["error"]["message"]
