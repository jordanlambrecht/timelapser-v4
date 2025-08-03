# backend/app/routers/admin_routers.py
"""
Admin HTTP endpoints for managing scheduled jobs.

Role: Administrative interface for scheduled job management
Responsibilities: View, control, and monitor all scheduled jobs in the system
Interactions: Uses ScheduledJobOperations and SchedulerWorker for job management

Features:
- List all scheduled jobs with filtering and pagination
- View detailed job information and execution history
- Pause/resume/disable individual jobs
- View system-wide job statistics and health metrics
- Manual job execution triggers
- Bulk operations on multiple jobs

Architecture: API Layer - delegates all business logic to services
- HTTP validation and error handling only
- No SSE broadcasting (handled by service layer)
- No business logic (delegated to operations/services)
- Follows same pattern as other routers
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query

from app.dependencies import (
    AdminServiceDep,
    ScheduledJobOperationsDep,
    get_health_service,
    get_scheduler_worker,
)
from app.enums import ScheduledJobStatus, ScheduledJobType

from app.models.scheduled_job_model import (
    ScheduledJobUpdate,
)
from app.utils.response_helpers import ResponseFormatter
from app.utils.router_helpers import handle_exceptions
from app.utils.time_utils import utc_now

router = APIRouter(tags=["admin"], prefix="/admin")

# Use enum values for validation
VALID_SCHEDULED_JOB_STATUSES = {status.value for status in ScheduledJobStatus}
VALID_JOB_TYPES = {job_type.value for job_type in ScheduledJobType}


def _validate_status(status: str) -> None:
    """Validate scheduled job status value."""
    if status not in VALID_SCHEDULED_JOB_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Valid statuses: {', '.join(sorted(VALID_SCHEDULED_JOB_STATUSES))}",
        )


def _validate_job_type(job_type: str) -> None:
    """Validate job type value."""
    if job_type not in VALID_JOB_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid job type '{job_type}'. Valid types: {', '.join(sorted(VALID_JOB_TYPES))}",
        )


@router.get("/jobs", response_model=Dict[str, Any])
@handle_exceptions("list scheduled jobs")
async def list_scheduled_jobs(
    admin_service: AdminServiceDep,
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    include_disabled: bool = Query(False, description="Include disabled jobs"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
) -> Dict[str, Any]:
    """
    List all scheduled jobs with filtering and pagination.

    Returns a paginated list of scheduled jobs with summary information.
    Use the detailed endpoint to get full job information.
    """

    # Validate input parameters
    if job_type is not None:
        _validate_job_type(job_type)
    if status is not None:
        _validate_status(status)

    # Use admin service for business logic
    result = await admin_service.get_paginated_jobs(
        page=page,
        limit=limit,
        job_type=job_type,
        status=status,
        entity_type=entity_type,
        entity_id=entity_id,
        include_disabled=include_disabled,
    )

    return ResponseFormatter.success(
        data=result,
        message=f"Retrieved {len(result['jobs'])} scheduled jobs",
    )


@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
@handle_exceptions("get scheduled job details")
async def get_scheduled_job_details(
    scheduled_job_ops: ScheduledJobOperationsDep,
    job_id: str = Path(..., description="Job ID to retrieve"),
) -> Dict[str, Any]:
    """
    Get detailed information about a specific scheduled job.

    Includes full job configuration, execution history, and current status.
    """

    # Get job details
    job = await scheduled_job_ops.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Get recent execution history
    executions = await scheduled_job_ops.get_job_executions(job_id, limit=10)

    # Get scheduler status (if available)
    scheduler_worker = get_scheduler_worker()
    scheduler_status = None
    if scheduler_worker:
        job_info = scheduler_worker.get_job_info()
        scheduler_status = {
            "is_registered": job_id in job_info.get("job_ids", []),
            "scheduler_running": job_info.get("scheduler_running", False),
            "total_scheduler_jobs": job_info.get("total_jobs", 0),
        }

    return ResponseFormatter.success(
        data={
            "job": job,
            "recent_executions": executions,
            "scheduler_status": scheduler_status,
        },
        message=f"Retrieved details for job {job_id}",
    )


@router.get("/jobs/{job_id}/executions", response_model=Dict[str, Any])
@handle_exceptions("get job execution history")
async def get_job_execution_history(
    scheduled_job_ops: ScheduledJobOperationsDep,
    job_id: str = Path(..., description="Job ID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
) -> Dict[str, Any]:
    """
    Get execution history for a specific job with pagination.
    """

    # Verify job exists
    job = await scheduled_job_ops.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Get paginated executions
    offset = (page - 1) * limit
    executions = await scheduled_job_ops.get_job_executions(
        job_id, limit=limit, offset=offset
    )

    # Get total count for pagination
    total_count = await scheduled_job_ops.get_job_execution_count(job_id)

    return ResponseFormatter.success(
        data={
            "executions": executions,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_count": total_count,
                "total_pages": (total_count + limit - 1) // limit,
                "has_next": offset + limit < total_count,
                "has_previous": page > 1,
            },
        },
        message=f"Retrieved {len(executions)} execution records for job {job_id}",
    )


@router.get("/statistics", response_model=Dict[str, Any])
@handle_exceptions("get job statistics")
async def get_job_statistics(
    scheduled_job_ops: ScheduledJobOperationsDep,
) -> Dict[str, Any]:
    """
    Get comprehensive statistics about all scheduled jobs.

    Includes counts by status, success rates, health metrics, and more.
    """

    # Get statistics
    stats = await scheduled_job_ops.get_job_statistics()

    # Get scheduler status
    scheduler_worker = get_scheduler_worker()
    scheduler_info = None
    if scheduler_worker:
        scheduler_info = scheduler_worker.get_job_info()
        scheduler_info["status"] = scheduler_worker.get_status()

    # Get job type breakdown
    job_type_stats = await scheduled_job_ops.get_job_type_statistics()

    return ResponseFormatter.success(
        data={
            "statistics": stats,
            "job_type_breakdown": job_type_stats,
            "scheduler_info": scheduler_info,
            "last_updated": utc_now(),
        },
        message="Retrieved job statistics",
    )


@router.put("/jobs/{job_id}", response_model=Dict[str, Any])
@handle_exceptions("update scheduled job")
async def update_scheduled_job(
    scheduled_job_ops: ScheduledJobOperationsDep,
    job_id: str = Path(..., description="Job ID to update"),
    update_data: ScheduledJobUpdate = Body(...),
) -> Dict[str, Any]:
    """
    Update a scheduled job's configuration.

    Can update schedule, status, and other job parameters.
    Note: Changes to actively running jobs may require scheduler restart.
    """

    # Verify job exists
    job = await scheduled_job_ops.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Validate update data
    if update_data.status and update_data.status not in VALID_SCHEDULED_JOB_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{update_data.status}'. Valid statuses: {', '.join(sorted(VALID_SCHEDULED_JOB_STATUSES))}",
        )

    # Update job in database
    success = await scheduled_job_ops.update_job(job_id, update_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update job")

    # Get updated job
    updated_job = await scheduled_job_ops.get_job_by_id(job_id)

    # Service layer handles any necessary SSE broadcasting

    # Note: We don't automatically sync with APScheduler here as that could
    # disrupt running jobs. This is a database-only update for configuration.

    return ResponseFormatter.success(
        data={"job": updated_job},
        message=f"Updated job {job_id}. Note: Scheduler sync may be required for active jobs.",
    )


@router.post("/jobs/{job_id}/actions/{action}", response_model=Dict[str, Any])
@handle_exceptions("execute job action")
async def execute_job_action(
    admin_service: AdminServiceDep,
    job_id: str = Path(..., description="Job ID"),
    action: str = Path(..., description="Action to execute"),
) -> Dict[str, Any]:
    """
    Execute actions on scheduled jobs.

    Available actions:
    - pause: Disable the job temporarily
    - resume: Re-enable a paused job
    - disable: Permanently disable the job
    - enable: Re-enable a disabled job
    - trigger: Manually trigger job execution (if scheduler is available)
    """
    valid_actions = {"pause", "resume", "disable", "enable", "trigger"}
    if action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{action}'. Valid actions: {', '.join(valid_actions)}",
        )

    try:
        # Get scheduler worker for trigger actions
        scheduler_worker = get_scheduler_worker() if action == "trigger" else None

        # Use admin service for business logic
        result = await admin_service.execute_job_action(
            job_id=job_id,
            action=action,
            scheduler_worker=scheduler_worker,
        )

        return ResponseFormatter.success(
            data={"job": result["job"]}, message=result["message"]
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/bulk-actions/{action}", response_model=Dict[str, Any])
@handle_exceptions("execute bulk job action")
async def execute_bulk_job_action(
    admin_service: AdminServiceDep,
    action: str = Path(..., description="Bulk action to execute"),
    job_ids: List[str] = Query(..., description="List of job IDs"),
) -> Dict[str, Any]:
    """
    Execute bulk actions on multiple scheduled jobs.

    Available actions:
    - pause: Pause multiple jobs
    - resume: Resume multiple jobs
    - disable: Disable multiple jobs
    - enable: Enable multiple jobs
    """
    valid_actions = {"pause", "resume", "disable", "enable"}
    if action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{action}'. Valid actions: {', '.join(valid_actions)}",
        )

    try:
        # Use admin service for business logic
        result = await admin_service.execute_bulk_job_action(
            job_ids=job_ids,
            action=action,
        )

        return ResponseFormatter.success(
            data=result,
            message=f"Bulk {action}: {result['successful']}/{result['total_jobs']} jobs processed successfully",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health", response_model=Dict[str, Any])
@handle_exceptions("admin health check")
async def admin_health_check(
    admin_service: AdminServiceDep,
) -> Dict[str, Any]:
    """
    Health check for the admin system and scheduler integration.

    Verifies database connectivity, scheduler status, and overall system health.
    Integrates with the existing HealthService for comprehensive health assessment.
    """

    # Get health service and scheduler worker
    health_service = await get_health_service()
    scheduler_worker = get_scheduler_worker()

    # Use admin service for health assessment business logic
    health_data = await admin_service.get_admin_health_assessment(
        health_service=health_service,
        scheduler_worker=scheduler_worker,
    )

    return ResponseFormatter.success(
        data=health_data,
        message=f"Admin system health check completed - Status: {'Healthy' if health_data['admin_healthy'] else 'Unhealthy'}",
    )
