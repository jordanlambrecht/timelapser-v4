"""
Image Service - Composition-based architecture.

This service handles image-related business logic using dependency injection
for database operations, providing type-safe Pydantic model interfaces.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from loguru import logger

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.image_operations import ImageOperations, SyncImageOperations
from ..database.sse_events_operations import SSEEventsOperations
from ..models.image_model import (
    Image,
    ImageWithDetails,
)
from ..models.shared_models import (
    ImageStatisticsResponse,
    BulkDownloadResponse,
)
from ..models.shared_models import (
    ThumbnailGenerationResult,
    ThumbnailRegenerationResponse,
)
from ..utils.cache_manager import cached_response
from ..utils.timezone_utils import get_timezone_aware_timestamp_string_async
from ..constants import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    DEFAULT_CAMERA_IMAGES_LIMIT,
    DEFAULT_TIMELAPSE_IMAGES_LIMIT,
    EVENT_IMAGE_CAPTURED,
    EVENT_IMAGE_PROCESSED,
)


class ImageService:
    """
    Image metadata and serving business logic.

    Responsibilities:
    - Image metadata management
    - Thumbnail coordination
    - File serving with fallbacks
    - Image statistics calculations

    Interactions:
    - Uses ImageOperations for database
    - Calls thumbnail_utils for processing
    - Coordinates with CorruptionService for quality data
    """

    def __init__(self, db: AsyncDatabase, settings_service, corruption_service=None):
        """
        Initialize ImageService with async database instance and service dependencies.

        Args:
            db: AsyncDatabase instance
            settings_service: SettingsService for configuration management
            corruption_service: Optional CorruptionService for quality data coordination
        """
        self.db = db
        self.image_ops = ImageOperations(db)
        self.sse_ops = SSEEventsOperations(db)
        self.settings_service = settings_service
        self.corruption_service = corruption_service

    async def get_images(
        self,
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        order_by: str = "captured_at",
        order_dir: str = "DESC",
    ) -> Dict[str, Any]:
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
            Dictionary containing images list (ImageWithDetails models) and pagination metadata
        """
        return await self.image_ops.get_images(
            timelapse_id, camera_id, page, page_size, order_by, order_dir
        )

    async def get_images_for_camera(
        self, camera_id: int, limit: int = DEFAULT_CAMERA_IMAGES_LIMIT
    ) -> List[ImageWithDetails]:
        """
        Get recent images for a specific camera.

        Args:
            camera_id: ID of the camera
            limit: Maximum number of images to return

        Returns:
            List of ImageWithDetails model instances
        """
        result = await self.image_ops.get_images(
            camera_id=camera_id,
            page=1,
            page_size=limit,
            order_by="captured_at",
            order_dir="DESC",
        )
        return result["images"]

    async def get_image_by_id(self, image_id: int) -> Optional[ImageWithDetails]:
        """
        Retrieve a specific image by ID.

        Args:
            image_id: ID of the image to retrieve

        Returns:
            ImageWithDetails model instance, or None if not found
        """
        return await self.image_ops.get_image_by_id(image_id)

    @cached_response(ttl_seconds=30, key_prefix="latest_image")
    async def get_latest_image_for_camera(
        self, camera_id: int
    ) -> Optional[ImageWithDetails]:
        """
        Get the latest image for a specific camera.

        CACHED: Results cached for 30 seconds to prevent API flooding.

        Args:
            camera_id: ID of the camera

        Returns:
            Latest ImageWithDetails model instance, or None if no images found
        """
        logger.debug(f"🔍 Fetching latest image for camera {camera_id}")
        return await self.image_ops.get_latest_image_for_camera(camera_id)

    async def get_latest_image_for_timelapse(
        self, timelapse_id: int
    ) -> Optional[ImageWithDetails]:
        """
        Get the latest image for a specific timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Latest ImageWithDetails model instance, or None if no images found
        """
        return await self.image_ops.get_latest_image_for_timelapse(timelapse_id)

    async def get_images_by_day_range(
        self, timelapse_id: int, start_day: int, end_day: int
    ) -> List[ImageWithDetails]:
        """
        Get images for a timelapse within a specific day range.

        Args:
            timelapse_id: ID of the timelapse
            start_day: Starting day number (inclusive)
            end_day: Ending day number (inclusive)

        Returns:
            List of ImageWithDetails models
        """
        return await self.image_ops.get_images_by_day_range(
            timelapse_id, start_day, end_day
        )

    async def get_images_by_date_range(
        self, timelapse_id: int, start_date: date, end_date: date
    ) -> List[ImageWithDetails]:
        """
        Get images for a timelapse within a specific date range.

        Args:
            timelapse_id: ID of the timelapse
            start_date: Starting date (inclusive)
            end_date: Ending date (inclusive)

        Returns:
            List of ImageWithDetails models
        """
        return await self.image_ops.get_images_by_date_range(
            timelapse_id, start_date, end_date
        )

    async def delete_image(self, image_id: int) -> bool:
        """
        Delete a specific image.

        Args:
            image_id: ID of the image to delete

        Returns:
            True if image was deleted successfully
        """
        # Get image info before deletion for SSE event
        image_to_delete = await self.get_image_by_id(image_id)
        
        success = await self.image_ops.delete_image(image_id)
        
        # Create SSE event for real-time updates
        if success and image_to_delete:
            await self.sse_ops.create_event(
                event_type="image_deleted",
                event_data={
                    "image_id": image_id,
                    "camera_id": image_to_delete.camera_id,
                    "timelapse_id": image_to_delete.timelapse_id,
                    "filename": image_to_delete.filename
                },
                priority="normal",
                source="api"
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
        
        # Create SSE event for real-time updates
        await self.sse_ops.create_event(
            event_type="image_captured",
            event_data={
                "image_id": image_record.id,
                "camera_id": image_record.camera_id,
                "timelapse_id": image_record.timelapse_id,
                "filename": image_record.filename,
                "captured_at": image_record.captured_at.isoformat()
            },
            priority="normal",
            source="worker"
        )
            
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

    async def get_images_for_timelapse(
        self, timelapse_id: int
    ) -> List[ImageWithDetails]:
        """
        Get all images for a specific timelapse (helper method).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            List of ImageWithDetails model instances
        """
        result = await self.image_ops.get_images(
            timelapse_id=timelapse_id, page=1, page_size=DEFAULT_TIMELAPSE_IMAGES_LIMIT
        )
        return result["images"]

    async def get_images_batch(
        self, image_ids: List[int], size: str = "thumbnail"
    ) -> List[ImageWithDetails]:
        """
        Get multiple images by their IDs for batch loading.

        Args:
            image_ids: List of image IDs to retrieve
            size: Size variant ('thumbnail', 'small', 'original')

        Returns:
            List of ImageWithDetails model instances with proper type safety
        """
        try:
            images = []
            for image_id in image_ids:
                try:
                    # Get image metadata using existing method that returns ImageWithDetails
                    image_data = await self.get_image_by_id(image_id)
                    if not image_data:
                        logger.warning(f"Image {image_id} not found for batch loading")
                        continue

                    # The image_data is already an ImageWithDetails Pydantic model
                    # No need to convert to dict - just append the model directly
                    images.append(image_data)

                except Exception as e:
                    logger.error(f"Error processing image {image_id} in batch: {e}")
                    continue

            logger.info(
                f"Batch loaded {len(images)} images out of {len(image_ids)} requested (size: {size})"
            )
            
            # SSE broadcasting handled by higher-level service layer
            
            return images

        except Exception as e:
            logger.error(f"Batch image loading failed: {e}")
            return []

    async def coordinate_thumbnail_generation(
        self, image_id: int, force_regenerate: bool = False
    ) -> ThumbnailGenerationResult:
        """
        Coordinate thumbnail generation via thumbnail_utils.

        Args:
            image_id: ID of the image to generate thumbnails for
            force_regenerate: Whether to regenerate existing thumbnails

        Returns:
            ThumbnailGenerationResult with generation details
        """
        try:
            # Get image details
            image = await self.get_image_by_id(image_id)
            if not image:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=image_id,
                    error=f"Image {image_id} not found",
                )

            # Import thumbnail utils for processing
            from ..utils import thumbnail_utils
            from ..utils.file_helpers import validate_file_path

            # Get data directory from database settings and construct secure paths
            data_directory = await self.settings_service.get_setting("data_directory")
            
            # Validate the image file path
            secure_image_path = validate_file_path(
                f"cameras/camera-{image.camera_id}/images/{image.file_path}",
                base_directory=data_directory,
                must_exist=True
            )
            
            # Generate secure output directory path
            secure_output_dir = validate_file_path(
                f"cameras/camera-{image.camera_id}",
                base_directory=data_directory,
                must_exist=False
            )
            
            thumbnail_result = thumbnail_utils.generate_thumbnails_from_file(
                Path(secure_image_path), Path(secure_output_dir)
            )
            thumbnail_tuple = thumbnail_result.get("thumbnail")
            small_tuple = thumbnail_result.get("small")

            thumbnail_path = thumbnail_tuple[0] if thumbnail_tuple else None
            thumbnail_size = thumbnail_tuple[1] if thumbnail_tuple else None
            small_path = small_tuple[0] if small_tuple else None
            small_size = small_tuple[1] if small_tuple else None

            # Prepare dict for DB update
            thumbnail_paths = {
                "thumbnail_path": thumbnail_path,
                "thumbnail_size": thumbnail_size,
                "small_path": small_path,
                "small_size": small_size,
            }
            await self.image_ops.update_image_thumbnails(image_id, thumbnail_paths)

            logger.info(
                f"Generated thumbnails for image {image_id}: thumbnail={thumbnail_path}, small={small_path}"
            )

            if thumbnail_path or small_path:
                result = ThumbnailGenerationResult(
                    success=True,
                    image_id=image_id,
                    thumbnail_path=thumbnail_path,
                    small_path=small_path,
                    thumbnail_size=thumbnail_size,
                    small_size=small_size,
                )
                
                # SSE broadcasting handled by higher-level service layer
                    
                return result
            else:
                error_msg = "Thumbnail generation failed: No thumbnails created"
                logger.error(
                    f"Thumbnail generation failed for image {image_id}: {error_msg}"
                )
                return ThumbnailGenerationResult(
                    success=False, image_id=image_id, error=error_msg
                )

        except Exception as e:
            logger.error(f"Thumbnail coordination failed for image {image_id}: {e}")
            return ThumbnailGenerationResult(
                success=False, image_id=image_id, error=str(e)
            )

    async def coordinate_file_serving(
        self, image_id: int, size_type: str = "full"
    ) -> Dict[str, Any]:
        """
        Coordinate file serving with cascading fallbacks.

        Args:
            image_id: ID of the image to serve
            size_type: Type of image size ('full', 'thumbnail', 'small')

        Returns:
            File serving coordination results including file path and metadata
        """
        try:
            # Get image details
            image = await self.get_image_by_id(image_id)
            if not image:
                return {"success": False, "error": f"Image {image_id} not found"}

            # Determine file path based on size type with fallbacks using secure path handling
            from pathlib import Path
            from ..utils.file_helpers import validate_file_path, ensure_directory_exists
            from .settings_service import SettingsService
            
            # Get data directory from database settings, not config
            data_directory = await self.settings_service.get_setting("data_directory")

            if size_type == "thumbnail":
                # Try thumbnail first, fall back to small, then full with secure path validation
                try:
                    thumbnail_path = validate_file_path(
                        f"cameras/camera-{image.camera_id}/thumbnails/{image.file_path}",
                        base_directory=data_directory,
                        must_exist=False
                    )
                except Exception:
                    thumbnail_path = None
                    
                try:
                    small_path = validate_file_path(
                        f"cameras/camera-{image.camera_id}/small/{image.file_path}",
                        base_directory=data_directory,
                        must_exist=False
                    )
                except Exception:
                    small_path = None
                    
                try:
                    full_path = validate_file_path(
                        f"cameras/camera-{image.camera_id}/images/{image.file_path}",
                        base_directory=data_directory,
                        must_exist=False
                    )
                except Exception:
                    full_path = None

                for path_type, file_path in [
                    ("thumbnail", thumbnail_path),
                    ("small", small_path),
                    ("full", full_path),
                ]:
                    if file_path and Path(file_path).exists():
                        return {
                            "success": True,
                            "file_path": str(file_path),
                            "size_type": path_type,
                            "file_size": Path(file_path).stat().st_size,
                            "fallback_used": path_type != size_type,
                        }

            elif size_type == "small":
                # Try small first, fall back to full with secure path validation
                try:
                    small_path = validate_file_path(
                        f"cameras/camera-{image.camera_id}/small/{image.file_path}",
                        base_directory=data_directory,
                        must_exist=False
                    )
                except Exception:
                    small_path = None
                    
                try:
                    full_path = validate_file_path(
                        f"cameras/camera-{image.camera_id}/images/{image.file_path}",
                        base_directory=data_directory,
                        must_exist=False
                    )
                except Exception:
                    full_path = None

                for path_type, file_path in [
                    ("small", small_path),
                    ("full", full_path),
                ]:
                    if file_path and Path(file_path).exists():
                        return {
                            "success": True,
                            "file_path": str(file_path),
                            "size_type": path_type,
                            "file_size": Path(file_path).stat().st_size,
                            "fallback_used": path_type != size_type,
                        }

            else:  # full size
                try:
                    full_path = validate_file_path(
                        f"cameras/camera-{image.camera_id}/images/{image.file_path}",
                        base_directory=data_directory,
                        must_exist=False
                    )
                    if full_path and Path(full_path).exists():
                        return {
                            "success": True,
                            "file_path": str(full_path),
                            "size_type": "full",
                            "file_size": Path(full_path).stat().st_size,
                            "fallback_used": False,
                        }
                except Exception:
                    pass

            return {
                "success": False,
                "error": f"No image file found for image {image_id}",
            }

        except Exception as e:
            logger.error(f"File serving coordination failed for image {image_id}: {e}")
            return {"success": False, "error": str(e)}

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
            # Get basic image statistics from database
            basic_stats = await self.image_ops.get_image_statistics(
                timelapse_id, camera_id
            )

            # Coordinate with corruption service for quality data if available
            quality_stats = None
            if self.corruption_service:
                if timelapse_id:
                    quality_stats = (
                        await self.corruption_service.get_timelapse_quality_statistics(
                            timelapse_id
                        )
                    )
                elif camera_id:
                    quality_stats = (
                        await self.corruption_service.get_camera_quality_statistics(
                            camera_id
                        )
                    )
                else:
                    quality_stats = (
                        await self.corruption_service.get_overall_quality_statistics()
                    )

            # Combine statistics
            from ..utils.timezone_utils import get_timezone_aware_timestamp_string_async

            calculation_timestamp = await get_timezone_aware_timestamp_string_async(
                self.db
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
            logger.error(f"Image statistics calculation failed: {e}")
            return {"error": str(e)}

    async def coordinate_quality_assessment(self, image_id: int) -> Dict[str, Any]:
        """
        Coordinate image quality assessment with corruption service.

        Args:
            image_id: ID of the image to assess

        Returns:
            Quality assessment results
        """
        try:
            # Get image details
            image = await self.get_image_by_id(image_id)
            if not image:
                return {"success": False, "error": f"Image {image_id} not found"}

            # Coordinate with corruption service if available
            if self.corruption_service:
                quality_result = await self.corruption_service.assess_image_quality(
                    image_id, image.file_path
                )

                # Update image with quality score if provided
                if quality_result.get("success") and "quality_score" in quality_result:
                    await self.image_ops.set_image_corruption_score(
                        image_id, quality_result["quality_score"]
                    )

                return quality_result
            else:
                logger.warning(
                    f"CorruptionService not available for quality assessment of image {image_id}"
                )
                return {"success": False, "error": "CorruptionService not configured"}

        except Exception as e:
            logger.error(
                f"Quality assessment coordination failed for image {image_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    async def serve_image_file(self, image_id: int, size_variant: str = "full"):
        """
        Serve an image file with proper cascading fallbacks.

        Args:
            image_id: ID of the image to serve
            size_variant: Size variant ('full', 'thumbnail', 'small')

        Returns:
            FastAPI Response for file serving
        """
        from fastapi import HTTPException, status
        from fastapi.responses import FileResponse
        from ..utils.file_helpers import create_file_response

        try:
            # Use the existing prepare_image_for_serving method
            result = await self.prepare_image_for_serving(image_id, size_variant)

            if not result.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=result.get("error", "Image not found"),
                )

            file_path = result.get("file_path")
            media_type = result.get("media_type", "image/jpeg")

            if file_path is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Image file not found"
                )
            # Use file_helpers to create secure file response
            return create_file_response(file_path, media_type)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to serve image {image_id} (size: {size_variant}): {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to serve image file",
            )

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
            image_data = await self.get_image_by_id(image_id)
            if not image_data:
                return {"success": False, "error": "Image not found"}

            # Use file_helpers to get image with fallbacks
            from ..utils.file_helpers import (
                get_image_with_fallbacks,
                validate_media_type,
            )
            from ..constants import ALLOWED_IMAGE_EXTENSIONS

            # Convert Pydantic model to dict for file_helpers compatibility
            image_dict = {
                "id": image_data.id,
                "file_path": image_data.file_path,
                "thumbnail_path": getattr(image_data, "thumbnail_path", None),
                "small_path": getattr(image_data, "small_path", None),
            }

            # Get data directory from database settings, not config
            data_directory = await self.settings_service.get_setting("data_directory")

            file_path = get_image_with_fallbacks(image_dict, size, data_directory)
            media_type = validate_media_type(file_path, ALLOWED_IMAGE_EXTENSIONS)

            return {
                "success": True,
                "file_path": file_path,
                "media_type": media_type,
                "image_id": image_id,
                "size": size,
                "fallback_used": False,  # file_helpers handles this internally
            }

        except Exception as e:
            logger.error(f"Failed to prepare image {image_id} for serving: {e}")
            return {"success": False, "error": str(e)}

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
            import io
            import zipfile
            from pathlib import Path
            from ..utils.file_helpers import validate_file_path, clean_filename
            from ..utils.timezone_utils import get_timezone_aware_timestamp_string_async
            from .settings_service import SettingsService
            
            # Get data directory from database settings, not config
            data_directory = await self.settings_service.get_setting("data_directory")

            if not image_ids:
                return {"success": False, "error": "No image IDs provided"}

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
                return {"success": False, "error": "No valid images found for download"}

            zip_buffer.seek(0)

            # Generate filename with timezone-aware timestamp
            timestamp = await get_timezone_aware_timestamp_string_async(self.db)
            filename = zip_filename or f"timelapser_images_{timestamp}.zip"
            filename = clean_filename(filename)

            result = {
                "success": True,
                "zip_data": zip_buffer.getvalue(),
                "filename": filename,
                "requested_images": len(image_ids),
                "included_images": added_files,
                "total_size": total_size,
            }
            
            # SSE broadcasting handled by higher-level service layer
            
            return result

        except Exception as e:
            logger.error(f"Bulk download preparation failed: {e}")
            return {"success": False, "error": str(e)}


class SyncImageService:
    """
    Sync image service for worker processes using composition pattern.

    This service orchestrates image-related business logic using
    dependency injection instead of mixin inheritance.
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize SyncImageService with sync database instance.

        Args:
            db: SyncDatabase instance
        """
        self.db = db
        self.image_ops = SyncImageOperations(db)

    def record_captured_image(self, image_data: Dict[str, Any]) -> Image:
        """
        Record a newly captured image (sync version for worker).

        Args:
            image_data: Dictionary containing image metadata

        Returns:
            Created Image model instance
        """
        return self.image_ops.record_captured_image(image_data)

    def get_image_count_by_timelapse(self, timelapse_id: int) -> int:
        """
        Get the total count of images for a timelapse (sync version).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Total image count
        """
        return self.image_ops.get_image_count_by_timelapse(timelapse_id)

    def calculate_day_number(self, timelapse_id: int, captured_at: datetime) -> int:
        """
        Calculate the day number for an image within a timelapse.

        Args:
            timelapse_id: ID of the timelapse
            captured_at: When the image was captured

        Returns:
            Day number (1-based)
        """
        return self.image_ops.calculate_day_number(timelapse_id, captured_at)

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
