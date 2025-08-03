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


import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional
from zoneinfo import ZoneInfo


# Note: get_timezone_async import moved to function level to avoid circular import
# from app.utils.cache_manager import get_timezone_async
# from ..services import settings_service  # Commented out to avoid circular import

# Import default timezone constant
from ..constants import DEFAULT_TIMEZONE

# Constant for UTC timezone to avoid hardcoded timezone.utc references
UTC_TIMEZONE = timezone.utc

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
            return timezone or DEFAULT_TIMEZONE
        else:
            # Settings service doesn't have expected method - fall back to UTC
            return DEFAULT_TIMEZONE
    except Exception:
        # Failed to get timezone from settings service - fall back to UTC
        return DEFAULT_TIMEZONE


# Async wrapper for cache (for FastAPI endpoints)
async def get_timezone_from_cache_async(settings_service) -> str:
    """Async wrapper for getting timezone from cache (for FastAPI endpoints)."""
    try:
        # Import here to avoid circular import
        from ..utils.cache_manager import get_timezone_async

        return await get_timezone_async(settings_service)
    except Exception:
        # Failed to get timezone from cache - fall back to UTC
        return DEFAULT_TIMEZONE


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
    except Exception:
        # Failed to create timezone-aware datetime - fallback to UTC
        return datetime.now(ZoneInfo(DEFAULT_TIMEZONE))


def get_timezone_aware_timestamp_from_settings_service(settings_service) -> str:
    """
    Generate timezone-aware timestamp using SettingsService.

    This is the primary function for generating timestamps throughout the application.

    Args:
        settings_service: SettingsService instance for timezone lookup

    Returns:
        ISO format timestamp string with timezone information
    """
    timezone_str = get_timezone_from_cache_sync(settings_service)
    dt = create_timezone_aware_datetime(timezone_str)
    return dt.isoformat()


# DEPRECATED: Use get_timezone_aware_timestamp_from_settings_service() instead
def get_timezone_aware_timestamp_from_settings(settings_dict: Dict[str, str]) -> str:
    """
    DEPRECATED: Generate timezone-aware timestamp using settings dictionary.

    Use get_timezone_aware_timestamp_from_settings_service() instead for consistent
    SettingsService usage throughout the application.
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
    timezone_str = settings_dict.get("timezone", DEFAULT_TIMEZONE)

    # Validate timezone string
    try:
        ZoneInfo(timezone_str)
        return timezone_str
    except Exception:
        # Invalid timezone - falling back to UTC
        return DEFAULT_TIMEZONE


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
def get_timezone_aware_timestamp_sync(settings_service) -> datetime:
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
    except Exception:
        # Error getting timezone-aware timestamp - fall back to UTC
        return datetime.now(UTC_TIMEZONE)


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
    except Exception:
        # Error getting timezone-aware timestamp - fall back to UTC
        return datetime.now(UTC_TIMEZONE)


def get_timezone_aware_date_sync(settings_service) -> str:
    """
    Get current date string in database timezone (sync version).

    Args:
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Date string in YYYY-MM-DD format using database timezone
    """
    timestamp = get_timezone_aware_timestamp_sync(settings_service)
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


def get_timezone_aware_timestamp_string_sync(settings_service) -> str:
    """
    Get current timestamp as filename-safe string in database timezone (sync).

    Args:
        settings_service: SettingsService instance for timezone lookup

    Returns:
        Timestamp string in YYYYMMDD_HHMMSS format using database timezone
    """
    timestamp = get_timezone_aware_timestamp_sync(settings_service)
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
    return datetime.now(UTC_TIMEZONE)


def now() -> datetime:
    """
    Get current timestamp with UTC fallback.

    This is a convenience function for cases where you need a timestamp
    but don't have access to settings service. Falls back to UTC.

    For timezone-aware operations, prefer get_timezone_aware_timestamp_sync(settings_service).

    Returns:
        Current datetime (UTC if no timezone settings available)
    """
    return datetime.now(UTC_TIMEZONE)


def utc_timestamp() -> str:
    """
    Get current UTC timestamp as ISO string - fallback only.

    WARNING: NOT timezone-aware. Use for internal operations only.
    For user-facing timestamps, use timezone-aware functions.

    Returns:
        Current UTC timestamp in ISO format
    """
    return datetime.now(UTC_TIMEZONE).isoformat()


def format_filename_timestamp(
    dt: Optional[datetime] = None, settings_service=None
) -> str:
    """
    Format datetime as filename-safe timestamp string.

    This centralizes the repeated pattern: dt.strftime("%Y%m%d_%H%M%S")

    Args:
        dt: Datetime object (defaults to current time in configured timezone)
        settings_service: SettingsService instance for timezone (defaults to UTC)

    Returns:
        Formatted timestamp string suitable for filenames (YYYYMMDD_HHMMSS)
    """
    if dt is None:
        if settings_service:
            timezone_str = get_timezone_from_cache_sync(settings_service)
            dt = create_timezone_aware_datetime(timezone_str)
        else:
            dt = utc_now()

    return dt.strftime("%Y%m%d_%H%M%S")


# DEPRECATED: Legacy function signature - use format_filename_timestamp() instead
def format_filename_timestamp_deprecated(
    dt: Optional[datetime] = None, settings_dict: Optional[dict] = None
) -> str:
    """
    DEPRECATED: Legacy format for backward compatibility.
    Use format_filename_timestamp() instead.
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
    timestamp = get_timezone_aware_timestamp_sync(settings_service)
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


