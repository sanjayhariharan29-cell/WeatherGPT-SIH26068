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
import time
try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None
    ImageDraw = None

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
    "rain": "precipitation_new",
    "wind": "wind_new",
    "temp": "temp_new",
    "precipitation": "precipitation_new",
    "precipitation_new": "precipitation_new",
    "rain_new": "precipitation_new",
    "wind_new": "wind_new",
    "temp_new": "temp_new",
}

SATELLITE_LAYER_NAMES = {
    "satellite",
    "himawari",
    "satellite_himawari",
    "himawari_b13",
    "himawari-b13"
}


async def _get_satellite_tile(z: int, x: int, y_int: int) -> Response:
    """Proxies Himawari-9 AHI Clean Infrared (Band 13) satellite imagery tiles.

    Attribution: JMA Himawari-9 / SSEC RealEarth (University of Wisconsin-Madison).
    Coverage: East Asia, Southeast Asia, Western Pacific, and India/South Asia.
    Refresh: ~10 minute rapid cycle.
    """
    cache_key = f"satellite_himawari_b13_{z}_{x}_{y_int}"
    cached_tile = provider_cache.get(cache_key)
    if cached_tile:
        return Response(
            content=cached_tile,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=600",
                "X-Cache": "HIT",
                "X-Satellite-Source": "Himawari-9 (JMA / SSEC RealEarth)",
                "X-Satellite-Band": "AHI Band 13 (Clean Infrared)"
            }
        )

    upstream_url = f"https://realearth.ssec.wisc.edu/tiles/HIMAWARI-B13/{z}/{x}/{y_int}.png"
    logger.info(f"[Satellite Tile] Fetching Himawari-9 tile: {upstream_url}")

    try:
        async with httpx.AsyncClient(timeout=settings.WEATHER_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                upstream_url,
                headers={"User-Agent": "WeatherGPT/1.0 (https://github.com/sanjayhariharan29-cell/WeatherGPT-SIH26068)"}
            )
            if resp.status_code == 200 and resp.content:
                provider_cache.set(cache_key, resp.content, ttl=600)
                return Response(
                    content=resp.content,
                    media_type="image/png",
                    headers={
                        "Cache-Control": "public, max-age=600",
                        "X-Cache": "MISS",
                        "X-Satellite-Source": "Himawari-9 (JMA / SSEC RealEarth)",
                        "X-Satellite-Band": "AHI Band 13 (Clean Infrared)"
                    }
                )
            else:
                logger.warning(f"Himawari satellite tile upstream error {resp.status_code} for {upstream_url}")
                raise HTTPException(
                    status_code=resp.status_code if 400 <= resp.status_code < 600 else 502,
                    detail=f"Himawari satellite tile upstream error ({resp.status_code})"
                )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error connecting to Himawari satellite tile upstream {upstream_url}: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to Himawari satellite tile upstream: {str(exc)}"
        )


_RAINVIEWER_CACHE = {"timestamp": 0.0, "host": "https://tilecache.rainviewer.com", "path": None, "data": None}


@router.get("/radar/timeline")
async def get_radar_timeline_metadata():
    """Returns cached RainViewer past radar frames for interactive timeline scrubber."""
    now = time.time()
    if not _RAINVIEWER_CACHE.get("data") or (now - _RAINVIEWER_CACHE["timestamp"] > 300):
        try:
            async with httpx.AsyncClient(timeout=settings.WEATHER_HTTP_TIMEOUT_SECONDS) as client:
                rv_resp = await client.get(
                    "https://api.rainviewer.com/public/weather-maps.json",
                    headers={"User-Agent": "WeatherGPT/1.0"}
                )
                if rv_resp.status_code == 200:
                    rv_data = rv_resp.json()
                    _RAINVIEWER_CACHE["data"] = rv_data
                    _RAINVIEWER_CACHE["host"] = rv_data.get("host", "https://tilecache.rainviewer.com")
                    past_frames = rv_data.get("radar", {}).get("past", [])
                    if past_frames:
                        _RAINVIEWER_CACHE["path"] = past_frames[-1]["path"]
                    _RAINVIEWER_CACHE["timestamp"] = now
        except Exception as exc:
            logger.warning(f"RainViewer radar metadata lookup warning: {exc}")

    if _RAINVIEWER_CACHE.get("data"):
        return _RAINVIEWER_CACHE["data"]
    return {"host": "https://tilecache.rainviewer.com", "radar": {"past": []}}


