# backend/app/workers/mixins/settings_helper_mixin.py
"""
SettingsHelperMixin for standardized configuration handling.

Eliminates repetitive settings retrieval and validation patterns across workers
while providing consistent fallback behavior and type safety.

This mixin provides:
- Type-safe settings retrieval with validation
- Consistent fallback behavior for invalid settings
- Standard logging for configuration issues
- Common configuration validation patterns
"""

from typing import Any, Optional, Dict, List
from ...services.logger import get_service_logger
from ...enums import LoggerName, LogSource
from ...constants import BOOLEAN_TRUE_STRING

# Initialize mixin logger
settings_logger = get_service_logger(LoggerName.SYSTEM, LogSource.WORKER)


class SettingsHelperMixin:
    """
    Mixin for standardized configuration handling and validation.

    Provides consistent settings retrieval patterns across workers:
    - Type-safe settings retrieval with proper validation
    - Consistent fallback behavior for invalid or missing settings
    - Standard logging for configuration issues
    - Common validation patterns for different data types

    Requires the worker to have a settings_service attribute.

    Usage:
        class MyWorker(SettingsHelperMixin, BaseWorker):
            def __init__(self, settings_service, ...):
                self.settings_service = settings_service
                # ...

            def get_my_config(self):
                return {
                    "retry_count": self.get_int_setting(self.settings_service, "max_retries", 3),
                    "enabled": self.get_bool_setting(self.settings_service, "feature_enabled", True),
                    "batch_size": self.get_int_setting(self.settings_service, "batch_size", 10, min_value=1, max_value=100)
                }
    """

    def get_int_setting(
        self,
        settings_service: Any,
        key: str,
        default: int,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        logger: Optional[Any] = None,
    ) -> int:
        """
        Get integer setting with type validation and range checking.

        Args:
            settings_service: Settings service to use for retrieval
            key: Settings key to retrieve
            default: Default value if setting is missing or invalid
            min_value: Optional minimum allowed value
            max_value: Optional maximum allowed value
            logger: Optional specific logger (uses settings_logger if None)

        Returns:
            Integer setting value or default if invalid
        """
        if logger is None:
            logger = settings_logger

        try:
            # Get raw setting value
            raw_value = settings_service.get_setting(key, str(default))

            if raw_value is None:
                logger.debug(f"Setting '{key}' not found, using default: {default}")
                return default

            # Convert to integer
            try:
                int_value = int(raw_value)
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid integer setting '{key}' = '{raw_value}', using default: {default}",
                    extra_context={
                        "setting_key": key,
                        "invalid_value": raw_value,
                        "default_value": default,
                        "validation_error": "type_conversion",
                    },
                )
                return default

            # Validate range if specified
            if min_value is not None and int_value < min_value:
                logger.warning(
                    f"Setting '{key}' = {int_value} below minimum {min_value}, using default: {default}",
                    extra_context={
                        "setting_key": key,
                        "value": int_value,
                        "min_value": min_value,
                        "default_value": default,
                        "validation_error": "below_minimum",
                    },
                )
                return default

            if max_value is not None and int_value > max_value:
                logger.warning(
                    f"Setting '{key}' = {int_value} above maximum {max_value}, using default: {default}",
                    extra_context={
                        "setting_key": key,
                        "value": int_value,
                        "max_value": max_value,
                        "default_value": default,
                        "validation_error": "above_maximum",
                    },
                )
                return default

            return int_value

        except Exception as e:
            logger.error(
                f"Unexpected error getting integer setting '{key}': {e}",
                store_in_db=False
            )
            return default

    def get_bool_setting(
        self,
        settings_service: Any,
        key: str,
        default: bool,
        logger: Optional[Any] = None,
    ) -> bool:
        """
        Get boolean setting with consistent true/false interpretation.

        Args:
            settings_service: Settings service to use for retrieval
            key: Settings key to retrieve
            default: Default value if setting is missing or invalid
            logger: Optional specific logger (uses settings_logger if None)

        Returns:
            Boolean setting value or default if invalid
        """
        if logger is None:
            logger = settings_logger

        try:
            # Get raw setting value
            raw_value = settings_service.get_setting(key, str(default).lower())

            if raw_value is None:
                logger.debug(f"Setting '{key}' not found, using default: {default}")
                return default

            # Convert to boolean using consistent logic
            if isinstance(raw_value, bool):
                return raw_value
            elif isinstance(raw_value, str):
                return raw_value.lower() == BOOLEAN_TRUE_STRING
            else:
                logger.warning(
                    f"Invalid boolean setting '{key}' = '{raw_value}', using default: {default}",
                    extra_context={
                        "setting_key": key,
                        "invalid_value": raw_value,
                        "default_value": default,
                        "validation_error": "invalid_type",
                    },
                )
                return default

        except Exception as e:
            logger.error(
                f"Unexpected error getting boolean setting '{key}': {e}",
                store_in_db=False
            )
            return default

    def get_string_setting(
        self,
        settings_service: Any,
        key: str,
        default: str,
        allowed_values: Optional[List[str]] = None,
        logger: Optional[Any] = None,
    ) -> str:
        """
        Get string setting with optional validation against allowed values.

        Args:
            settings_service: Settings service to use for retrieval
            key: Settings key to retrieve
            default: Default value if setting is missing or invalid
            allowed_values: Optional list of allowed string values
            logger: Optional specific logger (uses settings_logger if None)

        Returns:
            String setting value or default if invalid
        """
        if logger is None:
            logger = settings_logger

        try:
            # Get raw setting value
            raw_value = settings_service.get_setting(key, default)

            if raw_value is None:
                logger.debug(f"Setting '{key}' not found, using default: {default}")
                return default

            string_value = str(raw_value)

            # Validate against allowed values if specified
            if allowed_values is not None and string_value not in allowed_values:
                logger.warning(
                    f"Invalid string setting '{key}' = '{string_value}', not in allowed values {allowed_values}, using default: {default}",
                    extra_context={
                        "setting_key": key,
                        "invalid_value": string_value,
                        "allowed_values": allowed_values,
                        "default_value": default,
                        "validation_error": "not_in_allowed_values",
                    },
                )
                return default

            return string_value

        except Exception as e:
            logger.error(
                f"Unexpected error getting string setting '{key}': {e}",
                store_in_db=False
            )
            return default

    def get_retention_settings(
        self,
        settings_service: Any,
        setting_keys_and_defaults: Dict[str, int],
        logger: Optional[Any] = None,
    ) -> Dict[str, int]:
        """
        Get multiple retention settings with consistent validation.

        Common pattern for workers that need multiple retention period settings.

        Args:
            settings_service: Settings service to use for retrieval
            setting_keys_and_defaults: Dict mapping setting keys to default values
            logger: Optional specific logger (uses settings_logger if None)

        Returns:
            Dictionary with validated retention settings
        """
        if logger is None:
            logger = settings_logger

        retention_settings = {}

        for setting_key, default_value in setting_keys_and_defaults.items():
            retention_settings[setting_key] = self.get_int_setting(
                settings_service=settings_service,
                key=setting_key,
                default=default_value,
                min_value=0,  # Retention periods should be non-negative
                logger=logger,
            )

        logger.debug(
            f"Retrieved retention settings: {retention_settings}",
            extra_context={
                "operation": "get_retention_settings",
                "settings_count": len(retention_settings),
            },
        )

        return retention_settings

    def validate_required_settings(
        self,
        settings_service: Any,
        required_settings: List[str],
        logger: Optional[Any] = None,
    ) -> Dict[str, bool]:
        """
        Validate that required settings are present and non-empty.

        Args:
            settings_service: Settings service to use for retrieval
            required_settings: List of setting keys that must be present
            logger: Optional specific logger (uses settings_logger if None)

        Returns:
            Dictionary mapping setting keys to boolean validation results
        """
        if logger is None:
            logger = settings_logger

        validation_results = {}

        for setting_key in required_settings:
            try:
                value = settings_service.get_setting(setting_key)
                is_valid = value is not None and str(value).strip() != ""
                validation_results[setting_key] = is_valid

                if not is_valid:
                    logger.warning(
                        f"Required setting '{setting_key}' is missing or empty",
                        extra_context={
                            "setting_key": setting_key,
                            "validation_result": "missing_or_empty",
                            "operation": "validate_required_settings",
                        },
                    )

            except Exception as e:
                logger.error(
                    f"Error validating required setting '{setting_key}': {e}",
                    store_in_db=False
                )
                validation_results[setting_key] = False

        return validation_results
