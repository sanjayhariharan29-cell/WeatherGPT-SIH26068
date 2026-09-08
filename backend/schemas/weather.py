"""Pydantic API Response Schemas for Current Weather and Weather Services."""

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
