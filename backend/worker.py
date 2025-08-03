#!/usr/bin/env python3
#
"""
Timelapser Async Worker with Modular Architecture

This module implements an asynchronous timelapse worker using a modular architecture:

Core Functionality:
- Orchestrates specialized worker classes for different responsibilities
- Maintains the same external interface as the monolithic version
- Provides improved maintainability and testability

Worker Architecture (CEO Pattern):
- SchedulerWorker: CEO - Makes ALL timing decisions and coordinates work
- CaptureWorker: Direct delegate - Executes captures when instructed by scheduler
- HealthWorker: Direct delegate - Performs health checks when called
- WeatherWorker: Direct delegate - Refreshes weather data when called
- VideoWorker: Direct delegate - Processes video jobs when called
- ThumbnailWorker: Background processor - Autonomously processes thumbnail job queues
- OverlayWorker: Background processor - Autonomously processes overlay job queues
- CleanupWorker: Maintenance processor - Runs scheduled cleanup operations

IMPORTANT ARCHITECTURAL CLARIFICATION:
Some workers have run() methods for autonomous background processing:
- ThumbnailWorker.run() - Processes thumbnail generation job queues continuously
- OverlayWorker.run() - Processes overlay generation job queues continuously
- CleanupWorker.run() - Runs scheduled maintenance operations

These run() methods are LEGITIMATE and follow CEO architecture:
- They do NOT make timing decisions (scheduler's job)
- They process work queues created by the scheduler
- They handle background tasks that don't need scheduler coordination
- This pattern prevents blocking the main capture workflow

The CEO pattern is maintained:
- Scheduler = Timing authority and work coordinator
- Background Workers = Job queue processors (timing-independent)
- Direct Workers = Immediate execution delegates

The modular design allows for:
1. Independent testing of each worker type
2. Easier maintenance and debugging
3. Future scalability and microservice migration
4. Better separation of concerns

This implementation maintains full backward compatibility with the original
monolithic worker while providing a foundation for future architectural evolution.
"""


import signal
import asyncio


# Import from the same backend directory
from app.database import async_db, sync_db
from app.services.logger import Log
from app.enums import LogEmoji, LogLevel, LogSource, LoggerName
from app.config import settings
from app.database.sse_events_operations import SyncSSEEventsOperations
from app.dependencies import set_scheduler_worker

# Import new worker architecture
from app.workers import (
    CaptureWorker,
    HealthWorker,
    WeatherWorker,
    VideoWorker,
    SchedulerWorker,
    SSEWorker,
    CleanupWorker,
    ThumbnailWorker,
    OverlayWorker,
)

# Import composition-based services (only for non-capture workers)
# from app.services.video_service import SyncVideoService  # REMOVED: Using video pipeline now
from app.services.settings_service import SyncSettingsService
from app.services.camera_service import SyncCameraService
from app.services.timelapse_service import SyncTimelapseService
from app.services.thumbnail_pipeline.thumbnail_pipeline import ThumbnailPipeline
from app.services.overlay_pipeline.overlay_pipeline import OverlayPipeline
from app.services.weather.service import WeatherManager
from app.services.logger.logger_service import get_service_logger
from app.services.overlay_pipeline.services.job_service import (
    SyncOverlayJobService,
)
from app.services.overlay_pipeline.utils.font_cache import preload_overlay_fonts
from app.services.thumbnail_pipeline.services.job_service import (
    SyncThumbnailJobService,
)

logger = get_service_logger(LoggerName.SYSTEM, LogSource.SYSTEM)


