"""
Settings Cache Manager for Logger Service.

This module provides efficient caching and retrieval of user-configurable logging
settings from the database, with intelligent fallbacks and performance optimizations.

Now integrates with the global settings cache for TTL-based caching as requested.
"""

import threading
import time
from typing import Any, Dict, Optional

from ....database.core import AsyncDatabase, SyncDatabase
from ....enums import LogLevel
from ....services.settings_cache import (
    cache_logger_settings,
    get_cached_logger_settings,
    get_settings_cache,
)


class LoggerSettingsCache:
    """
    Cache manager for logger service settings with intelligent fallbacks.

    Provides efficient, cached access to user-configurable logging settings:
    - Database log settings (retention, level)
    - File log settings (retention, level, rotation, compression)
    - Debug storage control

    Features:
    - 30-second cache TTL for performance
    - Automatic cache invalidation
    - Safe fallbacks for all settings
    - Both sync and async support
    - Smart type conversion (string to enum/bool/int)
    """

    # Default settings - performance-optimized and safe
    DEFAULT_SETTINGS = {
        # Database logging defaults
        "db_log_retention_days": 30,
        "db_log_level": LogLevel.INFO,
        # File logging defaults
        "file_log_retention_days": 7,
        "file_log_level": LogLevel.INFO,
        "file_log_max_files": 10,
        "file_log_max_size": 10,  # MB
        "file_log_enable_compression": True,
        "file_log_enable_rotation": True,
        # Debug storage control
        "debug_logs_store_in_db": False,
    }

    def __init__(
        self,
        async_db: Optional[AsyncDatabase] = None,
        sync_db: Optional[SyncDatabase] = None,
    ):
        """
        Initialize the settings cache manager.

        Args:
            async_db: Async database instance
            sync_db: Sync database instance
        """
        self.async_db = async_db
        self.sync_db = sync_db

        # Cache storage with thread safety
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = 30.0  # 30 seconds cache TTL
        self._lock = threading.RLock()  # Reentrant lock for nested calls

        # Batch loading optimization
        self._batch_cache_timestamp = 0
        self._batch_loaded = False

    def _is_cache_valid(self, setting_key: str) -> bool:
        """Check if cached value is still valid (thread-safe)."""
        with self._lock:
            if setting_key not in self._cache_timestamps:
                return False

            return (time.time() - self._cache_timestamps[setting_key]) < self._cache_ttl

    def _parse_setting_value(self, raw_value: str, setting_key: str) -> Any:
        """
        Parse raw string setting value to appropriate type.

        Args:
            raw_value: Raw string value from database
            setting_key: Setting key for type inference

        Returns:
            Parsed value with correct type
        """
        if raw_value is None:
            return self.DEFAULT_SETTINGS.get(setting_key)

        # Convert string to lowercase for consistency
        raw_value = str(raw_value).strip().lower()

        # Log level settings
        if setting_key in ["db_log_level", "file_log_level"]:
            try:
                return LogLevel[raw_value.upper()]
            except (KeyError, AttributeError):
                return self.DEFAULT_SETTINGS[setting_key]

        # Boolean settings
        elif setting_key in [
            "file_log_enable_compression",
            "file_log_enable_rotation",
            "debug_logs_store_in_db",
        ]:
            return raw_value in ("true", "1", "yes", "on")

        # Integer settings with validation
        elif setting_key in ["db_log_retention_days", "file_log_retention_days"]:
            try:
                value = int(raw_value)
                # Validate retention days (1-3650 days = ~10 years max)
                if value < 1 or value > 3650:
                    return self.DEFAULT_SETTINGS[setting_key]
                return value
            except (ValueError, TypeError):
                return self.DEFAULT_SETTINGS[setting_key]
        elif setting_key == "file_log_max_files":
            try:
                value = int(raw_value)
                # Validate file count (1-1000 files max)
                if value < 1 or value > 1000:
                    return self.DEFAULT_SETTINGS[setting_key]
                return value
            except (ValueError, TypeError):
                return self.DEFAULT_SETTINGS[setting_key]
        elif setting_key == "file_log_max_size":
            try:
                value = int(raw_value)
                # Validate file size (1MB-1000MB max)
                if value < 1 or value > 1000:
                    return self.DEFAULT_SETTINGS[setting_key]
                return value
            except (ValueError, TypeError):
                return self.DEFAULT_SETTINGS[setting_key]

        # Default: return as string
        return raw_value

    def _set_cache_value(self, setting_key: str, value: Any) -> None:
        """Set cached value with timestamp (thread-safe)."""
        with self._lock:
            self._cache[setting_key] = value
            self._cache_timestamps[setting_key] = time.time()

    async def get_setting_async(self, setting_key: str) -> Any:
        """
        Get a setting value asynchronously with caching.

        Args:
            setting_key: Setting key to retrieve

        Returns:
            Setting value with appropriate type
        """
        # Check cache first (thread-safe)
        if self._is_cache_valid(setting_key):
            with self._lock:
                return self._cache[setting_key]

        # Check if we should do batch loading
        if (
            not self._batch_loaded
            or (time.time() - self._batch_cache_timestamp) > self._cache_ttl
        ):
            await self._load_all_settings_async()
            self._batch_loaded = True
            self._batch_cache_timestamp = time.time()

            # Return from batch-loaded cache
            if setting_key in self._cache:
                return self._cache[setting_key]

        # Fallback: load individual setting
        try:
            if not self.async_db:
                return self.DEFAULT_SETTINGS.get(setting_key)

            async with self.async_db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT value FROM settings WHERE key = %s", (setting_key,)
                    )
                    result = await cur.fetchone()

                    if result:
                        parsed_value = self._parse_setting_value(result[0], setting_key)
                        self._set_cache_value(setting_key, parsed_value)
                        return parsed_value
                    else:
                        # Setting doesn't exist, use default
                        default_value = self.DEFAULT_SETTINGS.get(setting_key)
                        self._set_cache_value(setting_key, default_value)
                        return default_value

        except Exception:
            # Database error - return default and cache it briefly
            default_value = self.DEFAULT_SETTINGS.get(setting_key)
            self._set_cache_value(setting_key, default_value)
            return default_value

    def get_setting_sync(self, setting_key: str) -> Any:
        """
        Get a setting value synchronously with caching.

        Args:
            setting_key: Setting key to retrieve

        Returns:
            Setting value with appropriate type
        """
        # Check cache first (thread-safe)
        if self._is_cache_valid(setting_key):
            with self._lock:
                return self._cache[setting_key]

        # Check if we should do batch loading
        if (
            not self._batch_loaded
            or (time.time() - self._batch_cache_timestamp) > self._cache_ttl
        ):
            self._load_all_settings_sync()
            self._batch_loaded = True
            self._batch_cache_timestamp = time.time()

            # Return from batch-loaded cache
            if setting_key in self._cache:
                return self._cache[setting_key]

        # Fallback: load individual setting
        try:
            if not self.sync_db:
                return self.DEFAULT_SETTINGS.get(setting_key)

            with self.sync_db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT value FROM settings WHERE key = %s", (setting_key,)
                    )
                    result = cur.fetchone()

                    if result:
                        parsed_value = self._parse_setting_value(result[0], setting_key)
                        self._set_cache_value(setting_key, parsed_value)
                        return parsed_value
                    else:
                        # Setting doesn't exist, use default
                        default_value = self.DEFAULT_SETTINGS.get(setting_key)
                        self._set_cache_value(setting_key, default_value)
                        return default_value

        except Exception:
            # Database error - return default and cache it briefly
            default_value = self.DEFAULT_SETTINGS.get(setting_key)
            self._set_cache_value(setting_key, default_value)
            return default_value

    async def _load_all_settings_async(self) -> None:
        """Load all logging settings in a single query for efficiency."""
        try:
            if not self.async_db:
                return

            # Get all logging-related settings in one query
            setting_keys = list(self.DEFAULT_SETTINGS.keys())
            placeholders = ",".join(["%s"] * len(setting_keys))

            async with self.async_db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"SELECT key, value FROM settings WHERE key IN ({placeholders})",
                        setting_keys,
                    )
                    results = await cur.fetchall()

                    # Parse and cache all results
                    for key, value in results:
                        parsed_value = self._parse_setting_value(value, key)
                        self._set_cache_value(key, parsed_value)

                    # Cache defaults for missing settings
                    for key in setting_keys:
                        if key not in self._cache:
                            self._set_cache_value(key, self.DEFAULT_SETTINGS[key])

        except Exception:
            # On error, cache all defaults
            for key, default_value in self.DEFAULT_SETTINGS.items():
                self._set_cache_value(key, default_value)

    def _load_all_settings_sync(self) -> None:
        """Load all logging settings in a single query for efficiency (sync version)."""
        try:
            if not self.sync_db:
                return

            # Get all logging-related settings in one query
            setting_keys = list(self.DEFAULT_SETTINGS.keys())
            placeholders = ",".join(["%s"] * len(setting_keys))

            with self.sync_db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT key, value FROM settings WHERE key IN ({placeholders})",
                        setting_keys,
                    )
                    results = cur.fetchall()

                    # Parse and cache all results
                    for key, value in results:
                        parsed_value = self._parse_setting_value(value, key)
                        self._set_cache_value(key, parsed_value)

                    # Cache defaults for missing settings
                    for key in setting_keys:
                        if key not in self._cache:
                            self._set_cache_value(key, self.DEFAULT_SETTINGS[key])

        except Exception:
            # On error, cache all defaults
            for key, default_value in self.DEFAULT_SETTINGS.items():
                self._set_cache_value(key, default_value)

    async def initialize_missing_settings_async(self) -> None:
        """
        Initialize any missing logging settings in the database with defaults.

        This ensures all required settings exist and have reasonable defaults.
        """
        try:
            if not self.async_db:
                return

            async with self.async_db.get_connection() as conn:
                async with conn.cursor() as cur:
                    for key, default_value in self.DEFAULT_SETTINGS.items():
                        # Convert enum and boolean values to strings for storage
                        if isinstance(default_value, LogLevel):
                            str_value = default_value.value
                        elif isinstance(default_value, bool):
                            str_value = "true" if default_value else "false"
                        else:
                            str_value = str(default_value)

                        # Determine setting category and description
                        category = "logging"
                        if key.startswith("db_log"):
                            description = f"Database logging setting: {key}"
                        elif key.startswith("file_log"):
                            description = f"File logging setting: {key}"
                        elif key == "debug_logs_store_in_db":
                            description = "Enable database storage for debug logs (affects performance)"
                        else:
                            description = f"Logging setting: {key}"

                        # Insert setting if it doesn't exist
                        await cur.execute(
                            """
                            INSERT INTO settings (key, value, description, type, category)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (key) DO NOTHING
                            """,
                            (key, str_value, description, "string", category),
                        )

                    await conn.commit()

        except Exception as e:
            # Log initialization failure but don't raise
            print(f"Failed to initialize logging settings: {e}")

    def invalidate_cache(self, setting_key: Optional[str] = None) -> None:
        """
        Invalidate cache for specific setting or all settings.

        Args:
            setting_key: Specific key to invalidate, or None for all
        """
        if setting_key:
            self._cache.pop(setting_key, None)
            self._cache_timestamps.pop(setting_key, None)
        else:
            self._cache.clear()
            self._cache_timestamps.clear()
            self._batch_loaded = False
            self._batch_cache_timestamp = 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dictionary with cache statistics
        """
        current_time = time.time()

        valid_entries = sum(
            1
            for key, timestamp in self._cache_timestamps.items()
            if (current_time - timestamp) < self._cache_ttl
        )

        # Get global cache statistics
        global_cache = get_settings_cache()
        global_stats = global_cache.get_statistics()

        return {
            "total_cached_settings": len(self._cache),
            "valid_cached_entries": valid_entries,
            "cache_ttl_seconds": self._cache_ttl,
            "batch_loaded": self._batch_loaded,
            "batch_age_seconds": (
                current_time - self._batch_cache_timestamp if self._batch_loaded else 0
            ),
            "cached_settings": list(self._cache.keys()),
            "global_cache_stats": global_stats,
        }

    def get_all_logger_settings_with_global_cache(self) -> Dict[str, Any]:
        """
        Get all 8 user-configurable logger settings using global cache with TTL.

        This method implements the originally requested functionality to cache
        the logger settings with TTL for performance optimization.

        Returns:
            Dictionary with all 8 logger settings
        """
        # Try to get from global cache first
        cached_settings = get_cached_logger_settings()
        if cached_settings is not None:
            return cached_settings

        # Cache miss - load settings and cache them
        settings = {}
        for key in self.DEFAULT_SETTINGS.keys():
            settings[key] = self.get_setting_sync(key)

        # Cache in global cache with TTL
        cache_logger_settings(settings)

        return settings

    def invalidate_global_cache(self) -> None:
        """
        Invalidate the global settings cache when settings are updated.

        This ensures the cache reflects the latest values immediately
        when settings are changed.
        """
        cache = get_settings_cache()
        cache.invalidate("logger_settings")

        # Also clear local cache
        with self._lock:
            self._cache.clear()
            self._cache_timestamps.clear()
            self._batch_loaded = False
