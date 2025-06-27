# backend/app/routers/image_routers.py
"""
Image metadata and serving HTTP endpoints.

Role: Image metadata and serving HTTP endpoints
Responsibilities: Image metadata queries, thumbnail serving with cascading fallbacks,
                 image statistics
Interactions: Uses ImageService for business logic, serves files directly from
             filesystem with proper headers
"""
# NOTE: THIS FILE SHOULD NOT CONTAIN ANY BUSINESS LOGIC.

import io
from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..dependencies import ImageServiceDep
from ..models.image_model import (
    ImageWithDetails,
    ThumbnailRegenerationResponse,
    ImageStatisticsResponse,
    BulkDownloadResponse,
    QualityAssessmentResponse,
)
from ..utils.router_helpers import handle_exceptions
from ..utils.response_helpers import ResponseFormatter, SSEEventManager
from ..utils.file_helpers import create_file_response
from ..utils.timezone_utils import get_timezone_aware_timestamp_string_async
from ..constants import IMAGE_SIZE_VARIANTS, CACHE_CONTROL_PUBLIC

router = APIRouter(prefix="/images", tags=["images"])


# ====================================================================
# REQUEST MODELS
# ====================================================================


class BulkDownloadRequest(BaseModel):
    """Request model for bulk image download"""

    image_ids: List[int] = Field(
        min_length=1, max_length=1000, description="List of image IDs to download"
    )
    zip_filename: Optional[str] = Field(
        None, description="Custom filename for ZIP file"
    )


# ====================================================================
# IMAGE METADATA ENDPOINTS
# ====================================================================


@router.get("/", response_model=List[ImageWithDetails])
@handle_exceptions("get images")
async def get_images(
    image_service: ImageServiceDep,
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
    timelapse_id: Optional[int] = Query(None, description="Filter by timelapse ID"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of images to return"
    ),
    offset: int = Query(0, ge=0, description="Number of images to skip"),
):
    """
    Get images with optional filtering by camera or timelapse.

    Supports pagination and filtering. Returns detailed image information
    including camera and timelapse context.
    """
    # Calculate page from offset and limit
    page = (offset // limit) + 1

    result = await image_service.get_images(
        camera_id=camera_id,
        timelapse_id=timelapse_id,
        page=page,
        page_size=limit,
        order_by="captured_at",
        order_dir="DESC",
    )

    return result.get("images", [])


@router.get("/{image_id}", response_model=ImageWithDetails)
@handle_exceptions("get image")
async def get_image(image_id: int, image_service: ImageServiceDep):
    """
    Get detailed image metadata by ID.

    Returns comprehensive image information including camera and timelapse context,
    corruption scores, and file metadata.
    """
    image = await image_service.get_image_by_id(image_id)
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )
    return image


# ====================================================================
# IMAGE SERVING ENDPOINTS
# ====================================================================


@router.get("/camera/{camera_id}/latest")
@handle_exceptions("serve camera latest image")
async def serve_camera_latest_image(
    camera_id: int,
    image_service: ImageServiceDep,
    size: str = Query(
        "full", description=f"Image size: {', '.join(IMAGE_SIZE_VARIANTS)}"
    ),
):
    """
    Serve the latest image for a camera.

    Automatically selects the most recent image for the specified camera
    with size variant support and cascading fallbacks.
    """
    latest_image = await image_service.get_latest_image_for_camera(camera_id)
    if not latest_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No images found for this camera",
        )

    # Delegate to service layer for file preparation
    serving_result = await image_service.prepare_image_for_serving(
        latest_image.id, size
    )
    if not serving_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=serving_result.get("error", "Failed to prepare image for serving"),
        )

    return create_file_response(
        file_path=serving_result["file_path"],
        media_type=serving_result["media_type"],
        headers={
            "Cache-Control": CACHE_CONTROL_PUBLIC,
            "X-Image-ID": str(latest_image.id),
            "X-Image-Size": size,
        },
    )


@router.get("/{image_id}/serve")
@handle_exceptions("serve image")
async def serve_image(
    image_id: int,
    image_service: ImageServiceDep,
    size: str = Query(
        "full", description=f"Image size: {', '.join(IMAGE_SIZE_VARIANTS)}"
    ),
):
    """
    Serve an image file by ID with size variant support.

    Supports automatic fallback from thumbnail -> small -> full size
    based on availability. Includes proper caching headers and security validation.
    """
    # Delegate to service layer for file preparation
    serving_result = await image_service.prepare_image_for_serving(image_id, size)
    if not serving_result.get("success"):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if "not found" in serving_result.get("error", "").lower()
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=serving_result.get("error", "Failed to prepare image for serving"),
        )

    return create_file_response(
        file_path=serving_result["file_path"],
        media_type=serving_result["media_type"],
        headers={
            "Cache-Control": CACHE_CONTROL_PUBLIC,
            "X-Image-ID": str(image_id),
            "X-Image-Size": size,
        },
    )


# ====================================================================
# IMAGE MANAGEMENT ENDPOINTS
# ====================================================================


@router.delete("/{image_id}")
@handle_exceptions("delete image")
async def delete_image(image_id: int, image_service: ImageServiceDep):
    """
    Delete an image and its associated files.

    Removes the image record from the database and attempts to clean up
    associated thumbnail and image files from the filesystem.
    """
    success = await image_service.delete_image(image_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )

    # Broadcast SSE event for real-time updates
    SSEEventManager.broadcast_event(
        {
            "type": "image_deleted",
            "data": {"image_id": image_id},
            "timestamp": await get_timezone_aware_timestamp_string_async(
                image_service.db
            ),
        }
    )

    return ResponseFormatter.success(
        message="Image deleted successfully",
        entity_type="image",
        entity_id=image_id,
        operation="delete",
    )


