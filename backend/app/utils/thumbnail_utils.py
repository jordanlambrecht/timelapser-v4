# backend/app/utils/thumbnail_utils.py

import cv2
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict
from PIL import Image
from io import BytesIO
from datetime import datetime
from ..config import settings
from .timezone_utils import (
    get_timezone_aware_timestamp_from_settings,
    get_timezone_aware_date_sync,
    utc_now,
)
from ..constants import (
    THUMBNAIL_GENERATION_MODE_DISABLED,
    THUMBNAIL_GENERATION_MODE_LATEST,
    THUMBNAIL_GENERATION_MODE_ALL,
    THUMBNAIL_SIZE,
    SMALL_SIZE,
    THUMBNAIL_QUALITY_FULL,
    THUMBNAIL_QUALITY_SMALL,
    THUMBNAIL_QUALITY_THUMBNAIL,
    THUMBNAIL_PIL_OPTIMIZATION_ENABLED,
    THUMBNAIL_WEBP_SUPPORT_ENABLED,
    THUMBNAIL_PROGRESSIVE_JPEG_ENABLED,
    THUMBNAIL_MAX_IMAGE_DIMENSION,
    THUMBNAIL_MEMORY_EFFICIENT_RESIZE,
    THUMBNAIL_SIZE_PREFIX_THUMB,
    THUMBNAIL_SIZE_PREFIX_SMALL,
    THUMBNAIL_FILE_EXTENSION,
    THUMBNAIL_IMAGE_FORMAT,
    THUMBNAIL_SMALL_SIZE_THRESHOLD,
    THUMBNAIL_SMALL_QUALITY_REDUCTION,
    THUMBNAIL_MIN_QUALITY,
    THUMBNAIL_DIR_CAMERAS,
    THUMBNAIL_DIR_THUMBNAILS,
    THUMBNAIL_DIR_SMALL,
    THUMBNAIL_DIR_SMALLS,
    THUMBNAIL_CAMERA_PREFIX,
    THUMBNAIL_TIMELAPSE_PREFIX,
)

logger = logging.getLogger(__name__)


def generate_timelapse_thumbnail_filename(
    timelapse_id: int, day_number: int, timestamp: str, size_type: str
) -> str:
    """
    Generate thumbnail filename following architecture document convention.

    Convention:
    - Original images: timelapse-{id}_day{XXX}_{HHMMSS}.jpg
    - Thumbnails: timelapse-{id}_thumb_day{XXX}_{HHMMSS}.jpg
    - Small images: timelapse-{id}_small_day{XXX}_{HHMMSS}.jpg

    Args:
        timelapse_id: ID of the timelapse
        day_number: Day number in sequence (1-based)
        timestamp: Timestamp in HHMMSS format
        size_type: 'thumbnail' or 'small'

    Returns:
        Formatted filename string
    """
    size_prefix = (
        THUMBNAIL_SIZE_PREFIX_THUMB
        if size_type == "thumbnail"
        else THUMBNAIL_SIZE_PREFIX_SMALL
    )
    return f"timelapse-{timelapse_id}_{size_prefix}_day{day_number:03d}_{timestamp}{THUMBNAIL_FILE_EXTENSION}"


def opencv_to_pil(cv_image) -> Image.Image:
    """Convert OpenCV image (BGR) to PIL Image (RGB)"""
    rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_image)


def generate_thumbnail_pil(
    pil_image: Image.Image, size: Tuple[int, int], quality: int = 85
) -> bytes:
    """
    Generate optimized thumbnail using Pillow with performance optimizations.
    This maintains aspect ratio and uses optimized resampling algorithms.
    """
    # Performance optimization: avoid unnecessary copy for memory efficiency
    if THUMBNAIL_MEMORY_EFFICIENT_RESIZE:
        # Use in-place thumbnail generation for memory efficiency
        thumb_image = pil_image.copy()
        thumb_image.thumbnail(size, Image.Resampling.LANCZOS)
    else:
        # Traditional method - create copy and resize
        thumb_image = pil_image.copy()
        thumb_image.thumbnail(size, Image.Resampling.LANCZOS)

    # Save to bytes with performance-optimized JPEG settings
    output = BytesIO()
    save_kwargs = {
        "format": THUMBNAIL_IMAGE_FORMAT,
        "quality": quality,
        "optimize": THUMBNAIL_PIL_OPTIMIZATION_ENABLED,  # Use performance setting
        "progressive": THUMBNAIL_PROGRESSIVE_JPEG_ENABLED,  # Use performance setting
    }

    # Additional performance optimizations for small thumbnails
    if max(size) <= THUMBNAIL_SMALL_SIZE_THRESHOLD:  # For very small thumbnails
        save_kwargs["quality"] = max(
            quality - THUMBNAIL_SMALL_QUALITY_REDUCTION, THUMBNAIL_MIN_QUALITY
        )  # Slightly reduce quality for speed
        save_kwargs["optimize"] = True  # Always optimize small images

    thumb_image.save(output, **save_kwargs)

    return output.getvalue()


