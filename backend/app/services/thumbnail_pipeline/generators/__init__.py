# backend/app/services/thumbnail_pipeline/generators/__init__.py
"""
Thumbnail Generation Components

Specialized components for different types of thumbnail generation:
- ThumbnailGenerator: 200x150 dashboard thumbnails
- SmallImageGenerator: 800x600 medium quality images
- BatchThumbnailGenerator: Bulk processing operations
"""

from .batch_thumbnail_generator import BatchThumbnailGenerator
from .small_image_generator import SmallImageGenerator
from .thumbnail_generator import ThumbnailGenerator

__all__ = [
    "ThumbnailGenerator",
    "SmallImageGenerator",
    "BatchThumbnailGenerator",
]
