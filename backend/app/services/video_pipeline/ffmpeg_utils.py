# backend/app/utils/ffmpeg_utils.py
"""
FFmpeg utilities for video generation.

Pure functions for FFmpeg command generation and video rendering operations.
No external dependencies or side effects - suitable for service layer consumption.
"""

import subprocess
import tempfile
import glob
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from ...services.logger import get_service_logger
from ...enums import LoggerName, VideoQuality

from ...config import settings

logger = get_service_logger(LoggerName.VIDEO_PIPELINE)
from ...utils import file_helpers


# Quality settings for different output levels
QUALITY_SETTINGS = {
    VideoQuality.LOW: {"crf": 28, "preset": "fast", "scale": "1280:720"},
    VideoQuality.MEDIUM: {"crf": 23, "preset": "medium", "scale": "1920:1080"},
    VideoQuality.HIGH: {"crf": 18, "preset": "slow", "scale": None},
}

# Supported image formats
SUPPORTED_FORMATS = [".jpg", ".jpeg", ".png"]

# Default overlay settings
DEFAULT_OVERLAY_SETTINGS = {
    "enabled": True,
    "position": "bottom-right",
    "font_size": 48,
    "font_color": "white",
    "background_color": "black@0.5",
    "format": "Day {day}",
}


def test_ffmpeg_available() -> Tuple[bool, str]:
    """
    Test if FFmpeg is available on the system.

    Returns:
        Tuple of (is_available, version_or_error_message)
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            return True, version_line
        else:
            return False, f"FFmpeg returned error code {result.returncode}"
    except FileNotFoundError:
        return False, "FFmpeg not found in system PATH"
    except subprocess.TimeoutExpired:
        return False, "FFmpeg version check timed out"
    except Exception as e:
        return False, f"Error checking FFmpeg: {str(e)}"


def get_quality_settings(quality: VideoQuality) -> Dict[str, Any]:
    """Get FFmpeg quality settings based on quality level."""
    return QUALITY_SETTINGS.get(quality, QUALITY_SETTINGS[VideoQuality.MEDIUM])


# Deprecated ASS subtitle functions - kept for backward compatibility
# def get_overlay_alignment(position: str) -> int:
#     """Get FFmpeg alignment value for overlay position. (DEPRECATED - use overlay images instead)"""
#     alignments = {
#         "bottom-left": 1,
#         "bottom-center": 2,
#         "bottom-right": 3,
#         "center-left": 4,
#         "center": 5,
#         "center-right": 6,
#         "top-left": 7,
#         "top-center": 8,
#         "top-right": 9,
#     }
#     return alignments.get(position, 3)


# def seconds_to_ass_time(seconds: float) -> str:
#     """Convert seconds to ASS time format (H:MM:SS.cc). (DEPRECATED - use overlay images instead)"""
#     hours = int(seconds // 3600)
#     minutes = int((seconds % 3600) // 60)
#     secs = seconds % 60
#     return f"{hours}:{minutes:02d}:{secs:05.2f}"


def find_overlay_images(camera_id: int, base_directory: Path) -> List[str]:
    """
    Find overlay images for a camera, sorted by filename.

    Args:
        camera_id: ID of the camera
        base_directory: Base data directory

    Returns:
        List of sorted overlay image file paths
    """
    overlay_dir = base_directory / f"cameras/camera-{camera_id}/overlays"
    image_files = []

    if not overlay_dir.exists():
        logger.debug(f"Overlay directory does not exist: {overlay_dir}")
        return image_files

    # Check if this has date subdirectories
    has_date_subdirs = any(
        d.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", d.name)
        for d in overlay_dir.iterdir()
        if d.is_dir()
    )

    if has_date_subdirs:
        # Overlay directory with date subdirectories
        for date_dir in overlay_dir.iterdir():
            if date_dir.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", date_dir.name):
                for ext in SUPPORTED_FORMATS:
                    pattern = str(date_dir / f"*{ext}")
                    files = glob.glob(pattern)
                    image_files.extend(files)
    else:
        # Flat overlay directory
        for ext in SUPPORTED_FORMATS:
            pattern = str(overlay_dir / f"*{ext}")
            files = glob.glob(pattern)
            image_files.extend(files)

    # Sort by filename for chronological order
    image_files.sort()
    logger.debug(f"Found {len(image_files)} overlay images for camera {camera_id}")

    return image_files


def find_image_files(images_directory: Path) -> List[str]:
    """
    Find all image files in directory and subdirectories, sorted by filename.

    Args:
        images_directory: Path to search for images

    Returns:
        List of sorted image file paths
    """
    image_files = []

    # Check if this is a camera directory with date subdirectories
    has_date_subdirs = any(
        d.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", d.name)
        for d in images_directory.iterdir()
        if d.is_dir()
    )

    if images_directory.name.startswith("camera-") or has_date_subdirs:
        # Camera directory with date subdirectories
        for date_dir in images_directory.iterdir():
            if date_dir.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", date_dir.name):
                for ext in SUPPORTED_FORMATS:
                    pattern = str(date_dir / f"*{ext}")
                    files = glob.glob(pattern)
                    image_files.extend(files)
    else:
        # Flat directory
        for ext in SUPPORTED_FORMATS:
            pattern = str(images_directory / f"*{ext}")
            files = glob.glob(pattern)
            image_files.extend(files)

    # Sort by filename for chronological order
    image_files.sort()
    logger.debug(f"Found {len(image_files)} image files in {images_directory}")

    return image_files


# def create_ass_subtitle_content(
#     image_list: List[str],
#     total_duration: float,
#     overlay_settings: Dict[str, Any],
#     day_numbers: Optional[List[int]] = None,
# ) -> str:
#     """
#     Create ASS subtitle content for day overlays. (DEPRECATED - use overlay images instead)

