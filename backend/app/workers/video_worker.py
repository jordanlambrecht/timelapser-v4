# backend/app/workers/video_worker.py
"""
Video worker for Timelapser v4 - SCHEDULER-CENTRIC EXECUTION-ONLY ARCHITECTURE.

🎯 TRANSFORMATION: This worker now operates in execution-only mode. All timing decisions
and automation triggers are handled by SchedulerWorker. VideoWorker simply executes
specific video generation tasks when commanded by the scheduler authority.

Core Philosophy: "Scheduler says jump, VideoWorker says how high"
"""

from typing import Dict, Any, Optional

from .base_worker import BaseWorker
from ..services.video_pipeline import create_video_pipeline, get_video_pipeline_health
from ..services.video_pipeline.video_workflow_service import VideoWorkflowService
from ..database.core import SyncDatabase


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
        """
        super().__init__("VideoWorker")
        self.db = db
        self.workflow_service: Optional[VideoWorkflowService] = None

    async def initialize(self) -> None:
        """Initialize video worker resources using factory pattern."""
        try:
            # Create video pipeline using factory
            self.workflow_service = create_video_pipeline(self.db)
            self.log_info("✅ Initialized video worker with simplified pipeline")

            # Perform startup recovery for stuck video jobs
            if self.workflow_service and hasattr(self.workflow_service, "video_ops"):
                try:
                    self.log_info(
                        "🔄 Performing startup recovery for stuck video generation jobs..."
                    )
                    recovery_results = await self.run_in_executor(
                        self.workflow_service.video_ops.recover_stuck_jobs, 30
                    )

                    if recovery_results.get("stuck_jobs_recovered", 0) > 0:
                        self.log_info(
                            f"✅ Recovered {recovery_results['stuck_jobs_recovered']} stuck video jobs on startup"
                        )
                    elif recovery_results.get("stuck_jobs_found", 0) > 0:
                        self.log_warning(
                            f"⚠️ Found {recovery_results['stuck_jobs_found']} stuck video jobs but only recovered "
                            f"{recovery_results['stuck_jobs_recovered']}"
                        )
                    else:
                        self.log_debug(
                            "No stuck video jobs found during startup recovery"
                        )

                except Exception as e:
                    self.log_error(f"Error during startup recovery for video jobs: {e}")

        except Exception as e:
            self.log_error("❌ Failed to initialize video worker", e)
            raise

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
                        self.log_info(
                            f"Cleaned up {cleaned_jobs} failed jobs during shutdown"
                        )

            self.log_info("✅ Cleaned up video worker")
        except Exception as e:
            self.log_error("❌ Error during video worker cleanup", e)

    async def process_pending_jobs(self) -> None:
        """
        🎯 SCHEDULER-CENTRIC: Process pending video jobs in execution-only mode.

        TRANSFORMATION: This method no longer makes autonomous decisions about WHEN
        to create jobs. It only executes existing jobs that were scheduled by
        the SchedulerWorker authority.

        Called by scheduler to process the video job queue.
        """
        try:
            if not self.workflow_service:
                self.log_error("Video workflow service not initialized")
                return

            # EXECUTION-ONLY: Process pending jobs without autonomous trigger evaluation
            result = await self.run_in_executor(
                self.workflow_service.process_queue_only
            )

            # Log execution results (no job creation, only processing)
            if result.get("success"):
                jobs_processed = result.get("jobs_processed", 0)

                if jobs_processed > 0:
                    self.log_info(f"Video execution: {jobs_processed} jobs processed")
                else:
                    self.log_debug("Video execution cycle completed - no pending jobs")
            else:
                errors = result.get("errors", [])
                if errors:
                    self.log_error(f"Video execution cycle failed: {'; '.join(errors)}")

        except Exception as e:
            self.log_error("Error processing video execution queue", e)

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
            if not self.workflow_service:
                self.log_error("Video workflow service not initialized")
                return False

            self.log_info(
                f"🎬 Executing video generation for timelapse {timelapse_id} (scheduler commanded)"
            )

            # EXECUTION-ONLY: Direct video generation without autonomous triggers
            result = await self.run_in_executor(
                self.workflow_service.execute_video_generation_direct,
                timelapse_id,
                video_settings,
            )

            if result.get("success"):
                video_path = result.get("video_path")
                self.log_info(
                    f"✅ Video generation completed for timelapse {timelapse_id}: {video_path}"
                )
                return True
            else:
                error = result.get("error", "Unknown error")
                self.log_error(
                    f"❌ Video generation failed for timelapse {timelapse_id}: {error}"
                )
                return False

        except Exception as e:
            self.log_error(
                f"Error executing video generation for timelapse {timelapse_id}", e
            )
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get current video generation status (STANDARDIZED METHOD NAME).

        This replaces get_video_generation_status() for consistency with other workers.

        Returns:
            Dict[str, Any]: Video generation status information
        """
        try:
            # Get base status from BaseWorker
            base_status = super().get_status()

            if not self.workflow_service:
                base_status.update(
                    {
                        "worker_type": "VideoWorker",
                        "pipeline_status": "error",
                        "error": "Video workflow service not initialized",
                        "active_generations": 0,
                        "pending_generations": 0,
                        "can_process_more": False,
                    }
                )
                return base_status

            # Get processing status from workflow service
            processing_status = self.workflow_service.get_processing_status()
            queue_status = processing_status.get("queue_status", {})

            # Add video-specific status information
            base_status.update(
                {
                    "worker_type": "VideoWorker",
                    "pipeline_status": "healthy",
                    "active_generations": processing_status.get(
                        "currently_processing", 0
                    ),
                    "pending_generations": queue_status.get("pending", 0),
                    "completed_today": queue_status.get("completed", 0),
                    "failed_today": queue_status.get("failed", 0),
                    "max_concurrent": processing_status.get("max_concurrent_jobs", 0),
                    "can_process_more": processing_status.get(
                        "can_process_more", False
                    ),
                    "workflow_service_status": (
                        "healthy" if self.workflow_service else "unavailable"
                    ),
                    "database_status": "healthy" if self.db else "unavailable",
                }
            )

            return base_status

        except Exception as e:
            self.log_error("Error getting video generation status", e)
            base_status = super().get_status()
            base_status.update(
                {
                    "worker_type": "VideoWorker",
                    "pipeline_status": "error",
                    "error": str(e),
                    "active_generations": 0,
                    "pending_generations": 0,
                    "can_process_more": False,
                }
            )
            return base_status

    async def get_video_generation_status(self) -> Dict[str, Any]:
        """
        Get current video generation status (DEPRECATED - use get_status()).

        Kept for backward compatibility.
        """
        # Delegate to standardized method
        status = self.get_status()
        return {
            "active_generations": status.get("active_generations", 0),
            "pending_generations": status.get("pending_generations", 0),
            "completed_today": status.get("completed_today", 0),
            "failed_today": status.get("failed_today", 0),
            "max_concurrent": status.get("max_concurrent", 0),
            "can_process_more": status.get("can_process_more", False),
            "queue_status": (
                "healthy" if status.get("pipeline_status") == "healthy" else "error"
            ),
            **({"error": status["error"]} if "error" in status else {}),
        }

    async def trigger_manual_generation(self, timelapse_id: int) -> bool:
        """
        Trigger manual video generation for a timelapse.

        Args:
            timelapse_id: Timelapse ID to generate video for

        Returns:
            bool: True if generation was triggered successfully
        """
        try:
            if not self.workflow_service:
                self.log_error("Video workflow service not initialized")
                return False

            # Trigger manual job processing using direct execution
            result = await self.run_in_executor(
                self.workflow_service.execute_video_generation_direct,
                timelapse_id,
                {"trigger_type": "manual"},
            )
            job_id = result.get("video_id") if result.get("success") else None

            if job_id:
                self.log_info(
                    f"✅ Triggered manual video generation for timelapse {timelapse_id}, job {job_id}"
                )
                return True
            else:
                self.log_warning(
                    f"❌ Failed to trigger manual generation for timelapse {timelapse_id}"
                )
                return False

        except Exception as e:
            self.log_error(
                f"Error triggering manual generation for timelapse {timelapse_id}", e
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
            if not self.workflow_service:
                self.log_error("Video workflow service not initialized")
                return 0

            # Clean up old jobs using job service
            cleaned_count = await self.run_in_executor(
                self.workflow_service.job_service.cleanup_old_jobs, days_to_keep
            )

            if cleaned_count > 0:
                self.log_info(f"✅ Cleaned up {cleaned_count} old video jobs")

            return cleaned_count

        except Exception as e:
            self.log_error("Error cleaning old video jobs", e)
            return 0

    async def get_video_pipeline_health(self) -> Dict[str, Any]:
        """
        Check video pipeline health using simplified architecture.

        Returns:
            Dict[str, Any]: Pipeline health status
        """
        try:
            if not self.workflow_service:
                return {
                    "status": "unhealthy",
                    "error": "Video workflow service not initialized",
                }

            # Get pipeline health using helper function
            health_status = await self.run_in_executor(
                get_video_pipeline_health, self.workflow_service
            )

            return health_status

        except Exception as e:
            self.log_error("Error checking video pipeline health", e)
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def process_next_job(self) -> bool:
        """
        Process the next pending video job in the queue.

        Returns:
            bool: True if a job was processed
        """
        try:
            if not self.workflow_service:
                self.log_error("Video workflow service not initialized")
                return False

            # Process next job in queue
            job_id = await self.run_in_executor(
                self.workflow_service.process_next_pending_job
            )

            if job_id:
                self.log_info(f"✅ Processed video job {job_id}")
                return True
            else:
                self.log_debug("No pending jobs to process")
                return False

        except Exception as e:
            self.log_error("Error processing next video job", e)
            return False
