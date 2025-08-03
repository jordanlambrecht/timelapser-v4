# backend/app/models/scheduled_job_model.py
"""
Scheduled Job Models - Pydantic models for scheduled job management.

Models for the hybrid scheduling approach where APScheduler remains the
execution engine but the database provides visibility, audit trails,
and recovery capabilities.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScheduledJobBase(BaseModel):
    """Base model for scheduled job data."""

    job_id: str = Field(
        ..., description="Unique job identifier matching APScheduler job_id"
    )
    job_type: str = Field(
        ..., description="Type of job (timelapse_capture, health_check, etc.)"
    )
    schedule_pattern: Optional[str] = Field(
        None, description="Cron expression or interval description"
    )
    interval_seconds: Optional[int] = Field(
        None, description="Interval in seconds for interval-based jobs"
    )
    entity_id: Optional[int] = Field(
        None, description="ID of related entity (camera_id, timelapse_id, etc.)"
    )
    entity_type: Optional[str] = Field(
        None, description="Type of related entity (camera, timelapse, system)"
    )
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Job-specific configuration"
    )
    status: str = Field(
        default="active", description="Job status: active, paused, disabled, error"
    )


class ScheduledJobCreate(ScheduledJobBase):
    """Model for creating a new scheduled job."""

    next_run_time: Optional[datetime] = Field(
        None, description="Next scheduled execution time"
    )


class ScheduledJobUpdate(BaseModel):
    """Model for updating an existing scheduled job."""

    schedule_pattern: Optional[str] = None
    interval_seconds: Optional[int] = None
    next_run_time: Optional[datetime] = None
    entity_id: Optional[int] = None
    entity_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class ScheduledJob(ScheduledJobBase):
    """Complete scheduled job model with all database fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    next_run_time: Optional[datetime] = None
    last_run_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.execution_count == 0:
            return 0.0
        return (self.success_count / self.execution_count) * 100

    @property
    def is_healthy(self) -> bool:
        """Check if the job is in a healthy state."""
        return (
            self.status == "active"
            and (self.execution_count == 0 or self.success_rate >= 50.0)
            and self.last_error_message is None
        )

    @property
    def has_recent_execution(self, minutes: int = 60) -> bool:
        """Check if the job has executed recently."""
        if not self.last_run_time:
            return False

        from ..utils.time_utils import utc_now

        time_diff = utc_now() - self.last_run_time
        return time_diff.total_seconds() < (minutes * 60)


class ScheduledJobExecutionBase(BaseModel):
    """Base model for job execution data."""

    job_id: str = Field(..., description="Job identifier")
    execution_start: datetime = Field(..., description="Execution start time")
    status: str = Field(
        ..., description="Execution status: running, completed, failed, timeout"
    )


class ScheduledJobExecutionCreate(ScheduledJobExecutionBase):
    """Model for creating a job execution log entry."""

    execution_end: Optional[datetime] = None
    result_message: Optional[str] = None
    error_message: Optional[str] = None
    execution_duration_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ScheduledJobExecution(ScheduledJobExecutionBase):
    """Complete job execution model with all database fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    scheduled_job_id: int
    execution_end: Optional[datetime] = None
    result_message: Optional[str] = None
    error_message: Optional[str] = None
    execution_duration_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get execution duration in seconds."""
        if self.execution_duration_ms is not None:
            return self.execution_duration_ms / 1000.0
        return None

    @property
    def was_successful(self) -> bool:
        """Check if the execution was successful."""
        return self.status == "completed" and self.error_message is None


class ScheduledJobStatistics(BaseModel):
    """Statistics about scheduled jobs."""

    total_jobs: int = 0
    active_jobs: int = 0
    paused_jobs: int = 0
    disabled_jobs: int = 0
    error_jobs: int = 0
    unique_job_types: int = 0
    total_executions: int = 0
    total_successes: int = 0
    total_failures: int = 0

    @property
    def overall_success_rate(self) -> float:
        """Calculate overall success rate as a percentage."""
        if self.total_executions == 0:
            return 0.0
        return (self.total_successes / self.total_executions) * 100

    @property
    def health_score(self) -> float:
        """Calculate a health score based on various metrics."""
        if self.total_jobs == 0:
            return 100.0

        # Factors that contribute to health:
        # - Percentage of active jobs
        # - Overall success rate
        # - Low error job percentage

        active_percentage = (self.active_jobs / self.total_jobs) * 100
        error_percentage = (self.error_jobs / self.total_jobs) * 100
        success_rate = self.overall_success_rate

        # Weighted health score
        health_score = (
            active_percentage * 0.4  # 40% weight for active jobs
            + success_rate * 0.5  # 50% weight for success rate
            + max(0, 100 - error_percentage * 2) * 0.1  # 10% weight for low errors
        )

        return min(100.0, max(0.0, health_score))


class ScheduledJobSummary(BaseModel):
    """Summary view of a scheduled job for lists and dashboards."""

    job_id: str
    job_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    status: str
    next_run_time: Optional[datetime] = None
    last_run_time: Optional[datetime] = None
    execution_count: int = 0
    success_rate: float = 0.0
    is_healthy: bool = True
    last_error_message: Optional[str] = None
