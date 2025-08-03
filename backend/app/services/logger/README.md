# Logger Service Module

A centralized logging system for Timelapser v4 that provides unified logging
across all application components with database storage, console output, file
logging, and SSE broadcasting capabilities.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            CENTRALIZED LOGGER SERVICE                          │
│                                                                                 │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────────────┐ │
│  │   Your Code     │───▶│  LoggerService   │───▶│        Handlers             │ │
│  │                 │    │                  │    │  ┌─────────────────────────┐ │ │
│  │ • Middleware    │    │ • log_request()  │    │  │     DatabaseHandler     │ │ │
│  │ • Workers       │    │ • log_error()    │    │  │   (stores in database)  │ │ │
│  │ • Services      │    │ • log_system()   │    │  └─────────────────────────┘ │ │
│  │ • Pipelines     │    │ • log_worker()   │    │  ┌─────────────────────────┐ │ │
│  │ • Controllers   │    │ • log_capture()  │    │  │     ConsoleHandler      │ │ │
│  │                 │    │                  │    │  │   (stdout with emojis)  │ │ │
│  └─────────────────┘    └──────────────────┘    │  └─────────────────────────┘ │ │
│                                ▲                │  ┌─────────────────────────┐ │ │
│                                │                │  │      FileHandler        │ │ │
│                                │                │  │    (rotating files)     │ │ │
│                                │                │  └─────────────────────────┘ │ │
│                                │                │  ┌─────────────────────────┐ │ │
│                                │                │  │    SSEBroadcast         │ │ │
│                                │                │  │   (real-time events)    │ │ │
│                                │                │  └─────────────────────────┘ │ │
│                                │                └─────────────────────────────┘ │
│                                │                                                │
│                     ┌──────────┴───────────┐                                   │
│                     │   Utility Services   │                                   │
│                     │                      │                                   │
│                     │ • Formatters         │                                   │
│                     │ • Context Extractor  │                                   │
│                     │ • Cleanup Service    │                                   │
│                     └──────────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start Guide

### Basic Usage

```python
from app.services.logger import LoggerService, LogLevel, LogSource, LoggerName, LogEmoji

# Initialize logger service (typically done in dependency injection)
logger_service = LoggerService()

# Request logging (middleware) - auto emoji
logger_service.log_request(
    message="GET /api/cameras",  # Emoji auto-added based on source/level
    request_info={"method": "GET", "path": "/api/cameras", "status": 200},
    level=LogLevel.INFO,
    source=LogSource.API,
    logger_name=LoggerName.REQUEST_LOGGER,
    store_in_db=True
)

# Request logging with explicit emoji
logger_service.log_request(
    message="Processing special request",
    emoji=LogEmoji.CLOWN,  # Type-safe emoji! 🤡
    request_info={"method": "POST", "path": "/api/fun"},
    level=LogLevel.INFO,
    source=LogSource.API,
    logger_name=LoggerName.REQUEST_LOGGER,
    store_in_db=True
)

# Error logging with type-safe emoji
logger_service.log_error(
    message="Database connection failed",
    emoji=LogEmoji.ERROR,  # Or use LogEmoji.FIRE for dramatic effect! 🔥
    error_context={"error": str(exception), "retry_count": 3},
    level=LogLevel.ERROR,
    source=LogSource.DATABASE,
    logger_name=LoggerName.CAMERA_SERVICE,
    store_in_db=True,
    broadcast_sse=True  # Trigger real-time alert
)

# Worker logging with auto emoji selection
logger_service.log_worker(
    message="Processing thumbnail job",  # Auto-adds 👷 (worker emoji)
    worker_context={"job_id": 12345, "image_id": 67890},
    level=LogLevel.INFO,
    source=LogSource.WORKER,
    logger_name=LoggerName.THUMBNAIL_WORKER,
    store_in_db=True
)

# System logging with fun emoji
logger_service.log_system(
    message="Application startup complete",
    emoji=LogEmoji.ROCKET,  # 🚀 for startup!
    system_context={"startup_time": "2.3s", "workers": 5},
    level=LogLevel.INFO,
    source=LogSource.SYSTEM,
    logger_name=LoggerName.SYSTEM,
    store_in_db=False  # Keep DB clean
)
```

### Log Flow Architecture

