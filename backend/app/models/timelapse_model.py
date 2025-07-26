# backend/app/models/timelapse.py

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Literal, Union
from datetime import datetime, date, time

# Import shared components to eliminate duplication
from .shared_models import (
    VideoGenerationMode,
    VideoAutomationMode,
    GenerationSchedule,
    MilestoneConfig,
)
from ..enums import TimelapseStatus


class TimelapseBase(BaseModel):
    camera_id: int = Field(..., description="ID of the associated camera")
    status: TimelapseStatus = Field(
        default=TimelapseStatus.CREATED, description="Timelapse status"
    )


class TimelapseCreateData(BaseModel):
    """Model for creating a new timelapse without requiring camera_id (gets it from query param)"""

    name: Optional[str] = Field(None, description="Custom name for the timelapse")
    auto_stop_at: Optional[datetime] = Field(None, description="Automatic stop time")

    # Capture scheduling
    capture_interval_seconds: int = Field(
        default=300,
        ge=30,
        le=86400,
        description="Capture interval in seconds (30 sec to 24 hours)",
    )

    # Time window configuration
    time_window_type: Literal["none", "time", "sunrise_sunset"] = Field(
        default="none", description="Type of time window control"
    )
    time_window_start: Optional[str] = Field(
        None, description="Custom time window start (HH:MM)"
    )
    time_window_end: Optional[str] = Field(
        None, description="Custom time window end (HH:MM)"
    )
    sunrise_offset_minutes: Optional[int] = Field(
        None, description="Minutes before (-) or after (+) sunrise to start capturing"
    )
    sunset_offset_minutes: Optional[int] = Field(
        None, description="Minutes before (-) or after (+) sunset to stop capturing"
    )
    use_custom_time_window: Optional[bool] = Field(
        False, description="Use custom time window instead of camera default"
    )

    # Video generation settings (optional overrides)
    video_generation_mode: Optional[VideoGenerationMode] = None
    standard_fps: Optional[int] = Field(default=None, ge=1, le=120)
    enable_time_limits: Optional[bool] = None
    min_time_seconds: Optional[int] = Field(default=None, ge=1)
    max_time_seconds: Optional[int] = Field(default=None, ge=1)
    target_time_seconds: Optional[int] = Field(default=None, ge=1)
    fps_bounds_min: Optional[int] = Field(default=None, ge=1, le=60)
    fps_bounds_max: Optional[int] = Field(default=None, ge=1, le=120)

    # Video automation settings (optional overrides)
    video_automation_mode: Optional[VideoAutomationMode] = None
    generation_schedule: Optional[GenerationSchedule] = None
    milestone_config: Optional[MilestoneConfig] = None


class TimelapseCreate(TimelapseBase):
    """Model for creating a new timelapse with optional video settings override"""

    name: Optional[str] = Field(None, description="Custom name for the timelapse")
    auto_stop_at: Optional[datetime] = Field(None, description="Automatic stop time")

    # Capture scheduling
    capture_interval_seconds: int = Field(
        default=300,
        ge=30,
        le=86400,
        description="Capture interval in seconds (30 sec to 24 hours)",
    )

    # Time window configuration
    time_window_type: Literal["none", "time", "sunrise_sunset"] = Field(
        default="none", description="Type of time window control"
    )
    time_window_start: Optional[str] = Field(
        None, description="Custom time window start (HH:MM)"
    )
    time_window_end: Optional[str] = Field(
        None, description="Custom time window end (HH:MM)"
    )
    sunrise_offset_minutes: Optional[int] = Field(
        None, description="Minutes before (-) or after (+) sunrise to start capturing"
    )
    sunset_offset_minutes: Optional[int] = Field(
        None, description="Minutes before (-) or after (+) sunset to stop capturing"
    )
    use_custom_time_window: Optional[bool] = Field(
        False, description="Use custom time window instead of camera default"
    )

    # Video generation settings (with defaults for database requirements)
    video_generation_mode: VideoGenerationMode = Field(
        default=VideoGenerationMode.STANDARD, description="Video generation mode"
    )
    standard_fps: int = Field(default=30, ge=1, le=120, description="Standard FPS")
    enable_time_limits: bool = Field(
        default=False, description="Enable time limits for video generation"
    )
    min_time_seconds: Optional[int] = Field(None, ge=1)
    max_time_seconds: Optional[int] = Field(None, ge=1)
    target_time_seconds: Optional[int] = Field(None, ge=1)
    fps_bounds_min: int = Field(
        default=15, ge=1, le=60, description="Minimum FPS bound"
    )
    fps_bounds_max: int = Field(
        default=60, ge=1, le=120, description="Maximum FPS bound"
    )

    # Video automation settings (with defaults for database requirements)
    video_automation_mode: VideoAutomationMode = Field(
        default=VideoAutomationMode.MANUAL, description="Video automation mode"
    )
    generation_schedule: Optional[GenerationSchedule] = None
    milestone_config: Optional[MilestoneConfig] = None


