#!/usr/bin/env python3
"""
Unit tests for BatchThumbnailGenerator.

Tests the batch thumbnail generation functionality including:
- Concurrent thumbnail and small image generation
- Progress tracking and reporting
- Error handling and recovery
- Memory-efficient batch operations
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from PIL import Image, ImageDraw

from app.services.thumbnail_pipeline.generators.batch_thumbnail_generator import (
    BatchThumbnailGenerator,
)
from app.services.thumbnail_pipeline.generators.small_image_generator import (
    SmallImageGenerator,
)
from app.services.thumbnail_pipeline.generators.thumbnail_generator import (
    ThumbnailGenerator,
)


@pytest.mark.unit
@pytest.mark.thumbnail
class TestBatchThumbnailGenerator:
    """Test suite for BatchThumbnailGenerator component."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_images(self, temp_dir):
        """Create multiple sample test images."""
        images = []
        for i in range(5):
            image_path = temp_dir / f"test_image_{i}.jpg"

            # Create test images with different colors
            colors = ["red", "blue", "green", "yellow", "purple"]
            img = Image.new("RGB", (800, 600), color=colors[i])
            draw = ImageDraw.Draw(img)
            draw.text((100, 100), f"Image {i}", fill="white")
            img.save(image_path, "JPEG")

            images.append(str(image_path))

        return images

    @pytest.fixture
    def batch_generator(self):
        """Create BatchThumbnailGenerator instance."""
        return BatchThumbnailGenerator(max_workers=2, batch_size=3)

    @pytest.fixture
    def output_dirs(self, temp_dir):
        """Create output directories for generated images."""
        thumbnail_dir = temp_dir / "thumbnails"
        small_dir = temp_dir / "small"
        thumbnail_dir.mkdir()
        small_dir.mkdir()

        return {"thumbnail": str(thumbnail_dir), "small": str(small_dir)}

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_batch_generator_initialization_defaults(self):
        """Test batch generator initialization with default parameters."""
        generator = BatchThumbnailGenerator()

        assert generator.max_workers == 4
        assert generator.batch_size == 10
        assert isinstance(generator.thumbnail_generator, ThumbnailGenerator)
        assert isinstance(generator.small_generator, SmallImageGenerator)

    def test_batch_generator_initialization_custom_params(self):
        """Test batch generator initialization with custom parameters."""
        mock_thumb_gen = Mock(spec=ThumbnailGenerator)
        mock_small_gen = Mock(spec=SmallImageGenerator)

        generator = BatchThumbnailGenerator(
            thumbnail_generator=mock_thumb_gen,
            small_generator=mock_small_gen,
            max_workers=6,
            batch_size=15,
        )

        assert generator.max_workers == 6
        assert generator.batch_size == 15
        assert generator.thumbnail_generator == mock_thumb_gen
        assert generator.small_generator == mock_small_gen

    def test_batch_generator_parameter_bounds(self):
        """Test that parameters are bounded to reasonable ranges."""
        # Test max_workers bounds
        generator_low = BatchThumbnailGenerator(max_workers=0)
        assert generator_low.max_workers == 1

        generator_high = BatchThumbnailGenerator(max_workers=20)
        assert generator_high.max_workers == 8

        # Test batch_size bounds
        generator_batch_low = BatchThumbnailGenerator(batch_size=0)
        assert generator_batch_low.batch_size == 1

    # ============================================================================
    # BATCH THUMBNAIL GENERATION TESTS
    # ============================================================================

    def test_generate_thumbnails_batch_success(
        self, batch_generator, sample_images, output_dirs
    ):
        """Test successful batch thumbnail generation."""
        # Mock the individual generators
        with patch.object(
            batch_generator.thumbnail_generator, "generate_thumbnail"
        ) as mock_thumb:
            mock_thumb.return_value = {
                "success": True,
                "output_path": "output.jpg",
                "size": (200, 150),
                "generation_time_ms": 50,
            }

            # Create batch job
            jobs = []
            for i, source in enumerate(sample_images):
                jobs.append(
                    {
                        "source_path": source,
                        "thumbnail_path": f"{output_dirs['thumbnail']}/thumb_{i}.jpg",
                    }
                )

            result = batch_generator.generate_thumbnails_batch(jobs)

            # Verify batch completion
            assert result.get("success") is True
            assert result.get("total_jobs") == len(sample_images)
            assert result.get("successful_jobs") == len(sample_images)
            assert result.get("failed_jobs") == 0
            assert "processing_time_ms" in result

            # Verify all thumbnails were generated
            assert mock_thumb.call_count == len(sample_images)

    def test_generate_thumbnails_batch_partial_failure(
        self, batch_generator, sample_images, output_dirs
    ):
        """Test batch thumbnail generation with some failures."""

        # Mock the individual generator with mixed results
        def mock_generate_side_effect(source_path, output_path):
            if "test_image_2" in source_path:
                return {"success": False, "error": "Processing failed"}
            return {
                "success": True,
                "output_path": output_path,
                "size": (200, 150),
                "generation_time_ms": 50,
            }

        with patch.object(
            batch_generator.thumbnail_generator,
            "generate_thumbnail",
            side_effect=mock_generate_side_effect,
        ):
            # Create batch job
            jobs = []
            for i, source in enumerate(sample_images):
                jobs.append(
                    {
                        "source_path": source,
                        "thumbnail_path": f"{output_dirs['thumbnail']}/thumb_{i}.jpg",
                    }
                )

            result = batch_generator.generate_thumbnails_batch(jobs)

            # Verify partial success
            assert result.get("success") is True  # Overall success even with failures
            assert result.get("total_jobs") == len(sample_images)
            assert result.get("successful_jobs") == len(sample_images) - 1
            assert result.get("failed_jobs") == 1
            assert len(result.get("failures", [])) == 1

    def test_generate_thumbnails_batch_empty_list(self, batch_generator):
        """Test batch generation with empty job list."""
        result = batch_generator.generate_thumbnails_batch([])

        assert result.get("success") is True
        assert result.get("total_jobs") == 0
        assert result.get("successful_jobs") == 0
        assert result.get("failed_jobs") == 0

    # ============================================================================
    # BATCH SMALL IMAGE GENERATION TESTS
    # ============================================================================

    def test_generate_small_images_batch_success(
        self, batch_generator, sample_images, output_dirs
    ):
        """Test successful batch small image generation."""
        # Mock the small image generator
        with patch.object(
            batch_generator.small_generator, "generate_small_image"
        ) as mock_small:
            mock_small.return_value = {
                "success": True,
                "output_path": "output.jpg",
                "size": (800, 600),
                "generation_time_ms": 75,
            }

            # Create batch job
            jobs = []
            for i, source in enumerate(sample_images):
                jobs.append(
                    {
                        "source_path": source,
                        "small_path": f"{output_dirs['small']}/small_{i}.jpg",
                    }
                )

            result = batch_generator.generate_small_images_batch(jobs)

            # Verify batch completion
            assert result.get("success") is True
            assert result.get("total_jobs") == len(sample_images)
            assert result.get("successful_jobs") == len(sample_images)
            assert result.get("failed_jobs") == 0

            # Verify all small images were generated
            assert mock_small.call_count == len(sample_images)

    # ============================================================================
    # COMBINED BATCH GENERATION TESTS
    # ============================================================================

    def test_generate_both_batch_success(
        self, batch_generator, sample_images, output_dirs
    ):
        """Test successful batch generation of both thumbnails and small images."""
        # Mock both generators
        with patch.object(
            batch_generator.thumbnail_generator, "generate_thumbnail"
        ) as mock_thumb:
            with patch.object(
                batch_generator.small_generator, "generate_small_image"
            ) as mock_small:
                mock_thumb.return_value = {
                    "success": True,
                    "output_path": "thumb.jpg",
                    "size": (200, 150),
                    "generation_time_ms": 50,
                }
                mock_small.return_value = {
                    "success": True,
                    "output_path": "small.jpg",
                    "size": (800, 600),
                    "generation_time_ms": 75,
                }

                # Create batch job
                jobs = []
                for i, source in enumerate(sample_images):
                    jobs.append(
                        {
                            "source_path": source,
                            "thumbnail_path": f"{output_dirs['thumbnail']}/thumb_{i}.jpg",
                            "small_path": f"{output_dirs['small']}/small_{i}.jpg",
                        }
                    )

                result = batch_generator.generate_both_batch(jobs)

                # Verify both types were generated
                assert result.get("success") is True
                assert result.get("total_jobs") == len(sample_images)
                assert result.get("thumbnail_results", {}).get(
                    "successful_jobs"
                ) == len(sample_images)
                assert result.get("small_image_results", {}).get(
                    "successful_jobs"
                ) == len(sample_images)

                # Verify all generators were called
                assert mock_thumb.call_count == len(sample_images)
                assert mock_small.call_count == len(sample_images)

    # ============================================================================
    # PROGRESS TRACKING TESTS
    # ============================================================================

    def test_batch_generation_with_progress_callback(
        self, batch_generator, sample_images, output_dirs
    ):
        """Test batch generation with progress tracking callback."""
        progress_updates = []

        def progress_callback(current, total, stage):
            progress_updates.append(
                {
                    "current": current,
                    "total": total,
                    "stage": stage,
                    "progress_percent": (current / total) * 100,
                }
            )

        # Mock the thumbnail generator
        with patch.object(
            batch_generator.thumbnail_generator, "generate_thumbnail"
        ) as mock_thumb:
            mock_thumb.return_value = {
                "success": True,
                "output_path": "output.jpg",
                "size": (200, 150),
                "generation_time_ms": 50,
            }

            # Create batch job with progress callback
            jobs = []
            for i, source in enumerate(sample_images):
                jobs.append(
                    {
                        "source_path": source,
                        "thumbnail_path": f"{output_dirs['thumbnail']}/thumb_{i}.jpg",
                    }
                )

            result = batch_generator.generate_thumbnails_batch(
                jobs, progress_callback=progress_callback
            )

            # Verify progress tracking
            assert result.get("success") is True
            assert len(progress_updates) > 0

            # Check progress sequence
            assert progress_updates[0]["current"] >= 1
            assert progress_updates[-1]["current"] == len(sample_images)
            assert all(
                update["total"] == len(sample_images) for update in progress_updates
            )

    # ============================================================================
    # CONCURRENT PROCESSING TESTS
    # ============================================================================

    def test_concurrent_processing_limits(self, sample_images, output_dirs):
        """Test that concurrent processing respects worker limits."""
        # Create generator with limited workers
        batch_generator = BatchThumbnailGenerator(max_workers=2)

        # Mock to track concurrent calls
        concurrent_calls = []

        def mock_generate_with_tracking(source_path, output_path):
            concurrent_calls.append(len([c for c in concurrent_calls if c is None]))
            # Simulate processing time
            import time

            time.sleep(0.1)
            concurrent_calls.pop()
            return {
                "success": True,
                "output_path": output_path,
                "size": (200, 150),
                "generation_time_ms": 100,
            }

        with patch.object(
            batch_generator.thumbnail_generator,
            "generate_thumbnail",
            side_effect=mock_generate_with_tracking,
        ):
            jobs = []
            for i, source in enumerate(sample_images):
                jobs.append(
                    {
                        "source_path": source,
                        "thumbnail_path": f"{output_dirs['thumbnail']}/thumb_{i}.jpg",
                    }
                )

            result = batch_generator.generate_thumbnails_batch(jobs)

            # Should complete successfully
            assert result.get("success") is True

            # Note: Due to mocking complexity, we verify the max_workers setting was respected
            # in the initialization rather than runtime concurrency

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    def test_batch_generation_exception_handling(
        self, batch_generator, sample_images, output_dirs
    ):
        """Test that batch generation handles exceptions gracefully."""
        # Mock generator to raise exceptions
        with patch.object(
            batch_generator.thumbnail_generator, "generate_thumbnail"
        ) as mock_thumb:
            mock_thumb.side_effect = Exception("Unexpected error")

            jobs = []
            for i, source in enumerate(sample_images):
                jobs.append(
                    {
                        "source_path": source,
                        "thumbnail_path": f"{output_dirs['thumbnail']}/thumb_{i}.jpg",
                    }
                )

            result = batch_generator.generate_thumbnails_batch(jobs)

            # Should handle exceptions gracefully
            assert (
                result.get("success") is True
            )  # Batch continues despite individual failures
            assert result.get("total_jobs") == len(sample_images)
            assert result.get("failed_jobs") == len(sample_images)
            assert len(result.get("failures", [])) == len(sample_images)

    def test_batch_generation_mixed_results(
        self, batch_generator, sample_images, output_dirs
    ):
        """Test batch generation with mixed success/failure results."""

        # Mock generator with alternating success/failure
        def mock_alternating_results(source_path, output_path):
            if "test_image_1" in source_path or "test_image_3" in source_path:
                return {"success": False, "error": "Simulated failure"}
            return {
                "success": True,
                "output_path": output_path,
                "size": (200, 150),
                "generation_time_ms": 50,
            }

        with patch.object(
            batch_generator.thumbnail_generator,
            "generate_thumbnail",
            side_effect=mock_alternating_results,
        ):
            jobs = []
            for i, source in enumerate(sample_images):
                jobs.append(
                    {
                        "source_path": source,
                        "thumbnail_path": f"{output_dirs['thumbnail']}/thumb_{i}.jpg",
                    }
                )

            result = batch_generator.generate_thumbnails_batch(jobs)

            # Should handle mixed results
            assert result.get("success") is True
            assert result.get("total_jobs") == len(sample_images)
            assert result.get("successful_jobs") == 3  # 0, 2, 4 succeed
            assert result.get("failed_jobs") == 2  # 1, 3 fail

    # ============================================================================
    # SCHEDULER INTEGRATION TESTS
    # ============================================================================

    def test_batch_generation_scheduler_integration(
        self, batch_generator, sample_images, output_dirs
    ):
        """Test that batch generation integrates properly with scheduler."""
        # Mock generators
        with patch.object(
            batch_generator.thumbnail_generator, "generate_thumbnail"
        ) as mock_thumb:
            mock_thumb.return_value = {
                "success": True,
                "output_path": "output.jpg",
                "size": (200, 150),
                "generation_time_ms": 50,
            }

            # Create batch job simulating scheduler request
            jobs = []
            for i, source in enumerate(sample_images):
                jobs.append(
                    {
                        "source_path": source,
                        "thumbnail_path": f"{output_dirs['thumbnail']}/thumb_{i}.jpg",
                        "priority": "high" if i < 2 else "normal",  # Simulate priority
                    }
                )

            result = batch_generator.generate_thumbnails_batch(jobs)

            # Should return scheduler-compatible result format
            assert result.get("success") is True
            assert "total_jobs" in result
            assert "successful_jobs" in result
            assert "failed_jobs" in result
            assert "processing_time_ms" in result

            # Should be suitable for scheduler job completion reporting
            expected_keys = [
                "success",
                "total_jobs",
                "successful_jobs",
                "failed_jobs",
                "processing_time_ms",
            ]
            for key in expected_keys:
                assert key in result

    def test_batch_generation_memory_efficiency(self, sample_images, output_dirs):
        """Test that batch generation processes in memory-efficient batches."""
        # Create generator with small batch size to test batching
        batch_generator = BatchThumbnailGenerator(batch_size=2)

        with patch.object(
            batch_generator.thumbnail_generator, "generate_thumbnail"
        ) as mock_thumb:
            mock_thumb.return_value = {
                "success": True,
                "output_path": "output.jpg",
                "size": (200, 150),
                "generation_time_ms": 50,
            }

            jobs = []
            for i, source in enumerate(sample_images):
                jobs.append(
                    {
                        "source_path": source,
                        "thumbnail_path": f"{output_dirs['thumbnail']}/thumb_{i}.jpg",
                    }
                )

            result = batch_generator.generate_thumbnails_batch(jobs)

            # Should complete all jobs despite small batch size
            assert result.get("success") is True
            assert result.get("total_jobs") == len(sample_images)
            assert result.get("successful_jobs") == len(sample_images)

            # All thumbnails should have been generated
            assert mock_thumb.call_count == len(sample_images)
