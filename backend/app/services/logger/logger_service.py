"""
Centralized Logger Service for Timelapser v4.

This service provides a unified logging interface that handles:
- Database storage with proper message extraction
- Console output with emoji support
- File logging with rotation
- SSE broadcasting for real-time events
- Worker integration and cleanup

Architecture:
- Type-safe enum-based configuration
- Multiple handler support
- Configurable storage and broadcasting
- Performance optimized for high-frequency logging
"""

from typing import Dict, Any, Optional
from loguru import logger


from ...enums import LogLevel, LogSource, LoggerName, LogEmoji, SSEEvent, SSEPriority
from ...database.core import AsyncDatabase, SyncDatabase
from ...database.log_operations import LogOperations, SyncLogOperations
from ...database.sse_events_operations import (
    SSEEventsOperations,
    SyncSSEEventsOperations,
)

# Timezone utilities available if needed
from ...utils.time_utils import utc_now
from .handlers.database_handler import EnhancedDatabaseHandler
from .handlers.batching_database_handler import BatchingDatabaseHandler
from .handlers.console_handler import ConsoleHandler
from .handlers.file_handler import FileHandler

# SSE operations imported below with other database operations
from .services.cleanup_service import LogCleanupService
from .utils.formatters import LogMessageFormatter
from .utils.context_extractor import ContextExtractor


