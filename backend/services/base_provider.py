"""Abstract Base Weather Data Provider Interface.

Defines the contract, connection pooling, and shared HTTP client behavior for all weather provider adapters.
Isolates provider failure modes behind predictable internal exceptions.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import httpx
from backend.config.settings import settings
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
    NormalizedAlertItem
)

_shared_http_clients: Dict[float, httpx.AsyncClient] = {}


def get_shared_http_client(timeout: float) -> httpx.AsyncClient:
    """Returns a singleton connection-pooled AsyncClient per timeout configuration."""
    if timeout not in _shared_http_clients or _shared_http_clients[timeout].is_closed:
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=100, keepalive_expiry=30.0)
        _shared_http_clients[timeout] = httpx.AsyncClient(timeout=timeout, limits=limits)
    return _shared_http_clients[timeout]


class BaseWeatherProvider(ABC):
    """Abstract Base Class for Weather Data Providers."""

    def __init__(self, timeout: Optional[float] = None, max_retries: Optional[int] = None):
        self.timeout = timeout if timeout is not None else settings.WEATHER_HTTP_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.WEATHER_HTTP_MAX_RETRIES

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'IMD', 'Open-Meteo', 'NASA POWER')."""
        pass

    @property
    @abstractmethod
    def authority_level(self) -> str:
        """Data authority classification (e.g. 'primary_authoritative', 'secondary_forecast', 'historical_climate')."""
        pass

    async def _fetch_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Shared async HTTP request execution with retry policy, connection pooling, and exception mapping."""
        last_exception = None
        client = get_shared_http_client(self.timeout)

        for attempt in range(self.max_retries + 1):
            try:
                resp = await client.get(url, params=params, headers=headers)

                if resp.status_code == 401 or resp.status_code == 403:
                    raise ProviderAuthenticationError(
                        f"Authentication failed with status {resp.status_code}",
                        provider_name=self.name
                    )
                elif resp.status_code == 429:
                    raise ProviderRateLimitedError(
                        "Rate limit exceeded",
                        provider_name=self.name
                    )
                elif resp.status_code >= 500:
                    raise ProviderUnavailableError(
                        f"Server error response {resp.status_code}",
                        provider_name=self.name
                    )
                elif resp.status_code != 200:
                    raise ProviderError(
                        f"Unexpected HTTP status {resp.status_code}",
                        provider_name=self.name
                    )

                try:
                    return resp.json()
                except Exception as e:
                    raise ProviderInvalidResponseError(
                        f"Failed to parse JSON response: {str(e)}",
                        provider_name=self.name
                    )

            except (httpx.TimeoutException, TimeoutError) as e:
                last_exception = ProviderTimeoutError(
                    f"Request timed out after {self.timeout}s: {str(e)}",
                    provider_name=self.name
                )
            except httpx.NetworkError as e:
                last_exception = ProviderUnavailableError(
                    f"Network connectivity failure: {str(e)}",
                    provider_name=self.name
                )
            except ProviderError as e:
                raise e
            except Exception as e:
                last_exception = ProviderError(
                    f"Unhandled HTTP client error: {str(e)}",
                    provider_name=self.name
                )

        if last_exception:
            raise last_exception
        raise ProviderUnavailableError("Provider request failed after retries", provider_name=self.name)

    @abstractmethod
    async def get_current_weather(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> NormalizedWeatherObservation:
        """Fetch current weather observations."""
        pass

    @abstractmethod
    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedForecastItem]:
        """Fetch weather forecast items."""
        pass

    @abstractmethod
    async def get_official_alerts(
        self,
        latitude: float,
        longitude: float,
        location_name: str = "Coimbatore"
    ) -> List[NormalizedAlertItem]:
        """Fetch active severe weather alerts."""
        pass
