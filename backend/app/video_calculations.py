# backend/app/video_calculations.py

from typing import NamedTuple, Optional, Union, TypeVar, cast
from dataclasses import dataclass
from enum import Enum

from app.models.camera import VideoGenerationMode

T = TypeVar("T")


@dataclass
class VideoGenerationSettings:
    """Video generation settings for a timelapse"""

    video_generation_mode: str
    standard_fps: int = 12
    enable_time_limits: bool = False
    min_time_seconds: Optional[int] = None
    max_time_seconds: Optional[int] = None
    target_time_seconds: Optional[int] = None
    fps_bounds_min: int = 1
    fps_bounds_max: int = 60


class VideoCalculationResult(NamedTuple):
    """Result of video generation calculations"""

    fps: float
    duration: float
    fps_was_adjusted: bool
    adjustment_reason: Optional[str]


def calculate_video_fps(
    total_images: int, settings: VideoGenerationSettings
) -> VideoCalculationResult:
    """
    Calculate the optimal FPS for video generation based on settings and image count.

    Args:
        total_images: Number of images in the timelapse
        settings: Video generation settings

    Returns:
        VideoCalculationResult with FPS, duration, and adjustment info
    """
    if total_images < 1:
        raise ValueError("Cannot generate video with less than 1 image")

    fps_was_adjusted = False
    adjustment_reason = None

    if settings.video_generation_mode == VideoGenerationMode.STANDARD:
        fps = float(settings.standard_fps)
        estimated_duration = total_images / fps

        if settings.enable_time_limits:
            # Check minimum time constraint
            if (
                settings.min_time_seconds is not None
                and estimated_duration < settings.min_time_seconds
            ):
                fps = total_images / settings.min_time_seconds
                fps_was_adjusted = True
                adjustment_reason = f"Adjusted FPS from {settings.standard_fps} to {fps:.2f} to meet minimum time of {settings.min_time_seconds}s"

            # Check maximum time constraint
            elif (
                settings.max_time_seconds is not None
                and estimated_duration > settings.max_time_seconds
            ):
                fps = total_images / settings.max_time_seconds
                fps_was_adjusted = True
                adjustment_reason = f"Adjusted FPS from {settings.standard_fps} to {fps:.2f} to meet maximum time of {settings.max_time_seconds}s"

    elif settings.video_generation_mode == VideoGenerationMode.TARGET:
        if settings.target_time_seconds is None:
            raise ValueError("Target time must be specified for target mode")

        # Calculate required FPS for target duration
        required_fps = total_images / settings.target_time_seconds
        fps = required_fps

        # Clamp to FPS bounds
        if required_fps < settings.fps_bounds_min:
            fps = float(settings.fps_bounds_min)
            fps_was_adjusted = True
            adjustment_reason = f"FPS clamped from {required_fps:.2f} to minimum bound of {settings.fps_bounds_min}"
        elif required_fps > settings.fps_bounds_max:
            fps = float(settings.fps_bounds_max)
            fps_was_adjusted = True
            adjustment_reason = f"FPS clamped from {required_fps:.2f} to maximum bound of {settings.fps_bounds_max}"

    else:
        raise ValueError(
            f"Unknown video generation mode: {settings.video_generation_mode}"
        )

    # Calculate final duration
    duration = total_images / fps

    return VideoCalculationResult(
        fps=fps,
        duration=duration,
        fps_was_adjusted=fps_was_adjusted,
        adjustment_reason=adjustment_reason,
    )


def validate_video_generation_settings(settings: VideoGenerationSettings) -> None:
    """
    Validate video generation settings for logical consistency.

    Args:
        settings: Video generation settings to validate

    Raises:
        ValueError: If settings are invalid
    """
    # Validate time limits consistency
    if (
        settings.min_time_seconds is not None
        and settings.max_time_seconds is not None
        and settings.min_time_seconds >= settings.max_time_seconds
    ):
        raise ValueError("Minimum time must be less than maximum time")

    # Validate FPS bounds consistency
    if settings.fps_bounds_min >= settings.fps_bounds_max:
        raise ValueError("Minimum FPS bound must be less than maximum FPS bound")

    # Validate target mode requirements
    if (
        settings.video_generation_mode == VideoGenerationMode.TARGET
        and settings.target_time_seconds is None
    ):
        raise ValueError("Target time must be specified for target mode")

    # Validate reasonable values
    if settings.standard_fps < 1 or settings.standard_fps > 120:
        raise ValueError("Standard FPS must be between 1 and 120")

    if settings.fps_bounds_min < 1 or settings.fps_bounds_max > 120:
        raise ValueError("FPS bounds must be between 1 and 120")

    if settings.min_time_seconds is not None and settings.min_time_seconds < 1:
        raise ValueError("Minimum time must be at least 1 second")

    if settings.max_time_seconds is not None and settings.max_time_seconds > 3600:
        raise ValueError("Maximum time cannot exceed 3600 seconds (1 hour)")


def get_effective_video_settings(
    camera_settings: dict, timelapse_settings: dict
) -> VideoGenerationSettings:
    """
    Get effective video generation settings by inheriting from camera and applying timelapse overrides.

    Args:
        camera_settings: Camera's default video generation settings
        timelapse_settings: Timelapse-specific overrides (None values use camera defaults)

    Returns:
        VideoGenerationSettings with effective values
    """

    def get_value(key: str, default_value: T) -> T:
        """Get value from timelapse settings, falling back to camera settings"""
        timelapse_value = timelapse_settings.get(key)
        if timelapse_value is not None:
            return cast(T, timelapse_value)
        camera_value = camera_settings.get(key)
        if camera_value is not None:
            return cast(T, camera_value)
        return default_value

    return VideoGenerationSettings(
        video_generation_mode=get_value("video_generation_mode", "standard"),
        standard_fps=get_value("standard_fps", 12),
        enable_time_limits=get_value("enable_time_limits", False),
        min_time_seconds=get_value("min_time_seconds", None),
        max_time_seconds=get_value("max_time_seconds", None),
        target_time_seconds=get_value("target_time_seconds", None),
        fps_bounds_min=get_value("fps_bounds_min", 1),
        fps_bounds_max=get_value("fps_bounds_max", 60),
    )


def preview_video_calculation(
    total_images: int, settings: VideoGenerationSettings
) -> dict:
    """
    Preview video generation calculation without actually generating.

    Args:
        total_images: Number of images available
        settings: Video generation settings

    Returns:
        Dictionary with preview information
    """
    if total_images < 10:
        return {
            "error": f"Not enough images for video generation (have {total_images}, need at least 10)"
        }

    try:
        validate_video_generation_settings(settings)
        result = calculate_video_fps(total_images, settings)

        return {
            "total_images": total_images,
            "calculated_fps": result.fps,
            "estimated_duration": result.duration,
            "duration_formatted": f"{int(result.duration // 60)}:{int(result.duration % 60):02d}",
            "fps_was_adjusted": result.fps_was_adjusted,
            "adjustment_reason": result.adjustment_reason,
            "settings": {
                "mode": settings.video_generation_mode,
                "standard_fps": settings.standard_fps,
                "enable_time_limits": settings.enable_time_limits,
                "min_time_seconds": settings.min_time_seconds,
                "max_time_seconds": settings.max_time_seconds,
                "target_time_seconds": settings.target_time_seconds,
                "fps_bounds": f"{settings.fps_bounds_min}-{settings.fps_bounds_max}",
            },
        }
    except ValueError as e:
        return {"error": str(e)}
