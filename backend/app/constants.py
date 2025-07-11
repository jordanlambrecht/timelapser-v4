# backend/app/constants.py
"""
Global Constants for Timelapser v4

Centralized location for all application constants to avoid hardcoded values
throughout the codebase.
"""

from typing import Set, Literal

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

# Thumbnail generation modes
THUMBNAIL_GENERATION_MODE_DISABLED = "disabled"
THUMBNAIL_GENERATION_MODE_LATEST = "latest"
THUMBNAIL_GENERATION_MODE_ALL = "all"

# Thumbnail processing dimensions (optimized for performance)
THUMBNAIL_SIZE = (200, 150)  # Small for dashboard cards
SMALL_SIZE = (800, 600)  # Medium for detail pages

# Thumbnail quality settings
THUMBNAIL_QUALITY_FULL = 90  # High quality for full images
THUMBNAIL_QUALITY_SMALL = 80  # Reduced from 85 for faster processing
THUMBNAIL_QUALITY_THUMBNAIL = 70  # Reduced from 75 for speed

# Thumbnail processing settings
THUMBNAIL_PIL_OPTIMIZATION_ENABLED = True
THUMBNAIL_WEBP_SUPPORT_ENABLED = False  # Disabled for compatibility
THUMBNAIL_PROGRESSIVE_JPEG_ENABLED = True
THUMBNAIL_MAX_IMAGE_DIMENSION = 4096  # Max dimension before downscaling
THUMBNAIL_MEMORY_EFFICIENT_RESIZE = True

# Thumbnail file naming
THUMBNAIL_SIZE_PREFIX_THUMB = "thumb"
THUMBNAIL_SIZE_PREFIX_SMALL = "small"
THUMBNAIL_FILE_EXTENSION = ".jpg"
THUMBNAIL_IMAGE_FORMAT = "JPEG"

# Thumbnail optimization thresholds
THUMBNAIL_SMALL_SIZE_THRESHOLD = 200  # For very small thumbnails
THUMBNAIL_SMALL_QUALITY_REDUCTION = 5  # Quality reduction for small thumbnails
THUMBNAIL_MIN_QUALITY = 60  # Minimum quality for small thumbnails

# Thumbnail directory structure
THUMBNAIL_DIR_CAMERAS = "cameras"
THUMBNAIL_DIR_THUMBNAILS = "thumbnails"
THUMBNAIL_DIR_SMALL = "small"
THUMBNAIL_DIR_SMALLS = "smalls"  # New structure uses "smalls" instead of "small"
THUMBNAIL_CAMERA_PREFIX = "camera-"
THUMBNAIL_TIMELAPSE_PREFIX = "timelapse-"

# ====================================================================
# PAGINATION CONSTANTS
# ====================================================================

# Default pagination values
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 1000
MAX_BULK_OPERATION_ITEMS = 1000
DEFAULT_CAMERA_IMAGES_LIMIT = 10
DEFAULT_TIMELAPSE_IMAGES_LIMIT = 10000

# ====================================================================
# CACHE CONSTANTS
# ====================================================================

# Cache control headers
CACHE_CONTROL_PUBLIC = "public, max-age=3600"
CACHE_CONTROL_PRIVATE = "private, max-age=300"
CACHE_CONTROL_NO_CACHE = "no-cache, no-store, must-revalidate"

# Service cache TTL (seconds)
DEFAULT_CAMERA_SERVICE_CACHE_TTL = 15

# ====================================================================
# STATUS CONSTANTS
# ====================================================================

# Camera statuses
CAMERA_STATUSES = ["active", "inactive", "error", "maintenance"]

# Timelapse statuses
TIMELAPSE_STATUSES = ["running", "paused", "completed", "archived"]
TIMELAPSE_STATUS_RUNNING = "running"
TIMELAPSE_STATUS_PAUSED = "paused"
TIMELAPSE_STATUS_COMPLETED = "completed"
TIMELAPSE_STATUS_ARCHIVED = "archived"

