"""Weather Services Package."""

from backend.services.base_provider import BaseWeatherProvider
from backend.services.imd_adapter import IMDAdapter
from backend.services.open_meteo_adapter import OpenMeteoAdapter
from backend.services.nasa_power_adapter import NasaPowerAdapter
from backend.services.geocoding_service import GeocodingService
from backend.services.current_weather_service import CurrentWeatherService
from backend.services.forecast_service import ForecastService
from backend.services.alert_service import AlertService
from backend.services.historical_weather_service import HistoricalWeatherService
from backend.services.weather_manager import WeatherManager
from backend.services.cache import ProviderCache, provider_cache
from backend.services.exceptions import (
    ProviderError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderRateLimitedError,
    ProviderInvalidResponseError,
    ProviderAuthenticationError
)
from backend.services.schemas import (
    NormalizedWeatherObservation,
    NormalizedForecastItem,
    NormalizedAlertItem,
    NormalizedHistoricalWeather,
    NormalizedClimateTrend
)

__all__ = [
    "BaseWeatherProvider",
    "IMDAdapter",
    "OpenMeteoAdapter",
    "NasaPowerAdapter",
    "GeocodingService",
    "CurrentWeatherService",
    "ForecastService",
    "AlertService",
    "HistoricalWeatherService",
    "WeatherManager",
    "ProviderCache",
    "provider_cache",
    "ProviderError",
    "ProviderUnavailableError",
    "ProviderTimeoutError",
    "ProviderRateLimitedError",
    "ProviderInvalidResponseError",
    "ProviderAuthenticationError",
    "NormalizedWeatherObservation",
    "NormalizedForecastItem",
    "NormalizedAlertItem",
    "NormalizedHistoricalWeather",
    "NormalizedClimateTrend"
]