#     Args:
#         image_list: List of image file paths
#         total_duration: Total video duration in seconds
#         overlay_settings: Overlay configuration settings
#         day_numbers: Optional list of day numbers (extracted from database)

#     Returns:
#         ASS subtitle content as string
#     """
#     if not overlay_settings.get("enabled", True):
#         return ""

#     # ASS subtitle header
#     ass_content = """[Script Info]
# Title: Day Overlay
# ScriptType: v4.00+

# [V4+ Styles]
# Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
# Style: Default,Arial,{font_size},&H00{font_color},&H000000FF,&H00000000,&H80{background_color},0,0,0,0,100,100,0,0,1,2,0,{alignment},10,10,10,1

# [Events]
# Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
# """.format(
#         font_size=overlay_settings.get("font_size", 48),
#         font_color=overlay_settings.get("font_color", "white").replace("#", ""),
#         background_color=overlay_settings.get("background_color", "black@0.5").replace(
#             "@", "&H"
#         ),
#         alignment=get_overlay_alignment(
#             overlay_settings.get("position", "bottom-right")
#         ),
#     )

#     # Calculate frame duration
#     if len(image_list) == 0:
#         return ass_content

#     frame_duration = total_duration / len(image_list)
#     overlay_format = overlay_settings.get("format", "Day {day}")

#     # Add dialogue lines for each frame
#     for i, image_path in enumerate(image_list):
#         start_time = i * frame_duration
#         end_time = (i + 1) * frame_duration

#         # Use provided day numbers or extract from filename
#         if day_numbers and i < len(day_numbers):
#             day_number = day_numbers[i]
#         else:
#             # Fallback: extract day number from filename
#             day_number = i + 1

#         text = overlay_format.format(day=day_number)

#         dialogue_line = f"Dialogue: 0,{seconds_to_ass_time(start_time)},{seconds_to_ass_time(end_time)},Default,,0,0,0,,{text}"
#         ass_content += dialogue_line + "\n"

