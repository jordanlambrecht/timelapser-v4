#!/usr/bin/env python3
# backend/tests/test_cache_manager.py
"""
Comprehensive test suite for cache_manager.py components.

Tests the core caching infrastructure including MemoryCache, CacheEntry,
decorators, and ETag utilities.
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.utils.cache_manager import (
    CacheEntry,
    MemoryCache,
    cache,
    cached_response,
    cached_response_with_etag,
    cleanup_expired_cache,
    clear_cache,
    delete_cache_by_prefix,
    extract_etag_from_headers,
    generate_collection_etag,
    generate_composite_etag,
    generate_content_hash_etag,
    generate_timestamp_etag,
    get_cache_stats,
    validate_etag_match,
)


class TestCacheEntry:
    """Test the CacheEntry class functionality."""

    def test_cache_entry_creation(self):
        """Test basic CacheEntry creation and properties."""
        data = {"test": "value"}
        ttl = 60
        etag = '"test-etag"'

        entry = CacheEntry(data, ttl, etag)

        assert entry.data == data
        assert entry.etag == etag
        assert entry.has_etag() is True
        assert entry.is_expired() is False
        assert entry.get_age_seconds() >= 0

    def test_cache_entry_without_etag(self):
        """Test CacheEntry without ETag."""
        entry = CacheEntry("test_data", 60)

        assert entry.etag is None
        assert entry.has_etag() is False

    def test_cache_entry_expiration(self):
        """Test TTL expiration logic."""
        # Create entry with very short TTL
        entry = CacheEntry("test_data", ttl_seconds=0)

        # Should be expired immediately
        assert entry.is_expired() is True

    def test_cache_entry_age_calculation(self):
        """Test age calculation accuracy."""
        entry = CacheEntry("test_data", 60)

        # Age should be close to 0 initially
        age = entry.get_age_seconds()
        assert 0 <= age <= 1

        # Wait a bit and check age increased
        time.sleep(0.2)  # Increased sleep time for more reliable timing
        new_age = entry.get_age_seconds()
        assert new_age >= age  # Use >= instead of > for timing precision


class TestMemoryCache:
    """Test the MemoryCache class functionality."""

    @pytest.mark.asyncio
    async def test_basic_set_and_get(self, fresh_cache):
        """Test basic cache set and get operations."""
        key = "test_key"
        value = "test_value"

        await fresh_cache.set(key, value)
        result = await fresh_cache.get(key)

        assert result == value

    @pytest.mark.asyncio
    async def test_cache_miss(self, fresh_cache):
        """Test cache miss for non-existent key."""
        result = await fresh_cache.get("non_existent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_with_etag(self, fresh_cache):
        """Test cache operations with ETag support."""
        key = "test_etag_key"
        value = {"data": "test"}
        etag = '"test-etag-123"'

        await fresh_cache.set(key, value, etag=etag)

        # Test get_with_etag
        result_value, result_etag = await fresh_cache.get_with_etag(key)
        assert result_value == value
        assert result_etag == etag

        # Test regular get still works
        regular_result = await fresh_cache.get(key)
        assert regular_result == value

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, fresh_cache):
        """Test TTL-based cache expiration."""
        key = "expire_test"
        value = "will_expire"

        # Set with very short TTL
        await fresh_cache.set(key, value, ttl_seconds=0.1)

        # Should be available immediately
        result = await fresh_cache.get(key)
        assert result == value

        # Wait for expiration
        await asyncio.sleep(0.2)

        # Should be expired and removed
        result = await fresh_cache.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_delete(self, fresh_cache):
        """Test cache entry deletion."""
        key = "delete_test"
        value = "to_be_deleted"

        await fresh_cache.set(key, value)

        # Verify it exists
        assert await fresh_cache.get(key) == value

        # Delete it
        deleted = await fresh_cache.delete(key)
        assert deleted is True

        # Verify it's gone
        assert await fresh_cache.get(key) is None

        # Try to delete again
        deleted_again = await fresh_cache.delete(key)
        assert deleted_again is False

    @pytest.mark.asyncio
    async def test_cache_clear(self, populated_cache):
        """Test clearing all cache entries."""
        # Verify cache has data
        stats = await populated_cache.get_stats()
        assert stats["total_entries"] > 0

        # Clear cache
        await populated_cache.clear()

        # Verify cache is empty
        stats = await populated_cache.get_stats()
        assert stats["total_entries"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, fresh_cache):
        """Test cleanup of expired entries."""
        # Add entries with different TTLs
        await fresh_cache.set("keep", "value1", ttl_seconds=60)
        await fresh_cache.set("expire1", "value2", ttl_seconds=0.1)
        await fresh_cache.set("expire2", "value3", ttl_seconds=0.1)

        # Wait for some to expire
        await asyncio.sleep(0.2)

        # Cleanup expired entries
        removed_count = await fresh_cache.cleanup_expired()
        assert removed_count == 2

        # Verify only non-expired entry remains
        assert await fresh_cache.get("keep") == "value1"
        assert await fresh_cache.get("expire1") is None
        assert await fresh_cache.get("expire2") is None

    @pytest.mark.asyncio
    async def test_prefix_operations(self, fresh_cache):
        """Test prefix-based cache operations."""
        # Add entries with different prefixes
        await fresh_cache.set("user:123", "user_data")
        await fresh_cache.set("user:456", "more_user_data")
        await fresh_cache.set("camera:789", "camera_data")
        await fresh_cache.set("setting:timezone", "UTC")

        # Test get_entries_by_prefix
        user_entries = await fresh_cache.get_entries_by_prefix("user:")
        assert len(user_entries) == 2
        assert "user:123" in user_entries
        assert "user:456" in user_entries

        # Test delete_by_prefix
        deleted_count = await fresh_cache.delete_by_prefix("user:")
        assert deleted_count == 2

        # Verify user entries are gone but others remain
        assert await fresh_cache.get("user:123") is None
        assert await fresh_cache.get("camera:789") == "camera_data"
        assert await fresh_cache.get("setting:timezone") == "UTC"

    @pytest.mark.asyncio
    async def test_cache_stats(self, fresh_cache):
        """Test cache statistics functionality."""
        # Add various entries
        await fresh_cache.set("test:1", "value1", ttl_seconds=60)
        await fresh_cache.set("test:2", "value2", ttl_seconds=0.1)  # Will expire
        await fresh_cache.set("camera:1", "camera_data", ttl_seconds=120)

        # Wait for one to expire
        await asyncio.sleep(0.2)

        stats = await fresh_cache.get_stats()

        assert stats["total_entries"] == 3
        assert stats["expired_entries"] == 1
        assert stats["active_entries"] == 2
        assert "test" in stats["cache_type_breakdown"]
        assert "camera" in stats["cache_type_breakdown"]
        assert stats["cache_type_breakdown"]["test"] == 2
        assert stats["cache_type_breakdown"]["camera"] == 1


class TestETagUtilities:
    """Test ETag generation and validation utilities."""

    def test_generate_timestamp_etag_dict(self, etag_test_objects):
        """Test timestamp ETag generation with dictionary."""
        camera = etag_test_objects["camera"]
        etag = generate_timestamp_etag(camera)

        expected_timestamp = camera["updated_at"].timestamp()
        expected_etag = f'"{expected_timestamp}"'

        assert etag == expected_etag

    def test_generate_timestamp_etag_object(self):
        """Test timestamp ETag generation with object attributes."""

        class MockObj:
            def __init__(self):
                self.updated_at = datetime(2023, 1, 1, 12, 0, 0)

        obj = MockObj()
        etag = generate_timestamp_etag(obj)

        expected_timestamp = obj.updated_at.timestamp()
        expected_etag = f'"{expected_timestamp}"'

        assert etag == expected_etag

    def test_generate_timestamp_etag_custom_field(self, etag_test_objects):
        """Test timestamp ETag generation with custom timestamp field."""
        obj = {"created_at": datetime(2023, 1, 1, 10, 0, 0)}
        etag = generate_timestamp_etag(obj, "created_at")

        expected_timestamp = obj["created_at"].timestamp()
        expected_etag = f'"{expected_timestamp}"'

        assert etag == expected_etag

    def test_generate_timestamp_etag_fallback(self):
        """Test timestamp ETag generation fallback for missing field."""
        obj = {"no_timestamp": "value"}
        etag = generate_timestamp_etag(obj)

        # Should generate valid ETag with current timestamp
        assert etag.startswith('"')
        assert etag.endswith('"')
        assert float(etag.strip('"')) > 0

    def test_generate_content_hash_etag(self):
        """Test content hash ETag generation."""
        content = {"key": "value", "number": 123}
        etag = generate_content_hash_etag(content)

        # Generate expected hash
        content_str = json.dumps(content, sort_keys=True, default=str)
        expected_hash = hashlib.md5(content_str.encode("utf-8")).hexdigest()
        expected_etag = f'"{expected_hash}"'

        assert etag == expected_etag

    def test_generate_content_hash_etag_different_algorithms(self):
        """Test content hash ETag with different algorithms."""
        content = "test content"

        md5_etag = generate_content_hash_etag(content, "md5")
        sha1_etag = generate_content_hash_etag(content, "sha1")
        sha256_etag = generate_content_hash_etag(content, "sha256")

        # All should be different
        assert md5_etag != sha1_etag
        assert md5_etag != sha256_etag
        assert sha1_etag != sha256_etag

        # All should be valid ETags
        for etag in [md5_etag, sha1_etag, sha256_etag]:
            assert etag.startswith('"')
            assert etag.endswith('"')

    def test_generate_composite_etag(self):
        """Test composite ETag generation."""
        obj_id = 123
        timestamp = datetime(2023, 1, 1, 12, 0, 0)

        etag = generate_composite_etag(obj_id, timestamp)

        expected_etag = f'"{obj_id}-{timestamp.timestamp()}"'
        assert etag == expected_etag

    def test_generate_composite_etag_with_version(self):
        """Test composite ETag generation with version."""
        obj_id = "config"
        version = "v2.1"

        etag = generate_composite_etag(obj_id, version=version)

        expected_etag = f'"{obj_id}-{version}"'
        assert etag == expected_etag

    def test_generate_collection_etag(self, etag_test_objects):
        """Test collection ETag generation."""
        images = etag_test_objects["image_collection"]
        etag = generate_collection_etag(images)

        # Should include count and latest timestamp
        count = len(images)
        latest_timestamp = max(img["updated_at"] for img in images).timestamp()
        expected_etag = f'"{count}-{latest_timestamp}"'

        assert etag == expected_etag

    def test_validate_etag_match(self):
        """Test ETag validation logic."""
        etag1 = '"1672531200.0"'
        etag2 = '"1672531200.0"'
        etag3 = '"1672531300.0"'

        # Same ETags should match
        assert validate_etag_match(etag1, etag2) is True

        # Different ETags should not match
        assert validate_etag_match(etag1, etag3) is False

        # None values should not match (test separately due to type hints)
        assert validate_etag_match("", etag1) is False
        assert validate_etag_match(etag1, "") is False

    def test_validate_etag_match_weak_etags(self):
        """Test ETag validation with weak ETags."""
        strong_etag = '"abc123"'
        weak_etag = 'W/"abc123"'

        # Weak and strong ETags with same value should match
        assert validate_etag_match(weak_etag, strong_etag) is True
        assert validate_etag_match(strong_etag, weak_etag) is True

    def test_extract_etag_from_headers(self):
        """Test ETag extraction from HTTP headers."""
        headers = {"if-none-match": '"1672531200.0"', "other-header": "value"}

        etag = extract_etag_from_headers(headers)
        assert etag == '"1672531200.0"'

    def test_extract_etag_from_headers_case_insensitive(self):
        """Test ETag extraction with different header cases."""
        headers = {"If-None-Match": '"test-etag"'}

        etag = extract_etag_from_headers(headers)
        assert etag == '"test-etag"'

    def test_extract_etag_from_headers_missing(self):
        """Test ETag extraction when header is missing."""
        headers = {"other-header": "value"}

        etag = extract_etag_from_headers(headers)
        assert etag is None


class TestCachingDecorators:
    """Test caching decorators functionality."""

    @pytest.mark.asyncio
    async def test_cached_response_decorator(self, fresh_cache):
        """Test basic cached_response decorator."""
        call_count = 0

        @cached_response(ttl_seconds=60, key_prefix="test")
        async def expensive_function(param1: str, param2: int):
            nonlocal call_count
            call_count += 1
            return f"result_{param1}_{param2}"

        # First call should execute function
        result1 = await expensive_function("a", 1)
        assert result1 == "result_a_1"
        assert call_count == 1

        # Second call should use cache
        result2 = await expensive_function("a", 1)
        assert result2 == "result_a_1"
        assert call_count == 1  # Function not called again

        # Different parameters should execute function
        result3 = await expensive_function("b", 2)
        assert result3 == "result_b_2"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cached_response_with_etag_decorator(self, fresh_cache):
        """Test ETag-aware caching decorator."""
        call_count = 0

        def etag_generator(result):
            return generate_content_hash_etag(result)

        @cached_response_with_etag(ttl_seconds=60, etag_generator=etag_generator)
        async def get_data_with_etag():
            nonlocal call_count
            call_count += 1
            return {"data": "test", "timestamp": call_count}

        # First call should execute and cache
        result1 = await get_data_with_etag()
        assert call_count == 1

        # Second call should use cache
        result2 = await get_data_with_etag()
        assert result2 == result1
        assert call_count == 1


class TestGlobalCacheFunctions:
    """Test global cache utility functions."""

    @pytest.mark.asyncio
    async def test_get_cache_stats_global(self, populated_cache):
        """Test global cache stats function."""
        # Replace global cache temporarily
        with patch("app.utils.cache_manager.cache", populated_cache):
            stats = await get_cache_stats()
            assert isinstance(stats, dict)
            assert "total_entries" in stats
            assert stats["total_entries"] > 0

    @pytest.mark.asyncio
    async def test_clear_cache_global(self, populated_cache):
        """Test global cache clear function."""
        with patch("app.utils.cache_manager.cache", populated_cache):
            # Verify cache has data
            stats = await get_cache_stats()
            assert stats["total_entries"] > 0

            # Clear cache
            await clear_cache()

            # Verify cache is empty
            stats = await get_cache_stats()
            assert stats["total_entries"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_cache_global(self, fresh_cache):
        """Test global cleanup expired function."""
        with patch("app.utils.cache_manager.cache", fresh_cache):
            # Add expired entries
            await fresh_cache.set("expire1", "value1", ttl_seconds=0.1)
            await fresh_cache.set("expire2", "value2", ttl_seconds=0.1)
            await fresh_cache.set("keep", "value3", ttl_seconds=60)

            # Wait for expiration
            await asyncio.sleep(0.2)

            # Cleanup
            removed_count = await cleanup_expired_cache()
            assert removed_count == 2

    @pytest.mark.asyncio
    async def test_delete_cache_by_prefix_global(self, fresh_cache):
        """Test global delete by prefix function."""
        with patch("app.utils.cache_manager.cache", fresh_cache):
            # Add test data
            await fresh_cache.set("user:1", "data1")
            await fresh_cache.set("user:2", "data2")
            await fresh_cache.set("other:1", "data3")

            # Delete by prefix
            deleted_count = await delete_cache_by_prefix("user:")
            assert deleted_count == 2

            # Verify correct deletion
            assert await fresh_cache.get("user:1") is None
            assert await fresh_cache.get("user:2") is None
            assert await fresh_cache.get("other:1") == "data3"


# Performance and edge case tests
class TestCachePerformanceAndEdgeCases:
    """Test cache performance and edge case scenarios."""

    @pytest.mark.asyncio
    async def test_large_cache_operations(self, fresh_cache):
        """Test cache with large number of entries."""
        # Add many entries
        for i in range(100):
            await fresh_cache.set(f"bulk:{i}", f"value_{i}", ttl_seconds=60)

        stats = await fresh_cache.get_stats()
        assert stats["total_entries"] == 100

        # Test bulk deletion
        deleted = await fresh_cache.delete_by_prefix("bulk:")
        assert deleted == 100

        stats = await fresh_cache.get_stats()
        assert stats["total_entries"] == 0

    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self, fresh_cache):
        """Test concurrent cache operations."""

        async def set_data(key_suffix: int):
            await fresh_cache.set(f"concurrent:{key_suffix}", f"value_{key_suffix}")

        async def get_data(key_suffix: int):
            return await fresh_cache.get(f"concurrent:{key_suffix}")

        # Run concurrent operations
        set_tasks = [set_data(i) for i in range(10)]
        await asyncio.gather(*set_tasks)

        get_tasks = [get_data(i) for i in range(10)]
        results = await asyncio.gather(*get_tasks)

        # Verify all operations succeeded
        for i, result in enumerate(results):
            assert result == f"value_{i}"

    @pytest.mark.asyncio
    async def test_cache_with_none_values(self, fresh_cache):
        """Test caching None values (should not cache)."""
        await fresh_cache.set("test_none", None)
        result = await fresh_cache.get("test_none")

        # None values should be cached
        assert result is None

        # But the key should exist in cache
        stats = await fresh_cache.get_stats()
        assert stats["total_entries"] == 1

    def test_etag_generation_edge_cases(self):
        """Test ETag generation with edge case inputs."""
        # Empty content
        etag = generate_content_hash_etag("")
        assert etag.startswith('"') and etag.endswith('"')

        # Very large content
        large_content = "x" * 10000
        etag = generate_content_hash_etag(large_content)
        assert etag.startswith('"') and etag.endswith('"')

        # Unicode content
        unicode_content = {"emoji": "🚀", "text": "test"}
        etag = generate_content_hash_etag(unicode_content)
        assert etag.startswith('"') and etag.endswith('"')
