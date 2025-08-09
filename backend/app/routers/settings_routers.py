# backend/app/routers/settings_routers.py
"""
System configuration HTTP endpoints.

Role: System configuration HTTP endpoints
Responsibilities: Global settings CRUD, validation, inheritance resolution
Interactions: Uses SettingsService for business logic, handles settings validation and broadcasting changes
"""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Response

from ..dependencies import SettingsServiceDep, WeatherManagerDep
from ..enums import LoggerName, LogSource
from ..models import (
    BulkSettingsUpdate,
    Setting,
    SettingCreate,
    SettingUpdate,
)
from ..services.logger import get_service_logger
from ..utils.cache_manager import (
    generate_collection_etag,
    generate_content_hash_etag,
)
from ..utils.response_helpers import ResponseFormatter
from ..utils.router_helpers import handle_exceptions

# No constants needed - all logic delegated to services

# NOTE: CACHING STRATEGY - ETAG + CACHE (IMPLEMENTED)
# Settings use ETag + Cache-Control strategy throughout this file:
# - GET operations: ETag + 10-15 min cache - settings change occasionally, fresh when changed
# - Write operations: SSE broadcasting - immediate real-time updates across system
# - Different cache durations based on setting type (weather, system, user preferences)
# Individual endpoint implementations are complete throughout this file.
logger = get_service_logger(LoggerName.API, LogSource.API)

router = APIRouter(tags=["settings"])


# Accept both /settings/ and /settings (no trailing slash)
# IMPLEMENTED: ETag + 10 minute cache (settings change occasionally)
# ETag based on hash of all settings updated_at timestamps
@router.get("/settings")
@router.get("")  # Add this line to handle /api/settings without trailing slash
@handle_exceptions("get settings")
async def get_settings(
    response: Response,
    settings_service: SettingsServiceDep,
    weather_manager: WeatherManagerDep,
):
    """Get all settings as a dictionary"""
    # Get all settings from service
    settings_dict = await settings_service.get_all_settings()

    # Handle API key display (security maintained by hashed storage)
    actual_key = await settings_service.get_openweather_api_key_for_display()
    if actual_key:
        settings_dict["openweather_api_key"] = actual_key
    else:
        settings_dict.pop("openweather_api_key", None)

    # Delegate weather data processing to weather service
    settings_dict = await weather_manager.get_weather_data_for_settings(settings_dict)

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
