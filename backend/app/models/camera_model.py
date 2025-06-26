# backend/app/models/camera.py

from pydantic import BaseModel, field_validator, Field, ConfigDict
from typing import Optional, Literal, Dict, Any
from datetime import datetime
import re

# Import shared components to eliminate duplication
from .shared_models import VideoGenerationMode, VideoAutomationMode, BaseStats


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

    # Video automation settings
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
        if not v:
            raise ValueError("RTSP URL cannot be empty")

        # Must start with rtsp:// or rtsps://
        if not v.startswith(("rtsp://", "rtsps://")):
            raise ValueError("URL must start with rtsp:// or rtsps://")

        # Prevent injection attacks - no dangerous characters
        dangerous_chars = [";", "&", "|", "`", "$", "(", ")", "<", ">", '"', "'"]
        if any(char in v for char in dangerous_chars):
            raise ValueError("RTSP URL contains invalid characters")

        # Basic URL format validation
        url_pattern = r"^rtsps?://[^\s/$.?#].[^\s]*$"
        if not re.match(url_pattern, v):
            raise ValueError("Invalid RTSP URL format")

        return v

    @field_validator("name")
    @classmethod
    def validate_name(_cls, v: str) -> str:
        """Validate camera name"""
        if not v.strip():
            raise ValueError("Camera name cannot be empty or just whitespace")
        return v.strip()

    @field_validator("min_time_seconds", "max_time_seconds")
    @classmethod
    def validate_time_bounds(_cls, v: Optional[int]) -> Optional[int]:
        """Validate time bounds are reasonable"""
        if v is not None and v > 3600:  # 1 hour max
            raise ValueError("Time limit cannot exceed 3600 seconds (1 hour)")
        return v

    @field_validator("fps_bounds_min", "fps_bounds_max")
    @classmethod
    def validate_fps_bounds(_cls, v: int) -> int:
        """Validate FPS bounds are reasonable"""
        if v < 1 or v > 120:
            raise ValueError("FPS bounds must be between 1 and 120")
        return v

    @field_validator("time_window_start", "time_window_end")
    @classmethod
    def validate_time_window(_cls, v: Optional[str]) -> Optional[str]:
        """Validate time window format (HH:MM:SS)"""
        if v is None:
            return v

        # Check format using regex
        time_pattern = r"^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"
        if not re.match(time_pattern, v):
            raise ValueError("Time must be in HH:MM:SS format (24-hour)")

        return v

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
    standard_fps: Optional[int] = Field(None, ge=1, le=120)
    enable_time_limits: Optional[bool] = None
    min_time_seconds: Optional[int] = Field(None, ge=1)
    max_time_seconds: Optional[int] = Field(None, ge=1)
    target_time_seconds: Optional[int] = Field(None, ge=1)
    fps_bounds_min: Optional[int] = Field(None, ge=1, le=60)
    fps_bounds_max: Optional[int] = Field(None, ge=1, le=120)

    # Video automation settings (all optional)
    video_automation_mode: Optional[VideoAutomationMode] = None
    # Keep consistent with database schema
    generation_schedule: Optional[Dict[str, Any]] = None
    milestone_config: Optional[Dict[str, Any]] = None

    # Corruption detection settings (all optional)
    corruption_detection_heavy: Optional[bool] = None
    corruption_score: Optional[int] = Field(None, ge=0, le=100)
    is_flagged: Optional[bool] = None

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate RTSP URL format and prevent injection"""
        if v is None:
            return v

        if not v:
            raise ValueError("RTSP URL cannot be empty")

        # Must start with rtsp:// or rtsps://
        if not v.startswith(("rtsp://", "rtsps://")):
            raise ValueError("URL must start with rtsp:// or rtsps://")

        # Prevent injection attacks - no dangerous characters
        dangerous_chars = [";", "&", "|", "`", "$", "(", ")", "<", ">", '"', "'"]
        if any(char in v for char in dangerous_chars):
            raise ValueError("RTSP URL contains invalid characters")

        # Basic URL format validation
        url_pattern = r"^rtsps?://[^\s/$.?#].[^\s]*$"
        if not re.match(url_pattern, v):
            raise ValueError("Invalid RTSP URL format")

        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate camera name"""
        if v is None:
            return v
        if not v.strip():
            raise ValueError("Camera name cannot be empty or just whitespace")
        return v.strip()


class Camera(CameraBase):
    """Full camera model with all database fields"""

    id: int
    health_status: Literal["online", "offline", "unknown"] = "unknown"
    last_capture_at: Optional[datetime] = None
    last_capture_success: Optional[bool] = None
    consecutive_failures: int = 0
    next_capture_at: Optional[datetime] = None  # When next capture is scheduled
    active_timelapse_id: Optional[int] = None  # Currently active timelapse
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CameraWithTimelapse(Camera):
    """Camera model with associated timelapse information"""

    timelapse_status: Optional[Literal["running", "stopped", "paused"]] = None
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
            # 🎯 FIXED: Use correct camera-based thumbnail endpoint, not forbidden /api/images/{id}/thumbnail
            return f"/api/cameras/{self.id}/latest-thumbnail"
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
    captured_at: datetime
    file_path: str
    file_size: Optional[int] = None
    day_number: int
    thumbnail_path: Optional[str] = None
    thumbnail_size: Optional[int] = None
    small_path: Optional[str] = None
    small_size: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# Update forward reference
CameraWithLastImage.model_rebuild()


class LogForCamera(BaseModel):
    """Simplified log model for camera relationships"""

    id: int
    timestamp: datetime
    level: str
    message: str
    camera_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class CameraDetailsResponse(BaseModel):
    """Comprehensive camera details response for single endpoint"""

    camera: CameraWithLastImage
    active_timelapse: Optional["Timelapse"] = None
    timelapses: list["Timelapse"] = []
    recent_images: list[ImageForCamera] = []
    videos: list["Video"] = []
    recent_activity: list[LogForCamera] = []
    stats: CameraStats

    model_config = ConfigDict(from_attributes=True)


# Forward reference updates for circular imports
from .timelapse_model import Timelapse
from .video_model import Video

CameraDetailsResponse.model_rebuild()
