# backend/app/database/settings_operations.py
"""
Settings database operations module - Composition Pattern.

This module handles all settings-related database operations including:
- Settings CRUD operations
- Settings dictionary management
- Configuration loading
"""

from typing import List, Optional, Dict, Any, Tuple
from loguru import logger

# Import database core for composition
from .core import AsyncDatabase, SyncDatabase
from ..models.settings_model import Setting
from ..models.shared_models import CorruptionSettings


class SettingsOperations:
    """Settings database operations using composition pattern."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Initialize with database instance."""
        self.db = db

    def _row_to_setting(self, row: Dict[str, Any]) -> Setting:
        """Convert database row to Setting model."""
        # Filter fields that belong to Setting model
        setting_fields = {k: v for k, v in row.items() if k in Setting.model_fields}
        return Setting(**setting_fields)

    async def get_all_settings(self) -> Dict[str, Any]:
        """
        Retrieve all settings as a dictionary.

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
        except Exception as e:
            logger.error(f"Failed to get all settings: {e}")
            raise

    async def get_all_setting_records(self) -> List[Setting]:
        """
        Retrieve all settings as Setting model instances.

        Returns:
            List of Setting model instances with full metadata
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM settings ORDER BY key")
                    results = await cur.fetchall()
                    return [self._row_to_setting(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to get all setting records: {e}")
            raise

    async def get_setting(self, key: str) -> Optional[str]:
        """
        Retrieve a specific setting value by key.

        Args:
            key: Setting key to retrieve

        Returns:
            Setting value, or None if not found

        Note: Returns str for simple value lookup (follows guidelines)
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT value FROM settings WHERE key = %s", (key,)
                    )
                    results = await cur.fetchall()
                    return results[0]["value"] if results else None
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            raise

    async def get_setting_record(self, key: str) -> Optional[Setting]:
        """
        Retrieve a specific setting record by key.

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
        except Exception as e:
            logger.error(f"Failed to get setting record {key}: {e}")
            raise

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
            logger.error(f"Invalid setting data: {error_msg}")
            raise ValueError(error_msg)

        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO settings (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key)
                        DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                        (key, value),
                    )

                    await self.db.broadcast_event(
                        "setting_updated", {"key": key, "value": value}
                    )
                    return True
        except Exception as e:
            logger.error(f"Failed to set setting {key}: {e}")
            raise

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
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    for key, value in settings_dict.items():
                        query = """
                        INSERT INTO settings (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key)
                        DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                        """
                        await cur.execute(query, (key, value))

                    await self.db.broadcast_event(
                        "settings_bulk_updated", {"settings": settings_dict}
                    )
                    return True
        except Exception as e:
            logger.error(f"Failed to set multiple settings: {e}")
            raise

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
                        await self.db.broadcast_event("setting_deleted", {"key": key})
                        return True
                    return False
        except Exception as e:
            logger.error(f"Failed to delete setting {key}: {e}")
            raise

    async def get_corruption_settings(self) -> CorruptionSettings:
        """
        Get all corruption detection related settings.

        Returns:
            CorruptionSettings model instance with proper types
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT key, value FROM settings 
                        WHERE key LIKE 'corruption_%'
                        ORDER BY key
                    """
                    )
                    results = await cur.fetchall()
                    settings_dict = {row["key"]: row["value"] for row in results}

                    # Convert string values to appropriate types with defaults
                    defaults = {
                        "corruption_detection_enabled": True,
                        "corruption_score_threshold": 70,
                        "corruption_auto_discard_enabled": False,
                        "corruption_auto_disable_degraded": False,
                        "corruption_degraded_consecutive_threshold": 10,
                        "corruption_degraded_time_window_minutes": 30,
                        "corruption_degraded_failure_percentage": 50,
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
                                result[key] = settings_dict[key].lower() in (
                                    "true",
                                    "1",
                                    "yes",
                                )
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
        except Exception as e:
            logger.error(f"Failed to get corruption settings: {e}")
            raise

    async def get_settings(self) -> List[Setting]:
        """
        Retrieve all settings as a list of Setting model instances.

        Returns:
            List of Setting model instances with id, key, value, timestamps
        """
        try:
            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT * FROM settings ORDER BY key")
                    results = await cur.fetchall()
                    return [self._row_to_setting(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to get settings list: {e}")
            raise

    async def get_settings_dict(self) -> Dict[str, Any]:
        """
        Retrieve all settings as a dictionary (backward compatibility alias).

        Returns:
            Dictionary containing all settings key-value pairs
        """
        return await self.get_all_settings()

    @staticmethod
    def validate_setting_data(key: str, value: str) -> Tuple[bool, Optional[str]]:
        """
        Validate setting data before database operations.

        Args:
            key: Setting key
            value: Setting value

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not key or not key.strip():
            return False, "Setting key cannot be empty"

        if len(key) > 255:
            return False, "Setting key cannot exceed 255 characters"

        if value is None:
            return False, "Setting value cannot be None"

        if len(value) > 10000:  # Reasonable limit for setting values
            return False, "Setting value too long (max 10000 characters)"

        return True, None


class SyncSettingsOperations:
    """Sync settings database operations for worker processes."""

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database instance."""
        self.db = db

    def _row_to_setting(self, row: Dict[str, Any]) -> Setting:
        """Convert database row to Setting model."""
        # Filter fields that belong to Setting model
        setting_fields = {k: v for k, v in row.items() if k in Setting.model_fields}
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
        except Exception as e:
            logger.error(f"Failed to get all settings: {e}")
            raise

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
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            raise

    def get_capture_interval_setting(self) -> int:
        """
        Get the capture interval setting as an integer.

        Returns:
            Capture interval in seconds (default: 300)
        """
        value = self.get_setting("capture_interval", "300")
        try:
            # value is guaranteed to be a string due to the default
            return int(value) if value is not None else 300
        except (ValueError, TypeError):
            return 300

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
                        WHERE key LIKE 'corruption_%'
                        ORDER BY key
                    """
                    )
                    results = cur.fetchall()
                    settings_dict = {row["key"]: row["value"] for row in results}

                    # Convert string values to appropriate types with defaults
                    defaults = {
                        "corruption_detection_enabled": True,
                        "corruption_score_threshold": 70,
                        "corruption_auto_discard_enabled": False,
                        "corruption_auto_disable_degraded": False,
                        "corruption_degraded_consecutive_threshold": 10,
                        "corruption_degraded_time_window_minutes": 30,
                        "corruption_degraded_failure_percentage": 50,
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
                                result[key] = settings_dict[key].lower() in (
                                    "true",
                                    "1",
                                    "yes",
                                )
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
        except Exception as e:
            logger.error(f"Failed to get corruption settings: {e}")
            raise

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
            logger.error(f"Invalid setting data: {error_msg}")
            raise ValueError(error_msg)

        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO settings (key, value) 
                        VALUES (%s, %s)
                        ON CONFLICT (key) 
                        DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                        (key, value),
                    )

                    self.db.broadcast_event(
                        "setting_updated", {"key": key, "value": value}
                    )
                    return True
        except Exception as e:
            logger.error(f"Failed to set setting {key}: {e}")
            raise

    def get_settings_dict(self) -> Dict[str, Any]:
        """
        Retrieve all settings as a dictionary (backward compatibility alias).

        Returns:
            Dictionary containing all settings key-value pairs
        """
        return self.get_all_settings()
