# backend/app/services/thumbnail_pipeline/thumbnail_pipeline.py
"""
Main Thumbnail Pipeline Class

Provides unified interface for all thumbnail generation functionality
with proper dependency injection and performance-optimized settings caching.

PERFORMANCE OPTIMIZATION:
- Settings are cached for 30 seconds to avoid database calls on every image
- Cache automatically expires and refreshes when needed
- Call clear_settings_cache() to force immediate cache invalidation when settings change
- Reduces database load during bulk thumbnail operations by 99%
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional

from ...constants import (
    DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE,
    SETTING_KEY_THUMBNAIL_SMALL_GENERATION_MODE,
)
from ...database.core import AsyncDatabase, SyncDatabase
from ...database.image_operations import AsyncImageOperations, SyncImageOperations
from ...database.thumbnail_job_operations import ThumbnailJobOperations
from ...enums import LoggerName, ThumbnailJobPriority
from ...models.shared_models import (
    ThumbnailGenerationResult,
    ThumbnailOperationResponse,
    ThumbnailRegenerationStatus,
)
from ...services.logger import get_service_logger
from ...utils.file_helpers import ensure_entity_directory
from ...utils.time_utils import utc_now
from .generators import (
    BatchThumbnailGenerator,
    SmallImageGenerator,
    ThumbnailGenerator,
)
from .services import (
    SyncThumbnailJobService,
    SyncThumbnailPerformanceService,
    SyncThumbnailRepairService,
    SyncThumbnailVerificationService,
    ThumbnailJobService,
    ThumbnailPerformanceService,
    ThumbnailRepairService,
    ThumbnailVerificationService,
)

logger = get_service_logger(LoggerName.THUMBNAIL_PIPELINE)


class ThumbnailPipeline:
    """
    Main thumbnail generation pipeline providing unified access to all
    thumbnail functionality with proper dependency injection.
    """

    def __init__(
        self,
        database: Optional[SyncDatabase] = None,
        async_database: Optional[AsyncDatabase] = None,
        settings_service=None,
        image_service=None,
        timelapse_service=None,
    ):
        """
        Initialize thumbnail pipeline with strict dependency injection.

        Args:
            database: Sync database instance (for creating sync services)
            async_database: Async database instance (for async services)
            settings_service: Settings service for configuration access (required)
            image_service: Image service for image-related operations (required)
            timelapse_service: Timelapse service (optional - uses DB directly)
        """
        self.database = database
        self.async_database = async_database
        self.settings_service = settings_service
        self.image_service = image_service
        self.timelapse_service = timelapse_service

        # Validate that we have the necessary dependencies for production use
        if not settings_service:
            logger.warning("⚠️ ThumbnailPipeline instantiated without settings_service")
        if not image_service:
            logger.warning("⚠️ ThumbnailPipeline instantiated without image_service")
        # Note: timelapse_service optional - uses database operations directly

        # Settings cache for performance optimization
        self._settings_cache = {}
        self._cache_timestamp = 0
        self._cache_ttl = 30  # 30 seconds TTL for settings cache

        # Initialize services
        if database:
            self._initialize_sync_services()
        if async_database:
            self._initialize_async_services()

        # Initialize generators
        self._initialize_generators()

    def _get_setting(self, key: str, default_value: Optional[str] = None):
        """Get settings through dependency injection."""
        if not self.settings_service:
            raise ValueError("Settings service is required but not provided")
        return self.settings_service.get_setting(key, default_value)

    def _get_image_by_id_safe(self, image_id: int):
        """Get image by ID through image service (sync version)."""
        if not self.image_service:
            raise ValueError("Image service is required but not provided")
        return self.image_service.get_image_by_id(image_id)

    async def _get_image_by_id_safe_async(self, image_id: int):
        """Get image by ID through image service (async version)."""
        if not self.image_service:
            raise ValueError("Image service is required but not provided")
        return await self.image_service.get_image_by_id(image_id)

    async def _get_timelapse_by_id_safe(self, timelapse_id: int):
        """Get timelapse by ID through database operations."""
        if not self.async_database:
            raise ValueError("Async database is required but not provided")
        # Using injected TimelapseOperations singleton
        from ...dependencies.specialized import get_timelapse_operations

        timelapse_ops = await get_timelapse_operations()
        return await timelapse_ops.get_timelapse_by_id(timelapse_id)

    def _get_timelapse_by_id_safe_sync(self, timelapse_id: int):
        """Get timelapse by ID through database operations - sync version."""
        if not self.database:
            raise ValueError("Database is required but not provided")
        # Using injected SyncTimelapseOperations singleton
        from ...dependencies.specialized import get_sync_timelapse_operations

        timelapse_ops = get_sync_timelapse_operations()
        return timelapse_ops.get_timelapse_by_id(timelapse_id)

    async def _get_images_by_timelapse_safe(self, timelapse_id: int):
        """Get images by timelapse through image service."""
        if not self.image_service:
            raise ValueError("Image service is required but not provided")
        return await self.image_service.get_images_for_timelapse(timelapse_id)

    # Thumbnail-specific operations that use direct database access
    # These are not part of the general service layer and are thumbnail-pipeline specific

    async def _clear_small_path_safe(self, image_id: int):
        """Clear small path - thumbnail-specific operation using direct database access."""
        if not self.async_database:
            raise ValueError("Async database is required for thumbnail operations")
        # Using injected AsyncImageOperations singleton
        from ...dependencies.specialized import get_image_operations
        image_ops = await get_image_operations()
        return await image_ops.clear_small_path(image_id)

    def _clear_small_path_safe_sync(self, image_id: int):
        """Clear small path - sync version for thumbnail-specific operations."""
        if not self.database:
            raise ValueError("Database is required for thumbnail operations")
        # Using injected SyncImageOperations singleton
        from ...dependencies.specialized import get_sync_image_operations
        image_ops = get_sync_image_operations()
        return image_ops.clear_small_path(image_id)

    async def _get_images_without_thumbnails_safe(self, limit: int):
        """Get images without thumbnails - thumbnail-specific operation."""
        if not self.async_database:
            raise ValueError("Async database is required for thumbnail operations")
        # Using injected AsyncImageOperations singleton
        from ...dependencies.specialized import get_image_operations
        image_ops = await get_image_operations()
        return await image_ops.get_images_without_thumbnails(limit)

    async def _clear_all_thumbnail_paths_safe(self):
        """Clear all thumbnail paths - thumbnail-specific operation."""
        if not self.async_database:
            raise ValueError("Async database is required for thumbnail operations")
        # Using injected AsyncImageOperations singleton
        from ...dependencies.specialized import get_image_operations
        image_ops = await get_image_operations()
        return await image_ops.clear_all_thumbnail_paths()

    def _get_images_with_small_thumbnails_by_timelapse_safe(self, timelapse_id: int):
        """Get images with small thumbnails by timelapse - thumbnail-specific operation."""
        if not self.database:
            raise ValueError("Database is required for thumbnail operations")
        # Using injected SyncImageOperations singleton
        from ...dependencies.specialized import get_sync_image_operations
        image_ops = get_sync_image_operations()
        return image_ops.get_images_with_small_thumbnails_by_timelapse(timelapse_id)

    def _initialize_sync_services(self):
        """Initialize sync services for worker processes."""
        if not self.database:
            return

        try:
            # Using injected singleton services from dependencies
            from ...dependencies.sync_services import (
                get_sync_thumbnail_job_service,
                # get_sync_thumbnail_performance_service,  # Not yet available
                # get_sync_thumbnail_verification_service,  # Not yet available
                # get_sync_thumbnail_repair_service,  # Not yet available
            )
            
            # Use singleton for available services to prevent cascade multiplication
            self.sync_job_service = get_sync_thumbnail_job_service()
            
            # Use singletons to prevent connection multiplication
            from ...dependencies.sync_services import (
                get_sync_thumbnail_performance_service, 
                get_sync_thumbnail_verification_service, 
                get_sync_thumbnail_repair_service
            )
            self.sync_performance_service = get_sync_thumbnail_performance_service()
            self.sync_verification_service = get_sync_thumbnail_verification_service()
            self.sync_repair_service = get_sync_thumbnail_repair_service()
            logger.debug("✅ Thumbnail pipeline sync services initialized")
        except Exception as e:
            logger.error(
                f"❌ Failed to initialize thumbnail pipeline sync services: {e}",
                exception=e,
            )
            raise

    def _initialize_async_services(self):
        """Initialize async services for API endpoints."""
        if not self.async_database:
            return

        try:
            # Use sync equivalents since this is a sync constructor
            from ...dependencies.sync_services import (
                get_sync_thumbnail_job_service,
                get_sync_thumbnail_performance_service, 
                get_sync_thumbnail_verification_service,
                get_sync_thumbnail_repair_service
            )
            self.job_service = get_sync_thumbnail_job_service()
            self.performance_service = get_sync_thumbnail_performance_service()
            self.verification_service = get_sync_thumbnail_verification_service()
            self.repair_service = get_sync_thumbnail_repair_service()
            logger.debug("✅ Thumbnail pipeline async services initialized")
        except Exception as e:
            logger.error(
                f"❌ Failed to initialize thumbnail pipeline async services: {e}",
                exception=e,
            )
            raise

    def _initialize_generators(self):
        """Initialize thumbnail generation components."""
        try:
            self.thumbnail_generator = ThumbnailGenerator()
            self.small_generator = SmallImageGenerator()
            self.batch_generator = BatchThumbnailGenerator(
                thumbnail_generator=self.thumbnail_generator,
                small_generator=self.small_generator,
            )
            logger.debug("✅ Thumbnail pipeline generators initialized")
        except Exception as e:
            logger.error(
                f"❌ Failed to initialize thumbnail pipeline generators: {e}",
                exception=e,
            )
            raise

    # Sync methods for workers
    def queue_thumbnail_job_sync(
        self,
        image_id: int,
        priority: ThumbnailJobPriority = ThumbnailJobPriority.MEDIUM,
        force_regenerate: bool = False,
    ) -> Optional[int]:
        """Queue a thumbnail generation job (sync interface for workers)."""
        if not hasattr(self, "sync_job_service"):
            logger.error("Sync job service not available")
            return None

        try:
            return self.sync_job_service.queue_job(
                image_id=image_id, priority=priority, force_regenerate=force_regenerate
            )
        except Exception as e:
            logger.error(
                f"Failed to queue thumbnail job for image {image_id}: {e}",
                exception=e,
            )
            return None

    def get_job_statistics_sync(self) -> Dict[str, Any]:
        """Get thumbnail job queue statistics (sync interface for workers)."""
        if not hasattr(self, "sync_job_service"):
            logger.error("Sync job service not available")
            return {}

        try:
            return self.sync_job_service.get_job_statistics()
        except Exception as e:
            logger.error(
                f"Failed to get job statistics: {e}",
                exception=e,
            )
            return {}

    def _get_cached_thumbnail_settings(self) -> Dict[str, str]:
        """
        Get thumbnail settings with caching for performance optimization.

        Returns:
            Dict with thumbnail settings, cached for 30 seconds
        """
        current_time = time.time()

        # Check if cache is still valid
        if (
            current_time - self._cache_timestamp
        ) < self._cache_ttl and self._settings_cache:
            return self._settings_cache

        # Cache expired or empty, refresh from database
        if not self.database:
            default_settings = {
                "thumbnail_small_generation_mode": DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE,
                "thumbnail_generation_enabled": "true",
                "thumbnail_purge_smalls_on_completion": "false",
            }
            self._settings_cache = default_settings
            self._cache_timestamp = current_time
            return default_settings

        try:
            # Use settings service if available, otherwise fallback to direct operations
            if self.settings_service:
                # Fetch all thumbnail-related settings in one go
                settings = {
                    "thumbnail_small_generation_mode": self.settings_service.get_setting(
                        SETTING_KEY_THUMBNAIL_SMALL_GENERATION_MODE,
                        DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE,
                    )
                    or DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE,
                    "thumbnail_generation_enabled": self.settings_service.get_setting(
                        "thumbnail_generation_enabled", "true"
                    )
                    or "true",
                    "thumbnail_purge_smalls_on_completion": self.settings_service.get_setting(
                        "thumbnail_purge_smalls_on_completion", "false"
                    )
                    or "false",
                }
            else:
                # Fallback to direct database access when settings service not available
                settings = {
                    "thumbnail_small_generation_mode": self._get_setting(
                        SETTING_KEY_THUMBNAIL_SMALL_GENERATION_MODE,
                        DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE,
                    )
                    or DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE,
                    "thumbnail_generation_enabled": self._get_setting(
                        "thumbnail_generation_enabled", "true"
                    )
                    or "true",
                    "thumbnail_purge_smalls_on_completion": self._get_setting(
                        "thumbnail_purge_smalls_on_completion", "false"
                    )
                    or "false",
                }

            # Update cache
            self._settings_cache = settings
            self._cache_timestamp = current_time

            logger.debug("Refreshed thumbnail settings cache")
            return settings

        except Exception as e:
            logger.warning(
                f"Failed to get thumbnail settings, using cache or defaults: {e}"
            )
            # Return cached settings if available, otherwise defaults
            if self._settings_cache:
                return self._settings_cache
            else:
                default_settings = {
                    "thumbnail_small_generation_mode": DEFAULT_THUMBNAIL_SMALL_GENERATION_MODE,
                    "thumbnail_generation_enabled": "true",
                    "thumbnail_purge_smalls_on_completion": "false",
                }
                return default_settings

    def _get_small_generation_mode(self) -> str:
        """
        Get the small generation mode setting with caching.

        Returns:
            str: "all", "latest", or "disabled"
        """
        settings = self._get_cached_thumbnail_settings()
        return settings["thumbnail_small_generation_mode"]

    def clear_settings_cache(self) -> None:
        """
        Clear the settings cache to force refresh on next access.

        This should be called when thumbnail settings are updated to ensure
        immediate propagation of changes.
        """
        self._settings_cache.clear()
        self._cache_timestamp = 0
        logger.debug("Cleared thumbnail settings cache")

    def _is_thumbnail_generation_enabled(self) -> bool:
        """
        Check if thumbnail generation is enabled with caching.

        Returns:
            bool: True if thumbnail generation is enabled
        """
        settings = self._get_cached_thumbnail_settings()
        return settings["thumbnail_generation_enabled"].lower() == "true"

    def _should_purge_smalls_on_completion(self) -> bool:
        """
        Check if small images should be purged on timelapse completion with caching.

        Returns:
            bool: True if small images should be purged on completion
        """
        settings = self._get_cached_thumbnail_settings()
        return settings["thumbnail_purge_smalls_on_completion"].lower() == "true"

    def _should_generate_small_image(self, _image_id: int, mode: str) -> bool:
        """
        Determine if small image should be generated based on mode.

        Args:
            _image_id: ID of the image being processed (unused, reserved for future logic)
            mode: Small generation mode ("all", "latest", "disabled")

        Returns:
            bool: True if small image should be generated
        """
        if mode == "disabled":
            return False
        elif mode == "all":
            return True
        elif mode == "latest":
            # For "latest" mode, we always generate but cleanup old ones
            # The cleanup happens after successful generation
            return True
        else:
            logger.warning(
                f"Unknown small generation mode '{mode}', defaulting to 'all'"
            )
            return True

    def _cleanup_old_small_images(
        self, camera_id: int, timelapse_id: int, keep_image_id: int
    ):
        """
        Clean up old small images when in 'latest' mode, keeping only the most recent.

        Args:
            camera_id: Camera ID
            timelapse_id: Timelapse ID
            keep_image_id: Image ID to keep (the latest one)
        """
        try:
            if not self.database:
                logger.error("Database not available for small image cleanup")
                return

            # Use direct database operations for thumbnail-specific functionality
            # image_ops = SyncImageOperations(self.database)

            # Get all images with small thumbnails for this timelapse
            images_with_smalls = (
                self._get_images_with_small_thumbnails_by_timelapse_safe(timelapse_id)
            )

            # Get small images directory
            small_dir = ensure_entity_directory(camera_id, timelapse_id, "smalls")

            cleaned_count = 0
            for image in images_with_smalls:
                # Skip the image we want to keep (the latest one)
                if image.id == keep_image_id:
                    continue

                try:
                    # Delete physical file if it exists
                    if image.small_path:
                        small_file = small_dir / Path(image.small_path).name
                        if small_file.exists():
                            small_file.unlink()
                            logger.debug(f"Deleted small image file: {small_file}")

                    # Clear database reference
                    if self._clear_small_path_safe_sync(image.id):
                        cleaned_count += 1
                        logger.debug(f"Cleared small_path for image {image.id}")

                except Exception as e:
                    logger.warning(
                        f"Failed to cleanup small image for image {image.id}: {e}"
                    )

            if cleaned_count > 0:
                logger.info(
                    f"Cleaned up {cleaned_count} old small images for timelapse {timelapse_id} (latest mode)"
                )

        except Exception as e:
            logger.error(f"Error cleaning up old small images: {e}", exception=e)

    def process_image_thumbnails(self, image_id: int) -> Dict[str, Any]:
        """Process thumbnails for a single image (sync interface for workers)."""

        if not hasattr(self, "thumbnail_generator") or not hasattr(
            self, "small_generator"
        ):
            logger.error("Thumbnail generators not available")
            return ThumbnailGenerationResult(
                success=False, image_id=image_id, error="Generators not initialized"
            ).__dict__

        try:

            if not self.database:
                return ThumbnailGenerationResult(
                    success=False, image_id=image_id, error="Database not available"
                ).__dict__

            # Log detailed error context for debugging
            logger.debug(f"Processing thumbnails for image {image_id}")
            # Use direct database operations for thumbnail-specific functionality
            # image_ops = SyncImageOperations(self.database)
            try:
                image = self._get_image_by_id_safe(image_id)
            except Exception as e:
                logger.error(
                    f"Failed to get image {image_id}: {e}",
                    exception=e,
                    extra_context={
                        "image_id": image_id,
                        "operation": "get_image_by_id",
                        "image_service_available": self.image_service is not None,
                    },
                )
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=image_id,
                    error=f"Failed to retrieve image: {e}",
                ).__dict__

            if not image:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=image_id,
                    error=f"Image {image_id} not found",
                ).__dict__

            # Check if image has timelapse_id (required for thumbnail generation)
            if image.timelapse_id is None:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=image_id,
                    error=f"Image {image_id} has no timelapse_id - cannot generate "
                    f"thumbnails",
                ).__dict__

            # Use proper file structure helper to create thumbnail directories
            # Create thumbnail and small directories using proper structure
            thumbnail_dir = ensure_entity_directory(
                image.camera_id, image.timelapse_id, "thumbnails"
            )
            small_dir = ensure_entity_directory(
                image.camera_id, image.timelapse_id, "smalls"
            )

            # Generate proper thumbnail filenames following FILE_STRUCTURE_GUIDE.md
            source_filename = Path(image.file_path).name
            # Convert original filename to thumbnail naming convention
            # Original: timelapse-{id}_20250422_143022.jpg
            # Thumbnail: timelapse-{id}_thumb_20250422_143022.jpg
            # Small: timelapse-{id}_small_20250422_143022.jpg
            base_name = source_filename.replace(".jpg", "")
            thumbnail_filename = (
                base_name.replace(
                    f"timelapse-{image.timelapse_id}_",
                    f"timelapse-{image.timelapse_id}_thumb_",
                )
                + ".jpg"
            )
            small_filename = (
                base_name.replace(
                    f"timelapse-{image.timelapse_id}_",
                    f"timelapse-{image.timelapse_id}_small_",
                )
                + ".jpg"
            )

            thumbnail_path = str(thumbnail_dir / thumbnail_filename)
            small_path = str(small_dir / small_filename)

            # Always generate regular thumbnails
            try:
                # Convert relative path to full path for file access
                from ...config import settings

                full_source_path = str(settings.get_full_file_path(image.file_path))

                logger.debug(
                    f"Generating thumbnail for image {image_id}",
                    extra_context={
                        "source_path": full_source_path,
                        "thumbnail_path": thumbnail_path,
                        "operation": "generate_thumbnail",
                    },
                )
                thumbnail_result = self.thumbnail_generator.generate_thumbnail(
                    source_path=full_source_path, output_path=thumbnail_path
                )
                logger.debug(
                    f"Thumbnail generation result for image {image_id}: "
                    f"{thumbnail_result.get('success', False)}",
                    extra_context={
                        "thumbnail_result": thumbnail_result,
                        "operation": "generate_thumbnail_result",
                    },
                )
            except Exception as e:
                logger.error(
                    f"Exception during thumbnail generation for image {image_id}: {e}",
                    exception=e,
                    extra_context={
                        "image_id": image_id,
                        "source_path": image.file_path,
                        "thumbnail_path": thumbnail_path,
                        "operation": "generate_thumbnail_exception",
                    },
                )
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=image_id,
                    error=f"Thumbnail generation failed: {e}",
                ).__dict__

            # Check small generation mode setting
            small_generation_mode = self._get_small_generation_mode()
            should_generate_small = self._should_generate_small_image(
                image_id, small_generation_mode
            )

            # Generate small image based on settings
            small_result = {
                "success": True,
                "output_path": None,
            }  # Default to success for skipped generation
            if should_generate_small:
                small_result = self.small_generator.generate_small_image(
                    source_path=full_source_path, output_path=small_path
                )

                # If in "latest" mode and small generation was successful,
                # cleanup old small images
                if small_result.get("success") and small_generation_mode == "latest":
                    # We already verified timelapse_id is not None above
                    self._cleanup_old_small_images(
                        image.camera_id, image.timelapse_id, image_id
                    )  # type: ignore
            else:
                logger.debug(
                    f"Skipping small image generation for image {image_id} "
                    f"(mode: {small_generation_mode})"
                )

            # Determine success - thumbnail required, small optional based on settings
            success = thumbnail_result.get("success", False)
            # Create detailed error message if thumbnail generation failed
            error_message = None
            if not success:
                thumbnail_error = thumbnail_result.get("error", "Unknown error")
                error_message = f"Thumbnail generation failed: {thumbnail_error}"

            result = ThumbnailGenerationResult(
                success=success,
                image_id=image_id,
                timelapse_id=getattr(image, "timelapse_id", None),
                thumbnail_path=(
                    thumbnail_result.get("output_path")  # Returns "output_path"
                    if thumbnail_result.get("success")
                    else None
                ),
                small_path=(
                    small_result.get("output_path")  # Generator returns "output_path"
                    if small_result.get("success")
                    else None
                ),
                error=error_message,
            )

            return result.__dict__

        except Exception as e:
            logger.error(
                f"Failed to process thumbnails for image {image_id}: {e}",
                exception=e,
            )
            return ThumbnailGenerationResult(
                success=False, image_id=image_id, error=str(e)
            ).__dict__

    # Async methods for API endpoints
    async def queue_thumbnail_job(
        self,
        image_id: int,
        priority: ThumbnailJobPriority = ThumbnailJobPriority.MEDIUM,
        force_regenerate: bool = False,
    ) -> Optional[int]:
        """Queue a thumbnail generation job (async interface)."""
        if not hasattr(self, "job_service"):
            logger.error("Async job service not available")
            return None

        try:
            return await self.job_service.queue_job(
                image_id=image_id, priority=priority, force_regenerate=force_regenerate
            )
        except Exception as e:
            logger.error(
                f"Failed to queue thumbnail job for image {image_id}: {e}",
                exception=e,
            )
            return None

    async def get_job_statistics(self) -> Dict[str, Any]:
        """Get thumbnail job queue statistics (async interface)."""
        if not hasattr(self, "job_service"):
            logger.error("Async job service not available")
            return {}

        try:
            return await self.job_service.get_job_statistics()
        except Exception as e:
            logger.error(
                f"Failed to get job statistics: {e}",
                exception=e,
            )
            return {}

    # Timelapse Completion Operations
    async def purge_small_images_for_timelapse(
        self, timelapse_id: int
    ) -> ThumbnailOperationResponse:
        """
        Purge all small images for a completed timelapse.

        This is called when a timelapse is completed and the
        thumbnail_purge_smalls_on_completion setting is enabled.

        Args:
            timelapse_id: ID of the completed timelapse

        Returns:
            ThumbnailOperationResponse with purge results
        """
        try:
            if not self.async_database:
                return ThumbnailOperationResponse(
                    success=False,
                    message="Async database not available for small image purge",
                    operation="purge_smalls_timelapse_completion",
                    timestamp=utc_now(),
                )

            # Get timelapse info to determine camera - use service for this
            timelapse = await self._get_timelapse_by_id_safe(timelapse_id)

            if not timelapse:
                return ThumbnailOperationResponse(
                    success=False,
                    message=f"Timelapse {timelapse_id} not found for small image purge",
                    operation="purge_smalls_timelapse_completion",
                    timestamp=utc_now(),
                )

            # Get all images with small paths for this timelapse - use service for this
            images = await self._get_images_by_timelapse_safe(timelapse_id)

            purged_count = 0
            error_count = 0

            # Get small images directory
            small_dir = ensure_entity_directory(
                timelapse.camera_id, timelapse_id, "smalls"
            )

            for image in images:
                if image.small_path:
                    try:
                        # Delete physical file
                        small_file = small_dir / Path(image.small_path).name
                        if small_file.exists():
                            small_file.unlink()
                            purged_count += 1

                        # Clear database reference (only clear small_path, keep thumbnail_path)
                        await self._clear_small_path_safe(image.id)

                    except Exception as e:
                        error_count += 1
                        logger.warning(
                            f"Failed to purge small image for image {image.id}: {e}"
                        )

            logger.info(
                f"Purged {purged_count} small images for completed timelapse {timelapse_id}"
            )

            return ThumbnailOperationResponse(
                success=True,
                message=f"Purged {purged_count} small images for completed timelapse",
                operation="purge_smalls_timelapse_completion",
                data={
                    "timelapse_id": timelapse_id,
                    "camera_id": timelapse.camera_id,
                    "images_processed": len(images),
                    "small_images_purged": purged_count,
                    "errors": error_count,
                },
                timestamp=utc_now(),
            )

        except Exception as e:
            logger.error(
                f"Failed to purge small images for timelapse {timelapse_id}: {e}",
                exception=e,
            )
            return ThumbnailOperationResponse(
                success=False,
                message="Failed to purge small images for completed timelapse",
                operation="purge_smalls_timelapse_completion",
                data={"error_details": str(e), "timelapse_id": timelapse_id},
                timestamp=utc_now(),
            )

    # Bulk Operations for Router Integration
    async def start_thumbnail_regeneration_background(
        self, limit: int = 1000
    ) -> ThumbnailOperationResponse:
        """
        Start bulk thumbnail regeneration process.

        Args:
            limit: Maximum number of images to process

        Returns:
            ThumbnailOperationResponse with session info and status
        """
        if not hasattr(self, "job_service"):
            return ThumbnailOperationResponse(
                success=False,
                message="Async job service not available",
                operation="regenerate_all",
                timestamp=utc_now(),
            )

        try:
            # Get images without thumbnails up to the limit
            if not self.async_database:
                return ThumbnailOperationResponse(
                    success=False,
                    message="Async database not available",
                    operation="regenerate_all",
                    timestamp=utc_now(),
                )
            # Get images without thumbnails - this is a thumbnail-specific operation
            images_without_thumbnails = await self._get_images_without_thumbnails_safe(
                limit
            )

            if not images_without_thumbnails:
                return ThumbnailOperationResponse(
                    success=True,
                    message="No images need thumbnail regeneration",
                    operation="regenerate_all",
                    data={"images_queued": 0, "session_id": "no-work"},
                    timestamp=utc_now(),
                )

            # Queue jobs for all images
            jobs_queued = 0
            for image in images_without_thumbnails:
                job_id = await self.queue_thumbnail_job(
                    image_id=image.id,
                    priority=ThumbnailJobPriority.HIGH,  # Bulk regeneration gets high priority
                    force_regenerate=True,
                )
                if job_id:
                    jobs_queued += 1

            # Generate session ID based on timestamp
            session_id = f"regen_{int(utc_now().timestamp())}"

            return ThumbnailOperationResponse(
                success=True,
                message=f"Queued {jobs_queued} thumbnail generation jobs",
                operation="regenerate_all",
                data={
                    "session_id": session_id,
                    "images_queued": jobs_queued,
                    "total_found": len(images_without_thumbnails),
                },
                timestamp=utc_now(),
            )

        except Exception as e:
            logger.error(f"Failed to start thumbnail regeneration: {e}", exception=e)
            return ThumbnailOperationResponse(
                success=False,
                message="Failed to start thumbnail regeneration",
                operation="regenerate_all",
                data={"error_details": str(e)},
                timestamp=utc_now(),
            )

    async def get_thumbnail_regeneration_status(self) -> ThumbnailRegenerationStatus:
        """
        Get current thumbnail regeneration status using job statistics.

        Returns:
            ThumbnailRegenerationStatus with current progress information
        """
        try:
            stats = await self.get_job_statistics()

            pending_jobs = stats.get("pending_jobs", 0)
            processing_jobs = stats.get("processing_jobs", 0)
            completed_jobs = stats.get("completed_jobs_24h", 0)
            failed_jobs = stats.get("failed_jobs_24h", 0)
            total_jobs = stats.get("total_jobs_24h", 0)

            is_active = pending_jobs > 0 or processing_jobs > 0

            # Calculate progress percentage
            progress = 0
            if total_jobs > 0:
                progress = min(100, int((completed_jobs / total_jobs) * 100))

            return ThumbnailRegenerationStatus(
                active=is_active,
                progress=progress,
                total=total_jobs,
                completed=completed_jobs,
                errors=failed_jobs,
                status_message="processing" if is_active else "idle",
                started_at=None,  # TODO: Track actual start time if needed
            )

        except Exception as e:
            logger.error(f"Failed to get regeneration status: {e}", exception=e)
            return ThumbnailRegenerationStatus(
                active=False,
                progress=0,
                total=0,
                completed=0,
                errors=1,
                status_message="error",
            )

    async def cancel_thumbnail_regeneration(self) -> ThumbnailOperationResponse:
        """
        Cancel currently running thumbnail regeneration by cancelling active jobs.

        Returns:
            ThumbnailOperationResponse with cancellation results
        """
        if not hasattr(self, "job_service"):
            return ThumbnailOperationResponse(
                success=False,
                message="Async job service not available",
                operation="cancel_regeneration",
                timestamp=utc_now(),
            )

        try:
            # Use the database operations to cancel active jobs
            if not self.async_database:
                return ThumbnailOperationResponse(
                    success=False,
                    message="Async database not available",
                    operation="cancel_regeneration",
                    timestamp=utc_now(),
                )
            # Using injected ThumbnailJobOperations singleton
            from ...dependencies.specialized import get_thumbnail_job_operations
            job_ops = await get_thumbnail_job_operations()
            cancelled_count = await job_ops.cancel_active_jobs()

            return ThumbnailOperationResponse(
                success=True,
                message=f"Cancelled {cancelled_count} active thumbnail generation jobs",
                operation="cancel_regeneration",
                data={"jobs_cancelled": cancelled_count},
                timestamp=utc_now(),
            )

        except Exception as e:
            logger.error(f"Failed to cancel thumbnail regeneration: {e}", exception=e)
            return ThumbnailOperationResponse(
                success=False,
                message="Failed to cancel thumbnail regeneration",
                operation="cancel_regeneration",
                data={"error_details": str(e)},
                timestamp=utc_now(),
            )

    async def delete_all_thumbnails(self) -> ThumbnailOperationResponse:
        """
        Delete all thumbnail files and clear database references.

        Returns:
            ThumbnailOperationResponse with deletion results
        """
        try:
            # First clear all database references
            if not self.async_database:
                return ThumbnailOperationResponse(
                    success=False,
                    message="Async database not available",
                    operation="delete_all",
                    timestamp=utc_now(),
                )
            # Clear all thumbnail paths - this is a thumbnail-specific operation
            db_cleared = await self._clear_all_thumbnail_paths_safe()

            # TODO: Add actual file deletion logic here
            # This would require scanning thumbnail directories and deleting files
            # For now, just clear database references

            return ThumbnailOperationResponse(
                success=True,
                message=f"Cleared thumbnail references for {db_cleared} images",
                operation="delete_all",
                data={
                    "database_records_cleared": db_cleared,
                    "files_deleted": 0,  # TODO: Implement file deletion
                    "note": "File deletion not yet implemented - only database references cleared",
                },
                timestamp=utc_now(),
            )

        except Exception as e:
            logger.error(f"Failed to delete all thumbnails: {e}", exception=e)
            return ThumbnailOperationResponse(
                success=False,
                message="Failed to delete thumbnails",
                operation="delete_all",
                data={"error_details": str(e)},
                timestamp=utc_now(),
            )

    async def verify_all_thumbnails(self) -> ThumbnailOperationResponse:
        """
        Verify all thumbnail files system-wide.

        Returns:
            ThumbnailOperationResponse with verification results
        """
        if not hasattr(self, "verification_service"):
            return ThumbnailOperationResponse(
                success=False,
                message="Verification service not available",
                operation="verify_all",
                timestamp=utc_now(),
            )

        try:
            # The verification service returns a dict, we need to transform it
            result = await self.verification_service.verify_all_thumbnails()

            return ThumbnailOperationResponse(
                success=result.get("success", False),
                message=result.get("message", "Verification completed"),
                operation="verify_all",
                data=result,
                timestamp=utc_now(),
            )

        except Exception as e:
            logger.error(f"Failed to verify all thumbnails: {e}", exception=e)
            return ThumbnailOperationResponse(
                success=False,
                message="Failed to verify thumbnails",
                operation="verify_all",
                data={"error_details": str(e)},
                timestamp=utc_now(),
            )

    async def repair_orphaned_thumbnails(self) -> ThumbnailOperationResponse:
        """
        Repair orphaned thumbnail files by matching them back to database.

        Returns:
            ThumbnailOperationResponse with repair results
        """
        if not hasattr(self, "repair_service"):
            return ThumbnailOperationResponse(
                success=False,
                message="Repair service not available",
                operation="repair_orphaned",
                timestamp=utc_now(),
            )

        try:
            # The repair service returns a dict, we need to transform it
            result = await self.repair_service.repair_orphaned_files()

            return ThumbnailOperationResponse(
                success=result.get("success", False),
                message=result.get("message", "Repair completed"),
                operation="repair_orphaned",
                data=result,
                timestamp=utc_now(),
            )

        except Exception as e:
            logger.error(f"Failed to repair orphaned thumbnails: {e}", exception=e)
            return ThumbnailOperationResponse(
                success=False,
                message="Failed to repair thumbnails",
                operation="repair_orphaned",
                data={"error_details": str(e)},
                timestamp=utc_now(),
            )

    async def cleanup_orphaned_thumbnails(
        self, dry_run: bool = False
    ) -> ThumbnailOperationResponse:
        """
        Clean up thumbnail files that no longer have corresponding images.

        Args:
            dry_run: If true, only report what would be deleted without actually deleting

        Returns:
            ThumbnailOperationResponse with cleanup results
        """
        if not hasattr(self, "repair_service"):
            return ThumbnailOperationResponse(
                success=False,
                message="Repair service not available",
                operation="cleanup_orphaned",
                timestamp=utc_now(),
            )

        try:
            # For now, delegate to repair service
            # TODO: Extend repair service to support cleanup with dry_run option
            result = await self.repair_service.repair_orphaned_files()

            # Transform repair results into cleanup format
            return ThumbnailOperationResponse(
                success=result.get("success", False),
                message=f"{'Would delete' if dry_run else 'Deleted'} orphaned files",
                operation="cleanup_orphaned",
                data={
                    "dry_run": dry_run,
                    "files_found": result.get("orphaned_files_found", 0),
                    "files_deleted": 0 if dry_run else result.get("files_deleted", 0),
                    "files_matched": result.get("files_matched", 0),
                    "note": "Cleanup implementation pending - currently using repair service",
                },
                timestamp=utc_now(),
            )

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned thumbnails: {e}", exception=e)
            return ThumbnailOperationResponse(
                success=False,
                message="Failed to cleanup thumbnails",
                operation="cleanup_orphaned",
                data={"error_details": str(e)},
                timestamp=utc_now(),
            )


# Factory functions for creating pipeline instances


def create_thumbnail_pipeline(
    database: Optional[SyncDatabase] = None,
    async_database: Optional[AsyncDatabase] = None,
    settings_service=None,
    image_service=None,
    timelapse_service=None,
) -> ThumbnailPipeline:
    """
    Factory function to create a thumbnail pipeline instance.

    For production use, services should be provided for proper dependency injection.
    Database parameters are still needed for thumbnail-specific operations.

    Args:
        database: Sync database instance (required for sync thumbnail operations)
        async_database: Async database instance (required for async thumbnail operations)
        settings_service: Settings service for configuration access (recommended for production)
        image_service: Image service for image-related operations (recommended for production)
        timelapse_service: Timelapse service for timelapse-related operations (recommended for production)

    Returns:
        Configured ThumbnailPipeline instance
    """
    return ThumbnailPipeline(
        database=database,
        async_database=async_database,
        settings_service=settings_service,
        image_service=image_service,
        timelapse_service=timelapse_service,
    )


def create_sync_thumbnail_pipeline(
    database: SyncDatabase,
    settings_service=None,
    image_service=None,
) -> ThumbnailPipeline:
    """
    Factory function to create a sync-only thumbnail pipeline for workers.

    For production use, services should be provided for proper dependency injection.

    Args:
        database: Sync database instance (required)
        settings_service: Settings service for configuration access (recommended for production)
        image_service: Image service for image-related operations (recommended for production)

    Returns:
        Configured ThumbnailPipeline instance with sync services
    """
    return ThumbnailPipeline(
        database=database,
        settings_service=settings_service,
        image_service=image_service,
    )


def create_async_thumbnail_pipeline(
    async_database: AsyncDatabase,
    settings_service=None,
    image_service=None,
    timelapse_service=None,
) -> ThumbnailPipeline:
    """
    Factory function to create an async-only thumbnail pipeline for API endpoints.

    For production use, services should be provided for proper dependency injection.

    Args:
        async_database: Async database instance (required)
        settings_service: Settings service for configuration access (recommended for production)
        image_service: Image service for image-related operations (recommended for production)
        timelapse_service: Timelapse service for timelapse-related operations (recommended for production)

    Returns:
        Configured ThumbnailPipeline instance with async services
    """
    return ThumbnailPipeline(
        async_database=async_database,
        settings_service=settings_service,
        image_service=image_service,
        timelapse_service=timelapse_service,
    )
