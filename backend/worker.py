#!/usr/bin/env python3
"""
Timelapser Async Worker with FastAPI Integration

This module implements an asynchronous timelapse worker that handles:

Core Functionality:
- Scheduled image capture from multiple RTSP cameras concurrently
- Camera health monitoring and connectivity testing
- Database integration with both sync and async database connections
- Graceful shutdown handling with proper signal management
- Time window support for camera capture scheduling
- Weather integration for sunrise/sunset capture windows
- Weather data collection and caching

Architecture:
- Uses AsyncIOScheduler for job scheduling
- Integrates with RTSPCapture for image acquisition
- Supports concurrent camera operations with asyncio
- Maintains camera health status and connectivity monitoring
- Database operations run in thread executor for sync compatibility
- Weather data refreshed daily for location-based timing

The worker runs continuously and performs:
1. Image capture from all active cameras at configured intervals
2. Health checks for camera connectivity (every minute)
3. Database updates for timelapse progress tracking
4. Event broadcasting for real-time UI updates
5. Weather data refreshing for sunrise/sunset calculations

Designed to work seamlessly with the FastAPI backend while maintaining
independent operation for reliable timelapse generation.
"""

import os
import signal
import asyncio
from pathlib import Path
from datetime import datetime, time, date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

# Import from the same backend directory
from app.database import async_db, sync_db
from app.time_utils import get_timezone_aware_timestamp_sync, get_timezone_aware_time_sync, utc_now, get_timezone_aware_date_sync, parse_time_string
from app.config import settings
from rtsp_capture import RTSPCapture
from video_generator import VideoGenerator
from worker_corruption_integration import initialize_worker_corruption_detection
from weather.service import WeatherManager, OpenWeatherService
from video_automation_service import VideoAutomationService


