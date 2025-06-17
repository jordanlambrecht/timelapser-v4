# backend/rtsp_capture.py

import cv2
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Any, Dict
import time
import sys
import os
from pathlib import Path

# Add the app directory to Python path for imports
current_dir = Path(__file__).parent
app_dir = current_dir / "app"
sys.path.insert(0, str(app_dir))

from thumbnail_processor import create_thumbnail_processor

logger = logging.getLogger(__name__)


class RTSPCapture:
    def __init__(self, base_data_dir: str = "/data"):
        self.base_data_dir = Path(base_data_dir)
        self.timeout_seconds = 10
        self.retry_attempts = 3
        self.retry_delay = 2  # seconds between retries
        
        # Initialize optimized thumbnail processor
        self.thumbnail_processor = create_thumbnail_processor()

    def ensure_timelapse_directory(self, camera_id: int, timelapse_id: int) -> Path:
        """Create and return timelapse-specific directory structure (entity-based)"""
        frames_dir = (
            self.base_data_dir
            / "cameras"
            / f"camera-{camera_id}"
            / f"timelapse-{timelapse_id}"
            / "frames"
        )
        frames_dir.mkdir(parents=True, exist_ok=True)
        return frames_dir

    def ensure_camera_directories(self, camera_id: int) -> Dict[str, Path]:
        """Create and return camera-specific directory structure with separate folders for different sizes"""
        today = datetime.now().strftime("%Y-%m-%d")
        base_dir = self.base_data_dir / "cameras" / f"camera-{camera_id}"
        
        directories = {
            'images': base_dir / "images" / today,
            'thumbnails': base_dir / "thumbnails" / today,
            'small': base_dir / "small" / today
        }
        
        # Create all directories
        for dir_path in directories.values():
            dir_path.mkdir(parents=True, exist_ok=True)
            
        return directories

    def save_frame_with_quality(self, frame, filepath: Path, quality: int = 85) -> Tuple[bool, int]:
        """Save frame to disk with specified JPEG quality. Returns (success, file_size)"""
        try:
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
            success = cv2.imwrite(str(filepath), frame, encode_params)

            if success:
                file_size = filepath.stat().st_size
                logger.debug(f"Saved image: {filepath} ({file_size} bytes)")
                return True, file_size
            else:
                logger.error(f"Failed to save image: {filepath}")
                return False, 0

        except Exception as e:
            logger.error(f"Exception saving frame: {e}")
            return False, 0

    def generate_entity_filename(self, day_number: int) -> str:
        """Generate day-based filename for entity-based structure"""
        timestamp = datetime.now().strftime("%H%M%S")
        return f"day{day_number:03d}_{timestamp}.jpg"

    def ensure_camera_directory(self, camera_id: int) -> Path:
        """Create and return camera-specific directory structure (LEGACY - for backward compatibility)"""
        today = datetime.now().strftime("%Y-%m-%d")
        camera_dir = (
            self.base_data_dir / "cameras" / f"camera-{camera_id}" / "images" / today
        )
        camera_dir.mkdir(parents=True, exist_ok=True)
        return camera_dir

    def generate_filename(self, camera_id: int) -> str:
        """Generate timestamped filename for captured image"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"capture_{timestamp}.jpg"

    def capture_frame_from_stream(self, rtsp_url: str) -> Optional[Any]:
        """Capture a single frame from RTSP stream with timeout handling"""
        cap = None
        try:
            logger.debug(f"Attempting to connect to RTSP stream: {rtsp_url}")

            # Configure OpenCV for RTSP
            cap = cv2.VideoCapture(rtsp_url)

            # Set timeout and buffer size
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.timeout_seconds * 1000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.timeout_seconds * 1000)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency

            if not cap.isOpened():
                logger.error(f"Failed to open RTSP stream: {rtsp_url}")
                return None

            # Read frame with timeout
            start_time = time.time()
            ret, frame = cap.read()
            elapsed_time = time.time() - start_time

            if not ret or frame is None:
                logger.error(
                    f"Failed to read frame from stream (took {elapsed_time:.2f}s)"
                )
                return None

            logger.debug(f"Successfully captured frame ({elapsed_time:.2f}s)")
            return frame

        except Exception as e:
            logger.error(f"Exception during frame capture: {e}")
            return None
        finally:
            if cap is not None:
                cap.release()

    def save_frame(self, frame, filepath: Path) -> bool:
        """Save frame to disk with JPEG compression (legacy method for compatibility)"""
        success, _ = self.save_frame_with_quality(frame, filepath, quality=85)
        return success

    def capture_image(
        self,
        camera_id: int,
        camera_name: str,
        rtsp_url: str,
        database=None,
        timelapse_id: Optional[int] = None,
        generate_thumbnails: bool = True,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Capture image from camera with retry logic and database tracking
        Uses entity-based file structure when timelapse_id is provided
        Generates thumbnails when enabled
        Returns (success: bool, message: str, filepath: Optional[str])
        """
        logger.info(f"Starting capture for camera {camera_id} ({camera_name})")

        # Determine if we're using entity-based structure
        use_entity_structure = timelapse_id is not None

        for attempt in range(self.retry_attempts):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt + 1}/{self.retry_attempts}")
                    time.sleep(self.retry_delay)

                # Capture frame
                frame = self.capture_frame_from_stream(rtsp_url)
                if frame is None:
                    continue

                # Prepare file path based on structure type
                if use_entity_structure and database:
                    # Get timelapse info to calculate day number
                    try:
                        # Get timelapse start date from database
                        query_result = database.get_connection()
                        with query_result as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    "SELECT start_date FROM timelapses WHERE id = %s",
                                    (timelapse_id,),
                                )
                                timelapse_row = cur.fetchone()

                        if not timelapse_row or not timelapse_row.get("start_date"):
                            logger.error(
                                f"Timelapse {timelapse_id} not found or missing start_date"
                            )
                            continue

                        # Calculate day number (1-based)
                        from datetime import date

                        start_date = timelapse_row["start_date"]
                        current_date = date.today()
                        day_number = (current_date - start_date).days + 1

                        # Use entity-based structure
                        frames_dir = self.ensure_timelapse_directory(
                            camera_id, timelapse_id
                        )
                        filename = self.generate_entity_filename(day_number)
                        filepath = frames_dir / filename

                        # Store relative path for database (entity-based)
                        relative_db_path = f"data/cameras/camera-{camera_id}/timelapse-{timelapse_id}/frames/{filename}"

                        # Entity-based structure doesn't use thumbnails yet - would need separate implementation
                        # For now, just save the main image
                        if self.save_frame(frame, filepath):
                            file_size = filepath.stat().st_size

                            # Record in database
                            image_id = database.record_captured_image(
                                camera_id=camera_id,
                                timelapse_id=timelapse_id,
                                file_path=relative_db_path,
                                file_size=file_size,
                            )

                            if image_id:
                                logger.info(f"Recorded image {image_id} in database")

                            message = f"Successfully captured and saved image: {filename}"
                            logger.info(message)
                            return True, message, str(filepath)

                    except Exception as e:
                        logger.error(f"Error setting up entity-based path: {e}")
                        continue
                else:
                    # Use legacy date-based structure with thumbnail support
                    directories = self.ensure_camera_directories(camera_id)
                    filename = self.generate_filename(camera_id)
                    filepath = directories['images'] / filename

                    # Store relative path for database (legacy)
                    relative_db_path = f"data/cameras/camera-{camera_id}/images/{datetime.now().strftime('%Y-%m-%d')}/{filename}"

                    # Save main image
                    success, file_size = self.save_frame_with_quality(frame, filepath, quality=85)
                    if not success:
                        continue

                    # Generate thumbnails if enabled
                    thumbnail_paths = {'thumbnail': None, 'small': None}
                    if generate_thumbnails:
                        # Use optimized Pillow-based thumbnail processor
                        thumbnail_results = self.thumbnail_processor.generate_thumbnails_from_opencv(
                            frame, filename, directories
                        )
                        
                        # Extract paths and sizes
                        if thumbnail_results['thumbnail']:
                            thumbnail_paths['thumbnail'] = thumbnail_results['thumbnail']
                            
                        if thumbnail_results['small']:
                            thumbnail_paths['small'] = thumbnail_results['small']

                    # Record in database if provided
                    image_id = None
                    if database:
                        # Prepare thumbnail data for database
                        thumbnail_path = thumbnail_paths['thumbnail'][0] if thumbnail_paths['thumbnail'] else None
                        thumbnail_size = thumbnail_paths['thumbnail'][1] if thumbnail_paths['thumbnail'] else None
                        small_path = thumbnail_paths['small'][0] if thumbnail_paths['small'] else None
                        small_size = thumbnail_paths['small'][1] if thumbnail_paths['small'] else None

                        # This is the legacy path - need to find active timelapse for this camera
                        try:
                            with database.get_connection() as conn:
                                with conn.cursor() as cur:
                                    cur.execute(
                                        """
                                        SELECT t.id 
                                        FROM cameras c
                                        INNER JOIN timelapses t ON c.active_timelapse_id = t.id
                                        WHERE c.id = %s AND t.status = 'running'
                                        """,
                                        (camera_id,)
                                    )
                                    active_timelapse_row = cur.fetchone()
                                    
                            if active_timelapse_row:
                                active_timelapse_id = active_timelapse_row["id"]
                                
                                # Call the enhanced database method with thumbnail data
                                image_id = database.record_captured_image(
                                    camera_id=camera_id,
                                    timelapse_id=active_timelapse_id,
                                    file_path=relative_db_path,
                                    file_size=file_size,
                                    thumbnail_path=thumbnail_path,
                                    thumbnail_size=thumbnail_size,
                                    small_path=small_path,
                                    small_size=small_size,
                                )
                                
                                if image_id:
                                    logger.info(f"Recorded image {image_id} in database with thumbnails")
                            else:
                                logger.warning(f"No active timelapse found for camera {camera_id} - legacy capture mode")
                                
                        except Exception as e:
                            logger.error(f"Error recording image with thumbnails for camera {camera_id}: {e}")

                    message = f"Successfully captured and saved image: {filename}"
                    if generate_thumbnails:
                        thumbnail_count = sum(1 for x in thumbnail_paths.values() if x is not None)
                        message += f" (+ {thumbnail_count} thumbnails)"
                    
                    logger.info(message)
                    return True, message, str(filepath)

            except Exception as e:
                message = f"Capture attempt {attempt + 1} failed: {str(e)}"
                logger.error(message)
                if attempt == self.retry_attempts - 1:  # Last attempt
                    return False, message, None
                continue

        final_message = f"All {self.retry_attempts} capture attempts failed"
        logger.error(final_message)
        return False, final_message, None

    def test_rtsp_connection(self, rtsp_url: str) -> Tuple[bool, str]:
        """Test RTSP connection without saving image"""
        try:
            frame = self.capture_frame_from_stream(rtsp_url)
            if frame is not None:
                height, width = frame.shape[:2]
                return True, f"Connection successful - Resolution: {width}x{height}"
            else:
                return False, "Failed to capture test frame"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
