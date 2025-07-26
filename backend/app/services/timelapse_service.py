# backend/app/services/timelapse_service.py
"""
Timelapse Service - Composition-based architecture.

This service handles timelapse-related business logic using dependency injection
for database operations, providing type-safe Pydantic model interfaces.

ARCHITECTURAL COMPLIANCE:
- Uses time_utils for all datetime operations
- Uses constants.py for status values
- Uses response_helpers for structured responses and SSE events
- Proper dependency injection pattern
- No direct database operations in business logic
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

from loguru import logger

from ..enums import SSEPriority

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.timelapse_operations import TimelapseOperations, SyncTimelapseOperations
from ..database.sse_events_operations import SSEEventsOperations
from ..models.timelapse_model import (
    Timelapse,
    TimelapseWithDetails,
    TimelapseCreate,
    TimelapseUpdate,
)
from ..models.shared_models import (
    TimelapseStatistics,
    TimelapseLibraryStatistics,
    TimelapseForCleanup,
    TimelapseVideoSettings,
)
from ..constants import (
    JOB_STATUS_LIST,
    TIMELAPSE_STATUSES,
    TimelapseStatus,
    EVENT_TIMELAPSE_CREATED,
    EVENT_TIMELAPSE_UPDATED,
    EVENT_TIMELAPSE_COMPLETED,
    EVENT_TIMELAPSE_HEALTH_MONITORED,
    EVENT_TIMELAPSE_STATISTICS_UPDATED,
    EVENT_HEALTH_CHECK_COMPLETED,
    SETTING_KEY_THUMBNAIL_PURGE_SMALLS_ON_COMPLETION,
)
from ..utils.time_utils import (
    get_timezone_aware_timestamp_async,
    utc_now,
)
from ..utils.response_helpers import (
    ResponseFormatter,
    LoggingHelper,
    ValidationHelper,
    MetricsHelper,
)


class TimelapseService:
    """
    Timelapse entity lifecycle business logic.

    Responsibilities:
    - Entity creation/completion
    - Statistics aggregation
    - Day number calculations
    - Auto-stop management
    - Progress tracking

    Interactions:
    - Uses TimelapseOperations for database
    - Coordinates with CameraService for active timelapse assignment
    - Provides data to VideoAutomationService
    """

    def __init__(
        self,
        db: AsyncDatabase,
        camera_service=None,
        video_automation_service=None,
        image_service=None,
        settings_service=None,
    ):
        """
        Initialize TimelapseService with async database instance and service dependencies.

        Args:
            db: AsyncDatabase instance
            camera_service: Optional CameraService for active timelapse coordination
            video_automation_service: Optional VideoAutomationService for automation triggers
            image_service: Optional ImageService for image operations
            settings_service: Optional SettingsService for configuration access
        """
        self.db = db
        self.timelapse_ops = TimelapseOperations(db)
        self.sse_ops = SSEEventsOperations(db)
        self.camera_service = camera_service
        self.video_automation_service = video_automation_service
        self.image_service = image_service
        self.settings_service = settings_service

    async def get_timelapses(
        self, camera_id: Optional[int] = None
    ) -> List[TimelapseWithDetails]:
        """
        Retrieve timelapses with optional camera filtering.

        Args:
            camera_id: Optional camera ID to filter by

        Returns:
            List of TimelapseWithDetails model instances
        """
        try:
            return await self.timelapse_ops.get_timelapses(camera_id)
        except Exception as e:
            LoggingHelper.log_operation_error(
                "retrieve", "timelapses", camera_id or "all", e
            )
            raise

    async def get_timelapses_for_camera(
        self, camera_id: int
    ) -> List[TimelapseWithDetails]:
        """
        Get all timelapses for a specific camera.

        Args:
            camera_id: ID of the camera

        Returns:
            List of TimelapseWithDetails model instances
        """
        ValidationHelper.validate_id_parameter(camera_id, "camera")
        return await self.get_timelapses(camera_id)

    async def get_timelapse_by_id(
        self, timelapse_id: int
    ) -> Optional[TimelapseWithDetails]:
        """
        Retrieve a specific timelapse by ID with metadata.

        Args:
            timelapse_id: ID of the timelapse to retrieve

        Returns:
            TimelapseWithDetails model instance, or None if not found
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        try:
            return await self.timelapse_ops.get_timelapse_by_id(timelapse_id)
        except Exception as e:
            LoggingHelper.log_operation_error("retrieve", "timelapse", timelapse_id, e)
            raise

    async def create_new_timelapse(
        self, camera_id: int, timelapse_data: TimelapseCreate
    ) -> Timelapse:
        """
        Create a new timelapse for a camera using entity-based architecture.

        Args:
            camera_id: ID of the camera
            timelapse_data: TimelapseCreate model instance

        Returns:
            Created Timelapse model instance
        """
        ValidationHelper.validate_id_parameter(camera_id, "camera")
        LoggingHelper.log_operation_start("create", "timelapse", f"camera_{camera_id}")

        try:
            # Create timelapse in database
            new_timelapse = await self.timelapse_ops.create_new_timelapse(
                camera_id, timelapse_data
            )

            # Create SSE event for real-time updates
            await self.sse_ops.create_event(
                event_type="timelapse_created",
                event_data={
                    "timelapse_id": new_timelapse.id,
                    "camera_id": camera_id,
                    "status": new_timelapse.status,
                    "name": new_timelapse.name,
                },
                priority=SSEPriority.NORMAL,
                source="api",
            )

            # Enhanced health monitoring integration
            await self._monitor_timelapse_health(new_timelapse.id, "creation")

            LoggingHelper.log_operation_success(
                "create", "timelapse", new_timelapse.id, f"for camera {camera_id}"
            )
            return new_timelapse

        except Exception as e:
            LoggingHelper.log_operation_error(
                "create", "timelapse", f"camera_{camera_id}", e
            )
            raise

    async def update_timelapse(
        self, timelapse_id: int, timelapse_data: TimelapseUpdate
    ) -> Timelapse:
        """
        Update an existing timelapse.

        Args:
            timelapse_id: ID of the timelapse to update
            timelapse_data: TimelapseUpdate model instance

        Returns:
            Updated Timelapse model instance
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        LoggingHelper.log_operation_start("update", "timelapse", timelapse_id)

        try:
            # Update timelapse in database
            updated_timelapse = await self.timelapse_ops.update_timelapse(
                timelapse_id, timelapse_data
            )

            # Create SSE event for real-time updates
            await self.sse_ops.create_event(
                event_type="timelapse_updated",
                event_data={
                    "timelapse_id": timelapse_id,
                    "camera_id": updated_timelapse.camera_id,
                    "status": updated_timelapse.status,
                    "name": updated_timelapse.name,
                },
                priority=SSEPriority.NORMAL,
                source="api",
            )

            # Invalidate statistics cache since updates may affect statistics
            self._invalidate_statistics_cache(timelapse_id)

            LoggingHelper.log_operation_success("update", "timelapse", timelapse_id)
            return updated_timelapse

        except Exception as e:
            LoggingHelper.log_operation_error("update", "timelapse", timelapse_id, e)
            raise

    async def delete_timelapse(self, timelapse_id: int) -> bool:
        """
        Delete a timelapse and all associated data.

        Args:
            timelapse_id: ID of the timelapse to delete

        Returns:
            True if timelapse was deleted successfully
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        LoggingHelper.log_operation_start("delete", "timelapse", timelapse_id)

        try:
            # Get timelapse info before deletion for SSE event
            timelapse_to_delete = await self.get_timelapse_by_id(timelapse_id)

            result = await self.timelapse_ops.delete_timelapse(timelapse_id)
            if result:
                LoggingHelper.log_operation_success("delete", "timelapse", timelapse_id)
                # Create SSE event for real-time updates
                if timelapse_to_delete:
                    await self.sse_ops.create_event(
                        event_type="timelapse_deleted",
                        event_data={
                            "timelapse_id": timelapse_id,
                            "camera_id": timelapse_to_delete.camera_id,
                            "name": timelapse_to_delete.name,
                        },
                        priority=SSEPriority.NORMAL,
                        source="api",
                    )
            return result
        except Exception as e:
            LoggingHelper.log_operation_error("delete", "timelapse", timelapse_id, e)
            raise

    async def get_timelapse_statistics(
        self, timelapse_id: int, use_cache: bool = True
    ) -> Optional[TimelapseStatistics]:
        """
        Get comprehensive statistics for a timelapse with optional caching.

        Args:
            timelapse_id: ID of the timelapse
            use_cache: Whether to use cached statistics (default: True)

        Returns:
            TimelapseStatistics model instance or None if timelapse not found
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")

        cache_key = f"timelapse_stats_{timelapse_id}"

        try:
            # Basic cache handling: check if we have a recently fetched result
            if use_cache and hasattr(self, "_stats_cache"):
                cached_result = self._stats_cache.get(cache_key)
                if (
                    cached_result
                    and cached_result.get("expires_at", 0) > utc_now().timestamp()
                ):
                    logger.debug(
                        f"Using cached statistics for timelapse {timelapse_id}"
                    )
                    return cached_result.get("data")

            # Fetch fresh statistics
            statistics = await self.timelapse_ops.get_timelapse_statistics(timelapse_id)

            # Cache the result for 5 minutes
            if use_cache:
                if not hasattr(self, "_stats_cache"):
                    self._stats_cache = {}
                self._stats_cache[cache_key] = {
                    "data": statistics,
                    "expires_at": utc_now().timestamp() + 300,  # 5 minutes cache
                }
                logger.debug(f"Cached statistics for timelapse {timelapse_id}")

            return statistics

        except Exception as e:
            LoggingHelper.log_operation_error(
                "get_statistics", "timelapse", timelapse_id, e
            )
            raise

    def _invalidate_statistics_cache(self, timelapse_id: int) -> None:
        """
        Invalidate cached statistics for a timelapse.

        Args:
            timelapse_id: ID of the timelapse to invalidate cache for
        """
        if hasattr(self, "_stats_cache"):
            cache_key = f"timelapse_stats_{timelapse_id}"
            self._stats_cache.pop(cache_key, None)
            logger.debug(f"Invalidated statistics cache for timelapse {timelapse_id}")

    async def get_library_statistics(self) -> TimelapseLibraryStatistics:
        """
        Get global statistics for the timelapse library.

        Returns comprehensive statistics across all timelapses including
        total counts, activity metrics, storage usage, and date ranges.
        """
        try:
            stats = await self.timelapse_ops.get_library_statistics()
            return stats

        except Exception as e:
            LoggingHelper.log_operation_error(
                "get_library_statistics", "timelapse", None, e
            )
            # Return empty statistics on error
            return TimelapseLibraryStatistics()

    async def get_active_timelapse_for_camera(
        self, camera_id: int
    ) -> Optional[Timelapse]:
        """
        Get the currently active timelapse for a camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Active Timelapse model instance, or None if no active timelapse
        """
        ValidationHelper.validate_id_parameter(camera_id, "camera")
        try:
            return await self.timelapse_ops.get_active_timelapse_for_camera(camera_id)
        except Exception as e:
            LoggingHelper.log_operation_error(
                "get_active", "timelapse", f"camera_{camera_id}", e
            )
            raise

    async def _update_timelapse_status(
        self,
        timelapse_id: int,
        status: TimelapseStatus,
        action_name: str,
    ) -> Timelapse:
        """
        Helper method to update timelapse status with proper validation.

        Args:
            timelapse_id: ID of the timelapse
            status: New status value
            action_name: Human-readable action name for logging

        Returns:
            Updated Timelapse model instance
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        ValidationHelper.validate_enum_value(status, set(TIMELAPSE_STATUSES), "status")

        # Get current timelapse to preserve existing settings
        current_timelapse = await self.get_timelapse_by_id(timelapse_id)
        if not current_timelapse:
            raise ValueError(f"Timelapse {timelapse_id} not found")

        # Ensure only allowed status values are passed to TimelapseUpdate
        if status not in TIMELAPSE_STATUSES:
            raise ValueError(
                f"Invalid status '{status}' for TimelapseUpdate. Allowed: {TIMELAPSE_STATUSES}"
            )
        timelapse_update = TimelapseUpdate(status=status)

        # Update timelapse
        updated_timelapse = await self.update_timelapse(timelapse_id, timelapse_update)

        # Create SSE event for status changes
        await self.sse_ops.create_event(
            event_type="timelapse_status_changed",
            event_data={
                "timelapse_id": timelapse_id,
                "camera_id": updated_timelapse.camera_id,
                "status": status,
                "action": action_name,
            },
            priority=SSEPriority.HIGH,
            source="api",
        )

        LoggingHelper.log_operation_success(action_name, "timelapse", timelapse_id)
        return updated_timelapse

    async def start_timelapse(self, timelapse_id: int) -> Timelapse:
        """
        Start a timelapse by updating its status to 'running'.

        Args:
            timelapse_id: ID of the timelapse to start

        Returns:
            Updated Timelapse model instance
        """
        updated_timelapse = await self._update_timelapse_status(
            timelapse_id, "running", "start"
        )

        # SSE broadcasting handled by higher-level service layer

        return updated_timelapse

    async def pause_timelapse(self, timelapse_id: int) -> Timelapse:
        """
        Pause a timelapse by updating its status to 'paused'.

        Args:
            timelapse_id: ID of the timelapse to pause

        Returns:
            Updated Timelapse model instance
        """
        updated_timelapse = await self._update_timelapse_status(
            timelapse_id, "paused", "pause"
        )

        # SSE broadcasting handled by higher-level service layer

        return updated_timelapse

    async def stop_timelapse(self, timelapse_id: int) -> Timelapse:
        """
        Stop a timelapse by updating its status to 'completed'.

        Args:
            timelapse_id: ID of the timelapse to stop

        Returns:
            Updated Timelapse model instance
        """
        updated_timelapse = await self._update_timelapse_status(
            timelapse_id, TimelapseStatus.COMPLETED, "stop"
        )

        # SSE broadcasting handled by higher-level service layer

        return updated_timelapse

    async def complete_timelapse(self, timelapse_id: int) -> Timelapse:
        """
        Mark a timelapse as completed and clean up camera references.

        Args:
            timelapse_id: ID of the timelapse to complete

        Returns:
            Completed Timelapse model instance
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        LoggingHelper.log_operation_start("complete", "timelapse", timelapse_id)

        try:
            completed_timelapse = await self.timelapse_ops.complete_timelapse(
                timelapse_id
            )

            # Check if we should purge small images on completion
            if self.settings_service:
                purge_setting = await self.settings_service.get_setting(
                    SETTING_KEY_THUMBNAIL_PURGE_SMALLS_ON_COMPLETION, "false"
                )
                if purge_setting.lower() == "true":
                    # TODO: Call ThumbnailService.purge_small_images_for_timelapse(timelapse_id)
                    # This should be moved to ThumbnailService for proper separation of concerns
                    logger.info(
                        f"Small image purge requested for timelapse {timelapse_id} but not yet implemented in ThumbnailService"
                    )

            # Invalidate statistics cache since completion changes statistics
            self._invalidate_statistics_cache(timelapse_id)

            # Enhanced statistics coordination (gets fresh data)
            await self._coordinate_statistics_update(timelapse_id, "completion")

            # Create SSE event for completion
            await self.sse_ops.create_event(
                event_type=EVENT_TIMELAPSE_COMPLETED,
                event_data={
                    "timelapse_id": timelapse_id,
                    "camera_id": completed_timelapse.camera_id,
                    "status": completed_timelapse.status,
                    "name": completed_timelapse.name,
                },
                priority=SSEPriority.HIGH,
                source="api",
            )

            LoggingHelper.log_operation_success("complete", "timelapse", timelapse_id)
            return completed_timelapse

        except Exception as e:
            LoggingHelper.log_operation_error("complete", "timelapse", timelapse_id, e)
            raise

    # TODO: Move thumbnail purge functionality to ThumbnailService for proper separation of concerns

    async def get_timelapse_images(
        self, timelapse_id: int, page: int = 1, per_page: int = 50
    ) -> Dict[str, Any]:
        """
        Get images for a specific timelapse with pagination.

        Args:
            timelapse_id: ID of the timelapse
            page: Page number (1-based)
            per_page: Number of images per page

        Returns:
            Dictionary containing images and pagination metadata
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        limit, offset = ValidationHelper.validate_pagination_params(page, per_page)

        try:
            if not self.image_service:
                return ResponseFormatter.error(
                    "Image service not available", error_code="service_unavailable"
                )

            return await self.image_service.get_images(
                timelapse_id=timelapse_id, page=page, page_size=per_page
            )
        except Exception as e:
            LoggingHelper.log_operation_error(
                "get_images", "timelapse", timelapse_id, e
            )
            return ResponseFormatter.error(
                f"Failed to retrieve images for timelapse {timelapse_id}",
                error_code="images_retrieval_failed",
            )

    async def cleanup_completed_timelapses(
        self, retention_days: int = 90
    ) -> Dict[str, Any]:
        """
        Clean up old completed timelapses.

        Args:
            retention_days: Number of days to keep completed timelapses

        Returns:
            Cleanup operation results
        """
        LoggingHelper.log_operation_start(
            "cleanup", "completed timelapses", f"{retention_days} days"
        )

        try:
            deleted_count = await self.timelapse_ops.cleanup_completed_timelapses(
                retention_days
            )

            LoggingHelper.log_operation_success(
                "cleanup",
                "completed timelapses",
                f"{deleted_count} items",
                f"older than {retention_days} days",
            )

            return ResponseFormatter.success(
                f"Cleaned up {deleted_count} completed timelapses",
                data={"deleted_count": deleted_count, "retention_days": retention_days},
            )
        except Exception as e:
            LoggingHelper.log_operation_error(
                "cleanup", "completed timelapses", retention_days, e
            )
            return ResponseFormatter.error(
                "Failed to cleanup completed timelapses", error_code="cleanup_failed"
            )

    async def get_timelapse_video_settings(
        self, timelapse_id: int
    ) -> Optional[TimelapseVideoSettings]:
        """
        Get timelapse video generation settings.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            TimelapseVideoSettings model instance or None if timelapse not found
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        try:
            return await self.timelapse_ops.get_timelapse_settings(timelapse_id)
        except Exception as e:
            LoggingHelper.log_operation_error(
                "get_video_settings", "timelapse", timelapse_id, e
            )
            raise

    async def coordinate_entity_creation(
        self, camera_id: int, timelapse_data: TimelapseCreate
    ) -> Dict[str, Any]:
        """
        Coordinate timelapse entity creation with camera service.

        Args:
            camera_id: ID of the camera to create timelapse for
            timelapse_data: Timelapse creation data

        Returns:
            Creation coordination results
        """
        ValidationHelper.validate_id_parameter(camera_id, "camera")
        LoggingHelper.log_operation_start(
            "coordinate_creation", "timelapse", f"camera_{camera_id}"
        )

        try:
            # Create the timelapse entity
            timelapse = await self.create_new_timelapse(camera_id, timelapse_data)

            # Coordinate with camera service to assign active timelapse
            if self.camera_service:
                await self.camera_service.update_camera(
                    camera_id, {"active_timelapse_id": timelapse.id}
                )

                # Create SSE event for entity coordination
                await self.sse_ops.create_event(
                    event_type="timelapse_entity_created",
                    event_data={
                        "timelapse_id": timelapse.id,
                        "camera_id": camera_id,
                        "status": timelapse.status,
                        "name": timelapse.name,
                    },
                    priority=SSEPriority.NORMAL,
                    source="api",
                )

            LoggingHelper.log_operation_success(
                "coordinate_creation",
                "timelapse",
                timelapse.id,
                f"for camera {camera_id}",
            )

            return ResponseFormatter.success(
                "Timelapse entity created and coordinated successfully",
                data={"timelapse": timelapse.model_dump(), "camera_id": camera_id},
            )

        except Exception as e:
            LoggingHelper.log_operation_error(
                "coordinate_creation", "timelapse", f"camera_{camera_id}", e
            )
            return ResponseFormatter.error(
                "Entity creation coordination failed",
                error_code="coordination_failed",
                details={"camera_id": camera_id, "error": str(e)},
            )

    async def coordinate_entity_completion(self, timelapse_id: int) -> Dict[str, Any]:
        """
        Coordinate timelapse entity completion with services.

        Args:
            timelapse_id: ID of the timelapse to complete

        Returns:
            Completion coordination results
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        LoggingHelper.log_operation_start(
            "coordinate_completion", "timelapse", timelapse_id
        )

        try:
            # Get timelapse details
            timelapse = await self.get_timelapse_by_id(timelapse_id)
            if not timelapse:
                return ResponseFormatter.error(
                    f"Timelapse {timelapse_id} not found",
                    error_code="timelapse_not_found",
                )

            # Complete the timelapse entity
            updated_timelapse = await self.complete_timelapse(timelapse_id)

            # Coordinate with camera service to clear active timelapse
            if self.camera_service:
                await self.camera_service.update_camera(
                    timelapse.camera_id, {"active_timelapse_id": None}
                )

            # Provide data to video automation service for final generation
            if self.video_automation_service:
                await self.video_automation_service.queue_video_generation(
                    timelapse_id=timelapse_id,
                    trigger_type="completion",
                    priority=SSEPriority.HIGH,
                )

            # Calculate final statistics
            final_stats = await self.calculate_statistics_aggregation(timelapse_id)

            LoggingHelper.log_operation_success(
                "coordinate_completion", "timelapse", timelapse_id
            )

            return ResponseFormatter.success(
                "Timelapse entity completed and coordinated successfully",
                data={
                    "timelapse": updated_timelapse.model_dump(),
                    "final_statistics": final_stats,
                },
            )

        except Exception as e:
            LoggingHelper.log_operation_error(
                "coordinate_completion", "timelapse", timelapse_id, e
            )
            return ResponseFormatter.error(
                "Entity completion coordination failed",
                error_code="completion_coordination_failed",
                details={"timelapse_id": timelapse_id, "error": str(e)},
            )

    async def calculate_statistics_aggregation(
        self, timelapse_id: int
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive statistics aggregation for timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Aggregated statistics data
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")

        try:
            # Get basic timelapse statistics
            stats = await self.get_timelapse_statistics(timelapse_id)
            if not stats:
                return {"error": "Statistics not found"}

            # Calculate additional aggregations
            timelapse = await self.get_timelapse_by_id(timelapse_id)
            if timelapse:
                duration_days = 0
                # Calculate duration from start_date to last_capture_at or current time
                if timelapse.start_date:
                    end_date = None
                    if timelapse.last_capture_at:
                        end_date = timelapse.last_capture_at.date()
                    elif timelapse.status == "completed":
                        # Use current date for completed timelapses
                        current_time = await get_timezone_aware_timestamp_async(self.db)
                        end_date = current_time.date()

                    if end_date:
                        duration_days = (end_date - timelapse.start_date).days

                # Images per day calculation using helper
                images_per_day = 0
                if duration_days > 0 and stats.total_images > 0:
                    images_per_day = stats.total_images / duration_days

                # Calculate completion percentage
                completion_rate = 100.0 if timelapse.status == "completed" else 0.0

                # Calculate data quality score using helper
                data_quality_score = MetricsHelper.calculate_percentage(
                    stats.total_images - stats.flagged_images, stats.total_images
                )

                aggregated_stats = {
                    "basic_statistics": stats.model_dump(),
                    "duration_days": duration_days,
                    "images_per_day": round(images_per_day, 2),
                    "completion_rate": completion_rate,
                    "data_quality_score": round(data_quality_score, 2),
                }

                return aggregated_stats

            return {"basic_statistics": stats.model_dump()}

        except Exception as e:
            LoggingHelper.log_operation_error(
                "calculate_statistics", "timelapse", timelapse_id, e
            )
            return {"error": str(e)}

    async def calculate_day_numbers(self, timelapse_id: int) -> Dict[str, Any]:
        """
        Calculate day numbers for timelapse images.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Day number calculation results
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")

        try:
            timelapse = await self.get_timelapse_by_id(timelapse_id)
            if not timelapse or not timelapse.start_date:
                return ResponseFormatter.error(
                    "Timelapse not found or missing start date",
                    error_code="invalid_timelapse",
                )

            if not self.image_service:
                return ResponseFormatter.error(
                    "Image service not available", error_code="service_unavailable"
                )

            # Calculate day numbers based on capture dates
            images = await self.image_service.get_images_for_timelapse(timelapse_id)
            day_calculations = []

            start_date = timelapse.start_date
            for image in images:
                capture_date = image.captured_at.date()
                day_number = (capture_date - start_date).days + 1
                day_calculations.append(
                    {
                        "image_id": image.id,
                        "capture_date": capture_date.isoformat(),
                        "day_number": day_number,
                    }
                )

            return ResponseFormatter.success(
                "Day numbers calculated successfully",
                data={
                    "start_date": start_date.isoformat(),
                    "total_days": len(
                        set(calc["capture_date"] for calc in day_calculations)
                    ),
                    "day_calculations": day_calculations,
                },
            )

        except Exception as e:
            LoggingHelper.log_operation_error(
                "calculate_day_numbers", "timelapse", timelapse_id, e
            )
            return ResponseFormatter.error(
                "Day number calculation failed", error_code="day_calculation_failed"
            )

    async def manage_auto_stop(self, timelapse_id: int) -> Dict[str, Any]:
        """
        Manage auto-stop conditions for timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Auto-stop management results
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")

        try:
            timelapse = await self.get_timelapse_by_id(timelapse_id)
            if not timelapse:
                return ResponseFormatter.error(
                    f"Timelapse {timelapse_id} not found",
                    error_code="timelapse_not_found",
                )

            # Check auto-stop conditions
            should_stop = False
            stop_reason = None

            # Use timezone-aware timestamp
            current_time = await get_timezone_aware_timestamp_async(self.db)

            # Check date-based auto-stop
            if timelapse.auto_stop_at and current_time >= timelapse.auto_stop_at:
                should_stop = True
                stop_reason = "date_reached"

            # Note: max_images field is not available in current model
            # This feature can be implemented when the field is added to the schema

            if should_stop:
                # Coordinate completion
                completion_result = await self.coordinate_entity_completion(
                    timelapse_id
                )

                return ResponseFormatter.success(
                    f"Timelapse auto-stopped: {stop_reason}",
                    data={
                        "auto_stopped": True,
                        "reason": stop_reason,
                        "completion_result": completion_result,
                    },
                )
            else:
                return ResponseFormatter.success(
                    "Timelapse continues running",
                    data={
                        "auto_stopped": False,
                        "continue_until": (
                            timelapse.auto_stop_at.isoformat()
                            if timelapse.auto_stop_at
                            else None
                        ),
                    },
                )

        except Exception as e:
            LoggingHelper.log_operation_error(
                "manage_auto_stop", "timelapse", timelapse_id, e
            )
            return ResponseFormatter.error(
                "Auto-stop management failed", error_code="auto_stop_failed"
            )

    async def track_progress(self, timelapse_id: int) -> Dict[str, Any]:
        """
        Track timelapse progress and provide metrics.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Progress tracking data
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")

        try:
            timelapse = await self.get_timelapse_by_id(timelapse_id)
            if not timelapse:
                return ResponseFormatter.error(
                    f"Timelapse {timelapse_id} not found",
                    error_code="timelapse_not_found",
                )

            # Get current statistics
            stats = await self.get_timelapse_statistics(timelapse_id)
            if not stats:
                return ResponseFormatter.error(
                    "Statistics not available", error_code="stats_unavailable"
                )

            # Use timezone-aware timestamp
            current_time = await get_timezone_aware_timestamp_async(self.db)

            # Calculate progress metrics
            progress_data = {
                "timelapse_id": timelapse_id,
                "status": timelapse.status,
                "current_images": stats.total_images,
                "start_date": (
                    timelapse.start_date.isoformat() if timelapse.start_date else None
                ),
                "current_date": current_time.date().isoformat(),
                "last_capture": (
                    stats.last_capture_at.isoformat() if stats.last_capture_at else None
                ),
            }

            # Calculate completion percentage using helper
            completion_percentage = None

            # Note: max_images field is not available in current model
            # This feature can be implemented when the field is added to the schema

            if timelapse.auto_stop_at and timelapse.start_date:
                # Convert start_date to datetime for comparison with auto_stop_at (datetime)
                start_datetime = datetime.combine(
                    timelapse.start_date, datetime.min.time()
                )
                start_datetime = start_datetime.replace(tzinfo=current_time.tzinfo)

                # Calculate progress based on time duration
                total_duration = timelapse.auto_stop_at - start_datetime
                elapsed_duration = current_time - start_datetime
                total_seconds = total_duration.total_seconds()
                elapsed_seconds = elapsed_duration.total_seconds()

                if total_seconds > 0:
                    completion_percentage = MetricsHelper.calculate_percentage(
                        elapsed_seconds, total_seconds
                    )

            progress_data["completion_percentage"] = completion_percentage

            # Calculate rate metrics
            if timelapse.start_date:
                days_running = (current_time.date() - timelapse.start_date).days + 1
                progress_data["images_per_day"] = stats.total_images / max(
                    days_running, 1
                )
                progress_data["days_running"] = days_running

            return ResponseFormatter.success(
                "Progress tracking data retrieved", data=progress_data
            )

        except Exception as e:
            LoggingHelper.log_operation_error(
                "track_progress", "timelapse", timelapse_id, e
            )
            return ResponseFormatter.error(
                "Progress tracking failed", error_code="progress_tracking_failed"
            )

    async def _monitor_timelapse_health(
        self, timelapse_id: int, operation: str
    ) -> None:
        """
        Enhanced health monitoring integration for timelapse operations.

        Args:
            timelapse_id: ID of the timelapse to monitor
            operation: Type of operation being monitored (creation, completion, etc.)
        """
        try:
            timestamp = await get_timezone_aware_timestamp_async(self.db)

            # Get basic timelapse health metrics
            timelapse = await self.timelapse_ops.get_timelapse_by_id(timelapse_id)
            if not timelapse:
                logger.warning(
                    f"Cannot monitor health for non-existent timelapse {timelapse_id}"
                )
                return

            # Calculate health metrics
            health_data = {
                "timelapse_id": timelapse_id,
                "operation": operation,
                "status": timelapse.status,
                "camera_id": timelapse.camera_id,
                "created_at": (
                    timelapse.created_at.isoformat() if timelapse.created_at else None
                ),
                "health_check_timestamp": timestamp.isoformat(),
            }

            # Create SSE event for health monitoring
            await self.sse_ops.create_event(
                event_type="timelapse_health_monitored",
                event_data=health_data,
                priority=SSEPriority.LOW,
                source="system",
            )

            logger.info(
                f"Timelapse health monitoring completed for {timelapse_id} during {operation}"
            )

        except Exception as e:
            logger.warning(
                f"Failed to monitor timelapse health for {timelapse_id}: {e}"
            )

    async def _coordinate_statistics_update(
        self, timelapse_id: int, trigger: str
    ) -> None:
        """
        Enhanced statistics coordination for timelapse operations.

        Args:
            timelapse_id: ID of the timelapse for statistics update
            trigger: What triggered the statistics update (completion, update, etc.)
        """
        try:
            timestamp = await get_timezone_aware_timestamp_async(self.db)

            # Get fresh timelapse statistics (bypass cache for accurate coordination)
            statistics = await self.get_timelapse_statistics(
                timelapse_id, use_cache=False
            )

            if statistics:
                stats_data = {
                    "timelapse_id": timelapse_id,
                    "trigger": trigger,
                    "statistics": statistics.model_dump(),
                    "update_timestamp": timestamp.isoformat(),
                }

                # Create SSE event for statistics coordination
                await self.sse_ops.create_event(
                    event_type="timelapse_statistics_updated",
                    event_data=stats_data,
                    priority=SSEPriority.LOW,
                    source="system",
                )

                logger.info(
                    f"Statistics coordination completed for timelapse {timelapse_id} via {trigger}"
                )
            else:
                logger.warning(f"No statistics available for timelapse {timelapse_id}")

        except Exception as e:
            logger.warning(
                f"Failed to coordinate statistics update for timelapse {timelapse_id}: {e}"
            )

    # SSE broadcasting methods removed per architectural guidelines
    # Real-time event broadcasting is handled at a higher service layer


class SyncTimelapseService:
    """
    Sync timelapse service for worker processes using composition pattern.

    This service orchestrates timelapse-related business logic using
    dependency injection instead of mixin inheritance.
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize SyncTimelapseService with sync database instance.

        Args:
            db: SyncDatabase instance
        """
        self.db = db
        self.timelapse_ops = SyncTimelapseOperations(db)

    def get_active_timelapse_for_camera(self, camera_id: int) -> Optional[Timelapse]:
        """
        Get the currently active timelapse for a camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Active Timelapse model instance, or None if no active timelapse
        """
        ValidationHelper.validate_id_parameter(camera_id, "camera")
        try:
            return self.timelapse_ops.get_active_timelapse_for_camera(camera_id)
        except Exception as e:
            LoggingHelper.log_operation_error(
                "get_active", "timelapse", f"camera_{camera_id}", e
            )
            raise

    def get_timelapse_by_id(self, timelapse_id: int) -> Optional[Timelapse]:
        """
        Retrieve a specific timelapse by ID.

        Args:
            timelapse_id: ID of the timelapse to retrieve

        Returns:
            Timelapse model instance or None if not found
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        try:
            return self.timelapse_ops.get_timelapse_by_id(timelapse_id)
        except Exception as e:
            LoggingHelper.log_operation_error("retrieve", "timelapse", timelapse_id, e)
            raise

    def update_timelapse_status(
        self,
        timelapse_id: int,
        status: Literal["running", "paused", "completed"],
    ) -> bool:
        """
        Update timelapse status.

        Args:
            timelapse_id: ID of the timelapse
            status: New status ('running', 'paused', 'completed')

        Returns:
            True if update was successful
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        ValidationHelper.validate_enum_value(status, set(TIMELAPSE_STATUSES), "status")

        try:
            return self.timelapse_ops.update_timelapse_status(timelapse_id, status)
        except Exception as e:
            LoggingHelper.log_operation_error(
                "update_status", "timelapse", timelapse_id, e
            )
            return False

    def increment_glitch_count(self, timelapse_id: int) -> bool:
        """
        Increment the glitch count for a timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            True if increment was successful
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        try:
            return self.timelapse_ops.increment_glitch_count(timelapse_id)
        except Exception as e:
            LoggingHelper.log_operation_error(
                "increment_glitch", "timelapse", timelapse_id, e
            )
            return False

    def update_timelapse_last_activity(self, timelapse_id: int) -> bool:
        """
        Update the last activity timestamp for a timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            True if update was successful
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        try:
            return self.timelapse_ops.update_timelapse_last_activity(timelapse_id)
        except Exception as e:
            LoggingHelper.log_operation_error(
                "update_last_activity", "timelapse", timelapse_id, e
            )
            return False

    def _update_timelapse_status_with_logging(
        self,
        timelapse_id: int,
        status: Literal["running", "paused", "completed"],
        action_name: str,
    ) -> bool:
        """
        Helper method to update status with consistent logging.

        Args:
            timelapse_id: ID of the timelapse
            status: New status value
            action_name: Action name for logging

        Returns:
            True if update was successful
        """
        try:
            success = self.update_timelapse_status(timelapse_id, status)
            if success:
                LoggingHelper.log_operation_success(
                    action_name, "timelapse", timelapse_id
                )
            return success
        except Exception as e:
            LoggingHelper.log_operation_error(action_name, "timelapse", timelapse_id, e)
            return False

    def start_timelapse(self, timelapse_id: int) -> bool:
        """
        Start a timelapse by updating its status to 'running' (sync version).

        Args:
            timelapse_id: ID of the timelapse to start

        Returns:
            True if update was successful
        """
        return self._update_timelapse_status_with_logging(
            timelapse_id, "running", "start"
        )

    def pause_timelapse(self, timelapse_id: int) -> bool:
        """
        Pause a timelapse by updating its status to 'paused' (sync version).

        Args:
            timelapse_id: ID of the timelapse to pause

        Returns:
            True if update was successful
        """
        return self._update_timelapse_status_with_logging(
            timelapse_id, "paused", "pause"
        )

    def stop_timelapse(self, timelapse_id: int) -> bool:
        """
        Stop a timelapse by updating its status to 'completed' (sync version).

        Args:
            timelapse_id: ID of the timelapse to stop

        Returns:
            True if update was successful
        """
        return self._update_timelapse_status_with_logging(
            timelapse_id, "completed", "stop"
        )

    def get_timelapses_for_cleanup(
        self, retention_days: int = 90
    ) -> List[TimelapseForCleanup]:
        """
        Get completed timelapses older than retention period.

        Args:
            retention_days: Number of days to keep completed timelapses

        Returns:
            List of TimelapseForCleanup model instances eligible for cleanup
        """
        try:
            return self.timelapse_ops.get_timelapses_for_cleanup(retention_days)
        except Exception as e:
            LoggingHelper.log_operation_error(
                "get_cleanup_candidates", "timelapses", retention_days, e
            )
            raise

    def cleanup_completed_timelapses(self, retention_days: int = 90) -> int:
        """
        Clean up old completed timelapses.

        Args:
            retention_days: Number of days to keep completed timelapses

        Returns:
            Number of timelapses deleted
        """
        LoggingHelper.log_operation_start(
            "cleanup", "completed timelapses", f"{retention_days} days"
        )

        try:
            deleted_count = self.timelapse_ops.cleanup_completed_timelapses(
                retention_days
            )
            LoggingHelper.log_operation_success(
                "cleanup",
                "completed timelapses",
                f"{deleted_count} items",
                f"older than {retention_days} days",
            )
            return deleted_count
        except Exception as e:
            LoggingHelper.log_operation_error(
                "cleanup", "completed timelapses", retention_days, e
            )
            return 0

    def get_timelapse_image_count(self, timelapse_id: int) -> int:
        """
        Get the current image count for a timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Number of images in the timelapse
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        try:
            return self.timelapse_ops.get_timelapse_image_count(timelapse_id)
        except Exception as e:
            LoggingHelper.log_operation_error(
                "get_image_count", "timelapse", timelapse_id, e
            )
            return 0

    def get_timelapse_video_settings(
        self, timelapse_id: int
    ) -> Optional[TimelapseVideoSettings]:
        """
        Get timelapse video generation settings.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            TimelapseVideoSettings model instance or None if timelapse not found
        """
        ValidationHelper.validate_id_parameter(timelapse_id, "timelapse")
        try:
            return self.timelapse_ops.get_timelapse_settings(timelapse_id)
        except Exception as e:
            LoggingHelper.log_operation_error(
                "get_video_settings", "timelapse", timelapse_id, e
            )
            raise

    def create_timelapse(self, timelapse_data: TimelapseCreate) -> Timelapse:
        """
        Create a new timelapse (sync version for worker).

        Args:
            timelapse_data: TimelapseCreate model instance

        Returns:
            Created Timelapse model instance
        """
        LoggingHelper.log_operation_start("create", "timelapse", "sync_worker")

        try:
            created_timelapse = self.timelapse_ops.create_timelapse(timelapse_data)
            LoggingHelper.log_operation_success(
                "create", "timelapse", created_timelapse.id
            )
            return created_timelapse
        except Exception as e:
            LoggingHelper.log_operation_error("create", "timelapse", "sync_worker", e)
            raise
