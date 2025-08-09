"""
Image Service - Composition-based architecture.

This service handles image-related business logic using dependency injection
for database operations, providing type-safe Pydantic model interfaces.
"""

# Standard library imports

import io
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from ..config import settings

# Local imports
from ..constants import (
    DEFAULT_CAMERA_IMAGES_LIMIT,
    DEFAULT_PAGE_SIZE,
    DEFAULT_TIMELAPSE_IMAGES_LIMIT,
    IMAGE_SIZE_VARIANTS,
    MAX_BULK_OPERATION_ITEMS,
)
from ..database.core import SyncDatabase
from ..enums import LoggerName, LogSource, SSEEvent, SSEEventSource, SSEPriority
from ..exceptions import (
    ImageNotFoundError,
    InvalidImageSizeError,
)
from ..models.health_model import HealthStatus
from ..models.image_model import Image
from ..models.shared_models import (  # ThumbnailOperationResponse,; ThumbnailRegenerationStatus,; NOTE: ThumbnailGenerationResult removed - thumbnail generation handled by ThumbnailPipeline
    PaginatedImagesResponse,
)

# NOTE: thumbnail_utils removed - thumbnail generation handled by ThumbnailPipeline
from ..utils.cache_manager import cached_response
from ..utils.conversion_utils import sanitize_error_message
from ..utils.file_helpers import (
    clean_filename,
    prepare_image_metadata_for_serving,
    serve_image_with_metadata,
    validate_file_path,
)
from ..utils.router_helpers import validate_entity_exists
from ..utils.time_utils import (
    format_date_string,
    format_filename_timestamp,
    get_timezone_aware_timestamp_async,
    get_timezone_aware_timestamp_string_async,
)
from .logger import get_service_logger

logger = get_service_logger(LoggerName.IMAGE_SERVICE, LogSource.SYSTEM)


