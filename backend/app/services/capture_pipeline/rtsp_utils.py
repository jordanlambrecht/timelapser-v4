# backend/app/services/capture_pipeline/rtsp_utils.py
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
from ...services.logger import get_service_logger
from ...enums import LoggerName

logger = get_service_logger(LoggerName.CAPTURE_PIPELINE)

from ...constants import (
    DEFAULT_MAX_RETRIES,
    RETRY_BACKOFF_BASE,
    DEFAULT_IMAGE_EXTENSION,
    DEFAULT_RTSP_QUALITY,
    DEFAULT_RTSP_TIMEOUT_SECONDS,
)
from ...exceptions import RTSPConnectionError, RTSPCaptureError
from .constants import (
    DEFAULT_RTSP_TIMEOUT_SECONDS as PIPELINE_TIMEOUT,
    DEFAULT_CAPTURE_RETRIES,
)


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


def configure_rtsp_capture(
    cap: cv2.VideoCapture, timeout_seconds: int = DEFAULT_RTSP_TIMEOUT_SECONDS
) -> None:
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
    timeout_seconds: int = DEFAULT_RTSP_TIMEOUT_SECONDS,
    skip_frames: int = 3,
) -> Optional[Any]:
    """
    Capture a single frame from RTSP stream with timeout handling.

    Supports both regular RTSP and RTSPS (RTSP over SSL/TLS) connections.

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

        # Check if this is an RTSPS (secure) connection
        is_rtsps = rtsp_url.lower().startswith("rtsps://")
        if is_rtsps:
            logger.debug("Configuring capture for RTSPS (secure RTSP) connection")
            # Set FFmpeg options for SSL/TLS RTSP connections
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                "rtsp_transport;tcp|rw_timeout;10000000|stimeout;10000000"
            )

        # Configure OpenCV for RTSP with HEVC/H.265 optimization
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

        # Apply RTSP configuration
        configure_rtsp_capture(cap, timeout_seconds)

        # Additional configuration for RTSPS streams
        if is_rtsps:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffering for SSL streams

        if not cap.isOpened():
            # If RTSPS failed, try fallback approaches
            if is_rtsps:
                logger.debug("Primary RTSPS capture failed, attempting fallbacks...")
                cap.release()
                return _capture_frame_rtsps_fallback(
                    rtsp_url, timeout_seconds, skip_frames
                )
            else:
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
            # For RTSPS, try fallback if frame capture fails
            if is_rtsps:
                logger.debug("RTSPS frame capture failed, trying fallback...")
                cap.release()
                return _capture_frame_rtsps_fallback(
                    rtsp_url, timeout_seconds, skip_frames
                )
            else:
                raise RTSPCaptureError(
                    f"Failed to read frame from stream (took {elapsed_time:.2f}s)"
                )

        logger.debug(f"Successfully captured frame ({elapsed_time:.2f}s)")
        return frame

    except (RTSPConnectionError, RTSPCaptureError):
        raise
    except Exception as e:
        # For RTSPS, try fallback on exception
        if cap is not None:
            cap.release()
        if rtsp_url.lower().startswith("rtsps://"):
            logger.debug(f"RTSPS capture exception, trying fallback: {e}")
            try:
                return _capture_frame_rtsps_fallback(
                    rtsp_url, timeout_seconds, skip_frames
                )
            except:
                pass
        raise RTSPCaptureError(f"Exception during frame capture: {e}")
    finally:
        if cap is not None:
            cap.release()


def _capture_frame_rtsps_fallback(
    rtsp_url: str, timeout_seconds: int, skip_frames: int
) -> Optional[Any]:
    """
    Fallback frame capture for RTSPS connections.

    Args:
        rtsp_url: RTSPS URL to capture from
        timeout_seconds: Timeout for capture operations
        skip_frames: Number of frames to skip

    Returns:
        OpenCV frame if successful, None if failed
    """
    try:
        # Approach 1: Try with TCP transport parameter
        if "?" in rtsp_url:
            tcp_url = rtsp_url + "&rtsp_transport=tcp"
        else:
            tcp_url = rtsp_url + "?rtsp_transport=tcp"

        logger.debug(f"Trying RTSPS capture with TCP transport: {tcp_url}")
        cap = cv2.VideoCapture(tcp_url, cv2.CAP_FFMPEG)
        configure_rtsp_capture(cap, timeout_seconds)

        if cap.isOpened():
            # Skip frames
            for _ in range(skip_frames):
                ret, _ = cap.read()
                if not ret:
                    break

            ret, frame = cap.read()
            cap.release()

            if ret and frame is not None:
                logger.info("RTSPS TCP fallback capture successful")
                return frame
        else:
            cap.release()

        # Approach 2: Try converting to regular RTSP without SRTP parameter
        regular_rtsp_url = rtsp_url.replace("rtsps://", "rtsp://")
        # Remove enableSrtp parameter as it may not be compatible with regular RTSP
        if "enableSrtp" in regular_rtsp_url:
            regular_rtsp_url = regular_rtsp_url.split("?")[0]
        logger.info(f"🔍 RTSP Capture Fallback Debug - Original URL: {rtsp_url}")
        logger.info(
            f"🔍 RTSP Capture Fallback Debug - Modified URL: {regular_rtsp_url}"
        )
        logger.debug(f"Trying regular RTSP fallback capture: {regular_rtsp_url}")

        cap = cv2.VideoCapture(regular_rtsp_url, cv2.CAP_FFMPEG)
        configure_rtsp_capture(cap, timeout_seconds)

        if cap.isOpened():
            # Skip frames
            for _ in range(skip_frames):
                ret, _ = cap.read()
                if not ret:
                    break

            ret, frame = cap.read()
            cap.release()

            if ret and frame is not None:
                logger.warning(
                    "Regular RTSP fallback capture successful (insecure connection)"
                )
                return frame
        else:
            cap.release()

        logger.error("All RTSPS capture fallback approaches failed")
        return None

    except Exception as e:
        logger.error("RTSPS capture fallback failed", exception=e)
        return None


def test_rtsp_connection(
    rtsp_url: str, timeout_seconds: int = DEFAULT_RTSP_TIMEOUT_SECONDS
) -> Tuple[bool, str]:
    """
    Test RTSP connection without capturing frames.

    Supports both regular RTSP and RTSPS (RTSP over SSL/TLS) connections.

    Args:
        rtsp_url: RTSP stream URL to test
        timeout_seconds: Connection timeout

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        logger.info(f"🔗 Testing RTSP connection to: {rtsp_url}")

        # Check if this is an RTSPS (secure) connection
        is_rtsps = rtsp_url.lower().startswith("rtsps://")
        if is_rtsps:
            logger.info("🔒 Detected RTSPS (secure RTSP) connection")
        else:
            logger.info("🔓 Detected regular RTSP connection")

        # Configure environment for SSL/TLS support
        if is_rtsps:
            # Set FFmpeg options for SSL/TLS RTSP connections with relaxed SSL verification
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                "rtsp_transport;tcp|rw_timeout;10000000|stimeout;10000000|tls_verify;0"
            )

        # Try primary approach with FFmpeg backend
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_seconds * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_seconds * 1000)

        # For RTSPS streams, set additional properties
        if is_rtsps:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffering for SSL streams

        if not cap.isOpened():
            cap.release()

            # If RTSPS failed, try fallback approaches
            if is_rtsps:
                logger.debug("RTSPS connection failed, trying fallback approaches...")
                return _test_rtsps_fallback(rtsp_url, timeout_seconds)
            else:
                logger.error(f"Failed to open RTSP stream: {rtsp_url}")
                return False, "Failed to open RTSP stream"

        # Get basic stream properties to verify it's working
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

        cap.release()

        if width > 0 and height > 0:
            logger.info(f"RTSP connection successful: {int(width)}x{int(height)}")
            return True, f"Connection successful - Stream: {int(width)}x{int(height)}"
        else:
            logger.warning("Stream opened but properties unavailable")
            return False, "Stream opened but properties unavailable"

    except Exception as e:
        logger.error("RTSP connection test exception", exception=e)
        return False, f"Connection test failed: {str(e)}"