# Timelapse status type
TimelapseStatus = Literal["running", "paused", "completed", "archived"]

# Video statuses
VIDEO_STATUSES = ["pending", "processing", "completed", "failed"]

# Health statuses
HEALTH_STATUSES = ["healthy", "degraded", "unhealthy", "unknown"]

# ====================================================================
# ERROR MESSAGES
# ====================================================================

# Camera error messages
CAMERA_NOT_FOUND = "Camera not found"
CAMERA_CONNECTION_FAILED = "Camera connection test failed"
CAMERA_CAPTURE_FAILED = "Manual capture failed"
CAMERA_OFFLINE = "Camera is offline and cannot capture images"

# Timelapse error messages
TIMELAPSE_NOT_FOUND = "Timelapse not found"
TIMELAPSE_NOT_ACTIVE = "No active timelapse found for this camera"

# Image error messages
IMAGE_NOT_FOUND = "Image not found"
NO_IMAGES_FOUND = "No images found for camera"

# Video error messages
VIDEO_NOT_FOUND = "Video not found"
VIDEO_GENERATION_FAILED = "Video generation failed"

# File error messages
FILE_NOT_FOUND = "File not found"
FILE_ACCESS_DENIED = "Access denied"

# General error messages
OPERATION_FAILED = "Operation failed"
INVALID_REQUEST_DATA = "Invalid request data"
INSUFFICIENT_PERMISSIONS = "Insufficient permissions"

# ====================================================================
# SUCCESS MESSAGES
# ====================================================================

# Camera success messages
CAMERA_CREATED_SUCCESS = "Camera created successfully"
CAMERA_UPDATED_SUCCESS = "Camera updated successfully"
CAMERA_DELETED_SUCCESS = "Camera deleted successfully"
CAMERA_STATUS_UPDATED_SUCCESS = "Camera status updated successfully"
CAMERA_HEALTH_UPDATED_SUCCESS = "Camera health updated successfully"
CAMERA_CONNECTION_SUCCESS = "Camera connection successful"
CAMERA_CAPTURE_SUCCESS = "Manual capture triggered successfully"

# General success messages
OPERATION_SUCCESS = "Operation completed successfully"

# ====================================================================
# CORRUPTION DETECTION CONSTANTS
# ====================================================================

# Corruption score thresholds
CORRUPTION_SCORE_EXCELLENT = 95
CORRUPTION_SCORE_GOOD = 80
CORRUPTION_SCORE_POOR = 60
CORRUPTION_SCORE_FAILED = 40

# Corruption detection defaults
DEFAULT_CORRUPTION_HISTORY_HOURS = 24
DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS = 90
DEFAULT_CORRUPTION_LOGS_PAGE_SIZE = 50
MAX_CORRUPTION_LOGS_PAGE_SIZE = 200

# Corruption auto-discard thresholds
CORRUPTION_CRITICAL_THRESHOLD = 90
CORRUPTION_FAST_CRITICAL_THRESHOLD = 95
CORRUPTION_HEAVY_CRITICAL_THRESHOLD = 95

# ====================================================================
# WEATHER SYSTEM CONSTANTS
# ====================================================================

# OpenWeather API configuration
OPENWEATHER_API_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_API_TIMEOUT = 10  # seconds
OPENWEATHER_API_UNITS = "metric"

# Weather failure thresholds
WEATHER_MAX_CONSECUTIVE_FAILURES = 4
WEATHER_FAILURE_RETRY_INTERVAL = 300  # 5 minutes in seconds

# Weather data refresh intervals
WEATHER_REFRESH_INTERVAL_HOURS = 1
WEATHER_CACHE_TTL_HOURS = 2

# Weather validation messages
WEATHER_API_KEY_VALID = "API key is valid"
WEATHER_API_KEY_INVALID = "Invalid API key"
WEATHER_LOCATION_INVALID = "Invalid location coordinates"
WEATHER_CONNECTION_ERROR = "Connection error"
WEATHER_REFRESH_SKIPPED_LOCATION = "Weather refresh skipped: Location not configured"
WEATHER_REFRESH_SKIPPED_DISABLED = "Weather functionality disabled, skipping refresh"
WEATHER_REFRESH_MISSING_SETTINGS = (
    "Weather refresh skipped: Missing required settings (lat/lng/api_key)"
)

