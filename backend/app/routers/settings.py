# backend/app/routers/settings.py
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from loguru import logger

from ..database import async_db
from ..models import Setting, SettingCreate, SettingUpdate

router = APIRouter()


@router.get("/")
async def get_settings():
    """Get all settings as a dictionary"""
    try:
        settings_dict = await async_db.get_settings_dict()
        return settings_dict
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch settings")


@router.get("/list", response_model=List[Setting])
async def get_settings_list():
    """Get all settings as a list"""
    try:
        settings = await async_db.get_settings()
        return settings
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch settings")


@router.get("/{key}", response_model=Setting)
async def get_setting(key: str):
    """Get a specific setting by key"""
    try:
        setting = await async_db.get_setting_by_key(key)
        if not setting:
            raise HTTPException(status_code=404, detail="Setting not found")
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
        setting = await async_db.create_or_update_setting(
            setting_data.key, setting_data.value
        )
        if not setting:
            raise HTTPException(status_code=500, detail="Failed to create setting")

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

        setting = await async_db.create_or_update_setting(key, str(value))
        if not setting:
            raise HTTPException(status_code=500, detail="Failed to update setting")

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
        setting = await async_db.create_or_update_setting(key, setting_data.value)
        if not setting:
            raise HTTPException(status_code=500, detail="Failed to update setting")

        logger.info(f"Updated setting: {key} = {setting_data.value}")
        return setting
    except Exception as e:
        logger.error(f"Error updating setting {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update setting")


@router.delete("/{key}")
async def delete_setting(key: str):
    """Delete a setting"""
    try:
        success = await async_db.delete_setting(key)
        if not success:
            raise HTTPException(status_code=404, detail="Setting not found")

        logger.info(f"Deleted setting: {key}")
        return {"message": "Setting deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting setting {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete setting")
