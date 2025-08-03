# backend/app/utils/file_helpers.py
"""
File Helper Functions

Common functions for file operations, path validation, and security checks.
Provides standardized file serving, path resolution, and security validation.
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response

from ..config import settings
from ..constants import ALLOWED_IMAGE_EXTENSIONS, ASSET_TYPE_MAP
from ..enums import LogEmoji, LoggerName
from ..services.logger import get_service_logger

# Initialize logger
logger = get_service_logger(LoggerName.UTILITY)


# Utility to safely delete a file with logging
def delete_file_safe(file_path: str) -> bool:
    """
    Safely delete a file, logging any errors. Returns True if deleted, False otherwise.

    Args:
        file_path: Path to the file to delete
    """
    try:
        path = Path(file_path).resolve()
        if path.exists():
            path.unlink()
            logger.info(
                f"Deleted file: {path}",
                emoji=LogEmoji.DELETE,
                extra_context={"operation": "file_delete", "file_path": str(path)},
            )
            return True
        else:
            logger.warning(
                f"File not found for deletion: {path}",
                emoji=LogEmoji.WARNING,
                extra_context={
                    "operation": "file_delete",
                    "file_path": str(path),
                    "status": "not_found",
                },
            )
            return False
    except Exception as e:
        logger.error(
            f"Failed to delete file {file_path}",
            emoji=LogEmoji.ERROR,
            error_context={"operation": "file_delete", "file_path": file_path},
            exception=e,
        )
        return False


def validate_file_path(
    file_path: str, base_directory: Optional[str] = None, must_exist: bool = True
) -> Path:
    """
    Validate and resolve a file path with security checks.

    Args:
        file_path: File path to validate (can be relative or absolute)
        base_directory: Base directory to resolve relative paths (defaults to data_directory)
        must_exist: Whether the file must exist

    Returns:
        Resolved and validated Path object

    Raises:
        HTTPException: 403 for path traversal attempts, 404 if file not found
    """
    if base_directory is None:
        base_directory = settings.data_directory

    base_path = Path(base_directory).resolve()

    # Handle both absolute and relative paths
    if Path(file_path).is_absolute():
        full_path = Path(file_path).resolve()
    else:
        full_path = (base_path / file_path).resolve()

    # Security check: ensure path is within allowed directory
    try:
        full_path.relative_to(base_path)
    except ValueError:
        logger.warning(
            f"Path traversal attempt detected: {file_path}",
            emoji=LogEmoji.SECURITY,
            extra_context={
                "operation": "file_validation",
                "file_path": file_path,
                "base_directory": str(base_path),
                "security_violation": "path_traversal",
            },
        )
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if file exists (if required)
    if must_exist and not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return full_path


def create_file_response(
    file_path: Path,
    filename: Optional[str] = None,
    media_type: str = "application/octet-stream",
    headers: Optional[Dict[str, str]] = None,
) -> FileResponse:
    """
    Create a standardized FileResponse with proper headers.

    Args:
        file_path: Path to the file
        filename: Optional custom filename for download
        media_type: MIME type for the response
        headers: Optional additional headers

    Returns:
        FileResponse object ready to return
    """
    response_headers = headers or {}

    return FileResponse(
        path=str(file_path),
        filename=filename or file_path.name,
        media_type=media_type,
        headers=response_headers,
    )


def create_image_response(
    file_path: Path,
    image_data: Optional[Dict[str, Any]] = None,
    cache_control: str = "no-cache, no-store, must-revalidate",
) -> Response:
    """
    Create an optimized image response with proper caching headers.

    Args:
        file_path: Path to the image file
        image_data: Optional image metadata from database
        cache_control: Cache control header value

    Returns:
        Response object with image data and proper headers
    """
    try:
        with open(file_path, "rb") as f:
            image_bytes = f.read()

        # Build headers
        headers = {
            "Cache-Control": cache_control,
            "Content-Length": str(len(image_bytes)),
        }

        # Add last modified if available
        if image_data and image_data.get("captured_at"):
            captured_at = image_data["captured_at"]
            if hasattr(captured_at, "strftime"):
                headers["Last-Modified"] = captured_at.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT"
                )

        # Set cache headers based on cache control
        if "no-cache" in cache_control:
            headers["Pragma"] = "no-cache"
            headers["Expires"] = "0"
        else:
            headers["Pragma"] = "public"

        return Response(content=image_bytes, media_type="image/jpeg", headers=headers)

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error reading image file") from e


def get_image_with_fallbacks(
    image_data: Dict[str, Any], size: str = "full", base_directory: Optional[str] = None
) -> Path:
    """
    Get image path with cascading fallbacks (thumbnail -> small -> full).

    Args:
        image_data: Image record from database
        size: Requested size ("thumbnail", "small", or "full")
        base_directory: Base directory for file resolution

    Returns:
        Path to the best available image file

    Raises:
        HTTPException: 404 if no image files are found
    """
    if base_directory is None:
        base_directory = settings.data_directory

    data_root = Path(base_directory)

    # Define fallback chain based on requested size
    if size == "thumbnail":
        fallback_chain = ["thumbnail_path", "small_path", "file_path"]
    elif size == "small":
        fallback_chain = ["small_path", "file_path"]
    else:
        fallback_chain = ["file_path"]

    # Try each option in the fallback chain
    for path_field in fallback_chain:
        path_value = image_data.get(path_field)
        if path_value:
            file_path = data_root / path_value
            if file_path.exists():
                return file_path

    # If we get here, no files were found
    raise HTTPException(status_code=404, detail="Image file not found")


def ensure_directory_exists(directory_path: str) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory_path: Path to the directory

    Returns:
        Path object for the directory

    Raises:
        HTTPException: 500 if directory cannot be created
    """
    try:
        path = Path(directory_path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create directory") from e


def clean_filename(filename: str) -> str:
    """
    Clean a filename to be safe for filesystem use.

    Args:
        filename: Original filename

    Returns:
        Cleaned filename safe for filesystem
    """
    # Remove/replace problematic characters
    cleaned = "".join(c for c in filename if c.isalnum() or c in (" ", "-", "_", "."))

    # Replace spaces with underscores
    cleaned = cleaned.replace(" ", "_")

    # Remove multiple consecutive underscores
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")

    # Strip leading/trailing underscores and dots
    cleaned = cleaned.strip("_.")

    return cleaned or "unknown"


def get_relative_path(full_path: Path, base_directory: Optional[str] = None) -> str:
    """
    Get relative path from full path for database storage.

    Args:
        full_path: Full file system path
        base_directory: Base directory to make path relative to

    Returns:
        Relative path string for database storage
    """
    if base_directory is None:
        base_directory = settings.data_directory

    base_path = Path(base_directory).resolve()
    try:
        return str(full_path.resolve().relative_to(base_path))
    except ValueError:
        # If path is outside base directory, return as-is
        return str(full_path)


def validate_media_type(file_path: Path, allowed_types: set) -> str:
    """
    Validate and determine media type for a file.

    Args:
        file_path: Path to the file
        allowed_types: Set of allowed file extensions (e.g., {'.jpg', '.png'})

    Returns:
        Appropriate media type string

    Raises:
        HTTPException: 400 if file type is not allowed
    """
    extension = file_path.suffix.lower()

    if extension not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type {extension} not allowed. Allowed types: {', '.join(allowed_types)}",
        )

    # Map extensions to media types

    return ASSET_TYPE_MAP.get(extension, "application/octet-stream")


