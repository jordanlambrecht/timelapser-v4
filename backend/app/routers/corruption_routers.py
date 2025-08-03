# backend/app/routers/corruption_routers.py
"""
Corruption detection management HTTP endpoints.

Role: Corruption detection management HTTP endpoints
Responsibilities: Corruption statistics, degraded mode management,
                corruption settings configuration
Interactions: Uses corruption pipeline services for business logic, provides quality metrics
            and audit trail access
"""

from typing import Optional
from fastapi import APIRouter, Query, UploadFile, File, HTTPException, Response
from ..services.logger import get_service_logger
from ..enums import LoggerName

logger = get_service_logger(LoggerName.API)

from ..dependencies import (
    CameraServiceDep,
    SettingsServiceDep,
    AsyncDatabaseDep,
)
from ..services.corruption_pipeline.services.evaluation_service import (
    CorruptionEvaluationService,
)
from ..services.corruption_pipeline.services.statistics_service import (
    CorruptionStatisticsService,
)
from ..services.corruption_pipeline.services.health_service import (
    CorruptionHealthService,
)

# NOTE: Some operations still use database operations directly until
# they are moved into the corruption pipeline services
from ..database.corruption_operations import CorruptionOperations
from ..utils.cache_manager import (
    generate_content_hash_etag,
)
from ..models.corruption_model import (
    CorruptionHistoryResponse,
    CorruptionSettings,
    CorruptionLogEntry,
    CorruptionTestResponse,
)
from ..utils.response_helpers import ResponseFormatter
from ..utils.router_helpers import validate_entity_exists, handle_exceptions
from ..utils.validation_helpers import process_uploaded_image_for_corruption_test
from ..constants import (
    DEFAULT_CORRUPTION_HISTORY_HOURS,
    DEFAULT_CORRUPTION_LOGS_PAGE_SIZE,
    MAX_CORRUPTION_LOGS_PAGE_SIZE,
)

router = APIRouter()


# IMPLEMENTED: ETag + 10 minute cache (corruption stats change slowly)
# ETag based on latest corruption log timestamp + total count
@router.get("/corruption/stats")
@handle_exceptions("get corruption system stats")
async def get_corruption_system_stats(response: Response, db: AsyncDatabaseDep):
    """Get system-wide corruption detection statistics"""
    statistics_service = CorruptionStatisticsService(db)
    stats = await statistics_service.get_system_statistics()

    # Generate ETag based on stats content for cache validation
    etag = generate_content_hash_etag(stats)

    # Add moderate cache for corruption statistics
    response.headers["Cache-Control"] = (
        "public, max-age=600, s-maxage=600"  # 10 minutes
    )
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
    camera_service: CameraServiceDep,
    db: AsyncDatabaseDep,
):
    """Get corruption statistics for a specific camera"""
    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    statistics_service = CorruptionStatisticsService(db)
    stats = await statistics_service.get_camera_statistics(camera_id)

    # Generate ETag based on camera ID and stats content
    etag = generate_content_hash_etag(f"{camera_id}-{stats}")

    # Add longer cache for camera corruption statistics
    response.headers["Cache-Control"] = (
        "public, max-age=900, s-maxage=900"  # 15 minutes
    )
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
    camera_service: CameraServiceDep,
    db: AsyncDatabaseDep,
    hours: Optional[int] = Query(
        DEFAULT_CORRUPTION_HISTORY_HOURS,
        description="Number of hours of history to retrieve",
    ),
):
    """Get corruption detection history for a camera"""
    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    hours_int = hours if hours is not None else DEFAULT_CORRUPTION_HISTORY_HOURS
    corruption_ops = CorruptionOperations(db)
    history = await corruption_ops.get_camera_corruption_history(
        camera_id, hours=hours_int
    )

    # Generate ETag based on camera ID, hours, and history content
    etag = generate_content_hash_etag(
        f"{camera_id}-{hours_int}-{len(history) if history else 0}"
    )

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
async def get_corruption_settings(
    response: Response, settings_service: SettingsServiceDep
):
    """Get corruption detection settings"""
    settings = await settings_service.get_corruption_settings()

    # Generate ETag based on settings content for cache validation
    etag = generate_content_hash_etag(
        settings.model_dump() if hasattr(settings, "model_dump") else settings.__dict__
    )

    # Add long cache for settings (change infrequently)
    response.headers["Cache-Control"] = (
        "public, max-age=1200, s-maxage=1200"  # 20 minutes
    )
    response.headers["ETag"] = etag

    return ResponseFormatter.success(
        "Corruption detection settings retrieved successfully",
        data=(
            settings.model_dump()
            if hasattr(settings, "model_dump")
            else settings.__dict__
        ),
    )


