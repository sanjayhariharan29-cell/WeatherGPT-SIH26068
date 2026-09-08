"""Current Weather Service.

Dedicated service layer for retrieving, normalizing, validating, persisting,
and converting current weather observations across primary (IMD) and secondary (Open-Meteo) providers.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.geocoding_service import GeocodingService
from backend.services.base_provider import BaseWeatherProvider
from backend.services.exceptions import ProviderError
from backend.services.schemas import NormalizedWeatherObservation
from backend.schemas.weather import (
    CurrentWeatherResponse,
    LocationDataSchema,
    WeatherDataSchema,
    ComparisonDataSchema,
    WeatherUnitsSchema
)
from backend.db.models import WeatherRecord
from ai.models import WeatherRecord as AIWeatherRecord, LocationInfo as AILocationInfo


class CurrentWeatherService:
    """Service layer managing current weather retrieval, failover, validation, and DB persistence."""

    def __init__(
        self,
        primary_provider: Optional[BaseWeatherProvider] = None,
        secondary_provider: Optional[BaseWeatherProvider] = None,
        geocoding_service: Optional[GeocodingService] = None
    ):
        self.primary = primary_provider or IMDAdapter()
        self.secondary = secondary_provider or OpenMeteoAdapter()
        self.geocoding = geocoding_service or GeocodingService()

    def validate_coordinates(self, lat: Optional[float], lon: Optional[float]) -> None:
        """Validates latitude and longitude numeric bounds."""
        if lat is not None:
            if not isinstance(lat, (int, float)) or lat < -90.0 or lat > 90.0:
                raise ValueError(f"Invalid latitude {lat}. Latitude must be between -90 and +90 degrees.")

        if lon is not None:
            if not isinstance(lon, (int, float)) or lon < -180.0 or lon > 180.0:
                raise ValueError(f"Invalid longitude {lon}. Longitude must be between -180 and +180 degrees.")

    async def fetch_current_weather(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore",
        db_session: Optional[Session] = None
    ) -> CurrentWeatherResponse:
        """Fetches, normalizes, compares, and optionally persists current weather observations."""
        self.validate_coordinates(lat, lon)

        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]
        resolved_name = loc["name"]

        # 1. Fetch Primary Observation (IMD) with failover to Secondary (Open-Meteo)
        source_label = f"{self.primary.name} (Primary), {self.secondary.name} (Secondary)"
        try:
            primary_obs = await self.primary.get_current_weather(latitude, longitude, resolved_name)
        except ProviderError:
            # Primary provider unavailable -> Failover to secondary provider
            primary_obs = await self.secondary.get_current_weather(latitude, longitude, resolved_name)
            source_label = f"{self.secondary.name} (Fallback)"

        # 2. Fetch Secondary Observation for multi-source agreement metric
        try:
            sec_obs = await self.secondary.get_current_weather(latitude, longitude, resolved_name)
            sec_temp = sec_obs.temperature_c
            sec_rain = sec_obs.rain_probability_pct
        except Exception:
            sec_temp = primary_obs.temperature_c
            sec_rain = primary_obs.rain_probability_pct

        sources_agree = abs(primary_obs.rain_probability_pct - sec_rain) <= 20.0

        # 3. Fetch Official Severe Alerts
        try:
            alerts = await self.primary.get_official_alerts(latitude, longitude, resolved_name)
            alert_dicts = [a.model_dump() for a in alerts]
        except Exception:
            alert_dicts = []

        # 4. Optional Database Persistence with 5-minute deduplication window
        if db_session is not None:
            self._persist_observation(db_session, primary_obs)

        # 5. Build and return structured response contract
        return CurrentWeatherResponse(
            location=LocationDataSchema(
                name=resolved_name,
                latitude=latitude,
                longitude=longitude,
                district=loc.get("district"),
                state=loc.get("state")
            ),
            weather=WeatherDataSchema(
                temperature=primary_obs.temperature_c,
                feels_like=primary_obs.feels_like_c,
                humidity=primary_obs.humidity_pct,
                rain_probability=primary_obs.rain_probability_pct,
                wind_speed=primary_obs.wind_speed_kmh,
                condition=primary_obs.condition,
                rainfall_mm=primary_obs.rainfall_mm
            ),
            comparison=ComparisonDataSchema(
                secondary_temperature=sec_temp,
                secondary_rain_probability=sec_rain,
                sources_agree=sources_agree
            ),
            alerts=alert_dicts,
            source=source_label,
            units=WeatherUnitsSchema(),
            observed_at=primary_obs.observed_at,
            retrieved_at=primary_obs.retrieved_at
        )

    def _persist_observation(self, db: Session, obs: NormalizedWeatherObservation) -> None:
        """Persists observation to database with deduplication within 5 minutes."""
        try:
            now = datetime.now(timezone.utc)
            five_mins_ago = now - timedelta(minutes=5)

            existing = db.query(WeatherRecord).filter(
                WeatherRecord.location_name == obs.location_name,
                WeatherRecord.observed_at >= five_mins_ago
            ).first()

            if not existing:
                record = WeatherRecord(
                    location_name=obs.location_name,
                    latitude=obs.latitude,
                    longitude=obs.longitude,
                    temperature=obs.temperature_c,
                    humidity=obs.humidity_pct,
                    rain_probability=obs.rain_probability_pct,
                    wind_speed=obs.wind_speed_kmh,
                    condition=obs.condition,
                    source=obs.source
                )
                db.add(record)
                db.commit()
        except Exception:
            db.rollback()

    async def get_ai_weather_record(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore"
    ) -> AIWeatherRecord:
        """Converts current observation directly to Person 1's AI WeatherRecord model."""
        res = await self.fetch_current_weather(lat, lon, location_name)
        return AIWeatherRecord(
            location=AILocationInfo(
                name=res.location.name,
                latitude=res.location.latitude,
                longitude=res.location.longitude
            ),
            observed_at=datetime.fromisoformat(res.observed_at),
            retrieved_at=datetime.fromisoformat(res.retrieved_at),
            temperature=res.weather.temperature,
            humidity=res.weather.humidity,
            rain_probability=res.weather.rain_probability,
            wind_speed=res.weather.wind_speed,
            weather_condition=res.weather.condition,
            source=res.source,
            rainfall_amount_mm=res.weather.rainfall_mm
        )
