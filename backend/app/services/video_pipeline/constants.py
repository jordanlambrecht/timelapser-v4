# backend/app/services/video_pipeline/constants.py
"""
Video Pipeline Domain Constants

Contains all constants used throughout the video pipeline domain.
Follows the same pattern as capture_pipeline/constants.py
"""

# Video Generation Job Statuses
from enum import Enum

from ...constants import (
    JOB_PRIORITY,
    JOB_STATUS_LIST,
    VIDEO_AUTOMATION_MODE,
    VIDEO_AUTOMATION_MODES_LIST,
    VIDEO_GENERATION_MODE,
    VIDEO_QUALITY_LEVEL,
)
from ...enums import SSEEvent

# Video Generation Trigger Types
VIDEO_TRIGGER_MANUAL = VIDEO_AUTOMATION_MODE.MANUAL
VIDEO_TRIGGER_PER_CAPTURE = VIDEO_AUTOMATION_MODE.PER_CAPTURE
VIDEO_TRIGGER_SCHEDULED = VIDEO_AUTOMATION_MODE.SCHEDULED
VIDEO_TRIGGER_MILESTONE = VIDEO_AUTOMATION_MODE.MILESTONE


# Video Generation Defaults
DEFAULT_VIDEO_FPS = 30
DEFAULT_VIDEO_QUALITY = VIDEO_QUALITY_LEVEL.MEDIUM
DEFAULT_VIDEO_GENERATION_MODE = VIDEO_GENERATION_MODE.STANDARD
DEFAULT_VIDEO_MIN_DURATION = 5
DEFAULT_VIDEO_MAX_DURATION = 300
DEFAULT_VIDEO_TARGET_DURATION = 60
DEFAULT_VIDEO_FPS_MIN = 1
DEFAULT_VIDEO_FPS_MAX = 60

# Video Pipeline Constants (for utils validation)
VIDEO_TRIGGER_TYPES = VIDEO_AUTOMATION_MODES_LIST  # Use existing automation modes
VIDEO_JOB_STATUSES = JOB_STATUS_LIST  # Use existing job statuses

# Magic Number Constants (extracted from hardcoded values)
VIDEO_MINIMUM_IMAGES_FOR_GENERATION = 10  # Minimum images needed for video generation
VIDEO_DISK_USAGE_WARNING_THRESHOLD = 90  # Disk usage percentage threshold
VIDEO_SCHEDULED_TIME_WINDOW_MINUTES = 5  # Time window for scheduled triggers
VIDEO_MILESTONE_DEFAULT_INTERVAL = 100  # Default milestone interval
VIDEO_SCHEDULED_DEFAULT_TIME = "09:00"  # Default scheduled time
VIDEO_QUEUE_UNHEALTHY_THRESHOLD = 100  # Pending jobs threshold for unhealthy status
VIDEO_QUEUE_DEGRADED_THRESHOLD = 50  # Pending jobs threshold for degraded status
VIDEO_PROCESSING_OVERHEAD_SECONDS = 10  # Fixed FFmpeg initialization overhead
VIDEO_PROCESSING_MIN_TIME_SECONDS = 30  # Minimum processing time
VIDEO_PROCESSING_MAX_TIME_SECONDS = 1800  # Maximum processing time (30 minutes)
VIDEO_FILE_SIZE_OVERHEAD_PERCENT = 10  # Container format overhead percentage
VIDEO_FILENAME_MAX_LENGTH = 255  # Maximum filename length

# Job Queue Settings
DEFAULT_VIDEO_JOB_PRIORITY = JOB_PRIORITY.MEDIUM


# Throttling Settings
DEFAULT_PER_CAPTURE_THROTTLE_MINUTES = 15
DEFAULT_MAX_CONCURRENT_VIDEO_JOBS = 3

# File Management Settings
DEFAULT_VIDEO_CLEANUP_DAYS = 30
DEFAULT_VIDEO_ARCHIVE_DIRECTORY = "archived_videos"

# SSE Event Lists for backward compatibility
VIDEO_SSE_EVENTS = [
    SSEEvent.VIDEO_JOB_QUEUED,
    SSEEvent.VIDEO_JOB_STARTED,
    SSEEvent.VIDEO_JOB_COMPLETED,
    SSEEvent.VIDEO_JOB_FAILED,
    SSEEvent.VIDEO_GENERATION_PROGRESS,
    SSEEvent.VIDEO_GENERATED,
    SSEEvent.VIDEO_PIPELINE_HEALTH,
]

# FFmpeg Settings
FFMPEG_COMMAND_TIMEOUT_SECONDS = 300
FFMPEG_AVAILABILITY_CHECK_TIMEOUT = 10

# Health Check Settings
VIDEO_PIPELINE_HEALTH_CHECK_INTERVAL = 60
VIDEO_PIPELINE_SERVICE_COUNT = 3  # Expected number of services in simplified pipeline

