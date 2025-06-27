# backend/app/utils/timezone_utils.py
"""
Centralized timezone utilities that ALWAYS read from database settings table.
CRITICAL: Never use hardcoded timezones or system timezone.
AI-CONTEXT RULE: All timezone operations must use database settings.
"""

from datetime import datetime, timezone
from typing import Dict, Optional
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)


def get_timezone_from_db_sync(sync_db) -> str:
    """Get timezone setting from database (sync version for worker)"""
    try:
        timezone_setting = sync_db.get_setting("timezone", "UTC")
        return timezone_setting if timezone_setting else "UTC"
    except Exception as e:
        logger.error(f"Failed to get timezone from database: {e}")
        return "UTC"  # Safe fallback


async def get_timezone_from_db_async(async_db) -> str:
    """Get timezone setting from database (async version for FastAPI)"""
    try:
        timezone_setting = await async_db.get_setting("timezone")
        return timezone_setting if timezone_setting else "UTC"
    except Exception as e:
        logger.error(f"Failed to get timezone from database: {e}")
        return "UTC"  # Safe fallback


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
        logger.warning(f"Invalid timezone '{timezone_str}': {e}. Falling back to UTC.")
        return "UTC"


def get_supported_timezones() -> list[str]:
    """
    Get list of supported timezone identifiers.

    Returns:
        List of valid timezone strings
    """
    import zoneinfo

    return sorted(zoneinfo.available_timezones())


def get_timezone_aware_timestamp_sync(sync_db) -> datetime:
    """Get current timestamp in database-configured timezone (sync)"""
    db_timezone_str = get_timezone_from_db_sync(sync_db)
    try:
        tz = ZoneInfo(db_timezone_str)
        return datetime.now(tz)
    except Exception as e:
        logger.error(f"Error getting timezone-aware timestamp: {e}")
        return datetime.now(timezone.utc)


async def get_timezone_aware_timestamp_async(async_db) -> datetime:
    """Get current timestamp in database-configured timezone (async)"""
    db_timezone_str = await get_timezone_from_db_async(async_db)
    try:
        tz = ZoneInfo(db_timezone_str)
        return datetime.now(tz)
    except Exception as e:
        logger.error(f"Error getting timezone-aware timestamp: {e}")
        return datetime.now(timezone.utc)


def get_timezone_aware_date_sync(sync_db) -> str:
    """Get current date string in database-configured timezone (sync)"""
    timestamp = get_timezone_aware_timestamp_sync(sync_db)
    return timestamp.strftime("%Y-%m-%d")


async def get_timezone_aware_date_async(async_db) -> str:
    """Get current date string in database-configured timezone (async)"""
    timestamp = await get_timezone_aware_timestamp_async(async_db)
    return timestamp.strftime("%Y-%m-%d")


def get_timezone_aware_timestamp_string_sync(sync_db) -> str:
    """Get formatted timestamp string for filenames (sync)"""
    timestamp = get_timezone_aware_timestamp_sync(sync_db)
    return timestamp.strftime("%Y%m%d_%H%M%S")


async def get_timezone_aware_timestamp_string_async(async_db) -> str:
    """Get formatted timestamp string for filenames (async)"""
    timestamp = await get_timezone_aware_timestamp_async(async_db)
    return timestamp.strftime("%Y%m%d_%H%M%S")


def utc_now() -> datetime:
    """Get UTC timestamp - NOT TIMEZONE AWARE use for internal calculations only"""
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    """Get UTC timestamp as ISO string - fallback only, NOT TIMEZONE AWARE"""
    return datetime.now(timezone.utc).isoformat()


def convert_to_db_timezone_sync(utc_timestamp: datetime, sync_db) -> datetime:
    """Convert UTC timestamp to database timezone (sync)"""
    db_timezone_str = get_timezone_from_db_sync(sync_db)
    try:
        tz = ZoneInfo(db_timezone_str)
        if utc_timestamp.tzinfo is None:
            utc_timestamp = utc_timestamp.replace(tzinfo=timezone.utc)
        return utc_timestamp.astimezone(tz)
    except Exception as e:
        logger.error(f"Error converting to database timezone: {e}")
        return utc_timestamp


async def convert_to_db_timezone_async(utc_timestamp: datetime, async_db) -> datetime:
    """Convert UTC timestamp to database timezone (async)"""
    db_timezone_str = await get_timezone_from_db_async(async_db)
    try:
        tz = ZoneInfo(db_timezone_str)
        if utc_timestamp.tzinfo is None:
            utc_timestamp = utc_timestamp.replace(tzinfo=timezone.utc)
        return utc_timestamp.astimezone(tz)
    except Exception as e:
        logger.error(f"Error converting to database timezone: {e}")
        return utc_timestamp


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


def get_timezone_aware_time_sync(sync_db) -> str:
    """
    Get current time string (HH:MM:SS) in database-configured timezone (sync).

    Args:
        sync_db: Synchronous database connection or wrapper

    Returns:
        Time string in HH:MM:SS format for the configured timezone
    """
    timestamp = get_timezone_aware_timestamp_sync(sync_db)
    return timestamp.strftime("%H:%M:%S")


async def get_timezone_aware_time_async(async_db) -> str:
    """
    Get current time string (HH:MM:SS) in database-configured timezone (async).

    Args:
        async_db: Asynchronous database connection or wrapper

    Returns:
        Time string in HH:MM:SS format for the configured timezone
    """
    timestamp = await get_timezone_aware_timestamp_async(async_db)
    return timestamp.strftime("%H:%M:%S")
