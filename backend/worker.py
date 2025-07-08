#!/usr/bin/env python3
#
"""
Timelapser Async Worker with Modular Architecture

This module implements an asynchronous timelapse worker using a modular architecture:

Core Functionality:
- Orchestrates specialized worker classes for different responsibilities
- Maintains the same external interface as the monolithic version
- Provides improved maintainability and testability

Worker Architecture:
- CaptureWorker: Handles image capture and health monitoring
- WeatherWorker: Manages weather data refresh and caching
- VideoWorker: Processes video automation and generation
- SchedulerWorker: Manages job scheduling and intervals

The modular design allows for:
1. Independent testing of each worker type
2. Easier maintenance and debugging
3. Future scalability and microservice migration
4. Better separation of concerns

This implementation maintains full backward compatibility with the original
monolithic worker while providing a foundation for future architectural evolution.
"""

import os
import signal
import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger

# Import from the same backend directory
from app.database import async_db, sync_db
from app.config import settings
from app.database.sse_events_operations import SyncSSEEventsOperations

# Import new worker architecture
from app.workers import (
    CaptureWorker,
    WeatherWorker,
    VideoWorker,
    SchedulerWorker,
    SSEWorker,
    CleanupWorker,
    ThumbnailWorker,
)

# Import composition-based services
from app.services.camera_service import SyncCameraService
from app.services.image_capture_service import ImageCaptureService
from app.services.video_service import SyncVideoService
from app.services.video_automation_service import VideoAutomationService
from app.services.corruption_service import SyncCorruptionService
from app.services.timelapse_service import SyncTimelapseService
from app.services.settings_service import SyncSettingsService
from app.services.thumbnail_service import ThumbnailService
from app.services.weather.service import WeatherManager


