"""OpenWeather Secondary Independent Live Weather Data Adapter.

Provides independent real-time observation and forecast data using the OpenWeather API.
Inherits from BaseWeatherProvider with server-side environment credential protection.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from backend.config.settings import settings
from backend.services.base_provider import BaseWeatherProvider
from backend.services.schemas import (
    NormalizedWeatherObservation,
    NormalizedForecastItem,
    NormalizedAlertItem
)
from backend.services.exceptions import (
    ProviderError,
    ProviderUnavailableError,
    ProviderAuthenticationError
)
from backend.services.cache import provider_cache


class OpenWeatherAdapter(BaseWeatherProvider):
    """Secondary Independent Weather Data Adapter (OpenWeather API)."""

    @property
    def name(self) -> str:
        return "OpenWeather"

    @property
    def authority_level(self) -> str:
        return "secondary_independent"

    @property
    def is_configured(self) -> bool:
        """Indicates whether valid live API credentials are configured in backend environment."""
        return bool(settings.OPENWEATHER_API_KEY and settings.OPENWEATHER_API_KEY.strip())

    async def get_current_weather(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> NormalizedWeatherObservation:
        """Fetch current weather from OpenWeather API with caching, normalization, and provenance."""
        cache_key = f"openweather_current_{location_name}_{latitude}_{longitude}"
        cached = provider_cache.get(cache_key)
        if cached:
            return cached

        if not self.is_configured:
            # Check if cached data exists before declaring unavailable
            cached_val, is_fresh, age = provider_cache.get_with_metadata(cache_key)
            if cached_val:
                return cached_val
            raise ProviderUnavailableError(
                "LIVE PROVIDER CREDENTIALS NOT CONFIGURED: OpenWeather API key is not set",
                provider_name=self.name,
                diagnostics={"provider": self.name, "is_configured": False}
            )

        now_utc = datetime.now(timezone.utc).isoformat()
        url = f"{settings.OPENWEATHER_BASE_URL}/weather"
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": settings.OPENWEATHER_API_KEY,
            "units": "metric"
        }

        try:
            payload = await self._fetch_json(url, params=params)
            main = payload.get("main", {}) or {}
            wind_data = payload.get("wind", {}) or {}
            weather_list = payload.get("weather", []) or []
            rain_data = payload.get("rain", {}) or {}

            temp = float(main.get("temp", 0.0))
            feels_like = float(main.get("feels_like", temp))
            humidity = float(main.get("humidity", 50.0))
            pressure = float(main.get("pressure", 1013.25))
            wind_speed = float(wind_data.get("speed", 0.0)) * 3.6  # Convert m/s to km/h
            wind_deg = float(wind_data.get("deg", 0.0)) if wind_data.get("deg") is not None else None

            # Rainfall in last 1 hour if available
            rainfall = float(rain_data.get("1h", 0.0))

            cond = "Clear"
            if weather_list and isinstance(weather_list, list) and len(weather_list) > 0:
                cond = weather_list[0].get("main", "Clear")

            # Observation timestamp from OpenWeather epoch dt
            dt_epoch = payload.get("dt")
            if dt_epoch:
                try:
                    obs_utc = datetime.fromtimestamp(dt_epoch, tz=timezone.utc).isoformat()
                except Exception:
                    obs_utc = now_utc
            else:
                obs_utc = now_utc

            rain_prob = 80.0 if (rainfall > 0 or "Rain" in cond or "Thunderstorm" in cond) else (25.0 if "Cloud" in cond else 5.0)

            obs = NormalizedWeatherObservation(
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                temperature_c=temp,
                feels_like_c=feels_like,
                humidity_pct=humidity,
                pressure_hpa=pressure,
                rain_probability_pct=rain_prob,
                wind_speed_kmh=wind_speed,
                wind_direction_deg=wind_deg,
                rainfall_mm=rainfall,
                condition=cond,
                source=self.name,
                authority_level=self.authority_level,
                observed_at=obs_utc,
                retrieved_at=now_utc
            )
            provider_cache.set(cache_key, obs)
            return obs

        except ProviderError as e:
            cached_val, is_fresh, age = provider_cache.get_with_metadata(cache_key)
            if cached_val:
                return cached_val
            raise e

    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedForecastItem]:
        """Fetch forecast from OpenWeather (5-day 3-hour endpoint)."""
        cache_key = f"openweather_forecast_{location_name}_{latitude}_{longitude}"
        cached = provider_cache.get(cache_key)
        if cached:
            return cached

        if not self.is_configured:
            return []

        now_utc = datetime.now(timezone.utc).isoformat()
        url = f"{settings.OPENWEATHER_BASE_URL}/forecast"
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": settings.OPENWEATHER_API_KEY,
            "units": "metric"
        }

        try:
            payload = await self._fetch_json(url, params=params)
            forecast_list = payload.get("list", []) or []
            items: List[NormalizedForecastItem] = []

            for entry in forecast_list[:8]:  # Next 24 hours (3-hour intervals)
                main = entry.get("main", {}) or {}
                wind_data = entry.get("wind", {}) or {}
                w_list = entry.get("weather", []) or []
                cond = w_list[0].get("main", "Cloudy") if w_list else "Cloudy"
                dt_txt = entry.get("dt_txt", now_utc)
                temp = float(main.get("temp", 0.0))
                pop = float(entry.get("pop", 0.0)) * 100.0
                wind_speed = float(wind_data.get("speed", 0.0)) * 3.6

                items.append(
                    NormalizedForecastItem(
                        forecast_time=dt_txt.split(" ")[-1][:5] if " " in dt_txt else "12:00",
                        forecast_for=dt_txt,
                        temperature_c=temp,
                        temp_min_c=float(main.get("temp_min", temp)),
                        temp_max_c=float(main.get("temp_max", temp)),
                        rain_probability_pct=pop,
                        wind_speed_kmh=wind_speed,
                        condition=cond,
                        source=self.name,
                        issued_at=now_utc,
                        retrieved_at=now_utc
                    )
                )

            if items:
                provider_cache.set(cache_key, items)
            return items

        except Exception:
            return []

    async def get_official_alerts(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedAlertItem]:
        """OpenWeather is a secondary provider and CANNOT issue official alerts in India (IMD is strictly authoritative)."""
        return []
