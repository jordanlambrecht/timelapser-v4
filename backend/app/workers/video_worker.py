# backend/app/workers/video_worker.py
"""
Video worker for Timelapser v4 - SCHEDULER-CENTRIC EXECUTION-ONLY ARCHITECTURE.

🎯 TRANSFORMATION: This worker now operates in execution-only mode. All timing decisions
and automation triggers are handled by SchedulerWorker. VideoWorker simply executes
specific video generation tasks when commanded by the scheduler authority.

Core Philosophy: "Scheduler says jump, VideoWorker says how high"
"""

from typing import Any, Dict, Optional

from ..database.core import SyncDatabase
from ..enums import (
    LogEmoji,
    LoggerName,
    LogSource,
    VideoAutomationMode,
    WorkerType,
)
from ..models.health_model import HealthStatus
from .base_worker import BaseWorker
from .exceptions import (
    CleanupOperationError,
    HealthCheckError,
    JobProcessingError,
    ServiceUnavailableError,
    VideoGenerationError,
    WorkerInitializationError,
)
from .utils.worker_status_builder import WorkerStatusBuilder

from ..services.logger import get_service_logger

logger = get_service_logger(LoggerName.VIDEO_WORKER, LogSource.WORKER)


class VideoWorker(BaseWorker):
    """
    Worker responsible for VIDEO EXECUTION ONLY using simplified pipeline.

    🎯 SCHEDULER-CENTRIC TRANSFORMATION:
    - NO autonomous trigger processing (moved to SchedulerWorker)
    - NO autonomous job queue processing (responds to scheduler commands)
    - Executes specific video generation jobs when directed by scheduler
    - Provides execution status and health monitoring

    Handles:
    - Execution of specific video generation jobs (when commanded)
    - Video generation using simplified pipeline
    - Execution status reporting
    - Health monitoring and cleanup
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize video worker with simplified architecture.

        Args:
            db: SyncDatabase instance for pipeline creation

        Raises:
            WorkerInitializationError: If required dependencies are missing
        """
        # Validate required dependencies
        if not db:
            raise WorkerInitializationError("SyncDatabase is required")

        super().__init__("VideoWorker")
        self.db = db
        self.workflow_service = (
            None  # Will be VideoWorkflowService after initialization
        )

    async def initialize(self) -> None:
        """Initialize video worker resources using factory pattern."""
        try:
            # Import locally to avoid circular import
            from ..services.video_pipeline import create_video_pipeline

            # Create video pipeline using factory
            self.workflow_service = create_video_pipeline(self.db)

            # FAIL FAST: Service must be initialized properly
            if not self.workflow_service:
                raise WorkerInitializationError(
                    "Failed to initialize video workflow service - worker cannot start"
                )

            logger.info(
                "Initialized video worker with simplified pipeline",
                store_in_db=False,
                emoji=LogEmoji.VIDEO,
            )

            # Startup recovery functionality not implemented in current video pipeline
            logger.debug(
                "VideoWorker initialized - no startup recovery needed",
                store_in_db=False,
            )

        except (WorkerInitializationError, ServiceUnavailableError):
            # Re-raise specific initialization errors
            raise
        except Exception as e:
            logger.error(f"Failed to initialize video worker: {e}", store_in_db=False)
            raise WorkerInitializationError(
                f"Unexpected initialization failure: {e}"
            ) from e

    async def cleanup(self) -> None:
        """Cleanup video worker resources."""
        try:
            if self.workflow_service:
                # Cleanup any failed jobs using job service
                if hasattr(self.workflow_service, "job_service") and hasattr(
                    self.workflow_service.job_service, "cleanup_old_jobs"
                ):
                    cleaned_jobs = self.workflow_service.job_service.cleanup_old_jobs(
                        30
                    )
                    if cleaned_jobs > 0:
                        logger.info(
                            f"Cleaned up {cleaned_jobs} failed jobs during shutdown"
                        )

            logger.info("Cleaned up video worker", emoji=LogEmoji.SUCCESS)
        except CleanupOperationError as e:
            logger.error(f"Error during video worker cleanup: {e}")
        except Exception as e:
            # Unexpected cleanup errors shouldn't prevent shutdown
            logger.warning(f"Unexpected error during cleanup: {e}")

    async def process_pending_jobs(self) -> None:
        """
        🎯 SCHEDULER-CENTRIC: Process pending video jobs in execution-only mode.

        TRANSFORMATION: This method no longer makes autonomous decisions about WHEN
        to create jobs. It only executes existing jobs that were scheduled by
        the SchedulerWorker authority.

        Called by scheduler to process the video job queue.
        """
        try:
            # Service guaranteed to exist after initialization - no defensive check needed
            if not self.workflow_service:
                raise ServiceUnavailableError("VideoWorkflowService not initialized")

            # EXECUTION-ONLY: Process pending jobs without autonomous trigger evaluation
            result = await self.run_in_executor(
                self.workflow_service.process_queue_only
            )

            # Log execution results (no job creation, only processing)
            if result.success:
                if result.jobs_processed > 0:
                    logger.info(
                        f"Video execution: {result.jobs_processed} jobs processed",
                        store_in_db=False,
                    )
                else:
                    logger.debug(
                        "Video execution cycle completed - no pending jobs",
                        store_in_db=False,
                    )
            else:
                if result.errors:
                    logger.error(
                        f"Video execution cycle failed: {'; '.join(result.errors)}",
                    )

        except JobProcessingError as e:
            logger.error(f"Error processing video execution queue: {e}")
        except Exception as e:
            # Unexpected processing errors should be logged but not crash the worker
            logger.warning(f"Unexpected error during job processing: {e}")

    async def execute_video_generation(
        self, timelapse_id: int, video_settings: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        🎯 SCHEDULER-CENTRIC: Execute specific video generation when commanded by scheduler.

        This is a direct execution method that bypasses all autonomous decision-making.
        Called directly by scheduler authority for immediate video generation.

        Args:
            timelapse_id: Timelapse to generate video for
            video_settings: Optional video generation settings override

        Returns:
            bool: True if video generation was executed successfully
        """
        try:
            # Service guaranteed to exist after initialization
            if not self.workflow_service:
                raise ServiceUnavailableError("VideoWorkflowService not initialized")

            logger.info(
                f"Executing video generation for timelapse {timelapse_id} (scheduler commanded)",
                emoji=LogEmoji.VIDEO,
            )

            # EXECUTION-ONLY: Direct video generation without autonomous triggers
            result = await self.run_in_executor(
                self.workflow_service.execute_video_generation_direct,
                timelapse_id,
                video_settings,
            )

            if result.success:
                logger.info(
                    f"Video generation completed for timelapse {timelapse_id}: {result.video_path}",
                    emoji=LogEmoji.SUCCESS,
                )
                return True
            else:
                error = result.error or "Unknown error"
                logger.error(
                    f"Video generation failed for timelapse {timelapse_id}: {error}",
                )
                return False

        except VideoGenerationError as e:
            logger.error(f"Video generation error for timelapse {timelapse_id}: {e}")
            return False
        except ServiceUnavailableError as e:
            logger.error(
                f"Service unavailable during video generation for timelapse {timelapse_id}: {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error executing video generation for timelapse {timelapse_id}: {e}"
            )
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get current video generation status using explicit status pattern.

        Returns:
            Dict[str, Any]: Video generation status information
        """
        try:
            # Build explicit base status - no super() calls
            base_status = WorkerStatusBuilder.build_base_status(
                name=self.name,
                running=self.running,
                worker_type=WorkerType.VIDEO_WORKER,
            )

            # Get video-specific status directly
            service_status = self._get_video_worker_status()

            # Simple, explicit merge
            return WorkerStatusBuilder.merge_service_status(base_status, service_status)

        except Exception as e:
            # Return standardized error status
            return WorkerStatusBuilder.build_error_status(
                name=self.name,
                worker_type=WorkerType.VIDEO_WORKER,
                error_type="unexpected",
                error_message=str(e),
            )

    def _get_video_worker_status(self) -> Dict[str, Any]:
        """
        Get video-specific status information.

        This is used to get service-specific status for the explicit status pattern.
        """
        # Service guaranteed to exist after initialization
        if not self.workflow_service:
            raise ServiceUnavailableError("VideoWorkflowService not initialized")

        # Get processing status from workflow service (now returns typed object)
        processing_status = self.workflow_service.get_processing_status()

        # Return video-specific status information using typed object
        return {
            "worker_type": WorkerType.VIDEO_WORKER,
            "pipeline_status": HealthStatus.HEALTHY.value,
            "active_generations": processing_status.currently_processing,
            "pending_generations": processing_status.queue_status.pending,
            "completed_today": processing_status.queue_status.completed,
            "failed_today": processing_status.queue_status.failed,
            "max_concurrent": processing_status.max_concurrent_jobs,
            "can_process_more": processing_status.can_process_more,
            "workflow_service_status": (
                HealthStatus.HEALTHY.value
                if self.workflow_service
                else HealthStatus.UNREACHABLE.value
            ),
            "database_status": (
                HealthStatus.HEALTHY.value
                if self.db
                else HealthStatus.UNREACHABLE.value
            ),
        }

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status for worker management system compatibility.

        This method provides simple binary health information separate
        from the detailed status reporting in get_status().
        """
        return WorkerStatusBuilder.build_simple_health_status(
            running=self.running,
            worker_type=WorkerType.VIDEO_WORKER,
            additional_checks={
                "workflow_service_available": self.workflow_service is not None,
                "database_available": self.db is not None,
            },
        )

    async def trigger_manual_generation(self, timelapse_id: int) -> bool:
        """
        Trigger manual video generation for a timelapse.

        Args:
            timelapse_id: Timelapse ID to generate video for

        Returns:
            bool: True if generation was triggered successfully
        """
        try:
            # Service guaranteed to exist after initialization
            if not self.workflow_service:
                raise ServiceUnavailableError("VideoWorkflowService not initialized")

            # Trigger manual job processing using direct execution
            result = await self.run_in_executor(
                self.workflow_service.execute_video_generation_direct,
                timelapse_id,
                {"trigger_type": VideoAutomationMode.MANUAL.value},
            )

            if result.success and result.video_id:
                logger.info(
                    f"Triggered manual video generation for timelapse {timelapse_id}, job {result.video_id}",
                    emoji=LogEmoji.SUCCESS,
                )
                return True
            else:
                logger.warning(
                    f"Failed to trigger manual generation for timelapse {timelapse_id}",
                )
                return False

        except VideoGenerationError as e:
            logger.error(
                f"Video generation error during manual trigger for timelapse {timelapse_id}: {e}"
            )
            return False
        except ServiceUnavailableError as e:
            logger.error(
                f"Service unavailable during manual trigger for timelapse {timelapse_id}: {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error triggering manual generation for timelapse {timelapse_id}: {e}"
            )
            return False

    async def clean_old_jobs(self, days_to_keep: int = 30) -> int:
        """
        Clean up old video generation jobs.

        Args:
            days_to_keep: Number of days to retain completed jobs

        Returns:
            int: Number of jobs cleaned up
        """
        try:
            # Service guaranteed to exist after initialization
            if not self.workflow_service:
                raise ServiceUnavailableError("VideoWorkflowService not initialized")

            # Clean up old jobs using job service
            cleaned_count = await self.run_in_executor(
                self.workflow_service.job_service.cleanup_old_jobs, days_to_keep
            )

            if cleaned_count > 0:
                logger.info(
                    f"Cleaned up {cleaned_count} old video jobs",
                    emoji=LogEmoji.CLEANUP,
                )

            return cleaned_count

        except CleanupOperationError as e:
            logger.error(f"Cleanup operation failed for video jobs: {e}")
            return 0
        except ServiceUnavailableError as e:
            logger.error(f"Service unavailable during job cleanup: {e}")
            return 0
        except Exception as e:
            logger.warning(f"Unexpected error cleaning old video jobs: {e}")
            return 0

    async def check_pipeline_health(self) -> Dict[str, Any]:
        """
        Check video pipeline health using simplified architecture.

        Returns:
            Dict[str, Any]: Pipeline health status
        """
        try:
            # Service guaranteed to exist after initialization
            # Get pipeline health using helper function
            from ..services.video_pipeline import get_video_pipeline_health

            health_status_dict = await self.run_in_executor(
                get_video_pipeline_health, self.workflow_service
            )

            # Return the health status dictionary directly since it already has the right structure
            return health_status_dict

        except HealthCheckError as e:
            logger.error(f"Health check operation failed: {e}")
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "error": str(e),
            }
        except ServiceUnavailableError as e:
            logger.error(f"Service unavailable during health check: {e}")
            return {
                "status": HealthStatus.UNREACHABLE.value,
                "error": str(e),
            }
        except Exception as e:
            logger.warning(f"Unexpected error checking video pipeline health: {e}")
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "error": str(e),
            }

    async def process_next_job(self) -> bool:
        """
        Process the next pending video job in the queue.

        Returns:
            bool: True if a job was processed
        """
        try:
            # Service guaranteed to exist after initialization
            if not self.workflow_service:
                raise ServiceUnavailableError("VideoWorkflowService not initialized")

            # Process next job in queue
            job_id = await self.run_in_executor(
                self.workflow_service.process_next_pending_job
            )

            if job_id:
                logger.info(f"Processed video job {job_id}", emoji=LogEmoji.SUCCESS)
                return True
            else:
                logger.debug("No pending jobs to process")
                return False

        except JobProcessingError as e:
            logger.error(f"Job processing failed: {e}")
            return False
        except ServiceUnavailableError as e:
            logger.error(f"Service unavailable during job processing: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error processing next video job: {e}")
            return False
