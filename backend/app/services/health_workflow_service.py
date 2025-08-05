# backend/app/services/health_workflow_service.py
"""
Health workflow service for Timelapser v4.

Provides Service Layer Boundary Pattern compliance for health monitoring operations.
Converts raw data to typed objects at the service boundary.
"""

from typing import Any
from ..workers.models.health_responses import HealthWorkerStatus, CameraHealthSummary
from ..models.health_model import HealthStatus
from ..enums import WorkerType
from ..services.logger import get_service_logger
from ..enums import LoggerName

health_service_logger = get_service_logger(LoggerName.HEALTH_WORKER)


class HealthWorkflowService:
    """
    Service layer for health monitoring operations.

    Converts raw service data to typed objects at the service boundary,
    following the Service Layer Boundary Pattern used by VideoWorkflowService.
    """

    def __init__(self):
        """Initialize health workflow service."""
        pass

    def get_worker_status(
        self,
        camera_service: Any,
        rtsp_service: Any,
        camera_count: int,
        worker_running: bool,
    ) -> HealthWorkerStatus:
        """
        Convert raw service status to typed HealthWorkerStatus at service boundary.

        Args:
            camera_service: Camera service instance (or None)
            rtsp_service: RTSP service instance (or None)
            camera_count: Number of active cameras
            worker_running: Whether the worker is currently running

        Returns:
            HealthWorkerStatus: Typed status object for clean worker access
        """
        # Convert service availability to typed status
        camera_status = (
            HealthStatus.HEALTHY if camera_service else HealthStatus.UNREACHABLE
        )
        rtsp_status = HealthStatus.HEALTHY if rtsp_service else HealthStatus.UNREACHABLE

        # Calculate monitoring capabilities
        monitoring_enabled = bool(camera_service and rtsp_service)
        system_healthy = bool(camera_service and rtsp_service and worker_running)

        # Return typed object at service boundary
        return HealthWorkerStatus(
            worker_type=WorkerType.HEALTH_WORKER,
            camera_service_status=camera_status,
            rtsp_service_status=rtsp_status,
            active_cameras_count=camera_count,
            monitoring_enabled=monitoring_enabled,
            health_system_healthy=system_healthy,
        )

    def get_camera_health_summary(
        self, total_cameras: int, online_cameras: int, check_completed: bool = True
    ) -> CameraHealthSummary:
        """
        Convert camera health metrics to typed summary at service boundary.

        Args:
            total_cameras: Total number of cameras monitored
            online_cameras: Number of cameras currently online
            check_completed: Whether the health check completed successfully

        Returns:
            CameraHealthSummary: Typed summary for clean worker access
        """
        offline_cameras = max(0, total_cameras - online_cameras)

        return CameraHealthSummary(
            total_cameras=total_cameras,
            online_cameras=online_cameras,
            offline_cameras=offline_cameras,
            last_check_completed=check_completed,
        )
