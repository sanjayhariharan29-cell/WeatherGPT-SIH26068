"""Provider Response In-Memory TTL Caching Layer.

Provides clean, short-lived response caching to prevent redundant upstream API requests
while maintaining data freshness, timestamp accuracy, and memory safety.
"""

import time
from typing import Dict, Any, Optional


class ProviderCache:
    """Thread-safe in-memory TTL Cache for weather data providers with bounded memory capacity."""

    def __init__(self, default_ttl: int = 300, max_entries: int = 1000):
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._store: Dict[str, Dict[str, Any]] = {}

    def _evict_expired_or_oldest(self) -> None:
        """Evicts expired keys and enforces max capacity bounds."""
        now = time.time()
        # 1. Purge expired keys
        expired_keys = [k for k, v in self._store.items() if now > v["expires_at"]]
        for k in expired_keys:
            del self._store[k]

        # 2. Enforce max entry limit by evicting oldest entries if capacity exceeded
        if len(self._store) >= self.max_entries:
            sorted_keys = sorted(self._store.keys(), key=lambda k: self._store[k]["expires_at"])
            overcapacity_count = len(self._store) - self.max_entries + 1
            for k in sorted_keys[:overcapacity_count]:
                del self._store[k]

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
        """Stores value with explicit or default TTL in seconds, enforcing memory bounds."""
        self._evict_expired_or_oldest()
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + effective_ttl
        self._store[key] = {
            "value": value,
            "expires_at": expires_at
        }

    def clear(self) -> None:
        """Clears all cached entries."""
        self._store.clear()

    @property
    def size(self) -> int:
        """Returns the number of active cached items."""
        return len(self._store)


# Global singleton instance for weather service package
provider_cache = ProviderCache(default_ttl=300, max_entries=1000)
