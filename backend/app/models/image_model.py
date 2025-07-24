# backend/app/models/image.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class ImageBase(BaseModel):
    camera_id: int = Field(..., description="ID of the associated camera")
    timelapse_id: Optional[int] = Field(
        None, description="ID of the associated timelapse (None for legacy images)"
    )
    file_path: str = Field(..., description="Path to the image file")
    day_number: int = Field(
        ..., ge=0, description="Day number in the timelapse sequence"
    )
    file_size: Optional[int] = Field(None, ge=0, description="File size in bytes")

    # Corruption detection fields (integrated, not separate)
    corruption_score: int = Field(
        default=100, ge=0, le=100, description="Corruption score (100 = perfect)"
    )
    is_flagged: bool = Field(default=False, description="Whether flagged as corrupted")
    corruption_details: Optional[Dict[str, Any]] = Field(
        None, description="Detailed corruption analysis results"
    )

    # Weather data fields for historical accuracy in overlays
    weather_temperature: Optional[float] = Field(
        None, description="Temperature in Celsius at time of capture"
    )
    weather_conditions: Optional[str] = Field(
        None, max_length=255, description="Weather description at time of capture"
    )
    weather_icon: Optional[str] = Field(
        None, max_length=50, description="OpenWeather icon code"
    )
    weather_fetched_at: Optional[datetime] = Field(
        None, description="When weather data was recorded for this image"
    )

    # Overlay tracking fields (added in overlay system)
    overlay_path: Optional[str] = Field(
        None, description="Path to generated overlay image"
    )
    has_valid_overlay: bool = Field(
        default=False, description="Whether image has a valid overlay"
    )
    overlay_updated_at: Optional[datetime] = Field(
        None, description="When overlay was last generated"
    )


class ImageCreate(ImageBase):
    """Model for creating a new image record"""
    
    captured_at: datetime = Field(..., description="When the image was captured")
    corruption_detected: bool = Field(default=False, description="Whether corruption was detected during capture")
    thumbnail_path: Optional[str] = Field(None, description="Path to the thumbnail image file")


class Image(ImageBase):
    """Full image model with all database and computed fields"""

    id: int
    captured_at: datetime
    created_at: datetime
    
    # Optional computed/joined fields
    camera_name: Optional[str] = None
    timelapse_status: Optional[str] = None
    thumbnail_path: Optional[str] = None
    small_path: Optional[str] = None
    thumbnail_size: Optional[int] = None
    small_size: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# class ThumbnailRegenerationResponse(BaseModel):
#     """Response model for thumbnail regeneration"""

#     image_id: int
#     thumbnail_path: Optional[str] = None
#     small_path: Optional[str] = None
#     thumbnail_size: Optional[int] = None
#     small_size: Optional[int] = None
#     thumbnail_generated: bool = False
#     small_generated: bool = False


# class ImageStatisticsResponse(BaseModel):
#     """Response model for image statistics"""

#     total_images: int = 0
#     total_file_size: int = 0
#     average_file_size: float = 0.0
#     corruption_rate: float = 0.0
#     quality_score: float = 100.0
#     date_range: Optional[Dict[str, str]] = None
#     day_range: Optional[Dict[str, int]] = None


# class BulkDownloadResponse(BaseModel):
#     """Response model for bulk download operations"""

#     requested_images: int
#     included_images: int
#     filename: str
#     total_size: Optional[int] = None


# class QualityAssessmentResponse(BaseModel):
#     """Response model for quality assessment"""

#     image_id: int
#     quality_score: int
#     corruption_detected: bool
#     analysis_details: Optional[Dict[str, Any]] = None
#     action_taken: Optional[str] = None
#     processing_time_ms: Optional[int] = None
