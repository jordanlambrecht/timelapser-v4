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
from ..models.log_summary_model import LogSourceModel, LogSummaryModel
from ..utils.router_helpers import (
    handle_exceptions,
    paginate_query_params,
)
from ..utils.response_helpers import ResponseFormatter
from ..utils.pagination_helpers import create_pagination_metadata
from ..utils.time_utils import (
    get_timezone_aware_timestamp_async,
    parse_iso_timestamp_safe,
)
from ..constants import (
    LOG_LEVELS,
    DEFAULT_LOG_PAGE_SIZE,
    LOG_LEVELS_LIST,
    MAX_LOG_PAGE_SIZE,
)

# NOTE: CACHING STRATEGY - MIXED APPROACH
# Log endpoints use mixed caching strategy:
# - Log statistics/summary: ETag + short cache (2-5 min) - aggregated data changes slowly
# - Log sources: ETag + longer cache (15-30 min) - mostly static configuration data
# - Log search/filtering: Minimal cache (30 seconds max) - dynamic queries with parameters
# - Historical logs: Short cache + ETag - immutable once written but accessed frequently
router = APIRouter(tags=["logs"])


@router.get("/logs/stats")
@handle_exceptions("get log stats")
async def get_log_stats(
    log_service: LogServiceDep,
    hours: int = Query(
        24,
        ge=1,
        le=168,
        description="Number of hours to include in comprehensive log statistics",
    ),
) -> dict:
    """Get comprehensive log statistics and summary for the specified time period (default: 24h)"""

    summary: LogSummaryModel = await log_service.get_log_summary(hours=hours)

    return ResponseFormatter.success(
        "Log statistics fetched successfully",
        data={
            "summary": summary.model_dump(),
            "period_hours": hours,
            "metadata": {
                "generated_at": (
                    await get_timezone_aware_timestamp_async(log_service.db)
                ).isoformat(),
                "data_range": {
                    "first_log": (
                        summary.first_log_at.isoformat()
                        if summary.first_log_at
                        else None
                    ),
                    "last_log": (
                        summary.last_log_at.isoformat() if summary.last_log_at else None
                    ),
                },
                "coverage": {
                    "unique_sources": summary.unique_sources,
                    "unique_cameras": summary.unique_cameras,
                },
            },
        },
    )


@router.get("/logs")
@handle_exceptions("get logs")
async def get_logs(
    log_service: LogServiceDep,
    level: Optional[str] = Query(
        None, description=f"Filter by log level ({', '.join(LOG_LEVELS_LIST)})"
    ),
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
    source: Optional[str] = Query(
        None, description="Filter by log source (system, camera)"
    ),
    search: Optional[str] = Query(None, description="Search in log messages"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(
        DEFAULT_LOG_PAGE_SIZE, ge=1, le=MAX_LOG_PAGE_SIZE, description="Items per page"
    ),
    start_date: Optional[str] = Query(
        None, description="Start date filter (ISO format)"
    ),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
):
    """Get logs with optional filtering and pagination"""

    # Validate pagination parameters
    limit, offset = paginate_query_params(page, limit, max_per_page=MAX_LOG_PAGE_SIZE)

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
    if level and level.upper() not in LOG_LEVELS_LIST:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid log level. Must be one of: {', '.join(LOG_LEVELS_LIST)}",
        )

    result = await log_service.get_logs(
        camera_id=camera_id,
        level=level.upper() if level else None,
        source=source,
        search_query=search,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        page=page,
        page_size=limit,
    )

    return ResponseFormatter.success(
        "Logs fetched successfully",
        data={
            "logs": result["logs"],
            "pagination": create_pagination_metadata(
                page=page,
                limit=limit,
                total_pages=result["total_pages"],
                total_count=result["total_count"],
            ),
            "filters_applied": {
                "level": level,
                "camera_id": camera_id,
                "source": source,
                "search": search,
                "start_date": start_date,
                "end_date": end_date,
            },
        },
    )


# DEPRECATED: /logs/levels endpoint removed - use static LOG_LEVELS constant from frontend
# Log levels are hardcoded constants and don't require database queries


@router.get("/logs/sources")
@handle_exceptions("get log sources")
async def get_log_sources(log_service: LogServiceDep) -> dict:
    """Get available log sources and their statistics"""

    sources: List[LogSourceModel] = await log_service.get_log_sources()
    return ResponseFormatter.success(
        "Log sources fetched successfully",
        data={
            "sources": [source.model_dump() for source in sources],
            "total_sources": len(sources),
        },
    )


@router.get("/logs/search")
@handle_exceptions("search logs")
async def search_logs(
    log_service: LogServiceDep,
    query: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(
        DEFAULT_LOG_PAGE_SIZE, ge=1, le=MAX_LOG_PAGE_SIZE, description="Items per page"
    ),
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
    level: Optional[str] = Query(None, description="Filter by log level"),
):
    """Search logs by message content"""

    # Validate pagination parameters
    limit, offset = paginate_query_params(page, limit, max_per_page=MAX_LOG_PAGE_SIZE)

    # Validate log level if provided
    if level and level.upper() not in LOG_LEVELS_LIST:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid log level. Must be one of: {', '.join(LOG_LEVELS_LIST)}",
        )

    # Use get_logs with search query - the search functionality is built into get_logs
    result = await log_service.get_logs(
        search_query=query,
        camera_id=camera_id,
        level=level.upper() if level else None,
        page=page,
        page_size=limit,
    )

    return ResponseFormatter.success(
        "Log search completed successfully",
        data={
            "logs": result["logs"],
            "search_query": query,
            "pagination": create_pagination_metadata(
                page=page,
                limit=limit,
                total_pages=result["total_pages"],
                total_count=result["total_count"],
            ),
            "filters_applied": {
                "camera_id": camera_id,
                "level": level,
            },
        },
    )


@router.delete("/logs/cleanup")
@handle_exceptions("cleanup old logs")
async def cleanup_old_logs(
    log_service: LogServiceDep,
    days_to_keep: int = Query(
        30,
        ge=0,
        le=365,
        description="Number of days of logs to keep (0 = delete all logs)",
    ),
):
    """Clean up logs older than the specified number of days (0 = delete all logs)"""

    # Perform cleanup using the existing service method
    deleted_count = await log_service.delete_old_logs(days_to_keep)

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        f"Cleaned up {deleted_count} old log entries",
        data={
            "deleted_count": deleted_count,
            "days_kept": days_to_keep,
        },
    )


@router.get("/logs/cameras/{camera_id}")
@handle_exceptions("get camera logs")
async def get_camera_logs(
    camera_id: int,
    log_service: LogServiceDep,
    limit: int = Query(
        DEFAULT_LOG_PAGE_SIZE,
        ge=1,
        le=MAX_LOG_PAGE_SIZE,
        description="Number of recent logs to return",
    ),
) -> dict:
    """Get recent logs for a specific camera"""

    logs: List[Log] = await log_service.get_logs_for_camera(camera_id, limit=limit)
    return ResponseFormatter.success(
        "Camera logs fetched successfully",
        data={
            "logs": [log.model_dump() for log in logs],
            "camera_id": camera_id,
            "count": len(logs),
        },
    )


# NOTE: Export, individual log retrieval, and individual log deletion endpoints
# are not implemented yet as the corresponding service methods don't exist.
# These can be added when the LogService is extended with:
# - export_logs() method for data export functionality
# - get_log_by_id() method for individual log retrieval
# - delete_log() method for individual log deletion
