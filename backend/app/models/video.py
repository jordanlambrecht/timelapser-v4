# backend/app/models/video.py

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Literal, Dict, Any
from datetime import datetime, date


class VideoBase(BaseModel):
    camera_id: int = Field(..., description="ID of the associated camera")
    name: str = Field(..., min_length=1, max_length=255, description="Video name")
    settings: Dict[str, Any] = Field(
        default_factory=dict, description="Video generation settings"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate video name"""
        if not v.strip():
            raise ValueError("Video name cannot be empty or just whitespace")
        return v.strip()


class VideoCreate(VideoBase):
    """Model for creating a new video"""

    pass


class VideoUpdate(BaseModel):
    """Model for updating a video"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    file_path: Optional[str] = None
    status: Optional[Literal["generating", "completed", "failed"]] = None
    settings: Optional[Dict[str, Any]] = None
    image_count: Optional[int] = None
    file_size: Optional[int] = None
    duration_seconds: Optional[float] = None
    images_start_date: Optional[date] = None
    images_end_date: Optional[date] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate video name"""
        if v is None:
            return v
        if not v.strip():
            raise ValueError("Video name cannot be empty or just whitespace")
        return v.strip()


class Video(VideoBase):
    """Full video model with all database fields"""

    id: int
    file_path: Optional[str] = None
    status: Literal["generating", "completed", "failed"] = "generating"
    image_count: Optional[int] = None
    file_size: Optional[int] = None
    duration_seconds: Optional[float] = None
    images_start_date: Optional[date] = None
    images_end_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    
    # Video generation calculation metadata
    calculated_fps: Optional[float] = None
    target_duration: Optional[int] = None
    actual_duration: Optional[float] = None
    fps_was_adjusted: bool = False
    adjustment_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class VideoWithDetails(Video):
    """Video model with additional details"""

    camera_name: str
