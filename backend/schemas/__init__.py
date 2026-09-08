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
from backend.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    TokenResponse,
    UserUpdateRequest,
    UserPreferenceSchema,
    SavedLocationCreate,
    SavedLocationResponse
)
from backend.schemas.locations import (
    LocationResolveRequest,
    ReverseGeocodeRequest,
    LocationDetailResponse
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
    "ChatResponse",
    "RegisterRequest",
    "LoginRequest",
    "UserResponse",
    "TokenResponse",
    "UserUpdateRequest",
    "UserPreferenceSchema",
    "SavedLocationCreate",
    "SavedLocationResponse",
    "LocationResolveRequest",
    "ReverseGeocodeRequest",
    "LocationDetailResponse"
]
