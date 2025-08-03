# backend/app/services/video_pipeline/overlay_integration_service.py
"""
Overlay Integration Service - Simplified Overlay Coordination

Handles overlay availability checking and fallback coordination.
Simplified version of OverlayManagementService focused on integration only.
"""

from typing import Dict, Any
from pathlib import Path
from ...services.logger import get_service_logger
from ...enums import LoggerName

from ...database.core import SyncDatabase

logger = get_service_logger(LoggerName.VIDEO_PIPELINE)
from ...database.timelapse_operations import SyncTimelapseOperations
from ...config import settings


class OverlayIntegrationService:
    """
    Simplified video overlay integration service.

    Handles overlay coordination for video generation:
    - Check overlay availability
    - Graceful fallback to no-overlay mode
    - Simple overlay status reporting
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize OverlayIntegrationService with database dependency.

        Args:
            db: SyncDatabase instance for database operations
        """
        self.db = db
        self.timelapse_ops = SyncTimelapseOperations(db)

        logger.debug("OverlayIntegrationService initialized")

    def check_overlays_available(self, timelapse_id: int) -> Dict[str, Any]:
        """
        Check if overlays are available for a timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Dictionary with overlay availability status
        """
        try:
            logger.debug(f"Checking overlay availability for timelapse {timelapse_id}")

            # Get timelapse info
            timelapse = self.timelapse_ops.get_timelapse_by_id(timelapse_id)
            if not timelapse:
                return {
                    "overlays_enabled": False,
                    "overlays_available": False,
                    "error": f"Timelapse {timelapse_id} not found",
                }

            # Check if overlays are enabled for this timelapse
            # For now, we'll check if overlay system is available at all
            overlay_system_available = self._check_overlay_system_availability()

            if not overlay_system_available:
                logger.debug(
                    f"Overlay system not available for timelapse {timelapse_id}"
                )
                return {
                    "overlays_enabled": False,
                    "overlays_available": False,
                    "message": "Overlay system not available, will use regular images",
                }

            # If overlay system is available, check for existing overlay images
            overlay_images_exist = self._check_overlay_images_exist(
                timelapse_id, timelapse.camera_id
            )

            return {
                "overlays_enabled": True,
                "overlays_available": overlay_images_exist,
                "message": (
                    "Overlay images available"
                    if overlay_images_exist
                    else "No overlay images found, will use regular images"
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

    def _check_overlay_system_availability(self) -> bool:
        """
        Check if the overlay system is available.

        Returns:
            True if overlay system is available
        """
        try:
            # Check if overlay service modules are available
            try:

                overlay_modules_available = True
            except ImportError:
                logger.debug("Overlay service modules not available")
                overlay_modules_available = False

            # Check if overlay directory structure exists
            overlay_base_dir = Path(settings.data_directory) / "overlays"
            overlay_structure_exists = overlay_base_dir.exists()

            # System is available if both modules and basic structure exist
            system_available = overlay_modules_available and overlay_structure_exists

            if system_available:
                logger.debug("Overlay system is available")
            else:
                logger.debug(
                    f"Overlay system not available: modules={overlay_modules_available}, structure={overlay_structure_exists}"
                )

            return system_available

        except Exception as e:
            logger.error(f"Error checking overlay system availability: {e}")
            return False

    def _check_overlay_images_exist(self, timelapse_id: int, camera_id: int) -> bool:
        """
        Check if overlay images exist for the timelapse.

        Args:
            timelapse_id: ID of the timelapse
            camera_id: ID of the camera

        Returns:
            True if overlay images exist
        """
        try:
            # Check for overlay images in expected location
            # Pattern: data/cameras/camera-{id}/overlays/
            overlay_dir = (
                Path(settings.data_directory) / f"cameras/camera-{camera_id}/overlays"
            )

            if not overlay_dir.exists():
                logger.debug(f"Overlay directory does not exist: {overlay_dir}")
                return False

            # Check if any overlay images exist
            overlay_files = list(overlay_dir.glob("*.jpg")) + list(
                overlay_dir.glob("*.png")
            )

            if overlay_files:
                logger.debug(
                    f"Found {len(overlay_files)} overlay images for camera {camera_id}"
                )
                return True
            else:
                logger.debug(f"No overlay images found for camera {camera_id}")
                return False

        except Exception as e:
            logger.error(f"Error checking overlay images for camera {camera_id}: {e}")
            return False

    def get_overlay_mode_for_video(self, timelapse_id: int) -> str:
        """
        Determine which overlay mode to use for video generation.

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
        Get overlay integration service health status.

        Returns:
            Service health metrics dictionary
        """
        try:
            overlay_system_available = self._check_overlay_system_availability()

            # Service is "degraded" if overlay system unavailable but service functional
            status = "healthy" if overlay_system_available else "degraded"

            return {
                "service": "overlay_integration_service",
                "status": status,
                "overlay_system_available": overlay_system_available,
                "database_connected": self.db is not None,
                "message": (
                    "Overlay system available"
                    if overlay_system_available
                    else "Overlay system unavailable, falling back to regular images"
                ),
                "error": None,
            }

        except Exception as e:
            logger.error(f"Overlay integration service health check failed: {e}")
            return {
                "service": "overlay_integration_service",
                "status": "unhealthy",
                "overlay_system_available": False,
                "database_connected": False,
                "error": str(e),
            }
