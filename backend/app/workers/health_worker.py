# backend/app/workers/health_worker.py
"""
Health monitoring worker for Timelapser v4.

Handles camera health monitoring and connectivity testing.
"""

from typing import Dict, Any
from .base_worker import BaseWorker
from ..services.camera_service import SyncCameraService
from ..services.capture_pipeline.rtsp_service import RTSPService
from ..utils.validation_helpers import validate_camera_exists, validate_camera_id


class HealthWorker(BaseWorker):
    """
    Worker responsible for camera health monitoring and connectivity testing.

    Handles:
    - Camera connectivity testing for all active cameras
    - Health status updates based on RTSP connectivity
    - Coordinated health monitoring separate from capture operations
    """

    def __init__(
        self,
        camera_service: SyncCameraService,
        rtsp_service: RTSPService,
    ):
        """
        Initialize health worker with injected dependencies.

        Args:
            camera_service: Camera operations service
            rtsp_service: RTSP service for connectivity testing
        """
        super().__init__("HealthWorker")
        self.camera_service = camera_service
        self.rtsp_service = rtsp_service

    async def initialize(self) -> None:
        """Initialize health worker resources."""
        self.log_info("Initialized health monitoring worker")

    async def cleanup(self) -> None:
        """Cleanup health worker resources."""
        self.log_info("Cleaned up health monitoring worker")

    async def check_camera_health(self) -> None:
        """
        Check and update camera health status based on RTSP connectivity.

        Performs comprehensive health monitoring for all active cameras:
        1. Retrieves all active cameras from database
        2. Tests RTSP connectivity without full image capture
        3. Updates database connectivity status for each camera
        4. Logs connectivity issues for monitoring and debugging
        """
        try:
            # Get all active cameras
            cameras = await self.run_in_executor(self.camera_service.get_active_cameras)

            if not cameras:
                self.log_debug("No active cameras found for health check")
                return

            self.log_info(f"Checking health for {len(cameras)} cameras")

            # Test connectivity for each camera
            for camera in cameras:
                camera_id = camera.id
                camera_name = camera.name

                try:
                    # Validate camera using validation helpers
                    validate_camera_exists(camera, camera_id)
                    camera_id = validate_camera_id(camera_id)

                    # Test RTSP connectivity using unified RTSP service
                    self.log_info(f"🔍 Health check - testing camera {camera_name} (ID: {camera_id})")
                    self.log_info(f"🔍 Health check - RTSP URL: {camera.rtsp_url}")
                    connectivity_result = await self.run_in_executor(
                        self.rtsp_service.test_connection, camera_id, camera.rtsp_url
                    )
                    success = connectivity_result.success
                    message = connectivity_result.error or "Connection test completed"

                    if success:
                        await self.run_in_executor(
                            self.camera_service.update_camera_connectivity,
                            camera_id,
                            True,
                            None,
                        )
                        self.log_debug(f"Camera {camera_name} is online: {message}")
                    else:
                        await self.run_in_executor(
                            self.camera_service.update_camera_connectivity,
                            camera_id,
                            False,
                            message,
                        )
                        self.log_warning(f"Camera {camera_name} is offline: {message}")

                except ValueError as e:
                    self.log_error(f"Invalid camera data for {camera_name}: {e}")
                except Exception as e:
                    if camera_id is not None:
                        await self.run_in_executor(
                            self.camera_service.update_camera_connectivity,
                            camera_id,
                            False,
                            str(e),
                        )
                    self.log_error(f"Health check failed for camera {camera_name}", e)

        except Exception as e:
            self.log_error("Error in check_camera_health", e)

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health worker status (STANDARDIZED METHOD NAME).

        Returns:
            Dict[str, Any]: Complete health worker status information
        """
        # Get base status from BaseWorker
        base_status = super().get_status()

        try:
            # Get camera count for monitoring
            camera_count = 0
            try:
                cameras = self.camera_service.get_active_cameras()
                camera_count = len(cameras) if cameras else 0
            except Exception as e:
                self.log_debug(f"Could not get camera count: {e}")

            # Add health-specific status information
            base_status.update(
                {
                    "worker_type": "HealthWorker",
                    # Service health status
                    "camera_service_status": (
                        "healthy" if self.camera_service else "unavailable"
                    ),
                    "rtsp_service_status": (
                        "healthy" if self.rtsp_service else "unavailable"
                    ),
                    # Health monitoring metrics
                    "active_cameras_count": camera_count,
                    "monitoring_enabled": all(
                        [
                            self.camera_service is not None,
                            self.rtsp_service is not None,
                        ]
                    ),
                    # Overall health worker status
                    "health_system_healthy": all(
                        [
                            self.camera_service is not None,
                            self.rtsp_service is not None,
                            self.running,
                        ]
                    ),
                }
            )

        except Exception as e:
            self.log_error("Error getting health worker status", e)
            base_status.update(
                {
                    "worker_type": "HealthWorker",
                    "camera_service_status": (
                        "healthy" if self.camera_service else "unavailable"
                    ),
                    "rtsp_service_status": (
                        "healthy" if self.rtsp_service else "unavailable"
                    ),
                    "health_system_healthy": False,
                    "status_error": str(e),
                }
            )

        return base_status
