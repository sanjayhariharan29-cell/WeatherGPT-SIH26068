"""Weather API Router.

Exposes endpoints for current weather, multi-day forecasts, official disaster alerts,
historical archives, and multi-year climate trends with strict input validation and provider failure mapping.
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional
from sqlalchemy.orm import Session

from backend.services.weather_manager import WeatherManager
from backend.services.exceptions import (
    ProviderError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderRateLimitedError
)
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


def validate_coordinates(lat: Optional[float], lon: Optional[float]):
    if lat is not None and not (-90.0 <= lat <= 90.0):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and +90 degrees.")
    if lon is not None and not (-180.0 <= lon <= 180.0):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and +180 degrees.")


@router.get("/current", response_model=CurrentWeatherResponse)
async def get_current_weather(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", min_length=1, max_length=100, description="Location name"),
    db: Session = Depends(get_db)
):
    """Returns normalized current weather observations (IMD primary, Open-Meteo secondary) with units and validation."""
    validate_coordinates(lat, lon)
    try:
        return await manager.get_current_weather(lat, lon, location.strip(), db_session=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderTimeoutError as e:
        raise HTTPException(status_code=504, detail=f"Weather provider timed out: {e.message}")
    except (ProviderUnavailableError, ProviderRateLimitedError, ProviderError) as e:
        raise HTTPException(status_code=502, detail=f"Weather provider error: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Current weather retrieval error: {str(e)}")


@router.get("/forecast", response_model=ForecastResponse)
async def get_weather_forecast(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", min_length=1, max_length=100, description="Location name"),
    days: int = Query(7, ge=1, le=7, description="Number of forecast days (1-7)"),
    db: Session = Depends(get_db)
):
    """Returns normalized hourly & daily aggregated forecast data (IMD primary, Open-Meteo secondary)."""
    validate_coordinates(lat, lon)
    try:
        return await manager.get_forecast(lat, lon, location.strip(), days=days, db_session=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderTimeoutError as e:
        raise HTTPException(status_code=504, detail=f"Weather provider timed out: {e.message}")
    except (ProviderUnavailableError, ProviderRateLimitedError, ProviderError) as e:
        raise HTTPException(status_code=502, detail=f"Weather provider error: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast retrieval error: {str(e)}")


@router.get("/alerts", response_model=AlertResponse)
async def get_weather_alerts(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", min_length=1, max_length=100, description="Location name"),
    active_only: bool = Query(True, description="Filter currently active alerts only"),
    db: Session = Depends(get_db)
):
    """Returns official IMD disaster warnings and safety alerts."""
    validate_coordinates(lat, lon)
    try:
        return await manager.get_alerts(lat, lon, location.strip(), active_only=active_only, db_session=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderTimeoutError as e:
        raise HTTPException(status_code=504, detail=f"Weather provider timed out: {e.message}")
    except (ProviderUnavailableError, ProviderRateLimitedError, ProviderError) as e:
        raise HTTPException(status_code=502, detail=f"Weather provider error: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Alerts retrieval error: {str(e)}")


@router.get("/history", response_model=HistoricalWeatherResponse)
async def get_weather_history(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", min_length=1, max_length=100, description="Location name"),
    start_date: str = Query("2020-01-01", description="Start date YYYY-MM-DD"),
    end_date: str = Query("2025-01-01", description="End date YYYY-MM-DD"),
    metric: str = Query("rainfall", description="Metric to inspect"),
    db: Session = Depends(get_db)
):
    """Returns historical weather data archive and normalized weather record statistics."""
    validate_coordinates(lat, lon)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date.")

    try:
        return await manager.get_history(lat, lon, location.strip(), start_date, end_date, metric, db_session=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderTimeoutError as e:
        raise HTTPException(status_code=504, detail=f"Historical provider timed out: {e.message}")
    except (ProviderUnavailableError, ProviderRateLimitedError, ProviderError) as e:
        raise HTTPException(status_code=502, detail=f"Historical provider error: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Historical weather retrieval error: {str(e)}")


@router.get("/trends", response_model=ClimateTrendResponse)
async def get_climate_trends(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", min_length=1, max_length=100, description="Location name"),
    start_year: int = Query(2015, description="Start year"),
    end_year: int = Query(2025, description="End year"),
    metric: str = Query("temperature", description="Climate metric")
):
    """Returns multi-year climate trend analysis."""
    validate_coordinates(lat, lon)
    if start_year > end_year:
        raise HTTPException(status_code=400, detail="start_year must be less than or equal to end_year.")

    try:
        return await manager.get_trends(lat, lon, location.strip(), start_year, end_year, metric)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProviderTimeoutError as e:
        raise HTTPException(status_code=504, detail=f"Climate provider timed out: {e.message}")
    except (ProviderUnavailableError, ProviderRateLimitedError, ProviderError) as e:
        raise HTTPException(status_code=502, detail=f"Climate provider error: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Climate trends retrieval error: {str(e)}")
