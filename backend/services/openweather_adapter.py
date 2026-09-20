"""OpenWeather Primary Live Weather Data Adapter.

Provides primary live real-time observation and forecast data using the OpenWeather API.
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
    """Primary Live Weather Data Adapter (OpenWeather API)."""

    def __init__(self, timeout: Optional[float] = None, authority_level: str = "secondary_independent"):
        super().__init__(timeout=timeout)
        self._authority_level = authority_level

    @property
    def name(self) -> str:
        return "OpenWeather"

    @property
    def authority_level(self) -> str:
        return self._authority_level

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

            temp = round(float(main.get("temp", 0.0)), 1)
            feels_like = round(float(main.get("feels_like", temp)), 1)
            humidity = round(float(main.get("humidity", 50.0)), 1)
            pressure = round(float(main.get("pressure", 1013.25)), 1)
            wind_speed = round(float(wind_data.get("speed", 0.0)) * 3.6, 1)  # Convert m/s to km/h
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

            for entry in forecast_list:  # Multi-day 5-day forecast (3-hour intervals)
                main = entry.get("main", {}) or {}
                wind_data = entry.get("wind", {}) or {}
                w_list = entry.get("weather", []) or []
                cond = w_list[0].get("main", "Cloudy") if w_list else "Cloudy"
                dt_txt = entry.get("dt_txt", now_utc)
                temp = round(float(main.get("temp", 0.0)), 1)
                pop = round(float(entry.get("pop", 0.0)) * 100.0, 1)
                wind_speed = round(float(wind_data.get("speed", 0.0)) * 3.6, 1)

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

    async def get_air_quality(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> Optional[Dict[str, Any]]:
        """Fetch real-time air pollution data from OpenWeather Air Pollution API."""
        if not self.is_configured:
            return None

        cache_key = f"openweather_aqi_{location_name}_{latitude}_{longitude}"
        cached = provider_cache.get(cache_key)
        if cached:
            return cached

        now_utc = datetime.now(timezone.utc).isoformat()
        url = f"{settings.OPENWEATHER_BASE_URL}/air_pollution"
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": settings.OPENWEATHER_API_KEY
        }

        try:
            payload = await self._fetch_json(url, params=params)
            item_list = payload.get("list", [])
            if not item_list:
                return None

            first = item_list[0]
            components = first.get("components", {})
            main = first.get("main", {})
            ow_aqi = int(main.get("aqi", 1))

            pm2_5 = float(components.get("pm2_5", 0.0))
            pm10 = float(components.get("pm10", 0.0))
            no2 = float(components.get("no2", 0.0))
            so2 = float(components.get("so2", 0.0))
            o3 = float(components.get("o3", 0.0))
            co = float(components.get("co", 0.0))

            # Continuous US AQI formula based on EPA PM2.5 breakpoints
            if pm2_5 <= 12.0:
                calc_aqi = round((50.0 / 12.0) * pm2_5)
            elif pm2_5 <= 35.4:
                calc_aqi = round(50 + ((100 - 51) / (35.4 - 12.1)) * (pm2_5 - 12.1))
            elif pm2_5 <= 55.4:
                calc_aqi = round(101 + ((150 - 101) / (55.4 - 35.5)) * (pm2_5 - 35.5))
            elif pm2_5 <= 150.4:
                calc_aqi = round(151 + ((200 - 151) / (150.4 - 55.5)) * (pm2_5 - 55.5))
            elif pm2_5 <= 250.4:
                calc_aqi = round(201 + ((300 - 201) / (250.4 - 150.5)) * (pm2_5 - 150.5))
            else:
                calc_aqi = round(301 + ((500 - 301) / (500.4 - 250.5)) * min(pm2_5 - 250.5, 250.0))

            aqi_val = max(1, min(500, calc_aqi))

            if aqi_val <= 50:
                category = "Good"
                recs = [
                    "Air quality is ideal for outdoor activities and exercise.",
                    "Safe for sensitive groups, children, and elderly.",
                    "Normal ventilation recommended."
                ]
            elif aqi_val <= 100:
                category = "Moderate"
                recs = [
                    "Air quality is acceptable for most outdoor activities.",
                    "Extremely sensitive individuals should limit prolonged outdoor exertion.",
                    "Comfortable conditions for commuting and outdoor sports."
                ]
            elif aqi_val <= 150:
                category = "Unhealthy for Sensitive Groups"
                recs = [
                    "People with respiratory or heart conditions should reduce heavy outdoor exertion.",
                    "Children and active adults should take frequent breaks during outdoor play.",
                    "Consider wearing a basic mask near heavy traffic corridors."
                ]
            elif aqi_val <= 200:
                category = "Unhealthy"
                recs = [
                    "Everyone may begin to experience minor respiratory discomfort.",
                    "Members of sensitive groups may experience more serious health effects.",
                    "Wear an N95/pollution mask when outdoors. Keep indoor windows closed."
                ]
            elif aqi_val <= 300:
                category = "Very Unhealthy"
                recs = [
                    "Health alert: The risk of health effects is increased for everyone.",
                    "Avoid prolonged outdoor activities. Use air purifiers indoors.",
                    "High-filtration masks required for essential travel."
                ]
            else:
                category = "Hazardous"
                recs = [
                    "Emergency conditions: Serious risk of respiratory distress.",
                    "Remain indoors and keep all ventilation closed.",
                    "Avoid all physical exertion outdoors."
                ]

            primary_pol = "PM2.5" if pm2_5 >= (pm10 / 2) else "PM10"

            res = {
                "location": location_name,
                "latitude": latitude,
                "longitude": longitude,
                "aqi": aqi_val,
                "category": category,
                "primary_pollutant": primary_pol,
                "pollutants": {
                    "pm2_5": round(pm2_5, 1),
                    "pm10": round(pm10, 1),
                    "no2": round(no2, 1),
                    "so2": round(so2, 1),
                    "o3": round(o3, 1),
                    "co": round(co, 1)
                },
                "recommendations": recs,
                "source": "OpenWeather",
                "source_identity": "OpenWeather",
                "source_type": "primary_live",
                "cpcb_status": "CPCB OFFICIAL API ACCESS NOT CONFIGURED (Served via OpenWeather)",
                "is_official_cpcb": False,
                "is_available": True,
                "status": "HEALTHY",
                "freshness": "FRESH",
                "is_real_time": True,
                "observed_at": now_utc,
                "station": None,
                "methodology": "OpenWeather Air Pollution Chemical Transport Model",
                "retrieved_at": now_utc
            }
            provider_cache.set(cache_key, res)
            return res
        except Exception:
            return None
