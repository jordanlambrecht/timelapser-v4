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

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

# Database operations will be injected to avoid circular imports
from ...database.core import AsyncDatabase, SyncDatabase
from ...enums import LogEmoji, LoggerName, LogLevel, LogSource, SSEEvent, SSEPriority

# from ...database.log_operations import LogOperations, SyncLogOperations
# from ...database.sse_events_operations import (
#     SSEEventsOperations,
#     SyncSSEEventsOperations,
# )
from ...models.log_model import Log
from ...models.log_summary_model import LogSourceModel, LogSummaryModel

# Timezone utilities available if needed
from ...utils.time_utils import utc_now
from .handlers.batching_database_handler import BatchingDatabaseHandler
from .handlers.console_handler import ConsoleHandler
from .handlers.file_handler import FileHandler

# SSE operations imported below with other database operations
from .services.cleanup_service import LogCleanupService
from .utils.context_extractor import ContextExtractor
from .utils.formatters import LogMessageFormatter
from .utils.settings_cache import LoggerSettingsCache


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

    def __init__(
        self,
        async_db=None,
        sync_db=None,
        async_log_ops=None,
        sync_log_ops=None,
        sse_ops=None,
        sync_sse_ops=None,
        enable_console: bool = True,
        enable_file_logging: bool = True,
        enable_sse_broadcasting: bool = True,
        enable_batching: bool = True,
    ):
        """
        Initialize the logger service with database connections and handler configuration.

        Args:
            async_db: Async database instance (optional, will be lazily loaded)
            sync_db: Sync database instance (optional, will be lazily loaded)
            async_log_ops: Async log operations (optional, for dependency injection)
            sync_log_ops: Sync log operations (optional, for dependency injection)
            sse_ops: SSE operations (optional, for dependency injection)
            sync_sse_ops: Sync SSE operations (optional, for dependency injection)
            enable_console: Enable console output handler
            enable_file_logging: Enable file logging handler
            enable_sse_broadcasting: Enable SSE broadcasting handler
            enable_batching: Enable batching for high-frequency logging (default: True)
        """
        # Database instances (may be None for lazy loading)
        self.async_db = async_db
        self.sync_db = sync_db

        # Database operations (injected dependencies to avoid circular imports)
        self.async_log_ops = async_log_ops
        self.sync_log_ops = sync_log_ops
        self.sse_ops = sse_ops
        self.sync_sse_ops = sync_sse_ops

        # Utility services
        self.formatter = LogMessageFormatter()
        self.context_extractor = ContextExtractor()
        self.settings_cache = LoggerSettingsCache(async_db, sync_db)

        # Handler configuration
        self.enable_console = enable_console
        self.enable_file_logging = enable_file_logging
        self.enable_sse_broadcasting = enable_sse_broadcasting
        self.enable_batching = enable_batching

        # Initialize handlers
        self._initialize_handlers()

        # Cleanup service (will be initialized lazily if operations are not provided)
        self.cleanup_service = None
        if self.async_log_ops and self.sync_log_ops:
            self.cleanup_service = LogCleanupService(
                self.async_log_ops, self.sync_log_ops, self.settings_cache
            )

    def _initialize_handlers(self) -> None:
        """Initialize all logging handlers based on configuration."""
        # Database handler (will be initialized lazily when operations are available)
        self.database_handler = None

        # Console handler
        if self.enable_console:
            self.console_handler = ConsoleHandler()

        # File handler
        if self.enable_file_logging:
            self.file_handler = FileHandler(settings_cache=self.settings_cache)

        # SSE operations for broadcasting (direct pattern like other services)

    def _ensure_database_operations(self):
        """
        Lazy initialization of database operations using singletons to avoid circular imports.
        Only imports and initializes when actually needed.
        """
        if self.async_log_ops is None or self.sync_log_ops is None:
            # Import singleton factories to avoid circular imports
            from ...dependencies.specialized import (
                get_sync_log_operations,
                get_sync_sse_events_operations,
            )

            if self.async_db and self.async_log_ops is None:
                # Direct instantiation since this is a sync method
                from ...database.log_operations import LogOperations

                self.async_log_ops = LogOperations(self.async_db)
            if self.sync_db and self.sync_log_ops is None:
                self.sync_log_ops = get_sync_log_operations()
            if self.async_db and self.sse_ops is None:
                # Direct instantiation since this is a sync method
                from ...database.sse_events_operations import SSEEventsOperations

                self.sse_ops = SSEEventsOperations(self.async_db)
            if self.sync_db and self.sync_sse_ops is None:
                self.sync_sse_ops = get_sync_sse_events_operations()

            # Initialize cleanup service if both operations are now available
            if (
                self.cleanup_service is None
                and self.async_log_ops
                and self.sync_log_ops
            ):
                from .services.cleanup_service import LogCleanupService

                self.cleanup_service = LogCleanupService(
                    self.async_log_ops, self.sync_log_ops, self.settings_cache
                )

            # Initialize database handler if operations are now available
            if (
                self.database_handler is None
                and self.async_log_ops
                and self.sync_log_ops
            ):
                from .handlers.batching_database_handler import BatchingDatabaseHandler
                from .handlers.database_handler import EnhancedDatabaseHandler

                if self.enable_batching:
                    self.database_handler = BatchingDatabaseHandler(
                        self.async_log_ops, self.sync_log_ops
                    )
                else:
                    self.database_handler = EnhancedDatabaseHandler(
                        self.async_log_ops, self.sync_log_ops
                    )

    # =============================================================================
    # USER SETTINGS INTEGRATION
    # =============================================================================

    async def _should_store_in_database_async(
        self, level: LogLevel, explicit_store: Optional[bool] = None
    ) -> bool:
        """
        Check if a log should be stored in database based on user settings and explicit override.

        Args:
            level: Log level to check
            explicit_store: Explicit store_in_db value (overrides user settings if provided)

        Returns:
            True if log should be stored in database
        """
        # Explicit override always takes precedence
        if explicit_store is not None:
            return explicit_store

        # Check user's db_log_level setting
        try:
            db_log_level = await self.settings_cache.get_setting_async("db_log_level")

            # Convert levels to comparable integers
            level_order = {
                LogLevel.DEBUG: 10,
                LogLevel.INFO: 20,
                LogLevel.WARNING: 30,
                LogLevel.ERROR: 40,
                LogLevel.CRITICAL: 50,
            }

            current_level_value = level_order.get(level, 0)
            min_level_value = level_order.get(db_log_level, 20)  # Default to INFO

            return current_level_value >= min_level_value

        except Exception:
            # Fallback: store INFO and above if we can't check settings
            return level in [
                LogLevel.INFO,
                LogLevel.WARNING,
                LogLevel.ERROR,
                LogLevel.CRITICAL,
            ]

    def _should_store_in_database_sync(
        self, level: LogLevel, explicit_store: Optional[bool] = None
    ) -> bool:
        """
        Check if a log should be stored in database based on user settings (sync version).

        Args:
            level: Log level to check
            explicit_store: Explicit store_in_db value (overrides user settings if provided)

        Returns:
            True if log should be stored in database
        """
        # Explicit override always takes precedence
        if explicit_store is not None:
            return explicit_store

        # Check user's db_log_level setting
        try:
            db_log_level = self.settings_cache.get_setting_sync("db_log_level")

            # Convert levels to comparable integers
            level_order = {
                LogLevel.DEBUG: 10,
                LogLevel.INFO: 20,
                LogLevel.WARNING: 30,
                LogLevel.ERROR: 40,
                LogLevel.CRITICAL: 50,
            }

            current_level_value = level_order.get(level, 0)
            min_level_value = level_order.get(db_log_level, 20)  # Default to INFO

            return current_level_value >= min_level_value

        except Exception:
            # Fallback: store INFO and above if we can't check settings
            return level in [
                LogLevel.INFO,
                LogLevel.WARNING,
                LogLevel.ERROR,
                LogLevel.CRITICAL,
            ]

    # =============================================================================
    # DEBUG STORAGE GATEWAY
    # =============================================================================

    async def _check_debug_storage_setting(self) -> bool:
        """
        Check user setting for debug storage preference using settings cache.

        Returns:
            bool: True if debug logs should be stored in database, False otherwise
        """
        try:
            return await self.settings_cache.get_setting_async("debug_logs_store_in_db")
        except Exception:
            # Fallback to False if we can't check settings
            return False

    def _check_debug_storage_setting_sync(self) -> bool:
        """
        Synchronous version of debug storage setting check using settings cache.

        Returns:
            bool: True if debug logs should be stored in database, False otherwise
        """
        try:
            return self.settings_cache.get_setting_sync("debug_logs_store_in_db")
        except Exception:
            # Fallback to False if we can't check settings
            return False

    async def initialize_logging_settings(self) -> None:
        """
        Initialize all logging settings in the database if they don't exist.

        This creates all required logging settings with default values to ensure
        the logger service can function properly with user-configurable behavior.
        """
        try:
            await self.settings_cache.initialize_missing_settings_async()

            # Invalidate cache to force reload of newly initialized settings
            self.settings_cache.invalidate_cache()

        except Exception as e:
            # If we can't initialize settings, log the issue but don't fail
            from loguru import logger as fallback_logger

            fallback_logger.warning(f"Failed to initialize logging settings: {e}")

    def refresh_settings_cache(self) -> None:
        """
        Refresh the settings cache to pick up configuration changes.

        This method can be called after settings have been updated to ensure
        the logger service uses the latest configuration.
        """
        if self.settings_cache:
            self.settings_cache.invalidate_cache()

        # Also refresh file handler settings if it exists
        if hasattr(self, "file_handler") and self.file_handler:
            # Force file handler to refresh its settings on next operation
            self.file_handler._settings_cache_time = 0

    def get_current_settings(self) -> Dict[str, Any]:
        """
        Get current logging settings for debugging and monitoring.

        Returns:
            Dictionary with current logging configuration
        """
        if not self.settings_cache:
            return {"error": "Settings cache not available"}

        try:
            # Try to get all settings via sync method (safe to call from any context)
            settings = {}
            for key in LoggerSettingsCache.DEFAULT_SETTINGS.keys():
                try:
                    settings[key] = self.settings_cache.get_setting_sync(key)
                except Exception as e:
                    settings[key] = f"Error: {e}"

            # Add cache statistics
            settings["_cache_stats"] = self.settings_cache.get_cache_stats()

            return settings

        except Exception as e:
            return {"error": f"Failed to retrieve settings: {e}"}

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
            event_type=SSEEvent.LOG_ERROR,
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

    def log_system_sync(
        self,
        message: str,
        system_context: Optional[Dict[str, Any]] = None,
        level: LogLevel = LogLevel.INFO,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.SYSTEM,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = False,  # System logs often don't need DB storage
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Sync version of system logging for use in sync contexts.

        Args:
            message: System message
            system_context: System context
            level: Log level
            source: Log source
            logger_name: Logger name
            emoji: Optional emoji
            store_in_db: Whether to store in database (default False for system logs)
            correlation_id: Optional correlation ID
        """
        self._log_entry_sync(
            message=message,
            level=level,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=system_context or {},
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
        event_type: SSEEvent = SSEEvent.LOG,
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

            # Database storage (check user settings and explicit override)
            should_store = await self._should_store_in_database_async(
                level, store_in_db
            )
            if should_store:
                self._ensure_database_operations()
                if self.database_handler:
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

            # Database storage (check user settings and explicit override)
            should_store = self._should_store_in_database_sync(level, store_in_db)
            if should_store:
                self._ensure_database_operations()
                if self.database_handler:
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
        if not self.cleanup_service:
            return 0
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
        if not self.cleanup_service:
            return 0
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
        if not self.cleanup_service:
            return {}
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
                "enabled": self.database_handler is not None,
                "healthy": (
                    self.database_handler.is_healthy()
                    if self.database_handler
                    else False
                ),
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
            if not self.sse_ops:
                return

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

    # =============================================================================
    # CONVENIENCE METHODS - Clean API for common logging patterns (async versions)
    # =============================================================================

    async def _error_async_internal(
        self,
        message: str,
        *,
        exception: Optional[Exception] = None,
        error_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.ERROR_HANDLER,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        broadcast_sse: bool = True,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Log an error message with automatic ERROR level (async version)."""
        await self.log_error(
            message=message,
            error_context=error_context,
            level=LogLevel.ERROR,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            store_in_db=store_in_db,
            broadcast_sse=broadcast_sse,
            correlation_id=correlation_id,
            exception=exception,
        )

    async def _warning_async_internal(
        self,
        message: str,
        *,
        extra_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.SYSTEM,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Log a warning message with automatic WARNING level (async version)."""
        await self._log_entry(
            message=message,
            level=LogLevel.WARNING,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=extra_context or {},
            store_in_db=store_in_db,
            broadcast_sse=broadcast_sse,
            correlation_id=correlation_id,
        )

    async def _info_async_internal(
        self,
        message: str,
        *,
        extra_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.SYSTEM,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
        event_type: Optional[SSEEvent] = None,
    ) -> None:
        """Log an info message with automatic INFO level (async version)."""
        await self._log_entry(
            message=message,
            level=LogLevel.INFO,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=extra_context or {},
            store_in_db=store_in_db,
            broadcast_sse=broadcast_sse,
            correlation_id=correlation_id,
            event_type=event_type or SSEEvent.LOG,
        )

    async def _debug_async_internal(
        self,
        message: str,
        *,
        extra_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.SYSTEM,
        emoji: Optional[LogEmoji] = None,
        store_in_db: Optional[
            bool
        ] = None,  # If None, check user settings via debug storage gateway
        broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Log a debug message with automatic DEBUG level (async version).

        Uses debug storage gateway to check user settings if store_in_db is None.
        This allows users to control whether debug logs are stored in the database
        via the 'debug_logs_store_in_db' setting.
        """
        # Apply debug storage gateway if store_in_db not explicitly set
        if store_in_db is None:
            store_in_db = await self._check_debug_storage_setting()

        await self._log_entry(
            message=message,
            level=LogLevel.DEBUG,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=extra_context or {},
            store_in_db=store_in_db,
            broadcast_sse=broadcast_sse,
            correlation_id=correlation_id,
        )

    # =============================================================================
    # SYNC CONVENIENCE METHODS
    # =============================================================================

    def _error_sync_internal(
        self,
        message: str,
        *,
        exception: Optional[Exception] = None,
        error_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.ERROR_HANDLER,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        # broadcast_sse: bool = True,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Log an error message with automatic ERROR level (sync)."""
        self.log_error_sync(
            message=message,
            error_context=error_context,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            store_in_db=store_in_db,
            correlation_id=correlation_id,
            exception=exception,
        )

    def _warning_sync_internal(
        self,
        message: str,
        *,
        extra_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.SYSTEM,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        # broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Log a warning message with automatic WARNING level (sync)."""
        self._log_entry_sync(
            message=message,
            level=LogLevel.WARNING,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=extra_context or {},
            store_in_db=store_in_db,
            correlation_id=correlation_id,
        )

    def _info_sync_internal(
        self,
        message: str,
        *,
        extra_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.SYSTEM,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        # broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
        # event_type: Optional[SSEEvent] = None,
    ) -> None:
        """Log an info message with automatic INFO level (sync)."""
        self._log_entry_sync(
            message=message,
            level=LogLevel.INFO,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=extra_context or {},
            store_in_db=store_in_db,
            correlation_id=correlation_id,
        )

    def _debug_sync_internal(
        self,
        message: str,
        *,
        extra_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.SYSTEM,
        emoji: Optional[LogEmoji] = None,
        store_in_db: Optional[
            bool
        ] = None,  # If None, check user settings via debug storage gateway
        # broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Log a debug message with automatic DEBUG level (sync).

        Uses debug storage gateway to check user settings if store_in_db is None.
        This allows users to control whether debug logs are stored in the database
        via the 'debug_logs_store_in_db' setting.
        """
        # Apply debug storage gateway if store_in_db not explicitly set
        if store_in_db is None:
            store_in_db = self._check_debug_storage_setting_sync()

        self._log_entry_sync(
            message=message,
            level=LogLevel.DEBUG,
            source=source,
            logger_name=logger_name,
            emoji=emoji,
            extra_context=extra_context or {},
            store_in_db=store_in_db,
            correlation_id=correlation_id,
        )

    # =============================================================================
    # INTELLIGENT CONTEXT-AWARE METHODS - No more await/sync confusion!
    # =============================================================================

    def error(
        self,
        message: str,
        *,
        exception: Optional[Exception] = None,
        error_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.ERROR_HANDLER,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        broadcast_sse: bool = True,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Intelligent error logging that auto-detects sync vs async context.

        This method can be called from both sync and async contexts without
        needing to worry about await - it handles context detection automatically.

        Usage:
            logger.error("Something failed", exception=e)  # Works in sync or async!
        """
        import asyncio

        try:
            # Try to get running event loop - if successful, we're in async context
            asyncio.get_running_loop()
            # We're in async context - schedule the async version
            asyncio.create_task(
                self._error_async_internal(
                    message=message,
                    exception=exception,
                    error_context=error_context,
                    source=source,
                    logger_name=logger_name,
                    emoji=emoji,
                    store_in_db=store_in_db,
                    broadcast_sse=broadcast_sse,
                    correlation_id=correlation_id,
                )
            )
        except RuntimeError:
            # No running loop - we're in sync context, use sync version
            self._error_sync_internal(
                message=message,
                exception=exception,
                error_context=error_context,
                source=source,
                logger_name=logger_name,
                emoji=emoji,
                store_in_db=store_in_db,
                # broadcast_sse=broadcast_sse,
                correlation_id=correlation_id,
            )

    def warning(
        self,
        message: str,
        *,
        extra_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.SYSTEM,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Intelligent warning logging that auto-detects sync vs async context.

        Usage:
            logger.warning("Performance issue detected")  # Works in sync or async!
        """

        try:
            asyncio.get_running_loop()
            asyncio.create_task(
                self._warning_async_internal(
                    message=message,
                    extra_context=extra_context,
                    source=source,
                    logger_name=logger_name,
                    emoji=emoji,
                    store_in_db=store_in_db,
                    broadcast_sse=broadcast_sse,
                    correlation_id=correlation_id,
                )
            )
        except RuntimeError:
            self._warning_sync_internal(
                message=message,
                extra_context=extra_context,
                source=source,
                logger_name=logger_name,
                emoji=emoji,
                store_in_db=store_in_db,
                correlation_id=correlation_id,
            )

    def info(
        self,
        message: str,
        *,
        extra_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.SYSTEM,
        emoji: Optional[LogEmoji] = None,
        store_in_db: bool = True,
        broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
        event_type: Optional[SSEEvent] = None,
    ) -> None:
        """
        Intelligent info logging that auto-detects sync vs async context.

        Usage:
            logger.info("Task completed successfully")  # Works in sync or async!
        """

        try:
            asyncio.get_running_loop()
            asyncio.create_task(
                self._info_async_internal(
                    message=message,
                    extra_context=extra_context,
                    source=source,
                    logger_name=logger_name,
                    emoji=emoji,
                    store_in_db=store_in_db,
                    broadcast_sse=broadcast_sse,
                    correlation_id=correlation_id,
                    event_type=event_type,
                )
            )
        except RuntimeError:
            self._info_sync_internal(
                message=message,
                extra_context=extra_context,
                source=source,
                logger_name=logger_name,
                emoji=emoji,
                store_in_db=store_in_db,
                correlation_id=correlation_id,
            )

    def debug(
        self,
        message: str,
        *,
        extra_context: Optional[Dict[str, Any]] = None,
        source: LogSource = LogSource.SYSTEM,
        logger_name: LoggerName = LoggerName.SYSTEM,
        emoji: Optional[LogEmoji] = None,
        store_in_db: Optional[bool] = None,
        broadcast_sse: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Intelligent debug logging that auto-detects sync vs async context.

        Uses debug storage gateway to check user settings if store_in_db is None.

        Usage:
            logger.debug("Processing step completed")  # Works in sync or async!
        """

        try:
            asyncio.get_running_loop()
            asyncio.create_task(
                self._debug_async_internal(
                    message=message,
                    extra_context=extra_context,
                    source=source,
                    logger_name=logger_name,
                    emoji=emoji,
                    store_in_db=store_in_db,
                    broadcast_sse=broadcast_sse,
                    correlation_id=correlation_id,
                )
            )
        except RuntimeError:
            self._debug_sync_internal(
                message=message,
                extra_context=extra_context,
                source=source,
                logger_name=logger_name,
                emoji=emoji,
                store_in_db=store_in_db,
                # broadcast_sse=broadcast_sse,
                correlation_id=correlation_id,
            )

    # =============================================================================
    # HTTP ENDPOINT METHODS FOR LOG ROUTERS
    # =============================================================================

    async def get_log_summary(self, hours: int = 24) -> LogSummaryModel:
        """
        Get comprehensive log statistics and summary.

        Args:
            hours: Number of hours to analyze

        Returns:
            LogSummaryModel with statistics
        """
        from ...models.log_summary_model import LogSummaryModel

        if not self.async_db:
            raise ValueError("Async database required for log summary")

        # Get basic counts and statistics
        # This is a placeholder - you may need to implement the actual
        # statistics gathering based on what LogSummaryModel expects
        return LogSummaryModel(
            total_logs=0,
            critical_count=0,
            error_count=0,
            warning_count=0,
            info_count=0,
            debug_count=0,
            unique_sources=0,
            unique_cameras=0,
            first_log_at=None,
            last_log_at=None,
        )

    async def get_logs(
        self,
        camera_id: Optional[int] = None,
        level: Optional[str] = None,
        source: Optional[str] = None,
        search_query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get logs with filtering and pagination.

        Args:
            camera_id: Filter by camera ID
            level: Filter by log level
            source: Filter by source
            search_query: Search in messages
            start_date: Start date filter
            end_date: End date filter
            page: Page number
            page_size: Items per page

        Returns:
            Dictionary with logs and pagination info
        """
        from ...database.log_operations import LogOperations

        if not self.async_db:
            raise ValueError("Async database required for log retrieval")

        # Use the singleton LogOperations instance
        await self._ensure_operations()
        log_ops = self.async_log_ops

        # Use the existing get_logs method from log_operations
        result = await log_ops.get_logs(
            camera_id=camera_id,
            level=level,
            source=source,
            search_query=search_query,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )

        # Extract logs from result and convert to dict format
        logs = result.get("logs", [])
        pagination = result.get("pagination", {})

        return {
            "logs": [log.model_dump() for log in logs],
            "total_count": pagination.get("total_count", 0),
            "total_pages": pagination.get("total_pages", 0),
            "page": pagination.get("current_page", page),
            "page_size": pagination.get("page_size", page_size),
        }

    async def delete_old_logs(self, days_to_keep: int) -> int:
        """
        Delete old logs.

        Args:
            days_to_keep: Number of days to keep

        Returns:
            Number of deleted logs
        """

        if not self.async_db:
            raise ValueError("Async database required for log deletion")

        # Use the singleton LogOperations instance
        await self._ensure_operations()
        return await self.async_log_ops.delete_old_logs(days_to_keep)

    async def get_logs_for_camera(self, camera_id: int, limit: int = 50) -> List[Log]:
        """
        Get recent logs for a specific camera.

        Args:
            camera_id: Camera ID
            limit: Number of logs to return

        Returns:
            List of Log models
        """

        if not self.async_db:
            raise ValueError("Async database required for camera logs")

        # Use the singleton LogOperations instance
        await self._ensure_operations()
        result = await self.async_log_ops.get_logs(limit=limit, camera_id=camera_id)
        return result.get("logs", [])

    async def get_log_sources(self) -> List[LogSourceModel]:
        """
        Get available log sources and their statistics.

        Returns:
            List of LogSourceModel
        """

        # Return available log sources
        # This is a simplified implementation - you may want to query actual sources from database
        sources = []
        for source in LogSource:
            sources.append(
                LogSourceModel(
                    source=source.value,
                    log_count=0,  # Placeholder - should query actual count
                    last_log_at=None,
                    error_count=0,
                    warning_count=0,
                )
            )

        return sources


# =============================================================================
# GLOBAL LOGGER INSTANCE AND FACTORY FUNCTIONS
# =============================================================================

# Global logger instance - will be initialized by application startup
_global_logger_instance: Optional[LoggerService] = None


async def initialize_global_logger(
    async_db: AsyncDatabase,
    sync_db: SyncDatabase,
    enable_console: bool = True,
    enable_file_logging: bool = True,
    enable_sse_broadcasting: bool = True,
    enable_batching: bool = True,
    auto_initialize_settings: bool = True,
) -> LoggerService:
    """
    Initialize the global logger instance with user settings support.

    This should be called once during application startup.

    Args:
        async_db: Async database instance
        sync_db: Sync database instance
        enable_console: Enable console output handler
        enable_file_logging: Enable file logging handler
        enable_sse_broadcasting: Enable SSE broadcasting handler
        enable_batching: Enable batching for high-frequency logging
        auto_initialize_settings: Automatically create missing logging settings

    Returns:
        Initialized LoggerService instance
    """
    global _global_logger_instance

    _global_logger_instance = LoggerService(
        async_db=async_db,
        sync_db=sync_db,
        enable_console=enable_console,
        enable_file_logging=enable_file_logging,
        enable_sse_broadcasting=enable_sse_broadcasting,
        enable_batching=enable_batching,
    )

    # Initialize logging settings in database if requested
    if auto_initialize_settings:
        try:
            await _global_logger_instance.initialize_logging_settings()
        except Exception as e:
            # Don't fail startup if settings initialization fails
            print(f"Warning: Failed to initialize logging settings: {e}")

    return _global_logger_instance


def log() -> LoggerService:
    """
    Get the global logger instance.

    Returns:
        Global LoggerService instance

    Raises:
        RuntimeError: If global logger not initialized
    """
    if _global_logger_instance is None:
        raise RuntimeError(
            "Global logger not initialized. Call initialize_global_logger() first."
        )

    return _global_logger_instance


def get_service_logger(
    logger_name: LoggerName,
    source: LogSource = LogSource.SYSTEM,
    default_emoji: Optional[LogEmoji] = None,
):
    """
    Factory function to create a pre-configured logger for a specific service.

    Returns a logger with simplified methods that automatically include
    the correct source and logger_name parameters while supporting all
    the rich features of the logging system.

    Emoji priority system (highest to lowest):
    1. Direct: Emoji passed directly to log method call
    2. Instance-set: Default emoji set when creating the service logger
    3. Fallback: Default emoji based on log level (ERROR, WARNING, INFO, DEBUG)

    Args:
        logger_name: The logger name enum to use for all calls
        source: The log source enum to use for all calls (defaults to SYSTEM)
        default_emoji: Instance-level default emoji that overrides level-based fallbacks

    Returns:
        ServiceLogger instance with error, warning, info, debug methods

    Example:
        from ...services.logger import get_service_logger, LogEmoji
        from ...enums import LoggerName

        # Basic usage - uses fallback emojis (ERROR, WARNING, INFO, DEBUG)
        logger = get_service_logger(LoggerName.VIDEO_PIPELINE)
        logger.error("Something went wrong")  # Uses LogEmoji.ERROR (fallback)

        # Instance-level emoji - overrides fallbacks for all levels
        camera_logger = get_service_logger(LoggerName.CAMERA, default_emoji=LogEmoji.CAMERA)
        camera_logger.error("Camera error")  # Uses LogEmoji.CAMERA (instance-set)
        camera_logger.info("Camera ready")   # Uses LogEmoji.CAMERA (instance-set)

        # Direct emoji - highest priority, overrides both instance and fallback
        camera_logger.error("Critical failure", emoji=LogEmoji.FIRE)  # Uses LogEmoji.FIRE (direct)
    """

    def _resolve_emoji(
        method_emoji: Optional[LogEmoji], fallback_emoji: LogEmoji
    ) -> LogEmoji:
        """
        Resolve emoji using three-tier priority system:
        1. Direct (method_emoji) - highest priority
        2. Instance-set (default_emoji) - medium priority
        3. Fallback (fallback_emoji) - lowest priority
        """
        if method_emoji is not None:
            return method_emoji  # Direct priority
        if default_emoji is not None:
            return default_emoji  # Instance-set priority
        return fallback_emoji  # Fallback priority

    class ServiceLogger:
        @staticmethod
        def error(
            message: str,
            exception: Optional[Exception] = None,
            error_context: Optional[Dict[str, Any]] = None,
            emoji: Optional[LogEmoji] = None,
            store_in_db: bool = True,
            broadcast_sse: bool = True,
            correlation_id: Optional[str] = None,
            **kwargs,
        ):
            """Log an error with emoji priority system."""
            resolved_emoji = _resolve_emoji(emoji, LogEmoji.ERROR)
            return log().error(
                message=message,
                exception=exception,
                error_context=error_context,
                source=source,
                logger_name=logger_name,
                emoji=resolved_emoji,
                store_in_db=store_in_db,
                broadcast_sse=broadcast_sse,
                correlation_id=correlation_id,
            )

        @staticmethod
        def warning(
            message: str,
            extra_context: Optional[Dict[str, Any]] = None,
            emoji: Optional[LogEmoji] = None,
            store_in_db: bool = True,
            broadcast_sse: bool = False,
            correlation_id: Optional[str] = None,
            **kwargs,
        ):
            """Log a warning with emoji priority system."""
            resolved_emoji = _resolve_emoji(emoji, LogEmoji.WARNING)
            return log().warning(
                message=message,
                extra_context=extra_context,
                source=source,
                logger_name=logger_name,
                emoji=resolved_emoji,
                store_in_db=store_in_db,
                broadcast_sse=broadcast_sse,
                correlation_id=correlation_id,
            )

        @staticmethod
        def info(
            message: str,
            extra_context: Optional[Dict[str, Any]] = None,
            emoji: Optional[LogEmoji] = None,
            store_in_db: bool = True,
            broadcast_sse: bool = False,
            correlation_id: Optional[str] = None,
            event_type: Optional[SSEEvent] = None,
            **kwargs,
        ):
            """Log an info message with emoji priority system."""
            resolved_emoji = _resolve_emoji(emoji, LogEmoji.INFO)
            return log().info(
                message=message,
                extra_context=extra_context,
                source=source,
                logger_name=logger_name,
                emoji=resolved_emoji,
                store_in_db=store_in_db,
                broadcast_sse=broadcast_sse,
                correlation_id=correlation_id,
                event_type=event_type,
            )

        @staticmethod
        def debug(
            message: str,
            extra_context: Optional[Dict[str, Any]] = None,
            emoji: Optional[LogEmoji] = None,
            store_in_db: Optional[
                bool
            ] = None,  # If None, debug storage gateway will check user settings
            broadcast_sse: bool = False,
            correlation_id: Optional[str] = None,
            **kwargs,
        ):
            """
            Log a debug message with all supported parameters.

            Uses debug storage gateway to check user settings if store_in_db is None.
            This allows users to control whether debug logs are stored in the database
            via the 'debug_logs_store_in_db' setting.
            """
            resolved_emoji = _resolve_emoji(emoji, LogEmoji.DEBUG)
            return log().debug(
                message=message,
                extra_context=extra_context,
                source=source,
                logger_name=logger_name,
                emoji=resolved_emoji,
                store_in_db=store_in_db,
                broadcast_sse=broadcast_sse,
                correlation_id=correlation_id,
            )

    return ServiceLogger()
