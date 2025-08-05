# backend/app/services/scheduler_workflow_service.py
"""
Scheduler workflow service for Timelapser v4.

Provides Service Layer Boundary Pattern compliance for scheduler operations.
Converts raw data to typed objects at the service boundary.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from ..enums import LoggerName, WorkerType
from ..models.health_model import HealthStatus
from ..services.logger import get_service_logger
from ..workers.models.scheduler_responses import (
    SchedulerJobInfo,
    SchedulerManagerStatus,
    SchedulerWorkerStatus,
)

scheduler_service_logger = get_service_logger(LoggerName.SYSTEM)


class SchedulerWorkflowService:
    """
    Service layer for scheduler operations.

    Converts raw service data to typed objects at the service boundary,
    following the Service Layer Boundary Pattern.
    """

    def __init__(self):
        """Initialize scheduler workflow service."""
        pass

    def get_worker_status(
        self,
        scheduler: Any,
        job_info: Dict[str, Any],
        manager_status: Dict[str, bool],
        settings_service: Any,
        scheduling_service: Any,
        capture_timing_enabled: bool = False,
        automation_enabled: bool = False,
        last_job_execution: Optional[datetime] = None,
    ) -> SchedulerWorkerStatus:
        """
        Convert raw service status to typed SchedulerWorkerStatus at service boundary.

        Args:
            scheduler: APScheduler instance
            job_info: Job information dictionary
            manager_status: Manager health status dictionary
            settings_service: Settings service instance
            scheduling_service: Scheduling service instance
            capture_timing_enabled: Whether capture timing is enabled
            automation_enabled: Whether automation is enabled
            last_job_execution: Last job execution timestamp

        Returns:
            SchedulerWorkerStatus: Typed status object for clean worker access
        """
        # Convert service availability to typed status using .value for explicit access
        scheduler_running = scheduler.running if scheduler else False
        settings_status = (
            HealthStatus.HEALTHY.value
            if settings_service
            else HealthStatus.UNREACHABLE.value
        )
        scheduling_status = (
            HealthStatus.HEALTHY.value
            if scheduling_service
            else HealthStatus.UNREACHABLE.value
        )

        # Create typed job info object
        job_info_typed = SchedulerJobInfo(
            total_jobs=job_info.get("total_jobs", 0),
            active_jobs=job_info.get("active_jobs", 0),
            paused_jobs=job_info.get("paused_jobs", 0),
            timelapse_jobs=job_info.get("timelapse_jobs", 0),
            standard_jobs=job_info.get("standard_jobs", 0),
            immediate_jobs=job_info.get("immediate_jobs", 0),
        )

        # Create typed manager status object
        manager_status_typed = SchedulerManagerStatus(
            immediate_job_manager_healthy=manager_status.get(
                "immediate_job_manager_healthy", False
            ),
            standard_job_manager_healthy=manager_status.get(
                "standard_job_manager_healthy", False
            ),
            automation_evaluator_healthy=manager_status.get(
                "automation_evaluator_healthy", False
            ),
        )

        # Return typed object at service boundary
        return SchedulerWorkerStatus(
            worker_type=WorkerType.SCHEDULER_WORKER.value,
            scheduler_running=scheduler_running,
            job_info=job_info_typed,
            manager_status=manager_status_typed,
            settings_service_status=settings_status,
            scheduling_service_status=scheduling_status,
            capture_timing_enabled=capture_timing_enabled,
            automation_enabled=automation_enabled,
            last_job_execution=last_job_execution,
        )
