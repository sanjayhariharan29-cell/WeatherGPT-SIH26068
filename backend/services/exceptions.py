from datetime import datetime, timezone
from typing import Dict, Any, Optional


class ProviderError(Exception):
    """Base exception for all weather provider operations with diagnostic context."""
    def __init__(
        self,
        message: str,
        provider_name: str = "Unknown",
        status_code: Optional[int] = None,
        diagnostics: Optional[Dict[str, Any]] = None
    ):
        self.provider_name = provider_name
        self.message = message
        self.status_code = status_code
        self.diagnostics = diagnostics or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        super().__init__(f"[{provider_name}] {message}")

    @property
    def status(self) -> Optional[Any]:
        """Diagnostic provider status (e.g. 'NOT_CONFIGURED', 'DOWN', 'DEGRADED')."""
        if self.diagnostics and "status" in self.diagnostics:
            return self.diagnostics["status"]
        return self.status_code


class ProviderUnavailableError(ProviderError):
    """Raised when an external weather provider is unreachable or down."""
    pass


class ProviderTimeoutError(ProviderError):
    """Raised when a request to a weather provider times out."""
    pass


class ProviderRateLimitedError(ProviderError):
    """Raised when request quota or rate limits are exceeded."""
    pass


class ProviderInvalidResponseError(ProviderError):
    """Raised when a provider returns unparseable or invalid payload format."""
    pass


class ProviderAuthenticationError(ProviderError):
    """Raised when provider API credentials are missing or rejected."""
    pass


class ProviderMalformedDataError(ProviderError):
    """Raised when provider returns data violating physical atmospheric boundaries."""
    pass


class ProviderStaleDataError(ProviderError):
    """Raised when provider returns expired or unacceptably stale telemetry."""
    pass

