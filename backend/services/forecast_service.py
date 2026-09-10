"""Forecast Engine Service.

Dedicated service layer for retrieving, normalizing, aggregating (hourly & daily),
validating, persisting, and converting multi-day weather forecasts across primary (IMD)
and secondary (Open-Meteo) adapters.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import defaultdict
from sqlalchemy.orm import Session

from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.geocoding_service import GeocodingService
from backend.services.base_provider import BaseWeatherProvider
from backend.services.exceptions import ProviderError
from backend.services.schemas import NormalizedForecastItem
from backend.schemas.weather import (
    ForecastResponse,
    ForecastItemSchema,
    DailyForecastItemSchema,
    WeatherUnitsSchema
)
from backend.db.models import Forecast as DBForecast
from ai.models import ForecastItem as AIForecastItem


class ForecastService:
    """Service layer managing multi-day forecast retrieval, daily aggregation, failover, and DB snapshotting."""

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

    async def fetch_forecast(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore",
        days: int = 7,
        db_session: Optional[Session] = None
    ) -> ForecastResponse:
        """Fetches, normalizes, aggregates hourly/daily forecasts, and optionally persists snapshots."""
        self.validate_coordinates(lat, lon)

        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]
        resolved_name = loc["name"]

        # 1. Fetch Primary Forecast (IMD) with failover to Secondary (Open-Meteo)
        source_label = self.primary.name
        primary_diag = None
        system_state_val = "ONLINE"
        try:
            raw_items = await self.primary.get_forecast(latitude, longitude, resolved_name)
        except ProviderError as e:
            primary_diag = {
                "failed_provider": self.primary.name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "timestamp": getattr(e, "timestamp", datetime.now(timezone.utc).isoformat()),
                "diagnostics": getattr(e, "diagnostics", {})
            }
            system_state_val = "DEGRADED"
            raw_items = await self.secondary.get_forecast(latitude, longitude, resolved_name)
            source_label = f"{self.secondary.name} (Fallback)"

        now_utc = datetime.now(timezone.utc).isoformat()
        issued_at_timestamp = raw_items[0].issued_at if raw_items else now_utc

        # 2. Build Hourly Forecast Items
        hourly_schemas: List[ForecastItemSchema] = []
        for item in raw_items:
            hourly_schemas.append(
                ForecastItemSchema(
                    forecast_time=item.forecast_time,
                    forecast_for=item.forecast_for or item.issued_at,
                    temperature=item.temperature_c,
                    temp_min=item.temp_min_c,
                    temp_max=item.temp_max_c,
                    rain_probability=item.rain_probability_pct,
                    rainfall_mm=item.rainfall_mm,
                    humidity=item.humidity_pct,
                    wind_speed=item.wind_speed_kmh,
                    wind_direction_deg=item.wind_direction_deg,
                    condition=item.condition,
                    source=item.source,
                    issued_at=item.issued_at,
                    retrieved_at=item.retrieved_at
                )
            )

        # 3. Aggregate Daily Forecast Summaries
        daily_schemas = self._aggregate_daily_forecast(hourly_schemas, source_label, issued_at_timestamp)

        # 4. Optional Database Persistence with Deduplication
        if db_session is not None:
            self._persist_forecasts(db_session, resolved_name, latitude, longitude, hourly_schemas)

        # 5. Build and return structured ForecastResponse contract
        return ForecastResponse(
            location=resolved_name,
            latitude=latitude,
            longitude=longitude,
            hourly_forecast=hourly_schemas,
            forecast=hourly_schemas,  # Alias for 100% frontend component compatibility
            daily_forecast=daily_schemas,
            days_count=min(max(days, 1), 7),
            source=source_label,
            units=WeatherUnitsSchema(),
            issued_at=issued_at_timestamp,
            retrieved_at=now_utc,
            system_state=system_state_val
        )

    def _aggregate_daily_forecast(
        self,
        hourly_items: List[ForecastItemSchema],
        source: str,
        issued_at: str
    ) -> List[DailyForecastItemSchema]:
        """Groups hourly forecast items by date to produce aggregated daily summaries."""
        date_groups: Dict[str, List[ForecastItemSchema]] = defaultdict(list)

        for item in hourly_items:
            try:
                dt = datetime.fromisoformat(item.forecast_for)
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            date_groups[date_str].append(item)

        daily_summaries: List[DailyForecastItemSchema] = []
        for date_str, items in date_groups.items():
            temps = [i.temperature for i in items]
            rain_probs = [i.rain_probability for i in items]
            rainfalls = [i.rainfall_mm for i in items]
            winds = [i.wind_speed for i in items]

            min_t = min([i.temp_min for i in items if i.temp_min is not None] or temps)
            max_t = max([i.temp_max for i in items if i.temp_max is not None] or temps)
            peak_rain_prob = max(rain_probs) if rain_probs else 0.0
            total_rain = sum(rainfalls)
            max_w = max(winds) if winds else 0.0

            # Determine dominant condition (highest rain probability or first item)
            dominant_item = max(items, key=lambda x: x.rain_probability) if items else items[0]
            dominant_condition = dominant_item.condition

            daily_summaries.append(
                DailyForecastItemSchema(
                    date=date_str,
                    temperature_min=min_t,
                    temperature_max=max_t,
                    rain_probability=peak_rain_prob,
                    total_rainfall_mm=total_rain,
                    max_wind_speed=max_w,
                    condition=dominant_condition,
                    source=source,
                    issued_at=issued_at
                )
            )

        return daily_summaries

    def _persist_forecasts(
        self,
        db: Session,
        location_name: str,
        lat: float,
        lon: float,
        items: List[ForecastItemSchema]
    ) -> None:
        """Persists forecast items to database with deduplication on location & target time."""
        try:
            for item in items:
                try:
                    target_dt = datetime.fromisoformat(item.forecast_for)
                except Exception:
                    target_dt = datetime.now(timezone.utc)

                existing = db.query(DBForecast).filter(
                    DBForecast.location_name == location_name,
                    DBForecast.forecast_time == target_dt
                ).first()

                if not existing:
                    rec = DBForecast(
                        location_name=location_name,
                        latitude=lat,
                        longitude=lon,
                        forecast_time=target_dt,
                        temperature=item.temperature,
                        rain_probability=item.rain_probability,
                        wind_speed=item.wind_speed,
                        condition=item.condition,
                        source=item.source
                    )
                    db.add(rec)
            db.commit()
        except Exception:
            db.rollback()

    async def get_ai_forecast_items(
        self,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        location_name: str = "Coimbatore"
    ) -> List[AIForecastItem]:
        """Converts forecast items directly to Person 1's AIForecastItem list."""
        res = await self.fetch_forecast(lat, lon, location_name)
        return [
            AIForecastItem(
                time=item.forecast_time,
                temperature=item.temperature,
                rain_probability=item.rain_probability,
                wind_speed=item.wind_speed,
                condition=item.condition,
                rainfall_amount_mm=item.rainfall_mm
            )
            for item in res.hourly_forecast
        ]
