# backend/app/routers/weather_routers.py
"""
Weather Router - Dedicated endpoints for weather data and operations.

This router provides clean separation between weather settings (configuration)
and weather data (actual temperature, conditions, etc.).
"""

from fastapi import APIRouter, HTTPException, Response

from ..dependencies import WeatherManagerDep
from ..utils.cache_manager import generate_content_hash_etag
from ..utils.response_helpers import ResponseFormatter
from ..utils.router_helpers import handle_exceptions

router = APIRouter()


@router.get("/")
@handle_exceptions("get weather data")
async def get_current_weather(response: Response, weather_manager: WeatherManagerDep):
    """
    Get current weather data and status.

    Returns weather information with proper ETag caching to minimize
    unnecessary data transfers.
    """
    # Get current weather data from database
    weather_data = await weather_manager.get_current_weather_data()

    if not weather_data:
        return ResponseFormatter.success(
            message="No weather data available",
            data={
                "current_temp": None,
                "current_weather_description": "No data",
                "current_weather_icon": None,
                "last_updated": None,
                "enabled": False,
            },
        )

    # Set ETag for caching
    if weather_data:
        etag = generate_content_hash_etag(weather_data)
        response.headers["ETag"] = etag

    # Return the weather data directly since it's already formatted
    return ResponseFormatter.success(
        message="Weather data retrieved successfully",
        data=weather_data,
    )


@router.post("/refresh")
@handle_exceptions("refresh weather data")
async def refresh_weather_data(weather_manager: WeatherManagerDep):
    """
    Manually refresh weather data from the API.

    Requires weather integration to be enabled and properly configured.
    """
    # Delegate to weather service
    result = await weather_manager.manual_weather_refresh()

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    # Check if weather data is available
    if not result.weather_data:
        raise HTTPException(
            status_code=500, detail="Weather refresh completed but no data was returned"
        )

    # Return success response with fresh weather data
    weather_data = result.weather_data
    return ResponseFormatter.success(
        "Weather data refreshed successfully",
        data={
            "temperature": weather_data.temperature,
            "description": weather_data.description,
            "icon": weather_data.icon,
            "humidity": getattr(weather_data, "humidity", None),
            "wind_speed": getattr(weather_data, "wind_speed", None),
            "sunrise_timestamp": weather_data.sunrise_timestamp,
            "sunset_timestamp": weather_data.sunset_timestamp,
            "date_fetched": (
                weather_data.date_fetched.isoformat()
                if hasattr(weather_data.date_fetched, "isoformat")
                else str(weather_data.date_fetched)
            ),
        },
    )


@router.get("/settings")
@handle_exceptions("get weather settings")
async def get_weather_settings(response: Response, weather_manager: WeatherManagerDep):
    """
    Get weather-related configuration settings.

    Returns only weather configuration, not actual weather data.
    Use GET /weather for actual weather information.
    """
    # Get weather settings from weather service
    weather_settings = await weather_manager.get_weather_settings()

    # Generate ETag based on settings content
    etag = generate_content_hash_etag(weather_settings)
    response.headers["Cache-Control"] = (
        "public, max-age=900, s-maxage=900"  # 15 minutes
    )
    response.headers["ETag"] = etag

    return ResponseFormatter.success(
        "Weather settings retrieved successfully", data=weather_settings
    )


@router.get("/status")
@handle_exceptions("get weather status")
async def get_weather_status(weather_manager: WeatherManagerDep):
    """
    Get weather system status and health information.

    Returns information about weather system configuration,
    API connectivity, and data freshness.
    """
    # Get weather settings to build status
    weather_settings = await weather_manager.get_weather_settings()

    # Build status response from available data
    status = {
        "enabled": weather_settings.get("weather_integration_enabled", False),
        "api_key_configured": bool(weather_settings.get("openweather_api_key")),
        "location_configured": all(
            [
                weather_settings.get("weather_location_lat"),
                weather_settings.get("weather_location_lng"),
            ]
        ),
        "has_current_data": bool(weather_settings.get("current_temp")),
        "last_updated": weather_settings.get("weather_last_updated"),
    }

    return ResponseFormatter.success(
        message="Weather system status retrieved", data=status
    )
