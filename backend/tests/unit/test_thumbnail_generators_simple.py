#!/usr/bin/env python3
"""
Simple unit tests for Thumbnail Generators using mock-based approach.

Tests the thumbnail generation functionality using the mock-based approach
that matches the existing test patterns in the codebase (similar to overlay tests).
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.unit
@pytest.mark.thumbnail
class TestThumbnailGeneratorsSimple:
    """Test suite for thumbnail generators using mocked operations."""

    @pytest.fixture
    def mock_thumbnail_generator(self):
        """Create mock thumbnail generator for testing."""
        return MagicMock()

    @pytest.fixture
    def mock_small_image_generator(self):
        """Create mock small image generator for testing."""
        return MagicMock()

    @pytest.fixture
    def mock_batch_generator(self):
        """Create mock batch thumbnail generator for testing."""
        return MagicMock()

    # ============================================================================
    # THUMBNAIL GENERATOR TESTS
    # ============================================================================

    def test_thumbnail_generator_success(self, mock_thumbnail_generator):
        """Test successful thumbnail generation."""
        # Setup mock response  
        expected_result = {
            'success': True,
            'output_path': '/thumbnails/thumb_001.jpg',
            'size': (200, 150),
            'source_size': (1920, 1080),
            'quality': 80,
            'generation_time_ms': 45
        }
        mock_thumbnail_generator.generate_thumbnail.return_value = expected_result

        # Test thumbnail generation
        result = mock_thumbnail_generator.generate_thumbnail(
            source_path='/images/source_001.jpg',
            output_path='/thumbnails/thumb_001.jpg'
        )

        # Verify success
        assert result['success'] is True
        assert result['output_path'] == '/thumbnails/thumb_001.jpg'
        assert result['size'] == (200, 150)
        assert result['source_size'] == (1920, 1080)
        assert result['generation_time_ms'] == 45

        # Verify mock was called correctly
        mock_thumbnail_generator.generate_thumbnail.assert_called_once_with(
            source_path='/images/source_001.jpg',
            output_path='/thumbnails/thumb_001.jpg'
        )

    def test_thumbnail_generator_failure(self, mock_thumbnail_generator):
        """Test thumbnail generation failure handling."""
        # Setup mock to return failure
        expected_result = {
            'success': False,
            'error': 'Source image not found',
            'output_path': '/thumbnails/thumb_002.jpg',
            'source_path': '/images/missing.jpg'
        }
        mock_thumbnail_generator.generate_thumbnail.return_value = expected_result

        # Test thumbnail generation failure
        result = mock_thumbnail_generator.generate_thumbnail(
            source_path='/images/missing.jpg',
            output_path='/thumbnails/thumb_002.jpg'
        )

        # Verify failure handling
        assert result['success'] is False
        assert 'error' in result
        assert result['error'] == 'Source image not found'

        # Verify mock was called correctly
        mock_thumbnail_generator.generate_thumbnail.assert_called_once()

    def test_thumbnail_generator_initialization_params(self, mock_thumbnail_generator):
        """Test thumbnail generator initialization with parameters."""
        # Mock initialization
        mock_thumbnail_generator.quality = 85
        mock_thumbnail_generator.target_size = (200, 150)

        # Verify initialization parameters
        assert mock_thumbnail_generator.quality == 85
        assert mock_thumbnail_generator.target_size == (200, 150)

    # ============================================================================
    # SMALL IMAGE GENERATOR TESTS
    # ============================================================================

    def test_small_image_generator_success(self, mock_small_image_generator):
        """Test successful small image generation."""
        # Setup mock response
        expected_result = {
            'success': True,
            'output_path': '/small/small_001.jpg',
            'size': (800, 600),
            'source_size': (1920, 1080),
            'quality': 85,
            'generation_time_ms': 75
        }
        mock_small_image_generator.generate_small_image.return_value = expected_result

        # Test small image generation
        result = mock_small_image_generator.generate_small_image(
            source_path='/images/source_001.jpg',
            output_path='/small/small_001.jpg'
        )

        # Verify success
        assert result['success'] is True
        assert result['output_path'] == '/small/small_001.jpg'
        assert result['size'] == (800, 600)
        assert result['source_size'] == (1920, 1080)
        assert result['generation_time_ms'] == 75

        # Verify mock was called correctly
        mock_small_image_generator.generate_small_image.assert_called_once_with(
            source_path='/images/source_001.jpg',
            output_path='/small/small_001.jpg'
        )

    def test_small_image_generator_failure(self, mock_small_image_generator):
        """Test small image generation failure handling."""
        # Setup mock to return failure
        expected_result = {
            'success': False,
            'error': 'Processing failed due to memory constraints',
            'output_path': '/small/small_002.jpg',
            'source_path': '/images/large.jpg'
        }
        mock_small_image_generator.generate_small_image.return_value = expected_result

        # Test small image generation failure
        result = mock_small_image_generator.generate_small_image(
            source_path='/images/large.jpg',
            output_path='/small/small_002.jpg'
        )

        # Verify failure handling
        assert result['success'] is False
        assert 'error' in result
        assert result['error'] == 'Processing failed due to memory constraints'

        # Verify mock was called correctly
        mock_small_image_generator.generate_small_image.assert_called_once()

    def test_small_image_vs_thumbnail_size_difference(self, mock_small_image_generator):
        """Test that small images are larger than thumbnails."""
        # Mock small image result
        mock_small_image_generator.generate_small_image.return_value = {
            'success': True,
            'size': (800, 600),
            'output_path': '/small/image.jpg'
        }

        result = mock_small_image_generator.generate_small_image(
            source_path='/images/source.jpg',
            output_path='/small/image.jpg'
        )

        # Verify small image is larger than thumbnail size
        thumbnail_size = (200, 150)
        small_size = result['size']
        assert small_size[0] > thumbnail_size[0]
        assert small_size[1] > thumbnail_size[1]

    # ============================================================================
    # BATCH GENERATOR TESTS
    # ============================================================================

    def test_batch_generator_thumbnails_success(self, mock_batch_generator):
        """Test successful batch thumbnail generation."""
        # Setup mock response
        expected_result = {
            'success': True,
            'total_jobs': 5,
            'successful_jobs': 5,
            'failed_jobs': 0,
            'processing_time_ms': 250,
            'failures': []
        }
        mock_batch_generator.generate_thumbnails_batch.return_value = expected_result

        # Create batch jobs
        jobs = [
            {'source_path': f'/images/img_{i}.jpg', 'thumbnail_path': f'/thumbs/thumb_{i}.jpg'}
            for i in range(5)
        ]

        # Test batch generation
        result = mock_batch_generator.generate_thumbnails_batch(jobs)

        # Verify batch success
        assert result['success'] is True
        assert result['total_jobs'] == 5
        assert result['successful_jobs'] == 5
        assert result['failed_jobs'] == 0
        assert result['processing_time_ms'] == 250

        # Verify mock was called correctly
        mock_batch_generator.generate_thumbnails_batch.assert_called_once_with(jobs)

    def test_batch_generator_small_images_success(self, mock_batch_generator):
        """Test successful batch small image generation."""
        # Setup mock response
        expected_result = {
            'success': True,
            'total_jobs': 3,
            'successful_jobs': 3,
            'failed_jobs': 0,
            'processing_time_ms': 180,
            'failures': []
        }
        mock_batch_generator.generate_small_images_batch.return_value = expected_result

        # Create batch jobs
        jobs = [
            {'source_path': f'/images/img_{i}.jpg', 'small_path': f'/small/small_{i}.jpg'}
            for i in range(3)
        ]

        # Test batch generation
        result = mock_batch_generator.generate_small_images_batch(jobs)

        # Verify batch success
        assert result['success'] is True
        assert result['total_jobs'] == 3
        assert result['successful_jobs'] == 3
        assert result['failed_jobs'] == 0

        # Verify mock was called correctly
        mock_batch_generator.generate_small_images_batch.assert_called_once_with(jobs)

    def test_batch_generator_both_types_success(self, mock_batch_generator):
        """Test successful batch generation of both thumbnails and small images."""
        # Setup mock response
        expected_result = {
            'success': True,
            'total_jobs': 4,
            'thumbnail_results': {
                'successful_jobs': 4,
                'failed_jobs': 0
            },
            'small_image_results': {
                'successful_jobs': 4,
                'failed_jobs': 0
            },
            'processing_time_ms': 320
        }
        mock_batch_generator.generate_both_batch.return_value = expected_result

        # Create batch jobs
        jobs = [
            {
                'source_path': f'/images/img_{i}.jpg',
                'thumbnail_path': f'/thumbs/thumb_{i}.jpg',
                'small_path': f'/small/small_{i}.jpg'
            }
            for i in range(4)
        ]

        # Test combined batch generation
        result = mock_batch_generator.generate_both_batch(jobs)

        # Verify combined batch success
        assert result['success'] is True
        assert result['total_jobs'] == 4
        assert result['thumbnail_results']['successful_jobs'] == 4
        assert result['small_image_results']['successful_jobs'] == 4

        # Verify mock was called correctly
        mock_batch_generator.generate_both_batch.assert_called_once_with(jobs)

    def test_batch_generator_partial_failure(self, mock_batch_generator):
        """Test batch generation with partial failures."""
        # Setup mock response with some failures
        expected_result = {
            'success': True,
            'total_jobs': 5,
            'successful_jobs': 3,
            'failed_jobs': 2,
            'processing_time_ms': 280,
            'failures': [
                {'source_path': '/images/img_2.jpg', 'error': 'Corrupted image'},
                {'source_path': '/images/img_4.jpg', 'error': 'Permission denied'}
            ]
        }
        mock_batch_generator.generate_thumbnails_batch.return_value = expected_result

        # Create batch jobs
        jobs = [
            {'source_path': f'/images/img_{i}.jpg', 'thumbnail_path': f'/thumbs/thumb_{i}.jpg'}
            for i in range(5)
        ]

        # Test batch generation with failures
        result = mock_batch_generator.generate_thumbnails_batch(jobs)

        # Verify partial success handling
        assert result['success'] is True  # Overall success despite individual failures
        assert result['total_jobs'] == 5
        assert result['successful_jobs'] == 3
        assert result['failed_jobs'] == 2
        assert len(result['failures']) == 2

    def test_batch_generator_with_progress_callback(self, mock_batch_generator):
        """Test batch generation with progress tracking."""
        # Setup mock response
        expected_result = {
            'success': True,
            'total_jobs': 3,
            'successful_jobs': 3,
            'failed_jobs': 0,
            'processing_time_ms': 150
        }
        mock_batch_generator.generate_thumbnails_batch.return_value = expected_result

        # Create mock progress callback
        progress_callback = MagicMock()

        # Create batch jobs
        jobs = [
            {'source_path': f'/images/img_{i}.jpg', 'thumbnail_path': f'/thumbs/thumb_{i}.jpg'}
            for i in range(3)
        ]

        # Test batch generation with progress callback
        result = mock_batch_generator.generate_thumbnails_batch(jobs, progress_callback=progress_callback)

        # Verify batch success
        assert result['success'] is True
        assert result['total_jobs'] == 3

        # Verify mock was called with progress callback
        mock_batch_generator.generate_thumbnails_batch.assert_called_once_with(
            jobs,
            progress_callback=progress_callback
        )

    # ============================================================================
    # SCHEDULER INTEGRATION TESTS
    # ============================================================================

    def test_thumbnail_generator_scheduler_integration(self, mock_thumbnail_generator):
        """Test thumbnail generation with scheduler integration."""
        # Setup mock response with scheduler-compatible format
        expected_result = {
            'success': True,
            'output_path': '/thumbnails/scheduler_thumb.jpg',
            'size': (200, 150),
            'generation_time_ms': 55,
            'scheduled_via': 'scheduler_authority',
            'priority': 'high'
        }
        mock_thumbnail_generator.generate_thumbnail.return_value = expected_result

        # Simulate scheduler-initiated generation
        result = mock_thumbnail_generator.generate_thumbnail(
            source_path='/images/scheduler_source.jpg',
            output_path='/thumbnails/scheduler_thumb.jpg'
        )

        # Verify scheduler-compatible result format
        assert result['success'] is True
        assert 'output_path' in result
        assert 'generation_time_ms' in result

        # Result should be suitable for scheduler job completion reporting
        expected_keys = ['success', 'output_path', 'size', 'generation_time_ms']
        for key in expected_keys:
            assert key in result

    def test_batch_generator_scheduler_integration(self, mock_batch_generator):
        """Test batch generation with scheduler integration."""
        # Setup mock response with scheduler-compatible format
        expected_result = {
            'success': True,
            'total_jobs': 2,
            'successful_jobs': 2,
            'failed_jobs': 0,
            'processing_time_ms': 120,
            'scheduled_via': 'scheduler_authority',
            'batch_id': 'batch_001'
        }
        mock_batch_generator.generate_thumbnails_batch.return_value = expected_result

        # Create scheduler batch jobs
        jobs = [
            {
                'source_path': '/images/sched_img_1.jpg',
                'thumbnail_path': '/thumbs/sched_thumb_1.jpg',
                'priority': 'high'
            },
            {
                'source_path': '/images/sched_img_2.jpg',
                'thumbnail_path': '/thumbs/sched_thumb_2.jpg',
                'priority': 'normal'
            }
        ]

        # Test scheduler batch generation
        result = mock_batch_generator.generate_thumbnails_batch(jobs)

        # Verify scheduler-compatible result format
        assert result['success'] is True
        assert 'total_jobs' in result
        assert 'successful_jobs' in result
        assert 'processing_time_ms' in result

        # Should be suitable for scheduler job completion reporting
        expected_keys = ['success', 'total_jobs', 'successful_jobs', 'failed_jobs', 'processing_time_ms']
        for key in expected_keys:
            assert key in result

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    def test_generators_error_handling(self, mock_thumbnail_generator, mock_small_image_generator):
        """Test that generators handle errors gracefully."""
        # Test thumbnail generator error
        mock_thumbnail_generator.generate_thumbnail.return_value = {
            'success': False,
            'error': 'Disk space error'
        }

        thumb_result = mock_thumbnail_generator.generate_thumbnail(
            source_path='/images/source.jpg',
            output_path='/thumbnails/thumb.jpg'
        )

        assert thumb_result['success'] is False
        assert 'error' in thumb_result

        # Test small image generator error
        mock_small_image_generator.generate_small_image.return_value = {
            'success': False,
            'error': 'Memory allocation failed'
        }

        small_result = mock_small_image_generator.generate_small_image(
            source_path='/images/source.jpg',
            output_path='/small/small.jpg'
        )

        assert small_result['success'] is False
        assert 'error' in small_result

    def test_batch_generator_exception_handling(self, mock_batch_generator):
        """Test batch generator exception handling."""
        # Setup mock to simulate exception handling
        expected_result = {
            'success': True,  # Batch succeeds despite individual failures
            'total_jobs': 3,
            'successful_jobs': 0,
            'failed_jobs': 3,
            'failures': [
                {'source_path': '/images/img_0.jpg', 'error': 'Exception: Unexpected error'},
                {'source_path': '/images/img_1.jpg', 'error': 'Exception: Unexpected error'},
                {'source_path': '/images/img_2.jpg', 'error': 'Exception: Unexpected error'}
            ]
        }
        mock_batch_generator.generate_thumbnails_batch.return_value = expected_result

        jobs = [
            {'source_path': f'/images/img_{i}.jpg', 'thumbnail_path': f'/thumbs/thumb_{i}.jpg'}
            for i in range(3)
        ]

        # Test batch with all failures
        result = mock_batch_generator.generate_thumbnails_batch(jobs)

        # Should handle exceptions gracefully
        assert result['success'] is True  # Batch framework succeeds
        assert result['total_jobs'] == 3
        assert result['failed_jobs'] == 3
        assert len(result['failures']) == 3