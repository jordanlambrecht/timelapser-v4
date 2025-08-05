#!/usr/bin/env python3
"""
Unit tests for Thumbnail Utils and Helper Functions.

Tests the utility functions and constants used throughout the thumbnail pipeline:
- Image validation functions
- File format support
- Constants and configuration
- Path resolution utilities
"""

import shutil
import tempfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

# Import thumbnail utils (adjust path as needed based on actual structure)
try:
    from app.services.thumbnail_pipeline.utils.constants import (
        MAX_IMAGE_SIZE_MB,
        SMALL_IMAGE_QUALITY,
        SMALL_IMAGE_SIZE,
        SUPPORTED_IMAGE_FORMATS,
        THUMBNAIL_QUALITY,
        THUMBNAIL_SIZE,
    )
    from app.services.thumbnail_pipeline.utils.thumbnail_utils import (
        calculate_thumbnail_size,
        estimate_processing_time,
        generate_thumbnail_path,
        get_image_dimensions,
        is_supported_format,
        validate_image_file,
    )
except ImportError:
    # Fallback for testing - these may not exist yet
    pytest.skip("Thumbnail utils not available", allow_module_level=True)


@pytest.mark.unit
@pytest.mark.thumbnail
class TestThumbnailUtils:
    """Test suite for thumbnail utility functions."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_image_path(self, temp_dir):
        """Create a sample valid image file."""
        image_path = temp_dir / "valid_image.jpg"

        img = Image.new("RGB", (800, 600), color="blue")
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 750, 550], fill="white")
        img.save(image_path, "JPEG", quality=90)

        return str(image_path)

    @pytest.fixture
    def invalid_file_path(self, temp_dir):
        """Create an invalid (non-image) file."""
        invalid_path = temp_dir / "invalid.txt"
        with open(invalid_path, "w") as f:
            f.write("This is not an image file")
        return str(invalid_path)

    # ============================================================================
    # IMAGE VALIDATION TESTS
    # ============================================================================

    def test_validate_image_file_valid_image(self, sample_image_path):
        """Test validation of valid image file."""
        if "validate_image_file" not in globals():
            pytest.skip("validate_image_file not available")

        result = validate_image_file(sample_image_path)
        assert result is True

    def test_validate_image_file_nonexistent(self):
        """Test validation of non-existent file."""
        if "validate_image_file" not in globals():
            pytest.skip("validate_image_file not available")

        result = validate_image_file("/nonexistent/file.jpg")
        assert result is False

    def test_validate_image_file_invalid_format(self, invalid_file_path):
        """Test validation of invalid file format."""
        if "validate_image_file" not in globals():
            pytest.skip("validate_image_file not available")

        result = validate_image_file(invalid_file_path)
        assert result is False

    def test_validate_image_file_corrupted_image(self, temp_dir):
        """Test validation of corrupted image file."""
        if "validate_image_file" not in globals():
            pytest.skip("validate_image_file not available")

        # Create a corrupted image file
        corrupted_path = temp_dir / "corrupted.jpg"
        with open(corrupted_path, "wb") as f:
            f.write(b"Not a valid JPEG file content")

        result = validate_image_file(str(corrupted_path))
        assert result is False

    # ============================================================================
    # IMAGE DIMENSION TESTS
    # ============================================================================

    def test_get_image_dimensions_valid(self, sample_image_path):
        """Test getting dimensions from valid image."""
        if "get_image_dimensions" not in globals():
            pytest.skip("get_image_dimensions not available")

        dimensions = get_image_dimensions(sample_image_path)
        assert dimensions == (800, 600)

    def test_get_image_dimensions_invalid(self, invalid_file_path):
        """Test getting dimensions from invalid file."""
        if "get_image_dimensions" not in globals():
            pytest.skip("get_image_dimensions not available")

        dimensions = get_image_dimensions(invalid_file_path)
        assert dimensions is None

    def test_get_image_dimensions_various_sizes(self, temp_dir):
        """Test dimension detection for various image sizes."""
        if "get_image_dimensions" not in globals():
            pytest.skip("get_image_dimensions not available")

        test_sizes = [(100, 100), (1920, 1080), (640, 480), (2048, 1536)]

        for width, height in test_sizes:
            img_path = temp_dir / f"test_{width}x{height}.jpg"
            img = Image.new("RGB", (width, height), color="red")
            img.save(img_path, "JPEG")

            dimensions = get_image_dimensions(str(img_path))
            assert dimensions == (width, height)

    # ============================================================================
    # SIZE CALCULATION TESTS
    # ============================================================================

    def test_calculate_thumbnail_size_standard(self):
        """Test thumbnail size calculation for standard images."""
        if "calculate_thumbnail_size" not in globals():
            pytest.skip("calculate_thumbnail_size not available")

        # Test 16:9 landscape
        size = calculate_thumbnail_size((1920, 1080), target=(200, 150))
        assert size == (200, 150)  # Should fit within target

        # Test 4:3 landscape
        size = calculate_thumbnail_size((800, 600), target=(200, 150))
        assert size == (200, 150)

        # Test portrait
        size = calculate_thumbnail_size((1080, 1920), target=(200, 150))
        assert size == (200, 150)  # Should be constrained to target

    def test_calculate_thumbnail_size_edge_cases(self):
        """Test thumbnail size calculation for edge cases."""
        if "calculate_thumbnail_size" not in globals():
            pytest.skip("calculate_thumbnail_size not available")

        # Very wide image
        size = calculate_thumbnail_size((2000, 100), target=(200, 150))
        assert size[0] <= 200 and size[1] <= 150

        # Very tall image
        size = calculate_thumbnail_size((100, 2000), target=(200, 150))
        assert size[0] <= 200 and size[1] <= 150

        # Square image
        size = calculate_thumbnail_size((1000, 1000), target=(200, 150))
        assert size[0] <= 200 and size[1] <= 150

    # ============================================================================
    # FORMAT SUPPORT TESTS
    # ============================================================================

    def test_is_supported_format_valid_formats(self):
        """Test format support detection for valid formats."""
        if "is_supported_format" not in globals():
            pytest.skip("is_supported_format not available")

        valid_formats = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]

        for fmt in valid_formats:
            assert is_supported_format(f"image{fmt}") is True
            assert (
                is_supported_format(f"image{fmt.upper()}") is True
            )  # Case insensitive

    def test_is_supported_format_invalid_formats(self):
        """Test format support detection for invalid formats."""
        if "is_supported_format" not in globals():
            pytest.skip("is_supported_format not available")

        invalid_formats = [".txt", ".pdf", ".doc", ".mp4", ".gif"]

        for fmt in invalid_formats:
            assert is_supported_format(f"file{fmt}") is False

    def test_is_supported_format_no_extension(self):
        """Test format support for files without extensions."""
        if "is_supported_format" not in globals():
            pytest.skip("is_supported_format not available")

        assert is_supported_format("filename_without_extension") is False
        assert is_supported_format("") is False

    # ============================================================================
    # PATH GENERATION TESTS
    # ============================================================================

    def test_generate_thumbnail_path_standard(self):
        """Test thumbnail path generation for standard cases."""
        if "generate_thumbnail_path" not in globals():
            pytest.skip("generate_thumbnail_path not available")

        source = "/data/images/2023-07-01/IMG_001.jpg"
        thumb_dir = "/data/thumbnails/2023-07-01"

        thumb_path = generate_thumbnail_path(source, thumb_dir)

        # Should generate path in thumbnail directory
        assert thumb_path.startswith(thumb_dir)
        assert thumb_path.endswith(".jpg")
        assert "thumb_" in thumb_path or "IMG_001" in thumb_path

    def test_generate_thumbnail_path_various_formats(self):
        """Test thumbnail path generation for various image formats."""
        if "generate_thumbnail_path" not in globals():
            pytest.skip("generate_thumbnail_path not available")

        formats = [".jpg", ".png", ".bmp", ".tiff"]
        thumb_dir = "/thumbnails"

        for fmt in formats:
            source = f"/images/test{fmt}"
            thumb_path = generate_thumbnail_path(source, thumb_dir)

            assert thumb_path.startswith(thumb_dir)
            # Output should typically be .jpg regardless of input format
            assert thumb_path.endswith(".jpg")

    def test_generate_thumbnail_path_nested_structure(self):
        """Test thumbnail path generation with nested directory structure."""
        if "generate_thumbnail_path" not in globals():
            pytest.skip("generate_thumbnail_path not available")

        source = "/data/cameras/cam001/2023/07/01/IMG_123.jpg"
        thumb_dir = "/thumbnails/cam001/2023/07/01"

        thumb_path = generate_thumbnail_path(source, thumb_dir)

        # Should maintain directory structure
        assert thumb_path.startswith(thumb_dir)
        assert "2023/07/01" in thumb_path or "2023-07-01" in thumb_path

    # ============================================================================
    # PROCESSING TIME ESTIMATION TESTS
    # ============================================================================

    def test_estimate_processing_time_by_size(self):
        """Test processing time estimation based on image size."""
        if "estimate_processing_time" not in globals():
            pytest.skip("estimate_processing_time not available")

        # Small image should be faster
        small_time = estimate_processing_time((640, 480))

        # Large image should take longer
        large_time = estimate_processing_time((4096, 3072))

        assert isinstance(small_time, (int, float))
        assert isinstance(large_time, (int, float))
        assert small_time < large_time

    def test_estimate_processing_time_batch(self):
        """Test processing time estimation for batch operations."""
        if "estimate_processing_time" not in globals():
            pytest.skip("estimate_processing_time not available")

        single_time = estimate_processing_time((1920, 1080), count=1)
        batch_time = estimate_processing_time((1920, 1080), count=10)

        # Batch should take longer but less than 10x single (due to parallelization)
        assert batch_time > single_time
        assert batch_time < single_time * 10

    # ============================================================================
    # CONSTANTS VALIDATION TESTS
    # ============================================================================

    def test_thumbnail_constants_validity(self):
        """Test that thumbnail constants are valid."""
        if "THUMBNAIL_SIZE" not in globals():
            pytest.skip("Constants not available")

        # Thumbnail size should be reasonable
        assert isinstance(THUMBNAIL_SIZE, tuple)
        assert len(THUMBNAIL_SIZE) == 2
        assert all(isinstance(dim, int) and dim > 0 for dim in THUMBNAIL_SIZE)

        # Quality should be in valid range
        assert isinstance(THUMBNAIL_QUALITY, int)
        assert 1 <= THUMBNAIL_QUALITY <= 95

    def test_small_image_constants_validity(self):
        """Test that small image constants are valid."""
        if "SMALL_IMAGE_SIZE" not in globals():
            pytest.skip("Constants not available")

        # Small image size should be larger than thumbnail
        assert isinstance(SMALL_IMAGE_SIZE, tuple)
        assert len(SMALL_IMAGE_SIZE) == 2

        if "THUMBNAIL_SIZE" in globals():
            assert SMALL_IMAGE_SIZE[0] > THUMBNAIL_SIZE[0]
            assert SMALL_IMAGE_SIZE[1] > THUMBNAIL_SIZE[1]

        # Quality should be in valid range
        assert isinstance(SMALL_IMAGE_QUALITY, int)
        assert 1 <= SMALL_IMAGE_QUALITY <= 95

    def test_supported_formats_constants(self):
        """Test that supported format constants are valid."""
        if "SUPPORTED_IMAGE_FORMATS" not in globals():
            pytest.skip("Constants not available")

        assert isinstance(SUPPORTED_IMAGE_FORMATS, (list, tuple, set))
        assert len(SUPPORTED_IMAGE_FORMATS) > 0

        # All formats should be strings starting with '.'
        for fmt in SUPPORTED_IMAGE_FORMATS:
            assert isinstance(fmt, str)
            assert fmt.startswith(".")
            assert len(fmt) > 1

    def test_max_image_size_constant(self):
        """Test that max image size constant is reasonable."""
        if "MAX_IMAGE_SIZE_MB" not in globals():
            pytest.skip("Constants not available")

        assert isinstance(MAX_IMAGE_SIZE_MB, (int, float))
        assert MAX_IMAGE_SIZE_MB > 0
        assert MAX_IMAGE_SIZE_MB <= 1000  # Reasonable upper bound

    # ============================================================================
    # INTEGRATION WITH GENERATORS TESTS
    # ============================================================================

    def test_utils_integration_with_generators(self, sample_image_path, temp_dir):
        """Test that utils integrate properly with generator classes."""
        # This test verifies that utils work correctly when used by generators

        # Test validation (used by generators before processing)
        if "validate_image_file" in globals():
            assert validate_image_file(sample_image_path) is True

        # Test dimension detection (used by generators for aspect ratio)
        if "get_image_dimensions" in globals():
            dimensions = get_image_dimensions(sample_image_path)
            assert dimensions == (800, 600)

        # Test path generation (used by generators for output paths)
        if "generate_thumbnail_path" in globals():
            thumb_path = generate_thumbnail_path(
                sample_image_path, str(temp_dir / "thumbnails")
            )
            assert isinstance(thumb_path, str)
            assert len(thumb_path) > 0

    def test_utils_error_handling(self):
        """Test that utility functions handle errors gracefully."""
        # Test with None inputs
        if "validate_image_file" in globals():
            assert validate_image_file(None) is False

        if "get_image_dimensions" in globals():
            assert get_image_dimensions(None) is None

        # Test with empty string inputs
        if "is_supported_format" in globals():
            assert is_supported_format("") is False

        if "generate_thumbnail_path" in globals():
            try:
                result = generate_thumbnail_path("", "")
                # Should either return empty string or raise handled exception
                assert isinstance(result, str)
            except (ValueError, TypeError):
                # Acceptable to raise exception for invalid inputs
                pass

    # ============================================================================
    # PERFORMANCE TESTS
    # ============================================================================

    def test_utils_performance_with_large_images(self, temp_dir):
        """Test utility performance with large images."""
        # Create a large test image
        large_img_path = temp_dir / "large_image.jpg"
        large_img = Image.new("RGB", (4096, 3072), color="green")
        large_img.save(large_img_path, "JPEG", quality=95)

        import time

        # Test validation performance
        if "validate_image_file" in globals():
            start_time = time.time()
            result = validate_image_file(str(large_img_path))
            validation_time = time.time() - start_time

            assert result is True
            assert validation_time < 1.0  # Should be fast

        # Test dimension detection performance
        if "get_image_dimensions" in globals():
            start_time = time.time()
            dimensions = get_image_dimensions(str(large_img_path))
            dimension_time = time.time() - start_time

            assert dimensions == (4096, 3072)
            assert dimension_time < 0.5  # Should be very fast
