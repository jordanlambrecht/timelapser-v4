"""
Enhanced Database Handler for the Logger Service.

This handler properly stores log entries in the database with correct message
extraction and context handling.
"""

from typing import Dict, Any, Optional


from ....enums import LogLevel, LogSource, LoggerName

from ....database.log_operations import LogOperations, SyncLogOperations
from ....models.log_model import Log
from ..constants import FALLBACK_LOG_LEVEL, FALLBACK_LOG_SOURCE, FALLBACK_LOGGER_NAME


class EnhancedDatabaseHandler:
    """
    Enhanced database handler that properly stores log entries with correct
    message formatting and context extraction.

    This handler bypasses loguru's record processing and directly stores
    log entries to ensure message content and context are preserved correctly.
    """

    def __init__(self, async_log_ops: LogOperations, sync_log_ops: SyncLogOperations):
        """
        Initialize the enhanced database handler.

        Args:
            async_log_ops: Async log operations instance
            sync_log_ops: Sync log operations instance
        """
        self.async_log_ops = async_log_ops
        self.sync_log_ops = sync_log_ops
        self._healthy = True

    def _ensure_enum_types(
        self, level: LogLevel, source: LogSource, logger_name: LoggerName
    ) -> tuple[LogLevel, LogSource, LoggerName]:
        """
        Ensure parameters are proper enum types, converting from strings if necessary.

        Args:
            level: Log level (enum or string)
            source: Log source (enum or string)
            logger_name: Logger name (enum or string)

        Returns:
            Tuple of properly converted enum values
        """
        # Convert level to enum if it's a string
        if isinstance(level, str):
            try:
                level = LogLevel(level.upper())
            except ValueError:
                level = LogLevel(FALLBACK_LOG_LEVEL)  # Default fallback
        elif not isinstance(level, LogLevel):
            level = LogLevel(FALLBACK_LOG_LEVEL)

        # Convert source to enum if it's a string
        if isinstance(source, str):
            try:
                source = LogSource(source.lower())
            except ValueError:
                source = LogSource(FALLBACK_LOG_SOURCE)  # Default fallback
        elif not isinstance(source, LogSource):
            source = LogSource(FALLBACK_LOG_SOURCE)

        # Convert logger_name to enum if it's a string
        if isinstance(logger_name, str):
            try:
                logger_name = LoggerName(logger_name.lower())
            except ValueError:
                logger_name = LoggerName(FALLBACK_LOGGER_NAME)  # Default fallback
        elif not isinstance(logger_name, LoggerName):
            logger_name = LoggerName(FALLBACK_LOGGER_NAME)

        return level, source, logger_name

    async def handle_async(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        camera_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Log]:
        """
        Handle async log storage in the database.

        Args:
            message: The log message (already formatted)
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            source: Log source (api, worker, system, etc.)
            logger_name: Logger name identifier
            camera_id: Optional camera ID for camera-specific logs
            extra_data: Optional additional context data

        Returns:
            Created Log instance or None if failed
        """
        try:
            # Validate required fields
            if not message or not message.strip():
                return None  # Skip empty messages

            # Ensure proper enum types with conversion if necessary
            level, source, logger_name = self._ensure_enum_types(
                level, source, logger_name
            )

            # Create log entry in database
            log_entry = await self.async_log_ops.add_log_entry(
                level=level,
                message=message,
                logger_name=logger_name,
                source=source,
                camera_id=camera_id,
                extra_data=extra_data,
            )

            return log_entry

        except Exception as e:
            # Log handler failures should not break the application
            print(f"EnhancedDatabaseHandler.handle_async failed: {e}")
            print(f"Failed message: {message}")
            self._healthy = False
            return None

    def handle_sync(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        camera_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Log]:
        """
        Handle sync log storage in the database for worker contexts.

        Args:
            message: The log message (already formatted)
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            source: Log source (api, worker, system, etc.)
            logger_name: Logger name identifier
            camera_id: Optional camera ID for camera-specific logs
            extra_data: Optional additional context data

        Returns:
            Created Log instance or None if failed
        """
        try:
            # Validate required fields
            if not message or not message.strip():
                return None  # Skip empty messages

            # Ensure proper enum types with conversion if necessary
            level, source, logger_name = self._ensure_enum_types(
                level, source, logger_name
            )

            # Create log entry in database
            log_entry = self.sync_log_ops.write_log_entry(
                level=level,
                message=message,
                source=source,
                camera_id=camera_id,
                logger_name=logger_name,
                extra_data=extra_data,
            )

            return log_entry

        except Exception as e:
            # Log handler failures should not break the application
            print(f"EnhancedDatabaseHandler.handle_sync failed: {e}")
            print(f"Failed message: {message}")
            self._healthy = False
            return None

    def is_healthy(self) -> bool:
        """
        Check if the database handler is in a healthy state.

        Returns:
            True if handler is healthy, False if recent failures occurred
        """
        return self._healthy

    def reset_health(self) -> None:
        """
        Reset the health status of the handler.

        This can be called after resolving database connectivity issues.
        """
        self._healthy = True


