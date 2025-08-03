# backend/app/services/thumbnail_pipeline/utils/thumbnail_utils.py
"""
Thumbnail Utility Functions
"""

from pathlib import Path
from typing import Tuple

from PIL import Image

from .constants import SUPPORTED_IMAGE_FORMATS


def validate_image_file(file_path: str) -> bool:
    """
    Validate if file is a supported image format.

    Args:
        file_path: Path to image file

    Returns:
        True if file is a valid image, False otherwise
    """
    try:
        file_path_obj = Path(file_path)

        # Check file exists
        if not file_path_obj.exists():
            return False

        # Check file extension
        if file_path_obj.suffix.lower() not in SUPPORTED_IMAGE_FORMATS:
            return False

        # Try to open as image
        with Image.open(file_path_obj) as img:
            img.verify()

        return True

    except Exception:
        return False


def calculate_thumbnail_dimensions(
    source_size: Tuple[int, int], target_size: Tuple[int, int]
) -> Tuple[int, int]:
    """
    Calculate thumbnail dimensions preserving aspect ratio.

    Args:
        source_size: (width, height) of source image
        target_size: (width, height) of target size

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


def create_thumbnail_directories(base_path: str, timelapse_id: int) -> None:
    """
    Create thumbnail directory structure.

    Args:
        base_path: Base data directory path
        timelapse_id: Timelapse ID for directory structure
    """
    base_path_obj = Path(base_path)

    # Create thumbnails and smalls directories
    thumbnail_dir = base_path_obj / f"timelapse-{timelapse_id}" / "thumbnails"
    small_dir = base_path_obj / f"timelapse-{timelapse_id}" / "smalls"

    thumbnail_dir.mkdir(parents=True, exist_ok=True)
    small_dir.mkdir(parents=True, exist_ok=True)


def generate_thumbnail_filename(original_path: str, size_type: str) -> str:
    """
    Generate thumbnail filename from original filename.

    Args:
        original_path: Path to original image
        size_type: Type of thumbnail ('thumbnail' or 'small')

    Returns:
        Generated thumbnail filename
    """
    original_path_obj = Path(original_path)
    stem = original_path_obj.stem

    if size_type == "thumbnail":
        return f"thumb_{stem}.jpg"
    elif size_type == "small":
        return f"small_{stem}.jpg"
    else:
        return f"{stem}.jpg"


def generate_thumbnail(
    source_path: str, output_path: str, size: Tuple[int, int], quality: int = 85
) -> bool:
    """
    Generate thumbnail image.

    Args:
        source_path: Path to source image
        output_path: Path for output thumbnail
        size: (width, height) for thumbnail
        quality: JPEG quality (1-95)

    Returns:
        True if successful, False otherwise
    """
    try:
        with Image.open(source_path) as img:
            # Convert to RGB if needed
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Calculate thumbnail size
            thumbnail_size = calculate_thumbnail_dimensions(img.size, size)

            # Create thumbnail
            img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)

            # Create final image with exact target size
            final_img = Image.new("RGB", size, (255, 255, 255))
            paste_x = (size[0] - img.width) // 2
            paste_y = (size[1] - img.height) // 2
            final_img.paste(img, (paste_x, paste_y))

            # Save thumbnail
            final_img.save(output_path, "JPEG", quality=quality, optimize=True)

        return True

    except Exception:
        return False


def generate_small_image(
    source_path: str, output_path: str, max_size: Tuple[int, int], quality: int = 90
) -> bool:
    """
    Generate small image.

    Args:
        source_path: Path to source image
        output_path: Path for output small image
        max_size: Maximum (width, height) for small image
        quality: JPEG quality (1-95)

    Returns:
        True if successful, False otherwise
    """
    try:
        with Image.open(source_path) as img:
            # Convert to RGB if needed
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Check if resize needed
            if img.width <= max_size[0] and img.height <= max_size[1]:
                # Image is already small enough
                img.save(output_path, "JPEG", quality=quality, optimize=True)
            else:
                # Resize preserving aspect ratio
                small_size = calculate_thumbnail_dimensions(img.size, max_size)
                img = img.resize(small_size, Image.Resampling.LANCZOS)
                img.save(output_path, "JPEG", quality=quality, optimize=True)

        return True

    except Exception:
        return False
