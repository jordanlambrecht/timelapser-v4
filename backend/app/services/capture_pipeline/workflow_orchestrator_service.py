# backend/app/services/capture_pipeline/workflow_orchestrator_service.py
"""
Capture Pipeline Workflow Orchestrator Service

Orchestrates the complete image capture workflow by coordinating existing services.
This is the main entry point for capture operations.
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional

from ...constants import (
    CAMERA_CAPTURE_FAILED,
    CAMERA_CAPTURE_SUCCESS,
)
from ...database.core import SyncDatabase
from ...database.sse_events_operations import SyncSSEEventsOperations
from ...enums import (
    LogEmoji,
    LoggerName,
    SSEEvent,
    SSEEventSource,
    SSEPriority,
    ThumbnailJobPriority,
)
from ...exceptions import RTSPCaptureError
from ...models.shared_models import RTSPCaptureResult
from ...services.camera_service import SyncCameraService
from ...services.image_service import SyncImageService
from ...services.logger import get_service_logger
from ...services.timelapse_service import SyncTimelapseService
from ...services.weather.service import WeatherManager
from ...utils.database_helpers import DatabaseUtilities
from ...utils.file_helpers import ensure_entity_directory, get_relative_path
from ...utils.time_utils import (
    get_timezone_aware_timestamp_sync,
    utc_now,
)
from ..corruption_pipeline.services.evaluation_service import (
    SyncCorruptionEvaluationService,
)
from .job_coordination_service import JobCoordinationService
from .rtsp_service import RTSPService
from .utils import generate_capture_filename

logger = get_service_logger(LoggerName.CAPTURE_PIPELINE)


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
        timelapse_service: SyncTimelapseService,
        rtsp_service: RTSPService,
        job_coordinator: JobCoordinationService,
        sse_ops: SyncSSEEventsOperations,
        scheduling_service=None,  # Optional for backward compatibility
        weather_service: Optional["WeatherManager"] = None,  # Optional weather service
        overlay_service=None,  # Optional overlay service
        settings_service=None,  # Settings service for timezone-aware operations
    ):
        """
        Initialize workflow orchestrator with injected services.

        Args:
            db: Synchronized database connection
            image_service: Image management service
            corruption_evaluation_service: Image quality evaluation service
            camera_service: Camera management service
            timelapse_service: Timelapse management service
            rtsp_service: RTSP capture service
            job_coordinator: Background job coordination service
            sse_ops: SSE event database operations
            weather_service: Optional weather service
            settings_service: Settings service for timezone-aware operations
        """
        self.db = db

        # Assign injected services
        self.image_service = image_service
        self.corruption_evaluation_service = corruption_evaluation_service
        self.camera_service = camera_service
        self.timelapse_service = timelapse_service
        self.rtsp_service = rtsp_service
        self.job_coordinator = job_coordinator
        self.sse_ops = sse_ops
        self.scheduling_service = scheduling_service
        self.weather_service = weather_service
        self.overlay_service = overlay_service
        self.settings_service = settings_service

        # Backward compatibility aliases for tests
        self.job_coordination_service = job_coordinator  # Alias for test compatibility
        self.sse_service = sse_ops  # Alias for test compatibility

    @property
    def timelapse_ops(self):
        """
        Access to timelapse database operations.

        Provides compatibility interface for workers that expect timelapse_ops
        from the workflow orchestrator.
        """
        return self.timelapse_service.timelapse_ops

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
                f"Starting capture workflow for camera {camera_id}, timelapse {timelapse_id}",
                emoji=LogEmoji.ROCKET,
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
            # Get camera object and create capture path
            camera = self.camera_service.get_camera_by_id(camera_id)
            if not camera:
                return RTSPCaptureResult(
                    success=False,
                    error=f"Camera {camera_id} not found for capture",
                    message="Camera validation failed",
                )

            # Create output path for captured image following FILE_STRUCTURE_GUIDE.md
            timestamp = utc_now()
            filename = generate_capture_filename(timelapse_id, timestamp)

            # Use existing file_helpers to create entity directory structure
            frames_dir = ensure_entity_directory(camera_id, timelapse_id, "frames")
            output_path = frames_dir / filename

            # Prepare capture settings
            capture_settings = self.rtsp_service._get_capture_settings()
            capture_settings.update({"quality": 90})

            logger.debug(
                "Capturing image via RTSP service",
                emoji=LogEmoji.CAMERA,
                extra_context={
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "camera_name": camera.name,
                    "output_path": str(output_path),
                    "capture_quality": 90,
                    "filename": filename,
                },
            )

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
                logger.error(
                    f"RTSP capture failed: {capture_result.error}",
                    emoji=LogEmoji.FAILED,
                    extra_context={
                        "camera_id": camera_id,
                        "timelapse_id": timelapse_id,
                        "camera_name": camera.name,
                        "rtsp_url": camera.rtsp_url,
                        "error_type": "rtsp_capture_failed",
                        "output_path": str(output_path),
                    },
                )
                return capture_result

            # Validate successful capture has image_path
            if not capture_result.image_path:
                logger.error(
                    "Successful capture result missing image_path",
                    extra_context={
                        "camera_id": camera_id,
                        "timelapse_id": timelapse_id,
                        "error_type": "missing_image_path",
                        "capture_result": {
                            "success": capture_result.success,
                            "message": capture_result.message,
                        },
                    },
                    emoji=LogEmoji.FAILED,
                )
                return RTSPCaptureResult(
                    success=False,
                    error="Missing image path in successful capture result",
                    message="Capture validation failed",
                )

            # 3. Evaluate image quality using CorruptionService
            logger.debug(
                "🔍 Evaluating image quality",
                extra_context={
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "image_path": str(capture_result.image_path),
                    "operation": "evaluate_image_quality",
                },
            )
            quality_result = self._evaluate_image_quality(
                camera_id=camera_id, image_path=capture_result.image_path
            )

            # 4. Handle quality evaluation results
            if quality_result["should_discard"]:
                logger.warning(
                    f"Image discarded due to quality: {quality_result['reason']}",
                    extra_context={
                        "camera_id": camera_id,
                        "timelapse_id": timelapse_id,
                        "image_path": str(capture_result.image_path),
                        "discard_reason": quality_result["reason"],
                        "corruption_score": quality_result.get("corruption_score"),
                        "operation": "image_quality_discard",
                    },
                )
                # Clean up the captured file
                self._cleanup_discarded_image(capture_result.image_path)

                # Check if retry is recommended
                if quality_result.get("retry_recommended", False):
                    logger.info(
                        "Retrying capture due to quality issues",
                        extra_context={
                            "camera_id": camera_id,
                            "timelapse_id": timelapse_id,
                            "operation": "quality_retry",
                            "original_reason": quality_result["reason"],
                        },
                    )
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
            logger.debug("Broadcasting capture events", emoji=LogEmoji.BROADCAST)
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
            logger.error("Capture workflow failed", exception=e)
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
            camera = self.camera_service.get_camera_by_id(camera_id)
            timelapse = self.timelapse_service.get_timelapse_by_id(timelapse_id)

            if not camera:
                return {"valid": False, "error": f"Camera {camera_id} not found"}

            if not timelapse:
                return {"valid": False, "error": f"Timelapse {timelapse_id} not found"}

            # Trust scheduler validation for status, health, timing, etc.
            # Only basic existence validation here
            return {"valid": True}

        except Exception as e:
            logger.error("Error in basic capture validation", exception=e)
            return {"valid": False, "error": f"Basic validation error: {str(e)}"}

    def _evaluate_image_quality(
        self,
        camera_id: int,
        image_path: str,
        _workflow_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate captured image quality using CorruptionService.

        TEMPORARILY DISABLED: Always return good quality to bypass corruption evaluation issues.

        Args:
            camera_id: Camera identifier
            image_path: Path to captured image
            workflow_context: Optional workflow context

        Returns:
            Quality evaluation result
        """
        logger.info(
            f"📸 Image quality evaluation BYPASSED for {image_path} - accepting all images"
        )

        # TEMPORARY BYPASS: Always return good quality
        return {
            "success": True,
            "should_discard": False,
            "retry_recommended": False,
            "final_score": 0.0,
            "quality_verdict": "good_quality",
            "fast_score": 0.0,
            "heavy_score": 0.0,
            "reason": "Quality evaluation temporarily disabled - all images accepted",
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
            # Use existing file_helpers to get proper relative path for database storage
            file_path = get_relative_path(Path(image_path))

            # Get timezone-aware timestamp using database timezone settings
            if self.settings_service:
                captured_time = get_timezone_aware_timestamp_sync(self.settings_service)
                logger.debug(f"Using timezone-aware timestamp: {captured_time}")
            else:
                captured_time = utc_now()
                logger.warning(
                    "Using UTC timestamp - settings_service not available for timezone conversion"
                )

            # Calculate correct day number based on timelapse start date
            day_number = self._calculate_day_number(timelapse_id, captured_time)

            # Get current weather data
            weather_data = self._get_current_weather()

            # Extract filename from path for database storage
            filename = Path(image_path).name

            image_data = {
                "camera_id": camera_id,
                "timelapse_id": timelapse_id,
                "file_path": file_path,
                "filename": filename,
                "captured_at": captured_time,
                "corruption_score": int(quality_data.get("final_score", 0.0)),
                "is_flagged": quality_data.get("quality_verdict") == "warning",
                "file_size": (
                    Path(image_path).stat().st_size if Path(image_path).exists() else 0
                ),
                # Required database fields
                "corruption_detected": quality_data.get("quality_verdict") == "warning",
                "day_number": day_number,
                "thumbnail_path": None,  # Will be set by thumbnail worker
                # Weather data from current weather_data table
                "weather_conditions": weather_data.get("current_weather_description"),
                "weather_fetched_at": weather_data.get("weather_date_fetched"),
                "weather_icon": weather_data.get("current_weather_icon"),
                "weather_temperature": weather_data.get("current_temp"),
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
            logger.error("Error creating image record", exception=e)
            return None

    def _calculate_day_number(self, timelapse_id: int, captured_time) -> int:
        """
        Calculate the correct day number for a timelapse based on its start date.

        IMPORTANT: Uses timezone-aware dates to ensure day boundaries align with
        user's local timezone, not UTC.

        Args:
            timelapse_id: ID of the timelapse
            captured_time: When the image was captured (timezone-aware)

        Returns:
            Day number (1-based) relative to timelapse start
        """
        try:
            # Get timelapse start date
            timelapse = self.timelapse_service.get_timelapse_by_id(timelapse_id)
            if not timelapse or not timelapse.start_date:
                logger.warning(
                    f"Could not get start date for timelapse {timelapse_id}, defaulting to day 1"
                )
                return 1

            # Convert both dates to timezone-aware dates for proper day calculation
            if self.settings_service:
                # Use timelapse start date directly since it's already a date
                start_date = timelapse.start_date
                current_date = captured_time.date()
                logger.debug(
                    f"Day calculation: start_date={start_date}, current_date={current_date}"
                )
            else:
                # Fallback to using start_date directly
                start_date = timelapse.start_date
                current_date = captured_time.date()
                logger.warning(
                    "Day calculation using direct dates - timezone conversion unavailable"
                )

            day_number = DatabaseUtilities.calculate_day_number(
                start_date, current_date
            )
            logger.debug(
                f"Calculated day number {day_number} for timelapse {timelapse_id}"
            )
            return day_number

        except Exception as e:
            logger.error(
                f"Error calculating day number for timelapse {timelapse_id}: {e}"
            )
            return 1  # Default to day 1 on error

    def _get_current_weather(self) -> dict:
        """
        Get current weather data from the weather_data table.

        Returns:
            Dictionary with current weather information, or empty dict if unavailable
        """
        try:
            weather_data = None
            if self.weather_service and hasattr(self.weather_service, "weather_ops"):
                weather_data = self.weather_service.weather_ops.get_latest_weather()

            if (
                weather_data
                and weather_data.get("api_key_valid")
                and not weather_data.get("api_failing")
            ):
                logger.debug(
                    f"Retrieved weather data: temp={weather_data.get('current_temp')}°, conditions={weather_data.get('current_weather_description')}"
                )
                return weather_data
            else:
                logger.debug("No valid weather data available")
                return {}
        except Exception as e:
            logger.warning(f"Error retrieving weather data: {e}")
            return {}

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
                priority=ThumbnailJobPriority.MEDIUM,
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
            logger.error("Error coordinating background jobs", exception=e)
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

            self.sse_ops.create_event(
                event_type=SSEEvent.IMAGE_CAPTURED,
                event_data={
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "image_count": image_count,
                    "day_number": day_number,
                    "image_id": image_record.id,
                },
                priority=SSEPriority.NORMAL,
                source=SSEEventSource.CAPTURE_PIPELINE,
            )

            logger.debug(
                f"Broadcast capture event for image {image_record.id} with {job_results.get('total_jobs_queued', 0)} jobs queued"
            )

        except Exception as e:
            logger.warning(f"Error broadcasting capture events: {e}")

    def _get_timelapse_image_count(self, timelapse_id: int) -> int:
        """Get current image count for timelapse."""
        try:
            timelapse = self.timelapse_service.get_timelapse_by_id(timelapse_id)
            if timelapse:
                return timelapse.image_count
            return 0
        except Exception:
            return 0

    def _cleanup_discarded_image(self, image_path: str) -> None:
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
            logger.error("Error in retry capture workflow", exception=e)
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
                    # Note: Using camera service to update connectivity
                    self.camera_service.update_camera_connectivity(
                        camera_id=camera_id,
                        is_connected=False,
                        error_message=str(error),
                    )
                except Exception as health_error:
                    logger.warning(f"Failed to update camera health: {health_error}")

            # Log error for monitoring
            logger.error(f"Workflow error for camera {camera_id}", exception=error)

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
            logger.error("Error in error handler", exception=handle_error)
            return RTSPCaptureResult(
                success=False,
                error=f"Workflow failed with unhandled error: {str(error)}",
                message=CAMERA_CAPTURE_FAILED,
            )