# Health scoring penalties and thresholds
HEALTH_DEGRADED_MODE_PENALTY = 50
HEALTH_CONSECUTIVE_FAILURES_HIGH_THRESHOLD = 5
HEALTH_CONSECUTIVE_FAILURES_HIGH_PENALTY = 30
HEALTH_CONSECUTIVE_FAILURES_MEDIUM_THRESHOLD = 2
HEALTH_CONSECUTIVE_FAILURES_MEDIUM_PENALTY = 15
HEALTH_POOR_QUALITY_THRESHOLD = 50
HEALTH_POOR_QUALITY_PENALTY = 20
HEALTH_AVERAGE_QUALITY_THRESHOLD = 70
HEALTH_AVERAGE_QUALITY_PENALTY = 10
HEALTH_HIGH_DETECTION_THRESHOLD = 20
HEALTH_HIGH_DETECTION_PENALTY = 15

# Corruption test default settings
DEFAULT_CORRUPTION_TEST_THRESHOLD = 50
DEFAULT_AUTO_DISCARD_THRESHOLD = 75
DEFAULT_FAST_WEIGHT = 0.7
DEFAULT_HEAVY_WEIGHT = 0.3

# Corruption worker integration defaults
DEFAULT_CORRUPTION_RETRY_ENABLED = True
DEFAULT_CORRUPTION_FALLBACK_SCORE = 100

# ====================================================================
# API CONSTANTS
# ====================================================================

# API version
API_VERSION = "v4"

# Application info
APPLICATION_NAME = "timelapser-api"
APPLICATION_VERSION = "4.0.0"

# Rate limiting
RATE_LIMIT_PER_MINUTE = 100
RATE_LIMIT_BURST = 20

# ====================================================================
# HEALTH CHECK CONSTANTS
# ====================================================================

# Health check response times (milliseconds)
HEALTH_DB_LATENCY_WARNING = 1000  # Warn if DB latency > 1 second
HEALTH_DB_LATENCY_ERROR = 5000  # Error if DB latency > 5 seconds

# System resource thresholds
HEALTH_CPU_WARNING = 90.0  # CPU usage warning threshold
HEALTH_CPU_ERROR = 95.0  # CPU usage error threshold
HEALTH_MEMORY_WARNING = 90.0  # Memory usage warning threshold
HEALTH_MEMORY_ERROR = 95.0  # Memory usage error threshold
HEALTH_DISK_WARNING = 90.0  # Disk usage warning threshold (used %)
HEALTH_DISK_ERROR = 95.0  # Disk usage error threshold (used %)

# Video queue thresholds
HEALTH_VIDEO_QUEUE_WARNING = 50  # Warn if pending jobs exceed this
HEALTH_VIDEO_QUEUE_ERROR = 100  # Error if pending jobs exceed this

# ====================================================================
# LOGGING CONSTANTS
# ====================================================================

# Log levels
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Log retention (days)
DEFAULT_LOG_RETENTION_DAYS = 30
MAX_LOG_RETENTION_DAYS = 365

# Log pagination constants
DEFAULT_LOG_PAGE_SIZE = 100
MAX_LOG_PAGE_SIZE = 1000
BULK_LOG_PAGE_SIZE = 10000

# Log UI constants
LOG_SEARCH_DEBOUNCE_MS = 500  # 500ms debounce for log search input

# ====================================================================
# VIDEO GENERATION CONSTANTS
# ====================================================================

# Video generation modes
VIDEO_GENERATION_MODES = ["manual", "per_capture", "scheduled", "milestone"]
VIDEO_AUTOMATION_MODES = ["manual", "per_capture", "scheduled", "milestone"]
VIDEO_QUALITIES = ["low", "medium", "high", "ultra"]