class TimelapseUpdate(BaseModel):
    """Model for updating a timelapse"""

    status: Optional[TimelapseStatus] = None
    starred: Optional[bool] = Field(
        default=None, description="Whether the timelapse is starred"
    )

    # Capture scheduling
    capture_interval_seconds: Optional[int] = Field(
        default=None, ge=30, le=86400, description="Capture interval in seconds"
    )

    # Time window configuration
    time_window_type: Optional[Literal["none", "time", "sunrise_sunset"]] = None
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    sunrise_offset_minutes: Optional[int] = None
    sunset_offset_minutes: Optional[int] = None
    use_custom_time_window: Optional[bool] = None

    # Video generation settings (optional overrides)
    video_generation_mode: Optional[VideoGenerationMode] = None
    standard_fps: Optional[int] = Field(default=None, ge=1, le=120)
    enable_time_limits: Optional[bool] = None
    min_time_seconds: Optional[int] = Field(default=None, ge=1)
    max_time_seconds: Optional[int] = Field(default=None, ge=1)
    target_time_seconds: Optional[int] = Field(default=None, ge=1)
    fps_bounds_min: Optional[int] = Field(default=None, ge=1, le=60)
    fps_bounds_max: Optional[int] = Field(default=None, ge=1, le=120)

    # Video automation settings (optional overrides)
    video_automation_mode: Optional[VideoAutomationMode] = None
    generation_schedule: Optional[GenerationSchedule] = None
    milestone_config: Optional[MilestoneConfig] = None


class Timelapse(TimelapseBase):
    """Full timelapse model with all database fields"""

    id: int
    name: Optional[str] = None
    start_date: Optional[date] = None
    auto_stop_at: Optional[datetime] = None

    # Capture scheduling
    capture_interval_seconds: int = Field(
        default=300, description="Capture interval in seconds"
    )

    # Time window configuration
    time_window_type: str = "none"
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    sunrise_offset_minutes: Optional[int] = None
    sunset_offset_minutes: Optional[int] = None
    use_custom_time_window: bool = False

    @field_validator("time_window_start", "time_window_end", mode="before")
    @classmethod
    def convert_time_to_string(cls, v):
        """Convert datetime.time objects to HH:MM string format"""
        if v is None:
            return v
        if isinstance(v, time):
            return v.strftime("%H:%M")
        if isinstance(v, str):
            return v
        return str(v)

    image_count: int = 0
    thumbnail_count: int = 0
    small_count: int = 0
    last_capture_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Video generation settings (nullable - inherited from camera)
    video_generation_mode: Optional[VideoGenerationMode] = None
    standard_fps: Optional[int] = None
    enable_time_limits: Optional[bool] = None
    min_time_seconds: Optional[int] = None
    max_time_seconds: Optional[int] = None
    target_time_seconds: Optional[int] = None
    fps_bounds_min: Optional[int] = None
    fps_bounds_max: Optional[int] = None

    # Video automation settings (nullable - inherited from camera)
    video_automation_mode: Optional[VideoAutomationMode] = None
    generation_schedule: Optional[GenerationSchedule] = None
    milestone_config: Optional[MilestoneConfig] = None

    model_config = ConfigDict(from_attributes=True)


class TimelapseWithDetails(Timelapse):
    """Timelapse model with additional details"""

    camera_name: str
