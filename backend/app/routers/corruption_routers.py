# backend/app/routers/corruption_routers.py
"""
Corruption detection management HTTP endpoints.

Role: Corruption detection management HTTP endpoints
Responsibilities: Corruption statistics, degraded mode management,
                 corruption settings configuration
Interactions: Uses CorruptionService for business logic, provides quality metrics
             and audit trail access
"""


from typing import Optional
from fastapi import APIRouter, Query, UploadFile, File, HTTPException, Response
from loguru import logger

from ..dependencies import CorruptionServiceDep, CameraServiceDep, SettingsServiceDep, AsyncDatabaseDep
from ..utils.cache_manager import (
    generate_collection_etag,
    generate_composite_etag,
    generate_content_hash_etag,
    generate_timestamp_etag
)
from ..models.corruption_model import (
    CorruptionHistoryResponse,
    CorruptionSettings,
    CorruptionLogEntry,
    CorruptionTestResponse,
)
from ..utils.response_helpers import ResponseFormatter
from ..database.sse_events_operations import SSEEventsOperations
from ..utils.router_helpers import (
    handle_exceptions,
    validate_entity_exists,
)
from ..utils.timezone_utils import get_timezone_aware_timestamp_string_async
from ..constants import (
    DEFAULT_CORRUPTION_HISTORY_HOURS,
    DEFAULT_CORRUPTION_LOGS_PAGE_SIZE,
    MAX_CORRUPTION_LOGS_PAGE_SIZE,
    EVENT_CORRUPTION_DEGRADED_MODE_RESET,
    EVENT_CORRUPTION_TEST_COMPLETED,
    EVENT_CORRUPTION_HEALTH_UPDATED,
)

# TODO: CACHING STRATEGY - MIXED APPROACH
# Corruption detection uses mixed caching strategy:
# - Statistics/settings: ETag + long cache (10-20 min) - changes slowly
# - Health/degraded mode: SSE broadcasting - critical real-time monitoring
# - Dynamic operations (testing): No cache - always run fresh
# Individual endpoint TODOs are well-defined throughout this file.
router = APIRouter(tags=["corruption"])


# IMPLEMENTED: ETag + 10 minute cache (corruption stats change slowly)
# ETag based on latest corruption log timestamp + total count
@router.get("/corruption/stats")
@handle_exceptions("get corruption system stats")
async def get_corruption_system_stats(response: Response, corruption_service: CorruptionServiceDep):
    """Get system-wide corruption detection statistics"""
    stats = await corruption_service.get_system_corruption_stats()
    
    # Generate ETag based on stats content for cache validation
    etag = generate_content_hash_etag(stats)
    
    # Add moderate cache for corruption statistics
    response.headers["Cache-Control"] = "public, max-age=600, s-maxage=600"  # 10 minutes
    response.headers["ETag"] = etag
    
    return ResponseFormatter.success(
        "System corruption statistics retrieved successfully", data=stats
    )


# IMPLEMENTED: ETag + 15 minute cache (camera corruption stats change slowly)
# ETag based on camera corruption count + last detection timestamp
@router.get("/corruption/camera/{camera_id}/stats")
@handle_exceptions("get camera corruption stats")
async def get_camera_corruption_stats(
    response: Response,
    camera_id: int,
    corruption_service: CorruptionServiceDep,
    camera_service: CameraServiceDep,
    days: Optional[int] = Query(7, description="Number of days to include in stats"),
):
    """Get corruption statistics for a specific camera"""
    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    stats = await corruption_service.get_camera_corruption_stats(camera_id)
    
    # Generate ETag based on camera ID, days parameter, and stats content
    etag = generate_content_hash_etag(f"{camera_id}-{days}-{stats}")
    
    # Add longer cache for camera corruption statistics
    response.headers["Cache-Control"] = "public, max-age=900, s-maxage=900"  # 15 minutes
    response.headers["ETag"] = etag
    
    return ResponseFormatter.success(
        f"Camera {camera_id} corruption statistics retrieved successfully", data=stats
    )


