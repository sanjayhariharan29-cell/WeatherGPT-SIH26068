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
    "ClimateTrendResponse"
]
