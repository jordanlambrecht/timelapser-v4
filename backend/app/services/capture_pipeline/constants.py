# backend/app/services/capture_pipeline/constants.py
"""
Capture Pipeline Domain Constants

Domain-specific constants for the complete capture workflow orchestration.
"""

# =============================================================================
# WORKFLOW STEP IDENTIFIERS
# =============================================================================

from ...constants import JOB_PRIORITY, JOB_STATUS


STEP_SCHEDULER_TRIGGER = "scheduler_trigger"
STEP_WORKER_RECEIVES = "worker_receives"
STEP_RTSP_CAPTURE = "rtsp_capture"
STEP_CORRUPTION_FAST = "corruption_fast"
STEP_CORRUPTION_HEAVY = "corruption_heavy"
STEP_CORRUPTION_EVALUATION = "corruption_evaluation"
STEP_RECORD_CREATION = "record_creation"
STEP_OVERLAY_GENERATION = "overlay_generation"
STEP_THUMBNAIL_QUEUEING = "thumbnail_queueing"
STEP_VIDEO_AUTOMATION = "video_automation"
STEP_SSE_BROADCASTING = "sse_broadcasting"
STEP_CAPTURE_COMPLETE = "capture_complete"

# =============================================================================
# WORKFLOW STATUS VALUES
# =============================================================================

WORKFLOW_STATUS_UNKNOWN = "unknown"
WORKFLOW_STATUS_PENDING = "pending"
WORKFLOW_STATUS_IN_PROGRESS = "in_progress"
WORKFLOW_STATUS_COMPLETED = "completed"
WORKFLOW_STATUS_FAILED = "failed"
WORKFLOW_STATUS_RETRYING = "retrying"

# =============================================================================
# CAPTURE PIPELINE RESULTS
# =============================================================================

CAPTURE_RESULT_SUCCESS = "success"
CAPTURE_RESULT_FAILURE = "failure"
CAPTURE_RESULT_PARTIAL = "partial"
CAPTURE_RESULT_RETRY_NEEDED = "retry_needed"

# =============================================================================
# ERROR HANDLING
# =============================================================================

ERROR_RTSP_CONNECTION_FAILED = "rtsp_connection_failed"
ERROR_FRAME_CAPTURE_FAILED = "frame_capture_failed"
ERROR_CORRUPTION_DETECTION_FAILED = "corruption_detection_failed"
ERROR_RECORD_CREATION_FAILED = "record_creation_failed"
ERROR_OVERLAY_GENERATION_FAILED = "overlay_generation_failed"
ERROR_JOB_QUEUEING_FAILED = "job_queueing_failed"
ERROR_SSE_BROADCASTING_FAILED = "sse_broadcasting_failed"

# =============================================================================
# RETRY LOGIC
# =============================================================================

DEFAULT_CAPTURE_RETRIES = 1
DEFAULT_RTSP_TIMEOUT_SECONDS = 30
DEFAULT_CORRUPTION_RETRY_THRESHOLD = 70

# =============================================================================
# JOB COORDINATION
# =============================================================================

THUMBNAIL_JOB_PRIORITY_AUTO = JOB_PRIORITY.MEDIUM
THUMBNAIL_JOB_PRIORITY_MANUAL = JOB_PRIORITY.HIGH
VIDEO_JOB_PRIORITY_IMMEDIATE = JOB_PRIORITY.HIGH
VIDEO_JOB_PRIORITY_MILESTONE = JOB_PRIORITY.MEDIUM
VIDEO_JOB_PRIORITY_SCHEDULED = JOB_PRIORITY.LOW


# =============================================================================
# BRIDGE SERVICES (for future domain extraction)
# =============================================================================

CORRUPTION_BRIDGE_ENABLED = True
OVERLAY_BRIDGE_ENABLED = True

# =============================================================================
# OVERLAY GENERATION
# =============================================================================

DEFAULT_OVERLAY_WIDTH = 1920
DEFAULT_OVERLAY_HEIGHT = 1080
MIN_OVERLAY_WIDTH = 320
MIN_OVERLAY_HEIGHT = 240
MAX_OVERLAY_WIDTH = 4096
MAX_OVERLAY_HEIGHT = 2160

# =============================================================================
# SSE EVENT TYPES
# =============================================================================

SSE_CAPTURE_STARTED = "capture_started"
SSE_CAPTURE_COMPLETED = "capture_completed"
SSE_CAPTURE_FAILED = "capture_failed"
SSE_CORRUPTION_DETECTED = "corruption_detected"
SSE_OVERLAY_GENERATED = "overlay_generated"
SSE_JOBS_QUEUED = "jobs_queued"

# =============================================================================
# WORKFLOW COORDINATION
# =============================================================================

WORKFLOW_TOTAL_STEPS = 12
WORKFLOW_VERSION = "v2.0"
WORKFLOW_STEP_TIMEOUT_SECONDS = 60
WORKFLOW_TOTAL_TIMEOUT_SECONDS = 300
WORKFLOW_CLEANUP_ON_FAILURE = True

# =============================================================================
# JOB QUEUE HEALTH STATUS
# =============================================================================

HEALTH_STATUS_HEALTHY = "healthy"
HEALTH_STATUS_DEGRADED = "degraded"
HEALTH_STATUS_UNHEALTHY = "unhealthy"
HEALTH_STATUS_OVERLOADED = "overloaded"
HEALTH_STATUS_UNKNOWN = "unknown"
HEALTH_STATUS_ERROR = "error"

# =============================================================================
# JOB VALIDATION
# =============================================================================

JOB_VALIDATION_RESULT_VALID = True
JOB_VALIDATION_RESULT_INVALID = False
JOB_VALIDATION_ERRORS_KEY = "errors"
JOB_VALIDATION_WARNINGS_KEY = "warnings"
JOB_VALIDATION_SANITIZED_KEY = "sanitized_parameters"