# IMPLEMENTED: ETag + 5 minute cache (corruption history is mostly historical)
# ETag based on latest corruption log for this camera
@router.get(
    "/corruption/camera/{camera_id}/history", response_model=CorruptionHistoryResponse
)
@handle_exceptions("get camera corruption history")
async def get_camera_corruption_history(
    response: Response,
    camera_id: int,
    corruption_service: CorruptionServiceDep,
    camera_service: CameraServiceDep,
    hours: Optional[int] = Query(
        DEFAULT_CORRUPTION_HISTORY_HOURS,
        description="Number of hours of history to retrieve",
    ),
):
    """Get corruption detection history for a camera"""
    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    hours_int = hours if hours is not None else DEFAULT_CORRUPTION_HISTORY_HOURS
    history = await corruption_service.get_camera_corruption_history(
        camera_id, hours=hours_int
    )
    
    # Generate ETag based on camera ID, hours, and history content
    etag = generate_content_hash_etag(f"{camera_id}-{hours_int}-{len(history) if history else 0}")
    
    # Add short cache for corruption history (mostly static historical data)
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
    response.headers["ETag"] = etag
    
    return ResponseFormatter.success(
        "Camera corruption history fetched", data={"logs": history}
    )


# IMPLEMENTED: ETag + 20 minute cache (corruption settings change rarely)
# ETag based on corruption settings updated_at timestamp
@router.get("/corruption/settings", response_model=CorruptionSettings)
@handle_exceptions("get corruption settings")
async def get_corruption_settings(response: Response, corruption_service: CorruptionServiceDep):
    """Get corruption detection settings"""
    settings = await corruption_service.get_corruption_settings()
    
    # Generate ETag based on settings content
    etag = generate_content_hash_etag(settings)
    
    # Add long cache for corruption settings (they change rarely)
    response.headers["Cache-Control"] = "public, max-age=1200, s-maxage=1200"  # 20 minutes
    response.headers["ETag"] = etag
    
    return ResponseFormatter.success(
        "Corruption settings retrieved successfully", data=settings
    )


@router.put("/corruption/settings")
@handle_exceptions("update corruption settings")
async def update_corruption_settings(
    settings_data: dict,
    corruption_service: CorruptionServiceDep
):
    """Update corruption detection settings"""
    # Extract global settings from the request
    global_settings = settings_data.get("global_settings", {})
    
    # Update corruption settings
    updated_settings = await corruption_service.update_corruption_settings(global_settings)
    
    return ResponseFormatter.success(
        "Corruption settings updated successfully",
        data=updated_settings
    )


# IMPLEMENTED: ETag + 5 minute cache (corruption logs change when new detections occur)
# ETag based on latest corruption log timestamp + page + filters
@router.get("/corruption/logs")
@handle_exceptions("get corruption logs")
async def get_corruption_logs(
    response: Response,
    corruption_service: CorruptionServiceDep,
    camera_service: CameraServiceDep,
    camera_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(
        DEFAULT_CORRUPTION_LOGS_PAGE_SIZE, ge=1, le=MAX_CORRUPTION_LOGS_PAGE_SIZE
    ),
    min_score: Optional[int] = Query(None),
    max_score: Optional[int] = Query(None),
):
    """Get corruption detection logs with filtering and pagination"""
    # Validate camera exists if camera_id provided
    if camera_id is not None:
        await validate_entity_exists(
            camera_service.get_camera_by_id, camera_id, "camera"
        )

    result = await corruption_service.get_corruption_logs(
        camera_id=camera_id,
        page=page,
        page_size=page_size,
        min_score=min_score,
        max_score=max_score,
    )

    # Generate ETag based on query parameters and result metadata
    etag_data = f"{camera_id}-{page}-{page_size}-{min_score}-{max_score}"
    if result and hasattr(result, 'model_dump'):
        etag_data += f"-{result.model_dump().get('total', 0)}"
    etag = generate_content_hash_etag(etag_data)
    
    # Add moderate cache for corruption logs 
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
    response.headers["ETag"] = etag

    return ResponseFormatter.success(
        "Corruption logs retrieved successfully", data=result.model_dump()
    )


# TODO: Add SSE broadcasting to Services for real-time degraded mode updates
# No HTTP caching needed for POST operations
@router.post("/corruption/camera/{camera_id}/reset-degraded")
@handle_exceptions("reset camera degraded mode")
async def reset_camera_degraded_mode(
    camera_id: int,
    corruption_service: CorruptionServiceDep,
    camera_service: CameraServiceDep,
    db: AsyncDatabaseDep,
):
    """Reset degraded mode for a specific camera"""
    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    # Reset degraded mode
    await corruption_service.reset_camera_degraded_mode(camera_id)

    # Get updated camera info to return
    camera = await camera_service.get_camera_by_id(camera_id)

    # Create SSE event for real-time degraded mode updates
    sse_ops = SSEEventsOperations(db)
    await sse_ops.create_event(
        event_type=EVENT_CORRUPTION_DEGRADED_MODE_RESET,
        event_data={
            "camera_id": camera_id,
            "degraded_mode_active": False,
            "consecutive_corruption_failures": 0,
            "camera_name": camera.name if camera else f"Camera {camera_id}",
        },
        priority="high",
        source="api"
    )

    return ResponseFormatter.success(
        f"Camera {camera_id} degraded mode reset successfully",
        data={
            "camera_id": camera_id,
            "degraded_mode_active": False,
            "consecutive_corruption_failures": 0,
        },
    )


