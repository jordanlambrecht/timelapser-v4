# backend/app/models/settings.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class SettingBase(BaseModel):
    key: str = Field(..., min_length=1, max_length=255, description="Setting key")
    value: str = Field(..., description="Setting value")


class SettingCreate(SettingBase):
    """Model for creating a new setting"""

    pass


class SettingUpdate(BaseModel):
    """Model for updating a setting"""

    value: str = Field(..., description="Setting value")


class Setting(SettingBase):
    """Full setting model with all database fields"""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
