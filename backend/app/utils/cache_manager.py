#!/usr/bin/env python3
# backend/app/utils/cache_manager.py

"""
Cache Manager - In-memory caching for API responses to prevent flooding.

Provides TTL-based caching for frequently requested data like latest images
to reduce database load and improve response times.

Related Files:
- cache_invalidation.py: Business logic for cache invalidation events
  This file contains the infrastructure (storage, TTL, statistics) while
  cache_invalidation.py contains the business logic for when and how to
  invalidate cached data based on SSE events and application state changes.
"""

import time
from typing import Dict, Any, Optional, TypeVar, Callable, Awaitable
from datetime import datetime, timedelta
from loguru import logger
import asyncio
from functools import wraps

T = TypeVar('T')


class CacheEntry:
    """Individual cache entry with TTL support."""
    
    def __init__(self, data: Any, ttl_seconds: int):
        self.data = data
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() > self.expires_at
        
    def get_age_seconds(self) -> int:
        """Get age of cache entry in seconds."""
        return int(time.time() - self.created_at)


class MemoryCache:
    """
    Thread-safe in-memory cache with TTL support.
    
    Designed for high-frequency API endpoints to reduce database load.
    """
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if it exists and hasn't expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if entry.is_expired():
                    del self._cache[key]
                    logger.debug(f"🗑️ Cache expired and removed: {key}")
                    return None
                
                logger.debug(f"🎯 Cache hit: {key} (age: {entry.get_age_seconds()}s)")
                return entry.data
                
        logger.debug(f"❌ Cache miss: {key}")
        return None
        
    async def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds (default 60)
        """
        async with self._lock:
            self._cache[key] = CacheEntry(value, ttl_seconds)
            logger.debug(f"💾 Cached: {key} (TTL: {ttl_seconds}s)")
            
    async def delete(self, key: str) -> bool:
        """
        Delete specific cache entry.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key was found and deleted, False otherwise
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"🗑️ Cache deleted: {key}")
                return True
        return False
        
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"🧹 Cache cleared: {count} entries removed")
            
    async def cleanup_expired(self) -> int:
        """
        Remove all expired cache entries.
        
        Returns:
            Number of entries removed
        """
        async with self._lock:
            expired_keys = []
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
                    
            for key in expired_keys:
                del self._cache[key]
                
            if expired_keys:
                logger.debug(f"🗑️ Removed {len(expired_keys)} expired cache entries")
                
            return len(expired_keys)
            
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics with breakdown by cache type."""
        async with self._lock:
            total_entries = len(self._cache)
            expired_count = sum(1 for entry in self._cache.values() if entry.is_expired())
            
            # Enhanced statistics with cache type breakdown
            cache_types = {}
            for key in self._cache.keys():
                cache_type = key.split(":")[0] if ":" in key else "general"
                cache_types[cache_type] = cache_types.get(cache_type, 0) + 1
            
            return {
                "total_entries": total_entries,
                "active_entries": total_entries - expired_count,
                "expired_entries": expired_count,
                "cache_keys": list(self._cache.keys()),
                "cache_type_breakdown": cache_types,
                "memory_efficiency": {
                    "hit_ratio_estimate": "Available via decorator usage",
                    "oldest_entry_age": self._get_oldest_entry_age(),
                    "newest_entry_age": self._get_newest_entry_age(),
                }
            }
    
    def _get_oldest_entry_age(self) -> Optional[int]:
        """Get age of oldest cache entry in seconds."""
        if not self._cache:
            return None
        oldest_time = min(entry.created_at for entry in self._cache.values())
        return int(time.time() - oldest_time)
    
    def _get_newest_entry_age(self) -> Optional[int]:
        """Get age of newest cache entry in seconds."""
        if not self._cache:
            return None
        newest_time = max(entry.created_at for entry in self._cache.values())
        return int(time.time() - newest_time)

    async def get_entries_by_prefix(self, prefix: str) -> Dict[str, Any]:
        """
        Get all cache entries matching a specific prefix.
        
        Useful for debugging and targeted operations on cache subsets.
        
        Args:
            prefix: Cache key prefix to match (e.g., "setting:", "latest_image:")
            
        Returns:
            Dictionary with matching keys and their metadata
        """
        async with self._lock:
            matching_entries = {}
            for key, entry in self._cache.items():
                if key.startswith(prefix):
                    matching_entries[key] = {
                        "age_seconds": entry.get_age_seconds(),
                        "expires_in_seconds": max(0, int(entry.expires_at - time.time())),
                        "is_expired": entry.is_expired(),
                        "data_type": type(entry.data).__name__,
                    }
            return matching_entries

    async def delete_by_prefix(self, prefix: str) -> int:
        """
        Delete all cache entries matching a specific prefix.
        
        More efficient than individual deletions for bulk operations.
        
        Args:
            prefix: Cache key prefix to match for deletion
            
        Returns:
            Number of entries deleted
        """
        async with self._lock:
            keys_to_delete = [key for key in self._cache.keys() if key.startswith(prefix)]
            
            for key in keys_to_delete:
                del self._cache[key]
                
            if keys_to_delete:
                logger.debug(f"🗑️ Bulk deleted {len(keys_to_delete)} cache entries with prefix '{prefix}'")
                
            return len(keys_to_delete)


# Global cache instance
cache = MemoryCache()


def cached_response(ttl_seconds: int = 60, key_prefix: str = ""):
    """
    Decorator for caching async function responses.
    
    Args:
        ttl_seconds: Time to live for cached responses
        key_prefix: Optional prefix for cache keys
        
    Usage:
        @cached_response(ttl_seconds=30, key_prefix="latest_image")
        async def get_latest_image(camera_id: int):
            return await some_expensive_operation(camera_id)
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key from function name and arguments, excluding self/object instances
            cache_key_parts = [key_prefix, func.__name__] if key_prefix else [func.__name__]
            
            # Add string representations of args (skip first if it's a service instance)
            filtered_args = args[1:] if args and hasattr(args[0], '__class__') else args
            if filtered_args:
                cache_key_parts.extend(str(arg) for arg in filtered_args)
            if kwargs:
                cache_key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                
            cache_key = ":".join(filter(None, cache_key_parts))
            
            # Try to get from cache first
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
                
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl_seconds)
            
            return result
            
        return wrapper
    return decorator


