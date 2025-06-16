#!/usr/bin/env python3
"""
Updated Timelapser Worker with FastAPI Integration
Uses asyncio and async database connections
"""

import os
import sys
import signal
import asyncio
from pathlib import Path
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

# Import from the same backend directory
from app.database import async_db, sync_db
from app.config import settings
from rtsp_capture import RTSPCapture
from video_generator import VideoGenerator


class AsyncTimelapseWorker:
    """Async timelapse worker with FastAPI integration"""

    def __init__(self):
        # Initialize components
        # Use absolute path to project root data directory
        project_root = Path(__file__).parent.parent
        data_dir = project_root / "data"
        self.capture = RTSPCapture(base_data_dir=str(data_dir))
        self.video_generator = VideoGenerator(sync_db)
        self.scheduler = AsyncIOScheduler()
        self.running = False
        self.current_interval = settings.capture_interval
        self.max_workers = settings.max_concurrent_captures

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Initialize sync database for worker
        sync_db.initialize()
        logger.info("Async worker initialized with sync database")

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
        """Check if current time is within camera's capture window"""
        if not camera.get("use_time_window", False):
            return True

        start_time = camera.get("time_window_start")
        end_time = camera.get("time_window_end")

        if not start_time or not end_time:
            return True

        try:
            # Convert string times to time objects if needed
            if isinstance(start_time, str):
                start_time = datetime.strptime(start_time, "%H:%M:%S").time()
            if isinstance(end_time, str):
                end_time = datetime.strptime(end_time, "%H:%M:%S").time()

            current_time = datetime.now().time()

            # Handle overnight windows (e.g., 22:00 - 06:00)
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                return current_time >= start_time or current_time <= end_time

        except Exception as e:
            logger.warning(f"Error parsing time window for camera {camera['id']}: {e}")
            return True

    async def capture_from_camera(self, camera_info):
        """Capture image from a single camera with improved error handling"""
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

            logger.info(f"Starting capture for camera {camera_id} ({camera_name})")

            # Capture image - RTSPCapture handles directory creation and database recording
            # Note: RTSPCapture still uses sync database, so we run in executor
            loop = asyncio.get_event_loop()
            success, message, saved_file_path = await loop.run_in_executor(
                None,
                self.capture.capture_image,
                camera_id,
                camera_name,
                rtsp_url,
                sync_db,  # RTSPCapture still uses sync_db
                timelapse["id"],
            )

            if success:
                await loop.run_in_executor(
                    None, sync_db.update_camera_health, camera_id, "online", True
                )

                # Get updated timelapse info for accurate image count
                updated_timelapse = await loop.run_in_executor(
                    None, sync_db.get_active_timelapse_for_camera, camera_id
                )
                if updated_timelapse:
                    logger.info(
                        f"Image captured, count: {updated_timelapse.get('image_count', 0)}"
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
        """Check and update camera health status based on RTSP connectivity"""
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

    async def check_for_video_generation_requests(self):
        """Check for pending video generation requests"""
        try:
            # This would need to be implemented in the database layer
            # For now, skip video generation in worker
            pass
        except Exception as e:
            logger.error(f"Error checking video generation requests: {e}")

    async def update_scheduler_interval(self):
        """Update scheduler interval if settings changed"""
        try:
            # In a full implementation, this would check for setting changes
            # For now, keep the current interval
            pass
        except Exception as e:
            logger.error(f"Error updating scheduler interval: {e}")

    async def start(self):
        """Start the async worker with scheduled jobs"""
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

        # Schedule video generation check (disabled for now)
        # self.scheduler.add_job(
        #     func=self.check_for_video_generation_requests,
        #     trigger="interval",
        #     seconds=60,
        #     id='video_job',
        #     name='Check Video Generation Requests',
        #     max_instances=1
        # )

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
    """Main async function"""
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
