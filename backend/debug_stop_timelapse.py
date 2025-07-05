#!/usr/bin/env python3
"""
Debug script to identify the stop timelapse issue.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.core import AsyncDatabase
from app.database.camera_operations import AsyncCameraOperations
from app.models.camera_model import Camera
from app.config import settings
from loguru import logger

async def debug_stop_timelapse():
    """Debug the stop timelapse issue"""
    
    # Initialize database
    db = AsyncDatabase()
    await db.initialize()
    
    # Create camera operations
    camera_ops = AsyncCameraOperations(db, None)  # No settings service for this test
    
    try:
        # Test the update_camera call that's failing
        camera_id = 1
        camera_data = {"active_timelapse_id": None}
        
        logger.info(f"Testing update_camera with camera_id={camera_id}, data={camera_data}")
        
        # Check Camera model fields
        logger.info(f"Camera.model_fields keys: {list(Camera.model_fields.keys())}")
        logger.info(f"Has active_timelapse_id: {'active_timelapse_id' in Camera.model_fields}")
        
        # Try the update
        result = await camera_ops.update_camera(camera_id, camera_data)
        logger.info(f"Update result type: {type(result)}")
        logger.info(f"Update result: {result}")
        
    except Exception as e:
        logger.error(f"Error during update_camera: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(debug_stop_timelapse())