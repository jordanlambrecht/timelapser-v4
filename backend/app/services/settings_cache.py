# backend/app/services/settings_cache.py
"""
Settings Caching Service with TTL

Provides high-performance caching for the 8 user-configurable logger settings
with Time-To-Live (TTL) cache expiration and thread-safe access.

This addresses the original user request to make the logger service respect
user settings while optimizing performance through intelligent caching.
"""

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

# Cache configuration
DEFAULT_TTL_SECONDS = 300  # 5 minutes
CACHE_CLEANUP_INTERVAL = 600  # 10 minutes


@dataclass
class CacheEntry:
    """Thread-safe cache entry with TTL support."""

    value: Any
    created_at: float
    ttl_seconds: int

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() - self.created_at > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return time.time() - self.created_at


class SettingsCache:
    """
    Thread-safe settings cache with TTL expiration.

    Caches the 8 user-configurable logger settings:
    - db_log_retention_days
    - db_log_level
    - file_log_retention_days
    - file_log_level
    - file_log_max_files
    - file_log_max_size
    - file_log_enable_compression
    - file_log_enable_rotation

    Features:
    - Thread-safe access using RLock
    - Configurable TTL per setting type
    - Automatic cleanup of expired entries
    - Performance monitoring and statistics
    """

    def __init__(self, default_ttl_seconds: int = DEFAULT_TTL_SECONDS):
        """
        Initialize settings cache with TTL support.

        Args:
            default_ttl_seconds: Default TTL for cache entries
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._default_ttl = default_ttl_seconds
        self._last_cleanup = time.time()

        # Performance tracking
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._cleanups = 0

        # Avoid circular import - logger will be set later if needed
        self._logger = None

        # Note: Logging avoided here to prevent circular import

    def get(self, key: str, ttl_seconds: Optional[int] = None) -> Optional[Any]:
        """
        Get cached value with TTL check.

        Args:
            key: Cache key
            ttl_seconds: Optional TTL override

        Returns:
            Cached value if valid and not expired, None otherwise
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            # Check if entry has expired
            effective_ttl = ttl_seconds or entry.ttl_seconds
            if time.time() - entry.created_at > effective_ttl:
                # Entry expired, remove it
                del self._cache[key]
                self._misses += 1

                # Cache entry expired - avoid logging to prevent circular imports
                return None

            self._hits += 1

            # Cache hit - avoid logging to prevent circular imports

            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Set cached value with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional TTL override
        """
        effective_ttl = ttl_seconds or self._default_ttl

        with self._lock:
            self._cache[key] = CacheEntry(
                value=value, created_at=time.time(), ttl_seconds=effective_ttl
            )
            self._sets += 1

            # Cache set - avoid logging to prevent circular imports

            # Cleanup expired entries periodically
            self._maybe_cleanup()

    def invalidate(self, key: str) -> bool:
        """
        Invalidate specific cache entry.

        Args:
            key: Cache key to invalidate

        Returns:
            True if entry was found and removed
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                # Cache invalidated - avoid logging to prevent circular imports
                return True
            return False

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()

            # Cache cleared - avoid logging to prevent circular imports

            return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if current_time - entry.created_at > entry.ttl_seconds
            ]

            for key in expired_keys:
                del self._cache[key]

            self._cleanups += 1
            self._last_cleanup = current_time

            # Cache cleanup completed - avoid logging to prevent circular imports

            return len(expired_keys)

    def _maybe_cleanup(self) -> None:
        """Perform cleanup if enough time has passed."""
        if time.time() - self._last_cleanup > CACHE_CLEANUP_INTERVAL:
            self.cleanup_expired()

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_requests = self._hits + self._misses
        return self._hits / total_requests if total_requests > 0 else 0.0

    @property
    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics.

        Returns:
            Dictionary with cache performance metrics
        """
        with self._lock:
            total_requests = self._hits + self._misses

            return {
                "cache_size": len(self._cache),
                "total_requests": total_requests,
                "cache_hits": self._hits,
                "cache_misses": self._misses,
                "cache_sets": self._sets,
                "hit_rate": self.hit_rate,
                "miss_rate": (
                    self._misses / total_requests if total_requests > 0 else 0.0
                ),
                "cleanups_performed": self._cleanups,
                "last_cleanup_ago_seconds": time.time() - self._last_cleanup,
                "default_ttl_seconds": self._default_ttl,
                "current_entries": [
                    {
                        "key": key,
                        "age_seconds": entry.age_seconds,
                        "ttl_seconds": entry.ttl_seconds,
                        "expires_in_seconds": entry.ttl_seconds - entry.age_seconds,
                    }
                    for key, entry in self._cache.items()
                    if not entry.is_expired
                ],
            }


# Global cache instance
_settings_cache: Optional[SettingsCache] = None
_cache_lock = threading.Lock()


def get_settings_cache() -> SettingsCache:
    """
    Get global settings cache instance (thread-safe singleton).

    Returns:
        Global SettingsCache instance
    """
    global _settings_cache

    if _settings_cache is None:
        with _cache_lock:
            if _settings_cache is None:
                _settings_cache = SettingsCache()

    return _settings_cache


def invalidate_settings_cache() -> int:
    """
    Invalidate the entire settings cache.

    This should be called when settings are updated to ensure
    the cache reflects the latest values.

    Returns:
        Number of entries cleared
    """
    cache = get_settings_cache()
    return cache.clear()


def get_cached_logger_settings() -> Optional[Dict[str, Any]]:
    """
    Get cached logger settings if available.

    Returns the 8 user-configurable logger settings from cache
    or None if not cached/expired.

    Returns:
        Dict with logger settings or None if not cached
    """
    cache = get_settings_cache()
    return cache.get("logger_settings", ttl_seconds=DEFAULT_TTL_SECONDS)


def cache_logger_settings(settings: Dict[str, Any]) -> None:
    """
    Cache the 8 user-configurable logger settings.

    Args:
        settings: Dict containing the logger settings to cache
    """
    cache = get_settings_cache()
    cache.set("logger_settings", settings, ttl_seconds=DEFAULT_TTL_SECONDS)
