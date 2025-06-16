from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Dict, Any, cast
from loguru import logger
from ..database import sync_db

router = APIRouter()


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
        with sync_db.get_connection() as conn:
            with conn.cursor() as cur:
                # Get latest images for debugging
                cur.execute(
                    """
                    SELECT id, camera_id, file_path, captured_at
                    FROM images
                    ORDER BY captured_at DESC
                    LIMIT 10
                    """
                )
                images = cast(list, cur.fetchall())

                # Get cameras with last image path
                cur.execute(
                    """
                    SELECT c.id, c.name, c.last_image_id, i.file_path as last_image_path
                    FROM cameras c
                    LEFT JOIN images i ON c.last_image_id = i.id
                    """
                )
                cameras = cast(list, cur.fetchall())

        return {
            "images": images,
            "cameras": cameras,
            "timestamp": "2024-01-01T00:00:00Z",
        }

    except Exception as e:
        logger.error(f"Failed to get debug images: {e}")
        # Return empty data instead of error for compatibility
        return {
            "images": [],
            "cameras": [],
            "timestamp": "error",
        }
