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
import hashlib
import json
from typing import Dict, Any, Optional, TypeVar, Callable, Awaitable, Union
from datetime import datetime, timedelta
from loguru import logger
import asyncio
from functools import wraps

T = TypeVar("T")


class CacheEntry:
    """Individual cache entry with TTL and ETag support."""

    def __init__(self, data: Any, ttl_seconds: int, etag: Optional[str] = None):
        self.data = data
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.etag = etag

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() > self.expires_at

    def get_age_seconds(self) -> int:
        """Get age of cache entry in seconds."""
        return int(time.time() - self.created_at)

    def has_etag(self) -> bool:
        """Check if this cache entry has an associated ETag."""
        return self.etag is not None


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

    async def set(
        self, key: str, value: Any, ttl_seconds: int = 60, etag: Optional[str] = None
    ) -> None:
        """
        Set value in cache with TTL and optional ETag.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds (default 60)
            etag: Optional ETag for cache validation
        """
        async with self._lock:
            self._cache[key] = CacheEntry(value, ttl_seconds, etag)
            etag_info = f" (ETag: {etag})" if etag else ""
            logger.debug(f"💾 Cached: {key} (TTL: {ttl_seconds}s){etag_info}")

    async def get_with_etag(self, key: str) -> tuple[Optional[Any], Optional[str]]:
        """
        Get value and ETag from cache if it exists and hasn't expired.

        Args:
            key: Cache key

        Returns:
            Tuple of (cached value, etag) or (None, None) if not found/expired
        """
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if entry.is_expired():
                    del self._cache[key]
                    logger.debug(f"🗑️ Cache expired and removed: {key}")
                    return None, None

                logger.debug(
                    f"🎯 Cache hit with ETag: {key} (age: {entry.get_age_seconds()}s)"
                )
                return entry.data, entry.etag

        logger.debug(f"❌ Cache miss: {key}")
        return None, None

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
            expired_count = sum(
                1 for entry in self._cache.values() if entry.is_expired()
            )

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
                },
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
                        "expires_in_seconds": max(
                            0, int(entry.expires_at - time.time())
                        ),
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
            keys_to_delete = [
                key for key in self._cache.keys() if key.startswith(prefix)
            ]

            for key in keys_to_delete:
                del self._cache[key]

            if keys_to_delete:
                logger.debug(
                    f"🗑️ Bulk deleted {len(keys_to_delete)} cache entries with prefix '{prefix}'"
                )

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
            cache_key_parts = (
                [key_prefix, func.__name__] if key_prefix else [func.__name__]
            )

            # Add string representations of args (skip first if it's a service instance)
            filtered_args = args[1:] if args and hasattr(args[0], "__class__") else args
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


# ════════════════════════════════════════════════════════════════════════════════
# ETag Utilities - HTTP Cache Validation Support
#
# Implements ETag generation and validation utilities following the caching strategy:
# - Timestamp-based ETags (most common): uses updated_at fields
# - Hash-based ETags: for content without timestamps
# - Composite ETags: ID + timestamp pattern (matches image_routers.py TODOs)
# - Collection ETags: count + latest timestamp for dynamic endpoints
# - ETag validation: If-None-Match header support for 304 responses
#
# Usage patterns from caching strategy documentation:
# - Services generate ETags, routers handle HTTP comparison
# - ETags work with Cache-Control headers for optimal performance
# - Smart invalidation only when content actually changes
# ════════════════════════════════════════════════════════════════════════════════


def generate_timestamp_etag(obj: Any, timestamp_field: str = "updated_at") -> str:
    """
    Generate ETag from object timestamp (most common pattern).

    Usage pattern from caching strategy:
    ```python
    settings, etag = await settings_service.get_settings_with_etag()
    # etag = f'"{settings.updated_at.timestamp()}"'
    ```

    Args:
        obj: Object with timestamp field (database model, dict, etc.)
        timestamp_field: Name of timestamp field (default: 'updated_at')

    Returns:
        ETag string in format: "1234567890.123456"

    Examples:
        >>> generate_timestamp_etag(camera)  # camera.updated_at = datetime(...)
        '"1672531200.0"'

        >>> generate_timestamp_etag({"updated_at": datetime.now()})
        '"1672531200.123456"'
    """
    try:
        # Handle dictionary access
        if isinstance(obj, dict):
            timestamp = obj.get(timestamp_field)
        else:
            # Handle object attribute access
            timestamp = getattr(obj, timestamp_field, None)

        if timestamp is None:
            logger.warning(
                f"⚠️ No {timestamp_field} found for ETag generation, using current time"
            )
            timestamp = datetime.now()

        # Convert datetime to timestamp
        if isinstance(timestamp, datetime):
            timestamp_value = timestamp.timestamp()
        else:
            # Assume it's already a timestamp
            timestamp_value = float(timestamp)

        etag = f'"{timestamp_value}"'
        logger.debug(f"🏷️ Generated timestamp ETag: {etag}")
        return etag

    except Exception as e:
        logger.error(f"❌ ETag generation failed: {e}")
        # Fallback to current timestamp
        return f'"{datetime.now().timestamp()}"'


