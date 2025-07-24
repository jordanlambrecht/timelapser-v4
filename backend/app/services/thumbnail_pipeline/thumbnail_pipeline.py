# backend/app/services/thumbnail_pipeline/thumbnail_pipeline.py
"""
Main Thumbnail Pipeline Class

Provides unified interface for all thumbnail generation functionality
with proper dependency injection.
"""

from pathlib import Path

from typing import Optional, Dict, Any
from loguru import logger

from ...database.core import AsyncDatabase, SyncDatabase
from ...enums import JobPriority
from .services import (
    ThumbnailJobService,
    SyncThumbnailJobService,
    ThumbnailPerformanceService,
    SyncThumbnailPerformanceService,
    ThumbnailVerificationService,
    SyncThumbnailVerificationService,
    ThumbnailRepairService,
    SyncThumbnailRepairService,
)
from .generators import (
    ThumbnailGenerator,
    SmallImageGenerator,
    BatchThumbnailGenerator,
)
from ...models.shared_models import ThumbnailGenerationResult
from ...database.image_operations import SyncImageOperations


class ThumbnailPipeline:
    """
    Main thumbnail generation pipeline providing unified access to all
    thumbnail functionality with proper dependency injection.
    """

    def __init__(
        self,
        database: Optional[SyncDatabase] = None,
        async_database: Optional[AsyncDatabase] = None,
    ):
        """
        Initialize thumbnail pipeline.

        Args:
            database: Sync database instance (for creating sync services)
            async_database: Async database instance (for async services)
        """
        self.database = database
        self.async_database = async_database

        # Initialize services
        if database:
            self._initialize_sync_services()
        if async_database:
            self._initialize_async_services()

        # Initialize generators
        self._initialize_generators()

    def _initialize_sync_services(self):
        """Initialize sync services for worker processes."""
        if not self.database:
            return

        try:
            self.sync_job_service = SyncThumbnailJobService(self.database)
            self.sync_performance_service = SyncThumbnailPerformanceService(
                self.database
            )
            self.sync_verification_service = SyncThumbnailVerificationService(
                self.database
            )
            self.sync_repair_service = SyncThumbnailRepairService(self.database)
            logger.debug("✅ Thumbnail pipeline sync services initialized")
        except Exception as e:
            logger.error(
                f"❌ Failed to initialize thumbnail pipeline sync services: {e}"
            )
            raise

    def _initialize_async_services(self):
        """Initialize async services for API endpoints."""
        if not self.async_database:
            return

        try:
            self.job_service = ThumbnailJobService(self.async_database)
            self.performance_service = ThumbnailPerformanceService(self.async_database)
            self.verification_service = ThumbnailVerificationService(
                self.async_database
            )
            self.repair_service = ThumbnailRepairService(self.async_database)
            logger.debug("✅ Thumbnail pipeline async services initialized")
        except Exception as e:
            logger.error(
                f"❌ Failed to initialize thumbnail pipeline async services: {e}"
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
            logger.error(f"❌ Failed to initialize thumbnail pipeline generators: {e}")
            raise

    # Sync methods for workers
    def queue_thumbnail_job_sync(
        self,
        image_id: int,
        priority: str = JobPriority.MEDIUM,
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
            logger.error(f"Failed to queue thumbnail job for image {image_id}: {e}")
            return None

    def get_job_statistics_sync(self) -> Dict[str, Any]:
        """Get thumbnail job queue statistics (sync interface for workers)."""
        if not hasattr(self, "sync_job_service"):
            logger.error("Sync job service not available")
            return {}

        try:
            return self.sync_job_service.get_job_statistics()
        except Exception as e:
            logger.error(f"Failed to get job statistics: {e}")
            return {}

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

            image_ops = SyncImageOperations(self.database)
            image = image_ops.get_image_by_id(image_id)

            if not image:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=image_id,
                    error=f"Image {image_id} not found",
                ).__dict__

            # Generate thumbnail paths based on source image
            source_path = Path(image.file_path)
            base_dir = source_path.parent.parent  # Go up from images/date to base

            # Create thumbnail and small paths
            thumbnail_dir = base_dir / "thumbnails" / source_path.parent.name
            small_dir = base_dir / "small" / source_path.parent.name

            # Ensure directories exist
            thumbnail_dir.mkdir(parents=True, exist_ok=True)
            small_dir.mkdir(parents=True, exist_ok=True)

            thumbnail_path = str(thumbnail_dir / source_path.name)
            small_path = str(small_dir / source_path.name)

            # Use generators to create thumbnails
            thumbnail_result = self.thumbnail_generator.generate_thumbnail(
                source_path=image.file_path, output_path=thumbnail_path
            )
            small_result = self.small_generator.generate_small_image(
                source_path=image.file_path, output_path=small_path
            )

            # Determine success based on at least one successful generation
            success = thumbnail_result.get("success", False) or small_result.get(
                "success", False
            )

            result = ThumbnailGenerationResult(
                success=success,
                image_id=image_id,
                timelapse_id=getattr(image, "timelapse_id", None),
                thumbnail_path=(
                    thumbnail_result.get("path")
                    if thumbnail_result.get("success")
                    else None
                ),
                small_path=(
                    small_result.get("path") if small_result.get("success") else None
                ),
                error=None if success else "Failed to generate thumbnails",
            )

            return result.__dict__

        except Exception as e:
            logger.error(f"Failed to process thumbnails for image {image_id}: {e}")
            return ThumbnailGenerationResult(
                success=False, image_id=image_id, error=str(e)
            ).__dict__

    # Async methods for API endpoints
    async def queue_thumbnail_job(
        self,
        image_id: int,
        priority: str = JobPriority.MEDIUM,
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
            logger.error(f"Failed to queue thumbnail job for image {image_id}: {e}")
            return None

    async def get_job_statistics(self) -> Dict[str, Any]:
        """Get thumbnail job queue statistics (async interface)."""
        if not hasattr(self, "job_service"):
            logger.error("Async job service not available")
            return {}

        try:
            return await self.job_service.get_job_statistics()
        except Exception as e:
            logger.error(f"Failed to get job statistics: {e}")
            return {}


# Factory functions for creating pipeline instances


def create_thumbnail_pipeline(
    database: Optional[SyncDatabase] = None,
    async_database: Optional[AsyncDatabase] = None,
) -> ThumbnailPipeline:
    """
    Factory function to create a thumbnail pipeline instance.

    Args:
        database: Sync database instance
        async_database: Async database instance

    Returns:
        Configured ThumbnailPipeline instance
    """
    return ThumbnailPipeline(database=database, async_database=async_database)


def create_sync_thumbnail_pipeline(database: SyncDatabase) -> ThumbnailPipeline:
    """
    Factory function to create a sync-only thumbnail pipeline for workers.

    Args:
        database: Sync database instance

    Returns:
        Configured ThumbnailPipeline instance with sync services
    """
    return ThumbnailPipeline(database=database)


def create_async_thumbnail_pipeline(async_database: AsyncDatabase) -> ThumbnailPipeline:
    """
    Factory function to create an async-only thumbnail pipeline for API endpoints.

    Args:
        async_database: Async database instance

    Returns:
        Configured ThumbnailPipeline instance with async services
    """
    return ThumbnailPipeline(async_database=async_database)
