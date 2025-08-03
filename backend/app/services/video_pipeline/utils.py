# backend/app/services/video_pipeline/utils.py
"""
Video Pipeline Domain Utilities

Utility functions specific to the video pipeline domain.
Pure functions with no external dependencies.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ...constants import (
    VIDEO_AUTOMATION_MODES_LIST,
    VIDEO_GENERATION_MODE,
    VIDEO_QUALITY_LEVEL,
)
from ...utils.time_utils import format_filename_timestamp, utc_now
from .constants import (
    DEFAULT_VIDEO_FPS,
    DEFAULT_VIDEO_MAX_DURATION,
    DEFAULT_VIDEO_MIN_DURATION,
    DEFAULT_VIDEO_QUALITY,
    DEFAULT_VIDEO_TARGET_DURATION,
    VIDEO_FILE_SIZE_OVERHEAD_PERCENT,
    VIDEO_FILENAME_MAX_LENGTH,
    VIDEO_JOB_STATUSES,
    VIDEO_PROCESSING_MAX_TIME_SECONDS,
    VIDEO_PROCESSING_MIN_TIME_SECONDS,
    VIDEO_PROCESSING_OVERHEAD_SECONDS,
)


def validate_video_quality(quality: str) -> bool:
    """
    Validate video quality setting.

    Args:
        quality: Quality setting to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        return isinstance(quality, str) and quality.lower() in [
            q.lower() for q in VIDEO_QUALITY_LEVEL
        ]
    except (AttributeError, TypeError):
        return False


def validate_video_generation_mode(mode: str) -> bool:
    """
    Validate video generation mode.

    Args:
        mode: Generation mode to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        return isinstance(mode, str) and mode.lower() in [
            m.lower() for m in VIDEO_GENERATION_MODE
        ]
    except (AttributeError, TypeError):
        return False


def validate_fps_value(fps: float) -> bool:
    """
    Validate FPS value.

    Args:
        fps: FPS value to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        return isinstance(fps, (int, float)) and 1 <= fps <= 120
    except (TypeError, ValueError):
        return False


def validate_duration_value(duration: int) -> bool:
    """
    Validate duration value in seconds.

    Args:
        duration: Duration in seconds to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        return isinstance(duration, int) and duration > 0
    except (TypeError, ValueError):
        return False


def calculate_target_fps(
    total_images: int, target_duration: int, fps_min: int, fps_max: int
) -> float:
    """
    Calculate FPS for target duration mode.

    Args:
        total_images: Total number of images in timelapse
        target_duration: Target video duration in seconds
        fps_min: Minimum allowed FPS
        fps_max: Maximum allowed FPS

    Returns:
        Calculated FPS value within bounds
    """
    try:
        if total_images <= 0 or target_duration <= 0:
            return DEFAULT_VIDEO_FPS

        # Calculate ideal FPS: fps = total_images / target_duration
        calculated_fps = total_images / target_duration

        # Clamp to min/max bounds
        return max(fps_min, min(fps_max, calculated_fps))
    except (TypeError, ValueError, ZeroDivisionError):
        return DEFAULT_VIDEO_FPS


def calculate_video_duration(total_images: int, fps: float) -> float:
    """
    Calculate video duration based on image count and FPS.

    Args:
        total_images: Total number of images
        fps: Frames per second

    Returns:
        Video duration in seconds
    """
    try:
        if total_images <= 0 or fps <= 0:
            return 0.0

        # Formula: duration = total_images / fps
        return total_images / fps
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def generate_video_filename(
    camera_name: str,
    trigger_type: str,
    timestamp: datetime,
    extra_info: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate video filename based on naming convention.

    Args:
        camera_name: Name of the camera
        trigger_type: Type of trigger that created the video
        timestamp: Timestamp for the video
        extra_info: Additional information for filename

    Returns:
        Generated filename with extension
    """
    try:
        # Sanitize camera name
        clean_camera_name = sanitize_filename(camera_name) or "camera"

        # Sanitize trigger type
        clean_trigger = sanitize_filename(trigger_type) or "video"

        # Format timestamp using timezone-aware utility
        timestamp_str = format_filename_timestamp(timestamp)

        # Build base filename
        base_filename = f"{clean_camera_name}_{clean_trigger}_{timestamp_str}"

        # Add extra info if provided
        if extra_info:
            extra_parts = []
            for key, value in extra_info.items():
                if value is not None:
                    clean_value = sanitize_filename(str(value))
                    if clean_value:
                        extra_parts.append(f"{key}-{clean_value}")

            if extra_parts:
                extra_str = "_".join(extra_parts)
                base_filename = f"{base_filename}_{extra_str}"

        # Ensure filename isn't too long and add extension
        max_base_length = VIDEO_FILENAME_MAX_LENGTH - 4  # Reserve 4 chars for .mp4
        if len(base_filename) > max_base_length:
            base_filename = base_filename[:max_base_length]

        return f"{base_filename}.mp4"
    except Exception:
        # Fallback to simple filename
        return f"video_{format_filename_timestamp(timestamp)}.mp4"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to ensure it's safe for filesystem.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    try:
        if not filename:
            return "video"

        # Remove/replace invalid characters for cross-platform compatibility
        invalid_chars = r'[<>:"/\|?*]'
        sanitized = re.sub(invalid_chars, "_", filename)

        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip(" .")

        # Ensure filename is not empty after sanitization
        if not sanitized:
            return "video"

        # Limit length to reasonable size
        if len(sanitized) > VIDEO_FILENAME_MAX_LENGTH:
            sanitized = sanitized[:VIDEO_FILENAME_MAX_LENGTH]

        return sanitized
    except Exception:
        return "video"