```
┌─────────────────┐
│ Application     │
│ Code Calls      │
│ logger_service  │
│ .log_xxx()      │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│ LoggerService   │
│ • Validates     │
│ • Enriches      │
│ • Routes        │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ DatabaseHandler │    │ ConsoleHandler  │    │ FileHandler     │    │ SSEBroadcast    │
│                 │    │                 │    │                 │    │                 │
│ if store_in_db: │    │ Always outputs  │    │ if file_logging │    │ if broadcast_   │
│   Store in DB   │    │ to console      │    │   enabled:      │    │   sse enabled:  │
│   with proper   │    │ with emojis     │    │   Write to      │    │   Send real-    │
│   formatting    │    │ and colors      │    │   rotating log  │    │   time event    │
│                 │    │                 │    │   files         │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Service Integration Patterns

### 1. Middleware Integration

```python
# In request_logger.py
class RequestLoggerMiddleware:
    def __init__(self, app: ASGIApp, logger_service: LoggerService):
        self.logger_service = logger_service

    async def dispatch(self, request: Request, call_next):
        # Log request start
        self.logger_service.log_request(
            message=f"📥 {request.method} {request.url.path}",
            request_info={
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host
            },
            level=LogLevel.INFO,
            source=LogSource.MIDDLEWARE,
            logger_name=LoggerName.REQUEST_LOGGER
        )
```

### 2. Worker Integration

```python
# In base_worker.py
class BaseWorker:
    def __init__(self, name: str, logger_service: LoggerService):
        self.name = name
        self.logger_service = logger_service

    def log_info(self, message: str, **context):
        """Enhanced log_info that routes through LoggerService"""
        self.logger_service.log_worker(
            message=f"[{self.name}] {message}",
            worker_context=context,
            level=LogLevel.INFO,
            source=LogSource.WORKER,
            logger_name=LoggerName(self.name.lower()),
            store_in_db=True
        )
```

### 3. Service Integration

```python
# In any service class
class CameraService:
    def __init__(self, logger_service: LoggerService):
        self.logger_service = logger_service

    async def create_camera(self, camera_data):
        try:
            # ... camera creation logic ...

            self.logger_service.log_system(
                message=f"📹 Camera created: {camera.name}",
                system_context={"camera_id": camera.id, "name": camera.name},
                level=LogLevel.INFO,
                source=LogSource.CAMERA,
                logger_name=LoggerName.CAMERA_SERVICE,
                store_in_db=True,
                broadcast_sse=True  # Real-time notification
            )
        except Exception as e:
            self.logger_service.log_error(
                message=f"💥 Failed to create camera: {str(e)}",
                error_context={"error": str(e), "camera_data": camera_data},
                level=LogLevel.ERROR,
                source=LogSource.CAMERA,
                logger_name=LoggerName.CAMERA_SERVICE,
                store_in_db=True,
                broadcast_sse=True
            )
```

## Camera-Specific Logging & Frontend Filtering

The logger service provides specialized methods for camera-related events that
automatically include camera context for frontend filtering capabilities.

### Built-in Camera Logging Methods

```python
# Capture-specific logging (automatically includes camera_id)
await logger.capture(
    message="RTSP connection failed",
    camera_id=camera_id,
    capture_context={
        "error": "connection_timeout",
        "rtsp_url": camera.rtsp_url,
        "retry_count": 3
    },
    broadcast_sse=True,  # Enable real-time frontend filtering
    store_in_db=True     # Enable historical filtering
)

# Camera-specific logging
await logger.camera(
    message="Camera status changed to offline",
    camera_id=camera_id,
    camera_context={
        "camera_name": camera.name,
        "previous_status": "online",
        "new_status": "offline"
    },
    broadcast_sse=True,
    event_type="camera_status_change"
)
```

### Standard Logging with Camera Context

For any log level, include camera information in structured data:

```python
# Using extra parameter for structured logging
logger.error(
    "Camera capture pipeline failed",
    extra={
        "camera_id": camera_id,
        "camera_name": camera.name,
        "rtsp_url": camera.rtsp_url,
        "error_type": "pipeline_failure",
        "component": "capture_service"
    },
    broadcast_sse=True,  # Critical for frontend filtering
    correlation_id=request.state.correlation_id
)

# Using extra_context parameter
await log().warning(
    "Camera performance degraded",
    extra_context={
        "camera_id": camera_id,
        "camera_name": camera.name,
        "response_time_ms": 5000,
        "threshold_ms": 3000,
        "operation": "health_check"
    },
    broadcast_sse=True,
    store_in_db=True
)
```

### Frontend Integration Patterns

Enable both real-time and historical camera filtering:

```python
async def log_camera_error(
    camera_id: int,
    camera_name: str,
    error_message: str,
    error_type: str,
    correlation_id: Optional[str] = None
):
    """Log camera error with full context for frontend filtering."""

    await logger.error(
        f"Camera {camera_name}: {error_message}",
        extra={
            "camera_id": camera_id,           # Required for filtering
            "camera_name": camera_name,       # Human-readable context
            "error_type": error_type,         # Error categorization
            "component": "camera_service",    # Component identification
            "filterable": True,               # Flag for frontend filtering
            "severity": "high"                # Additional metadata
        },
        correlation_id=correlation_id,
        broadcast_sse=True,                   # Real-time filtering
        store_in_db=True,                     # Historical filtering
        event_type="camera_error"             # Event categorization
    )
