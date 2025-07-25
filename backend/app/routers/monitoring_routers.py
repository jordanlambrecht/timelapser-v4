#!/usr/bin/env python3
# backend/app/routers/monitoring_routers.py

"""
Monitoring and cache management endpoints.

Provides visibility into system performance, cache statistics,
and tools for diagnosing API flooding issues.
"""

from typing import Dict, Any
from fastapi import APIRouter, Response

from ..utils.router_helpers import handle_exceptions
from ..utils.cache_manager import get_cache_stats, clear_cache, cleanup_expired_cache
from ..utils.response_helpers import ResponseFormatter

# TODO: CACHING STRATEGY - NO CACHE (ALREADY IMPLEMENTED CORRECTLY)
# Monitoring endpoints correctly use "no-cache, no-store, must-revalidate".
# Monitoring/debugging endpoints should always provide real-time data and never be cached.
# Current implementation follows caching strategy guide perfectly.

router = APIRouter()


@router.get("/monitoring/cache/stats")
@handle_exceptions("get cache statistics")
async def get_cache_statistics(response: Response) -> Dict[str, Any]:
    """
    Get cache performance statistics.

    Shows cache hit rates, entries, and performance metrics
    to help diagnose API flooding issues.
    """
    # No caching for monitoring endpoints
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    cache_stats = await get_cache_stats()

    # Cache statistics retrieval - logging handled by @handle_exceptions decorator

    return ResponseFormatter.success(
        message="Cache statistics retrieved successfully",
        data={
            "cache_statistics": cache_stats,
            "performance_notes": {
                "latest_image_cache_ttl": "30 seconds",
                "cameras_list_cache_ttl": "15 seconds",
                "image_serving_cache_ttl": "300 seconds (5 minutes)",
                "cache_purpose": "Prevent API flooding by reducing database load",
            },
        },
    )


@router.post("/monitoring/cache/clear")
@handle_exceptions("clear cache")
async def clear_all_cache(response: Response) -> Dict[str, Any]:
    """
    Clear all cached data.

    Emergency endpoint to reset cache if stale data is causing issues.
    Use with caution as this will temporarily increase database load.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    await clear_cache()

    # Cache cleared - logging handled by @handle_exceptions decorator

    return ResponseFormatter.success(
        message="Cache cleared successfully",
        data={
            "warning": "Cache cleared - expect temporary increase in database queries",
            "recommendation": "Cache will rebuild automatically as endpoints are called",
        },
    )


@router.post("/monitoring/cache/cleanup")
@handle_exceptions("cleanup expired cache")
async def cleanup_cache(response: Response) -> Dict[str, Any]:
    """
    Clean up expired cache entries.

    Remove stale cache data to free memory and improve performance.
    This is normally done automatically but can be triggered manually.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    removed_count = await cleanup_expired_cache()

    # Cache cleanup completed - logging handled by @handle_exceptions decorator

    return ResponseFormatter.success(
        message=f"Cache cleanup completed: {removed_count} expired entries removed",
        data={"removed_entries": removed_count, "status": "cleanup_completed"},
    )


@router.get("/monitoring/performance/latest-image")
@handle_exceptions("get latest image performance")
async def get_latest_image_performance(response: Response) -> Dict[str, Any]:
    """
    Get performance metrics for latest-image endpoints.

    Helps diagnose API flooding and response time issues.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    cache_stats = await get_cache_stats()

    # Filter for latest image cache entries
    latest_image_keys = [
        key for key in cache_stats.get("cache_keys", []) if "latest_image" in key
    ]

    performance_data = {
        "latest_image_cache_entries": len(latest_image_keys),
        "cache_keys": latest_image_keys,
        "endpoints_with_caching": [
            "/api/cameras/{id}/latest-image (30s TTL)",
            "/api/cameras/{id}/latest-image/thumbnail (300s TTL)",
            "/api/cameras/{id}/latest-image/small (300s TTL)",
            "/api/cameras/{id}/latest-image/full (60s TTL)",
        ],
        "recommendations": {
            "frontend_polling": "Reduce polling frequency to match cache TTL (30s minimum)",
            "use_conditional_requests": "Implement If-None-Match headers for ETag support",
            "batch_requests": "Combine multiple camera latest-image requests where possible",
        },
        "flood_prevention": {
            "service_layer_caching": "30 second TTL on database queries",
            "http_cache_headers": "Public caching with max-age directives",
            "etag_support": "ETag headers for conditional requests",
        },
    }

    # Performance metrics retrieved - logging handled by @handle_exceptions decorator

    return ResponseFormatter.success(
        message="Latest image performance metrics retrieved", data=performance_data
    )
