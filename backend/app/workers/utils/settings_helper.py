# backend/app/workers/utils/settings_helper.py
"""
Settings Helper Utility for Workers

Consolidates repeated settings access patterns across all workers to eliminate
code duplication and provide consistent settings handling.
"""

from typing import Dict, Any, Optional
from ...constants import (
    BOOLEAN_TRUE_STRING,
    SETTING_KEY_GENERATE_THUMBNAILS,
    DEFAULT_GENERATE_THUMBNAILS,
    SETTING_KEY_GENERATE_OVERLAYS,
    DEFAULT_GENERATE_OVERLAYS,
    SETTING_KEY_WEATHER_ENABLED,
    DEFAULT_WEATHER_ENABLED,
)


class SettingsHelper:
    """
    Utility class for consolidated settings access across workers.

    Eliminates redundant settings access patterns and provides
    consistent boolean parsing, default handling, and common settings queries.
    """

    def __init__(self, settings_service):
        """
        Initialize settings helper with settings service.

        Args:
            settings_service: SyncSettingsService instance
        """
        self.settings_service = settings_service

    def get_boolean_setting(self, key: str, default: str) -> bool:
        """
        Get boolean setting with consistent parsing.

        Handles the common pattern of:
        - Getting setting with default
        - Converting to lowercase
        - Comparing with BOOLEAN_TRUE_STRING

        Args:
            key: Setting key
            default: Default value

        Returns:
            Boolean value of setting
        """
        setting_value = self.settings_service.get_setting(key, default) or default
        return setting_value.lower() == BOOLEAN_TRUE_STRING

    def get_feature_flags(self) -> Dict[str, bool]:
        """
        Get common feature flags used across workers.

        Returns:
            Dictionary with feature flag states
        """
        return {
            "thumbnails_enabled": self.get_boolean_setting(
                SETTING_KEY_GENERATE_THUMBNAILS, DEFAULT_GENERATE_THUMBNAILS
            ),
            "overlays_enabled": self.get_boolean_setting(
                SETTING_KEY_GENERATE_OVERLAYS, DEFAULT_GENERATE_OVERLAYS
            ),
            "weather_enabled": self.get_boolean_setting(
                SETTING_KEY_WEATHER_ENABLED, DEFAULT_WEATHER_ENABLED
            ),
        }

    def get_retention_settings(self) -> Dict[str, int]:
        """
        Get retention settings for cleanup operations.

        Returns:
            Dictionary with retention periods in hours/days
        """
        return {
            "sse_events_hours": int(
                self.settings_service.get_setting("sse_event_retention_hours", "24")
            ),
            "log_retention_days": int(
                self.settings_service.get_setting("log_retention_days", "30")
            ),
            "temp_files_hours": int(
                self.settings_service.get_setting("temp_file_retention_hours", "6")
            ),
        }

    def get_worker_intervals(self) -> Dict[str, int]:
        """
        Get worker execution intervals.

        Returns:
            Dictionary with worker intervals in seconds
        """
        return {
            "weather_refresh_minutes": int(
                self.settings_service.get_setting(
                    "weather_refresh_interval_minutes", "60"
                )
            ),
            "health_check_minutes": int(
                self.settings_service.get_setting("health_check_interval_minutes", "5")
            ),
            "cleanup_hours": int(
                self.settings_service.get_setting("cleanup_interval_hours", "6")
            ),
        }

    def get_performance_settings(self) -> Dict[str, int]:
        """
        Get performance-related settings.

        Returns:
            Dictionary with performance thresholds and limits
        """
        return {
            "max_concurrent_jobs": int(
                self.settings_service.get_setting("max_concurrent_jobs", "5")
            ),
            "job_timeout_seconds": int(
                self.settings_service.get_setting("job_timeout_seconds", "300")
            ),
            "batch_size": int(
                self.settings_service.get_setting("worker_batch_size", "10")
            ),
        }

    async def get_all_settings_async(self) -> Dict[str, Any]:
        """
        Get all settings using async pattern for consistency with workers.

        Returns:
            Dictionary with all settings
        """
        import asyncio

        return await asyncio.get_event_loop().run_in_executor(
            None, self.settings_service.get_all_settings
        )

    def is_feature_enabled(self, feature_name: str) -> bool:
        """
        Check if a specific feature is enabled with sensible defaults.

        Args:
            feature_name: Name of feature to check

        Returns:
            True if feature is enabled
        """
        feature_mapping = {
            "thumbnails": (
                SETTING_KEY_GENERATE_THUMBNAILS,
                DEFAULT_GENERATE_THUMBNAILS,
            ),
            "overlays": (SETTING_KEY_GENERATE_OVERLAYS, DEFAULT_GENERATE_OVERLAYS),
            "weather": (SETTING_KEY_WEATHER_ENABLED, DEFAULT_WEATHER_ENABLED),
        }

        if feature_name not in feature_mapping:
            raise ValueError(f"Unknown feature: {feature_name}")

        key, default = feature_mapping[feature_name]
        return self.get_boolean_setting(key, default)
