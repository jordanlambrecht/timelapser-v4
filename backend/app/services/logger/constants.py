"""
Logger Service Constants

Local constants for the logger service to avoid hardcoded values
and provide centralized configuration for logger-specific settings.
"""

# ====================================================================
# CONSOLE HANDLER CONSTANTS
# ====================================================================

# ANSI color codes for different log levels
ANSI_COLOR_CYAN = "\033[36m"     # Debug
ANSI_COLOR_GREEN = "\033[32m"    # Info
ANSI_COLOR_YELLOW = "\033[33m"   # Warning
ANSI_COLOR_RED = "\033[31m"      # Error
ANSI_COLOR_MAGENTA = "\033[35m"  # Critical
ANSI_COLOR_PURPLE = "\033[35m"   # Capture process indicator

# ANSI formatting codes
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"

# Console output formatting
CONSOLE_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
CONSOLE_MAX_CONTEXT_ITEMS = 3
CONSOLE_CONTEXT_INDENTATION = "  ↳ "
CONSOLE_CAPTURE_BAR = "▎"  # Thick purple bar for capture processes

# ====================================================================
# CONTEXT EXTRACTOR CONSTANTS
# ====================================================================

# Stack trace analysis limits
DEFAULT_MAX_STACK_DEPTH = 10
MAX_CONTEXT_STRING_LENGTH = 500
CONTEXT_STRING_TRUNCATE_LENGTH = 497
CONTEXT_TRUNCATE_SUFFIX = "..."

# Performance context collection
MEMORY_USAGE_DECIMAL_PLACES = 2
CPU_PERCENT_DECIMAL_PLACES = 2

# Context cleanup thresholds
MIN_CONTEXT_STRING_LENGTH = 1

# File path filtering patterns
STACK_FILTER_PATTERNS = ["logger", "log_", "handler", "context_extractor"]

# Environment detection
DOCKER_ENV_FILE = "/.dockerenv"
DOCKER_CONTAINER_ENV_VAR = "DOCKER_CONTAINER"

# Module name extraction
TIMELAPSER_MODULE_INDICATOR = "timelapser"

# ====================================================================
# MESSAGE FORMATTER CONSTANTS
# ====================================================================

# Message formatting limits
FORMATTER_ERROR_MESSAGE_MAX_LENGTH = 50
FORMATTER_CONTEXT_PREVIEW_MAX_ITEMS = 3
FORMATTER_FALLBACK_MESSAGE = "Message extraction failed"

# Performance message formatting
PERFORMANCE_DURATION_MS_THRESHOLD_FAST = 100
PERFORMANCE_DURATION_MS_THRESHOLD_SLOW = 1000
PERFORMANCE_DURATION_DECIMAL_PLACES = 1

# Error message formatting
ERROR_CONTEXT_MAX_ITEMS = 10

# Context integration patterns
CONTEXT_CAMERA_ID_KEY = "camera_id"
CONTEXT_JOB_ID_KEY = "job_id"
CONTEXT_ERROR_KEY = "error"
CONTEXT_EXCEPTION_KEY = "exception"

# Worker message formatting
WORKER_NAME_SUFFIX_PATTERN = "_worker"
WORKER_NAME_SEPARATOR = "_"
WORKER_MESSAGE_PREFIX_PATTERN = "["

# ====================================================================
# DATABASE HANDLER CONSTANTS
# ====================================================================

# Enum conversion fallback values
FALLBACK_LOG_LEVEL = "INFO"
FALLBACK_LOG_SOURCE = "SYSTEM"
FALLBACK_LOGGER_NAME = "SYSTEM"

# Database operation timeouts (if needed in future)
DB_OPERATION_TIMEOUT_SECONDS = 30

# ====================================================================
# BATCHING CONSTANTS (from main constants.py)
# ====================================================================

# Log batching configuration (imported from main constants)
LOG_BATCH_SIZE = 100
LOG_BATCH_TIMEOUT_SECONDS = 5.0
LOG_BATCH_MAX_RETRIES = 3
LOG_BATCH_RETRY_DELAY = 1.0

# ====================================================================
# FILE HANDLER CONSTANTS (for future file handler implementation)
# ====================================================================

# File rotation settings
LOG_FILE_MAX_SIZE_MB = 10
LOG_FILE_MAX_COUNT = 10
LOG_FILE_RETENTION_DAYS = 7

# File naming patterns
LOG_FILE_BASE_NAME = "timelapser"
LOG_FILE_EXTENSION = ".log"
LOG_FILE_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

# ====================================================================
# HEALTH AND MONITORING CONSTANTS
# ====================================================================

# Handler health status
HANDLER_HEALTH_CHECK_INTERVAL_SECONDS = 60
HANDLER_FAILURE_RECOVERY_DELAY_SECONDS = 30

# Context extraction performance monitoring
CONTEXT_EXTRACTION_WARNING_TIME_MS = 100
CONTEXT_EXTRACTION_ERROR_TIME_MS = 500

# ====================================================================
# SSE HANDLER CONSTANTS (for future SSE handler implementation)
# ====================================================================

# SSE event formatting
SSE_EVENT_TYPE_LOG = "log"
SSE_EVENT_RETRY_DELAY_MS = 3000
SSE_MAX_PAYLOAD_SIZE = 1024

# SSE client management
SSE_CLIENT_TIMEOUT_SECONDS = 300
SSE_HEARTBEAT_INTERVAL_SECONDS = 30
