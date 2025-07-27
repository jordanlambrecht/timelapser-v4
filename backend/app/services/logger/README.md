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

## Configuration Options

### Database Storage Control

```python
# High-frequency logs - don't store in DB
logger_service.log_system(
    message="🔄 Health check passed",
    store_in_db=False  # Keep DB clean
)

# Important events - store in DB
logger_service.log_error(
    message="💥 Critical error occurred",
    store_in_db=True   # Store for analysis
)
```

### SSE Broadcasting Control

```python
# Error that needs immediate attention
logger_service.log_error(
    message="💥 Camera offline",
    broadcast_sse=True  # Real-time alert
)

# Debug info - no need to broadcast
logger_service.log_system(
    message="🔍 Debug info",
    broadcast_sse=False  # No noise
)
```

### File Logging Control

```python
# Configure in settings
LOGGER_SETTINGS = {
    "file_logging_enabled": True,
    "file_rotation_size": "10MB",
    "file_retention_days": 7,
    "file_log_level": LogLevel.INFO  # Only INFO and above to files
}
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

```python
# ✅ Store important events
logger_service.log_error("💥 Critical failure", store_in_db=True)
logger_service.log_worker("✅ Job completed", store_in_db=True)

# ✅ Don't store noisy events
logger_service.log_system("🔄 Health check", store_in_db=False)
logger_service.log_system("🔍 Debug trace", store_in_db=False)
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

### Before (Direct Loguru)

```python
from loguru import logger

logger.info("Processing request")
logger.error(f"Error occurred: {error}")
```

### After (LoggerService)

```python
from app.services.logger import LoggerService
from app.enums import LogLevel, LogSource, LoggerName

logger_service.log_request(
    message="📥 Processing request",
    level=LogLevel.INFO,
    source=LogSource.API,
    logger_name=LoggerName.REQUEST_LOGGER
)

logger_service.log_error(
    message=f"💥 Error occurred: {error}",
    level=LogLevel.ERROR,
    source=LogSource.API,
    logger_name=LoggerName.ERROR_HANDLER,
    error_context={"error": str(error)}
)
```

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

## Performance Considerations

- Database storage is async and non-blocking
- Console output has minimal performance impact
- File logging uses rotating handlers to manage disk space
- SSE broadcasting is optional and configurable per log
- Context extraction is optimized for minimal overhead

This logger service provides a robust, centralized logging solution that scales
with your application while maintaining excellent performance and developer
experience.
