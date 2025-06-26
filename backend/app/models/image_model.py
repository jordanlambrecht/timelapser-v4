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