```

### Frontend Filtering Capabilities

The structured camera logging enables frontend to:

- **Real-time filtering**: Subscribe to SSE events filtered by `camera_id`
- **Historical queries**: Search database logs by camera ID, name, or error type
- **Event categorization**: Filter by `event_type` (camera_error, camera_status,
  etc.)
- **Correlation tracking**: Follow complete request flows using `correlation_id`
- **Component filtering**: Filter by service component (capture_service,
  camera_service, etc.)

```javascript
// Frontend SSE filtering example
const eventSource = new EventSource("/api/sse/events")
eventSource.onmessage = (event) => {
  const logData = JSON.parse(event.data)

  // Filter by camera
  if (logData.camera_id === selectedCameraId) {
    displayCameraLog(logData)
  }

  // Filter by error type
  if (logData.event_type === "camera_error") {
    showErrorNotification(logData)
  }
}
```

## Configuration Options

The logger service respects user-configurable settings stored in the database, allowing fine-grained control over logging behavior without requiring code changes or application restarts.

### User-Configurable Settings

All logging settings are managed through the application's settings system and can be modified via the API or admin interface:

#### Database Logging Settings

- **`db_log_retention_days`** - Number of days to retain logs in database (default: 30)
- **`db_log_level`** - Minimum log level for database storage (DEBUG, INFO, WARNING, ERROR, CRITICAL)

#### File Logging Settings

- **`file_log_retention_days`** - Number of days to retain log files (default: 7)
- **`file_log_level`** - Minimum log level for file logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **`file_log_max_files`** - Maximum number of log files to keep (default: 10)
- **`file_log_max_size`** - Maximum size per log file in MB (default: 10)
- **`file_log_enable_compression`** - Enable gzip compression for rotated files (default: true)
- **`file_log_enable_rotation`** - Enable log file rotation (default: true)

#### Debug Storage Control

- **`debug_logs_store_in_db`** - Enable database storage for debug logs (default: false)

### Setting Configuration Examples

#### Via API

```bash
# Configure database log retention
curl -X PUT /api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "db_log_retention_days": "14",
    "db_log_level": "INFO"
  }'

# Configure file logging
curl -X PUT /api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "file_log_retention_days": "7",
    "file_log_level": "WARNING",
    "file_log_max_files": "5",
    "file_log_max_size": "25",
    "file_log_enable_compression": "true",
    "file_log_enable_rotation": "true"
  }'

# Enable debug log storage
curl -X PUT /api/settings \
  -H "Content-Type: application/json" \
  -d '{"debug_logs_store_in_db": "true"}'
```

#### Via Settings Service

```python
from app.services.settings_service import SettingsService

async def configure_logging_settings(settings_service: SettingsService):
    """Configure logging settings programmatically."""
    
    # Database logging configuration
    await settings_service.update_setting("db_log_retention_days", "30")
    await settings_service.update_setting("db_log_level", "INFO")
    
    # File logging configuration  
    await settings_service.update_setting("file_log_retention_days", "14")
    await settings_service.update_setting("file_log_level", "WARNING")
    await settings_service.update_setting("file_log_max_files", "8")
    await settings_service.update_setting("file_log_max_size", "20")
    await settings_service.update_setting("file_log_enable_compression", "true")
    await settings_service.update_setting("file_log_enable_rotation", "true")
    
    # Debug storage control
    await settings_service.update_setting("debug_logs_store_in_db", "false")
```

### How Settings Affect Logging Behavior

#### Database Storage Control

```python
# The logger service automatically respects db_log_level setting
logger.debug("Debug info")    # Stored only if db_log_level <= DEBUG
logger.info("Info message")   # Stored only if db_log_level <= INFO  
logger.warning("Warning!")    # Stored only if db_log_level <= WARNING
logger.error("Error occurred") # Stored only if db_log_level <= ERROR

# Manual override still works
logger.debug("Always store this", store_in_db=True)  # Ignores db_log_level
logger.error("Never store this", store_in_db=False)  # Ignores db_log_level
```

#### File Logging Control

```python
# File logging respects file_log_level setting
logger.debug("Debug to file")    # Written only if file_log_level <= DEBUG
logger.warning("Warning to file") # Written only if file_log_level <= WARNING

