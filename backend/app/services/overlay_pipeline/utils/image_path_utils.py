# backend/app/services/overlay_pipeline/utils/image_path_utils.py
"""
Image Path Utilities - Path resolution and image loading for overlay generation.

Handles different path formats (API assets, frontend assets, direct paths) and
provides secure image loading with validation.
"""

from pathlib import Path

from PIL import Image as PILImage

from ....enums import LoggerName, LogSource
from ....services.logger import get_service_logger
from .image_utils import validate_image_format

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)


def load_image_from_path(image_path: str) -> PILImage.Image:
    """
    Load image from file system with support for different path formats.

    Args:
        image_path: Path or URL to the image

    Returns:
        PIL Image object

    Raises:
        ValueError: If image cannot be loaded or format is unsupported
    """
    logger.debug(f"📁 Loading image from path: {image_path}")

    try:
        # Handle different path formats
        if image_path.startswith(("http://", "https://")):
            logger.error("HTTP URLs not supported for security reasons")
            # For now, don't support HTTP URLs for security
            # Future enhancement: Could support with proper validation
            raise ValueError("HTTP URLs not supported for watermarks")

        # Handle local file paths
        if image_path.startswith("/api/overlays/assets/"):
            logger.debug("🔗 Resolving API asset URL to file system path")
            # Extract asset ID from API URL (e.g., "/api/overlays/assets/123")
            asset_id = image_path.split("/")[-1]
            logger.debug(f"Extracted asset ID: {asset_id}")

            # Get asset from database and resolve to file path
            actual_path = resolve_api_asset_path(asset_id)
            logger.debug(f"Resolved API asset path: {actual_path}")
        elif image_path.startswith("/assets/"):
            logger.debug("🎨 Resolving frontend asset path to file system path")
            # Legacy frontend asset path - need to resolve to actual file system path
            actual_path = resolve_frontend_asset_path(image_path)
            logger.debug(f"Resolved asset path: {actual_path}")
        else:
            actual_path = Path(image_path)
            logger.debug(f"📂 Using direct file path: {actual_path}")

        # Validate path exists and is readable
        if not actual_path.exists():
            logger.error(f"Image file not found: {actual_path}")
            raise ValueError(f"Image file not found: {actual_path}")

        if not actual_path.is_file():
            logger.error(f"Path is not a file: {actual_path}")
            raise ValueError(f"Path is not a file: {actual_path}")

        logger.debug("📁 Image file found, attempting to load")

        # Load image
        image = PILImage.open(actual_path)
        logger.debug(
            f"Image loaded: {image.size} pixels, format: {image.format}, mode: {image.mode}"
        )

        # Validate image format
        validate_image_format(image)

        logger.debug("✅ Image loaded successfully")
        return image

    except Exception as e:
        logger.error(f"Failed to load watermark image: {e}")
        raise ValueError(f"Cannot load watermark image: {e}")


def resolve_frontend_asset_path(frontend_path: str) -> Path:
    """
    Resolve frontend asset path to actual file system path.

    Args:
        frontend_path: Frontend asset path (e.g., "/assets/logo.png")

    Returns:
        Resolved file system path

    Note:
        This would need to be configured based on your asset storage setup.
        For now, assuming a basic assets directory structure.
    """
    logger.debug(f"🎨 Resolving frontend asset path: {frontend_path}")

    # Remove leading /assets/ and resolve to actual directory
    relative_path = frontend_path.replace("/assets/", "")
    logger.debug(f"Relative path: {relative_path}")

    # This path should be configurable via settings
    # For now, assume assets are stored relative to the data directory

    # Import here to avoid circular import
    from ....routers.settings_routers import get_settings

    settings = get_settings()

    # Construct full path to assets
    assets_dir = Path(settings.data_directory) / "assets" / "overlays"
    full_path = assets_dir / relative_path

    logger.debug(f"✅ Resolved full path: {full_path}")
    return full_path


def resolve_api_asset_path(asset_id: str) -> Path:
    """
    Resolve API asset ID to actual file system path.

    Args:
        asset_id: Asset ID from API URL (e.g., "123")

    Returns:
        Resolved file system path

    Raises:
        ValueError: If asset not found or invalid ID
    """
    logger.debug(f"🔗 Resolving API asset ID to file path: {asset_id}")

    try:
        # Use dependency injection singleton to prevent database connection multiplication
        from ....dependencies.specialized import get_sync_overlay_operations
        from ....routers.settings_routers import get_settings

        # Get asset from database using singleton operations
        sync_ops = get_sync_overlay_operations()
        asset = sync_ops.get_asset_by_id(int(asset_id))
        if not asset:
            raise ValueError(f"Asset not found: {asset_id}")

        logger.debug(f"🗂️ Found asset: {asset.filename}")

        # Construct full path using stored file_path
        settings = get_settings()
        if asset.file_path.startswith("/"):
            # Absolute path
            full_path = Path(asset.file_path)
        else:
            # Relative to data directory
            full_path = Path(settings.data_directory) / asset.file_path

        logger.debug(f"✅ Resolved API asset path: {full_path}")
        return full_path

    except (ValueError, TypeError) as e:
        logger.error(f"Invalid asset ID: {asset_id} - {e}")
        raise ValueError(f"Invalid asset ID: {asset_id}")
    except Exception as e:
        logger.error(f"Failed to resolve asset {asset_id}: {e}")
        raise ValueError(f"Failed to resolve asset: {asset_id}")
