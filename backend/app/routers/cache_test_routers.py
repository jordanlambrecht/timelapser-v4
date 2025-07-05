#!/usr/bin/env python3
# backend/app/routers/cache_test_routers.py

"""
Cache Test Routers - Testing endpoints for cache and SSE integration.

Provides endpoints to test cache invalidation, SSE broadcasting,
and the interaction between caching and real-time updates.
"""

from typing import Dict, Any
from fastapi import APIRouter
from loguru import logger

from ..utils.cache_manager import cache, get_cache_stats, clear_cache
from ..utils.cache_invalidation import cache_invalidation
from ..utils.response_helpers import ResponseFormatter
from ..database.sse_events_operations import SyncSSEEventsOperations
from ..database import sync_db
from ..utils.router_helpers import handle_exceptions

# TODO: CACHING STRATEGY - NO CACHE
# Use "Cache-Control: no-store" for all testing endpoints.
# Testing/debugging endpoints should never be cached to ensure fresh results.
router = APIRouter(prefix="/test", tags=["cache-testing"])


@router.get("/cache/stats")
@handle_exceptions("get cache stats")
async def get_cache_statistics() -> Dict[str, Any]:
    """Get current cache statistics for monitoring."""
    stats = await get_cache_stats()
    return ResponseFormatter.success(data=stats, message="Cache statistics retrieved")


@router.post("/cache/clear")
@handle_exceptions("clear cache")
async def clear_all_cache() -> Dict[str, Any]:
    """Clear all cache entries for testing."""
    await clear_cache()
    return ResponseFormatter.success(message="All cache entries cleared")


@router.post("/cache/invalidate/camera/{camera_id}")
@handle_exceptions("invalidate camera cache")
async def invalidate_camera_cache(camera_id: int) -> Dict[str, Any]:
    """Test cache invalidation for a specific camera."""
    await cache_invalidation.invalidate_latest_image_cache(camera_id)
    await cache_invalidation.invalidate_camera_status_cache(camera_id)

    return ResponseFormatter.success(
        message=f"Cache invalidated for camera {camera_id}"
    )


@router.post("/sse/test/image-captured")
@handle_exceptions("test image captured SSE")
async def test_image_captured_sse(
    camera_id: int, image_id: int = 999, test_cache: bool = True
) -> Dict[str, Any]:
    """
    Test SSE broadcasting for image_captured event and verify cache invalidation.

    Args:
        camera_id: ID of camera to test
        image_id: Fake image ID for testing
        test_cache: Whether to test cache invalidation
    """

    cached_before = None
    cached_after = None
    test_cache_key = None

    if test_cache:
        # First, add a test cache entry
        test_cache_key = f"get_latest_image_for_camera:{camera_id}"
        await cache.set(test_cache_key, {"fake": "cached_data"}, ttl_seconds=300)

        # Verify it's cached
        cached_before = await cache.get(test_cache_key)
        logger.info(f"🧪 Cache before SSE: {cached_before is not None}")

    # Create SSE event (which should trigger cache invalidation)
    sse_ops = SyncSSEEventsOperations(sync_db)
    sse_ops.create_event(
        event_type="image_captured",
        event_data={
            "camera_id": camera_id,
            "image_id": image_id,
            "image_path": f"/test/image_{image_id}.jpg",
        },
        priority="normal",
        source="test"
    )

    if test_cache and test_cache_key:
        # Check if cache was invalidated
        import asyncio

        await asyncio.sleep(0.1)  # Give cache invalidation time to execute

        cached_after = await cache.get(test_cache_key)
        cache_invalidated = cached_after is None

        logger.info(
            f"🧪 Cache after SSE: {cached_after is not None}, Invalidated: {cache_invalidated}"
        )

        return ResponseFormatter.success(
            data={
                "event_sent": True,
                "cache_before": cached_before is not None,
                "cache_after": cached_after is not None,
                "cache_invalidated": cache_invalidated,
            },
            message=f"SSE event sent for camera {camera_id} - cache test completed",
        )
    else:
        return ResponseFormatter.success(
            data={"event_sent": True}, message=f"SSE event sent for camera {camera_id}"
        )


@router.post("/sse/test/camera-status")
@handle_exceptions("test camera status SSE")
async def test_camera_status_sse(
    camera_id: int, status: str = "online"
) -> Dict[str, Any]:
    """Test SSE broadcasting for camera_status_changed event."""

    # Create SSE event
    sse_ops = SyncSSEEventsOperations(sync_db)
    sse_ops.create_event(
        event_type="camera_status_changed",
        event_data={
            "camera_id": camera_id,
            "status": status,
            "connectivity": True if status == "online" else False,
        },
        priority="normal",
        source="test"
    )

    return ResponseFormatter.success(
        data={"event_sent": True, "camera_id": camera_id, "status": status},
        message=f"Camera status SSE event sent for camera {camera_id}",
    )


@router.get("/cache/manual-test/{camera_id}")
@handle_exceptions("manual cache test")
async def manual_cache_test(camera_id: int) -> Dict[str, Any]:
    """
    Manual test to add cache entries and check invalidation patterns.

    This helps verify that our cache keys match what the actual services use.
    """

    # Add various cache entries that would be created by real requests
    test_entries = [
        (f"get_latest_image_for_camera:{camera_id}", {"test": "latest_image_data"}),
        (
            f"latest_image:get_latest_image_for_camera:{camera_id}",
            {"test": "prefixed_latest_image"},
        ),
        (
            f"get_camera_latest_image_unified:{camera_id}",
            {"test": "unified_endpoint_data"},
        ),
        (f"get_camera_by_id:{camera_id}", {"test": "camera_data"}),
    ]

    # Add all test entries
    for key, data in test_entries:
        await cache.set(key, data, ttl_seconds=300)

    # Verify they're all cached
    cache_status = {}
    for key, _ in test_entries:
        cached_data = await cache.get(key)
        cache_status[key] = cached_data is not None

    return ResponseFormatter.success(
        data={
            "cache_entries_added": len(test_entries),
            "cache_status": cache_status,
            "instructions": f"Now call /test/cache/invalidate/camera/{camera_id} to test invalidation",
        },
        message=f"Manual cache test setup complete for camera {camera_id}",
    )
