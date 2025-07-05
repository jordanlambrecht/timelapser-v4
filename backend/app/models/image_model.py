# backend/app/models/image.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class ImageBase(BaseModel):
    camera_id: int = Field(..., description="ID of the associated camera")
    timelapse_id: int = Field(..., description="ID of the associated timelapse")
    file_path: str = Field(..., description="Path to the image file")
    day_number: int = Field(
        ..., ge=1, description="Day number in the timelapse sequence"
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


class ImageCreate(ImageBase):
    """Model for creating a new image record"""


class Image(ImageBase):
    """Full image model with all database fields"""

    id: int
    captured_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImageWithDetails(Image):
    """Image model with additional details"""

    camera_name: Optional[str] = None
    timelapse_status: Optional[str] = None
    thumbnail_path: Optional[str] = None
    small_path: Optional[str] = None
    thumbnail_size: Optional[int] = None
    small_size: Optional[int] = None


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