# File rotation behavior controlled by settings:
# - file_log_max_size: Rotate when file exceeds this size
# - file_log_max_files: Keep this many historical files
# - file_log_enable_compression: Compress rotated files
# - file_log_retention_days: Delete files older than this
```

#### Level Hierarchy

Log levels follow standard hierarchy (lower values are more verbose):

```python
LogLevel.DEBUG     = 10  # Most verbose
LogLevel.INFO      = 20
LogLevel.WARNING   = 30  
LogLevel.ERROR     = 40
LogLevel.CRITICAL  = 50  # Least verbose
```

### Configuration Best Practices

#### Production Settings

```python
# Recommended production configuration
PRODUCTION_SETTINGS = {
    # Database - moderate retention, avoid debug noise
    "db_log_retention_days": "14",
    "db_log_level": "INFO",
    "debug_logs_store_in_db": "false",
    
    # File logging - longer retention for troubleshooting
    "file_log_retention_days": "30", 
    "file_log_level": "WARNING",
    "file_log_max_files": "10",
    "file_log_max_size": "50",
    "file_log_enable_compression": "true",
    "file_log_enable_rotation": "true"
}
```

#### Development Settings

```python
# Recommended development configuration  
DEVELOPMENT_SETTINGS = {
    # Database - shorter retention, more verbose
    "db_log_retention_days": "3",
    "db_log_level": "DEBUG", 
    "debug_logs_store_in_db": "true",
    
    # File logging - minimal for local development
    "file_log_retention_days": "1",
    "file_log_level": "DEBUG",
    "file_log_max_files": "3", 
    "file_log_max_size": "10",
    "file_log_enable_compression": "false",
    "file_log_enable_rotation": "true"
}
```

#### Troubleshooting Settings

```python
# High-verbosity configuration for debugging issues
TROUBLESHOOTING_SETTINGS = {
    # Database - capture everything temporarily
    "db_log_retention_days": "1",
    "db_log_level": "DEBUG",
    "debug_logs_store_in_db": "true",
    
    # File logging - maximum detail
    "file_log_retention_days": "3",
    "file_log_level": "DEBUG", 
    "file_log_max_files": "5",
    "file_log_max_size": "100",
    "file_log_enable_compression": "true",
    "file_log_enable_rotation": "true"
}
```

### Settings Caching and Performance

The logger service implements intelligent caching for settings to minimize database overhead:

- **Cache Duration**: 30 seconds for most settings
- **Cache Invalidation**: Automatic when settings are updated
- **Fallback Behavior**: Safe defaults if settings unavailable
- **Batch Loading**: Multiple settings loaded in single query when possible

### Dynamic Configuration

Settings changes take effect immediately without requiring application restart:

```python
# Settings are checked on each log operation and cached intelligently
logger.info("This message respects current db_log_level setting")

# Update setting via API
curl -X PUT /api/settings -d '{"db_log_level": "ERROR"}'

# Subsequent logs immediately respect new setting
logger.info("This message may not be stored if db_log_level is now ERROR")
```

## Type-Safe Emoji System

The logger supports both automatic emoji selection and explicit type-safe emoji
specification:

### Automatic Emoji Selection

When no emoji is provided, the system intelligently selects emojis based on:

1. **Message content** - Keywords like "request", "error", "capture"
2. **Log level** - ERROR→💥, WARNING→⚠️, DEBUG→🔍
3. **Source** - CAMERA→📹, WORKER→👷, API→📥
4. **Logger name** - THUMBNAIL_WORKER→🖼️, VIDEO_PIPELINE→🎥

### Explicit Emoji Usage

```python
# Type-safe emoji specification
logger_service.log_error(
    message="Something went wrong",
    emoji=LogEmoji.CLOWN,  # 🤡 - Because sometimes you need humor!
    level=LogLevel.ERROR
)

