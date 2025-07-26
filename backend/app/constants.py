# backend/app/constants.py
"""
Global Constants for Timelapser v4

Centralized location for all application constants to avoid hardcoded values
throughout the codebase.
"""

from typing import Set
from enum import Enum

from .models.health_model import HealthStatus
from .enums import (
    # Priority Systems
    JobPriority,
    SSEPriority,
    # Job Systems
    JobStatus,
    JobTypes,
    # Video Systems
    VideoAutomationMode,
    VideoGenerationMode,
    VideoQuality,
    # Thumbnail Systems
    ThumbnailJobPriority,
    ThumbnailJobStatus,
    ThumbnailJobType,
    # Overlay Systems
    OverlayJobPriority,
    OverlayJobStatus,
    OverlayJobType,
    OverlayType,
    # Timelapse Systems
    TimelapseAction,
    TimelapseStatus,
)

# =============================================================================
# JOB COORDINATION - ALIASES FOR IMPORTED ENUMS
# =============================================================================

# Create backward-compatible aliases for centralized enums
JOB_TYPE = JobTypes
JOB_TYPE_LIST = [job_type.value for job_type in JobTypes]

JOB_STATUS = JobStatus
JOB_STATUS_LIST = [status.value for status in JobStatus]

JOB_PRIORITY = JobPriority
JOB_PRIORITIES_LIST = [priority.value for priority in JobPriority]
JOB_PRIORITY_LIST = JOB_PRIORITIES_LIST  # Alias for backwards compatibility

# SSE Priority System Alias
SSE_PRIORITY = SSEPriority

# Thumbnail System Aliases
THUMBNAIL_JOB_PRIORITY = ThumbnailJobPriority
THUMBNAIL_JOB_STATUS = ThumbnailJobStatus
THUMBNAIL_JOB_TYPE = ThumbnailJobType

# Overlay System Aliases
OVERLAY_JOB_PRIORITY = OverlayJobPriority
OVERLAY_JOB_STATUS = OverlayJobStatus
OVERLAY_JOB_TYPE = OverlayJobType
OVERLAY_TYPE = OverlayType

# Timelapse System Aliases
TIMELAPSE_ACTION = TimelapseAction

# ====================================================================
# FILE TYPE CONSTANTS

# Overlay asset file types
ALLOWED_OVERLAY_ASSET_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}

# Overlay asset size limits
MAX_OVERLAY_ASSET_SIZE = 10 * 1024 * 1024  # 10MB
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

# ====================================================================
# CAMERA HEALTH AND FAILURE CONSTANTS
# ====================================================================

# Camera health status thresholds
CAMERA_HEALTH_FAILURE_THRESHOLD = 5  # Consecutive failures before marking offline
CAMERA_HEALTH_DEGRADED_THRESHOLD = 1  # Consecutive failures before marking degraded

# Camera health statuses
CAMERA_HEALTH_ONLINE = "online"
CAMERA_HEALTH_DEGRADED = "degraded"
CAMERA_HEALTH_OFFLINE = "offline"
CAMERA_HEALTH_UNKNOWN = "unknown"

CAMERA_HEALTH_STATUSES = [
    CAMERA_HEALTH_ONLINE,
    CAMERA_HEALTH_DEGRADED,
    CAMERA_HEALTH_OFFLINE,
    CAMERA_HEALTH_UNKNOWN,
]

# Camera capture readiness criteria
CAMERA_CAPTURE_READY_STATUSES = ["active"]
CAMERA_TIMELAPSE_READY_STATUSES = ["running"]

# Camera health status values
CAMERA_HEALTH_STATUS_HEALTHY = "healthy"
CAMERA_HEALTH_STATUS_DEGRADED = "degraded"
CAMERA_HEALTH_STATUS_FAILED = "failed"

# List of all valid health statuses
HEALTH_STATUSES = [
    CAMERA_HEALTH_STATUS_HEALTHY,
    CAMERA_HEALTH_STATUS_DEGRADED,
    CAMERA_HEALTH_STATUS_FAILED,
]

# ====================================================================
# CORRUPTION DETECTION CONSTANTS
# ====================================================================

