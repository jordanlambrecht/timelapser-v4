# backend/app/routers/images.py
from fastapi import APIRouter, Query, HTTPException, Path
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional, Dict, Any, cast, List
from loguru import logger
from pathlib import Path as PathlibPath
import zipfile
import io
import os
from pydantic import BaseModel
from ..database import async_db, sync_db
from ..config import settings

router = APIRouter()


class BulkDownloadRequest(BaseModel):
    image_ids: List[int]


@router.post("/bulk-download")
async def bulk_download_images(request: BulkDownloadRequest):
    """Download multiple images as a ZIP file"""
    try:
        if not request.image_ids:
            raise HTTPException(status_code=400, detail="No image IDs provided")

        if len(request.image_ids) > 100:  # Reasonable limit
            raise HTTPException(
                status_code=400, detail="Too many images requested (max 100)"
            )

        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        project_root = PathlibPath("/Users/jordanlambrecht/dev-local/timelapser-v4")

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for image_id in request.image_ids:
                try:
                    # Get image details from database
                    image = await async_db.get_image_by_id(image_id)
                    if not image:
                        logger.warning(f"Image {image_id} not found in database")
                        continue

                    # Construct full file path
                    full_path = project_root / image["file_path"]

                    if not full_path.exists():
                        logger.warning(f"Image file not found: {full_path}")
                        continue

                    # Add file to ZIP with a clean filename
                    # Use image ID and timestamp to avoid conflicts
                    filename = (
                        f"image_{image_id}_{image.get('timestamp', 'unknown')}.jpg"
                    )
                    # Clean filename to avoid issues
                    filename = "".join(c for c in filename if c.isalnum() or c in ".-_")

                    zip_file.write(full_path, filename)

                except Exception as e:
                    logger.error(f"Error adding image {image_id} to ZIP: {e}")
                    continue

        zip_buffer.seek(0)

        # Return ZIP file as streaming response
        return StreamingResponse(
            io.BytesIO(zip_buffer.read()),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=images_bulk_download.zip"
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create bulk download: {e}")
        raise HTTPException(status_code=500, detail="Failed to create bulk download")


@router.get("/count")
async def get_image_count(
    timelapse_id: Optional[int] = Query(None, description="Filter by timelapse ID"),
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
):
    """Get image count by timelapse or camera"""
    try:
        if not timelapse_id and not camera_id:
            raise HTTPException(
                status_code=400, detail="timelapse_id or camera_id required"
            )

        try:
            with sync_db.get_connection() as conn:
                with conn.cursor() as cur:
                    if timelapse_id:
                        cur.execute(
                            "SELECT COUNT(*) as count FROM images WHERE timelapse_id = %s",
                            (timelapse_id,),
                        )
                    else:  # camera_id
                        cur.execute(
                            "SELECT COUNT(*) as count FROM images WHERE camera_id = %s",
                            (camera_id,),
                        )

                    result = cast(Optional[Dict[str, Any]], cur.fetchone())
                    count = result["count"] if result else 0
        except Exception as db_error:
            # Images table might not exist yet
            logger.warning(f"Images table query failed: {db_error}")
            count = 0

        return {"count": count}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get image count: {e}")
        # Return 0 instead of error for compatibility
        return {"count": 0}


@router.get("/debug")
async def get_debug_images():
    """Get latest images for debugging"""
    try:
        # Use async database for async endpoint
        # Get all timelapses to find images
        timelapses = await async_db.get_timelapses()
        if not timelapses:
            return {"error": "No timelapses found", "images": [], "cameras": []}

        # Get images from first timelapse
        first_timelapse_id = timelapses[0]["id"]
        images = await async_db.get_timelapse_images_paginated(
            first_timelapse_id, limit=10
        )

        return {
            "images": images[:5],  # Just return first 5 for debugging
            "timelapse_count": len(timelapses),
            "first_timelapse_id": first_timelapse_id,
            "total_images": len(images),
            "sample_image": images[0] if images else None,
        }

    except Exception as e:
        logger.error(f"Failed to get debug images: {e}")
        return {
            "error": str(e),
            "images": [],
            "cameras": [],
            "timestamp": "error",
        }


# Individual image serving endpoints
@router.get("/{image_id}/download")
async def download_image(image_id: int = Path(..., description="Image ID")):
    """Download full resolution image by ID"""
    try:
        # Get image details from database
        image = await async_db.get_image_by_id(image_id)
        if not image:
            raise HTTPException(status_code=404, detail="Image not found")

        # Construct full file path - stored paths are relative to project root
        project_root = PathlibPath("/Users/jordanlambrecht/dev-local/timelapser-v4")
        full_path = project_root / image["file_path"]

        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Image file not found")

        return FileResponse(
            path=str(full_path),
            media_type="image/jpeg",
            filename=full_path.name,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving image {image_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve image")


@router.get("/{image_id}/thumbnail")
async def get_image_thumbnail(image_id: int = Path(..., description="Image ID")):
    """Get thumbnail version of image by ID"""
    try:
        # Get image details from database
        image = await async_db.get_image_by_id(image_id)
        if not image:
            raise HTTPException(status_code=404, detail="Image not found")

        # Try thumbnail first, fall back to small, then full
        project_root = PathlibPath("/Users/jordanlambrecht/dev-local/timelapser-v4")

        if image.get("thumbnail_path"):
            thumbnail_path = project_root / image["thumbnail_path"]
            if thumbnail_path.exists():
                return FileResponse(
                    path=str(thumbnail_path),
                    media_type="image/jpeg",
                )

        if image.get("small_path"):
            small_path = project_root / image["small_path"]
            if small_path.exists():
                return FileResponse(
                    path=str(small_path),
                    media_type="image/jpeg",
                )

        # Fall back to full image
        full_path = project_root / image["file_path"]
        if full_path.exists():
            return FileResponse(
                path=str(full_path),
                media_type="image/jpeg",
            )

        raise HTTPException(status_code=404, detail="Image file not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving thumbnail for image {image_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve thumbnail")


@router.get("/{image_id}/small")
async def get_image_small(image_id: int = Path(..., description="Image ID")):
    """Get small version of image by ID"""
    try:
        # Get image details from database
        image = await async_db.get_image_by_id(image_id)
        if not image:
            raise HTTPException(status_code=404, detail="Image not found")

        # Try small first, fall back to full
        project_root = PathlibPath("/Users/jordanlambrecht/dev-local/timelapser-v4")

        if image.get("small_path"):
            small_path = project_root / image["small_path"]
            if small_path.exists():
                return FileResponse(
                    path=str(small_path),
                    media_type="image/jpeg",
                )

        # Fall back to full image
        full_path = project_root / image["file_path"]
        if full_path.exists():
            return FileResponse(
                path=str(full_path),
                media_type="image/jpeg",
            )

        raise HTTPException(status_code=404, detail="Image file not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving small image {image_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve small image")