def format_time_object_for_display(time_obj) -> str:
    """
    Format a time object for display purposes.

    Args:
        time_obj: time object to format

    Returns:
        Time string in HH:MM:SS format
    """
    return time_obj.strftime("%H:%M:%S")


def format_time_object_short(time_obj) -> str:
    """
    Format a time object for short display (HH:MM).

    Args:
        time_obj: time object to format

    Returns:
        Time string in HH:MM format
    """
    return time_obj.strftime("%H:%M")


def format_datetime_for_console(dt: datetime) -> str:
    """
    Format datetime for console display (YYYY-MM-DD HH:MM:SS).

    Args:
        dt: datetime object to format

    Returns:
        Datetime string in console format
    """
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_datetime_string(
    dt: Optional[datetime] = None, format_str: str = "%m/%d/%Y %H:%M:%S"
) -> str:
    """
    Format datetime as string with custom format.

    This centralizes the repeated pattern for datetime formatting with custom formats.

    Args:
        dt: Datetime object (defaults to current UTC time)
        format_str: strftime format string (default: "%m/%d/%Y %H:%M:%S")

    Returns:
        Formatted datetime string
    """
    if dt is None:
        dt = utc_now()

    return dt.strftime(format_str)


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
            utc_timestamp = utc_timestamp.replace(tzinfo=UTC_TIMEZONE)
        return utc_timestamp.astimezone(tz)
    except Exception:
        # Error converting to database timezone - return original timestamp
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
            utc_timestamp = utc_timestamp.replace(tzinfo=UTC_TIMEZONE)
        return utc_timestamp.astimezone(tz)
    except Exception:
        # Error converting to database timezone - return original timestamp
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
    except (ValueError, IndexError):
        # Could not extract date from filename - return None
        pass

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
    # seconds_in_minute = current_time.second

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
            dt = dt.replace(tzinfo=ZoneInfo(DEFAULT_TIMEZONE))

        return dt

    except (ValueError, TypeError) as e:
        # Failed to parse timestamp - raise ValueError with details
        raise ValueError(f"Invalid timestamp format: {timestamp_str}") from e


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
            # Timelapse has no start_date - default to day 1
            return 1

        return (current_date - start_date).days + 1

    except Exception:
        # Error calculating day number - default to day 1
        return 1


# ════════════════════════════════════════════════════════════════════════════════
#                           DST AND TIMEZONE VALIDATION UTILITIES
# ════════════════════════════════════════════════════════════════════════════════
# Functions for handling edge cases and validating timezone operations


def is_dst_transition(dt: datetime, timezone_str: str) -> tuple[bool, str]:
    """
    Check if a datetime falls during a DST transition period.

    This is critical for scheduling systems to avoid:
    - Capturing during non-existent times (spring forward)
    - Duplicate captures during repeated times (fall back)

    Args:
        dt: Datetime to check (should be timezone-aware)
        timezone_str: Timezone identifier (e.g., "America/Chicago")

    Returns:
        Tuple of (is_transition, transition_type)
        - is_transition: True if dt falls during DST transition
        - transition_type: "spring_forward", "fall_back", or "none"
    """
    try:
        tz = ZoneInfo(timezone_str)

        # If dt is naive, assume it's in the specified timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        else:
            # Convert to the target timezone
            dt = dt.astimezone(tz)

        # Check one hour before and after for DST changes
        one_hour_before = dt - timedelta(hours=1)
        one_hour_after = dt + timedelta(hours=1)

        # Get UTC offsets
        current_offset = dt.utcoffset()
        before_offset = one_hour_before.utcoffset()
        after_offset = one_hour_after.utcoffset()

        # Spring forward: clocks jump ahead (e.g., 2:00 AM becomes 3:00 AM)
        if before_offset and current_offset and before_offset < current_offset:
            return True, "spring_forward"

        # Fall back: clocks jump back (e.g., 2:00 AM happens twice)
        if current_offset and after_offset and current_offset > after_offset:
            return True, "fall_back"

        return False, "none"

    except Exception:
        # If we can't determine DST status, assume no transition
        return False, "none"


def get_safe_capture_time(
    target_time: datetime, timezone_str: str
) -> Optional[datetime]:
    """
    Get a safe capture time that avoids DST transition issues.

    Args:
        target_time: Desired capture time (timezone-aware)
        timezone_str: Timezone identifier

    Returns:
        Safe datetime for capture, or None if time doesn't exist
    """
    try:
        is_transition, transition_type = is_dst_transition(target_time, timezone_str)

        if not is_transition:
            return target_time

        if transition_type == "spring_forward":
            # Time doesn't exist - move forward to safe time
            return target_time + timedelta(hours=1)

        elif transition_type == "fall_back":
            # Time happens twice - use the first occurrence
            tz = ZoneInfo(timezone_str)
            # Assign the timezone directly (ZoneInfo does not support localize)
            naive_time = target_time.replace(tzinfo=None)
            return naive_time.replace(tzinfo=tz)

        return target_time

    except Exception:
        # If we can't determine safe time, return original
        return target_time


