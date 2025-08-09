# backend/app/services/capture_workflow_service.py
"""
Capture workflow service for Timelapser v4.

Provides Service Layer Boundary Pattern compliance for capture operations.
Converts raw data to typed objects at the service boundary.
"""

from typing import Any, Optional

from ..enums import LoggerName, LogSource, WorkerType
from ..models.health_model import HealthStatus
from ..services.logger import get_service_logger
from ..workers.models.capture_responses import CaptureWorkerStatus

capture_service_logger = get_service_logger(LoggerName.CAPTURE_WORKER, LogSource.WORKER)


class CaptureWorkflowService:
    """
    Service layer for capture operations.

    Converts raw service data to typed objects at the service boundary,
    following the Service Layer Boundary Pattern.
    """

    def __init__(self):
        """Initialize capture workflow service."""
        pass

    def get_worker_status(
        self,
        workflow_orchestrator: Any,
        camera_service: Any,
        timelapse_ops: Any,
        weather_manager: Optional[Any],
        thumbnail_job_service: Optional[Any],
        overlay_job_service: Optional[Any],
        pipeline_healthy: bool,
    ) -> CaptureWorkerStatus:
        """
        Convert raw service status to typed CaptureWorkerStatus at service boundary.

        Args:
            workflow_orchestrator: Workflow orchestrator instance
            camera_service: Camera service instance
            timelapse_ops: Timelapse operations instance
            weather_manager: Optional weather manager instance
            thumbnail_job_service: Optional thumbnail job service
            overlay_job_service: Optional overlay job service
            pipeline_healthy: Whether the overall pipeline is healthy

        Returns:
            CaptureWorkerStatus: Typed status object for clean worker access
        """
        # Convert service availability to typed status using .value for explicit access
        orchestrator_status = (
            HealthStatus.HEALTHY.value
            if workflow_orchestrator
            else HealthStatus.UNREACHABLE.value
        )
        camera_status = (
            HealthStatus.HEALTHY.value
            if camera_service
            else HealthStatus.UNREACHABLE.value
        )
        timelapse_status = (
            HealthStatus.HEALTHY.value
            if timelapse_ops
            else HealthStatus.UNREACHABLE.value
        )

        # Return typed object at service boundary
        return CaptureWorkerStatus(
            worker_type=WorkerType.CAPTURE_WORKER.value,
            workflow_orchestrator_status=orchestrator_status,
            camera_service_status=camera_status,
            timelapse_ops_status=timelapse_status,
            weather_manager_enabled=weather_manager is not None,
            thumbnail_job_service_enabled=thumbnail_job_service is not None,
            overlay_job_service_enabled=overlay_job_service is not None,
            pipeline_healthy=pipeline_healthy,
        )
