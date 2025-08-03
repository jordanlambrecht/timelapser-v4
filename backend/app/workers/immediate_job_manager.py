# backend/app/workers/immediate_job_manager.py
"""
Immediate Job Manager

ARCHITECTURE RELATIONSHIPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROLE: Manages ON-DEMAND job execution for manual triggers and urgent operations

┌─ ImmediateJobManager (this file) ────────────────────────────────────────────────────┐
│                                                                                      │
│  ┌─ IMMEDIATE CAPTURES ─────────┐     ┌─ IMMEDIATE PROCESSING ───────────────────── │
│  │ • Manual camera captures     │     │ • Video generation (manual/automation)    │ │
│  │ • Scheduler-triggered urgent │     │ • Overlay generation (manual triggers)    │ │
│  │ • Validation & execution     │     │ • Thumbnail generation (immediate)        │ │
│  └───────────────────────────────┘     └────────────────────────────────────────────┘ │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                   ┌────────────────────────┼────────────────────────┐
                   ▼                        ▼                        ▼

┌─ USES UTILITIES ──────┐   ┌─ INTEGRATES WITH ─────┐   ┌─ CALLED BY ──────────┐
│ • JobIdGenerator       │   │ • VideoWorker          │   │ • SchedulerWorker    │
│ • SchedulerTimeUtils   │   │ • OverlayWorker        │   │ • AutomationEvaluator│
│ • Database operations  │   │ • ThumbnailPipeline    │   │ • API endpoints      │
└────────────────────────┘   └────────────────────────┘   └──────────────────────┘

RELATIONSHIP TO SCHEDULER ECOSYSTEM:
• PARENT: SchedulerWorker creates and coordinates this manager
• SIBLINGS: StandardJobManager (recurring), AutomationEvaluator (triggers)
• CHILDREN: None - this is a leaf component that executes final operations

DESIGN PATTERN: Manager with Function Injection
• SchedulerWorker injects timelapse_capture_func reference
• Manager creates wrapper functions for each operation type
• All immediate jobs use APScheduler's date trigger for immediate execution
• Consistent error handling and logging across all immediate operations

IMMEDIATE vs SCHEDULED JOBS:
• IMMEDIATE: One-time execution, triggered by user action or automation
• SCHEDULED: Recurring execution, managed by StandardJobManager
• Both use the same APScheduler instance but different trigger types
"""

from typing import Dict, Any, Optional, Callable
from ..services.logger import get_service_logger, LogEmoji
from ..enums import LoggerName, OverlayJobPriority

logger = get_service_logger(LoggerName.SCHEDULER_WORKER)

from .utils import SchedulerTimeUtils, JobIdGenerator
from ..database.core import SyncDatabase
from ..enums import JobPriority


