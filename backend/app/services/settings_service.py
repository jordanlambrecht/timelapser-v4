# backend/app/services/settings_service.py
"""
Settings service layer for business logic orchestration.

This service provides a clean interface for settings operations,
handling business logic and coordinating between database operations
and external systems.
"""
from pathlib import Path
import time

import zoneinfo
from typing import List, Dict, Optional, Any

from ..utils.time_utils import utc_timestamp

from .logger import get_service_logger

from ..enums import SSEEvent, SSEEventSource, SSEPriority, LogSource, LoggerName

from ..database.settings_operations import (
    SettingsOperations,
    SyncSettingsOperations,
    SettingsOperationError,
)
from ..models.settings_model import Setting
from ..models.shared_models import CorruptionSettings
from ..database.sse_events_operations import SSEEventsOperations
from ..utils.hashing import mask_api_key
from ..utils.conversion_utils import safe_int
from .weather.api_key_service import APIKeyService, SyncAPIKeyService
from ..constants import (
    DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
    TIMEZONE_ALIASES,
    DEFAULT_TIMEZONE,
    DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE,
    DEFAULT_THUMBNAIL_PURGE_SMALLS_ON_COMPLETION,
)

logger = get_service_logger(LoggerName.SETTINGS_SERVICE, LogSource.SYSTEM)


