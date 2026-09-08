"""Master Weather Service Manager.

Orchestrates IMD (Primary), Open-Meteo (Secondary), NASA POWER (Climate/Historical),
CurrentWeatherService, and Geocoding services behind a unified architecture.
"""

from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.nasa_power_adapter import NasaPowerAdapter
from backend.services.geocoding_service import GeocodingService
from backend.services.current_weather_service import CurrentWeatherService
from backend.services.base_provider import BaseWeatherProvider
from ai.models import (
    WeatherRecord as AIWeatherRecord,
    ForecastItem as AIForecastItem,
    OfficialAlert as AIOfficialAlert
)


class WeatherManager:
    """Master Weather Service orchestrating provider adapters, geocoding, and AI conversion."""

    def __init__(
        self,
        primary_provider: Optional[BaseWeatherProvider] = None,
        secondary_provider: Optional[BaseWeatherProvider] = None,
        historical_provider: Optional[BaseWeatherProvider] = None,
        geocoding_service: Optional[GeocodingService] = None
    ):
        self.imd = primary_provider or IMDAdapter()
        self.open_meteo = secondary_provider or OpenMeteoAdapter()
        self.nasa_power = historical_provider or NasaPowerAdapter()
        self.geocoding = geocoding_service or GeocodingService()
        self.current_service = CurrentWeatherService(
            primary_provider=self.imd,
            secondary_provider=self.open_meteo,
            geocoding_service=self.geocoding
        )

        self.providers: Dict[str, BaseWeatherProvider] = {
            self.imd.name: self.imd,
            self.open_meteo.name: self.open_meteo,
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
        location_name: str = "Coimbatore"
    ) -> Dict[str, Any]:
        """Returns weather forecast."""
        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]

        forecast_items = await self.imd.get_forecast(latitude, longitude, loc["name"])
        return {
            "location": loc["name"],
            "latitude": latitude,
            "longitude": longitude,
            "forecast": [item.model_dump() for item in forecast_items],
            "source": self.imd.name
        }

    async def get_alerts(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore"
    ) -> Dict[str, Any]:
        """Returns official meteorological alerts."""
        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]

        alerts = await self.imd.get_official_alerts(latitude, longitude, loc["name"])
        return {
            "location": loc["name"],
            "alerts": [alert.model_dump() for alert in alerts],
            "source": f"{self.imd.name} Official"
        }

    async def get_history(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore",
        start_date: str = "2020-01-01",
        end_date: str = "2025-01-01",
        metric: str = "rainfall"
    ) -> Dict[str, Any]:
        """Returns historical weather data."""
        loc = await self.geocoding.resolve_location(location_name)
        hist = await self.nasa_power.get_historical_weather(
            loc["latitude"], loc["longitude"], start_date, end_date, metric
        )
        return hist.model_dump()

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
        loc = await self.geocoding.resolve_location(location_name)
        trends = await self.nasa_power.get_climate_trend(
            loc["latitude"], loc["longitude"], start_year, end_year, metric
        )
        return trends.model_dump()

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
        forecasts = await self.imd.get_forecast(latitude, longitude, loc["name"])
        alerts = await self.imd.get_official_alerts(latitude, longitude, loc["name"])

        ai_forecasts = [f.to_ai_forecast_item() for f in forecasts]
        ai_alerts = [a.to_ai_official_alert() for a in alerts]

        return ai_obs, ai_forecasts, ai_alerts
