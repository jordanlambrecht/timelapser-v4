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


# ====================================================================
# THUMBNAIL SYSTEM TEST FIXTURES
# ====================================================================


@pytest.fixture
def mock_sync_database():
    """Mock synchronous database for worker testing."""

    class MockSyncDatabase:
        def __init__(self):
            self.connection_active = True

        def get_connection(self):
            return MockAsyncContext(self)

        def execute(self, query, params=None):
            # Mock cursor with rowcount
            class MockCursor:
                rowcount = 1

            return MockCursor()

        def fetch_one(self, query, params=None):
            return {"id": 1, "status": "completed"}

        def fetch_all(self, query, params=None):
            return [{"id": 1, "status": "pending"}]

    return MockSyncDatabase()


@pytest.fixture
def mock_async_database():
    """Mock async database for service testing."""

    class MockAsyncDatabase:
        def __init__(self):
            self.connection_active = True

        def get_connection(self):
            return MockAsyncContext(self)

        async def execute(self, query, *params):
            return None

        async def fetch_one(self, query, *params):
            return {"id": 1, "status": "completed"}

        async def fetch_all(self, query, *params):
            return [{"id": 1, "status": "pending"}]

    return MockAsyncDatabase()


@pytest.fixture
def mock_thumbnail_job_operations(mock_async_database):
    """Mock thumbnail job operations for testing."""
    from app.database.thumbnail_job_operations import ThumbnailJobOperations
    from app.models.shared_models import (
        ThumbnailGenerationJob,
        ThumbnailGenerationJobCreate,
    )
    from datetime import datetime

    class MockThumbnailJobOperations:
        def __init__(self):
            self.jobs = {}
            self.next_id = 1

        async def create_job(self, job_data: ThumbnailGenerationJobCreate):
            job = ThumbnailGenerationJob(
                id=self.next_id,
                image_id=job_data.image_id,
                priority=job_data.priority,
                status=job_data.status,
                job_type=job_data.job_type,
                created_at=datetime.utcnow(),
                retry_count=0,
            )
            self.jobs[self.next_id] = job
            self.next_id += 1
            return job

        async def get_pending_jobs(self, batch_size=5):
            return [job for job in self.jobs.values() if job.status == "pending"][
                :batch_size
            ]

        async def mark_job_started(self, job_id):
            if job_id in self.jobs:
                self.jobs[job_id].status = "processing"
                return True
            return False

        async def mark_job_completed(self, job_id, processing_time_ms=None):
            if job_id in self.jobs:
                self.jobs[job_id].status = "completed"
                return True
            return False

        async def mark_job_failed(self, job_id, error_message, retry_count=0):
            if job_id in self.jobs:
                self.jobs[job_id].status = "failed"
                self.jobs[job_id].error_message = error_message
                return True
            return False

        async def get_job_statistics(self):
            """Get job queue statistics."""
            from app.models.shared_models import ThumbnailJobStatistics

            stats = {
                "pending_jobs": len(
                    [j for j in self.jobs.values() if j.status == "pending"]
                ),
                "processing_jobs": len(
                    [j for j in self.jobs.values() if j.status == "processing"]
                ),
                "completed_jobs_24h": len(
                    [j for j in self.jobs.values() if j.status == "completed"]
                ),
                "failed_jobs_24h": len(
                    [j for j in self.jobs.values() if j.status == "failed"]
                ),
                "total_jobs_24h": len(self.jobs),
                "average_processing_time_ms": 1500.0,
                "success_rate_percentage": 95.0,
            }

            return stats

        async def cancel_jobs_for_image(self, image_id):
            """Cancel jobs for specific image."""
            cancelled = 0
            for job in self.jobs.values():
                if job.image_id == image_id and job.status == "pending":
                    job.status = "cancelled"
                    cancelled += 1
            return cancelled

    return MockThumbnailJobOperations()


@pytest.fixture
def mock_sse_operations():
    """Mock SSE operations for testing."""

    class MockSSEOperations:
        def __init__(self):
            self.events = []

        async def create_event(
            self, event_type, event_data, priority="normal", source="test"
        ):
            event = {
                "event_type": event_type,
                "event_data": event_data,
                "priority": priority,
                "source": source,
                "created_at": datetime.utcnow(),
            }
            self.events.append(event)
            return event

        def get_events(self, event_type=None):
            if event_type:
                return [e for e in self.events if e["event_type"] == event_type]
            return self.events

        def clear_events(self):
            self.events.clear()

    return MockSSEOperations()


@pytest.fixture
def sample_thumbnail_job_data():
    """Sample data for thumbnail job testing."""
    from app.models.shared_models import ThumbnailGenerationJobCreate
    from app.constants import (
        THUMBNAIL_JOB_PRIORITY_MEDIUM,
        THUMBNAIL_JOB_STATUS_PENDING,
        THUMBNAIL_JOB_TYPE_SINGLE,
    )

    return {
        "basic_job": ThumbnailGenerationJobCreate(
            image_id=1,
            priority=THUMBNAIL_JOB_PRIORITY_MEDIUM,
            status=THUMBNAIL_JOB_STATUS_PENDING,
            job_type=THUMBNAIL_JOB_TYPE_SINGLE,
        ),
        "high_priority_job": ThumbnailGenerationJobCreate(
            image_id=2,
            priority="high",
            status=THUMBNAIL_JOB_STATUS_PENDING,
            job_type=THUMBNAIL_JOB_TYPE_SINGLE,
        ),
        "batch_jobs": [
            ThumbnailGenerationJobCreate(
                image_id=i,
                priority=THUMBNAIL_JOB_PRIORITY_MEDIUM,
                status=THUMBNAIL_JOB_STATUS_PENDING,
                job_type="bulk",
            )
            for i in range(10, 15)
        ],
    }


