"""Weather API Router.

Exposes endpoints for current weather, multi-day forecasts, official disaster alerts,
historical archives, and multi-year climate trends.
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional
from sqlalchemy.orm import Session

from backend.services.weather_manager import WeatherManager
from backend.schemas.weather import (
    CurrentWeatherResponse,
    ForecastResponse,
    AlertResponse,
    HistoricalWeatherResponse,
    ClimateTrendResponse
)
from backend.db.session import get_db

router = APIRouter(prefix="/weather", tags=["Weather"])
manager = WeatherManager()


@router.get("/current", response_model=CurrentWeatherResponse)
async def get_current_weather(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", description="Location name"),
    db: Session = Depends(get_db)
):
    """Returns normalized current weather observations (IMD primary, Open-Meteo secondary) with units and validation."""
    if lat is not None and (lat < -90.0 or lat > 90.0):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and +90 degrees.")

    if lon is not None and (lon < -180.0 or lon > 180.0):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and +180 degrees.")

    try:
        return await manager.get_current_weather(lat, lon, location, db_session=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Current weather retrieval error: {str(e)}")


@router.get("/forecast", response_model=ForecastResponse)
async def get_weather_forecast(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", description="Location name"),
    days: int = Query(7, ge=1, le=7, description="Number of forecast days (1-7)"),
    db: Session = Depends(get_db)
):
    """Returns normalized hourly & daily aggregated forecast data (IMD primary, Open-Meteo secondary)."""
    if lat is not None and (lat < -90.0 or lat > 90.0):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and +90 degrees.")

    if lon is not None and (lon < -180.0 or lon > 180.0):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and +180 degrees.")

    try:
        return await manager.get_forecast(lat, lon, location, days=days, db_session=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast retrieval error: {str(e)}")


@router.get("/alerts", response_model=AlertResponse)
async def get_weather_alerts(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", description="Location name"),
    active_only: bool = Query(True, description="Filter currently active alerts only"),
    db: Session = Depends(get_db)
):
    """Returns official IMD disaster warnings and safety alerts."""
    if lat is not None and (lat < -90.0 or lat > 90.0):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and +90 degrees.")

    if lon is not None and (lon < -180.0 or lon > 180.0):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and +180 degrees.")

    try:
        return await manager.get_alerts(lat, lon, location, active_only=active_only, db_session=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Alerts retrieval error: {str(e)}")


@router.get("/history", response_model=HistoricalWeatherResponse)
async def get_weather_history(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", description="Location name"),
    start_date: str = Query("2020-01-01", description="Start date YYYY-MM-DD"),
    end_date: str = Query("2025-01-01", description="End date YYYY-MM-DD"),
    metric: str = Query("rainfall", description="Metric to inspect"),
    db: Session = Depends(get_db)
):
    """Returns historical weather data archive and normalized weather record statistics."""
    if lat is not None and (lat < -90.0 or lat > 90.0):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and +90 degrees.")

    if lon is not None and (lon < -180.0 or lon > 180.0):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and +180 degrees.")

    try:
        return await manager.get_history(lat, lon, location, start_date, end_date, metric, db_session=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Historical weather retrieval error: {str(e)}")


@router.get("/trends", response_model=ClimateTrendResponse)
async def get_climate_trends(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", description="Location name"),
    start_year: int = Query(2015, description="Start year"),
    end_year: int = Query(2025, description="End year"),
    metric: str = Query("temperature", description="Climate metric")
):
    """Returns multi-year climate trend analysis."""
    if lat is not None and (lat < -90.0 or lat > 90.0):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and +90 degrees.")

    if lon is not None and (lon < -180.0 or lon > 180.0):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and +180 degrees.")

    try:
        return await manager.get_trends(lat, lon, location, start_year, end_year, metric)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Climate trends retrieval error: {str(e)}")
