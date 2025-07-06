"""Database logging handler for loguru integration."""

from loguru import logger

from ..database.core import SyncDatabase
from ..database.log_operations import SyncLogOperations
from ..models.log_model import LogCreate


class DatabaseLogHandler:
    """Custom loguru handler that writes logs to database."""

    def __init__(self, sync_db: SyncDatabase):
        self.sync_db = sync_db
        self.log_ops = SyncLogOperations(sync_db)  # Use sync operations
        self._cached_log_level = None
        self._last_settings_check = 0

    def _get_user_log_level(self) -> str:
        """
        Get user-configured log level from database settings.

        The enable_debug_logging setting overrides the log_level setting when enabled.
        This allows users to temporarily enable debug logging without changing their
        normal log level configuration.

        Returns:
            str: The effective log level ("DEBUG" if debug logging enabled, otherwise the configured log_level)
        """
        import time

        # Cache settings check for 30 seconds to avoid excessive DB queries
        current_time = time.time()
        if (current_time - self._last_settings_check) < 30 and self._cached_log_level:
            return self._cached_log_level

        try:
            with self.sync_db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Check if debug logging is enabled (overrides log_level)
                    cur.execute(
                        "SELECT value FROM settings WHERE key = 'enable_debug_logging'"
                    )
                    debug_result = cur.fetchone()
                    if debug_result and debug_result[0].lower() == "true":
                        self._cached_log_level = "DEBUG"
                        self._last_settings_check = current_time
                        return self._cached_log_level

                    # Otherwise use the configured log_level
                    cur.execute("SELECT value FROM settings WHERE key = 'log_level'")
                    result = cur.fetchone()
                    if result:
                        self._cached_log_level = result[0].upper()
                    else:
                        self._cached_log_level = "INFO"  # Default

                    self._last_settings_check = current_time
                    return self._cached_log_level
        except Exception:
            # Fall back to INFO if can't read settings
            return "INFO"

    def _should_log_to_database(self, record_level: str) -> bool:
        """Check if log should be written to database based on user settings."""
        user_level = self._get_user_log_level()

        # Level hierarchy: DEBUG < INFO < WARNING < ERROR < CRITICAL
        level_values = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50,
        }

        record_level_value = level_values.get(record_level, 20)
        user_level_value = level_values.get(user_level, 20)

        return record_level_value >= user_level_value

    def __call__(self, record) -> None:
        """Handle log record and write to database."""
        try:
            # Loguru passes a record object, not a dictionary
            level = record.level.name if hasattr(record, "level") else "INFO"
            message = str(record.message) if hasattr(record, "message") else ""
            logger_name = getattr(record, "name", "unknown")

            # Check if this log level should be written to database
            if not self._should_log_to_database(level):
                return

            # Extract camera_id if present in extra data
            camera_id = None
            extra_data = getattr(record, "extra", {})
            if isinstance(extra_data, dict) and "camera_id" in extra_data:
                camera_id = extra_data["camera_id"]

            # Determine source
            source = "worker" if "worker" in logger_name.lower() else "api"

            # Create LogCreate model for proper validation
            log_data = LogCreate(
                level=level,
                message=message,
                camera_id=camera_id,
                logger_name=logger_name,
                source=source,
                extra_data=extra_data if extra_data else None,
            )

            # Use the basic table schema (level, message, camera_id, timestamp)
            self.log_ops.write_log_entry(
                level=log_data.level,
                message=log_data.message,
                source=log_data.source if log_data.source is not None else "api",
                camera_id=log_data.camera_id,
            )

        except Exception as e:
            # Don't break logging if database is down
            print(f"Failed to write log to database: {e}")


def setup_database_logging(sync_db: SyncDatabase) -> None:
    """Setup database logging handler."""
    try:
        db_handler = DatabaseLogHandler(sync_db)
        logger.add(
            db_handler,
            level="DEBUG",  # Let the handler decide what to log based on user settings
            format="{time} | {level} | {name}:{function}:{line} - {message}",
        )
        logger.info("Database logging handler setup complete")
    except Exception as e:
        logger.error(f"Failed to setup database logging: {e}")
