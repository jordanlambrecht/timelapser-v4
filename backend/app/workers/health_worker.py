# backend/app/workers/health_worker.py
"""
Health monitoring worker for Timelapser v4.

Handles camera health monitoring and connectivity testing.
"""

from typing import Dict, Any, Optional
from .base_worker import BaseWorker
from .utils.worker_status_builder import WorkerStatusBuilder
from .models.health_responses import HealthWorkerStatus
from .exceptions import (
    ServiceUnavailableError,
    WorkerInitializationError,
    HealthCheckError,
)
from ..services.camera_service import SyncCameraService
from ..services.capture_pipeline.rtsp_service import RTSPService
from ..services.health_workflow_service import HealthWorkflowService
from ..utils.validation_helpers import validate_camera_exists, validate_camera_id
from ..services.logger import get_service_logger
from ..enums import LoggerName, LogSource, WorkerType, LogEmoji
from ..models.health_model import HealthStatus

# Initialize health worker logger
health_logger = get_service_logger(LoggerName.HEALTH_WORKER, LogSource.WORKER)


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
        async_camera_service: Optional[Any] = None,
    ):
        """
        Initialize health worker with injected dependencies.

        Args:
            camera_service: Camera operations service
            rtsp_service: RTSP service for connectivity testing
            async_camera_service: Optional async camera service for performance optimization
        """
        super().__init__("HealthWorker")
        self.camera_service = camera_service
        self.rtsp_service = rtsp_service

        # Store async services for performance optimization
        self.async_camera_service = async_camera_service

        # Initialize health workflow service for Service Layer Boundary Pattern
        self.health_service = HealthWorkflowService()

    async def initialize(self) -> None:
        """Initialize health worker resources."""
        try:
            # Validate required dependencies
            if not self.camera_service:
                raise WorkerInitializationError("HealthWorker requires camera_service")
            if not self.rtsp_service:
                raise WorkerInitializationError("HealthWorker requires rtsp_service")

            health_logger.info(
                "Initialized health monitoring worker", store_in_db=False
            )
        except WorkerInitializationError as e:
            health_logger.error(
                f"Failed to initialize health worker: {e}", store_in_db=False
            )
            raise

    async def cleanup(self) -> None:
        """Cleanup health worker resources."""
        health_logger.info("Cleaned up health monitoring worker", store_in_db=False)

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
            # Get all active cameras using async service
            if not self.async_camera_service:
                raise ServiceUnavailableError(
                    "No async camera service available for health check"
                )

            cameras = await self.async_camera_service.get_active_cameras()

            if not cameras:
                health_logger.debug(
                    "No active cameras found for health check", store_in_db=False
                )
                return

            health_logger.info(
                f"Checking health for {len(cameras)} cameras", store_in_db=False
            )

            # Test connectivity for each camera
            for camera in cameras:
                camera_id = camera.id
                camera_name = camera.name

                try:
                    # Validate camera using validation helpers
                    validate_camera_exists(camera, camera_id)
                    camera_id = validate_camera_id(camera_id)

                    # Test RTSP connectivity using unified RTSP service
                    health_logger.info(
                        f"Health check - testing camera {camera_name} (ID: {camera_id})",
                        emoji=LogEmoji.CAMERA,
                        store_in_db=False,
                    )
                    health_logger.debug(
                        f"Health check - RTSP URL: {camera.rtsp_url}", store_in_db=False
                    )
                    connectivity_result = await self.run_in_executor(
                        self.rtsp_service.test_connection, camera_id, camera.rtsp_url
                    )
                    success = connectivity_result.success
                    message = connectivity_result.error or "Connection test completed"

                    if success:
                        await self.async_camera_service.update_camera_connectivity(
                            camera_id, True, None
                        )
                        health_logger.debug(
                            f"Camera {camera_name} is online: {message}",
                            store_in_db=False,
                        )
                    else:
                        await self.async_camera_service.update_camera_connectivity(
                            camera_id, False, message
                        )
                        health_logger.warning(
                            f"Camera {camera_name} is offline: {message}",
                            store_in_db=False,
                        )

                except ValueError as e:
                    health_logger.error(
                        f"Invalid camera data for {camera_name}: {e}", store_in_db=False
                    )
                except Exception as e:
                    if camera_id is not None:
                        await self.async_camera_service.update_camera_connectivity(
                            camera_id, False, str(e)
                        )
                    raise HealthCheckError(
                        f"Health check failed for camera {camera_name}: {e}"
                    )

        except HealthCheckError as e:
            health_logger.error(f"Health check error: {e}")
        except Exception as e:
            health_logger.error(f"Unexpected error in check_camera_health: {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health worker status using HealthWorkerStatus model.

        Returns:
            Dict[str, Any]: Complete health worker status information
        """
        try:
            # Get camera count for monitoring
            camera_count = 0
            try:
                cameras = self.camera_service.get_active_cameras()
                camera_count = len(cameras) if cameras else 0
            except Exception as e:
                health_logger.debug(
                    f"Could not get camera count: {e}", store_in_db=False
                )

            # Create structured status using the model
            status = HealthWorkerStatus(
                worker_type=WorkerType.HEALTH_WORKER,
                camera_service_status=(
                    HealthStatus.HEALTHY
                    if self.camera_service
                    else HealthStatus.UNREACHABLE
                ),
                rtsp_service_status=(
                    HealthStatus.HEALTHY
                    if self.rtsp_service
                    else HealthStatus.UNREACHABLE
                ),
                active_cameras_count=camera_count,
                monitoring_enabled=self.running,
                health_system_healthy=all(
                    [
                        self.camera_service is not None,
                        self.rtsp_service is not None,
                        self.running,
                    ]
                ),
            )

            # Build base status
            base_status = WorkerStatusBuilder.build_base_status(
                name=self.name,
                running=self.running,
                worker_type=WorkerType.HEALTH_WORKER.value,
            )

            # Merge with structured status
            base_status.update(
                {
                    "health_status": status.model_dump(),
                    "is_healthy": status.is_healthy,
                    "services_online_count": status.services_online_count,
                    "has_cameras_to_monitor": status.has_cameras_to_monitor,
                }
            )

            return base_status

        except Exception as e:
            # Return standardized error status
            return WorkerStatusBuilder.build_error_status(
                name=self.name,
                worker_type=WorkerType.HEALTH_WORKER.value,
                error_type="status_generation",
                error_message=str(e),
            )

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status for worker management system compatibility.

        This method provides simple binary health information separate
        from the detailed status reporting in get_status().
        """
        return WorkerStatusBuilder.build_simple_health_status(
            running=self.running,
            worker_type=WorkerType.HEALTH_WORKER.value,
            additional_checks={
                "camera_service_available": self.camera_service is not None,
                "rtsp_service_available": self.rtsp_service is not None,
                "health_service_available": self.health_service is not None,
            },
        )
