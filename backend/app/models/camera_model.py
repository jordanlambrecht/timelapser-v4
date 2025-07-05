# backend/app/models/camera.py

from pydantic import BaseModel, field_validator, Field, ConfigDict
from typing import Optional, Literal, Sequence, Any
from datetime import datetime, time

# Import shared components to eliminate duplication
from .shared_models import (
    VideoGenerationMode,
    VideoAutomationMode,
    BaseStats,
    GenerationSchedule,
    MilestoneConfig,
)
from ..models.timelapse_model import TimelapseWithDetails
from ..models.image_model import ImageWithDetails
from ..models.log_model import Log
from ..utils.validation_helpers import (
    validate_rtsp_url,
    validate_camera_name,
    validate_time_window_format,
    validate_fps_bounds,
    validate_time_bounds,
)
from ..constants import (
    MIN_FPS,
    MAX_FPS,
    MAX_TIME_BOUNDS_SECONDS,
    TIME_WINDOW_PATTERN,
)


class CameraBase(BaseModel):
    """Base camera model with all settings"""

    name: str = Field(..., min_length=1, max_length=255, description="Camera name")
    rtsp_url: str = Field(..., description="RTSP stream URL")
    status: Literal["active", "inactive"] = Field(
        default="active", description="Camera status"
    )
    time_window_start: Optional[str] = Field(
        None, description="Start time for capture window (HH:MM:SS format)"
    )
    time_window_end: Optional[str] = Field(
        None, description="End time for capture window (HH:MM:SS format)"
    )
    use_time_window: bool = Field(
        default=False, description="Whether to use time windows"
    )

    # Video generation settings (using composition)
    video_generation_mode: VideoGenerationMode = Field(
        default=VideoGenerationMode.STANDARD, description="Video generation mode"
    )
    standard_fps: int = Field(
        default=12, ge=MIN_FPS, le=MAX_FPS, description="Standard FPS for video generation"
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
        default=MIN_FPS, ge=MIN_FPS, le=60, description="Minimum FPS bound for target mode"
    )
    fps_bounds_max: int = Field(
        default=60, ge=MIN_FPS, le=MAX_FPS, description="Maximum FPS bound for target mode"
    )

    # Video automation settings
    video_automation_mode: VideoAutomationMode = Field(
        default=VideoAutomationMode.MANUAL,
        description="Video generation automation mode",
    )
    generation_schedule: Optional[GenerationSchedule] = Field(
        None, description="Schedule configuration for scheduled mode"
    )
    milestone_config: Optional[MilestoneConfig] = Field(
        None, description="Milestone configuration for milestone mode"
    )

    # Corruption detection settings
    corruption_detection_heavy: bool = Field(
        default=False,
        description="Enable advanced computer vision corruption detection",
    )
    corruption_score: int = Field(
        default=100, ge=0, le=100, description="Corruption score (100 = perfect)"
    )
    is_flagged: bool = Field(default=False, description="Whether flagged as corrupted")
    lifetime_glitch_count: int = Field(
        default=0, description="Total corruption incidents"
    )
    consecutive_corruption_failures: int = Field(
        default=0, description="Current consecutive corruption failures"
    )

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(_cls, v: str) -> str:
        """Validate RTSP URL format and prevent injection"""
        return validate_rtsp_url(v, allow_none=False)

    @field_validator("name")
    @classmethod
    def validate_name(_cls, v: str) -> str:
        """Validate camera name"""
        return validate_camera_name(v, allow_none=False)

    @field_validator("min_time_seconds", "max_time_seconds")
    @classmethod
    def validate_time_bounds_field(_cls, v: Optional[int]) -> Optional[int]:
        """Validate time bounds are reasonable"""
        return validate_time_bounds(v, MAX_TIME_BOUNDS_SECONDS)

    @field_validator("fps_bounds_min", "fps_bounds_max")
    @classmethod
    def validate_fps_bounds_field(_cls, v: int) -> int:
        """Validate FPS bounds are reasonable"""
        return validate_fps_bounds(v, MIN_FPS, MAX_FPS)

    @field_validator("time_window_start", "time_window_end", mode='before')
    @classmethod
    def convert_time_to_string(cls, v: Optional[str | time]) -> Optional[str]:
        """Convert datetime.time objects to HH:MM:SS string format"""
        if v is None:
            return v
        if isinstance(v, time):
            return v.strftime('%H:%M:%S')
        if isinstance(v, str):
            return v
        return str(v)

    @field_validator("time_window_start", "time_window_end")
    @classmethod
    def validate_time_window(_cls, v: Optional[str]) -> Optional[str]:
        """Validate time window format (HH:MM:SS)"""
        return validate_time_window_format(v)

    def validate_video_settings(self) -> None:
        """Validate video generation settings consistency"""
        # Validate time limits consistency
        if (
            self.min_time_seconds is not None
            and self.max_time_seconds is not None
            and self.min_time_seconds >= self.max_time_seconds
        ):
            raise ValueError("Minimum time must be less than maximum time")

        # Validate FPS bounds consistency
        if self.fps_bounds_min >= self.fps_bounds_max:
            raise ValueError("Minimum FPS bound must be less than maximum FPS bound")

        # Validate target mode requirements
        if (
            self.video_generation_mode == VideoGenerationMode.TARGET
            and self.target_time_seconds is None
        ):
            raise ValueError("Target time must be specified for target mode")


