# backend/app/database/settings_operations.py
"""
Settings database operations module - Composition Pattern.

This module handles all settings-related database operations including:
- Settings CRUD operations
- Settings dictionary management
- Configuration loading
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg

from ..constants import (
    DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
    DEFAULT_DEGRADED_MODE_FAILURE_PERCENTAGE,
    DEFAULT_DEGRADED_MODE_FAILURE_THRESHOLD,
    DEFAULT_DEGRADED_MODE_TIME_WINDOW_MINUTES,
    MAX_SETTING_KEY_LENGTH,
    MAX_SETTING_VALUE_LENGTH,
)
from ..models.settings_model import Setting
from ..models.shared_models import CorruptionSettings
from ..utils.cache_invalidation import CacheInvalidationService
from ..utils.cache_manager import (
    cache,
    cached_response,
    generate_composite_etag,
)
from ..utils.time_utils import utc_now
from .core import AsyncDatabase, SyncDatabase
from .exceptions import SettingsOperationError


def _process_corruption_settings_shared(
    settings_dict: Dict[str, str],
) -> CorruptionSettings:
    """
    Shared helper function for processing corruption settings from database.

    This eliminates massive code duplication between async and sync get_corruption_settings methods.
    Handles type conversion, defaults, and validation for corruption settings.

    Args:
        settings_dict: Dictionary of raw settings from database (key-value strings)

    Returns:
        CorruptionSettings model instance with proper types
    """
    # Convert string values to appropriate types with defaults
    defaults = {
        "corruption_detection_enabled": True,
        "corruption_score_threshold": DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
        "corruption_auto_discard_enabled": False,
        "corruption_auto_disable_degraded": False,
        "corruption_degraded_consecutive_threshold": DEFAULT_DEGRADED_MODE_FAILURE_THRESHOLD,
        "corruption_degraded_time_window_minutes": DEFAULT_DEGRADED_MODE_TIME_WINDOW_MINUTES,
        "corruption_degraded_failure_percentage": DEFAULT_DEGRADED_MODE_FAILURE_PERCENTAGE,
    }

    # Apply type conversions and defaults
    result = {}
    boolean_keys = [
        "corruption_detection_enabled",
        "corruption_auto_discard_enabled",
        "corruption_auto_disable_degraded",
    ]
    integer_keys = [
        "corruption_score_threshold",
        "corruption_degraded_consecutive_threshold",
        "corruption_degraded_time_window_minutes",
        "corruption_degraded_failure_percentage",
    ]

    for key, default_value in defaults.items():
        if key in settings_dict:
            if key in boolean_keys:
                result[key] = settings_dict[key].lower() in ("true", "1", "yes")
            elif key in integer_keys:
                try:
                    result[key] = int(settings_dict[key])
                except (ValueError, TypeError):
                    result[key] = default_value
            else:
                result[key] = settings_dict[key]
        else:
            result[key] = default_value

    return CorruptionSettings.model_validate(result)


class SettingsOperations:
    """Settings database operations using composition pattern."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with database instance."""
        self.db = db
        # CacheInvalidationService is now used as static class methods

    async def _clear_settings_caches(
        self, setting_key: Optional[str] = None, updated_at: Optional[datetime] = None
    ) -> None:
        """Clear caches related to settings using sophisticated cache system."""
        # Clear settings-related caches using advanced cache manager
        cache_patterns = [
            "settings:get_all_settings",
            "settings:get_all_setting_records",
            "settings:get_setting",
            "settings:get_setting_record",
            "settings:get_corruption_settings",
            "settings:get_settings",
        ]

        if setting_key:
            cache_patterns.extend(
                [
                    f"settings:get_setting:{setting_key}",
                    f"settings:get_setting_record:{setting_key}",
                    f"settings:metadata:{setting_key}",
                ]
            )

            # Use ETag-aware invalidation if timestamp provided
            if updated_at:
                etag = generate_composite_etag(setting_key, updated_at)
                await CacheInvalidationService.invalidate_with_etag_validation(
                    f"settings:metadata:{setting_key}", etag
                )

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

    def _row_to_setting(self, row: Dict[str, Any]) -> Setting:
        """Convert database row to Setting model."""
        # Filter fields that belong to Setting model
        setting_fields = {
            k: v for k, v in row.items() if k in Setting.model_fields.keys()
        }
        return Setting(**setting_fields)

    @cached_response(ttl_seconds=300, key_prefix="settings")
    async def get_all_settings(self) -> Dict[str, Any]:
        """
        Retrieve all settings as a dictionary with sophisticated caching.

        Returns:
            Dictionary containing all settings key-value pairs

        Note: Returns Dict for key-value lookups (follows guidelines)
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT key, value FROM settings ORDER BY key")
                    results = await cur.fetchall()
                    return {row["key"]: row["value"] for row in results}
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                "Failed to retrieve all settings", operation="get_all_settings"
            ) from e

    @cached_response(ttl_seconds=300, key_prefix="settings")
    async def get_all_setting_records(self) -> List[Setting]:
        """
        Retrieve all settings as Setting model instances with sophisticated caching.

        Returns:
            List of Setting model instances with full metadata
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM settings ORDER BY key")
                    results = await cur.fetchall()
                    return [self._row_to_setting(row) for row in results]
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                "Failed to retrieve all setting records",
                operation="get_all_setting_records",
            ) from e

    async def get_setting(
        self, key: str, default: Optional[str] = None
    ) -> Optional[str]:
        """
        Retrieve a specific setting value by key using direct database access.

        Args:
            key: Setting key to retrieve
            default: Default value if setting not found

        Returns:
            Setting value, default value, or None if not found
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT value FROM settings WHERE key = %s", (key,)
                    )
                    results = await cur.fetchall()
                    return results[0]["value"] if results else default
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                f"Database operation failed: {e}", operation="get_setting"
            ) from e

    @cached_response(ttl_seconds=300, key_prefix="settings")
    async def get_setting_record(self, key: str) -> Optional[Setting]:
        """
        Retrieve a specific setting record by key with sophisticated caching.

        Args:
            key: Setting key to retrieve

        Returns:
            Setting model instance, or None if not found
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM settings WHERE key = %s", (key,))
                    results = await cur.fetchall()
                    return self._row_to_setting(results[0]) if results else None
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                f"Database operation failed: {e}", operation="database_operation"
            ) from e

    async def set_setting(self, key: str, value: str) -> bool:
        """
        Set a setting value, creating or updating as needed.

        Args:
            key: Setting key
            value: Setting value

        Returns:
            True if setting was saved successfully
        """
        # Validate input data
        is_valid, error_msg = self.validate_setting_data(key, value)
        if not is_valid:
            raise SettingsOperationError(
                f"Invalid setting data: {error_msg}", operation="set_setting"
            )

        try:
            current_time = utc_now()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO settings (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key)
                        DO UPDATE SET value = EXCLUDED.value, updated_at = %s
                    """,
                        (key, value, current_time),
                    )

                    # Clear related caches after successful setting update
                    await self._clear_settings_caches(key, updated_at=current_time)

                    return True
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                f"Failed to set setting '{key}' = '{value}'",
                operation="set_setting",
                details={"key": key, "value": value},
            ) from e

    async def set_multiple_settings(self, settings_dict: Dict[str, str]) -> bool:
        """
        Set multiple settings in a single transaction.

        Args:
            settings_dict: Dictionary of key-value pairs to set

        Returns:
            True if all settings were saved successfully
        """
        if not settings_dict:
            return True

        try:
            current_time = utc_now()
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    query = """
                        INSERT INTO settings (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key)
                        DO UPDATE SET value = EXCLUDED.value, updated_at = %s
                    """
                    params = [
                        (key, value, current_time)
                        for key, value in settings_dict.items()
                    ]
                    await cur.executemany(query, params)

                    # Clear related caches after successful bulk settings update
                    await self._clear_settings_caches(updated_at=current_time)

                    return True
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                f"Database operation failed: {e}", operation="database_operation"
            ) from e

    async def delete_setting(self, key: str) -> bool:
        """
        Delete a setting by key.

        Args:
            key: Setting key to delete

        Returns:
            True if setting was deleted successfully
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM settings WHERE key = %s", (key,))
                    affected = cur.rowcount

                    if affected and affected > 0:
                        # Clear related caches after successful deletion
                        await self._clear_settings_caches(key)
                        return True
                    return False
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                f"Database operation failed: {e}", operation="database_operation"
            ) from e

    @cached_response(ttl_seconds=300, key_prefix="settings")
    async def get_corruption_settings(self) -> CorruptionSettings:
        """
        Get all corruption detection related settings with sophisticated caching.

        Returns:
            CorruptionSettings model instance with proper types
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT key, value FROM settings
                        WHERE key ~ '^corruption_'
                        ORDER BY key
                    """
                    )
                    results = await cur.fetchall()
                    settings_dict = {row["key"]: row["value"] for row in results}

                    return _process_corruption_settings_shared(settings_dict)
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                f"Database operation failed: {e}", operation="database_operation"
            ) from e

    # Removed get_settings() - redundant duplicate of get_all_setting_records()
    # Use get_all_setting_records() directly for better performance

    # Removed get_settings_dict() - redundant alias for get_all_settings()
    # Use get_all_settings() directly for better performance

    @staticmethod
    def validate_setting_data(key: str, value: str) -> Tuple[bool, Optional[str]]:
        """
        Validate setting data before database operations.

        Delegates to business logic utility for better separation of concerns.
        """
        # Simple validation inline to avoid circular import
        if not key or len(key) > MAX_SETTING_KEY_LENGTH:
            raise ValueError(
                f"Setting key must be 1-{MAX_SETTING_KEY_LENGTH} characters"
            )
        if value and len(value) > MAX_SETTING_VALUE_LENGTH:
            raise ValueError(
                f"Setting value must be max {MAX_SETTING_VALUE_LENGTH} characters"
            )
        return True, None


