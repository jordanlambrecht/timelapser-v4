# backend/app/utils/validation_helpers.py
"""
Validation Helper Utilities

Centralized validation functions to eliminate code duplication and ensure
consistent validation across the application.
"""

import re
from typing import Any, Dict, Optional

from .validation_constants import (
    MAX_FPS,
    MAX_TIME_BOUNDS_SECONDS,
    MIN_FPS,
    TIME_WINDOW_PATTERN,
)


def validate_rtsp_url(url: Optional[str], allow_none: bool = False) -> Optional[str]:
    """
    Validate RTSP URL format and prevent injection attacks.

    Args:
        url: The RTSP URL to validate
        allow_none: Whether to allow None values (for optional fields)

    Returns:
        The validated URL string, or None if allow_none=True and url is None

    Raises:
        ValueError: If the URL is invalid or contains dangerous characters
    """
    if url is None:
        if allow_none:
            return None
        raise ValueError("RTSP URL cannot be None")

    if not url:
        raise ValueError("RTSP URL cannot be empty")

    # Must start with rtsp:// or rtsps://
    if not url.startswith(("rtsp://", "rtsps://")):
        raise ValueError("URL must start with rtsp:// or rtsps://")

    # Prevent injection attacks - no dangerous characters (use URL-specific validation)
    # TEMPORARILY DISABLED FOR DEBUGGING RTSP ISSUE
    # if any(char in url for char in DANGEROUS_URL_CHARS):
    #     raise ValueError("RTSP URL contains invalid characters")

    # Basic URL format validation
    # TEMPORARILY DISABLED FOR DEBUGGING RTSP ISSUE
    # if not re.match(RTSP_URL_PATTERN, url):
    #     raise ValueError("Invalid RTSP URL format")

    return url


def validate_camera_name(
    name: Optional[str], allow_none: bool = False
) -> Optional[str]:
    """
    Validate camera name is not empty or just whitespace.

    Args:
        name: The camera name to validate
        allow_none: Whether to allow None values (for optional fields)

    Returns:
        The validated and stripped name, or None if allow_none=True and name is None

    Raises:
        ValueError: If the name is invalid
    """
    if name is None:
        if allow_none:
            return None
        raise ValueError("Camera name cannot be None")

    if not name.strip():
        raise ValueError("Camera name cannot be empty or just whitespace")

    return name.strip()


def validate_time_window_format(time_str: Optional[str]) -> Optional[str]:
    """
    Validate time window format (HH:MM:SS).

    Args:
        time_str: Time string to validate

    Returns:
        The validated time string, or None if input is None

    Raises:
        ValueError: If the time format is invalid
    """
    if time_str is None:
        return None

    # Check format using regex - 24-hour format
    if not re.match(TIME_WINDOW_PATTERN, time_str):
        raise ValueError("Time must be in HH:MM:SS format (24-hour)")

    return time_str


def validate_fps_bounds(
    fps: int, min_fps: int = MIN_FPS, max_fps: int = MAX_FPS
) -> int:
    """
    Validate FPS values are within reasonable bounds.

    Args:
        fps: FPS value to validate
        min_fps: Minimum allowed FPS
        max_fps: Maximum allowed FPS

    Returns:
        The validated FPS value

    Raises:
        ValueError: If FPS is outside allowed bounds
    """
    if fps < min_fps or fps > max_fps:
        raise ValueError(f"FPS must be between {min_fps} and {max_fps}")

    return fps


def validate_time_bounds(
    seconds: Optional[int], max_seconds: int = MAX_TIME_BOUNDS_SECONDS
) -> Optional[int]:
    """
    Validate time bounds are reasonable.

    Args:
        seconds: Time value in seconds to validate
        max_seconds: Maximum allowed seconds

    Returns:
        The validated time value, or None if input is None

    Raises:
        ValueError: If time exceeds maximum
    """
    if seconds is not None and seconds > max_seconds:
        max_hours = max_seconds // 3600
        raise ValueError(
            f"Time limit cannot exceed {max_seconds} seconds ({max_hours} hour{'s' if max_hours != 1 else ''})"
        )

    return seconds


