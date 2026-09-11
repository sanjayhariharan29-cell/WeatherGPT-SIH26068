"""Master Weather Service Manager.

Orchestrates IMD (Primary), Open-Meteo (Secondary), NASA POWER (Climate/Historical),
CurrentWeatherService, ForecastService, AlertService, and Geocoding services behind a unified architecture.
"""

from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.openweather_adapter import OpenWeatherAdapter
from backend.services.nasa_power_adapter import NasaPowerAdapter
from backend.services.geocoding_service import GeocodingService
from backend.services.current_weather_service import CurrentWeatherService
from backend.services.forecast_service import ForecastService
from backend.services.alert_service import AlertService
from backend.services.historical_weather_service import HistoricalWeatherService
from backend.services.base_provider import BaseWeatherProvider
from ai.models import (
    WeatherRecord as AIWeatherRecord,
    ForecastItem as AIForecastItem,
    OfficialAlert as AIOfficialAlert,
    HistoricalWeatherDataset
)


class WeatherManager:
    """Master Weather Service orchestrating provider adapters, geocoding, and AI conversion."""

    def __init__(
        self,
        primary_provider: Optional[BaseWeatherProvider] = None,
        secondary_provider: Optional[BaseWeatherProvider] = None,
        tertiary_provider: Optional[BaseWeatherProvider] = None,
        historical_provider: Optional[BaseWeatherProvider] = None,
        geocoding_service: Optional[GeocodingService] = None
    ):
        self.imd = primary_provider or IMDAdapter()
        self.open_meteo = secondary_provider or OpenMeteoAdapter()
        self.openweather = tertiary_provider or OpenWeatherAdapter()
        self.nasa_power = historical_provider or NasaPowerAdapter()
        self.geocoding = geocoding_service or GeocodingService()
        self.current_service = CurrentWeatherService(
            primary_provider=self.imd,
            secondary_provider=self.open_meteo,
            tertiary_provider=self.openweather,
            geocoding_service=self.geocoding
        )
        self.forecast_service = ForecastService(
            primary_provider=self.imd,
            secondary_provider=self.open_meteo,
            geocoding_service=self.geocoding
        )
        self.alert_service = AlertService(
            primary_provider=self.imd,
            secondary_provider=self.open_meteo,
            geocoding_service=self.geocoding
        )
        self.historical_service = HistoricalWeatherService(
            historical_provider=self.nasa_power,
            geocoding_service=self.geocoding
        )

        self.providers: Dict[str, BaseWeatherProvider] = {
            self.imd.name: self.imd,
            self.open_meteo.name: self.open_meteo,
            self.openweather.name: self.openweather,
            self.nasa_power.name: self.nasa_power
        }

    async def get_current_weather(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore",
        db_session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Resolves location and returns primary IMD & secondary Open-Meteo observations."""
        res = await self.current_service.fetch_current_weather(lat, lon, location_name, db_session)
        return res.model_dump()

    async def get_forecast(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore",
        days: int = 7,
        db_session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Returns normalized hourly & daily aggregated forecast."""
        res = await self.forecast_service.fetch_forecast(lat, lon, location_name, days, db_session)
        return res.model_dump()

    async def get_alerts(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore",
        active_only: bool = True,
        db_session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Returns official meteorological alerts."""
        res = await self.alert_service.fetch_alerts(lat, lon, location_name, active_only, db_session)
        return res.model_dump()

    async def get_history(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore",
        start_date: str = "2020-01-01",
        end_date: str = "2025-01-01",
        metric: str = "rainfall",
        db_session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Returns historical weather data."""
        res = await self.historical_service.fetch_historical_weather(
            lat, lon, location_name, start_date, end_date, metric, db_session
        )
        return res.model_dump()

    async def get_historical_dataset(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        metric: str = "rainfall",
        db_session: Optional[Session] = None
    ) -> HistoricalWeatherDataset:
        """Returns normalized AI-ready HistoricalWeatherDataset."""
        return await self.historical_service.get_historical_dataset(
            lat, lon, location_name, start_date, end_date, metric, db_session
        )

    async def get_trends(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore",
        start_year: int = 2015,
        end_year: int = 2025,
        metric: str = "temperature"
    ) -> Dict[str, Any]:
        """Returns multi-year climate trend analysis."""
        res = await self.historical_service.fetch_climate_trends(
            lat, lon, location_name, start_year, end_year, metric
        )
        return res.model_dump()

    async def get_ai_weather_input(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore"
    ) -> Tuple[AIWeatherRecord, List[AIForecastItem], List[AIOfficialAlert]]:
        """Provides structured Pydantic input models directly for Person 1's Weather Reasoner."""
        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]

        ai_obs = await self.current_service.get_ai_weather_record(latitude, longitude, loc["name"])
        ai_forecasts = await self.forecast_service.get_ai_forecast_items(latitude, longitude, loc["name"])
        ai_alerts = await self.alert_service.get_ai_official_alerts(latitude, longitude, loc["name"])

        return ai_obs, ai_forecasts, ai_alerts

    async def get_air_quality(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore"
    ) -> Dict[str, Any]:
        """Resolves location and returns real-time ambient Air Quality Index & pollutants."""
        from datetime import datetime, timezone
        import httpx

        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]

        now_utc = datetime.now(timezone.utc).isoformat()
        aqi_val = None
        pm2_5 = None
        pm10 = None
        no2 = None
        so2 = None
        o3 = None
        co = None
        is_available = False

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                url = (
                    f"https://air-quality-api.open-meteo.com/v1/air-quality?"
                    f"latitude={latitude}&longitude={longitude}&"
                    f"current=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi"
                )
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    current = data.get("current", {})
                    if current:
                        pm2_5 = float(current.get("pm2_5")) if current.get("pm2_5") is not None else None
                        pm10 = float(current.get("pm10")) if current.get("pm10") is not None else None
                        co = float(current.get("carbon_monoxide")) if current.get("carbon_monoxide") is not None else None
                        no2 = float(current.get("nitrogen_dioxide")) if current.get("nitrogen_dioxide") is not None else None
                        so2 = float(current.get("sulphur_dioxide")) if current.get("sulphur_dioxide") is not None else None
                        o3 = float(current.get("ozone")) if current.get("ozone") is not None else None
                        raw_aqi = current.get("us_aqi")
                        if raw_aqi is not None:
                            aqi_val = int(raw_aqi)
                            is_available = True
        except Exception:
            is_available = False

        if not is_available or aqi_val is None:
            return {
                "location": loc.get("name", location_name),
                "latitude": latitude,
                "longitude": longitude,
                "aqi": None,
                "category": "Unavailable",
                "primary_pollutant": None,
                "pollutants": {
                    "pm2_5": 0.0,
                    "pm10": 0.0,
                    "no2": 0.0,
                    "so2": 0.0,
                    "o3": 0.0,
                    "co": 0.0
                },
                "recommendations": [
                    "Air quality telemetry is currently unavailable from provider.",
                    "Official CPCB monitoring station telemetry not configured."
                ],
                "source": "Air-quality model: Open-Meteo",
                "source_type": "unavailable",
                "cpcb_status": "CPCB OFFICIAL API ACCESS NOT CONFIGURED",
                "is_official_cpcb": False,
                "is_available": False,
                "status": "UNAVAILABLE",
                "station": None,
                "methodology": "Open-Meteo Atmospheric Chemistry Model (CAMS)",
                "retrieved_at": now_utc
            }

        # Determine category and health recommendations based on verified observation
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

        p_pm25 = pm2_5 if pm2_5 is not None else 0.0
        p_pm10 = pm10 if pm10 is not None else 0.0
        return {
            "location": loc.get("name", location_name),
            "latitude": latitude,
            "longitude": longitude,
            "aqi": aqi_val,
            "category": category,
            "primary_pollutant": "PM2.5" if p_pm25 >= (p_pm10 / 2) else "PM10",
            "pollutants": {
                "pm2_5": round(p_pm25, 1),
                "pm10": round(p_pm10, 1),
                "no2": round(no2, 1) if no2 is not None else 0.0,
                "so2": round(so2, 1) if so2 is not None else 0.0,
                "o3": round(o3, 1) if o3 is not None else 0.0,
                "co": round(co, 1) if co is not None else 0.0
            },
            "recommendations": recs,
            "source": "Air-quality model: Open-Meteo",
            "source_type": "modelled",
            "cpcb_status": "CPCB OFFICIAL API ACCESS NOT CONFIGURED",
            "is_official_cpcb": False,
            "is_available": True,
            "status": "HEALTHY",
            "station": None,
            "methodology": "Open-Meteo Atmospheric Chemistry Model (CAMS)",
            "retrieved_at": now_utc
        }

    # Backward compatibility alias
    fetch_air_quality = get_air_quality