class LoggerService:
    """
    Centralized logging service that provides unified logging across all application components.

    Features:
    - Type-safe enum-based logging methods
    - Multiple output handlers (database, console, file, SSE)
    - Configurable storage and broadcasting per log
    - Worker integration and cleanup
    - Performance optimized for high-frequency logging

    Usage:
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

    def __init__(
        self,
        async_db: AsyncDatabase,
        sync_db: SyncDatabase,
        enable_console: bool = True,
        enable_file_logging: bool = True,
        enable_sse_broadcasting: bool = True,
        enable_batching: bool = True,
    ):
        """
        Initialize the logger service with database connections and handler configuration.

        Args:
            async_db: Async database instance for async operations
            sync_db: Sync database instance for sync operations
            enable_console: Enable console output handler
            enable_file_logging: Enable file logging handler
            enable_sse_broadcasting: Enable SSE broadcasting handler
            enable_batching: Enable batching for high-frequency logging (default: True)
        """
        # Database instances
        self.async_db = async_db
        self.sync_db = sync_db

        # Database operations
        self.async_log_ops = LogOperations(async_db)
        self.sync_log_ops = SyncLogOperations(sync_db)
        self.sse_ops = SSEEventsOperations(async_db)
        self.sync_sse_ops = SyncSSEEventsOperations(sync_db)

        # Utility services
        self.formatter = LogMessageFormatter()
        self.context_extractor = ContextExtractor()

        # Handler configuration
        self.enable_console = enable_console
        self.enable_file_logging = enable_file_logging
        self.enable_sse_broadcasting = enable_sse_broadcasting
        self.enable_batching = enable_batching

        # Initialize handlers
        self._initialize_handlers()

        # Cleanup service
        self.cleanup_service = LogCleanupService(self.async_log_ops, self.sync_log_ops)

    def _initialize_handlers(self) -> None:
        """Initialize all logging handlers based on configuration."""
        # Database handler (choose batching or regular based on configuration)
        if self.enable_batching:
            self.database_handler = BatchingDatabaseHandler(
                self.async_log_ops, self.sync_log_ops
            )
        else:
            self.database_handler = EnhancedDatabaseHandler(
                self.async_log_ops, self.sync_log_ops
            )

        # Console handler
        if self.enable_console:
            self.console_handler = ConsoleHandler()

        # File handler
        if self.enable_file_logging:
            self.file_handler = FileHandler()

        # SSE operations for broadcasting (direct pattern like other services)

    # Core Logging Methods

    async def log_request(
        self,
        message: str,
        request_info: Optional[Dict[str, Any]] = None,
        level: LogLevel = LogLevel.INFO,
        source: LogSource = LogSource.API,
        logger_name: LoggerName = LoggerName.REQUEST_LOGGER,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Log HTTP request events with structured request information.

        Args:
            message: Log message (emoji will be auto-added if not provided)
            request_info: Request context (method, path, status, etc.)
            level: Log level using LogLevel enum
            source: Log source using LogSource enum
            logger_name: Logger name using LoggerName enum
            emoji: Optional emoji (defaults to smart selection based on level/source/logger)
            store_in_db: Whether to store in database
            broadcast_sse: Whether to broadcast via SSE
            correlation_id: Optional correlation ID for request tracing
        """
        await self._log_entry(
            message=message,
            level=level,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=request_info or {},
            store_in_db=store_in_db,
            broadcast_sse=broadcast_sse,
            correlation_id=correlation_id,
            event_type=SSEEvent.LOG_REQUESTED,
        )

    async def log_error(
        self,
        message: str,
        error_context: Optional[Dict[str, Any]] = None,
        level: LogLevel = LogLevel.ERROR,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.ERROR_HANDLER,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        broadcast_sse: bool = True,  # Errors usually need immediate attention
        correlation_id: Optional[str] = None,
        exception: Optional[Exception] = None,
    ) -> None:
        """
        Log error events with structured error information.

        Args:
            message: Error message (emoji will be auto-added if not provided)
            error_context: Error context (error details, stack trace, etc.)
            level: Log level using LogLevel enum
            source: Log source using LogSource enum
            logger_name: Logger name using LoggerName enum
            emoji: Optional emoji (defaults to smart selection based on level/source/logger)
            store_in_db: Whether to store in database
            broadcast_sse: Whether to broadcast via SSE (default True for errors)
            correlation_id: Optional correlation ID for request tracing
            exception: Optional exception object for additional context
        """
        # Enrich error context with exception details if provided
        if exception and error_context is not None:
            error_context.update(
                {
                    "exception_type": type(exception).__name__,
                    "exception_message": str(exception),
                }
            )
        elif exception:
            error_context = {
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
            }

        await self._log_entry(
            message=message,
            level=level,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=error_context or {},
            store_in_db=store_in_db,
            broadcast_sse=broadcast_sse,
            correlation_id=correlation_id,
            event_type="error_log",
            sse_priority=(
                SSEPriority.HIGH
                if level in [LogLevel.ERROR, LogLevel.CRITICAL]
                else SSEPriority.NORMAL
            ),
        )

    async def log_worker(
        self,
        message: str,
        worker_context: Optional[Dict[str, Any]] = None,
        level: LogLevel = LogLevel.INFO,
        source: LogSource = LogSource.WORKER,
        logger_name: LoggerName = LoggerName.UNKNOWN,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Log worker events with structured worker information.

        Args:
            message: Worker message (emoji will be auto-added if not provided)
            worker_context: Worker context (job_id, worker_name, etc.)
            level: Log level using LogLevel enum
            source: Log source using LogSource enum
            logger_name: Logger name using LoggerName enum
            emoji: Optional emoji (defaults to smart selection based on level/source/logger)
            store_in_db: Whether to store in database
            broadcast_sse: Whether to broadcast via SSE
            correlation_id: Optional correlation ID for request tracing
        """
        await self._log_entry(
            message=message,
            level=level,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=worker_context or {},
            store_in_db=store_in_db,
            broadcast_sse=broadcast_sse,
            correlation_id=correlation_id,
            event_type=SSEEvent.LOG_FOR_WORKER,
        )

    async def log_system(
        self,
        message: str,
        system_context: Optional[Dict[str, Any]] = None,
        level: LogLevel = LogLevel.INFO,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.SYSTEM,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = False,  # System logs often don't need DB storage
        broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Log system events with structured system information.

        Args:
            message: System message (emoji will be auto-added if not provided)
            system_context: System context (startup_time, config_changes, etc.)
            level: Log level using LogLevel enum
            source: Log source using LogSource enum
            logger_name: Logger name using LoggerName enum
            emoji: Optional emoji (defaults to smart selection based on level/source/logger)
            store_in_db: Whether to store in database (default False for system logs)
            broadcast_sse: Whether to broadcast via SSE
            correlation_id: Optional correlation ID for request tracing
        """
        await self._log_entry(
            message=message,
            level=level,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=system_context or {},
            store_in_db=store_in_db,
            broadcast_sse=broadcast_sse,
            correlation_id=correlation_id,
            event_type=SSEEvent.LOG_FOR_SYSTEM,
        )

    async def log_capture(
        self,
        message: str,
        capture_context: Optional[Dict[str, Any]] = None,
        level: LogLevel = LogLevel.INFO,
        source: LogSource = LogSource.CAMERA,
        logger_name: LoggerName = LoggerName.CAPTURE_PIPELINE,
        emoji: Optional[LogEmoji] = None,
        camera_id: Optional[int] = None,
        store_in_db: bool = True,
        broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Log capture events with camera and capture context.

        Args:
            message: Capture message (emoji will be auto-added if not provided)
            capture_context: Capture context (image_id, file_size, etc.)
            level: Log level using LogLevel enum
            source: Log source using LogSource enum
            logger_name: Logger name using LoggerName enum
            emoji: Optional emoji (defaults to smart selection based on level/source/logger)
            camera_id: Camera ID for camera-specific logs
            store_in_db: Whether to store in database
            broadcast_sse: Whether to broadcast via SSE
            correlation_id: Optional correlation ID for request tracing
        """
        # Ensure camera_id is included in context
        if capture_context is None:
            capture_context = {}
        if camera_id is not None:
            capture_context["camera_id"] = camera_id

        await self._log_entry(
            message=message,
            level=level,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            camera_id=camera_id,
            extra_context=capture_context,
            store_in_db=store_in_db,
            broadcast_sse=broadcast_sse,
            correlation_id=correlation_id,
            event_type=SSEEvent.LOG_FOR_CAPTURE,
        )

    # Sync versions for worker compatibility

    def log_worker_sync(
        self,
        message: str,
        worker_context: Optional[Dict[str, Any]] = None,
        level: LogLevel = LogLevel.INFO,
        source: LogSource = LogSource.WORKER,
        logger_name: LoggerName = LoggerName.UNKNOWN,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Sync version of worker logging for use in sync worker contexts.

        Args:
            message: Worker message
            worker_context: Worker context
            level: Log level
            source: Log source
            logger_name: Logger name
            store_in_db: Whether to store in database
            correlation_id: Optional correlation ID
        """
        self._log_entry_sync(
            message=message,
            level=level,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=worker_context or {},
            store_in_db=store_in_db,
            correlation_id=correlation_id,
        )

    def log_error_sync(
        self,
        message: str,
        error_context: Optional[Dict[str, Any]] = None,
        level: LogLevel = LogLevel.ERROR,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.ERROR_HANDLER,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        correlation_id: Optional[str] = None,
        exception: Optional[Exception] = None,
    ) -> None:
        """
        Sync version of error logging for use in sync worker contexts.

        Args:
            message: Error message
            error_context: Error context
            level: Log level
            source: Log source
            logger_name: Logger name
            store_in_db: Whether to store in database
            correlation_id: Optional correlation ID
            exception: Optional exception object
        """
        # Enrich error context with exception details if provided
        if exception and error_context is not None:
            error_context.update(
                {
                    "exception_type": type(exception).__name__,
                    "exception_message": str(exception),
                }
            )
        elif exception:
            error_context = {
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
            }

        self._log_entry_sync(
            message=message,
            level=level,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=error_context or {},
            store_in_db=store_in_db,
            correlation_id=correlation_id,
        )

    # Core internal logging implementation

    async def _log_entry(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        extra_context: Dict[str, Any],
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
        camera_id: Optional[int] = None,
        event_type: str = SSEEvent.LOG,
        sse_priority: SSEPriority = SSEPriority.NORMAL,
    ) -> None:
        """
        Internal async log entry method that routes to all configured handlers.

        Args:
            message: Log message
            level: Log level
            source: Log source
            logger_name: Logger name
            extra_context: Additional context data
            store_in_db: Whether to store in database
            broadcast_sse: Whether to broadcast via SSE
            correlation_id: Optional correlation ID
            camera_id: Optional camera ID
            event_type: Type of event for SSE
            sse_priority: SSE priority level
        """
        try:
            # Format message with context and emoji
            formatted_message = self.formatter.format_message(
                message, level, source, logger_name, extra_context, emoji
            )

            # Extract additional context
            enriched_context = self.context_extractor.extract_context(
                base_context=extra_context, correlation_id=correlation_id
            )

            # Console output (always immediate)
            if self.enable_console:
                self.console_handler.handle(formatted_message, level, source)

            # File logging (if enabled)
            if self.enable_file_logging:
                self.file_handler.handle(formatted_message, level, enriched_context)

            # Database storage (if requested)
            if store_in_db:
                await self.database_handler.handle_async(
                    message=message,
                    level=level,
                    source=source,
                    logger_name=logger_name,
                    camera_id=camera_id,
                    extra_data=enriched_context,
                )

            # SSE broadcasting (if requested and enabled)
            if broadcast_sse and self.enable_sse_broadcasting:
                await self._broadcast_log_event(
                    event_type=event_type,
                    event_data={
                        "message": formatted_message,
                        "level": level,
                        "source": source,
                        "logger_name": logger_name,
                        "context": enriched_context,
                    },
                    priority=sse_priority,
                )

        except Exception as e:
            # Fallback logging if our logging system fails
            logger.error(f"LoggerService._log_entry failed: {e}")
            logger.error(f"Original message: {message}")

    def _log_entry_sync(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        extra_context: Dict[str, Any],
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        correlation_id: Optional[str] = None,
        camera_id: Optional[int] = None,
    ) -> None:
        """
        Internal sync log entry method for use in sync worker contexts.

        Args:
            message: Log message
            level: Log level
            source: Log source
            logger_name: Logger name
            extra_context: Additional context data
            store_in_db: Whether to store in database
            correlation_id: Optional correlation ID
            camera_id: Optional camera ID
        """
        try:
            # Format message with context and emoji
            formatted_message = self.formatter.format_message(
                message, level, source, logger_name, extra_context, emoji
            )

            # Extract additional context
            enriched_context = self.context_extractor.extract_context(
                base_context=extra_context, correlation_id=correlation_id
            )

            # Console output (always immediate)
            if self.enable_console:
                self.console_handler.handle(formatted_message, level, source)

            # File logging (if enabled)
            if self.enable_file_logging:
                self.file_handler.handle(formatted_message, level, enriched_context)

            # Database storage (if requested)
            if store_in_db:
                self.database_handler.handle_sync(
                    message=message,
                    level=level,
                    source=source,
                    logger_name=logger_name,
                    camera_id=camera_id,
                    extra_data=enriched_context,
                )

        except Exception as e:
            # Fallback logging if our logging system fails
            logger.error(f"LoggerService._log_entry_sync failed: {e}")
            logger.error(f"Original message: {message}")

    # Cleanup and maintenance methods

    async def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """
        Clean up old log entries from the database.

        Args:
            days_to_keep: Number of days of logs to keep

        Returns:
            Number of logs deleted
        """
        result = await self.cleanup_service.cleanup_old_logs(days_to_keep)
        return result.get("logs_deleted", 0) if isinstance(result, dict) else 0

    def cleanup_old_logs_sync(self, days_to_keep: int = 30) -> int:
        """
        Clean up old log entries from the database (sync version).

        Args:
            days_to_keep: Number of days of logs to keep

        Returns:
            Number of logs deleted
        """
        result = self.cleanup_service.cleanup_old_logs_sync(days_to_keep)
        return result.get("logs_deleted", 0) if isinstance(result, dict) else 0

    async def get_log_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get logging statistics for monitoring and analysis.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dictionary containing log statistics
        """
        return await self.cleanup_service.get_log_statistics(hours)

    # Health and status methods

    def get_handler_status(self) -> Dict[str, Any]:
        """
        Get status of all logging handlers.

        Returns:
            Dictionary containing handler status information
        """
        return {
            "database_handler": {
                "enabled": True,
                "healthy": self.database_handler.is_healthy(),
            },
            "console_handler": {
                "enabled": self.enable_console,
                "healthy": (
                    self.console_handler.is_healthy() if self.enable_console else None
                ),
            },
            "file_handler": {
                "enabled": self.enable_file_logging,
                "healthy": (
                    self.file_handler.is_healthy() if self.enable_file_logging else None
                ),
            },
            "sse_broadcasting": {
                "enabled": self.enable_sse_broadcasting,
                "healthy": True if self.enable_sse_broadcasting else None,
            },
        }

    def is_healthy(self) -> bool:
        """
        Check if the logger service is in a healthy state.

        Returns:
            True if all enabled handlers are healthy
        """
        status = self.get_handler_status()

        for handler_status in status.values():
            if handler_status["enabled"] and not handler_status["healthy"]:
                return False

        return True

    # Shutdown and flush methods for graceful shutdown

    async def shutdown(self):
        """
        Gracefully shutdown the logger service with final flush.

        This ensures all pending logs are written before shutdown.
        """
        logger.info("Shutting down LoggerService...")

        # Flush batching handler if enabled (only BatchingDatabaseHandler has shutdown)
        if (
            self.enable_batching
            and isinstance(self.database_handler, BatchingDatabaseHandler)
            and hasattr(self.database_handler, "shutdown")
        ):
            await self.database_handler.shutdown()

        logger.info("LoggerService shutdown complete")

    def shutdown_sync(self):
        """
        Gracefully shutdown the logger service with final flush (sync version).

        This ensures all pending logs are written before shutdown.
        """
        logger.info("Shutting down LoggerService (sync)...")

        # Flush batching handler if enabled (only BatchingDatabaseHandler has shutdown_sync)
        if (
            self.enable_batching
            and isinstance(self.database_handler, BatchingDatabaseHandler)
            and hasattr(self.database_handler, "shutdown_sync")
        ):
            self.database_handler.shutdown_sync()

        logger.info("LoggerService shutdown complete (sync)")

    async def flush(self):
        """
        Manually flush any pending logs.

        Useful for ensuring logs are written at specific points.
        """
        # Only BatchingDatabaseHandler has flush methods
        if (
            self.enable_batching
            and isinstance(self.database_handler, BatchingDatabaseHandler)
            and hasattr(self.database_handler, "flush_async")
        ):
            await self.database_handler.flush_async()

    def flush_sync(self):
        """
        Manually flush any pending logs (sync version).

        Useful for ensuring logs are written at specific points.
        """
        # Only BatchingDatabaseHandler has flush methods
        if (
            self.enable_batching
            and isinstance(self.database_handler, BatchingDatabaseHandler)
            and hasattr(self.database_handler, "flush_sync")
        ):
            self.database_handler.flush_sync()

    def get_batching_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get batching statistics if batching is enabled.

        Returns:
            Dictionary with batching stats or None if batching disabled
        """
        # Only BatchingDatabaseHandler has get_stats method
        if (
            self.enable_batching
            and isinstance(self.database_handler, BatchingDatabaseHandler)
            and hasattr(self.database_handler, "get_stats")
        ):
            return self.database_handler.get_stats()
        return None

    async def _broadcast_log_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        priority: SSEPriority = SSEPriority.NORMAL,
        source: str = "logger",
    ) -> None:
        """Broadcast SSE event for log operations (matches other service patterns)."""
        try:

            event_data_with_timestamp = {
                **event_data,
                "timestamp": utc_now().isoformat(),
            }

            await self.sse_ops.create_event(
                event_type=event_type,
                event_data=event_data_with_timestamp,
                priority=priority,
                source=source,
            )

            logger.debug(f"Broadcasted SSE event: {event_type}")

        except Exception as e:
            logger.warning(f"Failed to broadcast SSE event {event_type}: {e}")