# Available fun emojis
LogEmoji.CLOWN     # 🤡
LogEmoji.PARTY     # 🎉
LogEmoji.FIRE      # 🔥
LogEmoji.ROCKET    # 🚀
LogEmoji.MAGIC     # ✨
LogEmoji.ROBOT     # 🤖
```

### Smart Emoji Fallbacks

1. **Explicit emoji** (if provided) → Used directly
2. **Auto-detection** (if enabled) → Smart selection based on context
3. **Level-based fallback** → LogLevel.ERROR → LogEmoji.ERROR
4. **Source-based fallback** → LogSource.CAMERA → LogEmoji.CAMERA
5. **No emoji** → Clean message without emoji prefix

## Enum Reference

### LogLevel

- `LogLevel.DEBUG` - Detailed debugging information
- `LogLevel.INFO` - General information messages
- `LogLevel.WARNING` - Warning messages
- `LogLevel.ERROR` - Error messages
- `LogLevel.CRITICAL` - Critical system failures

### LogSource

- `LogSource.API` - API endpoints and controllers
- `LogSource.WORKER` - Background workers
- `LogSource.SYSTEM` - System-level events
- `LogSource.CAMERA` - Camera-related events
- `LogSource.DATABASE` - Database operations
- `LogSource.SCHEDULER` - Scheduler operations
- `LogSource.PIPELINE` - Pipeline operations
- `LogSource.MIDDLEWARE` - Middleware operations

### LoggerName

- `LoggerName.REQUEST_LOGGER` - HTTP request logging
- `LoggerName.ERROR_HANDLER` - Error handler middleware
- `LoggerName.CAPTURE_WORKER` - Image capture worker
- `LoggerName.THUMBNAIL_WORKER` - Thumbnail generation worker
- `LoggerName.OVERLAY_WORKER` - Overlay generation worker
- `LoggerName.SCHEDULER_WORKER` - Scheduler worker
- `LoggerName.VIDEO_PIPELINE` - Video generation pipeline
- `LoggerName.CAPTURE_PIPELINE` - Image capture pipeline
- `LoggerName.CAMERA_SERVICE` - Camera service operations
- `LoggerName.SYSTEM` - System-level operations

## Best Practices

### 1. Use Appropriate Log Levels

```python
# ✅ Good
logger_service.log_worker("🔄 Job started", level=LogLevel.INFO)
logger_service.log_error("💥 Job failed", level=LogLevel.ERROR)

# ❌ Bad
logger_service.log_worker("💥 Job failed", level=LogLevel.INFO)  # Wrong level
```

### 2. Include Context Information

```python
# ✅ Good
logger_service.log_worker(
    message="🔄 Processing thumbnail",
    worker_context={
        "job_id": 123,
        "image_id": 456,
        "retry_count": 0
    }
)

# ❌ Bad
logger_service.log_worker("🔄 Processing thumbnail")  # No context
```

### 3. Use Emojis Consistently

```python
# ✅ Good emoji patterns
"📥 Incoming request"    # Incoming data
"📤 Outgoing response"   # Outgoing data
"🔄 Processing job"      # Work in progress
"✅ Job completed"       # Success
"💥 Job failed"          # Error
"⚠️ Warning condition"   # Warning
"📹 Camera event"        # Camera-related
"🎥 Video event"         # Video-related
"🖼️ Image event"         # Image-related
"⚙️ System event"        # System-related
```

### 4. Control Database Storage

Follow these guidelines for what should/shouldn't be stored in the database:

```python
# ✅ ALWAYS STORE - Important for audit trails and debugging
logger.error("Critical system failure", store_in_db=True, emoji=LogEmoji.FIRE)
logger.info("Video generation completed", store_in_db=True, emoji=LogEmoji.CHECK_MARK)  # Job outcomes
logger.warning("Camera disconnected", store_in_db=True, emoji=LogEmoji.CAMERA)         # Connectivity issues
logger.info("Video generation started", store_in_db=True, emoji=LogEmoji.MOVIE_CAMERA) # Job executions

# ❌ DON'T STORE - Noisy events that clutter the database
logger.debug("Processing frame 1234", store_in_db=False, emoji=LogEmoji.MAGNIFYING_GLASS)  # Progress updates
logger.info("Health check passed", store_in_db=False, emoji=LogEmoji.HEART)                # Heartbeats
logger.debug("Memory usage: 45%", store_in_db=False, emoji=LogEmoji.CHART)                 # Routine metrics
logger.info("Processing image batch", store_in_db=False, emoji=LogEmoji.RECYCLE)           # High frequency events

# 🎯 CASE-BY-CASE - Depends on context and importance to frontend users
logger.info("Settings updated", store_in_db=True, emoji=LogEmoji.GEAR)           # User actions - store
logger.warning("High CPU usage", store_in_db=True, emoji=LogEmoji.WARNING)       # Performance issues - store
logger.info("SSE client connected", store_in_db=False, emoji=LogEmoji.PLUG)      # Connection events - don't store

# 🎮 DEBUG STORAGE - Controlled by user settings, can be liberal with store_in_db=True
logger.debug("Function entry", store_in_db=True, emoji=LogEmoji.WRENCH)          # User can toggle debug storage via settings
```

### 5. Use SSE Broadcasting Wisely

```python
# ✅ Broadcast user-facing events
logger_service.log_error("💥 Camera offline", broadcast_sse=True)
logger_service.log_system("✅ Video generated", broadcast_sse=True)