class FileOperationMixin:
    """
    Mixin class for common file operation patterns.

    Can be used with service classes that need file handling capabilities.
    """

    @staticmethod
    def safe_file_operation(operation_name: str):
        """
        Decorator for safe file operations with error handling.

        Args:
            operation_name: Description of the operation for error messages
        """

        def decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except OSError as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"File system error during {operation_name}",
                    ) from e
                except Exception as e:
                    raise HTTPException(
                        status_code=500, detail=f"Failed to {operation_name}"
                    ) from e

            return wrapper

        return decorator

    def get_secure_file_path(
        self,
        relative_path: str,
        base_directory: Optional[str] = None,
        must_exist: bool = True,
    ) -> Path:
        """Instance method wrapper for validate_file_path."""
        return validate_file_path(relative_path, base_directory, must_exist)

    def create_secure_response(
        self,
        file_path: Path,
        filename: Optional[str] = None,
        media_type: Optional[str] = None,
    ) -> FileResponse:
        """Instance method wrapper for create_file_response with auto media type detection."""
        if media_type is None:
            extension = file_path.suffix.lower()
            media_type = validate_media_type(file_path, {extension})

        return create_file_response(file_path, filename, media_type)


def ensure_entity_directory(
    camera_id: int, timelapse_id: int, subdirectory: str = "frames"
) -> Path:
    """
    Create and return entity-based directory structure.

    Args:
        camera_id: Camera ID
        timelapse_id: Timelapse ID
        subdirectory: Subdirectory within timelapse (e.g., 'frames', 'videos')

    Returns:
        Path to the entity directory
    """

    entity_dir = (
        settings.data_path
        / "cameras"
        / f"camera-{camera_id}"
        / f"timelapse-{timelapse_id}"
        / subdirectory
    )
    entity_dir.mkdir(parents=True, exist_ok=True)
    return entity_dir