class ImmediateJobManager:
    """Manages immediate job scheduling for various operations."""

    def __init__(
        self,
        scheduler,
        job_registry: Dict[str, Any],
        db: SyncDatabase,
        time_utils: SchedulerTimeUtils,
        logger_prefix: str = "ImmediateJobManager",
    ):
        """Initialize immediate job manager."""
        self.scheduler = scheduler
        self.job_registry = job_registry
        self.db = db
        self.time_utils = time_utils
        self.logger_prefix = logger_prefix

        # External function references (injected by parent)
        self.timelapse_capture_func: Optional[Callable] = None

    def log_info(self, message: str) -> None:
        """Log info message with prefix."""
        logger.info(f"{self.logger_prefix}: {message}")

    def log_error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Log error message with prefix."""
        if exception:
            logger.error(f"{self.logger_prefix}: {message}: {exception}")
        else:
            logger.error(f"{self.logger_prefix}: {message}")

    def log_warning(self, message: str) -> None:
        """Log warning message with prefix."""
        logger.warning(f"{self.logger_prefix}: {message}")

    def log_debug(self, message: str) -> None:
        """Log debug message with prefix."""
        logger.debug(f"{self.logger_prefix}: {message}")

    async def schedule_immediate_capture(
        self, camera_id: int, timelapse_id: int, priority: str = JobPriority.MEDIUM
    ) -> bool:
        """Schedule immediate capture job."""
        try:
            if not self.timelapse_capture_func:
                self.log_error("No timelapse capture function configured")
                return False

            job_id = JobIdGenerator.immediate_capture(camera_id, timelapse_id)

            # Create capture wrapper
            async def immediate_capture_wrapper():
                try:
                    if self.timelapse_capture_func is not None:
                        await self.timelapse_capture_func(timelapse_id)
                    else:
                        self.log_error("Timelapse capture function not configured")
                except Exception as e:
                    self.log_error(
                        f"Error in immediate capture for timelapse {timelapse_id}", e
                    )

            # Schedule the job
            success = self._add_immediate_job(
                job_id=job_id, func=immediate_capture_wrapper, priority=priority
            )

            if success:
                self.log_info(
                    f"Scheduled immediate capture for camera {camera_id}, timelapse {timelapse_id}"
                )
            else:
                self.log_error(
                    f"Failed to schedule immediate capture for camera {camera_id}, timelapse {timelapse_id}"
                )

            return success

        except Exception as e:
            self.log_error(f"Error scheduling immediate capture", e)
            return False

    async def schedule_immediate_video_generation(
        self,
        timelapse_id: int,
        video_settings: Optional[Dict[str, Any]] = None,
        priority: str = JobPriority.MEDIUM,
    ) -> bool:
        """Schedule immediate video generation job."""
        try:
            job_id = JobIdGenerator.immediate_video(timelapse_id)

            # Create video generation wrapper
            async def immediate_video_wrapper():
                try:
                    # Import video worker to schedule video generation
                    from ..workers.video_worker import VideoWorker

                    # Create video worker with correct constructor
                    video_worker = VideoWorker(self.db)
                    await video_worker.initialize()

                    # Use video workflow service to generate video
                    if video_worker.workflow_service:
                        # Use direct generation method (no job_id required)
                        result = video_worker.workflow_service.execute_video_generation_direct(
                            timelapse_id=timelapse_id, settings=video_settings or {}
                        )
                        self.log_info(f"Video generation result: {result}")
                    else:
                        self.log_error("Video workflow service not initialized")

                except Exception as e:
                    self.log_error(
                        f"Error in immediate video generation for timelapse {timelapse_id}",
                        e,
                    )

            # Schedule the job
            success = self._add_immediate_job(
                job_id=job_id, func=immediate_video_wrapper, priority=priority
            )

            if success:
                self.log_info(
                    f"Scheduled immediate video generation for timelapse {timelapse_id}"
                )
            else:
                self.log_error(
                    f"Failed to schedule immediate video generation for timelapse {timelapse_id}"
                )

            return success

        except Exception as e:
            self.log_error(f"Error scheduling immediate video generation", e)
            return False

    async def schedule_immediate_overlay_generation(
        self, image_id: int, priority: str = JobPriority.MEDIUM
    ) -> bool:
        """Schedule immediate overlay generation job."""
        try:
            job_id = JobIdGenerator.immediate_overlay(image_id)

            # Create overlay generation wrapper
            async def immediate_overlay_wrapper():
                try:
                    # Import overlay worker and services
                    from ..workers.overlay_worker import OverlayWorker
                    from ..services.settings_service import SyncSettingsService

                    # Create settings service and overlay worker with correct constructor
                    settings_service = SyncSettingsService(self.db)
                    overlay_worker = OverlayWorker(
                        db=self.db, settings_service=settings_service
                    )
                    await overlay_worker.initialize()

                    # Queue overlay job instead of direct generation
                    job = overlay_worker.overlay_job_service.queue_job(
                        image_id=image_id, priority=OverlayJobPriority.HIGH
                    )

                    if job:
                        self.log_info(
                            f"Queued overlay generation job {job.id} for image {image_id}"
                        )
                    else:
                        self.log_error(
                            f"Failed to queue overlay job for image {image_id}"
                        )

                except Exception as e:
                    self.log_error(
                        f"Error in immediate overlay generation for image {image_id}", e
                    )

            # Schedule the job
            success = self._add_immediate_job(
                job_id=job_id, func=immediate_overlay_wrapper, priority=priority
            )

            if success:
                self.log_info(
                    f"Scheduled immediate overlay generation for image {image_id}"
                )
            else:
                self.log_error(
                    f"Failed to schedule immediate overlay generation for image {image_id}"
                )

            return success

        except Exception as e:
            self.log_error(f"Error scheduling immediate overlay generation", e)
            return False

    async def schedule_immediate_thumbnail_generation(
        self, image_id: int, priority: str = JobPriority.MEDIUM
    ) -> bool:
        """Schedule immediate thumbnail generation job."""
        try:
            job_id = JobIdGenerator.immediate_thumbnail(image_id)

            # Create thumbnail generation wrapper
            async def immediate_thumbnail_wrapper():
                try:
                    # Import thumbnail pipeline to schedule thumbnail generation
                    from ..services.thumbnail_pipeline.thumbnail_pipeline import (
                        ThumbnailPipeline,
                    )

                    # Create thumbnail pipeline
                    thumbnail_pipeline = ThumbnailPipeline(database=self.db)

                    # Generate thumbnails (sync method, not async)
                    result_dict = thumbnail_pipeline.process_image_thumbnails(image_id)

                    if not result_dict.get("success", False):
                        self.log_warning(
                            f"Thumbnail generation had issues for image {image_id}: {result_dict.get('message', 'Unknown error')}"
                        )

                except Exception as e:
                    self.log_error(
                        f"Error in immediate thumbnail generation for image {image_id}",
                        e,
                    )

            # Schedule the job
            success = self._add_immediate_job(
                job_id=job_id, func=immediate_thumbnail_wrapper, priority=priority
            )

            if success:
                self.log_info(
                    f"Scheduled immediate thumbnail generation for image {image_id}"
                )
            else:
                self.log_error(
                    f"Failed to schedule immediate thumbnail generation for image {image_id}"
                )

            return success

        except Exception as e:
            self.log_error(f"Error scheduling immediate thumbnail generation", e)
            return False

    def _add_immediate_job(
        self, job_id: str, func: Callable, priority: str = JobPriority.MEDIUM
    ) -> bool:
        """Add immediate job to scheduler."""
        try:
            # Remove existing job if present
            if job_id in self.job_registry:
                try:
                    self.scheduler.remove_job(job_id)
                    del self.job_registry[job_id]
                except:
                    pass  # Job may have already completed

            # Add the job with date trigger for immediate execution
            job = self.scheduler.add_job(
                func=func,
                trigger="date",
                id=job_id,
                max_instances=1,
                coalesce=True,
            )

            if job:
                self.job_registry[job_id] = job
                self.log_debug(f"Added immediate job {job_id}")
                return True

            return False

        except Exception as e:
            self.log_error(f"Failed to add immediate job {job_id}", e)
            return False
