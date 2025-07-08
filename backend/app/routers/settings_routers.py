# backend/app/routers/settings_routers.py
"""
System configuration HTTP endpoints.

Role: System configuration HTTP endpoints
Responsibilities: Global settings CRUD, validation, inheritance resolution
Interactions: Uses SettingsService for business logic, handles settings validation and broadcasting changes
"""

from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Response
from loguru import logger

from ..dependencies import SettingsServiceDep, AsyncDatabaseDep, SyncDatabaseDep
from ..models import (
    Setting,
    SettingCreate,
    SettingUpdate,
    BulkSettingsUpdate,
    WeatherSettingUpdate,
)
from ..utils.router_helpers import handle_exceptions
from ..utils.response_helpers import ResponseFormatter
from ..utils.cache_manager import (
    generate_collection_etag,
    generate_composite_etag,
    generate_content_hash_etag,
)
from ..constants import (
    EVENT_SETTING_UPDATED,
    EVENT_SETTING_DELETED,
    WEATHER_SETTINGS_KEYS,
)
from ..database.weather_operations import SyncWeatherOperations

# TODO: CACHING STRATEGY - ETAG + CACHE (PERFECT USE CASE)
# Settings are the perfect example for ETag + Cache-Control strategy:
# - GET operations: ETag + 10-15 min cache - settings change occasionally, fresh when changed
# - Write operations: SSE broadcasting - immediate real-time updates across system
# - Different cache durations based on setting type (weather, system, user preferences)
# Individual endpoint TODOs are well-defined throughout this file.
router = APIRouter(tags=["settings"])


# Accept both /settings/ and /settings (no trailing slash)
# IMPLEMENTED: ETag + 10 minute cache (settings change occasionally)
# ETag based on hash of all settings updated_at timestamps
@router.get("/settings")
@router.get("")  # Add this line to handle /api/settings without trailing slash
@handle_exceptions("get settings")
async def get_settings(
    response: Response, settings_service: SettingsServiceDep, sync_db: SyncDatabaseDep
):
    """Get all settings as a dictionary"""
    # Get all settings from service
    settings_dict = await settings_service.get_all_settings()

    # Get actual API key for frontend display (security is maintained by hashed storage)
    actual_key = await settings_service.get_openweather_api_key_for_display()
    if actual_key:
        settings_dict["openweather_api_key"] = actual_key
    else:
        # Ensure the key is not present if we can't retrieve it
        settings_dict.pop("openweather_api_key", None)

    # Get latest weather data from weather table using sync operations
    weather_ops = SyncWeatherOperations(sync_db)
    weather_data = weather_ops.get_latest_weather()

    if weather_data:
        # Convert weather timestamp to configured timezone for display
        weather_date_fetched = weather_data.get("weather_date_fetched")
        if weather_date_fetched:
            # Import timezone utilities
            from ..utils.timezone_utils import get_timezone_from_settings
            from zoneinfo import ZoneInfo

            # Get configured timezone
            timezone_str = get_timezone_from_settings(settings_dict)

            # Convert UTC timestamp to configured timezone
            try:
                if isinstance(weather_date_fetched, str):
                    # Parse string to datetime if needed
                    from datetime import datetime

                    weather_date_fetched = datetime.fromisoformat(
                        weather_date_fetched.replace("Z", "+00:00")
                    )

                # Convert to configured timezone (weather_date_fetched should now be datetime)
                tz = ZoneInfo(timezone_str)
                local_time = weather_date_fetched.astimezone(tz)
                settings_dict["weather_date_fetched"] = local_time.isoformat()
            except Exception as e:
                logger.warning(
                    f"Failed to convert weather timestamp to timezone {timezone_str}: {e}"
                )
                # Fallback to original timestamp with safe conversion
                settings_dict["weather_date_fetched"] = str(weather_date_fetched)
        else:
            settings_dict["weather_date_fetched"] = ""

        # Add other weather data to settings dict for backward compatibility
        settings_dict["current_temp"] = (
            str(weather_data.get("current_temp", ""))
            if weather_data.get("current_temp") is not None
            else ""
        )
        settings_dict["current_weather_icon"] = weather_data.get(
            "current_weather_icon", ""
        )
        settings_dict["current_weather_description"] = weather_data.get(
            "current_weather_description", ""
        )
        sunrise_ts = weather_data.get("sunrise_timestamp")
        settings_dict["sunrise_timestamp"] = (
            sunrise_ts.isoformat()
            if sunrise_ts and hasattr(sunrise_ts, "isoformat")
            else str(sunrise_ts) if sunrise_ts else ""
        )

        sunset_ts = weather_data.get("sunset_timestamp")
        settings_dict["sunset_timestamp"] = (
            sunset_ts.isoformat()
            if sunset_ts and hasattr(sunset_ts, "isoformat")
            else str(sunset_ts) if sunset_ts else ""
        )

    # Generate ETag based on the content of all settings
    etag = generate_content_hash_etag(settings_dict)

    # Add caching for settings
    response.headers["Cache-Control"] = (
        "public, max-age=600, s-maxage=600"  # 10 minutes
    )
    response.headers["ETag"] = etag

    return ResponseFormatter.success(
        "Settings retrieved successfully", data=settings_dict
    )


