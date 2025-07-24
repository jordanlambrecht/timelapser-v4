# backend/app/services/capture_pipeline/workflow_orchestrator_service.py
"""
Capture Pipeline Workflow Orchestrator Service

Orchestrates the complete image capture workflow by coordinating existing services.
This is the main entry point for capture operations.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import time
from loguru import logger


from ...models.shared_models import RTSPCaptureResult
from ...exceptions import RTSPCaptureError
from ...enums import JobPriority
from ...constants import (
    CAMERA_CAPTURE_SUCCESS,
    CAMERA_CAPTURE_FAILED,
)

from ...services.image_service import SyncImageService
from ...services.camera_service import SyncCameraService
from ..corruption_pipeline.services.evaluation_service import (
    SyncCorruptionEvaluationService,
)

from ...database.core import SyncDatabase
from ...database.camera_operations import SyncCameraOperations
from ...database.timelapse_operations import SyncTimelapseOperations
from ...database.sse_events_operations import SyncSSEEventsOperations
from .rtsp_service import RTSPService
from .job_coordination_service import JobCoordinationService


from ...utils.time_utils import utc_now
from .utils import generate_capture_filename
from ...config import settings


class WorkflowOrchestratorService:
    """
    Orchestrates the complete capture workflow using existing services.

    This service coordinates the capture process by delegating to existing
    business services rather than reimplementing capture logic.

    Responsibilities:
    - Coordinate complete capture workflow
    - Delegate to existing services (ImageService, CorruptionService, etc.)
    - Handle workflow-level error recovery
    - Provide unified capture interface for workers
    """

    def __init__(
        self,
        db: SyncDatabase,
        image_service: SyncImageService,
        corruption_evaluation_service: SyncCorruptionEvaluationService,
        camera_service: SyncCameraService,
        rtsp_service: RTSPService,
        job_coordinator: JobCoordinationService,
        camera_ops: SyncCameraOperations,
        timelapse_ops: SyncTimelapseOperations,
        sse_ops: SyncSSEEventsOperations,
        scheduling_service=None,  # Optional for backward compatibility
        weather_service=None,  # Optional weather service
        overlay_service=None,  # Optional overlay service
    ):
        """
        Initialize workflow orchestrator with injected services.

        Args:
            db: Synchronized database connection
            image_service: Image management service
            corruption_evaluation_service: Image quality evaluation service
            camera_service: Camera management service
            rtsp_service: RTSP capture service
            job_coordinator: Background job coordination service
            camera_ops: Camera database operations
            timelapse_ops: Timelapse database operations
            sse_ops: SSE event database operations
        """
        self.db = db

        # Assign injected services
        self.image_service = image_service
        self.corruption_evaluation_service = corruption_evaluation_service
        self.camera_service = camera_service
        self.rtsp_service = rtsp_service
        self.job_coordinator = job_coordinator
        self.camera_ops = camera_ops
        self.timelapse_ops = timelapse_ops
        self.sse_ops = sse_ops
        self.scheduling_service = scheduling_service
        self.weather_service = weather_service
        self.overlay_service = overlay_service

        # Backward compatibility aliases for tests
        self.timelapse_service = timelapse_ops  # Alias for test compatibility
        self.job_coordination_service = job_coordinator  # Alias for test compatibility
        self.sse_service = sse_ops  # Alias for test compatibility

    def execute_capture_workflow(
        self,
        camera_id: int,
        timelapse_id: int,
        workflow_context: Optional[Dict[str, Any]] = None,
    ) -> RTSPCaptureResult:
        """
        Execute the complete capture workflow using existing services.

        Main entry point for coordinated capture operations. Delegates to existing
        services rather than reimplementing capture logic.

        Args:
            camera_id: Camera identifier
            timelapse_id: Active timelapse identifier
            workflow_context: Optional context for workflow customization

        Returns:
            RTSPCaptureResult with complete workflow results
        """
        workflow_start_time = time.time()

        try:
            logger.info(
                f"🚀 Starting capture workflow for camera {camera_id}, timelapse {timelapse_id}"
            )

            # 1. Validate prerequisites
            validation_result = self._validate_capture_prerequisites(
                camera_id, timelapse_id
            )
            if not validation_result["valid"]:
                return RTSPCaptureResult(
                    success=False,
                    error=validation_result["error"],
                    message="Capture prerequisites validation failed",
                )

            # 2. Execute RTSP capture using RTSPService
            logger.debug("📹 Capturing image via RTSP service")

            # Get camera object and create capture path
            camera = self.camera_ops.get_camera_by_id(camera_id)
            if not camera:
                return RTSPCaptureResult(
                    success=False,
                    error=f"Camera {camera_id} not found for capture",
                    message="Camera validation failed",
                )

            # Create output path for captured image
            timestamp = utc_now()
            filename = generate_capture_filename(timelapse_id, timestamp)
            output_path = (
                Path(settings.data_directory)
                / "images"
                / timestamp.strftime("%Y-%m-%d")
                / filename
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Prepare capture settings
            capture_settings = self.rtsp_service._get_capture_settings()
            capture_settings.update({"quality": 90})

            # Execute capture and processing
            capture_result_dict = self.rtsp_service.capture_and_process_frame(
                camera=camera,
                output_path=output_path,
                capture_settings=capture_settings,
            )

            # Convert dict result to RTSPCaptureResult
            if capture_result_dict.get("success"):
                capture_result = RTSPCaptureResult(
                    success=True,
                    message="Capture successful",
                    image_path=str(output_path),
                    file_size=output_path.stat().st_size if output_path.exists() else 0,
                    metadata=capture_result_dict.get("metadata", {}),
                )
            else:
                capture_result = RTSPCaptureResult(
                    success=False,
                    error=capture_result_dict.get("error", "Unknown capture error"),
                    message="RTSP capture failed",
                )

            if not capture_result.success:
                logger.error(f"RTSP capture failed: {capture_result.error}")
                return capture_result

            # Validate successful capture has image_path
            if not capture_result.image_path:
                logger.error("Successful capture result missing image_path")
                return RTSPCaptureResult(
                    success=False,
                    error="Missing image path in successful capture result",
                    message="Capture validation failed",
                )

            # 3. Evaluate image quality using CorruptionService
            logger.debug("🔍 Evaluating image quality")
            quality_result = self._evaluate_image_quality(
                camera_id=camera_id, image_path=capture_result.image_path
            )

            # 4. Handle quality evaluation results
            if quality_result["should_discard"]:
                logger.warning(
                    f"Image discarded due to quality: {quality_result['reason']}"
                )
                # Clean up the captured file
                self._cleanup_discarded_image(capture_result.image_path)

                # Check if retry is recommended
                if quality_result.get("retry_recommended", False):
                    logger.info("Retrying capture due to quality issues")
                    return self._retry_capture_workflow(
                        camera_id, timelapse_id, workflow_context
                    )

                return RTSPCaptureResult(
                    success=False,
                    error=f"Image quality below threshold: {quality_result['final_score']:.1f}",
                    message="Image discarded due to quality",
                )

            # 5. Create image record using ImageService
            logger.debug("💾 Creating image record")
            image_record = self._create_image_record(
                camera_id=camera_id,
                timelapse_id=timelapse_id,
                image_path=capture_result.image_path,
                quality_data=quality_result,
                workflow_context=workflow_context,
            )

            if not image_record:
                logger.error("Failed to create image record")
                return RTSPCaptureResult(
                    success=False,
                    error="Database record creation failed",
                    message="Could not save image metadata",
                )

            # 6. Coordinate background jobs
            logger.debug("🔄 Coordinating background jobs")
            job_results = self._coordinate_background_jobs(
                image_id=image_record.id,
                timelapse_id=timelapse_id,
                workflow_context=workflow_context,
            )

            # 7. Broadcast SSE events
            logger.debug("📡 Broadcasting capture events")
            self._broadcast_capture_events(
                camera_id=camera_id,
                timelapse_id=timelapse_id,
                image_record=image_record,
                job_results=job_results,
            )

            # 8. Return successful result
            workflow_duration = time.time() - workflow_start_time
            logger.info(
                f"✅ Capture workflow completed successfully for image {image_record.id} in {workflow_duration:.3f}s"
            )

            return RTSPCaptureResult(
                success=True,
                message=CAMERA_CAPTURE_SUCCESS,
                image_id=image_record.id,
                image_path=capture_result.image_path,
                file_size=capture_result.file_size,
                metadata={
                    "workflow_version": "2.0",
                    "corruption_score": quality_result.get("final_score", 0.0),
                    "quality_verdict": quality_result.get("quality_verdict", "unknown"),
                    "background_jobs": job_results,
                    "image_count": self._get_timelapse_image_count(timelapse_id),
                },
            )

        except Exception as e:
            logger.error(f"Capture workflow failed: {e}")
            return self._handle_workflow_error(
                camera_id, timelapse_id, e, workflow_context
            )

    def _validate_capture_prerequisites(
        self, camera_id: int, timelapse_id: int
    ) -> Dict[str, Any]:
        """
        Minimal safety validation for capture workflow.

        TRUST MODEL: Assumes comprehensive validation already performed by SchedulerWorker
        using SchedulingService.validate_capture_readiness(). This method only performs
        basic safety checks as a final safeguard.

        Args:
            camera_id: Camera identifier
            timelapse_id: Timelapse identifier

        Returns:
            Validation result with status and details
        """
        try:
            # Basic existence checks only - trust scheduler's comprehensive validation
            camera = self.camera_ops.get_camera_by_id(camera_id)
            timelapse = self.timelapse_ops.get_timelapse_by_id(timelapse_id)

            if not camera:
                return {"valid": False, "error": f"Camera {camera_id} not found"}

            if not timelapse:
                return {"valid": False, "error": f"Timelapse {timelapse_id} not found"}

            # Trust scheduler validation for status, health, timing, etc.
            # Only basic existence validation here
            return {"valid": True}

        except Exception as e:
            logger.error(f"Error in basic capture validation: {e}")
            return {"valid": False, "error": f"Basic validation error: {str(e)}"}

    def _evaluate_image_quality(
        self,
        camera_id: int,
        image_path: str,
        _workflow_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate captured image quality using CorruptionService.

        Args:
            camera_id: Camera identifier
            image_path: Path to captured image
            workflow_context: Optional workflow context

        Returns:
            Quality evaluation result
        """
        try:
            # Use the new corruption evaluation service
            evaluation_result = (
                self.corruption_evaluation_service.evaluate_captured_image(
                    camera_id=camera_id, file_path=image_path
                )
            )

            # Determine if image should be discarded based on action taken
            should_discard = evaluation_result.action_taken in [
                "discarded",
                "auto_discard",
                "error",
            ]
            retry_recommended = evaluation_result.action_taken == "retried"

            # Map action_taken to quality verdict for logging consistency
            action_to_verdict = {
                "saved": "good_quality",
                "discarded": "corrupted",
                "retried": "corrupted",
                "auto_discard": "auto_discard",
                "error": "error",
            }
            quality_verdict = action_to_verdict.get(
                evaluation_result.action_taken, "unknown"
            )

            return {
                "success": True,
                "should_discard": should_discard,
                "retry_recommended": retry_recommended,
                "final_score": float(evaluation_result.corruption_score),
                "quality_verdict": quality_verdict,
                "fast_score": evaluation_result.fast_score,
                "heavy_score": evaluation_result.heavy_score,
                "reason": f"Action: {evaluation_result.action_taken}, Score: {evaluation_result.corruption_score}",
            }

        except Exception as e:
            logger.error(f"Error evaluating image quality: {e}")
            return {
                "success": False,
                "should_discard": True,
                "retry_recommended": False,
                "final_score": 100.0,
                "quality_verdict": "error",
                "reason": f"Quality evaluation error: {str(e)}",
            }

    def _create_image_record(
        self,
        camera_id: int,
        timelapse_id: int,
        image_path: str,
        quality_data: Dict[str, Any],
        workflow_context: Optional[Dict[str, Any]] = None,
    ):
        """
        Create image database record using ImageService.

        Args:
            camera_id: Camera identifier
            timelapse_id: Timelapse identifier
            image_path: Path to captured image
            quality_data: Quality evaluation results
            workflow_context: Optional workflow context

        Returns:
            Created image record or None if failed
        """
        try:
            # Prepare image data for ImageService
            image_data = {
                "camera_id": camera_id,
                "timelapse_id": timelapse_id,
                "file_path": str(Path(image_path).relative_to(Path.cwd())),
                "captured_at": utc_now(),
                "corruption_score": int(quality_data.get("final_score", 0.0)),
                "is_flagged": quality_data.get("quality_verdict") == "warning",
                "file_size": (
                    Path(image_path).stat().st_size if Path(image_path).exists() else 0
                ),
            }

            # Add quality metadata
            if quality_data.get("success", True):
                image_data["corruption_details"] = {
                    "fast_score": quality_data.get("fast_score"),
                    "heavy_score": quality_data.get("heavy_score"),
                    "quality_verdict": quality_data.get("quality_verdict"),
                    "workflow_context": workflow_context,
                }

            # Create record using ImageService
            image_record = self.image_service.record_captured_image(image_data)

            if image_record:
                logger.debug(f"Created image record {image_record.id}")
                return image_record
            else:
                logger.error("ImageService failed to create record")
                return None

        except Exception as e:
            logger.error(f"Error creating image record: {e}")
            return None

    def _coordinate_background_jobs(
        self,
        image_id: int,
        timelapse_id: int,
        workflow_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Coordinate background jobs using JobCoordinationService.

        Args:
            image_id: Created image record ID
            timelapse_id: Timelapse identifier
            workflow_context: Optional workflow context

        Returns:
            Job coordination results
        """
        try:
            job_results = {
                "thumbnail_job": None,
                "video_jobs": [],
                "total_jobs_queued": 0,
            }

            # Queue thumbnail generation job
            thumbnail_result = self.job_coordinator.coordinate_thumbnail_job(
                image_id=image_id,
                priority=JobPriority.MEDIUM,
                job_context=workflow_context,
            )

            if thumbnail_result.get("success"):
                job_results["thumbnail_job"] = thumbnail_result["job_id"]
                job_results["total_jobs_queued"] += 1

            # 🎯 SCHEDULER-CENTRIC: Video automation triggers are now handled by SchedulerWorker
            # after capture completion. This ensures ALL timing decisions flow through scheduler authority.
            # The capture pipeline only reports completion - timing decisions happen in SchedulerWorker.
            logger.debug(
                f"Video automation evaluation moved to SchedulerWorker for timelapse {timelapse_id}"
            )

            # Note: job_results["video_jobs"] and related counting removed since
            # video jobs are now created by scheduler, not capture pipeline

            return job_results

        except Exception as e:
            logger.error(f"Error coordinating background jobs: {e}")
            return {"error": str(e), "total_jobs_queued": 0}

    def _broadcast_capture_events(
        self,
        camera_id: int,
        timelapse_id: int,
        image_record,
        job_results: Dict[str, Any],
    ):
        """
        Broadcast SSE events for capture completion.

        Args:
            camera_id: Camera identifier
            timelapse_id: Timelapse identifier
            image_record: Created image record
            job_results: Background job results
        """
        try:
            # Use SSE operations to broadcast events
            image_count = self._get_timelapse_image_count(timelapse_id)
            day_number = image_record.day_number

            self.sse_ops.create_image_captured_event(
                camera_id=camera_id,
                timelapse_id=timelapse_id,
                image_count=image_count,
                day_number=day_number,
            )

            logger.debug(
                f"Broadcast capture event for image {image_record.id} with {job_results.get('total_jobs_queued', 0)} jobs queued"
            )

        except Exception as e:
            logger.warning(f"Error broadcasting capture events: {e}")

    def _get_timelapse_image_count(self, timelapse_id: int) -> int:
        """Get current image count for timelapse."""
        try:
            timelapse = self.timelapse_ops.get_timelapse_by_id(timelapse_id)
            if timelapse:
                return timelapse.image_count
            return 0
        except Exception:
            return 0

    def _cleanup_discarded_image(self, image_path: str):
        """Clean up discarded image file."""
        try:
            Path(image_path).unlink(missing_ok=True)
            logger.debug(f"Cleaned up discarded image: {image_path}")
        except Exception as e:
            logger.warning(f"Error cleaning up discarded image {image_path}: {e}")

    def _retry_capture_workflow(
        self,
        camera_id: int,
        timelapse_id: int,
        workflow_context: Optional[Dict[str, Any]] = None,
    ) -> RTSPCaptureResult:
        """
        Retry capture workflow once for quality issues.

        Args:
            camera_id: Camera identifier
            timelapse_id: Timelapse identifier
            workflow_context: Optional workflow context

        Returns:
            Retry capture result
        """
        try:
            logger.info(f"Retrying capture for camera {camera_id}")

            # Update context to indicate this is a retry
            retry_context = (workflow_context or {}).copy()
            retry_context.update(
                {"is_retry": True, "retry_reason": "quality_threshold"}
            )

            # Execute workflow again (this will be the final attempt)
            return self.execute_capture_workflow(camera_id, timelapse_id, retry_context)

        except Exception as e:
            logger.error(f"Error in retry capture workflow: {e}")
            return RTSPCaptureResult(
                success=False,
                error=f"Retry capture failed: {str(e)}",
                message=CAMERA_CAPTURE_FAILED,
            )

    def _handle_workflow_error(
        self,
        camera_id: int,
        timelapse_id: int,
        error: Exception,
        workflow_context: Optional[Dict[str, Any]] = None,
    ) -> RTSPCaptureResult:
        """
        Handle workflow-level errors.

        Args:
            camera_id: Camera identifier
            timelapse_id: Timelapse identifier
            error: Exception that occurred
            workflow_context: Optional workflow context

        Returns:
            Error RTSPCaptureResult
        """
        try:
            # Update camera connectivity if this indicates connectivity issues
            if isinstance(error, RTSPCaptureError):
                try:
                    # Note: Using sync camera operations directly since this is sync context
                    self.camera_ops.update_camera_connectivity(
                        camera_id=camera_id,
                        is_connected=False,
                        error_message=str(error),
                    )
                except Exception as health_error:
                    logger.warning(f"Failed to update camera health: {health_error}")

            # Log error for monitoring
            logger.error(f"Workflow error for camera {camera_id}: {error}")

            return RTSPCaptureResult(
                success=False,
                error=str(error),
                message=CAMERA_CAPTURE_FAILED,
                metadata={
                    "workflow_version": "2.0",
                    "error_type": type(error).__name__,
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "context": workflow_context,
                },
            )

        except Exception as handle_error:
            logger.error(f"Error in error handler: {handle_error}")
            return RTSPCaptureResult(
                success=False,
                error=f"Workflow failed with unhandled error: {str(error)}",
                message=CAMERA_CAPTURE_FAILED,
            )
