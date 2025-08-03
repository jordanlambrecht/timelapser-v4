# backend/app/models/settings.py

from datetime import datetime
from typing import Dict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SettingBase(BaseModel):
    key: str = Field(..., min_length=1, max_length=255, description="Setting key")
    value: str = Field(..., description="Setting value")


class SettingCreate(SettingBase):
    """Model for creating a new setting"""


class SettingUpdate(BaseModel):
    """Model for updating a setting"""

    value: str = Field(..., description="Setting value")


class BulkSettingsUpdate(BaseModel):
    """Model for updating multiple settings in bulk"""

    settings: Dict[str, str] = Field(
        ..., description="Dictionary of setting key-value pairs to update", min_length=1
    )


class WeatherSettingUpdate(BaseModel):
    """Model for updating weather-related settings"""

    key: str = Field(..., description="Weather setting key")
    value: str = Field(..., description="Weather setting value")

    @field_validator("key")
    @classmethod
    def validate_weather_key(cls, v):
        """Validate weather setting key"""
        allowed_keys = [
            "weather_enabled",
            "weather_api_key",
            "weather_location",
            "weather_units",
        ]
        if v not in allowed_keys:
            raise ValueError(f"Invalid weather setting key. Allowed: {allowed_keys}")
        return v


class Setting(SettingBase):
    """Full setting model with all database fields"""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
