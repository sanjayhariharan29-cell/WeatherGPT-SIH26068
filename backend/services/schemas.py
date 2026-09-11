"""Normalized Weather Data Models & Source Provenance.

Defines internal schemas for observed weather, forecasts, meteorological alerts,
and historical climate data while preserving source provenance and timestamps.
Includes conversion adapters for Person 1's AI reasoning layer.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from ai.models import (
    WeatherRecord as AIWeatherRecord,
    ForecastItem as AIForecastItem,
    OfficialAlert as AIOfficialAlert,
    LocationInfo as AILocationInfo,
    RiskLevelEnum
)


class NormalizedWeatherObservation(BaseModel):
    """Normalized weather observation schema with full source provenance."""
    location_name: str
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    temperature_c: float = Field(description="Temperature in Celsius")
    feels_like_c: Optional[float] = Field(default=None, description="Feels like temperature in Celsius")
    humidity_pct: float = Field(ge=0.0, le=100.0, description="Relative humidity percentage")
    pressure_hpa: Optional[float] = Field(default=None, description="Atmospheric pressure in hPa")
    wind_speed_kmh: float = Field(ge=0.0, description="Wind speed in km/h")
    wind_direction_deg: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    rain_probability_pct: float = Field(ge=0.0, le=100.0, description="Rain probability percentage")
    rainfall_mm: float = Field(default=0.0, ge=0.0, description="Rainfall amount in mm")
    visibility_km: Optional[float] = Field(default=None, ge=0.0)
    condition: str = Field(description="Weather condition string")
    source: str = Field(description="Data provider name (e.g., IMD, Open-Meteo)")
    authority_level: str = Field(default="primary_authoritative", description="e.g., primary_authoritative, secondary_forecast")
    observed_at: str = Field(description="Observation ISO 8601 UTC timestamp")
    retrieved_at: str = Field(description="Data retrieval ISO 8601 UTC timestamp")
    freshness_status: str = Field(default="FRESH", description="Freshness: FRESH, AGING, STALE, UNAVAILABLE")
    completeness_status: str = Field(default="COMPLETE", description="Completeness: COMPLETE, PARTIAL, INVALID, UNAVAILABLE")
    provider_status: str = Field(default="HEALTHY", description="Provider status: HEALTHY, DEGRADED, FAILED, UNAVAILABLE")
    validation_status: str = Field(default="VALID", description="Validation status: VALID, WARNING, INVALID")
    validation_issues: List[str] = Field(default_factory=list, description="Specific validation issues or warnings")
    provider_diagnostics: Optional[Dict[str, Any]] = Field(default=None, description="Diagnostic telemetry from provider")
    is_cached: bool = Field(default=False, description="Whether data was served from provider cache")
    cache_age_seconds: Optional[int] = Field(default=None, description="Age of cache entry in seconds")

    # Backward compatibility aliases for dict indexing & attributes
    @property
    def temperature(self) -> float:
        return self.temperature_c

    @property
    def humidity(self) -> float:
        return self.humidity_pct

    @property
    def rain_probability(self) -> float:
        return self.rain_probability_pct

    @property
    def wind_speed(self) -> float:
        return self.wind_speed_kmh

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            val = getattr(self, item)
            return val
        if item in self.model_fields:
            return getattr(self, item)
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in self.model_fields

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def to_ai_weather_record(self) -> AIWeatherRecord:
        """Converts to Person 1's AI WeatherRecord model for Weather Reasoner consumption."""
        try:
            obs_dt = datetime.fromisoformat(self.observed_at)
        except Exception:
            obs_dt = datetime.now(timezone.utc)

        try:
            ret_dt = datetime.fromisoformat(self.retrieved_at)
        except Exception:
            ret_dt = datetime.now(timezone.utc)

        return AIWeatherRecord(
            location=AILocationInfo(
                name=self.location_name,
                latitude=self.latitude,
                longitude=self.longitude
            ),
            observed_at=obs_dt,
            retrieved_at=ret_dt,
            temperature=self.temperature_c,
            humidity=self.humidity_pct,
            rain_probability=self.rain_probability_pct,
            wind_speed=self.wind_speed_kmh,
            weather_condition=self.condition,
            source=self.source,
            rainfall_amount_mm=self.rainfall_mm
        )