def generate_content_hash_etag(
    content: Union[str, dict, list], algorithm: str = "md5"
) -> str:
    """
    Generate ETag from content hash (for content without timestamps).

    Usage pattern from caching strategy:
    ```python
    etag = f'"{hashlib.md5(json.dumps(content).encode()).hexdigest()}"'
    ```

    Args:
        content: Content to hash (string, dict, list, etc.)
        algorithm: Hash algorithm (md5, sha1, sha256)

    Returns:
        ETag string in format: "abc123def456..."

    Examples:
        >>> generate_content_hash_etag({"key": "value"})
        '"d85b1213473c2fd7c2045020a6b9c62b"'

        >>> generate_content_hash_etag("file content", "sha1")
        '"2fd4e1c67a2d28fced849ee1bb76e7391b93eb12"'
    """
    try:
        # Convert content to string for hashing
        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, sort_keys=True, default=str)
        else:
            content_str = str(content)

        # Generate hash
        hasher = hashlib.new(algorithm)
        hasher.update(content_str.encode("utf-8"))
        hash_value = hasher.hexdigest()

        etag = f'"{hash_value}"'
        logger.debug(f"🏷️ Generated {algorithm} hash ETag: {etag}")
        return etag

    except Exception as e:
        logger.error(f"❌ Hash ETag generation failed: {e}")
        # Fallback to timestamp-based ETag
        return f'"{datetime.now().timestamp()}"'


def generate_composite_etag(
    obj_id: Union[int, str],
    timestamp: Optional[datetime] = None,
    version: Optional[Union[int, str]] = None,
) -> str:
    """
    Generate composite ETag from ID + timestamp/version (hybrid approach).

    Usage pattern from caching strategy and existing TODOs:
    ```python
    # ETag = f'"{image.id}-{image.updated_at.timestamp()}"'
    etag = generate_composite_etag(image.id, image.updated_at)
    ```

    Args:
        obj_id: Object ID (database primary key)
        timestamp: Optional timestamp for versioning
        version: Optional version number/string

    Returns:
        ETag string in format: "id-timestamp" or "id-version"

    Examples:
        >>> generate_composite_etag(123, datetime.now())
        '"123-1672531200.0"'

        >>> generate_composite_etag("image_456", version="v2")
        '"image_456-v2"'
    """
    try:
        parts = [str(obj_id)]

        if timestamp is not None:
            if isinstance(timestamp, datetime):
                parts.append(str(timestamp.timestamp()))
            else:
                parts.append(str(timestamp))

        if version is not None:
            parts.append(str(version))

        # If no timestamp or version provided, use current timestamp
        if len(parts) == 1:
            parts.append(str(datetime.now().timestamp()))

        etag = f'"{"-".join(parts)}"'
        logger.debug(f"🏷️ Generated composite ETag: {etag}")
        return etag

    except Exception as e:
        logger.error(f"❌ Composite ETag generation failed: {e}")
        return f'"{obj_id}-{datetime.now().timestamp()}"'


