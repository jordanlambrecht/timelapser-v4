# backend/app/models/shared_models.py
"""
Shared model components to eliminate duplication across models.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime


class VideoGenerationMode(str, Enum):
    STANDARD = "standard"
    TARGET = "target"


class VideoAutomationMode(str, Enum):
    MANUAL = "manual"
    PER_CAPTURE = "per_capture"
    SCHEDULED = "scheduled"
    MILESTONE = "milestone"


class VideoGenerationSettings(BaseModel):
    """Shared video generation settings to eliminate duplication"""

    video_generation_mode: VideoGenerationMode = Field(
        default=VideoGenerationMode.STANDARD, description="Video generation mode"
    )
    standard_fps: int = Field(
        default=12, ge=1, le=120, description="Standard FPS for video generation"
    )
    enable_time_limits: bool = Field(
        default=False, description="Enable time limits for standard FPS mode"
    )
    min_time_seconds: Optional[int] = Field(
        None, ge=1, description="Minimum video duration in seconds"
    )
    max_time_seconds: Optional[int] = Field(
        None, ge=1, description="Maximum video duration in seconds"
    )
    target_time_seconds: Optional[int] = Field(
        None, ge=1, description="Target video duration in seconds"
    )
    fps_bounds_min: int = Field(
        default=1, ge=1, le=60, description="Minimum FPS bound for target mode"
    )
    fps_bounds_max: int = Field(
        default=60, ge=1, le=120, description="Maximum FPS bound for target mode"
    )


class VideoGenerationSettingsOptional(BaseModel):
    """Optional version for updates and overrides"""

    video_generation_mode: Optional[VideoGenerationMode] = None
    standard_fps: Optional[int] = Field(None, ge=1, le=120)
    enable_time_limits: Optional[bool] = None
    min_time_seconds: Optional[int] = Field(None, ge=1)
    max_time_seconds: Optional[int] = Field(None, ge=1)
    target_time_seconds: Optional[int] = Field(None, ge=1)
    fps_bounds_min: Optional[int] = Field(None, ge=1, le=60)
    fps_bounds_max: Optional[int] = Field(None, ge=1, le=120)


class VideoAutomationSettings(BaseModel):
    """Shared video automation settings"""

    video_automation_mode: VideoAutomationMode = Field(
        default=VideoAutomationMode.MANUAL,
        description="Video generation automation mode",
    )
    # Keep consistent with database schema
    generation_schedule: Optional[Dict[str, Any]] = Field(
        None, description="Schedule configuration for scheduled mode"
    )
    milestone_config: Optional[Dict[str, Any]] = Field(
        None, description="Milestone configuration for milestone mode"
    )


class VideoAutomationSettingsOptional(BaseModel):
    """Optional version for updates"""

    video_automation_mode: Optional[VideoAutomationMode] = None
    # Keep consistent with database schema
    generation_schedule: Optional[Dict[str, Any]] = None
    milestone_config: Optional[Dict[str, Any]] = None


class CorruptionDetectionSettings(BaseModel):
    """Shared corruption detection settings"""

    corruption_detection_heavy: bool = Field(
        default=False,
        description="Enable advanced computer vision corruption detection",
    )
    # Add corruption fields that should be in main models
    corruption_score: int = Field(
        default=100, ge=0, le=100, description="Corruption score (100 = perfect)"
    )
    is_flagged: bool = Field(
        default=False, description="Whether image is flagged as corrupted"
    )
    lifetime_glitch_count: int = Field(
        default=0, description="Total corruption incidents"
    )
    consecutive_corruption_failures: int = Field(
        default=0, description="Current consecutive corruption failures"
    )


class CorruptionDetectionSettingsOptional(BaseModel):
    """Optional version for updates"""

    corruption_detection_heavy: Optional[bool] = None
    corruption_score: Optional[int] = Field(None, ge=0, le=100)
    is_flagged: Optional[bool] = None


class BaseStats(BaseModel):
    """Base statistics model to reduce duplication"""

    total_images: int = 0
    last_24h_images: int = 0
    success_rate_percent: Optional[float] = None
    storage_used_mb: Optional[float] = None


class CameraHealthStatus(BaseModel):
    """Camera health status model"""

    lifetime_glitch_count: int = 0
    consecutive_corruption_failures: int = 0
    degraded_mode_active: bool = False
    last_degraded_at: Optional[datetime] = None
    corruption_detection_heavy: bool = False
    corruption_logs_count: int = 0
    avg_corruption_score: Optional[float] = None


class TimelapseStatistics(BaseModel):
    """Timelapse statistics model"""

    total_images: int = 0
    total_videos: int = 0
    first_capture_at: Optional[datetime] = None
    last_capture_at: Optional[datetime] = None
    avg_quality_score: Optional[float] = None
    flagged_images: int = 0
    total_storage_bytes: Optional[int] = None
    total_video_storage_bytes: Optional[int] = None


class CameraStatistics(BaseModel):
    """Extended camera statistics model"""

    total_timelapses: int = 0
    total_images: int = 0
    total_videos: int = 0
    last_capture_at: Optional[datetime] = None
    first_capture_at: Optional[datetime] = None
    avg_quality_score: Optional[float] = None
    flagged_images: int = 0
