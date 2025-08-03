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

from datetime import datetime
from typing import Any, Dict, Optional, Union

from ..enums import SSEEvent

# logger = get_service_logger(LoggerName.SYSTEM)  # Commented out to avoid circular import
from .cache_manager import (
    cache,
    delete_cache_by_prefix,
    generate_collection_etag,
    generate_composite_etag,
    generate_timestamp_etag,
    get_setting_cached,
    validate_etag_match,
)

# from ..services.logger import get_service_logger, LogEmoji  # Commented out to avoid circular import


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
            # logger.info(f"🔄 Invalidated {invalidated_count} latest-image cache entries for camera {camera_id}")
            pass

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
            # logger.info(f"🔄 Invalidated {invalidated_count} camera status cache entries for camera {camera_id}")
            pass

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
            # logger.info(f"🔄 Invalidated {invalidated_count} timelapse cache entries for timelapse {timelapse_id}")
            pass

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
            # logger.info(f"🔄 Invalidated {invalidated_count} dashboard cache entries")
            pass

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
                # logger.info(f"🔄 Invalidated settings cache: {setting_key}")
                pass
        else:
            # Invalidate all settings cache entries using bulk operation
            invalidated_count = await delete_cache_by_prefix("setting:")
            if invalidated_count > 0:
                # logger.info(f"🔄 Invalidated {invalidated_count} settings cache entries")
                pass

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
                # logger.info(f"🔄 Invalidated settings cache: {key}")
                pass
            return success
        except Exception:
            # logger.error(f"❌ Failed to invalidate settings cache '{key}': {e}")
            pass
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

            # logger.info(f"🔄 Refreshed settings cache: {key}")
            pass
            return value

        except Exception:
            # logger.error(f"❌ Failed to refresh settings cache '{key}': {e}")
            pass
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
            # logger.info(f"🔄 Invalidated {invalidated_count} image batch cache entries")
            pass

    @classmethod
    async def handle_sse_event(
        cls, event_type: SSEEvent, event_data: Dict[str, Any]
    ) -> None:
        """
        Handle SSE events and invalidate appropriate cache entries.

        Args:
            event_type: Type of SSE event (e.g., 'image_captured')
            event_data: Event data containing relevant IDs
        """
        try:
            if event_type == SSEEvent.IMAGE_CAPTURED:
                camera_id = event_data.get("camera_id")
                if camera_id:
                    await cls.invalidate_latest_image_cache(camera_id)
                    # Dashboard shows latest images, so invalidate that too
                    await cls.invalidate_dashboard_cache()

            elif event_type == SSEEvent.CAMERA_STATUS_CHANGED:
                camera_id = event_data.get("camera_id")
                if camera_id:
                    await cls.invalidate_camera_status_cache(camera_id)
                    await cls.invalidate_dashboard_cache()

            elif event_type == SSEEvent.TIMELAPSE_STATUS_UPDATED:
                timelapse_id = event_data.get("timelapse_id")
                if timelapse_id:
                    await cls.invalidate_timelapse_cache(timelapse_id)
                    await cls.invalidate_dashboard_cache()

            elif event_type in [
                SSEEvent.CORRUPTION_DETECTED,
                SSEEvent.CORRUPTION_RESOLVED,
            ]:
                camera_id = event_data.get("camera_id")
                if camera_id:
                    await cls.invalidate_latest_image_cache(camera_id)
                    await cls.invalidate_dashboard_cache()

            elif event_type == SSEEvent.SETTINGS_UPDATED:
                setting_key = event_data.get("setting_key")
                await cls.invalidate_settings_cache(setting_key)
                # Settings changes might affect dashboard calculations
                await cls.invalidate_dashboard_cache()

            elif event_type in [
                SSEEvent.IMAGES_BATCH_LOADED,
                SSEEvent.IMAGE_DELETED,
                SSEEvent.IMAGE_UPDATED,
            ]:
                # Invalidate batch cache when image data changes
                await cls.invalidate_image_batch_cache()

                # Also invalidate camera-specific caches if camera_id provided
                camera_id = event_data.get("camera_id")
                if camera_id:
                    await cls.invalidate_latest_image_cache(camera_id)

        except Exception:
            # logger.error(f"❌ Cache invalidation failed for event {event_type}: {e}")
            pass

    # ════════════════════════════════════════════════════════════════════════════════
    # ETag-Aware Cache Invalidation Methods
    # ════════════════════════════════════════════════════════════════════════════════

    @staticmethod
    async def invalidate_with_etag_validation(
        cache_key: str, current_etag: str, force: bool = False
    ) -> tuple[bool, Optional[str]]:
        """
        Invalidate cache entry only if ETag has changed (smart invalidation).

        This prevents unnecessary cache invalidation when content hasn't actually changed,
        following the caching strategy's ETag validation pattern.

        Args:
            cache_key: Cache key to check/invalidate
            current_etag: Current ETag for the resource
            force: Force invalidation regardless of ETag match

        Returns:
            Tuple of (was_invalidated, old_etag)

        Examples:
            >>> await invalidate_with_etag_validation("settings:timezone", '"1672531200.0"')
            (True, '"1672531100.0"')  # Cache was stale, invalidated

            >>> await invalidate_with_etag_validation("settings:timezone", '"1672531200.0"')
            (False, '"1672531200.0"')  # Cache was current, not invalidated
        """
        try:
            # Get current cached entry with ETag
            cached_data, cached_etag = await cache.get_with_etag(cache_key)

            if cached_data is None:
                # logger.debug(f"🔍 No cached entry for ETag validation: {cache_key}")
                pass
                return False, None

            # Check if ETags match (content unchanged)
            if (
                not force
                and cached_etag
                and validate_etag_match(cached_etag, current_etag)
            ):
                # logger.debug(f"✅ ETag match, cache still valid: {cache_key}")
                pass
                return False, cached_etag

            # ETags don't match or forced invalidation - remove from cache
            invalidated = await cache.delete(cache_key)

            if invalidated:
                # logger.info(f"🔄 ETag-based cache invalidation: {cache_key} (old: {cached_etag}, new: {current_etag})")
                pass

            return invalidated, cached_etag

        except Exception:
            # logger.error(f"❌ ETag validation failed for {cache_key}: {e}")
            return False, None

    @staticmethod
    async def invalidate_image_metadata_cache(
        image_id: int, updated_at: Optional[datetime] = None
    ) -> bool:
        """
        Invalidate image metadata cache with ETag validation.

        Follows the pattern from image_routers.py TODOs:
        ETag = f'"{image.id}-{image.updated_at.timestamp()}"'

        Args:
            image_id: ID of the image whose metadata cache should be invalidated
            updated_at: Optional timestamp for ETag generation

        Returns:
            True if cache was invalidated, False if still valid
        """
        try:
            cache_key = f"get_image_metadata:{image_id}"

            if updated_at:
                current_etag = generate_composite_etag(image_id, updated_at)
                invalidated, old_etag = (
                    await CacheInvalidationService.invalidate_with_etag_validation(
                        cache_key, current_etag
                    )
                )

                if invalidated:
                    # logger.info(f"🔄 Image metadata cache invalidated: {image_id}")
                    pass

                return invalidated
            else:
                # Force invalidation if no timestamp provided
                invalidated = await cache.delete(cache_key)
                if invalidated:
                    # logger.info(f"🔄 Image metadata cache force invalidated: {image_id}")
                    pass
                return invalidated

        except Exception:
            # logger.error(f"❌ Image metadata cache invalidation failed: {e}")
            return False

    @staticmethod
    async def invalidate_settings_with_etag(
        settings_data: Union[dict, Any], setting_key: Optional[str] = None
    ) -> int:
        """
        Invalidate settings cache with ETag validation for efficiency.

        Uses timestamp-based ETag generation as specified in caching strategy.

        Args:
            settings_data: Settings object/dict with updated_at timestamp
            setting_key: Optional specific setting key to invalidate

        Returns:
            Number of cache entries invalidated
        """
        try:
            if setting_key:
                # Invalidate specific setting with ETag validation
                cache_key = f"setting:{setting_key}"
                current_etag = generate_timestamp_etag(settings_data)

                invalidated, old_etag = (
                    await CacheInvalidationService.invalidate_with_etag_validation(
                        cache_key, current_etag
                    )
                )

                return 1 if invalidated else 0
            else:
                # For bulk invalidation, use prefix-based approach
                # Individual ETag validation would be too expensive
                invalidated_count = await delete_cache_by_prefix("setting:")

                if invalidated_count > 0:
                    # logger.info(f"🔄 Bulk settings cache invalidation: {invalidated_count} entries")
                    pass

                return invalidated_count

        except Exception:
            # logger.error(f"❌ Settings ETag invalidation failed: {e}")
            return 0

    @staticmethod
    async def invalidate_image_collection_cache(
        camera_id: Optional[int] = None,
        latest_image_data: Optional[dict] = None,
        total_count: Optional[int] = None,
    ) -> bool:
        """
        Invalidate image collection/count caches with ETag validation.

        Follows the pattern from image_routers.py TODOs:
        "ETag based on latest image timestamp + total count"

        Args:
            camera_id: Optional camera ID for camera-specific collections
            latest_image_data: Latest image data for ETag generation
            total_count: Total image count for ETag generation

        Returns:
            True if any cache entries were invalidated
        """
        try:
            cache_patterns = []

            if camera_id:
                cache_patterns.extend(
                    [
                        f"get_images_for_camera:{camera_id}",
                        f"get_image_count:{camera_id}",
                    ]
                )
            else:
                cache_patterns.extend(
                    [
                        "get_all_images",
                        "get_total_image_count",
                    ]
                )

            invalidated_any = False

            for cache_key in cache_patterns:
                if latest_image_data and total_count:
                    # Generate collection ETag for validation
                    current_etag = generate_collection_etag(
                        [latest_image_data], "total_count"
                    )

                    invalidated, old_etag = (
                        await CacheInvalidationService.invalidate_with_etag_validation(
                            cache_key, current_etag
                        )
                    )

                    if invalidated:
                        invalidated_any = True
                else:
                    # Force invalidation if no ETag data provided
                    if await cache.delete(cache_key):
                        invalidated_any = True

            if invalidated_any:
                # camera_info = f" for camera {camera_id}" if camera_id else ""
                # logger.info(f"🔄 Image collection cache invalidated{camera_info}")
                pass

            return invalidated_any

        except Exception:
            # logger.error(f"❌ Image collection cache invalidation failed: {e}")
            return False

    @staticmethod
    async def validate_cached_resource_etag(
        cache_key: str, request_etag: Optional[str]
    ) -> tuple[bool, Optional[Any], Optional[str]]:
        """
        Validate cached resource against request ETag (for 304 responses).

        Used in routers to check if client has current version:
        ```python
        is_current, data, etag = await validate_cached_resource_etag(cache_key, request_etag)
        if is_current:
            return Response(status_code=304)
        ```

        Args:
            cache_key: Cache key to check
            request_etag: ETag from client's If-None-Match header

        Returns:
            Tuple of (is_current, cached_data, current_etag)
        """
        try:
            cached_data, cached_etag = await cache.get_with_etag(cache_key)

            if cached_data is None or cached_etag is None:
                # logger.debug(f"🔍 No cached data with ETag for: {cache_key}")
                pass
                return False, None, None

            # Validate ETag match
            is_current = validate_etag_match(request_etag, cached_etag)

            if is_current:
                # logger.debug(f"✅ Client has current version: {cache_key}")
                pass
            else:
                # logger.debug(f"🔄 Client version outdated: {cache_key}")
                pass

            return is_current, cached_data, cached_etag

        except Exception:
            # logger.error(f"❌ ETag validation failed for {cache_key}: {e}")
            return False, None, None

    @classmethod
    async def handle_sse_event_with_etag(
        cls,
        event_type: SSEEvent,
        event_data: Dict[str, Any],
        force_invalidation: bool = False,
    ) -> None:
        """
        Enhanced SSE event handler with ETag-aware cache invalidation.

        Provides more intelligent cache invalidation by checking ETags before
        invalidating cache entries, reducing unnecessary cache churn.

        Args:
            event_type: Type of SSE event
            event_data: Event data containing relevant IDs and timestamps
            force_invalidation: Skip ETag validation and force invalidation
        """
        try:
            if event_type == "image_captured":
                camera_id = event_data.get("camera_id")
                image_data = event_data.get("image_data", {})

                if camera_id:
                    # Smart invalidation with ETag validation
                    await cls.invalidate_image_collection_cache(
                        camera_id, image_data, image_data.get("total_count")
                    )
                    await cls.invalidate_latest_image_cache(camera_id)

            elif event_type == "settings_updated":
                setting_key = event_data.get("setting_key")
                settings_data = event_data.get("settings_data", {})

                # Use ETag-aware settings invalidation
                await cls.invalidate_settings_with_etag(settings_data, setting_key)

            elif event_type == "image_metadata_updated":
                image_id = event_data.get("image_id")
                updated_at = event_data.get("updated_at")

                if image_id:
                    await cls.invalidate_image_metadata_cache(image_id, updated_at)

            else:
                # Fallback to regular invalidation for other events
                await cls.handle_sse_event(event_type, event_data)

        except Exception:
            # logger.error(f"❌ ETag-aware cache invalidation failed for event {event_type}: {e}")
            pass
            # Fallback to regular invalidation
            await cls.handle_sse_event(event_type, event_data)


# Global instance for easy import
cache_invalidation = CacheInvalidationService()
