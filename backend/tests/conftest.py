#!/usr/bin/env python3
# backend/tests/conftest.py
"""
Pytest configuration and shared fixtures for Timelapser v4 tests.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any

from app.utils.cache_manager import MemoryCache, CacheEntry
from app.utils.cache_invalidation import CacheInvalidationService


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def fresh_cache():
    """Provide a fresh MemoryCache instance for each test."""
    cache = MemoryCache()
    yield cache
    await cache.clear()


@pytest.fixture
def cache_invalidation_service():
    """Provide a CacheInvalidationService instance."""
    return CacheInvalidationService()


@pytest.fixture
def sample_cache_data():
    """Provide sample data for cache testing."""
    return {
        "simple_string": "test_value",
        "complex_dict": {
            "id": 123,
            "name": "Test Camera",
            "updated_at": datetime.now(),
            "metadata": {"key": "value"},
        },
        "list_data": [1, 2, 3, 4, 5],
        "timestamp_obj": {
            "updated_at": datetime(2023, 1, 1, 12, 0, 0),
            "created_at": datetime(2023, 1, 1, 10, 0, 0),
        },
    }


@pytest.fixture
def etag_test_objects():
    """Provide objects for ETag testing."""
    return {
        "camera": {
            "id": 123,
            "name": "Test Camera",
            "updated_at": datetime(2023, 1, 1, 12, 0, 0),
        },
        "settings": {
            "timezone": "UTC",
            "capture_interval": 30,
            "updated_at": datetime(2023, 1, 2, 14, 30, 0),
        },
        "image_collection": [
            {"id": 1, "updated_at": datetime(2023, 1, 1, 12, 0, 0)},
            {"id": 2, "updated_at": datetime(2023, 1, 2, 13, 0, 0)},
            {"id": 3, "updated_at": datetime(2023, 1, 3, 14, 0, 0)},
        ],
    }


@pytest.fixture
async def populated_cache(fresh_cache, sample_cache_data):
    """Provide a cache pre-populated with test data."""
    cache = fresh_cache

    # Add various types of cached data
    await cache.set("test:string", sample_cache_data["simple_string"], ttl_seconds=60)
    await cache.set("test:dict", sample_cache_data["complex_dict"], ttl_seconds=120)
    await cache.set("test:list", sample_cache_data["list_data"], ttl_seconds=180)

    # Add data with ETags
    await cache.set(
        "test:with_etag",
        sample_cache_data["timestamp_obj"],
        ttl_seconds=300,
        etag='"1672596000.0"',
    )

    # Add short TTL data for expiration testing
    await cache.set("test:short_ttl", "expires_soon", ttl_seconds=1)

    yield cache


class MockAsyncContext:
    """Mock async context manager for testing."""

    def __init__(self, return_value=None):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_settings_service():
    """Mock settings service for cache testing."""

    class MockSettingsService:
        def __init__(self):
            self.settings = {
                "timezone": "UTC",
                "capture_interval": 30,
                "data_directory": "/test/data",
            }

        async def get_setting(self, key: str, default=None):
            return self.settings.get(key, default)

        async def get_all_settings(self):
            return self.settings.copy()

        def get_setting_sync(self, key: str, default=None):
            return self.settings.get(key, default)

    return MockSettingsService()


# Helper functions for testing
def assert_cache_hit(cache_result, expected_value):
    """Assert that cache returned expected value (cache hit)."""
    assert cache_result is not None
    assert cache_result == expected_value


def assert_cache_miss(cache_result):
    """Assert that cache returned None (cache miss)."""
    assert cache_result is None


def wait_for_expiration(seconds: float = 1.1):
    """Wait for cache entries to expire."""
    time.sleep(seconds)


# Test data generators
def generate_test_cameras(count: int = 3):
    """Generate test camera data."""
    cameras = []
    base_time = datetime(2023, 1, 1, 12, 0, 0)

    for i in range(count):
        cameras.append(
            {
                "id": i + 1,
                "name": f"Camera {i + 1}",
                "status": "online" if i % 2 == 0 else "offline",
                "updated_at": base_time + timedelta(hours=i),
                "health_status": "healthy",
            }
        )

    return cameras


def generate_test_images(camera_id: int, count: int = 5):
    """Generate test image data for a camera."""
    images = []
    base_time = datetime(2023, 1, 1, 12, 0, 0)

    for i in range(count):
        images.append(
            {
                "id": i + 1,
                "camera_id": camera_id,
                "file_path": f"/data/camera_{camera_id}/image_{i+1}.jpg",
                "captured_at": base_time + timedelta(minutes=i * 30),
                "updated_at": base_time + timedelta(minutes=i * 30 + 5),
                "file_size": 1024 * (i + 1),
            }
        )

    return images