def generate_collection_etag(items: list, count_field: Optional[str] = None) -> str:
    """
    Generate ETag for collections/lists (for image count endpoints, etc.).

    Usage from caching strategy TODOs:
    ```python
    # ETag based on latest image timestamp + total count
    etag = generate_collection_etag(images, "total_count")
    ```

    Args:
        items: List of items (database results, etc.)
        count_field: Optional field name containing total count

    Returns:
        ETag string based on collection size + latest timestamp

    Examples:
        >>> generate_collection_etag([{"id": 1, "updated_at": datetime.now()}])
        '"1-1672531200.0"'
    """
    try:
        count = len(items)

        # Find latest timestamp in collection
        latest_timestamp = None
        for item in items:
            timestamp = None

            if isinstance(item, dict):
                timestamp = (
                    item.get("updated_at")
                    or item.get("created_at")
                    or item.get("timestamp")
                )
            else:
                timestamp = getattr(item, "updated_at", None) or getattr(
                    item, "created_at", None
                )

            if timestamp and isinstance(timestamp, datetime):
                if latest_timestamp is None or timestamp > latest_timestamp:
                    latest_timestamp = timestamp

        # Use current time if no timestamps found
        if latest_timestamp is None:
            latest_timestamp = datetime.now()

        # Include count field if provided
        if count_field and items:
            first_item = items[0]
            if isinstance(first_item, dict):
                total_count = first_item.get(count_field, count)
            else:
                total_count = getattr(first_item, count_field, count)
        else:
            total_count = count

        etag = f'"{total_count}-{latest_timestamp.timestamp()}"'
        logger.debug(f"🏷️ Generated collection ETag: {etag} (count: {total_count})")
        return etag

    except Exception as e:
        logger.error(f"❌ Collection ETag generation failed: {e}")
        return f'"{len(items) if items else 0}-{datetime.now().timestamp()}"'


def validate_etag_match(request_etag: Optional[str], current_etag: str) -> bool:
    """
    Validate If-None-Match header against current ETag.

    Usage in routers from caching strategy:
    ```python
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)  # Not Modified
    ```

    Args:
        request_etag: ETag from If-None-Match header
        current_etag: Current ETag for the resource

    Returns:
        True if ETags match (resource not modified), False if different

    Examples:
        >>> validate_etag_match('"1672531200.0"', '"1672531200.0"')
        True

        >>> validate_etag_match('"old"', '"new"')
        False
    """
    if not request_etag or not current_etag:
        return False

    # Handle weak ETags (W/"value") and strong ETags ("value")
    normalized_request = request_etag.strip().replace("W/", "")
    normalized_current = current_etag.strip().replace("W/", "")

    match = normalized_request == normalized_current

    if match:
        logger.debug(f"✅ ETag match: {request_etag} == {current_etag}")
    else:
        logger.debug(f"❌ ETag mismatch: {request_etag} != {current_etag}")

    return match


def extract_etag_from_headers(headers: dict) -> Optional[str]:
    """
    Extract ETag from request headers (If-None-Match, If-Match).

    Args:
        headers: Request headers dictionary

    Returns:
        ETag value or None if not present

    Examples:
        >>> extract_etag_from_headers({"if-none-match": '"1672531200.0"'})
        '"1672531200.0"'
    """
    # Check common ETag header names (case-insensitive)
    for header_name in ["if-none-match", "If-None-Match", "if-match", "If-Match"]:
        etag = headers.get(header_name)
        if etag:
            logger.debug(f"🏷️ Extracted ETag from {header_name}: {etag}")
            return etag.strip()

    return None


# Enhanced caching decorator with ETag support
def cached_response_with_etag(
    ttl_seconds: int = 60,
    key_prefix: str = "",
    etag_generator: Optional[Callable] = None,
):
    """
    Enhanced caching decorator with ETag support for cache validation.

    Args:
        ttl_seconds: Time to live for cached responses
        key_prefix: Optional prefix for cache keys
        etag_generator: Optional function to generate ETag from result

    Usage:
        @cached_response_with_etag(ttl_seconds=300, etag_generator=generate_timestamp_etag)
        async def get_settings(settings_service):
            settings = await settings_service.get_all_settings()
            return settings, generate_timestamp_etag(settings)
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key from function name and arguments
            cache_key_parts = (
                [key_prefix, func.__name__] if key_prefix else [func.__name__]
            )

            # Add string representations of args (skip first if it's a service instance)
            filtered_args = args[1:] if args and hasattr(args[0], "__class__") else args
            if filtered_args:
                cache_key_parts.extend(str(arg) for arg in filtered_args)
            if kwargs:
                cache_key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))

            cache_key = ":".join(filter(None, cache_key_parts))

            # Try to get from cache with ETag
            cached_result, cached_etag = await cache.get_with_etag(cache_key)
            if cached_result is not None:
                logger.debug(f"🎯 Cache hit with ETag: {cache_key}")
                return cached_result

            # Execute function and cache result with ETag
            result = await func(*args, **kwargs)

            # Generate ETag if generator provided
            etag = None
            if etag_generator and result:
                try:
                    etag = etag_generator(result)
                except Exception as e:
                    logger.warning(f"⚠️ ETag generation failed for {cache_key}: {e}")

            await cache.set(cache_key, result, ttl_seconds, etag)

            return result

        return wrapper

    return decorator


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