@pytest.fixture
def mock_image_operations():
    """Mock image operations for testing."""
    from app.models.image_model import Image, ImageWithDetails
    from datetime import datetime

    class MockImageOperations:
        def __init__(self):
            self.images = {}
            self.next_id = 1

        async def get_image_by_id(self, image_id):
            return self.images.get(image_id)

        def get_image_by_id_sync(self, image_id):
            return self.images.get(image_id)

        async def get_images_by_ids(self, image_ids):
            return [self.images[id] for id in image_ids if id in self.images]

        async def get_images_by_cameras(self, camera_ids, limit=1000):
            return [img for img in self.images.values() if img.camera_id in camera_ids][
                :limit
            ]

        async def get_images_by_timelapses(self, timelapse_ids, limit=1000):
            return [
                img
                for img in self.images.values()
                if hasattr(img, "timelapse_id") and img.timelapse_id in timelapse_ids
            ][:limit]

        async def get_images_with_thumbnails(self, limit=1000):
            return [
                img
                for img in self.images.values()
                if hasattr(img, "thumbnail_path") and img.thumbnail_path
            ][:limit]

        def add_test_image(self, camera_id=1, timelapse_id=1, has_thumbnails=False):
            image = ImageWithDetails(
                id=self.next_id,
                camera_id=camera_id,
                timelapse_id=timelapse_id,
                file_path=f"test_image_{self.next_id}.jpg",
                captured_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                day_number=1,
                file_size=1024,
                corruption_score=100,
                corruption_details=None,
                is_flagged=False,
                thumbnail_path=f"thumb_{self.next_id}.jpg" if has_thumbnails else None,
                small_path=f"small_{self.next_id}.jpg" if has_thumbnails else None,
            )
            self.images[self.next_id] = image
            self.next_id += 1
            return image

    return MockImageOperations()


@pytest.fixture
def mock_thumbnail_worker_dependencies(
    mock_sync_database, mock_settings_service, mock_sse_operations
):
    """Bundle of dependencies needed for ThumbnailWorker testing."""

    class MockSyncSSEOperations:
        def __init__(self, async_sse_ops):
            self.async_sse_ops = async_sse_ops

        def create_event(
            self, event_type, event_data, priority="normal", source="test"
        ):
            # For sync testing, just store the event
            event = {
                "event_type": event_type,
                "event_data": event_data,
                "priority": priority,
                "source": source,
                "created_at": datetime.utcnow(),
            }
            self.async_sse_ops.events.append(event)
            return event

    return {
        "sync_db": mock_sync_database,
        "settings_service": mock_settings_service,
        "sse_ops": MockSyncSSEOperations(mock_sse_operations),
        "async_sse_ops": mock_sse_operations,
    }


def generate_test_thumbnail_jobs(count=5, image_id_start=1):
    """Generate test thumbnail job data."""
    from app.models.shared_models import ThumbnailGenerationJobCreate
    from app.constants import (
        THUMBNAIL_JOB_PRIORITY_MEDIUM,
        THUMBNAIL_JOB_STATUS_PENDING,
        THUMBNAIL_JOB_TYPE_SINGLE,
    )

    jobs = []
    for i in range(count):
        jobs.append(
            ThumbnailGenerationJobCreate(
                image_id=image_id_start + i,
                priority=THUMBNAIL_JOB_PRIORITY_MEDIUM,
                status=THUMBNAIL_JOB_STATUS_PENDING,
                job_type=THUMBNAIL_JOB_TYPE_SINGLE,
            )
        )
    return jobs


def assert_job_status(job, expected_status):
    """Assert that a job has the expected status."""
    assert job is not None
    assert job.status == expected_status


def assert_sse_event_sent(sse_ops, event_type, expected_count=1):
    """Assert that SSE events of specific type were sent."""
    events = sse_ops.get_events(event_type)
    assert len(events) == expected_count


@pytest.fixture
def mock_image_service():
    """Mock image service for ThumbnailService testing."""
    from app.models.shared_models import ThumbnailGenerationResult

    class MockImageService:
        def __init__(self):
            self.generation_results = {}

        async def coordinate_thumbnail_generation(
            self, image_id: int, force_regenerate: bool = False
        ):
            """Mock thumbnail generation coordination."""
            return ThumbnailGenerationResult(
                success=True,
                image_id=image_id,
                thumbnail_path=f"/data/thumbnails/thumb_{image_id}.jpg",
                small_path=f"/data/small/small_{image_id}.jpg",
            )

    return MockImageService()


@pytest.fixture
def mock_thumbnail_service_dependencies(
    mock_async_database, mock_settings_service, mock_image_service
):
    """Mock dependencies for ThumbnailService initialization."""
    return {
        "db": mock_async_database,
        "settings_service": mock_settings_service,
        "image_service": mock_image_service,
    }
