# backend/app/routers/settings_routers.py
"""
System configuration HTTP endpoints.

Role: System configuration HTTP endpoints
Responsibilities: Global settings CRUD, validation, inheritance resolution
Interactions: Uses SettingsService for business logic, handles settings validation and broadcasting changes
"""

from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Response

from ..dependencies import SettingsServiceDep
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
from ..constants import EVENT_SETTING_UPDATED, EVENT_SETTING_DELETED, WEATHER_SETTINGS_KEYS

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
async def get_settings(response: Response, settings_service: SettingsServiceDep):
    """Get all settings as a dictionary"""
    # Get all settings from service
    settings_dict = await settings_service.get_all_settings()

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