# ✅ Don't broadcast internal events
logger_service.log_system("🔄 Internal cleanup", broadcast_sse=False)
```

## Migration from Direct Loguru Usage

We provide multiple patterns for migrating from direct loguru usage, depending
on your preferences and requirements.

### Pattern 1: Service Logger Factory (Recommended)

The cleanest approach uses a factory function to create pre-configured loggers
for each service:

```python
# In logger_service.py - add this factory function
def get_service_logger(logger_name: LoggerName, source: LogSource = LogSource.SYSTEM):
    """
    Factory function to create a pre-configured logger for a specific service.

    Returns a logger with simplified methods that automatically include
    the correct source and logger_name parameters.
    """
    class ServiceLogger:
        @staticmethod
        def error(message: str, exception: Optional[Exception] = None, **kwargs):
            return log().error(message, exception=exception, source=source, logger_name=logger_name, **kwargs)

        @staticmethod
        def warning(message: str, **kwargs):
            return log().warning(message, source=source, logger_name=logger_name, **kwargs)

        @staticmethod
        def info(message: str, **kwargs):
            return log().info(message, source=source, logger_name=logger_name, **kwargs)

        @staticmethod
        def debug(message: str, **kwargs):
            return log().debug(message, source=source, logger_name=logger_name, **kwargs)

    return ServiceLogger()

# Usage in your service files:
from ...services.logger import get_service_logger, LogEmoji
from ...enums import LoggerName

logger = get_service_logger(LoggerName.VIDEO_PIPELINE)

# Simple calls (just like before):
logger.error("Something went wrong", exception=e)
logger.info("Processing completed")
logger.debug("Debug information")

# Rich feature usage with emojis and control:
logger.error("Critical system failure", exception=e, emoji=LogEmoji.FIRE, broadcast_sse=True)
logger.info("Video generation complete", emoji=LogEmoji.PARTY, broadcast_sse=True, store_in_db=True)
logger.warning("High memory usage detected", extra_context={"memory_usage": "85%"}, emoji=LogEmoji.WARNING)
logger.debug("Processing frame 1205", store_in_db=True, emoji=LogEmoji.MAGNIFYING_GLASS)

# Event broadcasting for real-time updates:
logger.info("Camera connected", broadcast_sse=True, event_type="camera_status", emoji=LogEmoji.CAMERA)
logger.error("Connection lost", broadcast_sse=True, correlation_id=request_id, emoji=LogEmoji.EXPLOSION)
```

### Pattern 2: Direct LoggerService Usage

For more control and explicit parameters:

```python
from app.services.logger import log
from app.enums import LogLevel, LogSource, LoggerName

# Basic usage with explicit parameters
log().error(
    message=f"💥 Error occurred: {error}",
    exception=error,
    source=LogSource.SYSTEM,
    logger_name=LoggerName.VIDEO_PIPELINE
)

log().info(
    message="📥 Processing request",
    source=LogSource.API,
    logger_name=LoggerName.REQUEST_LOGGER
)
```

### Pattern 3: Constants for Repeated Parameters

For reducing repetition while maintaining explicitness:

```python
from app.services.logger import log
from app.enums import LogSource, LoggerName

# Define constants for your service
LOGGER_PARAMS = {"source": LogSource.SYSTEM, "logger_name": LoggerName.VIDEO_PIPELINE}

# Usage
log().error("Error occurred", exception=e, **LOGGER_PARAMS)
log().info("Processing completed", **LOGGER_PARAMS)
```

### Migration Examples

#### Before (Direct Loguru)

```python
from loguru import logger

logger.info("Processing request")
logger.error(f"Error occurred: {error}")
logger.debug("Debug information")
logger.warning("Something suspicious")
```

#### After (Service Logger Factory - Recommended)

```python
from ...services.logger import get_service_logger, LogEmoji
from ...enums import LoggerName

logger = get_service_logger(LoggerName.VIDEO_PIPELINE)

# Simple usage (clean syntax maintained):
logger.info("Processing request")
logger.error(f"Error occurred: {error}", exception=error)
logger.debug("Debug information")
logger.warning("Something suspicious")

# Rich feature usage when needed:
logger.info("Video processing started", emoji=LogEmoji.MOVIE_CAMERA, broadcast_sse=True)
logger.error("Pipeline failure", exception=error, emoji=LogEmoji.FIRE, broadcast_sse=True)
logger.debug("Frame analysis", extra_context={"frame": 1205}, store_in_db=True, emoji=LogEmoji.MAGNIFYING_GLASS)
logger.warning("Performance issue", extra_context={"cpu_usage": "95%"}, broadcast_sse=True, emoji=LogEmoji.WARNING)
```

#### After (Direct Usage)

```python
from ...services.logger import log
from ...enums import LogSource, LoggerName