def _test_rtsps_fallback(rtsp_url: str, timeout_seconds: int) -> Tuple[bool, str]:
    """
    Fallback testing for RTSPS connections with alternative approaches.

    Args:
        rtsp_url: RTSPS URL to test
        timeout_seconds: Connection timeout

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Approach 1: Try with modified RTSPS URL (force TCP transport)
        if "?" in rtsp_url:
            tcp_url = rtsp_url + "&rtsp_transport=tcp"
        else:
            tcp_url = rtsp_url + "?rtsp_transport=tcp"

        logger.debug(f"Trying RTSPS with TCP transport: {tcp_url}")
        cap = cv2.VideoCapture(tcp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_seconds * 1000)

        if cap.isOpened():
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            cap.release()

            if width > 0 and height > 0:
                logger.info(
                    f"RTSPS TCP fallback successful: {int(width)}x{int(height)}"
                )
                return (
                    True,
                    f"RTSPS TCP connection successful - Stream: {int(width)}x{int(height)}",
                )
        else:
            cap.release()

        # Approach 2: Try converting to regular RTSP without SRTP parameter
        regular_rtsp_url = rtsp_url.replace("rtsps://", "rtsp://")
        # Remove enableSrtp parameter as it may not be compatible with regular RTSP
        if "enableSrtp" in regular_rtsp_url:
            regular_rtsp_url = regular_rtsp_url.split("?")[0]
        logger.info(f"🔍 RTSP Fallback Debug - Original URL: {rtsp_url}")
        logger.info(f"🔍 RTSP Fallback Debug - Modified URL: {regular_rtsp_url}")
        logger.debug(f"Trying regular RTSP fallback (no SRTP): {regular_rtsp_url}")

        cap = cv2.VideoCapture(regular_rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_seconds * 1000)

        if cap.isOpened():
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            cap.release()

            if width > 0 and height > 0:
                logger.warning(
                    f"Regular RTSP fallback worked (insecure): {int(width)}x{int(height)}"
                )
                return (
                    True,
                    f"Fallback RTSP connection successful - Stream: {int(width)}x{int(height)} (using insecure connection)",
                )
        else:
            cap.release()

        return False, "All RTSPS fallback approaches failed"

    except Exception as e:
        logger.error("RTSPS fallback failed", exception=e)
        return False, f"RTSPS fallback failed: {str(e)}"


def capture_frame_with_fallback(
    rtsp_url: str, timeout_seconds: int = DEFAULT_RTSP_TIMEOUT_SECONDS
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


def apply_rotation(frame: Any, rotation: int) -> Any:
    """
    Apply rotation to an OpenCV frame.

    Args:
        frame: OpenCV frame to rotate
        rotation: Rotation angle in degrees (0, 90, 180, 270)

    Returns:
        Rotated frame
    """
    if rotation == 0:
        return frame
    elif rotation == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    elif rotation == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    elif rotation == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    else:
        logger.warning(f"Invalid rotation angle {rotation}, returning original frame")
        return frame


def apply_crop(frame: Any, crop_settings: dict) -> Any:
    """
    Apply crop to an OpenCV frame.

    Args:
        frame: OpenCV frame to crop
        crop_settings: Dict with keys 'x', 'y', 'width', 'height'

    Returns:
        Cropped frame
    """
    try:
        x = crop_settings.get("x", 0)  # Default to 0 if missing
        y = crop_settings.get("y", 0)  # Default to 0 if missing
        width = crop_settings["width"]  # Required field
        height = crop_settings["height"]  # Required field

        if width is None or height is None:
            logger.warning("Missing width or height in crop settings")
            return frame

        # Validate crop bounds
        frame_height, frame_width = frame.shape[:2]

        # Clamp crop coordinates and dimensions to frame bounds
        x = max(0, min(x, frame_width - 1))
        y = max(0, min(y, frame_height - 1))
        width = max(1, min(width, frame_width - x))
        height = max(1, min(height, frame_height - y))

        # Apply crop
        cropped = frame[y : y + height, x : x + width]
        logger.debug(
            f"Applied crop: ({x},{y}) {width}x{height} from {frame_width}x{frame_height}"
        )

        return cropped

    except Exception as e:
        logger.error(f"Error applying crop: {e}")
        return frame


def apply_aspect_ratio(frame: Any, aspect_settings: dict) -> Any:
    """
    Apply aspect ratio adjustment to an OpenCV frame.

    Args:
        frame: OpenCV frame to adjust
        aspect_settings: Dict with keys 'enabled', 'ratio', 'mode'

    Returns:
        Frame with applied aspect ratio
    """
    try:
        if not aspect_settings.get("enabled", False):  # Optional with default
            return frame

        ratio_str = aspect_settings["ratio"]  # Required field
        mode = aspect_settings.get("mode", "crop")  # Optional with default

        if not ratio_str or ":" not in ratio_str:
            logger.warning("Invalid aspect ratio format")
            return frame

        # Parse aspect ratio
        width_ratio, height_ratio = map(float, ratio_str.split(":"))
        target_ratio = width_ratio / height_ratio

        frame_height, frame_width = frame.shape[:2]
        current_ratio = frame_width / frame_height

        if abs(current_ratio - target_ratio) < 0.01:  # Already close enough
            return frame

        if mode == "crop":
            # Crop to target aspect ratio (from center)
            if current_ratio > target_ratio:
                # Frame is too wide, crop horizontally
                new_width = int(frame_height * target_ratio)
                x_offset = (frame_width - new_width) // 2
                cropped = frame[:, x_offset : x_offset + new_width]
            else:
                # Frame is too tall, crop vertically
                new_height = int(frame_width / target_ratio)
                y_offset = (frame_height - new_height) // 2
                cropped = frame[y_offset : y_offset + new_height, :]

            logger.debug(f"Applied aspect ratio crop: {ratio_str} ({target_ratio:.2f})")
            return cropped

        elif mode == "letterbox":
            # Add padding to achieve target aspect ratio
            if current_ratio > target_ratio:
                # Frame is too wide, add vertical padding
                target_height = int(frame_width / target_ratio)
                padding = (target_height - frame_height) // 2
                padded = cv2.copyMakeBorder(
                    frame, padding, padding, 0, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0)
                )
            else:
                # Frame is too tall, add horizontal padding
                target_width = int(frame_height * target_ratio)
                padding = (target_width - frame_width) // 2
                padded = cv2.copyMakeBorder(
                    frame, 0, 0, padding, padding, cv2.BORDER_CONSTANT, value=(0, 0, 0)
                )

            logger.debug(
                f"Applied aspect ratio letterbox: {ratio_str} ({target_ratio:.2f})"
            )
            return padded

        else:
            logger.warning(f"Unknown aspect ratio mode: {mode}")
            return frame

    except Exception as e:
        logger.error(f"Error applying aspect ratio: {e}")
        return frame


def apply_processing_pipeline(frame: Any, settings: dict) -> Any:
    """
    Apply complete crop/rotation/aspect ratio processing pipeline to a frame.

    Args:
        frame: OpenCV frame to process
        settings: Dictionary containing processing settings

    Returns:
        Processed frame
    """
    try:
        if not settings:
            return frame

        # Get processing order (default: crop -> rotate -> aspect_ratio)
        processing_order = settings.get(
            "processing_order", ["crop", "rotate", "aspect_ratio"]
        )  # Optional with default

        processed_frame = frame

        for operation in processing_order:
            if operation == "crop" and "crop" in settings:
                processed_frame = apply_crop(processed_frame, settings["crop"])

            elif operation == "rotate":
                rotation = settings.get("rotation", 0)  # Optional with default
                if rotation != 0:
                    processed_frame = apply_rotation(processed_frame, rotation)

            elif operation == "aspect_ratio" and "aspect_ratio" in settings:
                processed_frame = apply_aspect_ratio(
                    processed_frame, settings["aspect_ratio"]
                )

        logger.debug(f"Completed processing pipeline: {processing_order}")
        return processed_frame

    except Exception as e:
        logger.error(f"Error in processing pipeline: {e}")
        return frame


def get_frame_resolution(frame: Any) -> Tuple[int, int]:
    """
    Get the resolution (width, height) of an OpenCV frame.

    Args:
        frame: OpenCV frame

    Returns:
        Tuple of (width, height)
    """
    try:
        height, width = frame.shape[:2]
        return width, height
    except Exception as e:
        logger.error(f"Error getting frame resolution: {e}")
        return 0, 0


def save_frame_to_file(
    frame: Any,
    filepath: Path,
    quality: int = DEFAULT_RTSP_QUALITY,
    rotation: int = 0,
    processing_settings: Optional[dict] = None,
) -> Tuple[bool, int]:
    """
    Save OpenCV frame to disk with specified JPEG quality and processing.

    Args:
        frame: OpenCV frame to save
        filepath: Path where to save the file
        quality: JPEG quality (1-100)
        rotation: Rotation angle in degrees (0, 90, 180, 270) - legacy parameter
        processing_settings: Complete crop/rotation/aspect ratio settings dict

    Returns:
        Tuple of (success: bool, file_size: int)
    """
    try:
        processed_frame = frame

        # Apply new processing pipeline if settings provided
        if processing_settings:
            processed_frame = apply_processing_pipeline(frame, processing_settings)
            logger.debug("Applied complete processing pipeline to frame")
        elif rotation != 0:
            # Fallback to legacy rotation parameter
            processed_frame = apply_rotation(frame, rotation)
            logger.debug(f"Applied legacy {rotation}° rotation to frame")

        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        success = cv2.imwrite(str(filepath), processed_frame, encode_params)

        if success:
            file_size = filepath.stat().st_size
            logger.debug(f"Saved processed image: {filepath} ({file_size} bytes)")
            return True, file_size

        logger.error(f"Failed to save image: {filepath}")
        return False, 0

    except Exception as e:
        logger.error(f"Exception saving frame: {e}")
        return False, 0


def capture_with_retry(
    rtsp_url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout_seconds: int = DEFAULT_RTSP_TIMEOUT_SECONDS,
    use_fallback: bool = True,
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
                delay = RETRY_BACKOFF_BASE**attempt
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

# def detect_source_resolution(
#     rtsp_url: str,
#     max_retries: int = DEFAULT_MAX_RETRIES,
#     timeout_seconds: int = DEFAULT_RTSP_TIMEOUT_SECONDS,
#     use_fallback: bool = True,
# ) -> Tuple[int, int]:
#     """
#     Detect the source resolution (width, height) of an RTSP stream.

#     Args:
#         rtsp_url: RTSP stream URL
#         max_retries: Maximum number of retry attempts
#         timeout_seconds: Timeout for each attempt
#         use_fallback: Whether to use fallback strategies

#     Returns:
#         Tuple of (width, height). Returns (0, 0) if detection fails.
#     """
#     frame = capture_with_retry(
#         rtsp_url,
#         max_retries=max_retries,
#         timeout_seconds=timeout_seconds,
#         use_fallback=use_fallback,
#     )
#     if frame is not None:
#         return get_frame_resolution(frame)
#     else:
#         logger.error(
#             f"❌ Failed to detect source resolution for RTSP stream: {rtsp_url}"
#         )
#         return 0, 0
