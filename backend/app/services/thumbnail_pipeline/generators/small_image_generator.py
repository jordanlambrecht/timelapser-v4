# backend/app/services/thumbnail_pipeline/generators/small_image_generator.py
"""
Small Image Generator Component

Specialized component for generating 800×600 medium-quality images.
Provides higher quality than thumbnails but smaller than full resolution.
"""

from pathlib import Path
from typing import Any, Dict, Tuple

from PIL import Image

from ....enums import LoggerName, LogSource
from ....services.logger import get_service_logger
from ..utils.constants import (
    SMALL_IMAGE_QUALITY,
    SMALL_IMAGE_SIZE,
    SUPPORTED_IMAGE_FORMATS,
)
from ..utils.thumbnail_utils import (
    validate_image_file,
)

logger = get_service_logger(LoggerName.THUMBNAIL_PIPELINE, LogSource.PIPELINE)


class SmallImageGenerator:
    """
    Component responsible for generating 800×600 medium-quality images.

    Optimized for:
    - Modal displays and detailed views
    - Good quality with reasonable file size
    - Faster loading than full resolution
    - Consistent aspect ratio handling
    """

    def __init__(self, quality: int = SMALL_IMAGE_QUALITY):
        """
        Initialize small image generator.

        Args:
            quality: JPEG compression quality (1-95, default from constants)
        """
        self.quality = max(1, min(95, quality))
        self.target_size = SMALL_IMAGE_SIZE

        logger.debug(
            f"SmallImageGenerator initialized (quality={self.quality}, size={self.target_size})"
        )

    def generate_small_image(
        self, source_path: str, output_path: str, force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate an 800x600 small image from source image.

        Args:
            source_path: Path to source image file
            output_path: Path where small image should be saved
            force_regenerate: Whether to overwrite existing small image

        Returns:
            Dict containing generation result and metadata
        """
        try:
            source_path_obj = Path(source_path)
            output_path_obj = Path(output_path)

            # Validate source image
            if not validate_image_file(str(source_path_obj)):
                return {
                    "success": False,
                    "error": f"Invalid or unsupported image file: {source_path_obj}",
                    "source_path": str(source_path_obj),
                    "output_path": str(output_path_obj),
                }

            # Check if small image already exists
            if output_path_obj.exists() and not force_regenerate:
                file_size = output_path_obj.stat().st_size
                return {
                    "success": True,
                    "generated": False,
                    "message": "Small image already exists",
                    "source_path": str(source_path_obj),
                    "output_path": str(output_path_obj),
                    "file_size": file_size,
                }

            # Ensure output directory exists
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Generate small image
            generation_result = self._generate_small_image_file(
                source_path_obj, output_path_obj
            )

            if generation_result["success"]:
                logger.debug(f"Generated small image: {output_path_obj.name}")

            return generation_result

        except Exception as e:
            logger.error(
                f"Failed to generate small image for {source_path}", exception=e
            )
            return {
                "success": False,
                "error": str(e),
                "source_path": source_path,
                "output_path": output_path,
            }

    def _generate_small_image_file(
        self, source_path: Path, output_path: Path
    ) -> Dict[str, Any]:
        """
        Internal method to perform the actual small image generation.

        Args:
            source_path: Source image path
            output_path: Output small image path

        Returns:
            Dict containing generation result and metadata
        """
        try:
            # Open and process image
            with Image.open(source_path) as img:
                # Store original size
                original_size = img.size

                # Convert to RGB if necessary (handles RGBA, P, etc.)
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")

                # Calculate dimensions preserving aspect ratio
                target_width, target_height = self.target_size

                # Check if image is already smaller than target
                if img.width <= target_width and img.height <= target_height:
                    # Image is smaller than target - save as-is with compression
                    img.save(
                        output_path,
                        # TODO: use enum
                        "JPEG",
                        quality=self.quality,
                        optimize=True,
                        progressive=True,
                    )

                    final_size = img.size
                else:
                    # Image is larger - resize with aspect ratio preservation
                    small_size = self._calculate_small_dimensions(
                        img.size, (target_width, target_height)
                    )

                    # Resize with high-quality resampling
                    img = img.resize(small_size, Image.Resampling.LANCZOS)

                    # Save with optimization
                    img.save(
                        output_path,
                        # TODO: use enum
                        "JPEG",
                        quality=self.quality,
                        optimize=True,
                        progressive=True,
                    )

                    final_size = img.size

                # Get file size
                file_size = output_path.stat().st_size

                return {
                    "success": True,
                    "generated": True,
                    "source_path": str(source_path),
                    "output_path": str(output_path),
                    "original_size": original_size,
                    "final_size": final_size,
                    "file_size": file_size,
                    "quality": self.quality,
                    "resized": original_size != final_size,
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Image processing failed: {str(e)}",
                "source_path": str(source_path),
                "output_path": str(output_path),
            }

    def _calculate_small_dimensions(
        self, source_size: Tuple[int, int], max_size: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Calculate small image dimensions that fit within max size while preserving aspect ratio.

        Args:
            source_size: (width, height) of source image
            max_size: (max_width, max_height) constraints

        Returns:
            (width, height) of calculated small image
        """
        source_width, source_height = source_size
        max_width, max_height = max_size

        # Calculate aspect ratio
        aspect_ratio = source_width / source_height

        # Calculate dimensions that fit within constraints
        if source_width / max_width > source_height / max_height:
            # Width is the limiting factor
            new_width = max_width
            new_height = int(max_width / aspect_ratio)
        else:
            # Height is the limiting factor
            new_height = max_height
            new_width = int(max_height * aspect_ratio)

        return (new_width, new_height)

    def validate_small_image(self, small_image_path: str) -> Dict[str, Any]:
        """
        Validate an existing small image file.

        Args:
            small_image_path: Path to small image file to validate

        Returns:
            Dict containing validation result and metadata
        """
        try:
            small_image_path_obj = Path(small_image_path)

            if not small_image_path_obj.exists():
                return {
                    "valid": False,
                    "error": "Small image file does not exist",
                    "path": str(small_image_path_obj),
                }

            # Check file size
            file_size = small_image_path_obj.stat().st_size
            if file_size == 0:
                return {
                    "valid": False,
                    "error": "Small image file is empty",
                    "path": str(small_image_path_obj),
                    "file_size": file_size,
                }

            # Try to open as image
            with Image.open(small_image_path_obj) as img:
                return {
                    "valid": True,
                    "path": str(small_image_path_obj),
                    "size": img.size,
                    "mode": img.mode,
                    "format": img.format,
                    "file_size": file_size,
                }

        except Exception as e:
            return {
                "valid": False,
                "error": f"Small image validation failed: {str(e)}",
                "path": small_image_path,
            }

    def estimate_generation_time(self, source_size: Tuple[int, int]) -> float:
        """
        Estimate small image generation time based on source image size.

        Args:
            source_size: (width, height) of source image

        Returns:
            Estimated generation time in seconds
        """
        source_width, source_height = source_size
        total_pixels = source_width * source_height

        # Empirical estimation - small images take longer than thumbnails due to higher quality
        base_time = (
            total_pixels / 800_000
        )  # Slightly slower processing for higher quality
        overhead = 0.15  # Slightly higher overhead for quality processing

        return base_time + overhead

    def get_compression_ratio(
        self, original_size: Tuple[int, int], final_size: Tuple[int, int]
    ) -> float:
        """
        Calculate compression ratio between original and final image.

        Args:
            original_size: (width, height) of original image
            final_size: (width, height) of final small image

        Returns:
            Compression ratio (0.0 to 1.0)
        """
        original_pixels = original_size[0] * original_size[1]
        final_pixels = final_size[0] * final_size[1]

        if original_pixels == 0:
            return 0.0

        return final_pixels / original_pixels

    def get_supported_formats(self) -> list:
        """
        Get list of supported image formats for small image generation.

        Returns:
            List of supported file extensions
        """
        return list(SUPPORTED_IMAGE_FORMATS)