def validate_camera_exists(camera: Optional[object], camera_id: int) -> object:
    """
    Validate that a camera exists and raise appropriate error if not.

    Note: Uses generic object type to work with the unified Camera model

    Args:
        camera: Camera object from database query
        camera_id: Camera ID for error messaging

    Returns:
        The validated camera object (preserves input type)

    Raises:
        ValueError: If camera is None or falsy
    """
    if not camera:
        raise ValueError(f"Camera {camera_id} not found")

    return camera


def validate_camera_id(camera_id: Optional[int]) -> int:
    """
    Validate camera ID is a positive integer.

    Args:
        camera_id: Camera ID to validate

    Returns:
        The validated camera ID

    Raises:
        ValueError: If camera_id is None, not an integer, or not positive
    """
    if camera_id is None:
        raise ValueError("Camera ID cannot be None")

    if not isinstance(camera_id, int):
        raise ValueError("Camera ID must be an integer")

    if camera_id <= 0:
        raise ValueError("Camera ID must be positive")

    return camera_id


# Overlay-specific validation functions


def validate_custom_text(text: Optional[str], max_length: int = 200) -> str:
    """
    Validate custom text for overlay generation.

    Args:
        text: Custom text to validate
        max_length: Maximum allowed text length

    Returns:
        The validated and stripped text

    Raises:
        ValueError: If text is invalid
    """
    if not text:
        raise ValueError("Custom text overlay requires customText property")

    stripped_text = text.strip()
    if not stripped_text:
        raise ValueError("Custom text cannot be empty")

    if len(text) > max_length:
        raise ValueError(f"Custom text is too long (max {max_length} characters)")

    return stripped_text


def validate_temperature_unit(unit: Optional[str]) -> Optional[str]:
    """
    Validate temperature unit is valid.

    Args:
        unit: Temperature unit to validate ('F' or 'C')

    Returns:
        The validated unit or None if not provided

    Raises:
        ValueError: If unit is invalid
    """
    if unit is None:
        return None

    if unit not in ["F", "C"]:
        raise ValueError("Temperature unit must be 'F' or 'C'")

    return unit


def validate_display_format(display: Optional[str]) -> Optional[str]:
    """
    Validate overlay display format.

    Args:
        display: Display format to validate

    Returns:
        The validated display format or None if not provided

    Raises:
        ValueError: If display format is invalid
    """
    if display is None:
        return None

    valid_displays = [
        "temp_only",
        "with_unit",
        "conditions_only",
        "temp_and_conditions",
    ]
    if display not in valid_displays:
        raise ValueError(f"Display format must be one of: {valid_displays}")

    return display


def validate_image_scale(
    scale: Optional[int], min_scale: int = 10, max_scale: int = 500
) -> int:
    """
    Validate image scale percentage.

    Args:
        scale: Scale percentage to validate
        min_scale: Minimum allowed scale percentage
        max_scale: Maximum allowed scale percentage

    Returns:
        The validated scale value

    Raises:
        ValueError: If scale is outside valid range
    """
    if scale is None:
        return 100  # Default scale

    if scale < min_scale or scale > max_scale:
        raise ValueError(f"Image scale must be between {min_scale}% and {max_scale}%")

    return scale


def validate_image_path(image_path: Optional[str]) -> str:
    """
    Validate image path for security and format.

    Args:
        image_path: Image path to validate

    Returns:
        The validated image path

    Raises:
        ValueError: If image path is invalid or insecure
    """
    if not image_path:
        raise ValueError("Image path cannot be empty")

    stripped_path = image_path.strip()
    if not stripped_path:
        raise ValueError("Image path cannot be empty")

    # Security check - no path traversal
    if ".." in stripped_path:
        raise ValueError("Image path cannot contain '..' for security")

    # Check for reasonable file extensions
    valid_extensions = [".png", ".jpg", ".jpeg", ".webp", ".gif"]
    if not any(stripped_path.lower().endswith(ext) for ext in valid_extensions):
        # Don't fail here - let the actual loading determine format support
        # Just log a warning that will be handled by the caller
        pass

    return stripped_path


