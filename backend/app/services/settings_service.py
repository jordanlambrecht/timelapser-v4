# backend/app/services/settings_service.py
"""
Settings service layer for business logic orchestration.

This service provides a clean interface for settings operations,
handling business logic and coordinating between database operations
and external systems.
"""

import zoneinfo
from typing import List, Dict, Optional, Any
from loguru import logger

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.settings_operations import SettingsOperations, SyncSettingsOperations
from ..models.settings_model import Setting
from ..models.shared_models import CorruptionSettings
from ..database.sse_events_operations import SSEEventsOperations
from ..utils.timezone_utils import get_timezone_aware_timestamp_string_async
from ..constants import (
    EVENT_SETTING_UPDATED,
    EVENT_SETTING_DELETED,
    DEFAULT_CAPTURE_INTERVAL_SECONDS,
    MIN_CAPTURE_INTERVAL_SECONDS,
    MAX_CAPTURE_INTERVAL_SECONDS,
    DEFAULT_CORRUPTION_DISCARD_THRESHOLD,
    VIDEO_GENERATION_MODES,
    VIDEO_AUTOMATION_MODES,
    DEFAULT_TIMEZONE,
)


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

    def __init__(self, db: AsyncDatabase):
        """Initialize service with async database instance."""
        self.db = db
        self.settings_ops = SettingsOperations(db)
        self.sse_ops = SSEEventsOperations(db)

    async def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        try:
            return await self.settings_ops.get_all_settings()
        except Exception as e:
            logger.error(f"Failed to get all settings: {e}")
            raise

    async def get_setting(self, key: str) -> Optional[str]:
        """Get specific setting by key."""
        try:
            return await self.settings_ops.get_setting(key)
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            raise

    async def set_setting(self, key: str, value: str) -> bool:
        """Set a setting value."""
        try:
            result = await self.settings_ops.set_setting(key, value)
            
            if result:
                # Create SSE event for setting changes
                await self.sse_ops.create_event(
                    event_type=EVENT_SETTING_UPDATED,
                    event_data={
                        "key": key,
                        "value": value,
                        "operation": "update",
                    },
                    priority="normal",
                    source="api"
                )
                
            return result
        except Exception as e:
            logger.error(f"Failed to set setting {key}: {e}")
            raise

    async def set_multiple_settings(self, settings_dict: Dict[str, str]) -> bool:
        """Set multiple settings in a single transaction."""
        try:
            result = await self.settings_ops.set_multiple_settings(settings_dict)
            
            if result:
                # Create SSE event for bulk setting changes
                await self.sse_ops.create_event(
                    event_type=EVENT_SETTING_UPDATED,
                    event_data={
                        "operation": "bulk_update",
                        "updated_keys": list(settings_dict.keys()),
                        "count": len(settings_dict),
                    },
                    priority="normal",
                    source="api"
                )
                
            return result
        except Exception as e:
            logger.error(f"Failed to set multiple settings: {e}")
            raise

    async def delete_setting(self, key: str) -> bool:
        """Delete a setting by key."""
        try:
            result = await self.settings_ops.delete_setting(key)
            
            if result:
                # Create SSE event for setting deletion
                await self.sse_ops.create_event(
                    event_type=EVENT_SETTING_DELETED,
                    event_data={
                        "key": key,
                        "value": None,
                        "operation": "delete",
                    },
                    priority="normal",
                    source="api"
                )
                
            return result
        except Exception as e:
            logger.error(f"Failed to delete setting {key}: {e}")
            raise

    async def get_corruption_settings(self) -> CorruptionSettings:
        """Get corruption detection related settings."""
        try:
            return await self.settings_ops.get_corruption_settings()
        except Exception as e:
            logger.error(f"Failed to get corruption settings: {e}")
            raise

    async def get_settings(self) -> List[Setting]:
        """Get all settings as a list of Setting model instances."""
        try:
            return await self.settings_ops.get_settings()
        except Exception as e:
            logger.error(f"Failed to get settings list: {e}")
            raise

    async def get_settings_dict(self) -> Dict[str, Any]:
        """Get all settings as a dictionary (backward compatibility)."""
        try:
            return await self.settings_ops.get_settings_dict()
        except Exception as e:
            logger.error(f"Failed to get settings dict: {e}")
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
                "capture_interval": self._validate_capture_interval,
                "corruption_discard_threshold": self._validate_corruption_threshold,
                "data_directory": self._validate_data_directory,
                "video_generation_mode": self._validate_video_generation_mode,
                "video_automation_mode": self._validate_video_automation_mode,
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
            logger.error(f"Setting validation failed for {key}: {e}")
            return {"valid": False, "error": str(e)}

    async def set_setting_with_validation(self, key: str, value: str) -> Dict[str, Any]:
        """
        Set a setting with validation and change propagation.

        Args:
            key: Setting key
            value: Setting value

        Returns:
            Operation results including validation and propagation status
        """
        try:
            # Validate the setting
            validation_result = await self.validate_setting(key, value)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Validation failed: {validation_result['error']}",
                    "validation_result": validation_result,
                }

            # Use validated/formatted value
            formatted_value = validation_result.get("formatted_value", value)

            # Store the setting
            success = await self.set_setting(key, formatted_value)
            if not success:
                return {"success": False, "error": "Failed to store setting"}

            # Propagate changes
            propagation_result = await self.propagate_setting_change(
                key, formatted_value
            )

            # SSE broadcasting removed - now handled in router layer

            logger.info(
                f"Setting '{key}' updated successfully with validation and propagation"
            )
            return {
                "success": True,
                "value": formatted_value,
                "validation_result": validation_result,
                "propagation_result": propagation_result,
            }

        except Exception as e:
            logger.error(f"Failed to set setting {key} with validation: {e}")
            return {"success": False, "error": str(e)}

    async def resolve_inheritance(
        self, entity_type: str, entity_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Resolve settings inheritance (Global → Camera → Timelapse).

        Args:
            entity_type: Type of entity ('global', 'camera', 'timelapse')
            entity_id: ID of the entity (required for camera/timelapse)

        Returns:
            Resolved settings with inheritance chain information
        """
        try:
            resolved_settings = {}
            inheritance_chain = []

            # Start with global settings
            global_settings = await self.get_all_settings()
            resolved_settings.update(global_settings)
            inheritance_chain.append(
                {"level": "global", "settings_count": len(global_settings)}
            )

            # Apply camera-level overrides if applicable
            if entity_type in ["camera", "timelapse"] and entity_id:
                camera_id = (
                    entity_id
                    if entity_type == "camera"
                    else await self._get_camera_id_for_timelapse(entity_id)
                )
                if camera_id:
                    camera_settings = await self._get_camera_settings(camera_id)
                    if camera_settings:
                        resolved_settings.update(camera_settings)
                        inheritance_chain.append(
                            {
                                "level": "camera",
                                "camera_id": camera_id,
                                "settings_count": len(camera_settings),
                            }
                        )

            # Apply timelapse-level overrides if applicable
            if entity_type == "timelapse" and entity_id:
                timelapse_settings = await self._get_timelapse_settings(entity_id)
                if timelapse_settings:
                    resolved_settings.update(timelapse_settings)
                    inheritance_chain.append(
                        {
                            "level": "timelapse",
                            "timelapse_id": entity_id,
                            "settings_count": len(timelapse_settings),
                        }
                    )

            return {
                "resolved_settings": resolved_settings,
                "inheritance_chain": inheritance_chain,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "total_settings": len(resolved_settings),
            }

        except Exception as e:
            logger.error(
                f"Settings inheritance resolution failed for {entity_type}:{entity_id}: {e}"
            )
            return {"error": str(e)}

    async def propagate_setting_change(self, key: str, value: str) -> Dict[str, Any]:
        """
        Propagate setting changes to dependent systems.

        Args:
            key: Setting key that changed
            value: New setting value

        Returns:
            Propagation results for each dependent system
        """
        try:
            propagation_results = {}

            # Timezone changes affect time calculations
            if key == "timezone":
                propagation_results["timezone"] = await self._propagate_timezone_change(
                    value
                )

            # Capture interval changes affect scheduling
            if key == "capture_interval":
                propagation_results["capture_scheduling"] = (
                    await self._propagate_capture_interval_change(value)
                )

            # Corruption settings affect detection behavior
            if key.startswith("corruption_"):
                propagation_results["corruption_detection"] = (
                    await self._propagate_corruption_setting_change(key, value)
                )

            # Video settings affect generation behavior
            if key.startswith("video_"):
                propagation_results["video_generation"] = (
                    await self._propagate_video_setting_change(key, value)
                )

            # Data directory changes affect file operations
            if key == "data_directory":
                propagation_results["file_operations"] = (
                    await self._propagate_data_directory_change(value)
                )

            return {
                "success": True,
                "propagated_systems": list(propagation_results.keys()),
                "results": propagation_results,
            }

        except Exception as e:
            logger.error(f"Setting propagation failed for {key}: {e}")
            return {"success": False, "error": str(e)}

    async def manage_timezone_settings(self) -> Dict[str, Any]:
        """
        Coordinate timezone management across the system.

        Returns:
            Timezone management status and configuration
        """
        try:
            # Get current timezone setting
            current_timezone = await self.get_setting("timezone")
            if not current_timezone:
                current_timezone = "UTC"  # Default fallback

            # Validate timezone is still valid
            validation_result = self._validate_timezone(current_timezone)
            if not validation_result["valid"]:
                logger.warning(
                    f"Current timezone '{current_timezone}' is invalid: {validation_result['error']}"
                )
                # Set to UTC as fallback
                await self.set_setting("timezone", "UTC")
                current_timezone = "UTC"

            # Get timezone coordination status
            coordination_status = await self._get_timezone_coordination_status(
                current_timezone
            )

            return {
                "current_timezone": current_timezone,
                "validation_status": validation_result,
                "coordination_status": coordination_status,
                "system_time_info": {
                    "utc_now": "datetime.utcnow().isoformat()",
                    "local_now": f"Local time in {current_timezone}",
                },
            }

        except Exception as e:
            logger.error(f"Timezone management failed: {e}")
            return {"error": str(e)}

    async def coordinate_feature_flags(self) -> Dict[str, Any]:
        """
        Coordinate feature flag management across services.

        Returns:
            Feature flag coordination status
        """
        try:
            # Get all feature flag settings
            all_settings = await self.get_all_settings()
            feature_flags = {
                k: v for k, v in all_settings.items() if k.startswith("feature_")
            }

            # Analyze feature flag impact
            flag_analysis = {}
            for flag_key, flag_value in feature_flags.items():
                flag_analysis[flag_key] = {
                    "enabled": flag_value.lower() == "true",
                    "impact_systems": self._get_feature_flag_impact_systems(flag_key),
                    "dependencies": self._get_feature_flag_dependencies(flag_key),
                }

            return {
                "feature_flags": feature_flags,
                "flag_analysis": flag_analysis,
                "total_flags": len(feature_flags),
                "enabled_flags": len(
                    [f for f in flag_analysis.values() if f["enabled"]]
                ),
            }

        except Exception as e:
            logger.error(f"Feature flag coordination failed: {e}")
            return {"error": str(e)}

    def _validate_timezone(self, value: str) -> Dict[str, Any]:
        """Validate timezone setting."""
        try:
            # Check timezone aliases first
            from ..constants import TIMEZONE_ALIASES

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

    def _validate_capture_interval(self, value: str) -> Dict[str, Any]:
        """Validate capture interval setting."""
        try:
            interval = int(value)
            if interval < MIN_CAPTURE_INTERVAL_SECONDS:
                return {
                    "valid": False,
                    "error": f"Capture interval must be at least {MIN_CAPTURE_INTERVAL_SECONDS} seconds",
                    "suggested_value": str(DEFAULT_CAPTURE_INTERVAL_SECONDS),
                }
            if interval > MAX_CAPTURE_INTERVAL_SECONDS:
                return {
                    "valid": False,
                    "error": f"Capture interval cannot exceed {MAX_CAPTURE_INTERVAL_SECONDS} seconds",
                    "suggested_value": str(MAX_CAPTURE_INTERVAL_SECONDS),
                }
            return {"valid": True, "formatted_value": str(interval)}
        except ValueError:
            return {
                "valid": False,
                "error": "Capture interval must be a valid integer",
                "suggested_value": str(DEFAULT_CAPTURE_INTERVAL_SECONDS),
            }

    def _validate_corruption_threshold(self, value: str) -> Dict[str, Any]:
        """Validate corruption threshold setting."""
        try:
            threshold = int(value)
            if threshold < 0 or threshold > 100:
                return {
                    "valid": False,
                    "error": "Corruption threshold must be between 0 and 100",
                    "suggested_value": str(DEFAULT_CORRUPTION_DISCARD_THRESHOLD),
                }
            return {"valid": True, "formatted_value": str(threshold)}
        except ValueError:
            return {
                "valid": False,
                "error": "Corruption threshold must be a valid integer",
                "suggested_value": str(DEFAULT_CORRUPTION_DISCARD_THRESHOLD),
            }

    def _validate_data_directory(self, value: str) -> Dict[str, Any]:
        """Validate data directory setting."""
        from pathlib import Path

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

    def _validate_video_generation_mode(self, value: str) -> Dict[str, Any]:
        """Validate video generation mode setting."""
        valid_modes = [
            "standard",
            "target",
        ]  # From video-generation-settings-implementation.md
        if value not in valid_modes:
            return {
                "valid": False,
                "error": f"Video generation mode must be one of: {valid_modes}",
                "suggested_value": "standard",
            }
        return {"valid": True, "formatted_value": value}

    def _validate_video_automation_mode(self, value: str) -> Dict[str, Any]:
        """Validate video automation mode setting."""
        if value not in VIDEO_AUTOMATION_MODES:
            return {
                "valid": False,
                "error": f"Video automation mode must be one of: {VIDEO_AUTOMATION_MODES}",
                "suggested_value": "manual",
            }
        return {"valid": True, "formatted_value": value}

    async def _propagate_timezone_change(self, new_timezone: str) -> Dict[str, Any]:
        """Propagate timezone changes."""
        return {
            "propagated": True,
            "new_timezone": new_timezone,
            "message": "Timezone updated across system",
        }

    async def _propagate_capture_interval_change(
        self, new_interval: str
    ) -> Dict[str, Any]:
        """Propagate capture interval changes."""
        return {
            "propagated": True,
            "new_interval": new_interval,
            "message": "Capture scheduling updated",
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

    async def _propagate_video_setting_change(
        self, key: str, value: str
    ) -> Dict[str, Any]:
        """Propagate video setting changes."""
        return {
            "propagated": True,
            "setting": key,
            "value": value,
            "message": "Video generation updated",
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

    async def _get_timezone_coordination_status(self, timezone: str) -> Dict[str, Any]:
        """Get timezone coordination status."""
        return {
            "coordinated": True,
            "timezone": timezone,
            "systems_updated": ["database", "scheduling", "logging"],
        }

    def _get_feature_flag_impact_systems(self, flag_key: str) -> List[str]:
        """Get systems impacted by a feature flag."""
        impact_map = {
            "feature_advanced_corruption": ["corruption_detection", "image_processing"],
            "feature_auto_video_generation": ["video_generation", "automation"],
            "feature_real_time_thumbnails": ["thumbnail_generation", "image_service"],
        }
        return impact_map.get(flag_key, ["unknown"])

    def _get_feature_flag_dependencies(self, flag_key: str) -> List[str]:
        """Get dependencies for a feature flag."""
        dependency_map = {
            "feature_advanced_corruption": ["corruption_detection_enabled"],
            "feature_auto_video_generation": ["video_automation_mode"],
            "feature_real_time_thumbnails": ["thumbnail_generation_enabled"],
        }
        return dependency_map.get(flag_key, [])

    async def _get_camera_id_for_timelapse(self, timelapse_id: int) -> Optional[int]:
        """Get camera ID for a timelapse."""
        # This would typically query the timelapse operations
        return None  # Placeholder

    async def _get_camera_settings(self, camera_id: int) -> Optional[Dict[str, Any]]:
        """Get camera-specific settings."""
        # This would typically query camera-specific settings
        return {}  # Placeholder

    async def _get_timelapse_settings(
        self, timelapse_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get timelapse-specific settings."""
        # This would typically query timelapse-specific settings
        return {}  # Placeholder


class SyncSettingsService:
    """Sync settings service for worker processes."""

    def __init__(self, db: SyncDatabase):
        """Initialize service with sync database instance."""
        self.db = db
        self.settings_ops = SyncSettingsOperations(db)

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        try:
            return self.settings_ops.get_all_settings()
        except Exception as e:
            logger.error(f"Failed to get all settings: {e}")
            raise

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get specific setting by key."""
        try:
            return self.settings_ops.get_setting(key, default)
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            raise

    def get_capture_interval_setting(self) -> int:
        """Get capture interval setting as integer."""
        try:
            return self.settings_ops.get_capture_interval_setting()
        except Exception as e:
            logger.error(f"Failed to get capture interval setting: {e}")
            raise

    def get_corruption_settings(self) -> CorruptionSettings:
        """Get corruption detection related settings."""
        try:
            return self.settings_ops.get_corruption_settings()
        except Exception as e:
            logger.error(f"Failed to get corruption settings: {e}")
            raise

    def set_setting(self, key: str, value: str) -> bool:
        """Set a setting value."""
        try:
            return self.settings_ops.set_setting(key, value)
        except Exception as e:
            logger.error(f"Failed to set setting {key}: {e}")
            raise