def ensure_camera_directories(camera_id: int, date_str: str) -> Dict[str, Path]:
    """
    Create and return camera-specific directory structure for date-based storage.

    Args:
        camera_id: Camera ID
        date_str: Date string (YYYY-MM-DD format)

    Returns:
        Dictionary mapping directory types to paths
    """

    base_dir = settings.data_path / "cameras" / f"camera-{camera_id}"

    directories = {
        "images": base_dir / "images" / date_str,
        "thumbnails": base_dir / "thumbnails" / date_str,
        "small": base_dir / "small" / date_str,
    }

    for dir_path in directories.values():
        dir_path.mkdir(parents=True, exist_ok=True)

    return directories


def scan_directory_for_thumbnails(directory_path: str) -> list:
    """
    Recursively scan directory for thumbnail files.

    Args:
        directory_path: Directory to scan

    Returns:
        List of thumbnail file paths found
    """
    try:
        path = Path(directory_path)
        if not path.exists():
            return []

        thumbnail_files = []

        # Scan for thumbnail files (looking for _thumb_ and _small_ patterns)
        for file_path in path.rglob("*.jpg"):
            filename = file_path.name
            if "_thumb_" in filename or "_small_" in filename:
                thumbnail_files.append(str(file_path))

        return thumbnail_files

    except Exception:
        # Error scanning directory - return empty list
        return []


def parse_thumbnail_filename(filename: str) -> dict:
    """
    Parse thumbnail filename to extract metadata.

    Args:
        filename: Thumbnail filename to parse

    Returns:
        Dictionary with extracted metadata
    """
    try:
        # Expected format: timelapse-{id}_thumb_day{XXX}_{HHMMSS}.jpg
        # or: timelapse-{id}_small_day{XXX}_{HHMMSS}.jpg

        base_name = Path(filename).stem
        parts = base_name.split("_")

        if len(parts) < 4:
            return {"valid": False, "error": "Insufficient filename parts"}

        # Extract timelapse ID
        timelapse_part = parts[0]  # timelapse-{id}
        if not timelapse_part.startswith("timelapse-"):
            return {"valid": False, "error": "Invalid timelapse prefix"}

        try:
            timelapse_id = int(timelapse_part.split("-")[1])
        except (IndexError, ValueError):
            return {"valid": False, "error": "Invalid timelapse ID"}

        # Extract type (thumb or small)
        thumbnail_type = parts[1]  # thumb or small
        if thumbnail_type not in ["thumb", "small"]:
            return {"valid": False, "error": "Invalid thumbnail type"}

        # Extract day number
        day_part = parts[2]  # day{XXX}
        if not day_part.startswith("day"):
            return {"valid": False, "error": "Invalid day format"}

        try:
            day_number = int(day_part[3:])  # Remove 'day' prefix
        except ValueError:
            return {"valid": False, "error": "Invalid day number"}

        # Extract time
        time_part = parts[3]  # HHMMSS
        if len(time_part) != 6:
            return {"valid": False, "error": "Invalid time format"}

        return {
            "valid": True,
            "timelapse_id": timelapse_id,
            "type": thumbnail_type,
            "day_number": day_number,
            "time": time_part,
            "filename": filename,
        }

    except Exception as e:
        return {"valid": False, "error": str(e)}


