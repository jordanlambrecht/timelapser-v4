# backend/app/services/thumbnail_pipeline/utils/__init__.py
"""
Thumbnail Utility Functions and Constants

Shared utilities for thumbnail pipeline:
- Thumbnail processing utilities
- File management helpers
- Constants and configuration values
"""

from .constants import (
    SMALL_FILE_PREFIX,
    SMALL_IMAGE_QUALITY,
    SMALL_IMAGE_SIZE,
    SUPPORTED_IMAGE_FORMATS,
    THUMBNAIL_FILE_PREFIX,
    THUMBNAIL_QUALITY,
    THUMBNAIL_SIZE,
)
from .thumbnail_utils import (
    calculate_thumbnail_dimensions,
    create_thumbnail_directories,
    generate_small_image,
    generate_thumbnail,
    generate_thumbnail_filename,
    validate_image_file,
)

__all__ = [
    "generate_thumbnail",
    "generate_small_image",
    "validate_image_file",
    "calculate_thumbnail_dimensions",
    "create_thumbnail_directories",
    "generate_thumbnail_filename",
    "THUMBNAIL_SIZE",
    "SMALL_IMAGE_SIZE",
    "THUMBNAIL_QUALITY",
    "SMALL_IMAGE_QUALITY",
    "SUPPORTED_IMAGE_FORMATS",
    "THUMBNAIL_FILE_PREFIX",
    "SMALL_FILE_PREFIX",
]
