# backend/app/services/thumbnail_pipeline/__init__.py
"""
Thumbnail Pipeline Module

Comprehensive thumbnail generation system following the corruption pipeline model.
"""

from .generators import (
    BatchThumbnailGenerator,
    SmallImageGenerator,
    ThumbnailGenerator,
)
from .services import (
    SyncThumbnailJobService,
    SyncThumbnailPerformanceService,
    SyncThumbnailRepairService,
    SyncThumbnailVerificationService,
    ThumbnailJobService,
    ThumbnailPerformanceService,
    ThumbnailRepairService,
    ThumbnailVerificationService,
)
from .thumbnail_pipeline import (
    ThumbnailPipeline,
    create_async_thumbnail_pipeline,
    create_sync_thumbnail_pipeline,
    create_thumbnail_pipeline,
)
from .utils import (
    SMALL_FILE_PREFIX,
    SMALL_IMAGE_QUALITY,
    SMALL_IMAGE_SIZE,
    SUPPORTED_IMAGE_FORMATS,
    THUMBNAIL_FILE_PREFIX,
    THUMBNAIL_QUALITY,
    THUMBNAIL_SIZE,
    calculate_thumbnail_dimensions,
    create_thumbnail_directories,
    generate_small_image,
    generate_thumbnail,
    generate_thumbnail_filename,
    validate_image_file,
)

__all__ = [
    # Main pipeline
    "ThumbnailPipeline",
    "create_thumbnail_pipeline",
    "create_sync_thumbnail_pipeline",
    "create_async_thumbnail_pipeline",
    # Services
    "ThumbnailJobService",
    "SyncThumbnailJobService",
    "ThumbnailPerformanceService",
    "SyncThumbnailPerformanceService",
    "ThumbnailVerificationService",
    "SyncThumbnailVerificationService",
    "ThumbnailRepairService",
    "SyncThumbnailRepairService",
    # Generators
    "ThumbnailGenerator",
    "SmallImageGenerator",
    "BatchThumbnailGenerator",
    # Utils
    "generate_thumbnail",
    "generate_small_image",
    "validate_image_file",
    "calculate_thumbnail_dimensions",
    "create_thumbnail_directories",
    "generate_thumbnail_filename",
    # Constants
    "THUMBNAIL_SIZE",
    "SMALL_IMAGE_SIZE",
    "THUMBNAIL_QUALITY",
    "SMALL_IMAGE_QUALITY",
    "SUPPORTED_IMAGE_FORMATS",
    "THUMBNAIL_FILE_PREFIX",
    "SMALL_FILE_PREFIX",
]
