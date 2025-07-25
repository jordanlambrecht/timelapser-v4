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
    from app.enums import JobStatus, JobPriority
    from app.constants import (
        THUMBNAIL_JOB_TYPE_SINGLE,
    )

    return {
        "basic_job": ThumbnailGenerationJobCreate(
            image_id=1,
            priority=JobPriority.MEDIUM,
            status=JobStatus.PENDING,
            job_type=THUMBNAIL_JOB_TYPE_SINGLE,
        ),
        "high_priority_job": ThumbnailGenerationJobCreate(
            image_id=2,
            priority="high",
            status=JobStatus.PENDING,
            job_type=THUMBNAIL_JOB_TYPE_SINGLE,
        ),
        "batch_jobs": [
            ThumbnailGenerationJobCreate(
                image_id=i,
                priority=JobPriority.MEDIUM,
                status=JobStatus.PENDING,
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
    from app.enums import JobStatus, JobPriority
    from app.constants import (
        THUMBNAIL_JOB_TYPE_SINGLE,
    )

    jobs = []
    for i in range(count):
        jobs.append(
            ThumbnailGenerationJobCreate(
                image_id=image_id_start + i,
                priority=JobPriority.MEDIUM,
                status=JobStatus.PENDING,
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

        async def schedule_thumbnail_generation(
            self, image_id: int, force_regenerate: bool = False
        ):
            """Mock thumbnail generation scheduling."""
            return {
                "success": True,
                "image_id": image_id,
                "message": "Thumbnail generation scheduled through scheduler authority",
                "scheduled": True,
                "force_regenerate": force_regenerate,
                "reason": "scheduler_scheduled"
            }

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


# ====================================================================
# CAPTURE PIPELINE INTEGRATION TEST FIXTURES
# ====================================================================


@pytest.fixture
def mock_capture_pipeline_services(mock_sync_database, mock_settings_service):
    """Bundle of mock services for capture pipeline integration testing."""
    
    class MockCaptureServices:
        def __init__(self, sync_db, settings_service):
            self.sync_db = sync_db
            self.settings_service = settings_service
            
        def create_mock_camera(self, camera_id=1, status="active"):
            """Create mock camera data."""
            from app.models.camera_model import Camera
            return Camera(
                id=camera_id,
                name=f"Test Camera {camera_id}",
                rtsp_url=f"rtsp://test.camera{camera_id}/stream",
                status=status,
                health_status="healthy",
                active_timelapse_id=camera_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            
        def create_mock_timelapse(self, timelapse_id=1, camera_id=1, status="active"):
            """Create mock timelapse data."""
            from app.models.timelapse_model import Timelapse
            return Timelapse(
                id=timelapse_id,
                camera_id=camera_id,
                name=f"Test Timelapse {timelapse_id}",
                status=status,
                capture_interval=30,
                image_count=5,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            
        def create_mock_image(self, image_id=1, camera_id=1, timelapse_id=1):
            """Create mock image data."""
            from app.models.image_model import Image
            return Image(
                id=image_id,
                camera_id=camera_id,
                timelapse_id=timelapse_id,
                file_path=f"/test/data/images/image_{image_id}.jpg",
                captured_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                file_size=1024,
                corruption_score=95,
            )
    
    return MockCaptureServices(mock_sync_database, mock_settings_service)


@pytest.fixture
def mock_rtsp_capture_result():
    """Mock RTSP capture result for testing."""
    from app.models.shared_models import RTSPCaptureResult
    
    return RTSPCaptureResult(
        success=True,
        image_path="/test/data/images/test_image.jpg",
        file_size=1024,
        capture_time_ms=50,
        rtsp_url="rtsp://test.camera/stream",
        error_message=None,
    )


@pytest.fixture
def mock_capture_validation_result():
    """Mock capture validation result for testing."""
    from app.services.scheduling import CaptureReadinessValidationResult
    
    return CaptureReadinessValidationResult(
        valid=True,
        error=None,
        error_type=None,
        camera_id=1,
        timelapse_id=1,
    )


@pytest.fixture
def integration_test_data():
    """Complete test data bundle for integration tests."""
    return {
        "camera": {
            "id": 1,
            "name": "Test Camera",
            "rtsp_url": "rtsp://test.camera/stream",
            "status": "active",
            "health_status": "healthy",
            "active_timelapse_id": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        "timelapse": {
            "id": 1,
            "camera_id": 1,
            "name": "Test Timelapse",
            "status": "active",
            "capture_interval": 30,
            "image_count": 5,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        "image": {
            "id": 1,
            "camera_id": 1,
            "timelapse_id": 1,
            "file_path": "/test/data/images/test_image.jpg",
            "captured_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "file_size": 1024,
            "corruption_score": 95,
        },
        "settings": {
            "timezone": "UTC",
            "capture_interval": 30,
            "data_directory": "/test/data",
            "corruption_detection_enabled": True,
            "generate_thumbnails": True,
        },
    }


# ====================================================================
# OVERLAY SYSTEM TEST FIXTURES
# ====================================================================


@pytest.fixture
def mock_overlay_operations(mock_async_database):
    """Mock overlay operations for testing."""
    from app.database.overlay_operations import OverlayOperations
    from app.models.overlay_model import (
        OverlayPreset,
        OverlayPresetCreate,
        TimelapseOverlay,
        OverlayAsset,
        OverlayConfiguration,
    )
    from datetime import datetime

    class MockOverlayOperations:
        def __init__(self):
            self.presets = {}
            self.timelapse_overlays = {}
            self.assets = {}
            self.next_id = 1

        async def get_all_presets(self):
            return list(self.presets.values())

        async def get_preset_by_id(self, preset_id):
            return self.presets.get(preset_id)

        async def create_preset(self, preset_data: OverlayPresetCreate):
            preset = OverlayPreset(
                id=self.next_id,
                name=preset_data.name,
                description=preset_data.description,
                overlay_config=preset_data.overlay_config,
                is_builtin=preset_data.is_builtin,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.presets[self.next_id] = preset
            self.next_id += 1
            return preset

        async def update_preset(self, preset_id, update_data):
            if preset_id in self.presets:
                preset = self.presets[preset_id]
                if update_data.name:
                    preset.name = update_data.name
                if update_data.description:
                    preset.description = update_data.description
                if update_data.overlay_config:
                    preset.overlay_config = update_data.overlay_config
                preset.updated_at = datetime.utcnow()
                return preset
            return None

        async def delete_preset(self, preset_id):
            if preset_id in self.presets:
                del self.presets[preset_id]
                return True
            return False

        async def get_timelapse_overlay(self, timelapse_id):
            return next(
                (config for config in self.timelapse_overlays.values() 
                 if config.timelapse_id == timelapse_id), 
                None
            )

        async def create_timelapse_overlay(self, config_data):
            config = TimelapseOverlay(
                id=self.next_id,
                timelapse_id=config_data.timelapse_id,
                preset_id=config_data.preset_id,
                overlay_config=config_data.overlay_config,
                enabled=config_data.enabled,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.timelapse_overlays[self.next_id] = config
            self.next_id += 1
            return config

        async def update_timelapse_overlay(self, timelapse_id, update_data):
            config = await self.get_timelapse_overlay(timelapse_id)
            if config:
                if update_data.preset_id:
                    config.preset_id = update_data.preset_id
                if update_data.overlay_config:
                    config.overlay_config = update_data.overlay_config
                if update_data.enabled is not None:
                    config.enabled = update_data.enabled
                config.updated_at = datetime.utcnow()
                return config
            return None

        async def delete_timelapse_overlay(self, timelapse_id):
            config = await self.get_timelapse_overlay(timelapse_id)
            if config:
                del self.timelapse_overlays[config.id]
                return True
            return False

        async def get_all_assets(self):
            return list(self.assets.values())

        async def get_asset_by_id(self, asset_id):
            return self.assets.get(asset_id)

        async def create_asset(self, asset_data):
            asset = OverlayAsset(
                id=self.next_id,
                name=asset_data.name,
                description=asset_data.description,
                file_path=asset_data.file_path,
                original_name=asset_data.original_name,
                mime_type=asset_data.mime_type,
                file_size=asset_data.file_size,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.assets[self.next_id] = asset
            self.next_id += 1
            return asset

        async def delete_asset(self, asset_id):
            if asset_id in self.assets:
                del self.assets[asset_id]
                return True
            return False

        def add_builtin_presets(self):
            """Add built-in presets for testing."""
            builtin_presets = [
                {
                    "name": "Basic Timestamp",
                    "description": "Simple timestamp overlay",
                    "overlay_config": OverlayConfiguration(
                        show_timestamp=True,
                        timestamp_format="%Y-%m-%d %H:%M:%S",
                        timestamp_position="bottom_right",
                    ),
                },
                {
                    "name": "Weather + Time",
                    "description": "Timestamp with weather info",
                    "overlay_config": OverlayConfiguration(
                        show_timestamp=True,
                        show_weather=True,
                        timestamp_position="bottom_center",
                    ),
                },
                {
                    "name": "Minimal",
                    "description": "Minimal overlay with just time",
                    "overlay_config": OverlayConfiguration(
                        show_timestamp=True,
                        timestamp_format="%H:%M",
                        timestamp_position="top_right",
                    ),
                },
                {
                    "name": "Complete Info",
                    "description": "Full overlay with all information",
                    "overlay_config": OverlayConfiguration(
                        show_timestamp=True,
                        show_weather=True,
                        show_camera_name=True,
                        timestamp_position="bottom_right",
                        camera_name_position="top_left",
                    ),
                },
            ]
            
            for preset_data in builtin_presets:
                preset = OverlayPreset(
                    id=self.next_id,
                    name=preset_data["name"],
                    description=preset_data["description"],
                    overlay_config=preset_data["overlay_config"],
                    is_builtin=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                self.presets[self.next_id] = preset
                self.next_id += 1

    return MockOverlayOperations()


@pytest.fixture
def mock_overlay_job_operations(mock_async_database):
    """Mock overlay job operations for testing."""
    from app.database.overlay_job_operations import OverlayJobOperations
    from app.models.overlay_model import (
        OverlayJob,
        OverlayJobCreate,
        OverlayJobStatistics,
    )
    from app.enums import JobStatus, JobPriority
    from app.constants import (
        OVERLAY_JOB_TYPE_SINGLE,
        OVERLAY_JOB_PRIORITY_MEDIUM,
    )
    from datetime import datetime

    class MockOverlayJobOperations:
        def __init__(self):
            self.jobs = {}
            self.next_id = 1

        async def create_job(self, job_data: OverlayJobCreate):
            job = OverlayJob(
                id=self.next_id,
                image_id=job_data.image_id,
                timelapse_id=job_data.timelapse_id,
                preset_id=job_data.preset_id,
                job_type=job_data.job_type,
                priority=job_data.priority,
                overlay_config=job_data.overlay_config,
                status=job_data.status,
                created_at=datetime.utcnow(),
                started_at=None,
                completed_at=None,
                error_message=None,
                processing_time_ms=None,
                retry_count=0,
                output_path=None,
            )
            self.jobs[self.next_id] = job
            self.next_id += 1
            return job

        async def get_pending_jobs(self, batch_size=5):
            pending = [job for job in self.jobs.values() if job.status == JobStatus.PENDING]
            # Sort by priority (high first) then by creation time
            pending.sort(key=lambda x: (x.priority, x.created_at))
            return pending[:batch_size]

        async def get_job_by_id(self, job_id):
            return self.jobs.get(job_id)

        async def get_jobs_by_timelapse(self, timelapse_id):
            return [job for job in self.jobs.values() if job.timelapse_id == timelapse_id]

        async def mark_job_started(self, job_id):
            if job_id in self.jobs:
                self.jobs[job_id].status = JobStatus.PROCESSING
                self.jobs[job_id].started_at = datetime.utcnow()
                return True
            return False

        async def mark_job_completed(self, job_id, output_path, processing_time_ms=None):
            if job_id in self.jobs:
                self.jobs[job_id].status = JobStatus.COMPLETED
                self.jobs[job_id].completed_at = datetime.utcnow()
                self.jobs[job_id].output_path = output_path
                self.jobs[job_id].processing_time_ms = processing_time_ms
                return True
            return False

        async def mark_job_failed(self, job_id, error_message, retry_count=0):
            if job_id in self.jobs:
                self.jobs[job_id].status = JobStatus.FAILED
                self.jobs[job_id].error_message = error_message
                self.jobs[job_id].retry_count = retry_count
                return True
            return False

        async def schedule_retry(self, job_id, retry_count, delay_minutes=5):
            if job_id in self.jobs:
                self.jobs[job_id].status = JobStatus.PENDING
                self.jobs[job_id].retry_count = retry_count
                return True
            return False

        async def cancel_jobs_for_image(self, image_id):
            cancelled = 0
            for job in self.jobs.values():
                if job.image_id == image_id and job.status == JobStatus.PENDING:
                    job.status = "cancelled"
                    cancelled += 1
            return cancelled

        async def cancel_jobs_for_timelapse(self, timelapse_id):
            cancelled = 0
            for job in self.jobs.values():
                if (job.timelapse_id == timelapse_id and 
                    job.status in [JobStatus.PENDING, JobStatus.PROCESSING]):
                    job.status = "cancelled"
                    cancelled += 1
            return cancelled

        async def cleanup_old_jobs(self, older_than_hours=24):
            # For testing, just count completed/failed jobs
            count = len([
                job for job in self.jobs.values() 
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, "cancelled"]
            ])
            return count

        async def get_job_statistics(self):
            """Get job queue statistics."""
            status_counts = {}
            processing_times = []
            
            for job in self.jobs.values():
                status_counts[job.status] = status_counts.get(job.status, 0) + 1
                if job.processing_time_ms:
                    processing_times.append(job.processing_time_ms)
            
            total_jobs = len(self.jobs)
            completed_jobs = status_counts.get(JobStatus.COMPLETED, 0)
            failed_jobs = status_counts.get(JobStatus.FAILED, 0)
            avg_processing_time = (
                int(sum(processing_times) / len(processing_times)) 
                if processing_times else 0
            )
            
            # Calculate success rate
            active_jobs = completed_jobs + failed_jobs
            success_rate = (completed_jobs / active_jobs * 100) if active_jobs > 0 else 0.0
            
            return OverlayJobStatistics(
                pending_jobs=status_counts.get(JobStatus.PENDING, 0),
                processing_jobs=status_counts.get(JobStatus.PROCESSING, 0),
                completed_jobs_24h=completed_jobs,
                failed_jobs_24h=failed_jobs,
                total_jobs_24h=total_jobs,
                average_processing_time_ms=avg_processing_time,
                success_rate_percentage=success_rate,
            )

    return MockOverlayJobOperations()


@pytest.fixture
def sample_overlay_preset_data():
    """Sample data for overlay preset testing."""
    from app.models.overlay_model import OverlayPresetCreate, OverlayConfiguration
    
    overlay_config = OverlayConfiguration(
        show_timestamp=True,
        timestamp_format="%Y-%m-%d %H:%M:%S",
        timestamp_position="bottom_right",
        show_weather=False,
        show_camera_name=True,
        camera_name_position="top_left",
        background_opacity=0.7,
        text_color="#FFFFFF",
        font_size=24,
    )
    
    return {
        "basic_preset": OverlayPresetCreate(
            name="Test Preset",
            description="A test overlay preset",
            overlay_config=overlay_config,
            is_builtin=False,
        ),
        "weather_preset": OverlayPresetCreate(
            name="Weather Preset",
            description="Preset with weather information",
            overlay_config=OverlayConfiguration(
                show_timestamp=True,
                show_weather=True,
                show_camera_name=False,
                timestamp_position="bottom_center",
                background_opacity=0.8,
            ),
            is_builtin=False,
        ),
    }


@pytest.fixture
def sample_overlay_job_data():
    """Sample data for overlay job testing."""
    from app.models.overlay_model import OverlayJobCreate
    from app.enums import JobStatus, JobPriority
    from app.constants import (
        OVERLAY_JOB_TYPE_SINGLE,
        OVERLAY_JOB_TYPE_BATCH,
        OVERLAY_JOB_PRIORITY_HIGH,
        OVERLAY_JOB_PRIORITY_MEDIUM,
    )

    return {
        "single_job": OverlayJobCreate(
            image_id=1,
            timelapse_id=1,
            preset_id=1,
            job_type=OVERLAY_JOB_TYPE_SINGLE,
            priority=OVERLAY_JOB_PRIORITY_MEDIUM,
            overlay_config={
                "show_timestamp": True,
                "timestamp_format": "%Y-%m-%d %H:%M:%S",
            },
            status=JobStatus.PENDING,
        ),
        "high_priority_job": OverlayJobCreate(
            image_id=2,
            timelapse_id=1,
            preset_id=1,
            job_type=OVERLAY_JOB_TYPE_SINGLE,
            priority=OVERLAY_JOB_PRIORITY_HIGH,
            overlay_config={
                "show_timestamp": True,
                "show_weather": True,
            },
            status=JobStatus.PENDING,
        ),
        "batch_job": OverlayJobCreate(
            image_id=None,  # Batch jobs don't have single image
            timelapse_id=1,
            preset_id=2,
            job_type=OVERLAY_JOB_TYPE_BATCH,
            priority=OVERLAY_JOB_PRIORITY_HIGH,
            overlay_config={
                "show_timestamp": True,
                "show_weather": True,
                "show_camera_name": True,
            },
            status=JobStatus.PENDING,
        ),
    }


@pytest.fixture
def mock_overlay_service_dependencies(
    mock_async_database, mock_overlay_operations, mock_overlay_job_operations
):
    """Bundle of dependencies needed for OverlayIntegrationService testing."""
    return {
        "db": mock_async_database,
        "overlay_ops": mock_overlay_operations,
        "overlay_job_ops": mock_overlay_job_operations,
    }


def generate_test_overlay_jobs(count=5, timelapse_id=1):
    """Generate test overlay job data."""
    from app.models.overlay_model import OverlayJobCreate  
    from app.enums import JobStatus, JobPriority
    from app.constants import (
        OVERLAY_JOB_TYPE_SINGLE,
        OVERLAY_JOB_PRIORITY_MEDIUM,
    )

    jobs = []
    for i in range(count):
        jobs.append(
            OverlayJobCreate(
                image_id=i + 1,
                timelapse_id=timelapse_id,
                preset_id=1,
                job_type=OVERLAY_JOB_TYPE_SINGLE,
                priority=OVERLAY_JOB_PRIORITY_MEDIUM,
                overlay_config={
                    "show_timestamp": True,
                    "timestamp_format": "%Y-%m-%d %H:%M:%S",
                },
                status=JobStatus.PENDING,
            )
        )
    return jobs


def assert_overlay_preset_valid(preset, expected_name=None):
    """Assert that an overlay preset has valid structure."""
    from app.models.overlay_model import OverlayPreset
    
    assert preset is not None
    assert isinstance(preset, OverlayPreset)
    assert preset.id is not None
    assert preset.name is not None
    if expected_name:
        assert preset.name == expected_name
    assert preset.overlay_config is not None
    assert isinstance(preset.is_builtin, bool)


def assert_overlay_job_valid(job, expected_status=None):
    """Assert that an overlay job has valid structure."""
    from app.models.overlay_model import OverlayJob
    from app.enums import JobStatus
    
    assert job is not None
    assert isinstance(job, OverlayJob)
    assert job.id is not None
    assert job.timelapse_id is not None
    assert job.preset_id is not None
    assert job.status in [JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.COMPLETED, JobStatus.FAILED]
    if expected_status:
        assert job.status == expected_status


def assert_overlay_configuration_valid(config):
    """Assert that overlay configuration is valid."""
    assert isinstance(config, dict)
    
    # If timestamp is enabled, required fields must be present
    if config.get("show_timestamp"):
        assert "timestamp_format" in config
        assert "timestamp_position" in config
        
    # Validate opacity if present
    if "background_opacity" in config:
        opacity = config["background_opacity"]
        assert isinstance(opacity, (int, float))
        assert 0.0 <= opacity <= 1.0
        
    # Validate color format if present  
    if "text_color" in config:
        color = config["text_color"]
        assert isinstance(color, str)
        assert color.startswith("#") and len(color) == 7  # Basic hex color validation
