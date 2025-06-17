# backend/thumbnail_processor.py

import cv2
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Any, Dict
from PIL import Image, ImageOps
import numpy as np

logger = logging.getLogger(__name__)


class ThumbnailProcessor:
    """Optimized thumbnail generation using Pillow for better quality and performance"""

    def __init__(self):
        # Thumbnail sizes
        self.thumbnail_size = (200, 150)  # Small for dashboard cards
        self.small_size = (800, 600)  # Medium for detail pages

        # Quality settings optimized for each size
        self.qualities = {
            "full": 90,  # High quality for full images
            "small": 85,  # Good quality for medium images
            "thumbnail": 75,  # Optimized for size while maintaining clarity
        }

    def opencv_to_pil(self, cv_image) -> Image.Image:
        """Convert OpenCV image (BGR) to PIL Image (RGB)"""
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb_image)

    def generate_thumbnail_pil(
        self, pil_image: Image.Image, size: Tuple[int, int], quality: int = 85
    ) -> bytes:
        """
        Generate optimized thumbnail using Pillow's built-in thumbnail method
        This maintains aspect ratio and uses high-quality resampling
        """
        # Create a copy to avoid modifying original
        thumb_image = pil_image.copy()

        # Use Pillow's optimized thumbnail method
        # This automatically handles aspect ratio and uses high-quality algorithms
        thumb_image.thumbnail(size, Image.Resampling.LANCZOS)

        # Create a new image with exact target size and paste thumbnail centered
        # This ensures consistent dimensions for all thumbnails
        # final_image = Image.new("RGB", size, (0, 0, 0))  # Black background

        # Calculate position to center the thumbnail
        # thumb_width, thumb_height = thumb_image.size
        # target_width, target_height = size

        # x = (target_width - thumb_width) // 2
        # y = (target_height - thumb_height) // 2

        # final_image.paste(thumb_image, (x, y))

        # Save to bytes with optimized JPEG settings
        from io import BytesIO

        output = BytesIO()
        # final_image.save(
        #     output,
        #     format="JPEG",
        #     quality=quality,
        #     optimize=True,  # Enable JPEG optimization
        #     progressive=True,  # Progressive JPEG for better loading
        # )

        thumb_image.save(
            output,
            format="JPEG",
            quality=quality,
            optimize=True,  # Enable JPEG optimization
            progressive=True,  # Progressive JPEG for better loading
        )

        return output.getvalue()

    def save_thumbnail_to_file(
        self, thumbnail_bytes: bytes, filepath: Path
    ) -> Tuple[bool, int]:
        """Save thumbnail bytes to file and return success status and file size"""
        try:
            with open(filepath, "wb") as f:
                f.write(thumbnail_bytes)

            file_size = filepath.stat().st_size
            logger.debug(f"Saved thumbnail: {filepath} ({file_size} bytes)")
            return True, file_size

        except Exception as e:
            logger.error(f"Failed to save thumbnail {filepath}: {e}")
            return False, 0

    def generate_thumbnails_from_opencv(
        self, cv_frame, base_filename: str, directories: Dict[str, Path]
    ) -> Dict[str, Optional[Tuple[str, int]]]:
        """
        Generate thumbnail and small versions using Pillow for better quality
        Takes OpenCV frame, converts to PIL, and generates optimized thumbnails
        """
        results = {"thumbnail": None, "small": None}

        try:
            # Convert OpenCV frame to PIL Image
            pil_image = self.opencv_to_pil(cv_frame)

            # Generate thumbnail (200x150) with Pillow
            thumbnail_bytes = self.generate_thumbnail_pil(
                pil_image, self.thumbnail_size, self.qualities["thumbnail"]
            )

            thumbnail_path = directories["thumbnails"] / base_filename
            success, file_size = self.save_thumbnail_to_file(
                thumbnail_bytes, thumbnail_path
            )

            if success:
                # Store relative path for database
                camera_id = (
                    str(directories["thumbnails"]).split("camera-")[1].split("/")[0]
                )
                today = datetime.now().strftime("%Y-%m-%d")
                relative_path = f"data/cameras/camera-{camera_id}/thumbnails/{today}/{base_filename}"
                results["thumbnail"] = (relative_path, file_size)
                logger.debug(f"Generated optimized thumbnail: {thumbnail_path}")
            else:
                logger.warning(f"Failed to generate thumbnail for {base_filename}")

            # Generate small version (800x600) with Pillow
            small_bytes = self.generate_thumbnail_pil(
                pil_image, self.small_size, self.qualities["small"]
            )

            small_path = directories["small"] / base_filename
            success, file_size = self.save_thumbnail_to_file(small_bytes, small_path)

            if success:
                # Store relative path for database
                relative_path = (
                    f"data/cameras/camera-{camera_id}/small/{today}/{base_filename}"
                )
                results["small"] = (relative_path, file_size)
                logger.debug(f"Generated optimized small image: {small_path}")
            else:
                logger.warning(f"Failed to generate small image for {base_filename}")

        except Exception as e:
            logger.error(f"Exception during Pillow thumbnail generation: {e}")

        return results

    def generate_thumbnails_from_file(
        self, image_path: Path, output_dir: Path
    ) -> Dict[str, Optional[Tuple[str, int]]]:
        """
        Generate thumbnails from existing image file (for regeneration)
        This is more efficient than the OpenCV conversion path
        """
        results = {"thumbnail": None, "small": None}

        try:
            # Open image directly with Pillow (more efficient)
            with Image.open(image_path) as pil_image:
                # Ensure RGB mode (handle different formats)
                if pil_image.mode != "RGB":
                    pil_image = pil_image.convert("RGB")

                base_filename = image_path.name

                # Generate thumbnail
                thumbnail_bytes = self.generate_thumbnail_pil(
                    pil_image, self.thumbnail_size, self.qualities["thumbnail"]
                )

                thumbnail_path = output_dir / "thumbnails" / base_filename
                thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

                success, file_size = self.save_thumbnail_to_file(
                    thumbnail_bytes, thumbnail_path
                )
                if success:
                    results["thumbnail"] = (str(thumbnail_path), file_size)

                # Generate small version
                small_bytes = self.generate_thumbnail_pil(
                    pil_image, self.small_size, self.qualities["small"]
                )

                small_path = output_dir / "small" / base_filename
                small_path.parent.mkdir(parents=True, exist_ok=True)

                success, file_size = self.save_thumbnail_to_file(
                    small_bytes, small_path
                )
                if success:
                    results["small"] = (str(small_path), file_size)

        except Exception as e:
            logger.error(f"Exception generating thumbnails from file {image_path}: {e}")

        return results


# Factory function for easy integration
def create_thumbnail_processor() -> ThumbnailProcessor:
    """Create and return a ThumbnailProcessor instance"""
    return ThumbnailProcessor()
