# backend/app/services/thumbnail_pipeline/generators/thumbnail_generator.py
"""
Thumbnail Generator Component

Specialized component for generating 200×150 dashboard-optimized thumbnails.
Handles individual thumbnail generation with quality and performance optimization.
"""

from pathlib import Path
from typing import Any, Dict, Tuple

from PIL import Image

from ....enums import LoggerName, LogSource
from ....services.logger import get_service_logger
from ..utils.constants import (
    SUPPORTED_IMAGE_FORMATS,
    THUMBNAIL_QUALITY,
    THUMBNAIL_SIZE,
)
from ..utils.thumbnail_utils import (
    validate_image_file,
)

logger = get_service_logger(LoggerName.THUMBNAIL_PIPELINE)
logger = get_service_logger(LoggerName.THUMBNAIL_PIPELINE, LogSource.PIPELINE)


class ThumbnailGenerator:
    """
    Component responsible for generating 200×150 dashboard thumbnails.

    Optimized for:
    - Dashboard loading performance
    - Consistent aspect ratio handling
    - High-quality compression
    - Fast generation times
    """

    def __init__(self, quality: int = THUMBNAIL_QUALITY):
        """
        Initialize thumbnail generator.

        Args:
            quality: JPEG compression quality (1-95, default from constants)
        """
        self.quality = max(1, min(95, quality))
        self.target_size = THUMBNAIL_SIZE

        logger.debug(
            f"ThumbnailGenerator initialized (quality={self.quality}, size={self.target_size})"
        )

    def generate_thumbnail(
        self, source_path: str, output_path: str, force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a 200×150 thumbnail from source image.

        Args:
            source_path: Path to source image file
            output_path: Path where thumbnail should be saved
            force_regenerate: Whether to overwrite existing thumbnail

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

            # Check if thumbnail already exists
            if output_path_obj.exists() and not force_regenerate:
                file_size = output_path_obj.stat().st_size
                return {
                    "success": True,
                    "generated": False,
                    "message": "Thumbnail already exists",
                    "source_path": str(source_path_obj),
                    "output_path": str(output_path_obj),
                    "file_size": file_size,
                }

            # Ensure output directory exists
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Generate thumbnail
            generation_result = self._generate_thumbnail_image(
                source_path_obj, output_path_obj
            )

            if generation_result["success"]:
                logger.debug(f"Generated thumbnail: {output_path_obj.name}")

            return generation_result

        except Exception as e:
            logger.error(
                f"Failed to generate thumbnail for {source_path}",
                exception=e,
                extra_context={
                    "source_path": source_path,
                    "output_path": output_path,
                },
            )
            return {
                "success": False,
                "error": str(e),
                "source_path": source_path,
                "output_path": output_path,
            }

    def _generate_thumbnail_image(
        self, source_path: Path, output_path: Path
    ) -> Dict[str, Any]:
        """
        Internal method to perform the actual thumbnail generation.

        Args:
            source_path: Source image path
            output_path: Output thumbnail path

        Returns:
            Dict containing generation result and metadata
        """
        try:
            # Open and process image
            with Image.open(source_path) as img:
                # Convert to RGB if necessary (handles RGBA, P, etc.)
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")

                # Calculate dimensions preserving aspect ratio
                target_width, target_height = self.target_size
                thumbnail_size = self._calculate_thumbnail_dimensions(
                    img.size, (target_width, target_height)
                )

                # Create thumbnail with high-quality resampling
                img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)

                # Create final thumbnail with proper centering on transparent background
                thumbnail = Image.new(
                    "RGB", (target_width, target_height), (255, 255, 255)
                )

                # Calculate position to center the thumbnail
                paste_x = (target_width - img.width) // 2
                paste_y = (target_height - img.height) // 2
                thumbnail.paste(img, (paste_x, paste_y))

                # Save with optimization
                thumbnail.save(
                    output_path,
                    "JPEG",
                    quality=self.quality,
                    optimize=True,
                    progressive=True,
                )

                # Get file size
                file_size = output_path.stat().st_size

                return {
                    "success": True,
                    "generated": True,
                    "source_path": str(source_path),
                    "output_path": str(output_path),
                    "source_size": img.size,
                    "thumbnail_size": (target_width, target_height),
                    "file_size": file_size,
                    "quality": self.quality,
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Image processing failed: {str(e)}",
                "source_path": str(source_path),
                "output_path": str(output_path),
            }

    def _calculate_thumbnail_dimensions(
        self, source_size: Tuple[int, int], target_size: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Calculate thumbnail dimensions that fit within target size while preserving aspect ratio.

        Args:
            source_size: (width, height) of source image
            target_size: (width, height) of target thumbnail

        Returns:
            (width, height) of calculated thumbnail
        """
        source_width, source_height = source_size
        target_width, target_height = target_size

        # Calculate aspect ratios
        source_ratio = source_width / source_height
        target_ratio = target_width / target_height

        if source_ratio > target_ratio:
            # Source is wider - fit to width
            new_width = target_width
            new_height = int(target_width / source_ratio)
        else:
            # Source is taller - fit to height
            new_height = target_height
            new_width = int(target_height * source_ratio)

        return (new_width, new_height)

    def validate_thumbnail(self, thumbnail_path: str) -> Dict[str, Any]:
        """
        Validate an existing thumbnail file.

        Args:
            thumbnail_path: Path to thumbnail file to validate

        Returns:
            Dict containing validation result and metadata
        """
        try:
            thumbnail_path_obj = Path(thumbnail_path)

            if not thumbnail_path_obj.exists():
                return {
                    "valid": False,
                    "error": "Thumbnail file does not exist",
                    "path": str(thumbnail_path_obj),
                }

            # Check file size
            file_size = thumbnail_path_obj.stat().st_size
            if file_size == 0:
                return {
                    "valid": False,
                    "error": "Thumbnail file is empty",
                    "path": str(thumbnail_path_obj),
                    "file_size": file_size,
                }

            # Try to open as image
            with Image.open(thumbnail_path_obj) as img:
                return {
                    "valid": True,
                    "path": str(thumbnail_path_obj),
                    "size": img.size,
                    "mode": img.mode,
                    "format": img.format,
                    "file_size": file_size,
                }

        except Exception as e:
            return {
                "valid": False,
                "error": f"Thumbnail validation failed: {str(e)}",
                "path": thumbnail_path,
            }

    def estimate_generation_time(self, source_size: Tuple[int, int]) -> float:
        """
        Estimate thumbnail generation time based on source image size.

        Args:
            source_size: (width, height) of source image

        Returns:
            Estimated generation time in seconds
        """
        source_width, source_height = source_size
        total_pixels = source_width * source_height

        # Empirical estimation based on image processing performance
        # Assumes ~1M pixels processed per second for thumbnail generation
        base_time = total_pixels / 1_000_000  # Base processing time
        overhead = 0.1  # Fixed overhead for file I/O and setup

        return base_time + overhead

    def get_supported_formats(self) -> list:
        """
        Get list of supported image formats for thumbnail generation.

        Returns:
            List of supported file extensions
        """
        return list(SUPPORTED_IMAGE_FORMATS)
