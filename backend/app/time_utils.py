"""
Centralized Time Utilities for Timelapser V4

This module provides centralized time and timezone handling for the entire application,
ensuring consistent time-aware operations across all components.

Key Features:
- Single source of truth for timezone configuration
- Consistent timezone-aware timestamp generation and parsing
- Centralized time formatting and conversion utilities
- Time window calculations and validation
- Proper error handling and fallbacks
- Support for both sync and async database operations

Follows AI-CONTEXT rules:
- Always use database timezone setting, not system/browser local time
- All timestamps must be timezone-aware for consistency
- Centralized error handling with UTC fallback
- No manual datetime manipulation - use utility functions
"""

import logging
import os
from datetime import datetime, time, timedelta, date
from typing import Dict, Optional, TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from .database import SyncDatabase, AsyncDatabase

logger = logging.getLogger(__name__)


def get_timezone_from_settings(settings_dict: Dict[str, str]) -> str:
    """
    Get timezone string from settings dictionary with validation.

    Args:
        settings_dict: Dictionary containing timezone setting

    Returns:
        Valid timezone string (defaults to UTC if invalid)
    """
    timezone_str = settings_dict.get("timezone", "UTC")

    # Validate timezone string
    try:
        ZoneInfo(timezone_str)
        return timezone_str
    except Exception as e:
        logger.warning(f"Invalid timezone '{timezone_str}': {e}. Falling back to UTC.")
        return "UTC"


def create_timezone_aware_datetime(timezone_str: str) -> datetime:
    """
    Create timezone-aware datetime object.

    Args:
        timezone_str: Timezone string (e.g., "America/Chicago")

    Returns:
        Timezone-aware datetime object
    """
    try:
        tz = ZoneInfo(timezone_str)
        return datetime.now(tz)
    except Exception as e:
        logger.warning(
            f"Failed to create timezone-aware datetime for '{timezone_str}': {e}"
        )
        # Fallback to UTC
        return datetime.now(ZoneInfo("UTC"))


def get_timezone_aware_timestamp_from_settings(settings_dict: Dict[str, str]) -> str:
    """
    Generate timezone-aware timestamp using provided timezone setting.

    This is the primary function for generating timestamps throughout the application.

    Args:
        settings_dict: Dictionary containing timezone setting

    Returns:
        ISO format timestamp string with timezone information
    """
    timezone_str = get_timezone_from_settings(settings_dict)
    dt = create_timezone_aware_datetime(timezone_str)
    return dt.isoformat()


def get_timezone_aware_timestamp_sync(sync_db: "SyncDatabase") -> str:
    """
    Generate timezone-aware timestamp using sync database connection.

    Args:
        sync_db: SyncDatabase instance

    Returns:
        ISO format timestamp string with timezone information
    """
    try:
        settings_dict = sync_db.get_settings_dict()
        return get_timezone_aware_timestamp_from_settings(settings_dict)
    except Exception as e:
        logger.warning(f"Failed to get timezone from sync database: {e}")
        # Fallback to UTC
        return datetime.now(ZoneInfo("UTC")).isoformat()


async def get_timezone_aware_timestamp_async(async_db: "AsyncDatabase") -> str:
    """
    Generate timezone-aware timestamp using async database connection.

    Args:
        async_db: AsyncDatabase instance

    Returns:
        ISO format timestamp string with timezone information
    """
    try:
        settings_dict = await async_db.get_settings_dict()
        return get_timezone_aware_timestamp_from_settings(settings_dict)
    except Exception as e:
        logger.warning(f"Failed to get timezone from async database: {e}")
        # Fallback to UTC
        return datetime.now(ZoneInfo("UTC")).isoformat()


