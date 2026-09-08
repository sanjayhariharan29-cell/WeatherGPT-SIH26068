from fastapi import APIRouter, Query
from typing import Optional
from backend.services.weather_manager import WeatherManager

router = APIRouter(prefix="/weather", tags=["Weather"])
manager = WeatherManager()

@router.get("/current")
async def get_current_weather(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    location: str = Query("Coimbatore", description="Location name")
):
    """Returns current weather observations (IMD primary, Open-Meteo secondary)."""
    return await manager.get_current_weather(lat, lon, location)

@router.get("/forecast")
async def get_weather_forecast(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    location: str = Query("Coimbatore", description="Location name"),
    date: str = Query("tomorrow", description="Date requirement")
):
    """Returns weather forecast."""
    return await manager.get_forecast(lat, lon, location)

@router.get("/alerts")
async def get_weather_alerts(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    location: str = Query("Coimbatore", description="Location name")
):
    """Returns official IMD disaster warnings and safety alerts."""
    return await manager.get_alerts(lat, lon, location)

@router.get("/history")
async def get_weather_history(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    location: str = Query("Coimbatore", description="Location name"),
    start_date: str = Query("2020-01-01", description="Start date"),
    end_date: str = Query("2025-01-01", description="End date"),
    metric: str = Query("rainfall", description="Metric to inspect")
):
    """Returns historical weather data."""
    return await manager.get_history(lat, lon, location, start_date, end_date, metric)

@router.get("/trends")
async def get_climate_trends(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    location: str = Query("Coimbatore", description="Location name"),
    start_year: int = Query(2015, description="Start year"),
    end_year: int = Query(2025, description="End year"),
    metric: str = Query("temperature", description="Climate metric")
):
    """Returns multi-year climate trend analysis."""
    return await manager.get_trends(lat, lon, location, start_year, end_year, metric)
