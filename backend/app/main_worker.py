#!/usr/bin/env python3
#
"""
Timelapser Modular Worker Architecture

Modern asynchronous timelapse worker built with clean modular architecture
and dependency injection patterns.

Core Architecture:
- Service Locator Pattern for dependency management
- Specialized worker classes with clear responsibilities
- Clean separation of concerns and testability

Worker Architecture (CEO Pattern):
- SchedulerWorker: CEO - Makes ALL timing decisions and coordinates work
- CaptureWorker: Direct delegate - Executes captures when instructed by scheduler
- HealthWorker: Direct delegate - Performs health checks when called
- WeatherWorker: Direct delegate - Refreshes weather data when called
- VideoWorker: Direct delegate - Processes video jobs when called
- ThumbnailWorker: Background processor - Autonomously processes thumbnail job queues
- OverlayWorker: Background processor - Autonomously processes overlay job queues
- CleanupWorker: Maintenance processor - Runs scheduled cleanup operations

Background Processing Pattern:
Some workers have run() methods for autonomous background processing:
- ThumbnailWorker.run() - Processes thumbnail generation job queues continuously
- OverlayWorker.run() - Processes overlay generation job queues continuously
- CleanupWorker.run() - Runs scheduled maintenance operations

This follows CEO architecture principles:
- They do NOT make timing decisions (scheduler's job)
- They process work queues created by the scheduler
- They handle background tasks that don't need scheduler coordination
- This pattern prevents blocking the main capture workflow

Architecture Benefits:
1. Independent testing of each worker type
2. Easier maintenance and debugging
3. Scalability and microservice readiness
4. Clean separation of concerns
5. Type-safe dependency injection
"""


import asyncio
import signal
from typing import Any, Dict, Optional

from .config import settings

# Import from the same app directory
from .database import async_db, sync_db
from .enums import LogEmoji, LoggerName, LogSource, WorkerType
from .models.health_model import HealthStatus

# Import necessary services for initialization
from .services.logger.logger_service import get_service_logger
from .services.overlay_pipeline.utils.font_cache import preload_overlay_fonts
from .utils.time_utils import utc_now
from .workers.models.main_worker_responses import (
    EcosystemStats,
    MainWorkerStatus,
    ServiceHealthStatus,
    WorkerEcosystemStatus,
    WorkerHealthStatus,
)
from .workers.utils.worker_status_builder import WorkerStatusBuilder

logger: Optional[Any] = None