log().info("Processing request", source=LogSource.SYSTEM, logger_name=LoggerName.VIDEO_PIPELINE)
log().error(f"Error occurred: {error}", exception=error, source=LogSource.SYSTEM, logger_name=LoggerName.VIDEO_PIPELINE)
log().debug("Debug information", source=LogSource.SYSTEM, logger_name=LoggerName.VIDEO_PIPELINE)
log().warning("Something suspicious", source=LogSource.SYSTEM, logger_name=LoggerName.VIDEO_PIPELINE)
```

### Choosing the Right Pattern

- **Service Logger Factory**: Best for most use cases - clean, simple, no
  repetition
- **Direct Usage**: Best when you need different sources/logger_names in the
  same file
- **Constants Pattern**: Good middle-ground when you want explicit control but
  less repetition

## Troubleshooting

### Common Issues

1. **Logs not appearing in database**

   - Check `store_in_db=True` is set
   - Verify database connection is healthy
   - Check log level filtering in database settings

2. **SSE events not broadcasting**

   - Verify `broadcast_sse=True` is set
   - Check SSE service is running
   - Confirm SSE event types are configured

3. **File logs not being written**

   - Check file logging is enabled in settings
   - Verify file permissions and disk space
   - Check log rotation settings

4. **Missing context information**
   - Always include relevant context dictionaries
   - Use appropriate enum values for categorization
   - Include correlation IDs for request tracing

## Debug Storage Gateway

The Debug Storage Gateway is a user-configurable feature that provides
fine-grained control over whether debug logs are stored in the database,
balancing observability needs with performance requirements.

### How It Works

#### User Setting Configuration

- **Setting Key**: `debug_logs_store_in_db`
- **Default Value**: `false` (optimized for performance)
- **Type**: boolean
- **Description**: Enable database storage for debug logs (impacts performance)

The logger service automatically creates this setting with the default value if
it doesn't exist.

#### Usage Patterns

**Default Behavior (Respects User Setting):**

```python
from backend.app.services.logger import get_service_logger
from backend.app.enums import LoggerName

logger = get_service_logger(LoggerName.API)

# Checks user setting to determine if debug logs should be stored
logger.debug("This debug message respects user settings")
```

**Override Behavior (Explicit Control):**

```python
# Force storage regardless of user setting
logger.debug("Always store this", store_in_db=True)

# Force no storage regardless of user setting
logger.debug("Never store this", store_in_db=False)
```

#### Setting Management via API

Users can control debug log storage through the settings API:

```bash
# Enable debug log storage
curl -X PUT /api/settings \
  -H "Content-Type: application/json" \
  -d '{"debug_logs_store_in_db": "true"}'

# Disable debug log storage (default)
curl -X PUT /api/settings \
  -H "Content-Type: application/json" \
  -d '{"debug_logs_store_in_db": "false"}'
```

#### Performance Optimizations

- **Caching**: Setting values cached for 30 seconds to minimize database queries
- **Fallback**: Defaults to `false` (no storage) if settings unavailable,
  maintaining performance
- **Smart Parsing**: Converts string values ('true', '1', 'yes', 'on') to
  boolean
- **Default Off**: Debug logs not stored by default for optimal performance

#### Implementation Flow

1. **Cache Check**: Verifies if setting is cached and valid (30s TTL)
2. **Database Query**: Queries settings table if not cached
3. **Value Parsing**: Converts string values to boolean
4. **Fallback Handling**: Defaults to `false` if setting missing or query fails
5. **Result Caching**: Stores result for 30 seconds to improve performance

This gateway enables precise control over debug log storage while maintaining
excellent performance characteristics.

## Exception-Based Logging Architecture

The logging service implements an exception-based architecture to eliminate
circular imports and ensure clean separation of concerns. This pattern was
developed to solve critical architectural issues discovered during system
debugging.

### Architecture Pattern: Database → Exceptions → Services → Logger

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│                     │    │                     │    │                     │    │                     │
│  Database Layer     │───▶│   Exception Layer   │───▶│   Service Layer     │───▶│   Logger Service    │
│                     │    │                     │    │                     │    │                     │
│ • Operations        │    │ • Domain Exceptions │    │ • Business Logic    │    │ • Centralized       │
│ • Direct DB Access  │    │ • Error Context     │    │ • Service Coord.    │    │   Logging           │
│ • No Business Logic │    │ • Exception Chains  │    │ • Exception Handling│    │ • Multi-Output      │
│                     │    │                     │    │                     │    │                     │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

### Key Principles

1. **Database Operations Never Log Directly**: Database operations raise
   domain-specific exceptions instead of logging
2. **Services Handle Exceptions**: Services catch exceptions and log them with
   appropriate context
3. **Domain-Specific Exceptions**: Each domain has specific exception types
   (CameraOperationError, SettingsOperationError, etc.)
4. **Clean Dependency Flow**: No circular imports between database operations
   and logging

### Implementation Pattern

#### Database Operations Layer

```python
# In database/camera_operations.py
from .exceptions import CameraOperationError

