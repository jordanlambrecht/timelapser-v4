# backend/app/enums.py
"""
Application Enums - Centralized enum definitions.

This module contains all enum definitions to break circular imports between
constants.py and shared_models.py. By centralizing enums here, both modules
can import them without creating circular dependencies.
"""

from enum import Enum


# =============================================================================
# PRIORITY SYSTEMS
# =============================================================================


class JobPriority(str, Enum):
    """Job priority levels for all job queue systems (3-level system). Must be: unknown, low, medium, high."""

    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SSEPriority(str, Enum):
    """SSE event priority levels for real-time event streaming (4-level system). Must be: low, normal, high, critical."""

    UNKNOWN = "unknown"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# JOB SYSTEMS
# =============================================================================


class JobStatus(str, Enum):
    """General job statuses for all job queue systems."""

    UNKNOWN = "unknown"
    TRACKING_ERROR = "tracking_error"
    NOT_IMPLEMENTED = "not_implemented"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobTypes(str, Enum):
    """General job types for all job queue systems."""

    UNKNOWN = "unknown"
    THUMBNAIL = "thumbnail"
    OVERLAY = "overlay"
    VIDEO_GENERATION = "video_generation"


# =============================================================================
# THUMBNAIL SYSTEM
# =============================================================================


class ThumbnailJobPriority(str, Enum):
    """Thumbnail job priority levels (uses JobPriority values)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ThumbnailJobStatus(str, Enum):
    """Thumbnail job status values."""

    UNKNOWN = "unknown"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ThumbnailJobType(str, Enum):
    """Thumbnail job types."""

    SINGLE = "single"
    BULK = "bulk"


# =============================================================================
# OVERLAY SYSTEM
# =============================================================================


class OverlayJobPriority(str, Enum):
    """Overlay job priority levels (uses JobPriority values)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OverlayJobStatus(str, Enum):
    """Overlay job status values."""

    UNKNOWN = "unknown"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OverlayJobType(str, Enum):
    """Overlay job types."""

    SINGLE = "single"
    BATCH = "batch"
    PRIORITY = "priority"


class OverlayType(str, Enum):
    """Overlay type constants."""

    DATE = "date"
    DATE_TIME = "date_time"
    TIME = "time"
    FRAME_NUMBER = "frame_number"
    DAY_NUMBER = "day_number"
    CUSTOM_TEXT = "custom_text"
    TIMELAPSE_NAME = "timelapse_name"
    TEMPERATURE = "temperature"
    WEATHER_CONDITIONS = "weather_conditions"
    WEATHER_TEMP_CONDITIONS = "weather_temp_conditions"
    WATERMARK = "watermark"


# =============================================================================
# VIDEO SYSTEM
# =============================================================================


class VideoGenerationMode(str, Enum):
    """Video generation mode enum for FPS calculation methods."""

    STANDARD = "standard"
    TARGET = "target"


class VideoAutomationMode(str, Enum):
    """Video automation mode enum for trigger types."""

    UNKNOWN = "unknown"
    MANUAL = "manual"
    PER_CAPTURE = "per_capture"
    SCHEDULED = "scheduled"
    MILESTONE = "milestone"
    IMMEDIATE = "immediate"
    THUMBNAIL = "thumbnail"


class VideoQuality(str, Enum):
    """Video quality levels for generation settings (unified definition)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"


# =============================================================================
# TIMELAPSE SYSTEM
# =============================================================================


class TimelapseAction(str, Enum):
    """Actions that can be performed on timelapses."""

    CREATE = "create"
    PAUSE = "pause"
    RESUME = "resume"
    END = "end"


# =============================================================================
# SSE EVENT SYSTEM
# =============================================================================


class SSEEvent(str, Enum):
    """SSE event types for real-time event streaming."""

    # Video Pipeline Events
    VIDEO_JOB_QUEUED = "video_job_queued"
    VIDEO_JOB_STARTED = "video_job_started"
    VIDEO_JOB_COMPLETED = "video_job_completed"
    VIDEO_JOB_FAILED = "video_job_failed"
    VIDEO_GENERATION_PROGRESS = "video_generation_progress"
    VIDEO_GENERATED = "video_generated"
    VIDEO_PIPELINE_HEALTH = "video_pipeline_health"

    # Thumbnail Worker Events
    THUMBNAIL_WORKER_STARTED = "thumbnail_worker_started"
    THUMBNAIL_WORKER_STOPPED = "thumbnail_worker_stopped"
    THUMBNAIL_WORKER_ERROR = "thumbnail_worker_error"
    THUMBNAIL_WORKER_PERFORMANCE = "thumbnail_worker_performance"
    THUMBNAIL_JOB_STARTED = "thumbnail_job_started"
    THUMBNAIL_JOB_COMPLETED = "thumbnail_job_completed"
    THUMBNAIL_JOB_RETRY_SCHEDULED = "thumbnail_job_retry_scheduled"
    THUMBNAIL_JOB_FAILED_PERMANENTLY = "thumbnail_job_failed_permanently"
    THUMBNAIL_JOBS_CLEANED_UP = "thumbnail_jobs_cleaned_up"

    # Capture Pipeline Events
    IMAGE_CAPTURED = "image_captured"
    CAPTURE_FAILED = "capture_failed"
    TIMELAPSE_STARTED = "timelapse_started"
    TIMELAPSE_PAUSED = "timelapse_paused"
    TIMELAPSE_RESUMED = "timelapse_resumed"
    TIMELAPSE_COMPLETED = "timelapse_completed"

    # Camera Events
    CAMERA_CREATED = "camera_created"
    CAMERA_UPDATED = "camera_updated"
    CAMERA_DELETED = "camera_deleted"
    CAMERA_HEALTH_CHANGED = "camera_health_changed"

    # Settings Events
    SETTINGS_UPDATED = "settings_updated"

    # System Events
    WORKER_STARTED = "worker_started"
    WORKER_STOPPED = "worker_stopped"
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"


class SSEEventSource(str, Enum):
    """SSE event sources for identifying event origins."""

    VIDEO_PIPELINE = "video_pipeline"
    VIDEO_WORKER = "video_worker"
    THUMBNAIL_WORKER = "thumbnail_worker"
    OVERLAY_WORKER = "overlay_worker"
    CAPTURE_PIPELINE = "capture_pipeline"
    CAMERA_SERVICE = "camera_service"
    SETTINGS_SERVICE = "settings_service"
    SYSTEM = "system"
    WORKER = "worker"
    FFMPEG = "ffmpeg"


# =============================================================================
# LOGGING SYSTEM
# =============================================================================


class LogLevel(str, Enum):
    """Log level constants for centralized logging system."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogSource(str, Enum):
    """Log source constants for identifying log origins."""

    API = "api"
    WORKER = "worker"
    SYSTEM = "system"
    CAMERA = "camera"
    DATABASE = "database"
    SCHEDULER = "scheduler"
    PIPELINE = "pipeline"
    MIDDLEWARE = "middleware"


