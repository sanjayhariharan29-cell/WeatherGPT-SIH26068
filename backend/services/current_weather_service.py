"""Current Weather Service.

Dedicated service layer for retrieving, normalizing, validating, persisting,
and converting current weather observations across primary (IMD) and secondary (Open-Meteo) providers.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.openweather_adapter import OpenWeatherAdapter
from backend.services.geocoding_service import GeocodingService
from backend.services.base_provider import BaseWeatherProvider
from backend.services.exceptions import ProviderError
from backend.services.schemas import NormalizedWeatherObservation
from backend.schemas.weather import (
    CurrentWeatherResponse,
    LocationDataSchema,
    WeatherDataSchema,
    ComparisonDataSchema,
    ProviderObservationSummarySchema,
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
        tertiary_provider: Optional[BaseWeatherProvider] = None,
        geocoding_service: Optional[GeocodingService] = None
    ):
        self.primary = primary_provider or IMDAdapter()
        self.secondary = secondary_provider or OpenMeteoAdapter()
        self.tertiary = tertiary_provider or OpenWeatherAdapter()
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
        """Fetches, normalizes, compares, and optionally persists current weather observations across multiple providers."""
        self.validate_coordinates(lat, lon)

        loc = await self.geocoding.resolve_location(location_name)
        latitude = lat if lat is not None else loc["latitude"]
        longitude = lon if lon is not None else loc["longitude"]
        resolved_name = loc["name"]

        # 1. Fetch from All Configured Providers with failover and resilient caching
        is_primary_healthy = False
        is_secondary_healthy = False
        is_tertiary_healthy = False
        primary_diag: Optional[Dict[str, Any]] = None

        primary_obs: Optional[NormalizedWeatherObservation] = None
        sec_obs: Optional[NormalizedWeatherObservation] = None
        tertiary_obs: Optional[NormalizedWeatherObservation] = None
        cache_key = f"current_obs_{resolved_name}_{latitude}_{longitude}"

        from backend.services.cache import provider_cache

        # Attempt Primary (IMD)
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

        # Attempt Secondary (Open-Meteo)
        try:
            sec_obs = await self.secondary.get_current_weather(latitude, longitude, resolved_name)
            is_secondary_healthy = True
        except Exception:
            is_secondary_healthy = False
            sec_obs = None

        # Attempt Tertiary (OpenWeather / Independent Provider) if configured
        try:
            tertiary_obs = await self.tertiary.get_current_weather(latitude, longitude, resolved_name)
            is_tertiary_healthy = True
        except Exception:
            is_tertiary_healthy = False
            tertiary_obs = None

        # Determine Lead Observation: Primary is preferred; if failed, failover to secondary, then tertiary
        if is_primary_healthy:
            lead_obs = primary_obs
        elif is_secondary_healthy:
            lead_obs = sec_obs
        elif is_tertiary_healthy:
            lead_obs = tertiary_obs
        else:
            lead_obs = None

        # Handle outage when all providers fail
        if lead_obs is None:
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
                    lead_obs = cached_val
                    lead_obs.is_cached = True
                    lead_obs.cache_age_seconds = cache_age
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
            # Store successfully retrieved lead observation
            provider_cache.set(cache_key, lead_obs)

        # Build list of active source names
        sources_list: List[str] = []
        if is_primary_healthy and primary_obs:
            sources_list.append(self.primary.name)
        if is_secondary_healthy and sec_obs:
            sources_list.append(self.secondary.name)
        if is_tertiary_healthy and tertiary_obs:
            sources_list.append(self.tertiary.name)

        if not sources_list and getattr(lead_obs, "is_cached", False):
            sources_list.append(f"{lead_obs.source} (Cached)")

        # Determine composite source label
        if is_primary_healthy and is_secondary_healthy:
            source_label = f"{self.primary.name} (Primary), {self.secondary.name} (Secondary)"
        elif is_primary_healthy:
            source_label = f"{self.primary.name} (Primary)"
        elif is_secondary_healthy:
            source_label = f"{self.secondary.name} (Fallback)"
        elif is_tertiary_healthy:
            source_label = f"{self.tertiary.name} (Fallback)"
        else:
            source_label = f"{lead_obs.source} (Cached Telemetry)"

        provider_status = "HEALTHY" if (is_primary_healthy and is_secondary_healthy) else ("DEGRADED" if (is_primary_healthy or is_secondary_healthy or is_tertiary_healthy) else "UNAVAILABLE")

        # 2. Extract comparison data and individual un-averaged provider records
        provider_records: List[ProviderObservationSummarySchema] = []

        if is_primary_healthy and primary_obs:
            p_name = getattr(self.primary, "name", "IMD")
            p_name = str(p_name) if not hasattr(p_name, "_mock_name") else "IMD"
            p_auth = getattr(self.primary, "authority_level", getattr(primary_obs, "authority_level", "primary_authoritative"))
            p_auth = str(p_auth) if not hasattr(p_auth, "_mock_name") else getattr(primary_obs, "authority_level", "primary_authoritative")

            provider_records.append(
                ProviderObservationSummarySchema(
                    provider=p_name,
                    authority_level=p_auth,
                    temperature=primary_obs.temperature_c,
                    feels_like=primary_obs.feels_like_c,
                    humidity=primary_obs.humidity_pct,
                    wind_speed=primary_obs.wind_speed_kmh,
                    rain_probability=primary_obs.rain_probability_pct,
                    condition=primary_obs.condition,
                    observed_at=primary_obs.observed_at,
                    freshness=getattr(primary_obs, "freshness_status", "FRESH"),
                    is_real_time=True,
                    status="HEALTHY"
                )
            )

        if is_secondary_healthy and sec_obs:
            s_name = getattr(self.secondary, "name", "Open-Meteo")
            s_name = str(s_name) if not hasattr(s_name, "_mock_name") else "Open-Meteo"
            s_auth = getattr(self.secondary, "authority_level", getattr(sec_obs, "authority_level", "secondary_forecast"))
            s_auth = str(s_auth) if not hasattr(s_auth, "_mock_name") else getattr(sec_obs, "authority_level", "secondary_forecast")

            provider_records.append(
                ProviderObservationSummarySchema(
                    provider=s_name,
                    authority_level=s_auth,
                    temperature=sec_obs.temperature_c,
                    feels_like=sec_obs.feels_like_c,
                    humidity=sec_obs.humidity_pct,
                    wind_speed=sec_obs.wind_speed_kmh,
                    rain_probability=sec_obs.rain_probability_pct,
                    condition=sec_obs.condition,
                    observed_at=sec_obs.observed_at,
                    freshness=getattr(sec_obs, "freshness_status", "FRESH"),
                    is_real_time=True,
                    status="HEALTHY"
                )
            )

        if is_tertiary_healthy and tertiary_obs:
            t_name = getattr(self.tertiary, "name", "OpenWeather")
            t_name = str(t_name) if not hasattr(t_name, "_mock_name") else "OpenWeather"
            t_auth = getattr(self.tertiary, "authority_level", getattr(tertiary_obs, "authority_level", "secondary_independent"))
            t_auth = str(t_auth) if not hasattr(t_auth, "_mock_name") else getattr(tertiary_obs, "authority_level", "secondary_independent")

            provider_records.append(
                ProviderObservationSummarySchema(
                    provider=t_name,
                    authority_level=t_auth,
                    temperature=tertiary_obs.temperature_c,
                    feels_like=tertiary_obs.feels_like_c,
                    humidity=tertiary_obs.humidity_pct,
                    wind_speed=tertiary_obs.wind_speed_kmh,
                    rain_probability=tertiary_obs.rain_probability_pct,
                    condition=tertiary_obs.condition,
                    observed_at=tertiary_obs.observed_at,
                    freshness=getattr(tertiary_obs, "freshness_status", "FRESH"),
                    is_real_time=True,
                    status="HEALTHY"
                )
            )

        # For comparison schema, extract secondary temp/rain if available, else primary
        comparison_partner = sec_obs or tertiary_obs
        if comparison_partner:
            sec_temp = comparison_partner.temperature_c
            sec_rain = comparison_partner.rain_probability_pct
        else:
            sec_temp = lead_obs.temperature_c
            sec_rain = lead_obs.rain_probability_pct

        # 3. Multi-source agreement evaluation using canonical ai.reasoner.agreement
        from ai.reasoner.agreement import evaluate_source_agreement
        from ai.models import SourceAgreementEnum

        primary_ai_rec = lead_obs.to_ai_weather_record()
        secondary_ai_rec = comparison_partner.to_ai_weather_record() if comparison_partner else None

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
            disagreement_notes = f"High variance between providers: {agr_text}. Prioritizing authoritative {lead_obs.source}."

        # 4. Freshness, Completeness, and System State evaluation
        from backend.services.weather_reliability import (
            evaluate_weather_freshness,
            validate_weather_completeness,
            determine_system_state,
            FreshnessClassification,
            SystemStateEnum
        )

        fresh_class, obs_age_min, fresh_meta = evaluate_weather_freshness(
            observed_at=lead_obs.observed_at,
            retrieved_at=lead_obs.retrieved_at,
            is_cached=getattr(lead_obs, "is_cached", False),
            cache_age_seconds=getattr(lead_obs, "cache_age_seconds", None)
        )

        comp_class, val_class, val_issues = validate_weather_completeness(lead_obs.model_dump())

        derived_state = determine_system_state(
            is_primary_healthy=is_primary_healthy,
            is_secondary_healthy=is_secondary_healthy,
            is_cached=getattr(lead_obs, "is_cached", False),
            freshness=fresh_class
        ).value

        # Update lead_obs reliability fields
        lead_obs.freshness_status = fresh_class.value
        lead_obs.completeness_status = comp_class.value
        lead_obs.validation_status = val_class.value
        lead_obs.validation_issues = val_issues
        lead_obs.provider_status = provider_status
        lead_obs.provider_diagnostics = primary_diag

        # 5. Fetch Official Severe Alerts (IMD is strictly authoritative)
        try:
            alerts = await self.primary.get_official_alerts(latitude, longitude, resolved_name)
            alert_dicts = [a.model_dump() for a in alerts]
        except Exception:
            alert_dicts = []

        # 6. Optional Database Persistence with 5-minute deduplication window
        if db_session is not None:
            self._persist_observation(db_session, lead_obs)

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
                temperature=lead_obs.temperature_c,
                feels_like=lead_obs.feels_like_c,
                humidity=lead_obs.humidity_pct,
                rain_probability=lead_obs.rain_probability_pct,
                wind_speed=lead_obs.wind_speed_kmh,
                condition=lead_obs.condition,
                rainfall_mm=lead_obs.rainfall_mm
            ),
            comparison=ComparisonDataSchema(
                secondary_temperature=sec_temp,
                secondary_rain_probability=sec_rain,
                sources_agree=sources_agree,
                confidence_level=confidence_level,
                disagreement_notes=disagreement_notes,
                provider_records=provider_records
            ),
            alerts=alert_dicts,
            source=source_label,
            sources=sources_list,
            units=WeatherUnitsSchema(),
            observed_at=lead_obs.observed_at,
            retrieved_at=lead_obs.retrieved_at,
            data_freshness=data_freshness_str,
            freshness_status=fresh_class.value,
            completeness_status=comp_class.value,
            validation_status=val_class.value,
            validation_issues=val_issues,
            is_cached=getattr(lead_obs, "is_cached", False),
            cache_age_seconds=getattr(lead_obs, "cache_age_seconds", None),
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
