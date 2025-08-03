"""
File Handler for the Logger Service.

This handler writes logs to rotating files with proper formatting,
compression, and retention policies. Designed for production
environments where log persistence is required.
"""

import gzip
import json
import re
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from ....constants import (
    LOG_FILE_BASE_NAME,
    LOG_FILE_DIRECTORY,
    LOG_FILE_MAX_COUNT,
    LOG_FILE_MAX_SIZE,
    LOG_FILE_RETENTION_DAYS,
)
from ....enums import LogLevel, LogSource
from ....utils.time_utils import (
    format_date_string,
    format_filename_timestamp,
    format_time_object_for_display,
    utc_now,
)
from ..utils.settings_cache import LoggerSettingsCache


class FileHandler:
    """
    File handler that writes logs to rotating files with compression and retention.

    Features:
    - Automatic file rotation based on size or time
    - Gzip compression of old log files
    - Configurable retention policies
    - Thread-safe file operations
    - Structured log format (JSON or plain text)
    - Error recovery and fallback handling
    """

    def __init__(
        self,
        settings_cache: Optional[LoggerSettingsCache] = None,
        log_directory: str = LOG_FILE_DIRECTORY,
        base_filename: str = LOG_FILE_BASE_NAME,
        max_file_size: Optional[int] = None,  # Will use user settings if None
        max_files: Optional[int] = None,  # Will use user settings if None
        retention_days: Optional[int] = None,  # Will use user settings if None
        min_level: Optional[LogLevel] = None,  # Will use user settings if None
        use_json_format: bool = True,
        compress_old_files: Optional[bool] = None,  # Will use user settings if None
    ):
        """
        Initialize the file handler with dynamic user settings support.

        Args:
            settings_cache: Settings cache for dynamic configuration
            log_directory: Directory to store log files
            base_filename: Base name for log files
            max_file_size: Maximum size per log file (bytes, None = use user settings)
            max_files: Maximum number of log files to keep (None = use user settings)
            retention_days: Days to retain log files (None = use user settings)
            min_level: Minimum log level to write to files (None = use user settings)
            use_json_format: Whether to use JSON format (vs plain text)
            compress_old_files: Whether to compress rotated files (None = use user settings)
        """
        self.settings_cache = settings_cache
        self.log_directory = Path(log_directory)
        self.base_filename = base_filename
        self.use_json_format = use_json_format

        # Store override values (None means use user settings)
        self._override_max_file_size = max_file_size
        self._override_max_files = max_files
        self._override_retention_days = retention_days
        self._override_min_level = min_level
        self._override_compress_old_files = compress_old_files

        # Cache current settings to avoid frequent database queries
        self._cached_settings = {}
        self._settings_cache_time = 0
        self._settings_cache_ttl = 30.0  # 30 seconds

        # Initialize computed properties
        self._update_settings_from_cache()

        # Dynamic properties (will be updated from user settings)
        self.max_file_size = self._get_setting_value("max_file_size")
        self.max_files = self._get_setting_value("max_files")
        self.retention_days = self._get_setting_value("retention_days")
        self.min_level = self._get_setting_value("min_level")
        self.compress_old_files = self._get_setting_value("compress_old_files")

        # Thread safety
        self._lock = threading.Lock()
        self._healthy = True

        # Current log file
        self._current_file = None
        self._current_file_size = 0

        # Initialize log directory and files
        self._initialize_logging()

    def _update_settings_from_cache(self) -> None:
        """Update settings from cache if needed."""
        if not self.settings_cache:
            return

        current_time = time.time()
        if (current_time - self._settings_cache_time) < self._settings_cache_ttl:
            return  # Cache still valid

        try:
            # Load all file logging settings at once for efficiency
            self._cached_settings = {
                "file_log_max_size": self.settings_cache.get_setting_sync(
                    "file_log_max_size"
                ),
                "file_log_max_files": self.settings_cache.get_setting_sync(
                    "file_log_max_files"
                ),
                "file_log_retention_days": self.settings_cache.get_setting_sync(
                    "file_log_retention_days"
                ),
                "file_log_level": self.settings_cache.get_setting_sync(
                    "file_log_level"
                ),
                "file_log_enable_compression": self.settings_cache.get_setting_sync(
                    "file_log_enable_compression"
                ),
            }
            self._settings_cache_time = current_time

        except Exception:
            # On error, use defaults (handled by _get_setting_value fallbacks)
            pass

    def _get_setting_value(self, setting_type: str) -> Any:
        """
        Get a setting value, using override if provided, otherwise user settings, otherwise defaults.

        Args:
            setting_type: Type of setting (max_file_size, max_files, etc.)

        Returns:
            Setting value
        """
        # Check for override first
        if setting_type == "max_file_size" and self._override_max_file_size is not None:
            return self._override_max_file_size
        elif setting_type == "max_files" and self._override_max_files is not None:
            return self._override_max_files
        elif (
            setting_type == "retention_days"
            and self._override_retention_days is not None
        ):
            return self._override_retention_days
        elif setting_type == "min_level" and self._override_min_level is not None:
            return self._override_min_level
        elif (
            setting_type == "compress_old_files"
            and self._override_compress_old_files is not None
        ):
            return self._override_compress_old_files

        # Update cache if needed
        self._update_settings_from_cache()

        # Get from user settings with fallbacks
        if setting_type == "max_file_size":
            mb_value = self._cached_settings.get("file_log_max_size", 10)
            return mb_value * 1024 * 1024  # Convert MB to bytes
        elif setting_type == "max_files":
            return self._cached_settings.get("file_log_max_files", LOG_FILE_MAX_COUNT)
        elif setting_type == "retention_days":
            return self._cached_settings.get(
                "file_log_retention_days", LOG_FILE_RETENTION_DAYS
            )
        elif setting_type == "min_level":
            return self._cached_settings.get("file_log_level", LogLevel.INFO)
        elif setting_type == "compress_old_files":
            return self._cached_settings.get("file_log_enable_compression", True)

        # Fallback to constants
        return {
            "max_file_size": LOG_FILE_MAX_SIZE,
            "max_files": LOG_FILE_MAX_COUNT,
            "retention_days": LOG_FILE_RETENTION_DAYS,
            "min_level": LogLevel.INFO,
            "compress_old_files": True,
        }.get(setting_type)

    def _initialize_logging(self) -> None:
        """Initialize the logging directory and current log file."""
        try:
            # Create log directory if it doesn't exist
            self.log_directory.mkdir(parents=True, exist_ok=True)

            # Set up current log file
            self._setup_current_log_file()

            # Clean up old files
            self._cleanup_old_files()

        except Exception as e:
            self._healthy = False
            print(f"FileHandler initialization failed: {e}")

    def _setup_current_log_file(self) -> None:
        """Set up the current log file for writing."""
        try:
            # Generate current log file path (YYYYMMDD format for daily rotation)
            timestamp = format_filename_timestamp(utc_now())[:8]  # Extract YYYYMMDD

            if self.use_json_format:
                current_log_path = (
                    self.log_directory / f"{self.base_filename}_{timestamp}.jsonl"
                )
            else:
                current_log_path = (
                    self.log_directory / f"{self.base_filename}_{timestamp}.log"
                )

            # Check if we need to rotate (file exists and is too large)
            if current_log_path.exists():
                current_size = current_log_path.stat().st_size
                if current_size >= self.max_file_size:
                    self._rotate_current_file(current_log_path)
                    # Create new file after rotation
                    self._setup_current_log_file()
                    return
                else:
                    self._current_file_size = current_size
            else:
                self._current_file_size = 0

            # Open current log file for appending
            self._current_log_path = current_log_path

        except Exception as e:
            self._healthy = False
            print(f"FileHandler._setup_current_log_file failed: {e}")

    def handle(
        self,
        message: str,
        level: LogLevel,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        source: Optional[LogSource] = None,
        logger_name: Optional[str] = None,
    ) -> None:
        """
        Handle file logging for a log entry.

        Args:
            message: The formatted log message
            level: Log level
            context: Optional context data
            timestamp: Optional timestamp (defaults to now)
            source: Optional log source
            logger_name: Optional logger name
        """
        try:
            # Check if we should log this level
            if not self._should_log_level(level):
                return

            # Use current time if timestamp not provided
            if timestamp is None:
                timestamp = utc_now()

            # Thread-safe file operations
            with self._lock:
                # Check if we need to rotate files
                self._check_rotation()

                # Format log entry
                log_entry = self._format_log_entry(
                    message, level, context, timestamp, source, logger_name
                )

                # Write to file
                self._write_to_file(log_entry)

        except Exception as e:
            # Don't break the application if file logging fails
            self._healthy = False
            print(f"FileHandler.handle failed: {e}")

    def _should_log_level(self, level: LogLevel) -> bool:
        """
        Check if the given log level should be written to files based on current user settings.

        Args:
            level: Log level to check

        Returns:
            True if level should be logged
        """
        # Refresh settings dynamically
        current_min_level = self._get_setting_value("min_level")

        level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4,
        }

        return level_order.get(level, 0) >= level_order.get(current_min_level, 0)

    def _format_log_entry(
        self,
        message: str,
        level: LogLevel,
        context: Optional[Dict[str, Any]],
        timestamp: datetime,
        source: Optional[LogSource],
        logger_name: Optional[str],
    ) -> str:
        """
        Format a log entry for file output.

        Args:
            message: Log message
            level: Log level
            context: Context data
            timestamp: Timestamp
            source: Log source
            logger_name: Logger name

        Returns:
            Formatted log entry string
        """
        if self.use_json_format:
            return self._format_json_entry(
                message, level, context, timestamp, source, logger_name
            )
        else:
            return self._format_text_entry(
                message, level, context, timestamp, source, logger_name
            )

    def _format_json_entry(
        self,
        message: str,
        level: LogLevel,
        context: Optional[Dict[str, Any]],
        timestamp: datetime,
        source: Optional[LogSource],
        logger_name: Optional[str],
    ) -> str:
        """Format log entry as JSON (JSONL format)."""
        entry: Dict[str, Any] = {
            "timestamp": timestamp.isoformat(),
            "level": level.value,
            "message": message,
        }

        if source:
            entry["source"] = source.value

        if logger_name:
            entry["logger_name"] = logger_name

        if context:
            entry["context"] = context

        return json.dumps(entry, separators=(",", ":")) + "\n"

    def _format_text_entry(
        self,
        message: str,
        level: LogLevel,
        context: Optional[Dict[str, Any]],
        timestamp: datetime,
        source: Optional[LogSource],
        logger_name: Optional[str],
    ) -> str:
        """Format log entry as plain text."""
        timestamp_str = (
            format_date_string(timestamp)
            + " "
            + format_time_object_for_display(timestamp.time())
        )

        # Build log line
        parts = [f"[{timestamp_str}]", f"[{level.value}]"]

        if source:
            if logger_name:
                parts.append(f"({source.value}:{logger_name})")
            else:
                parts.append(f"({source.value})")
        elif logger_name:
            parts.append(f"({logger_name})")

        parts.append(message)

        # Add context if present
        if context:
            context_str = json.dumps(context, separators=(",", ":"))
            parts.append(f"| {context_str}")

        return " ".join(parts) + "\n"

    def _write_to_file(self, log_entry: str) -> None:
        """
        Write log entry to the current log file.

        Args:
            log_entry: Formatted log entry string
        """
        try:
            # Write to current log file
            with open(self._current_log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
                f.flush()  # Ensure immediate write

            # Update current file size
            self._current_file_size += len(log_entry.encode("utf-8"))

        except Exception as e:
            self._healthy = False
            raise e

    def _check_rotation(self) -> None:
        """Check if log file rotation is needed."""
        try:
            # Get current settings dynamically
            current_max_size = self._get_setting_value("max_file_size")

            # Check file size rotation
            if self._current_file_size >= current_max_size:
                self._rotate_current_file(self._current_log_path)
                self._setup_current_log_file()
                return

            # Check date-based rotation (daily rotation)
            current_date = format_filename_timestamp(utc_now())[:8]  # Extract YYYYMMDD
            file_date = self._extract_date_from_filename(self._current_log_path.name)

            if file_date != current_date:
                # Day has changed, rotate to new daily file
                self._setup_current_log_file()

        except Exception as e:
            print(f"FileHandler._check_rotation failed: {e}")

    def _rotate_current_file(self, current_path: Path) -> None:
        """
        Rotate the current log file.

        Args:
            current_path: Path to current log file
        """
        try:
            # Generate rotated filename with timestamp
            timestamp = format_filename_timestamp(utc_now())
            name_parts = current_path.stem.split("_")

            if len(name_parts) >= 2:
                base_name = "_".join(name_parts[:-1])  # Remove date part
            else:
                base_name = current_path.stem

            rotated_name = f"{base_name}_{timestamp}{current_path.suffix}"
            rotated_path = current_path.parent / rotated_name

            # Move current file to rotated name
            shutil.move(str(current_path), str(rotated_path))

            # Compress if enabled (check user settings)
            current_compression_enabled = self._get_setting_value("compress_old_files")
            if current_compression_enabled:
                self._compress_file(rotated_path)

        except Exception as e:
            print(f"FileHandler._rotate_current_file failed: {e}")

    def _compress_file(self, file_path: Path) -> None:
        """
        Compress a log file using gzip.

        Args:
            file_path: Path to file to compress
        """
        try:
            compressed_path = file_path.with_suffix(file_path.suffix + ".gz")

            with open(file_path, "rb") as f_in:
                with gzip.open(compressed_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Remove original file after compression
            file_path.unlink()

        except Exception as e:
            print(f"FileHandler._compress_file failed: {e}")

    def _cleanup_old_files(self) -> None:
        """Clean up old log files based on current user retention policies."""
        try:
            # Get current settings dynamically
            current_max_files = self._get_setting_value("max_files")
            current_retention_days = self._get_setting_value("retention_days")

            # Get all log files in directory
            log_files = []

            for file_path in self.log_directory.iterdir():
                if file_path.is_file() and self.base_filename in file_path.name:
                    log_files.append(file_path)

            # Sort by modification time (oldest first)
            log_files.sort(key=lambda x: x.stat().st_mtime)

            # Remove files beyond max count
            if len(log_files) > current_max_files:
                files_to_remove = log_files[: len(log_files) - current_max_files]
                for file_path in files_to_remove:
                    try:
                        file_path.unlink()
                    except Exception as e:
                        print(f"Failed to remove old log file {file_path}: {e}")

            # Remove files older than retention period
            cutoff_date = utc_now() - timedelta(days=current_retention_days)
            cutoff_timestamp = cutoff_date.timestamp()

            for file_path in log_files:
                try:
                    if file_path.stat().st_mtime < cutoff_timestamp:
                        file_path.unlink()
                except Exception as e:
                    print(f"Failed to remove expired log file {file_path}: {e}")

        except Exception as e:
            print(f"FileHandler._cleanup_old_files failed: {e}")

    def _extract_date_from_filename(self, filename: str) -> str:
        """
        Extract date from log filename.

        Args:
            filename: Log filename

        Returns:
            Date string or empty string if not found
        """
        try:
            # Look for date pattern YYYYMMDD in filename

            date_pattern = r"(\d{8})"
            match = re.search(date_pattern, filename)
            return match.group(1) if match else ""
        except Exception:
            return ""

    def set_min_level(self, level: LogLevel) -> None:
        """
        Update the minimum log level for file output.

        Args:
            level: New minimum log level
        """
        self.min_level = level

    def is_healthy(self) -> bool:
        """
        Check if the file handler is in a healthy state.

        Returns:
            True if handler is healthy
        """
        return self._healthy

    def reset_health(self) -> None:
        """
        Reset the health status of the handler.

        This can be called after resolving file system issues.
        """
        self._healthy = True
        try:
            # Re-initialize logging if needed
            if (
                not hasattr(self, "_current_log_path")
                or not self._current_log_path.exists()
            ):
                self._initialize_logging()
        except Exception as e:
            print(f"FileHandler.reset_health failed: {e}")

    def get_log_file_paths(self) -> list[Path]:
        """
        Get paths to all current log files.

        Returns:
            List of log file paths
        """
        try:
            log_files = []
            for file_path in self.log_directory.iterdir():
                if file_path.is_file() and self.base_filename in file_path.name:
                    log_files.append(file_path)
            return sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)
        except Exception:
            return []

    def get_stats(self) -> Dict[str, Any]:
        """
        Get file handler statistics.

        Returns:
            Dictionary containing handler statistics
        """
        try:
            log_files = self.get_log_file_paths()
            total_size = sum(f.stat().st_size for f in log_files if f.exists())

            return {
                "healthy": self._healthy,
                "log_directory": str(self.log_directory),
                "current_file": str(getattr(self, "_current_log_path", "None")),
                "current_file_size": getattr(self, "_current_file_size", 0),
                "total_files": len(log_files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "max_file_size_mb": round(self.max_file_size / (1024 * 1024), 2),
                "retention_days": self.retention_days,
                "min_level": self.min_level.value,
                "use_json_format": self.use_json_format,
                "compress_old_files": self.compress_old_files,
            }
        except Exception as e:
            return {"healthy": False, "error": str(e)}
