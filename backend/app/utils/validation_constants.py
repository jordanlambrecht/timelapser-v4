# backend/app/utils/validation_constants.py
"""
Validation-related constants extracted to break circular imports.

These constants are used by validation_helpers.py and other modules
that need validation patterns without importing the full constants module.
"""

# File name validation
DANGEROUS_CHARS = r'[<>:"|?*\x00-\x1f]'

# URL validation - characters that are dangerous for URLs (excludes ? and : which are valid for query params and ports)
# Using actual character set instead of regex pattern for iteration
DANGEROUS_URL_CHARS = '<>"|*' + ''.join(chr(i) for i in range(0x00, 0x20))

# RTSP URL validation pattern (supports both rtsp:// and rtsps://)
RTSP_URL_PATTERN = r"^rtsps?://[^\s]+$"

# Time window validation pattern
TIME_WINDOW_PATTERN = r"^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$"

# Time formats
ISO_FORMAT = "%Y-%m-%d %H:%M:%S"
ISO_FORMAT_WITH_MICROSECONDS = "%Y-%m-%d %H:%M:%S.%f"

# File size constants
MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# URL validation patterns
HTTP_URL_PATTERN = r"^https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)$"
BASE_URL_PATTERN = r"^https?://[^/\s]+/?$"

# Filename patterns
SAFE_FILENAME_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9\s\-_.()]*$"
IMAGE_FILENAME_PATTERN = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_camera_\d+(?:_timelapse_\d+)?\.(?:jpg|jpeg|png)$"

# Path validation
ALLOWED_PATH_CHARS = r"^[a-zA-Z0-9\-_./\\]+$"
MAX_PATH_LENGTH = 255

# Image file extensions
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

# FPS validation bounds
MIN_FPS = 1
MAX_FPS = 120  # Updated to match video generation capabilities

# Time bounds validation
MAX_TIME_BOUNDS_SECONDS = 86400  # 24 hours in seconds
