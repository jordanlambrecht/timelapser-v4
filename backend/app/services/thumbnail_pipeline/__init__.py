# backend/app/services/thumbnail_pipeline/__init__.py
"""
Thumbnail Pipeline Module

Comprehensive thumbnail generation system following the corruption pipeline model.
"""

from .thumbnail_pipeline import (
    ThumbnailPipeline,
    create_thumbnail_pipeline,
    create_sync_thumbnail_pipeline,
    create_async_thumbnail_pipeline,
)

from .services import (
    ThumbnailJobService,
    SyncThumbnailJobService,
    ThumbnailPerformanceService,
    SyncThumbnailPerformanceService,
    ThumbnailVerificationService,
    SyncThumbnailVerificationService,
    ThumbnailRepairService,
    SyncThumbnailRepairService,
)

from .generators import (
    ThumbnailGenerator,
    SmallImageGenerator,
    BatchThumbnailGenerator,
)

from .utils import (
    generate_thumbnail,
    generate_small_image,
    validate_image_file,
    calculate_thumbnail_dimensions,
    create_thumbnail_directories,
    generate_thumbnail_filename,
    THUMBNAIL_SIZE,
    SMALL_IMAGE_SIZE,
    THUMBNAIL_QUALITY,
    SMALL_IMAGE_QUALITY,
    SUPPORTED_IMAGE_FORMATS,
    THUMBNAIL_FILE_PREFIX,
    SMALL_FILE_PREFIX,
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