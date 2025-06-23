# backend/app/routers/health.py
from fastapi import APIRouter

from loguru import logger

from ..database import sync_db, async_db
from ..time_utils import get_timezone_aware_timestamp_async

router = APIRouter()


@router.get("/")
async def health_check():
    """Main health check endpoint"""
    try:
        # Test database connectivity
        health_stats = sync_db.get_system_health()
        db_healthy = health_stats.get("status") == "healthy"

        # Test async database connectivity
        async_healthy = True
        try:
            # Quick test of async database
            await async_db.get_cameras()
        except Exception as e:
            logger.warning(f"Async database health check failed: {e}")
            async_healthy = False

        overall_healthy = db_healthy and async_healthy

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "timestamp": await get_timezone_aware_timestamp_async(async_db),
            "version": "1.0.0",
            "services": {
                "database": {
                    "sync": "healthy" if db_healthy else "unhealthy",
                    "async": "healthy" if async_healthy else "unhealthy",
                },
                "api": "healthy",  # If we reach this point, FastAPI is working
            },
            "quick_stats": {
                "total_cameras": health_stats.get("cameras", {}).get(
                    "total_cameras", 0
                ),
                "online_cameras": health_stats.get("cameras", {}).get(
                    "online_cameras", 0
                ),
                "running_timelapses": health_stats.get("timelapses", {}).get(
                    "running_timelapses", 0
                ),
            },
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": await get_timezone_aware_timestamp_async(async_db),
            "version": "1.0.0",
            "error": str(e),
            "services": {
                "database": {"sync": "unknown", "async": "unknown"},
                "api": "healthy",  # FastAPI is running
            },
        }


@router.get("/stats")
async def get_health_stats():
    """Get comprehensive system health statistics"""
    try:
        # Use the existing get_system_health method from sync_db
        health_stats = sync_db.get_system_health()
        return health_stats

    except Exception as e:
        logger.error(f"Failed to fetch health stats: {e}")
        # Return degraded status with empty stats
        return {
            "cameras": {
                "total_cameras": 0,
                "online_cameras": 0,
                "offline_cameras": 0,
                "active_cameras": 0,
            },
            "timelapses": {"running_timelapses": 0, "paused_timelapses": 0},
            "captures": {"recent_captures": 0},
            "images": {"total_images": 0},
            "status": "error",
            "error": str(e),
        }


@router.get("/stats-discovery")
async def get_stats_discovery():
    """
    Discover all available statistics endpoints across the system.
    This endpoint helps users find the specific stats they need.
    """
    return {
        "description": "Available statistics endpoints throughout the Timelapser system",
        "endpoints": {
            "system_health": {
                "url": "/api/health/stats",
                "description": "Comprehensive system health statistics including cameras, timelapses, and captures",
            },
            "cameras": {
                "url": "/api/cameras/stats",
                "description": "Camera statistics with detailed image and capture information",
            },
            "corruption_detection": {
                "url": "/api/corruption/stats",
                "description": "Image corruption detection statistics and system health scores",
            },
            "thumbnails": {
                "url": "/api/thumbnails/stats",
                "description": "Thumbnail coverage statistics and image processing metrics",
            },
            "logs": {
                "url": "/api/logs/stats",
                "description": "System log statistics by level and frequency",
            },
            "video_automation": {
                "url": "/api/video-automation/stats",
                "description": "Video automation job queue statistics and processing metrics",
            },
        },
        "usage_note": "Each endpoint provides domain-specific statistics. Use the URLs above to access detailed metrics for specific system components.",
    }