# Corruption score thresholds
CORRUPTION_SCORE_EXCELLENT = 95
CORRUPTION_SCORE_GOOD = 80
CORRUPTION_SCORE_POOR = 60
CORRUPTION_SCORE_FAILED = -1  # Indicates corruption detection failed

# Corruption detection defaults
DEFAULT_CORRUPTION_HISTORY_HOURS = 24
DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS = 90
DEFAULT_CORRUPTION_LOGS_PAGE_SIZE = 50
MAX_CORRUPTION_LOGS_PAGE_SIZE = 200

# Corruption auto-discard thresholds
CORRUPTION_CRITICAL_THRESHOLD = 90
CORRUPTION_FAST_CRITICAL_THRESHOLD = 95
CORRUPTION_HEAVY_CRITICAL_THRESHOLD = 95

# Corruption detection thresholds
DEFAULT_CORRUPTION_DISCARD_THRESHOLD = 80  # Images below this score are discarded

# Degraded mode thresholds
DEFAULT_DEGRADED_MODE_FAILURE_THRESHOLD = (
    5  # Number of failures to trigger degraded mode
)
DEFAULT_DEGRADED_MODE_TIME_WINDOW_MINUTES = 60  # Time window for failure counting
DEFAULT_DEGRADED_MODE_FAILURE_PERCENTAGE = 50  # Percentage threshold for degraded mode

# Corruption analysis constants
DEFAULT_CORRUPTION_LOGS_RETENTION_DAYS = 30  # Days to keep corruption logs
DEFAULT_CORRUPTION_LOGS_PAGE_SIZE = 50  # Default page size for corruption log queries
MIN_CORRUPTION_ANALYSIS_SAMPLE_SIZE = (
    10  # Minimum images needed for corruption analysis
)

# ====================================================================
# STATISTICS AND HEALTH SCORING CONSTANTS
# ====================================================================

# Video queue health thresholds
VIDEO_QUEUE_WARNING_THRESHOLD = 10  # Number of queued jobs to trigger warning
VIDEO_QUEUE_ERROR_THRESHOLD = 25  # Number of queued jobs to trigger error

# Health scoring weights (must sum to 1.0)
HEALTH_CAMERA_WEIGHT = 0.4  # Weight for camera health in overall score
HEALTH_QUALITY_WEIGHT = 0.3  # Weight for image quality in overall score
HEALTH_ACTIVITY_WEIGHT = 0.3  # Weight for system activity in overall score

# Health scoring penalties
HEALTH_DEGRADED_PENALTY = 20  # Points to subtract for degraded cameras
HEALTH_FLAGGED_PENALTY = 10  # Points to subtract for flagged images

# Health scoring perfect scores
HEALTH_ACTIVITY_PERFECT_SCORE = 100  # Perfect activity score baseline

# Statistics retention
DEFAULT_STATISTICS_RETENTION_DAYS = 90  # Days to keep statistical data

# ====================================================================
# TIME WINDOW SERVICE CONSTANTS
# ====================================================================

# Time window validation settings
DEFAULT_TIME_WINDOW_VALIDATION_TIMEOUT_SECONDS = (
    30  # Timeout for time window validation
)
DEFAULT_TIME_WINDOW_GRACE_PERIOD_SECONDS = (
    60  # Grace period for time window calculations
)

# Time window event types
EVENT_TIME_WINDOW_VALIDATED = "time_window_validated"
EVENT_TIME_WINDOW_STATUS_CALCULATED = "time_window_status_calculated"
EVENT_CAPTURE_COUNT_ESTIMATED = "capture_count_estimated"

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

HEALTH_STATUS = HealthStatus
HEALTH_STATUSES = [status.value for status in HealthStatus]

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
# LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


LOG_LEVELS = LogLevel
LOG_LEVELS_LIST = [level.value for level in LogLevel]

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
# VIDEO_GENERATION_MODES = ["manual", "per_capture", "scheduled", "milestone"]


VIDEO_GENERATION_MODE = VideoGenerationMode
VIDEO_AUTOMATION_MODE = VideoAutomationMode
VIDEO_QUALITIES = VideoQuality
VIDEO_QUALITY_LEVEL = VideoQuality  # Alias for backwards compatibility

# If we need a list of all modes:
VIDEO_AUTOMATION_MODES_LIST = [mode.value for mode in VideoAutomationMode]
VIDEO_GENERATION_MODES_LIST = [mode.value for mode in VideoGenerationMode]
VIDEO_QUALITIES_LIST = [quality.value for quality in VideoQuality]