class AsyncTimelapseWorker:
    """
    Modular asynchronous timelapse worker for concurrent camera management.

    This class orchestrates specialized worker instances for different responsibilities:
    - CaptureWorker: Image capture and health monitoring
    - WeatherWorker: Weather data refresh and management
    - VideoWorker: Video automation processing
    - SchedulerWorker: Job scheduling and interval management
    - ThumbnailWorker: Background thumbnail generation processing
    - OverlayWorker: Background overlay generation processing

    The modular design provides:
    - Better separation of concerns
    - Improved testability and maintainability
    - Foundation for future microservice architecture
    - Independent scaling of different worker types

    Maintains full backward compatibility with the original monolithic worker
    while enabling future architectural evolution.
    """

    def __init__(self):
        """
        Initialize the modular async timelapse worker.

        Sets up all necessary components including:
        - Signal handlers for graceful shutdown
        - Database initialization
        - Composition-based services with dependency injection
        - Specialized worker instances
        - Cross-worker coordination
        """
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Initialize sync database for worker FIRST
        sync_db.initialize()

        logger.info(
            "Sync database initialized for worker",
        )

        # Initialize composition-based services (only for non-capture workers)
        from app.database.weather_operations import SyncWeatherOperations
        from app.database.overlay_job_operations import SyncOverlayJobOperations

        weather_ops = SyncWeatherOperations(sync_db)
        overlay_job_ops = SyncOverlayJobOperations(sync_db)
        self.sse_ops = SyncSSEEventsOperations(sync_db)

        # Initialize core services (order matters for dependencies)
        self.settings_service = SyncSettingsService(sync_db)

        # Initialize weather manager first (needed by other services)
        self.weather_manager = WeatherManager(weather_ops, self.settings_service)

        # Initialize services for non-capture workers only (capture pipeline handles its own)
        # Note: VideoWorker now uses simplified pipeline directly - no legacy video service needed
        self.thumbnail_pipeline = ThumbnailPipeline(
            database=sync_db,
        )
        self.overlay_pipeline = OverlayPipeline(
            database=sync_db,
        )

        # Initialize specialized workers
        self._initialize_workers()

        # Initialize overlay font cache for performance
        self._initialize_font_cache()

        # Worker state
        self.running = False

        logger.info(
            " Modular worker architecture initialized successfully",
            emoji=LogEmoji.STARTUP,
        )

    def _initialize_workers(self):
        """Initialize all specialized worker instances."""
        try:
            # Initialize CaptureWorker using the new factory pattern
            from app.services.capture_pipeline import (
                create_capture_pipeline,
                WorkflowOrchestratorService,
            )

            logger.info(
                "Creating capture pipeline with factory function...",
                emoji=LogEmoji.FACTORY,
            )
            workflow_orchestrator: WorkflowOrchestratorService = (
                create_capture_pipeline(settings_service=self.settings_service)
            )

            self.capture_worker = CaptureWorker(
                workflow_orchestrator=workflow_orchestrator,
                weather_manager=self.weather_manager,
            )

            # Initialize HealthWorker with proper dependency injection
            health_camera_service = SyncCameraService(
                sync_db, 
                async_db,
                rtsp_service=workflow_orchestrator.rtsp_service,
                settings_service=self.settings_service
            )
            
            self.health_worker = HealthWorker(
                camera_service=health_camera_service,
                rtsp_service=workflow_orchestrator.rtsp_service,
            )

            # Initialize WeatherWorker
            self.weather_worker = WeatherWorker(
                self.weather_manager,
                self.settings_service,
                self.sse_ops,
            )

            # Initialize VideoWorker with simplified pipeline
            self.video_worker = VideoWorker(sync_db)

            # Initialize SchedulerWorker with scheduling service from workflow orchestrator
            # The scheduling_service might be None, so we need to handle that case
            from app.services.scheduling import (
                SyncTimeWindowService,
                SyncSchedulingService,
                SyncCaptureTimingService,
            )

            scheduling_service: SyncCaptureTimingService
            if workflow_orchestrator.scheduling_service is None:
                # Create scheduling service if not provided
                time_window_service = SyncTimeWindowService(sync_db)
                scheduling_service = SyncSchedulingService(
                    sync_db, 
                    async_db,
                    time_window_service, 
                    self.settings_service
                )
            else:
                scheduling_service = workflow_orchestrator.scheduling_service

            self.scheduler_worker = SchedulerWorker(
                self.settings_service,
                sync_db,
                scheduling_service,
            )

            # 🎯 SCHEDULER-CENTRIC: Set global scheduler worker instance for dependency injection
            set_scheduler_worker(self.scheduler_worker)

            # Initialize SSEWorker
            self.sse_worker = SSEWorker(async_db)

            # Initialize CleanupWorker
            self.cleanup_worker = CleanupWorker(
                sync_db,
                async_db,
                self.settings_service,
                cleanup_interval_hours=6,  # Run cleanup every 6 hours
            )

            self.thumbnail_job_service = SyncThumbnailJobService(
                sync_db, self.settings_service
            )

            self.thumbnail_worker = ThumbnailWorker(
                thumbnail_job_service=self.thumbnail_job_service,
                thumbnail_pipeline=self.thumbnail_pipeline,
                sse_ops=self.sse_ops,
            )

            # Initialize OverlayJobService
            self.overlay_job_service = SyncOverlayJobService(
                sync_db, self.settings_service
            )

            self.timelapse_service = SyncTimelapseService(sync_db)

            self.overlay_worker = OverlayWorker(
                sync_db,
                self.settings_service,
                weather_manager=self.weather_manager,
            )

            # Connect optional job services to capture worker for backward compatibility
            self.capture_worker.thumbnail_job_service = self.thumbnail_job_service
            self.capture_worker.overlay_job_service = self.overlay_job_service

            logger.info(
                "All specialized workers initialized successfully",
                emoji=LogEmoji.SUCCESS,
            )

        except Exception as e:
            logger.error(
                "Failed to initialize workers",
                exception=e,
            )
            raise

    def _initialize_font_cache(self):
        """Initialize global font cache for overlay performance optimization."""
        try:

            logger.info(
                "Preloading overlay fonts for performance optimization...",
                emoji=LogEmoji.SYSTEM,
            )
            preload_overlay_fonts()
            logger.info(
                "Overlay font cache initialized successfully",
                emoji=LogEmoji.SUCCESS,
            )

        except Exception as e:
            logger.warning(
                "Failed to initialize font cache (overlay performance may be reduced)",
                error_context={"operation": "font_cache_initialization"},
                exception=e,
            )

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(
            f"Received signal {signum}, shutting down gracefully...",
            system_context={"signal": signum},
        )
        self.running = False
        # Don't shut down scheduler here - let the main loop handle it

    async def _async_shutdown(self):
        """Async shutdown cleanup."""
        try:
            logger.info(
                "Starting async shutdown...",
            )

            # Stop all workers
            await self._stop_all_workers()

            # Stop scheduler
            if (
                hasattr(self.scheduler_worker, "scheduler")
                and self.scheduler_worker.scheduler.running
            ):
                self.scheduler_worker.stop_scheduler()

            # Close sync database connections
            sync_db.close()
            logger.info(
                "Database connections closed",
            )

        except Exception as e:
            logger.error(
                "Error during async shutdown",
                exception=e,
            )

    async def _stop_all_workers(self):
        """Stop all specialized workers."""
        try:
            workers = [
                self.capture_worker,
                self.health_worker,
                self.weather_worker,
                self.video_worker,
                self.scheduler_worker,
                self.cleanup_worker,
                self.thumbnail_worker,
                self.overlay_worker,
            ]

            # Stop all workers concurrently
            await asyncio.gather(
                *[worker.stop() for worker in workers], return_exceptions=True
            )

            logger.info(
                "All workers stopped successfully",
                emoji=LogEmoji.SUCCESS,
            )

        except Exception as e:
            logger.error(
                "Error stopping workers",
                exception=e,
            )

    async def _start_all_workers(self):
        """Start all specialized workers."""
        try:
            workers = [
                self.capture_worker,
                self.health_worker,
                self.weather_worker,
                self.video_worker,
                self.scheduler_worker,
                self.cleanup_worker,
                self.thumbnail_worker,
                self.overlay_worker,
            ]

            # Start all workers concurrently
            await asyncio.gather(
                *[worker.start() for worker in workers], return_exceptions=True
            )

            logger.info(
                "All workers started successfully",
                emoji=LogEmoji.SUCCESS,
            )

        except Exception as e:
            logger.error(
                "Error starting workers",
                error_context={"operation": "start_workers"},
                exception=e,
            )
            raise

    # Wrapper methods to maintain backward compatibility
    async def capture_from_camera(self, camera_info):
        """Capture image from a single camera (delegates to CaptureWorker)."""
        return await self.capture_worker.capture_from_camera(camera_info)

    async def capture_single_timelapse(self, timelapse_id: int):
        """Capture image for a specific timelapse (delegates to CaptureWorker)."""
        return await self.capture_worker.capture_single_timelapse(timelapse_id)

    async def check_camera_health(self):
        """Check camera health status (delegates to HealthWorker)."""
        return await self.health_worker.check_camera_health()

    async def refresh_weather_data(self, force_refresh: bool = False):
        """Refresh weather data (delegates to WeatherWorker)."""
        return await self.weather_worker.refresh_weather_data(
            force_refresh=force_refresh
        )

    async def process_video_automation(self):
        """
        🎯 SCHEDULER-CENTRIC: Process video execution queue (delegates to VideoWorker).

        TRANSFORMATION: This now calls execution-only processing instead of autonomous automation.
        The VideoWorker no longer makes timing decisions - it only executes pending jobs.
        """
        return await self.video_worker.process_pending_jobs()

    async def sync_timelapse_jobs(self):
        """Synchronize timelapse jobs (delegates to SchedulerWorker)."""
        return self.scheduler_worker.sync_running_timelapses()

    async def cleanup_sse_events(self):
        """Clean up old SSE events (delegates to SSEWorker)."""
        return await self.sse_worker.cleanup_old_events()

    async def start(self):
        """
        Start the modular async worker with comprehensive job management.

        This method initializes and starts the complete worker system using
        the new modular architecture:

        Worker Responsibilities:
        1. CaptureWorker - Image capture and health monitoring
        2. WeatherWorker - Weather data refresh and management
        3. VideoWorker - Video automation processing
        4. SchedulerWorker - Job scheduling and interval management

        The modular design provides improved maintainability, testability,
        and enables future architectural evolution while maintaining full
        backward compatibility.
        """
        logger.info(
            "Starting Modular Async Timelapse Worker",
        )

        try:
            # Start all specialized workers
            await self._start_all_workers()

            # Start the scheduler
            self.scheduler_worker.start_scheduler()

            # Set the timelapse capture function for scheduler to call
            self.scheduler_worker.set_timelapse_capture_function(
                self.capture_single_timelapse
            )

            # Add standard jobs to scheduler
            success = self.scheduler_worker.add_standard_jobs(
                health_check_func=self.check_camera_health,
                weather_refresh_func=self.refresh_weather_data,
                video_automation_func=self.process_video_automation,
                sse_cleanup_func=self.cleanup_sse_events,
            )

            if not success:
                logger.warning(
                    "Some standard jobs failed to be added",
                )

            self.running = True
            logger.info(
                "Modular worker started successfully",
                emoji=LogEmoji.SUCCESS,
            )

            # Keep the event loop running
            while self.running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info(
                "Worker stopped by user",
            )
        except Exception as e:
            logger.error(
                "Worker error",
                error_context={"operation": "worker_main_loop"},
                exception=e,
            )
        finally:
            logger.info(
                "Worker shutting down...",
            )
            await self._async_shutdown()


async def main():
    """
    Main async entry point for the modular timelapse worker application.

    This function handles the complete worker lifecycle using the new
    modular architecture:
    1. Ensures data directory structure exists
    2. Configures rotating log files with size and retention limits
    3. Creates and initializes the AsyncTimelapseWorker with modular design
    4. Manages graceful shutdown on interruption or error

    The modular worker provides improved maintainability and enables
    future architectural evolution while maintaining full compatibility.
    """

    # Ensure data directory exists (AI-CONTEXT compliant)
    data_path = settings.data_path
    data_path.mkdir(parents=True, exist_ok=True)

    # Create and start modular async worker with integrated logging
    worker = AsyncTimelapseWorker()
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Main: Worker interrupted by user")
    except Exception as e:
        logger.error(f"Main: Worker error: {e}")
    finally:
        logger.info("Main: Modular worker finished")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exception=e)
    finally:
        logger.info(
            "Application exiting",
            error_context={"operation": "main_application"},
        )