def save_thumbnail_to_file(thumbnail_bytes: bytes, filepath: Path) -> Tuple[bool, int]:
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
    timelapse_id: Optional[int],
    size_type: str,
    size: tuple,
    quality: int,
    use_legacy_path: bool = False,
) -> Optional[Tuple[str, int]]:
    """Generate a single thumbnail (either thumbnail or small size)"""
    try:
        # Generate thumbnail bytes
        thumbnail_bytes = generate_thumbnail_pil(pil_image, size, quality)

        # Determine path based on size type using config-driven paths

        base_dir = Path(settings.data_directory)

        if use_legacy_path:
            # Legacy camera-based structure for backward compatibility

            today = datetime.utcnow().date().isoformat()

            if size_type == "thumbnail":
                size_dir = (
                    base_dir
                    / THUMBNAIL_DIR_CAMERAS
                    / f"{THUMBNAIL_CAMERA_PREFIX}{camera_id}"
                    / THUMBNAIL_DIR_THUMBNAILS
                    / today
                )
                size_dir.mkdir(parents=True, exist_ok=True)
                thumbnail_path = size_dir / filename
                relative_path = f"{THUMBNAIL_DIR_CAMERAS}/{THUMBNAIL_CAMERA_PREFIX}{camera_id}/{THUMBNAIL_DIR_THUMBNAILS}/{today}/{filename}"
            else:  # small
                size_dir = (
                    base_dir
                    / THUMBNAIL_DIR_CAMERAS
                    / f"{THUMBNAIL_CAMERA_PREFIX}{camera_id}"
                    / THUMBNAIL_DIR_SMALL
                    / today
                )
                size_dir.mkdir(parents=True, exist_ok=True)
                thumbnail_path = size_dir / filename
                relative_path = f"{THUMBNAIL_DIR_CAMERAS}/{THUMBNAIL_CAMERA_PREFIX}{camera_id}/{THUMBNAIL_DIR_SMALL}/{today}/{filename}"
        else:
            # New timelapse-based structure following architecture document
            if timelapse_id is None:
                raise ValueError("timelapse_id is required for new path structure")

            if size_type == "thumbnail":
                size_dir = (
                    base_dir
                    / THUMBNAIL_DIR_CAMERAS
                    / f"{THUMBNAIL_CAMERA_PREFIX}{camera_id}"
                    / f"{THUMBNAIL_TIMELAPSE_PREFIX}{timelapse_id}"
                    / THUMBNAIL_DIR_THUMBNAILS
                )
                size_dir.mkdir(parents=True, exist_ok=True)
                thumbnail_path = size_dir / filename
                relative_path = f"{THUMBNAIL_DIR_CAMERAS}/{THUMBNAIL_CAMERA_PREFIX}{camera_id}/{THUMBNAIL_TIMELAPSE_PREFIX}{timelapse_id}/{THUMBNAIL_DIR_THUMBNAILS}/{filename}"
            else:  # small
                size_dir = (
                    base_dir
                    / THUMBNAIL_DIR_CAMERAS
                    / f"{THUMBNAIL_CAMERA_PREFIX}{camera_id}"
                    / f"{THUMBNAIL_TIMELAPSE_PREFIX}{timelapse_id}"
                    / THUMBNAIL_DIR_SMALLS
                )
                size_dir.mkdir(parents=True, exist_ok=True)
                thumbnail_path = size_dir / filename
                relative_path = f"{THUMBNAIL_DIR_CAMERAS}/{THUMBNAIL_CAMERA_PREFIX}{camera_id}/{THUMBNAIL_TIMELAPSE_PREFIX}{timelapse_id}/{THUMBNAIL_DIR_SMALLS}/{filename}"

        # Save thumbnail
        success, file_size = save_thumbnail_to_file(thumbnail_bytes, thumbnail_path)

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
        camera_id = (
            str(directories["thumbnails"])
            .split(THUMBNAIL_CAMERA_PREFIX)[1]
            .split("/")[0]
        )
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

        # Generate thumbnail (200x150) with Pillow - using legacy path for backward compatibility
        results["thumbnail"] = generate_single_thumbnail(
            pil_image,
            base_filename,
            camera_id,
            None,  # timelapse_id not used in legacy mode
            "thumbnail",
            THUMBNAIL_SIZE,
            THUMBNAIL_QUALITY_THUMBNAIL,
            use_legacy_path=True,
        )

        # Generate small version (800x600) with Pillow - using legacy path for backward compatibility
        results["small"] = generate_single_thumbnail(
            pil_image,
            base_filename,
            camera_id,
            None,  # timelapse_id not used in legacy mode
            "small",
            SMALL_SIZE,
            THUMBNAIL_QUALITY_SMALL,
            use_legacy_path=True,
        )

    except Exception as e:
        logger.error("Exception during Pillow thumbnail generation: %s", e)

    return results