# VIDEO_QUALITIES = ["low", "medium", "high", "ultra"]

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

# # Video generation job statuses
# VIDEO_JOB_STATUSES = [
#     "unknown",
#     "pending",
#     "processing",
#     "completed",
#     "failed",
#     "cancelled",
# ]


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
# DEFAULT_VIDEO_GENERATION_PRIORITY = JOB_PRIORITY.MEDIUM

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
EVENT_TIMELAPSE_HEALTH_MONITORED = "timelapse_health_monitored"
EVENT_TIMELAPSE_STATISTICS_UPDATED = "timelapse_statistics_updated"
EVENT_HEALTH_CHECK_COMPLETED = "health_check_completed"

# Image events
EVENT_IMAGE_CAPTURED = "image_captured"
EVENT_IMAGE_DELETED = "image_deleted"
EVENT_IMAGE_PROCESSED = "image_processed"
EVENT_IMAGE_CORRUPTED = "image_corrupted"

# Corruption detection events
EVENT_CORRUPTION_DEGRADED_MODE_RESET = "corruption_degraded_mode_reset"
EVENT_CORRUPTION_TEST_COMPLETED = "corruption_test_completed"
EVENT_CORRUPTION_HEALTH_UPDATED = "corruption_health_updated"

# Video events
EVENT_VIDEO_CREATED = "video_created"
EVENT_VIDEO_UPDATED = "video_updated"
EVENT_VIDEO_DELETED = "video_deleted"
EVENT_VIDEO_STATS_CALCULATED = "video_stats_calculated"
EVENT_VIDEO_JOB_QUEUED = "video_job_queued"
EVENT_VIDEO_JOB_STARTED = "video_job_started"
EVENT_VIDEO_JOB_COMPLETED = "video_job_completed"

# Generic job events
EVENT_JOB_CREATED = "job_created"
EVENT_JOB_FAILED = "job_failed"

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

# Note: DEFAULT_OVERLAY_SETTINGS removed - overlay settings are now handled by the overlay system

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
SETTING_KEY_GENERATE_OVERLAYS = "generate_overlays"
SETTING_KEY_THUMBNAIL_PURGE_SMALLS_ON_COMPLETION = (
    "thumbnail_purge_smalls_on_completion"
)
SETTING_KEY_THUMBNAIL_GENERATION_ENABLED = "thumbnail_generation_enabled"
SETTING_KEY_THUMBNAIL_SMALL_GENERATION_MODE = "thumbnail_small_generation_mode"
DEFAULT_WEATHER_ENABLED = "false"
DEFAULT_TEMPERATURE_UNIT = "celsius"
DEFAULT_GENERATE_THUMBNAILS = "true"
DEFAULT_GENERATE_OVERLAYS = "true"
BOOLEAN_TRUE_STRING = "true"

# Temperature unit constants
TEMPERATURE_UNIT_CELSIUS = "celsius"
TEMPERATURE_UNIT_FAHRENHEIT = "fahrenheit"

# SSE event configuration
SSE_SOURCE_WORKER = "worker"

# Logging configuration
LOG_ROTATION_SIZE = "10 MB"
LOG_RETENTION_PERIOD = "30 days"

# ====================================================================
# VALIDATION CONSTANTS
# ====================================================================

# File path validation
# MOVED TO: utils/validation_constants.py to avoid circular imports
# DANGEROUS_CHARS = r'[<>:"|?*\x00-\x1f]'

# RTSP URL validation pattern
# MOVED TO: utils/validation_constants.py to avoid circular imports
# RTSP_URL_PATTERN = r"^rtsps?://[^\s]+$"

# Time window validation pattern
# MOVED TO: utils/validation_constants.py to avoid circular imports
# TIME_WINDOW_PATTERN = r"^\d{2}:\d{2}-\d{2}:\d{2}$"

# FPS validation bounds
# MOVED TO: utils/validation_constants.py to avoid circular imports
# MIN_FPS = 1
# MAX_FPS = 60

# Time bounds validation (in seconds)
# MOVED TO: utils/validation_constants.py to avoid circular imports
# MAX_TIME_BOUNDS_SECONDS = 86400  # 24 hours in seconds