#     return ass_content


def build_ffmpeg_command(
    image_list_file: str,
    output_path: str,
    framerate: float,
    quality: VideoQuality,
    rotation: int = 0,
    # subtitle_file: Optional[str] = None,
    overlay_settings: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Build FFmpeg command for video generation.

    Args:
        image_list_file: Path to file containing list of images
        output_path: Output video file path
        framerate: Video framerate
        quality: Quality level (low/medium/high)
        rotation: Video rotation in degrees (0, 90, 180, 270)
        # subtitle_file: Optional ASS subtitle file for overlays (deprecated)
        # overlay_settings: Optional overlay configuration (deprecated)

    Returns:
        FFmpeg command as list of strings
    """
    quality_opts = get_quality_settings(quality)

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output files
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        image_list_file,
        "-c:v",
        "libx264",
        "-crf",
        str(quality_opts["crf"]),
        "-preset",
        quality_opts["preset"],
    ]

    # Build video filter chain
    video_filters = [f"fps={framerate}"]

    # Add rotation filter if needed
    if rotation == 90:
        video_filters.append("transpose=1")
    elif rotation == 180:
        video_filters.append("transpose=2,transpose=2")
    elif rotation == 270:
        video_filters.append("transpose=2")

    # Apply video filters
    cmd.extend(["-vf", ",".join(video_filters)])

    # Add scaling if specified
    if quality_opts.get("scale"):
        cmd.extend(["-s", quality_opts["scale"]])

    # Add subtitle overlay if provided (deprecated - use overlay images instead)
    # if subtitle_file and overlay_settings and overlay_settings.get("enabled", True):
    #     # Override the video filter to add subtitles (deprecated path)
    #     cmd[-1] = f"fps={framerate},subtitles={subtitle_file}"
    #     logger.warning("Using deprecated subtitle overlay system in FFmpeg command")

    cmd.extend(["-pix_fmt", "yuv420p", output_path])  # Ensure compatibility

    return cmd


def execute_ffmpeg_command(
    cmd: List[str], timeout: int = 300, capture_output: bool = True
) -> Tuple[bool, str]:
    """
    Execute FFmpeg command with proper error handling.

    Args:
        cmd: FFmpeg command as list of strings
        timeout: Command timeout in seconds
        capture_output: Whether to capture stdout/stderr

    Returns:
        Tuple of (success, output_or_error_message)
    """
    try:
        logger.info(f"Executing FFmpeg command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd, capture_output=capture_output, text=True, timeout=timeout, check=False
        )

        if result.returncode == 0:
            logger.info("FFmpeg command completed successfully")
            return True, result.stdout if capture_output else "Success"
        else:
            error_msg = f"FFmpeg failed with code {result.returncode}"
            if capture_output and result.stderr:
                error_msg += f": {result.stderr}"
            logger.error(error_msg)
            return False, error_msg

    except subprocess.TimeoutExpired:
        error_msg = f"FFmpeg command timed out after {timeout} seconds"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Error executing FFmpeg command: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def create_image_list_file(image_files: List[str]) -> str:
    """
    Create temporary file with list of images for FFmpeg concat demuxer.

    Args:
        image_files: List of image file paths

    Returns:
        Path to temporary file containing image list
    """
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)

    try:
        for image_file in image_files:
            # Use validated paths and resolve properly
            validated_path = file_helpers.validate_file_path(
                image_file, must_exist=True
            )
            temp_file.write(f"file '{validated_path}'\n")
            temp_file.write("duration 1\n")  # 1 frame duration

        # Add final frame to maintain last image duration
        if image_files:
            validated_path = file_helpers.validate_file_path(
                image_files[-1], must_exist=True
            )
            temp_file.write(f"file '{validated_path}'\n")

        temp_file.flush()
        logger.debug(f"Created image list file: {temp_file.name}")
        return temp_file.name

    finally:
        temp_file.close()


def generate_video(
    images_directory: Path,
    output_path: str,
    framerate: float = 24.0,
    quality: VideoQuality = VideoQuality.MEDIUM,
    rotation: int = 0,
    use_overlay_images: bool = False,
    # overlay_settings: Optional[Dict[str, Any]] = None,
    # day_numbers: Optional[List[int]] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Generate timelapse video from images directory.

    Args:
        images_directory: Directory containing source images
        output_path: Output video file path
        framerate: Video framerate
        quality: Quality level (low/medium/high)
        rotation: Video rotation in degrees (0, 90, 180, 270)
        use_overlay_images: Whether to use pre-rendered overlay images
        # overlay_settings: Optional overlay configuration (deprecated - use overlay images)
        # day_numbers: Optional list of day numbers for overlays (deprecated)

    Returns:
        Tuple of (success, message, metadata_dict)
    """
    temp_files = []

    try:
        # Determine which images to use
        if use_overlay_images:
            # Extract camera ID from directory path
            camera_id = None
            if "camera-" in str(images_directory):
                camera_match = re.search(r"camera-(\d+)", str(images_directory))
                if camera_match:
                    camera_id = int(camera_match.group(1))

            # Try to find overlay images
            overlay_images = []
            if camera_id:
                # images_directory is like: data/cameras/camera-1/images
                # We need base_directory as: data/
                base_directory = images_directory.parent.parent
                overlay_images = find_overlay_images(camera_id, base_directory)

            if overlay_images:
                logger.info(
                    f"Using {len(overlay_images)} overlay images for video generation"
                )
                image_files = overlay_images
            else:
                logger.info("No overlay images found, falling back to regular images")
                image_files = find_image_files(images_directory)
        else:
            # Use regular images
            image_files = find_image_files(images_directory)

        if not image_files:
            return False, "No image files found in directory", {}

        logger.info(f"Generating video from {len(image_files)} images")

        # Create image list file
        image_list_file = create_image_list_file(image_files)
        temp_files.append(image_list_file)

        # Calculate video duration
        duration = len(image_files) / framerate

        # Create subtitle file if using deprecated overlay system
        # subtitle_file = None
        # if (
        #     not use_overlay_images
        #     and overlay_settings
        #     and overlay_settings.get("enabled", True)
        # ):
        #     logger.warning(
        #         "Using deprecated ASS subtitle overlay system. Consider using pre-rendered overlay images."
        #     )
        # ass_content = create_ass_subtitle_content(
        #     image_files, duration, overlay_settings, day_numbers
        # )

        # subtitle_file = tempfile.NamedTemporaryFile(
        #     mode="w", suffix=".ass", delete=False
        # )
        # subtitle_file.write(ass_content)
        # subtitle_file.close()
        # temp_files.append(subtitle_file.name)

        # Build FFmpeg command
        cmd = build_ffmpeg_command(
            image_list_file,
            output_path,
            framerate,
            quality,
            rotation,
            # subtitle_file.name if subtitle_file else None,
            # overlay_settings,
        )

        # Execute FFmpeg
        success, output = execute_ffmpeg_command(cmd)

        if success:
            # Get output file info
            output_path_obj = Path(output_path)
            output_size = (
                output_path_obj.stat().st_size if output_path_obj.exists() else 0
            )

            metadata = {
                "image_count": len(image_files),
                "duration_seconds": duration,
                "framerate": framerate,
                "quality": quality,
                "rotation": rotation,
                "file_size_bytes": output_size,
                "overlay_enabled": bool(use_overlay_images),
                "overlay_images_used": use_overlay_images,
            }

            return True, f"Video generated successfully: {output_path}", metadata
        else:
            return False, f"Video generation failed: {output}", {}

    except Exception as e:
        error_msg = f"Error during video generation: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, {}

    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                temp_file_path = Path(temp_file)
                if temp_file_path.exists():
                    temp_file_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_file}: {e}")