class AsyncTimelapseWorker:
    """
    Asynchronous timelapse worker for concurrent camera management.

    This class orchestrates the entire timelapse capture process with support for:
    - Multiple concurrent RTSP camera streams
    - Scheduled image capture with configurable intervals
    - Camera health monitoring and connectivity testing
    - Time window restrictions for capture scheduling
    - Database integration for timelapse tracking
    - Graceful shutdown with signal handling
    - Real-time event broadcasting for UI updates

    The worker runs as a continuous background service using AsyncIOScheduler
    for job management and asyncio for concurrent operations. It maintains
    both sync and async database connections to support legacy components
    while providing modern async performance.

    Attributes:
        capture (RTSPCapture): RTSP capture handler for image acquisition
        video_generator (VideoGenerator): Video generation service
        scheduler (AsyncIOScheduler): Job scheduler for periodic tasks
        running (bool): Worker running state flag
        current_interval (int): Current capture interval in seconds
        max_workers (int): Maximum concurrent capture operations
    """

    def __init__(self):
        """
        Initialize the async timelapse worker.

        Sets up all necessary components including:
        - RTSP capture system with data directory configuration
        - Video generator with sync database connection
        - AsyncIO scheduler for periodic jobs
        - Signal handlers for graceful shutdown
        - Database initialization for worker operations

        The worker is configured from settings but remains flexible for
        runtime configuration changes.
        """
        # Initialize components
        # Use config-driven data directory (AI-CONTEXT compliant)
        self.capture = RTSPCapture(base_data_dir=settings.data_directory)
        self.video_generator = VideoGenerator(sync_db)

        self.scheduler = AsyncIOScheduler()
        self.running = False
        self.current_interval = settings.capture_interval
        self.max_workers = settings.max_concurrent_captures

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Initialize sync database for worker FIRST
        sync_db.initialize()
        logger.info("Sync database initialized for worker")

        # Initialize corruption detection integration AFTER database is ready
        self.corruption_integration = initialize_worker_corruption_detection(sync_db)
        logger.info("✅ Corruption detection initialized successfully")

        # Initialize weather manager for sunrise/sunset and weather data
        self.weather_manager = WeatherManager(sync_db)
        logger.info("Weather manager initialized")

        # Initialize video automation service
        self.video_automation = VideoAutomationService(sync_db)
        logger.info("Video automation service initialized")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        # Don't shut down scheduler here - let the main loop handle it

    async def _async_shutdown(self):
        """Async shutdown cleanup"""
        try:
            logger.info("Starting async shutdown...")
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            # Close sync database connections
            sync_db.close()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error during async shutdown: {e}")
        # Don't call sys.exit(0) here - let the main loop handle the exit

    def _is_within_time_window(self, camera) -> bool:
        """Check if current time is within camera's capture window (regular or sun-based)"""
        try:
            # Check if camera uses custom time window (overrides global settings)
            if camera.get("use_custom_time_window", False):
                start_time = camera.get("custom_time_window_start")
                end_time = camera.get("custom_time_window_end")

                if start_time and end_time:
                    return self._check_time_range(start_time, end_time)

            # Check camera's regular time window
            if camera.get("use_time_window", False):
                start_time = camera.get("time_window_start")
                end_time = camera.get("time_window_end")

                if start_time and end_time:
                    return self._check_time_range(start_time, end_time)

            # Check if sunrise/sunset mode is enabled and weather data is available
            settings_dict = sync_db.get_settings_dict()
            if settings_dict.get("sunrise_sunset_enabled", "false").lower() == "true":
                return self._check_sun_based_window(settings_dict)

            # No time restrictions - capture allowed
            return True

        except Exception as e:
            logger.warning(
                f"Error checking time window for camera {camera.get('id')}: {e}"
            )
            return True  # Default to allowing capture if check fails

    def _check_time_range(self, start_time_str: str, end_time_str: str) -> bool:
        """Check if current time is within the specified time range"""
        try:
            # Convert string times to time objects if needed
            if isinstance(start_time_str, str):
                start_time = parse_time_string(start_time_str)
            else:
                start_time = start_time_str

            if isinstance(end_time_str, str):
                end_time = parse_time_string(end_time_str)
            else:
                end_time = end_time_str

            # Get current time in the configured timezone
            try:
                from app.time_utils import get_timezone_aware_time_sync
                current_time = get_timezone_aware_time_sync(sync_db)
            except Exception:
                # Fallback to centralized timezone utility (AI-CONTEXT compliant)
                from app.time_utils import utc_now
                current_time = utc_now().time()

            # Handle overnight windows (e.g., 22:00 - 06:00)
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                return current_time >= start_time or current_time <= end_time

        except Exception as e:
            logger.warning(
                f"Error parsing time range {start_time_str} - {end_time_str}: {e}"
            )
            return True

    def _check_sun_based_window(self, settings_dict: dict) -> bool:
        """Check if current time is within sunrise/sunset window"""
        try:
            # Check if we have required weather data
            sunrise_timestamp = settings_dict.get("sunrise_timestamp")
            sunset_timestamp = settings_dict.get("sunset_timestamp")

            if not sunrise_timestamp or not sunset_timestamp:
                logger.debug("No sunrise/sunset data available")
                return True  # Allow capture if no data

            # Get offsets
            sunrise_offset_minutes = int(settings_dict.get("sunrise_offset_minutes", 0))
            sunset_offset_minutes = int(settings_dict.get("sunset_offset_minutes", 0))

            # Use weather service to check if within window
            service = OpenWeatherService(
                api_key="dummy",  # Not needed for time calculations
                latitude=0,
                longitude=0,
            )

            # Get timezone for sun window calculation
            timezone_str = settings_dict.get("timezone", "UTC")

            return service.is_within_sun_window(
                sunrise_timestamp=int(sunrise_timestamp),
                sunset_timestamp=int(sunset_timestamp),
                sunrise_offset_minutes=sunrise_offset_minutes,
                sunset_offset_minutes=sunset_offset_minutes,
                timezone_str=timezone_str,
            )

        except Exception as e:
            logger.warning(f"Error checking sun-based window: {e}")
            return True  # Default to allowing capture if check fails

    async def capture_from_camera(self, camera_info):
        """
        Capture image from a single camera with comprehensive error handling.

        This method handles the complete image capture workflow for a single camera:
        1. Validates time window restrictions
        2. Retrieves active timelapse configuration
        3. Checks thumbnail generation setting
        4. Executes RTSP capture via thread executor (sync compatibility)
        5. Updates camera health status
        6. Calculates next capture timing
        7. Broadcasts capture events for real-time UI updates

        Args:
            camera_info (dict): Camera configuration containing:
                - id: Camera database ID
                - name: Human-readable camera name
                - rtsp_url: RTSP stream URL
                - time_window settings (if applicable)

        The method runs sync database operations in a thread executor to
        maintain async compatibility while supporting legacy sync components.

        Raises:
            Exception: Logs but doesn't re-raise exceptions to prevent
                      individual camera failures from stopping other captures
        """
        camera_id = camera_info["id"]
        camera_name = camera_info["name"]
        rtsp_url = camera_info["rtsp_url"]

        try:
            # Check time window
            if not self._is_within_time_window(camera_info):
                logger.debug(f"Camera {camera_name} outside time window, skipping")
                return

            # Get active timelapse for this camera
            loop = asyncio.get_event_loop()
            timelapse = await loop.run_in_executor(
                None, sync_db.get_active_timelapse_for_camera, camera_id
            )
            if not timelapse:
                logger.debug(f"No active timelapse for camera {camera_name}")
                return

            # Check thumbnail generation setting
            def get_thumbnail_setting():
                try:
                    with sync_db.get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT value FROM settings WHERE key = 'generate_thumbnails'"
                            )
                            result = cur.fetchone()
                            if result:
                                # result is a tuple, so access by index
                                return result[0].lower() == "true"
                            return True  # Default to enabled if setting not found
                except Exception as e:
                    logger.warning(f"Failed to get thumbnail setting: {e}")
                    return True  # Default to enabled on error

            generate_thumbnails = await loop.run_in_executor(
                None, get_thumbnail_setting
            )

            logger.info(
                f"Starting capture for camera {camera_id} ({camera_name}) [thumbnails: {'enabled' if generate_thumbnails else 'disabled'}]"
            )

            # Capture image with corruption detection and retry logic
            def capture_func():
                return self.capture.capture_image(
                    camera_id,
                    camera_name,
                    rtsp_url,
                    sync_db,  # RTSPCapture still uses sync_db
                    timelapse["id"],
                    generate_thumbnails,  # Pass thumbnail setting
                )

            # Use corruption-aware capture with retry logic
            success, message, saved_file_path, corruption_details = (
                await loop.run_in_executor(
                    None,
                    self.corruption_integration.evaluate_with_retry,
                    camera_id,
                    rtsp_url,
                    capture_func,
                    timelapse["id"],
                )
            )

            # Log corruption detection results
            if corruption_details and not corruption_details.get("detection_disabled"):
                corruption_score = corruption_details.get("score", "N/A")
                action_taken = corruption_details.get("action_taken", "unknown")
                logger.info(
                    f"Camera {camera_id} corruption check: score={corruption_score}, action={action_taken}"
                )

            if success:
                await loop.run_in_executor(
                    None, sync_db.update_camera_health, camera_id, "online", True
                )

                # Calculate and update next capture time
                capture_interval = await loop.run_in_executor(
                    None, sync_db.get_capture_interval_setting
                )
                await loop.run_in_executor(
                    None,
                    sync_db.calculate_and_update_next_capture,
                    camera_id,
                    capture_interval,
                )

                # Get updated timelapse info for accurate image count
                updated_timelapse = await loop.run_in_executor(
                    None, sync_db.get_active_timelapse_for_camera, camera_id
                )
                if updated_timelapse:
                    logger.info(
                        f"Image captured, count: {updated_timelapse.get('image_count', 0)}"
                    )

                # Trigger per-capture video automation if enabled
                try:
                    automation_triggered = await loop.run_in_executor(
                        None,
                        self.video_automation.trigger_per_capture_generation,
                        camera_id,
                    )
                    if automation_triggered:
                        logger.info(
                            f"Triggered per-capture video generation for camera {camera_id}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to trigger per-capture automation for camera {camera_id}: {e}"
                    )

                # Broadcast image captured event with corruption details
                event_data = {
                    "type": "image_captured",
                    "data": {
                        "camera_id": camera_id,
                        "image_count": (
                            updated_timelapse.get("image_count", 0)
                            if updated_timelapse
                            else 0
                        ),
                    },
                    "timestamp": get_timezone_aware_timestamp_sync(sync_db),
                }

                # Add corruption details if available
                if corruption_details and not corruption_details.get(
                    "detection_disabled"
                ):
                    event_data["data"]["corruption_score"] = corruption_details.get(
                        "score"
                    )
                    event_data["data"]["corruption_action"] = corruption_details.get(
                        "action_taken"
                    )

                await loop.run_in_executor(
                    None,
                    sync_db.broadcast_event,
                    event_data,
                )

                logger.info(f"Successfully captured and saved image: {message}")
            else:
                await loop.run_in_executor(
                    None, sync_db.update_camera_health, camera_id, "offline", False
                )
                logger.error(f"Failed to capture from camera {camera_name}: {message}")

        except Exception as e:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, sync_db.update_camera_health, camera_id, "offline", False
            )
            logger.error(f"Unexpected error capturing from camera {camera_name}: {e}")

    async def capture_all_running_cameras(self):
        """Capture images from all running cameras concurrently"""
        try:
            # Run sync database query in executor
            loop = asyncio.get_event_loop()
            cameras = await loop.run_in_executor(None, sync_db.get_running_timelapses)

            if not cameras:
                logger.debug("No running cameras found")
                return

            logger.info(f"Capturing from {len(cameras)} running cameras")

            # Use asyncio.gather for concurrent async captures
            tasks = [self.capture_from_camera(camera) for camera in cameras]
            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Error in capture_all_running_cameras: {e}")

    async def check_camera_health(self):
        """
        Check and update camera health status based on RTSP connectivity.

        This method performs comprehensive health monitoring for all active cameras:
        1. Retrieves all active cameras from database (not just running timelapses)
        2. Tests RTSP connectivity without full image capture
        3. Updates database connectivity status for each camera
        4. Logs connectivity issues for monitoring and debugging

        The health check runs independently of image capture to provide
        accurate connectivity status even when timelapses are not active.
        This enables proper camera status reporting in the UI.

        Connection tests are performed in thread executor to maintain
        async compatibility with the sync RTSP testing methods.

        Frequency: Typically scheduled to run every minute
        """
        try:
            # Get all active cameras (not just running timelapses)
            loop = asyncio.get_event_loop()
            cameras = await loop.run_in_executor(None, sync_db.get_active_cameras)

            if not cameras:
                logger.debug("No active cameras found for health check")
                return

            logger.info(f"Checking health for {len(cameras)} cameras")

            # Test connectivity for each camera
            for camera in cameras:
                camera_id = camera["id"]
                camera_name = camera["name"]
                rtsp_url = camera["rtsp_url"]

                try:
                    # Test RTSP connectivity (not full capture) - run in executor since it's sync
                    success, message = await loop.run_in_executor(
                        None, self.capture.test_rtsp_connection, rtsp_url
                    )

                    if success:
                        # Camera is reachable
                        await loop.run_in_executor(
                            None, sync_db.update_camera_connectivity, camera_id, True
                        )
                        logger.debug(f"Camera {camera_name} is online: {message}")
                    else:
                        # Camera is unreachable
                        await loop.run_in_executor(
                            None, sync_db.update_camera_connectivity, camera_id, False
                        )
                        logger.warning(f"Camera {camera_name} is offline: {message}")

                except Exception as e:
                    # Connection test failed
                    await loop.run_in_executor(
                        None, sync_db.update_camera_connectivity, camera_id, False
                    )
                    logger.error(f"Health check failed for camera {camera_name}: {e}")

        except Exception as e:
            logger.error(f"Error in check_camera_health: {e}")

    async def process_video_automation(self):
        """Process video automation triggers and jobs"""
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, self.video_automation.process_automation_triggers
            )

            # Log activity if any
            if any(results.values()):
                logger.info(f"Video automation activity: {results}")

        except Exception as e:
            logger.error(f"Error processing video automation: {e}")

    async def refresh_weather_data(self):
        """Refresh weather data if needed and weather is enabled"""
        try:
            # Check if weather functionality is enabled
            settings_dict = await asyncio.get_event_loop().run_in_executor(
                None, sync_db.get_settings_dict
            )

            weather_enabled = (
                settings_dict.get("weather_enabled", "false").lower() == "true"
            )
            if not weather_enabled:
                logger.debug("Weather functionality disabled, skipping refresh")
                return

            # Check if we have required settings
            latitude = settings_dict.get("latitude")
            longitude = settings_dict.get("longitude")
            api_key = settings_dict.get("openweather_api_key")

            if not all([latitude, longitude, api_key]):
                logger.warning(
                    "Weather refresh skipped: Missing required settings (lat/lng/api_key)"
                )
                return

            # Type narrowing - at this point we know api_key is not None
            assert api_key is not None, "api_key should not be None after validation"

            # Check if weather data is stale (not from today)
            # Use timezone-aware date for proper comparison
            from app.time_utils import get_timezone_aware_date_sync
            today = get_timezone_aware_date_sync(sync_db)
            weather_date_fetched = settings_dict.get("weather_date_fetched", "")

            if weather_date_fetched == today:
                logger.debug("Weather data is current, skipping refresh")
                return

            logger.info("Refreshing weather data...")

            # Call the async weather refresh method directly with plain text API key
            weather_data = await self.weather_manager.refresh_weather_if_needed(api_key)

            if weather_data:
                logger.info(
                    f"Weather data refreshed: {weather_data.temperature}°C, {weather_data.description}"
                )

                # Broadcast weather update event
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    sync_db.broadcast_event,
                    {
                        "type": "weather_updated",
                        "data": {
                            "temperature": weather_data.temperature,
                            "icon": weather_data.icon,
                            "description": weather_data.description,
                            "date_fetched": weather_data.date_fetched.isoformat(),
                        },
                        "timestamp": get_timezone_aware_timestamp_sync(sync_db),
                    },
                )
            else:
                logger.warning("Failed to refresh weather data")

        except Exception as e:
            logger.error(f"Error refreshing weather data: {e}")

    async def update_scheduler_interval(self):
        """Update scheduler interval if settings changed"""
        try:
            # In a full implementation, this would check for setting changes
            # For now, keep the current interval
            pass
        except Exception as e:
            logger.error(f"Error updating scheduler interval: {e}")

    async def start(self):
        """
        Start the async worker with comprehensive scheduled job management.

        This method initializes and starts the complete worker system with
        multiple scheduled jobs:

        Jobs Configured:
        1. Image Capture Job - Captures from all running cameras at configured interval
        2. Health Monitoring Job - Tests camera connectivity every minute
        3. Weather Data Refresh Job - Updates weather data daily at 6 AM and on startup
        4. Interval Update Job - Checks for configuration changes every 5 minutes

        The worker runs continuously until interrupted by signal or error.
        All jobs are configured with max_instances=1 to prevent overlapping
        executions that could cause resource conflicts.

        Weather functionality includes:
        - Daily refresh of weather data for sunrise/sunset calculations
        - Automatic sunrise/sunset time window support for cameras
        - Weather condition logging for capture context

        Job scheduling uses AsyncIOScheduler for true async operation while
        database operations are executed in thread pools for sync compatibility.

        Raises:
            KeyboardInterrupt: Handled gracefully for user-initiated shutdown
            Exception: Logged and triggers graceful shutdown process
        """
        logger.info("Starting Async Timelapse Worker")

        # Schedule image capture job
        self.scheduler.add_job(
            func=self.capture_all_running_cameras,
            trigger="interval",
            seconds=self.current_interval,
            id="capture_job",
            name="Capture Images from Running Cameras",
            max_instances=1,
        )

        # Schedule health monitoring job (connectivity test)
        self.scheduler.add_job(
            func=self.check_camera_health,
            trigger="interval",
            seconds=60,  # Check connectivity every minute
            id="health_job",
            name="Monitor Camera Connectivity",
            max_instances=1,
        )

        # Schedule weather data refresh job (daily at 6 AM)
        self.scheduler.add_job(
            func=self.refresh_weather_data,
            trigger="cron",
            hour=6,
            minute=0,
            id="weather_job",
            name="Refresh Weather Data",
            max_instances=1,
        )

        # Also run weather refresh on startup
        # Use centralized timezone utility (AI-CONTEXT compliant)
        from app.time_utils import utc_now
        startup_time = utc_now()
        self.scheduler.add_job(
            func=self.refresh_weather_data,
            trigger="date",
            run_date=startup_time,
            id="weather_startup_job",
            name="Initial Weather Data Refresh",
            max_instances=1,
        )

        # Schedule video automation processing
        self.scheduler.add_job(
            func=self.process_video_automation,
            trigger="interval",
            seconds=120,  # Check every 2 minutes
            id="video_automation_job",
            name="Process Video Automation",
            max_instances=1,
        )

        # Schedule interval update check
        self.scheduler.add_job(
            func=self.update_scheduler_interval,
            trigger="interval",
            seconds=300,  # Check every 5 minutes
            id="interval_job",
            name="Update Scheduler Interval",
            max_instances=1,
        )

        self.running = True
        logger.info("Async worker started successfully")

        try:
            self.scheduler.start()
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
    Main async entry point for the timelapse worker application.

    This function handles the complete worker lifecycle:
    1. Ensures data directory structure exists
    2. Configures rotating log files with size and retention limits
    3. Creates and initializes the AsyncTimelapseWorker
    4. Manages graceful shutdown on interruption or error

    The worker runs indefinitely until terminated by signal or exception.
    All exceptions are caught and logged to ensure clean shutdown.

    Logging Configuration:
    - 10MB file rotation to prevent disk space issues
    - 30-day retention for debugging and monitoring
    - Configurable log level from settings
    """
    # Ensure data directory exists
    os.makedirs(settings.data_directory, exist_ok=True)

    # Setup logging
    log_path = os.path.join(settings.data_directory, "worker.log")
    logger.add(
        log_path,
        rotation="10 MB",
        retention="30 days",
        level=settings.log_level,
    )

    # Create and start async worker
    worker = AsyncTimelapseWorker()
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Main: Worker interrupted by user")
    except Exception as e:
        logger.error(f"Main: Worker error: {e}")
    finally:
        logger.info("Main: Worker finished")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        logger.info("Application exiting")
