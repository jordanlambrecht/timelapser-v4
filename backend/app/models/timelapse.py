# backend/app/models/timelapse.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime, date


class TimelapseBase(BaseModel):
    camera_id: int = Field(..., description="ID of the associated camera")
    status: Literal["running", "stopped", "paused", "completed", "archived"] = Field(
        default="stopped", description="Timelapse status"
    )


class TimelapseCreate(TimelapseBase):
    """Model for creating a new timelapse"""
    
    name: Optional[str] = Field(None, description="Custom name for the timelapse")
    auto_stop_at: Optional[datetime] = Field(None, description="Automatic stop time")
    time_window_start: Optional[str] = Field(None, description="Custom time window start (HH:MM)")
    time_window_end: Optional[str] = Field(None, description="Custom time window end (HH:MM)")
    use_custom_time_window: Optional[bool] = Field(False, description="Use custom time window instead of camera default")
    
    # Video generation settings (inherited from camera, can be overridden)
    video_generation_mode: Optional[str] = None
    standard_fps: Optional[int] = Field(None, ge=1, le=120)
    enable_time_limits: Optional[bool] = None
    min_time_seconds: Optional[int] = Field(None, ge=1)
    max_time_seconds: Optional[int] = Field(None, ge=1)
    target_time_seconds: Optional[int] = Field(None, ge=1)
    fps_bounds_min: Optional[int] = Field(None, ge=1, le=60)
    fps_bounds_max: Optional[int] = Field(None, ge=1, le=120)


class TimelapseUpdate(BaseModel):
    """Model for updating a timelapse"""

    status: Optional[Literal["running", "stopped", "paused", "completed", "archived"]] = None
    
    # Video generation settings can be updated
    video_generation_mode: Optional[str] = None
    standard_fps: Optional[int] = Field(None, ge=1, le=120)
    enable_time_limits: Optional[bool] = None
    min_time_seconds: Optional[int] = Field(None, ge=1)
    max_time_seconds: Optional[int] = Field(None, ge=1)
    target_time_seconds: Optional[int] = Field(None, ge=1)
    fps_bounds_min: Optional[int] = Field(None, ge=1, le=60)
    fps_bounds_max: Optional[int] = Field(None, ge=1, le=120)


class Timelapse(TimelapseBase):
    """Full timelapse model with all database fields"""

    id: int
    name: Optional[str] = None
    start_date: Optional[date] = None
    auto_stop_at: Optional[datetime] = None
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    use_custom_time_window: bool = False
    image_count: int = 0
    last_capture_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Video generation settings (nullable - inherited from camera)
    video_generation_mode: Optional[str] = None
    standard_fps: Optional[int] = None
    enable_time_limits: Optional[bool] = None
    min_time_seconds: Optional[int] = None
    max_time_seconds: Optional[int] = None
    target_time_seconds: Optional[int] = None
    fps_bounds_min: Optional[int] = None
    fps_bounds_max: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class TimelapseWithDetails(Timelapse):
    """Timelapse model with additional details"""

    camera_name: str