class LogEmoji(str, Enum):
    """Type-safe emoji constants for log messages."""

    # Request/Response emojis
    INCOMING = "📥"
    OUTGOING = "📤"
    REQUEST = "📥"
    RESPONSE = "📤"

    # Status emojis
    SUCCESS = "✅"
    COMPLETED = "✅"
    FAILED = "💥"
    ERROR = "💥"
    WARNING = "⚠️"
    INFO = "ℹ️"
    DEBUG = "🔍"
    CRITICAL = "🚨"

    # Work emojis
    PROCESSING = "🔄"
    WORKING = "🔄"
    JOB = "🔄"
    TASK = "🔄"
    RUNNING = "▶️"
    STOPPED = "⏹️"
    PAUSED = "⏸️"
    RESUMED = "▶️"

    # Camera/Video emojis
    CAMERA = "📹"
    VIDEO = "🎥"
    IMAGE = "🖼️"
    CAPTURE = "📸"
    THUMBNAIL = "🖼️"
    OVERLAY = "🎨"
    TIMELAPSE = "⏯️"

    # System emojis
    SYSTEM = "⚙️"
    STARTUP = "🚀"
    SHUTDOWN = "🔌"
    HEALTH = "💓"
    CLEANUP = "🧹"
    MAINTENANCE = "🔧"

    # Database emojis
    DATABASE = "🗄️"
    STORAGE = "💾"
    BACKUP = "💾"

    # Network emojis
    NETWORK = "🌐"
    CONNECTION = "🔗"
    DISCONNECTED = "🔌"

    # Worker emojis
    WORKER = "👷"
    SCHEDULER = "⏰"
    QUEUE = "📋"

    # Other emojis
    CLOWN = "🤡"
    PARTY = "🎉"
    FIRE = "🔥"
    ROCKET = "🚀"
    MAGIC = "✨"
    ROBOT = "🤖"


class LoggerName(str, Enum):
    """Logger name constants for categorizing log entries. Consolidated with SSEEventSource."""

    # API/Request loggers
    REQUEST_LOGGER = "request_logger"
    ERROR_HANDLER = "error_handler"
    MIDDLEWARE = "middleware"

    # Worker loggers (consolidated from SSEEventSource)
    CAPTURE_WORKER = "capture_worker"
    THUMBNAIL_WORKER = "thumbnail_worker"
    OVERLAY_WORKER = "overlay_worker"
    SCHEDULER_WORKER = "scheduler_worker"
    HEALTH_WORKER = "health_worker"
    VIDEO_WORKER = "video_worker"

    # Pipeline loggers (consolidated from SSEEventSource)
    VIDEO_PIPELINE = "video_pipeline"
    CAPTURE_PIPELINE = "capture_pipeline"
    THUMBNAIL_PIPELINE = "thumbnail_pipeline"
    OVERLAY_PIPELINE = "overlay_pipeline"
    CORRUPTION_PIPELINE = "corruption_pipeline"

    # Service loggers (consolidated from SSEEventSource)
    CAMERA_SERVICE = "camera_service"
    IMAGE_SERVICE = "image_service"
    TIMELAPSE_SERVICE = "timelapse_service"
    VIDEO_SERVICE = "video_service"
    SETTINGS_SERVICE = "settings_service"
    LOG_SERVICE = "log_service"

    # System loggers (consolidated from SSEEventSource)
    SYSTEM = "system"
    FFMPEG = "ffmpeg"

    # Generic
    UNKNOWN = "unknown"


# =============================================================================
# TIMELAPSE SYSTEMS
# =============================================================================


class TimelapseStatus(str, Enum):
    """Timelapse status values for tracking timelapse lifecycle."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
