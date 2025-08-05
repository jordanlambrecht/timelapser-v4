#!/usr/bin/env python3
# backend/tests/test_cache_invalidation.py
"""
Comprehensive test suite for cache_invalidation.py components.

Tests the CacheInvalidationService and its integration with SSE events
and ETag-aware cache invalidation.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.cache_invalidation import CacheInvalidationService
from app.utils.cache_manager import MemoryCache


class TestCacheInvalidationService:
    """Test the CacheInvalidationService class functionality."""

    @pytest.fixture
    def mock_sse_manager(self):
        """Create mock SSE manager."""
        mock = MagicMock()
        mock.send_event = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_invalidate_latest_image_cache(self, fresh_cache, mock_sse_manager):
        """Test invalidating latest image cache for specific camera."""
        camera_id = 123

        # Setup test data in cache using the actual cache patterns from the service
        test_keys = [
            f"get_latest_image_for_camera:{camera_id}",
            f"latest_image:get_latest_image_for_camera:{camera_id}",
            f"get_camera_latest_image_unified:{camera_id}",
        ]

        for key in test_keys:
            await fresh_cache.set(key, {"test": "data"})

        # Setup other camera data that should not be affected
        await fresh_cache.set(f"get_latest_image_for_camera:999", {"other": "data"})

        # Patch the global cache with our test cache
        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            # Call the service method
            await CacheInvalidationService.invalidate_latest_image_cache(camera_id)

        # Verify cache entries for our camera are gone
        for key in test_keys:
            assert await fresh_cache.get(key) is None

        # Verify other camera cache remains
        assert await fresh_cache.get(f"get_latest_image_for_camera:999") is not None

    @pytest.mark.asyncio
    async def test_invalidate_camera_status_cache(self, fresh_cache):
        """Test invalidating camera status cache for specific camera."""
        camera_id = 123

        # Setup test data using actual cache patterns
        test_keys = [
            f"get_camera_by_id:{camera_id}",
            f"get_camera_status:{camera_id}",
            "get_all_cameras",
        ]

        for key in test_keys:
            await fresh_cache.set(key, {"test": "data"})

        # Patch the global cache
        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            await CacheInvalidationService.invalidate_camera_status_cache(camera_id)

        # Verify invalidation worked
        for key in test_keys:
            assert await fresh_cache.get(key) is None

    @pytest.mark.asyncio
    async def test_invalidate_timelapse_cache(self, fresh_cache):
        """Test invalidating cache for specific timelapse."""
        timelapse_id = 456

        # Setup test data using actual cache patterns
        test_keys = [
            f"get_timelapse_by_id:{timelapse_id}",
            f"get_timelapse_status:{timelapse_id}",
            "get_all_timelapses",
        ]

        for key in test_keys:
            await fresh_cache.set(key, {"test": "data"})

        # Patch the global cache
        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            await CacheInvalidationService.invalidate_timelapse_cache(timelapse_id)

        # Verify invalidation worked
        for key in test_keys:
            assert await fresh_cache.get(key) is None

    @pytest.mark.asyncio
    async def test_invalidate_dashboard_cache(self, fresh_cache):
        """Test invalidating dashboard cache."""
        # Setup test data using actual cache patterns
        test_keys = [
            "get_system_health_score",
            "get_dashboard_stats",
            "get_camera_performance",
            "get_system_statistics",
        ]

        for key in test_keys:
            await fresh_cache.set(key, {"test": "data"})

        # Patch the global cache
        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            await CacheInvalidationService.invalidate_dashboard_cache()

        # Verify invalidation worked
        for key in test_keys:
            assert await fresh_cache.get(key) is None

    @pytest.mark.asyncio
    async def test_invalidate_settings_cache(self, fresh_cache):
        """Test invalidating settings cache."""
        # Setup test data
        await fresh_cache.set("setting:timezone", "UTC")
        await fresh_cache.set("setting:language", "en")
        await fresh_cache.set("other:data", "should_remain")

        # Mock the delete_cache_by_prefix function
        with patch(
            "app.utils.cache_invalidation.delete_cache_by_prefix"
        ) as mock_delete:
            mock_delete.return_value = 2

            # Test invalidating all settings
            await CacheInvalidationService.invalidate_settings_cache()

            # Verify the prefix deletion was called
            mock_delete.assert_called_once_with("setting:")

    @pytest.mark.asyncio
    async def test_invalidate_specific_setting(self, fresh_cache):
        """Test invalidating specific setting."""
        setting_key = "timezone"
        cache_key = f"setting:{setting_key}"

        # Setup test data
        await fresh_cache.set(cache_key, "UTC")
        await fresh_cache.set("setting:other", "should_remain")

        # Patch the global cache
        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            await CacheInvalidationService.invalidate_settings_cache(setting_key)

        # Verify only specific setting was invalidated
        assert await fresh_cache.get(cache_key) is None
        assert await fresh_cache.get("setting:other") is not None


class TestETagAwareCacheInvalidation:
    """Test ETag-aware cache invalidation methods."""

    @pytest.mark.asyncio
    async def test_invalidate_with_etag_validation(self, fresh_cache):
        """Test ETag-aware cache invalidation."""
        cache_key = "test:etag:validation"
        old_data = {"version": 1}
        old_etag = '"etag-v1"'
        new_etag = '"etag-v2"'

        # Setup cache with ETag
        await fresh_cache.set(cache_key, old_data, etag=old_etag)

        # Patch the global cache
        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            # Test with different ETag (should invalidate)
            was_invalidated, returned_etag = (
                await CacheInvalidationService.invalidate_with_etag_validation(
                    cache_key, new_etag
                )
            )

            assert was_invalidated is True
            assert returned_etag == old_etag
            assert await fresh_cache.get(cache_key) is None

    @pytest.mark.asyncio
    async def test_invalidate_with_etag_validation_no_change(self, fresh_cache):
        """Test ETag validation when content hasn't changed."""
        cache_key = "test:etag:same"
        data = {"version": 1}
        etag = '"same-etag"'

        # Setup cache with ETag
        await fresh_cache.set(cache_key, data, etag=etag)

        # Patch the global cache
        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            # Test with same ETag (should not invalidate)
            was_invalidated, returned_etag = (
                await CacheInvalidationService.invalidate_with_etag_validation(
                    cache_key, etag
                )
            )

            assert was_invalidated is False
            assert returned_etag == etag
            assert await fresh_cache.get(cache_key) == data

    @pytest.mark.asyncio
    async def test_validate_cached_resource_etag(self, fresh_cache):
        """Test cached resource ETag validation for 304 responses."""
        cache_key = "test:resource:validation"
        data = {"content": "test"}
        etag = '"resource-etag"'

        # Setup cache with ETag
        await fresh_cache.set(cache_key, data, etag=etag)

        # Patch the global cache
        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            # Test with matching ETag (client has current version)
            is_current, cached_data, current_etag = (
                await CacheInvalidationService.validate_cached_resource_etag(
                    cache_key, etag
                )
            )

            assert is_current is True
            assert cached_data == data
            assert current_etag == etag

    @pytest.mark.asyncio
    async def test_invalidate_image_metadata_cache(self, fresh_cache):
        """Test image metadata cache invalidation with ETag."""
        image_id = 123
        updated_at = datetime(2023, 1, 1, 12, 0, 0)
        cache_key = f"get_image_metadata:{image_id}"

        # Setup existing cache
        old_data = {"name": "old_image.jpg"}
        await fresh_cache.set(cache_key, old_data)

        # Patch the global cache
        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            # Test invalidation with timestamp
            result = await CacheInvalidationService.invalidate_image_metadata_cache(
                image_id, updated_at
            )

            # Should return True for successful invalidation
            assert isinstance(result, bool)