@router.put("/corruption/settings")
@handle_exceptions("update corruption settings")
async def update_corruption_settings(
    settings_data: dict, settings_service: SettingsServiceDep
):
    """Update corruption detection settings"""
    # Extract global settings from the request
    global_settings = settings_data.get("global_settings", {})

    # Update individual settings through settings service
    updated_settings = {}
    for key, value in global_settings.items():
        success = await settings_service.set_setting(key, value)
        if success:
            updated_settings[key] = value

    return ResponseFormatter.success(
        "Corruption detection settings updated successfully", data=updated_settings
    )


# IMPLEMENTED: ETag + 5 minute cache (corruption logs grow but slowly)
# ETag based on latest corruption log timestamp + page + filters
@router.get("/corruption/logs")
@handle_exceptions("get corruption logs")
async def get_corruption_logs(
    response: Response,
    camera_service: CameraServiceDep,
    db: AsyncDatabaseDep,
    camera_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(
        DEFAULT_CORRUPTION_LOGS_PAGE_SIZE, ge=1, le=MAX_CORRUPTION_LOGS_PAGE_SIZE
    ),
    min_score: Optional[int] = Query(None, ge=0, le=100),
    max_score: Optional[int] = Query(None, ge=0, le=100),
):
    """Get corruption detection logs with pagination and filtering"""
    # Validate camera if specified
    if camera_id:
        await validate_entity_exists(
            camera_service.get_camera_by_id, camera_id, "camera"
        )

    corruption_ops = CorruptionOperations(db)
    logs = await corruption_ops.get_corruption_logs(
        camera_id=camera_id,
        page=page,
        page_size=page_size,
        min_score=min_score,
        max_score=max_score,
    )

    # Generate ETag based on filter parameters and page info
    etag = generate_content_hash_etag(
        f"{camera_id}-{page}-{page_size}-{min_score}-{max_score}-{logs.total_count}"
    )

    # Add short cache for logs (they grow over time)
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
    response.headers["ETag"] = etag

    return ResponseFormatter.success(
        "Corruption logs retrieved successfully",
        data=logs.model_dump() if hasattr(logs, "model_dump") else logs.__dict__,
    )


# No HTTP caching needed for POST operations
@router.post("/corruption/camera/{camera_id}/reset-degraded")
@handle_exceptions("reset camera degraded mode")
async def reset_camera_degraded_mode(
    camera_id: int,
    camera_service: CameraServiceDep,
    db: AsyncDatabaseDep,
):
    """Reset degraded mode for a specific camera"""
    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "camera")

    corruption_ops = CorruptionOperations(db)
    success = await corruption_ops.reset_camera_degraded_mode(camera_id)

    if success:
        return ResponseFormatter.success(
            f"Degraded mode reset successfully for camera {camera_id}"
        )
    else:
        return ResponseFormatter.error(
            f"Failed to reset degraded mode for camera {camera_id}"
        )


# TODO: No caching needed - image testing is dynamic operation
@router.post("/corruption/test-image", response_model=CorruptionTestResponse)
@handle_exceptions("test image corruption")
async def test_image_corruption(
    db: AsyncDatabaseDep,
    image: UploadFile = File(..., description="Image file to test for corruption"),
):
    """Test an uploaded image for corruption detection"""
    try:
        # Delegate file processing to validation helpers
        result_data = await process_uploaded_image_for_corruption_test(image, db)

        test_result = CorruptionTestResponse(**result_data)

        return ResponseFormatter.success(
            "Image corruption test completed successfully",
            data=(
                test_result.model_dump()
                if hasattr(test_result, "model_dump")
                else test_result.__dict__
            ),
        )

    except Exception as e:
        # Error handling delegated to validation helpers (includes cleanup)
        raise HTTPException(status_code=400, detail=f"Image test failed: {str(e)}")


# Use very short cache (1-2 minutes max) or preferably SSE events via services layer
@router.get("/system-health")
@handle_exceptions("get system health")
async def get_system_health(db: AsyncDatabaseDep):
    """Get current system health overview."""
    health_service = CorruptionHealthService(db)
    health_data = await health_service.get_system_health_overview()
    return ResponseFormatter.success(
        "System health retrieved successfully", data=health_data
    )