async def get_active_cameras():
    """Database operation that raises exceptions instead of logging."""
    try:
        # Database operation
        result = await execute_query("SELECT * FROM cameras WHERE enabled = true")
        return result
    except (psycopg.Error, KeyError, ValueError) as e:
        # Raise domain exception instead of logging
        raise CameraOperationError(
            "Failed to retrieve active cameras",
            operation="get_active_cameras"
        ) from e
```

#### Exception Layer

```python
# In database/exceptions.py
class CameraOperationError(Exception):
    """Domain-specific exception for camera operations."""
    def __init__(self, message: str, operation: str = None, **context):
        super().__init__(message)
        self.operation = operation
        self.context = context
```

#### Service Layer

```python
# In services/camera_service.py
from ..database.exceptions import CameraOperationError
from .logger import get_service_logger

logger = get_service_logger(LoggerName.CAMERA_SERVICE, LogSource.CAMERA)

async def get_cameras(self):
    """Service method that handles exceptions and logs appropriately."""
    try:
        return await self.camera_ops.get_active_cameras()
    except CameraOperationError as e:
        # Service layer handles logging with full context
        logger.error(
            f"❌ Database error retrieving cameras: {e}",
            exception=e,
            extra_context={
                "operation": e.operation,
                **e.context
            },
            broadcast_sse=True,
            store_in_db=True
        )
        raise
```

### Benefits of Exception-Based Architecture

1. **Eliminates Circular Imports**: Database operations don't import logger
   service
2. **Clean Separation**: Each layer has a single responsibility
3. **Better Error Context**: Exceptions carry rich context information
4. **Consistent Error Handling**: Services handle all logging consistently
5. **Testable**: Database operations can be tested without logger dependencies

### Domain Exception Types

```python
# Database exception hierarchy
CameraOperationError     # Camera-related database operations
SettingsOperationError   # Settings-related database operations
VideoOperationError      # Video-related database operations
ImageOperationError      # Image-related database operations
TimelapseOperationError  # Timelapse-related database operations
StatisticsOperationError # Statistics-related database operations
```

### Architectural Guidelines

1. **Services Use Service Layer**: Services should coordinate with other
   services, not access database operations directly
2. **SettingsService vs SettingsOperations**: Services should use
   `SettingsService`, only `SettingsService` should use `SettingsOperations`
3. **Exception Chaining**: Always use `from e` to preserve original exception
   context
4. **Rich Context**: Include operation names and relevant parameters in
   exceptions
5. **Consistent Patterns**: Apply the same exception-based pattern across all
   domains

### Migration from Direct Logging

#### Before (Direct Logging - Causes Circular Imports)

```python
# ❌ BAD: Database operation directly imports logger
from ..services.logger import get_service_logger

async def get_cameras():
    try:
        result = await execute_query("SELECT * FROM cameras")
        logger.info("Retrieved cameras successfully")  # Creates circular import
        return result
    except Exception as e:
        logger.error(f"Failed to get cameras: {e}")  # Creates circular import
        raise
```

#### After (Exception-Based - Clean Architecture)

```python
# ✅ GOOD: Database operation raises domain exception
from .exceptions import CameraOperationError

async def get_cameras():
    try:
        result = await execute_query("SELECT * FROM cameras")
        return result
    except (psycopg.Error, KeyError, ValueError) as e:
        raise CameraOperationError(
            "Failed to retrieve cameras",
            operation="get_cameras"
        ) from e

# Service layer handles logging
try:
    cameras = await self.camera_ops.get_cameras()
    logger.info("✅ Retrieved cameras successfully")
except CameraOperationError as e:
    logger.error(f"❌ Database error: {e}", exception=e)
    raise
```

This exception-based architecture ensures maintainable, testable code while
providing excellent logging capabilities throughout the system.

## Performance Considerations

- Database storage is async and non-blocking
- Console output has minimal performance impact
- File logging uses rotating handlers to manage disk space
- SSE broadcasting is optional and configurable per log
- Context extraction is optimized for minimal overhead
- Exception-based pattern adds minimal overhead while eliminating circular
  dependencies

This logger service provides a robust, centralized logging solution that scales
with your application while maintaining excellent performance and developer
experience.
