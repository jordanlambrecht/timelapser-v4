# backend/app/routers/dashboard_routers.py
"""
Dashboard aggregation HTTP endpoints.

Role: Dashboard aggregation HTTP endpoints
Responsibilities: System overview metrics, health summaries, real-time status endpoints
Interactions: Uses StatisticsService for aggregated data, coordinates multiple services for dashboard views
"""

from fastapi import APIRouter, Response

from ..dependencies import CameraServiceDep, StatisticsServiceDep, HealthServiceDep
from ..utils.cache_manager import (
    generate_collection_etag,
    generate_composite_etag,
    generate_content_hash_etag,
    generate_timestamp_etag
)
from ..models.statistics_model import (
    DashboardStatsModel,
    EnhancedDashboardStatsModel,
    SystemHealthScoreModel,
)
from ..utils.router_helpers import handle_exceptions
from ..utils.response_helpers import ResponseFormatter

# TODO: CACHING STRATEGY - ETAG + SHORT CACHE
# Dashboard is perfect use case for ETag + short cache strategy:
# - Composite data (stats/overview): ETag + 2-3 min cache - changes occasionally
# - Health status: SSE broadcasting - critical real-time monitoring
# Dashboard data is expensive to compute but doesn't change every second.
router = APIRouter(tags=["dashboard"])


# IMPLEMENTED: ETag + 2-3 minute cache (composite dashboard data changes occasionally)
# This is the PERFECT use case for composite endpoint caching
# ETag based on hash of latest camera/timelapse/image/video timestamps
@router.get("/dashboard", response_model=EnhancedDashboardStatsModel)
@handle_exceptions("get dashboard overview")
async def get_dashboard_overview(
    response: Response,
    statistics_service: StatisticsServiceDep,
) -> EnhancedDashboardStatsModel:
    """Get complete unified dashboard overview including system data"""
    # All business logic handled in service layer
    enhanced_stats = await statistics_service.get_enhanced_dashboard_stats()
    
    # Generate ETag based on dashboard stats content (composite data)
    etag = generate_content_hash_etag(enhanced_stats.model_dump())
    
    # Add short cache for dashboard composite data
    response.headers["Cache-Control"] = "public, max-age=180, s-maxage=180"  # 3 minutes
    response.headers["ETag"] = etag
    
    return enhanced_stats


# IMPLEMENTED: ETag + 2-3 minute cache (dashboard stats change occasionally)
# ETag based on system activity - camera counts, image counts, latest activity
@router.get("/dashboard/stats", response_model=DashboardStatsModel)
@handle_exceptions("get dashboard stats")
async def get_dashboard_stats(
    response: Response,
    statistics_service: StatisticsServiceDep,
) -> DashboardStatsModel:
    """Get comprehensive dashboard statistics"""
    dashboard_stats = await statistics_service.get_dashboard_stats()
    
    # Generate ETag based on dashboard stats content
    etag = generate_content_hash_etag(dashboard_stats.model_dump())
    
    # Add short cache for dashboard statistics
    response.headers["Cache-Control"] = "public, max-age=180, s-maxage=180"  # 3 minutes
    response.headers["ETag"] = etag
    
    return dashboard_stats


# DEPRECATED ENDPOINTS MERGED INTO MAIN /dashboard:
# - /dashboard/system-overview merged into main /dashboard endpoint
# - /dashboard/storage merged into main /dashboard endpoint
# - /dashboard/quality-trends merged into main /dashboard endpoint
# - /dashboard/camera-performance merged into main /dashboard endpoint
# - /dashboard/health-score merged into main /dashboard endpoint
# All system overview, storage, quality trends, camera performance, and health score data is now included in the unified dashboard response


# TODO: Replace with SSE in services layer- health status changes frequently and is critical for monitoring
# Use very short cache (30 seconds max) or preferably SSE events
@router.get("/dashboard/health")
@handle_exceptions("get dashboard health")
async def get_dashboard_health(health_service: HealthServiceDep):
    """Get health status for dashboard display"""
    health_status = await health_service.get_detailed_health()
    return ResponseFormatter.success(
        "Dashboard health status retrieved", data=health_status.model_dump()
    )


# TODO: Decide if we need this
# @router.get("/dashboard/complete")
# @handle_exceptions("retrieve complete dashboard")
# async def get_complete_dashboard(
#     camera_service: CameraServiceDep,
#     statistics_service: StatisticsServiceDep
# ) -> Dict[str, Any]:
#     """Single call replacing 4-6 separate dashboard API calls"""
#     dashboard_data = await asyncio.gather(
#         camera_service.list_cameras_with_latest_images(),
#         statistics_service.get_system_overview(),
#         statistics_service.get_recent_activity(limit=10),
#         statistics_service.get_health_summary()
#     )

#     return ResponseFormatter.success(data={
#         "cameras": dashboard_data[0],
#         "system_stats": dashboard_data[1],
#         "recent_activity": dashboard_data[2],
#         "health": dashboard_data[3]
#     })
