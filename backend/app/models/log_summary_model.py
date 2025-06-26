# backend/app/models/log_summary_model.py
"""
Pydantic models for log summary and statistics data.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LogSourceModel(BaseModel):
    """Model for log source statistics"""
    source: str
    log_count: int
    last_log_at: Optional[datetime]
    error_count: int
    warning_count: int


class LogLevelModel(BaseModel):
    """Model for log level statistics"""
    level: str
    log_count: int
    count_last_24h: int


class LogSummaryModel(BaseModel):
    """Model for log summary statistics"""
    total_logs: int
    critical_count: int
    error_count: int
    warning_count: int
    info_count: int
    debug_count: int
    unique_sources: int
    unique_cameras: int
    first_log_at: Optional[datetime]
    last_log_at: Optional[datetime]


class ErrorCountBySourceModel(BaseModel):
    """Model for error count by source statistics"""
    source: str
    error_count: int
    critical_count: int
    total_count: int
    last_error_at: Optional[datetime]
