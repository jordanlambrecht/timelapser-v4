# backend/app/services/video_pipeline/overlay_integration_service.py
"""
Overlay Integration Service - Unified Overlay Coordination

Handles overlay availability checking and fallback coordination for video generation.
Integrates with the unified overlay configuration system.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from ...config import settings
from ...database.core import SyncDatabase
from ...database.overlay_operations import SyncOverlayOperations
from ...database.timelapse_operations import SyncTimelapseOperations
from ...enums import LoggerName, LogSource
from ...models.overlay_model import OverlayConfiguration, TimelapseOverlay
from ...services.logger import get_service_logger
from ..overlay_pipeline.services.preset_service import SyncOverlayPresetService
from ..overlay_pipeline.utils.overlay_utils import validate_overlay_configuration

logger = get_service_logger(LoggerName.VIDEO_PIPELINE, LogSource.PIPELINE)


class OverlayIntegrationService:
    """
    Unified video overlay integration service.

    Handles overlay coordination for video generation using the unified overlay system:
    - Check overlay configuration availability
    - Validate overlay configurations and presets
    - Graceful fallback to no-overlay mode
    - Integration with unified overlay configuration system
    """

    def __init__(self, db: SyncDatabase, timelapse_ops=None, overlay_ops=None, preset_service=None):
        """
        Initialize OverlayIntegrationService with injected dependencies.

        Args:
            db: SyncDatabase instance for database operations
            timelapse_ops: Optional SyncTimelapseOperations instance
            overlay_ops: Optional SyncOverlayOperations instance 
            preset_service: Optional SyncOverlayPresetService instance
        """
        self.db = db
        self.timelapse_ops = timelapse_ops or self._get_default_timelapse_ops()
        self.overlay_ops = overlay_ops or self._get_default_overlay_ops()
        self.preset_service = preset_service or self._get_default_preset_service()
        
    def _get_default_timelapse_ops(self):
        """Fallback to create SyncTimelapseOperations directly if not injected"""
        # Using injected SyncTimelapseOperations singleton
        from ...dependencies.specialized import get_sync_timelapse_operations
        return get_sync_timelapse_operations()
        
    def _get_default_overlay_ops(self):
        """Fallback to create SyncOverlayOperations directly if not injected"""
        # Using injected SyncOverlayOperations singleton
        from ...dependencies.specialized import get_sync_overlay_operations
        return get_sync_overlay_operations()
        
    def _get_default_preset_service(self):
        """Fallback to create SyncOverlayPresetService directly if not injected"""
        return SyncOverlayPresetService(self.db)

        logger.debug("OverlayIntegrationService initialized with unified system")

    def check_overlays_available(self, timelapse_id: int) -> Dict[str, Any]:
        """
        Check if overlays are available for a timelapse using unified configuration system.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Dictionary with overlay availability status
        """
        try:
            logger.debug(
                f"Checking unified overlay availability for timelapse {timelapse_id}"
            )

            # Get timelapse info
            timelapse = self.timelapse_ops.get_timelapse_by_id(timelapse_id)
            if not timelapse:
                return {
                    "overlays_enabled": False,
                    "overlays_available": False,
                    "error": f"Timelapse {timelapse_id} not found",
                }

            # Get timelapse overlay configuration
            timelapse_overlay = self.overlay_ops.get_timelapse_overlay(timelapse_id)
            if not timelapse_overlay:
                logger.debug(
                    f"No overlay configuration found for timelapse {timelapse_id}"
                )
                return {
                    "overlays_enabled": False,
                    "overlays_available": False,
                    "message": "No overlay configuration found, will use regular images",
                }

            # Check if overlays are enabled for this timelapse
            if not timelapse_overlay.enabled:
                logger.debug(f"Overlays disabled for timelapse {timelapse_id}")
                return {
                    "overlays_enabled": False,
                    "overlays_available": False,
                    "message": "Overlays disabled for timelapse, will use regular images",
                }

            # Get effective configuration (merge preset + timelapse overrides)
            effective_config = self._get_effective_configuration(timelapse_overlay)
            if not effective_config:
                logger.debug(
                    f"No effective overlay configuration for timelapse {timelapse_id}"
                )
                return {
                    "overlays_enabled": True,
                    "overlays_available": False,
                    "message": "Invalid overlay configuration, will use regular images",
                }

            # Validate configuration completeness
            config_valid = validate_overlay_configuration(effective_config)
            if not config_valid:
                logger.debug(
                    f"Invalid overlay configuration for timelapse {timelapse_id}"
                )
                return {
                    "overlays_enabled": True,
                    "overlays_available": False,
                    "message": "Invalid overlay configuration, will use regular images",
                }

            # Check overlay system availability (basic infrastructure)
            overlay_system_available = self._check_overlay_system_availability()
            if not overlay_system_available:
                logger.debug(
                    f"Overlay system infrastructure not available for timelapse {timelapse_id}"
                )
                return {
                    "overlays_enabled": True,
                    "overlays_available": False,
                    "message": "Overlay system not available, will use regular images",
                }

            # All checks passed - overlays are available
            logger.debug(f"Overlays available for timelapse {timelapse_id}")
            return {
                "overlays_enabled": True,
                "overlays_available": True,
                "message": "Overlays available for video generation",
                "config_valid": True,
                "overlay_count": (
                    len(effective_config.overlay_items) if effective_config else 0
                ),
            }

        except Exception as e:
            logger.error(
                f"Failed to check overlay availability for timelapse {timelapse_id}: {e}"
            )
            return {
                "overlays_enabled": False,
                "overlays_available": False,
                "error": str(e),
            }

    def _get_effective_configuration(
        self, timelapse_overlay: TimelapseOverlay
    ) -> Optional[OverlayConfiguration]:
        """
        Get effective overlay configuration by merging preset and timelapse settings.

        Args:
            timelapse_overlay: Timelapse overlay configuration

        Returns:
            Effective overlay configuration or None if invalid
        """
        try:
            # Start with the timelapse's own overlay configuration
            base_config = timelapse_overlay.overlay_config

            # If a preset is specified, use preset as base and apply timelapse overrides
            if timelapse_overlay.preset_id:
                preset = self.preset_service.get_preset_by_id(
                    timelapse_overlay.preset_id
                )
                if preset and preset.overlay_config:
                    # Use preset configuration as base
                    preset_config = preset.overlay_config

                    # Create merged configuration
                    merged_items = list(preset_config.overlay_items)

                    # Apply timelapse-specific item overrides by adding new items
                    if base_config and base_config.overlay_items:
                        # Create dict for quick lookup by id
                        merged_dict = {item.id: item for item in merged_items}

                        # Add or override items from timelapse config
                        for item in base_config.overlay_items:
                            merged_dict[item.id] = item

                        merged_items = list(merged_dict.values())

                    # Apply timelapse-specific global setting overrides
                    merged_global_settings = preset_config.global_settings
                    if base_config and base_config.global_settings:
                        # Override global settings with timelapse-specific values
                        from ...models.overlay_model import GlobalSettings

                        global_settings_dict = merged_global_settings.model_dump()
                        timelapse_global_dict = base_config.global_settings.model_dump()

                        # Only override non-default values from timelapse config
                        for key, value in timelapse_global_dict.items():
                            if value is not None:
                                global_settings_dict[key] = value

                        merged_global_settings = GlobalSettings(**global_settings_dict)

                    # Create final merged configuration
                    return OverlayConfiguration(
                        overlay_items=merged_items,
                        global_settings=merged_global_settings,
                    )
                else:
                    logger.warning(
                        f"Preset {timelapse_overlay.preset_id} not found, using timelapse config only"
                    )

            # Return timelapse configuration if no preset or preset not found
            return base_config if base_config else None

        except Exception as e:
            logger.error(f"Failed to resolve effective overlay configuration: {e}")
            return None

    def _check_overlay_system_availability(self) -> bool:
        """
        Check if the overlay system infrastructure is available.

        Returns:
            True if overlay system is available
        """
        try:
            # Check if overlay service modules are available
            try:

                overlay_modules_available = True
            except ImportError as e:
                logger.debug(f"Overlay service modules not available: {e}")
                overlay_modules_available = False

            # Check if overlay directory structure exists
            overlay_base_dir = Path(settings.data_directory) / "overlays"
            overlay_structure_exists = overlay_base_dir.exists()

            # System is available if both modules and basic structure exist
            system_available = overlay_modules_available and overlay_structure_exists

            if system_available:
                logger.debug("Overlay system infrastructure is available")
            else:
                logger.debug(
                    f"Overlay system not available: modules={overlay_modules_available}, structure={overlay_structure_exists}"
                )

            return system_available

        except Exception as e:
            logger.error(f"Error checking overlay system availability: {e}")
            return False

    def get_overlay_mode_for_video(self, timelapse_id: int) -> str:
        """
        Determine which overlay mode to use for video generation using unified system.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            'overlay' if overlays should be used, 'regular' for regular images
        """
        try:
            overlay_status = self.check_overlays_available(timelapse_id)

            if overlay_status.get("overlays_enabled") and overlay_status.get(
                "overlays_available"
            ):
                logger.debug(f"Using overlay mode for timelapse {timelapse_id}")
                return "overlay"
            else:
                logger.debug(f"Using regular mode for timelapse {timelapse_id}")
                return "regular"

        except Exception as e:
            logger.error(
                f"Error determining overlay mode for timelapse {timelapse_id}: {e}"
            )
            return "regular"  # Default to regular images

    def get_service_health(self) -> Dict[str, Any]:
        """
        Get overlay integration service health status using unified system.

        Returns:
            Service health metrics dictionary
        """
        try:
            # Check database connectivity
            db_healthy = False
            try:
                with self.db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        db_healthy = cur.fetchone() is not None
            except Exception as e:
                logger.debug(f"Database health check failed: {e}")
                db_healthy = False

            # Check overlay operations availability
            overlay_ops_healthy = False
            try:
                # Test overlay operations with a simple query
                self.overlay_ops.get_timelapse_overlay(
                    0
                )  # Test query (result not used)
                overlay_ops_healthy = True  # If no exception, operations are available
            except Exception as e:
                logger.debug(f"Overlay operations health check failed: {e}")
                overlay_ops_healthy = False

            # Check overlay system infrastructure
            overlay_system_available = self._check_overlay_system_availability()

            # Service is healthy if database and overlay operations work
            # Overlay system availability affects functionality but not core health
            core_healthy = db_healthy and overlay_ops_healthy

            if core_healthy and overlay_system_available:
                status = "healthy"
                message = "All overlay integration components available"
            elif core_healthy:
                status = "degraded"
                message = "Core functionality available, overlay system may have issues"
            else:
                status = "unhealthy"
                message = "Core database or overlay operations unavailable"

            return {
                "service": "overlay_integration_service",
                "status": status,
                "database_connected": db_healthy,
                "overlay_operations_available": overlay_ops_healthy,
                "overlay_system_available": overlay_system_available,
                "message": message,
                "unified_system": True,  # Indicates this service uses unified overlay system
                "error": None,
            }

        except Exception as e:
            logger.error(f"Overlay integration service health check failed: {e}")
            return {
                "service": "overlay_integration_service",
                "status": "unhealthy",
                "database_connected": False,
                "overlay_operations_available": False,
                "overlay_system_available": False,
                "unified_system": True,
                "error": str(e),
            }
