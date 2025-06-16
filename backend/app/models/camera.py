# backend/app/models/camera.py

from pydantic import BaseModel, field_validator, Field, ConfigDict
from typing import Optional, Literal, Dict, Any
from datetime import datetime, time
from loguru import logger
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
    next_capture_at: Optional[datetime] = None  # When next capture is scheduled
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
            return f"/api/images/{self.last_image.id}/thumbnail"
        return None


class CameraStats(BaseModel):
    """Camera statistics and metrics"""

    total_images: int = 0
    last_24h_images: int = 0
    avg_capture_interval_minutes: Optional[float] = None
    success_rate_percent: Optional[float] = None
    storage_used_mb: Optional[float] = None


class CameraWithStats(CameraWithLastImage):
    """Camera model with statistics included"""

    stats: CameraStats


# Circular import prevention - define after Camera models
from .image import Image


class ImageForCamera(BaseModel):
    """Simplified image model for camera relationships"""

    id: int
    captured_at: datetime
    file_path: str
    file_size: Optional[int] = None
    day_number: int

    model_config = ConfigDict(from_attributes=True)


# Update forward reference
CameraWithLastImage.model_rebuild()


# Utility functions for transforming database rows to models
def transform_camera_with_image_row(row: Dict[str, Any]) -> CameraWithLastImage:
    """Transform a database row with LATERAL joined image data into a CameraWithLastImage model"""

    # Extract camera data, filtering out last_image_ prefixed fields and timelapse fields
    camera_data = {
        k: v
        for k, v in row.items()
        if not k.startswith("last_image_") and not k.startswith("timelapse_")
    }

    # Add timelapse fields manually
    if "timelapse_status" in row:
        camera_data["timelapse_status"] = row["timelapse_status"]
    if "timelapse_id" in row:
        camera_data["timelapse_id"] = row["timelapse_id"]

    # Create camera instance
    camera = CameraWithLastImage(**camera_data)

    # Add image data if available from LATERAL join
    if row.get("last_image_id") and row.get("last_image_captured_at"):
        camera.last_image = ImageForCamera(
            id=int(row["last_image_id"]),
            captured_at=row["last_image_captured_at"],
            file_path=row["last_image_file_path"],
            file_size=row.get("last_image_file_size"),
            day_number=row["last_image_day_number"],
        )

    return camera


def transform_camera_with_stats_row(
    row: Dict[str, Any], stats: Dict[str, Any]
) -> CameraWithStats:
    """Transform a database row with stats into a CameraWithStats model"""

    # First get the camera with image
    camera_with_image = transform_camera_with_image_row(row)

    # Convert to CameraWithStats and add stats
    camera_with_stats = CameraWithStats(**camera_with_image.model_dump())
    camera_with_stats.stats = CameraStats(**stats)

    return camera_with_stats
