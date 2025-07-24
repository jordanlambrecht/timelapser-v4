# backend/app/models/camera.py

from pydantic import BaseModel, field_validator, Field, ConfigDict
from typing import Optional, Literal, Sequence, Any, Dict, Union
from datetime import datetime

# Import shared components to eliminate duplication

from ..models.timelapse_model import TimelapseWithDetails
from ..models.image_model import Image
from ..models.log_model import Log
from ..utils.validation_helpers import (
    validate_rtsp_url,
    validate_camera_name,
)


# ============================================================================
# CROP AND ROTATION MODELS
# ============================================================================


class CropSettings(BaseModel):
    """Camera crop settings model"""

    x: int = Field(ge=0, description="Crop X coordinate (top-left)")
    y: int = Field(ge=0, description="Crop Y coordinate (top-left)")
    width: int = Field(gt=0, description="Crop width in pixels")
    height: int = Field(gt=0, description="Crop height in pixels")

    @field_validator("width", "height")
    @classmethod
    def validate_dimensions(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Width and height must be positive")
        return v


class AspectRatioSettings(BaseModel):
    """Camera aspect ratio settings model"""

    enabled: bool = Field(
        default=False, description="Whether aspect ratio adjustment is enabled"
    )
    ratio: Optional[str] = Field(
        None, description="Target aspect ratio (e.g., '16:9', '4:3', '1:1')"
    )
    mode: Literal["crop", "letterbox"] = Field(
        default="crop", description="How to achieve aspect ratio"
    )

    @field_validator("ratio")
    @classmethod
    def validate_ratio(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if ":" not in v:
            raise ValueError(
                "Aspect ratio must be in format 'width:height' (e.g., '16:9')"
            )
        try:
            width_str, height_str = v.split(":")
            width = float(width_str)
            height = float(height_str)
            if width <= 0 or height <= 0:
                raise ValueError("Aspect ratio components must be positive numbers")
        except ValueError:
            raise ValueError("Invalid aspect ratio format")
        return v


class SourceResolution(BaseModel):
    """Original camera resolution before any processing"""

    width: int = Field(gt=0, description="Original width in pixels")
    height: int = Field(gt=0, description="Original height in pixels")
    detected_at: datetime = Field(description="When resolution was detected")

    @field_validator("width", "height")
    @classmethod
    def validate_dimensions(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Resolution dimensions must be positive")
        return v


class CropRotationSettings(BaseModel):
    """Complete crop and rotation settings for a camera"""

    # Rotation settings (preserving existing field)
    rotation: Literal[0, 90, 180, 270] = Field(
        default=0, description="Rotation in degrees"
    )

    # Crop settings
    crop: Optional[CropSettings] = Field(None, description="Crop settings")

    # Aspect ratio settings (Optional with defaults)
    aspect_ratio: Optional[AspectRatioSettings] = Field(
        default=None, description="Aspect ratio settings"
    )

    # Processing order
    processing_order: list[Literal["crop", "rotate", "aspect_ratio"]] = Field(
        default=["crop", "rotate", "aspect_ratio"],
        description="Order of image processing operations",
    )

    # Preview settings
    preview_enabled: bool = Field(
        default=True, description="Whether to show preview in UI"
    )

    @field_validator("processing_order")
    @classmethod
    def validate_processing_order(cls, v: list[str]) -> list[str]:
        valid_operations = {"crop", "rotate", "aspect_ratio"}
        if not set(v).issubset(valid_operations):
            raise ValueError(
                f"Invalid operations in processing order. Valid: {valid_operations}"
            )
        return v


class CropRotationUpdate(BaseModel):
    """Model for updating crop/rotation settings"""

    rotation: Optional[Literal[0, 90, 180, 270]] = None
    crop: Optional[CropSettings] = None
    aspect_ratio: Optional[AspectRatioSettings] = None
    processing_order: Optional[list[Literal["crop", "rotate", "aspect_ratio"]]] = None
    preview_enabled: Optional[bool] = None

    @field_validator("processing_order")
    @classmethod
    def validate_processing_order(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        valid_operations = {"crop", "rotate", "aspect_ratio"}
        if not set(v).issubset(valid_operations):
            raise ValueError(
                f"Invalid operations in processing order. Valid: {valid_operations}"
            )
        return v


# ============================================================================
# CAMERA STATISTICS FIELDS (Now integrated directly into Camera model)
# ============================================================================

# CameraStats class removed - fields moved directly into Camera model


# ============================================================================
# MAIN CAMERA MODELS (Updated with crop/rotation support)
# ============================================================================


class CameraBase(BaseModel):
    """Base camera model with all settings"""

    name: str = Field(..., min_length=1, max_length=255, description="Camera name")
    rtsp_url: str = Field(..., description="RTSP stream URL")
    status: Literal["active", "inactive"] = Field(
        default="active", description="Camera status"
    )

    # Time window, video generation, and video automation settings moved to timelapse entity

    # Image capture settings
    rotation: Literal[0, 90, 180, 270] = Field(
        default=0, description="Camera rotation in degrees (0, 90, 180, 270)"
    )

    # Crop and rotation settings (new unified system)
    crop_rotation_enabled: bool = Field(
        default=False, description="Whether custom crop/rotation settings are enabled"
    )
    crop_rotation_settings: Optional[Dict] = Field(
        default=None, description="JSONB crop, rotation, and aspect ratio settings"
    )
    source_resolution: Optional[Dict] = Field(
        default=None,
        description="Original camera resolution (width, height) before any processing",
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
    # Degraded mode status
    degraded_mode_active: bool = Field(
        default=False, description="Whether camera is in degraded mode"
    )
    last_degraded_at: Optional[datetime] = Field(
        None, description="When camera last entered degraded mode"
    )

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(_cls, v: str) -> str:
        """Validate RTSP URL format and prevent injection"""
        result = validate_rtsp_url(v, allow_none=False)
        assert result is not None  # Type assertion for Pylance
        return result

    @field_validator("name")
    @classmethod
    def validate_name(_cls, v: str) -> str:
        """Validate camera name"""
        result = validate_camera_name(v, allow_none=False)
        assert result is not None  # Type assertion for Pylance
        return result


class CameraCreate(CameraBase):
    """Model for creating a new camera"""

    pass


class CameraUpdate(BaseModel):
    """Model for updating a camera (all fields optional)"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    rtsp_url: Optional[str] = None
    status: Optional[Literal["active", "inactive"]] = None
    active_timelapse_id: Optional[int] = None

    # Image capture settings (optional)
    rotation: Optional[Literal[0, 90, 180, 270]] = None

    # Crop and rotation settings (optional)
    crop_rotation_enabled: Optional[bool] = None
    crop_rotation_settings: Optional[Dict] = None
    source_resolution: Optional[Dict] = None

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
    """Full camera model with all database fields, timelapse info, last image, and statistics"""

    # Core database fields
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

    # Timelapse information (previously from CameraWithTimelapse)
    timelapse_status: Optional[Literal["running", "paused"]] = None
    timelapse_id: Optional[int] = None

    # Last image details (previously from CameraWithLastImage)
    last_image: Optional["ImageForCamera"] = None  # Full image object, not just ID

    # Statistics fields (previously from CameraWithStats, now integrated directly)
    # Clear naming for image counts
    image_count_lifetime: int = 0  # Total images ever captured by this camera
    image_count_active_timelapse: int = (
        0  # Images in currently running/paused timelapse
    )
    # Additional camera-specific stats
    current_timelapse_images: int = (
        0  # Legacy field - same as image_count_active_timelapse
    )
    current_timelapse_name: Optional[str] = None
    total_videos: int = 0
    timelapse_count: int = 0
    total_images: int = 0  # Legacy field for backward compatibility
    first_capture_at: Optional[datetime] = None
    avg_capture_interval_minutes: Optional[float] = None
    days_since_first_capture: Optional[int] = None

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

    model_config = ConfigDict(
        from_attributes=True,
        # Configure timezone-aware datetime handling
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
    )


class ImageForCamera(BaseModel):
    """Simplified image model for camera relationships"""

    id: int
    captured_at: datetime = Field(
        description="Image capture timestamp (timezone-aware)"
    )
    file_path: str
    file_size: Optional[int] = None
    day_number: int
    thumbnail_path: Optional[str] = None
    thumbnail_size: Optional[int] = None
    small_path: Optional[str] = None
    small_size: Optional[int] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
    )


# Update forward reference
Camera.model_rebuild()


class LogForCamera(BaseModel):
    """Simplified log model for camera relationships"""

    id: int
    timestamp: datetime = Field(description="Log timestamp (timezone-aware)")
    level: str
    message: str
    camera_id: Optional[int] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
    )


class CameraDetailsResponse(BaseModel):
    """Comprehensive camera details response for single endpoint"""

    camera: "Camera"  # Now unified - use Camera everywhere
    timelapses: Sequence[TimelapseWithDetails]
    videos: Sequence[Any]  # Adjust as needed
    recent_images: Sequence[Image]
    recent_activity: Sequence[Log]
    model_config = ConfigDict(from_attributes=True)


CameraDetailsResponse.model_rebuild()
