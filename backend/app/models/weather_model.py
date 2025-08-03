# backend/app/models/weather_model.py
"""
Weather models for the new compartmentalized architecture.

This module defines models for:
- Weather data storage in weather_data table
- OpenWeather API integration
- Sun-based time window calculations
- Error tracking and API failure handling

Architecture:
- Worker fetches weather hourly from OpenWeather API
- Data stored in dedicated weather_data table
- Capture system uses cached weather data only
- Settings handle configuration, not data storage
"""

from datetime import date, datetime, time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class WeatherApiStatus(str, Enum):
    """Weather API status values"""

    VALID = "valid"
    INVALID = "invalid"
    FAILING = "failing"
    UNKNOWN = "unknown"


class WeatherDataRecord(BaseModel):
    """Weather data record from weather_data table"""

    id: Optional[int] = Field(None, description="Database record ID")
    weather_date_fetched: Optional[datetime] = Field(
        None, description="When weather was fetched"
    )
    current_temp: Optional[float] = Field(None, description="Temperature in Celsius")
    current_weather_icon: Optional[str] = Field(
        None, max_length=50, description="OpenWeather icon code"
    )
    current_weather_description: Optional[str] = Field(
        None, max_length=255, description="Weather description"
    )
    sunrise_timestamp: Optional[datetime] = Field(None, description="Sunrise datetime")
    sunset_timestamp: Optional[datetime] = Field(None, description="Sunset datetime")
    api_key_valid: Optional[bool] = Field(True, description="Whether API key is valid")
    api_failing: Optional[bool] = Field(False, description="Whether API is failing")
    error_response_code: Optional[int] = Field(
        None, description="HTTP error code if failed"
    )
    last_error_message: Optional[str] = Field(None, description="Last error message")
    consecutive_failures: Optional[int] = Field(
        0, description="Number of consecutive failures"
    )
    created_at: Optional[datetime] = Field(None, description="Record creation time")
    updated_at: Optional[datetime] = Field(None, description="Record update time")


class OpenWeatherApiData(BaseModel):
    """Raw weather data from OpenWeather API"""

    temperature: int = Field(..., description="Temperature in Celsius")
    icon: str = Field(..., max_length=50, description="OpenWeather icon code")
    description: str = Field(..., max_length=255, description="Weather description")
    sunrise_timestamp: int = Field(..., description="Sunrise Unix timestamp")
    sunset_timestamp: int = Field(..., description="Sunset Unix timestamp")
    date_fetched: date = Field(..., description="Date when weather was fetched")


class SunTimeWindow(BaseModel):
    """Sun-based time window for capture restrictions"""

    start_time: time = Field(..., description="Window start time")
    end_time: time = Field(..., description="Window end time")
    is_overnight: bool = Field(False, description="True if window spans midnight")

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v):
        """Ensure times are valid time objects"""
        if not isinstance(v, time):
            raise ValueError("Must be a time object")
        return v


class WeatherConfiguration(BaseModel):
    """Weather system configuration from settings"""

    weather_enabled: bool = Field(False, description="Enable weather data collection")
    sunrise_sunset_enabled: bool = Field(
        False, description="Enable sunrise/sunset time windows"
    )
    latitude: Optional[float] = Field(
        None, ge=-90, le=90, description="Location latitude"
    )
    longitude: Optional[float] = Field(
        None, ge=-180, le=180, description="Location longitude"
    )
    openweather_api_key: Optional[str] = Field(None, description="OpenWeather API key")
    sunrise_offset_minutes: int = Field(0, description="Minutes to offset sunrise")
    sunset_offset_minutes: int = Field(0, description="Minutes to offset sunset")
    timezone: str = Field(
        "UTC", description="Timezone for calculations"
    )  # Keep as literal for Pydantic default


class WeatherApiValidationRequest(BaseModel):
    """Request to validate OpenWeather API key"""

    api_key: str = Field(
        ..., min_length=1, description="OpenWeather API key to validate"
    )
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Test latitude")
    longitude: Optional[float] = Field(
        None, ge=-180, le=180, description="Test longitude"
    )


class WeatherApiValidationResponse(BaseModel):
    """Response from API key validation"""

    valid: bool = Field(..., description="Whether the API key is valid")
    message: str = Field(..., description="Validation result message")
    status: WeatherApiStatus = Field(..., description="API status")


class WeatherRefreshResult(BaseModel):
    """Result from weather data refresh operation"""

    success: bool = Field(..., description="Whether refresh was successful")
    message: str = Field(..., description="Refresh result message")
    weather_data: Optional[OpenWeatherApiData] = Field(
        None, description="Fetched weather data"
    )
    error_code: Optional[int] = Field(None, description="Error code if failed")


class WeatherSystemStatus(BaseModel):
    """Overall weather system status for monitoring"""

    enabled: bool = Field(..., description="Whether weather system is enabled")
    api_key_configured: bool = Field(..., description="Whether API key is configured")
    location_configured: bool = Field(..., description="Whether lat/lng is configured")
    last_successful_fetch: Optional[datetime] = Field(
        None, description="Last successful data fetch"
    )
    last_error: Optional[str] = Field(None, description="Last error message")
    consecutive_failures: int = Field(0, description="Number of consecutive failures")
    api_status: WeatherApiStatus = Field(..., description="Current API status")


# Legacy compatibility models for existing API endpoints
class LegacyWeatherData(BaseModel):
    """Legacy weather data format for backward compatibility"""

    temperature: Optional[int] = Field(None, description="Temperature in Celsius")
    icon: Optional[str] = Field(None, description="OpenWeather icon code")
    description: Optional[str] = Field(None, description="Weather description")
    date_fetched: Optional[date] = Field(
        None, description="Date when weather was fetched"
    )
    sunrise_timestamp: Optional[int] = Field(None, description="Sunrise Unix timestamp")
    sunset_timestamp: Optional[int] = Field(None, description="Sunset Unix timestamp")


class LegacyWeatherRefreshResponse(BaseModel):
    """Legacy weather refresh response for backward compatibility"""

    success: bool = Field(..., description="Whether refresh was successful")
    message: str = Field(..., description="Refresh result message")
    weather_data: Optional[LegacyWeatherData] = Field(
        None, description="Updated weather data"
    )