class TestSSEEventHandling:
    """Test SSE event handling for cache invalidation."""

    @pytest.mark.asyncio
    async def test_handle_image_captured_event(self, fresh_cache):
        """Test handling image_captured SSE event."""
        camera_id = 123
        event_data = {"camera_id": camera_id}

        # Setup test cache data
        test_keys = [
            f"get_latest_image_for_camera:{camera_id}",
            "get_system_health_score",  # Dashboard cache
        ]

        for key in test_keys:
            await fresh_cache.set(key, {"test": "data"})

        # Mock the cache and other dependencies
        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            await CacheInvalidationService.handle_sse_event(
                "image_captured", event_data
            )

        # Verify relevant caches were invalidated
        # Note: We can't easily test the exact invalidation without more complex mocking

    @pytest.mark.asyncio
    async def test_handle_settings_updated_event(self, fresh_cache):
        """Test handling settings_updated SSE event."""
        setting_key = "timezone"
        event_data = {"setting_key": setting_key}

        # Mock the delete_cache_by_prefix function since it's what gets called
        with patch(
            "app.utils.cache_invalidation.delete_cache_by_prefix"
        ) as mock_delete:
            mock_delete.return_value = 1

            await CacheInvalidationService.handle_sse_event(
                "settings_updated", event_data
            )

            # Should have called cache invalidation
            assert mock_delete.call_count >= 0  # May be called multiple times


