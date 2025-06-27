# backend/app/routers/settings_routers.py
"""
System configuration HTTP endpoints.

Role: System configuration HTTP endpoints
Responsibilities: Global settings CRUD, validation, inheritance resolution
Interactions: Uses SettingsService for business logic, handles settings validation 
             and broadcasting changes
"""

from datetime import datetime, timezone
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ..dependencies import SettingsServiceDep
from ..models import Setting, SettingCreate, SettingUpdate
from ..models.shared_models import CorruptionSettings
from ..utils.router_helpers import handle_exceptions, create_success_response

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


@router.get("/{key}", response_model=Setting)
@handle_exceptions("get setting")
async def get_setting_by_key(key: str, settings_service: SettingsServiceDep):
    """Get a specific setting by key"""
    value = await settings_service.get_setting(key)
    if not value:
        raise HTTPException(status_code=404, detail="Setting not found")

    # Create a Setting object to return with timezone-aware timestamps
    current_timestamp = datetime.now(timezone.utc)
    setting = Setting(
        id=0,  # We don't track IDs in our simple settings table
        key=key,
        value=value,
        created_at=current_timestamp,
        updated_at=current_timestamp,
    )
    return setting


@router.post("/", response_model=Setting)
@handle_exceptions("create setting")
async def create_setting(setting_data: SettingCreate, settings_service: SettingsServiceDep):
    """Create a new setting"""
    success = await settings_service.set_setting(
        setting_data.key, setting_data.value
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create setting")

    # Retrieve the created setting to return it
    value = await settings_service.get_setting(setting_data.key)
    if value is None:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve created setting"
        )

    # Create a Setting object to return with timezone-aware timestamps
    current_timestamp = datetime.now(timezone.utc)
    setting = Setting(
        id=0,  # We don't track IDs in our simple settings table
        key=setting_data.key,
        value=value,
        created_at=current_timestamp,
        updated_at=current_timestamp,
    )

    logger.info(f"Created/updated setting: {setting_data.key}")
    return setting


@router.put("/", response_model=Setting)
@handle_exceptions("update setting from body")
async def update_setting_body(setting_data: Dict[str, Any], settings_service: SettingsServiceDep):
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

    # Retrieve the updated setting to return it
    updated_value = await settings_service.get_setting(key)
    if updated_value is None:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve updated setting"
        )

    # Create a Setting object to return with timezone-aware timestamps
    current_timestamp = datetime.now(timezone.utc)
    setting = Setting(
        id=0,  # We don't track IDs in our simple settings table
        key=key,
        value=updated_value,
        created_at=current_timestamp,
        updated_at=current_timestamp,
    )

    logger.info(f"Updated setting: {key} = {value}")
    return setting


@router.put("/{key}", response_model=Setting)
@handle_exceptions("update setting")
async def update_setting(key: str, setting_data: SettingUpdate, settings_service: SettingsServiceDep):
    """Update a setting by key"""
    success = await settings_service.set_setting(key, setting_data.value)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update setting")

    # Create return object with timezone-aware timestamps
    current_timestamp = datetime.now(timezone.utc)
    setting = Setting(
        id=0,
        key=key,
        value=setting_data.value,
        created_at=current_timestamp,
        updated_at=current_timestamp,
    )

    logger.info(f"Updated setting: {key} = {setting_data.value}")
    return setting


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
async def update_multiple_settings(settings_data: Dict[str, str], settings_service: SettingsServiceDep):
    """Update multiple settings in a single transaction"""
    success = await settings_service.set_multiple_settings(settings_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update settings")

    logger.info(f"Updated {len(settings_data)} settings in bulk")
    return create_success_response(
        f"Successfully updated {len(settings_data)} settings",
        updated_keys=list(settings_data.keys())
    )


@router.get("/corruption/settings", response_model=CorruptionSettings)
@handle_exceptions("get corruption settings")
async def get_corruption_settings(settings_service: SettingsServiceDep):
    """Get corruption detection related settings"""
    corruption_settings = await settings_service.get_corruption_settings()
    return corruption_settings