class AsyncTimelapseWorker:
    """
    Modular asynchronous timelapse worker for concurrent camera management.

    This class orchestrates specialized worker instances for different responsibilities:
    - CaptureWorker: Image capture and health monitoring
    - WeatherWorker: Weather data refresh and management
    - VideoWorker: Video automation processing
    - SchedulerWorker: Job scheduling and interval management

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
        logger.info("Sync database initialized for worker")

        # Initialize composition-based services
        from app.database.camera_operations import SyncCameraOperations
        from app.database.image_operations import SyncImageOperations
        from app.database.settings_operations import SyncSettingsOperations
        from app.database.weather_operations import SyncWeatherOperations
        from app.database.thumbnail_job_operations import SyncThumbnailJobOperations

        camera_ops = SyncCameraOperations(sync_db)
        image_ops = SyncImageOperations(sync_db)
        settings_ops = SyncSettingsOperations(sync_db)
        weather_ops = SyncWeatherOperations(sync_db)
        thumbnail_job_ops = SyncThumbnailJobOperations(sync_db)
        self.sse_ops = SyncSSEEventsOperations(sync_db)

        # Initialize core services
        self.image_capture_service = ImageCaptureService(
            sync_db, camera_ops, image_ops, settings_ops, 
            thumbnail_job_ops=thumbnail_job_ops
        )
        self.camera_service = SyncCameraService(sync_db, self.image_capture_service)
        self.video_service = SyncVideoService(sync_db)
        self.video_automation_service = VideoAutomationService(sync_db)
        self.corruption_service = SyncCorruptionService(sync_db)
        self.timelapse_service = SyncTimelapseService(sync_db)
        self.settings_service = SyncSettingsService(sync_db)
        self.thumbnail_service = ThumbnailService(
            thumbnail_job_ops, 
            self.sse_ops, 
            image_operations=image_ops,
            settings_service=self.settings_service
        )

        # Initialize weather manager with proper dependency injection
        self.weather_manager = WeatherManager(weather_ops, self.settings_service)
        logger.info("Weather manager initialized with dependency injection")

        # Initialize specialized workers
        self._initialize_workers()

        # Worker state
        self.running = False

        logger.info("✅ Modular worker architecture initialized successfully")

    def _initialize_workers(self):
        """Initialize all specialized worker instances."""
        try:
            # Initialize CaptureWorker (will add thumbnail_job_service after it's created)
            self.capture_worker = CaptureWorker(
                camera_service=self.camera_service,
                image_capture_service=self.image_capture_service,
                timelapse_service=self.timelapse_service,
                settings_service=self.settings_service,
                video_automation_service=self.video_automation_service,
                weather_manager=self.weather_manager,
                sse_ops=self.sse_ops,
            )

            # Initialize WeatherWorker
            self.weather_worker = WeatherWorker(
                weather_manager=self.weather_manager,
                settings_service=self.settings_service,
                sse_ops=self.sse_ops,
            )

            # Initialize VideoWorker
            self.video_worker = VideoWorker(
                video_automation_service=self.video_automation_service,
                video_service=self.video_service,
            )

            # Initialize SchedulerWorker
            self.scheduler_worker = SchedulerWorker(
                settings_service=self.settings_service,
            )

            # Initialize SSEWorker
            self.sse_worker = SSEWorker(async_db)

            # Initialize CleanupWorker
            self.cleanup_worker = CleanupWorker(
                sync_db=sync_db,
                async_db=async_db,
                settings_service=self.settings_service,
                cleanup_interval_hours=6,  # Run cleanup every 6 hours
            )

            # Initialize ThumbnailJobService 
            from app.services.thumbnail_job_service import SyncThumbnailJobService
            self.thumbnail_job_service = SyncThumbnailJobService(
                sync_db=sync_db,
                settings_service=self.settings_service
            )
            
            self.thumbnail_worker = ThumbnailWorker(
                thumbnail_job_service=self.thumbnail_job_service,
                thumbnail_service=self.thumbnail_service,
                sse_ops=self.sse_ops,
            )
            
            # Now connect the thumbnail job service to the capture worker
            self.capture_worker.thumbnail_job_service = self.thumbnail_job_service

            logger.info("All specialized workers initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize workers: {e}")
            raise

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        # Don't shut down scheduler here - let the main loop handle it

    async def _async_shutdown(self):
        """Async shutdown cleanup."""
        try:
            logger.info("Starting async shutdown...")

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
            logger.info("Database connections closed")

        except Exception as e:
            logger.error(f"Error during async shutdown: {e}")

    async def _stop_all_workers(self):
        """Stop all specialized workers."""
        try:
            workers = [
                self.capture_worker,
                self.weather_worker,
                self.video_worker,
                self.scheduler_worker,
                self.cleanup_worker,
                self.thumbnail_worker,
            ]

            # Stop all workers concurrently
            await asyncio.gather(
                *[worker.stop() for worker in workers], return_exceptions=True
            )

            logger.info("All workers stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping workers: {e}")

    async def _start_all_workers(self):
        """Start all specialized workers."""
        try:
            workers = [
                self.capture_worker,
                self.weather_worker,
                self.video_worker,
                self.scheduler_worker,
                self.cleanup_worker,
                self.thumbnail_worker,
            ]

            # Start all workers concurrently
            await asyncio.gather(
                *[worker.start() for worker in workers], return_exceptions=True
            )

            logger.info("All workers started successfully")

        except Exception as e:
            logger.error(f"Error starting workers: {e}")
            raise

    # Wrapper methods to maintain backward compatibility
    async def capture_from_camera(self, camera_info):
        """Capture image from a single camera (delegates to CaptureWorker)."""
        return await self.capture_worker.capture_from_camera(camera_info)

    async def capture_all_running_cameras(self):
        """Capture images from all running cameras (delegates to CaptureWorker)."""
        return await self.capture_worker.capture_all_running_cameras()

    async def check_camera_health(self):
        """Check camera health status (delegates to CaptureWorker)."""
        return await self.capture_worker.check_camera_health()

    async def refresh_weather_data(self, force_refresh: bool = False):
        """Refresh weather data (delegates to WeatherWorker)."""
        return await self.weather_worker.refresh_weather_data(force_refresh=force_refresh)

    async def process_video_automation(self):
        """Process video automation (delegates to VideoWorker)."""
        return await self.video_worker.process_video_automation()

    async def update_scheduler_interval(self):
        """Update scheduler interval (delegates to SchedulerWorker)."""
        return await self.scheduler_worker.update_capture_interval()

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
        logger.info("Starting Modular Async Timelapse Worker")

        try:
            # Start all specialized workers
            await self._start_all_workers()

            # Start the scheduler
            self.scheduler_worker.start_scheduler()

            # Add standard jobs to scheduler
            success = self.scheduler_worker.add_standard_jobs(
                capture_func=self.capture_all_running_cameras,
                health_func=self.check_camera_health,
                weather_func=self.refresh_weather_data,
                video_func=self.process_video_automation,
                sse_cleanup_func=self.cleanup_sse_events,
            )

            if not success:
                logger.warning("Some standard jobs failed to be added")

            self.running = True
            logger.info("Modular worker started successfully")

            # Keep the event loop running
            while self.running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            logger.info("Worker shutting down...")
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

    # Setup logging (AI-CONTEXT compliant)
    log_path = data_path / "worker.log"
    logger.add(
        str(log_path),
        rotation="10 MB",
        retention="30 days",
        level=settings.log_level,
    )

    # Add database logging handler
    try:
        from app.logging.database_handler import setup_database_logging

        setup_database_logging(sync_db)
        logger.info("Database logging enabled for modular worker")
    except Exception as e:
        logger.error(f"Failed to enable database logging: {e}")

    # Create and start modular async worker
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
        logger.error(f"Application error: {e}")
    finally:
        logger.info("Application exiting")
