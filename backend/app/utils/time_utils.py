# backend/app/utils/time_utils.py
"""
Centralized timezone and time utilities for database-aware operations.
CRITICAL: Never use hardcoded timezones or system timezone.
AI-CONTEXT RULE: All timezone operations must use database settings.

Timezone settings are cached in memory for performance via cache_manager.py
and only updated when the settings table changes through cache invalidation.

This module combines timezone-aware operations with pure time utilities:
- Database-aware timezone operations (primary focus)
- Pure time utilities and parsing functions
- Filename and timestamp formatting utilities
- Time calculation and duration parsing


Related Files:
- cache_manager.py: Provides the underlying caching infrastructure for settings
- cache_invalidation.py: Handles cache invalidation when settings change
- services/scheduling_service.py: Capture scheduling business logic
- services/time_window_service.py: Time window business rules
"""


from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional
from zoneinfo import ZoneInfo
from pathlib import Path
from loguru import logger
import re

# Import the cache manager for settings (async version only)
# Note: get_timezone_async is only used by async functions.
# Sync functions use direct settings service access to avoid event loop conflicts.
from app.utils.cache_manager import get_timezone_async
from ..services import settings_service


# ════════════════════════════════════════════════════════════════════════════════
#                           DATABASE-AWARE TIMEZONE OPERATIONS
# ════════════════════════════════════════════════════════════════════════════════
# Functions that require database settings and cache integration


# Sync timezone cache access (for non-async contexts)
def get_timezone_from_cache_sync(settings_service) -> str:
    """
    Get timezone using SettingsService (sync version, bypasses async cache).

    This function directly accesses settings without using the async cache infrastructure
    to avoid event loop conflicts in worker processes.
    """
    try:
        # Direct sync access without async cache to avoid event loop conflicts
        if hasattr(settings_service, "get_setting"):
            timezone = settings_service.get_setting("timezone")
            return timezone or "UTC"
        else:
            logger.warning(
                f"Settings service {type(settings_service)} does not have get_setting method"
            )
            return "UTC"
    except Exception as e:
        logger.error(f"❌ Failed to get timezone from settings service: {e}")
        return "UTC"


# Async wrapper for cache (for FastAPI endpoints)
async def get_timezone_from_cache_async(settings_service) -> str:
    """Async wrapper for getting timezone from cache (for FastAPI endpoints)."""
    try:
        return await get_timezone_async(settings_service)
    except Exception as e:
        logger.error(f"❌ Failed to get timezone from cache (async): {e}")
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
            f"⚠️ Failed to create timezone-aware datetime for '{timezone_str}': {e}"
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


def get_timezone_from_settings(settings_dict: dict) -> str:
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
        logger.warning(
            f"⚠️ Invalid timezone '{timezone_str}': {e}. Falling back to UTC."
        )
        return "UTC"


def get_supported_timezones() -> list[str]:
    """
    Get list of supported timezone identifiers.

    Returns:
        List of valid timezone strings
    """
    import zoneinfo

    return sorted(zoneinfo.available_timezones())


# ════════════════════════════════════════════════════════════════════════════════
#                       TIMEZONE-AWARE TIMESTAMP OPERATIONS
# ════════════════════════════════════════════════════════════════════════════════
# Functions that generate timestamps using database timezone settings


# Updated: Use cache-backed timezone for sync timestamp
def get_timezone_aware_timestamp_sync() -> datetime:
    """
    Get current timestamp in database timezone (sync version).

    Uses cached timezone settings from database to generate timezone-aware
    datetime objects. Falls back to UTC if timezone cannot be determined.

    Args:
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Current datetime in database timezone
    """
    db_timezone_str = get_timezone_from_cache_sync(settings_service)
    try:
        tz = ZoneInfo(db_timezone_str)
        return datetime.now(tz)
    except Exception as e:
        logger.error(f"❌ Error getting timezone-aware timestamp: {e}")
        return datetime.now(timezone.utc)


# Updated: Use cache-backed timezone for async timestamp
async def get_timezone_aware_timestamp_async(settings_service) -> datetime:
    """
    Get current timestamp in database timezone (async version).

    Uses cached timezone settings from database to generate timezone-aware
    datetime objects. Falls back to UTC if timezone cannot be determined.

    Args:
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Current datetime in database timezone
    """
    db_timezone_str = await get_timezone_from_cache_async(settings_service)
    try:
        tz = ZoneInfo(db_timezone_str)
        return datetime.now(tz)
    except Exception as e:
        logger.error(f"❌ Error getting timezone-aware timestamp: {e}")
        return datetime.now(timezone.utc)


def get_timezone_aware_date_sync(settings_service) -> str:
    """
    Get current date string in database timezone (sync version).

    Args:
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Date string in YYYY-MM-DD format using database timezone
    """
    timestamp = get_timezone_aware_timestamp_sync()
    return timestamp.strftime("%Y-%m-%d")


async def get_timezone_aware_date_async(settings_service) -> str:
    """
    Get current date string in database timezone (async version).

    Args:
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Date string in YYYY-MM-DD format using database timezone
    """
    timestamp = await get_timezone_aware_timestamp_async(settings_service)
    return timestamp.strftime("%Y-%m-%d")