def generate_thumbnails_for_timelapse_image(
    image_path: Path,
    camera_id: int,
    timelapse_id: int,
    filename_override: Optional[str] = None,
    small_generation_mode: str = "all",
    is_latest_image: bool = False,
) -> Dict[str, Optional[Tuple[str, int]]]:
    """
    Generate thumbnails for a specific image using timelapse-based file structure.

    This function is designed for the job queue system and follows the architecture
    document's timelapse-based file organization.

    Args:
        image_path: Path to the source image file
        camera_id: ID of the camera
        timelapse_id: ID of the timelapse session
        filename_override: Optional filename override for thumbnails
        small_generation_mode: THUMBNAIL_GENERATION_MODE_* - controls small image generation
        is_latest_image: Whether this is the latest image (for "latest" mode)

    Returns:
        Dictionary with thumbnail and small generation results
    """
    results: Dict[str, Optional[Tuple[str, int]]] = {
        "thumbnail": None,
        "small": None,
    }

    try:
        # Open image directly with Pillow (efficient for regeneration)
        with Image.open(image_path) as pil_image:
            # Performance optimization: check if source image is too large
            original_size = pil_image.size
            if max(original_size) > THUMBNAIL_MAX_IMAGE_DIMENSION:
                # Downscale source image first for faster processing
                scale_factor = THUMBNAIL_MAX_IMAGE_DIMENSION / max(original_size)
                new_size = (
                    int(original_size[0] * scale_factor),
                    int(original_size[1] * scale_factor),
                )
                pil_image.thumbnail(new_size, Image.Resampling.LANCZOS)
                logger.debug(
                    f"Downscaled source image from {original_size} to {new_size} for faster processing"
                )

            # Ensure RGB mode (handle different formats) - only convert if necessary
            if pil_image.mode not in ("RGB", "L"):  # L for grayscale is also efficient
                pil_image = pil_image.convert("RGB")
            elif pil_image.mode == "L":
                # Keep grayscale for smaller file sizes if source is grayscale
                pass

            # Use original filename or override
            base_filename = filename_override or image_path.name

            # Generate thumbnail using new timelapse-based structure - optimized order (smallest first)
            results["thumbnail"] = generate_single_thumbnail(
                pil_image,
                base_filename,
                str(camera_id),
                timelapse_id,
                "thumbnail",
                THUMBNAIL_SIZE,
                THUMBNAIL_QUALITY_THUMBNAIL,
                use_legacy_path=False,  # Use new structure
            )

            # Generate small version based on settings
            should_generate_small = (
                small_generation_mode == THUMBNAIL_GENERATION_MODE_ALL
                or (
                    small_generation_mode == THUMBNAIL_GENERATION_MODE_LATEST
                    and is_latest_image
                )
            )

            if should_generate_small:
                results["small"] = generate_single_thumbnail(
                    pil_image,
                    base_filename,
                    str(camera_id),
                    timelapse_id,
                    "small",
                    SMALL_SIZE,
                    THUMBNAIL_QUALITY_SMALL,
                    use_legacy_path=False,  # Use new structure
                )
            else:
                logger.debug(
                    f"Skipping small image generation: mode={small_generation_mode}, is_latest={is_latest_image}"
                )

    except Exception as e:
        logger.error(
            f"Exception generating thumbnails for timelapse image {image_path}: {e}"
        )

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
                pil_image, THUMBNAIL_SIZE, THUMBNAIL_QUALITY_THUMBNAIL
            )

            thumbnail_path = output_dir / "thumbnails" / base_filename
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

            success, file_size = save_thumbnail_to_file(thumbnail_bytes, thumbnail_path)
            if success:
                results["thumbnail"] = (str(thumbnail_path), file_size)

            # Generate small version
            small_bytes = generate_thumbnail_pil(
                pil_image, SMALL_SIZE, THUMBNAIL_QUALITY_SMALL
            )

            small_path = output_dir / "small" / base_filename
            small_path.parent.mkdir(parents=True, exist_ok=True)

            success, file_size = save_thumbnail_to_file(small_bytes, small_path)
            if success:
                results["small"] = (str(small_path), file_size)

    except Exception as e:
        logger.error("Exception generating thumbnails from file %s: %s", image_path, e)

    return results