# FPS bounds
MIN_FPS = 1
MAX_FPS = 120  # Updated to match video generation capabilities
DEFAULT_FPS = 12

# Timelapse default FPS settings
DEFAULT_TIMELAPSE_STANDARD_FPS = 30
DEFAULT_TIMELAPSE_FPS_BOUNDS_MIN = 15
DEFAULT_TIMELAPSE_FPS_BOUNDS_MAX = 60

# Video duration bounds (seconds)
MIN_VIDEO_DURATION = 1
MAX_VIDEO_DURATION = 3600  # 1 hour
DEFAULT_TARGET_DURATION = 30

# Video generation job statuses
VIDEO_JOB_STATUSES = ["pending", "processing", "completed", "failed", "cancelled"]

# Video generation priorities
VIDEO_JOB_PRIORITIES = ["low", "medium", "high", "urgent"]

# Video generation limits
MAX_CONCURRENT_VIDEO_JOBS = 3
VIDEO_QUEUE_WARNING_THRESHOLD = 50
VIDEO_QUEUE_ERROR_THRESHOLD = 100
MAX_VIDEO_JOB_TIMEOUT_MINUTES = 30

# Video automation health statuses
VIDEO_AUTOMATION_HEALTH_STATUSES = [
    "healthy",
    "degraded",
    "unhealthy",
    "overloaded",
    "unknown",
]

# Video service constants
DEFAULT_VIDEO_CLEANUP_DAYS = 30
DEFAULT_VIDEO_ARCHIVE_DIRECTORY = "archive/videos"
DEFAULT_VIDEO_GENERATION_PRIORITY = "medium"

# Image retention constants
DEFAULT_IMAGE_RETENTION_DAYS = 30

# ====================================================================
# DASHBOARD CONSTANTS
# ====================================================================

# Dashboard query defaults
DEFAULT_DASHBOARD_QUALITY_TREND_DAYS = 7

# ====================================================================
# CAPTURE & RETRY CONSTANTS
# ====================================================================

# Capture settings
DEFAULT_CAPTURE_INTERVAL_SECONDS = 300  # 5 minutes
MIN_CAPTURE_INTERVAL_SECONDS = 30  # 30 seconds minimum
MAX_CAPTURE_INTERVAL_SECONDS = 3600  # 1 hour maximum

# Capture retry settings
DEFAULT_MAX_RETRIES = 3
DEFAULT_IMAGE_EXTENSION = ".jpg"
GENERATE_ALL_THUMBNAIL_SIZES = True

# RTSP capture settings
DEFAULT_RTSP_QUALITY = 85
DEFAULT_RTSP_TIMEOUT_SECONDS = 10
DEFAULT_CORRUPTION_SCORE = 100
DEFAULT_IS_FLAGGED = False

# Scheduling service settings
DEFAULT_CAPTURE_GRACE_PERIOD_SECONDS = 5

# Exponential backoff base (seconds)
RETRY_BACKOFF_BASE = 2

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

# ====================================================================
# EVENT CONSTANTS
# ====================================================================

# Camera events
EVENT_CAMERA_CREATED = "camera_created"
EVENT_CAMERA_UPDATED = "camera_updated"
EVENT_CAMERA_DELETED = "camera_deleted"
EVENT_CAMERA_STATUS_UPDATED = "camera_status_updated"
EVENT_CAMERA_HEALTH_UPDATED = "camera_health_updated"

# Timelapse events
EVENT_TIMELAPSE_CREATED = "timelapse_created"
EVENT_TIMELAPSE_UPDATED = "timelapse_updated"
EVENT_TIMELAPSE_COMPLETED = "timelapse_completed"
EVENT_TIMELAPSE_ARCHIVED = "timelapse_archived"
EVENT_TIMELAPSE_HEALTH_MONITORED = "timelapse_health_monitored"
EVENT_TIMELAPSE_STATISTICS_UPDATED = "timelapse_statistics_updated"

# Image events
EVENT_IMAGE_CAPTURED = "image_captured"
EVENT_IMAGE_PROCESSED = "image_processed"
EVENT_IMAGE_CORRUPTED = "image_corrupted"

