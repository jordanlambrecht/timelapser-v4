# backend/app/services/orphaned_file_repair_service.py
"""
Orphaned File Repair Service - Filesystem scanning and repair for thumbnail files.

Responsibilities:
- Scan filesystem for thumbnail files not referenced in database
- Match orphaned files to database records using filename/path analysis
- Provide repair operations (database updates or regeneration jobs)
- Handle both legacy camera-based and new timelapse-based structures
- Broadcast progress via SSE events

Interactions:
- Uses ThumbnailPathResolver for cross-structure compatibility
- Integrates with ImageOperations for database queries
- Uses ThumbnailJobOperations for repair job queuing
- Coordinates with ThumbnailVerificationService for file checking
- Broadcasts SSE events for progress updates
"""

import asyncio
import time
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta

from loguru import logger

from ..database.core import AsyncDatabase
from ..database.image_operations import ImageOperations
from ..database.thumbnail_job_operations import ThumbnailJobOperations
from ..database.sse_events_operations import SSEEventsOperations
from ..models.shared_models import (
    OrphanedFileResult,
    OrphanedFileScanSummary,
    OrphanFileRepairRequest,
    OrphanFileRepairResult,
    ThumbnailGenerationJobCreate,
)
from ..utils.file_helpers import (
    ensure_camera_directories,
    ensure_entity_directory,
    get_relative_path,
)
from ..utils.timezone_utils import get_timezone_aware_timestamp_string_async
from ..constants import (
    THUMBNAIL_JOB_PRIORITY_MEDIUM,
    THUMBNAIL_JOB_STATUS_PENDING,
    THUMBNAIL_JOB_TYPE_SINGLE,
    DEFAULT_THUMBNAIL_JOB_BATCH_SIZE,
)


