"""
Console Handler for the Logger Service.

This handler outputs logs to console with emoji support, color formatting,
and proper level-based styling. It provides immediate visual feedback
for development and production monitoring.
"""

import sys
from datetime import datetime
from typing import Any, Dict, Optional

from ....enums import LogEmoji, LoggerName, LogLevel, LogSource
from ....utils.time_utils import (
    format_datetime_for_console,
    utc_now,
    get_timezone_from_cache_sync,
)
from ..constants import (
    ANSI_BOLD,
    ANSI_COLOR_CYAN,
    ANSI_COLOR_GREEN,
    ANSI_COLOR_MAGENTA,
    ANSI_COLOR_RED,
    ANSI_COLOR_YELLOW,
    ANSI_DIM,
    ANSI_RESET,
    CONSOLE_CONTEXT_INDENTATION,
    CONSOLE_MAX_CONTEXT_ITEMS,
)


class ConsoleHandler:
    """
    Console handler that outputs logs to stdout with emoji support and color formatting.

    Features:
    - Color-coded log levels (using ANSI color codes)
    - Emoji support for visual clarity
    - Proper timestamp formatting
    - Level-based filtering
    - Health status tracking
    """

    # ANSI color codes for different log levels
    COLORS = {
        LogLevel.DEBUG: ANSI_COLOR_CYAN,
        LogLevel.INFO: ANSI_COLOR_GREEN,
        LogLevel.WARNING: ANSI_COLOR_YELLOW,
        LogLevel.ERROR: ANSI_COLOR_RED,
        LogLevel.CRITICAL: ANSI_COLOR_MAGENTA,
    }

    # Reset color code
    RESET = ANSI_RESET

    # Bold text
    BOLD = ANSI_BOLD

    # Dim text
    DIM = ANSI_DIM

    def __init__(
        self,
        min_level: LogLevel = LogLevel.DEBUG,
        use_colors: bool = True,
        include_timestamp: bool = True,
        include_source: bool = True,
        settings_service=None,
    ):
        """
        Initialize the console handler.

        Args:
            min_level: Minimum log level to output (default: DEBUG)
            use_colors: Whether to use ANSI colors (default: True)
            include_timestamp: Whether to include timestamps (default: True)
            include_source: Whether to include source information (default: True)
            settings_service: Settings service for timezone-aware timestamps
        """
        self.min_level = min_level
        self.use_colors = use_colors
        self.include_timestamp = include_timestamp
        self.include_source = include_source
        self.settings_service = settings_service
        self._healthy = True

        # Check if stdout supports colors (for production environments)
        if not sys.stdout.isatty():
            self.use_colors = False

    def handle(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: Optional[LoggerName] = None,
        timestamp: Optional[datetime] = None,
        emoji: Optional[LogEmoji] = None,
    ) -> None:
        """
        Handle console output for a log entry.

        Args:
            message: The formatted log message
            level: Log level
            source: Log source
            logger_name: Optional logger name
            timestamp: Optional timestamp (defaults to now)
        """
        try:
            # Check if we should output this log level
            if not self._should_log_level(level):
                return

            # Use current time if timestamp not provided
            if timestamp is None:
                timestamp = utc_now()

            # Build console output
            output_parts = []

            # Add timestamp if enabled
            if self.include_timestamp:
                # Convert to timezone-aware timestamp for console display
                display_timestamp = self._get_timezone_aware_timestamp(timestamp)
                timestamp_str = format_datetime_for_console(display_timestamp)
                if self.use_colors:
                    output_parts.append(f"{self.DIM}[{timestamp_str}]{self.RESET}")
                else:
                    output_parts.append(f"[{timestamp_str}]")

            # Add log level with color
            level_str = self._format_level(level)
            output_parts.append(level_str)

            # Add source if enabled
            if self.include_source:
                source_str = self._format_source(source, logger_name)
                output_parts.append(source_str)

            # Add the message
            output_parts.append(message)

            # Combine and output
            formatted_output = " ".join(output_parts)
            print(formatted_output, file=sys.stdout)

            # Flush for immediate output
            sys.stdout.flush()

        except Exception as e:
            # Don't break the application if console output fails
            self._healthy = False
            # Fallback to basic print
            try:
                print(f"[CONSOLE_HANDLER_ERROR] {message}", file=sys.stderr)
                print(f"[CONSOLE_HANDLER_ERROR] Handler error: {e}", file=sys.stderr)
            except Exception:
                pass  # If even stderr fails, give up silently

    def _should_log_level(self, level: LogLevel) -> bool:
        """
        Check if the given log level should be output.

        Args:
            level: Log level to check

        Returns:
            True if level should be logged
        """
        level_order = {
            LogLevel.UNKNOWN: 0,
            LogLevel.TRACE: 0,
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4,
        }

        return level_order.get(level, 0) >= level_order.get(self.min_level, 0)

    def _format_level(self, level: LogLevel) -> str:
        """
        Format the log level with appropriate colors and styling.
        Pads the level name to ensure consistent alignment.

        Args:
            level: Log level to format

        Returns:
            Formatted level string with consistent width
        """
        level_name = level.value
        # Center-align to 8 characters to align all levels
        padded_level = f"{level_name:^8}"

        if self.use_colors:
            color = self.COLORS.get(level, "")
            if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                # Make errors bold for visibility
                return f"{color}{self.BOLD}[{padded_level}]{self.RESET}"
            else:
                return f"{color}[{padded_level}]{self.RESET}"
        else:
            return f"[{padded_level}]"

    def _format_source(
        self, source: LogSource, logger_name: Optional[LoggerName] = None
    ) -> str:
        """
        Format the source and logger name information with consistent padding.

        Args:
            source: Log source
            logger_name: Optional logger name

        Returns:
            Formatted source string with consistent width
        """
        if logger_name:
            # Extract subcategory from logger name if it follows the pattern
            logger_str = (
                str(logger_name.value)
                if hasattr(logger_name, "value")
                else str(logger_name)
            )
            subcategory = self._extract_subcategory(logger_str)

            if subcategory:
                # Format: (source) [subcategory] with tight, consistent padding
                padded_source = f"{source.value:^8}"  # Center-align source to 8 chars
                padded_subcategory = (
                    f"{subcategory:^9}"  # Center-align subcategory to 9 chars
                )
                source_str = f"{padded_source} [{padded_subcategory}]"
            else:
                # No subcategory detected, show the full logger name with source
                padded_source = f"{source.value:^8}"  # Center-align source to 8 chars
                padded_logger = (
                    f"{logger_str:^9}"  # Center-align logger name to 9 chars
                )
                source_str = f"{padded_source} [{padded_logger}]"
        else:
            # No logger name, just center the source compactly
            padded_source = f"{source.value:^10}"  # Center-align source to 10 chars
            source_str = padded_source

        if self.use_colors:
            return f"{self.DIM}({source_str}){self.RESET}"
        else:
            return f"({source_str})"

    def _extract_subcategory(self, logger_name: str) -> Optional[str]:
        """
        Extract subcategory from logger names for better formatting.

        Args:
            logger_name: The logger name string

        Returns:
            Extracted subcategory or None
        """
        # Map logger names to readable subcategories
        subcategory_map = {
            "SCHEDULER_WORKER": "Scheduler",
            "WEATHER_SERVICE": "Weather",
            "WEATHER_WORKER": "Weather",
            "CAPTURE_WORKER": "Capture",
            "VIDEO_WORKER": "Video",
            "CLEANUP_WORKER": "Cleanup",
            "OVERLAY_WORKER": "Overlay",
            "THUMBNAIL_WORKER": "Thumbnail",
            "SSE_WORKER": "SSE",
            "HEALTH_WORKER": "Health",
            "VIDEO_PIPELINE": "Video",
            "CAPTURE_PIPELINE": "Capture",
            "THUMBNAIL_PIPELINE": "Thumbnail",
            "OVERLAY_PIPELINE": "Overlay",
            "CORRUPTION_PIPELINE": "Corruption",
        }

        return subcategory_map.get(logger_name)

    def _get_timezone_aware_timestamp(self, timestamp: datetime) -> datetime:
        """
        Convert timestamp to timezone-aware timestamp for display.

        Args:
            timestamp: UTC timestamp to convert

        Returns:
            Timezone-aware timestamp for display
        """
        try:
            if self.settings_service:
                # Get timezone from settings and convert timestamp
                timezone_str = get_timezone_from_cache_sync(self.settings_service)
                from zoneinfo import ZoneInfo

                tz = ZoneInfo(timezone_str)

                # Ensure timestamp has timezone info
                if timestamp.tzinfo is None:
                    from ....utils.time_utils import UTC_TIMEZONE

                    timestamp = timestamp.replace(tzinfo=UTC_TIMEZONE)

                # Convert to configured timezone
                return timestamp.astimezone(tz)
            else:
                # Try to get timezone from global database connections
                try:
                    # Import here to avoid circular imports
                    from ....database import sync_db
                    from ....services.settings_service import SyncSettingsService

                    # Create a temporary settings service to get timezone
                    temp_settings_service = SyncSettingsService(sync_db)
                    timezone_str = (
                        temp_settings_service.get_setting("timezone") or "UTC"
                    )

                    from zoneinfo import ZoneInfo

                    tz = ZoneInfo(timezone_str)

                    # Ensure timestamp has timezone info
                    if timestamp.tzinfo is None:
                        from ....utils.time_utils import UTC_TIMEZONE

                        timestamp = timestamp.replace(tzinfo=UTC_TIMEZONE)

                    # Convert to configured timezone
                    return timestamp.astimezone(tz)
                except Exception:
                    # Fallback to original timestamp if settings access fails
                    return timestamp
        except Exception:
            # Error converting timezone, return original timestamp
            return timestamp

    def set_min_level(self, level: LogLevel) -> None:
        """
        Update the minimum log level for console output.

        Args:
            level: New minimum log level
        """
        self.min_level = level

    def is_healthy(self) -> bool:
        """
        Check if the console handler is in a healthy state.

        Returns:
            True if handler is healthy
        """
        return self._healthy

    def reset_health(self) -> None:
        """
        Reset the health status of the handler.

        This can be called if console output issues are resolved.
        """
        self._healthy = True