# IMPLEMENTED: ETag + 10 minute cache (settings list changes occasionally)
# ETag based on hash of all settings updated_at timestamps
@router.get("/settings/list", response_model=List[Setting])
@handle_exceptions("get settings list")
async def get_settings_list(response: Response, settings_service: SettingsServiceDep):
    """Get all settings as a list"""
    settings = await settings_service.get_settings()

    # Generate ETag based on all settings' updated_at timestamps
    if settings:
        etag = generate_collection_etag([s.updated_at for s in settings])
    else:
        etag = generate_content_hash_etag("empty")

    # Add caching for settings list
    response.headers["Cache-Control"] = (
        "public, max-age=600, s-maxage=600"  # 10 minutes
    )
    response.headers["ETag"] = etag

    return settings


# IMPLEMENTED: ETag + 15 minute cache (individual settings change rarely)
# ETag = f'"{key}-{setting.updated_at.timestamp()}"'
@router.get("/settings/{key}")
@handle_exceptions("get setting")
async def get_setting_by_key(
    response: Response, key: str, settings_service: SettingsServiceDep
):
    """Get a specific setting by key"""
    value = await settings_service.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Setting not found")

    # Generate ETag based on key and value content for individual setting cache validation
    etag = generate_content_hash_etag(f"{key}-{value}")

    # Add longer cache for individual settings
    response.headers["Cache-Control"] = (
        "public, max-age=900, s-maxage=900"  # 15 minutes
    )
    response.headers["ETag"] = etag

    return ResponseFormatter.success(
        "Setting retrieved successfully", data={"key": key, "value": value}
    )


@router.post("/settings")
@handle_exceptions("create setting")
async def create_setting(
    setting_data: SettingCreate, settings_service: SettingsServiceDep
):
    """Create a new setting"""
    success = await settings_service.set_setting(setting_data.key, setting_data.value)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create setting")

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        "Setting created successfully",
        data={"key": setting_data.key, "value": setting_data.value},
    )


@router.put("/settings")
@handle_exceptions("update setting from body")
async def update_setting_body(
    setting_data: Dict[str, Any], settings_service: SettingsServiceDep
):
    """Update a setting using request body"""
    # Extract key and value from request body
    key = setting_data.get("key")
    value = setting_data.get("value")

    if not key:
        raise HTTPException(status_code=400, detail="Setting key is required")
    if value is None:
        raise HTTPException(status_code=400, detail="Setting value is required")

    success = await settings_service.set_setting(key, str(value))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update setting")

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        "Setting updated successfully", data={"key": key, "value": str(value)}
    )


@router.put("/settings/{key}")
@handle_exceptions("update setting")
async def update_setting(
    key: str, setting_data: SettingUpdate, settings_service: SettingsServiceDep
):
    """Update a setting by key"""
    success = await settings_service.set_setting(key, setting_data.value)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update setting")

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        "Setting updated successfully", data={"key": key, "value": setting_data.value}
    )


@router.delete("/settings/{key}")
@handle_exceptions("delete setting")
async def delete_setting(key: str, settings_service: SettingsServiceDep):
    """Delete a setting"""
    success = await settings_service.delete_setting(key)
    if not success:
        raise HTTPException(status_code=404, detail="Setting not found")

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success("Setting deleted successfully")


@router.post("/settings/bulk")
@handle_exceptions("update multiple settings")
async def update_multiple_settings(
    bulk_data: BulkSettingsUpdate, settings_service: SettingsServiceDep
):
    """Update multiple settings in a single transaction"""
    success = await settings_service.set_multiple_settings(bulk_data.settings)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update settings")

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        f"Successfully updated {len(bulk_data.settings)} settings",
        data={"updated_keys": list(bulk_data.settings.keys())},
    )


# IMPLEMENTED: ETag + 15 minute cache (weather settings change rarely)
# ETag based on weather settings updated_at timestamps
@router.get("/settings/weather")
@handle_exceptions("get weather settings")
async def get_weather_settings(
    response: Response, settings_service: SettingsServiceDep
):
    """Get weather-related settings"""
    weather_settings = {}

    for key in WEATHER_SETTINGS_KEYS:
        value = await settings_service.get_setting(key)
        if value is not None:
            weather_settings[key] = value

    # Generate ETag based on content of weather settings
    etag = generate_content_hash_etag(weather_settings)

    # Add longer cache for weather settings (they change rarely)
    response.headers["Cache-Control"] = (
        "public, max-age=900, s-maxage=900"  # 15 minutes
    )
    response.headers["ETag"] = etag

    return ResponseFormatter.success(
        "Weather settings retrieved successfully", data=weather_settings
    )