# ====================================================================
# STATISTICS ENDPOINTS
# ====================================================================


@router.get("/camera/{camera_id}/statistics", response_model=ImageStatisticsResponse)
@handle_exceptions("get camera image statistics")
async def get_camera_image_statistics(camera_id: int, image_service: ImageServiceDep):
    """
    Get comprehensive image statistics for a camera.

    Includes total image counts, corruption statistics, file size metrics,
    and quality assessment data.
    """
    stats = await image_service.calculate_image_statistics(camera_id=camera_id)
    if not stats or "error" in stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found or no images available",
        )

    return ResponseFormatter.success(
        message="Camera image statistics retrieved successfully",
        data=stats,
        camera_id=camera_id,
    )


@router.get(
    "/timelapse/{timelapse_id}/statistics", response_model=ImageStatisticsResponse
)
@handle_exceptions("get timelapse image statistics")
async def get_timelapse_image_statistics(
    timelapse_id: int, image_service: ImageServiceDep
):
    """
    Get comprehensive image statistics for a timelapse.

    Includes day-by-day breakdowns, capture consistency metrics,
    and quality assessment summaries.
    """
    stats = await image_service.calculate_image_statistics(timelapse_id=timelapse_id)
    if not stats or "error" in stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timelapse not found or no images available",
        )

    return ResponseFormatter.success(
        message="Timelapse image statistics retrieved successfully",
        data=stats,
        timelapse_id=timelapse_id,
    )


# ====================================================================
# BULK OPERATIONS
# ====================================================================


@router.post("/bulk/download", response_model=BulkDownloadResponse)
@handle_exceptions("bulk download images")
async def bulk_download_images(
    request: BulkDownloadRequest, image_service: ImageServiceDep
):
    """
    Download multiple images as a ZIP file.

    Creates a ZIP archive containing the requested images with clean filenames.
    Supports up to 1000 images per request with proper error handling for
    missing or inaccessible files.
    """
    # Delegate to service layer for ZIP preparation
    bulk_result = await image_service.prepare_bulk_download(
        image_ids=request.image_ids, zip_filename=request.zip_filename
    )

    if not bulk_result.get("success"):
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
                if "No image IDs" in bulk_result.get("error", "")
                else status.HTTP_404_NOT_FOUND
            ),
            detail=bulk_result.get("error", "Bulk download preparation failed"),
        )

    # Broadcast SSE event for bulk operation tracking
    SSEEventManager.broadcast_event(
        {
            "type": "bulk_download_completed",
            "data": {
                "requested_images": bulk_result["requested_images"],
                "included_images": bulk_result["included_images"],
                "filename": bulk_result["filename"],
            },
            "timestamp": await get_timezone_aware_timestamp_string_async(
                image_service.db
            ),
        }
    )

    return StreamingResponse(
        io.BytesIO(bulk_result["zip_data"]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={bulk_result['filename']}",
            "X-Total-Images": str(bulk_result["included_images"]),
            "X-Requested-Images": str(bulk_result["requested_images"]),
            "X-Total-Size": str(bulk_result.get("total_size", 0)),
        },
    )


# ====================================================================
# THUMBNAIL AND QUALITY ENDPOINTS
# ====================================================================


@router.post(
    "/{image_id}/regenerate-thumbnails", response_model=ThumbnailRegenerationResponse
)
@handle_exceptions("regenerate thumbnails")
async def regenerate_thumbnails(image_id: int, image_service: ImageServiceDep):
    """
    Force regeneration of thumbnails for an image.

    Useful for fixing corrupted thumbnails or updating thumbnail quality.
    Uses the ImageService coordination for proper thumbnail management.
    """
    result = await image_service.coordinate_thumbnail_generation(
        image_id=image_id, force_regenerate=True
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Thumbnail regeneration failed: {result.error}",
        )

    # Create response model
    response_data = ThumbnailRegenerationResponse(
        image_id=image_id,
        thumbnail_path=result.thumbnail_path,
        small_path=result.small_path,
        thumbnail_size=result.thumbnail_size,
        small_size=result.small_size,
        thumbnail_generated=bool(result.thumbnail_path),
        small_generated=bool(result.small_path),
    )

    # Broadcast SSE event for real-time updates
    SSEEventManager.broadcast_event(
        {
            "type": "thumbnails_regenerated",
            "data": {
                "image_id": image_id,
                "thumbnail_generated": response_data.thumbnail_generated,
                "small_generated": response_data.small_generated,
            },
            "timestamp": await get_timezone_aware_timestamp_string_async(
                image_service.db
            ),
        }
    )

    return response_data


@router.get("/{image_id}/quality-assessment", response_model=QualityAssessmentResponse)
@handle_exceptions("get image quality assessment")
async def get_image_quality_assessment(image_id: int, image_service: ImageServiceDep):
    """
    Get detailed quality assessment for an image.

    Provides corruption scores, quality metrics, and analysis details
    from the integrated corruption detection system.
    """
    quality_result = await image_service.coordinate_quality_assessment(image_id)

    if not quality_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quality assessment failed: {quality_result.get('error', 'Unknown error')}",
        )

    # Create response model
    response_data = QualityAssessmentResponse(
        image_id=image_id,
        quality_score=quality_result.get("quality_score", 0),
        corruption_detected=quality_result.get("corruption_detected", False),
        analysis_details=quality_result.get("analysis_details"),
        action_taken=quality_result.get("action_taken"),
        processing_time_ms=quality_result.get("processing_time_ms"),
    )

    return response_data