# ====================================================================
# CAMERA STATUS MESSAGES
# ====================================================================

# Error and success messages for camera operations
CAMERA_NOT_FOUND = "Camera not found"
CAMERA_CAPTURE_SUCCESS = "Capture successful"


# ====================================================================
# OVERLAY SYSTEM CONSTANTS
# ====================================================================

# Thumbnail job priorities - MOVED TO enums.py, use THUMBNAIL_JOB_PRIORITY enum instead

# Thumbnail job statuses - MOVED TO enums.py, use JobStatus enum instead

# Thumbnail job types
THUMBNAIL_JOB_TYPE_SINGLE = "single"
THUMBNAIL_JOB_TYPE_BULK = "bulk"

# Thumbnail job processing constants
DEFAULT_THUMBNAIL_JOB_BATCH_SIZE = 5
DEFAULT_THUMBNAIL_WORKER_INTERVAL = 10
DEFAULT_THUMBNAIL_MAX_RETRIES = 3
DEFAULT_THUMBNAIL_CLEANUP_HOURS = 24

# Thumbnail job retry and performance constants
THUMBNAIL_JOB_RETRY_DELAYS = [30, 120, 300]  # Minutes: 30s, 2min, 5min
HIGH_LOAD_THUMBNAIL_JOB_BATCH_SIZE = 15
HIGH_LOAD_THUMBNAIL_WORKER_INTERVAL = 3
THUMBNAIL_QUEUE_SIZE_HIGH_THRESHOLD = 50
THUMBNAIL_QUEUE_SIZE_LOW_THRESHOLD = 10
THUMBNAIL_PROCESSING_TIME_WARNING_MS = 5000
THUMBNAIL_MEMORY_WARNING_THRESHOLD = 100  # MB
THUMBNAIL_CONCURRENT_JOBS = 3

# Overlay job priorities - MOVED TO enums.py, use OVERLAY_JOB_PRIORITY enum instead

# Overlay job statuses - MOVED TO enums.py, use JobStatus enum instead

# Overlay job types
OVERLAY_JOB_TYPE_SINGLE = "single"
OVERLAY_JOB_TYPE_BATCH = "batch"

# Overlay job processing constants
DEFAULT_OVERLAY_JOB_BATCH_SIZE = 5
DEFAULT_OVERLAY_WORKER_INTERVAL = 10
DEFAULT_OVERLAY_MAX_RETRIES = 3
DEFAULT_OVERLAY_CLEANUP_HOURS = 24

# Overlay job retry and performance constants
OVERLAY_JOB_RETRY_DELAYS = [30, 120, 300]  # Minutes: 30s, 2min, 5min
HIGH_LOAD_OVERLAY_JOB_BATCH_SIZE = 15
HIGH_LOAD_OVERLAY_WORKER_INTERVAL = 3
OVERLAY_QUEUE_SIZE_HIGH_THRESHOLD = 50
OVERLAY_QUEUE_SIZE_LOW_THRESHOLD = 10
OVERLAY_PROCESSING_TIME_WARNING_MS = 5000
OVERLAY_MEMORY_WARNING_THRESHOLD = 100  # MB
OVERLAY_CONCURRENT_JOBS = 3

# Overlay types
OVERLAY_TYPE_DATE = "date"
OVERLAY_TYPE_DATE_TIME = "date_time"
OVERLAY_TYPE_TIME = "time"
OVERLAY_TYPE_FRAME_NUMBER = "frame_number"
OVERLAY_TYPE_DAY_NUMBER = "day_number"
OVERLAY_TYPE_CUSTOM_TEXT = "custom_text"
OVERLAY_TYPE_TIMELAPSE_NAME = "timelapse_name"
OVERLAY_TYPE_TEMPERATURE = "temperature"
OVERLAY_TYPE_WEATHER_CONDITIONS = "weather_conditions"
OVERLAY_TYPE_WEATHER_TEMP_CONDITIONS = "weather_temp_conditions"
OVERLAY_TYPE_WATERMARK = "watermark"

# ====================================================================
# TIMELAPSE ACTION CONSTANTS
# ====================================================================

