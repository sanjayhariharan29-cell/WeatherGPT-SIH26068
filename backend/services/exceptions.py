"""Weather Provider Exception Hierarchy.

Isolates external meteorological provider errors behind predictable internal exceptions.
"""

class ProviderError(Exception):
    """Base exception for all weather provider operations."""
    def __init__(self, message: str, provider_name: str = "Unknown"):
        self.provider_name = provider_name
        self.message = message
        super().__init__(f"[{provider_name}] {message}")


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
