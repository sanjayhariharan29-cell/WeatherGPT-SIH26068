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
        db_session: Optional[Session] = None,
        allow_stale: bool = False
    ) -> CurrentWeatherResponse:
        """Fetches, normalizes, compares, and optionally persists current weather observations."""
        self.validate_coordinates(lat, lon)

        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]
        resolved_name = loc["name"]

        # 1. Fetch Primary & Secondary Observations with failover and resilient caching
        is_primary_healthy = True
        is_secondary_healthy = True
        primary_diag: Optional[Dict[str, Any]] = None
        source_label = f"{self.primary.name} (Primary), {self.secondary.name} (Secondary)"
        provider_status = "HEALTHY"

        primary_obs: Optional[NormalizedWeatherObservation] = None
        sec_obs: Optional[NormalizedWeatherObservation] = None
        cache_key = f"current_obs_{resolved_name}_{latitude}_{longitude}"

        from backend.services.cache import provider_cache

        try:
            primary_obs = await self.primary.get_current_weather(latitude, longitude, resolved_name)
            is_primary_healthy = True
        except ProviderError as e:
            is_primary_healthy = False
            primary_diag = {
                "failed_provider": self.primary.name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "timestamp": getattr(e, "timestamp", datetime.now(timezone.utc).isoformat()),
                "diagnostics": getattr(e, "diagnostics", {})
            }
            provider_status = "DEGRADED"

        if is_primary_healthy:
            # Primary succeeded -> fetch secondary for multi-source agreement metric
            try:
                sec_obs = await self.secondary.get_current_weather(latitude, longitude, resolved_name)
                is_secondary_healthy = True
                source_label = f"{self.primary.name} (Primary), {self.secondary.name} (Secondary)"
            except Exception:
                is_secondary_healthy = False
                source_label = f"{self.primary.name} (Primary)"
                provider_status = "DEGRADED"
                sec_obs = None
        else:
            # Primary failed -> failover to secondary as observation
            try:
                primary_obs = await self.secondary.get_current_weather(latitude, longitude, resolved_name)
                is_secondary_healthy = True
                source_label = f"{self.secondary.name} (Fallback)"
                sec_obs = primary_obs
            except Exception:
                is_secondary_healthy = False
                sec_obs = None

        # Handle outage when both providers fail
        if not is_primary_healthy and not is_secondary_healthy:
            from backend.services.exceptions import ProviderUnavailableError
            if allow_stale:
                cached_val, is_fresh_cache, cache_age = provider_cache.get_with_metadata(cache_key, max_stale_seconds=7200)
                if not cached_val:
                    cached_val, is_fresh_cache, cache_age = provider_cache.get_with_metadata(
                        f"imd_current_{resolved_name}_{latitude}_{longitude}", max_stale_seconds=7200
                    )
                if not cached_val:
                    cached_val, is_fresh_cache, cache_age = provider_cache.get_with_metadata(
                        f"openmeteo_current_{resolved_name}_{latitude}_{longitude}", max_stale_seconds=7200
                    )

                if cached_val:
                    primary_obs = cached_val
                    primary_obs.is_cached = True
                    primary_obs.cache_age_seconds = cache_age
                    source_label = f"{cached_val.source} (Cached Telemetry)"
                    provider_status = "UNAVAILABLE"
                else:
                    raise ProviderUnavailableError(
                        "All weather providers are unavailable and no usable cached observation exists.",
                        provider_name="All Providers",
                        diagnostics=primary_diag or {}
                    )
            else:
                sec_name = getattr(self.secondary, "name", "Open-Meteo")
                raise ProviderUnavailableError(
                    f"All weather providers are unavailable: {self.primary.name} and {sec_name}",
                    provider_name=sec_name,
                    diagnostics=primary_diag or {}
                )
        else:
            # Store successfully retrieved observation for future degraded/offline resilience
            if primary_obs:
                provider_cache.set(cache_key, primary_obs)

        # 2. Extract comparison data
        if sec_obs:
            sec_temp = sec_obs.temperature_c
            sec_rain = sec_obs.rain_probability_pct
        else:
            sec_temp = primary_obs.temperature_c
            sec_rain = primary_obs.rain_probability_pct

        # 3. Multi-source agreement evaluation using canonical ai.reasoner.agreement
        from ai.reasoner.agreement import evaluate_source_agreement
        from ai.models import SourceAgreementEnum

        primary_ai_rec = primary_obs.to_ai_weather_record()
        secondary_ai_rec = sec_obs.to_ai_weather_record() if sec_obs else None

        agr_status, agr_text = evaluate_source_agreement(primary_ai_rec, secondary_ai_rec)
        sources_agree = (agr_status in (SourceAgreementEnum.HIGH, SourceAgreementEnum.SINGLE_SOURCE))

        if agr_status == SourceAgreementEnum.HIGH:
            confidence_level = "HIGH"
            disagreement_notes = None
        elif agr_status in (SourceAgreementEnum.MODERATE, SourceAgreementEnum.MEDIUM):
            confidence_level = "MEDIUM"
            disagreement_notes = agr_text
        elif agr_status == SourceAgreementEnum.SINGLE_SOURCE:
            confidence_level = "HIGH"
            disagreement_notes = None
        else:
            confidence_level = "CAUTIOUS"
            disagreement_notes = agr_text

        # 4. Freshness, Completeness, and System State evaluation
        from backend.services.weather_reliability import (
            evaluate_weather_freshness,
            validate_weather_completeness,
            determine_system_state,
            FreshnessClassification,
            SystemStateEnum
        )

        fresh_class, obs_age_min, fresh_meta = evaluate_weather_freshness(
            observed_at=primary_obs.observed_at,
            retrieved_at=primary_obs.retrieved_at,
            is_cached=getattr(primary_obs, "is_cached", False),
            cache_age_seconds=getattr(primary_obs, "cache_age_seconds", None)
        )

        comp_class, val_class, val_issues = validate_weather_completeness(primary_obs.model_dump())

        derived_state = determine_system_state(
            is_primary_healthy=is_primary_healthy,
            is_secondary_healthy=is_secondary_healthy,
            is_cached=getattr(primary_obs, "is_cached", False),
            freshness=fresh_class
        ).value

        # Update primary_obs reliability fields
        primary_obs.freshness_status = fresh_class.value
        primary_obs.completeness_status = comp_class.value
        primary_obs.validation_status = val_class.value
        primary_obs.validation_issues = val_issues
        primary_obs.provider_status = provider_status
        primary_obs.provider_diagnostics = primary_diag

        # 5. Fetch Official Severe Alerts (IMD is strictly authoritative)
        try:
            alerts = await self.primary.get_official_alerts(latitude, longitude, resolved_name)
            alert_dicts = [a.model_dump() for a in alerts]
        except Exception:
            alert_dicts = []

        # 6. Optional Database Persistence with 5-minute deduplication window
        if db_session is not None:
            self._persist_observation(db_session, primary_obs)

        # 7. Build and return structured response contract
        data_freshness_str = "FRESH" if fresh_class == FreshnessClassification.FRESH else ("STALE_DEGRADED" if fresh_class == FreshnessClassification.STALE else "CACHED")

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
                sources_agree=sources_agree,
                confidence_level=confidence_level,
                disagreement_notes=disagreement_notes
            ),
            alerts=alert_dicts,
            source=source_label,
            units=WeatherUnitsSchema(),
            observed_at=primary_obs.observed_at,
            retrieved_at=primary_obs.retrieved_at,
            data_freshness=data_freshness_str,
            freshness_status=fresh_class.value,
            completeness_status=comp_class.value,
            validation_status=val_class.value,
            validation_issues=val_issues,
            is_cached=getattr(primary_obs, "is_cached", False),
            cache_age_seconds=getattr(primary_obs, "cache_age_seconds", None),
            provider_status=provider_status,
            provider_diagnostics=primary_diag,
            system_state=derived_state
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
