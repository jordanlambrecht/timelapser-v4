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
from typing import Dict, Any
from app.utils.time_utils import utc_now


# Import from the same backend directory
from app.database import async_db, sync_db
from app.enums import LogEmoji, LogSource, LoggerName
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
from app.services.logger.logger_service import (
    get_service_logger,
    initialize_global_logger,
)
from app.services.overlay_pipeline.services.job_service import (
    SyncOverlayJobService,
)
from app.services.overlay_pipeline.utils.font_cache import preload_overlay_fonts
from app.services.thumbnail_pipeline.services.job_service import (
    SyncThumbnailJobService,
)

# Logger will be initialized during worker startup
logger = None


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
        - Composition-based services with dependency injection (databases already initialized)
        - Specialized worker instances
        - Cross-worker coordination

        Note: Database initialization is handled by the worker factory pattern
        before this constructor is called.
        """
        global logger

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Get the already initialized logger (databases initialized by factory)
        logger = get_service_logger(LoggerName.SYSTEM, LogSource.SYSTEM)

        logger.info(
            "Worker constructor started (databases already initialized by factory)",
            emoji=LogEmoji.WORKER,
        )

        # Create complete worker ecosystem using factory pattern
        from app.workers.worker_factory import create_worker_ecosystem

        logger.info(
            "Creating worker ecosystem using factory pattern",
            emoji=LogEmoji.FACTORY,
        )

        # Create all workers and services with proper dependency injection
        self.ecosystem = create_worker_ecosystem(sync_db, async_db)

        # Extract commonly used services for backward compatibility
        self.settings_service = self.ecosystem["settings_service"]
        self.weather_manager = self.ecosystem["weather_manager"]
        self.sse_ops = self.ecosystem["sse_ops"]
        self.thumbnail_pipeline = self.ecosystem["thumbnail_pipeline"]
        self.overlay_pipeline = self.ecosystem["overlay_pipeline"]

        logger.info(
            "Worker ecosystem created successfully with dependency injection",
            emoji=LogEmoji.SUCCESS,
        )

        # Initialize specialized workers using ecosystem
        self._initialize_workers_from_ecosystem()

        # Initialize overlay font cache for performance
        self._initialize_font_cache()

        # Worker state
        self.running = False

        logger.info(
            " Modular worker architecture initialized successfully",
            emoji=LogEmoji.STARTUP,
        )

    def _initialize_workers_from_ecosystem(self):
        """Initialize all specialized worker instances from ecosystem."""
        try:
            # Extract workers from ecosystem
            self.capture_worker = self.ecosystem["capture_worker"]
            self.health_worker = self.ecosystem["health_worker"]
            self.weather_worker = self.ecosystem["weather_worker"]
            self.video_worker = self.ecosystem["video_worker"]
            self.scheduler_worker = self.ecosystem["scheduler_worker"]
            self.sse_worker = self.ecosystem["sse_worker"]
            self.cleanup_worker = self.ecosystem["cleanup_worker"]
            self.thumbnail_worker = self.ecosystem["thumbnail_worker"]
            self.overlay_worker = self.ecosystem["overlay_worker"]

            # Extract job services for backward compatibility
            self.thumbnail_job_service = self.ecosystem["thumbnail_job_service"]
            self.overlay_job_service = self.ecosystem["overlay_job_service"]
            self.timelapse_service = self.ecosystem["sync_timelapse_service"]

            logger.info(
                "All specialized workers extracted from ecosystem successfully",
                emoji=LogEmoji.SUCCESS,
            )

        except Exception as e:
            logger.error(
                "Failed to initialize workers from ecosystem",
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

    def get_worker_health(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of all workers and services.

        Returns:
            Dictionary with health status for monitoring and debugging
        """
        try:
            health_status = {
                "timestamp": utc_now().isoformat(),
                "overall_status": "healthy",
                "workers": {},
                "services": {},
                "ecosystem_status": "healthy",
                "error_count": 0,
            }

            # Check worker health
            workers = [
                ("capture_worker", self.capture_worker),
                ("health_worker", self.health_worker),
                ("weather_worker", self.weather_worker),
                ("video_worker", self.video_worker),
                ("scheduler_worker", self.scheduler_worker),
                ("sse_worker", self.sse_worker),
                ("cleanup_worker", self.cleanup_worker),
                ("thumbnail_worker", self.thumbnail_worker),
                ("overlay_worker", self.overlay_worker),
            ]

            for worker_name, worker in workers:
                try:
                    # Check if worker has health method
                    if hasattr(worker, "get_health"):
                        worker_health = worker.get_health()
                    elif hasattr(worker, "running"):
                        worker_health = {
                            "status": "running" if worker.running else "stopped"
                        }
                    else:
                        worker_health = {"status": "available"}

                    health_status["workers"][worker_name] = worker_health

                except Exception as e:
                    health_status["workers"][worker_name] = {
                        "status": "error",
                        "error": str(e),
                    }
                    health_status["error_count"] += 1

            # Check service health
            services = [
                ("settings_service", self.settings_service),
                ("weather_manager", self.weather_manager),
                ("thumbnail_pipeline", self.thumbnail_pipeline),
                ("overlay_pipeline", self.overlay_pipeline),
            ]

            for service_name, service in services:
                try:
                    if hasattr(service, "get_health"):
                        service_health = service.get_health()
                    elif hasattr(service, "is_healthy"):
                        service_health = {
                            "status": "healthy" if service.is_healthy() else "unhealthy"
                        }
                    else:
                        service_health = {"status": "available"}

                    health_status["services"][service_name] = service_health

                except Exception as e:
                    health_status["services"][service_name] = {
                        "status": "error",
                        "error": str(e),
                    }
                    health_status["error_count"] += 1

            # Determine overall status
            if health_status["error_count"] > 0:
                if health_status["error_count"] > 3:
                    health_status["overall_status"] = "unhealthy"
                else:
                    health_status["overall_status"] = "degraded"

            # Add ecosystem statistics
            health_status["ecosystem_stats"] = {
                "total_workers": len(workers),
                "total_services": len(services),
                "factory_created": hasattr(self, "ecosystem"),
                "running": self.running,
            }

            return health_status

        except Exception as e:
            logger.error(
                "Failed to get worker health status",
                exception=e,
            )
            return {
                "timestamp": utc_now().isoformat(),
                "overall_status": "error",
                "error": str(e),
                "ecosystem_status": "error",
            }

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
            "Starting Modular Async Timelapse Worker with comprehensive error handling",
            emoji=LogEmoji.STARTUP,
        )

        try:
            # Step 1: Validate worker ecosystem health before starting
            health_status = self.get_worker_health()
            if health_status["overall_status"] == "error":
                raise RuntimeError(
                    f"Worker ecosystem unhealthy: {health_status.get('error', 'Unknown error')}"
                )

            logger.info(
                f"Worker ecosystem health check passed: {health_status['overall_status']}",
                emoji=LogEmoji.HEALTH,
                extra_context={
                    "workers_count": health_status["ecosystem_stats"]["total_workers"],
                    "services_count": health_status["ecosystem_stats"][
                        "total_services"
                    ],
                    "error_count": health_status["error_count"],
                },
            )

            # Step 2: Start all specialized workers with error handling
            try:
                await self._start_all_workers()
                logger.info(
                    "All workers started successfully",
                    emoji=LogEmoji.SUCCESS,
                )
            except Exception as e:
                logger.error(
                    "Failed to start workers - attempting graceful recovery",
                    exception=e,
                )
                # Attempt to stop any workers that may have started
                await self._stop_all_workers()
                raise

            # Step 3: Start the scheduler with validation
            try:
                self.scheduler_worker.start_scheduler()
                logger.info(
                    "Scheduler started successfully",
                    emoji=LogEmoji.SUCCESS,
                )
            except Exception as e:
                logger.error(
                    "Failed to start scheduler",
                    exception=e,
                )
                await self._stop_all_workers()
                raise

            # Step 4: Configure scheduler functions
            try:
                self.scheduler_worker.set_timelapse_capture_function(
                    self.capture_single_timelapse
                )

                # Add standard jobs to scheduler with validation
                success = self.scheduler_worker.add_standard_jobs(
                    health_check_func=self.check_camera_health,
                    weather_refresh_func=self.refresh_weather_data,
                    video_automation_func=self.process_video_automation,
                    sse_cleanup_func=self.cleanup_sse_events,
                )

                if not success:
                    logger.warning(
                        "Some standard jobs failed to be added - worker may have reduced functionality",
                        emoji=LogEmoji.WARNING,
                    )
                else:
                    logger.info(
                        "All standard jobs added successfully",
                        emoji=LogEmoji.SUCCESS,
                    )

            except Exception as e:
                logger.error(
                    "Failed to configure scheduler jobs",
                    exception=e,
                )
                # Don't fail startup for job configuration issues
                logger.warning(
                    "Continuing startup with reduced scheduler functionality",
                )

            # Step 5: Mark as running and start main loop
            self.running = True
            logger.info(
                "Modular worker started successfully with full functionality",
                emoji=LogEmoji.SUCCESS,
            )

            # Main worker loop with health monitoring
            health_check_interval = 300  # 5 minutes
            last_health_check = 0

            while self.running:
                current_time = asyncio.get_event_loop().time()

                # Periodic health check
                if current_time - last_health_check > health_check_interval:
                    try:
                        health = self.get_worker_health()
                        if health["overall_status"] == "unhealthy":
                            logger.warning(
                                "Worker ecosystem health degraded",
                                emoji=LogEmoji.WARNING,
                                extra_context={
                                    "error_count": health["error_count"],
                                    "workers_with_errors": [
                                        name
                                        for name, status in health["workers"].items()
                                        if status.get("status") == "error"
                                    ],
                                },
                            )
                        last_health_check = current_time
                    except Exception as e:
                        logger.error(
                            "Health check failed",
                            exception=e,
                        )

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info(
                "Worker stopped by user interrupt",
                emoji=LogEmoji.STOP,
            )
        except Exception as e:
            logger.error(
                "Critical worker error - initiating emergency shutdown",
                error_context={"operation": "worker_main_loop"},
                exception=e,
            )
        finally:
            logger.info(
                "Worker shutting down gracefully...",
                emoji=LogEmoji.SHUTDOWN,
            )
            await self._async_shutdown()


async def main():
    """
    Main async entry point for the modular timelapse worker application.

    This function handles the complete worker lifecycle using the new
    modular architecture:
    1. Ensures data directory structure exists
    2. Initializes databases using worker factory pattern
    3. Creates and initializes the AsyncTimelapseWorker with modular design
    4. Manages graceful shutdown on interruption or error

    The modular worker provides improved maintainability and enables
    future architectural evolution while maintaining full compatibility.
    """
    global logger

    # Ensure data directory exists (AI-CONTEXT compliant)
    data_path = settings.data_path
    data_path.mkdir(parents=True, exist_ok=True)

    # Initialize worker database context using factory pattern
    from app.workers.database_factory import create_worker_database_context

    try:
        logger, async_db_instance, sync_db_instance = (
            await create_worker_database_context()
        )

        logger.info(
            "Worker database context initialized successfully",
            emoji=LogEmoji.SUCCESS,
            extra_context={
                "data_path": str(data_path),
                "environment": settings.environment,
            },
        )

    except Exception as e:
        print(f"CRITICAL: Failed to initialize worker database context: {e}")
        raise

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
