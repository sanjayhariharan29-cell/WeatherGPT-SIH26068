"""Abstract Base Weather Data Provider Interface.

Defines the contract and shared HTTP client behavior for all weather provider adapters.
Isolates provider failure modes behind predictable exception types.
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
        """Shared async HTTP request execution with retry policy and exception mapping."""
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
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