# TODO: No caching needed - image testing is dynamic operation
@router.post("/corruption/test-image", response_model=CorruptionTestResponse)
@handle_exceptions("test image corruption")
async def test_image_corruption(
    corruption_service: CorruptionServiceDep,
    db: AsyncDatabaseDep,
    image: UploadFile = File(..., description="Image file to test for corruption"),
):
    """Test an uploaded image for corruption detection"""
    # Read the uploaded image
    image_data = await image.read()

    # Validate image file
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Please upload an image file."
        )

    # Test corruption detection on the image - returns CorruptionTestResponse directly
    corruption_result = await corruption_service.test_image_corruption(
        image_data, filename=image.filename or "test_image"
    )

    # Create SSE event for corruption test completion
    sse_ops = SSEEventsOperations(db)
    await sse_ops.create_event(
        event_type=EVENT_CORRUPTION_TEST_COMPLETED,
        event_data={
            "filename": corruption_result.filename,
            "file_size_bytes": corruption_result.file_size_bytes,
            "image_dimensions": corruption_result.image_dimensions,
            "has_error": corruption_result.error is not None,
            "test_type": "manual_upload",
        },
        priority="normal",
        source="api"
    )

    return corruption_result


# TODO: Replace with SSE in services layer - corruption health changes with each detection
# Use very short cache (1-2 minutes max) or preferably SSE events via services layer
@router.get("/corruption/health")
@handle_exceptions("get corruption system health")
async def get_corruption_system_health(
    corruption_service: CorruptionServiceDep,
    settings_service: SettingsServiceDep,
    db: AsyncDatabaseDep,
):
    """Get corruption detection system health status"""
    try:
        # Get system stats to determine health
        stats = await corruption_service.get_system_corruption_stats()
        degraded_cameras = await corruption_service.get_degraded_cameras()

        # Calculate health metrics
        total_cameras = stats.get("total_cameras", 0)
        degraded_count = len(degraded_cameras)
        healthy_cameras = total_cameras - degraded_count

        health_status = "healthy"
        issues = []

        # Check for health issues
        if total_cameras > 0:
            degraded_percentage = (degraded_count / total_cameras) * 100

            if degraded_percentage > 50:
                health_status = "critical"
                issues.append(
                    f"Over 50% of cameras ({degraded_count}/{total_cameras}) in degraded mode"
                )
            elif degraded_percentage > 25:
                health_status = "warning"
                issues.append(
                    f"{degraded_count}/{total_cameras} cameras in degraded mode"
                )
            elif degraded_count > 0:
                health_status = "degraded"
                issues.append(f"{degraded_count} camera(s) in degraded mode")

        # Check recent detection activity
        recent_detections = stats.get("images_flagged_today", 0)
        if recent_detections > 100:  # High detection rate might indicate issues
            health_status = "warning" if health_status == "healthy" else health_status
            issues.append(
                f"High corruption detection rate: {recent_detections} images flagged today"
            )

        health_data = {
            "status": health_status,
            "total_cameras": total_cameras,
            "healthy_cameras": healthy_cameras,
            "degraded_cameras": degraded_count,
            "recent_detections": recent_detections,
            "issues": issues,
            "last_check": await get_timezone_aware_timestamp_string_async(
                settings_service
            ),
        }

        # Create SSE event for corruption health updates
        sse_ops = SSEEventsOperations(db)
        await sse_ops.create_event(
            event_type=EVENT_CORRUPTION_HEALTH_UPDATED,
            event_data={
                "health_status": health_status,
                "total_cameras": total_cameras,
                "degraded_cameras": degraded_count,
                "healthy_cameras": healthy_cameras,
                "recent_detections": recent_detections,
                "issues_count": len(issues),
            },
            priority="normal",
            source="api"
        )

        return ResponseFormatter.success(
            "Corruption system health retrieved successfully", data=health_data
        )

    except Exception as e:
        logger.error(f"Error getting corruption system health: {e}")
        return ResponseFormatter.success(
            "Corruption system health check failed",
            data={"status": "unknown", "error": str(e)},
        )
