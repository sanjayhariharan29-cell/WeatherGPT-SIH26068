"""Phase 4 Current Weather Engine Tests.

Verifies coordinate validation, normalized responses, units metadata, provider failover,
database persistence with deduplication, Person 1 AI model integration, and FastAPI API contracts.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.current_weather_service import CurrentWeatherService
from backend.services.exceptions import ProviderError, ProviderUnavailableError
from backend.schemas.weather import CurrentWeatherResponse
from backend.db.session import SessionLocal, engine, Base
from backend.db.models import WeatherRecord
from ai.models import WeatherRecord as AIWeatherRecord

client = TestClient(app)


@pytest.fixture(scope="module")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def test_coordinate_validation_valid():
    """Verify valid coordinates pass validation."""
    service = CurrentWeatherService()
    service.validate_coordinates(11.0168, 76.9558)
    service.validate_coordinates(-89.9, 179.9)


def test_coordinate_validation_invalid_latitude():
    """Verify invalid latitude raises ValueError."""
    service = CurrentWeatherService()
    with pytest.raises(ValueError) as exc_info:
        service.validate_coordinates(95.0, 76.9558)
    assert "Latitude must be between -90 and +90" in str(exc_info.value)

    with pytest.raises(ValueError):
        service.validate_coordinates(-100.0, 0.0)


def test_coordinate_validation_invalid_longitude():
    """Verify invalid longitude raises ValueError."""
    service = CurrentWeatherService()
    with pytest.raises(ValueError) as exc_info:
        service.validate_coordinates(11.0168, 200.0)
    assert "Longitude must be between -180 and +180" in str(exc_info.value)

    with pytest.raises(ValueError):
        service.validate_coordinates(0.0, -190.0)


@pytest.mark.asyncio
async def test_current_weather_service_nagapattinam():
    """Verify Nagapattinam current weather returns heavy rain, units, and provenance."""
    service = CurrentWeatherService()
    res = await service.fetch_current_weather(location_name="Nagapattinam")

    assert isinstance(res, CurrentWeatherResponse)
    assert res.location.name == "Nagapattinam"
    assert res.weather.temperature == 27.5
    assert res.weather.rain_probability == 85.0
    assert "IMD" in res.source
    assert res.units.temperature == "°C"
    assert res.units.wind_speed == "km/h"


@pytest.mark.asyncio
async def test_current_weather_failover_on_primary_failure():
    """Verify failover to secondary provider when primary IMD provider fails."""
    service = CurrentWeatherService()
    service.primary.get_current_weather = AsyncMock(side_effect=ProviderUnavailableError("IMD API Down"))

    res = await service.fetch_current_weather(location_name="Coimbatore")
    assert isinstance(res, CurrentWeatherResponse)
    assert "Fallback" in res.source or "Open-Meteo" in res.source
    assert res.weather.temperature > 0


@pytest.mark.asyncio
async def test_current_weather_db_persistence_and_deduplication(test_db):
    """Verify observations are persisted to WeatherRecord with 5-minute deduplication."""
    service = CurrentWeatherService()

    # Clear existing test records for Coimbatore
    test_db.query(WeatherRecord).filter(WeatherRecord.location_name == "Coimbatore").delete()
    test_db.commit()

    # First fetch with db_session
    res1 = await service.fetch_current_weather(location_name="Coimbatore", db_session=test_db)
    count1 = test_db.query(WeatherRecord).filter(WeatherRecord.location_name == "Coimbatore").count()
    assert count1 >= 1

    # Immediate second fetch (within 5 minutes) -> deduplication prevents duplicate row
    res2 = await service.fetch_current_weather(location_name="Coimbatore", db_session=test_db)
    count2 = test_db.query(WeatherRecord).filter(WeatherRecord.location_name == "Coimbatore").count()
    assert count2 == count1


@pytest.mark.asyncio
async def test_current_weather_ai_record_conversion():
    """Verify conversion to Person 1's AIWeatherRecord."""
    service = CurrentWeatherService()
    ai_obs = await service.get_ai_weather_record(location_name="Coimbatore")

    assert isinstance(ai_obs, AIWeatherRecord)
    assert ai_obs.location.name == "Coimbatore"
    assert ai_obs.temperature == 29.0
    assert ai_obs.source is not None


def test_api_current_weather_endpoint_success():
    """Verify GET /api/v1/weather/current returns HTTP 200 with schema compliance."""
    resp = client.get("/api/v1/weather/current?location=Coimbatore")
    assert resp.status_code == 200

    data = resp.json()
    assert data["location"]["name"] == "Coimbatore"
    assert "weather" in data
    assert "temperature" in data["weather"]
    assert "units" in data
    assert data["units"]["temperature"] == "°C"


def test_api_current_weather_endpoint_invalid_lat_lon():
    """Verify GET /api/v1/weather/current with invalid lat/lon returns HTTP 400 Bad Request."""
    resp1 = client.get("/api/v1/weather/current?lat=120.0")
    assert resp1.status_code == 400
    assert "Latitude must be between -90 and +90" in resp1.json()["error"]["message"]

    resp2 = client.get("/api/v1/weather/current?lon=-250.0")
    assert resp2.status_code == 400
    assert "Longitude must be between -180 and +180" in resp2.json()["error"]["message"]
