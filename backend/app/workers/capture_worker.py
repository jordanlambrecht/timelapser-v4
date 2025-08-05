# backend/app/workers/capture_worker.py
"""
Capture worker for Timelapser v4.

Handles image capture from RTSP cameras.
"""

from typing import Optional, Any, Dict, TYPE_CHECKING

from .base_worker import BaseWorker
from .utils.worker_status_builder import WorkerStatusBuilder
from .models.capture_responses import CaptureWorkerStatus
from .exceptions import (
    ServiceUnavailableError,
    CaptureWorkflowError,
    CameraConnectionError,
    TimelapseValidationError,
    WorkerInitializationError,
)
from ..models.camera_model import Camera
from ..models.shared_models import RTSPCaptureResult
from ..services.logger import get_service_logger
from ..enums import LoggerName, LogSource, LogEmoji, WorkerType
from ..services.capture_workflow_service import CaptureWorkflowService
from ..constants import UNKNOWN_ERROR_MESSAGE

if TYPE_CHECKING:
    from ..services.timelapse_service import TimelapseService
    from ..services.camera_service import CameraService

from ..services.weather.service import WeatherManager
from ..services.capture_pipeline.workflow_orchestrator_service import (
    WorkflowOrchestratorService,
)

capture_logger = get_service_logger(LoggerName.CAPTURE_WORKER, LogSource.WORKER)


