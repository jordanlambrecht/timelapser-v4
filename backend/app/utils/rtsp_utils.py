# backend/app/utils/rtsp_utils.py
"""
RTSP Capture Utilities

Pure RTSP stream capture functions using OpenCV.
Handles RTSP connections, frame capture, and connection testing.
"""

import cv2
import os
import time
from pathlib import Path
from typing import Optional, Tuple, Any
from loguru import logger

from ..constants import (
    DEFAULT_MAX_RETRIES,
    RETRY_BACKOFF_BASE,
    DEFAULT_IMAGE_EXTENSION,
)
from ..exceptions import RTSPConnectionError, RTSPCaptureError


def configure_opencv_logging() -> None:
    """
    Configure OpenCV and FFmpeg logging to suppress codec warnings.
    Reduces noise from HEVC "PPS id out of range" and similar codec warnings.
    """
    os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"  # Suppress most ffmpeg logs
    
    try:
        cv2.setLogLevel(3)  # ERROR level, suppress INFO and DEBUG
    except AttributeError:
        # Older OpenCV versions may not have this
        pass


def configure_rtsp_capture(cap: cv2.VideoCapture, timeout_seconds: int = 10) -> None:
    """
    Configure VideoCapture object for optimal RTSP/HEVC performance.
    
    Args:
        cap: OpenCV VideoCapture object to configure
        timeout_seconds: Timeout for capture operations
    """
    # Set timeout and buffer size
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_seconds * 1000)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_seconds * 1000)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency

    # Set video codec preference (helps with HEVC streams)
    cap.set(cv2.CAP_PROP_CODEC_PIXEL_FORMAT, -1)  # Let OpenCV choose best format

    # Reduce frame rate for more stable capture
    cap.set(cv2.CAP_PROP_FPS, 5)

    # Additional settings for problematic streams
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)  # Suggest resolution
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)


def capture_frame_from_rtsp(
    rtsp_url: str, 
    timeout_seconds: int = 10,
    skip_frames: int = 3
) -> Optional[Any]:
    """
    Capture a single frame from RTSP stream with timeout handling.
    
    Args:
        rtsp_url: RTSP stream URL
        timeout_seconds: Timeout for capture operations
        skip_frames: Number of frames to skip before capturing
        
    Returns:
        OpenCV frame if successful, None if failed
        
    Raises:
        RTSPConnectionError: If cannot connect to stream
        RTSPCaptureError: If cannot capture frame
    """
    cap = None
    try:
        logger.debug(f"Connecting to RTSP stream: {rtsp_url}")
        
        # Configure OpenCV for RTSP with HEVC/H.265 optimization
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        
        # Apply RTSP configuration
        configure_rtsp_capture(cap, timeout_seconds)

        if not cap.isOpened():
            raise RTSPConnectionError(f"Failed to open RTSP stream: {rtsp_url}")

        # Skip frames to get past initial codec issues
        for _ in range(skip_frames):
            ret, _ = cap.read()
            if not ret:
                break

        # Capture the actual frame
        start_time = time.time()
        ret, frame = cap.read()
        elapsed_time = time.time() - start_time

        if not ret or frame is None:
            raise RTSPCaptureError(
                f"Failed to read frame from stream (took {elapsed_time:.2f}s)"
            )

        logger.debug(f"Successfully captured frame ({elapsed_time:.2f}s)")
        return frame

    except (RTSPConnectionError, RTSPCaptureError):
        raise
    except Exception as e:
        raise RTSPCaptureError(f"Exception during frame capture: {e}")
    finally:
        if cap is not None:
            cap.release()


def test_rtsp_connection(rtsp_url: str, timeout_seconds: int = 5) -> Tuple[bool, str]:
    """
    Test RTSP connection without capturing frames.
    
    Args:
        rtsp_url: RTSP stream URL to test
        timeout_seconds: Connection timeout
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_seconds * 1000)

        if not cap.isOpened():
            cap.release()
            return False, "Failed to open RTSP stream"

        # Get basic stream properties to verify it's working
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

        cap.release()

        if width > 0 and height > 0:
            return True, f"Connection successful - Stream: {int(width)}x{int(height)}"
        else:
            return False, "Stream opened but properties unavailable"

    except Exception as e:
        return False, f"Connection test failed: {str(e)}"


def capture_frame_with_fallback(
    rtsp_url: str, 
    timeout_seconds: int = 10
) -> Optional[Any]:
    """
    Capture frame with multiple fallback strategies for problematic streams.
    
    Args:
        rtsp_url: RTSP stream URL
        timeout_seconds: Timeout for capture operations
        
    Returns:
        OpenCV frame if any strategy succeeds, None if all fail
    """
    # Strategy 1: Standard FFMPEG backend
    try:
        frame = capture_frame_from_rtsp(rtsp_url, timeout_seconds)
        if frame is not None:
            return frame
    except (RTSPConnectionError, RTSPCaptureError) as e:
        logger.debug(f"Standard capture failed: {e}")

    logger.debug("Standard capture failed, trying fallback strategies")

    # Strategy 2: Try with GSTREAMER backend if available
    try:
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_GSTREAMER)
        configure_rtsp_capture(cap, timeout_seconds)

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
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_seconds * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_seconds * 1000)
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


def save_frame_to_file(
    frame: Any, 
    filepath: Path, 
    quality: int = 85
) -> Tuple[bool, int]:
    """
    Save OpenCV frame to disk with specified JPEG quality.
    
    Args:
        frame: OpenCV frame to save
        filepath: Path where to save the file
        quality: JPEG quality (1-100)
        
    Returns:
        Tuple of (success: bool, file_size: int)
    """
    try:
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        success = cv2.imwrite(str(filepath), frame, encode_params)

        if success:
            file_size = filepath.stat().st_size
            logger.debug(f"Saved image: {filepath} ({file_size} bytes)")
            return True, file_size

        logger.error(f"Failed to save image: {filepath}")
        return False, 0

    except Exception as e:
        logger.error(f"Exception saving frame: {e}")
        return False, 0


def capture_with_retry(
    rtsp_url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout_seconds: int = 10,
    use_fallback: bool = True
) -> Optional[Any]:
    """
    Capture frame with retry logic and exponential backoff.
    
    Args:
        rtsp_url: RTSP stream URL
        max_retries: Maximum number of retry attempts
        timeout_seconds: Timeout for each attempt
        use_fallback: Whether to use fallback strategies
        
    Returns:
        OpenCV frame if successful, None if all attempts failed
    """
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                delay = RETRY_BACKOFF_BASE ** attempt
                logger.info(f"Retry attempt {attempt + 1}/{max_retries} after {delay}s")
                time.sleep(delay)

            if use_fallback and attempt == max_retries - 1:
                # Use fallback on last attempt
                frame = capture_frame_with_fallback(rtsp_url, timeout_seconds)
            else:
                frame = capture_frame_from_rtsp(rtsp_url, timeout_seconds)

            if frame is not None:
                return frame

        except (RTSPConnectionError, RTSPCaptureError) as e:
            logger.warning(f"Capture attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"All {max_retries} capture attempts failed")
                return None

    return None


# Initialize OpenCV logging suppression when module is imported
configure_opencv_logging()