class DevConsoleHandler(ConsoleHandler):
    """
    Enhanced console handler specifically for development environments.

    Includes additional debugging features:
    - More detailed source information
    - Context data preview
    - Enhanced emoji and color usage
    """

    def __init__(self, **kwargs):
        """Initialize development console handler with enhanced defaults."""
        super().__init__(
            min_level=LogLevel.DEBUG,  # Show all logs in dev
            use_colors=True,
            include_timestamp=True,
            include_source=True,
            **kwargs,
        )

    def handle(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: Optional[LoggerName] = None,
        timestamp: Optional[datetime] = None,
        emoji: Optional[LogEmoji] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Enhanced handle method that includes context preview for development.

        Args:
            message: The formatted log message
            level: Log level
            source: Log source
            logger_name: Optional logger name
            timestamp: Optional timestamp
            emoji: Optional emoji for log entry
            context: Optional context data to preview
        """
        # Call parent handler first
        super().handle(message, level, source, logger_name, timestamp, emoji)

        # Add context preview for development (if context is significant)
        if context and len(context) > 0 and self._should_show_context(context):
            context_preview = self._format_context_preview(context)
            if context_preview:
                if self.use_colors:
                    print(
                        f"{CONSOLE_CONTEXT_INDENTATION}{self.DIM}{context_preview}{self.RESET}",
                        file=sys.stdout,
                    )
                else:
                    print(
                        f"{CONSOLE_CONTEXT_INDENTATION}{context_preview}",
                        file=sys.stdout,
                    )
                sys.stdout.flush()

    def _should_show_context(self, context: Dict[str, Any]) -> bool:
        """
        Determine if context should be shown for this log entry.

        Args:
            context: Context dictionary

        Returns:
            True if context should be displayed
        """
        # Show context for errors and warnings
        # Skip context for very basic/common entries
        if not context:
            return False

        # Skip if only timestamp or very basic info
        basic_keys = {"timestamp", "level", "source", "logger_name"}
        interesting_keys = set(context.keys()) - basic_keys

        return len(interesting_keys) > 0

    def _format_context_preview(self, context: Dict[str, Any]) -> str:
        """
        Format context data for preview display.

        Args:
            context: Context dictionary

        Returns:
            Formatted context preview string
        """
        try:
            # Show most interesting context items (limit to avoid noise)
            preview_items = []

            # Prioritize certain keys
            priority_keys = [
                "error",
                "exception",
                "camera_id",
                "job_id",
                "image_id",
                "worker_name",
            ]

            for key in priority_keys:
                if key in context:
                    value = context[key]
                    preview_items.append(f"{key}={value}")
                    if (
                        len(preview_items) >= CONSOLE_MAX_CONTEXT_ITEMS
                    ):  # Limit preview length
                        break

            # Add other interesting keys if we have room
            if len(preview_items) < CONSOLE_MAX_CONTEXT_ITEMS:
                for key, value in context.items():
                    if key not in priority_keys and key not in {
                        "timestamp",
                        "level",
                        "source",
                        "logger_name",
                    }:
                        preview_items.append(f"{key}={value}")
                        if len(preview_items) >= CONSOLE_MAX_CONTEXT_ITEMS:
                            break

            return ", ".join(preview_items) if preview_items else ""

        except Exception:
            return "context_preview_error"


class ProductionConsoleHandler(ConsoleHandler):
    """
    Console handler optimized for production environments.

    Features:
    - Higher minimum log level (INFO by default)
    - No colors (safe for log aggregation)
    - Structured output format
    - Minimal performance impact
    """

    def __init__(self, **kwargs):
        """Initialize production console handler with production defaults."""
        super().__init__(
            min_level=LogLevel.INFO,  # Hide debug logs in production
            use_colors=False,  # No colors for log aggregation
            include_timestamp=True,
            include_source=True,
            **kwargs,
        )