class AsyncTimelapseWorker:
    """
    Modern modular asynchronous timelapse worker for concurrent camera management.

    Orchestrates specialized worker instances with clean dependency injection:
    - CaptureWorker: Image capture and health monitoring
    - WeatherWorker: Weather data refresh and management
    - VideoWorker: Video automation processing
    - SchedulerWorker: Job scheduling and interval management
    - ThumbnailWorker: Background thumbnail generation processing
    - OverlayWorker: Background overlay generation processing

    Architecture Benefits:
    - Clean separation of concerns
    - Improved testability and maintainability
    - Microservice-ready design
    - Independent scaling of worker types
    - Type-safe service locator pattern
    """

    def __init__(self):
        """
        Initialize the modular async timelapse worker.

        Sets up all necessary components including:
        - Signal handlers for graceful shutdown
        - Composition-based services with dependency injection
          (databases already initialized)
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
        assert logger is not None, "Logger must be initialized"

        logger.info(
            "Worker constructor started (databases already initialized by factory)",
            emoji=LogEmoji.WORKER,
        )

        # Create complete worker ecosystem using service locator pattern
        from .workers.service_locator import create_worker_ecosystem

        logger.info(
            "Creating worker ecosystem using service locator pattern",
            emoji=LogEmoji.FACTORY,
        )

        # Create all workers and services with proper dependency injection
        self.ecosystem = create_worker_ecosystem(sync_db, async_db)

        # Extract commonly used services for easy access
        service_locator = self.ecosystem["service_locator"]
        self.settings_service = service_locator.get_sync_settings_service()
        self.weather_manager = service_locator.get_weather_manager()
        self.sse_ops = service_locator.get_sync_sse_operations()
        self.thumbnail_pipeline = service_locator.get_thumbnail_pipeline()
        self.overlay_pipeline = service_locator.get_overlay_pipeline()

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
            "Modular worker architecture initialized successfully",
            emoji=LogEmoji.STARTUP,
        )

    def _initialize_workers_from_ecosystem(self):
        """Initialize all specialized worker instances from ecosystem."""
        try:
            assert logger is not None, "Logger must be initialized"
            # Extract workers from background_workers
            background_workers = self.ecosystem["background_workers"]
            service_locator = self.ecosystem["service_locator"]

            self.capture_worker = background_workers["capture"]
            self.weather_worker = background_workers["weather"]
            self.video_worker = background_workers["video"]
            self.cleanup_worker = background_workers["cleanup"]
            self.thumbnail_worker = background_workers["thumbnail"]
            self.overlay_worker = background_workers["overlay"]

            # Create missing workers that aren't in the service locator yet
            # from .services.camera_service import SyncCameraService

            # Create health worker
            # from .services.capture_pipeline.rtsp_service import RTSPService
            from .workers.health_worker import HealthWorker
            from .workers.scheduler_worker import SchedulerWorker
            from .workers.sse_worker import SSEWorker

            # Use singleton services instead of creating new instances
            from .dependencies.sync_services import (
                get_sync_camera_service,
                get_rtsp_service,
            )

            sync_camera_service = get_sync_camera_service()
            rtsp_service = get_rtsp_service()

            self.health_worker = HealthWorker(
                camera_service=sync_camera_service,
                rtsp_service=rtsp_service,
                async_camera_service=service_locator.get_camera_service(),
            )

            # Create scheduler worker with singleton services
            from .dependencies.sync_services import (
                # get_sync_time_window_service,
                get_sync_capture_timing_service,
            )

            # time_window_service = get_sync_time_window_service()
            scheduling_service = get_sync_capture_timing_service()

            self.scheduler_worker = SchedulerWorker(
                settings_service=service_locator.get_sync_settings_service(),
                db=service_locator.sync_db,
                scheduling_service=scheduling_service,
            )

            # Create SSE worker
            self.sse_worker = SSEWorker(
                db=service_locator.async_db,
            )

            # Extract job services for easy access
            self.thumbnail_job_service = service_locator.get_thumbnail_job_service()
            self.overlay_job_service = service_locator.get_overlay_job_service()
            self.timelapse_service = service_locator.get_sync_timelapse_service()

            logger.info(
                "All specialized workers extracted from ecosystem successfully",
                emoji=LogEmoji.SUCCESS,
            )

        except Exception as e:
            assert logger is not None, "Logger must be initialized"
            logger.error(f"Failed to initialize workers from ecosystem: {e}")
            raise

    def _initialize_font_cache(self):
        """Initialize global font cache for overlay performance optimization."""
        try:
            assert (
                logger is not None
            ), "Logger must be initialized before font cache initialization"

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
            assert logger is not None, "Logger must be initialized"
            logger.warning(
                f"Failed to initialize font cache "
                f"(overlay performance may be reduced): {e}",
                store_in_db=False,
            )

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        assert logger is not None, "Logger must be initialized"
        logger.info(
            f"Received signal {signum}, shutting down gracefully...", store_in_db=False
        )
        self.running = False
        # Don't shut down scheduler here - let the main loop handle it

    async def _async_shutdown(self):
        """Async shutdown cleanup."""
        try:
            assert logger is not None, "Logger must be initialized"
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
            assert logger is not None, "Logger must be initialized"
            logger.error(f"Error during async shutdown: {e}")

    async def _stop_all_workers(self):
        """Stop all specialized workers."""
        try:
            assert logger is not None, "Logger must be initialized"
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
            assert logger is not None, "Logger must be initialized"
            logger.error(f"Error stopping workers: {e}")

    async def _start_all_workers(self):
        """Start all specialized workers."""
        try:
            assert logger is not None, "Logger must be initialized"
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
            assert logger is not None, "Logger must be initialized"
            logger.error(f"Error starting workers: {e}")
            raise

    # Worker delegation methods
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
        Process video execution queue (delegates to VideoWorker).

        The VideoWorker executes pending video jobs without making timing decisions.
        All timing decisions are handled by the SchedulerWorker.
        """
        return await self.video_worker.process_pending_jobs()

    async def sync_timelapse_jobs(self):
        """Synchronize timelapse jobs (delegates to SchedulerWorker)."""
        return self.scheduler_worker.sync_running_timelapses()

    async def cleanup_sse_events(self):
        """Clean up old SSE events (delegates to SSEWorker)."""
        return await self.sse_worker.cleanup_old_events()

    async def execute_cleanup(self):
        """Execute cleanup operations (delegates to CleanupWorker)."""
        return await self.cleanup_worker.execute_cleanup()

    def get_worker_health(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of all workers and services using
        structured models.

        Returns:
            Dictionary with health status for monitoring and debugging
        """
        try:
            assert logger is not None, "Logger must be initialized"

            # Initialize ecosystem status with structured models
            workers_status: Dict[str, WorkerHealthStatus] = {}
            services_status: Dict[str, ServiceHealthStatus] = {}
            error_count = 0
            errors = []

            # Check worker health using WorkerType enums
            worker_configs = [
                ("capture_worker", self.capture_worker, "WorkerType.CAPTURE_WORKER"),
                ("health_worker", self.health_worker, "WorkerType.HEALTH_WORKER"),
                ("weather_worker", self.weather_worker, "WorkerType.WEATHER_WORKER"),
                ("video_worker", self.video_worker, "WorkerType.VIDEO_WORKER"),
                (
                    "scheduler_worker",
                    self.scheduler_worker,
                    "WorkerType.SCHEDULER_WORKER",
                ),
                ("sse_worker", self.sse_worker, "WorkerType.SSE_WORKER"),
                ("cleanup_worker", self.cleanup_worker, "WorkerType.CLEANUP_WORKER"),
                (
                    "thumbnail_worker",
                    self.thumbnail_worker,
                    "WorkerType.THUMBNAIL_WORKER",
                ),
                ("overlay_worker", self.overlay_worker, "WorkerType.OVERLAY_WORKER"),
            ]

            for worker_name, worker, worker_type_str in worker_configs:
                try:
                    # Initialize raw_health to None
                    raw_health = None

                    # Determine worker type enum
                    worker_type = getattr(WorkerType, worker_type_str.split(".")[-1])

                    # Get structured health status
                    if hasattr(worker, "get_health"):
                        raw_health = worker.get_health()
                        running = raw_health.get("running", False)

                        # Convert raw status to HealthStatus enum
                        raw_status = raw_health.get("status", "unknown")
                        if raw_status in ["healthy", "running"]:
                            status = HealthStatus.HEALTHY
                        elif raw_status in ["degraded", "warning"]:
                            status = HealthStatus.DEGRADED
                        elif raw_status in ["unhealthy", "error", "failed"]:
                            status = HealthStatus.UNHEALTHY
                        else:
                            status = HealthStatus.UNKNOWN
                    elif hasattr(worker, "running"):
                        running = worker.running
                        status = (
                            HealthStatus.HEALTHY if running else HealthStatus.UNHEALTHY
                        )
                    else:
                        running = False
                        status = HealthStatus.UNKNOWN

                    workers_status[worker_name] = WorkerHealthStatus(
                        worker_name=worker_name,
                        worker_type=worker_type,
                        status=status,
                        running=running,
                        details=raw_health,
                    )

                except Exception as e:
                    workers_status[worker_name] = WorkerHealthStatus(
                        worker_name=worker_name,
                        worker_type=WorkerType.UNKNOWN,
                        status=HealthStatus.ERROR,
                        running=False,
                        error=str(e),
                    )
                    error_count += 1
                    errors.append(f"Worker {worker_name}: {str(e)}")

            # Check service health
            service_configs = [
                ("settings_service", self.settings_service),
                ("weather_manager", self.weather_manager),
                ("thumbnail_pipeline", self.thumbnail_pipeline),
                ("overlay_pipeline", self.overlay_pipeline),
            ]

            for service_name, service in service_configs:
                try:
                    # Initialize raw_health to None
                    raw_health = None

                    if hasattr(service, "get_health"):
                        raw_health = service.get_health()
                        available = raw_health.get("available", True)
                        raw_status = raw_health.get("status", "unknown")

                        # Convert to HealthStatus enum
                        if raw_status in ["healthy", "available"]:
                            status = HealthStatus.HEALTHY
                        elif raw_status in ["degraded", "warning"]:
                            status = HealthStatus.DEGRADED
                        elif raw_status in ["unhealthy", "error", "unavailable"]:
                            status = HealthStatus.UNHEALTHY
                        else:
                            status = HealthStatus.UNKNOWN

                    elif hasattr(service, "is_healthy"):
                        is_healthy = service.is_healthy()
                        available = True
                        status = (
                            HealthStatus.HEALTHY
                            if is_healthy
                            else HealthStatus.UNHEALTHY
                        )
                    else:
                        available = service is not None
                        status = (
                            HealthStatus.HEALTHY
                            if available
                            else HealthStatus.UNREACHABLE
                        )

                    services_status[service_name] = ServiceHealthStatus(
                        service_name=service_name,
                        status=status,
                        available=available,
                        details=raw_health,
                    )

                except Exception as e:
                    services_status[service_name] = ServiceHealthStatus(
                        service_name=service_name,
                        status=HealthStatus.ERROR,
                        available=False,
                        error=str(e),
                    )
                    error_count += 1
                    errors.append(f"Service {service_name}: {str(e)}")

            # Create ecosystem statistics
            ecosystem_stats = EcosystemStats(
                total_workers=len(worker_configs),
                healthy_workers=sum(
                    1
                    for w in workers_status.values()
                    if w.status == HealthStatus.HEALTHY
                ),
                total_services=len(service_configs),
                healthy_services=sum(
                    1
                    for s in services_status.values()
                    if s.status == HealthStatus.HEALTHY
                ),
                factory_created=hasattr(self, "ecosystem"),
                running=self.running,
            )

            # Determine overall status using HealthStatus enum
            if error_count > 3:
                overall_status = HealthStatus.UNHEALTHY
                ecosystem_status = HealthStatus.UNHEALTHY
            elif error_count > 0:
                overall_status = HealthStatus.DEGRADED
                ecosystem_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.HEALTHY
                ecosystem_status = HealthStatus.HEALTHY

            # Create structured ecosystem status
            ecosystem_status_model = WorkerEcosystemStatus(
                overall_status=overall_status,
                timestamp=utc_now().isoformat(),
                ecosystem_status=ecosystem_status,
                error_count=error_count,
                workers=workers_status,
                services=services_status,
                ecosystem_stats=ecosystem_stats,
                errors=errors,
            )

            # Create main worker status that encompasses the entire ecosystem
            main_worker_status = MainWorkerStatus(
                running=self.running,
                ecosystem_healthy=ecosystem_status == HealthStatus.HEALTHY,
                total_workers_managed=len(worker_configs),
                total_services_managed=len(service_configs),
                ecosystem=ecosystem_status_model,
            )

            # Return as dictionary for backward compatibility
            return main_worker_status.model_dump()

        except Exception as e:
            assert logger is not None, "Logger must be initialized"
            logger.error(f"Failed to get worker health status: {e}")

            # Return structured error status using WorkerStatusBuilder
            error_status = WorkerStatusBuilder.build_error_status(
                name="MainWorker",
                worker_type="MAIN_WORKER",
                error_type="health_check_failed",
                error_message=str(e),
            )
            return error_status

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
        and microservice-ready architecture.
        """
        assert logger is not None, "Logger must be initialized"
        logger.info(
            "Starting Modular Async Timelapse Worker with comprehensive error handling",
            emoji=LogEmoji.STARTUP,
        )

        try:
            # Step 1: Validate worker ecosystem health before starting
            health_status = self.get_worker_health()
            ecosystem_status = health_status["ecosystem"]
            if ecosystem_status["overall_status"] == HealthStatus.ERROR.value:
                errors = ecosystem_status.get("errors", [])
                error_msg = errors[0] if errors else "Unknown error"
                raise RuntimeError(f"Worker ecosystem unhealthy: {error_msg}")

            logger.info(
                f"Worker ecosystem health check passed: "
                f"{ecosystem_status['overall_status']}",
                emoji=LogEmoji.HEALTH,
                extra_context={
                    "workers_count": ecosystem_status["ecosystem_stats"][
                        "total_workers"
                    ],
                    "services_count": ecosystem_status["ecosystem_stats"][
                        "total_services"
                    ],
                    "error_count": ecosystem_status["error_count"],
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
                    f"Failed to start workers - attempting graceful recovery: {e}"
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
                logger.error(f"Failed to start scheduler: {e}")
                await self._stop_all_workers()
                raise

            # Step 4: Configure scheduler functions
            try:
                self.scheduler_worker.set_timelapse_capture_function(
                    self.capture_single_timelapse
                )

                # Add standard jobs to scheduler with validation
                jobs_added = self.scheduler_worker.add_standard_jobs(
                    health_check_func=self.check_camera_health,
                    weather_refresh_func=self.refresh_weather_data,
                    video_automation_func=self.process_video_automation,
                    sse_cleanup_func=self.cleanup_sse_events,
                    cleanup_func=self.execute_cleanup,
                )

                if jobs_added == 0:
                    logger.warning(
                        "No standard jobs were added - worker may have "
                        "reduced functionality",
                        emoji=LogEmoji.WARNING,
                        store_in_db=False,
                    )
                else:
                    logger.info(
                        f"{jobs_added} standard jobs added successfully",
                        emoji=LogEmoji.SUCCESS,
                    )

            except Exception as e:
                logger.error(f"Failed to configure scheduler jobs: {e}")
                # Don't fail startup for job configuration issues
                logger.warning(
                    "Continuing startup with reduced scheduler functionality",
                    store_in_db=False,
                )

            # Step 5: Perform comprehensive startup recovery
            try:
                logger.info(
                    "Performing comprehensive startup recovery...",
                    emoji=LogEmoji.TASK,
                )

                # Use dependency injection singleton to prevent database connection multiplication
                from .dependencies.sync_services import get_sync_recovery_service

                recovery_service = get_sync_recovery_service(scheduler_worker=self.scheduler_worker)

                recovery_results = recovery_service.perform_startup_recovery(
                    max_processing_age_minutes=30, log_recovery_details=True
                )

                # Log recovery summary
                total_recovered = recovery_results.get("total_jobs_recovered", 0)
                timelapse_recovery = recovery_results.get("job_type_results", {}).get(
                    "timelapse_capture_jobs", {}
                )
                timelapses_recovered = timelapse_recovery.get("timelapses_recovered", 0)

                logger.info(
                    f"Startup recovery completed - Jobs: {total_recovered}, "
                    f"Timelapses: {timelapses_recovered}",
                    emoji=LogEmoji.SUCCESS,
                    extra_context={
                        "total_jobs_recovered": total_recovered,
                        "timelapses_recovered": timelapses_recovered,
                        "recovery_duration": recovery_results.get(
                            "recovery_duration_seconds", 0
                        ),
                    },
                )

            except Exception as e:
                logger.error(f"Startup recovery failed: {e}")
                # Don't fail worker startup for recovery issues
                logger.warning(
                    "Continuing startup - individual workers will attempt "
                    "recovery later",
                    store_in_db=False,
                )

            # Step 6: Mark as running and start main loop
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
                        ecosystem = health["ecosystem"]
                        if ecosystem["overall_status"] == HealthStatus.UNHEALTHY.value:
                            logger.warning(
                                "Worker ecosystem health degraded",
                                emoji=LogEmoji.WARNING,
                                extra_context={
                                    "error_count": ecosystem["error_count"],
                                    "workers_with_errors": [
                                        name
                                        for name, status in ecosystem["workers"].items()
                                        if status.get("status")
                                        == HealthStatus.ERROR.value
                                    ],
                                },
                            )
                        last_health_check = current_time
                    except Exception as e:
                        logger.error(f"Health check failed: {e}", store_in_db=False)

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info(
                "Worker stopped by user interrupt",
                emoji=LogEmoji.SHUTDOWN,
            )
        except Exception as e:
            logger.error(f"Critical worker error - initiating emergency shutdown: {e}")
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

    The modular worker provides improved maintainability and
    microservice-ready architecture.
    """
    global logger

    # Ensure data directory exists (AI-CONTEXT compliant)
    data_path = settings.data_path
    data_path.mkdir(parents=True, exist_ok=True)

    # Initialize worker database context using factory pattern
    from .workers.database_factory import create_worker_database_context

    try:
        logger, async_db_instance, sync_db_instance = (
            await create_worker_database_context()
        )
        assert logger is not None, "Logger must be initialized from database factory"

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
        assert logger is not None, "Logger must be initialized"
        logger.info("Main: Worker interrupted by user")
    except Exception as e:
        assert logger is not None, "Logger must be initialized"
        logger.error(f"Main: Worker error: {e}")
    finally:
        assert logger is not None, "Logger must be initialized"
        logger.info("Main: Modular worker finished")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        if logger is not None:
            logger.info("Application interrupted by user")
    except Exception as e:
        if logger is not None:
            logger.error(f"Application error: {e}")
    finally:
        if logger is not None:
            logger.info("Application exiting", store_in_db=False)
