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


class TimelapseUpdate(BaseModel):
    """Model for updating a timelapse"""

    status: Optional[Literal["running", "stopped", "paused", "completed", "archived"]] = None


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

    model_config = ConfigDict(from_attributes=True)


class TimelapseWithDetails(Timelapse):
    """Timelapse model with additional details"""

    camera_name: str
