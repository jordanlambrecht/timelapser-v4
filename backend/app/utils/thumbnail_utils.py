# backend/app/utils/thumbnail_utils.py

import cv2
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict
from PIL import Image
from io import BytesIO

from .timezone_utils import (
    get_timezone_aware_timestamp_from_settings,
    get_timezone_aware_date_sync,
    utc_now,
)

logger = logging.getLogger(__name__)

# Thumbnail sizes and quality settings
THUMBNAIL_SIZE = (200, 150)  # Small for dashboard cards
SMALL_SIZE = (800, 600)  # Medium for detail pages

QUALITIES = {
    "full": 90,  # High quality for full images
    "small": 85,  # Good quality for medium images
    "thumbnail": 75,  # Optimized for size while maintaining clarity
}


def opencv_to_pil(cv_image) -> Image.Image:
    """Convert OpenCV image (BGR) to PIL Image (RGB)"""
    rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_image)


def generate_thumbnail_pil(
    pil_image: Image.Image, size: Tuple[int, int], quality: int = 85
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
    thumbnail_bytes: bytes, filepath: Path
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


def generate_single_thumbnail(
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
        thumbnail_bytes = generate_thumbnail_pil(pil_image, size, quality)

        # Determine path based on size type using config-driven paths
        from ..config import settings
        base_dir = Path(settings.data_directory)
        
        if size_type == "thumbnail":
            size_dir = base_dir / "cameras" / f"camera-{camera_id}" / "thumbnails" / today
            size_dir.mkdir(parents=True, exist_ok=True)
            thumbnail_path = size_dir / filename
            relative_path = f"cameras/camera-{camera_id}/thumbnails/{today}/{filename}"
        else:  # small
            size_dir = base_dir / "cameras" / f"camera-{camera_id}" / "small" / today
            size_dir.mkdir(parents=True, exist_ok=True)
            thumbnail_path = size_dir / filename
            relative_path = f"cameras/camera-{camera_id}/small/{today}/{filename}"

        # Save thumbnail
        success, file_size = save_thumbnail_to_file(
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
    cv_frame, base_filename: str, directories: Dict[str, Path], sync_db=None
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
        pil_image = opencv_to_pil(cv_frame)

        # Extract camera_id and get timezone-aware date for later use
        camera_id = str(directories["thumbnails"]).split("camera-")[1].split("/")[0]
        try:
            # Get timezone-aware date using centralized utilities
            if sync_db:
                today = get_timezone_aware_date_sync(sync_db)
            else:
                today = utc_now().date().isoformat()
        except Exception as e:
            logger.warning(
                f"Failed to get timezone-aware date: {e}, using settings-aware fallback"
            )
            try:
                # Try to get timezone from database settings
                if sync_db:
                    settings = sync_db.get_all_settings()
                    timestamp = get_timezone_aware_timestamp_from_settings(settings)
                    today = timestamp.split("T")[0]  # Extract date part
                else:
                    today = utc_now().date().isoformat()
            except Exception as fallback_error:
                logger.warning(
                    f"Settings-aware fallback also failed: {fallback_error}, using UTC"
                )
                today = utc_now().date().isoformat()

        # Generate thumbnail (200x150) with Pillow
        results["thumbnail"] = generate_single_thumbnail(
            pil_image,
            base_filename,
            camera_id,
            today,
            "thumbnail",
            THUMBNAIL_SIZE,
            QUALITIES["thumbnail"],
        )

        # Generate small version (800x600) with Pillow
        results["small"] = generate_single_thumbnail(
            pil_image,
            base_filename,
            camera_id,
            today,
            "small",
            SMALL_SIZE,
            QUALITIES["small"],
        )

    except Exception as e:
        logger.error("Exception during Pillow thumbnail generation: %s", e)

    return results


def generate_thumbnails_from_file(
    image_path: Path, output_dir: Path
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
            thumbnail_bytes = generate_thumbnail_pil(
                pil_image, THUMBNAIL_SIZE, QUALITIES["thumbnail"]
            )

            thumbnail_path = output_dir / "thumbnails" / base_filename
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

            success, file_size = save_thumbnail_to_file(
                thumbnail_bytes, thumbnail_path
            )
            if success:
                results["thumbnail"] = (str(thumbnail_path), file_size)

            # Generate small version
            small_bytes = generate_thumbnail_pil(
                pil_image, SMALL_SIZE, QUALITIES["small"]
            )

            small_path = output_dir / "small" / base_filename
            small_path.parent.mkdir(parents=True, exist_ok=True)

            success, file_size = save_thumbnail_to_file(
                small_bytes, small_path
            )
            if success:
                results["small"] = (str(small_path), file_size)

    except Exception as e:
        logger.error(
            "Exception generating thumbnails from file %s: %s", image_path, e
        )

    return results