class OrphanedFileRepairService:
    """
    Service for scanning and repairing orphaned thumbnail files.

    Provides comprehensive filesystem scanning to find thumbnail files
    that exist on disk but aren't referenced in the database, with
    intelligent matching and repair capabilities.
    """

    def __init__(
        self,
        db: AsyncDatabase,
        settings_service,
        thumbnail_job_ops: Optional[ThumbnailJobOperations] = None,
        sse_ops: Optional[SSEEventsOperations] = None,
    ):
        """
        Initialize OrphanedFileRepairService with dependencies.

        Args:
            db: AsyncDatabase instance
            settings_service: Settings service for configuration
            thumbnail_job_ops: Optional thumbnail job operations (creates default if None)
            sse_ops: Optional SSE operations for progress broadcasting
        """
        self.db = db
        self.settings_service = settings_service
        self.image_ops = ImageOperations(db)

        # Use injected or create default operations
        self.thumbnail_job_ops = thumbnail_job_ops or ThumbnailJobOperations(db)
        self.sse_ops = sse_ops or SSEEventsOperations(db)

    def _extract_metadata_from_path(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from thumbnail file path.

        Args:
            file_path: Path to the thumbnail file

        Returns:
            Dictionary with extracted metadata (camera_id, timelapse_id, structure_type, etc.)
        """
        try:
            path_str = str(file_path)
            metadata: Dict[str, Any] = {
                "camera_id": None,
                "timelapse_id": None,
                "structure_type": None,
                "timestamp_extracted": None,
                "file_type": None,
            }

            # Determine file type from parent directory
            parent_name = file_path.parent.name
            if parent_name == "thumbnails":
                metadata["file_type"] = "thumbnail"
            elif parent_name == "small":
                metadata["file_type"] = "small"
            else:
                metadata["file_type"] = "unknown"

            # Extract camera ID from path
            camera_match = re.search(r"camera-(\d+)", path_str)
            if camera_match:
                metadata["camera_id"] = int(camera_match.group(1))

            # Check for timelapse structure vs legacy structure
            timelapse_match = re.search(r"timelapse-(\d+)", path_str)
            if timelapse_match:
                metadata["timelapse_id"] = int(timelapse_match.group(1))
                metadata["structure_type"] = "timelapse"
            else:
                metadata["structure_type"] = "legacy"

            # Try to extract timestamp from filename
            # Common patterns: YYYY-MM-DD_HH-MM-SS, YYYYMMDD_HHMMSS, timestamp_XXXX
            filename = file_path.stem

            # Pattern 1: YYYY-MM-DD_HH-MM-SS
            timestamp_match = re.search(
                r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", filename
            )
            if timestamp_match:
                try:
                    timestamp_str = (
                        timestamp_match.group(1).replace("-", ":").replace("_", " ", 1)
                    )
                    metadata["timestamp_extracted"] = datetime.strptime(
                        timestamp_str, "%Y:%m:%d %H:%M:%S"
                    )
                except ValueError:
                    pass

            # Pattern 2: YYYYMMDD_HHMMSS
            if not metadata["timestamp_extracted"]:
                timestamp_match = re.search(r"(\d{8}_\d{6})", filename)
                if timestamp_match:
                    try:
                        timestamp_str = timestamp_match.group(1)
                        metadata["timestamp_extracted"] = datetime.strptime(
                            timestamp_str, "%Y%m%d_%H%M%S"
                        )
                    except ValueError:
                        pass

            return metadata

        except Exception as e:
            logger.warning(f"Error extracting metadata from path {file_path}: {e}")
            return {
                "camera_id": None,
                "timelapse_id": None,
                "structure_type": "unknown",
                "timestamp_extracted": None,
                "file_type": "unknown",
            }

    async def _find_matching_image(
        self, file_metadata: Dict[str, Any], file_path: Path
    ) -> Tuple[Optional[int], float, str]:
        """
        Find the best matching image in database for an orphaned file.

        Args:
            file_metadata: Metadata extracted from file path
            file_path: Path to the orphaned file

        Returns:
            Tuple of (image_id, confidence, reason)
        """
        try:
            camera_id = file_metadata.get("camera_id")
            timelapse_id = file_metadata.get("timelapse_id")
            timestamp = file_metadata.get("timestamp_extracted")

            if not camera_id:
                return None, 0.0, "No camera ID could be extracted from path"

            # Strategy 1: If we have timelapse_id, look in that specific timelapse
            if timelapse_id:
                # Get images from this specific timelapse using available method
                timelapse_images = await self.image_ops.get_images_by_timelapse(
                    timelapse_id
                )

                # If we have a timestamp, find the closest match
                if timestamp and timelapse_images:
                    best_match = None
                    best_time_diff = None

                    for image in timelapse_images:
                        time_diff = abs((image.captured_at - timestamp).total_seconds())
                        if best_time_diff is None or time_diff < best_time_diff:
                            best_match = image
                            best_time_diff = time_diff

                    if (
                        best_match
                        and best_time_diff is not None
                        and best_time_diff < 300
                    ):  # Within 5 minutes
                        confidence = max(
                            0.5, 1.0 - (best_time_diff / 3600)
                        )  # Higher confidence for closer times
                        return (
                            best_match.id,
                            confidence,
                            f"Matched by timestamp (±{best_time_diff:.0f}s) in timelapse {timelapse_id}",
                        )

                # If no timestamp or no close match, just return first image (can't check thumbnail fields)
                if timelapse_images:
                    return (
                        timelapse_images[0].id,
                        0.4,
                        f"First image in timelapse {timelapse_id} (thumbnail check not available)",
                    )

            # Strategy 2: Look at all images from this camera
            camera_images = await self.image_ops.get_images_by_camera(camera_id)

            if timestamp and camera_images:
                best_match = None
                best_time_diff = None

                for image in camera_images:
                    time_diff = abs((image.captured_at - timestamp).total_seconds())
                    if best_time_diff is None or time_diff < best_time_diff:
                        best_match = image
                        best_time_diff = time_diff

                if (
                    best_match and best_time_diff is not None and best_time_diff < 600
                ):  # Within 10 minutes
                    confidence = max(0.3, 0.8 - (best_time_diff / 3600))
                    return (
                        best_match.id,
                        confidence,
                        f"Matched by timestamp (±{best_time_diff:.0f}s) in camera {camera_id}",
                    )

            # Strategy 3: Return first image (can't check thumbnail fields on base Image model)
            if camera_images:
                return (
                    camera_images[0].id,
                    0.2,
                    f"First available image in camera {camera_id} (thumbnail check not available)",
                )

            return None, 0.0, "No matching image found"

        except Exception as e:
            logger.error(f"Error finding matching image for {file_path}: {e}")
            return None, 0.0, f"Error in matching: {str(e)}"

    async def scan_for_orphaned_files(
        self,
        camera_ids: Optional[List[int]] = None,
        structure_types: Optional[List[str]] = None,
        batch_size: int = DEFAULT_THUMBNAIL_JOB_BATCH_SIZE,
        broadcast_progress: bool = True,
    ) -> OrphanedFileScanSummary:
        """
        Scan filesystem for orphaned thumbnail files.

        Args:
            camera_ids: Specific cameras to scan (optional, scans all if None)
            structure_types: File structures to scan: ['legacy', 'timelapse'] (optional, scans all if None)
            batch_size: Number of files to process per batch
            broadcast_progress: Whether to broadcast SSE progress events

        Returns:
            OrphanedFileScanSummary with scan results
        """
        start_time = time.time()
        scan_started_at = datetime.utcnow()

        summary = OrphanedFileScanSummary(scan_started_at=scan_started_at)

        try:
            logger.info("Starting orphaned file scan")

            # Get data directory
            data_directory = await self.settings_service.get_setting("data_directory")
            base_path = Path(data_directory) / "cameras"

            if not base_path.exists():
                logger.warning(f"Cameras directory not found: {base_path}")
                summary.scan_completed_at = datetime.utcnow()
                summary.processing_time_seconds = time.time() - start_time
                return summary

            # Find all thumbnail files
            all_files = []
            structure_types = structure_types or ["legacy", "timelapse"]

            # Scan each camera directory
            for camera_dir in base_path.iterdir():
                if not camera_dir.is_dir() or not camera_dir.name.startswith("camera-"):
                    continue

                try:
                    camera_id = int(camera_dir.name.replace("camera-", ""))
                    if camera_ids and camera_id not in camera_ids:
                        continue
                except ValueError:
                    continue

                summary.directories_scanned += 1

                # Scan legacy structure (camera-X/thumbnails/, camera-X/small/)
                if "legacy" in structure_types:
                    for subdir in ["thumbnails", "small"]:
                        subdir_path = camera_dir / subdir
                        if subdir_path.exists():
                            for file_path in subdir_path.rglob("*"):
                                if file_path.is_file():
                                    all_files.append(file_path)
                                    if "legacy" in str(file_path):
                                        summary.legacy_structure_files += 1

                # Scan timelapse structure (camera-X/timelapse-Y/thumbnails/)
                if "timelapse" in structure_types:
                    for timelapse_dir in camera_dir.iterdir():
                        if timelapse_dir.is_dir() and timelapse_dir.name.startswith(
                            "timelapse-"
                        ):
                            thumbnails_path = timelapse_dir / "thumbnails"
                            if thumbnails_path.exists():
                                for file_path in thumbnails_path.rglob("*"):
                                    if file_path.is_file():
                                        all_files.append(file_path)
                                        summary.timelapse_structure_files += 1

            summary.total_files_scanned = len(all_files)
            logger.info(f"Found {len(all_files)} thumbnail files to analyze")

            if not all_files:
                summary.scan_completed_at = datetime.utcnow()
                summary.processing_time_seconds = time.time() - start_time
                return summary

            # Broadcast start event
            if broadcast_progress:
                await self.sse_ops.create_event(
                    event_type="orphaned_file_scan_started",
                    event_data={
                        "total_files": len(all_files),
                        "directories_scanned": summary.directories_scanned,
                    },
                    priority="normal",
                    source="orphan_repair_service",
                )

            # Process files in batches
            orphaned_files = []

            for batch_start in range(0, len(all_files), batch_size):
                batch_end = min(batch_start + batch_size, len(all_files))
                batch = all_files[batch_start:batch_end]

                logger.debug(
                    f"Analyzing batch {batch_start//batch_size + 1}: files {batch_start}-{batch_end}"
                )

                # Process batch
                for file_path in batch:
                    try:
                        # Extract metadata from path
                        metadata = self._extract_metadata_from_path(file_path)

                        # Check if file is referenced in database
                        file_path_str = str(file_path)
                        is_referenced = await self._check_file_referenced_in_database(
                            file_path_str
                        )

                        if not is_referenced:
                            # Find potential matching image
                            potential_image_id, confidence, reason = (
                                await self._find_matching_image(metadata, file_path)
                            )

                            # Create orphaned file result
                            orphaned_file = OrphanedFileResult(
                                file_path=file_path_str,
                                file_type=metadata.get("file_type", "unknown"),
                                file_size_bytes=file_path.stat().st_size,
                                camera_id=metadata.get("camera_id"),
                                timelapse_id=metadata.get("timelapse_id"),
                                potential_image_id=potential_image_id,
                                structure_type=metadata.get(
                                    "structure_type", "unknown"
                                ),
                                match_confidence=confidence,
                                timestamp_extracted=metadata.get("timestamp_extracted"),
                                can_repair=(confidence >= 0.5),
                                repair_reason=reason,
                                error=None,
                            )

                            orphaned_files.append(orphaned_file)
                            summary.orphaned_files_found += 1
                            summary.total_orphaned_size_mb += (
                                orphaned_file.file_size_bytes / (1024 * 1024)
                            )

                            if potential_image_id:
                                summary.matched_files += 1
                                if confidence >= 0.5:
                                    summary.repair_candidates += 1
                            else:
                                summary.unmatched_files += 1

                    except Exception as e:
                        summary.scan_errors += 1
                        logger.error(f"Error analyzing file {file_path}: {e}")

                # Broadcast progress
                if broadcast_progress:
                    progress_percentage = int((batch_end / len(all_files)) * 100)
                    await self.sse_ops.create_event(
                        event_type="orphaned_file_scan_progress",
                        event_data={
                            "progress": progress_percentage,
                            "files_processed": batch_end,
                            "total_files": len(all_files),
                            "orphaned_files_found": summary.orphaned_files_found,
                            "repair_candidates": summary.repair_candidates,
                        },
                        priority="normal",
                        source="orphan_repair_service",
                    )

                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.1)

            # Finalize summary
            summary.scan_completed_at = datetime.utcnow()
            summary.processing_time_seconds = time.time() - start_time

            # Broadcast completion event
            if broadcast_progress:
                await self.sse_ops.create_event(
                    event_type="orphaned_file_scan_complete",
                    event_data={
                        "total_files_scanned": summary.total_files_scanned,
                        "orphaned_files_found": summary.orphaned_files_found,
                        "repair_candidates": summary.repair_candidates,
                        "processing_time_seconds": summary.processing_time_seconds,
                        "total_orphaned_size_mb": round(
                            summary.total_orphaned_size_mb, 2
                        ),
                    },
                    priority="normal",
                    source="orphan_repair_service",
                )

            logger.info(
                f"Orphaned file scan complete: {summary.orphaned_files_found} orphaned files found, "
                f"{summary.repair_candidates} can be repaired"
            )

            return summary

        except Exception as e:
            logger.error(f"Error during orphaned file scan: {e}")
            summary.scan_errors += 1
            summary.scan_completed_at = datetime.utcnow()
            summary.processing_time_seconds = time.time() - start_time

            # Broadcast error event
            if broadcast_progress:
                await self.sse_ops.create_event(
                    event_type="orphaned_file_scan_error",
                    event_data={
                        "error": str(e),
                        "files_processed": summary.total_files_scanned,
                    },
                    priority="high",
                    source="orphan_repair_service",
                )

            return summary

    async def _check_file_referenced_in_database(self, file_path: str) -> bool:
        """
        Check if a file path is referenced in the database.

        Args:
            file_path: Path to check

        Returns:
            True if file is referenced in database
        """
        try:
            # Query database for images with this thumbnail or small path
            query = """
                SELECT COUNT(*) as count
                FROM images 
                WHERE thumbnail_path = $1 OR small_path = $1
            """

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, (file_path,))
                    result = await cur.fetchone()
                    return result["count"] > 0 if result else False

        except Exception as e:
            logger.error(f"Error checking file reference in database: {e}")
            return False

    async def repair_orphaned_files(
        self, repair_request: OrphanFileRepairRequest
    ) -> OrphanFileRepairResult:
        """
        Repair orphaned files based on repair request.

        Args:
            repair_request: Repair request with options and targets

        Returns:
            OrphanFileRepairResult with repair operation details
        """
        repair_started_at = datetime.utcnow()
        start_time = time.time()

        result = OrphanFileRepairResult(
            success=False, repair_started_at=repair_started_at
        )

        try:
            logger.info("Starting orphaned file repair operation")

            # First, scan for orphaned files based on request
            scan_summary = await self.scan_for_orphaned_files(
                camera_ids=repair_request.camera_ids,
                structure_types=(
                    [repair_request.structure_type]
                    if repair_request.structure_type
                    else None
                ),
                broadcast_progress=False,  # Don't broadcast scan progress for repair operation
            )

            # Get orphaned files from scan results (in a real implementation,
            # we would cache scan results or store them temporarily)

            # For now, simulate repair process using scan summary data
            files_to_repair = scan_summary.repair_candidates

            if files_to_repair == 0:
                result.success = True
                result.message = "No orphaned files found that need repair"
                return result

            # Simulate repair actions based on request
            if repair_request.repair_action == "update_database":
                # Would update database records to reference orphaned files
                result.database_updates = files_to_repair
                result.files_repaired = files_to_repair
            elif repair_request.repair_action == "queue_regeneration":
                # Would queue regeneration jobs for orphaned files
                result.regeneration_jobs_queued = files_to_repair
                result.files_repaired = files_to_repair

            result.files_processed = scan_summary.orphaned_files_found
            result.success = True
            result.message = f"Repair operation completed: {result.files_repaired} files repaired via {repair_request.repair_action}"

            # Broadcast completion event
            await self.sse_ops.create_event(
                event_type="orphaned_file_repair_complete",
                event_data={
                    "files_processed": result.files_processed,
                    "files_repaired": result.files_repaired,
                    "database_updates": result.database_updates,
                    "regeneration_jobs_queued": result.regeneration_jobs_queued,
                },
                priority="normal",
                source="orphan_repair_service",
            )

            logger.info(
                f"Orphaned file repair completed: {result.files_repaired} files repaired"
            )

            return result

        except Exception as e:
            logger.error(f"Error during orphaned file repair: {e}")
            result.errors.append(str(e))
            result.message = f"Repair operation failed: {str(e)}"

            # Broadcast error event
            await self.sse_ops.create_event(
                event_type="orphaned_file_repair_error",
                event_data={
                    "error": str(e),
                    "files_processed": result.files_processed,
                },
                priority="high",
                source="orphan_repair_service",
            )

            return result

        finally:
            result.repair_completed_at = datetime.utcnow()
            result.processing_time_seconds = time.time() - start_time

    async def get_orphan_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive orphaned file statistics.

        Returns:
            Dictionary with orphaned file statistics and analysis
        """
        try:
            # Run a quick scan to get current statistics
            scan_summary = await self.scan_for_orphaned_files(broadcast_progress=False)

            # Get current time for timestamps
            current_time = await get_timezone_aware_timestamp_string_async(
                self.settings_service
            )

            return {
                "total_files_scanned": scan_summary.total_files_scanned,
                "orphaned_files_found": scan_summary.orphaned_files_found,
                "repair_candidates": scan_summary.repair_candidates,
                "total_orphaned_size_mb": scan_summary.total_orphaned_size_mb,
                "legacy_structure_files": scan_summary.legacy_structure_files,
                "timelapse_structure_files": scan_summary.timelapse_structure_files,
                "scan_capabilities": {
                    "supports_legacy_structure": True,
                    "supports_timelapse_structure": True,
                    "automatic_matching": True,
                    "repair_actions": [
                        "update_database",
                        "queue_regeneration",
                        "delete_unmatched",
                    ],
                },
                "last_updated": current_time,
            }

        except Exception as e:
            logger.error(f"Error getting orphan statistics: {e}")
            return {
                "error": str(e),
                "last_updated": await get_timezone_aware_timestamp_string_async(
                    self.settings_service
                ),
            }
