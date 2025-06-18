# backend/app/routers/thumbnails.py

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Generator, Dict, Any
from loguru import logger
import asyncio
import json
import os
from pathlib import Path

from ..database import sync_db, async_db
from ..thumbnail_processor import create_thumbnail_processor

router = APIRouter()

# Global state for regeneration progress
regeneration_state = {
    "active": False,
    "progress": 0,
    "total": 0,
    "current_image": "",
    "errors": 0,
    "completed": 0
}


def generate_thumbnails_for_image(thumbnail_processor, image_path: str, image_id: int) -> Dict[str, Any]:
    """Generate thumbnails for a single image using optimized Pillow processor"""
    try:
        # Get project root
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        )
        
        # Handle both absolute and relative paths
        if not image_path.startswith("/"):
            full_path = os.path.join(project_root, image_path)
        else:
            full_path = image_path

        if not os.path.exists(full_path):
            return {"success": False, "error": "Image file not found"}

        # Extract camera ID and date from path
        # Expected format: data/cameras/camera-{id}/images/YYYY-MM-DD/filename.jpg
        path_parts = Path(image_path).parts
        if len(path_parts) < 5:
            return {"success": False, "error": "Invalid image path format"}
        
        camera_id_part = path_parts[-4]  # camera-{id}
        if not camera_id_part.startswith("camera-"):
            return {"success": False, "error": "Invalid camera ID in path"}
        
        camera_id = int(camera_id_part.split("-")[1])
        date_str = path_parts[-2]  # YYYY-MM-DD
        filename = path_parts[-1]   # capture_*.jpg

        # Setup directory structure for thumbnails
        base_dir = Path(project_root) / "data" / "cameras" / f"camera-{camera_id}"
        thumbnail_output_dir = base_dir / date_str
        
        # Create thumbnail and small directories if they don't exist
        (thumbnail_output_dir / "thumbnails").mkdir(parents=True, exist_ok=True)
        (thumbnail_output_dir / "small").mkdir(parents=True, exist_ok=True)

        # Use the optimized Pillow-based thumbnail processor
        image_file_path = Path(full_path)
        thumbnail_results = thumbnail_processor.generate_thumbnails_from_file(
            image_file_path, thumbnail_output_dir
        )
        
        # Convert absolute paths to relative paths for database storage
        thumbnail_path = None
        thumbnail_size = None
        small_path = None
        small_size = None
        
        if thumbnail_results['thumbnail']:
            abs_thumb_path, thumb_size = thumbnail_results['thumbnail']
            # Convert to relative path
            rel_thumb_path = os.path.relpath(abs_thumb_path, project_root)
            thumbnail_path = rel_thumb_path
            thumbnail_size = thumb_size
            
        if thumbnail_results['small']:
            abs_small_path, small_file_size = thumbnail_results['small']
            # Convert to relative path
            rel_small_path = os.path.relpath(abs_small_path, project_root)
            small_path = rel_small_path
            small_size = small_file_size
        
        # Update database with thumbnail paths
        with sync_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE images 
                    SET thumbnail_path = %s, thumbnail_size = %s, 
                        small_path = %s, small_size = %s
                    WHERE id = %s
                    """,
                    (thumbnail_path, thumbnail_size, small_path, small_size, image_id)
                )
        
        return {
            "success": True, 
            "thumbnail_generated": thumbnail_results['thumbnail'] is not None,
            "small_generated": thumbnail_results['small'] is not None
        }
        
    except Exception as e:
        logger.error(f"Error generating thumbnails for image {image_id}: {e}")
        return {"success": False, "error": str(e)}


async def regenerate_all_thumbnails_background():
    """Background task to regenerate all thumbnails"""
    global regeneration_state
    
    try:
        regeneration_state["active"] = True
        regeneration_state["progress"] = 0
        regeneration_state["errors"] = 0
        regeneration_state["completed"] = 0
        
        # Get all images for regeneration (not just missing thumbnails)
        with sync_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, file_path, camera_id
                    FROM images 
                    ORDER BY captured_at DESC
                    """
                )
                images_to_process = cur.fetchall()
        
        regeneration_state["total"] = len(images_to_process)
        
        if regeneration_state["total"] == 0:
            regeneration_state["active"] = False
            async_db.broadcast_event({
                "type": "thumbnail_regeneration_complete",
                "message": "No images needed thumbnail regeneration"
            })
            return

        logger.info(f"Starting thumbnail regeneration for {regeneration_state['total']} images")
        
        # Initialize optimized thumbnail processor
        thumbnail_processor = create_thumbnail_processor()
        
        for i, image in enumerate(images_to_process):
            if not regeneration_state["active"]:  # Allow cancellation
                break
                
            regeneration_state["current_image"] = f"Camera {image['camera_id']} - Image {image['id']}"
            regeneration_state["progress"] = i + 1
            
            # Generate thumbnails for this image using optimized Pillow processor
            result = generate_thumbnails_for_image(thumbnail_processor, image['file_path'], image['id'])
            
            if result["success"]:
                regeneration_state["completed"] += 1
            else:
                regeneration_state["errors"] += 1
                logger.warning(f"Failed to regenerate thumbnails for image {image['id']}: {result.get('error')}")
            
            # Broadcast progress update
            async_db.broadcast_event({
                "type": "thumbnail_regeneration_progress",
                "progress": regeneration_state["progress"],
                "total": regeneration_state["total"],
                "current_image": regeneration_state["current_image"],
                "completed": regeneration_state["completed"],
                "errors": regeneration_state["errors"]
            })
            
            # Small delay to prevent overwhelming the system
            await asyncio.sleep(0.1)
        
        # Complete
        regeneration_state["active"] = False
        
        async_db.broadcast_event({
            "type": "thumbnail_regeneration_complete",
            "total": regeneration_state["total"],
            "completed": regeneration_state["completed"],
            "errors": regeneration_state["errors"]
        })
        
        logger.info(f"Thumbnail regeneration completed: {regeneration_state['completed']}/{regeneration_state['total']} successful, {regeneration_state['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error in thumbnail regeneration background task: {e}")
        regeneration_state["active"] = False
        async_db.broadcast_event({
            "type": "thumbnail_regeneration_error",
            "error": str(e)
        })


