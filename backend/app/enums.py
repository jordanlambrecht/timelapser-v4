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