# Corruption detection events
EVENT_CORRUPTION_DEGRADED_MODE_RESET = "corruption_degraded_mode_reset"
EVENT_CORRUPTION_TEST_COMPLETED = "corruption_test_completed"
EVENT_CORRUPTION_HEALTH_UPDATED = "corruption_health_updated"

# Video events
EVENT_VIDEO_JOB_QUEUED = "video_job_queued"
EVENT_VIDEO_JOB_STARTED = "video_job_started"
EVENT_VIDEO_JOB_COMPLETED = "video_job_completed"
EVENT_VIDEO_GENERATED = "video_generated"

# System events
EVENT_SETTING_UPDATED = "setting_updated"
EVENT_SETTING_DELETED = "setting_deleted"
EVENT_HEALTH_CHECK_COMPLETED = "health_check_completed"
EVENT_SUNRISE_SUNSET_UPDATED = "sunrise_sunset_updated"
EVENT_WEATHER_UPDATED = "weather_updated"
EVENT_AUDIT_TRAIL_CREATED = "audit_trail_created"

# Time window events
EVENT_TIME_WINDOW_VALIDATED = "time_window_validated"
EVENT_TIME_WINDOW_STATUS_CALCULATED = "time_window_status_calculated"
EVENT_CAPTURE_COUNT_ESTIMATED = "capture_count_estimated"
EVENT_LOG_CLEANUP_COMPLETED = "log_cleanup_completed"

# ====================================================================
# CORRUPTION ACTION CONSTANTS
# ====================================================================

# Corruption detection actions
CORRUPTION_ACTION_SAVED = "saved"
CORRUPTION_ACTION_DISCARDED = "discarded"
CORRUPTION_ACTION_RETRIED = "retried"
CORRUPTION_ACTION_FLAGGED = "flagged"

# Corruption detection modes
CORRUPTION_DETECTION_FAST = "fast"
CORRUPTION_DETECTION_HEAVY = "heavy"
CORRUPTION_DETECTION_BOTH = "both"

# ====================================================================
# OVERLAY CONSTANTS
# ====================================================================

# Video overlay positions
OVERLAY_POSITION_TOP_LEFT = "top-left"
OVERLAY_POSITION_TOP_RIGHT = "top-right"
OVERLAY_POSITION_BOTTOM_LEFT = "bottom-left"
OVERLAY_POSITION_BOTTOM_RIGHT = "bottom-right"
OVERLAY_POSITION_CENTER = "center"

# Default overlay settings
DEFAULT_OVERLAY_SETTINGS = {
    "enabled": True,
    "position": OVERLAY_POSITION_BOTTOM_RIGHT,
    "font_size": 48,
    "font_color": "white",
    "background_color": "black@0.5",
    "format": "Day {day}",
}

# Overlay template formats
OVERLAY_FORMAT_DAY_ONLY = "Day {day}"
OVERLAY_FORMAT_DAY_TEMP = "Day {day} • {temperature}°C"
OVERLAY_FORMAT_DAY_WEATHER = "Day {day} • {temperature}°C • {weather}"
OVERLAY_FORMAT_WEATHER_DETAILED = (
    "{temperature}°C • {weather} • {humidity}% • {pressure}hPa"
)

# ====================================================================
# WORKER CONFIGURATION CONSTANTS
# ====================================================================

# Scheduler job configuration
# Increased from 1 to 3 to prevent "maximum number of running instances reached"
# errors when jobs take longer than their interval to complete
SCHEDULER_MAX_INSTANCES = 3
HEALTH_CHECK_INTERVAL_SECONDS = 60
WEATHER_REFRESH_MINUTE = 0
VIDEO_AUTOMATION_INTERVAL_SECONDS = 120
SCHEDULER_UPDATE_INTERVAL_SECONDS = 300
STANDARD_JOBS_COUNT = 6

# Worker loop configuration
WORKER_MAIN_LOOP_SLEEP_SECONDS = 1

