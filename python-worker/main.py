import os
import logging
import signal
import sys
import time
from datetime import datetime, time as datetime_time
from concurrent.futures import ThreadPoolExecutor, as_completed
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
import threading

from database import Database
from capture import RTSPCapture
from video_generator import VideoGenerator

# Configure logging
project_data_dir = "/Users/jordanlambrecht/dev-local/timelapser-v4/data"
os.makedirs(project_data_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"{project_data_dir}/worker.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


class TimelapseWorker:
    def __init__(self):
        self.db = Database()
        # Pass the correct data directory to RTSPCapture
        project_data_dir = "/Users/jordanlambrecht/dev-local/timelapser-v4/data"
        self.capture = RTSPCapture(base_data_dir=project_data_dir)
        self.video_generator = VideoGenerator(self.db)
        self.scheduler = BlockingScheduler()
        self.running = False
        self.current_interval = 300  # Default 5 minutes
        self.max_workers = 4  # Max concurrent camera captures

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        self.scheduler.shutdown(wait=False)
        sys.exit(0)

    def setup_database(self):
        """Initialize database tables if needed"""
        try:
            self.db.create_logs_table_if_not_exists()
            logger.info("Database setup completed")
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            raise

    def is_within_time_window(self, camera) -> bool:
        """Check if current time is within camera's time window"""
        try:
            # If time window is disabled, always capture
            if not camera.get('use_time_window', False):
                return True
            
            # Get current time
            now = datetime.now().time()
            
            # Parse time window from camera settings
            start_time_str = camera.get('time_window_start', '06:00:00')
            end_time_str = camera.get('time_window_end', '18:00:00')
            
            # Convert to time objects
            if isinstance(start_time_str, str):
                start_time = datetime_time.fromisoformat(start_time_str)
            else:
                start_time = start_time_str
                
            if isinstance(end_time_str, str):
                end_time = datetime_time.fromisoformat(end_time_str)
            else:
                end_time = end_time_str
            
            # Handle overnight time windows (e.g., 22:00 to 06:00)
            if start_time <= end_time:
                # Normal time window (e.g., 06:00 to 18:00)
                return start_time <= now <= end_time
            else:
                # Overnight time window (e.g., 22:00 to 06:00)
                return now >= start_time or now <= end_time
                
        except Exception as e:
            logger.warning(f"Failed to check time window for camera {camera.get('id', 'unknown')}: {e}")
            # If there's an error, default to allowing capture
            return True

    def capture_camera_image(self, camera) -> dict:
        """Capture image from a single camera with timelapse tracking"""
        camera_id = camera["id"]
        camera_name = camera["name"]
        rtsp_url = camera["rtsp_url"]

        # Get active timelapse for this camera
        active_timelapse = self.db.get_active_timelapse_for_camera(camera_id)
        
        if not active_timelapse:
            # Create/update timelapse to running status
            timelapse_id = self.db.create_or_update_timelapse(camera_id, 'running')
            if not timelapse_id:
                message = "Failed to create/update timelapse record"
                logger.error(f"Camera {camera_id}: {message}")
                self.db.log_capture_attempt(camera_id, False, message)
                self.db.update_camera_health(camera_id, False)
                return {
                    "camera_id": camera_id,
                    "camera_name": camera_name,
                    "success": False,
                    "message": message,
                    "duration": 0,
                }
        else:
            timelapse_id = active_timelapse['id']

        start_time = time.time()
        success, message, filepath = self.capture.capture_image(
            camera_id, camera_name, rtsp_url, database=self.db, timelapse_id=timelapse_id
        )
        duration = time.time() - start_time

        # Log to database
        self.db.log_capture_attempt(camera_id, success, message)

        # Update camera health
        self.db.update_camera_health(camera_id, success)

        if success:
            self.db.update_camera_last_capture(camera_id)

        return {
            "camera_id": camera_id,
            "camera_name": camera_name,
            "success": success,
            "message": message,
            "duration": duration,
            "filepath": filepath,
            "timelapse_id": timelapse_id
        }

    def run_capture_cycle(self):
        """Run a complete capture cycle for all running timelapses"""
        try:
            logger.info("Starting capture cycle...")

            # Get cameras with running timelapses
            cameras = self.db.get_running_timelapses()

            if not cameras:
                logger.info("No running timelapses found")
                return

            # Filter cameras by time window
            cameras_to_capture = []
            cameras_outside_window = []
            
            for camera in cameras:
                if self.is_within_time_window(camera):
                    cameras_to_capture.append(camera)
                else:
                    cameras_outside_window.append(camera)

            # Log time window filtering
            if cameras_outside_window:
                camera_names = [c['name'] for c in cameras_outside_window]
                logger.info(f"Skipping {len(cameras_outside_window)} cameras outside time window: {', '.join(camera_names)}")

            if not cameras_to_capture:
                logger.info("No cameras within time window for capture")
                return

            logger.info(f"Found {len(cameras_to_capture)} cameras ready for capture (within time window)")

            # Process cameras concurrently
            results = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all capture tasks
                future_to_camera = {
                    executor.submit(self.capture_camera_image, camera): camera
                    for camera in cameras_to_capture
                }

                # Collect results as they complete
                for future in as_completed(future_to_camera):
                    camera = future_to_camera[future]
                    try:
                        result = future.result()
                        results.append(result)

                        status = "✓" if result["success"] else "✗"
                        logger.info(
                            f"{status} Camera {result['camera_id']} ({result['camera_name']}) "
                            f"- {result['duration']:.2f}s - {result['message']}"
                        )

                    except Exception as e:
                        logger.error(
                            f"Camera {camera['id']} capture failed with exception: {e}"
                        )
                        self.db.log_capture_attempt(
                            camera["id"], False, f"Exception: {str(e)}"
                        )

            # Summary
            successful = sum(1 for r in results if r["success"])
            total = len(results)
            skipped = len(cameras_outside_window)
            logger.info(f"Capture cycle completed: {successful}/{total} successful, {skipped} skipped (time window)")

        except Exception as e:
            logger.error(f"Capture cycle failed: {e}")

    def update_schedule_if_needed(self):
        """Check if capture interval has changed and update schedule"""
        try:
            new_interval = self.db.get_capture_interval()
            if new_interval != self.current_interval:
                logger.info(
                    f"Capture interval changed: {self.current_interval}s -> {new_interval}s"
                )
                self.current_interval = new_interval

                # Remove existing job and add new one
                if self.scheduler.get_jobs():
                    self.scheduler.remove_all_jobs()

                self.scheduler.add_job(
                    func=self.run_capture_cycle,
                    trigger=IntervalTrigger(seconds=new_interval),
                    id="capture_cycle",
                    name="Camera Capture Cycle",
                    replace_existing=True,
                )
                logger.info(f"Schedule updated to run every {new_interval} seconds")

        except Exception as e:
            logger.error(f"Failed to update schedule: {e}")

    def check_for_video_generation_requests(self):
        """Check for pending video generation requests and process them"""
        try:
            # Get videos with 'generating' status that might be stuck or need processing
            pending_videos = self.db.get_pending_video_generations()
            
            if not pending_videos:
                logger.debug("No pending video generation requests")
                return
            
            logger.info(f"Found {len(pending_videos)} pending video generation requests")
            
            for video in pending_videos:
                try:
                    self.process_video_generation_request(video)
                except Exception as e:
                    logger.error(f"Failed to process video generation for video {video['id']}: {e}")
                    # Mark video as failed
                    self.db.update_video_record(video['id'], status='failed')
                    
        except Exception as e:
            logger.error(f"Failed to check for video generation requests: {e}")

    def process_video_generation_request(self, video_record):
        """Process a single video generation request"""
        video_id = video_record['id']
        camera_id = video_record['camera_id']
        settings = video_record.get('settings', {})
        
        logger.info(f"Processing video generation request {video_id} for camera {camera_id}")
        
        # Get camera details
        cameras = self.db.get_active_cameras()
        camera = next((c for c in cameras if c['id'] == camera_id), None)
        
        if not camera:
            logger.error(f"Camera {camera_id} not found or not active")
            self.db.update_video_record(video_id, status='failed')
            return
        
        # Build images directory path - use all images for the camera
        base_images_dir = f"/Users/jordanlambrecht/dev-local/timelapser-v4/data/cameras/camera-{camera_id}/images"
        
        # Check if directory exists and has images
        from pathlib import Path
        images_path = Path(base_images_dir)
        if not images_path.exists():
            logger.error(f"Images directory not found: {base_images_dir}")
            self.db.update_video_record(video_id, status='failed')
            return
            
        # Find all image files across all date directories
        image_files = []
        for date_dir in images_path.iterdir():
            if date_dir.is_dir():
                date_images = self.video_generator.find_image_files(date_dir)
                image_files.extend(date_images)
        
        if len(image_files) < 2:
            logger.error(f"Not enough images found for camera {camera_id}: {len(image_files)}")
            self.db.update_video_record(video_id, status='failed')
            return
        
        logger.info(f"Found {len(image_files)} total images for camera {camera_id}")
        
        # Extract settings
        framerate = settings.get('framerate', 30)
        quality = settings.get('quality', 'medium')
        
        # Generate video name if not provided
        video_name = video_record['name']
        if not video_name:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_name = f"{camera['name']}_timelapse_{timestamp}"
            
        # Update video name in record
        self.db.update_video_record(video_id, name=video_name)
        
        # Output directory
        output_directory = "/Users/jordanlambrecht/dev-local/timelapser-v4/data/videos"
        
        # Use the existing video generator but bypass the record creation
        # since we already have a record
        try:
            # Update settings and start generation
            self.db.update_video_record(
                video_id,
                image_count=len(image_files),
                settings=settings
            )
            
            # Build a temporary images directory with all images
            import tempfile
            import shutil
            import os
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Copy all images to temp directory with sequential naming
                for i, image_file in enumerate(sorted(image_files)):
                    src_path = image_file
                    # Keep original extension but use sequential naming
                    ext = os.path.splitext(image_file)[1]
                    dst_path = os.path.join(temp_dir, f"frame_{i:06d}{ext}")
                    shutil.copy2(src_path, dst_path)
                
                # Generate video using temporary directory
                output_path = os.path.join(output_directory, f"{video_name}.mp4")
                
                success, message = self.video_generator.generate_video(
                    images_directory=temp_dir,
                    output_path=output_path,
                    framerate=framerate,
                    quality=quality
                )
                
                if success:
                    # Get file size and duration
                    file_size = Path(output_path).stat().st_size if Path(output_path).exists() else 0
                    duration_seconds = len(image_files) / framerate
                    
                    # Update record with success
                    self.db.update_video_record(
                        video_id,
                        status='completed',
                        file_path=output_path,
                        file_size=file_size,
                        duration_seconds=duration_seconds
                    )
                    
                    logger.info(f"Video generation completed for video {video_id}: {message}")
                else:
                    # Update record with failure
                    self.db.update_video_record(video_id, status='failed')
                    logger.error(f"Video generation failed for video {video_id}: {message}")
                    
        except Exception as e:
            logger.error(f"Video generation exception for video {video_id}: {e}")
            self.db.update_video_record(video_id, status='failed')

    def auto_generate_videos_for_stopped_timelapses(self):
        """Check for recently stopped timelapses and auto-generate videos"""
        try:
            # This could be implemented to automatically create videos when timelapses stop
            # For now, we'll just log that this check happened
            logger.debug("Checked for stopped timelapses needing auto-video generation")
        except Exception as e:
            logger.error(f"Failed to check for auto-video generation: {e}")

    def monitor_camera_health(self):
        """Monitor camera health and log offline cameras"""
        try:
            # Update health status based on recent activity
            self.db.check_camera_health_status()
            
            # Get offline cameras and log warnings
            offline_cameras = self.db.get_offline_cameras()
            
            if offline_cameras:
                for camera in offline_cameras:
                    camera_name = camera['name']
                    last_capture = camera['last_capture_at']
                    failures = camera['consecutive_failures']
                    
                    if last_capture:
                        time_since = datetime.now() - last_capture
                        logger.warning(f"📴 Camera '{camera_name}' offline - Last capture: {time_since} ago, Failures: {failures}")
                    else:
                        logger.warning(f"📴 Camera '{camera_name}' offline - No successful captures, Failures: {failures}")
            else:
                logger.debug("All cameras healthy")
                
        except Exception as e:
            logger.error(f"Failed to monitor camera health: {e}")

    def start(self):
        """Start the timelapse worker"""
        try:
            logger.info("=== Timelapser Worker Starting ===")

            # Setup database
            self.setup_database()

            # Log startup info
            self.current_interval = self.db.get_capture_interval()
            logger.info(f"Initial capture interval: {self.current_interval} seconds")

            # Schedule the capture job
            self.scheduler.add_job(
                func=self.run_capture_cycle,
                trigger=IntervalTrigger(seconds=self.current_interval),
                id="capture_cycle",
                name="Camera Capture Cycle",
            )

            # Schedule interval check (every 30 seconds)
            self.scheduler.add_job(
                func=self.update_schedule_if_needed,
                trigger=IntervalTrigger(seconds=30),
                id="schedule_check",
                name="Schedule Update Check",
            )

            # Schedule video generation check (every 60 seconds)
            self.scheduler.add_job(
                func=self.check_for_video_generation_requests,
                trigger=IntervalTrigger(seconds=60),
                id="video_generation_check",
                name="Video Generation Check",
            )

            # Schedule auto-video generation check (every 5 minutes)
            self.scheduler.add_job(
                func=self.auto_generate_videos_for_stopped_timelapses,
                trigger=IntervalTrigger(seconds=300),
                id="auto_video_check",
                name="Auto Video Generation Check",
            )

            # Schedule camera health monitoring (every 2 minutes)
            self.scheduler.add_job(
                func=self.monitor_camera_health,
                trigger=IntervalTrigger(seconds=120),
                id="health_monitoring",
                name="Camera Health Monitoring",
            )

            self.running = True
            logger.info("Worker started successfully, waiting for scheduled tasks...")

            # Start scheduler (this blocks)
            self.scheduler.start()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Worker startup failed: {e}")
            raise
        finally:
            logger.info("Worker stopped")


def main():
    """Main entry point"""
    try:
        # Load environment variables
        from dotenv import load_dotenv

        load_dotenv("/Users/jordanlambrecht/dev-local/timelapser-v4/.env.local")

        # Create project data directory (already done above, but ensure it exists)
        project_data_dir = "/Users/jordanlambrecht/dev-local/timelapser-v4/data"
        os.makedirs(project_data_dir, exist_ok=True)
        os.makedirs(f"{project_data_dir}/cameras", exist_ok=True)
        os.makedirs(f"{project_data_dir}/videos", exist_ok=True)

        # Start worker
        worker = TimelapseWorker()
        worker.start()

    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
