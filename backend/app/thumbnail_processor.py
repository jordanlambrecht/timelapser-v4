# backend/app/thumbnail_processor.py

import cv2
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict
from PIL import Image
from io import BytesIO

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

        # Save to bytes with optimized JPEG settings
        output = BytesIO()
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
            logger.debug("Saved thumbnail: %s (%d bytes)", filepath, file_size)
            return True, file_size

        except Exception as e:
            logger.error("Failed to save thumbnail %s: %s", filepath, e)
            return False, 0

    def _generate_single_thumbnail(
        self,
        pil_image,
        filename: str,
        camera_id: str,
        today: str,
        size_type: str,
        size: tuple,
        quality: int,
    ) -> Optional[Tuple[str, int]]:
        """Generate a single thumbnail (either thumbnail or small size)"""
        try:
            # Generate thumbnail bytes
            thumbnail_bytes = self.generate_thumbnail_pil(pil_image, size, quality)

            # Determine path based on size type
            if size_type == "thumbnail":
                directories = {
                    "thumbnails": Path(
                        f"data/cameras/camera-{camera_id}/thumbnails/{today}"
                    )
                }
                directories["thumbnails"].mkdir(parents=True, exist_ok=True)
                thumbnail_path = directories["thumbnails"] / filename
                relative_path = (
                    f"data/cameras/camera-{camera_id}/thumbnails/{today}/{filename}"
                )
            else:  # small
                directories = {
                    "small": Path(f"data/cameras/camera-{camera_id}/small/{today}")
                }
                directories["small"].mkdir(parents=True, exist_ok=True)
                thumbnail_path = directories["small"] / filename
                relative_path = (
                    f"data/cameras/camera-{camera_id}/small/{today}/{filename}"
                )

            # Save thumbnail
            success, file_size = self.save_thumbnail_to_file(
                thumbnail_bytes, thumbnail_path
            )

            if success:
                logger.debug("Generated optimized %s: %s", size_type, thumbnail_path)
                return (relative_path, file_size)
            else:
                logger.warning("Failed to generate %s for %s", size_type, filename)
                return None

        except Exception as e:
            logger.error("Exception during %s generation: %s", size_type, e)
            return None

    def generate_thumbnails_from_opencv(
        self, cv_frame, base_filename: str, directories: Dict[str, Path]
    ) -> Dict[str, Optional[Tuple[str, int]]]:
        """
        Generate thumbnail and small versions using Pillow for better quality
        Takes OpenCV frame, converts to PIL, and generates optimized thumbnails
        """
        results: Dict[str, Optional[Tuple[str, int]]] = {
            "thumbnail": None,
            "small": None,
        }

        try:
            # Convert OpenCV frame to PIL Image
            pil_image = self.opencv_to_pil(cv_frame)

            # Extract camera_id and today for later use
            camera_id = str(directories["thumbnails"]).split("camera-")[1].split("/")[0]
            today = datetime.now().strftime("%Y-%m-%d")

            # Generate thumbnail (200x150) with Pillow
            results["thumbnail"] = self._generate_single_thumbnail(
                pil_image,
                base_filename,
                camera_id,
                today,
                "thumbnail",
                self.thumbnail_size,
                self.qualities["thumbnail"],
            )

            # Generate small version (800x600) with Pillow
            results["small"] = self._generate_single_thumbnail(
                pil_image,
                base_filename,
                camera_id,
                today,
                "small",
                self.small_size,
                self.qualities["small"],
            )

        except Exception as e:
            logger.error("Exception during Pillow thumbnail generation: %s", e)

        return results

    def generate_thumbnails_from_file(
        self, image_path: Path, output_dir: Path
    ) -> Dict[str, Optional[Tuple[str, int]]]:
        """
        Generate thumbnails from existing image file (for regeneration)
        This is more efficient than the OpenCV conversion path
        """
        results: Dict[str, Optional[Tuple[str, int]]] = {
            "thumbnail": None,
            "small": None,
        }

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
            logger.error(
                "Exception generating thumbnails from file %s: %s", image_path, e
            )

        return results


# Factory function for easy integration
def create_thumbnail_processor() -> ThumbnailProcessor:
    """Create and return a ThumbnailProcessor instance"""
    return ThumbnailProcessor()