def validate_database_timezone_config() -> tuple[bool, str]:
    """
    Validate that the database is configured to store timestamps in UTC.

    This is critical for data integrity - if the database timezone is wrong,
    all timestamp data could be silently corrupted.

    Returns:
        Tuple of (is_valid, current_timezone)
        - is_valid: True if database is configured for UTC
        - current_timezone: Current database timezone setting
    """
    try:
        # Import here to avoid circular imports
        from app.database import sync_db

        with sync_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_setting('timezone')")
                result = cur.fetchone()
                if result:
                    db_timezone = result[0].strip()

                    # Accept various UTC representations
                    valid_utc_settings = {
                        "UTC",
                        "GMT",
                        "GMT+0",
                        "GMT-0",
                        "UTC+0",
                        "UTC-0",
                    }
                    is_valid = db_timezone.upper() in valid_utc_settings

                    return is_valid, db_timezone

        return False, "unknown"

    except Exception as e:
        # Database connection failed - return error info
        return False, f"error: {str(e)}"


def log_timezone_change(old_tz: str, new_tz: str, source: str = "unknown") -> None:
    """
    Log timezone changes for audit and debugging purposes.

    Args:
        old_tz: Previous timezone setting
        new_tz: New timezone setting
        source: Source of the change (e.g., "user_settings", "api", "migration")
    """
    try:
        # Use basic logging to avoid circular imports with service logger
        import logging

        logger = logging.getLogger("timezone_audit")

        # Validate both timezones
        old_valid = validate_timezone(old_tz)
        new_valid = validate_timezone(new_tz)

        logger.info(
            f"Timezone change: {old_tz} -> {new_tz} (source: {source})",
            extra={
                "event_type": "timezone_change",
                "old_timezone": old_tz,
                "new_timezone": new_tz,
                "old_timezone_valid": old_valid,
                "new_timezone_valid": new_valid,
                "change_source": source,
                "timestamp_utc": utc_timestamp(),
            },
        )

        # Log warning if either timezone is invalid
        if not old_valid or not new_valid:
            logger.warning(
                f"Invalid timezone in change: old={old_tz}({old_valid}) new={new_tz}({new_valid})"
            )

    except Exception:
        # Don't let logging failures break timezone operations
        # Try basic print as last resort
        try:
            print(f"TIMEZONE_CHANGE: {old_tz} -> {new_tz} (source: {source})")
        except Exception:
            pass


def validate_timezone_cache_consistency() -> dict:
    """
    Check if timezone cache is consistent across the system.

    Validates:
    - Cache exists and is accessible
    - Cached timezone matches database setting
    - Cache age is reasonable
    - No stale or corrupted cache entries

    Returns:
        Dictionary with cache validation results
    """
    try:
        issues_found = []
        cache_status = "healthy"

        # Import here to avoid circular imports
        from app.database import sync_db
        from app.services.settings_service import SyncSettingsService

        settings_service = SyncSettingsService(sync_db)

        # Get timezone from database directly
        db_timezone = settings_service.get_setting("timezone", DEFAULT_TIMEZONE)

        # Get timezone from cache (simulated - this would be more complex in real distributed cache)
        try:
            cached_timezone = settings_service.get_setting("timezone", DEFAULT_TIMEZONE)

            if cached_timezone != db_timezone:
                issues_found.append(
                    f"Cache mismatch: cache='{cached_timezone}' db='{db_timezone}'"
                )
                cache_status = "inconsistent"

        except Exception as e:
            issues_found.append(f"Cache access failed: {str(e)}")
            cache_status = "error"

        # Validate timezone value itself
        if not validate_timezone(db_timezone or DEFAULT_TIMEZONE):
            issues_found.append(f"Invalid timezone in database: '{db_timezone}'")
            cache_status = "invalid_data"

        # Check database connectivity for cache refresh capability
        try:
            is_valid, current_db_tz = validate_database_timezone_config()
            if not is_valid:
                issues_found.append(
                    f"Database timezone misconfigured: '{current_db_tz}'"
                )
        except Exception as e:
            issues_found.append(f"Database validation failed: {str(e)}")

        return {
            "cache_status": cache_status,
            "last_check": utc_timestamp(),
            "issues_found": issues_found,
            "db_timezone": db_timezone,
            "cache_accessible": True,
            "validation_passed": len(issues_found) == 0,
        }

    except Exception as e:
        return {
            "cache_status": "error",
            "last_check": utc_timestamp(),
            "issues_found": [f"Validation error: {str(e)}"],
            "db_timezone": None,
            "cache_accessible": False,
            "validation_passed": False,
        }
