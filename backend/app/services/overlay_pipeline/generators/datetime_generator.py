# backend/app/services/overlay_pipeline/generators/datetime_generator.py
"""
DateTime Overlay Generator - Handles date, time, and datetime overlay content generation.

Supports various date/time formats with timezone-aware rendering.
"""

from datetime import datetime
from typing import Union

from PIL import Image as PILImage

from ....enums import LoggerName, LogSource
from ....models.overlay_model import OverlayItem
from ....services.logger import get_service_logger
from ....utils.time_utils import convert_to_db_timezone_sync
from .base_generator import BaseOverlayGenerator, OverlayGenerationContext

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)


class DateTimeGenerator(BaseOverlayGenerator):
    """
    Generator for date and time overlay content.

    Handles unified date/time overlays with customizable format strings.
    The frontend provides a drag-and-drop format builder that allows users
    to create any combination of date/time components (YYYY, MM, DD, HH, mm, etc.).

    Supported types:
    - date_time: Customizable date and time overlay with format builder

    Format Support:
    - Uses moment.js style format tokens (YYYY, MM, DD, HH, mm, ss, etc.)
    - Converts to Python strftime format for rendering
    - Supports custom separators and text

    Examples:
    - "YYYY-MM-DD HH:mm:ss" → "2025-08-06 14:30:15"
    - "MMM DD, YYYY h:mm A" → "Aug 06, 2025 2:30 PM"
    - "dddd, MMMM DD" → "Tuesday, August 06"

    Supports custom date formatting and timezone-aware rendering.
    """

    @property
    def generator_type(self) -> str:
        """Return the primary generator type."""
        return "date_time"

    @property
    def display_name(self) -> str:
        """Human-readable name for this generator."""
        return "Date & Time"

    @property
    def description(self) -> str:
        """Description of what this generator does."""
        return "Displays timestamps with customizable date and time formats"

    @property
    def supported_types(self) -> list[str]:
        """Return list of overlay types this generator supports."""
        return ["date_time"]

    @property
    def is_static(self) -> bool:
        """Date/time content is dynamic - changes with each frame."""
        return False

    def generate_content(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
    ) -> Union[str, PILImage.Image]:
        """
        Generate date/time text content based on overlay type and format.

        Args:
            overlay_item: Date/time overlay configuration
            context: Generation context with timestamp information

        Returns:
            Formatted date/time string

        Raises:
            ValueError: If overlay type is not supported or format is invalid
        """
        logger.debug(f"Starting {overlay_item.type} overlay generation")

        try:
            self.validate_overlay_item(overlay_item)
            logger.debug(
                f"Overlay item validation passed for type: {overlay_item.type}"
            )

            # Convert timestamp to database timezone using existing utility
            timestamp = context.image_timestamp
            logger.debug("Converting timestamp to database timezone")

            if context.settings_service:
                timestamp = convert_to_db_timezone_sync(
                    timestamp, context.settings_service
                )
                logger.debug(f"Timestamp converted to database timezone: {timestamp}")
            else:
                logger.warning(
                    f"No settings service provided, using timestamp as-is: {timestamp}"
                )

            # Get date format from overlay item
            date_format = overlay_item.settings.get(
                "date_format"
            ) or self._get_default_format(overlay_item.type)
            logger.debug(f"Using date format: {date_format}")

            # Generate content using custom format
            logger.debug(f"Generating {overlay_item.type} content")
            if overlay_item.type == "date_time":
                result = self._format_datetime(timestamp, date_format)
            else:
                logger.error(f"Unsupported overlay type: {overlay_item.type}")
                raise ValueError(f"Unsupported overlay type: {overlay_item.type}")

            logger.debug(
                f"Successfully generated {overlay_item.type} overlay content: '{result}'"
            )
            return result

        except ValueError as e:
            logger.error("Validation error in datetime overlay generation", exception=e)
            raise
        except Exception as e:
            logger.error("Failed to generate date/time overlay content", exception=e)
            raise RuntimeError(f"Failed to generate date/time content: {e}")

    def _get_default_format(self, overlay_type: str) -> str:
        """Get default date format for the given overlay type."""
        return "MM/dd/yyyy HH:mm"

    def _format_date(self, timestamp: datetime, date_format: str) -> str:
        """Format date-only content."""
        return self._apply_format(timestamp, date_format)

    def _format_time(self, timestamp: datetime, date_format: str) -> str:
        """Format time-only content."""
        # If no specific format provided for time, use default
        if date_format == "MM/dd/yyyy HH:mm":  # Default from overlay_item
            date_format = "HH:mm"
        return self._apply_format(timestamp, date_format)

    def _format_datetime(self, timestamp: datetime, date_format: str) -> str:
        """Format combined date and time content."""
        return self._apply_format(timestamp, date_format)

    def _apply_format(self, timestamp: datetime, format_string: str) -> str:
        """
        Apply custom date format string to timestamp.

        Converts frontend format tokens to Python strftime format.
        Frontend uses moment.js style tokens, backend uses strftime.
        """
        # Convert frontend moment.js format to Python strftime format
        python_format = self._convert_frontend_format(format_string)

        try:
            return timestamp.strftime(python_format)
        except ValueError:
            # Fallback to default format if custom format fails
            default_format = "%m/%d/%Y %H:%M"
            return timestamp.strftime(default_format)

    def _convert_frontend_format(self, frontend_format: str) -> str:
        """
        Convert frontend date format tokens to Python strftime format.

        Frontend Format (moment.js style) → Python strftime:
        YYYY → %Y (4-digit year)
        YY → %y (2-digit year)
        MM → %m (2-digit month)
        MMM → %b (3-letter month)
        MMMM → %B (full month name)
        DD → %d (2-digit day)
        D → %-d (day without leading zero) or %#d on Windows
        dddd → %A (full day name)
        ddd → %a (3-letter day)
        HH → %H (24-hour, 2-digit)
        hh → %I (12-hour, 2-digit)
        h → %-I (12-hour, no leading zero) or %#I on Windows
        mm → %M (minutes)
        ss → %S (seconds)
        A → %p (AM/PM uppercase)
        a → %p (AM/PM - Python doesn't have lowercase, will be uppercase)
        """
        logger.debug(
            f"Converting frontend format '{frontend_format}' to Python strftime"
        )

        format_map = {
            "YYYY": "%Y",
            "YY": "%y",
            "MMMM": "%B",
            "MMM": "%b",
            "MM": "%m",
            "dddd": "%A",
            "ddd": "%a",
            "DD": "%d",
            "D": "%-d",  # Note: Windows uses %#d
            "HH": "%H",
            "hh": "%I",
            "h": "%-I",  # Note: Windows uses %#I
            "mm": "%M",
            "ss": "%S",
            "A": "%p",
            "a": "%p",  # Python %p is always uppercase
        }

        # Replace tokens in order of length (longest first to avoid partial replacements)
        python_format = frontend_format
        for token in sorted(format_map.keys(), key=len, reverse=True):
            python_format = python_format.replace(token, format_map[token])

        logger.debug(f"Converted to Python format: '{python_format}'")
        return python_format

    def validate_overlay_item(self, overlay_item: OverlayItem) -> None:
        """
        Validate date/time overlay item configuration.

        Args:
            overlay_item: Overlay item to validate

        Raises:
            ValueError: If overlay item is invalid for date/time generation
        """
        super().validate_overlay_item(overlay_item)

        # Validate date format if provided
        date_format = overlay_item.settings.get("date_format")
        if date_format:
            try:
                # Test format with a sample date (naive datetime is intentional for format testing)
                test_date = datetime(
                    2025, 1, 15, 14, 30, 45
                )  # Test data - timezone-irrelevant
                self._apply_format(test_date, date_format)
            except Exception as e:
                logger.error(
                    f"Invalid date format '{date_format}' for overlay item",
                    exception=e,
                )
                raise ValueError(f"Invalid date format '{date_format}': {e}")