def validate_timelapse_settings(settings: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate complete timelapse video settings.

    Args:
        settings: Dictionary of video settings

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if not isinstance(settings, dict):
            return False, "Settings must be a dictionary"

        # Validate FPS if provided
        fps = settings.get("fps")
        if fps is not None and not validate_fps_value(fps):
            return False, f"Invalid FPS value: {fps}. Must be between 1 and 120."

        # Validate quality if provided
        quality = settings.get("quality")
        if quality is not None and not validate_video_quality(quality):
            return False, f"Invalid quality value: {quality}"

        # Validate generation mode if provided
        generation_mode = settings.get("generation_mode")
        if generation_mode is not None and not validate_video_generation_mode(
            generation_mode
        ):
            return False, f"Invalid generation mode: {generation_mode}"

        # Validate duration settings if provided
        min_duration = settings.get("min_duration")
        if min_duration is not None and not validate_duration_value(min_duration):
            return False, f"Invalid min_duration: {min_duration}"

        max_duration = settings.get("max_duration")
        if max_duration is not None and not validate_duration_value(max_duration):
            return False, f"Invalid max_duration: {max_duration}"

        # Check min <= max duration if both provided
        if (
            min_duration is not None
            and max_duration is not None
            and min_duration > max_duration
        ):
            return False, "min_duration cannot be greater than max_duration"

        return True, None
    except Exception as e:
        return False, f"Settings validation error: {str(e)}"


def transform_frontend_settings(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform frontend form data to backend processing format.

    Args:
        form_data: Frontend TimelapseForm data

    Returns:
        Backend-compatible settings dictionary
    """
    try:
        if not isinstance(form_data, dict):
            return {}

        # Map frontend field names to backend format
        field_mapping = {
            "videoFps": "fps",
            "videoQuality": "quality",
            "videoGenerationMode": "generation_mode",
            "videoMinDuration": "min_duration",
            "videoMaxDuration": "max_duration",
            "videoTargetDuration": "target_duration",
            "videoRotation": "rotation",
            "useOverlayImages": "use_overlay_images",
        }

        backend_settings = {}

        for frontend_key, backend_key in field_mapping.items():
            if frontend_key in form_data:
                value = form_data[frontend_key]
                # Basic type conversion
                if backend_key in [
                    "fps",
                    "min_duration",
                    "max_duration",
                    "target_duration",
                    "rotation",
                ]:
                    try:
                        backend_settings[backend_key] = (
                            int(value) if value is not None else None
                        )
                    except (ValueError, TypeError):
                        continue
                elif backend_key == "use_overlay_images":
                    backend_settings[backend_key] = bool(value)
                else:
                    backend_settings[backend_key] = (
                        str(value) if value is not None else None
                    )

        return backend_settings
    except Exception:
        return {}


def get_effective_video_settings(timelapse_settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get effective video settings from timelapse (no inheritance).

    Args:
        timelapse_settings: Timelapse video settings

    Returns:
        Effective video settings for generation
    """
    try:
        if not isinstance(timelapse_settings, dict):
            timelapse_settings = {}

        # Extract and validate settings with proper defaults
        settings = {
            "fps": timelapse_settings.get("video_standard_fps", DEFAULT_VIDEO_FPS),
            "quality": timelapse_settings.get("video_quality", DEFAULT_VIDEO_QUALITY),
            "generation_mode": timelapse_settings.get(
                "video_generation_mode", "standard"
            ),
            "min_duration": timelapse_settings.get(
                "video_min_duration", DEFAULT_VIDEO_MIN_DURATION
            ),
            "max_duration": timelapse_settings.get(
                "video_max_duration", DEFAULT_VIDEO_MAX_DURATION
            ),
            "target_duration": timelapse_settings.get(
                "video_target_duration", DEFAULT_VIDEO_TARGET_DURATION
            ),
            "rotation": timelapse_settings.get("video_rotation", 0),
            "use_overlay_images": timelapse_settings.get("use_overlay_images", True),
        }

        # Validate and sanitize values
        if not validate_fps_value(settings["fps"]):
            settings["fps"] = DEFAULT_VIDEO_FPS

        if not validate_video_quality(settings["quality"]):
            settings["quality"] = DEFAULT_VIDEO_QUALITY

        if not validate_video_generation_mode(settings["generation_mode"]):
            settings["generation_mode"] = "standard"

        if not validate_duration_value(settings["min_duration"]):
            settings["min_duration"] = DEFAULT_VIDEO_MIN_DURATION

        if not validate_duration_value(settings["max_duration"]):
            settings["max_duration"] = DEFAULT_VIDEO_MAX_DURATION

        # Ensure min <= max duration
        if settings["min_duration"] > settings["max_duration"]:
            settings["max_duration"] = settings["min_duration"]

        return settings
    except Exception:
        # Return safe defaults on any error
        return {
            "fps": DEFAULT_VIDEO_FPS,
            "quality": DEFAULT_VIDEO_QUALITY,
            "generation_mode": "standard",
            "min_duration": DEFAULT_VIDEO_MIN_DURATION,
            "max_duration": DEFAULT_VIDEO_MAX_DURATION,
            "target_duration": DEFAULT_VIDEO_TARGET_DURATION,
            "rotation": 0,
            "use_overlay_images": True,
        }


def format_video_job_name(timelapse_name: str, trigger_type: str) -> str:
    """
    Format video job name for display.

    Args:
        timelapse_name: Name of the timelapse
        trigger_type: Type of trigger

    Returns:
        Formatted job name
    """
    try:
        # Clean inputs
        clean_name = timelapse_name.strip() if timelapse_name else "Unnamed Timelapse"
        clean_trigger = trigger_type.strip() if trigger_type else "unknown"

        # Format trigger type for display
        trigger_display_map = {
            "manual": "Manual",
            "per_capture": "Per-Capture",
            "scheduled": "Scheduled",
            "milestone": "Milestone",
        }

        display_trigger = trigger_display_map.get(
            clean_trigger.lower(), clean_trigger.title()
        )

        return f"Video: {clean_name} ({display_trigger})"
    except Exception:
        return "Video Generation Job"


def calculate_estimated_processing_time(
    total_images: int, quality: str, generation_mode: str
) -> int:
    """
    Calculate estimated video processing time.

    Args:
        total_images: Total number of images
        quality: Video quality setting
        generation_mode: Generation mode

    Returns:
        Estimated processing time in seconds
    """
    try:
        if total_images <= 0:
            return 60  # Default 1 minute

        # Base processing time per image (seconds)
        base_time_per_image = 0.1  # 100ms per image baseline

        # Quality multipliers
        quality_multipliers = {"low": 0.5, "medium": 1.0, "high": 1.5, "ultra": 2.0}

        # Generation mode multipliers
        mode_multipliers = {
            "standard": 1.0,
            "target": 1.2,  # Slightly more complex
        }

        quality_mult = quality_multipliers.get(quality, 1.0)
        mode_mult = mode_multipliers.get(generation_mode, 1.0)

        # Calculate estimated time
        estimated_seconds = (
            total_images * base_time_per_image * quality_mult * mode_mult
        )

        # Add fixed overhead (FFmpeg initialization, etc.)
        estimated_seconds += VIDEO_PROCESSING_OVERHEAD_SECONDS

        # Apply min/max bounds
        return max(
            VIDEO_PROCESSING_MIN_TIME_SECONDS,
            min(VIDEO_PROCESSING_MAX_TIME_SECONDS, int(estimated_seconds)),
        )
    except Exception:
        return 60  # Default fallback


def validate_trigger_type(trigger_type: str) -> bool:
    """
    Validate video trigger type.

    Args:
        trigger_type: Trigger type to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        return isinstance(trigger_type, str) and trigger_type.lower() in [
            t.lower() for t in VIDEO_AUTOMATION_MODES_LIST
        ]
    except (AttributeError, TypeError):
        return False


def validate_job_status(status: str) -> bool:
    """
    Validate video job status.

    Args:
        status: Job status to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        return isinstance(status, str) and status.lower() in [
            s.lower() for s in VIDEO_JOB_STATUSES
        ]
    except (AttributeError, TypeError):
        return False


def format_video_settings_for_display(settings: Dict[str, Any]) -> Dict[str, str]:
    """
    Format video settings for display in UI.

    Args:
        settings: Video settings dictionary

    Returns:
        Formatted settings for display
    """
    try:
        formatted = {}

        # Format FPS
        fps = settings.get("fps")
        if fps is not None:
            formatted["Frame Rate"] = f"{fps} FPS"

        # Format quality
        quality = settings.get("quality")
        if quality is not None:
            quality_labels = {
                "low": "Low (Fast)",
                "medium": "Medium (Balanced)",
                "high": "High (Quality)",
                "ultra": "Ultra (Best)",
            }
            formatted["Quality"] = quality_labels.get(quality, quality.title())

        # Format generation mode
        generation_mode = settings.get("generation_mode")
        if generation_mode is not None:
            mode_labels = {"standard": "Standard FPS", "target": "Target Duration"}
            formatted["Mode"] = mode_labels.get(
                generation_mode, generation_mode.title()
            )

        # Format durations
        min_duration = settings.get("min_duration")
        if min_duration is not None:
            formatted["Min Duration"] = f"{min_duration}s"

        max_duration = settings.get("max_duration")
        if max_duration is not None:
            formatted["Max Duration"] = f"{max_duration}s"

        return formatted
    except Exception:
        return {}


def calculate_video_file_size_estimate(
    total_images: int, quality: str, fps: float, duration: float
) -> int:
    """
    Calculate estimated video file size.

    Args:
        total_images: Number of images
        quality: Video quality setting
        fps: Frames per second
        duration: Video duration in seconds

    Returns:
        Estimated file size in bytes
    """
    try:
        if total_images <= 0 or duration <= 0:
            return 1024 * 1024  # Default 1MB

        # Base bitrate estimates (kbps) for different qualities
        quality_bitrates = {
            "low": 500,  # 500 kbps
            "medium": 2000,  # 2 Mbps
            "high": 5000,  # 5 Mbps
            "ultra": 10000,  # 10 Mbps
        }

        bitrate_kbps = quality_bitrates.get(quality, 2000)  # Default to medium

        # Convert bitrate to bytes per second
        bytes_per_second = (bitrate_kbps * 1000) / 8  # kbps to bytes/sec

        # Calculate file size: duration * bytes_per_second
        estimated_size = int(duration * bytes_per_second)

        # Add overhead for container format
        overhead_mult = 1 + (VIDEO_FILE_SIZE_OVERHEAD_PERCENT / 100)
        estimated_size = int(estimated_size * overhead_mult)

        # Minimum 100KB, maximum 5GB
        return max(100 * 1024, min(5 * 1024 * 1024 * 1024, estimated_size))
    except Exception:
        return 1024 * 1024  # Default 1MB


def validate_disk_space_for_video(
    estimated_size: int, output_directory: Path, min_free_space_mb: int = 1000
) -> bool:
    """
    Validate sufficient disk space for video generation.

    Args:
        estimated_size: Estimated video file size in bytes
        output_directory: Directory where video will be saved
        min_free_space_mb: Minimum free space required in MB

    Returns:
        True if sufficient space, False otherwise
    """
    try:

        # Get available disk space
        total, used, free = shutil.disk_usage(output_directory)

        # Convert minimum free space to bytes
        min_free_bytes = min_free_space_mb * 1024 * 1024

        # Required space = estimated file size + minimum free space buffer
        required_space = estimated_size + min_free_bytes

        return free >= required_space
    except Exception:
        # If we can't check disk space, assume it's available
        return True


def create_video_job_metadata(
    timelapse_id: int,
    trigger_type: str,
    settings: Dict[str, Any],
    estimated_duration: int,
) -> Dict[str, Any]:
    """
    Create metadata for video generation job.

    Args:
        timelapse_id: ID of the timelapse
        trigger_type: Type of trigger
        settings: Video generation settings
        estimated_duration: Estimated processing time

    Returns:
        Job metadata dictionary
    """
    try:
        # Get current timestamp
        created_at = utc_now().isoformat()

        # Validate and clean inputs
        clean_timelapse_id = int(timelapse_id) if timelapse_id is not None else 0
        clean_trigger_type = str(trigger_type) if trigger_type else "unknown"
        clean_settings = dict(settings) if isinstance(settings, dict) else {}
        clean_estimated_duration = (
            int(estimated_duration) if estimated_duration is not None else 60
        )

        # Create comprehensive metadata
        metadata = {
            "timelapse_id": clean_timelapse_id,
            "trigger_type": clean_trigger_type,
            "created_at": created_at,
            "estimated_duration_seconds": clean_estimated_duration,
            "video_settings": clean_settings,
            "metadata_version": "1.0",
            "pipeline_version": "simplified_3_service",
        }

        # Add quality-based estimates if settings available
        if "fps" in clean_settings and "quality" in clean_settings:
            metadata["estimated_file_size_mb"] = "calculated_on_demand"
            metadata["processing_complexity"] = _calculate_processing_complexity(
                clean_settings
            )

        return metadata
    except Exception as e:
        # Return minimal safe metadata on error
        return {
            "timelapse_id": timelapse_id or 0,
            "trigger_type": trigger_type or "unknown",
            "created_at": utc_now().isoformat(),
            "estimated_duration_seconds": 60,
            "video_settings": {},
            "metadata_version": "1.0",
            "error": str(e),
        }


def validate_timelapse_id(timelapse_id: int) -> bool:
    """
    Validate timelapse ID format and value.

    Args:
        timelapse_id: ID to validate

    Returns:
        True if valid timelapse ID
    """
    try:
        # Check if it's an integer or can be converted to one
        if isinstance(timelapse_id, str):
            timelapse_id = int(timelapse_id)

        # Must be a positive integer
        return (
            isinstance(timelapse_id, int)
            and timelapse_id > 0
            and timelapse_id < 2147483647
        )  # Max 32-bit int
    except (ValueError, TypeError, OverflowError):
        return False


def _calculate_processing_complexity(settings: Dict[str, Any]) -> str:
    """
    Calculate processing complexity based on video settings.

    Args:
        settings: Video generation settings

    Returns:
        Complexity level string
    """
    try:
        fps = settings.get("fps", DEFAULT_VIDEO_FPS)
        quality = settings.get("quality", DEFAULT_VIDEO_QUALITY)

        # Base complexity on FPS and quality
        complexity_score = 0

        # FPS complexity
        if fps <= 15:
            complexity_score += 1
        elif fps <= 30:
            complexity_score += 2
        else:
            complexity_score += 3

        # Quality complexity
        quality_scores = {"low": 1, "medium": 2, "high": 3, "ultra": 4}
        complexity_score += quality_scores.get(
            quality.lower() if isinstance(quality, str) else "medium", 2
        )

        # Return complexity level
        if complexity_score <= 3:
            return "low"
        elif complexity_score <= 5:
            return "medium"
        else:
            return "high"
    except Exception:
        return "medium"


def format_overlay_error_message(error: str, timelapse_id: int) -> str:
    """
    Format overlay error message with context.

    Args:
        error: Original error message
        timelapse_id: ID of the timelapse

    Returns:
        Formatted error message
    """
    try:
        clean_error = str(error).strip() if error else "Unknown overlay error"
        clean_timelapse_id = (
            int(timelapse_id) if timelapse_id is not None else "unknown"
        )

        # Add helpful context based on error type
        if "not found" in clean_error.lower():
            return f"Overlay system error for timelapse {clean_timelapse_id}: {clean_error}. Check if overlay images exist in the expected directory."
        elif "permission" in clean_error.lower():
            return f"Overlay system error for timelapse {clean_timelapse_id}: {clean_error}. Check file permissions for overlay directory."
        elif "import" in clean_error.lower() or "module" in clean_error.lower():
            return f"Overlay system error for timelapse {clean_timelapse_id}: {clean_error}. Overlay system may not be installed or configured."
        else:
            return f"Overlay system error for timelapse {clean_timelapse_id}: {clean_error}. Video generation will fall back to regular images."
    except Exception:
        return f"Overlay error for timelapse {timelapse_id}: {error}"
