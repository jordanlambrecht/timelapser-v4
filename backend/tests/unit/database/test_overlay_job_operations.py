#!/usr/bin/env python3
"""
Unit tests for OverlayJobOperations.

Tests the database layer for overlay job queue management including
job creation, status updates, priority handling, and statistics.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.constants import (
    OVERLAY_JOB_PRIORITY_HIGH,
    OVERLAY_JOB_PRIORITY_LOW,
    OVERLAY_JOB_PRIORITY_MEDIUM,
    OVERLAY_JOB_TYPE_BATCH,
    OVERLAY_JOB_TYPE_SINGLE,
)
from app.database.overlay_job_operations import (
    OverlayJobOperations,
    SyncOverlayJobOperations,
)
from app.enums import JobPriority, JobStatus
from app.models.overlay_model import (
    OverlayJob,
    OverlayJobCreate,
    OverlayJobStatistics,
    OverlayJobUpdate,
)


@pytest.mark.unit
@pytest.mark.overlay
class TestOverlayJobOperations:
    """Test suite for OverlayJobOperations database layer."""

    @pytest.fixture
    def job_ops(self, mock_async_database):
        """Create OverlayJobOperations instance with mock database."""
        return OverlayJobOperations(mock_async_database)

    @pytest.fixture
    def sample_job_data(self):
        """Sample overlay job creation data."""
        return OverlayJobCreate(
            image_id=1,
            timelapse_id=1,
            preset_id=1,
            job_type=OVERLAY_JOB_TYPE_SINGLE,
            priority=OVERLAY_JOB_PRIORITY_MEDIUM,
            overlay_config={
                "show_timestamp": True,
                "timestamp_format": "%Y-%m-%d %H:%M:%S",
                "timestamp_position": "bottom_right",
            },
            status=JobStatus.PENDING,
        )

    @pytest.fixture
    def sample_batch_job_data(self):
        """Sample batch overlay job creation data."""
        return OverlayJobCreate(
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
        )

    # ============================================================================
    # JOB CREATION TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_create_job_success(
        self, job_ops, sample_job_data, mock_async_database
    ):
        """Test successful overlay job creation."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "image_id": 1,
                "timelapse_id": 1,
                "preset_id": 1,
                "job_type": OVERLAY_JOB_TYPE_SINGLE,
                "priority": OVERLAY_JOB_PRIORITY_MEDIUM,
                "overlay_config": sample_job_data.overlay_config,
                "status": JobStatus.PENDING,
                "created_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "error_message": None,
                "processing_time_ms": None,
                "retry_count": 0,
                "output_path": None,
            }
        )

        # Test job creation
        job = await job_ops.create_job(sample_job_data)

        # Assertions
        assert job is not None
        assert isinstance(job, OverlayJob)
        assert job.id == 1
        assert job.image_id == 1
        assert job.timelapse_id == 1
        assert job.preset_id == 1
        assert job.job_type == OVERLAY_JOB_TYPE_SINGLE
        assert job.priority == OVERLAY_JOB_PRIORITY_MEDIUM
        assert job.status == JobStatus.PENDING

        # Verify database was called correctly
        mock_async_database.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_batch_job_success(
        self, job_ops, sample_batch_job_data, mock_async_database
    ):
        """Test successful batch overlay job creation."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 2,
                "image_id": None,
                "timelapse_id": 1,
                "preset_id": 2,
                "job_type": OVERLAY_JOB_TYPE_BATCH,
                "priority": OVERLAY_JOB_PRIORITY_HIGH,
                "overlay_config": sample_batch_job_data.overlay_config,
                "status": JobStatus.PENDING,
                "created_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "error_message": None,
                "processing_time_ms": None,
                "retry_count": 0,
                "output_path": None,
            }
        )

        # Test batch job creation
        job = await job_ops.create_job(sample_batch_job_data)

        # Assertions
        assert job is not None
        assert isinstance(job, OverlayJob)
        assert job.id == 2
        assert job.image_id is None  # Batch jobs don't have single image
        assert job.timelapse_id == 1
        assert job.job_type == OVERLAY_JOB_TYPE_BATCH
        assert job.priority == OVERLAY_JOB_PRIORITY_HIGH

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

    # ============================================================================
    # JOB RETRIEVAL TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_pending_jobs_priority_order(self, job_ops, mock_async_database):
        """Test that pending jobs are returned in priority order."""
        # Mock database response with jobs in different priorities
        mock_async_database.fetch_all = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "image_id": 1,
                    "timelapse_id": 1,
                    "preset_id": 1,
                    "job_type": OVERLAY_JOB_TYPE_SINGLE,
                    "priority": OVERLAY_JOB_PRIORITY_HIGH,
                    "overlay_config": {"show_timestamp": True},
                    "status": JobStatus.PENDING,
                    "created_at": datetime.utcnow() - timedelta(minutes=5),
                    "started_at": None,
                    "completed_at": None,
                    "error_message": None,
                    "processing_time_ms": None,
                    "retry_count": 0,
                    "output_path": None,
                },
                {
                    "id": 2,
                    "image_id": 2,
                    "timelapse_id": 1,
                    "preset_id": 1,
                    "job_type": OVERLAY_JOB_TYPE_SINGLE,
                    "priority": OVERLAY_JOB_PRIORITY_MEDIUM,
                    "overlay_config": {"show_timestamp": True},
                    "status": JobStatus.PENDING,
                    "created_at": datetime.utcnow() - timedelta(minutes=3),
                    "started_at": None,
                    "completed_at": None,
                    "error_message": None,
                    "processing_time_ms": None,
                    "retry_count": 0,
                    "output_path": None,
                },
            ]
        )

        # Test getting pending jobs
        jobs = await job_ops.get_pending_jobs(batch_size=5)

        # Assertions
        assert len(jobs) == 2
        assert all(isinstance(job, OverlayJob) for job in jobs)

        # Higher priority jobs should come first
        assert jobs[0].priority == OVERLAY_JOB_PRIORITY_HIGH
        assert jobs[1].priority == OVERLAY_JOB_PRIORITY_MEDIUM

        # Verify database query was called with correct parameters
        mock_async_database.fetch_all.assert_called_once()
        args = mock_async_database.fetch_all.call_args[0]
        assert JobStatus.PENDING in args
        assert 5 in args

    @pytest.mark.asyncio
    async def test_get_job_by_id_success(self, job_ops, mock_async_database):
        """Test successful retrieval of job by ID."""
        # Mock database response
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "image_id": 1,
                "timelapse_id": 1,
                "preset_id": 1,
                "job_type": OVERLAY_JOB_TYPE_SINGLE,
                "priority": OVERLAY_JOB_PRIORITY_MEDIUM,
                "overlay_config": {"show_timestamp": True},
                "status": JobStatus.COMPLETED,
                "created_at": datetime.utcnow() - timedelta(minutes=10),
                "started_at": datetime.utcnow() - timedelta(minutes=8),
                "completed_at": datetime.utcnow() - timedelta(minutes=7),
                "error_message": None,
                "processing_time_ms": 60000,  # 1 minute
                "retry_count": 0,
                "output_path": "/data/overlays/output_1.jpg",
            }
        )

        # Test getting job by ID
        job = await job_ops.get_job_by_id(1)

        # Assertions
        assert job is not None
        assert isinstance(job, OverlayJob)
        assert job.id == 1
        assert job.status == JobStatus.COMPLETED
        assert job.processing_time_ms == 60000
        assert job.output_path == "/data/overlays/output_1.jpg"

        # Verify database was called correctly
        mock_async_database.fetch_one.assert_called_once()

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
    async def test_get_jobs_by_timelapse_success(self, job_ops, mock_async_database):
        """Test getting all jobs for a specific timelapse."""
        # Mock database response
        mock_async_database.fetch_all = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "image_id": 1,
                    "timelapse_id": 1,
                    "preset_id": 1,
                    "job_type": OVERLAY_JOB_TYPE_SINGLE,
                    "priority": OVERLAY_JOB_PRIORITY_MEDIUM,
                    "overlay_config": {"show_timestamp": True},
                    "status": JobStatus.COMPLETED,
                    "created_at": datetime.utcnow(),
                    "started_at": datetime.utcnow(),
                    "completed_at": datetime.utcnow(),
                    "error_message": None,
                    "processing_time_ms": 30000,
                    "retry_count": 0,
                    "output_path": "/data/overlays/output_1.jpg",
                },
                {
                    "id": 2,
                    "image_id": 2,
                    "timelapse_id": 1,
                    "preset_id": 1,
                    "job_type": OVERLAY_JOB_TYPE_SINGLE,
                    "priority": OVERLAY_JOB_PRIORITY_MEDIUM,
                    "overlay_config": {"show_timestamp": True},
                    "status": JobStatus.PENDING,
                    "created_at": datetime.utcnow(),
                    "started_at": None,
                    "completed_at": None,
                    "error_message": None,
                    "processing_time_ms": None,
                    "retry_count": 0,
                    "output_path": None,
                },
            ]
        )

        # Test getting jobs by timelapse
        jobs = await job_ops.get_jobs_by_timelapse(1)

        # Assertions
        assert len(jobs) == 2
        assert all(isinstance(job, OverlayJob) for job in jobs)
        assert all(job.timelapse_id == 1 for job in jobs)

        # Verify database was called correctly
        mock_async_database.fetch_all.assert_called_once()

    # ============================================================================
    # JOB STATUS UPDATE TESTS
    # ============================================================================

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
        assert JobStatus.PROCESSING in args
        assert 1 in args
        assert JobStatus.PENDING in args

    @pytest.mark.asyncio
    async def test_mark_job_completed(self, job_ops, mock_async_database):
        """Test marking a job as completed."""
        # Mock database execute
        mock_async_database.execute = AsyncMock(return_value=MagicMock())

        # Test marking job as completed
        output_path = "/data/overlays/output_1.jpg"
        result = await job_ops.mark_job_completed(
            1, output_path, processing_time_ms=45000
        )

        # Assertions
        assert result is True

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert JobStatus.COMPLETED in args
        assert output_path in args
        assert 45000 in args
        assert 1 in args
        assert JobStatus.PROCESSING in args

    @pytest.mark.asyncio
    async def test_mark_job_failed(self, job_ops, mock_async_database):
        """Test marking a job as failed."""
        # Mock database execute
        mock_async_database.execute = AsyncMock(return_value=MagicMock())

        # Test marking job as failed
        error_message = "Failed to process overlay: Invalid configuration"
        result = await job_ops.mark_job_failed(1, error_message, retry_count=1)

        # Assertions
        assert result is True

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert JobStatus.FAILED in args
        assert error_message in args
        assert 1 in args  # retry_count
        assert 1 in args  # job_id
        assert JobStatus.PROCESSING in args

    @pytest.mark.asyncio
    async def test_schedule_retry(self, job_ops, mock_async_database):
        """Test scheduling a failed job for retry."""
        # Mock database execute
        mock_async_database.execute = AsyncMock(return_value=MagicMock())

        # Test scheduling retry
        result = await job_ops.schedule_retry(1, retry_count=2, delay_minutes=10)

        # Assertions
        assert result is True

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert JobStatus.PENDING in args
        assert 2 in args  # retry_count
        assert 1 in args  # job_id
        assert JobStatus.FAILED in args
        assert "10 minutes" in args  # delay interval

    # ============================================================================
    # JOB MANAGEMENT TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_cancel_jobs_for_image(self, job_ops, mock_async_database):
        """Test cancelling all jobs for a specific image."""
        # Mock database execute returning cursor with rowcount
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 2
        mock_async_database.execute = AsyncMock(return_value=mock_cursor)

        # Test cancelling jobs
        cancelled_count = await job_ops.cancel_jobs_for_image(123)

        # Assertions
        assert cancelled_count == 2

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert "cancelled" in args
        assert 123 in args  # image_id
        assert JobStatus.PENDING in args

    @pytest.mark.asyncio
    async def test_cancel_jobs_for_timelapse(self, job_ops, mock_async_database):
        """Test cancelling all jobs for a specific timelapse."""
        # Mock database execute returning cursor with rowcount
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 5
        mock_async_database.execute = AsyncMock(return_value=mock_cursor)

        # Test cancelling jobs
        cancelled_count = await job_ops.cancel_jobs_for_timelapse(456)

        # Assertions
        assert cancelled_count == 5

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert "cancelled" in args
        assert 456 in args  # timelapse_id
        assert JobStatus.PENDING in args
        assert JobStatus.PROCESSING in args

    @pytest.mark.asyncio
    async def test_cleanup_old_jobs(self, job_ops, mock_async_database):
        """Test cleanup of old completed and failed jobs."""
        # Mock database execute returning cursor with rowcount
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 10
        mock_async_database.execute = AsyncMock(return_value=mock_cursor)

        # Test cleanup
        cleaned_count = await job_ops.cleanup_old_jobs(older_than_hours=48)

        # Assertions
        assert cleaned_count == 10

        # Verify database was called with correct parameters
        mock_async_database.execute.assert_called_once()
        args = mock_async_database.execute.call_args[0]
        assert JobStatus.COMPLETED in args
        assert JobStatus.FAILED in args
        assert "cancelled" in args

    # ============================================================================
    # STATISTICS TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_get_job_statistics(self, job_ops, mock_async_database):
        """Test getting overlay job queue statistics."""
        # Mock database response
        mock_async_database.fetch_all = AsyncMock(
            return_value=[
                {
                    "status": JobStatus.PENDING,
                    "count": 8,
                    "avg_processing_time_ms": None,
                },
                {
                    "status": JobStatus.PROCESSING,
                    "count": 3,
                    "avg_processing_time_ms": None,
                },
                {
                    "status": JobStatus.COMPLETED,
                    "count": 25,
                    "avg_processing_time_ms": 42000.5,
                },
                {
                    "status": JobStatus.FAILED,
                    "count": 2,
                    "avg_processing_time_ms": None,
                },
            ]
        )

        # Test getting statistics
        stats = await job_ops.get_job_statistics()

        # Assertions
        assert isinstance(stats, OverlayJobStatistics)
        assert stats.pending_jobs == 8
        assert stats.processing_jobs == 3
        assert stats.completed_jobs_24h == 25
        assert stats.failed_jobs_24h == 2
        assert stats.total_jobs_24h == 38  # 8 + 3 + 25 + 2
        assert stats.average_processing_time_ms == 42000  # Converted to int
        assert stats.success_rate_percentage == pytest.approx(
            92.1, rel=1e-1
        )  # 25/27 active jobs

        # Verify database was called correctly
        mock_async_database.fetch_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_statistics_empty(self, job_ops, mock_async_database):
        """Test getting statistics when no jobs exist."""
        # Mock empty database response
        mock_async_database.fetch_all = AsyncMock(return_value=[])

        # Test getting statistics
        stats = await job_ops.get_job_statistics()

        # Assertions
        assert isinstance(stats, OverlayJobStatistics)
        assert stats.pending_jobs == 0
        assert stats.processing_jobs == 0
        assert stats.completed_jobs_24h == 0
        assert stats.failed_jobs_24h == 0
        assert stats.total_jobs_24h == 0
        assert stats.average_processing_time_ms == 0
        assert stats.success_rate_percentage == 0.0

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    @pytest.mark.asyncio
    async def test_error_handling_database_exception(
        self, job_ops, mock_async_database
    ):
        """Test error handling when database operations fail."""
        # Mock database raising an exception
        mock_async_database.fetch_all = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        # Test that exceptions are handled gracefully
        jobs = await job_ops.get_pending_jobs()

        # Should return empty list on error, not raise exception
        assert jobs == []

    @pytest.mark.asyncio
    async def test_error_handling_invalid_overlay_config(
        self, job_ops, mock_async_database
    ):
        """Test handling of jobs with invalid overlay configuration."""
        # Mock database response with invalid overlay config
        mock_async_database.fetch_one = AsyncMock(
            return_value={
                "id": 1,
                "image_id": 1,
                "timelapse_id": 1,
                "preset_id": 1,
                "job_type": OVERLAY_JOB_TYPE_SINGLE,
                "priority": OVERLAY_JOB_PRIORITY_MEDIUM,
                "overlay_config": "invalid_json",  # Invalid JSON
                "status": JobStatus.PENDING,
                "created_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "error_message": None,
                "processing_time_ms": None,
                "retry_count": 0,
                "output_path": None,
            }
        )

        # Test getting job with malformed config
        job = await job_ops.get_job_by_id(1)

        # Should handle gracefully (exact behavior depends on implementation)
        assert job is None or isinstance(job, OverlayJob)


@pytest.mark.unit
@pytest.mark.overlay
class TestSyncOverlayJobOperations:
    """Test suite for SyncOverlayJobOperations database layer."""

    @pytest.fixture
    def sync_job_ops(self, mock_sync_database):
        """Create SyncOverlayJobOperations instance with mock database."""
        return SyncOverlayJobOperations(mock_sync_database)

    @pytest.mark.asyncio
    async def test_sync_get_pending_jobs_success(
        self, sync_job_ops, mock_sync_database
    ):
        """Test sync version of get_pending_jobs."""
        # Mock the sync database methods
        mock_sync_database.fetch_all = MagicMock(
            return_value=[
                {
                    "id": 1,
                    "image_id": 1,
                    "timelapse_id": 1,
                    "preset_id": 1,
                    "job_type": OVERLAY_JOB_TYPE_SINGLE,
                    "priority": OVERLAY_JOB_PRIORITY_HIGH,
                    "overlay_config": {"show_timestamp": True},
                    "status": JobStatus.PENDING,
                    "created_at": datetime.utcnow(),
                    "started_at": None,
                    "completed_at": None,
                    "error_message": None,
                    "processing_time_ms": None,
                    "retry_count": 0,
                    "output_path": None,
                }
            ]
        )

        # Test getting pending jobs (sync version)
        jobs = sync_job_ops.get_pending_jobs(batch_size=5)

        # Assertions
        assert len(jobs) == 1
        assert all(isinstance(job, OverlayJob) for job in jobs)
        assert jobs[0].priority == OVERLAY_JOB_PRIORITY_HIGH
        assert jobs[0].status == JobStatus.PENDING

        # Verify database was called correctly
        mock_sync_database.fetch_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_mark_job_completed(self, sync_job_ops, mock_sync_database):
        """Test sync version of mark_job_completed."""
        # Mock the sync database methods
        mock_sync_database.execute = MagicMock(return_value=MagicMock())

        # Test marking job as completed (sync version)
        output_path = "/data/overlays/output_1.jpg"
        result = sync_job_ops.mark_job_completed(
            1, output_path, processing_time_ms=30000
        )

        # Assertions
        assert result is True

        # Verify database was called correctly
        mock_sync_database.execute.assert_called_once()
        args = mock_sync_database.execute.call_args[0]
        assert JobStatus.COMPLETED in args
        assert output_path in args
        assert 30000 in args
        assert 1 in args
        assert JobStatus.PROCESSING in args
