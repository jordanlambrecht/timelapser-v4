# backend/app/models/log_model.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal, Dict, Any
from datetime import datetime


class LogBase(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        ..., description="Log level"
    )
    message: str = Field(..., description="Log message")
    camera_id: Optional[int] = Field(None, description="Associated camera ID")


class LogCreate(LogBase):
    """Model for creating a new log entry"""
    logger_name: Optional[str] = Field("system", description="Logger name")
    source: Optional[str] = Field("system", description="Log source")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="Additional log data")


class Log(LogBase):
    """Full log model with all database fields"""
    id: int
    timestamp: datetime
    logger_name: Optional[str] = None
    source: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    camera_name: Optional[str] = None  # From JOIN with cameras table

    model_config = ConfigDict(from_attributes=True)
