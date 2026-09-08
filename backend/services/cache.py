"""Provider Response In-Memory TTL Caching Layer.

Provides clean, short-lived response caching to prevent redundant upstream API requests
while maintaining data freshness and timestamp accuracy.
"""

import time
from typing import Dict, Any, Optional


class ProviderCache:
    """Thread-safe in-memory TTL Cache for weather data providers."""

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Retrieves cached entry if it exists and has not expired."""
        entry = self._store.get(key)
        if not entry:
            return None

        if time.time() > entry["expires_at"]:
            del self._store[key]
            return None

        return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Stores value with explicit or default TTL in seconds."""
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + effective_ttl
        self._store[key] = {
            "value": value,
            "expires_at": expires_at
        }

    def clear(self) -> None:
        """Clears all cached entries."""
        self._store.clear()


# Global singleton instance for weather service package
provider_cache = ProviderCache(default_ttl=300)
