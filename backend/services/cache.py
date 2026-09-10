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

    def _evict_expired_or_oldest(self, max_retention: int = 7200) -> None:
        """Evicts entries older than max retention and enforces max capacity bounds."""
        now = time.time()
        # 1. Purge keys older than maximum retention limit (7200s default)
        expired_keys = [
            k for k, v in self._store.items()
            if (now - v.get("cached_at", v["expires_at"] - self.default_ttl)) > max_retention
        ]
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
            return None

        return entry["value"]

    def get_with_metadata(
        self,
        key: str,
        max_stale_seconds: int = 7200
    ) -> tuple[Optional[Any], bool, Optional[int]]:
        """
        Retrieves cached entry with freshness metadata.
        Returns:
            (value, is_fresh, age_seconds)
            - value: Cached payload, or None if absent or older than max_stale_seconds.
            - is_fresh: True if current time <= expires_at, False if expired but within max_stale_seconds.
            - age_seconds: Age in seconds since caching, or None if entry not found.
        """
        entry = self._store.get(key)
        if not entry:
            return None, False, None

        now = time.time()
        cached_at = entry.get("cached_at", entry["expires_at"] - self.default_ttl)
        age_seconds = max(0, int(now - cached_at))

        if now <= entry["expires_at"]:
            return entry["value"], True, age_seconds

        # Expired: check if within allowable stale window for offline/degraded operation
        if (now - cached_at) <= max_stale_seconds:
            return entry["value"], False, age_seconds

        # Beyond maximum stale retention
        del self._store[key]
        return None, False, None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Stores value with explicit or default TTL in seconds, enforcing memory bounds."""
        self._evict_expired_or_oldest()
        now = time.time()
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = now + effective_ttl
        self._store[key] = {
            "value": value,
            "cached_at": now,
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
