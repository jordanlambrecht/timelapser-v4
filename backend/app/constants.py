# backend/app/constants.py
"""
Global Constants for Timelapser v4

Centralized location for all application constants to avoid hardcoded values
throughout the codebase.
"""

from typing import Set

# ====================================================================
# FILE TYPE CONSTANTS
# ====================================================================

# Allowed image file extensions
ALLOWED_IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Allowed video file extensions
ALLOWED_VIDEO_EXTENSIONS: Set[str] = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# Allowed archive file extensions
ALLOWED_ARCHIVE_EXTENSIONS: Set[str] = {".zip", ".tar", ".gz"}

# All allowed file extensions
ALL_ALLOWED_EXTENSIONS: Set[str] = (
    ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS | ALLOWED_ARCHIVE_EXTENSIONS
)

# ====================================================================
# SIZE CONSTANTS
# ====================================================================

# Maximum file sizes (in bytes)
MAX_IMAGE_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_VIDEO_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB
MAX_ARCHIVE_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1GB

# Image size variants
IMAGE_SIZE_VARIANTS = ["full", "small", "thumbnail"]

# Thumbnail dimensions
THUMBNAIL_DIMENSIONS = {"thumbnail": (150, 150), "small": (400, 400)}

# ====================================================================
# PAGINATION CONSTANTS
# ====================================================================

# Default pagination values
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 1000
MAX_BULK_OPERATION_ITEMS = 1000

# ====================================================================
# CACHE CONSTANTS
# ====================================================================

# Cache control headers
CACHE_CONTROL_PUBLIC = "public, max-age=3600"
CACHE_CONTROL_PRIVATE = "private, max-age=300"
CACHE_CONTROL_NO_CACHE = "no-cache, no-store, must-revalidate"

# ====================================================================
# STATUS CONSTANTS
# ====================================================================

# Camera statuses
CAMERA_STATUSES = ["active", "inactive", "error", "maintenance"]

# Timelapse statuses
TIMELAPSE_STATUSES = ["running", "paused", "stopped", "completed", "archived"]

# Video statuses
VIDEO_STATUSES = ["pending", "processing", "completed", "failed"]

# Health statuses
HEALTH_STATUSES = ["healthy", "degraded", "unhealthy", "unknown"]

# ====================================================================
# CORRUPTION DETECTION CONSTANTS
# ====================================================================

# Corruption score thresholds
CORRUPTION_SCORE_EXCELLENT = 95
CORRUPTION_SCORE_GOOD = 80
CORRUPTION_SCORE_POOR = 60
CORRUPTION_SCORE_FAILED = 40

# ====================================================================
# API CONSTANTS
# ====================================================================

# API version
API_VERSION = "v4"

# Rate limiting
RATE_LIMIT_PER_MINUTE = 100
RATE_LIMIT_BURST = 20

# ====================================================================
# LOGGING CONSTANTS
# ====================================================================

# Log levels
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Log retention (days)
DEFAULT_LOG_RETENTION_DAYS = 30
MAX_LOG_RETENTION_DAYS = 365

# ====================================================================
# VIDEO GENERATION CONSTANTS
# ====================================================================

# Video generation modes
VIDEO_GENERATION_MODES = ["manual", "per_capture", "scheduled", "milestone"]
VIDEO_QUALITIES = ["low", "medium", "high", "ultra"]

# FPS bounds
MIN_FPS = 1
MAX_FPS = 60
DEFAULT_FPS = 12

# Video duration bounds (seconds)
MIN_VIDEO_DURATION = 1
MAX_VIDEO_DURATION = 3600  # 1 hour
DEFAULT_TARGET_DURATION = 30

# ====================================================================
# TIMEZONE CONSTANTS
# ====================================================================

# Default timezone
DEFAULT_TIMEZONE = "UTC"

# Common timezone aliases
TIMEZONE_ALIASES = {
    "EST": "America/New_York",
    "CST": "America/Chicago",
    "MST": "America/Denver",
    "PST": "America/Los_Angeles",
}
