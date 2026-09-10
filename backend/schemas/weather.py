"""Pydantic API Response Schemas for Current Weather, Forecast Engine, Alert Engine, and Weather Services."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class WeatherUnitsSchema(BaseModel):
    """Explicit unit declarations for weather observation fields."""
    temperature: str = Field(default="°C")
    humidity: str = Field(default="%")
    rain_probability: str = Field(default="%")
    wind_speed: str = Field(default="km/h")
    rainfall: str = Field(default="mm")
    pressure: str = Field(default="hPa")
    visibility: str = Field(default="km")


class WeatherDataSchema(BaseModel):
    """Core observed weather data fields."""
    temperature: float = Field(description="Temperature in Celsius")
    feels_like: Optional[float] = Field(default=None, description="Feels like temperature in Celsius")
    humidity: float = Field(description="Humidity percentage")
    rain_probability: float = Field(description="Rain probability percentage")
    wind_speed: float = Field(description="Wind speed in km/h")
    condition: str = Field(description="Condition description e.g. Rain, Moderate Rain")
    rainfall_mm: float = Field(default=0.0, description="Rainfall amount in mm")


class ComparisonDataSchema(BaseModel):
    """Multi-source agreement comparison metrics."""
    secondary_temperature: float
    secondary_rain_probability: float
    sources_agree: bool
    confidence_level: Optional[str] = Field(default="HIGH", description="Confidence: HIGH, MEDIUM, CAUTIOUS")
    disagreement_notes: Optional[str] = Field(default=None, description="Detailed explanation if providers disagree")


class LocationDataSchema(BaseModel):
    """Resolved location geographic details."""
    name: str
    latitude: float
    longitude: float
    district: Optional[str] = None
    state: Optional[str] = None


class CurrentWeatherResponse(BaseModel):
    """Normalized Current Weather API Response Contract."""
    location: LocationDataSchema
    weather: WeatherDataSchema
    comparison: ComparisonDataSchema
    alerts: List[Dict[str, Any]] = Field(default_factory=list)
    source: str
    units: WeatherUnitsSchema = Field(default_factory=WeatherUnitsSchema)
    observed_at: str
    retrieved_at: str
    data_freshness: Optional[str] = Field(default="FRESH", description="Freshness: FRESH, CACHED, STALE_DEGRADED")
    freshness_status: Optional[str] = Field(default="FRESH", description="Classification: FRESH, AGING, STALE, UNAVAILABLE")
    completeness_status: Optional[str] = Field(default="COMPLETE", description="Classification: COMPLETE, PARTIAL, INVALID, UNAVAILABLE")
    validation_status: Optional[str] = Field(default="VALID", description="Validation status: VALID, WARNING, INVALID")
    validation_issues: List[str] = Field(default_factory=list, description="Validation issues or warnings")
    is_cached: bool = Field(default=False, description="Whether observation was retrieved from cache")
    cache_age_seconds: Optional[int] = Field(default=None, description="Age of cached observation in seconds")
    provider_status: Optional[str] = Field(default="HEALTHY", description="Provider status: HEALTHY, DEGRADED, FAILED, UNAVAILABLE")
    provider_diagnostics: Optional[Dict[str, Any]] = Field(default=None, description="Diagnostic telemetry from provider")



class ForecastItemSchema(BaseModel):
    """Normalized hourly/sub-daily forecast item schema."""
    forecast_time: str = Field(description="Human readable time e.g. '07:00 AM'")
    forecast_for: str = Field(description="Target forecast ISO 8601 UTC timestamp")
    temperature: float = Field(description="Temperature in Celsius (°C)")
    temp_min: Optional[float] = Field(default=None, description="Minimum temperature in Celsius")
    temp_max: Optional[float] = Field(default=None, description="Maximum temperature in Celsius")
    rain_probability: float = Field(description="Precipitation probability 0-100%")
    rainfall_mm: float = Field(default=0.0, description="Precipitation amount in mm")
    humidity: Optional[float] = Field(default=None, description="Relative humidity %")
    wind_speed: float = Field(description="Wind speed in km/h")
    wind_direction_deg: Optional[float] = Field(default=None, description="Wind direction degrees")
    condition: str = Field(description="Weather condition string")
    source: str = Field(description="Forecast provider source name")
    issued_at: str = Field(description="Forecast issuance ISO 8601 UTC timestamp")
    retrieved_at: str = Field(description="Data retrieval ISO 8601 UTC timestamp")


class DailyForecastItemSchema(BaseModel):
    """Aggregated daily forecast summary item schema."""
    date: str = Field(description="Target date string YYYY-MM-DD")
    temperature_min: float = Field(description="Minimum daily temperature in Celsius (°C)")
    temperature_max: float = Field(description="Maximum daily temperature in Celsius (°C)")
    rain_probability: float = Field(description="Peak daily precipitation probability %")
    total_rainfall_mm: float = Field(default=0.0, description="Total daily precipitation in mm")
    max_wind_speed: float = Field(description="Maximum daily wind speed in km/h")
    condition: str = Field(description="Dominant daily weather condition")
    source: str = Field(description="Forecast provider source name")
    issued_at: str = Field(description="Forecast issuance ISO 8601 UTC timestamp")


class ForecastResponse(BaseModel):
    """Normalized Forecast API Response Contract."""
    location: str = Field(description="Location name string")
    latitude: float
    longitude: float
    hourly_forecast: List[ForecastItemSchema] = Field(description="Hourly/sub-daily forecast items")
    forecast: List[ForecastItemSchema] = Field(description="Backward-compatible alias for frontend consumers")
    daily_forecast: List[DailyForecastItemSchema] = Field(default_factory=list, description="Aggregated daily forecast items")
    days_count: int = Field(default=7, description="Number of forecast days included")
    source: str = Field(description="Forecast provider attribution")
    units: WeatherUnitsSchema = Field(default_factory=WeatherUnitsSchema)
    issued_at: str = Field(description="Forecast issuance ISO 8601 UTC timestamp")
    retrieved_at: str = Field(description="Data retrieval ISO 8601 UTC timestamp")


class AlertItemSchema(BaseModel):
    """Normalized official severe weather alert item schema."""
    alert_type: str = Field(description="Category e.g., heavy_rain_cyclone, thunderstorm_warning")
    severity: str = Field(description="Standardized severity: low, medium, high, extreme")
    title: str = Field(description="Warning title narrative")
    description: str = Field(description="Detailed official warning description")
    instructions: Optional[str] = Field(default=None, description="Official emergency safety instructions")
    area: Optional[str] = Field(default=None, description="Affected geographical zone/district")
    source: str = Field(default="IMD", description="Official meteorological authority")
    is_official: bool = Field(default=True, description="Flag confirming official meteorological warning")
    is_active: bool = Field(default=True, description="Flag indicating currently active warning")
    issued_at: str = Field(description="Issuance ISO 8601 UTC timestamp")
    expires_at: str = Field(description="Expiration ISO 8601 UTC timestamp")
    updated_at: Optional[str] = Field(default=None, description="Update ISO 8601 UTC timestamp")
    retrieved_at: str = Field(description="Data retrieval ISO 8601 UTC timestamp")


class AlertResponse(BaseModel):
    """Normalized Weather Alert Engine API Response Contract."""
    location: str = Field(description="Location name string")
    latitude: float
    longitude: float
    alerts: List[AlertItemSchema] = Field(default_factory=list, description="Official severe weather alerts")
    active_count: int = Field(default=0, description="Count of currently active alerts")
    source: str = Field(default="IMD Official", description="Source authority attribution")
    status: str = Field(default="VERIFIED", description="Alert status: VERIFIED or UNVERIFIED")
    retrieved_at: str = Field(description="Data retrieval ISO 8601 UTC timestamp")


class HistoricalRecordItemSchema(BaseModel):
    """Normalized individual historical weather record item."""
    observed_at: str = Field(description="ISO 8601 UTC timestamp of observation")
    temperature: float = Field(description="Temperature in Celsius (°C)")
    humidity: float = Field(description="Relative humidity %")
    rain_probability: float = Field(default=0.0, description="Rain probability %")
    wind_speed: float = Field(description="Wind speed in km/h")
    rainfall_mm: float = Field(default=0.0, description="Precipitation amount in mm")
    condition: str = Field(description="Observed weather condition string")
    source: str = Field(description="Historical provider source name")
    retrieved_at: str = Field(description="Ingestion/Retrieval ISO 8601 UTC timestamp")


class HistoricalWeatherResponse(BaseModel):
    """Normalized Historical Weather API Response Contract."""
    location: str = Field(description="Location name string")
    latitude: float
    longitude: float
    start_date: str = Field(description="Query range start date YYYY-MM-DD")
    end_date: str = Field(description="Query range end date YYYY-MM-DD")
    metric: str = Field(default="all", description="Target metric or 'all'")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Aggregated statistics (averages, totals, extremes)")
    records: List[HistoricalRecordItemSchema] = Field(default_factory=list, description="Historical observations list")
    count: int = Field(default=0, description="Total number of observation records returned")
    source: str = Field(default="NASA POWER / IMD Archive", description="Historical provider attribution")
    units: WeatherUnitsSchema = Field(default_factory=WeatherUnitsSchema)
    retrieved_at: str = Field(description="Data retrieval ISO 8601 UTC timestamp")


class ClimateTrendResponse(BaseModel):
    """Normalized Climate Trend API Response Contract."""
    location: str = Field(description="Location name string")
    latitude: float
    longitude: float
    period: str = Field(description="Multi-year period e.g. 2015-2025")
    start_year: int
    end_year: int
    metric: str
    trend: str = Field(description="Overall direction e.g., increasing, stable, decreasing")
    temperature_delta_c: float = Field(description="Net temperature change in Celsius")
    rainfall_variability: str = Field(description="Qualitative rainfall variability indicator")
    analysis: str = Field(description="Detailed meteorological climate trend summary")
    source: str = Field(default="NASA POWER Climate Archive", description="Provider source name")
    retrieved_at: str = Field(description="Data retrieval ISO 8601 UTC timestamp")


class AirQualityPollutantsSchema(BaseModel):
    """Breakdown of critical ambient air pollutants."""
    pm2_5: float = Field(default=0.0, description="Particulate Matter PM2.5 in µg/m³")
    pm10: float = Field(default=0.0, description="Particulate Matter PM10 in µg/m³")
    no2: float = Field(default=0.0, description="Nitrogen Dioxide in µg/m³")
    so2: float = Field(default=0.0, description="Sulfur Dioxide in µg/m³")
    o3: float = Field(default=0.0, description="Ozone in µg/m³")
    co: float = Field(default=0.0, description="Carbon Monoxide in µg/m³")


class AirQualityResponse(BaseModel):
    """Normalized Air Quality Index API Response Contract."""
    location: str = Field(description="Location name")
    latitude: float
    longitude: float
    aqi: int = Field(description="Normalized Air Quality Index (0-500)")
    category: str = Field(description="AQI Category: Good, Moderate, Unhealthy for Sensitive Groups, Unhealthy, Very Unhealthy, Hazardous")
    primary_pollutant: str = Field(default="PM2.5", description="Dominant ambient pollutant")
    pollutants: AirQualityPollutantsSchema
    recommendations: List[str] = Field(default_factory=list, description="Health & outdoor activity recommendations")
    source: str = Field(default="CPCB / Open-Meteo Air Quality", description="Source provider attribution")
    retrieved_at: str = Field(description="Data retrieval ISO 8601 UTC timestamp")


