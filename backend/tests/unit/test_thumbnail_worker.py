#!/usr/bin/env python3
"""
Unit tests for ThumbnailWorker.

Tests the background worker process including job processing,
error handling, dependency injection, and SSE event broadcasting.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.workers.thumbnail_worker import ThumbnailWorker
from app.models.shared_models import (
    ThumbnailGenerationJob,
    ThumbnailGenerationJobCreate,
)
from app.models.image_model import Image
from app.constants import (
    THUMBNAIL_JOB_STATUS_PENDING,
    THUMBNAIL_JOB_STATUS_PROCESSING,
    THUMBNAIL_JOB_STATUS_COMPLETED,
    THUMBNAIL_JOB_STATUS_FAILED,
    THUMBNAIL_JOB_PRIORITY_HIGH,
    THUMBNAIL_JOB_PRIORITY_MEDIUM,
    THUMBNAIL_JOB_TYPE_SINGLE,
)


@pytest.mark.unit
@pytest.mark.thumbnail
@pytest.mark.worker
class TestThumbnailWorker:
    """Test suite for ThumbnailWorker background process."""

    @pytest.fixture
    def mock_thumbnail_operations(self):
        """Mock sync thumbnail job operations."""

        class MockSyncThumbnailOperations:
            def __init__(self):
                self.jobs = []

            def get_pending_jobs(self, batch_size=5):
                return self.jobs[:batch_size]

            def mark_job_started(self, job_id):
                return True

            def mark_job_completed(self, job_id, processing_time_ms=None):
                return True

            def mark_job_failed(self, job_id, error_message, retry_count=0):
                return True

            def add_test_job(
                self, job_id=1, image_id=1, status=THUMBNAIL_JOB_STATUS_PENDING
            ):
                job = ThumbnailGenerationJob(
                    id=job_id,
                    image_id=image_id,
                    priority=THUMBNAIL_JOB_PRIORITY_MEDIUM,
                    status=status,
                    job_type=THUMBNAIL_JOB_TYPE_SINGLE,
                    created_at=datetime.utcnow(),
                    retry_count=0,
                )
                self.jobs.append(job)
                return job

        return MockSyncThumbnailOperations()

    @pytest.fixture
    def mock_sync_image_operations(self):
        """Mock sync image operations."""

        class MockSyncImageOperations:
            def __init__(self):
                self.images = {}

            def get_image_by_id_sync(self, image_id):
                return self.images.get(image_id)

            def update_image_thumbnail_paths(
                self, image_id, thumbnail_path, small_path
            ):
                if image_id in self.images:
                    image = self.images[image_id]
                    image.thumbnail_path = thumbnail_path
                    image.small_path = small_path
                    return True
                return False

            def add_test_image(self, image_id=1, camera_id=1, timelapse_id=1):
                image = Image(
                    id=image_id,
                    camera_id=camera_id,
                    timelapse_id=timelapse_id,
                    file_path=f"/test/camera_{camera_id}/image_{image_id}.jpg",
                    captured_at=datetime.now(),
                    day_number=1,
                    file_size=1024,
                    corruption_score=100,
                    corruption_details=None,
                    is_flagged=False,
                    created_at=datetime.now(),
                )
                self.images[image_id] = image
                return image

        return MockSyncImageOperations()

    @pytest.fixture
    def worker_dependencies(
        self,
        mock_thumbnail_worker_dependencies,
        mock_thumbnail_operations,
        mock_sync_image_operations,
    ):
        """Complete worker dependencies."""
        deps = mock_thumbnail_worker_dependencies.copy()
        deps["thumbnail_job_ops"] = mock_thumbnail_operations
        deps["sync_image_ops"] = mock_sync_image_operations
        return deps

    @pytest.fixture
    def thumbnail_worker(self, worker_dependencies):
        """Create ThumbnailWorker instance with all dependencies."""
        return ThumbnailWorker(
            thumbnail_job_service=worker_dependencies["thumbnail_job_ops"],
            thumbnail_service=worker_dependencies["sync_image_ops"],
            sse_ops=worker_dependencies["sse_ops"],
        )

    def test_worker_initialization(self, thumbnail_worker, worker_dependencies):
        """Test worker initializes with correct dependencies."""
        assert thumbnail_worker.name == "ThumbnailWorker"
        assert thumbnail_worker.worker_interval > 0
        assert thumbnail_worker.batch_size > 0
        assert thumbnail_worker.thumbnail_job_ops is not None
        assert thumbnail_worker.sse_ops is not None

    def test_get_pending_jobs_empty_queue(self, thumbnail_worker):
        """Test getting pending jobs when queue is empty."""
        jobs = thumbnail_worker.get_pending_jobs()
        assert jobs == []

    def test_get_pending_jobs_with_jobs(self, thumbnail_worker, worker_dependencies):
        """Test getting pending jobs when queue has jobs."""
        # Add test jobs
        job_ops = worker_dependencies["thumbnail_job_ops"]
        job1 = job_ops.add_test_job(job_id=1, image_id=1)
        job2 = job_ops.add_test_job(job_id=2, image_id=2)

        jobs = thumbnail_worker.get_pending_jobs()

        assert len(jobs) == 2
        assert jobs[0].id == 1
        assert jobs[1].id == 2

    @pytest.mark.asyncio
    async def test_process_single_job_success(
        self, thumbnail_worker, worker_dependencies
    ):
        """Test successful processing of a single job."""
        # Setup test data
        job_ops = worker_dependencies["thumbnail_job_ops"]
        image_ops = worker_dependencies["sync_image_ops"]

        job = job_ops.add_test_job(job_id=1, image_id=1)
        image = image_ops.add_test_image(image_id=1, camera_id=1, timelapse_id=1)

        # Mock thumbnail generation
        with patch(
            "app.utils.thumbnail_utils.generate_thumbnails_for_timelapse_image"
        ) as mock_generate:
            mock_generate.return_value = {
                "thumbnail_path": "/test/thumbnails/thumb_1.jpg",
                "small_path": "/test/thumbnails/small_1.jpg",
                "success": True,
            }

            # Process the job
            await thumbnail_worker.process_single_job(job)

            # Verify thumbnail generation was called
            mock_generate.assert_called_once_with(
                image.file_path, image.camera_id, image.timelapse_id
            )

    @pytest.mark.asyncio
    async def test_process_single_job_image_not_found(
        self, thumbnail_worker, worker_dependencies
    ):
        """Test processing job when image doesn't exist."""
        job_ops = worker_dependencies["thumbnail_job_ops"]
        job = job_ops.add_test_job(job_id=1, image_id=999)  # Non-existent image

        # Process the job
        await thumbnail_worker.process_single_job(job)

        # Should handle gracefully without crashing
        assert True  # Test passes if no exception was raised

    @pytest.mark.asyncio
    async def test_process_single_job_legacy_image(
        self, thumbnail_worker, worker_dependencies
    ):
        """Test processing job for legacy image without timelapse_id."""
        job_ops = worker_dependencies["thumbnail_job_ops"]
        image_ops = worker_dependencies["sync_image_ops"]

        job = job_ops.add_test_job(job_id=1, image_id=1)

        # Create legacy image without timelapse_id
        image = Image(
            id=1,
            camera_id=1,
            timelapse_id=None,  # Legacy image, so timelapse_id is None
            file_path="/test/camera_1/image_1.jpg",
            captured_at=datetime.now(),
            day_number=1,
            file_size=1024,
            corruption_score=100,
            corruption_details=None,
            is_flagged=False,
            created_at=datetime.now(),
        )
        # Note: no timelapse_id attribute (set to None for legacy)
        image_ops.images[1] = image

        # Mock thumbnail generation
        with patch(
            "app.utils.thumbnail_utils.generate_thumbnails_for_timelapse_image"
        ) as mock_generate:
            mock_generate.return_value = {
                "thumbnail_path": "/test/thumbnails/thumb_1.jpg",
                "small_path": "/test/thumbnails/small_1.jpg",
                "success": True,
            }

            # Process the job
            await thumbnail_worker.process_single_job(job)

            # Verify thumbnail generation was called with None timelapse_id
            mock_generate.assert_called_once_with(
                image.file_path,
                image.camera_id,
                None,  # Should pass None for legacy images
            )

    @pytest.mark.asyncio
    async def test_process_single_job_generation_failure(
        self, thumbnail_worker, worker_dependencies
    ):
        """Test processing job when thumbnail generation fails."""
        job_ops = worker_dependencies["thumbnail_job_ops"]
        image_ops = worker_dependencies["sync_image_ops"]

        job = job_ops.add_test_job(job_id=1, image_id=1)
        image = image_ops.add_test_image(image_id=1, camera_id=1, timelapse_id=1)

        # Mock thumbnail generation failure
        with patch(
            "app.utils.thumbnail_utils.generate_thumbnails_for_timelapse_image"
        ) as mock_generate:
            mock_generate.return_value = {
                "success": False,
                "error": "File not accessible",
            }

            # Process the job
            await thumbnail_worker.process_single_job(job)

            # Should handle gracefully
            assert True

    @pytest.mark.asyncio
    async def test_process_single_job_exception_handling(
        self, thumbnail_worker, worker_dependencies
    ):
        """Test processing job when an exception is raised."""
        job_ops = worker_dependencies["thumbnail_job_ops"]
        image_ops = worker_dependencies["sync_image_ops"]

        job = job_ops.add_test_job(job_id=1, image_id=1)
        image = image_ops.add_test_image(image_id=1, camera_id=1, timelapse_id=1)

        # Mock thumbnail generation raising exception
        with patch(
            "app.utils.thumbnail_utils.generate_thumbnails_for_timelapse_image"
        ) as mock_generate:
            mock_generate.side_effect = Exception("Unexpected error")

            # Process the job - should not raise exception
            await thumbnail_worker.process_single_job(job)

            # Should handle gracefully
            assert True

    @pytest.mark.asyncio
    async def test_run_iteration_no_jobs(self, thumbnail_worker):
        """Test worker iteration when no jobs are pending."""
        result = await thumbnail_worker.run_iteration()

        # Should complete without processing any jobs
        assert result is None or result == 0

    @pytest.mark.asyncio
    async def test_run_iteration_with_jobs(self, thumbnail_worker, worker_dependencies):
        """Test worker iteration with pending jobs."""
        # Setup test data
        job_ops = worker_dependencies["thumbnail_job_ops"]
        image_ops = worker_dependencies["sync_image_ops"]

        # Add multiple jobs
        for i in range(3):
            job_ops.add_test_job(job_id=i + 1, image_id=i + 1)
            image_ops.add_test_image(image_id=i + 1, camera_id=1, timelapse_id=1)

        # Mock thumbnail generation
        with patch(
            "app.utils.thumbnail_utils.generate_thumbnails_for_timelapse_image"
        ) as mock_generate:
            mock_generate.return_value = {
                "thumbnail_path": "/test/thumbnails/thumb.jpg",
                "small_path": "/test/thumbnails/small.jpg",
                "success": True,
            }

            # Run iteration
            result = await thumbnail_worker.run_iteration()

            # Should have processed jobs
            assert mock_generate.call_count == 3

    @pytest.mark.asyncio
    async def test_sse_event_broadcasting(self, thumbnail_worker, worker_dependencies):
        """Test that SSE events are broadcast during job processing."""
        # Setup test data
        job_ops = worker_dependencies["thumbnail_job_ops"]
        image_ops = worker_dependencies["sync_image_ops"]
        sse_ops = worker_dependencies["async_sse_ops"]

        job = job_ops.add_test_job(job_id=1, image_id=1)
        image = image_ops.add_test_image(image_id=1, camera_id=1, timelapse_id=1)

        # Mock thumbnail generation
        with patch(
            "app.utils.thumbnail_utils.generate_thumbnails_for_timelapse_image"
        ) as mock_generate:
            mock_generate.return_value = {
                "thumbnail_path": "/test/thumbnails/thumb_1.jpg",
                "small_path": "/test/thumbnails/small_1.jpg",
                "success": True,
            }

            # Process the job
            await thumbnail_worker.process_single_job(job)

            # Check that SSE events were created
            events = sse_ops.get_events()
            assert len(events) > 0

            # Should have events for job processing
            event_types = [e["event_type"] for e in events]
            assert any("thumbnail" in event_type for event_type in event_types)

    def test_worker_configuration(self, thumbnail_worker):
        """Test worker configuration settings."""
        # Verify default configuration
        assert thumbnail_worker.worker_name == "ThumbnailWorker"
        assert thumbnail_worker.process_interval > 0
        assert thumbnail_worker.batch_size > 0

        # Verify worker is properly configured for background processing
        assert hasattr(thumbnail_worker, "thumbnail_job_ops")
        assert hasattr(thumbnail_worker, "sync_image_ops")

    @pytest.mark.asyncio
    async def test_concurrent_job_processing(
        self, thumbnail_worker, worker_dependencies
    ):
        """Test that worker can handle multiple jobs efficiently."""
        # Setup multiple test jobs
        job_ops = worker_dependencies["thumbnail_job_ops"]
        image_ops = worker_dependencies["sync_image_ops"]

        # Add more jobs than batch size to test batching
        for i in range(10):
            job_ops.add_test_job(job_id=i + 1, image_id=i + 1)
            image_ops.add_test_image(image_id=i + 1, camera_id=1, timelapse_id=1)

        # Mock thumbnail generation with variable processing time
        with patch(
            "app.utils.thumbnail_utils.generate_thumbnails_for_timelapse_image"
        ) as mock_generate:
            mock_generate.return_value = {
                "thumbnail_path": "/test/thumbnails/thumb.jpg",
                "small_path": "/test/thumbnails/small.jpg",
                "success": True,
            }

            # Run iteration
            await thumbnail_worker.run_iteration()

            # Should process up to batch_size jobs
            assert mock_generate.call_count <= thumbnail_worker.batch_size
            assert mock_generate.call_count > 0