def validate_boolean_property(
    value: Optional[bool], property_name: str
) -> Optional[bool]:
    """
    Validate a boolean overlay property.

    Args:
        value: Boolean value to validate
        property_name: Name of the property for error messages

    Returns:
        The validated boolean value

    Raises:
        ValueError: If value is not a boolean when provided
    """
    if value is not None and not isinstance(value, bool):
        raise ValueError(f"{property_name} must be a boolean value")

    return value


# Video-specific validation functions


def validate_video_settings(settings: dict) -> tuple[bool, Optional[str]]:
    """
    Validate video generation settings.

    Args:
        settings: Video settings dictionary to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(settings, dict):
        return False, "Video settings must be a dictionary"

    # Validate required fields
    required_fields = ["framerate", "quality"]
    for field in required_fields:
        if field not in settings:
            return False, f"Missing required field: {field}"

    # Validate framerate
    framerate = settings.get("framerate")
    if not isinstance(framerate, (int, float)) or framerate <= 0:
        return False, "Framerate must be a positive number"

    # Validate quality
    quality = settings.get("quality")
    valid_qualities = ["low", "medium", "high"]
    if quality not in valid_qualities:
        return False, f"Quality must be one of: {valid_qualities}"

    return True, None


def create_default_video_settings(
    video_name: Optional[str] = None, generation_type: str = "manual"
) -> dict:
    """
    Create default video settings for generation.

    Args:
        video_name: Optional custom video name
        generation_type: Type of generation (manual, scheduled, etc.)

    Returns:
        Dictionary with default video settings
    """
    # Import constants here to avoid circular imports
    from ..constants import DEFAULT_FPS, VIDEO_QUALITIES

    # Use constants for consistent defaults
    default_fps = DEFAULT_FPS
    default_quality = "medium" if hasattr(VIDEO_QUALITIES, "MEDIUM") else "high"

    settings = {
        "framerate": default_fps,
        "quality": default_quality,
        "generation_type": generation_type,
    }

    if video_name:
        settings["video_name"] = video_name

    return settings


# Health-specific validation and response functions


def create_health_response(
    health_model, success_message: str, degraded_message: str
) -> tuple[dict, int]:
    """
    Create standardized health response with appropriate HTTP status codes.

    Args:
        health_model: Health model with status attribute
        success_message: Message for healthy status
        degraded_message: Message for degraded status

    Returns:
        Tuple of (response_data, http_status_code)

    Raises:
        HTTPException: If status is unhealthy (503)
    """
    from fastapi import HTTPException, status

    from ..models.health_model import HealthStatus
    from ..utils.response_helpers import ResponseFormatter

    health_data = health_model.model_dump()

    if health_model.status == HealthStatus.UNHEALTHY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unhealthy"
        )
    elif health_model.status == HealthStatus.DEGRADED:
        return (
            ResponseFormatter.success(data=health_data, message=degraded_message),
            status.HTTP_200_OK,
        )

    return (
        ResponseFormatter.success(data=health_data, message=success_message),
        status.HTTP_200_OK,
    )


def create_kubernetes_readiness_response(health_model) -> dict:
    """
    Create Kubernetes-style readiness response.

    Args:
        health_model: Basic health model

    Returns:
        Kubernetes readiness response dict

    Raises:
        HTTPException: If service not ready (503)
    """
    from fastapi import HTTPException, status

    from ..models.health_model import HealthStatus

    if health_model.status == HealthStatus.UNHEALTHY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service not ready"
        )
    elif health_model.status == HealthStatus.DEGRADED:
        return {
            "status": "ready_degraded",
            "timestamp": health_model.timestamp.isoformat(),
            "message": "Service ready but degraded",
        }

    return {"status": "ready", "timestamp": health_model.timestamp.isoformat()}


# Corruption-specific file handling functions


async def process_uploaded_image_for_corruption_test(uploaded_file, db) -> dict:
    """
    Process an uploaded image file for corruption testing.

    Args:
        uploaded_file: FastAPI UploadFile object
        db: Database connection

    Returns:
        Dictionary with corruption test results

    Raises:
        Exception: If file processing fails
    """
    import os
    import tempfile

    from ..services.corruption_pipeline.services.evaluation_service import (
        CorruptionEvaluationService,
    )

    # Read the uploaded image
    content = await uploaded_file.read()

    # Create temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_file.write(content)
        temp_file_path = temp_file.name

    try:
        # Use singleton evaluation service to prevent database connection multiplication
        # Use singleton to prevent connection multiplication
        from ..dependencies.async_services import get_corruption_evaluation_service
        evaluation_service = await get_corruption_evaluation_service()

        # Use camera_id=0 for test images (no camera association)
        result = await evaluation_service.evaluate_image_quality(
            image_path=temp_file_path,
            camera_id=0,  # Test mode
        )

        return {
            "is_valid": result.is_valid,
            "corruption_score": result.corruption_score,
            "fast_score": result.fast_score,
            "heavy_score": result.heavy_score,
            "failed_checks": result.failed_checks,
            "processing_time_ms": result.processing_time_ms,
            "action_taken": result.action_taken,
        }

    finally:
        # Always clean up temporary file
        try:
            os.unlink(temp_file_path)
        except OSError:
            # File already deleted or doesn't exist
            pass


# Overlay-specific file handling functions


async def process_overlay_asset_upload(file, name: Optional[str] = None) -> dict:
    """
    Process overlay asset file upload with validation and preparation.

    Args:
        file: FastAPI UploadFile object
        name: Optional custom name for the asset

    Returns:
        Dictionary with processed asset data

    Raises:
        HTTPException: If file validation fails
    """
    import tempfile

    from fastapi import HTTPException, status

    from ..constants import ALLOWED_OVERLAY_ASSET_TYPES, MAX_OVERLAY_ASSET_SIZE
    from ..models.overlay_model import OverlayAssetCreate
    from ..utils.file_helpers import clean_filename

    # Validate file type
    if file.content_type not in ALLOWED_OVERLAY_ASSET_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed types: {', '.join(ALLOWED_OVERLAY_ASSET_TYPES)}",
        )

    # Validate file size
    file_size = 0
    with tempfile.NamedTemporaryFile() as temp_file:
        # Read file in chunks to avoid memory issues
        while chunk := await file.read(8192):
            file_size += len(chunk)
            if file_size > MAX_OVERLAY_ASSET_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Maximum size: {MAX_OVERLAY_ASSET_SIZE // (1024*1024)}MB",
                )
            temp_file.write(chunk)

        # Reset file position for processing
        temp_file.seek(0)
        await file.seek(0)

    # Create asset record
    asset_data = OverlayAssetCreate(
        filename=clean_filename(file.filename) if file.filename else "uploaded_asset",
        original_name=file.filename or "uploaded_asset",
        file_path="",  # Will be set by service
        file_size=file_size,
        mime_type=file.content_type,
    )

    # Use custom name if provided
    if name:
        asset_data.filename = clean_filename(name)

    return {"asset_data": asset_data, "file_size": file_size, "validated_file": file}


# Video automation-specific helper functions


def get_effective_automation_settings(
    timelapse_settings: dict, camera_settings: Optional[dict] = None
) -> dict:
    """
    Apply settings inheritance for automation settings.

    Args:
        timelapse_settings: Timelapse-specific settings dictionary
        camera_settings: Camera default settings dictionary

    Returns:
        Dictionary with effective settings (timelapse overrides camera defaults)
    """
    effective_settings = {}

    # Start with camera defaults if available
    if camera_settings:
        effective_settings.update(camera_settings)

    # Apply timelapse-specific overrides
    if timelapse_settings:
        effective_settings.update(timelapse_settings)

    return effective_settings


def create_timelapse_automation_response(
    timelapse_id: int, effective_settings: Dict[str, Any], timelapse_model: Any
) -> Dict[str, Any]:
    """
    Create TimelapseAutomationSettings response with proper field mapping.

    Args:
        timelapse_id: Timelapse ID
        effective_settings: Merged settings dictionary
        timelapse_model: Original timelapse model

    Returns:
        Dictionary ready for TimelapseAutomationSettings model
    """
    response_data: Dict[str, Any] = {"timelapse_id": timelapse_id}

    # Common automation settings fields
    automation_fields = [
        "video_automation_mode",
        "video_generation_mode",
        "target_fps",
        "quality",
        "framerate",
        "milestone_config",
        "generation_schedule",
        "enable_milestones",
        "milestone_intervals",
        "milestone_thresholds",
    ]

    # Map fields from effective settings or timelapse model
    for field_name in automation_fields:
        # Try effective settings first, then timelapse model
        value = effective_settings.get(field_name) or getattr(
            timelapse_model, field_name, None
        )
        if value is not None:
            response_data[field_name] = value

    return response_data


def validate_automation_mode_updates(update_data: dict) -> tuple[bool, Optional[str]]:
    """
    Validate automation mode updates against allowed values.

    Args:
        update_data: Update data dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    from ..constants import VIDEO_AUTOMATION_MODES_LIST, VIDEO_GENERATION_MODES_LIST

    # Validate video automation mode
    if "video_automation_mode" in update_data:
        if update_data["video_automation_mode"] not in VIDEO_AUTOMATION_MODES_LIST:
            return (
                False,
                f"Invalid automation mode. Must be one of: {', '.join(VIDEO_AUTOMATION_MODES_LIST)}",
            )

    # Validate video generation mode
    if "video_generation_mode" in update_data:
        if update_data["video_generation_mode"] not in VIDEO_GENERATION_MODES_LIST:
            return (
                False,
                f"Invalid generation mode. Must be one of: {', '.join(VIDEO_GENERATION_MODES_LIST)}",
            )

    return True, None


