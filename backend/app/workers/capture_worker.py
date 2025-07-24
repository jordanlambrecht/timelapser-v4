# backend/app/workers/capture_worker.py
"""
Capture worker for Timelapser v4.

Handles image capture from RTSP cameras.
"""

from .base_worker import BaseWorker
from ..models.camera_model import Camera
from typing import Optional, Any, Dict
from ..services.weather.service import WeatherManager
from ..services.capture_pipeline.workflow_orchestrator_service import (
    WorkflowOrchestratorService,
)


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

    async def initialize(self) -> None:
        """Initialize capture worker resources."""
        self.log_info("Initialized capture worker")

    async def cleanup(self) -> None:
        """Cleanup capture worker resources."""
        self.log_info("Cleaned up capture worker")

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
            timelapse = await self.run_in_executor(
                self.timelapse_ops.get_active_timelapse_for_camera, camera_id
            )
            if not timelapse:
                self.log_debug(f"No active timelapse for camera {camera_name}")
                return

            # Use the injected WorkflowOrchestratorService for the complete 12-step workflow
            self.log_info(
                f"🚀 Starting unified capture workflow for camera {camera_id} ({camera_name})"
            )

            # Use the injected workflow orchestrator (required - no legacy fallback)
            if not self.workflow_orchestrator:
                raise RuntimeError(
                    "CaptureWorker requires workflow_orchestrator - use create_capture_pipeline() factory"
                )

            workflow_orchestrator = self.workflow_orchestrator

            # Execute the complete 12-step capture workflow
            result = await self.run_in_executor(
                workflow_orchestrator.execute_capture_workflow,
                camera_id,
                timelapse.id,
                {"source": "capture_worker", "camera_name": camera_name},
            )

            if result.was_successful:
                self.log_info(
                    f"✅ Capture workflow completed successfully: {result.overall_result.value}"
                )

                # Update camera connectivity status to online
                await self.run_in_executor(
                    self.camera_service.update_camera_connectivity,
                    camera_id,
                    True,
                    None,
                )
            else:
                self.log_error(
                    f"❌ Capture workflow failed: {result.error_summary or result.overall_result.value}"
                )

                # Update camera connectivity status to offline
                await self.run_in_executor(
                    self.camera_service.update_camera_connectivity,
                    camera_id,
                    False,
                    result.error_summary or result.overall_result.value,
                )

        except Exception as e:
            # Update camera connectivity as offline on any error
            if camera_id is not None:
                await self.run_in_executor(
                    self.camera_service.update_camera_connectivity,
                    camera_id,
                    False,
                    str(e),
                )
            self.log_error(
                f"Unexpected error in capture workflow for camera {camera_name}", e
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
            timelapse = await self.run_in_executor(
                self.timelapse_ops.get_timelapse_by_id, timelapse_id
            )

            if not timelapse:
                self.log_warning(f"Timelapse {timelapse_id} not found for capture")
                return

            # Get the camera for this timelapse (basic existence check)
            camera = await self.run_in_executor(
                self.camera_service.get_camera_by_id, timelapse.camera_id
            )

            if not camera:
                self.log_error(
                    f"Camera {timelapse.camera_id} not found for timelapse {timelapse_id}"
                )
                return

            self.log_info(
                f"🎯 Starting timelapse-specific capture for timelapse {timelapse_id} on camera {camera.name}"
            )

            # Use the injected workflow orchestrator (required - no legacy fallback)
            if not self.workflow_orchestrator:
                raise RuntimeError(
                    "CaptureWorker requires workflow_orchestrator - use create_capture_pipeline() factory"
                )

            workflow_orchestrator = self.workflow_orchestrator

            # Execute the complete 12-step capture workflow
            result = await self.run_in_executor(
                workflow_orchestrator.execute_capture_workflow,
                camera.id,
                timelapse_id,
                {"source": "scheduler", "timelapse_id": timelapse_id},
            )

            if result.was_successful:
                self.log_info(
                    f"✅ Timelapse capture workflow completed: {result.overall_result.value}"
                )
            else:
                self.log_error(
                    f"❌ Timelapse capture workflow failed: {result.error_summary or result.overall_result.value}"
                )

        except Exception as e:
            self.log_error(
                f"Error in timelapse capture workflow for timelapse {timelapse_id}", e
            )

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive capture worker status (STANDARDIZED METHOD NAME).

        Returns:
            Dict[str, Any]: Complete capture worker status information
        """
        # Get base status from BaseWorker
        base_status = super().get_status()

        # Add capture-specific status information
        base_status.update(
            {
                "worker_type": "CaptureWorker",
                # Pipeline health status
                "workflow_orchestrator_status": (
                    "healthy" if self.workflow_orchestrator else "unavailable"
                ),
                "camera_service_status": (
                    "healthy" if self.camera_service else "unavailable"
                ),
                "timelapse_ops_status": (
                    "healthy" if self.timelapse_ops else "unavailable"
                ),
                # Optional service status
                "weather_manager_enabled": self.weather_manager is not None,
                "thumbnail_job_service_enabled": self.thumbnail_job_service is not None,
                "overlay_job_service_enabled": self.overlay_job_service is not None,
                # Overall pipeline health
                "pipeline_healthy": all(
                    [
                        self.workflow_orchestrator is not None,
                        self.camera_service is not None,
                        self.timelapse_ops is not None,
                    ]
                ),
            }
        )

        return base_status
