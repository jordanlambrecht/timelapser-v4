# backend/app/routers/settings.py
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from loguru import logger
from datetime import date

from ..database import async_db
from ..models import Setting, SettingCreate, SettingUpdate
from ..models.weather import (
    WeatherSettings, WeatherData, WeatherApiKeyValidation, 
    WeatherApiKeyValidationResponse, WeatherRefreshResponse, SunTimeWindow
)
from ..hashing import hash_api_key, mask_api_key, verify_api_key

router = APIRouter()

# Settings that should be hashed for security
# NOTE: For development, we store API keys in plain text
# In production, implement proper encryption/decryption
HASHABLE_SETTINGS = {}  # Disabled for development

# Settings that should be masked when returned
MASKABLE_SETTINGS = {"openweather_api_key"}


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


# Weather-related endpoints - MUST be before /{key} route

@router.get("/weather", response_model=WeatherSettings)
async def get_weather_settings():
    """Get weather configuration settings"""
    try:
        settings_dict = await async_db.get_settings_dict()
        
        return WeatherSettings(
            latitude=float(settings_dict.get('latitude', 0)) if settings_dict.get('latitude') else None,
            longitude=float(settings_dict.get('longitude', 0)) if settings_dict.get('longitude') else None,
            weather_enabled=settings_dict.get('weather_enabled', 'false').lower() == 'true',
            sunrise_sunset_enabled=settings_dict.get('sunrise_sunset_enabled', 'false').lower() == 'true'
        )
    except Exception as e:
        logger.error(f"Error fetching weather settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch weather settings") from e


@router.put("/weather", response_model=WeatherSettings)
async def update_weather_settings(settings: WeatherSettings):
    """Update weather configuration settings"""
    try:
        # Update all weather settings
        updates = {
            'latitude': str(settings.latitude) if settings.latitude is not None else '',
            'longitude': str(settings.longitude) if settings.longitude is not None else '',
            'weather_enabled': str(settings.weather_enabled).lower(),
            'sunrise_sunset_enabled': str(settings.sunrise_sunset_enabled).lower()
        }
        
        for key, value in updates.items():
            await async_db.create_or_update_setting(key, value)
        
        logger.info(f"Updated weather settings: enabled={settings.weather_enabled}, sun_mode={settings.sunrise_sunset_enabled}")
        return settings
        
    except Exception as e:
        logger.error(f"Error updating weather settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update weather settings") from e


@router.get("/weather/data", response_model=WeatherData)
async def get_weather_data():
    """Get current cached weather data"""
    try:
        settings_dict = await async_db.get_settings_dict()
        
        # Parse date if present
        date_fetched = None
        if settings_dict.get('weather_date_fetched'):
            try:
                date_fetched = date.fromisoformat(settings_dict['weather_date_fetched'])
            except ValueError:
                pass
        
        return WeatherData(
            temperature=int(settings_dict.get('current_temp', 0)) if settings_dict.get('current_temp') else None,
            icon=settings_dict.get('current_weather_icon', '') or None,
            description=settings_dict.get('current_weather_description', '') or None,
            date_fetched=date_fetched,
            sunrise_timestamp=int(settings_dict.get('sunrise_timestamp', 0)) if settings_dict.get('sunrise_timestamp') else None,
            sunset_timestamp=int(settings_dict.get('sunset_timestamp', 0)) if settings_dict.get('sunset_timestamp') else None
        )
        
    except Exception as e:
        logger.error(f"Error fetching weather data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch weather data") from e


@router.post("/weather/validate-api-key", response_model=WeatherApiKeyValidationResponse)
async def validate_weather_api_key(validation: WeatherApiKeyValidation):
    """Validate OpenWeather API key"""
    try:
        # Import here to avoid circular imports
        from weather.service import OpenWeatherService
        
        # Use provided coordinates or get from settings
        latitude = validation.latitude
        longitude = validation.longitude
        
        if latitude is None or longitude is None:
            settings_dict = await async_db.get_settings_dict()
            latitude = float(settings_dict.get('latitude', 0)) if settings_dict.get('latitude') else None
            longitude = float(settings_dict.get('longitude', 0)) if settings_dict.get('longitude') else None
            
        if latitude is None or longitude is None:
            return WeatherApiKeyValidationResponse(
                valid=False,
                message="Location coordinates required for validation"
            )
        
        service = OpenWeatherService(
            api_key=validation.api_key,
            latitude=latitude,
            longitude=longitude
        )
        
        is_valid, message = service.validate_api_key()
        
        return WeatherApiKeyValidationResponse(
            valid=is_valid,
            message=message
        )
        
    except Exception as e:
        logger.error(f"Error validating weather API key: {e}")
        return WeatherApiKeyValidationResponse(
            valid=False,
            message=f"Validation error: {str(e)}"
        )


@router.post("/weather/refresh", response_model=WeatherRefreshResponse)
async def refresh_weather_data():
    """Manually refresh weather data from API"""
    try:
        # Import here to avoid circular imports
        from weather.service import WeatherManager
        
        # Get API key
        api_key_setting = await async_db.get_setting_by_key('openweather_api_key')
        if not api_key_setting or not api_key_setting.get('value'):
            return WeatherRefreshResponse(
                success=False,
                message="OpenWeather API key not configured",
                weather_data=None
            )
        
        # Use the plain text API key directly (development mode)
        api_key = api_key_setting['value']
        
        # Create weather manager and refresh data
        weather_manager = WeatherManager(async_db)
        weather_data = await weather_manager.refresh_weather_if_needed(api_key)
        
        if weather_data:
            return WeatherRefreshResponse(
                success=True,
                message="Weather data refreshed successfully",
                weather_data=WeatherData(
                    temperature=weather_data.temperature,
                    icon=weather_data.icon,
                    description=weather_data.description,
                    date_fetched=weather_data.date_fetched,
                    sunrise_timestamp=weather_data.sunrise_timestamp,
                    sunset_timestamp=weather_data.sunset_timestamp
                )
            )
        else:
            return WeatherRefreshResponse(
                success=False,
                message="Failed to fetch weather data from API",
                weather_data=None
            )
            
    except Exception as e:
        logger.error(f"Error refreshing weather data: {e}")
        return WeatherRefreshResponse(
            success=False,
            message=f"Refresh error: {str(e)}",
            weather_data=None
        )


@router.get("/weather/sun-window", response_model=SunTimeWindow)
async def get_current_sun_window():
    """Get current sun-based time window"""
    try:
        # Import here to avoid circular imports
        from weather.service import WeatherManager
        
        weather_manager = WeatherManager(async_db)
        time_window = await weather_manager.get_current_sun_window()
        
        if not time_window:
            raise HTTPException(
                status_code=404, 
                detail="Sun-based time window not available (check weather settings and data)"
            )
        
        return SunTimeWindow(
            start_time=time_window.start_time,
            end_time=time_window.end_time,
            is_overnight=time_window.is_overnight
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sun window: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate sun window") from e


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

        # Handle API key hashing - DISABLED FOR DEVELOPMENT
        # Always store keys as plain text for development
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
