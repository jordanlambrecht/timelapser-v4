from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ImageBase(BaseModel):
    camera_id: int = Field(..., description="ID of the associated camera")
    timelapse_id: int = Field(..., description="ID of the associated timelapse")
    file_path: str = Field(..., description="Path to the image file")
    day_number: int = Field(..., ge=1, description="Day number in the timelapse sequence")
    file_size: Optional[int] = Field(None, ge=0, description="File size in bytes")


class ImageCreate(ImageBase):
    """Model for creating a new image record"""
    pass


class Image(ImageBase):
    """Full image model with all database fields"""
    id: int
    captured_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ImageWithDetails(Image):
    """Image model with additional details"""
    camera_name: Optional[str] = None
    timelapse_status: Optional[str] = None

    class Config:
        from_attributes = True
