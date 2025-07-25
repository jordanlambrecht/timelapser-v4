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

from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Query, HTTPException, status, Response
from pydantic import BaseModel, Field, field_validator

from ..dependencies import ImageServiceDep

from ..models.image_model import Image
from ..models.shared_models import BulkDownloadResponse
from ..utils.router_helpers import handle_exceptions
from ..utils.response_helpers import ResponseFormatter
from ..utils.file_helpers import create_file_response
from ..utils.cache_manager import (
    generate_composite_etag,
    generate_content_hash_etag,
)
from ..constants import IMAGE_SIZE_VARIANTS, CACHE_CONTROL_PUBLIC

# NOTE: CACHING STRATEGY - IMPLEMENTED THROUGHOUT THIS FILE
# Images are immutable content with aggressive caching implemented:
# - Image files: Long cache (1 year) + ETag - implemented in serve endpoints
# - Image metadata: ETag + moderate cache (5-10 min) - implemented in metadata endpoints  
# - Dynamic operations (bulk downloads, deletion): No cache + SSE broadcasting - implemented
# This caching strategy is fully implemented across all endpoints below.
router = APIRouter(tags=["images"])


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


class BatchImageRequest(BaseModel):
    """Request model for batch image loading"""
    
    image_ids: List[int] = Field(
        ..., min_length=1, max_length=1000, description="List of image IDs to load"
    )
    
    @field_validator('image_ids')
    @classmethod
    def validate_image_ids(cls, v):
        """Validate that all image IDs are positive integers"""
        if not all(id > 0 for id in v):
            raise ValueError("All image IDs must be positive integers")
        return v


# ====================================================================
# IMAGE METADATA ENDPOINTS
# ====================================================================


# Removed /images GET endpoint per decision: "DEPRECATE BACKEND - Unnecessary API surface area"
# Use scoped endpoints like /images/camera/{id} and /timelapses/{id}/images instead


# IMPLEMENTED: ETag + 5 minute cache (count changes when images added/removed)
# ETag based on latest image timestamp + total count
@router.get("/images/count")
@handle_exceptions("get image count")
async def get_image_count(
    response: Response,
    image_service: ImageServiceDep,
    camera_id: Optional[int] = Query(None),
    timelapse_id: Optional[int] = Query(None),
):
    """Get total count of images with optional filtering"""
    # Use get_images with filters and count the results
    images_result = await image_service.get_images(
        camera_id=camera_id, timelapse_id=timelapse_id, page=1, page_size=1
    )
    total_count = (
        images_result.get("total", 0) if isinstance(images_result, dict) else 0
    )

    # Generate ETag based on count and filter parameters for cache validation
    etag_data = f"count-{total_count}-{camera_id}-{timelapse_id}"
    etag = generate_content_hash_etag(etag_data)

    # Add moderate cache for count data
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=300"  # 5 minutes
    response.headers["ETag"] = etag

    return ResponseFormatter.success(
        "Image count retrieved successfully",
        data={
            "count": total_count,
            "camera_id": camera_id,
            "timelapse_id": timelapse_id,
        },
    )


# IMPLEMENTED: ETag + long cache (image metadata never changes after creation)
# ETag = f'"{image.id}-{image.updated_at.timestamp()}"'
@router.get("/images/{image_id}")
@handle_exceptions("get image")
async def get_image(response: Response, image_id: int, image_service: ImageServiceDep):
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

    # Generate ETag based on image ID and captured timestamp
    etag = generate_composite_etag(image.id, image.captured_at)

    # Add long cache for immutable image metadata
    response.headers["Cache-Control"] = "public, max-age=3600, s-maxage=3600"  # 1 hour
    response.headers["ETag"] = etag

    return ResponseFormatter.success(
        message="Image retrieved successfully",
        data=image.model_dump(),
        entity_type="image",
        entity_id=image_id,
    )


# ====================================================================
# IMAGE SERVING ENDPOINTS
# ====================================================================


# Removed /images/camera/{camera_id}/latest endpoint per decision: "DEPRECATE BACKEND - Remove legacy endpoint"
# Use unified /cameras/{camera_id}/latest-image system instead


# IMPLEMENTED: long cache + ETag for immutable image files
# Cache-Control: public, max-age=31536000, immutable + ETag based on image.id
@router.get("/images/{image_id}/serve")
@handle_exceptions("serve image")
async def serve_image(
    response: Response,
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

    # Generate ETag based on image ID and size for immutable content cache validation
    etag = generate_content_hash_etag(f"{image_id}-{size}")

    # Add aggressive cache for immutable image files
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # 1 year
    response.headers["ETag"] = etag

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


@router.delete("/images/{image_id}")
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

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        message="Image deleted successfully",
        entity_type="image",
        entity_id=image_id,
        operation="delete",
    )


# ====================================================================
# STATISTICS ENDPOINTS
# ====================================================================


