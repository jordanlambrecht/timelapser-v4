# backend/app/routers/dashboard_routers.py
"""
Dashboard aggregation HTTP endpoints.

Role: Dashboard aggregation HTTP endpoints
Responsibilities: System overview metrics, health summaries, real-time status endpoints
Interactions: Uses StatisticsService for aggregated data, coordinates multiple services for dashboard views
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger

from ..dependencies import StatisticsServiceDep
from ..models.statistics_model import (
    DashboardStatsModel,
    CameraPerformanceModel,
    QualityTrendDataPoint,
    StorageStatsModel,
    SystemHealthScoreModel,
)
from ..utils.response_helpers import ResponseFormatter
from ..utils.router_helpers import handle_exceptions
from ..utils.response_helpers import ResponseFormatter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsModel)
@handle_exceptions("get dashboard stats")
async def get_dashboard_stats(statistics_service: StatisticsServiceDep):
    """Get comprehensive dashboard statistics"""
    dashboard_stats = await statistics_service.get_dashboard_stats()
    return ResponseFormatter.success(
        "Dashboard statistics retrieved", data=dashboard_stats.model_dump()
    )


@router.get("/health-score", response_model=SystemHealthScoreModel)
@handle_exceptions("get system health score")
async def get_system_health_score(statistics_service: StatisticsServiceDep):
    """Get overall system health score"""
    health_score = await statistics_service.get_system_health_score()
    return ResponseFormatter.success(
        "System health score retrieved", data=health_score.model_dump()
    )


@router.get("/camera-performance", response_model=list[CameraPerformanceModel])
@handle_exceptions("get camera performance")
async def get_camera_performance(
    statistics_service: StatisticsServiceDep,
    limit: Optional[int] = Query(10, description="Number of cameras to return"),
):
    """Get camera performance metrics"""
    performance_data = await statistics_service.get_camera_performance_stats()
    return ResponseFormatter.success(
        "Camera performance metrics retrieved",
        data=[item.model_dump() for item in performance_data],
    )


@router.get("/quality-trends")
@handle_exceptions("get quality trends")
async def get_quality_trends(
    statistics_service: StatisticsServiceDep,
    days: Optional[int] = Query(7, description="Number of days to include"),
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
):
    """Get quality trend data points"""
    trend_data = await statistics_service.get_quality_trend_data()
    return ResponseFormatter.success(
        "Quality trend data points retrieved",
        data=[item.model_dump() for item in trend_data],
    )


@router.get("/storage", response_model=StorageStatsModel)
@handle_exceptions("get storage stats")
async def get_storage_stats(statistics_service: StatisticsServiceDep):
    """Get storage utilization statistics"""
    storage_stats = await statistics_service.get_storage_statistics()
    return ResponseFormatter.success(
        "Storage utilization statistics retrieved", data=storage_stats.model_dump()
    )


@router.get("/system-overview")
@handle_exceptions("get system overview")
async def get_system_overview(statistics_service: StatisticsServiceDep):
    """Get complete system overview for dashboard"""
    # Get simple UTC timestamp for last_updated
    current_timestamp = datetime.now(timezone.utc)

    overview = await statistics_service.get_dashboard_stats()
    overview_dict = overview.model_dump()
    overview_dict["last_updated"] = current_timestamp.isoformat()
    return ResponseFormatter.success("System overview retrieved", data=overview_dict)
