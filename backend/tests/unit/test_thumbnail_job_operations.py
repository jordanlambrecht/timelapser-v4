#!/usr/bin/env python3
"""
Unit tests for ThumbnailJobOperations.

Tests the database layer for thumbnail job management including
job creation, status updates, priority handling, and cleanup.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.database.thumbnail_job_operations import ThumbnailJobOperations
from app.models.shared_models import (
    ThumbnailGenerationJob,
    ThumbnailGenerationJobCreate,
)
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
class TestThumbnailJobOperations:
    """Test suite for ThumbnailJobOperations database layer."""

    @pytest.fixture
    def job_ops(self, mock_async_database):
        """Create ThumbnailJobOperations instance with mock database."""
        return ThumbnailJobOperations(mock_async_database)

    @pytest.fixture
    def sample_job_data(self):
        """Sample job creation data."""
        return ThumbnailGenerationJobCreate(
            image_id=1,
            priority=THUMBNAIL_JOB_PRIORITY_MEDIUM,
            status=THUMBNAIL_JOB_STATUS_PENDING,
            job_type=THUMBNAIL_JOB_TYPE_SINGLE,
        )

    @pytest.mark.asyncio
    async def test_create_job_success(
        self, job_ops, sample_job_data, mock_async_database
    ):
        """Test successful job creation."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "image_id": 1,
                "priority": THUMBNAIL_JOB_PRIORITY_MEDIUM,
                "status": THUMBNAIL_JOB_STATUS_PENDING,
                "job_type": THUMBNAIL_JOB_TYPE_SINGLE,
                "created_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "error_message": None,
                "processing_time_ms": None,
                "retry_count": 0,
            }
        )

        # Test job creation
        job = await job_ops.create_job(sample_job_data)

        # Assertions
        assert job is not None
        assert isinstance(job, ThumbnailGenerationJob)
        assert job.id == 1
        assert job.image_id == 1
        assert job.priority == THUMBNAIL_JOB_PRIORITY_MEDIUM
        assert job.status == THUMBNAIL_JOB_STATUS_PENDING

        # Verify database was called correctly
        mock_async_database.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_job_failure(
        self, job_ops, sample_job_data, mock_async_database
    ):
        """Test job creation failure handling."""
        # Mock database returning None (creation failed)
        mock_async_database.fetch_one = AsyncMock(return_value=None)

        # Test job creation
        job = await job_ops.create_job(sample_job_data)

        # Assertions
        assert job is None

    @pytest.mark.asyncio
    async def test_get_pending_jobs_priority_order(self, job_ops, mock_async_database):
        """Test that pending jobs are returned in priority order."""
        # Mock database response with jobs in different priorities
        mock_async_database.fetch_all = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "image_id": 1,
                    "priority": THUMBNAIL_JOB_PRIORITY_HIGH,
                    "status": THUMBNAIL_JOB_STATUS_PENDING,
                    "job_type": THUMBNAIL_JOB_TYPE_SINGLE,
                    "created_at": datetime.utcnow(),
                    "started_at": None,
                    "completed_at": None,
                    "error_message": None,
                    "processing_time_ms": None,
                    "retry_count": 0,
                },
                {
                    "id": 2,
                    "image_id": 2,
                    "priority": THUMBNAIL_JOB_PRIORITY_MEDIUM,
                    "status": THUMBNAIL_JOB_STATUS_PENDING,
                    "job_type": THUMBNAIL_JOB_TYPE_SINGLE,
                    "created_at": datetime.utcnow(),
                    "started_at": None,
                    "completed_at": None,
                    "error_message": None,
                    "processing_time_ms": None,
                    "retry_count": 0,
                },
            ]
        )

        # Test getting pending jobs
        jobs = await job_ops.get_pending_jobs(batch_size=5)

        # Assertions
        assert len(jobs) == 2
        assert all(isinstance(job, ThumbnailGenerationJob) for job in jobs)

        # Verify database query was called with correct parameters
        mock_async_database.fetch_all.assert_called_once()
        args = mock_async_database.fetch_all.call_args[0]
        assert THUMBNAIL_JOB_STATUS_PENDING in args
        assert 5 in args

    @pytest.mark.asyncio
    async def test_mark_job_started(self, job_ops, mock_async_database):
        """Test marking a job as started."""
        # Mock database execute
        mock_async_database.execute = AsyncMock(return_value=MagicMock())

        # Test marking job as started
        result = await job_ops.mark_job_started(1)

        # Assertions
        assert result is True

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert THUMBNAIL_JOB_STATUS_PROCESSING in args
        assert 1 in args
        assert THUMBNAIL_JOB_STATUS_PENDING in args

    @pytest.mark.asyncio
    async def test_mark_job_completed(self, job_ops, mock_async_database):
        """Test marking a job as completed."""
        # Mock database execute
        mock_async_database.execute = AsyncMock(return_value=MagicMock())

        # Test marking job as completed
        result = await job_ops.mark_job_completed(1, processing_time_ms=1500)

        # Assertions
        assert result is True

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert THUMBNAIL_JOB_STATUS_COMPLETED in args
        assert 1500 in args
        assert 1 in args
        assert THUMBNAIL_JOB_STATUS_PROCESSING in args

    @pytest.mark.asyncio
    async def test_mark_job_failed(self, job_ops, mock_async_database):
        """Test marking a job as failed."""
        # Mock database execute
        mock_async_database.execute = AsyncMock(return_value=MagicMock())

        # Test marking job as failed
        error_message = "File not found"
        result = await job_ops.mark_job_failed(1, error_message, retry_count=1)

        # Assertions
        assert result is True

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert THUMBNAIL_JOB_STATUS_FAILED in args
        assert error_message in args
        assert 1 in args  # retry_count
        assert 1 in args  # job_id
        assert THUMBNAIL_JOB_STATUS_PROCESSING in args

    @pytest.mark.asyncio
    async def test_schedule_retry(self, job_ops, mock_async_database):
        """Test scheduling a job for retry."""
        # Mock database execute
        mock_async_database.execute = AsyncMock(return_value=MagicMock())

        # Test scheduling retry
        result = await job_ops.schedule_retry(1, retry_count=2, delay_minutes=5)

        # Assertions
        assert result is True

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert THUMBNAIL_JOB_STATUS_PENDING in args
        assert 2 in args  # retry_count
        assert 1 in args  # job_id
        assert THUMBNAIL_JOB_STATUS_FAILED in args
        assert "5 minutes" in args  # delay interval

    @pytest.mark.asyncio
    async def test_cancel_jobs_for_image(self, job_ops, mock_async_database):
        """Test cancelling all jobs for a specific image."""
        # Mock database execute returning cursor with rowcount
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 3
        mock_async_database.execute = AsyncMock(return_value=mock_cursor)

        # Test cancelling jobs
        cancelled_count = await job_ops.cancel_jobs_for_image(123)

        # Assertions
        assert cancelled_count == 3

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert "cancelled" in args
        assert 123 in args  # image_id
        assert THUMBNAIL_JOB_STATUS_PENDING in args

    @pytest.mark.asyncio
    async def test_cleanup_completed_jobs(self, job_ops, mock_async_database):
        """Test cleanup of old completed jobs."""
        # Mock database execute returning cursor with rowcount
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        mock_async_database.execute = AsyncMock(return_value=mock_cursor)

        # Test cleanup
        cleaned_count = await job_ops.cleanup_completed_jobs(older_than_hours=24)

        # Assertions
        assert cleaned_count == 5

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert THUMBNAIL_JOB_STATUS_COMPLETED in args
        assert THUMBNAIL_JOB_STATUS_FAILED in args
        assert "cancelled" in args

    @pytest.mark.asyncio
    async def test_get_job_statistics(self, job_ops, mock_async_database):
        """Test getting job queue statistics."""
        # Mock database response
        mock_async_database.fetch_all = AsyncMock(
            return_value=[
                {
                    "status": THUMBNAIL_JOB_STATUS_PENDING,
                    "count": 5,
                    "avg_processing_time_ms": None,
                },
                {
                    "status": THUMBNAIL_JOB_STATUS_COMPLETED,
                    "count": 10,
                    "avg_processing_time_ms": 1200.5,
                },
                {
                    "status": THUMBNAIL_JOB_STATUS_FAILED,
                    "count": 2,
                    "avg_processing_time_ms": None,
                },
            ]
        )

        # Test getting statistics
        stats = await job_ops.get_job_statistics()

        # Assertions
        assert isinstance(stats, dict)
        assert stats["total_jobs_24h"] == 17  # 5 + 10 + 2
        assert stats["pending_jobs"] == 5
        assert stats["completed_jobs_24h"] == 10
        assert stats["failed_jobs_24h"] == 2
        assert stats["avg_processing_time_ms"] == 1200  # Converted to int

    @pytest.mark.asyncio
    async def test_get_job_by_id(self, job_ops, mock_async_database):
        """Test getting a specific job by ID."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "image_id": 123,
                "priority": THUMBNAIL_JOB_PRIORITY_HIGH,
                "status": THUMBNAIL_JOB_STATUS_COMPLETED,
                "job_type": THUMBNAIL_JOB_TYPE_SINGLE,
                "created_at": datetime.utcnow(),
                "started_at": datetime.utcnow(),
                "completed_at": datetime.utcnow(),
                "error_message": None,
                "processing_time_ms": 850,
                "retry_count": 0,
            }
        )

        # Test getting job
        job = await job_ops.get_job_by_id(1)

        # Assertions
        assert job is not None
        assert isinstance(job, ThumbnailGenerationJob)
        assert job.id == 1
        assert job.image_id == 123
        assert job.status == THUMBNAIL_JOB_STATUS_COMPLETED
        assert job.processing_time_ms == 850

    @pytest.mark.asyncio
    async def test_get_job_by_id_not_found(self, job_ops, mock_async_database):
        """Test getting a job that doesn't exist."""
        # Mock database returning None
        mock_async_database.fetch_one = AsyncMock(return_value=None)

        # Test getting non-existent job
        job = await job_ops.get_job_by_id(999)

        # Assertions
        assert job is None

    @pytest.mark.asyncio
    async def test_error_handling(self, job_ops, mock_async_database):
        """Test error handling in job operations."""
        # Mock database raising an exception
        mock_async_database.fetch_one = AsyncMock(
            side_effect=Exception("Database error")
        )

        # Test that exceptions are handled gracefully
        job_data = ThumbnailGenerationJobCreate(
            image_id=1,
            priority=THUMBNAIL_JOB_PRIORITY_MEDIUM,
            status=THUMBNAIL_JOB_STATUS_PENDING,
            job_type=THUMBNAIL_JOB_TYPE_SINGLE,
        )

        job = await job_ops.create_job(job_data)

        # Should return None on error, not raise exception
        assert job is None