# Moved camera statistics endpoint to cameras namespace per decision: "MOVE TO CAMERAS NAMESPACE"
# Camera image statistics now available at /cameras/{camera_id}/statistics


# Removed /images/timelapse/{timelapse_id}/statistics endpoint per decision: "DEPRECATE BACKEND - Remove duplicate functionality"
# Timelapse statistics are available through camera statistics and main timelapse endpoints


# ====================================================================
# BULK OPERATIONS
# ====================================================================


@router.post("/images/batch")
@handle_exceptions("batch load images")
async def get_images_batch(
    request: BatchImageRequest,
    image_service: ImageServiceDep,
    size: str = Query("thumbnail", description="thumbnail|small|original"),
):
    """Batch load multiple images/thumbnails in single request"""
    images = await image_service.get_images_batch(request.image_ids, size)

    # Convert Pydantic models to dicts for ResponseFormatter compatibility
    # NOTE: Required because ResponseFormatter expects Dict/List, not Pydantic models
    images_data = [image.model_dump() for image in images]

    # SSE broadcasting handled by service layer (proper architecture)

    return ResponseFormatter.success(
        message="Images batch retrieved successfully",
        data={
            "images": images_data,
            "size": size,
            "requested_count": len(request.image_ids),
            "loaded_count": len(images),
        },
    )


@router.post("/images/bulk/download", response_model=BulkDownloadResponse)
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

    # SSE broadcasting handled by service layer (proper architecture)

    bulk_response = BulkDownloadResponse(
        requested_images=bulk_result["requested_images"],
        included_images=bulk_result["included_images"],
        filename=bulk_result["filename"],
        total_size=bulk_result.get("total_size"),
        zip_data=bulk_result.get("zip_data"),
    )
    
    return ResponseFormatter.success(
        message="Bulk download prepared successfully",
        data=bulk_response.model_dump(),
        entity_type="bulk_download",
        operation="create",
    )


# ====================================================================
# THUMBNAIL AND QUALITY ENDPOINTS
# ====================================================================


# Removed quality-assessment endpoint per decision: "DEPRECATE BACKEND - Include quality data in main image endpoint"
# Quality assessment data is now included in the main /images/{image_id} GET endpoint via Image model


# IMPLEMENTED: long cache + ETag for immutable image files
# Cache-Control: public, max-age=31536000, immutable + ETag based on image.id
@router.get("/images/{image_id}/small")
@handle_exceptions("serve small image")
async def serve_small_image(
    response: Response, image_id: int, image_service: ImageServiceDep
):
    """Serve small/medium-sized version of an image (800x600)"""
    # Delegate to service layer for file preparation
    serving_result = await image_service.prepare_image_for_serving(image_id, "small")
    if not serving_result.get("success"):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if "not found" in serving_result.get("error", "").lower()
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=serving_result.get(
                "error", "Failed to prepare small image for serving"
            ),
        )

    # Generate ETag based on image ID and size for immutable content cache validation
    etag = generate_content_hash_etag(f"{image_id}-small")

    # Add aggressive cache for immutable image files
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # 1 year
    response.headers["ETag"] = etag

    return create_file_response(
        file_path=serving_result["file_path"],
        media_type=serving_result["media_type"],
        headers={
            "Cache-Control": CACHE_CONTROL_PUBLIC,
            "X-Image-ID": str(image_id),
            "X-Image-Size": "small",
        },
    )


# IMPLEMENTED: long cache + ETag for immutable thumbnail files
# Cache-Control: public, max-age=31536000, immutable + ETag based on image.id
@router.get("/images/{image_id}/thumbnail")
@handle_exceptions("serve thumbnail image")
async def serve_thumbnail_image(
    response: Response, image_id: int, image_service: ImageServiceDep
):
    """Serve thumbnail version of an image (200x150)"""
    # Delegate to service layer for file preparation
    serving_result = await image_service.prepare_image_for_serving(
        image_id, "thumbnail"
    )
    if not serving_result.get("success"):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
                if "not found" in serving_result.get("error", "").lower()
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=serving_result.get(
                "error", "Failed to prepare thumbnail for serving"
            ),
        )

    # Generate ETag based on image ID and size for immutable content cache validation
    etag = generate_content_hash_etag(f"{image_id}-thumbnail")

    # Add aggressive cache for immutable thumbnail files
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # 1 year
    response.headers["ETag"] = etag

    return create_file_response(
        file_path=serving_result["file_path"],
        media_type=serving_result["media_type"],
        headers={
            "Cache-Control": CACHE_CONTROL_PUBLIC,
            "X-Image-ID": str(image_id),
            "X-Image-Size": "thumbnail",
        },
    )


# @router.get("/images/{path:path}")
# @handle_exceptions("serve dynamic image path")
# async def serve_dynamic_image_path(path: str, image_service: ImageServiceDep):
#     """Serve images by dynamic file path (for frontend compatibility)"""
#     return await image_service.serve_image_by_path(path)