class ImageService:
    """
    Image metadata and serving business logic.

    Responsibilities:
    - Image metadata management (CRUD operations)
    - File serving with fallbacks
    - Image statistics calculations

    Interactions:
    - Uses ImageOperations for database operations
    - Serves image files with cascading fallbacks (full -> small -> thumbnail)
    - Coordinates with corruption pipeline for quality data

    Note: Thumbnail generation is handled by ThumbnailPipeline, not ImageService
    """

    def __init__(
        self,
        db,
        settings_service,
        image_ops,
        sse_ops,
        # corruption_service: Optional[CorruptionService] = None,  # Removed
        health_service=None,
    ):
        """
        Initialize ImageService with injected dependencies.

        Args:
            db: AsyncDatabase instance
            settings_service: SettingsService instance for configuration management
            image_ops: Injected ImageOperations singleton
            sse_ops: Injected SSEEventsOperations singleton
            # corruption_service: Optional CorruptionService for quality data coordination (removed)
            health_service: Optional HealthService for health monitoring
        """
        self.db = db
        self.image_ops = image_ops
        self.async_image_ops = image_ops  # Use the same instance for consistency
        self.sse_ops = sse_ops
        self.settings_service = settings_service
        # self.corruption_service = corruption_service  # Removed
        self.health_service = health_service

    def _get_data_directory(self) -> str:
        """Get data directory from config."""
        return settings.data_directory

    async def _get_validated_image(self, image_id: int) -> Image:
        """Get image and validate it exists."""
        return await validate_entity_exists(self.get_image_by_id, image_id, "image")

    async def _check_database_health(
        self, operation_name: str = "database operation"
    ) -> None:
        """
        Check database health and log warnings if unhealthy.

        Args:
            operation_name: Name of the operation for logging context
        """
        if not self.health_service:
            return

        try:
            db_health = await self.health_service.get_database_health()
            if db_health.status == HealthStatus.UNHEALTHY:
                logger.warning(f"Database health is unhealthy during {operation_name}")
            elif db_health.status == HealthStatus.DEGRADED:
                logger.warning(f"Database health is degraded during {operation_name}")
        except Exception as e:
            logger.warning(f"Health check failed during {operation_name}: {e}")

    async def get_images(
        self,
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        order_by: str = "captured_at",
        order_dir: str = "DESC",
    ) -> PaginatedImagesResponse:
        """
        Retrieve images with pagination and filtering.

        Args:
            timelapse_id: Optional timelapse ID to filter by
            camera_id: Optional camera ID to filter by
            page: Page number (1-based)
            page_size: Number of images per page
            order_by: Column to order by
            order_dir: Order direction (ASC/DESC)

        Returns:
            Dictionary containing images list (Image models) and pagination metadata
        """
        # Light health monitoring for read operations (no performance impact)
        if self.health_service:
            await self._check_database_health("get_images")

        # Calculate offset from page
        offset = (page - 1) * page_size

        # Get images with database-level filtering and computed fields populated
        images = await self.image_ops.get_images(
            limit=page_size,
            offset=offset,
            order_by=order_by,
            order_dir=order_dir,
            timelapse_id=timelapse_id,
            camera_id=camera_id,
        )

        # Get accurate total count for pagination
        total_count = await self.image_ops.get_images_count(
            timelapse_id=timelapse_id, camera_id=camera_id
        )

        # Calculate pagination metadata
        total_pages = (total_count + page_size - 1) // page_size

        return PaginatedImagesResponse(
            images=images,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

    async def get_images_for_camera(
        self, camera_id: int, limit: int = DEFAULT_CAMERA_IMAGES_LIMIT
    ) -> List[Image]:
        """
        Get recent images for a specific camera.

        Args:
            camera_id: ID of the camera
            limit: Maximum number of images to return

        Returns:
            List of Image model instances
        """
        # Use the camera-specific method from ImageOperations
        images = await self.image_ops.get_images_by_camera(camera_id)

        # Limit the results and return
        return images[:limit]

    async def get_image_by_id(self, image_id: int) -> Optional[Image]:
        """
        Retrieve a specific image by ID.

        Args:
            image_id: ID of the image to retrieve

        Returns:
            Image model instance, or None if not found
        """
        image = await self.image_ops.get_image_by_id(image_id)
        if image is None:
            return None

        return image

    @cached_response(ttl_seconds=30, key_prefix="latest_image")
    async def get_latest_image_for_camera(self, camera_id: int) -> Optional[Image]:
        """
        Get the latest image for a specific camera.

        CACHED: Results cached for 30 seconds to prevent API flooding.

        Args:
            camera_id: ID of the camera

        Returns:
            Latest Image model instance, or None if no images found
        """
        logger.debug(f"🔍 Fetching latest image for camera {camera_id}")

        image = await self.image_ops.get_latest_image_for_camera(camera_id)
        if image is None:
            return None

        return image

    async def get_latest_image_for_timelapse(
        self, timelapse_id: int
    ) -> Optional[Image]:
        """
        Get the latest image for a specific timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Latest Image model instance, or None if no images found
        """
        # Get images for timelapse and return the latest one
        images = await self.image_ops.get_images_by_timelapse(timelapse_id)
        if not images:
            return None

        # Get the latest image (images are ordered by captured_at ASC, so take the last one)
        latest_image = images[-1]

        return latest_image

    async def get_images_by_day_range(
        self, timelapse_id: int, start_day: int, end_day: int
    ) -> List[Image]:
        """
        Get images for a timelapse within a specific day range.

        Args:
            timelapse_id: ID of the timelapse
            start_day: Starting day number (inclusive)
            end_day: Ending day number (inclusive)

        Returns:
            List of Image models
        """
        # Get all images for the timelapse and filter by day number
        images = await self.image_ops.get_images_by_timelapse(timelapse_id)

        # Filter by day range
        filtered_images = [
            img for img in images if start_day <= img.day_number <= end_day
        ]

        return filtered_images

    async def get_images_by_date_range(
        self, timelapse_id: int, start_date: date, end_date: date
    ) -> List[Image]:
        """
        Get images for a timelapse within a specific date range.

        Args:
            timelapse_id: ID of the timelapse
            start_date: Starting date (inclusive)
            end_date: Ending date (inclusive)

        Returns:
            List of Image models
        """
        # Convert dates to datetime for the database query

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        start_str = format_date_string(start_dt)
        end_str = format_date_string(end_dt)

        # Use the date range method from ImageOperations
        images = await self.image_ops.get_images_by_date_range(start_str, end_str)

        # Filter by timelapse_id
        filtered_images = [img for img in images if img.timelapse_id == timelapse_id]

        return filtered_images

    async def delete_image(self, image_id: int) -> bool:
        """
        Delete a specific image.

        Args:
            image_id: ID of the image to delete

        Returns:
            True if image was deleted successfully
        """
        # Get image info before deletion for SSE event and audit trail
        image_to_delete = await self.get_image_by_id(image_id)
        logger.debug(
            f"Attempting to delete image {image_id} (camera: {image_to_delete.camera_id if image_to_delete else 'N/A'})"
        )
        # Audit trail for sensitive delete operation
        # if self.log_service and image_to_delete:
        #     await self.log_service.maintain_audit_trail(
        #         action="delete",
        #         entity_type="image",
        #         entity_id=image_id,
        #         changes={
        #             "image_metadata": {
        #                 "camera_id": image_to_delete.camera_id,
        #                 "timelapse_id": image_to_delete.timelapse_id,
        #                 "file_path": image_to_delete.file_path,
        #                 "captured_at": (
        #                     image_to_delete.captured_at.isoformat()
        #                     if image_to_delete and image_to_delete.captured_at
        #                     else None
        #                 ),
        #             }
        #         },
        #     )

        success = await self.image_ops.delete_image(image_id)

        # Create SSE event for real-time updates
        if success and image_to_delete:
            logger.info(f"Image {image_id} deleted successfully")
            await self.sse_ops.create_event(
                event_type=SSEEvent.IMAGE_DELETED,
                event_data={
                    "image_id": image_id,
                    "camera_id": image_to_delete.camera_id,
                    "timelapse_id": image_to_delete.timelapse_id,
                    "filename": image_to_delete.file_path,
                },
                priority=SSEPriority.NORMAL,
                source=SSEEventSource.API,
            )

        return success

    async def delete_images_by_timelapse(self, timelapse_id: int) -> int:
        """
        Delete all images for a specific timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Number of images deleted
        """
        return await self.image_ops.delete_images_by_timelapse(timelapse_id)

    async def record_captured_image(self, image_data: Dict[str, Any]) -> Image:
        """
        Record a newly captured image.

        Args:
            image_data: Dictionary containing image metadata

        Returns:
            Created Image model instance
        """
        image_record = await self.image_ops.record_captured_image(image_data)

        # Audit trail for image creation
        # if self.log_service:
        #     await self.log_service.maintain_audit_trail(
        #         action="create",
        #         entity_type="image",
        #         entity_id=image_record.id,
        #         changes={
        #             "image_metadata": {
        #                 "camera_id": image_record.camera_id,
        #                 "timelapse_id": image_record.timelapse_id,
        #                 "file_path": image_record.file_path,
        #                 "captured_at": image_record.captured_at.isoformat(),
        #                 "file_size": image_data.get("file_size"),
        #                 "day_number": image_record.day_number,
        #             }
        #         },
        #         user_id="system",
        #     )

        # NOTE: SSE event for IMAGE_CAPTURED is handled by workflow_orchestrator_service.py
        # to avoid duplicate events. The orchestrator has full context (timelapse info, job results)
        # and is the authoritative source for capture completion events.

        return image_record

    async def get_image_count_by_timelapse(self, timelapse_id: int) -> int:
        """
        Get the total count of images for a timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Total image count
        """
        return await self.image_ops.get_image_count_by_timelapse(timelapse_id)

    async def get_images_for_timelapse(self, timelapse_id: int) -> List[Image]:
        """
        Get all images for a specific timelapse (helper method).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            List of Image model instances
        """
        # Use the timelapse-specific method from ImageOperations
        images = await self.image_ops.get_images_by_timelapse(timelapse_id)

        # Limit the results
        limited_images = images[:DEFAULT_TIMELAPSE_IMAGES_LIMIT]

        return limited_images

    async def get_images_batch(
        self, image_ids: List[int], size: str = "thumbnail"
    ) -> List[Image]:
        """
        Get multiple images by their IDs for batch loading.

        Args:
            image_ids: List of image IDs to retrieve
            size: Size variant ('thumbnail', 'small', 'original')

        Returns:
            List of Image model instances with proper type safety
        """
        try:
            images = []
            for image_id in image_ids:
                try:
                    # Get image metadata using existing method that returns Image
                    image_data = await self.get_image_by_id(image_id)
                    if not image_data:
                        logger.warning(f"Image {image_id} not found for batch loading")
                        continue

                    # The image_data is already an Image Pydantic model
                    # No need to convert to dict - just append the model directly
                    images.append(image_data)

                except Exception as e:
                    logger.error(
                        f"Error processing image {image_id} in batch: {e}", exception=e
                    )
                    continue

            logger.info(
                f"Batch loaded {len(images)} images out of {len(image_ids)} requested (size: {size})"
            )

            # SSE broadcasting handled by higher-level service layer

            return images

        except Exception as e:
            logger.error(f"Batch image loading failed: {e}")
            return []

    async def calculate_image_statistics(
        self, timelapse_id: Optional[int] = None, camera_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive image statistics.

        Args:
            timelapse_id: Optional timelapse ID to filter by
            camera_id: Optional camera ID to filter by

        Returns:
            Comprehensive image statistics including quality metrics
        """
        try:
            # Health monitoring for intensive database operation
            await self._check_database_health("statistics calculation")

            # Get basic image statistics from database using the new method
            basic_stats = await self.async_image_ops.get_image_statistics(
                camera_id=camera_id, timelapse_id=timelapse_id
            )

            # Quality statistics will be provided by corruption pipeline when needed
            quality_stats = None

            # Combine statistics

            calculation_timestamp = await get_timezone_aware_timestamp_string_async(
                self.settings_service
            )
            comprehensive_stats = {
                "basic_statistics": basic_stats,
                "quality_statistics": quality_stats,
                "calculation_timestamp": calculation_timestamp,
            }

            # Calculate additional derived metrics
            if basic_stats and quality_stats:
                total_images = basic_stats.get("total_images", 0)
                flagged_images = quality_stats.get("flagged_images", 0)

                comprehensive_stats["derived_metrics"] = {
                    "quality_ratio": (1 - (flagged_images / max(total_images, 1)))
                    * 100,
                    "corruption_rate": (flagged_images / max(total_images, 1)) * 100,
                    "data_health_score": max(
                        0, min(100, 100 - (flagged_images / max(total_images, 1)) * 100)
                    ),
                }

            return comprehensive_stats

        except Exception as e:
            logger.error("Image statistics calculation failed", exception=e)
            return {
                "basic_statistics": None,
                "quality_statistics": None,
                "calculation_timestamp": None,
                "error": sanitize_error_message(e, "statistics calculation"),
            }

    # coordinate_quality_assessment method removed - use corruption_pipeline directly

    async def serve_image_file(self, image_id: int, size_variant: str = "full"):
        """
        Serve an image file with proper cascading fallbacks.

        Args:
            image_id: ID of the image to serve
            size_variant: Size variant ('full', 'thumbnail', 'small')

        Returns:
            FastAPI Response for file serving
        """
        # Validate size_variant parameter
        if size_variant not in IMAGE_SIZE_VARIANTS:
            raise InvalidImageSizeError(
                f"Invalid size variant. Must be one of: {', '.join(IMAGE_SIZE_VARIANTS)}"
            )

        try:
            # Get image data and prepare for serving
            result = await self.prepare_image_for_serving(image_id, size_variant)

            if not result["success"]:
                raise ImageNotFoundError(result.get("error", "Image not found"))

            file_path = result["file_path"]
            media_type = result.get("media_type", "image/jpeg")
            image_data = result["image_data"]

            if file_path is None:
                raise ImageNotFoundError("Image file not found")

            # Convert Pydantic model to dict for file_helpers
            image_dict = None
            if hasattr(image_data, "__dict__"):
                image_dict = {
                    "id": image_data.id,
                    "captured_at": image_data.captured_at,
                }
            elif isinstance(image_data, dict):
                image_dict = image_data

            # Use file_helpers for serving
            return serve_image_with_metadata(
                file_path=file_path,
                media_type=media_type,
                image_data=image_dict,
                image_id=image_id,
            )

        except (ImageNotFoundError, InvalidImageSizeError):
            raise
        except Exception as e:
            logger.error(
                f"Failed to serve image {image_id} (size: {size_variant})", exception=e
            )
            # raise ImageServiceError("Failed to serve image file")

    async def prepare_image_for_serving(
        self, image_id: int, size: str = "full"
    ) -> Dict[str, Any]:
        """
        Prepare image for serving with proper file path resolution and validation.

        Args:
            image_id: ID of the image to serve
            size: Requested size (full, small, thumbnail)

        Returns:
            Dictionary with file path and metadata for serving
        """
        try:
            # Get image data
            image_data = await self._get_validated_image(image_id)
            data_directory = self._get_data_directory()

            # Convert Pydantic model to dict for file_helpers compatibility
            image_dict = {
                "id": image_data.id,
                "file_path": image_data.file_path,
                "thumbnail_path": image_data.thumbnail_path,
                "small_path": image_data.small_path,
                "captured_at": image_data.captured_at,
            }

            # Use file_helpers function for preparation
            result = prepare_image_metadata_for_serving(
                image_data=image_dict, data_directory=data_directory, size=size
            )

            # Add the original image_data for ETag generation
            if result["success"]:
                result["image_data"] = image_data

            return result

        except Exception as e:
            logger.error(f"Failed to prepare image {image_id} for serving", exception=e)
            return {
                "success": False,
                "file_path": None,
                "media_type": None,
                "image_data": None,
                "error": sanitize_error_message(e, "image preparation"),
            }

    async def prepare_bulk_download(
        self, image_ids: List[int], zip_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare bulk download by creating ZIP file with requested images.

        Args:
            image_ids: List of image IDs to include
            zip_filename: Optional custom filename

        Returns:
            Dictionary with ZIP file data and metadata
        """
        try:
            data_directory = self._get_data_directory()

            if not image_ids:
                logger.warning("No image IDs provided")
                # Return an empty ZIP file and metadata if no IDs provided
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED):
                    pass
                zip_buffer.seek(0)
                timestamp_dt = await get_timezone_aware_timestamp_async(
                    self.settings_service
                )
                timestamp = format_filename_timestamp(timestamp_dt)
                filename = zip_filename or f"timelapser_images_{timestamp}.zip"
                filename = clean_filename(filename)
                return {
                    "zip_data": zip_buffer.getvalue(),
                    "filename": filename,
                    "requested_images": 0,
                    "included_images": 0,
                    "total_size": 0,
                }

            # Create ZIP file in memory
            zip_buffer = io.BytesIO()
            added_files = 0
            total_size = 0

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for image_id in image_ids:
                    try:
                        image_data = await self.get_image_by_id(image_id)
                        if not image_data:
                            logger.warning(
                                f"Image {image_id} not found for bulk download"
                            )
                            continue

                        # Use file_helpers to get secure file path with proper camera directory structure
                        file_path = validate_file_path(
                            f"cameras/camera-{image_data.camera_id}/images/{image_data.file_path}",
                            base_directory=data_directory,
                            must_exist=True,
                        )

                        # Create clean filename for ZIP
                        original_name = Path(image_data.file_path).name
                        clean_name = clean_filename(f"image_{image_id}_{original_name}")

                        # Add file to ZIP
                        zip_file.write(str(file_path), clean_name)
                        added_files += 1
                        total_size += file_path.stat().st_size

                    except Exception as e:
                        logger.warning(f"Failed to add image {image_id} to ZIP: {e}")
                        continue

            if added_files == 0:
                logger.warning(
                    "No valid images found for download - returning empty ZIP"
                )
            zip_buffer.seek(0)

            # Generate filename with timezone-aware timestamp
            timestamp_dt = await get_timezone_aware_timestamp_async(
                self.settings_service
            )
            timestamp = format_filename_timestamp(timestamp_dt)
            filename = zip_filename or f"timelapser_images_{timestamp}.zip"
            filename = clean_filename(filename)

            result = {
                "zip_data": zip_buffer.getvalue(),
                "filename": filename,
                "requested_images": len(image_ids),
                "included_images": added_files,
                "total_size": total_size,
            }

            # SSE broadcasting handled by higher-level service layer

            return result

        except Exception as e:
            logger.error(f"Bulk download preparation failed: {e}", exception=e)
            # Always return a dict even on error
            return {
                "zip_data": b"",
                "filename": "error.zip",
                "requested_images": len(image_ids) if image_ids else 0,
                "included_images": 0,
                "total_size": 0,
                "error": sanitize_error_message(e, "bulk download"),
            }

    async def serve_images_batch(self, image_ids: List[int], size: str = "thumbnail"):
        """
        Batch image serving for multiple images.

        Args:
            image_ids: List of image IDs
            size: Size variant for all images

        Returns:
            JSON with image URLs and metadata
        """
        try:
            # Get images metadata
            results = []

            for image_id in image_ids:
                try:
                    image = await self.get_image_by_id(image_id)
                    if image:
                        # Build URL based on size
                        url = f"/api/images/{image_id}/serve?size={size}"

                        results.append(
                            {
                                "image_id": image_id,
                                "url": url,
                                "camera_id": image.camera_id,
                                "captured_at": (
                                    image.captured_at.isoformat()
                                    if image.captured_at
                                    else None
                                ),
                                "available": True,
                            }
                        )
                    else:
                        results.append(
                            {
                                "image_id": image_id,
                                "url": None,
                                "available": False,
                                "error": "Image not found",
                            }
                        )

                except Exception as e:
                    results.append(
                        {
                            "image_id": image_id,
                            "url": None,
                            "available": False,
                            "error": sanitize_error_message(
                                e, "latest image retrieval"
                            ),
                        }
                    )

            return {
                "images": results,
                "size": size,
                "total_requested": len(image_ids),
                "total_available": len([r for r in results if r["available"]]),
            }

        except Exception as e:
            logger.error(f"Error in batch image serving: {e}")
            raise

    async def serve_images_batch_from_string(
        self, ids_string: str, size: str = "thumbnail"
    ):
        """
        Batch image serving from comma-separated string of image IDs.

        Handles parsing, validation, and batch size limits before delegating
        to serve_images_batch().

        Args:
            ids_string: Comma-separated string of image IDs
            size: Size variant for all images

        Returns:
            JSON with image URLs and metadata

        Raises:
            ValueError: If image IDs format is invalid
            HTTPException: If batch size exceeds limits
        """

        try:
            # Parse comma-separated string to List[int]
            image_ids = [int(id_str.strip()) for id_str in ids_string.split(",")]

            # Validate batch size
            if len(image_ids) > MAX_BULK_OPERATION_ITEMS:
                raise HTTPException(
                    status_code=413,
                    detail=f"Batch size too large (max {MAX_BULK_OPERATION_ITEMS} images)",
                )

            # Delegate to existing batch method
            return await self.serve_images_batch(image_ids, size)

        except ValueError as e:
            raise ValueError(
                "Invalid image IDs format - must be comma-separated integers"
            ) from e

    async def get_status(self) -> Dict[str, Any]:
        """
        Get service status information following standardized pattern.

        Returns:
            Dict containing service health and operational status
        """
        try:
            # Basic service health
            status_info = {
                "service_name": "image_service",
                "status": "healthy",
                "database_connected": self.db is not None,
                "health_service_available": self.health_service is not None,
            }

            # Database operations status
            try:
                # Test basic database connectivity with a simple operation
                await self.image_ops.get_images_count()
                status_info["database_operations"] = "healthy"
            except Exception as e:
                status_info["database_operations"] = "error"
                status_info["database_error"] = str(e)
                status_info["status"] = "degraded"

            # Service capabilities
            status_info["capabilities"] = {
                "image_crud": True,
                "image_serving": True,
                "batch_operations": True,
                "statistics_calculation": True,
                "bulk_download": True,
                "sse_events": self.sse_ops is not None,
                "health_monitoring": self.health_service is not None,
                "corruption_detection": False,  # Handled by corruption pipeline
            }

            # Operational metrics
            try:
                total_images = await self.image_ops.get_images_count()
                status_info["metrics"] = {
                    "total_images": total_images,
                    "cache_enabled": True,  # Using @cached_response decorator
                }
            except Exception:
                status_info["metrics"] = {"total_images": "unavailable"}

            return status_info

        except Exception as e:
            logger.error("Failed to get image service status", exception=e)
            return {
                "service_name": "image_service",
                "status": "error",
                "error": str(e),
                "database_connected": False,
            }


class SyncImageService:
    """
    Sync image service for worker processes using composition pattern.

    This service orchestrates image-related business logic using
    dependency injection instead of mixin inheritance.
    """

    def __init__(self, db: SyncDatabase, image_ops):
        """
        Initialize SyncImageService with injected dependencies.

        Args:
            db: SyncDatabase instance
            image_ops: Injected SyncImageOperations singleton
        """
        self.db = db
        self.image_ops = image_ops

    def record_captured_image(self, image_data: Dict[str, Any]) -> Image:
        """
        Record a newly captured image (sync version for worker).

        Args:
            image_data: Dictionary containing image metadata

        Returns:
            Created Image model instance
        """
        image_record = self.image_ops.record_captured_image(image_data)

        # Sync audit trail for image creation (if log service available)
        # if self.log_service:
        #     self.log_service.write_log_entry(
        #         level="INFO",
        #         message=f"Image captured and recorded: {image_record.file_path}",
        #         logger_name="sync_image_service",
        #         source="worker",
        #         camera_id=image_record.camera_id,
        #         extra_data={
        #             "action": "create",
        #             "entity_type": "image",
        #             "entity_id": image_record.id,
        #             "image_metadata": {
        #                 "camera_id": image_record.camera_id,
        #                 "timelapse_id": image_record.timelapse_id,
        #                 "file_path": image_record.file_path,
        #                 "file_size": image_data.get("file_size"),
        #                 "day_number": image_record.day_number,
        #             },
        #         },
        #     )

        return image_record

    def get_image_count_by_timelapse(self, timelapse_id: int) -> int:
        """
        Get the total count of images for a timelapse (sync version).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Total image count
        """
        return self.image_ops.get_image_count_by_timelapse(timelapse_id)

    def cleanup_old_images(self, days_to_keep: int = 30) -> int:
        """
        Clean up old images based on retention policy.

        Args:
            days_to_keep: Number of days to keep images (default: 30)

        Returns:
            Number of images deleted
        """
        return self.image_ops.cleanup_old_images(days_to_keep)

    def get_image_by_id(self, image_id: int) -> Optional[Image]:
        """
        Retrieve a specific image by ID (sync version).

        Args:
            image_id: ID of the image to retrieve

        Returns:
            Image model instance, or None if not found
        """
        return self.image_ops.get_image_by_id(image_id)

    def get_images_for_camera(
        self, camera_id: int, limit: int = DEFAULT_CAMERA_IMAGES_LIMIT
    ) -> List[Image]:
        """
        Get recent images for a specific camera (sync version).

        Args:
            camera_id: ID of the camera
            limit: Maximum number of images to return

        Returns:
            List of Image model instances
        """
        images = self.image_ops.get_images_by_camera(camera_id)
        return images[:limit]

    def update_image_overlay_status(
        self,
        image_id: int,
        overlay_path: str,
        has_valid_overlay: bool,
        overlay_updated_at,
    ) -> bool:
        """
        Update overlay status and path for an image.

        Args:
            image_id: ID of the image to update
            overlay_path: Path to the overlay image file
            has_valid_overlay: Whether the overlay was successfully generated
            overlay_updated_at: Timestamp when overlay was generated

        Returns:
            True if update was successful
        """
        return self.image_ops.update_image_overlay_status(
            image_id=image_id,
            overlay_path=overlay_path,
            has_valid_overlay=has_valid_overlay,
            overlay_updated_at=overlay_updated_at,
        )

    def get_status(self) -> Dict[str, Any]:
        """
        Get service status information following standardized pattern (sync version).

        Returns:
            Dict containing service health and operational status
        """
        try:
            # Basic service health
            status_info = {
                "service_name": "sync_image_service",
                "status": "healthy",
                "database_connected": self.db is not None,
                "version": "sync",
            }

            # Database operations status
            try:
                # Test basic database connectivity with a simple operation
                total_images = self.image_ops.get_images_count()
                status_info["database_operations"] = "healthy"
                status_info["metrics"] = {"total_images": total_images}
            except Exception as e:
                status_info["database_operations"] = "error"
                status_info["database_error"] = str(e)
                status_info["status"] = "degraded"
                status_info["metrics"] = {"total_images": "unavailable"}

            # Service capabilities
            status_info["capabilities"] = {
                "image_crud": True,
                "sync_operations": True,
                "worker_compatible": True,
            }

            return status_info

        except Exception as e:
            logger.error("Failed to get sync image service status", exception=e)
            return {
                "service_name": "sync_image_service",
                "status": "error",
                "error": str(e),
                "database_connected": False,
            }
