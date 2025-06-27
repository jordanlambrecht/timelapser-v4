# backend/app/utils/time_utils.py
"""
Pure Time Utilities for Timelapser V4

This module provides pure time utilities for the entire application.
Timezone-specific operations are handled by timezone_utils.py.
Business logic has been moved to appropriate service modules.

REFACTORED FROM:
- app/utils/time_helpers.py (merged and removed)

RELATED MODULES:
- app/timezone_utils.py - Database-aware timezone operations
- services/scheduling_service.py - Capture scheduling business logic
- services/time_window_service.py - Time window business rules

Key Features:
- Pure time utilities (no database dependencies)
- Time parsing and formatting
- Display formatting (relative time, ISO, filename-safe)
- Proper error handling and fallbacks
- No business logic - only utilities
"""

from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)


def extract_date_from_filename(
    filename: str, prefix: str = "capture_"
) -> Optional[date]:
    """
    Extract date from capture filename with standardized error handling.

    This centralizes the repeated pattern for parsing dates from filenames.

    Args:
        filename: Filename to parse (e.g., "capture_20240615_143022.jpg")
        prefix: Expected prefix before date (default: "capture_")

    Returns:
        date object if successful, None if parsing fails
    """
    try:
        basename = Path(filename).name
        if basename.startswith(prefix) and len(basename) >= len(prefix) + 8:
            date_str = basename[len(prefix) : len(prefix) + 8]  # Extract YYYYMMDD
            return datetime.strptime(date_str, "%Y%m%d").date()
    except (ValueError, IndexError) as e:
        logger.debug(f"Could not extract date from filename '{filename}': {e}")

    return None


def format_time_relative(seconds: int) -> str:
    """
    Format a time duration in seconds to a human-readable relative string.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable time string (e.g., "2 hours ago", "in 5 minutes")
    """
    if seconds == 0:
        return "now"

    is_future = seconds > 0
    abs_seconds = abs(seconds)

    if abs_seconds < 60:
        unit = "second" if abs_seconds == 1 else "seconds"
        time_str = f"{abs_seconds} {unit}"
    elif abs_seconds < 3600:
        minutes = abs_seconds // 60
        unit = "minute" if minutes == 1 else "minutes"
        time_str = f"{minutes} {unit}"
    elif abs_seconds < 86400:
        hours = abs_seconds // 3600
        unit = "hour" if hours == 1 else "hours"
        time_str = f"{hours} {unit}"
    else:
        days = abs_seconds // 86400
        unit = "day" if days == 1 else "days"
        time_str = f"{days} {unit}"

    return f"in {time_str}" if is_future else f"{time_str} ago"


def parse_duration_string(duration_str: str) -> Optional[int]:
    """
    Parse a duration string into seconds.

    Supports formats like:
    - "30s", "5m", "2h", "1d"
    - "30 seconds", "5 minutes", "2 hours", "1 day"

    Args:
        duration_str: Duration string to parse

    Returns:
        Duration in seconds, or None if invalid
    """
    if not duration_str:
        return None

    duration_str = duration_str.strip().lower()

    # Unit mappings
    units = {
        "s": 1,
        "sec": 1,
        "second": 1,
        "seconds": 1,
        "m": 60,
        "min": 60,
        "minute": 60,
        "minutes": 60,
        "h": 3600,
        "hr": 3600,
        "hour": 3600,
        "hours": 3600,
        "d": 86400,
        "day": 86400,
        "days": 86400,
    }

    # Try to parse number + unit
    import re

    match = re.match(r"^(\d+)\s*([a-z]+)$", duration_str)
    if match:
        number, unit = match.groups()
        if unit in units:
            return int(number) * units[unit]

    return None


def get_time_until_next_interval(current_time: datetime, interval_minutes: int) -> int:
    """
    Calculate seconds until the next interval boundary.

    Args:
        current_time: Current datetime
        interval_minutes: Interval in minutes

    Returns:
        Seconds until next interval
    """
    if interval_minutes <= 0:
        return 0

    # Calculate minutes since start of hour
    minutes_in_hour = current_time.minute
    seconds_in_minute = current_time.second

    # Find next interval boundary
    next_interval = ((minutes_in_hour // interval_minutes) + 1) * interval_minutes

    # If next interval is beyond this hour, it's at the start of next hour
    if next_interval >= 60:
        next_interval = 0
        # Add an hour
        next_time = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(
            hours=1
        )
    else:
        next_time = current_time.replace(minute=next_interval, second=0, microsecond=0)

    # Calculate time difference
    time_diff = next_time - current_time
    return int(time_diff.total_seconds())


def format_datetime_for_filename(dt: datetime) -> str:
    """
    Format datetime for use in filenames (filesystem-safe).

    Args:
        dt: Datetime to format

    Returns:
        Filesystem-safe datetime string
    """
    return dt.strftime("%Y%m%d_%H%M%S")


def parse_time_string(time_str: str) -> Optional[datetime]:
    """
    Parse various time string formats into datetime objects.

    Supports:
    - ISO format: "2023-12-01T10:30:00"
    - Date only: "2023-12-01"
    - Time only: "10:30:00"

    Args:
        time_str: Time string to parse

    Returns:
        Parsed datetime or None if invalid
    """
    if not time_str:
        return None

    time_str = time_str.strip()

    # Try different formats
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%H:%M:%S",
        "%H:%M",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue

    return None


def create_time_delta(
    days: int = 0, seconds: int = 0, minutes: int = 0, hours: int = 0, weeks: int = 0
) -> timedelta:
    """
    Create timedelta with explicit parameter names for clarity.

    This provides a more explicit alternative to direct timedelta() calls.

    Args:
        days: Number of days
        seconds: Number of seconds
        minutes: Number of minutes
        hours: Number of hours
        weeks: Number of weeks

    Returns:
        timedelta object
    """
    return timedelta(
        days=days, seconds=seconds, minutes=minutes, hours=hours, weeks=weeks
    )


def parse_iso_timestamp_safe(timestamp_str: str) -> datetime:
    """
    Safely parse ISO timestamp string with proper timezone handling.

    Handles common variations like "Z" suffix and missing timezone info.
    This centralizes the repeated pattern: datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    Args:
        timestamp_str: ISO timestamp string (may include "Z" or timezone)

    Returns:
        Timezone-aware datetime object

    Raises:
        ValueError: If timestamp cannot be parsed
    """
    try:
        # Handle Z suffix (common in JSON APIs)
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str.replace("Z", "+00:00")

        # Parse the timestamp
        dt = datetime.fromisoformat(timestamp_str)

        # Ensure it's timezone-aware
        if dt.tzinfo is None:
            # Assume UTC if no timezone info
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))

        return dt

    except (ValueError, TypeError) as e:
        logger.error(f"Failed to parse timestamp '{timestamp_str}': {e}")
        raise ValueError(f"Invalid timestamp format: {timestamp_str}")