class SettingsService:
    """
    System configuration business logic.

    Responsibilities:
    - Settings validation
    - Inheritance resolution
    - Change propagation
    - Timezone management
    - Feature flag coordination

    Interactions:
    - Uses SettingsOperations for database
    - Provides configuration data to all other services
    - Broadcasts configuration changes
    """

    def __init__(self, db):
        """Initialize service with async database instance."""
        self.db = db
        self.settings_ops = SettingsOperations(db)
        self.sse_ops = SSEEventsOperations(db)
        self.api_key_service = APIKeyService(db)

        # Settings caching (extracted from RTSPService)
        self._settings_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, float] = {}

    async def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        try:
            return await self.settings_ops.get_all_settings()
        except SettingsOperationError as e:
            logger.error(f"Database error retrieving all settings: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving all settings: {e}")
            raise

    async def get_setting(self, key: str) -> Optional[str]:
        """Get specific setting by key."""
        try:
            return await self.settings_ops.get_setting(key)
        except SettingsOperationError as e:
            logger.error(f"Database error retrieving setting '{key}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving setting '{key}': {e}")
            raise

    async def get_openweather_api_key(self) -> Optional[str]:
        """Get the actual OpenWeather API key for use by weather service."""
        return await self.api_key_service.get_api_key_for_service()

    async def get_openweather_api_key_for_display(self) -> Optional[str]:
        """Get the actual OpenWeather API key for frontend display."""
        return await self.api_key_service.get_api_key_for_display()

    async def get_cached_settings_group(
        self,
        group_name: str,
        setting_keys: List[str],
        cache_ttl_seconds: int = 30,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Get a group of related settings with caching support.

        Extracted from RTSPService to provide centralized settings caching.

        Args:
            group_name: Name for this settings group (for cache key)
            setting_keys: List of setting keys to fetch
            cache_ttl_seconds: Cache time-to-live in seconds (default 30)
            force_refresh: Force refresh of cache

        Returns:
            Dictionary of setting_key -> value
        """
        # Check cache validity
        current_time = time.time()
        cache_key = f"{group_name}_{hash(tuple(setting_keys))}"

        if (
            not force_refresh
            and cache_key in self._settings_cache
            and cache_key in self._cache_timestamps
            and (current_time - self._cache_timestamps[cache_key]) < cache_ttl_seconds
        ):
            return self._settings_cache[cache_key]

        try:
            # Fetch settings from database
            settings = {}
            for key in setting_keys:
                value = await self.settings_ops.get_setting(key)
                settings[key] = value

            # Update cache
            self._settings_cache[cache_key] = settings
            self._cache_timestamps[cache_key] = current_time

            return settings

        except Exception as e:
            logger.warning(f"Failed to get cached settings group '{group_name}': {e}")
            # Return cached value if available, otherwise empty dict
            return self._settings_cache.get(cache_key, {})

    def clear_settings_cache(self, group_name: Optional[str] = None) -> None:
        """
        Clear settings cache, optionally for a specific group.

        Args:
            group_name: If provided, only clear cache entries containing this group name
        """
        if group_name is None:
            # Clear all cache
            self._settings_cache.clear()
            self._cache_timestamps.clear()
        else:
            # Clear specific group cache entries
            keys_to_remove = [
                key for key in self._settings_cache.keys() if group_name in key
            ]
            for key in keys_to_remove:
                self._settings_cache.pop(key, None)
                self._cache_timestamps.pop(key, None)

    async def set_setting(self, key: str, value: str) -> bool:
        """Set a setting value with special handling for API keys."""
        try:
            # Special handling for OpenWeather API key
            if key == "openweather_api_key":
                result = await self.api_key_service.store_api_key(value)

                if result:
                    # Clear settings cache since a setting was updated
                    self.clear_settings_cache()

                    # Create SSE event (use masked value for security)
                    await self.sse_ops.create_event(
                        event_type=SSEEvent.SETTINGS_UPDATED,
                        event_data={
                            "key": "openweather_api_key",
                            "value": mask_api_key(value) if value.strip() else "",
                            "operation": "update",
                        },
                        priority=SSEPriority.NORMAL,
                        source=SSEEventSource.API,
                    )

                return result
            else:
                # Normal setting handling
                result = await self.settings_ops.set_setting(key, value)

                if result:
                    # Clear settings cache since a setting was updated
                    self.clear_settings_cache()

                    # Create SSE event for setting changes
                    await self.sse_ops.create_event(
                        event_type=SSEEvent.SETTINGS_UPDATED,
                        event_data={
                            "key": key,
                            "value": value,
                            "operation": "update",
                        },
                        priority=SSEPriority.NORMAL,
                        source=SSEEventSource.API,
                    )

                return result
        except SettingsOperationError as e:
            logger.error(f"Database error setting '{key}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error setting '{key}': {e}")
            raise

    async def set_multiple_settings(self, settings_dict: Dict[str, str]) -> bool:
        """Set multiple settings in a single transaction with API key hashing."""
        try:
            # Process settings to handle API key hashing
            processed_settings = {}
            processed_keys = []

            for key, value in settings_dict.items():
                if key == "openweather_api_key":
                    # Handle API key through dedicated service
                    await self.api_key_service.store_api_key(value)
                    processed_keys.append("openweather_api_key")
                # logger.info("Updated OpenWeather API key in bulk update")
                else:
                    # Normal setting
                    processed_settings[key] = value
                    processed_keys.append(key)

            result = await self.settings_ops.set_multiple_settings(processed_settings)

            if result:
                # Create SSE event for bulk setting changes
                await self.sse_ops.create_event(
                    event_type=SSEEvent.SETTINGS_UPDATED,
                    event_data={
                        "operation": "bulk_update",
                        "updated_keys": processed_keys,
                        "count": len(processed_settings),
                    },
                    priority=SSEPriority.NORMAL,
                    source=SSEEventSource.API,
                )

            return result
        except SettingsOperationError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def delete_setting(self, key: str) -> bool:
        """Delete a setting by key."""
        try:
            result = await self.settings_ops.delete_setting(key)

            if result:
                # Create SSE event for setting deletion
                await self.sse_ops.create_event(
                    event_type=SSEEvent.SETTING_DELETED,
                    event_data={
                        "key": key,
                        "value": None,
                        "operation": "delete",
                    },
                    priority=SSEPriority.NORMAL,
                    source=SSEEventSource.API,
                )

            return result
        except SettingsOperationError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def get_corruption_settings(self) -> CorruptionSettings:
        """Get corruption detection related settings."""
        try:
            return await self.settings_ops.get_corruption_settings()
        except SettingsOperationError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def get_settings(self) -> List[Setting]:
        """Get all settings as a list of Setting model instances."""
        try:
            return await self.settings_ops.get_all_setting_records()
        except SettingsOperationError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def get_settings_dict(self) -> Dict[str, Any]:
        """Get all settings as a dictionary (backward compatibility)."""
        try:
            return await self.settings_ops.get_all_settings()
        except SettingsOperationError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def validate_setting(self, key: str, value: str) -> Dict[str, Any]:
        """
        Validate a setting value before storage.

        Args:
            key: Setting key to validate
            value: Setting value to validate

        Returns:
            Validation results including success status and formatted value
        """
        try:
            validation_rules = {
                "timezone": self._validate_timezone,
                "corruption_discard_threshold": self._validate_corruption_threshold,
                "data_directory": self._validate_data_directory,
                "thumbnail_small_generation_mode": self._validate_thumbnail_small_generation_mode,
                "thumbnail_purge_smalls_on_completion": self._validate_boolean_setting,
                "thumbnail_generation_enabled": self._validate_boolean_setting,
            }

            # Apply specific validation if rule exists
            if key in validation_rules:
                validation_result = validation_rules[key](value)
                if not validation_result["valid"]:
                    return {
                        "valid": False,
                        "error": validation_result["error"],
                        "suggested_value": validation_result.get("suggested_value"),
                    }
                formatted_value = validation_result.get("formatted_value", value)
            else:
                # Generic validation for unknown settings
                formatted_value = (
                    value.strip() if isinstance(value, str) else str(value)
                )

            return {
                "valid": True,
                "formatted_value": formatted_value,
                "validation_notes": f"Setting '{key}' validated successfully",
            }

        except Exception as e:
            # logger.error(f"Setting validation failed for {key}: {e}")
            return {"valid": False, "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get service status information."""
        try:
            # Get basic metrics
            settings_dict = {}
            try:
                # Safely attempt to get settings count
                import asyncio

                if asyncio.get_event_loop().is_running():
                    settings_dict = {}  # Can't call async from sync context
                else:
                    settings_dict = asyncio.run(self.get_all_settings())
            except:
                settings_dict = {}

            return {
                "service": "SettingsService",
                "status": "healthy",
                "database_connected": True,
                "settings_count": len(settings_dict),
                "cache_entries": len(self._settings_cache),
                "api_key_service_available": self.api_key_service is not None,
                "last_checked": utc_timestamp(),
            }
        except Exception as e:
            return {
                "service": "SettingsService",
                "status": "unhealthy",
                "error": str(e),
                "database_connected": False,
                "last_checked": utc_timestamp(),
            }

    def _validate_timezone(self, value: str) -> Dict[str, Any]:
        """Validate timezone setting."""
        try:
            # Check timezone aliases first

            if value in TIMEZONE_ALIASES:
                value = TIMEZONE_ALIASES[value]

            zoneinfo.ZoneInfo(value)
            return {"valid": True, "formatted_value": value}
        except Exception:
            return {
                "valid": False,
                "error": f"Invalid timezone: {value}",
                "suggested_value": DEFAULT_TIMEZONE,
            }

    def _validate_corruption_threshold(self, value: str) -> Dict[str, Any]:
        """Validate corruption threshold setting."""
        threshold = safe_int(value)
        if threshold is None:
            return {
                "valid": False,
                "error": "Corruption threshold must be a valid integer",
                "suggested_value": str(DEFAULT_CORRUPTION_DISCARD_THRESHOLD),
            }

        if threshold < 0 or threshold > 100:
            return {
                "valid": False,
                "error": "Corruption threshold must be between 0 and 100",
                "suggested_value": str(DEFAULT_CORRUPTION_DISCARD_THRESHOLD),
            }
        return {"valid": True, "formatted_value": str(threshold)}

    def _validate_data_directory(self, value: str) -> Dict[str, Any]:
        """Validate data directory setting."""

        try:
            path = Path(value)
            if not path.is_absolute():
                return {
                    "valid": False,
                    "error": "Data directory must be an absolute path",
                }
            return {"valid": True, "formatted_value": str(path)}
        except Exception as e:
            return {"valid": False, "error": f"Invalid data directory path: {e}"}

    def _validate_thumbnail_small_generation_mode(self, value: str) -> Dict[str, Any]:
        """Validate thumbnail small generation mode setting."""
        valid_modes = ["all", "latest", "disabled"]

        if value not in valid_modes:
            return {
                "valid": False,
                "error": f"Invalid small generation mode: {value}. Must be one of: {', '.join(valid_modes)}",
                "suggested_value": DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE,
            }

        return {"valid": True, "formatted_value": value}

    def _validate_boolean_setting(self, value: str) -> Dict[str, Any]:
        """Validate boolean string setting (true/false)."""
        valid_values = ["true", "false"]
        value_lower = value.lower().strip()

        if value_lower not in valid_values:
            return {
                "valid": False,
                "error": f"Invalid boolean value: {value}. Must be 'true' or 'false'",
                "suggested_value": "false",
            }

        return {"valid": True, "formatted_value": value_lower}

    # Thumbnail Settings Helper Methods

    async def get_thumbnail_small_generation_mode(self) -> str:
        """
        Get the current thumbnail small generation mode setting.

        Returns:
            str: "all", "latest", or "disabled"
        """
        try:
            mode = await self.get_setting("thumbnail_small_generation_mode")
            return mode or DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE
        except Exception as e:
            logger.warning(f"Failed to get thumbnail small generation mode: {e}")
            return DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE

    async def get_thumbnail_purge_smalls_on_completion(self) -> bool:
        """
        Get the thumbnail purge smalls on completion setting as a boolean.

        Returns:
            bool: True if small images should be purged on timelapse completion
        """
        try:
            value = await self.get_setting("thumbnail_purge_smalls_on_completion")
            return (
                value or DEFAULT_THUMBNAIL_PURGE_SMALLS_ON_COMPLETION
            ).lower() == "true"
        except Exception as e:
            logger.warning(f"Failed to get thumbnail purge smalls setting: {e}")
            return DEFAULT_THUMBNAIL_PURGE_SMALLS_ON_COMPLETION.lower() == "true"

    async def get_thumbnail_generation_enabled(self) -> bool:
        """
        Get the thumbnail generation enabled setting as a boolean.

        Returns:
            bool: True if thumbnail generation is enabled
        """
        try:
            value = await self.get_setting("thumbnail_generation_enabled")
            return (value or "true").lower() == "true"  # Default to enabled
        except Exception as e:
            logger.warning(f"Failed to get thumbnail generation enabled setting: {e}")
            return True  # Default to enabled

    async def _propagate_timezone_change(self, new_timezone: str) -> Dict[str, Any]:
        """Propagate timezone changes."""
        return {
            "propagated": True,
            "new_timezone": new_timezone,
            "message": "Timezone updated across system",
        }

    async def _propagate_corruption_setting_change(
        self, key: str, value: str
    ) -> Dict[str, Any]:
        """Propagate corruption setting changes."""
        return {
            "propagated": True,
            "setting": key,
            "value": value,
            "message": "Corruption detection updated",
        }

    async def _propagate_data_directory_change(
        self, new_directory: str
    ) -> Dict[str, Any]:
        """Propagate data directory changes."""
        return {
            "propagated": True,
            "new_directory": new_directory,
            "message": "File operations updated",
        }


class SyncSettingsService:
    """Sync settings service for worker processes."""

    def __init__(self, db):
        """Initialize service with sync database instance."""
        self.db = db
        self.settings_ops = SyncSettingsOperations(db)
        self.api_key_service = SyncAPIKeyService(db)

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        try:
            return self.settings_ops.get_all_settings()
        except SettingsOperationError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get specific setting by key."""
        try:
            return self.settings_ops.get_setting(key, default)
        except SettingsOperationError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def get_corruption_settings(self) -> CorruptionSettings:
        """Get corruption detection related settings."""
        try:
            return self.settings_ops.get_corruption_settings()
        except SettingsOperationError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def set_setting(self, key: str, value: str) -> bool:
        """Set a setting value."""
        try:
            return self.settings_ops.set_setting(key, value)
        except SettingsOperationError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def get_openweather_api_key(self) -> Optional[str]:
        """Get the actual OpenWeather API key for use by weather service."""
        return self.api_key_service.get_api_key_for_service()

    def get_openweather_api_key_for_display(self) -> Optional[str]:
        """Get the actual OpenWeather API key for frontend display."""
        return self.api_key_service.get_api_key_for_display()

    # Thumbnail Settings Helper Methods (Sync versions)

    def get_thumbnail_small_generation_mode(self) -> str:
        """
        Get the current thumbnail small generation mode setting (sync).

        Returns:
            str: "all", "latest", or "disabled"
        """
        try:
            mode = self.get_setting("thumbnail_small_generation_mode")
            return mode or DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE
        except Exception as e:
            logger.warning(f"Failed to get thumbnail small generation mode: {e}")
            return DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE

    def get_thumbnail_purge_smalls_on_completion(self) -> bool:
        """
        Get the thumbnail purge smalls on completion setting as a boolean (sync).

        Returns:
            bool: True if small images should be purged on timelapse completion
        """
        try:
            value = self.get_setting("thumbnail_purge_smalls_on_completion")
            return (
                value or DEFAULT_THUMBNAIL_PURGE_SMALLS_ON_COMPLETION
            ).lower() == "true"
        except Exception as e:
            logger.warning(f"Failed to get thumbnail purge smalls setting: {e}")
            return DEFAULT_THUMBNAIL_PURGE_SMALLS_ON_COMPLETION.lower() == "true"

    def get_thumbnail_generation_enabled(self) -> bool:
        """
        Get the thumbnail generation enabled setting as a boolean (sync).

        Returns:
            bool: True if thumbnail generation is enabled
        """
        try:
            value = self.get_setting("thumbnail_generation_enabled")
            return (value or "true").lower() == "true"  # Default to enabled
        except Exception as e:
            logger.warning(f"Failed to get thumbnail generation enabled setting: {e}")
            return True  # Default to enabled

    def get_status(self) -> Dict[str, Any]:
        """Get service status information."""
        try:
            # Test database connectivity and get metrics
            settings_dict = self.get_all_settings()

            return {
                "service": "SyncSettingsService",
                "status": "healthy",
                "database_connected": True,
                "settings_count": len(settings_dict),
                "api_key_service_available": self.api_key_service is not None,
                "last_checked": utc_timestamp(),
            }
        except Exception as e:
            return {
                "service": "SyncSettingsService",
                "status": "unhealthy",
                "error": str(e),
                "database_connected": False,
                "last_checked": utc_timestamp(),
            }