@router.put("/settings/weather")
@handle_exceptions("update weather setting")
async def update_weather_setting(
    setting_data: WeatherSettingUpdate, settings_service: SettingsServiceDep
):
    """Update a weather-related setting with validation"""
    key = setting_data.key
    value = setting_data.value

    success = await settings_service.set_setting(key, str(value))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update weather setting")

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        "Weather setting updated successfully", data={"key": key, "value": str(value)}
    )


@router.post("/settings/weather/refresh")
@handle_exceptions("refresh weather data")
async def refresh_weather_data(
    sync_db: SyncDatabaseDep, settings_service: SettingsServiceDep
):
    """Manually refresh weather data immediately"""
    # Import here to avoid circular imports
    from ..services.weather.service import WeatherManager
    from ..database.weather_operations import SyncWeatherOperations

    # Get weather settings
    settings_dict = await settings_service.get_all_settings()

    # Check if weather is enabled
    weather_enabled = settings_dict.get("weather_enabled", "false").lower() == "true"
    if not weather_enabled:
        raise HTTPException(status_code=400, detail="Weather integration is disabled")

    # Check required settings
    latitude = settings_dict.get("latitude")
    longitude = settings_dict.get("longitude")

    # Get API key securely through settings service
    api_key = await settings_service.get_openweather_api_key()

    if not all([latitude, longitude, api_key]):
        raise HTTPException(
            status_code=400,
            detail="Missing required weather settings (latitude, longitude, or API key)",
        )

    # Type assertions after validation to help type checker
    assert api_key is not None, "API key should not be None after validation"
    assert latitude is not None, "Latitude should not be None after validation"
    assert longitude is not None, "Longitude should not be None after validation"

    # Convert to float with error handling
    try:
        lat_float = float(latitude)
        lon_float = float(longitude)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid latitude or longitude values: {e}"
        )

    # Create weather manager and refresh
    weather_ops = SyncWeatherOperations(sync_db)
    weather_manager = WeatherManager(weather_ops, settings_service)

    try:
        logger.info(
            f"Attempting manual weather refresh with API key: {'***' + api_key[-4:] if len(api_key) > 4 else '***'}"
        )
        logger.info(f"Latitude: {latitude}, Longitude: {longitude}")

        # Create OpenWeather service directly for testing
        from ..services.weather.service import OpenWeatherService

        ow_service = OpenWeatherService(api_key, lat_float, lon_float)

        # Test API connection
        logger.info("Testing OpenWeather API connection...")
        weather_data = ow_service.fetch_current_weather()
        logger.info(f"Direct API call result: {weather_data is not None}")

        if weather_data:
            # Try to save to database using weather manager
            logger.info("Attempting to save weather data...")
            cache_success = await weather_manager.update_weather_cache(weather_data)
            logger.info(f"Cache update success: {cache_success}")

        if weather_data:
            # Create SSE event for manual weather refresh (same as worker)
            from ..database.sse_events_operations import SyncSSEEventsOperations
            from ..constants import (
                EVENT_WEATHER_UPDATED,
                SSE_PRIORITY_NORMAL,
                SSE_SOURCE_WORKER,
            )

            try:
                sse_ops = SyncSSEEventsOperations(sync_db)
                event_id = sse_ops.create_event(
                    EVENT_WEATHER_UPDATED,
                    {
                        "temperature": weather_data.temperature,
                        "icon": weather_data.icon,
                        "description": weather_data.description,
                        "date_fetched": (
                            weather_data.date_fetched.isoformat()
                            if hasattr(weather_data.date_fetched, "isoformat")
                            else str(weather_data.date_fetched)
                        ),
                    },
                    SSE_PRIORITY_NORMAL,
                    "api",  # Source is API (manual refresh) not worker
                )
                logger.info(f"Created weather update SSE event with ID: {event_id}")
            except Exception as e:
                logger.error(f"Failed to create weather update SSE event: {e}")

            return ResponseFormatter.success(
                "Weather data refreshed successfully",
                data={
                    "temperature": weather_data.temperature,
                    "description": weather_data.description,
                    "icon": weather_data.icon,
                    "sunrise_timestamp": weather_data.sunrise_timestamp,
                    "sunset_timestamp": weather_data.sunset_timestamp,
                    "date_fetched": (
                        weather_data.date_fetched.isoformat()
                        if hasattr(weather_data.date_fetched, "isoformat")
                        else str(weather_data.date_fetched)
                    ),
                },
            )
        else:
            raise HTTPException(
                status_code=500, detail="Failed to refresh weather data"
            )
    except Exception as e:
        import traceback

        logger.error(f"Weather refresh error: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Weather refresh failed: {str(e)}")
