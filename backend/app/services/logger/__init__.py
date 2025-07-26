"""
Centralized Logger Service Module.

This module provides a unified logging interface for the Timelapser v4 application,
replacing direct loguru usage with a structured, type-safe logging system.

Features:
- Type-safe enum-based logging methods
- Multiple output handlers (database, console, file, SSE)
- Configurable storage and broadcasting per log
- Worker integration and cleanup
- Performance optimized for high-frequency logging

Usage:
    from app.services.logger import LoggerService
    from app.enums import LogLevel, LogSource, LoggerName
    
    logger_service = LoggerService(async_db, sync_db)
    
    logger_service.log_request(
        message="📥 GET /api/cameras",
        request_info={"method": "GET", "path": "/api/cameras"},
        level=LogLevel.INFO,
        source=LogSource.API,
        logger_name=LoggerName.REQUEST_LOGGER,
        store_in_db=True
    )
"""

from .logger_service import LoggerService
from .handlers import EnhancedDatabaseHandler, ConsoleHandler, FileHandler
from .services import SSEBroadcastService, LogCleanupService
from .utils import LogMessageFormatter, ContextExtractor

# Re-export commonly used enums for convenience
from ...enums import LogLevel, LogSource, LoggerName, LogEmoji

__all__ = [
    "LoggerService",
    "EnhancedDatabaseHandler",
    "ConsoleHandler", 
    "FileHandler",
    "SSEBroadcastService",
    "LogCleanupService",
    "LogMessageFormatter",
    "ContextExtractor",
    # Enums
    "LogLevel",
    "LogSource", 
    "LoggerName",
    "LogEmoji"
]