async def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics with breakdown."""
    return await cache.get_stats()


async def clear_cache() -> None:
    """Clear global cache."""
    await cache.clear()


async def cleanup_expired_cache() -> int:
    """Clean up expired cache entries."""
    return await cache.cleanup_expired()


async def get_cache_entries_by_prefix(prefix: str) -> Dict[str, Any]:
    """Get cache entries matching a specific prefix for debugging."""
    return await cache.get_entries_by_prefix(prefix)


async def delete_cache_by_prefix(prefix: str) -> int:
    """Delete cache entries matching a specific prefix."""
    return await cache.delete_by_prefix(prefix)


# Settings-specific caching utilities
@cached_response(ttl_seconds=300, key_prefix="setting")
async def get_timezone_async(settings_service) -> str:
    """
    Get timezone using SettingsService and unified cache infrastructure.
    
    Args:
        settings_service: SettingsService instance for data access
        
    Returns:
        Timezone string (defaults to 'UTC' if not configured)
    """
    try:
        timezone = await settings_service.get_setting("timezone")
        return timezone or "UTC"
    except Exception as e:
        logger.warning(f"Failed to get timezone from settings service: {e}")
        return "UTC"


@cached_response(ttl_seconds=300, key_prefix="setting")
async def get_setting_cached(
    settings_service, key: str, default: Optional[str] = None
) -> Optional[str]:
    """
    Get any setting with unified caching infrastructure using decorator pattern.
    
    Args:
        settings_service: SettingsService instance for data access
        key: Setting key to retrieve  
        default: Default value if setting not found
        
    Returns:
        Setting value or default
    """
    try:
        # Load from service layer (caching handled by decorator)
        value = await settings_service.get_setting(key)
        return value if value is not None else default
        
    except Exception as e:
        logger.error(f"❌ Settings error for key '{key}': {e}")
        return default
