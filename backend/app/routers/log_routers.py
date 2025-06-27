# backend/app/routers/log_routers.py
"""
Log management HTTP endpoints.

Role: Log management HTTP endpoints
Responsibilities: Log retrieval, filtering, search, and cleanup operations
Interactions: Uses LogService for business logic, provides structured log accesswith pagination and filtering capabilities
"""

from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException

from ..dependencies import LogServiceDep
from ..models.log_model import Log
from ..models.log_summary_model import LogSourceModel, LogLevelModel, LogSummaryModel
from ..utils.router_helpers import (
    handle_exceptions,
    create_success_response,
    paginate_query_params,
)
from ..utils.time_utils import parse_iso_timestamp_safe
from ..constants import LOG_LEVELS

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/")
@handle_exceptions("get logs")
async def get_logs(
    log_service: LogServiceDep,
    level: Optional[str] = Query(
        None, description=f"Filter by log level ({', '.join(LOG_LEVELS)})"
    ),
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
    search: Optional[str] = Query(None, description="Search in log messages"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    start_date: Optional[str] = Query(
        None, description="Start date filter (ISO format)"
    ),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
):
    """Get logs with optional filtering and pagination"""
    # Validate pagination parameters
    limit, offset = paginate_query_params(page, limit, max_per_page=100)

    # Parse date strings with proper timezone handling
    parsed_start_date = None
    parsed_end_date = None

    if start_date:
        try:
            parsed_start_date = parse_iso_timestamp_safe(start_date)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid start_date format. Use ISO format."
            )

    if end_date:
        try:
            parsed_end_date = parse_iso_timestamp_safe(end_date)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid end_date format. Use ISO format."
            )

    # Validate log level if provided
    if level and level.upper() not in LOG_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid log level. Must be one of: {', '.join(LOG_LEVELS)}",
        )

    result = await log_service.get_logs(
        camera_id=camera_id,
        level=level.upper() if level else None,
        search_query=search,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        page=page,
        page_size=limit,
    )

    # Calculate pagination metadata
    total_pages = result["total_pages"]
    has_next = page < total_pages
    has_previous = page > 1

    return {
        "logs": result["logs"],
        "pagination": {
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_items": result["total_count"],
            "has_next": has_next,
            "has_previous": has_previous,
        },
        "filters_applied": {
            "level": level,
            "camera_id": camera_id,
            "search": search,
            "start_date": start_date,
            "end_date": end_date,
        },
    }


@router.get("/levels")
@handle_exceptions("get log levels")
async def get_log_levels(log_service: LogServiceDep) -> dict:
    """Get available log levels and their counts"""
    levels: List[LogLevelModel] = await log_service.get_log_levels()
    return {
        "levels": [level.model_dump() for level in levels],
        "total_logs": sum(level.log_count for level in levels),
    }


@router.get("/sources")
@handle_exceptions("get log sources")
async def get_log_sources(log_service: LogServiceDep) -> dict:
    """Get available log sources and their statistics"""
    sources: List[LogSourceModel] = await log_service.get_log_sources()
    return {
        "sources": [source.model_dump() for source in sources],
        "total_sources": len(sources),
    }


@router.get("/recent")
@handle_exceptions("get recent logs")
async def get_recent_logs(
    log_service: LogServiceDep,
    count: int = Query(50, ge=1, le=200, description="Number of recent logs to return"),
    level: Optional[str] = Query(
        None, description=f"Filter by log level ({', '.join(LOG_LEVELS)})"
    ),
):
    """Get the most recent logs"""
    # Validate log level if provided
    if level and level.upper() not in LOG_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid log level. Must be one of: {', '.join(LOG_LEVELS)}",
        )

    # Use get_logs with pagination to get recent logs
    result = await log_service.get_logs(
        level=level.upper() if level else None, page=1, page_size=count
    )

    return {"logs": result["logs"], "count": len(result["logs"]), "level_filter": level}


@router.get("/search")
@handle_exceptions("search logs")
async def search_logs(
    log_service: LogServiceDep,
    query: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
    level: Optional[str] = Query(None, description="Filter by log level"),
):
    """Search logs by message content"""
    # Validate pagination parameters
    limit, offset = paginate_query_params(page, limit, max_per_page=100)

    # Validate log level if provided
    if level and level.upper() not in LOG_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid log level. Must be one of: {', '.join(LOG_LEVELS)}",
        )

    # Use get_logs with search query - the search functionality is built into get_logs
    result = await log_service.get_logs(
        search_query=query,
        camera_id=camera_id,
        level=level.upper() if level else None,
        page=page,
        page_size=limit,
    )

    # Calculate pagination metadata
    total_pages = result["total_pages"]
    has_next = page < total_pages
    has_previous = page > 1

    return {
        "logs": result["logs"],
        "search_query": query,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_items": result["total_count"],
            "has_next": has_next,
            "has_previous": has_previous,
        },
        "filters_applied": {
            "camera_id": camera_id,
            "level": level,
        },
    }


@router.get("/summary")
@handle_exceptions("get log summary")
async def get_log_summary(
    log_service: LogServiceDep,
    hours: int = Query(
        24, ge=1, le=168, description="Number of hours to include in summary"
    ),
) -> dict:
    """Get log summary statistics for the specified time period"""
    summary: LogSummaryModel = await log_service.get_log_summary(hours=hours)
    return {"summary": summary.model_dump(), "period_hours": hours}


@router.get("/errors")
@handle_exceptions("get recent errors")
async def get_recent_errors(
    log_service: LogServiceDep,
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look back"),
    limit: int = Query(
        50, ge=1, le=200, description="Maximum number of errors to return"
    ),
) -> dict:
    """Get recent error and critical logs"""
    errors: List[Log] = await log_service.get_recent_errors(hours=hours, limit=limit)
    return {
        "errors": [error.model_dump() for error in errors],
        "count": len(errors),
        "hours_analyzed": hours,
    }


@router.delete("/cleanup")
@handle_exceptions("cleanup old logs")
async def cleanup_old_logs(
    log_service: LogServiceDep,
    days_to_keep: int = Query(
        30, ge=1, le=365, description="Number of days of logs to keep"
    ),
):
    """Clean up logs older than the specified number of days"""
    # Perform cleanup using the existing service method
    deleted_count = await log_service.delete_old_logs(days_to_keep)
    return create_success_response(
        f"Cleaned up {deleted_count} old log entries",
        deleted_count=deleted_count,
        days_kept=days_to_keep,
    )


@router.get("/cameras/{camera_id}")
@handle_exceptions("get camera logs")
async def get_camera_logs(
    camera_id: int,
    log_service: LogServiceDep,
    limit: int = Query(50, ge=1, le=200, description="Number of recent logs to return"),
) -> dict:
    """Get recent logs for a specific camera"""
    logs: List[Log] = await log_service.get_logs_for_camera(camera_id, limit=limit)
    return {
        "logs": [log.model_dump() for log in logs],
        "camera_id": camera_id,
        "count": len(logs),
    }


# Note: Export, individual log retrieval, and individual log deletion endpoints
# are not implemented yet as the corresponding service methods don't exist.
# These can be added when the LogService is extended with:
# - export_logs() method for data export functionality
# - get_log_by_id() method for individual log retrieval
# - delete_log() method for individual log deletion
