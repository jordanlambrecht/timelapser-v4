# backend/app/models/shared_models.py
"""
Shared model components to eliminate duplication across models.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, Literal, List
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
    generation_schedule: Optional["GenerationSchedule"] = Field(
        None, description="Schedule configuration for scheduled mode"
    )
    milestone_config: Optional["MilestoneConfig"] = Field(
        None, description="Milestone configuration for milestone mode"
    )


class VideoAutomationSettingsOptional(BaseModel):
    """Optional version for updates"""

    video_automation_mode: Optional[VideoAutomationMode] = None
    generation_schedule: Optional["GenerationSchedule"] = None
    milestone_config: Optional["MilestoneConfig"] = None


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


class VideoGenerationJob(BaseModel):
    """Video generation job model"""

    id: int
    timelapse_id: int
    trigger_type: str
    status: str = "pending"
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    video_path: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class VideoGenerationJobWithDetails(VideoGenerationJob):
    """Video generation job with additional context"""

    timelapse_name: Optional[str] = None
    camera_name: Optional[str] = None


class VideoGenerationJobCreate(BaseModel):
    """Model for creating video generation jobs"""

    timelapse_id: int
    trigger_type: str = "manual"
    settings: Optional[Dict[str, Any]] = None


class VideoStatistics(BaseModel):
    """Video statistics model"""

    total_videos: int = 0
    total_size_bytes: Optional[int] = None
    avg_duration_seconds: Optional[float] = None
    avg_fps: Optional[float] = None
    latest_video_at: Optional[datetime] = None


class TimelapseForCleanup(BaseModel):
    """Timelapse model for cleanup operations"""

    id: int
    camera_id: int
    name: str
    description: Optional[str] = None
    status: str
    completed_at: Optional[datetime] = None
    camera_name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimelapseVideoSettings(BaseModel):
    """Timelapse video generation settings model"""

    video_generation_mode: VideoGenerationMode = VideoGenerationMode.STANDARD
    standard_fps: int = 12
    enable_time_limits: bool = False
    min_time_seconds: Optional[int] = None
    max_time_seconds: Optional[int] = None
    target_time_seconds: Optional[int] = None
    fps_bounds_min: int = 1
    fps_bounds_max: int = 60

    model_config = ConfigDict(from_attributes=True)


# Timelapse scheduling and automation models
class GenerationSchedule(BaseModel):
    """Generation schedule configuration"""

    type: Literal["daily", "weekly", "custom"] = "daily"
    time: str = "18:00"  # HH:MM format
    timezone: str = "UTC"
    enabled: bool = True
    model_config = ConfigDict(from_attributes=True)


class MilestoneConfig(BaseModel):
    """Milestone-based generation configuration"""

    thresholds: List[int] = Field(default_factory=lambda: [100, 500, 1000])
    enabled: bool = True
    reset_on_completion: bool = False
    model_config = ConfigDict(from_attributes=True)


class CorruptionSettings(BaseModel):
    """Global corruption detection settings model"""

    corruption_detection_enabled: bool = True
    corruption_score_threshold: int = Field(default=70, ge=0, le=100)
    corruption_auto_discard_enabled: bool = False
    corruption_auto_disable_degraded: bool = False
    corruption_degraded_consecutive_threshold: int = Field(default=10, ge=1)
    corruption_degraded_time_window_minutes: int = Field(default=30, ge=1)
    corruption_degraded_failure_percentage: int = Field(default=50, ge=0, le=100)

    model_config = ConfigDict(from_attributes=True)



class ThumbnailGenerationResult(BaseModel):
    """Result of thumbnail generation operation"""

    success: bool
    image_id: int
    thumbnail_path: Optional[str] = None
    small_path: Optional[str] = None
    thumbnail_size: Optional[int] = None
    small_size: Optional[int] = None
    error: Optional[str] = None
    processing_time_ms: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ThumbnailRegenerationStatus(BaseModel):
    """Status of thumbnail regeneration process"""

    active: bool = False
    progress: int = 0  # Percentage 0-100
    total_images: int = 0
    completed_images: int = 0
    failed_images: int = 0
    current_image_id: Optional[int] = None
    current_image_name: Optional[str] = None
    estimated_time_remaining_seconds: Optional[int] = None
    started_at: Optional[datetime] = None
    status_message: str = "idle"

    model_config = ConfigDict(from_attributes=True)


class ThumbnailStatistics(BaseModel):
    """Comprehensive thumbnail statistics"""

    total_images: int = 0
    images_with_thumbnails: int = 0
    images_with_small: int = 0
    images_without_thumbnails: int = 0
    thumbnail_coverage_percentage: float = 0.0
    total_thumbnail_storage_mb: float = 0.0
    total_small_storage_mb: float = 0.0
    avg_thumbnail_size_kb: float = 0.0
    avg_small_size_kb: float = 0.0
    last_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ThumbnailOperationResponse(BaseModel):
    """Standard response for thumbnail operations"""

    success: bool
    message: str
    operation: str  # 'generate', 'regenerate', 'cleanup', etc.
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
