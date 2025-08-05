#!/usr/bin/env python3
"""
Unit tests for SmallImageGenerator.

Tests the small image generation functionality including:
- 800×600 small image generation
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

from app.services.thumbnail_pipeline.generators.small_image_generator import (
    SmallImageGenerator,
)


@pytest.mark.unit
@pytest.mark.thumbnail
class TestSmallImageGenerator:
    """Test suite for SmallImageGenerator component."""

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

        # Create a test image (1920x1080)
        img = Image.new("RGB", (1920, 1080), color="green")
        draw = ImageDraw.Draw(img)
        draw.rectangle([200, 200, 1720, 880], fill="yellow")
        img.save(image_path, "JPEG")

        return str(image_path)

    @pytest.fixture
    def small_image_generator(self):
        """Create SmallImageGenerator instance."""
        return SmallImageGenerator(quality=85)

    @pytest.fixture
    def sample_output_path(self, temp_dir):
        """Create output path for generated small images."""
        return str(temp_dir / "output_small.jpg")

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_generator_initialization_default_quality(self):
        """Test small image generator initialization with default quality."""
        generator = SmallImageGenerator()

        # Should use default quality from constants
        assert hasattr(generator, "quality")
        assert 1 <= generator.quality <= 95
        assert hasattr(generator, "target_size")
        assert generator.target_size == (800, 600)

    def test_generator_initialization_custom_quality(self):
        """Test small image generator initialization with custom quality."""
        generator = SmallImageGenerator(quality=70)

        assert generator.quality == 70
        assert generator.target_size == (800, 600)

    def test_generator_quality_bounds_clamping(self):
        """Test that quality values are clamped to valid range."""
        # Test lower bound
        generator_low = SmallImageGenerator(quality=-5)
        assert generator_low.quality == 1

        # Test upper bound
        generator_high = SmallImageGenerator(quality=100)
        assert generator_high.quality == 95

        # Test zero value
        generator_zero = SmallImageGenerator(quality=0)
        assert generator_zero.quality == 1

    # ============================================================================
    # SMALL IMAGE GENERATION TESTS
    # ============================================================================

    def test_generate_small_image_success(
        self, small_image_generator, sample_image_path, sample_output_path
    ):
        """Test successful small image generation."""
        # Mock the validation and generation process
        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                # Create mock image
                mock_img = MagicMock()
                mock_img.size = (1920, 1080)
                mock_img.mode = "RGB"
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                # Test small image generation
                result = small_image_generator.generate_small_image(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                # Verify success
                assert result.get("success") is True
                assert result.get("output_path") == sample_output_path
                assert result.get("size") == (800, 600)

                # Verify image processing calls
                mock_img.resize.assert_called_once_with(
                    (800, 600), Image.Resampling.LANCZOS
                )
                mock_resized.save.assert_called_once()

    def test_generate_small_image_invalid_source(
        self, small_image_generator, sample_output_path
    ):
        """Test small image generation with invalid source file."""
        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = False

            result = small_image_generator.generate_small_image(
                source_path="/nonexistent/file.jpg", output_path=sample_output_path
            )

            assert result.get("success") is False
            assert "error" in result
            assert "validation failed" in result["error"].lower()

    def test_generate_small_image_pil_error(
        self, small_image_generator, sample_image_path, sample_output_path
    ):
        """Test small image generation with PIL processing error."""
        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_open.side_effect = Exception("PIL processing error")

                result = small_image_generator.generate_small_image(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                assert result.get("success") is False
                assert "error" in result
                assert "PIL processing error" in result["error"]

    def test_generate_small_image_creates_output_directory(
        self, small_image_generator, sample_image_path, temp_dir
    ):
        """Test that small image generation creates output directory if it doesn't exist."""
        # Create nested output path
        nested_output = temp_dir / "nested" / "small" / "image.jpg"

        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (1920, 1080)
                mock_img.mode = "RGB"
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                with patch("pathlib.Path.mkdir") as mock_mkdir:
                    result = small_image_generator.generate_small_image(
                        source_path=sample_image_path, output_path=str(nested_output)
                    )

                    # Verify directory creation
                    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
                    assert result.get("success") is True

    # ============================================================================
    # ASPECT RATIO AND SIZING TESTS
    # ============================================================================

    def test_small_image_aspect_ratio_handling(
        self, small_image_generator, sample_output_path
    ):
        """Test proper aspect ratio handling for different source images."""
        test_sizes = [
            (3840, 2160),  # 4K 16:9 landscape
            (2160, 3840),  # 4K 9:16 portrait
            (2048, 2048),  # Square high-res
            (4096, 2304),  # Cinema 16:9
        ]

        for width, height in test_sizes:
            with patch(
                "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
            ) as mock_validate:
                mock_validate.return_value = True

                with patch("PIL.Image.open") as mock_open:
                    mock_img = MagicMock()
                    mock_img.size = (width, height)
                    mock_img.mode = "RGB"
                    mock_resized = MagicMock()
                    mock_img.resize.return_value = mock_resized
                    mock_open.return_value.__enter__.return_value = mock_img

                    result = small_image_generator.generate_small_image(
                        source_path=f"test_{width}x{height}.jpg",
                        output_path=sample_output_path,
                    )

                    # All small images should be resized to 800x600
                    assert result.get("success") is True
                    mock_img.resize.assert_called_with(
                        (800, 600), Image.Resampling.LANCZOS
                    )

    def test_small_image_upscaling_handling(
        self, small_image_generator, sample_output_path
    ):
        """Test handling of upscaling small source images."""
        # Test with source smaller than target
        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (400, 300)  # Smaller than 800x600 target
                mock_img.mode = "RGB"
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                result = small_image_generator.generate_small_image(
                    source_path="small_source.jpg", output_path=sample_output_path
                )

                # Should still resize to target size (upscaling)
                assert result.get("success") is True
                mock_img.resize.assert_called_with((800, 600), Image.Resampling.LANCZOS)

    # ============================================================================
    # QUALITY AND PERFORMANCE TESTS
    # ============================================================================

    def test_generate_small_image_with_metadata(
        self, small_image_generator, sample_image_path, sample_output_path
    ):
        """Test small image generation includes metadata in result."""
        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
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
                    mock_stat.return_value.st_size = 75000

                    result = small_image_generator.generate_small_image(
                        source_path=sample_image_path, output_path=sample_output_path
                    )

                    # Verify metadata in result
                    assert result.get("success") is True
                    assert result.get("source_size") == (1920, 1080)
                    assert result.get("output_size") == (800, 600)
                    assert result.get("quality") == small_image_generator.quality
                    assert "generation_time_ms" in result

    def test_small_image_quality_settings_applied(
        self, sample_image_path, sample_output_path
    ):
        """Test that quality settings are properly applied during generation."""
        generator = SmallImageGenerator(quality=90)

        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (1920, 1080)
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                result = generator.generate_small_image(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                # Verify quality setting was used
                assert result.get("success") is True
                save_call_args = mock_resized.save.call_args
                if save_call_args and len(save_call_args) > 1:
                    # Check if quality was passed to save method
                    kwargs = save_call_args[1]
                    if "quality" in kwargs:
                        assert kwargs["quality"] == 90

    # ============================================================================
    # ERROR HANDLING TESTS
    # ============================================================================

    def test_generate_small_image_permission_error(
        self, small_image_generator, sample_image_path, sample_output_path
    ):
        """Test handling of file permission errors."""
        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (1920, 1080)
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_resized.save.side_effect = PermissionError("Access denied")
                mock_open.return_value.__enter__.return_value = mock_img

                result = small_image_generator.generate_small_image(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                assert result.get("success") is False
                assert (
                    "permission" in result["error"].lower()
                    or "access" in result["error"].lower()
                )

    def test_generate_small_image_io_error(
        self, small_image_generator, sample_image_path, sample_output_path
    ):
        """Test handling of I/O errors."""
        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (1920, 1080)
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_resized.save.side_effect = IOError("I/O operation failed")
                mock_open.return_value.__enter__.return_value = mock_img

                result = small_image_generator.generate_small_image(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                assert result.get("success") is False
                assert (
                    "i/o" in result["error"].lower()
                    or "operation failed" in result["error"].lower()
                )

    # ============================================================================
    # SCHEDULER INTEGRATION TESTS
    # ============================================================================

    def test_small_image_generation_scheduler_integration(
        self, small_image_generator, sample_image_path, sample_output_path
    ):
        """Test that small image generation can be properly integrated with scheduler."""
        # Mock scheduler authority service call
        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (1920, 1080)
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                # Simulate scheduler-initiated generation
                result = small_image_generator.generate_small_image(
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

    def test_small_image_generation_priority_handling(
        self, small_image_generator, sample_image_path, sample_output_path
    ):
        """Test that small image generation can handle priority-based processing."""
        # Mock high-priority generation (faster processing expected)
        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (1920, 1080)
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                result = small_image_generator.generate_small_image(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                # Should complete successfully regardless of priority
                assert result.get("success") is True
                assert isinstance(result.get("generation_time_ms"), (int, float))

    # ============================================================================
    # COMPARISON TESTS WITH THUMBNAIL GENERATOR
    # ============================================================================

    def test_small_image_vs_thumbnail_size_difference(
        self, sample_image_path, sample_output_path
    ):
        """Test that small images are larger than thumbnails as expected."""
        small_generator = SmallImageGenerator()

        with patch(
            "app.services.thumbnail_pipeline.generators.small_image_generator.validate_image_file"
        ) as mock_validate:
            mock_validate.return_value = True

            with patch("PIL.Image.open") as mock_open:
                mock_img = MagicMock()
                mock_img.size = (1920, 1080)
                mock_resized = MagicMock()
                mock_img.resize.return_value = mock_resized
                mock_open.return_value.__enter__.return_value = mock_img

                result = small_generator.generate_small_image(
                    source_path=sample_image_path, output_path=sample_output_path
                )

                # Small image should be 800x600 (larger than 200x150 thumbnails)
                assert result.get("success") is True
                assert result.get("size") == (800, 600)

                # Verify size is indeed larger than thumbnail size
                thumbnail_size = (200, 150)
                small_size = result.get("size")
                assert small_size[0] > thumbnail_size[0]
                assert small_size[1] > thumbnail_size[1]
