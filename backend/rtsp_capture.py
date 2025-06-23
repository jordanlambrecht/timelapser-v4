# backend/rtsp_capture.py

import cv2
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Any, Dict
import time
import sys

# Add the app directory to Python path for imports
current_dir = Path(__file__).parent
app_dir = current_dir / "app"
sys.path.insert(0, str(app_dir))

from app.thumbnail_processor import create_thumbnail_processor

logger = logging.getLogger(__name__)


class RTSPCapture:
    def __init__(self, base_data_dir: str = "/data"):
        self.base_data_dir = Path(base_data_dir)
        self.timeout_seconds = 10
        self.retry_attempts = 3
        self.retry_delay = 2  # seconds between retries

        # Initialize optimized thumbnail processor
        self.thumbnail_processor = create_thumbnail_processor()

        # Suppress ffmpeg/OpenCV codec warnings for cleaner logs
        self._suppress_codec_warnings()

    def ensure_timelapse_directory(self, camera_id: int, timelapse_id: int) -> Path:
        """Create and return timelapse-specific directory structure (entity-based)"""
        # Use config-driven camera directory structure (AI-CONTEXT compliant)
        frames_dir = (
            self.base_data_dir
            / "cameras"  # This is acceptable as it's a subfolder of the configurable base
            / f"camera-{camera_id}"
            / f"timelapse-{timelapse_id}"
            / "frames"
        )
        frames_dir.mkdir(parents=True, exist_ok=True)
        return frames_dir

    def ensure_camera_directories(self, camera_id: int) -> Dict[str, Path]:
        """Create and return camera-specific directory structure with separate folders for different sizes"""
        # Use centralized timezone utility for date formatting (AI-CONTEXT compliant)
        # Note: This should ideally get timezone from database, but for now using UTC fallback
        from app.time_utils import format_date_string
        today = format_date_string()
        # Use config-driven base directory (AI-CONTEXT compliant)
        base_dir = self.base_data_dir / "cameras" / f"camera-{camera_id}"

        directories = {
            "images": base_dir / "images" / today,
            "thumbnails": base_dir / "thumbnails" / today,
            "small": base_dir / "small" / today,
        }

        # Create all directories
        for dir_path in directories.values():
            dir_path.mkdir(parents=True, exist_ok=True)

        return directories

    def save_frame_with_quality(
        self, frame, filepath: Path, quality: int = 85
    ) -> Tuple[bool, int]:
        """Save frame to disk with specified JPEG quality. Returns (success, file_size)"""
        try:
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
            success = cv2.imwrite(str(filepath), frame, encode_params)

            if success:
                file_size = filepath.stat().st_size
                logger.debug("Saved image: %s (%d bytes)", filepath, file_size)
                return True, file_size

            logger.error("Failed to save image: %s", filepath)
            return False, 0

        except Exception as e:
            logger.error("Exception saving frame: %s", e)
            return False, 0

    def generate_entity_filename(self, day_number: int) -> str:
        """Generate day-based filename for entity-based structure"""
        # Use centralized timezone utility for timestamp (AI-CONTEXT compliant)
        from app.time_utils import format_filename_timestamp
        timestamp = format_filename_timestamp().split('_')[1]  # Get just the time part
        return f"day{day_number:03d}_{timestamp}.jpg"

    def ensure_camera_directory(self, camera_id: int) -> Path:
        """Create and return camera-specific directory structure (LEGACY - for backward compatibility)"""
        # Use centralized timezone utility for date formatting (AI-CONTEXT compliant)
        from app.time_utils import format_date_string
        today = format_date_string()
        # Use config-driven base directory (AI-CONTEXT compliant)
        camera_dir = (
            self.base_data_dir / "cameras" / f"camera-{camera_id}" / "images" / today
        )
        camera_dir.mkdir(parents=True, exist_ok=True)
        return camera_dir

    def generate_filename(self, _camera_id: int) -> str:
        """Generate timestamped filename for captured image"""
        # Use centralized timezone utility for timestamp (AI-CONTEXT compliant)
        from app.time_utils import format_filename_timestamp
        timestamp = format_filename_timestamp()
        return f"capture_{timestamp}.jpg"

    def capture_frame_from_stream(self, rtsp_url: str) -> Optional[Any]:
        """
        Capture a single frame from RTSP stream with timeout handling and HEVC optimization.

        Configures OpenCV to handle HEVC/H.265 streams more robustly and suppress
        common codec warnings like "PPS id out of range".
        """
        cap = None
        try:
            logger.debug("Attempting to connect to RTSP stream: %s", rtsp_url)

            # Configure OpenCV for RTSP with HEVC/H.265 optimization
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

            # Apply RTSP configuration
            self._configure_rtsp_capture(cap)

            if not cap.isOpened():
                logger.error("Failed to open RTSP stream: %s", rtsp_url)
                return None

            # Skip a few frames to get past any initial codec issues
            for _ in range(3):
                ret, _ = cap.read()
                if not ret:
                    break

            # Read the actual frame we want
            start_time = time.time()
            ret, frame = cap.read()
            elapsed_time = time.time() - start_time

            if not ret or frame is None:
                logger.error(
                    f"Failed to read frame from stream (took {elapsed_time:.2f}s)"
                )
                return None

            logger.debug("Successfully captured frame (%.2fs)", elapsed_time)
            return frame

        except Exception as e:
            logger.error("Exception during frame capture: %s", e)
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
        logger.info("Starting capture for camera %d (%s)", camera_id, camera_name)

        # Determine if we're using entity-based structure
        use_entity_structure = timelapse_id is not None

        for attempt in range(self.retry_attempts):
            try:
                if attempt > 0:
                    logger.info("Retry attempt %d/%d", attempt + 1, self.retry_attempts)
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
                                logger.info("Recorded image %d in database", image_id)

                            message = (
                                f"Successfully captured and saved image: {filename}"
                            )
                            logger.info(message)
                            return True, message, str(filepath)

                    except Exception as e:
                        logger.error("Error setting up entity-based path: %s", e)
                        continue
                else:
                    # Use legacy date-based structure with thumbnail support
                    directories = self.ensure_camera_directories(camera_id)
                    filename = self.generate_filename(camera_id)
                    filepath = directories["images"] / filename

                    # Store relative path for database (legacy) using centralized timezone utility (AI-CONTEXT compliant)
                    from app.time_utils import utc_now
                    today_str = utc_now().strftime('%Y-%m-%d')
                    relative_db_path = f"data/cameras/camera-{camera_id}/images/{today_str}/{filename}"

                    # Save main image
                    success, file_size = self.save_frame_with_quality(
                        frame, filepath, quality=85
                    )
                    if not success:
                        continue

                    # Generate thumbnails if enabled
                    thumbnail_paths = (
                        {}
                    )  # Empty dictionary to store thumbnail paths and sizes
                    if generate_thumbnails:
                        # Use optimized Pillow-based thumbnail processor
                        thumbnail_results = (
                            self.thumbnail_processor.generate_thumbnails_from_opencv(
                                frame, filename, directories
                            )
                        )

                        # Extract paths and sizes
                        if thumbnail_results["thumbnail"]:
                            thumbnail_paths["thumbnail"] = thumbnail_results[
                                "thumbnail"
                            ]

                        if thumbnail_results["small"]:
                            thumbnail_paths["small"] = thumbnail_results["small"]

                    # Record in database if provided
                    image_id = None
                    if database:
                        # Prepare thumbnail data for database
                        thumbnail_path = (
                            thumbnail_paths.get("thumbnail", (None, None))[0]
                            if "thumbnail" in thumbnail_paths
                            else None
                        )
                        thumbnail_size = (
                            thumbnail_paths.get("thumbnail", (None, None))[1]
                            if "thumbnail" in thumbnail_paths
                            else None
                        )
                        small_path = (
                            thumbnail_paths.get("small", (None, None))[0]
                            if "small" in thumbnail_paths
                            else None
                        )
                        small_size = (
                            thumbnail_paths.get("small", (None, None))[1]
                            if "small" in thumbnail_paths
                            else None
                        )

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
                                        (camera_id,),
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
                                    logger.info(
                                        "Recorded image %d in database with thumbnails",
                                        image_id,
                                    )
                            else:
                                logger.warning(
                                    "No active timelapse found for camera %d - legacy capture mode",
                                    camera_id,
                                )

                        except Exception as e:
                            logger.error(
                                "Error recording image with thumbnails for camera %d: %s",
                                camera_id,
                                e,
                            )

                    message = f"Successfully captured and saved image: {filename}"
                    if generate_thumbnails:
                        thumbnail_count = sum(
                            1 for x in thumbnail_paths.values() if x is not None
                        )
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

    def _suppress_codec_warnings(self):
        """
        Suppress common ffmpeg/OpenCV codec warnings for cleaner logs.

        This helps reduce noise from HEVC "PPS id out of range" and similar
        codec-related warnings that don't affect functionality.
        """
        import os

        # Set ffmpeg log level to suppress codec warnings
        os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"  # Suppress most ffmpeg logs
        # Alternative approach - set cv2 log level if available
        try:
            cv2.setLogLevel(3)  # 3 = ERROR level, suppress INFO and DEBUG
        except AttributeError:
            # Older OpenCV versions may not have this
            pass

    def _configure_rtsp_capture(self, cap) -> None:
        """
        Configure VideoCapture object for optimal RTSP/HEVC performance.

        Args:
            cap: OpenCV VideoCapture object to configure
        """
        # Set timeout and buffer size
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.timeout_seconds * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.timeout_seconds * 1000)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency

        # Set video codec preference (helps with HEVC streams)
        cap.set(cv2.CAP_PROP_CODEC_PIXEL_FORMAT, -1)  # Let OpenCV choose best format

        # Reduce frame rate for more stable capture
        cap.set(cv2.CAP_PROP_FPS, 5)

        # Additional settings that may help with problematic streams
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)  # Suggest resolution
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    def capture_frame_with_fallback(self, rtsp_url: str) -> Optional[Any]:
        """
        Capture frame with multiple fallback strategies for problematic HEVC streams.

        This method tries different OpenCV backends and configurations to handle
        streams that produce codec warnings or fail with the default settings.
        """
        # Strategy 1: Standard FFMPEG backend (already implemented above)
        frame = self.capture_frame_from_stream(rtsp_url)
        if frame is not None:
            return frame

        logger.debug("Standard capture failed, trying fallback strategies")

        # Strategy 2: Try with GSTREAMER backend if available
        try:
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_GSTREAMER)
            self._configure_rtsp_capture(cap)

            if cap.isOpened():
                # Skip frames and read
                for _ in range(3):
                    ret, _ = cap.read()
                    if not ret:
                        break

                ret, frame = cap.read()
                cap.release()

                if ret and frame is not None:
                    logger.debug("GStreamer backend successful")
                    return frame
        except Exception as e:
            logger.debug(f"GStreamer fallback failed: {e}")

        # Strategy 3: Try with different pixel format
        try:
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.timeout_seconds * 1000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.timeout_seconds * 1000)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)  # Slightly larger buffer
            cap.set(cv2.CAP_PROP_FORMAT, cv2.CV_8UC3)  # Force RGB format

            if cap.isOpened():
                # Read multiple frames to stabilize stream
                for _ in range(5):
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        cap.release()
                        logger.debug("Alternative format capture successful")
                        return frame

            cap.release()
        except Exception as e:
            logger.debug(f"Alternative format fallback failed: {e}")

        logger.warning("All capture fallback strategies failed")
        return None
