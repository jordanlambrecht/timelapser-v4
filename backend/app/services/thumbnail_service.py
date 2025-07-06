# backend/app/services/thumbnail_service.py
"""
Thumbnail Service - Composition-based architecture.

This service handles thumbnail-related business logic using dependency injection
for database operations, providing type-safe Pydantic model interfaces.

Responsibilities:
- Thumbnail generation and regeneration
- Progress tracking for bulk operations
- SSE broadcasting for real-time updates
- State management for background processes
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
import asyncio
from pathlib import Path

from ..database.core import AsyncDatabase
from ..database.image_operations import ImageOperations
from ..database.sse_events_operations import SSEEventsOperations
from ..models.shared_models import (
    ThumbnailGenerationResult,
    ThumbnailRegenerationResponse,
    ThumbnailRegenerationStatus,
    ThumbnailOperationResponse,
    ThumbnailStatistics,
)
from ..utils.cache_manager import cached_response
from ..utils.timezone_utils import get_timezone_aware_timestamp_string_async
from ..constants import (
    MAX_BULK_OPERATION_ITEMS,
)


class ThumbnailService:
    """
    Thumbnail business logic service.

    Responsibilities:
    - Thumbnail generation coordination
    - Bulk regeneration with progress tracking
    - Real-time SSE progress broadcasting
    - Background task management

    Interactions:
    - Uses ImageOperations for database queries
    - Coordinates with ImageService for thumbnail generation
    - Broadcasts SSE events for frontend updates
    - Manages background processing state
    """

    # Class-level shared state for regeneration tracking
    _regeneration_active = False
    _regeneration_progress = {
        "total_images": 0,
        "completed_images": 0,
        "failed_images": 0,
        "current_image": None,
        "status_message": "idle",
    }

    def __init__(self, db: AsyncDatabase, settings_service, image_service):
        """
        Initialize ThumbnailService with async database instance and service dependencies.

        Args:
            db: AsyncDatabase instance
            settings_service: SettingsService for configuration management
            image_service: ImageService for thumbnail generation coordination
        """
        self.db = db
        self.image_ops = ImageOperations(db)
        self.sse_ops = SSEEventsOperations(db)
        self.settings_service = settings_service
        self.image_service = image_service

    async def get_images_for_regeneration(
        self,
        limit: int = 1000,
        check_file_existence: bool = True,
        force_all: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get images that need thumbnail regeneration.

        Args:
            limit: Maximum number of images to process
            check_file_existence: Whether to verify files exist on disk before including them
            force_all: If True, get all images regardless of existing thumbnails (for regenerate all)

        Returns:
            List of image dictionaries with id, file_path, camera_id
        """
        try:
            if force_all:
                logger.info(
                    f"🔍 Getting ALL images for forced regeneration: limit={limit}, check_file_existence={check_file_existence}"
                )
                # Use the get_all_images_for_regeneration method from image_ops with file existence check
                images = await self.image_ops.get_all_images_for_regeneration(
                    limit, check_file_existence
                )
            else:
                logger.info(f"🔍 Getting images WITHOUT thumbnails: limit={limit}")
                # For normal regeneration, only get images missing thumbnails
                images_without_thumbnails = (
                    await self.image_ops.get_images_without_thumbnails(limit)
                )
                # Convert ImageWithDetails to dict format
                images = []
                for img in images_without_thumbnails:
                    images.append(
                        {
                            "id": img.id,
                            "file_path": img.file_path,
                            "camera_id": img.camera_id,
                        }
                    )

            logger.info(f"📊 Found {len(images)} images for regeneration")

            # Debug: log first few images if any
            if images and len(images) > 0:
                logger.debug(f"🔍 Sample images: {images[:3]}")

            return images
        except Exception as e:
            logger.error(
                f"❌ Error getting images for regeneration: {e}", exc_info=True
            )
            return []

    async def start_thumbnail_regeneration(self, limit: int = 1000) -> Dict[str, Any]:
        """
        Start bulk thumbnail regeneration process.

        Args:
            limit: Maximum number of images to process

        Returns:
            Dictionary with start status and message
        """
        try:
            logger.info(f"🚀 Starting thumbnail regeneration with limit={limit}")

            # Check if thumbnail generation is enabled
            generate_thumbnails = await self.settings_service.get_setting(
                "generate_thumbnails"
            )
            logger.info(f"📋 Thumbnail generation setting: {generate_thumbnails}")

            if not generate_thumbnails or str(generate_thumbnails).lower() != "true":
                logger.warning("❌ Thumbnail generation is disabled in settings")
                # Broadcast error event
                await self.sse_ops.create_event(
                    event_type="thumbnail_regeneration_error",
                    event_data={
                        "error": "Thumbnail generation is disabled in settings",
                        "reason": "settings_disabled",
                    },
                    priority="normal",
                    source="api",
                )
                return {
                    "success": False,
                    "message": "Thumbnail generation is disabled in settings",
                }

            # Get images to process (force regeneration of ALL images for "regenerate all" feature)
            logger.info("🔍 Getting images for regeneration...")
            images_to_process = await self.get_images_for_regeneration(
                limit, check_file_existence=False, force_all=True
            )
            logger.info(f"📊 Found {len(images_to_process)} images to process")

            if not images_to_process:
                logger.info("✨ No images need thumbnail regeneration")
                # Broadcast completion event for empty set
                await self.sse_ops.create_event(
                    event_type="thumbnail_regeneration_complete",
                    event_data={
                        "total_images": 0,
                        "completed_images": 0,
                        "failed_images": 0,
                        "message": "No images need thumbnail regeneration",
                    },
                    priority="normal",
                    source="api",
                )
                return {
                    "success": True,
                    "message": "No images need thumbnail regeneration",
                }

            # Check if regeneration is already active
            if ThumbnailService._regeneration_active:
                logger.warning("⚠️ Thumbnail regeneration is already in progress")
                return {
                    "success": False,
                    "message": "Thumbnail regeneration is already in progress",
                }

            # Set active state
            ThumbnailService._regeneration_active = True
            ThumbnailService._regeneration_progress = {
                "total_images": len(images_to_process),
                "completed_images": 0,
                "failed_images": 0,
                "current_image": None,
                "status_message": "starting",
            }

            # Broadcast start event
            await self.sse_ops.create_event(
                event_type="thumbnail_regeneration_started",
                event_data={
                    "total_images": len(images_to_process),
                    "limit": limit,
                    "status": "started",
                },
                priority="normal",
                source="api",
            )

            logger.info(
                f"✅ Started thumbnail regeneration for {len(images_to_process)} images"
            )

            # Start background processing task
            asyncio.create_task(self._process_thumbnail_regeneration(images_to_process))

            return {
                "success": True,
                "message": f"Thumbnail regeneration started for {len(images_to_process)} images",
            }

        except Exception as e:
            logger.error(
                f"❌ Error starting thumbnail regeneration: {e}", exc_info=True
            )

            # Broadcast error event
            await self.sse_ops.create_event(
                event_type="thumbnail_regeneration_error",
                event_data={"error": str(e), "reason": "startup_failed"},
                priority="high",
                source="api",
            )

            return {
                "success": False,
                "message": f"Failed to start regeneration: {str(e)}",
            }

    async def _process_thumbnail_regeneration(
        self, images_to_process: List[Dict[str, Any]]
    ) -> None:
        """
        Background task to process thumbnail regeneration.

        Args:
            images_to_process: List of image dictionaries to process
        """
        total_images = len(images_to_process)
        completed_images = 0
        failed_images = 0

        try:
            logger.info(f"Starting background processing of {total_images} images")
            ThumbnailService._regeneration_progress["status_message"] = "processing"

            for i, image_data in enumerate(images_to_process):
                # Check for cancellation
                if not ThumbnailService._regeneration_active:
                    logger.info(
                        f"Thumbnail regeneration cancelled after processing {completed_images} images"
                    )
                    break

                try:
                    image_id = image_data["id"]

                    # Update current processing state
                    ThumbnailService._regeneration_progress["current_image"] = image_id
                    ThumbnailService._regeneration_progress["status_message"] = (
                        f"processing image {i+1} of {total_images}"
                    )

                    # Generate thumbnails for this image using ImageService
                    result = await self.image_service.coordinate_thumbnail_generation(
                        image_id, force_regenerate=True
                    )

                    if result.success:
                        completed_images += 1
                        ThumbnailService._regeneration_progress["completed_images"] = (
                            completed_images
                        )
                        logger.debug(
                            f"Successfully generated thumbnails for image {image_id}"
                        )
                        status_message = "success"
                    else:
                        failed_images += 1
                        ThumbnailService._regeneration_progress["failed_images"] = (
                            failed_images
                        )
                        if "not found" in result.error.lower():
                            logger.debug(
                                f"Skipping image {image_id}: file not found on disk"
                            )
                            status_message = "file_not_found"
                        else:
                            logger.warning(
                                f"Failed to generate thumbnails for image {image_id}: {result.error}"
                            )
                            status_message = "error"

                    # Broadcast progress event
                    progress_percentage = int((i + 1) / total_images * 100)
                    await self.sse_ops.create_event(
                        event_type="thumbnail_regeneration_progress",
                        event_data={
                            "progress": progress_percentage,
                            "total": total_images,
                            "current_image": image_id,
                            "completed": completed_images,
                            "errors": failed_images,
                            "current_image_path": image_data.get("file_path", ""),
                            "status": "processing",
                            "current_status": status_message,
                            "message": f"Processing {i+1}/{total_images} - {completed_images} successful, {failed_images} failed",
                        },
                        priority="normal",
                        source="background_task",
                    )

                    # Small delay to prevent overwhelming the system
                    await asyncio.sleep(0.1)

                except Exception as e:
                    failed_images += 1
                    ThumbnailService._regeneration_progress["failed_images"] = (
                        failed_images
                    )
                    logger.error(
                        f"Error processing image {image_data.get('id', 'unknown')}: {e}"
                    )
                    continue

            # Update final state
            ThumbnailService._regeneration_progress["status_message"] = "completed"

            # Broadcast completion event
            await self.sse_ops.create_event(
                event_type="thumbnail_regeneration_complete",
                event_data={
                    "total_images": total_images,
                    "completed_images": completed_images,
                    "failed_images": failed_images,
                    "success_rate": (
                        (completed_images / total_images * 100)
                        if total_images > 0
                        else 0
                    ),
                    "message": f"Completed thumbnail regeneration: {completed_images} successful, {failed_images} failed",
                },
                priority="normal",
                source="background_task",
            )

            logger.info(
                f"Thumbnail regeneration completed: {completed_images}/{total_images} successful"
            )

        except Exception as e:
            logger.error(
                f"Critical error in thumbnail regeneration background task: {e}"
            )

            # Update error state
            ThumbnailService._regeneration_progress["status_message"] = "error"

            # Broadcast error event
            await self.sse_ops.create_event(
                event_type="thumbnail_regeneration_error",
                event_data={
                    "error": str(e),
                    "reason": "background_task_failed",
                    "completed_images": completed_images,
                    "failed_images": failed_images,
                    "total_images": total_images,
                },
                priority="high",
                source="background_task",
            )
        finally:
            # Always reset active state when done
            ThumbnailService._regeneration_active = False

    async def get_thumbnail_regeneration_status(self) -> ThumbnailRegenerationStatus:
        """
        Get current thumbnail regeneration status.

        Returns:
            ThumbnailRegenerationStatus with current progress
        """
        try:
            progress = ThumbnailService._regeneration_progress
            total = progress["total_images"]
            completed = progress["completed_images"]

            # Calculate progress percentage
            progress_percentage = int((completed / total * 100)) if total > 0 else 0

            return ThumbnailRegenerationStatus(
                active=ThumbnailService._regeneration_active,
                progress=progress_percentage,
                total_images=total,
                completed_images=completed,
                failed_images=progress["failed_images"],
                status_message=progress["status_message"],
            )
        except Exception as e:
            logger.error(f"Error getting thumbnail regeneration status: {e}")
            return ThumbnailRegenerationStatus(
                active=False,
                progress=0,
                total_images=0,
                completed_images=0,
                failed_images=0,
                status_message="error",
            )

    async def cancel_thumbnail_regeneration(self) -> Dict[str, Any]:
        """
        Cancel currently running thumbnail regeneration process.

        Returns:
            Dictionary with cancellation status
        """
        try:
            if not ThumbnailService._regeneration_active:
                await self.sse_ops.create_event(
                    event_type="thumbnail_regeneration_cancelled",
                    event_data={
                        "reason": "no_active_operation",
                        "message": "No active thumbnail regeneration to cancel",
                    },
                    priority="normal",
                    source="api",
                )
                return {
                    "success": False,
                    "message": "No active thumbnail regeneration to cancel",
                }

            # Reset the active state to signal cancellation
            ThumbnailService._regeneration_active = False
            ThumbnailService._regeneration_progress["status_message"] = "cancelled"

            # Broadcast cancellation event
            await self.sse_ops.create_event(
                event_type="thumbnail_regeneration_cancelled",
                event_data={
                    "reason": "user_requested",
                    "message": "Thumbnail regeneration cancelled by user",
                    "completed_images": ThumbnailService._regeneration_progress[
                        "completed_images"
                    ],
                    "total_images": ThumbnailService._regeneration_progress[
                        "total_images"
                    ],
                },
                priority="normal",
                source="api",
            )

            logger.info("Thumbnail regeneration cancelled by user")
            return {"success": True, "message": "Thumbnail regeneration cancelled"}

        except Exception as e:
            logger.error(f"Error cancelling thumbnail regeneration: {e}")
            return {
                "success": False,
                "message": f"Failed to cancel regeneration: {str(e)}",
            }

    async def get_thumbnail_statistics(self) -> ThumbnailStatistics:
        """
        Get comprehensive thumbnail statistics.

        Returns:
            ThumbnailStatistics with coverage and storage information
        """
        try:
            # Get thumbnail statistics from image operations
            stats_data = await self.image_ops.get_thumbnail_statistics()

            # Use database-aware timezone for last_updated timestamp
            current_time = await get_timezone_aware_timestamp_string_async(
                self.settings_service
            )

            return ThumbnailStatistics(**stats_data, last_updated=current_time)

        except Exception as e:
            logger.error(f"Error getting thumbnail statistics: {e}")
            # Return default statistics on error
            current_time = await get_timezone_aware_timestamp_string_async(
                self.settings_service
            )
            return ThumbnailStatistics(
                total_images=0,
                images_with_thumbnails=0,
                images_with_small=0,
                images_without_thumbnails=0,
                thumbnail_coverage_percentage=0.0,
                total_thumbnail_storage_mb=0.0,
                total_small_storage_mb=0.0,
                avg_thumbnail_size_kb=0.0,
                avg_small_size_kb=0.0,
                last_updated=current_time,
            )

    async def generate_thumbnail_for_image(
        self, image_id: int, force_regenerate: bool = False
    ) -> ThumbnailGenerationResult:
        """
        Generate thumbnails for a specific image.

        Args:
            image_id: ID of the image to generate thumbnails for
            force_regenerate: Whether to regenerate existing thumbnails

        Returns:
            ThumbnailGenerationResult with generation details
        """
        try:
            # Delegate to ImageService for actual thumbnail generation
            result = await self.image_service.coordinate_thumbnail_generation(
                image_id, force_regenerate
            )

            # Broadcast SSE event for single image generation
            if result.success:
                await self.sse_ops.create_event(
                    event_type="thumbnail_generated",
                    event_data={
                        "image_id": image_id,
                        "thumbnail_path": result.thumbnail_path,
                        "small_path": result.small_path,
                        "force_regenerate": force_regenerate,
                    },
                    priority="normal",
                    source="api",
                )

            return result

        except Exception as e:
            logger.error(f"Error generating thumbnail for image {image_id}: {e}")
            return ThumbnailGenerationResult(
                success=False,
                image_id=image_id,
                error=str(e),
            )

    async def delete_all_thumbnails(self) -> Dict[str, Any]:
        """
        Delete all thumbnail files from the filesystem and clear database references.

        Returns:
            Dictionary with deletion status and statistics
        """
        try:
            # Get data directory
            data_directory = await self.settings_service.get_setting("data_directory")

            deleted_files = 0
            deleted_size_mb = 0.0
            cameras_processed = 0
            errors = []

            import os
            import shutil
            from pathlib import Path

            # Get all cameras to process their thumbnail directories
            from ..database.camera_operations import CameraOperations

            camera_ops = CameraOperations(self.db)
            cameras = await camera_ops.get_cameras()

            # Broadcast start event
            await self.sse_ops.create_event(
                event_type="thumbnail_deletion_started",
                event_data={"total_cameras": len(cameras), "status": "started"},
                priority="normal",
                source="api",
            )

            logger.info(
                f"Starting deletion of all thumbnails for {len(cameras)} cameras"
            )

            for camera in cameras:
                try:
                    camera_id = camera.id
                    cameras_processed += 1

                    # Define thumbnail directories for this camera
                    thumbnail_dir = (
                        Path(data_directory) / f"cameras/camera-{camera_id}/thumbnails"
                    )
                    small_dir = (
                        Path(data_directory) / f"cameras/camera-{camera_id}/small"
                    )

                    # Delete thumbnail directory if it exists
                    if thumbnail_dir.exists():
                        # Calculate size before deletion
                        for file_path in thumbnail_dir.rglob("*"):
                            if file_path.is_file():
                                deleted_size_mb += file_path.stat().st_size / (
                                    1024 * 1024
                                )
                                deleted_files += 1

                        shutil.rmtree(thumbnail_dir)
                        logger.debug(f"Deleted thumbnail directory: {thumbnail_dir}")

                    # Delete small directory if it exists
                    if small_dir.exists():
                        # Calculate size before deletion
                        for file_path in small_dir.rglob("*"):
                            if file_path.is_file():
                                deleted_size_mb += file_path.stat().st_size / (
                                    1024 * 1024
                                )
                                deleted_files += 1

                        shutil.rmtree(small_dir)
                        logger.debug(f"Deleted small directory: {small_dir}")

                    # Broadcast progress event
                    await self.sse_ops.create_event(
                        event_type="thumbnail_deletion_progress",
                        event_data={
                            "cameras_processed": cameras_processed,
                            "total_cameras": len(cameras),
                            "current_camera_id": camera_id,
                            "deleted_files": deleted_files,
                            "deleted_size_mb": round(deleted_size_mb, 2),
                            "status": "processing",
                        },
                        priority="normal",
                        source="background_task",
                    )

                except Exception as e:
                    error_msg = (
                        f"Error deleting thumbnails for camera {camera_id}: {str(e)}"
                    )
                    errors.append(error_msg)
                    logger.error(error_msg)
                    continue

            # Clear thumbnail paths from database
            try:
                cleared_count = await self.image_ops.clear_all_thumbnail_paths()
                logger.info(
                    f"Cleared thumbnail paths from {cleared_count} image records"
                )
            except Exception as e:
                error_msg = f"Error clearing thumbnail paths from database: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                cleared_count = 0

            # Broadcast completion event
            await self.sse_ops.create_event(
                event_type="thumbnail_deletion_complete",
                event_data={
                    "cameras_processed": cameras_processed,
                    "deleted_files": deleted_files,
                    "deleted_size_mb": round(deleted_size_mb, 2),
                    "cleared_database_records": cleared_count,
                    "errors": len(errors),
                    "message": f"Deleted {deleted_files} thumbnail files ({deleted_size_mb:.1f} MB) from {cameras_processed} cameras",
                },
                priority="normal",
                source="background_task",
            )

            logger.info(
                f"Thumbnail deletion completed: {deleted_files} files deleted ({deleted_size_mb:.1f} MB), {cleared_count} database records cleared"
            )

            return {
                "success": True,
                "message": f"Successfully deleted {deleted_files} thumbnail files",
                "deleted_files": deleted_files,
                "deleted_size_mb": round(deleted_size_mb, 2),
                "cameras_processed": cameras_processed,
                "cleared_database_records": cleared_count,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Critical error in delete all thumbnails: {e}")

            # Broadcast error event
            await self.sse_ops.create_event(
                event_type="thumbnail_deletion_error",
                event_data={"error": str(e), "reason": "deletion_failed"},
                priority="high",
                source="background_task",
            )

            return {
                "success": False,
                "message": f"Failed to delete thumbnails: {str(e)}",
                "error": str(e),
            }
