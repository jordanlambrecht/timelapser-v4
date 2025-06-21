# backend/app/models/weather.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, time


class WeatherSettings(BaseModel):
    """Weather configuration settings"""
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Location latitude")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Location longitude")
    weather_enabled: bool = Field(False, description="Enable weather data collection")
    sunrise_sunset_enabled: bool = Field(False, description="Enable sunrise/sunset time windows globally")


class WeatherData(BaseModel):
    """Current weather data"""
    temperature: Optional[int] = Field(None, description="Temperature in Celsius")
    icon: Optional[str] = Field(None, description="OpenWeather icon code")
    description: Optional[str] = Field(None, description="Weather description")
    date_fetched: Optional[date] = Field(None, description="Date when weather was fetched")
    sunrise_timestamp: Optional[int] = Field(None, description="Sunrise Unix timestamp")
    sunset_timestamp: Optional[int] = Field(None, description="Sunset Unix timestamp")


class SunTimeWindow(BaseModel):
    """Sun-based time window"""
    start_time: time = Field(..., description="Window start time")
    end_time: time = Field(..., description="Window end time")
    is_overnight: bool = Field(False, description="True if window spans midnight")


class WeatherApiKeyValidation(BaseModel):
    """API key validation request"""
    api_key: str = Field(..., min_length=1, description="OpenWeather API key to validate")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Test latitude")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Test longitude")


class WeatherApiKeyValidationResponse(BaseModel):
    """API key validation response"""
    valid: bool = Field(..., description="Whether the API key is valid")
    message: str = Field(..., description="Validation result message")


class WeatherRefreshResponse(BaseModel):
    """Weather data refresh response"""
    success: bool = Field(..., description="Whether refresh was successful")
    message: str = Field(..., description="Refresh result message")
    weather_data: Optional[WeatherData] = Field(None, description="Updated weather data")


class TimeWindowMode(BaseModel):
    """Time window mode configuration"""
    mode: str = Field(..., description="Time window mode: 'none', 'time', or 'sun'")
    time_start: Optional[str] = Field(None, description="Start time for 'time' mode (HH:MM:SS)")
    time_end: Optional[str] = Field(None, description="End time for 'time' mode (HH:MM:SS)")
    sunrise_offset: Optional[int] = Field(None, description="Sunrise offset in minutes for 'sun' mode")
    sunset_offset: Optional[int] = Field(None, description="Sunset offset in minutes for 'sun' mode")
