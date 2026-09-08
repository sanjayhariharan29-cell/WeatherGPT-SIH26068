"""API Response Schemas Package."""

from backend.schemas.weather import (
    CurrentWeatherResponse,
    LocationDataSchema,
    WeatherDataSchema,
    ComparisonDataSchema,
    WeatherUnitsSchema,
    ForecastItemSchema,
    DailyForecastItemSchema,
    ForecastResponse,
    AlertItemSchema,
    AlertResponse,
    HistoricalRecordItemSchema,
    HistoricalWeatherResponse,
    ClimateTrendResponse
)
from backend.schemas.chat import (
    LocationPayload,
    ChatRequest,
    RiskSummary,
    ValidationSummary,
    ChatResponse
)

__all__ = [
    "CurrentWeatherResponse",
    "LocationDataSchema",
    "WeatherDataSchema",
    "ComparisonDataSchema",
    "WeatherUnitsSchema",
    "ForecastItemSchema",
    "DailyForecastItemSchema",
    "ForecastResponse",
    "AlertItemSchema",
    "AlertResponse",
    "HistoricalRecordItemSchema",
    "HistoricalWeatherResponse",
    "ClimateTrendResponse",
    "LocationPayload",
    "ChatRequest",
    "RiskSummary",
    "ValidationSummary",
    "ChatResponse"
]