# Overlay Management Settings
OVERLAY_PREFLIGHT_TIMEOUT_SECONDS = 30
OVERLAY_REGENERATION_TIMEOUT_SECONDS = 180
OVERLAY_FALLBACK_TIMEOUT_SECONDS = 60
OVERLAY_HEALTH_CHECK_INTERVAL = 300

# Transaction Settings
VIDEO_TRANSACTION_TIMEOUT_SECONDS = 600
VIDEO_TRANSACTION_MAX_RETRIES = 3

# Video File Settings
SUPPORTED_VIDEO_FORMATS = [".mp4", ".avi", ".mov"]
DEFAULT_VIDEO_EXTENSION = ".mp4"
DEFAULT_VIDEO_CODEC = "libx264"
DEFAULT_VIDEO_PIXEL_FORMAT = "yuv420p"
VIDEO_STORAGE_SUBDIRECTORY = "videos"
TEMP_VIDEO_SUBDIRECTORY = "temp_videos"
VIDEO_METADATA_VERSION = "1.0"

# Automation Settings
VIDEO_AUTOMATION_CYCLE_INTERVAL_SECONDS = 120  # 2 minutes
VIDEO_AUTOMATION_MAX_JOBS_PER_CYCLE = 5


# Error Messages
class VideoPipelineErrorMessages(Enum):
    """Error messages for video pipeline operations."""

    FFMPEG_NOT_AVAILABLE = "FFmpeg is not available on the system"
    INVALID_VIDEO_SETTINGS = "Invalid video generation settings"
    VIDEO_FILE_NOT_FOUND = "Video file not found"
    VIDEO_DIRECTORY_CREATION_FAILED = "Failed to create video directory"
    VIDEO_METADATA_INVALID = "Video metadata is invalid"
    INSUFFICIENT_DISK_SPACE = "Insufficient disk space for video generation"
    TIMELAPSE_NOT_FOUND = "Timelapse not found"
    NO_IMAGES_FOUND = "No images found for video generation"
    VIDEO_GENERATION_FAILED = "Video generation failed"
    JOB_ALREADY_PROCESSING = "Job is already being processed"
    INVALID_JOB_STATUS = "Invalid job status"
    TRANSACTION_FAILED = "Video generation transaction failed"
    OVERLAY_SYSTEM_UNAVAILABLE = "Overlay system is unavailable"
    OVERLAY_REGENERATION_FAILED = "Overlay regeneration failed"
    OVERLAY_FILE_NOT_FOUND = "Overlay file not found"
    UNEXPECTED_ERROR = "An unexpected error occurred in the video pipeline"


VIDEO_ERROR_MESSAGES = {error.name: error.value for error in VideoPipelineErrorMessages}
VIDEO_ERROR_MESSAGE = VideoPipelineErrorMessages

# Direct error constants for import convenience
ERROR_FFMPEG_NOT_AVAILABLE = VideoPipelineErrorMessages.FFMPEG_NOT_AVAILABLE.value
ERROR_INVALID_VIDEO_SETTINGS = VideoPipelineErrorMessages.INVALID_VIDEO_SETTINGS.value
ERROR_VIDEO_FILE_NOT_FOUND = VideoPipelineErrorMessages.VIDEO_FILE_NOT_FOUND.value
ERROR_VIDEO_DIRECTORY_CREATION_FAILED = (
    VideoPipelineErrorMessages.VIDEO_DIRECTORY_CREATION_FAILED.value
)
ERROR_VIDEO_METADATA_INVALID = VideoPipelineErrorMessages.VIDEO_METADATA_INVALID.value
ERROR_INSUFFICIENT_DISK_SPACE = VideoPipelineErrorMessages.INSUFFICIENT_DISK_SPACE.value
ERROR_TIMELAPSE_NOT_FOUND = VideoPipelineErrorMessages.TIMELAPSE_NOT_FOUND.value
ERROR_NO_IMAGES_FOUND = VideoPipelineErrorMessages.NO_IMAGES_FOUND.value
ERROR_VIDEO_GENERATION_FAILED = VideoPipelineErrorMessages.VIDEO_GENERATION_FAILED.value
ERROR_JOB_ALREADY_PROCESSING = VideoPipelineErrorMessages.JOB_ALREADY_PROCESSING.value
ERROR_INVALID_JOB_STATUS = VideoPipelineErrorMessages.INVALID_JOB_STATUS.value
ERROR_TRANSACTION_FAILED = VideoPipelineErrorMessages.TRANSACTION_FAILED.value
ERROR_OVERLAY_SYSTEM_UNAVAILABLE = (
    VideoPipelineErrorMessages.OVERLAY_SYSTEM_UNAVAILABLE.value
)
ERROR_OVERLAY_REGENERATION_FAILED = (
    VideoPipelineErrorMessages.OVERLAY_REGENERATION_FAILED.value
)
ERROR_OVERLAY_FILE_NOT_FOUND = VideoPipelineErrorMessages.OVERLAY_FILE_NOT_FOUND.value
ERROR_UNEXPECTED_ERROR = VideoPipelineErrorMessages.UNEXPECTED_ERROR.value
