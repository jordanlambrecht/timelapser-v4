#!/usr/bin/env python3
# backend/app/utils/cache_invalidation.py

"""
Cache Invalidation Service - Coordinates cache invalidation with SSE events.

Ensures cache coherency by invalidating stale cache entries when real-time
events indicate data changes.

Related Files:
- cache_manager.py: Core caching infrastructure and storage mechanisms
  This file contains the business logic for cache invalidation while
  cache_manager.py provides the underlying TTL-based storage, statistics,
  and caching decorators. Both work together to maintain cache coherency.
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from .cache_manager import cache, delete_cache_by_prefix, get_setting_cached


class CacheInvalidationService:
    """
    Service to invalidate cache entries based on SSE events.

    Maintains cache coherency by removing stale entries when real-time
    events indicate the underlying data has changed.
    """

    @staticmethod
    async def invalidate_latest_image_cache(camera_id: int) -> None:
        """
        Invalidate all latest-image related cache entries for a camera.

        Args:
            camera_id: ID of the camera whose cache should be invalidated
        """
        # Cache key patterns that need invalidation when new images arrive
        cache_patterns = [
            f"get_latest_image_for_camera:{camera_id}",
            f"latest_image:get_latest_image_for_camera:{camera_id}",
            f"get_camera_latest_image_unified:{camera_id}",
        ]

        invalidated_count = 0
        for pattern in cache_patterns:
            if await cache.delete(pattern):
                invalidated_count += 1

        if invalidated_count > 0:
            logger.info(
                f"🔄 Invalidated {invalidated_count} latest-image cache entries for camera {camera_id}"
            )

    @staticmethod
    async def invalidate_camera_status_cache(camera_id: int) -> None:
        """
        Invalidate camera status related cache entries.

        Args:
            camera_id: ID of the camera whose status cache should be invalidated
        """
        cache_patterns = [
            f"get_camera_by_id:{camera_id}",
            f"get_camera_status:{camera_id}",
            "get_all_cameras",  # Camera lists may be cached
        ]

        invalidated_count = 0
        for pattern in cache_patterns:
            if await cache.delete(pattern):
                invalidated_count += 1

        if invalidated_count > 0:
            logger.info(
                f"🔄 Invalidated {invalidated_count} camera status cache entries for camera {camera_id}"
            )

    @staticmethod
    async def invalidate_timelapse_cache(timelapse_id: int) -> None:
        """
        Invalidate timelapse related cache entries.

        Args:
            timelapse_id: ID of the timelapse whose cache should be invalidated
        """
        cache_patterns = [
            f"get_timelapse_by_id:{timelapse_id}",
            f"get_timelapse_status:{timelapse_id}",
            "get_all_timelapses",  # Timelapse lists may be cached
        ]

        invalidated_count = 0
        for pattern in cache_patterns:
            if await cache.delete(pattern):
                invalidated_count += 1

        if invalidated_count > 0:
            logger.info(
                f"🔄 Invalidated {invalidated_count} timelapse cache entries for timelapse {timelapse_id}"
            )

    @staticmethod
    async def invalidate_dashboard_cache() -> None:
        """
        Invalidate dashboard and statistics cache entries.

        Called when system-wide events occur that affect dashboard data.
        """
        cache_patterns = [
            "get_system_health_score",
            "get_dashboard_stats",
            "get_camera_performance",
            "get_system_statistics",
        ]

        invalidated_count = 0
        for pattern in cache_patterns:
            if await cache.delete(pattern):
                invalidated_count += 1

        if invalidated_count > 0:
            logger.info(f"🔄 Invalidated {invalidated_count} dashboard cache entries")

    @staticmethod
    async def invalidate_settings_cache(setting_key: Optional[str] = None) -> None:
        """
        Invalidate settings cache entries using enhanced cache manager.
        
        Args:
            setting_key: Optional specific setting key to invalidate.
                        If None, invalidates all settings cache entries.
        """
        if setting_key:
            # Invalidate specific setting
            cache_key = f"setting:{setting_key}"
            if await cache.delete(cache_key):
                logger.info(f"🔄 Invalidated settings cache: {setting_key}")
        else:
            # Invalidate all settings cache entries using bulk operation
            invalidated_count = await delete_cache_by_prefix("setting:")
            if invalidated_count > 0:
                logger.info(f"🔄 Invalidated {invalidated_count} settings cache entries")

    @staticmethod
    async def invalidate_all_settings_cache() -> int:
        """
        Invalidate all settings-related cache entries.
        
        Convenience function for settings cache invalidation.
        """
        return await delete_cache_by_prefix("setting:")

    @staticmethod
    async def invalidate_image_cache() -> int:
        """
        Invalidate all image-related cache entries.
        
        Convenience function for image cache invalidation.
        """
        deleted_latest = await delete_cache_by_prefix("latest_image:")
        deleted_batch = await delete_cache_by_prefix("get_images_batch:")
        return deleted_latest + deleted_batch

    @staticmethod
    async def invalidate_setting(key: str) -> bool:
        """
        Invalidate specific setting cache entry.
        
        Args:
            key: Setting key to invalidate
            
        Returns:
            True if cache entry was found and removed
        """
        try:
            cache_key = f"setting:{key}"
            success = await cache.delete(cache_key)
            if success:
                logger.info(f"🔄 Invalidated settings cache: {key}")
            return success
        except Exception as e:
            logger.error(f"❌ Failed to invalidate settings cache '{key}': {e}")
            return False

    @staticmethod
    async def refresh_setting(settings_service, key: str) -> Optional[str]:
        """
        Force refresh a specific setting by invalidating cache and reloading.
        
        Args:
            settings_service: SettingsService instance for data access
            key: Setting key to refresh
            
        Returns:
            Updated setting value
        """
        try:
            # Invalidate existing cache
            await CacheInvalidationService.invalidate_setting(key)
            
            # Reload from service (decorator handles caching)
            value = await get_setting_cached(settings_service, key)
            
            logger.info(f"🔄 Refreshed settings cache: {key}")
            return value
            
        except Exception as e:
            logger.error(f"❌ Failed to refresh settings cache '{key}': {e}")
            return None

    @staticmethod
    async def invalidate_image_batch_cache() -> None:
        """
        Invalidate image batch loading cache entries using enhanced cache manager.
        
        Called when image data changes that could affect batch loading results.
        """
        # Use enhanced cache manager function for efficient bulk deletion
        invalidated_count = await delete_cache_by_prefix("get_images_batch:")
        
        if invalidated_count > 0:
            logger.info(f"🔄 Invalidated {invalidated_count} image batch cache entries")

    @classmethod
    async def handle_sse_event(
        cls, event_type: str, event_data: Dict[str, Any]
    ) -> None:
        """
        Handle SSE events and invalidate appropriate cache entries.

        Args:
            event_type: Type of SSE event (e.g., 'image_captured')
            event_data: Event data containing relevant IDs
        """
        try:
            if event_type == "image_captured":
                camera_id = event_data.get("camera_id")
                if camera_id:
                    await cls.invalidate_latest_image_cache(camera_id)
                    # Dashboard shows latest images, so invalidate that too
                    await cls.invalidate_dashboard_cache()

            elif event_type == "camera_status_changed":
                camera_id = event_data.get("camera_id")
                if camera_id:
                    await cls.invalidate_camera_status_cache(camera_id)
                    await cls.invalidate_dashboard_cache()

            elif event_type == "timelapse_status_changed":
                timelapse_id = event_data.get("timelapse_id")
                if timelapse_id:
                    await cls.invalidate_timelapse_cache(timelapse_id)
                    await cls.invalidate_dashboard_cache()

            elif event_type in ["corruption_detected", "corruption_resolved"]:
                camera_id = event_data.get("camera_id")
                if camera_id:
                    await cls.invalidate_latest_image_cache(camera_id)
                    await cls.invalidate_dashboard_cache()

            elif event_type == "settings_updated":
                setting_key = event_data.get("setting_key")
                await cls.invalidate_settings_cache(setting_key)
                # Settings changes might affect dashboard calculations
                await cls.invalidate_dashboard_cache()

            elif event_type in ["images_batch_loaded", "image_deleted", "image_updated"]:
                # Invalidate batch cache when image data changes
                await cls.invalidate_image_batch_cache()
                
                # Also invalidate camera-specific caches if camera_id provided
                camera_id = event_data.get("camera_id")
                if camera_id:
                    await cls.invalidate_latest_image_cache(camera_id)

        except Exception as e:
            logger.error(f"❌ Cache invalidation failed for event {event_type}: {e}")


# Global instance for easy import
cache_invalidation = CacheInvalidationService()