def validate_timezone(timezone_str: str) -> bool:
    """
    Validate if a timezone string is valid.

    Args:
        timezone_str: Timezone string to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        ZoneInfo(timezone_str)
        return True
    except Exception:
        return False


def get_supported_timezones() -> list[str]:
    """
    Get list of supported timezone identifiers.

    Returns:
        List of valid timezone strings
    """
    # Import zoneinfo and get available zones
    import zoneinfo

    return sorted(zoneinfo.available_timezones())


# Convenience functions for common use cases
def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(ZoneInfo("UTC"))


def utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return utc_now().isoformat()


# Legacy compatibility - these will be removed after migration
def get_timezone_aware_timestamp(db: "SyncDatabase") -> str:
    """
    Legacy compatibility function.

    DEPRECATED: Use get_timezone_aware_timestamp_sync() instead.
    """
    logger.warning(
        "Using deprecated get_timezone_aware_timestamp(). Use get_timezone_aware_timestamp_sync() instead."
    )
    return get_timezone_aware_timestamp_sync(db)


def get_timezone_aware_date_from_settings(settings_dict: Dict[str, str]) -> str:
    """
    Generate timezone-aware date string (YYYY-MM-DD) using provided timezone setting.

    This function centralizes the common pattern of getting today's date
    in the configured timezone for comparisons and event filtering.

    Args:
        settings_dict: Dictionary containing timezone setting

    Returns:
        Date string in YYYY-MM-DD format in the configured timezone
    """
    timezone_str = get_timezone_from_settings(settings_dict)
    dt = create_timezone_aware_datetime(timezone_str)
    return dt.date().isoformat()


def get_timezone_aware_date_sync(sync_db: "SyncDatabase") -> str:
    """
    Generate timezone-aware date string using sync database connection.

    Args:
        sync_db: SyncDatabase instance

    Returns:
        Date string in YYYY-MM-DD format in the configured timezone
    """
    try:
        settings_dict = sync_db.get_settings_dict()
        return get_timezone_aware_date_from_settings(settings_dict)
    except Exception as e:
        logger.warning(f"Failed to get timezone-aware date from sync database: {e}")
        # Fallback to UTC
        return datetime.now(ZoneInfo("UTC")).date().isoformat()


async def get_timezone_aware_date_async(async_db: "AsyncDatabase") -> str:
    """
    Generate timezone-aware date string using async database connection.

    Args:
        async_db: AsyncDatabase instance

    Returns:
        Date string in YYYY-MM-DD format in the configured timezone
    """
    try:
        settings_dict = await async_db.get_settings_dict()
        return get_timezone_aware_date_from_settings(settings_dict)
    except Exception as e:
        logger.warning(f"Failed to get timezone-aware date from async database: {e}")
        # Fallback to UTC
        return datetime.now(ZoneInfo("UTC")).date().isoformat()


def get_timezone_aware_time_from_settings(settings_dict: Dict[str, str]) -> time:
    """
    Get current time in the configured timezone.

    Args:
        settings_dict: Dictionary containing timezone setting

    Returns:
        Current time in the configured timezone
    """
    timezone_str = get_timezone_from_settings(settings_dict)
    dt = create_timezone_aware_datetime(timezone_str)
    return dt.time()


def get_timezone_aware_time_sync(sync_db: "SyncDatabase") -> time:
    """
    Get current time in the configured timezone using sync database connection.

    Args:
        sync_db: SyncDatabase instance

    Returns:
        Current time in the configured timezone
    """
    try:
        settings_dict = sync_db.get_settings_dict()
        return get_timezone_aware_time_from_settings(settings_dict)
    except Exception as e:
        logger.warning(f"Failed to get timezone-aware time from sync database: {e}")
        # Fallback to UTC
        return datetime.now(ZoneInfo("UTC")).time()


async def get_timezone_aware_time_async(async_db: "AsyncDatabase") -> time:
    """
    Get current time in the configured timezone using async database connection.

    Args:
        async_db: AsyncDatabase instance

    Returns:
        Current time in the configured timezone
    """
    try:
        settings_dict = await async_db.get_settings_dict()
        return get_timezone_aware_time_from_settings(settings_dict)
    except Exception as e:
        logger.warning(f"Failed to get timezone-aware time from async database: {e}")
        # Fallback to UTC
        return datetime.now(ZoneInfo("UTC")).time()


def get_timezone_aware_timestamp_string_from_settings(
    settings_dict: Dict[str, str], format_str: str = "%Y%m%d_%H%M%S"
) -> str:
    """
    Generate timezone-aware timestamp string for filenames and logging.

    Args:
        settings_dict: Dictionary containing timezone setting
        format_str: strftime format string (default: "%Y%m%d_%H%M%S")

    Returns:
        Formatted timestamp string in the configured timezone
    """
    timezone_str = get_timezone_from_settings(settings_dict)
    dt = create_timezone_aware_datetime(timezone_str)
    return dt.strftime(format_str)


def get_timezone_aware_timestamp_string_sync(
    sync_db: "SyncDatabase", format_str: str = "%Y%m%d_%H%M%S"
) -> str:
    """
    Generate timezone-aware timestamp string using sync database connection.

    Args:
        sync_db: SyncDatabase instance
        format_str: strftime format string (default: "%Y%m%d_%H%M%S")

    Returns:
        Formatted timestamp string in the configured timezone
    """
    try:
        settings_dict = sync_db.get_settings_dict()
        return get_timezone_aware_timestamp_string_from_settings(
            settings_dict, format_str
        )
    except Exception as e:
        logger.warning(
            f"Failed to get timezone-aware timestamp string from sync database: {e}"
        )
        # Fallback to UTC
        return datetime.now(ZoneInfo("UTC")).strftime(format_str)


async def get_timezone_aware_timestamp_string_async(
    async_db: "AsyncDatabase", format_str: str = "%Y%m%d_%H%M%S"
) -> str:
    """
    Generate timezone-aware timestamp string using async database connection.

    Args:
        async_db: AsyncDatabase instance
        format_str: strftime format string (default: "%Y%m%d_%H%M%S")

    Returns:
        Formatted timestamp string in the configured timezone
    """
    try:
        settings_dict = await async_db.get_settings_dict()
        return get_timezone_aware_timestamp_string_from_settings(
            settings_dict, format_str
        )
    except Exception as e:
        logger.warning(
            f"Failed to get timezone-aware timestamp string from async database: {e}"
        )
        # Fallback to UTC
        return datetime.now(ZoneInfo("UTC")).strftime(format_str)


# =============================================================================
# ADDITIONAL TIME UTILITY FUNCTIONS
# =============================================================================
# These functions centralize repeated time-related code patterns found
# throughout the backend to improve maintainability and consistency.


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


def format_filename_timestamp(
    dt: datetime = None, settings_dict: Optional[Dict[str, str]] = None
) -> str:
    """
    Format datetime as filename-safe timestamp string.

    This centralizes the repeated pattern: dt.strftime("%Y%m%d_%H%M%S")

    Args:
        dt: Datetime object (defaults to current time in configured timezone)
        settings_dict: Settings dictionary for timezone (defaults to UTC)

    Returns:
        Formatted timestamp string suitable for filenames (YYYYMMDD_HHMMSS)
    """
    if dt is None:
        if settings_dict:
            timezone_str = get_timezone_from_settings(settings_dict)
            dt = create_timezone_aware_datetime(timezone_str)
        else:
            dt = utc_now()

    return dt.strftime("%Y%m%d_%H%M%S")


def format_filename_timestamp_sync(sync_db: "SyncDatabase", dt: datetime = None) -> str:
    """
    Format datetime as filename-safe timestamp using sync database connection.

    Args:
        sync_db: SyncDatabase instance
        dt: Datetime object (defaults to current time in configured timezone)

    Returns:
        Formatted timestamp string suitable for filenames
    """
    try:
        if dt is None:
            timestamp_str = get_timezone_aware_timestamp_sync(sync_db)
            dt = parse_iso_timestamp_safe(timestamp_str)
        return format_filename_timestamp(dt)
    except Exception as e:
        logger.warning(f"Failed to format filename timestamp from sync database: {e}")
        return utc_now().strftime("%Y%m%d_%H%M%S")


async def format_filename_timestamp_async(
    async_db: "AsyncDatabase", dt: datetime = None
) -> str:
    """
    Format datetime as filename-safe timestamp using async database connection.

    Args:
        async_db: AsyncDatabase instance
        dt: Datetime object (defaults to current time in configured timezone)

    Returns:
        Formatted timestamp string suitable for filenames
    """
    try:
        if dt is None:
            timestamp_str = await get_timezone_aware_timestamp_async(async_db)
            dt = parse_iso_timestamp_safe(timestamp_str)
        return format_filename_timestamp(dt)
    except Exception as e:
        logger.warning(f"Failed to format filename timestamp from async database: {e}")
        return utc_now().strftime("%Y%m%d_%H%M%S")


def parse_time_string(time_str: str, format_str: str = "%H:%M:%S") -> time:
    """
    Parse time string to time object with error handling.

    This centralizes the repeated pattern: datetime.strptime(time_str, "%H:%M:%S").time()

    Args:
        time_str: Time string to parse
        format_str: strptime format string (default: "%H:%M:%S")

    Returns:
        time object

    Raises:
        ValueError: If time string cannot be parsed
    """
    try:
        return datetime.strptime(time_str, format_str).time()
    except (ValueError, TypeError) as e:
        logger.error(
            f"Failed to parse time string '{time_str}' with format '{format_str}': {e}"
        )
        raise ValueError(f"Invalid time format: {time_str}")


def format_time_object(time_obj: time, format_str: str = "%H:%M:%S") -> str:
    """
    Format time object to string representation.

    This centralizes the repeated pattern for time object to string conversion.

    Args:
        time_obj: time object to format
        format_str: strftime format string (default: "%H:%M:%S")

    Returns:
        Formatted time string
    """
    try:
        return time_obj.strftime(format_str)
    except (ValueError, AttributeError) as e:
        logger.error(f"Failed to format time object {time_obj}: {e}")
        return "00:00:00"  # Safe fallback


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
        basename = os.path.basename(filename)
        if basename.startswith(prefix) and len(basename) >= len(prefix) + 8:
            date_str = basename[len(prefix) : len(prefix) + 8]  # Extract YYYYMMDD
            return datetime.strptime(date_str, "%Y%m%d").date()
    except (ValueError, IndexError) as e:
        logger.debug(f"Could not extract date from filename '{filename}': {e}")

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
    from datetime import timedelta

    return timedelta(
        days=days, seconds=seconds, minutes=minutes, hours=hours, weeks=weeks
    )


def parse_timestamp_flexible(timestamp_input: Any) -> Optional[datetime]:
    """
    Flexibly parse various timestamp formats to datetime object.

    Handles strings, datetime objects, and None values gracefully.

    Args:
        timestamp_input: Various timestamp formats (str, datetime, None)

    Returns:
        Timezone-aware datetime object or None if parsing fails
    """
    if timestamp_input is None:
        return None

    # Already a datetime object
    if isinstance(timestamp_input, datetime):
        # Ensure it's timezone-aware
        if timestamp_input.tzinfo is None:
            return timestamp_input.replace(tzinfo=ZoneInfo("UTC"))
        return timestamp_input

    # String input
    if isinstance(timestamp_input, str):
        try:
            return parse_iso_timestamp_safe(timestamp_input)
        except ValueError:
            logger.debug(f"Could not parse timestamp string: {timestamp_input}")
            return None

    # Unsupported type
    logger.warning(f"Unsupported timestamp type: {type(timestamp_input)}")
    return None


def is_within_time_window(current_time: time, start_time: time, end_time: time) -> bool:
    """
    Check if current time falls within a time window.

    Handles overnight windows (e.g., 22:00-06:00) correctly.

    Args:
        current_time: Time to check
        start_time: Window start time
        end_time: Window end time

    Returns:
        True if current_time is within the window
    """
    if start_time <= end_time:
        # Normal window (e.g., 06:00-18:00)
        return start_time <= current_time <= end_time
    else:
        # Overnight window (e.g., 22:00-06:00)
        return current_time >= start_time or current_time <= end_time


def calculate_next_capture_time(
    current_time: datetime,
    interval_seconds: int,
    start_time: Optional[time] = None,
    end_time: Optional[time] = None,
) -> datetime:
    """
    Calculate next capture time considering interval and optional time window.

    Args:
        current_time: Current timezone-aware datetime
        interval_seconds: Capture interval in seconds
        start_time: Optional window start time
        end_time: Optional window end time

    Returns:
        Next capture datetime
    """
    # Calculate base next capture time
    next_capture = current_time + create_time_delta(seconds=interval_seconds)

    # If no time window, return the calculated time
    if start_time is None or end_time is None:
        return next_capture

    next_time = next_capture.time()

    # If next capture is within window, use it
    if is_within_time_window(next_time, start_time, end_time):
        return next_capture

    # Otherwise, move to next window start
    next_date = next_capture.date()

    # Create datetime for window start on the next capture date
    window_start = datetime.combine(next_date, start_time)
    window_start = window_start.replace(tzinfo=current_time.tzinfo)

    # If window start is in the past, move to next day
    if window_start <= current_time:
        window_start += create_time_delta(days=1)

    return window_start


def format_date_string(dt: datetime = None, format_str: str = "%Y-%m-%d") -> str:
    """
    Format datetime as date string.
    
    This centralizes the repeated pattern: dt.strftime("%Y-%m-%d")
    
    Args:
        dt: Datetime object (defaults to current UTC time)
        format_str: strftime format string (default: "%Y-%m-%d")
        
    Returns:
        Formatted date string
    """
    if dt is None:
        dt = utc_now()
    
    return dt.strftime(format_str)


def format_date_string_sync(sync_db: "SyncDatabase", dt: datetime = None, format_str: str = "%Y-%m-%d") -> str:
    """
    Format datetime as date string using sync database connection.
    
    Args:
        sync_db: SyncDatabase instance
        dt: Datetime object (defaults to current time in configured timezone)
        format_str: strftime format string (default: "%Y-%m-%d")
        
    Returns:
        Formatted date string in the configured timezone
    """
    try:
        if dt is None:
            timestamp_str = get_timezone_aware_timestamp_sync(sync_db)
            dt = parse_iso_timestamp_safe(timestamp_str)
        return format_date_string(dt, format_str)
    except Exception as e:
        logger.warning(f"Failed to format date string from sync database: {e}")
        return utc_now().strftime(format_str)


async def format_date_string_async(async_db: "AsyncDatabase", dt: datetime = None, format_str: str = "%Y-%m-%d") -> str:
    """
    Format datetime as date string using async database connection.
    
    Args:
        async_db: AsyncDatabase instance  
        dt: Datetime object (defaults to current time in configured timezone)
        format_str: strftime format string (default: "%Y-%m-%d")
        
    Returns:
        Formatted date string in the configured timezone
    """
    try:
        if dt is None:
            timestamp_str = await get_timezone_aware_timestamp_async(async_db)
            dt = parse_iso_timestamp_safe(timestamp_str)
        return format_date_string(dt, format_str)
    except Exception as e:
        logger.warning(f"Failed to format date string from async database: {e}")
        return utc_now().strftime(format_str)


# Legacy compatibility functions
def get_current_timestamp_formatted() -> str:
    """
    DEPRECATED: Use format_filename_timestamp() instead.
    """
    logger.warning(
        "Using deprecated get_current_timestamp_formatted(). Use format_filename_timestamp() instead."
    )
    return format_filename_timestamp()
