"""WeatherGPT — Core AI & Meteorological Data Models

Strictly defines schemas for NLU, Weather Observations, Forecasts,
Official IMD Alerts, Reasoning Results, and Persona Decision Advisories.
Aligned with docs/08_Api_Contracts.md and docs/09_AI_Design.md.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PersonaEnum(str, Enum):
    GENERAL = "general"
    STUDENT = "student"
    FARMER = "farmer"
    FISHERMAN = "fisherman"
    TRAVELLER = "traveller"
    DISASTER_RESPONSE = "disaster_response"


class LanguageEnum(str, Enum):
    EN = "en"
    TA = "ta"
    TANGLISH = "tanglish"
    HI = "hi"
    UNKNOWN = "unknown"


class IntentEnum(str, Enum):
    CURRENT_WEATHER = "current_weather"
    FORECAST = "forecast"
    RAIN_FORECAST = "rain_forecast"
    TEMPERATURE = "temperature"
    WIND = "wind"
    HUMIDITY = "humidity"
    WEATHER_ALERT = "weather_alert"
    TRAVEL_ADVISORY = "travel_advisory"
    OUTDOOR_DECISION = "outdoor_decision"
    AGRICULTURE_ADVISORY = "agriculture_advisory"
    HISTORICAL_WEATHER = "historical_weather"
    CLIMATE_TREND = "climate_trend"
    LOCATION_WEATHER = "location_weather"
    FORECAST_COMPARISON = "forecast_comparison"
    WEATHER_EXPLANATION = "weather_explanation"
    CYCLONE_INQUIRY = "cyclone_inquiry"
    GENERAL_WEATHER_QUESTION = "general_weather_question"


class RiskLevelEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class FreshnessStatusEnum(str, Enum):
    FRESH = "fresh"          # < 60 mins
    ACCEPTABLE = "acceptable" # 60 - 180 mins
    STALE = "stale"          # > 180 mins


class SourceAgreementEnum(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SINGLE_SOURCE = "single_source"


class LocationInfo(BaseModel):
    name: str
    latitude: float
    longitude: float
    district: Optional[str] = None
    state: Optional[str] = None


class WeatherRecord(BaseModel):
    """Normalized observation schema (docs/06_Data_sources.md)."""
    location: LocationInfo
    observed_at: datetime
    retrieved_at: datetime
    temperature: float = Field(description="Temperature in Celsius")
    humidity: float = Field(description="Relative humidity in percentage")
    rain_probability: float = Field(description="Precipitation probability 0-100%")
    wind_speed: float = Field(description="Wind speed in km/h")
    weather_condition: str = Field(description="e.g. Rain, Thunderstorm, Sunny, Cloudy")
    source: str = Field(default="IMD", description="Data source name e.g. IMD, Open-Meteo")
    rainfall_amount_mm: Optional[float] = Field(default=0.0, description="Observed/expected rainfall in mm")


class ForecastItem(BaseModel):
    time: str
    temperature: float
    rain_probability: float
    wind_speed: float
    condition: str
    rainfall_amount_mm: Optional[float] = 0.0


class OfficialAlert(BaseModel):
    """Official severe weather warning (docs/08_Api_Contracts.md)."""
    type: str = Field(description="e.g. heavy_rain, cyclone, thunderstorm, heatwave")
    severity: RiskLevelEnum = Field(description="low, medium, high, extreme")
    title: str
    description: str
    source: str = Field(default="IMD")
    issued_at: datetime
    expires_at: datetime
    affected_locations: List[str] = Field(default_factory=list)


class ExtractedEntities(BaseModel):
    location: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    weather_variable: Optional[str] = None
    persona: Optional[PersonaEnum] = None
    activity: Optional[str] = None


class NLUResult(BaseModel):
    original_text: str
    detected_language: LanguageEnum
    intent: IntentEnum
    entities: ExtractedEntities
    confidence: float = Field(ge=0.0, le=1.0)


class HazardDetection(BaseModel):
    hazard_type: str
    detected: bool
    severity: RiskLevelEnum
    details: str


class WeatherReasoningResult(BaseModel):
    """Output of the Weather Reasoner engine."""
    evaluated_at: datetime
    location: str
    freshness: FreshnessStatusEnum
    data_age_minutes: int
    source_agreement: SourceAgreementEnum
    consistency_score: int = Field(ge=0, le=100, description="0-100 composite indicator")
    active_warnings: List[OfficialAlert] = Field(default_factory=list)
    detected_hazards: List[HazardDetection] = Field(default_factory=list)
    overall_risk: RiskLevelEnum
    uncertainty_note: Optional[str] = None
    sources_used: List[str] = Field(default_factory=list)


class DecisionAdvisory(BaseModel):
    """Persona-tailored actionable recommendation."""
    persona: PersonaEnum
    risk_level: RiskLevelEnum
    headline: str
    advisory_text: str
    key_precautions: List[str]
    official_warning_present: bool
    official_warning_title: Optional[str] = None
    source_attribution: str
    timestamp_info: str


class ValidationResult(BaseModel):
    is_valid: bool
    hallucination_detected: bool
    warning_consistency_passed: bool
    issues: List[str] = Field(default_factory=list)
    verified_claims: List[str] = Field(default_factory=list)
