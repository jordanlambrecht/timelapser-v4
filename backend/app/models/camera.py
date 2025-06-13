# backend/app/models/camera.py

from pydantic import BaseModel, field_validator, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime, time
import re


class CameraBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Camera name")
    rtsp_url: str = Field(..., description="RTSP stream URL")
    status: Literal["active", "inactive"] = Field(
        default="active", description="Camera status"
    )
    time_window_start: Optional[time] = Field(
        None, description="Start time for capture window"
    )
    time_window_end: Optional[time] = Field(
        None, description="End time for capture window"
    )
    use_time_window: bool = Field(
        default=False, description="Whether to use time windows"
    )

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, v: str) -> str:
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
    def validate_name(cls, v: str) -> str:
        """Validate camera name"""
        if not v.strip():
            raise ValueError("Camera name cannot be empty or just whitespace")
        return v.strip()


class CameraCreate(CameraBase):
    """Model for creating a new camera"""

    pass


class CameraUpdate(BaseModel):
    """Model for updating a camera (all fields optional)"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    rtsp_url: Optional[str] = None
    status: Optional[Literal["active", "inactive"]] = None
    time_window_start: Optional[time] = None
    time_window_end: Optional[time] = None
    use_time_window: Optional[bool] = None

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate RTSP URL format and prevent injection"""
        if v is None:
            return v

        # Use the same validation as CameraBase
        return CameraBase.model_validate({"rtsp_url": v, "name": "temp"}).rtsp_url

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
    last_image_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CameraWithTimelapse(Camera):
    """Camera model with associated timelapse information"""

    timelapse_status: Optional[Literal["running", "stopped", "paused"]] = None
    timelapse_id: Optional[int] = None
