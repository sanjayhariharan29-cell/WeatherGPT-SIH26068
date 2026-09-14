"""Weather API Router.

Exposes endpoints for current weather, multi-day forecasts, official disaster alerts,
historical archives, and multi-year climate trends with strict input validation and provider failure mapping.
"""

from fastapi import APIRouter, Query, HTTPException, Depends, Response
from typing import Optional
from sqlalchemy.orm import Session
import httpx
import io
import math
from PIL import Image, ImageDraw

from backend.config.settings import settings
from backend.config.logging import logger
from backend.services.cache import provider_cache

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
    ClimateTrendResponse,
    AirQualityResponse
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
    """Returns normalized current weather observations (OpenWeather primary, Open-Meteo secondary) with units and validation."""
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
    """Returns normalized hourly & daily aggregated forecast data (OpenWeather primary, Open-Meteo secondary)."""
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


@router.get("/alerts/all", response_model=AlertResponse)
async def get_all_weather_alerts(
    active_only: bool = Query(True, description="Filter currently active alerts only"),
    db: Session = Depends(get_db)
):
    """Returns all active official disaster alerts across all cities (global multi-city view)."""
    try:
        return await manager.get_alerts(location_name="all", active_only=active_only, db_session=db, all_cities=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"All alerts retrieval error: {str(e)}")


@router.get("/alerts", response_model=AlertResponse)
async def get_weather_alerts(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", min_length=1, max_length=100, description="Location name"),
    active_only: bool = Query(True, description="Filter currently active alerts only"),
    all_cities: bool = Query(False, description="Filter all active alerts across all cities"),
    db: Session = Depends(get_db)
):
    """Returns official IMD disaster warnings and safety alerts."""
    is_global = all_cities or location.strip().lower() == "all"
    if not is_global:
        validate_coordinates(lat, lon)
    try:
        return await manager.get_alerts(
            lat, lon, location.strip(),
            active_only=active_only,
            db_session=db,
            all_cities=is_global
        )
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


@router.get("/air-quality", response_model=AirQualityResponse)
async def get_air_quality(
    lat: Optional[float] = Query(None, description="Latitude (-90 to +90)"),
    lon: Optional[float] = Query(None, description="Longitude (-180 to +180)"),
    location: str = Query("Coimbatore", min_length=1, max_length=100, description="Location name")
):
    """Returns real-time Air Quality Index (AQI), key pollutants (PM2.5, PM10, etc.), and health recommendations."""
    validate_coordinates(lat, lon)
    try:
        return await manager.get_air_quality(lat, lon, location.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Air quality retrieval error: {str(e)}")


# ---------------------------------------------------------------------------
# OpenWeather Weather Maps 2.0 Tile Proxy & Overlay Engine
# ---------------------------------------------------------------------------

OPENWEATHER_LAYER_MAP = {
    "radar": "precipitation_new",
    "temp": "temp_new",
    "rain": "precipitation_new",
    "wind": "wind_new",
    "clouds": "clouds_new",
    "pressure": "pressure_new",
    "waves": "pressure_new",
    "precipitation": "precipitation_new",
    "precipitation_new": "precipitation_new",
    "rain_new": "precipitation_new",
    "wind_new": "wind_new",
    "clouds_new": "clouds_new",
    "temp_new": "temp_new",
    "pressure_new": "pressure_new",
}


@router.get("/tiles/{layer}/{z}/{x}/{y}.png")
@router.get("/tiles/{layer}/{z}/{x}/{y}")
async def get_weather_map_tile(layer: str, z: int, x: int, y: str) -> Response:
    """
    Proxies OpenWeather Weather Maps 2.0 tile layers without exposing API keys client-side.
    Supported layers: radar, temp, rain, wind, clouds, pressure, waves (and canonical OpenWeather layer names).
    Accepts URLs with or without .png suffix (e.g. /tiles/temp/7/93/60.png or /tiles/temp/7/93/60).
    """
    clean_layer = layer.lower().replace(".png", "")
    clean_y_str = str(y).replace(".png", "")

    try:
        y_int = int(clean_y_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Tile coordinate y must be an integer.")

    if clean_layer not in OPENWEATHER_LAYER_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported weather tile layer '{layer}'. Valid layers: {list(OPENWEATHER_LAYER_MAP.keys())}"
        )

    canonical_layer = OPENWEATHER_LAYER_MAP[clean_layer]

    # Coordinate validation
    if z < 0 or z > 18:
        raise HTTPException(status_code=400, detail="Tile zoom level z must be between 0 and 18.")
    max_coord = 2 ** z
    if x < 0 or x >= max_coord or y_int < 0 or y_int >= max_coord:
        raise HTTPException(status_code=400, detail=f"Tile coordinates ({x}, {y_int}) out of bounds for zoom {z}.")

    cache_key = f"ow_tile_{canonical_layer}_{z}_{x}_{y_int}"
    cached_tile = provider_cache.get(cache_key)
    if cached_tile:
        return Response(
            content=cached_tile,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=600", "X-Cache": "HIT"}
        )

    # Construct upstream URL to tile.openweathermap.org
    api_key = (settings.OPENWEATHER_API_KEY or "").strip()
    if not api_key:
        logger.error("OPENWEATHER_API_KEY is not configured. Upstream weather map tiles require a valid API key.")
        raise HTTPException(
            status_code=502,
            detail="OpenWeather API key is not configured. A valid OPENWEATHER_API_KEY must be supplied by the developer before deployment."
        )

    upstream_url = f"https://tile.openweathermap.org/map/{canonical_layer}/{z}/{x}/{y_int}.png?appid={api_key}"

    print(f"[OpenWeather Tile] (1) Upstream URL: {upstream_url}", flush=True)
    logger.info(f"[OpenWeather Tile] (1) Upstream URL: {upstream_url}")

    status_code = None
    content_bytes = 0
    resp_text = ""
    try:
        async with httpx.AsyncClient(timeout=settings.WEATHER_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.get(upstream_url)
            status_code = resp.status_code
            content_bytes = len(resp.content) if resp.content else 0
            resp_text = resp.text

            print(f"[OpenWeather Tile] (2) Upstream HTTP Status: {status_code}", flush=True)
            logger.info(f"[OpenWeather Tile] (2) Upstream HTTP Status: {status_code}")
            print(f"[OpenWeather Tile] (3) Upstream Byte Size: {content_bytes} bytes", flush=True)
            logger.info(f"[OpenWeather Tile] (3) Upstream Byte Size: {content_bytes} bytes")

            if status_code == 200 and resp.content:
                provider_cache.set(cache_key, resp.content, ttl=600)
                return Response(
                    content=resp.content,
                    media_type="image/png",
                    headers={"Cache-Control": "public, max-age=600", "X-Cache": "MISS"}
                )
            else:
                error_msg = f"Upstream OpenWeather tile failed with status {status_code} for {upstream_url}: {resp_text[:200]}"
                logger.error(error_msg)
                raise HTTPException(
                    status_code=status_code if (status_code and 400 <= status_code < 600) else 502,
                    detail=f"OpenWeather tile upstream error ({status_code}): {resp_text[:120]}"
                )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error fetching upstream OpenWeather tile from {upstream_url}: {exc}")
        print(f"[OpenWeather Tile] Exception connecting to upstream: {exc}", flush=True)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to OpenWeather tile upstream: {str(exc)}"
        )