class LegacyLoguruDatabaseHandler:
    """
    Legacy loguru-compatible database handler for backwards compatibility.

    This handler can be used to gradually migrate from the old loguru-based
    system while maintaining compatibility with existing loguru configurations.

    NOTE: This handler has the message extraction issues that the Enhanced
    handler fixes. Use EnhancedDatabaseHandler for new implementations.
    """

    def __init__(self, sync_log_ops: SyncLogOperations):
        """
        Initialize the legacy loguru database handler.

        Args:
            sync_log_ops: Sync log operations instance
        """
        self.sync_log_ops = sync_log_ops
        self._healthy = True

    def __call__(self, record) -> None:
        """
        Handle loguru record and write to database (legacy compatibility).

        This method maintains the old loguru handler interface but with
        improved message extraction.

        Args:
            record: Loguru record object
        """
        try:
            # Extract basic information from loguru record
            level = record.level.name if hasattr(record, "level") else LogLevel.INFO

            # Improved message extraction - try multiple approaches
            message = self._extract_message_from_record(record)

            # Skip empty or meaningless messages
            if not message or not message.strip():
                return

            # Extract logger name
            logger_name = record.name
            # Extract camera_id if present in extra data
            camera_id = None
            extra_data = getattr(record, "extra", {})
            if isinstance(extra_data, dict) and "camera_id" in extra_data:
                camera_id = extra_data["camera_id"]

            # Determine source from logger name or extra data
            source = self._determine_source(logger_name, extra_data)

            # Store in database
            self.sync_log_ops.write_log_entry(
                level=level,
                message=message,
                source=source,
                camera_id=camera_id,
                logger_name=logger_name,
                extra_data=extra_data if extra_data else None,
            )

        except Exception as e:
            # Don't break logging if database is down
            print(f"LegacyLoguraDatabaseHandler failed: {e}")
            print(
                f"Record info: level={getattr(record, 'level', 'unknown')}, name={getattr(record, 'name', 'unknown')}"
            )
            self._healthy = False

    def _extract_message_from_record(self, record) -> str:
        """
        Extract the formatted message from a loguru record.

        This method tries multiple approaches to get the final formatted message.

        Args:
            record: Loguru record object

        Returns:
            Extracted message string
        """
        # Try different message extraction methods

        # Method 1: Try to get the formatted message
        try:
            if hasattr(record, "formatted"):
                # Strip ANSI color codes and extract just the message part
                formatted = record.formatted
                # Basic ANSI color code removal
                import re

                ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
                clean_formatted = ansi_escape.sub("", formatted)
                return clean_formatted.strip()
        except:
            pass

        # Method 2: Try record.message (may be template)
        try:
            if hasattr(record, "message") and record.message:
                return str(record.message)
        except:
            pass

        # Method 3: Try to reconstruct from record data
        try:
            if hasattr(record, "record") and "message" in record.record:
                return str(record.record["message"])
        except:
            pass

        # Method 4: Fallback to string representation
        try:
            return str(record)
        except:
            pass

        # Last resort
        return "Message extraction failed"

    def _determine_source(self, logger_name: str, extra_data: Dict[str, Any]) -> str:
        """
        Determine the log source from logger name and extra data.

        Args:
            logger_name: Logger name
            extra_data: Extra data from record

        Returns:
            Determined source string
        """
        # Check extra data for explicit source
        if isinstance(extra_data, dict) and "source" in extra_data:
            return extra_data["source"]

        # Determine from logger name
        logger_lower = logger_name.lower()

        if LogSource.WORKER in logger_lower:
            return LogSource.WORKER
        elif LogSource.API in logger_lower or "request" in logger_lower:
            return LogSource.API
        elif LogSource.CAMERA in logger_lower:
            return LogSource.CAMERA
        elif LogSource.SYSTEM in logger_lower:
            return LogSource.SYSTEM
        elif LogSource.SCHEDULER in logger_lower:
            return LogSource.SCHEDULER
        else:
            return LogSource.API  # Default fallback

    def is_healthy(self) -> bool:
        """
        Check if the legacy handler is in a healthy state.

        Returns:
            True if handler is healthy
        """
        return self._healthy
