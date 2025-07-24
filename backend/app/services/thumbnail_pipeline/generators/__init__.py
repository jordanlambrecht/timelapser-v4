# backend/app/services/thumbnail_pipeline/generators/__init__.py
"""
Thumbnail Generation Components

Specialized components for different types of thumbnail generation:
- ThumbnailGenerator: 200x150 dashboard thumbnails
- SmallImageGenerator: 800x600 medium quality images
- BatchThumbnailGenerator: Bulk processing operations
"""

from .thumbnail_generator import ThumbnailGenerator
from .small_image_generator import SmallImageGenerator
from .batch_thumbnail_generator import BatchThumbnailGenerator

__all__ = [
    "ThumbnailGenerator",
    "SmallImageGenerator",
    "BatchThumbnailGenerator",
]