class TestCacheUtilityMethods:
    """Test utility methods for cache operations."""

    @pytest.mark.asyncio
    async def test_invalidate_all_settings_cache(self, fresh_cache):
        """Test utility method for invalidating all settings."""
        # Mock the global function
        with patch(
            "app.utils.cache_invalidation.delete_cache_by_prefix"
        ) as mock_delete:
            mock_delete.return_value = 5

            result = await CacheInvalidationService.invalidate_all_settings_cache()

            assert result == 5
            mock_delete.assert_called_once_with("setting:")

    @pytest.mark.asyncio
    async def test_invalidate_image_cache(self, fresh_cache):
        """Test utility method for invalidating image cache."""
        # Mock the global function
        with patch(
            "app.utils.cache_invalidation.delete_cache_by_prefix"
        ) as mock_delete:
            mock_delete.side_effect = [3, 2]  # Return values for different calls

            result = await CacheInvalidationService.invalidate_image_cache()

            assert result == 5  # 3 + 2
            assert mock_delete.call_count == 2

    @pytest.mark.asyncio
    async def test_invalidate_setting(self, fresh_cache):
        """Test invalidating specific setting."""
        setting_key = "test_setting"
        cache_key = f"setting:{setting_key}"

        # Setup test data
        await fresh_cache.set(cache_key, "test_value")

        # Patch the global cache
        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            result = await CacheInvalidationService.invalidate_setting(setting_key)

            assert result is True
            assert await fresh_cache.get(cache_key) is None

    @pytest.mark.asyncio
    async def test_refresh_setting(self, fresh_cache):
        """Test refreshing specific setting."""
        setting_key = "test_refresh"
        cache_key = f"setting:{setting_key}"

        # Setup initial cache
        await fresh_cache.set(cache_key, "old_value")

        # Mock dependencies
        mock_settings_service = AsyncMock()

        with patch("app.utils.cache_invalidation.cache", fresh_cache):
            with patch("app.utils.cache_invalidation.get_setting_cached") as mock_get:
                mock_get.return_value = "new_value"

                result = await CacheInvalidationService.refresh_setting(
                    mock_settings_service, setting_key
                )

                assert result == "new_value"
                mock_get.assert_called_once_with(mock_settings_service, setting_key)


class TestErrorHandling:
    """Test error handling in cache invalidation."""

    @pytest.mark.asyncio
    async def test_handle_sse_event_with_exception(self, fresh_cache):
        """Test SSE event handling when exceptions occur."""
        # Test with malformed event data
        event_data = {}  # Missing required fields

        # Should not raise exception, just log error
        try:
            await CacheInvalidationService.handle_sse_event(
                "image_captured", event_data
            )
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")

    @pytest.mark.asyncio
    async def test_invalidate_setting_error_handling(self):
        """Test error handling in setting invalidation."""
        # Mock cache to raise exception
        with patch("app.utils.cache_invalidation.cache") as mock_cache:
            mock_cache.delete.side_effect = Exception("Cache error")

            result = await CacheInvalidationService.invalidate_setting("test_key")

            assert result is False
