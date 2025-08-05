# backend/app/utils/startup_cleanup.py
"""
Startup Cleanup Utilities - Handle cleanup of partial work and orphaned files.

This module provides utilities for cleaning up incomplete work that may have been
left behind after system crashes or restarts, including:
- Incomplete thumbnail files
- Temporary files
- Orphaned processing artifacts
"""


from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from ..config import settings
from ..constants import ALLOWED_VIDEO_EXTENSIONS
from ..database.core import SyncDatabase
from ..database.image_operations import SyncImageOperations
from ..database.thumbnail_job_operations import SyncThumbnailJobOperations
from ..database.video_operations import SyncVideoOperations
from ..enums import LoggerName
from ..services.logger import get_service_logger
from ..services.settings_service import SyncSettingsService
from ..utils.temp_file_manager import (
    cleanup_temporary_files,
    get_timelapser_temp_file_count,
)
from ..utils.time_utils import UTC_TIMEZONE, utc_now, utc_timestamp

# UTC timezone constant imported from time_utils for consistency

logger = get_service_logger(LoggerName.SYSTEM)


class StartupCleanupService:
    """
    Service for cleaning up incomplete work and orphaned files on startup.

    Handles cleanup of:
    - Thumbnail files for jobs that were marked as processing but never completed
    - Temporary files and processing artifacts
    - Orphaned files that don't have corresponding database records
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize startup cleanup service.

        Args:
            db: SyncDatabase instance
        """
        self.db = db
        self.thumbnail_ops = SyncThumbnailJobOperations(db)
        self.image_ops = SyncImageOperations(db)
        self.video_ops = SyncVideoOperations(db)
        self.settings_service = SyncSettingsService(db)

    def perform_startup_cleanup(
        self,
        cleanup_thumbnails: bool = True,
        cleanup_temp_files: bool = True,
        cleanup_orphaned_files: bool = False,  # More aggressive, disabled by default
        max_age_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive startup cleanup operations.

        Args:
            cleanup_thumbnails: Whether to clean up incomplete thumbnail files
            cleanup_temp_files: Whether to clean up temporary files
            cleanup_orphaned_files: Whether to clean up orphaned files (aggressive)
            max_age_hours: Maximum age of files to consider for cleanup

        Returns:
            Dictionary with cleanup statistics
        """
        cleanup_start_time = utc_now()
        logger.info("🧹 Starting startup cleanup operations...")

        cleanup_results = {
            "cleanup_timestamp": cleanup_start_time.isoformat(),
            "max_age_hours": max_age_hours,
            "operations_performed": [],
            "files_cleaned": 0,
            "errors": [],
        }

        try:
            # 1. Clean up incomplete thumbnail files
            if cleanup_thumbnails:
                thumbnail_results = self._cleanup_incomplete_thumbnails(max_age_hours)
                cleanup_results["thumbnail_cleanup"] = thumbnail_results
                cleanup_results["files_cleaned"] += thumbnail_results.get(
                    "files_removed", 0
                )
                cleanup_results["operations_performed"].append("thumbnail_cleanup")

            # 2. Clean up temporary files
            if cleanup_temp_files:
                temp_results = self._cleanup_temporary_files(max_age_hours)
                cleanup_results["temp_file_cleanup"] = temp_results
                cleanup_results["files_cleaned"] += temp_results.get("files_removed", 0)
                cleanup_results["operations_performed"].append("temp_file_cleanup")

            # 3. Clean up orphaned files (optional, more aggressive)
            if cleanup_orphaned_files:
                orphan_results = self._cleanup_orphaned_files(max_age_hours)
                cleanup_results["orphaned_file_cleanup"] = orphan_results
                cleanup_results["files_cleaned"] += orphan_results.get(
                    "files_removed", 0
                )
                cleanup_results["operations_performed"].append("orphaned_file_cleanup")

            # Calculate duration
            cleanup_duration = (utc_now() - cleanup_start_time).total_seconds()
            cleanup_results["cleanup_duration_seconds"] = cleanup_duration
            cleanup_results["cleanup_successful"] = True

            # Log summary
            total_files = cleanup_results["files_cleaned"]
            if total_files > 0:
                logger.info(
                    f"✅ Startup cleanup completed in {cleanup_duration:.2f}s - "
                    f"Cleaned up {total_files} files"
                )
            else:
                logger.info(
                    f"✅ Startup cleanup completed in {cleanup_duration:.2f}s - "
                    f"No cleanup required"
                )

            return cleanup_results

        except Exception as e:
            cleanup_duration = (utc_now() - cleanup_start_time).total_seconds()
            logger.error(
                f"❌ Startup cleanup failed after {cleanup_duration:.2f}s: {e}"
            )

            cleanup_results.update(
                {
                    "cleanup_duration_seconds": cleanup_duration,
                    "cleanup_successful": False,
                    "error": str(e),
                }
            )
            return cleanup_results

    def _cleanup_incomplete_thumbnails(self, max_age_hours: int) -> Dict[str, Any]:
        """
        Clean up thumbnail files for jobs that were processing but never completed.

        This removes thumbnail files for jobs that were stuck in 'processing' status
        and have been reset to 'pending' by the recovery process.

        Args:
            max_age_hours: Maximum age of files to consider for cleanup

        Returns:
            Dictionary with cleanup results
        """
        try:
            logger.info("🖼️ Cleaning up incomplete thumbnail files...")

            # Use operations layer to find recovered jobs
            recovered_jobs = self.thumbnail_ops.get_recovered_jobs(max_age_hours)

            files_removed = 0
            files_checked = 0
            errors = []

            for job in recovered_jobs:
                try:
                    # Get image record to find potential thumbnail path
                    image_record = self.image_ops.get_image_by_id(job["image_id"])
                    if not image_record:
                        continue

                    files_checked += 1

                    # If thumbnail_path exists, check if the file exists and remove it
                    if image_record.thumbnail_path:
                        thumbnail_full_path = Path(image_record.thumbnail_path)

                        # Handle both absolute and relative paths
                        if not thumbnail_full_path.is_absolute():
                            # Convert relative path to absolute
                            thumbnail_full_path = (
                                Path(settings.data_directory) / thumbnail_full_path
                            )

                        if thumbnail_full_path.exists():
                            # Check if file is old enough to be from a failed processing attempt
                            # Convert file timestamp to UTC for comparison
                            file_mtime_utc = datetime.fromtimestamp(
                                thumbnail_full_path.stat().st_mtime, tz=UTC_TIMEZONE
                            )
                            file_age = utc_now() - file_mtime_utc
                            if file_age.total_seconds() > 300:  # 5 minutes old
                                thumbnail_full_path.unlink()
                                files_removed += 1
                                logger.debug(
                                    f"Removed incomplete thumbnail: {thumbnail_full_path}"
                                )

                                # Clear thumbnail_path from database
                                self.image_ops.update_image_thumbnails(
                                    job["image_id"],
                                    {"thumbnail_path": None, "small_path": None},
                                )

                except Exception as e:
                    error_msg = f"Error cleaning thumbnail for job {job['id']}: {e}"
                    errors.append(error_msg)
                    logger.warning(error_msg)

            result = {
                "files_checked": files_checked,
                "files_removed": files_removed,
                "recovered_jobs_found": len(recovered_jobs),
                "errors": errors,
            }

            if files_removed > 0:
                logger.info(f"🖼️ Cleaned up {files_removed} incomplete thumbnail files")
            else:
                logger.debug("🖼️ No incomplete thumbnail files found for cleanup")

            return result

        except Exception as e:
            logger.error(f"Error during thumbnail cleanup: {e}")
            return {
                "files_checked": 0,
                "files_removed": 0,
                "recovered_jobs_found": 0,
                "errors": [str(e)],
            }

    def _cleanup_temporary_files(self, max_age_hours: int) -> Dict[str, Any]:
        """
        Clean up temporary files and processing artifacts.

        Uses the existing temp_file_manager utility to clean up temporary files
        that may have been left behind during processing.

        Args:
            max_age_hours: Maximum age of temporary files to clean up

        Returns:
            Dictionary with cleanup results
        """
        try:
            logger.info("🗑️ Cleaning up temporary files...")

            # Use existing temp file cleanup utility
            files_removed = cleanup_temporary_files(max_age_hours=max_age_hours)

            result = {"files_removed": files_removed, "max_age_hours": max_age_hours}

            if files_removed > 0:
                logger.info(f"🗑️ Cleaned up {files_removed} temporary files")
            else:
                logger.debug("🗑️ No temporary files found for cleanup")

            return result

        except Exception as e:
            logger.error(f"Error during temporary file cleanup: {e}")
            return {"files_removed": 0, "max_age_hours": max_age_hours, "error": str(e)}

    def _cleanup_orphaned_files(self, max_age_hours: int) -> Dict[str, Any]:
        """
        Clean up orphaned files that don't have corresponding database records.

        WARNING: This is an aggressive cleanup operation that should be used carefully.
        It checks for files in the storage directories that don't have corresponding
        database records and removes them if they're old enough.

        This scans for:
        1. Image files in cameras directory without database records
        2. Thumbnail files without corresponding image records
        3. Small image files without corresponding image records
        4. Overlay files without corresponding image records
        5. Video files without corresponding database records

        Args:
            max_age_hours: Maximum age of files to consider for cleanup

        Returns:
            Dictionary with cleanup results
        """
        try:
            logger.info("🔍 Scanning for orphaned files (aggressive cleanup)...")

            # Initialize result tracking
            result = {
                "files_scanned": 0,
                "files_removed": 0,
                "orphaned_files_found": 0,
                "directories_scanned": 0,
                "by_type": {
                    "images": {"scanned": 0, "removed": 0},
                    "thumbnails": {"scanned": 0, "removed": 0},
                    "small_images": {"scanned": 0, "removed": 0},
                    "overlays": {"scanned": 0, "removed": 0},
                    "videos": {"scanned": 0, "removed": 0},
                },
                "errors": [],
            }

            # Calculate cutoff time for old files
            cutoff_time = utc_now() - timedelta(hours=max_age_hours)

            # Get all database file paths for comparison
            db_file_paths = self._get_all_database_file_paths()

            # 1. Clean up orphaned images in cameras directory
            self._cleanup_orphaned_images(
                settings.images_directory, db_file_paths, cutoff_time, result
            )

            # 2. Clean up orphaned thumbnails
            self._cleanup_orphaned_thumbnails(
                settings.thumbnails_directory, db_file_paths, cutoff_time, result
            )

            # 3. Clean up orphaned videos
            self._cleanup_orphaned_videos(
                settings.videos_directory, db_file_paths, cutoff_time, result
            )

            # Update totals
            result["orphaned_files_found"] = sum(
                type_data["scanned"] - type_data["removed"]
                for type_data in result["by_type"].values()
            )

            if result["files_removed"] > 0:
                logger.warning(
                    f"🔍 Removed {result['files_removed']} orphaned files "
                    f"(scanned {result['files_scanned']} total files)"
                )
            else:
                logger.info(
                    f"🔍 No orphaned files found "
                    f"(scanned {result['files_scanned']} files)"
                )

            return result

        except Exception as e:
            logger.error(f"Error during orphaned file cleanup: {e}")
            return {
                "files_scanned": 0,
                "files_removed": 0,
                "orphaned_files_found": 0,
                "directories_scanned": 0,
                "by_type": {},
                "errors": [str(e)],
            }

    def _get_all_database_file_paths(self) -> set:
        """Get all file paths that are referenced in the database using operations layer."""
        try:

            file_paths = set()

            # Get all image file paths using operations layer
            image_file_paths = self.image_ops.get_all_file_paths()
            for path in image_file_paths:
                if path:
                    # Convert to absolute path for comparison using file helpers
                    if not Path(path).is_absolute():
                        abs_path = Path(settings.data_directory) / path
                    else:
                        abs_path = Path(path)
                    file_paths.add(str(abs_path.resolve()))

            # Get video file paths using operations layer
            try:
                video_file_paths = self.video_ops.get_all_video_file_paths()
                for path in video_file_paths:
                    if path:
                        # Convert to absolute path for comparison using file helpers
                        if not Path(path).is_absolute():
                            abs_path = Path(settings.data_directory) / path
                        else:
                            abs_path = Path(path)
                        file_paths.add(str(abs_path.resolve()))
            except Exception as e:
                # Video operations might not be available
                logger.debug(f"Could not get video file paths: {e}")

            logger.debug(f"Found {len(file_paths)} file paths in database")
            return file_paths

        except Exception as e:
            logger.error(f"Error getting database file paths: {e}")
            return set()

    def _cleanup_orphaned_images(
        self,
        images_dir: str,
        db_paths: set,
        cutoff_time: datetime,
        result: Dict[str, Any],
    ) -> None:
        """Clean up orphaned image files in the cameras directory."""
        try:
            images_path = Path(images_dir)
            if not images_path.exists():
                return

            result["directories_scanned"] += 1

            # Scan for image files recursively
            image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

            for image_file in images_path.rglob("*"):
                if (
                    image_file.is_file()
                    and image_file.suffix.lower() in image_extensions
                ):
                    result["by_type"]["images"]["scanned"] += 1
                    result["files_scanned"] += 1

                    # Check if file is old enough
                    file_mtime = datetime.fromtimestamp(
                        image_file.stat().st_mtime, tz=UTC_TIMEZONE
                    )
                    if file_mtime > cutoff_time:
                        continue

                    # Check if file path exists in database
                    abs_file_path = str(image_file.resolve())
                    if abs_file_path not in db_paths:
                        try:
                            image_file.unlink()
                            result["by_type"]["images"]["removed"] += 1
                            result["files_removed"] += 1
                            logger.debug(f"Removed orphaned image: {image_file}")
                        except Exception as e:
                            error_msg = (
                                f"Failed to remove orphaned image {image_file}: {e}"
                            )
                            result["errors"].append(error_msg)
                            logger.warning(error_msg)

        except Exception as e:
            error_msg = f"Error scanning images directory {images_dir}: {e}"
            result["errors"].append(error_msg)
            logger.error(error_msg)

    def _cleanup_orphaned_thumbnails(
        self,
        thumbnails_dir: str,
        db_paths: set,
        cutoff_time: datetime,
        result: Dict[str, Any],
    ) -> None:
        """Clean up orphaned thumbnail and small image files."""
        try:
            thumbnails_path = Path(thumbnails_dir)
            if not thumbnails_path.exists():
                return

            result["directories_scanned"] += 1

            # Scan for thumbnail files
            image_extensions = {".jpg", ".jpeg", ".png", ".webp"}

            for thumb_file in thumbnails_path.rglob("*"):
                if (
                    thumb_file.is_file()
                    and thumb_file.suffix.lower() in image_extensions
                ):
                    # Determine if it's a thumbnail or small image based on naming convention
                    if "_small." in thumb_file.name:
                        file_type = "small_images"
                    else:
                        file_type = "thumbnails"

                    result["by_type"][file_type]["scanned"] += 1
                    result["files_scanned"] += 1

                    # Check if file is old enough
                    file_mtime = datetime.fromtimestamp(
                        thumb_file.stat().st_mtime, tz=UTC_TIMEZONE
                    )
                    if file_mtime > cutoff_time:
                        continue

                    # Check if file path exists in database
                    abs_file_path = str(thumb_file.resolve())
                    if abs_file_path not in db_paths:
                        try:
                            thumb_file.unlink()
                            result["by_type"][file_type]["removed"] += 1
                            result["files_removed"] += 1
                            logger.debug(
                                f"Removed orphaned {file_type.replace('_', ' ')}: {thumb_file}"
                            )
                        except Exception as e:
                            error_msg = f"Failed to remove orphaned {file_type} {thumb_file}: {e}"
                            result["errors"].append(error_msg)
                            logger.warning(error_msg)

        except Exception as e:
            error_msg = f"Error scanning thumbnails directory {thumbnails_dir}: {e}"
            result["errors"].append(error_msg)
            logger.error(error_msg)

    def _cleanup_orphaned_videos(
        self,
        videos_dir: str,
        db_paths: set,
        cutoff_time: datetime,
        result: Dict[str, Any],
    ) -> None:
        """Clean up orphaned video files."""
        try:
            videos_path = Path(videos_dir)
            if not videos_path.exists():
                return

            result["directories_scanned"] += 1

            # Scan for video files
            video_extensions = ALLOWED_VIDEO_EXTENSIONS

            for video_file in videos_path.rglob("*"):
                if (
                    video_file.is_file()
                    and video_file.suffix.lower() in video_extensions
                ):
                    result["by_type"]["videos"]["scanned"] += 1
                    result["files_scanned"] += 1

                    # Check if file is old enough
                    file_mtime = datetime.fromtimestamp(
                        video_file.stat().st_mtime, tz=UTC_TIMEZONE
                    )
                    if file_mtime > cutoff_time:
                        continue

                    # Check if file path exists in database
                    abs_file_path = str(video_file.resolve())
                    if abs_file_path not in db_paths:
                        try:
                            video_file.unlink()
                            result["by_type"]["videos"]["removed"] += 1
                            result["files_removed"] += 1
                            logger.debug(f"Removed orphaned video: {video_file}")
                        except Exception as e:
                            error_msg = (
                                f"Failed to remove orphaned video {video_file}: {e}"
                            )
                            result["errors"].append(error_msg)
                            logger.warning(error_msg)

        except Exception as e:
            error_msg = f"Error scanning videos directory {videos_dir}: {e}"
            result["errors"].append(error_msg)
            logger.error(error_msg)

    def get_cleanup_recommendations(self) -> Dict[str, Any]:
        """
        Analyze the system and provide cleanup recommendations.

        Returns:
            Dictionary with recommended cleanup actions
        """
        try:
            recommendations = {
                "timestamp": utc_timestamp(),
                "recommendations": [],
                "estimated_cleanup_impact": {},
            }

            # Check for stuck jobs that might have left artifacts using operations layer
            stuck_thumbnail_jobs = 0
            try:
                # Use operations layer to get recovered jobs and count them
                recovered_jobs = self.thumbnail_ops.get_recovered_jobs(24)  # 24 hours
                stuck_thumbnail_jobs = len(recovered_jobs)
            except Exception as e:
                logger.warning(f"Error checking stuck jobs: {e}")

            if stuck_thumbnail_jobs > 0:
                recommendations["recommendations"].append(
                    {
                        "type": "thumbnail_cleanup",
                        "priority": "medium",
                        "description": f"Found {stuck_thumbnail_jobs} recently recovered thumbnail jobs that may have left incomplete files",
                        "action": "Run startup cleanup with thumbnail cleanup enabled",
                    }
                )

            # Check temporary file directory size using temp file manager
            temp_file_count = get_timelapser_temp_file_count()
            if temp_file_count > 10:
                recommendations["recommendations"].append(
                    {
                        "type": "temp_file_cleanup",
                        "priority": "low",
                        "description": f"Found {temp_file_count} temporary files",
                        "action": "Run temporary file cleanup",
                    }
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error generating cleanup recommendations: {e}")
            return {
                "timestamp": utc_timestamp(),
                "error": str(e),
                "recommendations": [],
            }
