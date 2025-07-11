# backend/app/routers/image_serving_routers.py
"""
Image serving endpoints for thumbnails and various image sizes.

Critical endpoints required by frontend for thumbnail display.
Missing these endpoints means the frontend cannot show thumbnails.
"""

from fastapi import APIRouter, Path, Query, HTTPException, Response


from typing import Literal

from ..dependencies import ImageServiceDep, CameraServiceDep
from ..utils.router_helpers import handle_exceptions, validate_entity_exists
from ..constants import MAX_BULK_OPERATION_ITEMS

router = APIRouter()


@router.get("/api/cameras/{camera_id}/latest-image/thumbnail")
@handle_exceptions("get camera latest thumbnail")
async def get_camera_latest_thumbnail(
    response: Response,
    camera_service: CameraServiceDep,
    image_service: ImageServiceDep,
    camera_id: int = Path(..., description="Camera ID"),
):
    """
    Get the latest thumbnail image for a camera (200×150).

    Returns the most recent thumbnail with proper caching headers.
    Falls back to small → full → placeholder if thumbnail missing.
    """
    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "Camera")

    # Get latest image with thumbnail
    return await image_service.get_latest_image_with_thumbnail(camera_id)


@router.get("/api/cameras/{camera_id}/latest-image/small")
@handle_exceptions("get camera latest small image")
async def get_camera_latest_small(
    response: Response,
    camera_service: CameraServiceDep,
    image_service: ImageServiceDep,
    camera_id: int = Path(..., description="Camera ID"),
):
    """
    Get the latest small image for a camera (800×600).

    Returns the most recent small image with proper caching headers.
    Falls back to full → placeholder if small missing.
    """
    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "Camera")

    # Get latest image with small
    return await image_service.get_latest_image_with_small(camera_id)


@router.get("/api/cameras/{camera_id}/latest-image/full")
@handle_exceptions("get camera latest full image")
async def get_camera_latest_full(
    response: Response,
    camera_service: CameraServiceDep,
    image_service: ImageServiceDep,
    camera_id: int = Path(..., description="Camera ID"),
):
    """
    Get the latest full resolution image for a camera.

    Returns the most recent full image with proper caching headers.
    """
    # Validate camera exists
    await validate_entity_exists(camera_service.get_camera_by_id, camera_id, "Camera")

    # Get latest full image
    return await image_service.get_latest_full_image(camera_id)


@router.get("/api/images/{image_id}/thumbnail")
@handle_exceptions("get image thumbnail")
async def get_image_thumbnail(
    response: Response,
    image_service: ImageServiceDep,
    image_id: int = Path(..., description="Image ID"),
):
    """
    Get thumbnail for a specific image (200×150).

    Direct access to thumbnail file with 1-hour caching.
    Returns 404 if thumbnail doesn't exist.
    """
    # Get image thumbnail
    return await image_service.get_image_thumbnail_path(image_id)


@router.get("/api/images/{image_id}/small")
@handle_exceptions("get image small")
async def get_image_small(
    response: Response,
    image_service: ImageServiceDep,
    image_id: int = Path(..., description="Image ID"),
):
    """
    Get small image for a specific image (800×600).

    Direct access to small file with 1-hour caching.
    Returns 404 if small doesn't exist.
    """
    # Get image small
    return await image_service.get_image_small_path(image_id)


@router.get("/api/images/{image_id}/serve")
@handle_exceptions("serve image with size parameter")
async def serve_image_with_size(
    response: Response,
    image_service: ImageServiceDep,
    image_id: int = Path(..., description="Image ID"),
    size: Literal["thumbnail", "small", "full"] = Query(
        "full", description="Image size variant"
    ),
):
    """
    Universal image serving endpoint with size parameter.

    Serves different image variants based on size parameter:
    - thumbnail: 200×150 optimized for dashboard
    - small: 800×600 medium quality
    - full: Original resolution
    """
    # Serve image with size
    return await image_service.serve_image_with_size(image_id, size)


@router.get("/api/images/batch")
@handle_exceptions("batch image serving")
async def serve_images_batch(
    response: Response,
    image_service: ImageServiceDep,
    ids: str = Query(..., description="Comma-separated image IDs"),
    size: Literal["thumbnail", "small", "full"] = Query(
        "thumbnail", description="Image size variant"
    ),
):
    """
    Batch thumbnail serving for multiple images.

    Returns JSON array with image URLs and metadata for efficient loading.
    Used by frontend for gallery views and thumbnail grids.
    """
    try:
        image_ids = [int(id_str.strip()) for id_str in ids.split(",")]
        if len(image_ids) > MAX_BULK_OPERATION_ITEMS:
            raise HTTPException(
                status_code=413,
                detail=f"Batch size too large (max {MAX_BULK_OPERATION_ITEMS} images)",
            )

        # Serve images batch
        return await image_service.serve_images_batch(image_ids, size)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid image IDs format - must be comma-separated integers",
        )
