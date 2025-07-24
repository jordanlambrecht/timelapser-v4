# backend/app/services/thumbnail_pipeline/utils/constants.py
"""
Thumbnail Pipeline Constants
"""

# Thumbnail dimensions (width, height)
THUMBNAIL_SIZE = (200, 150)  # Dashboard optimized
SMALL_IMAGE_SIZE = (800, 600)  # Medium quality for modals

# Image quality settings (1-95)
THUMBNAIL_QUALITY = 85
SMALL_IMAGE_QUALITY = 90

# Supported image formats
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}

# File naming prefixes
THUMBNAIL_FILE_PREFIX = "thumb_"
SMALL_FILE_PREFIX = "small_"


# Batch processing settings
DEFAULT_BATCH_SIZE = 10
MAX_CONCURRENT_WORKERS = 4

# Performance settings
DEFAULT_PROCESSING_TIMEOUT = 30  # seconds
MAX_RETRY_ATTEMPTS = 3