@router.post("/regenerate-all")
async def start_thumbnail_regeneration(background_tasks: BackgroundTasks):
    """Start regenerating thumbnails for all images"""
    global regeneration_state
    
    if regeneration_state["active"]:
        raise HTTPException(status_code=409, detail="Thumbnail regeneration already in progress")
    
    # Check if thumbnail generation is enabled
    settings = await async_db.get_settings_dict()
    if settings.get("generate_thumbnails", "true").lower() != "true":
        raise HTTPException(
            status_code=400, 
            detail="Thumbnail generation is disabled in settings. Enable it first."
        )
    
    # Start background task
    background_tasks.add_task(regenerate_all_thumbnails_background)
    
    return {
        "message": "Thumbnail regeneration started",
        "status": "started"
    }


@router.post("/regenerate-all/cancel")
async def cancel_thumbnail_regeneration():
    """Cancel ongoing thumbnail regeneration"""
    global regeneration_state
    
    if not regeneration_state["active"]:
        raise HTTPException(status_code=400, detail="No thumbnail regeneration in progress")
    
    regeneration_state["active"] = False
    
    async_db.broadcast_event({
        "type": "thumbnail_regeneration_cancelled",
        "message": "Thumbnail regeneration cancelled by user"
    })
    
    return {
        "message": "Thumbnail regeneration cancelled",
        "status": "cancelled"
    }


@router.get("/regenerate-all/status")
async def get_regeneration_status():
    """Get current status of thumbnail regeneration"""
    return {
        "active": regeneration_state["active"],
        "progress": regeneration_state["progress"],
        "total": regeneration_state["total"],
        "current_image": regeneration_state["current_image"],
        "errors": regeneration_state["errors"],
        "completed": regeneration_state["completed"]
    }


@router.get("/stats")
async def get_thumbnail_stats():
    """Get statistics about thumbnail coverage"""
    try:
        with sync_db.get_connection() as conn:
            with conn.cursor() as cur:
                # Get overall stats
                cur.execute(
                    """
                    SELECT 
                        COUNT(*) as total_images,
                        COUNT(thumbnail_path) as has_thumbnails,
                        COUNT(small_path) as has_small_images,
                        COUNT(CASE WHEN thumbnail_path IS NOT NULL AND small_path IS NOT NULL THEN 1 END) as has_both
                    FROM images
                    """
                )
                overall_stats = cur.fetchone()
                
                # Get per-camera stats
                cur.execute(
                    """
                    SELECT 
                        c.id as camera_id,
                        c.name as camera_name,
                        COUNT(i.id) as total_images,
                        COUNT(i.thumbnail_path) as has_thumbnails,
                        COUNT(i.small_path) as has_small_images
                    FROM cameras c
                    LEFT JOIN images i ON c.id = i.camera_id
                    GROUP BY c.id, c.name
                    ORDER BY c.id
                    """
                )
                camera_stats = cur.fetchall()
        
        return {
            "overall": overall_stats,
            "by_camera": camera_stats,
            "regeneration_active": regeneration_state["active"]
        }
        
    except Exception as e:
        logger.error(f"Error getting thumbnail stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get thumbnail statistics")