def get_timezone_aware_timestamp_string_sync() -> str:
    """
    Get current timestamp as filename-safe string in database timezone (sync).

    Args:
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Timestamp string in YYYYMMDD_HHMMSS format using database timezone
    """
    timestamp = get_timezone_aware_timestamp_sync()
    return timestamp.strftime("%Y%m%d_%H%M%S")


async def get_timezone_aware_timestamp_string_async(settings_service) -> str:
    """
    Get current timestamp as filename-safe string in database timezone (async).

    Args:
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Timestamp string in YYYYMMDD_HHMMSS format using database timezone
    """
    timestamp = await get_timezone_aware_timestamp_async(settings_service)
    return timestamp.strftime("%Y%m%d_%H%M%S")


def utc_now() -> datetime:
    """
    Get current UTC timestamp - NOT timezone-aware.

    WARNING: Use for internal calculations only. For user-facing operations,
    use timezone-aware functions that respect database timezone settings.

    Returns:
        Current UTC datetime object
    """
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    """
    Get current UTC timestamp as ISO string - fallback only.

    WARNING: NOT timezone-aware. Use for internal operations only.
    For user-facing timestamps, use timezone-aware functions.

    Returns:
        Current UTC timestamp in ISO format
    """
    return datetime.now(timezone.utc).isoformat()


def format_filename_timestamp(
    dt: Optional[datetime] = None, settings_dict: Optional[dict] = None
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


def format_date_string(
    dt: Optional[datetime] = None, format_str: str = "%Y-%m-%d"
) -> str:
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


def get_timezone_aware_time_sync(settings_service) -> str:
    """
    Get current time string in database timezone (sync version).

    Args:
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Time string in HH:MM:SS format using database timezone
    """
    timestamp = get_timezone_aware_timestamp_sync()
    return timestamp.strftime("%H:%M:%S")


async def get_timezone_aware_time_async(settings_service) -> str:
    """
    Get current time string in database timezone (async version).

    Args:
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Time string in HH:MM:SS format using database timezone
    """
    timestamp = await get_timezone_aware_timestamp_async(settings_service)
    return timestamp.strftime("%H:%M:%S")


# ════════════════════════════════════════════════════════════════════════════════
#                            TIMEZONE CONVERSION FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════
# Functions for converting between UTC and database timezone


def convert_to_db_timezone_sync(utc_timestamp: datetime, settings_service) -> datetime:
    """
    Convert UTC timestamp to database timezone (sync, cache-backed).

    Args:
        utc_timestamp: UTC datetime to convert (timezone-naive or timezone-aware)
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Datetime object converted to database timezone
    """
    db_timezone_str = get_timezone_from_cache_sync(settings_service)
    try:
        tz = ZoneInfo(db_timezone_str)
        if utc_timestamp.tzinfo is None:
            utc_timestamp = utc_timestamp.replace(tzinfo=timezone.utc)
        return utc_timestamp.astimezone(tz)
    except Exception as e:
        logger.error(f"❌ Error converting to database timezone: {e}")
        return utc_timestamp


async def convert_to_db_timezone_async(
    utc_timestamp: datetime, settings_service
) -> datetime:
    """
    Convert UTC timestamp to database timezone (async, cache-backed).

    Args:
        utc_timestamp: UTC datetime to convert (timezone-naive or timezone-aware)
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Datetime object converted to database timezone
    """
    db_timezone_str = await get_timezone_from_cache_async(settings_service)
    try:
        tz = ZoneInfo(db_timezone_str)
        if utc_timestamp.tzinfo is None:
            utc_timestamp = utc_timestamp.replace(tzinfo=timezone.utc)
        return utc_timestamp.astimezone(tz)
    except Exception as e:
        logger.error(f"❌ Error converting to database timezone: {e}")
        return utc_timestamp


# ════════════════════════════════════════════════════════════════════════════════
#                               PURE TIME UTILITIES
# ════════════════════════════════════════════════════════════════════════════════
# Pure time utilities with no database dependencies - merged from time_utils.py


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
        logger.debug(f"🔍 Could not extract date from filename '{filename}': {e}")

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
        Filesystem-safe datetime string (YYYYMMDD_HHMMSS)
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
        logger.error(f"❌ Failed to parse timestamp '{timestamp_str}': {e}")
        raise ValueError(f"Invalid timestamp format: {timestamp_str}")


def calculate_day_number_for_timelapse(timelapse, settings_service) -> int:
    """
    Calculate day number for timelapse sequence using database timezone.

    Moved from RTSPService for better reusability across the codebase.

    Args:
        timelapse: Timelapse object or dictionary with start_date
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Day number starting from 1 (defaults to 1 if calculation fails)
    """
    try:
        current_date_str = get_timezone_aware_date_sync(settings_service)
        current_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()

        start_date = (
            timelapse.get("start_date")
            if isinstance(timelapse, dict)
            else getattr(timelapse, "start_date", None)
        )

        if not start_date:
            logger.warning("Timelapse has no start_date, defaulting day_number to 1")
            return 1

        return (current_date - start_date).days + 1

    except Exception as e:
        logger.warning(f"Error calculating day number: {e}")
        return 1
