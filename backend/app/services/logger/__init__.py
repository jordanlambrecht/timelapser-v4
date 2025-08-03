"""
Centralized Logger Service Module.

A unified logging interface with a structured, type-safe logging system.

Features:
- Type-safe enum-based logging methods
- Multiple output handlers (database, console, file, SSE)
- Configurable storage and broadcasting per log
- Worker integration and cleanup
- Performance optimized for high-frequency logging

Usage:
    from app.services.logger import Log
    from app.enums import LogLevel, LogSource, LoggerName

    log = Log(async_db, sync_db)

    await log.log_request(
        message="📥 GET /api/cameras",
        request_info={"method": "GET", "path": "/api/cameras"},
        level=LogLevel.INFO,
        source=LogSource.API,
        logger_name=LoggerName.REQUEST_LOGGER,
        store_in_db=True
    )
"""

# Re-export commonly used enums for convenience
from ...enums import LogEmoji, LoggerName, LogLevel, LogSource
from .handlers import ConsoleHandler, EnhancedDatabaseHandler, FileHandler
from .logger_service import Log, get_service_logger, initialize_global_logger, log
from .services import LogCleanupService
from .utils import ContextExtractor, LogMessageFormatter

__all__ = [
    "Log",
    "log",
    "get_service_logger",
    "initialize_global_logger",
    "EnhancedDatabaseHandler",
    "ConsoleHandler",
    "FileHandler",
    "LogCleanupService",
    "LogMessageFormatter",
    "ContextExtractor",
    # Enums
    "LogLevel",
    "LogSource",
    "LoggerName",
    "LogEmoji",
]