def calculate_directory_size(directory_path: str) -> float:
    """
    Calculate total size of directory in MB.

    Args:
        directory_path: Directory to calculate size for

    Returns:
        Size in MB
    """
    try:
        path = Path(directory_path)
        if not path.exists():
            return 0.0

        total_size = 0
        for file_path in path.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return total_size / (1024 * 1024)  # Convert to MB

    except Exception:
        # Error calculating directory size - return 0
        return 0.0


# Note: Use existing delete_file_safe() function instead of duplicating
# Note: Use Path.exists() directly instead of wrapper function


def get_overlay_path_for_image(
    image_path: str,
    camera_id: int,
    timelapse_id: int,
    base_directory: Optional[str] = None,
) -> Path:
    """
    Get the standardized overlay file path for a given image.

    Args:
        image_path: Path to original image file
        camera_id: Camera ID
        timelapse_id: Timelapse ID
        base_directory: Base directory (defaults to settings.data_directory)

    Returns:
        Path to overlay file following standard structure
    """

    # Use provided base directory or default to settings
    if base_directory:
        base_dir = Path(base_directory)
    else:
        base_dir = settings.data_path

    # Extract image filename without extension
    image_file = Path(image_path)
    image_stem = image_file.stem

    # Standard overlay structure: data/cameras/camera-{id}/timelapse-{id}/overlays/
    overlay_dir = (
        base_dir
        / "cameras"
        / f"camera-{camera_id}"
        / f"timelapse-{timelapse_id}"
        / "overlays"
    )

    # Handle date subdirectories if image is in date-based structure
    # Check if image path contains date pattern (YYYY-MM-DD)

    for part in image_file.parts:
        if re.match(r"\d{4}-\d{2}-\d{2}", part):
            overlay_dir = overlay_dir / part
            break

    # Generate overlay filename: original_name_overlay.png
    overlay_filename = f"{image_stem}_overlay.png"
    return overlay_dir / overlay_filename


def get_overlay_path_from_image_path(
    image_file: str, base_directory: Optional[Path] = None
) -> Optional[Path]:
    """
    Get overlay path by extracting camera/timelapse info from image file path.

    Used by video generation when camera_id/timelapse_id aren't directly available.

    Args:
        image_file: Path to original image file
        base_directory: Base directory to search from

    Returns:
        Path to overlay file, or None if structure doesn't match expected pattern
    """

    try:
        image_path = Path(image_file)

        # Extract camera and timelapse info from path
        if "camera-" in str(image_path) and (
            "timelapse-" in str(image_path)
            or re.search(r"\d{4}-\d{2}-\d{2}", str(image_path))
        ):
            path_parts = image_path.parts

            # Find camera directory and extract camera_id
            camera_id = None
            camera_dir_idx = None
            for i, part in enumerate(path_parts):
                if part.startswith("camera-"):
                    camera_dir_idx = i
                    # Extract camera_id from "camera-123" format
                    camera_id = int(part.split("-")[1])
                    break

            if camera_id is not None and camera_dir_idx is not None:
                # Look for timelapse directory and extract timelapse_id
                timelapse_id = None
                for i in range(camera_dir_idx + 1, len(path_parts)):
                    if path_parts[i].startswith("timelapse-"):
                        # Extract timelapse_id from "timelapse-456" format
                        timelapse_id = int(path_parts[i].split("-")[1])
                        break

                if timelapse_id is not None:
                    # Use the standard overlay path function
                    return get_overlay_path_for_image(
                        image_path=image_file,
                        camera_id=camera_id,
                        timelapse_id=timelapse_id,
                        base_directory=str(base_directory) if base_directory else None,
                    )

        return None

    except Exception:
        # Failed to determine overlay path from image path - return None
        return None


