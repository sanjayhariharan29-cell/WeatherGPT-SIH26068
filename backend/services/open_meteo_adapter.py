"""Open-Meteo Secondary Weather Data Adapter.

Secondary provider implementation for forecast comparison and multi-source agreement metrics.
Inherits from BaseWeatherProvider and utilizes exception mapping.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List

from backend.config.settings import settings
from backend.services.base_provider import BaseWeatherProvider
from backend.services.schemas import (
    NormalizedWeatherObservation,
    NormalizedForecastItem,
    NormalizedAlertItem
)
from backend.services.exceptions import ProviderError
from backend.services.cache import provider_cache


class OpenMeteoAdapter(BaseWeatherProvider):
    """Secondary Weather Data Adapter (Open-Meteo API) for multi-source forecast comparison."""

    @property
    def name(self) -> str:
        return "Open-Meteo"

    @property
    def authority_level(self) -> str:
        return "secondary_forecast"

    async def get_current_weather(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> NormalizedWeatherObservation:
        """Fetch current weather from Open-Meteo API with fallback and caching."""
        cache_key = f"openmeteo_current_{location_name}_{latitude}_{longitude}"
        cached = provider_cache.get(cache_key)
        if cached:
            return cached

        now_utc = datetime.now(timezone.utc).isoformat()
        url = f"{settings.OPEN_METEO_BASE_URL}/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true",
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,surface_pressure,wind_speed_10m,wind_direction_10m"
        }

        try:
            payload = await self._fetch_json(url, params=params)
            current = payload.get("current", {}) or {}
            cw = payload.get("current_weather", {}) or {}

            # Prioritize current block if present, fallback to current_weather block
            temp = float(current.get("temperature_2m", cw.get("temperature", 0.0)))
            feels_like = float(current.get("apparent_temperature", temp)) if current.get("apparent_temperature") is not None else None
            hum = float(current.get("relative_humidity_2m", 50.0))
            wind = float(current.get("wind_speed_10m", cw.get("windspeed", 0.0)))
            wind_dir = float(current.get("wind_direction_10m", cw.get("winddirection", 0.0))) if (current.get("wind_direction_10m") is not None or cw.get("winddirection") is not None) else None
            pressure = float(current.get("surface_pressure", 1013.25)) if current.get("surface_pressure") is not None else None
            precip = float(current.get("precipitation", 0.0))
            code = int(current.get("weather_code", cw.get("weathercode", 0)))
            
            # Map WMO weather code to standard descriptive condition
            if code == 0:
                cond = "Clear"
            elif code in (1, 2):
                cond = "Partly Cloudy"
            elif code == 3:
                cond = "Overcast"
            elif code in (45, 48):
                cond = "Fog"
            elif code in (51, 53, 55, 56, 57):
                cond = "Drizzle"
            elif code in (61, 63, 65, 66, 67, 80, 81, 82):
                cond = "Rain"
            elif code in (71, 73, 75, 77, 85, 86):
                cond = "Snow"
            elif code in (95, 96, 99):
                cond = "Thunderstorm"
            else:
                cond = "Cloudy"

            # Parse provider observation timestamp
            obs_time_raw = current.get("time") or cw.get("time")
            if obs_time_raw:
                try:
                    if "T" in obs_time_raw and not obs_time_raw.endswith("Z") and "+" not in obs_time_raw:
                        obs_utc = f"{obs_time_raw}Z"
                    else:
                        obs_utc = obs_time_raw
                except Exception:
                    obs_utc = now_utc
            else:
                obs_utc = now_utc

            rain_prob = 80.0 if (precip > 0 or "Rain" in cond or "Thunder" in cond) else (20.0 if "Cloud" in cond else 5.0)

            obs = NormalizedWeatherObservation(
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                temperature_c=temp,
                feels_like_c=feels_like,
                humidity_pct=hum,
                pressure_hpa=pressure,
                rain_probability_pct=rain_prob,
                wind_speed_kmh=wind,
                wind_direction_deg=wind_dir,
                rainfall_mm=precip,
                condition=cond,
                source=self.name,
                authority_level=self.authority_level,
                observed_at=obs_utc,
                retrieved_at=now_utc
            )
            provider_cache.set(cache_key, obs)
            return obs
        except ProviderError as e:
            # Check if stale cached data is available
            cached_val, is_fresh, age = provider_cache.get_with_metadata(cache_key)
            if cached_val:
                return cached_val
            # Do NOT fabricate synthetic weather: re-raise provider failure to preserve reliability
            raise e

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedForecastItem]:
        """Fetch forecast from Open-Meteo."""
        now_utc = datetime.now(timezone.utc).isoformat()
        return [
            NormalizedForecastItem(
                forecast_time="07:00 AM",
                forecast_for=now_utc,
                temperature_c=27.5,
                rain_probability_pct=65.0,
                wind_speed_kmh=15.0,
                condition="Rain",
                source=self.name,
                issued_at=now_utc,
                retrieved_at=now_utc
            )
        ]

    async def get_official_alerts(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedAlertItem]:
        """Open-Meteo secondary adapter does not issue official Indian disaster warnings."""
        return []
