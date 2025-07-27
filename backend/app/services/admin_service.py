# backend/app/services/admin_service.py
"""
Admin Service - Business logic for administrative operations.

Role: Service layer for admin functionality
Responsibilities:
- Handle admin-specific business logic (job actions, health scoring)
- Coordinate between operations and workers
- Manage pagination and filtering for admin endpoints
- Provide admin-specific data aggregation

Architecture: Service Layer - contains business logic separated from HTTP layer
- Delegates data operations to operations classes
- Coordinates with worker services for job actions
- Provides consistent admin data formatting
"""

from typing import Dict, Any, List, Optional
from loguru import logger

from ..utils.time_utils import utc_now

from ..database.scheduled_job_operations import ScheduledJobOperations
from ..models.scheduled_job_model import ScheduledJobUpdate, ScheduledJobSummary
from ..models.health_model import HealthStatus
from ..enums import JobPriority, ScheduledJobStatus, ScheduledJobType
from ..utils.pagination_helpers import calculate_pagination_params


class AdminService:
    """
    Service for administrative operations and business logic.

    Handles business logic that was previously in admin routers,
    maintaining clean separation between HTTP layer and business logic.
    """

    def __init__(self, scheduled_job_ops: ScheduledJobOperations):
        """
        Initialize admin service.

        Args:
            scheduled_job_ops: Scheduled job operations instance
        """
        self.scheduled_job_ops = scheduled_job_ops

    async def get_paginated_jobs(
        self,
        page: int,
        limit: int,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        include_disabled: bool = False,
    ) -> Dict[str, Any]:
        """
        Get paginated list of scheduled jobs with filtering.

        Handles the business logic for filtering, pagination, and
        formatting of scheduled jobs for admin interface.

        Args:
            page: Page number (1-based)
            limit: Items per page
            job_type: Filter by job type
            status: Filter by status
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            include_disabled: Include disabled jobs

        Returns:
            Dictionary with paginated jobs and metadata
        """
        try:
            # Get filtered jobs from operations layer
            all_jobs = await self.scheduled_job_ops.get_jobs_filtered(
                job_type=job_type,
                status=status,
                entity_type=entity_type,
                entity_id=entity_id,
                include_disabled=include_disabled,
            )

            # Calculate pagination using helper
            total_count = len(all_jobs)
            pagination_params = calculate_pagination_params(page, limit, total_count)

            # Apply pagination
            start_idx = pagination_params["offset"]
            end_idx = start_idx + limit
            jobs_page = all_jobs[start_idx:end_idx]

            # Convert to summary format (concise)
            job_summaries = [
                ScheduledJobSummary(
                    job_id=job.job_id,
                    job_type=job.job_type,
                    entity_type=job.entity_type,
                    entity_id=job.entity_id,
                    status=job.status,
                    next_run_time=job.next_run_time,
                    last_run_time=job.last_run_time,
                    execution_count=job.execution_count,
                    success_rate=job.success_rate,
                    is_healthy=job.is_healthy,
                    last_error_message=job.last_error_message,
                )
                for job in jobs_page
            ]

            return {
                "jobs": job_summaries,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_count": total_count,
                    "total_pages": pagination_params["total_pages"],
                    "has_next": pagination_params["has_next"],
                    "has_previous": pagination_params["has_previous"],
                },
                "filters": {
                    "job_type": job_type,
                    "status": status,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "include_disabled": include_disabled,
                },
            }

        except Exception as e:
            logger.error(f"Error getting paginated jobs: {e}")
            raise

    async def execute_job_action(
        self,
        job_id: str,
        action: str,
        scheduler_worker=None,
    ) -> Dict[str, Any]:
        """
        Execute administrative actions on scheduled jobs.

        Handles the business logic for job state changes and
        manual triggering operations.

        Args:
            job_id: Job ID to act on
            action: Action to execute (pause, resume, disable, enable, trigger)
            scheduler_worker: Optional scheduler worker for triggering

        Returns:
            Dictionary with action results and updated job state

        Raises:
            ValueError: If action is invalid or job not found
            RuntimeError: If action execution fails
        """
        try:
            # Verify job exists
            job = await self.scheduled_job_ops.get_job_by_id(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            result_message = ""

            if action in {"pause", "disable"}:
                new_status = (
                    ScheduledJobStatus.PAUSED
                    if action == "pause"
                    else ScheduledJobStatus.DISABLED
                )
                update_data = ScheduledJobUpdate(status=new_status)
                success = await self.scheduled_job_ops.update_job(job_id, update_data)

                if success:
                    result_message = f"Job {job_id} {action}d successfully"
                else:
                    raise RuntimeError(f"Failed to {action} job")

            elif action in {"resume", "enable"}:
                update_data = ScheduledJobUpdate(status=ScheduledJobStatus.ACTIVE)
                success = await self.scheduled_job_ops.update_job(job_id, update_data)

                if success:
                    result_message = f"Job {job_id} {action}d successfully"
                else:
                    raise RuntimeError(f"Failed to {action} job")

            elif action == "trigger":
                if not scheduler_worker:
                    raise RuntimeError(
                        "Scheduler worker not available for manual triggering"
                    )

                # Handle manual triggering based on job type
                result_message = await self._handle_manual_trigger(
                    job, scheduler_worker
                )

            else:
                raise ValueError(f"Invalid action '{action}'")

            # Get updated job state
            updated_job = await self.scheduled_job_ops.get_job_by_id(job_id)

            return {
                "job": updated_job,
                "message": result_message,
                "action": action,
            }

        except Exception as e:
            logger.error(f"Error executing job action {action} on {job_id}: {e}")
            raise

    async def _handle_manual_trigger(self, job, scheduler_worker) -> str:
        """
        Handle manual triggering of jobs based on their type.

        Args:
            job: Job object to trigger
            scheduler_worker: Scheduler worker instance

        Returns:
            Success message string

        Raises:
            RuntimeError: If triggering fails
            ValueError: If job type doesn't support manual triggering
        """
        if job.job_type == ScheduledJobType.TIMELAPSE_CAPTURE and job.entity_id:
            # For timelapse jobs, trigger immediate capture
            success = await scheduler_worker.schedule_immediate_capture(
                camera_id=0,  # Will be extracted from timelapse
                timelapse_id=job.entity_id,
                priority=JobPriority.HIGH,
            )

            if success:
                return f"Triggered immediate capture for timelapse {job.entity_id}"
            else:
                raise RuntimeError("Failed to trigger immediate capture")
        else:
            raise ValueError(
                f"Manual triggering not supported for job type '{job.job_type}'"
            )

    async def execute_bulk_job_action(
        self,
        job_ids: List[str],
        action: str,
    ) -> Dict[str, Any]:
        """
        Execute bulk actions on multiple scheduled jobs.

        Args:
            job_ids: List of job IDs to act on
            action: Bulk action to execute

        Returns:
            Dictionary with bulk operation results

        Raises:
            ValueError: If action is invalid or no job IDs provided
        """
        try:
            if not job_ids:
                raise ValueError("No job IDs provided")

            # Determine new status based on action (simplified)
            match action:
                case "pause":
                    new_status = ScheduledJobStatus.PAUSED
                case "resume" | "enable":
                    new_status = ScheduledJobStatus.ACTIVE
                case "disable":
                    new_status = ScheduledJobStatus.DISABLED
                case _:
                    raise ValueError(f"Invalid bulk action '{action}'")

            # Execute bulk update via operations layer
            results = await self.scheduled_job_ops.bulk_update_job_status(
                job_ids, new_status
            )

            # Calculate success metrics
            success_count = sum(1 for r in results.values() if r)
            failed_jobs = [job_id for job_id, success in results.items() if not success]

            return {
                "action": action,
                "total_jobs": len(job_ids),
                "successful": success_count,
                "failed": len(failed_jobs),
                "failed_job_ids": failed_jobs,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Error executing bulk action {action}: {e}")
            raise

    def calculate_job_health_score(self, stats) -> float:
        """
        Calculate job health score from statistics.

        Moved from router to service layer for proper business logic separation.

        Args:
            stats: Job statistics object

        Returns:
            Health score as float (0-100)
        """
        try:
            # Use existing health score if available
            if stats.health_score is not None:
                return float(stats.health_score)

            # Fallback calculation if no health score in stats
            # This would be implemented based on business requirements
            return 0.0

        except Exception as e:
            logger.warning(f"Error calculating job health score: {e}")
            return 0.0

    async def get_admin_health_assessment(
        self,
        health_service,
        scheduler_worker=None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive admin health assessment.

        Centralizes admin health logic that was previously in the router.

        Args:
            health_service: HealthService instance
            scheduler_worker: Optional scheduler worker instance

        Returns:
            Dictionary with comprehensive admin health data
        """

        try:
            # Get comprehensive health check from HealthService
            try:
                system_health = await health_service.get_detailed_health()
                system_healthy = system_health.status == HealthStatus.HEALTHY
            except Exception as e:
                logger.error(f"Failed to get system health: {e}")
                system_health = None
                system_healthy = False

            # Check scheduled job statistics with health scoring
            try:
                stats = await self.scheduled_job_ops.get_job_statistics()
                job_stats_healthy = True
                job_error = None

                # Calculate job health score using business logic
                job_health_score = self.calculate_job_health_score(stats)
                job_stats_healthy = (
                    job_health_score >= 70.0
                )  # 70% threshold for healthy
            except Exception as e:
                job_stats_healthy = False
                job_error = str(e)
                stats = None
                job_health_score = 0

            # Check scheduler worker status
            scheduler_healthy = scheduler_worker is not None
            scheduler_status = None
            if scheduler_worker:
                try:
                    scheduler_status = scheduler_worker.get_status()
                    scheduler_healthy = scheduler_status.get(
                        "scheduler_system_healthy", False
                    )
                except Exception as e:
                    scheduler_healthy = False
                    scheduler_status = {"error": str(e)}

            # Overall admin health assessment
            admin_healthy = system_healthy and job_stats_healthy and scheduler_healthy

            return {
                "timestamp": utc_now(),
                "admin_healthy": admin_healthy,
                "system_health": (
                    system_health.model_dump()
                    if system_health
                    else {"error": "Health check failed"}
                ),
                "scheduled_jobs": {
                    "healthy": job_stats_healthy,
                    "health_score": job_health_score,
                    "error": job_error,
                    "statistics": stats,
                },
                "scheduler": {
                    "healthy": scheduler_healthy,
                    "available": scheduler_worker is not None,
                    "status": scheduler_status,
                },
                "health_thresholds": {
                    "job_health_minimum": 70.0,
                    "description": "Job health score must be >= 70% for healthy status",
                },
            }

        except Exception as e:
            logger.error(f"Error getting admin health assessment: {e}")
            raise
