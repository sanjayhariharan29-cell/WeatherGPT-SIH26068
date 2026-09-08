"""Pydantic API Response Schemas for Current Weather, Forecast Engine, and Weather Services."""

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