# Weather worker configuration
WEATHER_DATA_STALE_THRESHOLD_HOURS = 25
DATE_STRING_LENGTH = 10
DUMMY_API_KEY = "dummy"

# Setting keys and defaults
SETTING_KEY_WEATHER_ENABLED = "weather_enabled"
SETTING_KEY_TEMPERATURE_UNIT = "temperature_unit"
SETTING_KEY_GENERATE_THUMBNAILS = "generate_thumbnails"
DEFAULT_WEATHER_ENABLED = "false"
DEFAULT_TEMPERATURE_UNIT = "celsius"
DEFAULT_GENERATE_THUMBNAILS = "true"
BOOLEAN_TRUE_STRING = "true"

# Temperature unit constants
TEMPERATURE_UNIT_CELSIUS = "celsius"
TEMPERATURE_UNIT_FAHRENHEIT = "fahrenheit"

# SSE event configuration
SSE_PRIORITY_NORMAL = "normal"
SSE_SOURCE_WORKER = "worker"

# Logging configuration
LOG_ROTATION_SIZE = "10 MB"
LOG_RETENTION_PERIOD = "30 days"

# ====================================================================
# VALIDATION CONSTANTS
# ====================================================================

# RTSP URL validation
DANGEROUS_CHARS = [";", "&", "|", "`", "$", "(", ")", "<", ">", '"', "'"]
RTSP_URL_PATTERN = r"^rtsps?://[^\s/$.?#].[^\s]*$"

# Time format validation
TIME_WINDOW_PATTERN = r"^([01]?[0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"

# Maximum bounds for validation
MAX_TIME_BOUNDS_SECONDS = MAX_VIDEO_DURATION  # 1 hour max for time limits

# ====================================================================
# THRESHOLD CONSTANTS
# ====================================================================

# Default thresholds
DEFAULT_CORRUPTION_DISCARD_THRESHOLD = 70
DEFAULT_DEGRADED_MODE_FAILURE_THRESHOLD = 10
DEFAULT_DEGRADED_MODE_TIME_WINDOW_MINUTES = 30
DEFAULT_DEGRADED_MODE_FAILURE_PERCENTAGE = 50
DEFAULT_PER_CAPTURE_THROTTLE_MINUTES = 5
DEFAULT_HEALTH_CHECK_INTERVAL_MINUTES = 15

# Corruption analysis constants
MIN_CORRUPTION_ANALYSIS_SAMPLE_SIZE = 20

# Time window constants
TIME_WINDOW_TYPE_MANUAL = "manual"
TIME_WINDOW_TYPE_SUNRISE_SUNSET = "sunrise_sunset"
TIME_WINDOW_TYPE_DISABLED = "disabled"

# Settings validation constants
MAX_SETTING_KEY_LENGTH = 255
MAX_SETTING_VALUE_LENGTH = 10000

# Weather settings keys
WEATHER_SETTINGS_KEYS = [
    "weather_enabled",
    "temperature_unit",
    "latitude",
    "longitude",
    "openweather_api_key",
    "sunrise_sunset_enabled",
]

# Time window constants
DEFAULT_TIME_WINDOW_VALIDATION_TIMEOUT_SECONDS = 5
DEFAULT_TIME_WINDOW_GRACE_PERIOD_SECONDS = 300  # 5 minutes

# Health scoring constants
HEALTH_CAMERA_WEIGHT = 0.3
HEALTH_QUALITY_WEIGHT = 0.4
HEALTH_ACTIVITY_WEIGHT = 0.3
HEALTH_DEGRADED_PENALTY = 50
HEALTH_FLAGGED_PENALTY = 30
HEALTH_ACTIVITY_PERFECT_SCORE = 10
DEFAULT_STATISTICS_RETENTION_DAYS = 365

# ====================================================================
# THUMBNAIL JOB CONSTANTS
# ====================================================================

