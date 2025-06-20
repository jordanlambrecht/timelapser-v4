# backend/app/routers/settings.py
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from loguru import logger

from ..database import async_db
from ..models import Setting, SettingCreate, SettingUpdate
from ..hashing import hash_api_key, mask_api_key, verify_api_key

router = APIRouter()

# Settings that should be hashed for security
HASHABLE_SETTINGS = {"openweather_api_key": "openweather_api_key_hash"}

# Settings that should be masked when returned
MASKABLE_SETTINGS = {"openweather_api_key_hash"}


@router.get("/")
async def get_settings():
    """Get all settings as a dictionary"""
    try:
        settings_dict = await async_db.get_settings_dict()

        # Mask sensitive settings for display
        for key, value in settings_dict.items():
            if key in MASKABLE_SETTINGS and value:
                settings_dict[key] = mask_api_key(value)

        return settings_dict
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch settings") from e


@router.get("/list", response_model=List[Setting])
async def get_settings_list():
    """Get all settings as a list"""
    try:
        settings = await async_db.get_settings()
        return settings
    except Exception as e:
        logger.error(f"Error fetching settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch settings") from e


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
        raise HTTPException(status_code=500, detail="Failed to fetch setting") from e


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
        raise HTTPException(status_code=500, detail="Failed to create setting") from e


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

        # Handle API key hashing
        if key in HASHABLE_SETTINGS:
            # Store the hash instead of the raw key
            hash_key = HASHABLE_SETTINGS[key]
            hashed_value = hash_api_key(str(value)) if value else ""
            setting = await async_db.create_or_update_setting(hash_key, hashed_value)
            logger.info(f"Updated setting (hashed): {hash_key}")
        else:
            setting = await async_db.create_or_update_setting(key, str(value))
            logger.info(f"Updated setting: {key} = {value}")

        if not setting:
            raise HTTPException(status_code=500, detail="Failed to update setting")

        return setting
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating setting: {e}")
        raise HTTPException(status_code=500, detail="Failed to update setting") from e


@router.put("/{key}", response_model=Setting)
async def update_setting(key: str, setting_data: SettingUpdate):
    """Update a setting by key"""
    try:
        # Handle API key hashing
        if key in HASHABLE_SETTINGS:
            # Store the hash instead of the raw key
            hash_key = HASHABLE_SETTINGS[key]
            hashed_value = (
                hash_api_key(setting_data.value) if setting_data.value else ""
            )
            setting = await async_db.create_or_update_setting(hash_key, hashed_value)
            logger.info(f"Updated setting (hashed): {hash_key}")
        else:
            setting = await async_db.create_or_update_setting(key, setting_data.value)
            logger.info(f"Updated setting: {key} = {setting_data.value}")

        if not setting:
            raise HTTPException(status_code=500, detail="Failed to update setting")

        return setting
    except Exception as e:
        logger.error(f"Error updating setting {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update setting") from e


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
        raise HTTPException(status_code=500, detail="Failed to delete setting") from e


@router.post("/verify-api-key")
async def verify_api_key_endpoint(request_data: Dict[str, Any]):
    """Verify an API key against the stored hash"""
    try:
        api_key = request_data.get("api_key")
        key_type = request_data.get("key_type", "openweather_api_key")

        if not api_key:
            raise HTTPException(status_code=400, detail="API key is required")

        if key_type not in HASHABLE_SETTINGS:
            raise HTTPException(status_code=400, detail="Invalid key type")

        # Get the stored hash
        hash_key = HASHABLE_SETTINGS[key_type]
        setting = await async_db.get_setting_by_key(hash_key)

        if not setting or not setting.get("value"):
            return {"valid": False, "message": "No API key configured"}

        stored_hash = setting["value"]

        # Verify the key
        is_valid = verify_api_key(api_key, stored_hash)

        return {
            "valid": is_valid,
            "message": "API key is valid" if is_valid else "API key is invalid",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify API key") from e
