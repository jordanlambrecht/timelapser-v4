#!/usr/bin/env python3
"""
Test script to debug thumbnail regeneration endpoints
"""

import asyncio
import sys
import traceback
from app.database import async_db
from app.services.image_service import ImageService
from app.services.settings_service import SettingsService


async def test_image_service():
    """Test ImageService methods directly"""
    try:
        print("🔧 Initializing database...")
        await async_db.initialize()
        
        print("🔧 Creating services...")
        settings_service = SettingsService(async_db)
        image_service = ImageService(async_db, settings_service)
        
        print("🔧 Testing get_images_for_regeneration...")
        images = await image_service.get_images_for_regeneration(5)
        print(f"✅ Found {len(images)} images for regeneration")
        if images:
            print(f"   First image: {images[0]}")
        
        print("🔧 Testing start_thumbnail_regeneration...")
        result = await image_service.start_thumbnail_regeneration(5)
        print(f"✅ Start result: {result}")
        
        print("🔧 Testing get_thumbnail_regeneration_status...")
        status = await image_service.get_thumbnail_regeneration_status()
        print(f"✅ Status result: {status}")
        
        print("🔧 Testing cancel_thumbnail_regeneration...")
        cancel_result = await image_service.cancel_thumbnail_regeneration()
        print(f"✅ Cancel result: {cancel_result}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
    finally:
        print("🔧 Closing database...")
        await async_db.close()


if __name__ == "__main__":
    asyncio.run(test_image_service())