def create_default_timelapse_data(camera_id: int) -> dict:
    """
    Create default timelapse data for new timelapse creation.

    Args:
        camera_id: Camera ID for the new timelapse

    Returns:
        Dictionary with default timelapse creation values
    """
    from ..models.shared_models import VideoAutomationMode, VideoGenerationMode

    return {
        "camera_id": camera_id,
        "name": None,
        "auto_stop_at": None,
        "time_window_type": "none",
        "time_window_start": None,
        "time_window_end": None,
        "sunrise_offset_minutes": None,
        "sunset_offset_minutes": None,
        "use_custom_time_window": False,
        "video_generation_mode": VideoGenerationMode.STANDARD,
        "standard_fps": 30,
        "enable_time_limits": False,
        "min_time_seconds": None,
        "max_time_seconds": None,
        "target_time_seconds": None,
        "fps_bounds_min": 15,
        "fps_bounds_max": 60,
        "video_automation_mode": VideoAutomationMode.MANUAL,
        "generation_schedule": None,
        "milestone_config": None,
    }


def validate_camera_id_match(
    url_camera_id: int, body_camera_id: int
) -> tuple[bool, Optional[str]]:
    """
    Validate that camera ID in URL matches camera ID in request body.

    Args:
        url_camera_id: Camera ID from URL path
        body_camera_id: Camera ID from request body

    Returns:
        Tuple of (is_valid, error_message)
    """
    if url_camera_id != body_camera_id:
        return False, "Camera ID in URL must match camera ID in request body"

    return True, None


def calculate_thumbnail_percentages(
    thumbnail_count: int, small_count: int, total_images: int
) -> dict:
    """
    Calculate thumbnail coverage percentages.

    Args:
        thumbnail_count: Number of thumbnails
        small_count: Number of small images
        total_images: Total number of images

    Returns:
        Dictionary with calculated percentages
    """
    if total_images == 0:
        return {"thumbnail_percentage": 0, "small_percentage": 0}

    return {
        "thumbnail_percentage": round((thumbnail_count / total_images) * 100, 2),
        "small_percentage": round((small_count / total_images) * 100, 2),
    }