async def _get_rainviewer_radar_tile(z: int, x: int, y_int: int) -> Response:
    """Proxies live Doppler precipitation radar reflectivity imagery from RainViewer API."""
    cache_key = f"rainviewer_radar_{z}_{x}_{y_int}"
    cached_tile = provider_cache.get(cache_key)
    if cached_tile:
        return Response(
            content=cached_tile,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=300",
                "X-Cache": "HIT",
                "X-Radar-Source": "RainViewer Doppler Radar"
            }
        )

    now = time.time()
    # Refresh metadata cache every 5 minutes (300s)
    if not _RAINVIEWER_CACHE["path"] or (now - _RAINVIEWER_CACHE["timestamp"] > 300):
        try:
            async with httpx.AsyncClient(timeout=settings.WEATHER_HTTP_TIMEOUT_SECONDS) as client:
                rv_resp = await client.get(
                    "https://api.rainviewer.com/public/weather-maps.json",
                    headers={"User-Agent": "WeatherGPT/1.0"}
                )
                if rv_resp.status_code == 200:
                    rv_data = rv_resp.json()
                    host = rv_data.get("host", "https://tilecache.rainviewer.com")
                    past_frames = rv_data.get("radar", {}).get("past", [])
                    if past_frames:
                        _RAINVIEWER_CACHE["host"] = host
                        _RAINVIEWER_CACHE["path"] = past_frames[-1]["path"]
                        _RAINVIEWER_CACHE["timestamp"] = now
        except Exception as exc:
            logger.warning(f"RainViewer radar metadata lookup warning: {exc}")

    if _RAINVIEWER_CACHE["path"]:
        upstream_url = f"{_RAINVIEWER_CACHE['host']}{_RAINVIEWER_CACHE['path']}/256/{z}/{x}/{y_int}/2/1_1.png"
        try:
            async with httpx.AsyncClient(timeout=settings.WEATHER_HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.get(
                    upstream_url,
                    headers={"User-Agent": "WeatherGPT/1.0"}
                )
                if resp.status_code == 200 and resp.content:
                    provider_cache.set(cache_key, resp.content, ttl=300)
                    return Response(
                        content=resp.content,
                        media_type="image/png",
                        headers={
                            "Cache-Control": "public, max-age=300",
                            "X-Cache": "MISS",
                            "X-Radar-Source": "RainViewer Doppler Radar"
                        }
                    )
        except Exception as exc:
            logger.warning(f"RainViewer radar tile fetch fallback: {exc}")

    # Fallback to OpenWeather precipitation tile if RainViewer is temporarily unreachable
    return await _get_openweather_tile("precipitation_new", z, x, y_int)


async def _get_openweather_tile(canonical_layer: str, z: int, x: int, y_int: int) -> Response:
    """Proxies OpenWeather Weather Maps 2.0 layers without exposing API keys client-side."""
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


@router.get("/tiles/{layer}/{z}/{x}/{y}.png")
@router.get("/tiles/{layer}/{z}/{x}/{y}")
async def get_weather_map_tile(layer: str, z: int, x: int, y: str) -> Response:
    """
    Proxies OpenWeather Weather Maps 2.0, RainViewer Doppler radar, and Himawari-9 satellite tile layers without exposing API keys client-side.
    Supported layers: radar, satellite (Himawari-9 IR), rain, wind, temp.
    Accepts URLs with or without .png suffix (e.g. /tiles/satellite/7/93/60.png or /tiles/temp/7/93/60).
    """
    clean_layer = layer.lower().replace(".png", "")
    clean_y_str = str(y).replace(".png", "")

    try:
        y_int = int(clean_y_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Tile coordinate y must be an integer.")

    # Coordinate validation
    if z < 0 or z > 18:
        raise HTTPException(status_code=400, detail="Tile zoom level z must be between 0 and 18.")
    max_coord = 2 ** z
    if x < 0 or x >= max_coord or y_int < 0 or y_int >= max_coord:
        raise HTTPException(status_code=400, detail=f"Tile coordinates ({x}, {y_int}) out of bounds for zoom {z}.")

    # Special handling for satellite infrared layers (Himawari-9 AHI / SSEC RealEarth)
    if clean_layer in SATELLITE_LAYER_NAMES:
        return await _get_satellite_tile(z, x, y_int)

    # Special handling for Doppler precipitation radar (RainViewer API with Titan/Rainbow reflectivity)
    if clean_layer == "radar":
        return await _get_rainviewer_radar_tile(z, x, y_int)

    if clean_layer not in OPENWEATHER_LAYER_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported weather tile layer '{layer}'. Valid layers: {list(OPENWEATHER_LAYER_MAP.keys()) + ['satellite', 'himawari']}"
        )

    canonical_layer = OPENWEATHER_LAYER_MAP[clean_layer]
    return await _get_openweather_tile(canonical_layer, z, x, y_int)

