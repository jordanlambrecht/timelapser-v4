# backend/app/models/health_model.py
"""
Health Check Pydantic Models

Models for health check endpoints providing proper validation and documentation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class HealthStatus(str, Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class BaseHealthModel(BaseModel):
    """Base model for all health-related models with common configuration"""
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )


class BasicHealthCheck(BaseHealthModel):
    """Basic health check response model"""
    status: HealthStatus = Field(description="Overall health status")
    timestamp: datetime = Field(description="Health check timestamp (timezone-aware)")
    service: str = Field(description="Service name")
    version: str = Field(description="Application version")


class ComponentHealth(BaseHealthModel):
    """Individual component health status"""
    status: HealthStatus = Field(description="Component health status")
    message: str = Field(description="Health status message")
    response_time_seconds: Optional[float] = Field(None, description="Response time in seconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional health details")


class DatabaseHealth(BaseHealthModel):
    """Database health status model"""
    status: HealthStatus = Field(description="Database health status")
    async_latency_ms: Optional[float] = Field(None, description="Async connection latency")
    sync_latency_ms: Optional[float] = Field(None, description="Sync connection latency")
    pool_status: Optional[Dict[str, Any]] = Field(None, description="Connection pool status")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class FilesystemHealth(BaseHealthModel):
    """Filesystem health status model"""
    status: HealthStatus = Field(description="Filesystem health status")
    data_directory_accessible: bool = Field(description="Data directory accessibility")
    write_permissions: bool = Field(description="Write permissions available")
    disk_usage_percent: Optional[float] = Field(None, description="Disk usage percentage")
    free_space_gb: Optional[float] = Field(None, description="Free space in GB")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class SystemMetrics(BaseHealthModel):
    """System performance metrics model"""
    cpu_percent: float = Field(description="CPU usage percentage")
    memory_percent: float = Field(description="Memory usage percentage")
    memory_total_gb: float = Field(description="Total memory in GB")
    memory_available_gb: float = Field(description="Available memory in GB")
    disk_usage_percent: Optional[float] = Field(None, description="Disk usage percentage")
    load_average: Optional[Dict[str, float]] = Field(None, description="System load average")


class ApplicationMetrics(BaseHealthModel):
    """Application-specific metrics model"""
    total_cameras: int = Field(description="Total number of cameras")
    active_cameras: int = Field(description="Number of active cameras")
    running_timelapses: int = Field(description="Number of running timelapses")
    images_last_24h: int = Field(description="Images captured in last 24 hours")
    pending_video_jobs: int = Field(description="Pending video generation jobs")
    processing_video_jobs: int = Field(description="Processing video generation jobs")


class DetailedHealthCheck(BaseHealthModel):
    """Comprehensive health check response model"""
    status: HealthStatus = Field(description="Overall health status")
    timestamp: datetime = Field(description="Health check timestamp (timezone-aware)")
    service: str = Field(description="Service name")
    version: str = Field(description="Application version")
    uptime_seconds: float = Field(description="Service uptime in seconds")
    components: Dict[str, ComponentHealth] = Field(description="Component health statuses")
    warnings: Optional[List[str]] = Field(None, description="Health warnings")


class HealthResponse(BaseHealthModel):
    """Standardized health response wrapper"""
    success: bool = Field(description="Whether health check succeeded")
    message: str = Field(description="Health check message")
    data: Optional[Dict[str, Any]] = Field(None, description="Health check data")
    timestamp: datetime = Field(description="Response timestamp (timezone-aware)")
