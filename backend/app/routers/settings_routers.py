# backend/app/routers/settings_routers.py

from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from loguru import logger

from ..database import async_db
from ..models import Setting, SettingCreate, SettingUpdate
from ..models.shared_models import CorruptionSettings
from ..services.settings_service import SettingsService

# Initialize service with async database
settings_service = SettingsService(async_db)
router = APIRouter()

# Settings that should be masked when returned
MASKABLE_SETTINGS = {"openweather_api_key"}


def mask_api_key(api_key: str) -> str:
    """Mask API key for display purposes."""
    if not api_key or len(api_key) < 8:
        return "*" * 8
    return f"{api_key[:4]}{'*' * (len(api_key) - 8)}{api_key[-4:]}"


@router.get("/")
async def get_settings():
    """Get all settings as a dictionary"""
    try:
        settings_dict = await settings_service.get_all_settings()

        # Mask sensitive settings for display
        for key, value in settings_dict.items():
            if key in MASKABLE_SETTINGS and value:
                settings_dict[key] = mask_api_key(value)

        return settings_dict
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch settings")


@router.get("/list", response_model=List[Setting])
async def get_settings_list():
    """Get all settings as a list"""
    try:
        settings = await settings_service.get_settings()
        return settings
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch settings")


@router.get("/{key}", response_model=Setting)
async def get_setting_by_key(key: str):
    """Get a specific setting by key"""
    try:
        value = await settings_service.get_setting(key)
        if not value:
            raise HTTPException(status_code=404, detail="Setting not found")

        # Create a Setting object to return
        setting = Setting(
            id=0,  # We don't track IDs in our simple settings table
            key=key,
            value=value,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        return setting
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching setting {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch setting")


@router.post("/", response_model=Setting)
async def create_setting(setting_data: SettingCreate):
    """Create a new setting"""
    try:
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

        # Create a Setting object to return
        setting = Setting(
            id=0,  # We don't track IDs in our simple settings table
            key=setting_data.key,
            value=value,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        logger.info(f"Created/updated setting: {setting_data.key}")
        return setting
    except Exception as e:
        logger.error(f"Error creating setting: {e}")
        raise HTTPException(status_code=500, detail="Failed to create setting")


@router.put("/", response_model=Setting)
async def update_setting_body(setting_data: Dict[str, Any]):
    """Update a setting using request body"""
    try:
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

        # Create a Setting object to return
        setting = Setting(
            id=0,  # We don't track IDs in our simple settings table
            key=key,
            value=updated_value,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        logger.info(f"Updated setting: {key} = {value}")
        return setting
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating setting: {e}")
        raise HTTPException(status_code=500, detail="Failed to update setting")


@router.put("/{key}", response_model=Setting)
async def update_setting(key: str, setting_data: SettingUpdate):
    """Update a setting by key"""
    try:
        success = await settings_service.set_setting(key, setting_data.value)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update setting")

        # Create return object
        setting = Setting(
            id=0,
            key=key,
            value=setting_data.value,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        logger.info(f"Updated setting: {key} = {setting_data.value}")
        return setting
    except Exception as e:
        logger.error(f"Error updating setting {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update setting")


@router.delete("/{key}")
async def delete_setting(key: str):
    """Delete a setting"""
    try:
        success = await settings_service.delete_setting(key)
        if not success:
            raise HTTPException(status_code=404, detail="Setting not found")

        logger.info(f"Deleted setting: {key}")
        return {"message": "Setting deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting setting {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete setting")


@router.post("/bulk")
async def update_multiple_settings(settings_data: Dict[str, str]):
    """Update multiple settings in a single transaction"""
    try:
        success = await settings_service.set_multiple_settings(settings_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update settings")

        logger.info(f"Updated {len(settings_data)} settings in bulk")
        return {
            "message": f"Successfully updated {len(settings_data)} settings",
            "updated_keys": list(settings_data.keys()),
        }
    except Exception as e:
        logger.error(f"Error updating multiple settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update settings")


@router.get("/corruption/settings", response_model=CorruptionSettings)
async def get_corruption_settings():
    """Get corruption detection related settings"""
    try:
        corruption_settings = await settings_service.get_corruption_settings()
        return corruption_settings
    except Exception as e:
        logger.error(f"Error fetching corruption settings: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch corruption settings"
        )