class SyncSettingsOperations:
    """Sync settings database operations for worker processes."""

    def __init__(self, db: SyncDatabase) -> None:
        """Initialize with sync database instance."""
        self.db = db

    def _row_to_setting(self, row: Dict[str, Any]) -> Setting:
        """Convert database row to Setting model."""
        # Filter fields that belong to Setting model
        setting_fields = {
            k: v for k, v in row.items() if k in Setting.model_fields.keys()
        }
        return Setting(**setting_fields)

    def get_all_settings(self) -> Dict[str, Any]:
        """
        Retrieve all settings as a dictionary.

        Returns:
            Dictionary containing all settings key-value pairs
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT key, value FROM settings ORDER BY key")
                    results = cur.fetchall()
                    return {row["key"]: row["value"] for row in results}
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                f"Database operation failed: {e}", operation="database_operation"
            ) from e

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a specific setting value by key.

        Args:
            key: Setting key to retrieve
            default: Default value if setting not found

        Returns:
            Setting value, default value, or None if not found
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
                    results = cur.fetchall()
                    return results[0]["value"] if results else default
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                f"Database operation failed: {e}", operation="database_operation"
            ) from e

    def get_corruption_settings(self) -> CorruptionSettings:
        """
        Get all corruption detection related settings.

        Returns:
            CorruptionSettings model instance with proper types
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT key, value FROM settings
                        WHERE key ~ '^corruption_'
                        ORDER BY key
                    """
                    )
                    results = cur.fetchall()
                    settings_dict = {row["key"]: row["value"] for row in results}

                    return _process_corruption_settings_shared(settings_dict)
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                f"Database operation failed: {e}", operation="database_operation"
            ) from e

    def set_setting(self, key: str, value: str) -> bool:
        """
        Set a setting value, creating or updating as needed.

        Args:
            key: Setting key
            value: Setting value

        Returns:
            True if setting was saved successfully
        """
        # Validate input data
        is_valid, error_msg = SettingsOperations.validate_setting_data(key, value)
        if not is_valid:
            raise SettingsOperationError(
                f"Invalid setting data: {error_msg}", operation="sync_set_setting"
            )

        try:
            current_time = utc_now()
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO settings (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key)
                        DO UPDATE SET value = EXCLUDED.value, updated_at = %s
                    """,
                        (key, value, current_time),
                    )

                    return True
        except (psycopg.Error, KeyError, ValueError) as e:
            raise SettingsOperationError(
                f"Database operation failed: {e}", operation="database_operation"
            ) from e

    # Removed get_settings_dict() - redundant alias for get_all_settings()
    # Use get_all_settings() directly for better performance
