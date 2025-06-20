# backend/app/models/log.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime


class LogBase(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        ..., description="Log level"
    )
    message: str = Field(..., description="Log message")
    camera_id: Optional[int] = Field(None, description="Associated camera ID")


class LogCreate(LogBase):
    """Model for creating a new log entry"""

    pass


class Log(LogBase):
    """Full log model with all database fields"""

    id: int
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
