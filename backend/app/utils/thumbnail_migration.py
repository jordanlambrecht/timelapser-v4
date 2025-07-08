# backend/app/utils/thumbnail_migration.py
"""
Thumbnail Migration Utility

Migrates thumbnail files from camera-based structure to timelapse-based structure
according to the architecture document specifications.

MIGRATION PATH:
FROM: cameras/camera-{id}/thumbnails/{date}/{filename}
TO:   cameras/camera-{id}/timelapse-{id}/thumbnails/{filename}

This utility provides safe migration with rollback capability and comprehensive logging.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from loguru import logger

from ..database.core import SyncDatabase
from ..database.image_operations import SyncImageOperations
from ..database.camera_operations import SyncCameraOperations
from ..database.timelapse_operations import SyncTimelapseOperations
from ..utils.timezone_utils import utc_now


@dataclass
class MigrationResult:
    """Result of a migration operation"""

    success: bool
    files_processed: int = 0
    files_migrated: int = 0
    files_failed: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    rollback_data: Optional[Dict[str, Any]] = None


@dataclass
class ThumbnailFileInfo:
    """Information about a thumbnail file to be migrated"""

    source_path: Path
    camera_id: int
    date_folder: str
    filename: str
    size_type: str  # 'thumbnail' or 'small'
    image_id: Optional[int] = None
    timelapse_id: Optional[int] = None
    target_path: Optional[Path] = None


class ThumbnailMigrationService:
    """
    Service for migrating thumbnail files from legacy structure to timelapse-based structure.

    Features:
    - Safe migration with file existence verification
    - Rollback capability for failed migrations
    - Batch processing with progress tracking
    - Database path updates
    - Comprehensive error handling and logging
    """

    def __init__(
        self,
        db: SyncDatabase,
        data_directory: str,
        dry_run: bool = False,
        batch_size: int = 100,
    ):
        """
        Initialize migration service.

        Args:
            db: Sync database instance
            data_directory: Base data directory path
            dry_run: If True, simulate migration without moving files
            batch_size: Number of files to process per batch
        """
        self.db = db
        self.data_directory = Path(data_directory)
        self.dry_run = dry_run
        self.batch_size = batch_size

        # Database operations
        self.image_ops = SyncImageOperations(db)
        self.camera_ops = SyncCameraOperations(db)
        self.timelapse_ops = SyncTimelapseOperations(db)

        # Migration state
        self.rollback_data: Dict[str, List[Tuple[Path, Path]]] = {}

    def analyze_existing_structure(self) -> Dict[str, Any]:
        """
        Analyze existing thumbnail structure to understand scope of migration.

        Returns:
            Dictionary with analysis results
        """
        logger.info("Analyzing existing thumbnail structure...")

        analysis = {
            "total_thumbnail_files": 0,
            "total_small_files": 0,
            "cameras_with_thumbnails": 0,
            "date_folders_found": 0,
            "estimated_migration_size_mb": 0.0,
            "structure_issues": [],
            "cameras": {},
        }

        try:
            cameras_dir = self.data_directory / "cameras"
            if not cameras_dir.exists():
                analysis["structure_issues"].append("No cameras directory found")
                return analysis

            for camera_dir in cameras_dir.iterdir():
                if not camera_dir.is_dir() or not camera_dir.name.startswith("camera-"):
                    continue

                camera_id_str = camera_dir.name.replace("camera-", "")
                try:
                    camera_id = int(camera_id_str)
                except ValueError:
                    analysis["structure_issues"].append(
                        f"Invalid camera directory: {camera_dir.name}"
                    )
                    continue

                camera_analysis = self._analyze_camera_thumbnails(camera_dir, camera_id)

                if (
                    camera_analysis["thumbnail_files"] > 0
                    or camera_analysis["small_files"] > 0
                ):
                    analysis["cameras_with_thumbnails"] += 1
                    analysis["cameras"][camera_id] = camera_analysis
                    analysis["total_thumbnail_files"] += camera_analysis[
                        "thumbnail_files"
                    ]
                    analysis["total_small_files"] += camera_analysis["small_files"]
                    analysis["date_folders_found"] += camera_analysis["date_folders"]
                    analysis["estimated_migration_size_mb"] += camera_analysis[
                        "total_size_mb"
                    ]

            logger.info(
                f"Analysis complete: {analysis['total_thumbnail_files']} thumbnails, "
                f"{analysis['total_small_files']} small images across "
                f"{analysis['cameras_with_thumbnails']} cameras"
            )

        except Exception as e:
            logger.error(f"Error during structure analysis: {e}")
            analysis["structure_issues"].append(f"Analysis error: {str(e)}")

        return analysis

    def _analyze_camera_thumbnails(
        self, camera_dir: Path, camera_id: int
    ) -> Dict[str, Any]:
        """Analyze thumbnail structure for a specific camera."""
        camera_analysis = {
            "camera_id": camera_id,
            "thumbnail_files": 0,
            "small_files": 0,
            "date_folders": 0,
            "total_size_mb": 0.0,
            "date_ranges": [],
        }

        # Check thumbnails directory
        thumbnails_dir = camera_dir / "thumbnails"
        if thumbnails_dir.exists():
            for date_dir in thumbnails_dir.iterdir():
                if date_dir.is_dir():
                    camera_analysis["date_folders"] += 1
                    camera_analysis["date_ranges"].append(date_dir.name)

                    for thumb_file in date_dir.iterdir():
                        if thumb_file.is_file() and thumb_file.suffix.lower() in [
                            ".jpg",
                            ".jpeg",
                            ".png",
                        ]:
                            camera_analysis["thumbnail_files"] += 1
                            camera_analysis[
                                "total_size_mb"
                            ] += thumb_file.stat().st_size / (1024 * 1024)

        # Check small directory
        small_dir = camera_dir / "small"
        if small_dir.exists():
            for date_dir in small_dir.iterdir():
                if date_dir.is_dir():
                    for small_file in date_dir.iterdir():
                        if small_file.is_file() and small_file.suffix.lower() in [
                            ".jpg",
                            ".jpeg",
                            ".png",
                        ]:
                            camera_analysis["small_files"] += 1
                            camera_analysis[
                                "total_size_mb"
                            ] += small_file.stat().st_size / (1024 * 1024)

        return camera_analysis

    def discover_thumbnail_files(self) -> List[ThumbnailFileInfo]:
        """
        Discover all thumbnail files in legacy structure.

        Returns:
            List of ThumbnailFileInfo objects for all discovered files
        """
        logger.info("Discovering thumbnail files in legacy structure...")

        thumbnail_files = []
        cameras_dir = self.data_directory / "cameras"

        if not cameras_dir.exists():
            logger.warning("No cameras directory found")
            return thumbnail_files

        for camera_dir in cameras_dir.iterdir():
            if not camera_dir.is_dir() or not camera_dir.name.startswith("camera-"):
                continue

            try:
                camera_id = int(camera_dir.name.replace("camera-", ""))
            except ValueError:
                logger.warning(f"Invalid camera directory: {camera_dir.name}")
                continue

            # Process thumbnails directory
            thumbnails_dir = camera_dir / "thumbnails"
            if thumbnails_dir.exists():
                thumbnail_files.extend(
                    self._discover_files_in_size_dir(
                        thumbnails_dir, camera_id, "thumbnail"
                    )
                )

            # Process small directory
            small_dir = camera_dir / "small"
            if small_dir.exists():
                thumbnail_files.extend(
                    self._discover_files_in_size_dir(small_dir, camera_id, "small")
                )

        logger.info(f"Discovered {len(thumbnail_files)} thumbnail files to migrate")
        return thumbnail_files

    def _discover_files_in_size_dir(
        self, size_dir: Path, camera_id: int, size_type: str
    ) -> List[ThumbnailFileInfo]:
        """Discover files in a specific size directory (thumbnails or small)."""
        files = []

        for date_dir in size_dir.iterdir():
            if not date_dir.is_dir():
                continue

            date_folder = date_dir.name

            for file_path in date_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in [
                    ".jpg",
                    ".jpeg",
                    ".png",
                ]:
                    files.append(
                        ThumbnailFileInfo(
                            source_path=file_path,
                            camera_id=camera_id,
                            date_folder=date_folder,
                            filename=file_path.name,
                            size_type=size_type,
                        )
                    )

        return files

    def match_files_to_images(
        self, thumbnail_files: List[ThumbnailFileInfo]
    ) -> List[ThumbnailFileInfo]:
        """
        Match thumbnail files to their corresponding images and timelapses.

        Args:
            thumbnail_files: List of discovered thumbnail files

        Returns:
            List of thumbnail files with image_id and timelapse_id populated
        """
        logger.info(
            f"Matching {len(thumbnail_files)} thumbnail files to database records..."
        )

        matched_files = []
        unmatched_count = 0

        for batch_start in range(0, len(thumbnail_files), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(thumbnail_files))
            batch = thumbnail_files[batch_start:batch_end]

            logger.debug(
                f"Processing batch {batch_start//self.batch_size + 1}: "
                f"files {batch_start}-{batch_end}"
            )

            for file_info in batch:
                try:
                    # Try to match by filename pattern and camera
                    image_record = self._find_matching_image(file_info)

                    if image_record:
                        file_info.image_id = image_record.id
                        file_info.timelapse_id = image_record.timelapse_id

                        # Generate target path
                        file_info.target_path = self._generate_target_path(file_info)
                        matched_files.append(file_info)
                    else:
                        unmatched_count += 1
                        logger.debug(f"Could not match file: {file_info.source_path}")

                except Exception as e:
                    logger.error(f"Error matching file {file_info.source_path}: {e}")
                    unmatched_count += 1

        logger.info(f"Matched {len(matched_files)} files, {unmatched_count} unmatched")
        return matched_files

    def _find_matching_image(self, file_info: ThumbnailFileInfo) -> Optional[Any]:
        """Find the database image record that matches this thumbnail file."""
        try:
            # Get all images for this camera
            # This is a simplified approach - in production you might want more sophisticated matching
            images = self.image_ops.get_images_by_camera(file_info.camera_id)

            # Try to match by filename similarity or date
            filename_base = (
                file_info.filename.replace(".jpg", "")
                .replace(".jpeg", "")
                .replace(".png", "")
            )

            for image in images:
                # Simple filename matching - this could be enhanced based on your naming conventions
                image_filename_base = Path(image.file_path).stem

                if self._files_likely_match(
                    filename_base, image_filename_base, file_info.date_folder
                ):
                    return image

            return None

        except Exception as e:
            logger.error(f"Error finding matching image for {file_info.filename}: {e}")
            return None

    def _files_likely_match(
        self, thumb_filename: str, image_filename: str, date_folder: str
    ) -> bool:
        """Determine if thumbnail and image files likely belong together."""
        # This is a heuristic approach - adjust based on your filename conventions

        # Remove common prefixes/suffixes
        thumb_clean = thumb_filename.lower()
        image_clean = image_filename.lower()

        # Check if they share a common timestamp or pattern
        # This is a simplified check - enhance based on your actual patterns
        return (
            image_clean in thumb_clean
            or thumb_clean in image_clean
            or self._extract_timestamp_from_filename(thumb_clean)
            == self._extract_timestamp_from_filename(image_clean)
        )

    def _extract_timestamp_from_filename(self, filename: str) -> Optional[str]:
        """Extract timestamp pattern from filename for matching."""
        import re

        # Look for timestamp patterns like HHMMSS or HH-MM-SS
        timestamp_patterns = [
            r"\d{6}",  # HHMMSS
            r"\d{2}[-_]\d{2}[-_]\d{2}",  # HH-MM-SS or HH_MM_SS
            r"\d{4}-\d{2}-\d{2}[-_]\d{2}[-_]\d{2}[-_]\d{2}",  # Full datetime
        ]

        for pattern in timestamp_patterns:
            match = re.search(pattern, filename)
            if match:
                return match.group()

        return None

    def _generate_target_path(self, file_info: ThumbnailFileInfo) -> Path:
        """Generate target path for migrated thumbnail file."""
        size_folder = "thumbnails" if file_info.size_type == "thumbnail" else "smalls"

        return (
            self.data_directory
            / "cameras"
            / f"camera-{file_info.camera_id}"
            / f"timelapse-{file_info.timelapse_id}"
            / size_folder
            / file_info.filename
        )

    def migrate_files(self, matched_files: List[ThumbnailFileInfo]) -> MigrationResult:
        """
        Migrate matched thumbnail files to new timelapse-based structure.

        Args:
            matched_files: List of files matched to database records

        Returns:
            MigrationResult with detailed migration statistics
        """
        start_time = datetime.utcnow()
        result = MigrationResult(success=True)

        logger.info(
            f"Starting migration of {len(matched_files)} files (dry_run={self.dry_run})"
        )

        try:
            for batch_start in range(0, len(matched_files), self.batch_size):
                batch_end = min(batch_start + self.batch_size, len(matched_files))
                batch = matched_files[batch_start:batch_end]

                logger.info(
                    f"Processing migration batch {batch_start//self.batch_size + 1}: "
                    f"files {batch_start}-{batch_end}"
                )

                batch_result = self._migrate_file_batch(batch)

                # Aggregate results
                result.files_processed += batch_result.files_processed
                result.files_migrated += batch_result.files_migrated
                result.files_failed += batch_result.files_failed
                result.errors.extend(batch_result.errors)

                if not batch_result.success:
                    result.success = False

        except Exception as e:
            logger.error(f"Critical error during migration: {e}")
            result.success = False
            result.errors.append(f"Critical migration error: {str(e)}")

        finally:
            result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
            result.rollback_data = dict(self.rollback_data)  # Copy for safety

        logger.info(
            f"Migration complete: {result.files_migrated}/{result.files_processed} files migrated "
            f"in {result.duration_seconds:.1f}s"
        )

        return result

    def _migrate_file_batch(self, batch: List[ThumbnailFileInfo]) -> MigrationResult:
        """Migrate a batch of thumbnail files."""
        result = MigrationResult(success=True)

        for file_info in batch:
            try:
                result.files_processed += 1

                if not file_info.target_path:
                    result.errors.append(f"No target path for {file_info.source_path}")
                    result.files_failed += 1
                    continue

                # Create target directory
                if not self.dry_run:
                    file_info.target_path.parent.mkdir(parents=True, exist_ok=True)

                # Move file
                success = self._move_thumbnail_file(file_info)

                if success:
                    result.files_migrated += 1

                    # Store rollback information
                    camera_key = f"camera-{file_info.camera_id}"
                    if camera_key not in self.rollback_data:
                        self.rollback_data[camera_key] = []

                    self.rollback_data[camera_key].append(
                        (file_info.target_path, file_info.source_path)
                    )
                else:
                    result.files_failed += 1

            except Exception as e:
                logger.error(f"Error migrating {file_info.source_path}: {e}")
                result.errors.append(
                    f"Migration error for {file_info.source_path}: {str(e)}"
                )
                result.files_failed += 1

        return result

    def _move_thumbnail_file(self, file_info: ThumbnailFileInfo) -> bool:
        """Move a single thumbnail file to its new location."""
        try:
            if self.dry_run:
                logger.debug(
                    f"DRY RUN: Would move {file_info.source_path} -> {file_info.target_path}"
                )
                return True

            # Check if target path is available
            if not file_info.target_path:
                logger.warning(f"No target path available for: {file_info.source_path}")
                return False

            # Check if source exists
            if not file_info.source_path.exists():
                logger.warning(f"Source file no longer exists: {file_info.source_path}")
                return False

            # Check if target already exists
            if file_info.target_path.exists():
                logger.warning(f"Target already exists: {file_info.target_path}")
                return False

            # Move the file
            shutil.move(str(file_info.source_path), str(file_info.target_path))
            logger.debug(f"Moved: {file_info.source_path} -> {file_info.target_path}")

            return True

        except Exception as e:
            logger.error(f"Failed to move {file_info.source_path}: {e}")
            return False

    def rollback_migration(
        self, rollback_data: Dict[str, List[Tuple[Path, Path]]]
    ) -> MigrationResult:
        """
        Rollback a previous migration by moving files back to original locations.

        Args:
            rollback_data: Rollback data from original migration

        Returns:
            MigrationResult with rollback statistics
        """
        start_time = datetime.utcnow()
        result = MigrationResult(success=True)

        logger.info(f"Starting migration rollback (dry_run={self.dry_run})")

        try:
            for camera_key, file_moves in rollback_data.items():
                logger.info(f"Rolling back {len(file_moves)} files for {camera_key}")

                for target_path, source_path in file_moves:
                    try:
                        result.files_processed += 1

                        if self.dry_run:
                            logger.debug(
                                f"DRY RUN: Would rollback {target_path} -> {source_path}"
                            )
                            result.files_migrated += 1
                        else:
                            # Create source directory if needed
                            source_path.parent.mkdir(parents=True, exist_ok=True)

                            # Move file back
                            if target_path.exists():
                                shutil.move(str(target_path), str(source_path))
                                result.files_migrated += 1
                                logger.debug(
                                    f"Rolled back: {target_path} -> {source_path}"
                                )
                            else:
                                logger.warning(
                                    f"Rollback target missing: {target_path}"
                                )
                                result.files_failed += 1

                    except Exception as e:
                        logger.error(f"Rollback error for {target_path}: {e}")
                        result.errors.append(f"Rollback error: {str(e)}")
                        result.files_failed += 1

        except Exception as e:
            logger.error(f"Critical rollback error: {e}")
            result.success = False
            result.errors.append(f"Critical rollback error: {str(e)}")

        finally:
            result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()

        logger.info(
            f"Rollback complete: {result.files_migrated}/{result.files_processed} files "
            f"rolled back in {result.duration_seconds:.1f}s"
        )

        return result

    def cleanup_empty_directories(self) -> int:
        """
        Clean up empty legacy directories after migration.

        Returns:
            Number of directories removed
        """
        logger.info("Cleaning up empty legacy directories...")

        removed_count = 0
        cameras_dir = self.data_directory / "cameras"

        if not cameras_dir.exists():
            return removed_count

        try:
            for camera_dir in cameras_dir.iterdir():
                if not camera_dir.is_dir() or not camera_dir.name.startswith("camera-"):
                    continue

                # Check thumbnails directory
                thumbnails_dir = camera_dir / "thumbnails"
                if thumbnails_dir.exists():
                    removed_count += self._remove_empty_subdirs(thumbnails_dir)

                    # Remove thumbnails dir if now empty
                    if self._is_directory_empty(thumbnails_dir):
                        if not self.dry_run:
                            thumbnails_dir.rmdir()
                        removed_count += 1
                        logger.debug(
                            f"Removed empty thumbnails directory: {thumbnails_dir}"
                        )

                # Check small directory
                small_dir = camera_dir / "small"
                if small_dir.exists():
                    removed_count += self._remove_empty_subdirs(small_dir)

                    # Remove small dir if now empty
                    if self._is_directory_empty(small_dir):
                        if not self.dry_run:
                            small_dir.rmdir()
                        removed_count += 1
                        logger.debug(f"Removed empty small directory: {small_dir}")

        except Exception as e:
            logger.error(f"Error during directory cleanup: {e}")

        logger.info(f"Cleaned up {removed_count} empty directories")
        return removed_count

    def _remove_empty_subdirs(self, parent_dir: Path) -> int:
        """Remove empty subdirectories within a parent directory."""
        removed_count = 0

        try:
            for subdir in parent_dir.iterdir():
                if subdir.is_dir() and self._is_directory_empty(subdir):
                    if not self.dry_run:
                        subdir.rmdir()
                    removed_count += 1
                    logger.debug(f"Removed empty directory: {subdir}")
        except Exception as e:
            logger.error(f"Error removing subdirectories in {parent_dir}: {e}")

        return removed_count

    def _is_directory_empty(self, directory: Path) -> bool:
        """Check if a directory is empty."""
        try:
            return not any(directory.iterdir())
        except Exception:
            return False
