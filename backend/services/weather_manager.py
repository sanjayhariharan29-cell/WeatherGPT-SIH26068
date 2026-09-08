from typing import Dict, Any, List, Optional
from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.nasa_power_adapter import NasaPowerAdapter
from backend.services.geocoding_service import GeocodingService

class WeatherManager:
    """Master Weather Service orchestrating IMD, secondary forecast adapters, geocoding, and historical climate analytics."""

    def __init__(self):
        self.imd = IMDAdapter()
        self.open_meteo = OpenMeteoAdapter()
        self.nasa_power = NasaPowerAdapter()
        self.geocoding = GeocodingService()

    async def get_current_weather(self, lat: Optional[float] = None, lon: Optional[float] = None, location_name: str = "Coimbatore") -> Dict[str, Any]:
        """Resolves location coordinates and returns current IMD & Open-Meteo observations."""
        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]
        resolved_name = loc["name"]

        imd_data = await self.imd.get_current_weather(latitude, longitude, resolved_name)
        open_meteo_data = await self.open_meteo.get_current_weather(latitude, longitude, resolved_name)
        alerts = await self.imd.get_official_alerts(latitude, longitude, resolved_name)

        return {
            "location": loc,
            "weather": {
                "temperature": imd_data["temperature"],
                "humidity": imd_data["humidity"],
                "rain_probability": imd_data["rain_probability"],
                "wind_speed": imd_data["wind_speed"],
                "condition": imd_data["condition"]
            },
            "comparison": {
                "secondary_temperature": open_meteo_data["temperature"],
                "secondary_rain_probability": open_meteo_data["rain_probability"],
                "sources_agree": abs(imd_data["rain_probability"] - open_meteo_data["rain_probability"]) <= 20
            },
            "alerts": alerts,
            "source": "IMD (Primary), Open-Meteo (Secondary)",
            "observed_at": imd_data["observed_at"],
            "retrieved_at": imd_data["retrieved_at"]
        }

    async def get_forecast(self, lat: Optional[float] = None, lon: Optional[float] = None, location_name: str = "Coimbatore") -> Dict[str, Any]:
        """Returns location forecast."""
        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]

        forecast_list = await self.imd.get_forecast(latitude, longitude, loc["name"])
        return {
            "location": loc["name"],
            "latitude": latitude,
            "longitude": longitude,
            "forecast": forecast_list,
            "source": "IMD"
        }

    async def get_alerts(self, lat: Optional[float] = None, lon: Optional[float] = None, location_name: str = "Coimbatore") -> Dict[str, Any]:
        """Returns official meteorological alerts."""
        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]

        alerts = await self.imd.get_official_alerts(latitude, longitude, loc["name"])
        return {
            "location": loc["name"],
            "alerts": alerts,
            "source": "IMD Official"
        }

    async def get_history(self, lat: Optional[float] = None, lon: Optional[float] = None, location_name: str = "Coimbatore", start_date: str = "2020-01-01", end_date: str = "2025-01-01", metric: str = "rainfall") -> Dict[str, Any]:
        """Returns historical weather data."""
        loc = await self.geocoding.resolve_location(location_name)
        return await self.nasa_power.get_historical_weather(loc["latitude"], loc["longitude"], start_date, end_date, metric)

    async def get_trends(self, lat: Optional[float] = None, lon: Optional[float] = None, location_name: str = "Coimbatore", start_year: int = 2015, end_year: int = 2025, metric: str = "temperature") -> Dict[str, Any]:
        """Returns multi-year climate trend analysis."""
        loc = await self.geocoding.resolve_location(location_name)
        return await self.nasa_power.get_climate_trend(loc["latitude"], loc["longitude"], start_year, end_year, metric)
