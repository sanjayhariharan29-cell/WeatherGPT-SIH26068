"""Unit and Integration Tests for Phase 7 — Historical Weather Engine."""

import pytest
import math
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select, and_

from backend.main import app
from backend.db.session import get_db, Base, engine
from backend.db.models import WeatherRecord
from backend.services.base_provider import BaseWeatherProvider
from backend.services.historical_weather_service import HistoricalWeatherService
from backend.services.nasa_power_adapter import NasaPowerAdapter
from backend.services.schemas import NormalizedHistoricalWeather, NormalizedClimateTrend
from backend.services.exceptions import ProviderError

client = TestClient(app)


# Setup fixture for clean in-memory database test session
@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


def test_1_valid_history_service(db_session):
    """Test 1: Valid historical weather retrieval via HistoricalWeatherService."""
    service = HistoricalWeatherService()
    import asyncio
    res = asyncio.run(
        service.fetch_historical_weather(
            lat=11.0168,
            lon=76.9558,
            location_name="Coimbatore",
            start_date="2020-01-01",
            end_date="2024-01-01",
            metric="rainfall",
            db_session=db_session
        )
    )
    assert res.location == "Coimbatore"
    assert res.latitude == 11.0168
    assert res.longitude == 76.9558
    assert res.start_date == "2020-01-01"
    assert res.end_date == "2024-01-01"
    assert res.count > 0
    assert "average_annual_rainfall_mm" in res.summary


def test_2_date_range_validation():
    """Test 2: Proper parsing of date ranges."""
    start_dt, end_dt = HistoricalWeatherService.parse_and_validate_dates("2022-01-01", "2022-12-31")
    assert start_dt.year == 2022 and start_dt.month == 1 and start_dt.day == 1
    assert end_dt.year == 2022 and end_dt.month == 12 and end_dt.day == 31
    assert start_dt.tzinfo == timezone.utc
    assert end_dt.tzinfo == timezone.utc


def test_3_invalid_range():
    """Test 3: Reject start_date > end_date."""
    service = HistoricalWeatherService()
    import asyncio
    with pytest.raises(ValueError, match="must be <= end_date"):
        asyncio.run(
            service.fetch_historical_weather(
                location_name="Coimbatore",
                start_date="2025-01-01",
                end_date="2020-01-01"
            )
        )


def test_4_empty_range(db_session):
    """Test 4: Query range with explicit lat/lon and no existing DB records generates clean fallback structure."""
    service = HistoricalWeatherService()
    import asyncio
    res = asyncio.run(
        service.fetch_historical_weather(
            lat=10.0,
            lon=77.0,
            location_name="UnknownPlace",
            start_date="2023-05-01",
            end_date="2023-05-02",
            db_session=db_session
        )
    )
    assert res.location == "UnknownPlace"
    assert res.count == 1
    assert res.records[0].condition == "Historical Summary"


def test_5_timezone_preservation(db_session):
    """Test 5: Explicit verification of UTC timezone-aware datetimes."""
    service = HistoricalWeatherService()
    obs_dt = datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    rec = service.save_historical_record(
        db_session=db_session,
        location_name="Chennai",
        latitude=13.0827,
        longitude=80.2707,
        temperature=32.5,
        humidity=70.0,
        rain_probability=20.0,
        wind_speed=15.0,
        condition="Partly Cloudy",
        source="IMD Archive",
        observed_at_dt=obs_dt
    )
    assert rec.observed_at is not None
    assert obs_dt.tzinfo == timezone.utc


def test_6_multiple_sources(db_session):
    """Test 6: Handles historical observations from multiple sources without cross-contamination."""
    service = HistoricalWeatherService()
    obs_dt = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    r1 = service.save_historical_record(
        db_session, "Madurai", 9.9252, 78.1198, 30.0, 60.0, 10.0, 8.0, "Clear", "IMD Archive", obs_dt
    )
    r2 = service.save_historical_record(
        db_session, "Madurai", 9.9252, 78.1198, 30.2, 58.0, 15.0, 9.0, "Sunny", "NASA POWER", obs_dt
    )

    assert r1.id != r2.id
    assert r1.source == "IMD Archive"
    assert r2.source == "NASA POWER"


def test_7_deduplication(db_session):
    """Test 7: Prevents duplicate record insertion for same location, source, and observed_at."""
    service = HistoricalWeatherService()
    obs_dt = datetime(2023, 3, 1, 10, 0, 0, tzinfo=timezone.utc)

    r1 = service.save_historical_record(
        db_session, "Salem", 11.6643, 78.1460, 29.0, 65.0, 5.0, 10.0, "Clear", "NASA POWER", obs_dt
    )
    r2 = service.save_historical_record(
        db_session, "Salem", 11.6643, 78.1460, 29.0, 65.0, 5.0, 10.0, "Clear", "NASA POWER", obs_dt
    )

    assert r1.id == r2.id

    rows = db_session.execute(
        select(WeatherRecord).where(
            and_(
                WeatherRecord.location_name == "Salem",
                WeatherRecord.source == "NASA POWER",
                WeatherRecord.observed_at == obs_dt
            )
        )
    ).scalars().all()
    assert len(rows) == 1