class CaptureWorker(BaseWorker):
    """
    Worker responsible for image capture from RTSP cameras.

    Handles:
    - Image capture from RTSP cameras when triggered by scheduler
    - Integration with thumbnail and overlay job queuing
    - Integration with corruption detection and video automation
    - SSE event broadcasting for captured images
    """

    def __init__(
        self,
        workflow_orchestrator: WorkflowOrchestratorService,  # Required - injected capture pipeline
        async_timelapse_service: "TimelapseService",  # Required for performance optimization
        async_camera_service: "CameraService",  # Required for performance optimization
        weather_manager: Optional[
            WeatherManager
        ] = None,  # Optional for weather integration
        thumbnail_job_service: Optional[
            Any
        ] = None,  # Optional for thumbnail job queuing
        overlay_job_service: Optional[Any] = None,  # Optional for overlay job queuing
    ):
        """
        Initialize capture worker with dependency injection.

        Args:
            workflow_orchestrator: Complete capture pipeline created by create_capture_pipeline()
            async_timelapse_service: Required async timelapse service for performance optimization
            async_camera_service: Required async camera service for performance optimization
            weather_manager: Optional weather manager
            thumbnail_job_service: Optional thumbnail job service for queuing jobs
            overlay_job_service: Optional overlay job service for queuing overlay jobs
        """
        super().__init__("CaptureWorker")

        # Store primary dependency
        self.workflow_orchestrator = workflow_orchestrator

        # Extract services for connectivity updates and basic existence checks
        self.camera_service = workflow_orchestrator.camera_service
        self.timelapse_ops = workflow_orchestrator.timelapse_ops

        # Store optional services
        self.weather_manager = weather_manager
        self.thumbnail_job_service = thumbnail_job_service
        self.overlay_job_service = overlay_job_service

        # Store async services for performance optimization
        self.async_timelapse_service = async_timelapse_service
        self.async_camera_service = async_camera_service

        # Initialize workflow service for Service Layer Boundary Pattern
        self.capture_service = CaptureWorkflowService()

    async def initialize(self) -> None:
        """Initialize capture worker resources."""
        try:
            # Validate required dependencies
            if not self.workflow_orchestrator:
                raise WorkerInitializationError(
                    "CaptureWorker requires workflow_orchestrator"
                )
            if not self.async_timelapse_service:
                raise WorkerInitializationError(
                    "CaptureWorker requires async_timelapse_service"
                )
            if not self.async_camera_service:
                raise WorkerInitializationError(
                    "CaptureWorker requires async_camera_service"
                )

            capture_logger.info("Initialized capture worker", store_in_db=False)
        except WorkerInitializationError as e:
            capture_logger.error(
                f"Failed to initialize capture worker: {e}", store_in_db=False
            )
            raise

    async def cleanup(self) -> None:
        """Cleanup capture worker resources."""
        capture_logger.info("Cleaned up capture worker", store_in_db=False)

    async def capture_from_camera(self, camera_info: Camera) -> None:
        """
        Capture image from a single camera using the injected capture pipeline.

        TRUST MODEL: Assumes scheduler has already validated capture readiness.
        This method focuses on workflow orchestration rather than validation.

        Args:
            camera_info: Camera model instance containing id, name, rtsp_url, etc.
        """
        # Use direct attribute access for Pydantic models
        camera_id = camera_info.id
        camera_name = camera_info.name

        try:
            # Trust scheduler validation - no redundant checks needed
            # Get active timelapse for this camera (basic existence check)
            timelapse = (
                await self.async_timelapse_service.get_active_timelapse_for_camera(
                    camera_id
                )
            )
            if not timelapse:
                capture_logger.debug(
                    f"No active timelapse for camera {camera_name}", store_in_db=False
                )
                return

            # Use the injected WorkflowOrchestratorService for the complete 12-step workflow
            capture_logger.info(
                f"Starting unified capture workflow for camera {camera_id} ({camera_name})",
                emoji=LogEmoji.CAMERA,
            )

            # Use the injected workflow orchestrator (required)
            if not self.workflow_orchestrator:
                raise RuntimeError(
                    "CaptureWorker requires workflow_orchestrator - use create_capture_pipeline() factory"
                )

            workflow_orchestrator = self.workflow_orchestrator

            # Execute the complete 12-step capture workflow
            result: RTSPCaptureResult = await self.run_in_executor(
                workflow_orchestrator.execute_capture_workflow,
                camera_id,
                timelapse.id,
                {"source": "capture_worker", "camera_name": camera_name},
            )

            if result.success:
                capture_logger.info(
                    "Capture workflow completed successfully", emoji=LogEmoji.SUCCESS
                )

                # Update camera connectivity status to online
                await self.async_camera_service.update_camera_connectivity(
                    camera_id, True, None
                )
            else:
                capture_logger.error(
                    f"Capture workflow failed: {result.error or UNKNOWN_ERROR_MESSAGE}"
                )

                # Update camera connectivity status to offline
                await self.async_camera_service.update_camera_connectivity(
                    camera_id, False, result.error or UNKNOWN_ERROR_MESSAGE
                )

        except CaptureWorkflowError as e:
            capture_logger.error(
                f"Capture workflow error for camera {camera_name}: {e}"
            )
            # Update camera connectivity as offline on workflow error
            if camera_id is not None:
                await self.async_camera_service.update_camera_connectivity(
                    camera_id, False, str(e)
                )
        except CameraConnectionError as e:
            capture_logger.error(
                f"Camera connection error for camera {camera_name}: {e}"
            )
            # Update camera connectivity as offline on connection error
            if camera_id is not None:
                await self.async_camera_service.update_camera_connectivity(
                    camera_id, False, str(e)
                )
        except ServiceUnavailableError as e:
            capture_logger.error(
                f"Required service unavailable for camera {camera_name} capture: {e}"
            )
            # Update camera connectivity as offline on service error
            if camera_id is not None:
                await self.async_camera_service.update_camera_connectivity(
                    camera_id, False, str(e)
                )
        except Exception as e:
            capture_logger.warning(
                f"Unexpected error in capture workflow for camera {camera_name}: {e}"
            )
            # Update camera connectivity as offline on any unexpected error
            if camera_id is not None:
                await self.async_camera_service.update_camera_connectivity(
                    camera_id, False, str(e)
                )

    async def capture_single_timelapse(self, timelapse_id: int) -> None:
        """
        Capture image for a specific timelapse by ID using the injected workflow.

        TRUST MODEL: This method is called by the scheduler for per-timelapse capture jobs.
        The scheduler has already validated that the timelapse is running and the camera is active
        using SchedulingService.validate_capture_readiness().

        Args:
            timelapse_id: ID of the timelapse to capture for
        """
        try:
            # Trust scheduler validation - minimal existence checks only
            # Get the timelapse info (basic existence check)
            timelapse = await self.async_timelapse_service.get_timelapse_by_id(
                timelapse_id
            )

            if not timelapse:
                capture_logger.warning(
                    f"Timelapse {timelapse_id} not found for capture", store_in_db=False
                )
                return

            # Get the camera for this timelapse (basic existence check)
            camera = await self.async_camera_service.get_camera_by_id(
                timelapse.camera_id
            )

            if not camera:
                capture_logger.error(
                    f"Camera {timelapse.camera_id} not found for timelapse {timelapse_id}",
                    store_in_db=False,
                )
                return

            capture_logger.info(
                f"Starting timelapse-specific capture for timelapse {timelapse_id} on camera {camera.name}",
                emoji=LogEmoji.TIMELAPSE,
            )

            # Use the injected workflow orchestrator (required - no legacy fallback)
            if not self.workflow_orchestrator:
                raise RuntimeError(
                    "CaptureWorker requires workflow_orchestrator - use create_capture_pipeline() factory"
                )

            workflow_orchestrator = self.workflow_orchestrator

            # Execute the complete 12-step capture workflow
            result: RTSPCaptureResult = await self.run_in_executor(
                workflow_orchestrator.execute_capture_workflow,
                camera.id,
                timelapse_id,
                {"source": "scheduler", "timelapse_id": timelapse_id},
            )

            if result.success:
                capture_logger.info(
                    "Timelapse capture workflow completed successfully",
                    emoji=LogEmoji.SUCCESS,
                )
            else:
                capture_logger.error(
                    f"Timelapse capture workflow failed: {result.error or UNKNOWN_ERROR_MESSAGE}"
                )

        except TimelapseValidationError as e:
            capture_logger.error(
                f"Timelapse validation error for timelapse {timelapse_id}: {e}"
            )
        except CaptureWorkflowError as e:
            capture_logger.error(
                f"Capture workflow error for timelapse {timelapse_id}: {e}"
            )
        except CameraConnectionError as e:
            capture_logger.error(
                f"Camera connection error for timelapse {timelapse_id}: {e}"
            )
        except ServiceUnavailableError as e:
            capture_logger.error(
                f"Required service unavailable for timelapse {timelapse_id} capture: {e}"
            )
        except Exception as e:
            capture_logger.warning(
                f"Unexpected error in timelapse capture workflow for timelapse {timelapse_id}: {e}"
            )

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive capture worker status using CaptureWorkerStatus model.

        Returns:
            Dict[str, Any]: Complete capture worker status information
        """
        try:
            # Create structured status using the model
            status = CaptureWorkerStatus(
                worker_type=WorkerType.CAPTURE_WORKER.value,
                workflow_orchestrator_status=(
                    "healthy" if self.workflow_orchestrator else "unavailable"
                ),
                camera_service_status=(
                    "healthy" if self.camera_service else "unavailable"
                ),
                timelapse_ops_status="healthy" if self.timelapse_ops else "unavailable",
                weather_manager_enabled=self.weather_manager is not None,
                thumbnail_job_service_enabled=self.thumbnail_job_service is not None,
                overlay_job_service_enabled=self.overlay_job_service is not None,
                pipeline_healthy=all(
                    [
                        self.workflow_orchestrator is not None,
                        self.camera_service is not None,
                        self.timelapse_ops is not None,
                    ]
                ),
            )

            # Build base status
            base_status = WorkerStatusBuilder.build_base_status(
                name=self.name,
                running=self.running,
                worker_type=WorkerType.CAPTURE_WORKER.value,
            )

            # Merge with structured status
            base_status.update(
                {
                    "capture_status": status.__dict__,
                    "is_healthy": status.is_healthy,
                    "core_services_count": status.core_services_count,
                    "optional_services_count": status.optional_services_count,
                }
            )

            return base_status

        except Exception as e:
            # Return standardized error status
            return WorkerStatusBuilder.build_error_status(
                name=self.name,
                worker_type=WorkerType.CAPTURE_WORKER.value,
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
            worker_type=WorkerType.CAPTURE_WORKER.value,
            additional_checks={
                "workflow_orchestrator_available": self.workflow_orchestrator
                is not None,
                "camera_service_available": self.camera_service is not None,
                "timelapse_ops_available": self.timelapse_ops is not None,
            },
        )