class NormalizedForecastItem(BaseModel):
    """Normalized forecast item schema."""
    forecast_time: str = Field(description="Human readable time e.g., '07:00 AM' or ISO string")
    forecast_for: Optional[str] = Field(default=None, description="Target forecast ISO string or date string")
    temperature_c: float = Field(description="Temperature in Celsius")
    temp_min_c: Optional[float] = None
    temp_max_c: Optional[float] = None
    rain_probability_pct: float = Field(ge=0.0, le=100.0)
    rainfall_mm: float = Field(default=0.0, ge=0.0)
    humidity_pct: Optional[float] = None
    wind_speed_kmh: float = Field(ge=0.0)
    wind_direction_deg: Optional[float] = None
    condition: str
    source: str
    issued_at: str = Field(description="Forecast issuance ISO 8601 UTC timestamp")
    retrieved_at: str = Field(description="Data retrieval ISO 8601 UTC timestamp")
    freshness_status: str = Field(default="FRESH", description="Freshness: FRESH, AGING, STALE, UNAVAILABLE")
    completeness_status: str = Field(default="COMPLETE", description="Completeness: COMPLETE, PARTIAL, INVALID, UNAVAILABLE")

    # Backward compatibility aliases
    @property
    def temperature(self) -> float:
        return self.temperature_c

    @property
    def rain_probability(self) -> float:
        return self.rain_probability_pct

    @property
    def wind_speed(self) -> float:
        return self.wind_speed_kmh

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.model_fields:
            return getattr(self, item)
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in self.model_fields

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def to_ai_forecast_item(self) -> AIForecastItem:
        """Converts to Person 1's AIForecastItem model."""
        return AIForecastItem(
            time=self.forecast_time,
            temperature=self.temperature_c,
            rain_probability=self.rain_probability_pct,
            wind_speed=self.wind_speed_kmh,
            condition=self.condition,
            rainfall_amount_mm=self.rainfall_mm
        )


class NormalizedAlertItem(BaseModel):
    """Normalized severe weather alert schema with authoritative provenance and lifecycle state."""
    alert_id: Optional[str] = Field(default=None, description="Authoritative warning identifier")
    alert_type: str = Field(description="Category e.g., heavy_rain, cyclone, thunderstorm")
    severity: str = Field(description="low, medium, high, extreme")
    title: str
    description: str
    instructions: Optional[str] = None
    area: Optional[str] = None
    source: str = Field(default="IMD")
    source_url: Optional[str] = Field(default=None, description="Official bulletin URL or CAP reference")
    product_type: str = Field(default="district_warning", description="Product: district_warning or district_nowcast")
    state: str = Field(default="LIVE", description="Explicit IMD state: LIVE, STALE, FAILED, UNAVAILABLE, FIXTURE")
    geometry: Optional[Dict[str, Any]] = Field(default=None, description="Official GeoJSON geometry")
    toi: Optional[str] = Field(default=None, description="Time of issue HHMM")
    vupto: Optional[str] = Field(default=None, description="Valid upto HHMM")
    matched_district: Optional[str] = Field(default=None, description="Canonical resolved IMD district name")
    issued_at: str
    expires_at: str
    valid_from: Optional[str] = Field(default=None, description="Valid from ISO 8601 UTC timestamp")
    updated_at: Optional[str] = None
    retrieved_at: str
    status: str = Field(default="ACTIVE", description="ACTIVE, SCHEDULED, EXPIRED, INVALID, CANCELLED")
    version: int = Field(default=1, description="Update sequence version number")
    validation_issues: List[str] = Field(default_factory=list, description="Validation issues if any")

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.model_fields:
            return getattr(self, item)
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in self.model_fields

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default

    def to_ai_official_alert(self) -> AIOfficialAlert:
        """Converts to Person 1's OfficialAlert model for hazard reasoning."""
        sev_map = {
            "yellow": RiskLevelEnum.LOW,
            "low": RiskLevelEnum.LOW,
            "orange": RiskLevelEnum.MEDIUM,
            "medium": RiskLevelEnum.MEDIUM,
            "red": RiskLevelEnum.HIGH,
            "high": RiskLevelEnum.HIGH,
            "extreme": RiskLevelEnum.EXTREME,
            "critical": RiskLevelEnum.EXTREME
        }
        severity_enum = sev_map.get(self.severity.lower(), RiskLevelEnum.MEDIUM)

        try:
            iss_dt = datetime.fromisoformat(self.issued_at)
        except Exception:
            iss_dt = datetime.now(timezone.utc)

        try:
            exp_dt = datetime.fromisoformat(self.expires_at)
        except Exception:
            exp_dt = datetime.now(timezone.utc)

        vf_dt = None
        if self.valid_from:
            try:
                vf_dt = datetime.fromisoformat(self.valid_from)
            except Exception:
                vf_dt = None

        return AIOfficialAlert(
            id=self.alert_id,
            type=self.alert_type,
            severity=severity_enum,
            title=self.title,
            description=self.description,
            instructions=self.instructions,
            source=self.source,
            source_url=self.source_url,
            issued_at=iss_dt,
            expires_at=exp_dt,
            valid_from=vf_dt,
            status=self.status,
            version=self.version,
            affected_locations=[self.area] if self.area else []
        )


class NormalizedHistoricalWeather(BaseModel):
    """Normalized historical weather summary."""
    latitude: float
    longitude: float
    start_date: str
    end_date: str
    metric: str
    summary: Dict[str, Any]
    source: str
    retrieved_at: str

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.model_fields:
            return getattr(self, item)
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in self.model_fields

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default


class NormalizedClimateTrend(BaseModel):
    """Normalized multi-year climate trend analysis."""
    latitude: float
    longitude: float
    period: str
    metric: str
    trend: str
    temperature_delta_c: float
    rainfall_variability: str
    analysis: str
    source: str
    retrieved_at: str

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.model_fields:
            return getattr(self, item)
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in self.model_fields

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default
