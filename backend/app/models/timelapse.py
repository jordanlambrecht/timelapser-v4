from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, date


class TimelapseBase(BaseModel):
    camera_id: int = Field(..., description="ID of the associated camera")
    status: Literal["running", "stopped", "paused"] = Field(default="stopped", description="Timelapse status")


class TimelapseCreate(TimelapseBase):
    """Model for creating a new timelapse"""
    pass


class TimelapseUpdate(BaseModel):
    """Model for updating a timelapse"""
    status: Optional[Literal["running", "stopped", "paused"]] = None


class Timelapse(TimelapseBase):
    """Full timelapse model with all database fields"""
    id: int
    start_date: Optional[date] = None
    image_count: int = 0
    last_capture_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TimelapseWithDetails(Timelapse):
    """Timelapse model with additional details"""
    camera_name: str

    class Config:
        from_attributes = True
