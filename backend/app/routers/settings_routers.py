# backend/app/routers/settings_routers.py
"""
System configuration HTTP endpoints.

Role: System configuration HTTP endpoints
Responsibilities: Global settings CRUD, validation, inheritance resolution
Interactions: Uses SettingsService for business logic, handles settings validation and broadcasting changes
"""

from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from loguru import logger

from ..dependencies import SettingsServiceDep
from ..models import Setting, SettingCreate, SettingUpdate
from ..models.shared_models import CorruptionSettings
from ..utils.router_helpers import handle_exceptions, create_success_response
from ..utils.timezone_utils import (
    get_timezone_aware_timestamp_async,
    validate_timezone,
    get_supported_timezones,
    get_timezone_from_settings,
)

router = APIRouter(prefix="/settings", tags=["settings"])

# Settings that should be masked when returned
MASKABLE_SETTINGS = {"openweather_api_key"}


def mask_api_key(api_key: str) -> str:
    """Mask API key for display purposes."""
    if not api_key or len(api_key) < 8:
        return "*" * 8
    return f"{api_key[:4]}{'*' * (len(api_key) - 8)}{api_key[-4:]}"


@router.get("/")
@handle_exceptions("get settings")
async def get_settings(settings_service: SettingsServiceDep):
    """Get all settings as a dictionary"""
    settings_dict = await settings_service.get_all_settings()

    # Mask sensitive settings for display
    for key, value in settings_dict.items():
        if key in MASKABLE_SETTINGS and value:
            settings_dict[key] = mask_api_key(value)

    return settings_dict


@router.get("/list", response_model=List[Setting])
@handle_exceptions("get settings list")
async def get_settings_list(settings_service: SettingsServiceDep):
    """Get all settings as a list"""
    settings = await settings_service.get_settings()
    return settings


@router.get("/{key}")
@handle_exceptions("get setting")
async def get_setting_by_key(key: str, settings_service: SettingsServiceDep):
    """Get a specific setting by key"""
    value = await settings_service.get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Setting not found")

    # Return simple key-value response since we don't track individual setting timestamps
    return {"key": key, "value": value}


@router.post("/")
@handle_exceptions("create setting")
async def create_setting(
    setting_data: SettingCreate, settings_service: SettingsServiceDep
):
    """Create a new setting"""
    success = await settings_service.set_setting(setting_data.key, setting_data.value)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create setting")

    logger.info(f"Created/updated setting: {setting_data.key}")
    return {
        "key": setting_data.key,
        "value": setting_data.value,
        "success": True,
        "message": "Setting created successfully",
    }


@router.put("/")
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

    logger.info(f"Updated setting: {key} = {value}")
    return {
        "key": key,
        "value": str(value),
        "success": True,
        "message": "Setting updated successfully",
    }


@router.put("/{key}")
@handle_exceptions("update setting")
async def update_setting(
    key: str, setting_data: SettingUpdate, settings_service: SettingsServiceDep
):
    """Update a setting by key"""
    success = await settings_service.set_setting(key, setting_data.value)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update setting")

    logger.info(f"Updated setting: {key} = {setting_data.value}")
    return {
        "key": key,
        "value": setting_data.value,
        "success": True,
        "message": "Setting updated successfully",
    }


@router.delete("/{key}")
@handle_exceptions("delete setting")
async def delete_setting(key: str, settings_service: SettingsServiceDep):
    """Delete a setting"""
    success = await settings_service.delete_setting(key)
    if not success:
        raise HTTPException(status_code=404, detail="Setting not found")

    logger.info(f"Deleted setting: {key}")
    return create_success_response("Setting deleted successfully")


@router.post("/bulk")
@handle_exceptions("update multiple settings")
async def update_multiple_settings(
    settings_data: Dict[str, str], settings_service: SettingsServiceDep
):
    """Update multiple settings in a single transaction"""
    success = await settings_service.set_multiple_settings(settings_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update settings")

    logger.info(f"Updated {len(settings_data)} settings in bulk")
    return create_success_response(
        f"Successfully updated {len(settings_data)} settings",
        updated_keys=list(settings_data.keys()),
    )


@router.get("/timezone/supported")
@handle_exceptions("get supported timezones")
async def get_supported_timezones_endpoint():
    """Get list of supported timezone identifiers"""
    timezones = get_supported_timezones()
    return {"timezones": timezones, "count": len(timezones), "default": "UTC"}


@router.post("/timezone/validate")
@handle_exceptions("validate timezone")
async def validate_timezone_endpoint(timezone_data: Dict[str, str]):
    """Validate a timezone string"""
    timezone_str = timezone_data.get("timezone")
    if not timezone_str:
        raise HTTPException(status_code=400, detail="Timezone is required")

    is_valid = validate_timezone(timezone_str)
    return {
        "timezone": timezone_str,
        "valid": is_valid,
        "message": f"Timezone '{timezone_str}' is {'valid' if is_valid else 'invalid'}",
    }


@router.get("/timezone/current")
@handle_exceptions("get current timezone")
async def get_current_timezone(settings_service: SettingsServiceDep):
    """Get current timezone setting and timestamp"""
    all_settings = await settings_service.get_all_settings()
    current_timezone = get_timezone_from_settings(all_settings)
    current_timestamp = await get_timezone_aware_timestamp_async(settings_service.db)

    return {
        "timezone": current_timezone,
        "current_time": current_timestamp.isoformat(),
        "is_utc": current_timezone == "UTC",
        "valid": validate_timezone(current_timezone),
    }


@router.put("/timezone")
@handle_exceptions("update timezone")
async def update_timezone(
    timezone_data: Dict[str, str], settings_service: SettingsServiceDep
):
    """Update system timezone with validation"""
    new_timezone = timezone_data.get("timezone")
    if not new_timezone:
        raise HTTPException(status_code=400, detail="Timezone is required")

    # Validate timezone
    if not validate_timezone(new_timezone):
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {new_timezone}")

    # Update setting
    success = await settings_service.set_setting("timezone", new_timezone)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update timezone")

    # Get new timestamp with updated timezone
    new_timestamp = await get_timezone_aware_timestamp_async(settings_service.db)

    logger.info(f"System timezone updated to: {new_timezone}")
    return {
        "success": True,
        "timezone": new_timezone,
        "updated_at": new_timestamp.isoformat(),
        "message": f"System timezone updated to {new_timezone}",
    }


@router.get("/corruption/settings", response_model=CorruptionSettings)
@handle_exceptions("get corruption settings")
async def get_corruption_settings(settings_service: SettingsServiceDep):
    """Get corruption detection related settings"""
    corruption_settings = await settings_service.get_corruption_settings()
    return corruption_settings