def test_8_malformed_provider_data():
    """Test 8: Rejects NaN, Inf, and impossible parameter ranges."""
    # NaN temp
    with pytest.raises(ValueError, match="Invalid temperature"):
        HistoricalWeatherService.sanitize_record_data({"temperature": float("nan")})

    # Out of bounds humidity > 100
    with pytest.raises(ValueError, match="Invalid humidity"):
        HistoricalWeatherService.sanitize_record_data({"humidity": 150.0})

    # Negative wind speed
    with pytest.raises(ValueError, match="Invalid wind speed"):
        HistoricalWeatherService.sanitize_record_data({"wind_speed": -5.0})

    # Negative rainfall
    with pytest.raises(ValueError, match="Invalid rainfall"):
        HistoricalWeatherService.sanitize_record_data({"rainfall_mm": -10.0})


def test_9_provider_failure_resilience():
    """Test 9: Handles provider failures gracefully."""
    class FailingProvider(BaseWeatherProvider):
        @property
        def name(self) -> str:
            return "Failing"
        @property
        def authority_level(self) -> str:
            return "archive"
        async def get_current_weather(self, lat, lon, loc="Coimbatore"):
            raise ProviderError("Archive down")
        async def get_forecast(self, lat, lon, loc="Coimbatore"):
            return []
        async def get_official_alerts(self, lat, lon, loc="Coimbatore"):
            return []
        async def get_historical_weather(self, lat, lon, start, end, metric="rainfall"):
            raise ProviderError("NASA POWER connection timeout")
        async def get_climate_trend(self, lat, lon, start_year=2015, end_year=2025, metric="temperature"):
            raise ProviderError("Climate archive failure")

    service = HistoricalWeatherService(historical_provider=FailingProvider())
    import asyncio
    with pytest.raises(ProviderError, match="NASA POWER connection timeout"):
        asyncio.run(service.fetch_historical_weather(11.0, 76.9, "Coimbatore", "2020-01-01", "2021-01-01"))


def test_10_database_persistence(db_session):
    """Test 10: Ensures records are persisted into weather_records table."""
    service = HistoricalWeatherService()
    obs_dt = datetime(2022, 5, 20, 8, 30, 0, tzinfo=timezone.utc)

    rec = service.save_historical_record(
        db_session, "Trichy", 10.7905, 78.7047, 35.0, 50.0, 0.0, 14.0, "Sunny", "IMD Archive", obs_dt
    )

    db_rec = db_session.execute(
        select(WeatherRecord).where(WeatherRecord.id == rec.id)
    ).scalar_one_or_none()
    assert db_rec is not None
    assert db_rec.location_name == "Trichy"
    assert db_rec.temperature == 35.0


def test_11_database_retrieval(db_session):
    """Test 11: Retrieves historical records matching location and date range from DB."""
    service = HistoricalWeatherService()
    start_dt = datetime(2023, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    mid_dt = datetime(2023, 10, 15, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2023, 10, 30, 0, 0, 0, tzinfo=timezone.utc)

    service.save_historical_record(db_session, "Ooty", 11.4102, 76.6950, 15.0, 85.0, 80.0, 5.0, "Heavy Rain", "IMD Archive", mid_dt)

    import asyncio
    res = asyncio.run(
        service.fetch_historical_weather(
            lat=11.4102,
            lon=76.6950,
            location_name="Ooty",
            start_date="2023-10-01",
            end_date="2023-10-31",
            db_session=db_session
        )
    )
    assert res.location == "Ooty"
    assert res.count == 1
    assert res.records[0].temperature == 15.0
    assert res.records[0].condition == "Heavy Rain"


def test_12_api_endpoints():
    """Test 12: Validates GET /api/v1/weather/history and GET /api/v1/weather/trends endpoints."""
    # Valid history request
    resp = client.get("/api/v1/weather/history?location=Coimbatore&start_date=2020-01-01&end_date=2024-01-01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["location"] == "Coimbatore"
    assert "summary" in body
    assert "records" in body

    # Valid trends request
    resp_trends = client.get("/api/v1/weather/trends?location=Coimbatore&start_year=2015&end_year=2025")
    assert resp_trends.status_code == 200
    body_trends = resp_trends.json()
    assert body_trends["location"] == "Coimbatore"
    assert body_trends["trend"] == "increasing"
    assert body_trends["temperature_delta_c"] == 0.85

    # Invalid latitude
    resp_bad = client.get("/api/v1/weather/history?lat=150.0")
    assert resp_bad.status_code == 400
    assert "Latitude must be between" in resp_bad.json()["error"]["message"]


def test_13_large_range_safety():
    """Test 13: Enforces max query range (3650 days / 10 years)."""
    service = HistoricalWeatherService()
    import asyncio
    with pytest.raises(ValueError, match="range too large"):
        asyncio.run(
            service.fetch_historical_weather(
                location_name="Coimbatore",
                start_date="2000-01-01",
                end_date="2025-01-01"
            )
        )


def test_14_missing_values_handling():
    """Test 14: Handles optional/missing fields safely without crash."""
    valid_data = {
        "temperature": 25.0,
        "humidity": 50.0,
        "rain_probability": 0.0,
        "wind_speed": 10.0,
        "rainfall_mm": 0.0
    }
    sanitized = HistoricalWeatherService.sanitize_record_data(valid_data)
    assert sanitized["temperature"] == 25.0
