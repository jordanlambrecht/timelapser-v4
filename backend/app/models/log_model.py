# backend/app/models/log_model.py
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..enums import LogEmoji, LoggerName, LogLevel, LogSource


class LogBase(BaseModel):
    level: LogLevel = Field(LogLevel.INFO, description="Log level")
    message: str = Field(..., description="Log message")

    camera_id: Optional[int] = Field(None, description="Associated camera ID")


class LogCreate(LogBase):
    """Model for creating a new log entry"""

    logger_name: Optional[LoggerName] = Field(
        LoggerName.SYSTEM, description="Logger name"
    )
    emoji: Optional[LogEmoji] = Field(
        None, description="Emoji representation of the log level"
    )
    source: Optional[LogSource] = Field(LogSource.SYSTEM, description="Log source")
    extra_data: Optional[Dict[str, Any]] = Field(
        None, description="Additional log data"
    )


class Log(LogBase):
    """Full log model with all database fields"""

    id: int
    timestamp: datetime
    logger_name: Optional[LoggerName] = None
    source: Optional[LogSource] = None
    extra_data: Optional[Dict[str, Any]] = None
    camera_name: Optional[str] = None  # From JOIN with cameras table

    model_config = ConfigDict(from_attributes=True)
