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

    @staticmethod
    def _map_wmo_code(code: int) -> str:
        """Map WMO weather code to standard descriptive condition."""
        if code == 0:
            return "Clear"
        elif code in (1, 2):
            return "Partly Cloudy"
        elif code == 3:
            return "Overcast"
        elif code in (45, 48):
            return "Fog"
        elif code in (51, 53, 55, 56, 57):
            return "Drizzle"
        elif code in (61, 63, 65, 66, 67, 80, 81, 82):
            return "Rain"
        elif code in (71, 73, 75, 77, 85, 86):
            return "Snow"
        elif code in (95, 96, 99):
            return "Thunderstorm"
        return "Cloudy"

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
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,surface_pressure,wind_speed_10m,wind_direction_10m",
            "hourly": "precipitation_probability"
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
            cond = self._map_wmo_code(code)

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

            # Extract real precipitation probability from Open-Meteo hourly model
            rain_prob = 0.0
            hourly = payload.get("hourly", {}) or {}
            h_times = hourly.get("time", [])
            h_probs = hourly.get("precipitation_probability", [])
            if h_times and h_probs:
                target_str = obs_time_raw if obs_time_raw else now_utc[:13]
                target_prefix = target_str[:13]
                matched_idx = -1
                for idx, ht in enumerate(h_times):
                    if ht.startswith(target_prefix):
                        matched_idx = idx
                        break
                if matched_idx >= 0 and matched_idx < len(h_probs) and h_probs[matched_idx] is not None:
                    rain_prob = float(h_probs[matched_idx])
                elif h_probs and h_probs[0] is not None:
                    rain_prob = float(h_probs[0])
            elif precip > 0:
                rain_prob = 100.0

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
        location_name: str = "Coimbatore",
        days: int = 7
    ) -> List[NormalizedForecastItem]:
        """Fetch multi-day daily and hourly forecast from Open-Meteo API."""
        cache_key = f"openmeteo_forecast_{location_name}_{latitude}_{longitude}_{days}"
        cached = provider_cache.get(cache_key)
        if cached:
            return cached

        now_utc = datetime.now(timezone.utc).isoformat()
        url = f"{settings.OPEN_METEO_BASE_URL}/forecast"
        forecast_days = min(max(days, 1), 16)
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,weather_code,wind_speed_10m_max",
            "timezone": "auto",
            "forecast_days": forecast_days
        }

        try:
            payload = await self._fetch_json(url, params=params)
            daily = payload.get("daily", {}) or {}
            times = daily.get("time", [])
            temp_maxs = daily.get("temperature_2m_max", [])
            temp_mins = daily.get("temperature_2m_min", [])
            rain_probs = daily.get("precipitation_probability_max", [])
            precips = daily.get("precipitation_sum", [])
            codes = daily.get("weather_code", [])
            winds = daily.get("wind_speed_10m_max", [])

            forecast_items: List[NormalizedForecastItem] = []
            for i, d_time in enumerate(times):
                t_max = float(temp_maxs[i]) if i < len(temp_maxs) and temp_maxs[i] is not None else 0.0
                t_min = float(temp_mins[i]) if i < len(temp_mins) and temp_mins[i] is not None else 0.0
                mean_temp = round((t_max + t_min) / 2.0, 1)
                r_prob = float(rain_probs[i]) if i < len(rain_probs) and rain_probs[i] is not None else 0.0
                p_sum = float(precips[i]) if i < len(precips) and precips[i] is not None else 0.0
                w_spd = float(winds[i]) if i < len(winds) and winds[i] is not None else 0.0
                code = int(codes[i]) if i < len(codes) and codes[i] is not None else 0

                cond = self._map_wmo_code(code)

                item = NormalizedForecastItem(
                    forecast_time=d_time,
                    forecast_for=d_time,
                    temperature_c=mean_temp,
                    temp_min_c=t_min,
                    temp_max_c=t_max,
                    rain_probability_pct=r_prob,
                    rainfall_mm=p_sum,
                    wind_speed_kmh=w_spd,
                    condition=cond,
                    source=self.name,
                    issued_at=now_utc,
                    retrieved_at=now_utc
                )
                forecast_items.append(item)

            if forecast_items:
                provider_cache.set(cache_key, forecast_items)
                return forecast_items

            raise ProviderError("Open-Meteo returned empty forecast dataset", provider_name=self.name)
        except ProviderError as e:
            cached_val, is_fresh, age = provider_cache.get_with_metadata(cache_key)
            if cached_val:
                return cached_val
            raise e

    async def get_official_alerts(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedAlertItem]:
        """Open-Meteo secondary adapter does not issue official Indian disaster warnings."""
        return []
