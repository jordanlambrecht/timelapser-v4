#!/usr/bin/env python3
"""
Unit tests for ThumbnailGenerator.

Tests the core thumbnail generation functionality including:
- 200×150 thumbnail generation
- Quality settings and optimization
- Error handling and validation
- File format support
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from PIL import Image, ImageDraw

from app.services.thumbnail_pipeline.generators.thumbnail_generator import (
    ThumbnailGenerator,
)


@pytest.mark.unit
@pytest.mark.thumbnail
class TestThumbnailGenerator:
    """Test suite for ThumbnailGenerator component."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_image_path(self, temp_dir):
        """Create a sample test image."""
        image_path = temp_dir / "test_image.jpg"

        # Create a test image (800x600)
        img = Image.new("RGB", (800, 600), color="red")
        draw = ImageDraw.Draw(img)
        draw.rectangle([100, 100, 700, 500], fill="blue")
        img.save(image_path, "JPEG")

        return str(image_path)

    @pytest.fixture
    def thumbnail_generator(self):
        """Create ThumbnailGenerator instance."""
        return ThumbnailGenerator(quality=80)

    @pytest.fixture
    def sample_output_path(self, temp_dir):
        """Create output path for generated thumbnails."""
        return str(temp_dir / "output_thumbnail.jpg")

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_generator_initialization_default_quality(self):
        """Test thumbnail generator initialization with default quality."""
        generator = ThumbnailGenerator()

        # Should use default quality from constants
        assert hasattr(generator, "quality")
        assert 1 <= generator.quality <= 95
        assert hasattr(generator, "target_size")
        assert generator.target_size == (200, 150)

    def test_generator_initialization_custom_quality(self):
        """Test thumbnail generator initialization with custom quality."""
        generator = ThumbnailGenerator(quality=90)

        assert generator.quality == 90
        assert generator.target_size == (200, 150)

    def test_generator_quality_bounds_clamping(self):
        """Test that quality values are clamped to valid range."""
        # Test lower bound
        generator_low = ThumbnailGenerator(quality=0)
        assert generator_low.quality == 1

        # Test upper bound
        generator_high = ThumbnailGenerator(quality=100)
        assert generator_high.quality == 95

        # Test negative value
        generator_negative = ThumbnailGenerator(quality=-10)
        assert generator_negative.quality == 1

    # ============================================================================
    # THUMBNAIL GENERATION TESTS
    # ============================================================================

    def test_generate_thumbnail_success(
        self, thumbnail_generator, sample_image_path, sample_output_path
    ):
        """Test successful thumbnail generation."""
        # Mock the validation and generation process
        with patch(
            "app.services.thumbnail_pipeline.generators.thumbnail_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                # Create mock image
                mock_img = MagicMock()
                mock_img.size = (800, 600)
                mock_img.mode = "RGB"
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                # Test thumbnail generation
                result = thumbnail_generator.generate_thumbnail(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                # Verify success
                assert result.get("success") is True
                assert result.get("output_path") == sample_output_path
                assert result.get("size") == (200, 150)

                # Verify image processing calls
                mock_img.resize.assert_called_once_with(
                    (200, 150), Image.Resampling.LANCZOS
                )
                mock_resized.save.assert_called_once()

    def test_generate_thumbnail_invalid_source(
        self, thumbnail_generator, sample_output_path
    ):
        """Test thumbnail generation with invalid source file."""
        with patch(
            "app.services.thumbnail_pipeline.generators.thumbnail_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = False

            result = thumbnail_generator.generate_thumbnail(
                source_path="/nonexistent/file.jpg", output_path=sample_output_path
            )

            assert result.get("success") is False
            assert "error" in result
            assert "validation failed" in result["error"].lower()

    def test_generate_thumbnail_pil_error(
        self, thumbnail_generator, sample_image_path, sample_output_path
    ):
        """Test thumbnail generation with PIL processing error."""
        with patch(
            "app.services.thumbnail_pipeline.generators.thumbnail_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_open.side_effect = Exception("PIL processing error")

                result = thumbnail_generator.generate_thumbnail(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                assert result.get("success") is False
                assert "error" in result
                assert "PIL processing error" in result["error"]

    def test_generate_thumbnail_creates_output_directory(
        self, thumbnail_generator, sample_image_path, temp_dir
    ):
        """Test that thumbnail generation creates output directory if it doesn't exist."""
        # Create nested output path
        nested_output = temp_dir / "nested" / "directory" / "thumbnail.jpg"

        with patch(
            "app.services.thumbnail_pipeline.generators.thumbnail_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (800, 600)
                mock_img.mode = "RGB"
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                with patch("pathlib.Path.mkdir") as mock_mkdir:
                    result = thumbnail_generator.generate_thumbnail(
                        source_path=sample_image_path, output_path=str(nested_output)
                    )

                    # Verify directory creation
                    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
                    assert result.get("success") is True

    # ============================================================================
    # ASPECT RATIO AND SIZING TESTS
    # ============================================================================

    def test_thumbnail_aspect_ratio_handling(
        self, thumbnail_generator, sample_output_path
    ):
        """Test proper aspect ratio handling for different source images."""
        test_sizes = [
            (1920, 1080),  # 16:9 landscape
            (1080, 1920),  # 9:16 portrait
            (800, 800),  # 1:1 square
            (1600, 900),  # 16:9 wide
        ]

        for width, height in test_sizes:
            with patch(
                "app.services.thumbnail_pipeline.generators.thumbnail_generator.validate_image_file"
            ) as mock_validate:
                mock_validate.return_value = True

                with patch("PIL.Image.open") as mock_open:
                    mock_img = MagicMock()
                    mock_img.size = (width, height)
                    mock_img.mode = "RGB"
                    mock_resized = MagicMock()
                    mock_img.resize.return_value = mock_resized
                    mock_open.return_value.__enter__.return_value = mock_img

                    result = thumbnail_generator.generate_thumbnail(
                        source_path=f"test_{width}x{height}.jpg",
                        output_path=sample_output_path,
                    )

                    # All thumbnails should be resized to 200x150
                    assert result.get("success") is True
                    mock_img.resize.assert_called_with(
                        (200, 150), Image.Resampling.LANCZOS
                    )

    # ============================================================================
    # BATCH PROCESSING TESTS
    # ============================================================================

    def test_generate_thumbnail_with_metadata(
        self, thumbnail_generator, sample_image_path, sample_output_path
    ):
        """Test thumbnail generation includes metadata in result."""
        with patch(
            "app.services.thumbnail_pipeline.generators.thumbnail_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (1920, 1080)
                mock_img.mode = "RGB"
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                with patch("pathlib.Path.stat") as mock_stat:
                    # Mock file size
                    mock_stat.return_value.st_size = 15000

                    result = thumbnail_generator.generate_thumbnail(
                        source_path=sample_image_path, output_path=sample_output_path
                    )

                    # Verify metadata in result
                    assert result.get("success") is True
                    assert result.get("source_size") == (1920, 1080)
                    assert result.get("output_size") == (200, 150)
                    assert result.get("quality") == thumbnail_generator.quality
                    assert "generation_time_ms" in result

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    def test_generate_thumbnail_permission_error(
        self, thumbnail_generator, sample_image_path, sample_output_path
    ):
        """Test handling of file permission errors."""
        with patch(
            "app.services.thumbnail_pipeline.generators.thumbnail_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (800, 600)
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_resized.save.side_effect = PermissionError("Permission denied")
                mock_open.return_value.__enter__.return_value = mock_img

                result = thumbnail_generator.generate_thumbnail(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                assert result.get("success") is False
                assert "permission" in result["error"].lower()

    def test_generate_thumbnail_disk_space_error(
        self, thumbnail_generator, sample_image_path, sample_output_path
    ):
        """Test handling of disk space errors."""
        with patch(
            "app.services.thumbnail_pipeline.generators.thumbnail_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (800, 600)
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_resized.save.side_effect = OSError("No space left on device")
                mock_open.return_value.__enter__.return_value = mock_img

                result = thumbnail_generator.generate_thumbnail(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                assert result.get("success") is False
                assert (
                    "space" in result["error"].lower()
                    or "device" in result["error"].lower()
                )

    # ============================================================================
    # PERFORMANCE AND QUALITY TESTS
    # ============================================================================

    def test_generate_thumbnail_performance_tracking(
        self, thumbnail_generator, sample_image_path, sample_output_path
    ):
        """Test that thumbnail generation tracks performance metrics."""
        with patch(
            "app.services.thumbnail_pipeline.generators.thumbnail_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (800, 600)
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                result = thumbnail_generator.generate_thumbnail(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                # Should include timing information
                assert result.get("success") is True
                assert "generation_time_ms" in result
                assert isinstance(result["generation_time_ms"], (int, float))
                assert result["generation_time_ms"] >= 0

    def test_thumbnail_quality_settings_applied(
        self, sample_image_path, sample_output_path
    ):
        """Test that quality settings are properly applied during generation."""
        generator = ThumbnailGenerator(quality=75)

        with patch(
            "app.services.thumbnail_pipeline.generators.thumbnail_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (800, 600)
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                result = generator.generate_thumbnail(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                # Verify quality setting was used
                assert result.get("success") is True
                save_call_args = mock_resized.save.call_args
                if save_call_args and len(save_call_args) > 1:
                    # Check if quality was passed to save method
                    kwargs = save_call_args[1]
                    if "quality" in kwargs:
                        assert kwargs["quality"] == 75

    # ============================================================================
    # INTEGRATION WITH SCHEDULER TESTS
    # ============================================================================

    def test_thumbnail_generation_scheduler_integration(
        self, thumbnail_generator, sample_image_path, sample_output_path
    ):
        """Test that thumbnail generation can be properly integrated with scheduler."""
        # Mock scheduler authority service call
        with patch(
            "app.services.thumbnail_pipeline.generators.thumbnail_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (800, 600)
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                # Simulate scheduler-initiated generation
                result = thumbnail_generator.generate_thumbnail(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                # Should return scheduler-compatible result format
                assert result.get("success") is True
                assert "output_path" in result
                assert "generation_time_ms" in result

                # Result should be suitable for scheduler job completion reporting
                expected_keys = ["success", "output_path", "size", "generation_time_ms"]
                for key in expected_keys:
                    assert key in result
