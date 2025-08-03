# backend/app/utils/temp_file_manager.py
"""
Temporary File Management Utilities

Provides centralized management of temporary files for overlay previews,
test captures, and other transient file operations.
"""

import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..enums import LoggerName
from ..services.logger import get_service_logger
from .time_utils import format_filename_timestamp, utc_now

logger = get_service_logger(LoggerName.SYSTEM)


class TempFileManager:
    """
    Manager for temporary file operations with automatic cleanup.

    Handles creation, tracking, and cleanup of temporary files used for
    overlay previews and other transient operations.
    """

    def __init__(self, base_temp_dir: Optional[str] = None, max_age_hours: int = 2):
        """
        Initialize temporary file manager.

        Args:
            base_temp_dir: Base directory for temporary files (defaults to system temp)
            max_age_hours: Maximum age of files before cleanup (default: 2 hours)
        """
        self.base_temp_dir = (
            Path(base_temp_dir) if base_temp_dir else Path(tempfile.gettempdir())
        )
        self.max_age_hours = max_age_hours

        # Create timelapser-specific temp directories
        self.preview_dir = self.base_temp_dir / "timelapser_previews"
        self.overlay_dir = self.base_temp_dir / "timelapser_overlays"
        self.test_capture_dir = self.base_temp_dir / "timelapser_test_captures"

        # Ensure directories exist
        for directory in [self.preview_dir, self.overlay_dir, self.test_capture_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def create_preview_path(
        self, camera_id: int, timestamp: Optional[datetime] = None
    ) -> Path:
        """
        Create a unique file path for camera preview images.

        Args:
            camera_id: ID of the camera
            timestamp: Optional timestamp (defaults to current time)

        Returns:
            Unique file path for preview image
        """
        if timestamp is None:
            timestamp = utc_now()

        timestamp_str = format_filename_timestamp(timestamp)
        filename = f"camera_{camera_id}_preview_{timestamp_str}.jpg"
        return self.preview_dir / filename

    def create_overlay_preview_path(
        self, camera_id: int, timestamp: Optional[datetime] = None
    ) -> Path:
        """
        Create a unique file path for overlay preview images.

        Args:
            camera_id: ID of the camera
            timestamp: Optional timestamp (defaults to current time)

        Returns:
            Unique file path for overlay preview image
        """
        if timestamp is None:
            timestamp = utc_now()

        timestamp_str = format_filename_timestamp(timestamp)
        filename = f"camera_{camera_id}_overlay_preview_{timestamp_str}.png"
        return self.overlay_dir / filename

    def create_test_capture_path(
        self, camera_id: int, timestamp: Optional[datetime] = None
    ) -> Path:
        """
        Create a unique file path for test capture images.

        Args:
            camera_id: ID of the camera
            timestamp: Optional timestamp (defaults to current time)

        Returns:
            Unique file path for test capture image
        """
        if timestamp is None:
            timestamp = utc_now()

        timestamp_str = format_filename_timestamp(timestamp)
        filename = f"camera_{camera_id}_test_{timestamp_str}.jpg"
        return self.test_capture_dir / filename

    def cleanup_old_files(self, max_age_hours: Optional[int] = None) -> int:
        """
        Clean up temporary files older than the specified age.

        Args:
            max_age_hours: Maximum age in hours (defaults to instance max_age_hours)

        Returns:
            Number of files cleaned up
        """
        if max_age_hours is None:
            max_age_hours = self.max_age_hours

        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_count = 0

        # Clean up all managed directories
        for directory in [self.preview_dir, self.overlay_dir, self.test_capture_dir]:
            if directory.exists():
                for file_path in directory.iterdir():
                    if file_path.is_file():
                        try:
                            # Check file age
                            file_age = file_path.stat().st_mtime
                            if file_age < cutoff_time:
                                file_path.unlink()  # Delete the file
                                cleaned_count += 1
                                logger.debug(
                                    f"Cleaned up old temporary file: {file_path}"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Failed to clean up temporary file {file_path}: {e}"
                            )

        if cleaned_count > 0:
            logger.info(
                f"Cleaned up {cleaned_count} old temporary files (older than {max_age_hours} hours)"
            )

        return cleaned_count

    def cleanup_camera_files(self, camera_id: int) -> int:
        """
        Clean up all temporary files for a specific camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Number of files cleaned up
        """
        camera_pattern = f"camera_{camera_id}_"
        cleaned_count = 0

        # Clean up camera-specific files in all directories
        for directory in [self.preview_dir, self.overlay_dir, self.test_capture_dir]:
            if directory.exists():
                for file_path in directory.iterdir():
                    if file_path.is_file() and camera_pattern in file_path.name:
                        try:
                            file_path.unlink()  # Delete the file
                            cleaned_count += 1
                            logger.debug(
                                f"Cleaned up camera {camera_id} temporary file: {file_path}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to clean up camera file {file_path}: {e}"
                            )

        if cleaned_count > 0:
            logger.info(
                f"Cleaned up {cleaned_count} temporary files for camera {camera_id}"
            )

        return cleaned_count

    def get_temp_file_stats(self) -> dict:
        """
        Get statistics about temporary files.

        Returns:
            Dictionary with file counts and sizes for each directory
        """
        stats = {
            "preview_files": {"count": 0, "total_size": 0},
            "overlay_files": {"count": 0, "total_size": 0},
            "test_files": {"count": 0, "total_size": 0},
            "total": {"count": 0, "total_size": 0},
        }

        directory_map = {
            self.preview_dir: "preview_files",
            self.overlay_dir: "overlay_files",
            self.test_capture_dir: "test_files",
        }

        for directory, key in directory_map.items():
            if directory.exists():
                for file_path in directory.iterdir():
                    if file_path.is_file():
                        try:
                            file_size = file_path.stat().st_size
                            stats[key]["count"] += 1
                            stats[key]["total_size"] += file_size
                            stats["total"]["count"] += 1
                            stats["total"]["total_size"] += file_size
                        except Exception as e:
                            logger.warning(
                                f"Failed to get stats for temp file {file_path}: {e}"
                            )

        return stats

    def ensure_directories_exist(self) -> bool:
        """
        Ensure all temporary directories exist.

        Returns:
            True if all directories exist or were created successfully
        """
        try:
            for directory in [
                self.preview_dir,
                self.overlay_dir,
                self.test_capture_dir,
            ]:
                directory.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to ensure temporary directories exist: {e}")
            return False


# Global instance for easy access
temp_file_manager = TempFileManager()


def cleanup_temporary_files(max_age_hours: int = 2) -> int:
    """
    Convenience function to clean up old temporary files.

    Args:
        max_age_hours: Maximum age in hours for files to keep

    Returns:
        Number of files cleaned up
    """
    return temp_file_manager.cleanup_old_files(max_age_hours)


def get_preview_image_path(
    camera_id: int, timestamp: Optional[datetime] = None
) -> Path:
    """
    Convenience function to get a preview image path.

    Args:
        camera_id: ID of the camera
        timestamp: Optional timestamp

    Returns:
        Unique file path for preview image
    """
    return temp_file_manager.create_preview_path(camera_id, timestamp)


def get_overlay_preview_path(
    camera_id: int, timestamp: Optional[datetime] = None
) -> Path:
    """
    Convenience function to get an overlay preview path.

    Args:
        camera_id: ID of the camera
        timestamp: Optional timestamp

    Returns:
        Unique file path for overlay preview image
    """
    return temp_file_manager.create_overlay_preview_path(camera_id, timestamp)


def get_timelapser_temp_file_count() -> int:
    """
    Get count of all timelapser-related temporary files in system temp directory.

    This includes any files/directories matching the 'timelapser_*' pattern.
    Useful for cleanup recommendations and system health monitoring.

    Returns:
        Number of timelapser temporary files found
    """
    try:
        temp_dir = Path(tempfile.gettempdir())
        temp_files = list(temp_dir.glob("timelapser_*/*"))
        return len(temp_files)
    except Exception as e:
        logger.debug(f"Could not check temp directory for timelapser files: {e}")
        return 0