def prepare_image_metadata_for_serving(
    image_data: Dict[str, Any], data_directory: str, size: str = "full"
) -> Dict[str, Any]:
    """
    Prepare image metadata for serving with proper file path resolution.

    This is a pure function that doesn't depend on database or service state.

    Args:
        image_data: Image metadata dict with file paths
        data_directory: Base data directory path
        size: Requested size (full, small, thumbnail)

    Returns:
        Dictionary with file path and metadata for serving
    """
    try:
        # Convert to format expected by get_image_with_fallbacks
        image_dict = {
            "id": image_data.get("id"),
            "file_path": image_data.get("file_path"),
            "thumbnail_path": image_data.get("thumbnail_path"),
            "small_path": image_data.get("small_path"),
        }

        file_path = get_image_with_fallbacks(image_dict, size, data_directory)

        media_type = validate_media_type(file_path, ALLOWED_IMAGE_EXTENSIONS)

        return {
            "success": True,
            "file_path": str(file_path),
            "media_type": media_type,
            "image_id": image_data.get("id"),
            "size": size,
            "fallback_used": False,  # get_image_with_fallbacks handles this internally
            "image_data": image_data,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Image preparation failed: {str(e)}",
        }


def serve_image_with_metadata(
    file_path: str,
    media_type: str,
    image_data: Optional[Dict[str, Any]] = None,
    image_id: Optional[int] = None,
) -> FileResponse:
    """
    Create a FileResponse for serving an image with proper caching headers.

    Args:
        file_path: Path to the image file
        media_type: MIME type for the response
        image_data: Optional image metadata for ETag generation
        image_id: Optional image ID for ETag generation

    Returns:
        FileResponse with proper caching headers
    """
    try:
        # Generate ETag and cache headers based on image metadata
        if image_data and image_data.get("captured_at") and image_id:
            # Simple ETag generation using image ID and timestamp
            captured_at = image_data["captured_at"]
            if hasattr(captured_at, "timestamp"):
                etag = f"img-{image_id}-{int(captured_at.timestamp())}"
            else:
                # Handle string timestamps
                etag = f"img-{image_id}-{hash(str(captured_at))}"

            headers = {"ETag": f'"{etag}"', "Cache-Control": "max-age=3600, public"}

            return create_file_response(
                file_path=Path(file_path), media_type=media_type, headers=headers
            )
        else:
            # Fallback without caching if no image metadata
            return FileResponse(path=file_path, media_type=media_type)

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to serve image file") from e


def get_file_size(file_path: str) -> int:
    """
    Get file size in bytes.

    Args:
        file_path: Path to file

    Returns:
        File size in bytes, 0 if file doesn't exist
    """
    try:
        return Path(file_path).stat().st_size
    except Exception:
        return 0


def build_camera_image_urls(camera_id: int) -> Dict[str, str]:
    """
    Build standard camera latest image URLs.

    Args:
        camera_id: Camera ID

    Returns:
        Dictionary with full, small, thumbnail, and download URLs
    """
    return {
        "full": f"/api/cameras/{camera_id}/latest-image/full",
        "small": f"/api/cameras/{camera_id}/latest-image/small",
        "thumbnail": f"/api/cameras/{camera_id}/latest-image/thumbnail",
        "download": f"/api/cameras/{camera_id}/latest-image/download",
    }