class CameraCreate(CameraBase):
    """Model for creating a new camera"""

    pass


class CameraUpdate(BaseModel):
    """Model for updating a camera (all fields optional)"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    rtsp_url: Optional[str] = None
    status: Optional[Literal["active", "inactive"]] = None
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    use_time_window: Optional[bool] = None
    active_timelapse_id: Optional[int] = None

    # Video generation settings (all optional)
    video_generation_mode: Optional[VideoGenerationMode] = None
    standard_fps: Optional[int] = Field(None, ge=MIN_FPS, le=MAX_FPS)
    enable_time_limits: Optional[bool] = None
    min_time_seconds: Optional[int] = Field(None, ge=1)
    max_time_seconds: Optional[int] = Field(None, ge=1)
    target_time_seconds: Optional[int] = Field(None, ge=1)
    fps_bounds_min: Optional[int] = Field(None, ge=MIN_FPS, le=60)
    fps_bounds_max: Optional[int] = Field(None, ge=MIN_FPS, le=MAX_FPS)

    # Video automation settings (all optional)
    video_automation_mode: Optional[VideoAutomationMode] = None
    generation_schedule: Optional[GenerationSchedule] = None
    milestone_config: Optional[MilestoneConfig] = None

    # Corruption detection settings (all optional)
    corruption_detection_heavy: Optional[bool] = None
    corruption_score: Optional[int] = Field(None, ge=0, le=100)
    is_flagged: Optional[bool] = None

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate RTSP URL format and prevent injection"""
        return validate_rtsp_url(v, allow_none=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate camera name"""
        return validate_camera_name(v, allow_none=True)


class Camera(CameraBase):
    """Full camera model with all database fields"""

    id: int
    health_status: Literal["online", "offline", "unknown"] = "unknown"
    last_capture_at: Optional[datetime] = Field(
        None, description="Last successful capture timestamp (timezone-aware)"
    )
    last_capture_success: Optional[bool] = None
    consecutive_failures: int = 0
    next_capture_at: Optional[datetime] = Field(
        None, description="Next scheduled capture timestamp (timezone-aware)"
    )
    active_timelapse_id: Optional[int] = None  # Currently active timelapse
    created_at: datetime = Field(description="Creation timestamp (timezone-aware)")
    updated_at: datetime = Field(description="Last update timestamp (timezone-aware)")

    model_config = ConfigDict(
        from_attributes=True,
        # Configure timezone-aware datetime handling
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )


class CameraWithTimelapse(Camera):
    """Camera model with associated timelapse information"""

    timelapse_status: Optional[Literal["running", "paused"]] = None
    timelapse_id: Optional[int] = None


class CameraWithLastImage(CameraWithTimelapse):
    """Camera model with full last image details"""

    last_image: Optional["ImageForCamera"] = None  # Full image object, not just ID

    @property
    def has_preview_image(self) -> bool:
        """Check if camera has a preview image available"""
        return self.last_image is not None

    @property
    def preview_image_url(self) -> Optional[str]:
        """Get the preview image URL if available"""
        if self.last_image:
            # ✅ FIXED: Use unified latest-image system endpoint
            return f"/api/cameras/{self.id}/latest-image/thumbnail"
        return None


class CameraStats(BaseStats):
    """Enhanced camera statistics extending base stats"""

    avg_capture_interval_minutes: Optional[float] = None
    # Additional camera-specific stats
    current_timelapse_images: int = 0
    current_timelapse_name: Optional[str] = None
    total_videos: int = 0
    timelapse_count: int = 0
    days_since_first_capture: Optional[int] = None


class CameraWithStats(CameraWithLastImage):
    """Camera model with statistics included"""

    stats: CameraStats


class ImageForCamera(BaseModel):
    """Simplified image model for camera relationships"""

    id: int
    captured_at: datetime = Field(description="Image capture timestamp (timezone-aware)")
    file_path: str
    file_size: Optional[int] = None
    day_number: int
    thumbnail_path: Optional[str] = None
    thumbnail_size: Optional[int] = None
    small_path: Optional[str] = None
    small_size: Optional[int] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )


# Update forward reference
CameraWithLastImage.model_rebuild()


class LogForCamera(BaseModel):
    """Simplified log model for camera relationships"""

    id: int
    timestamp: datetime = Field(description="Log timestamp (timezone-aware)")
    level: str
    message: str
    camera_id: Optional[int] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )


class CameraDetailsResponse(BaseModel):
    """Comprehensive camera details response for single endpoint"""

    camera: CameraWithLastImage
    stats: CameraStats
    timelapses: Sequence[TimelapseWithDetails]
    videos: Sequence[Any]  # Adjust as needed
    recent_images: Sequence[ImageWithDetails]
    recent_activity: Sequence[Log]

    model_config = ConfigDict(from_attributes=True)


# Forward reference updates for circular imports
from .timelapse_model import Timelapse
from .video_model import Video

CameraDetailsResponse.model_rebuild()
