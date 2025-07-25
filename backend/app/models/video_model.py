# backend/app/models/video.py


from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Literal, Dict, Any
from datetime import datetime, date


# Video generation status models
class Progress(BaseModel):
    image_count: Optional[int] = None
    file_size: Optional[int] = None
    duration_seconds: Optional[float] = None


class VideoGenerationStatus(BaseModel):
    video_id: int
    status: str
    job_id: Optional[int] = None
    trigger_type: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    progress: Progress


class VideoGenerationJob(BaseModel):
    id: int
    timelapse_id: int
    trigger_type: Optional[str] = None
    status: str
    settings: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    video_path: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    timelapse_name: Optional[str] = None

    camera_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class VideoBase(BaseModel):
    camera_id: int = Field(..., description="ID of the associated camera")
    name: str = Field(..., min_length=1, max_length=255, description="Video name")
    settings: Dict[str, Any] = Field(
        default_factory=dict, description="Video generation settings"
    )

    @field_validator("name")
    @classmethod
    def validate_name(_cls, v: str) -> str:
        """Validate video name"""
        if not v.strip():
            raise ValueError("Video name cannot be empty or just whitespace")
        return v.strip()


class VideoCreate(VideoBase):
    """Model for creating a new video"""
    
    timelapse_id: int = Field(..., description="ID of the associated timelapse")
    file_path: Optional[str] = Field(None, description="Path to the video file")
    status: Literal["generating", "completed", "failed"] = Field(default="generating", description="Initial video status")
    trigger_type: Optional[Literal["manual", "per_capture", "scheduled", "milestone"]] = Field(default="manual", description="How the video generation was triggered")


class VideoUpdate(BaseModel):
    """Model for updating a video"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    timelapse_id: Optional[int] = Field(None, description="ID of the associated timelapse")
    file_path: Optional[str] = None
    status: Optional[Literal["generating", "completed", "failed"]] = None
    settings: Optional[Dict[str, Any]] = None
    image_count: Optional[int] = None
    file_size: Optional[int] = None
    duration_seconds: Optional[float] = None
    images_start_date: Optional[date] = None
    images_end_date: Optional[date] = None
    trigger_type: Optional[Literal["manual", "per_capture", "scheduled", "milestone"]] = None

    @field_validator("name")
    @classmethod
    def validate_name(_cls, v: Optional[str]) -> Optional[str]:
        """Validate video name"""
        if v is None:
            return v
        if not v.strip():
            raise ValueError("Video name cannot be empty or just whitespace")
        return v.strip()


class Video(VideoBase):
    """Full video model with all database fields"""

    id: int
    timelapse_id: Optional[int] = Field(None, description="ID of the associated timelapse")
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

    # Video automation tracking
    trigger_type: Optional[
        Literal["manual", "per_capture", "scheduled", "milestone"]
    ] = None
    job_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class VideoWithDetails(Video):
    """Video model with additional details"""

    camera_name: str
