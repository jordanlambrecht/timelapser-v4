"""
Typed response models for scheduler worker operations.

These models provide type-safe access to scheduler workflow results and status information,
enhancing error handling and providing operational clarity.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class SchedulerJobInfo:
    """Information about scheduler jobs."""

    total_jobs: int = 0
    active_jobs: int = 0
    paused_jobs: int = 0
    timelapse_jobs: int = 0
    standard_jobs: int = 0
    immediate_jobs: int = 0

    @property
    def is_active(self) -> bool:
        """Check if scheduler has active jobs."""
        return self.active_jobs > 0

    @property
    def job_distribution(self) -> Dict[str, int]:
        """Get job distribution breakdown."""
        return {
            "timelapse": self.timelapse_jobs,
            "standard": self.standard_jobs,
            "immediate": self.immediate_jobs,
        }


@dataclass
class SchedulerManagerStatus:
    """Status of scheduler managers."""

    immediate_job_manager_healthy: bool = False
    standard_job_manager_healthy: bool = False
    automation_evaluator_healthy: bool = False

    @property
    def all_managers_healthy(self) -> bool:
        """Check if all managers are healthy."""
        return (
            self.immediate_job_manager_healthy
            and self.standard_job_manager_healthy
            and self.automation_evaluator_healthy
        )

    @property
    def healthy_managers_count(self) -> int:
        """Count of healthy managers."""
        return sum(
            [
                self.immediate_job_manager_healthy,
                self.standard_job_manager_healthy,
                self.automation_evaluator_healthy,
            ]
        )


@dataclass
class SchedulerWorkerStatus:
    """Comprehensive scheduler worker status."""

    worker_type: str
    scheduler_running: bool = False
    job_info: Optional[SchedulerJobInfo] = None
    manager_status: Optional[SchedulerManagerStatus] = None
    settings_service_status: str = "unknown"
    scheduling_service_status: str = "unknown"
    capture_timing_enabled: bool = False
    automation_enabled: bool = False
    last_job_execution: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchedulerWorkerStatus":
        """Create SchedulerWorkerStatus from dictionary for backward compatibility."""
        job_info_data = data.get("job_info", {})
        job_info = SchedulerJobInfo(
            total_jobs=job_info_data.get("total_jobs", 0),
            active_jobs=job_info_data.get("active_jobs", 0),
            paused_jobs=job_info_data.get("paused_jobs", 0),
            timelapse_jobs=job_info_data.get("timelapse_jobs", 0),
            standard_jobs=job_info_data.get("standard_jobs", 0),
            immediate_jobs=job_info_data.get("immediate_jobs", 0),
        )

        manager_data = data.get("manager_status", {})
        manager_status = SchedulerManagerStatus(
            immediate_job_manager_healthy=manager_data.get(
                "immediate_job_manager_healthy", False
            ),
            standard_job_manager_healthy=manager_data.get(
                "standard_job_manager_healthy", False
            ),
            automation_evaluator_healthy=manager_data.get(
                "automation_evaluator_healthy", False
            ),
        )

        return cls(
            worker_type=data.get("worker_type", ""),
            scheduler_running=data.get("scheduler_running", False),
            job_info=job_info,
            manager_status=manager_status,
            settings_service_status=data.get("settings_service_status", "unknown"),
            scheduling_service_status=data.get("scheduling_service_status", "unknown"),
            capture_timing_enabled=data.get("capture_timing_enabled", False),
            automation_enabled=data.get("automation_enabled", False),
            last_job_execution=data.get("last_job_execution"),
        )

    @property
    def is_healthy(self) -> bool:
        """Check if scheduler worker is healthy."""
        return (
            self.scheduler_running and self.manager_status.all_managers_healthy
            if self.manager_status
            else False
            and self.settings_service_status == "healthy"
            and self.scheduling_service_status == "healthy"
        )

    @property
    def is_functional(self) -> bool:
        """Check if scheduler has basic functionality."""
        return self.scheduler_running and self.settings_service_status == "healthy"

    @property
    def workload_summary(self) -> str:
        """Get a summary of current workload."""
        if not self.job_info:
            return "No job information"

        if self.job_info.total_jobs == 0:
            return "No jobs scheduled"
        elif self.job_info.active_jobs == 0:
            return f"{self.job_info.total_jobs} jobs (all paused)"
        else:
            return f"{self.job_info.active_jobs}/{self.job_info.total_jobs} jobs active"

    @property
    def has_active_workload(self) -> bool:
        """Check if scheduler has active work to do."""
        return self.job_info.is_active if self.job_info else False
