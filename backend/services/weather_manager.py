"""Master Weather Service Manager.

Orchestrates OpenWeather (Primary), Open-Meteo (Secondary), NASA POWER (Climate/Historical),
CurrentWeatherService, ForecastService, AlertService, and Geocoding services behind a unified architecture.
"""

from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.config.settings import settings
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
        # OpenWeather is the active primary live data source.
        # Open-Meteo is secondary provider.
        # IMDAdapter remains in codebase as a stub/placeholder implementing BaseWeatherProvider,
        # but is not called in the active pipeline until a real IMD_API_KEY is present in config.
        self.openweather = primary_provider if isinstance(primary_provider, OpenWeatherAdapter) else (
            tertiary_provider if isinstance(tertiary_provider, OpenWeatherAdapter) else OpenWeatherAdapter(authority_level="primary_live")
        )
        self.open_meteo = secondary_provider or OpenMeteoAdapter()
        self.imd = primary_provider if isinstance(primary_provider, IMDAdapter) else IMDAdapter()
        self.nasa_power = historical_provider or NasaPowerAdapter()
        self.geocoding = geocoding_service or GeocodingService()

        # If an explicit non-default primary_provider was injected (e.g. In unit tests), honor it
        if primary_provider is not None and not isinstance(primary_provider, IMDAdapter):
            cur_primary = primary_provider
            cur_tertiary = tertiary_provider or self.imd
        elif primary_provider is not None and isinstance(primary_provider, IMDAdapter) and (primary_provider.is_live_configured or getattr(primary_provider, "mode", "") == "test"):
            cur_primary = primary_provider
            cur_tertiary = tertiary_provider or self.openweather
        else:
            cur_primary = self.openweather
            cur_tertiary = self.imd

        self.current_service = CurrentWeatherService(
            primary_provider=cur_primary,
            secondary_provider=self.open_meteo,
            tertiary_provider=cur_tertiary,
            geocoding_service=self.geocoding
        )
        self.forecast_service = ForecastService(
            primary_provider=cur_primary,
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
            self.openweather.name: self.openweather,
            self.open_meteo.name: self.open_meteo,
            self.imd.name: self.imd,
            self.nasa_power.name: self.nasa_power
        }

    @property
    def is_imd_active(self) -> bool:
        """Returns True only when IMD credentials are configured and active."""
        return bool(settings.IMD_API_KEY and self.imd and self.imd.is_live_configured)

    async def get_current_weather(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore",
        db_session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Resolves location and returns primary OpenWeather & secondary Open-Meteo observations."""
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

        # Check for manual CPCB record in database first
        try:
            from backend.db.session import SessionLocal
            from backend.db.models import AirQualityRecord
            from backend.services.weather_reliability import evaluate_weather_freshness, FreshnessClassification

            resolved_loc_name = loc.get("name", location_name).strip()
            with SessionLocal() as db:
                cpcb_record = db.query(AirQualityRecord).filter(
                    AirQualityRecord.source == "CPCB_MANUAL",
                    (AirQualityRecord.station.ilike(f"%{location_name.strip()}%")) |
                    (AirQualityRecord.station.ilike(f"%{resolved_loc_name}%"))
                ).order_by(AirQualityRecord.timestamp.desc()).first()

                if cpcb_record:
                    now_dt = datetime.now(timezone.utc)
                    freshness_enum, age_mins, meta = evaluate_weather_freshness(
                        cpcb_record.timestamp,
                        cpcb_record.uploaded_at,
                        current_time=now_dt
                    )
                    # Never label manual data as automatic, live, or real-time unless genuinely recent (<15 min)
                    is_recent = (age_mins < 15 and freshness_enum == FreshnessClassification.FRESH)
                    freshness_state = "LIVE" if is_recent else freshness_enum.value

                    p_pm25 = cpcb_record.pm2_5 if cpcb_record.pm2_5 is not None else 0.0
                    p_pm10 = cpcb_record.pm10 if cpcb_record.pm10 is not None else 0.0
                    p_no2 = cpcb_record.no2 if cpcb_record.no2 is not None else 0.0
                    p_so2 = cpcb_record.so2 if cpcb_record.so2 is not None else 0.0
                    p_o3 = cpcb_record.o3 if cpcb_record.o3 is not None else 0.0
                    p_co = cpcb_record.co if cpcb_record.co is not None else 0.0

                    final_aqi = int(cpcb_record.aqi) if cpcb_record.aqi is not None else None
                    category = "Unavailable"
                    recs = ["Manual CPCB ground station telemetry available."]
                    if final_aqi is not None:
                        if final_aqi <= 50:
                            category = "Good"
                            recs = [
                                "Air quality is ideal for outdoor activities and exercise.",
                                "Safe for sensitive groups, children, and elderly.",
                                "Normal ventilation recommended."
                            ]
                        elif final_aqi <= 100:
                            category = "Moderate"
                            recs = [
                                "Air quality is acceptable for most outdoor activities.",
                                "Extremely sensitive individuals should limit prolonged outdoor exertion."
                            ]
                        elif final_aqi <= 150:
                            category = "Unhealthy for Sensitive Groups"
                            recs = [
                                "People with respiratory or heart conditions should reduce heavy outdoor exertion.",
                                "Children and active adults should take frequent breaks during outdoor play."
                            ]
                        elif final_aqi <= 200:
                            category = "Unhealthy"
                            recs = [
                                "Everyone may begin to experience minor respiratory discomfort.",
                                "Wear an N95/pollution mask when outdoors. Keep indoor windows closed."
                            ]
                        elif final_aqi <= 300:
                            category = "Very Unhealthy"
                            recs = [
                                "Health alert: The risk of health effects is increased for everyone.",
                                "Avoid prolonged outdoor activities. Use air purifiers indoors."
                            ]
                        else:
                            category = "Hazardous"
                            recs = [
                                "Emergency conditions: Serious risk of respiratory distress.",
                                "Remain indoors and keep all ventilation closed."
                            ]

                    return {
                        "location": resolved_loc_name,
                        "latitude": latitude,
                        "longitude": longitude,
                        "aqi": final_aqi,
                        "category": category,
                        "primary_pollutant": cpcb_record.dominant_pollutant or ("PM2.5" if p_pm25 >= (p_pm10 / 2) else "PM10"),
                        "pollutants": {
                            "pm2_5": round(p_pm25, 1),
                            "pm10": round(p_pm10, 1),
                            "no2": round(p_no2, 1),
                            "so2": round(p_so2, 1),
                            "o3": round(p_o3, 1),
                            "co": round(p_co, 1)
                        },
                        "recommendations": recs,
                        "source": "CPCB_MANUAL",
                        "source_identity": "CPCB_MANUAL",
                        "source_type": "manual_cpcb",
                        "cpcb_status": f"CPCB Ground Station Export: {cpcb_record.station}",
                        "is_official_cpcb": True,
                        "is_available": True,
                        "status": freshness_state,
                        "freshness": freshness_state,
                        "is_real_time": is_recent,
                        "observed_at": cpcb_record.timestamp.isoformat(),
                        "station": cpcb_record.station,
                        "methodology": "Manual CPCB Ground Monitoring Station Export",
                        "retrieved_at": cpcb_record.uploaded_at.isoformat()
                    }
        except Exception:
            pass

        # 2. Active Primary Provider: Query OpenWeather Air Pollution API
        try:
            ow_res = await self.openweather.get_air_quality(latitude, longitude, loc.get("name", location_name))
            if ow_res:
                is_avail = ow_res.get("is_available") if isinstance(ow_res, dict) else getattr(ow_res, "is_available", True)
                if is_avail:
                    return ow_res if isinstance(ow_res, dict) else ow_res.model_dump()
        except Exception:
            pass

        # 3. Secondary Provider Fallback: Query Open-Meteo Air Quality API
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
                "source": "OpenWeather",
                "source_identity": "OpenWeather",
                "source_type": "unavailable",
                "cpcb_status": "CPCB OFFICIAL API ACCESS NOT CONFIGURED",
                "is_official_cpcb": False,
                "is_available": False,
                "status": "UNAVAILABLE",
                "station": None,
                "methodology": "OpenWeather Air Pollution Chemical Transport Model",
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
            "source": "Open-Meteo",
            "source_identity": "Open-Meteo",
            "source_type": "modelled",
            "cpcb_status": "CPCB OFFICIAL API ACCESS NOT CONFIGURED (Served via Open-Meteo)",
            "is_official_cpcb": False,
            "is_available": True,
            "status": "HEALTHY",
            "station": None,
            "methodology": "Open-Meteo Atmospheric Chemistry Model (CAMS)",
            "retrieved_at": now_utc
        }

    # Backward compatibility alias
    fetch_air_quality = get_air_quality

