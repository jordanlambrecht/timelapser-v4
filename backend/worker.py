#!/usr/bin/env python3
"""
Updated Timelapser Worker with FastAPI Integration
Uses connection pooling and modern database patterns
"""

import os
import sys
import signal
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time
from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger

# Import from the same backend directory
from app.database import sync_db
from app.config import settings
from rtsp_capture import RTSPCapture
from video_generator import VideoGenerator


class ModernTimelapseWorker:
    """Modern timelapse worker with connection pooling and FastAPI integration"""

    def __init__(self):
        # Initialize components
        self.capture = RTSPCapture(base_data_dir="./data")
        self.video_generator = VideoGenerator(sync_db)
        self.scheduler = BlockingScheduler()
        self.running = False
        self.current_interval = settings.capture_interval
        self.max_workers = settings.max_concurrent_captures

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Initialize database connection pool
        sync_db.initialize()
        logger.info("Worker initialized with connection pooling")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        self.scheduler.shutdown(wait=False)
        sync_db.close()
        sys.exit(0)

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

    def capture_from_camera(self, camera_info):
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
            timelapse = sync_db.get_active_timelapse_for_camera(camera_id)
            if not timelapse:
                logger.debug(f"No active timelapse for camera {camera_name}")
                return

            logger.info(f"Starting capture for camera {camera_id} ({camera_name})")

            # Capture image - RTSPCapture handles directory creation and database recording
            success, message, saved_file_path = self.capture.capture_image(
                camera_id=camera_id,
                camera_name=camera_name,
                rtsp_url=rtsp_url,
                database=sync_db,
                timelapse_id=timelapse["id"],
            )

            if success:
                sync_db.update_camera_health(camera_id, True)
                logger.info(f"Successfully captured and saved image: {message}")
            else:
                sync_db.update_camera_health(camera_id, False)
                logger.error(f"Failed to capture from camera {camera_name}: {message}")

        except Exception as e:
            sync_db.update_camera_health(camera_id, False)
            logger.error(f"Unexpected error capturing from camera {camera_name}: {e}")

    def capture_all_running_cameras(self):
        """Capture images from all running cameras concurrently"""
        try:
            cameras = sync_db.get_running_timelapses()

            if not cameras:
                logger.debug("No running cameras found")
                return

            logger.info(f"Capturing from {len(cameras)} running cameras")

            # Use ThreadPoolExecutor for concurrent captures
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_camera = {
                    executor.submit(self.capture_from_camera, camera): camera
                    for camera in cameras
                }

                for future in as_completed(future_to_camera):
                    camera = future_to_camera[future]
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(
                            f"Error in capture thread for camera {camera['name']}: {e}"
                        )

        except Exception as e:
            logger.error(f"Error in capture_all_running_cameras: {e}")

    def check_camera_health(self):
        """Check and update camera health status based on RTSP connectivity"""
        try:
            # Get all active cameras (not just running timelapses)
            cameras = sync_db.get_active_cameras()

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
                    # Test RTSP connectivity (not full capture)
                    success, message = self.capture.test_rtsp_connection(rtsp_url)

                    if success:
                        # Camera is reachable
                        sync_db.update_camera_connectivity(camera_id, True)
                        logger.debug(f"Camera {camera_name} is online: {message}")
                    else:
                        # Camera is unreachable
                        sync_db.update_camera_connectivity(camera_id, False)
                        logger.warning(f"Camera {camera_name} is offline: {message}")

                except Exception as e:
                    # Connection test failed
                    sync_db.update_camera_connectivity(camera_id, False)
                    logger.error(f"Health check failed for camera {camera_name}: {e}")

        except Exception as e:
            logger.error(f"Error in check_camera_health: {e}")

    def check_for_video_generation_requests(self):
        """Check for pending video generation requests"""
        try:
            # This would need to be implemented in the database layer
            # For now, skip video generation in worker
            pass
        except Exception as e:
            logger.error(f"Error checking video generation requests: {e}")

    def update_scheduler_interval(self):
        """Update scheduler interval if settings changed"""
        try:
            # In a full implementation, this would check for setting changes
            # For now, keep the current interval
            pass
        except Exception as e:
            logger.error(f"Error updating scheduler interval: {e}")

    def start(self):
        """Start the worker with scheduled jobs"""
        logger.info("Starting Timelapse Worker")

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
        logger.info("Worker started successfully")

        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
        except Exception as e:
            logger.error(f"Worker error: {e}")
        finally:
            sync_db.close()


if __name__ == "__main__":
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

    # Create and start worker
    worker = ModernTimelapseWorker()
    worker.start()