# Timelapse action types
TIMELAPSE_ACTION_CREATE = "create"
TIMELAPSE_ACTION_PAUSE = "pause"
TIMELAPSE_ACTION_RESUME = "resume"
TIMELAPSE_ACTION_END = "end"

# Valid timelapse actions list
TIMELAPSE_ACTIONS = [
    TIMELAPSE_ACTION_CREATE,
    TIMELAPSE_ACTION_PAUSE,
    TIMELAPSE_ACTION_RESUME,
    TIMELAPSE_ACTION_END,
]

# Type alias for timelapse actions
# MOVED TO: models/enums.py to avoid circular imports
# TimelapseAction = Literal["create", "pause", "resume", "end"]

# ====================================================================
# SETTINGS SYSTEM CONSTANTS
# ====================================================================

# Settings validation limits
MAX_SETTING_KEY_LENGTH = 255
MAX_SETTING_VALUE_LENGTH = 1000

# ====================================================================
# VIDEO AUTOMATION CONSTANTS
# ====================================================================

# Video automation throttling
DEFAULT_PER_CAPTURE_THROTTLE_MINUTES = (
    15  # Minutes between per-capture video generations
)

# Video automation event types
EVENT_VIDEO_JOB_QUEUED = "video_job_queued"
EVENT_VIDEO_JOB_STARTED = "video_job_started"
EVENT_VIDEO_JOB_COMPLETED = "video_job_completed"

# ====================================================================
# TIMELAPSE SYSTEM CONSTANTS
# ====================================================================

# Valid timelapse statuses list (using enum values)
TIMELAPSE_STATUSES = [status.value for status in TimelapseStatus]

# Timelapse event types
EVENT_TIMELAPSE_CREATED = "timelapse_created"
EVENT_TIMELAPSE_UPDATED = "timelapse_updated"
EVENT_TIMELAPSE_COMPLETED = "timelapse_completed"
EVENT_TIMELAPSE_HEALTH_MONITORED = "timelapse_health_monitored"
EVENT_TIMELAPSE_STATISTICS_UPDATED = "timelapse_statistics_updated"
EVENT_HEALTH_CHECK_COMPLETED = "health_check_completed"

# Timelapse setting keys
SETTING_KEY_THUMBNAIL_PURGE_SMALLS_ON_COMPLETION = (
    "thumbnail_purge_smalls_on_completion"
)
SETTING_KEY_THUMBNAIL_GENERATION_ENABLED = "thumbnail_generation_enabled"

# ====================================================================
# RTSP SERVICE CONSTANTS
# ====================================================================

# RTSP operation defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_RTSP_TIMEOUT_SECONDS = 10
DEFAULT_RTSP_QUALITY = 90
DEFAULT_IMAGE_EXTENSION = ".jpg"

# RTSP capture defaults
DEFAULT_CORRUPTION_SCORE = 100
DEFAULT_IS_FLAGGED = False

# RTSP connection messages
CAMERA_CONNECTION_SUCCESS = "Connection successful"
CAMERA_CONNECTION_FAILED = "Connection failed"
CAMERA_CAPTURE_FAILED = "Capture failed"
CAMERA_DELETED_SUCCESS = "Camera deleted successfully"
CAMERA_STATUS_UPDATED_SUCCESS = "Camera status updated successfully"
NO_IMAGES_FOUND = "No images found"

# =============================================================================
# JOB PRIORITY CONSTANTS (REFERENCE ENUM VALUES)
# =============================================================================

# Thumbnail job priority constants (reference enum values)
THUMBNAIL_JOB_PRIORITY_HIGH = ThumbnailJobPriority.HIGH
THUMBNAIL_JOB_PRIORITY_MEDIUM = ThumbnailJobPriority.MEDIUM
THUMBNAIL_JOB_PRIORITY_LOW = ThumbnailJobPriority.LOW

# Job priority constants (reference enum values)
JOB_PRIORITY_HIGH = JobPriority.HIGH
JOB_PRIORITY_MEDIUM = JobPriority.MEDIUM
JOB_PRIORITY_LOW = JobPriority.LOW

# =============================================================================
# SSE (SERVER-SENT EVENTS) CONSTANTS
# =============================================================================


# SSE source constants
SSE_SOURCE_WORKER = "worker"
SSE_SOURCE_API = "api"
SSE_SOURCE_SCHEDULER = "scheduler"
