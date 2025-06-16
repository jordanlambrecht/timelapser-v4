# backend/rtsp_capture.py

import cv2
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Any
import time

logger = logging.getLogger(__name__)


class RTSPCapture:
    def __init__(self, base_data_dir: str = "/data"):
        self.base_data_dir = Path(base_data_dir)
        self.timeout_seconds = 10
        self.retry_attempts = 3
        self.retry_delay = 2  # seconds between retries

    def ensure_camera_directory(self, camera_id: int) -> Path:
        """Create and return camera-specific directory structure"""
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
        """Save frame to disk with JPEG compression"""
        try:
            # Use moderate compression (quality 85/100)
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]
            success = cv2.imwrite(str(filepath), frame, encode_params)

            if success:
                # Log file size
                file_size = filepath.stat().st_size
                logger.debug(f"Saved image: {filepath} ({file_size} bytes)")
                return True
            else:
                logger.error(f"Failed to save image: {filepath}")
                return False

        except Exception as e:
            logger.error(f"Exception saving frame: {e}")
            return False

    def capture_image(
        self,
        camera_id: int,
        camera_name: str,
        rtsp_url: str,
        database=None,
        timelapse_id: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Capture image from camera with retry logic and database tracking
        Returns (success: bool, message: str, filepath: Optional[str])
        """
        logger.info(f"Starting capture for camera {camera_id} ({camera_name})")

        for attempt in range(self.retry_attempts):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt + 1}/{self.retry_attempts}")
                    time.sleep(self.retry_delay)

                # Capture frame
                frame = self.capture_frame_from_stream(rtsp_url)
                if frame is None:
                    continue

                # Prepare file path
                camera_dir = self.ensure_camera_directory(camera_id)
                filename = self.generate_filename(camera_id)
                filepath = camera_dir / filename

                # Save frame
                if self.save_frame(frame, filepath):
                    # Get file size for database
                    file_size = filepath.stat().st_size

                    # Update camera's last image path for UI display
                    # Database update is handled by record_captured_image method
                    logger.debug(
                        f"Image captured and will be recorded in database for camera {camera_id}"
                    )

                    # Record in database if provided and timelapse is active
                    if database and timelapse_id:
                        # Store relative path from project root
                        relative_db_path = f"data/cameras/camera-{camera_id}/images/{datetime.now().strftime('%Y-%m-%d')}/{filename}"
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
                else:
                    message = f"Failed to save captured frame"
                    logger.error(message)
                    continue

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