# Thumbnail job statuses
THUMBNAIL_JOB_STATUS_PENDING = "pending"
THUMBNAIL_JOB_STATUS_PROCESSING = "processing"
THUMBNAIL_JOB_STATUS_COMPLETED = "completed"
THUMBNAIL_JOB_STATUS_FAILED = "failed"
THUMBNAIL_JOB_STATUS_CANCELLED = "cancelled"

# Thumbnail job priorities
THUMBNAIL_JOB_PRIORITY_HIGH = "high"  # Manual operations from settings UI
THUMBNAIL_JOB_PRIORITY_MEDIUM = "medium"  # New image captures
THUMBNAIL_JOB_PRIORITY_LOW = "low"  # Bulk background operations

# Thumbnail job types
THUMBNAIL_JOB_TYPE_SINGLE = "single"  # Single image processing
THUMBNAIL_JOB_TYPE_BULK = "bulk"  # Bulk operation processing

# Job queue configuration defaults - OPTIMIZED FOR PERFORMANCE
DEFAULT_THUMBNAIL_JOB_BATCH_SIZE = 10  # Increased from 5 for better throughput
DEFAULT_THUMBNAIL_WORKER_INTERVAL = 3  # Reduced from 10s for faster response
DEFAULT_THUMBNAIL_MAX_RETRIES = 3
DEFAULT_THUMBNAIL_CLEANUP_HOURS = 24

# High-load configuration (for busy systems)
HIGH_LOAD_THUMBNAIL_JOB_BATCH_SIZE = 20  # For systems with many cameras
HIGH_LOAD_THUMBNAIL_WORKER_INTERVAL = 1  # Near real-time processing

# Memory optimization settings
THUMBNAIL_MEMORY_LIMIT_MB = 512  # Memory limit per worker
THUMBNAIL_CONCURRENT_JOBS = 3  # Concurrent processing limit

# Retry backoff timing (minutes) - OPTIMIZED
THUMBNAIL_JOB_RETRY_DELAYS = [2, 10, 30]  # 2min, 10min, 30min - less aggressive

# Thumbnail job settings keys
SETTING_KEY_THUMBNAIL_JOB_BATCH_SIZE = "thumbnail_job_batch_size"
SETTING_KEY_THUMBNAIL_WORKER_INTERVAL = "thumbnail_worker_interval"
SETTING_KEY_THUMBNAIL_MAX_RETRIES = "thumbnail_max_retries"
SETTING_KEY_THUMBNAIL_CLEANUP_HOURS = "thumbnail_cleanup_hours"
SETTING_KEY_THUMBNAIL_GENERATION_ENABLED = "thumbnail_generation_enabled"
SETTING_KEY_THUMBNAIL_SMALL_GENERATION_MODE = "thumbnail_small_generation_mode"
SETTING_KEY_THUMBNAIL_PURGE_SMALLS_ON_COMPLETION = (
    "thumbnail_purge_smalls_on_completion"
)

# Performance optimization settings
SETTING_KEY_THUMBNAIL_HIGH_LOAD_MODE = "thumbnail_high_load_mode"
SETTING_KEY_THUMBNAIL_MEMORY_LIMIT = "thumbnail_memory_limit_mb"
SETTING_KEY_THUMBNAIL_CONCURRENT_JOBS = "thumbnail_concurrent_jobs"

# Performance thresholds for adaptive scaling
THUMBNAIL_QUEUE_SIZE_HIGH_THRESHOLD = 50  # Switch to high-load mode
THUMBNAIL_QUEUE_SIZE_LOW_THRESHOLD = 10  # Switch back to normal mode
THUMBNAIL_PROCESSING_TIME_WARNING_MS = 5000  # Log slow processing warning
THUMBNAIL_MEMORY_WARNING_THRESHOLD = 0.8  # Memory usage warning (80%)

# Thumbnail verification and maintenance constants
THUMBNAIL_VERIFICATION_BATCH_SIZE = 10000  # Maximum images to verify at once
BYTES_TO_MB_DIVISOR = 1024 * 1024  # Conversion factor for bytes to MB
BYTES_TO_KB_DIVISOR = 1024  # Conversion factor for bytes to KB
