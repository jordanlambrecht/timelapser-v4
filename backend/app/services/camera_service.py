# backend/app/services/camera_service.py
"""
Camera Service - Composition-based architecture.

This service handles camera-related business logic using dependency injection
for database operations, providing type-safe Pydantic model interfaces.
"""

from typing import List, Optional, Dict, Any
from loguru import logger

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.camera_operations import AsyncCameraOperations, SyncCameraOperations
from ..database.timelapse_operations import TimelapseOperations, SyncTimelapseOperations
from ..database.settings_operations import SettingsOperations, SyncSettingsOperations
from ..utils.cache_manager import cached_response
from ..models.camera_model import (
    Camera,
    CameraWithLastImage,
    CameraWithStats,
    CameraCreate,
    CameraUpdate,
    CameraDetailsResponse,
)
from ..models.timelapse_model import TimelapseCreate, TimelapseUpdate
from ..models.shared_models import (
    CameraHealthStatus,
    CameraStatistics,
    VideoGenerationJob,
    VideoGenerationJobCreate,
    ThumbnailGenerationResult,
    CameraHealthMonitoringResult,
    CameraCaptureScheduleResult,
    CameraConnectivityTestResult,
    CameraCaptureWorkflowResult,
)
from ..models.corruption_model import CorruptionSettingsModel
from ..models.health_model import (
    HealthStatus,
    ComponentHealth,
)
from ..utils.timezone_utils import (
    get_timezone_aware_timestamp_async,
    get_timezone_aware_timestamp_sync,
    get_timezone_aware_timestamp_string_async,
)
from ..utils.timezone_utils import create_time_delta
from ..utils.file_helpers import validate_file_path, ensure_directory_exists
from ..utils.database_helpers import DatabaseUtilities, CommonQueries
from ..database.sse_events_operations import SSEEventsOperations
from ..constants import (
    DEFAULT_CAPTURE_INTERVAL_SECONDS,
    CAMERA_STATUSES,
    CAMERA_NOT_FOUND,
    CAMERA_CONNECTION_FAILED,
    CAMERA_CREATED_SUCCESS,
    CAMERA_UPDATED_SUCCESS,
    CAMERA_DELETED_SUCCESS,
    OPERATION_FAILED,
    HEALTH_STATUSES,
    EVENT_CAMERA_CREATED,
    EVENT_CAMERA_UPDATED,
    EVENT_CAMERA_DELETED,
    EVENT_CAMERA_STATUS_UPDATED,
    EVENT_CAMERA_HEALTH_UPDATED,
    DEFAULT_CAMERA_SERVICE_CACHE_TTL,
    DEFAULT_TIMELAPSE_STANDARD_FPS,
    DEFAULT_TIMELAPSE_FPS_BOUNDS_MIN,
    DEFAULT_TIMELAPSE_FPS_BOUNDS_MAX,
)


class CameraService:
    """
    Camera lifecycle and health management business logic.

    Responsibilities:
    - Camera creation/updates with validation
    - Health monitoring coordination
    - Capture scheduling
    - Connectivity management

    Interactions:
    - Uses CameraOperations for database
    - Calls ImageCaptureService for capture coordination
    - Broadcasts events via database SSE
    """

    def __init__(
        self,
        db: AsyncDatabase,
        settings_service,
        image_capture_service=None,
        corruption_service=None,
    ):
        """
        Initialize CameraService with async database instance, settings service, and service dependencies.

        Args:
            db: AsyncDatabase instance
            settings_service: SettingsService instance
            image_capture_service: Optional ImageCaptureService for capture coordination
            corruption_service: Optional CorruptionService for health monitoring
        """
        self.db = db
        self.settings_service = settings_service
        self.camera_ops = AsyncCameraOperations(db, settings_service)
        self.timelapse_ops = TimelapseOperations(db)
        self.sse_ops = SSEEventsOperations(db)
        self.image_capture_service = image_capture_service
        self.corruption_service = corruption_service

    async def get_cameras(self) -> List[CameraWithStats]:
        """
        Retrieve all cameras with their current status and statistics.

        Returns:
            List of CameraWithStats model instances
        """
        return await self.camera_ops.get_cameras()

    async def get_camera_by_id(self, camera_id: int) -> Optional[CameraWithStats]:
        """
        Retrieve a specific camera by ID.

        Args:
            camera_id: ID of the camera to retrieve

        Returns:
            CameraWithStats model instance, or None if not found
        """
        camera = await self.camera_ops.get_camera_by_id(camera_id)
        if camera is None:
            logger.warning(
                f"Camera not found",
                extra={"camera_id": camera_id, "operation": "get_camera_by_id"},
            )
        else:
            logger.info(
                f"Camera retrieved successfully",
                extra={"camera_id": camera_id, "operation": "get_camera_by_id"},
            )
        return camera

    @cached_response(
        ttl_seconds=DEFAULT_CAMERA_SERVICE_CACHE_TTL, key_prefix="cameras_with_images"
    )
    async def get_cameras_with_images(self) -> List[CameraWithLastImage]:
        """
        Get all cameras with their latest image details.

        CACHED: Results cached for {DEFAULT_CAMERA_SERVICE_CACHE_TTL} seconds to prevent dashboard flooding.

        Returns:
            List of CameraWithLastImage model instances
        """
        logger.debug("🔍 Fetching all cameras with latest images")
        cameras = await self.camera_ops.get_cameras_with_images()
        logger.info(
            f"Retrieved cameras with images",
            extra={"count": len(cameras), "operation": "get_cameras_with_images"},
        )
        return cameras

    async def create_camera(self, camera_data: CameraCreate) -> Camera:
        """
        Create a new camera with business logic orchestration.

        Args:
            camera_data: CameraCreate model instance

        Returns:
            Created Camera model instance

        Raises:
            ValueError: If camera data is invalid
            RuntimeError: If database operation fails
        """
        try:
            # Business Logic: Calculate initial next capture time using timezone-aware utilities
            capture_interval_str = await self.settings_service.get_setting(
                "capture_interval"
            )
            capture_interval = (
                int(capture_interval_str)
                if capture_interval_str
                else DEFAULT_CAPTURE_INTERVAL_SECONDS
            )

            current_time = await get_timezone_aware_timestamp_async(
                self.settings_service
            )
            next_capture_at = current_time + create_time_delta(seconds=capture_interval)

            # Convert model to dict and add next capture time
            camera_dict = camera_data.model_dump()
            camera_data_with_timing = {
                **camera_dict,
                "next_capture_at": next_capture_at,
            }

            # Create camera via database operations (pure CRUD)
            created_camera = await self.camera_ops.create_camera(
                camera_data_with_timing
            )

            # Business Logic: Create SSE event after successful creation
            await self.sse_ops.create_event(
                event_type="camera_created",
                event_data={
                    "camera_id": created_camera.id,
                    "camera_name": created_camera.name,
                    "rtsp_url": created_camera.rtsp_url,
                },
                priority="normal",
                source="api"
            )

            logger.info(
                f"Created camera successfully",
                extra={
                    "camera_id": created_camera.id,
                    "camera_name": created_camera.name,
                    "operation": "create_camera",
                },
            )
            return created_camera

        except Exception as e:
            logger.error(
                f"Failed to create camera",
                extra={
                    "camera_name": camera_data.name,
                    "error": str(e),
                    "operation": "create_camera",
                },
            )
            raise RuntimeError(f"Failed to create camera: {str(e)}") from e

    async def update_camera(self, camera_id: int, camera_data: CameraUpdate) -> Camera:
        """
        Update an existing camera with business logic orchestration.

        Args:
            camera_id: ID of the camera to update
            camera_data: CameraUpdate model instance

        Returns:
            Updated Camera model instance

        Raises:
            ValueError: If camera_id is invalid or camera not found
            RuntimeError: If database operation fails
        """
        try:
            # Convert model to dict for processing
            camera_dict = camera_data.model_dump(exclude_unset=True)

            # Note: capture_interval is a global setting, not a camera attribute
            # If next capture time needs updating, it should be done through schedule_capture method

            # Update camera via database operations (pure CRUD)
            updated_camera = await self.camera_ops.update_camera(camera_id, camera_dict)
            if not updated_camera:
                raise ValueError(CAMERA_NOT_FOUND)

            # Business Logic: Create SSE event after successful update
            await self.sse_ops.create_event(
                event_type="camera_updated",
                event_data={
                    "camera_id": camera_id,
                    "camera_name": updated_camera.name,
                    "changes": camera_dict,
                },
                priority="normal",
                source="api"
            )

            logger.info(
                f"Updated camera successfully",
                extra={
                    "camera_id": camera_id,
                    "camera_name": updated_camera.name,
                    "operation": "update_camera",
                    "updated_fields": list(camera_dict.keys()),
                },
            )
            return updated_camera

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                f"Failed to update camera",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "update_camera",
                },
            )
            raise RuntimeError(f"Failed to update camera: {str(e)}") from e

    async def delete_camera(self, camera_id: int) -> bool:
        """
        Delete a camera with business logic orchestration.

        Args:
            camera_id: ID of the camera to delete

        Returns:
            True if camera was deleted successfully

        Raises:
            ValueError: If camera not found
            RuntimeError: If database operation fails
        """
        try:
            # Business Logic: Get camera details before deletion for event broadcasting
            camera = await self.camera_ops.get_camera_by_id(camera_id)
            if not camera:
                raise ValueError(CAMERA_NOT_FOUND)

            # Delete camera via database operations (pure CRUD)
            success = await self.camera_ops.delete_camera(camera_id)

            if success:
                # Business Logic: Create SSE event after successful deletion
                await self.sse_ops.create_event(
                    event_type="camera_deleted",
                    event_data={
                        "camera_id": camera_id,
                        "camera_name": camera.name,
                    },
                    priority="normal",
                    source="api"
                )

                logger.info(
                    f"Deleted camera successfully",
                    extra={
                        "camera_id": camera_id,
                        "camera_name": camera.name,
                        "operation": "delete_camera",
                    },
                )

            return success

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                f"Failed to delete camera",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "delete_camera",
                },
            )
            raise RuntimeError(f"Failed to delete camera: {str(e)}") from e

    async def update_camera_status(
        self, camera_id: int, status: str, error_message: Optional[str] = None
    ) -> bool:
        """
        Update camera status with business logic orchestration.

        Args:
            camera_id: ID of the camera
            status: New status (must be in CAMERA_STATUSES)
            error_message: Optional error message

        Returns:
            True if status was updated successfully

        Raises:
            ValueError: If status is invalid or camera not found
            RuntimeError: If database operation fails
        """
        try:
            # Validate status against allowed values
            if status not in CAMERA_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Must be one of: {CAMERA_STATUSES}"
                )

            # Update status via database operations (pure CRUD)
            success = await self.camera_ops.update_camera_status(
                camera_id, status, error_message
            )

            if success:
                # Business Logic: Create SSE event after successful status update
                await self.sse_ops.create_event(
                    event_type="camera_status_updated",
                    event_data={
                        "camera_id": camera_id,
                        "status": status,
                        "error_message": error_message,
                    },
                    priority="high",
                    source="api"
                )

                logger.info(
                    f"Updated camera status successfully",
                    extra={
                        "camera_id": camera_id,
                        "new_status": status,
                        "operation": "update_camera_status",
                    },
                )
            else:
                raise ValueError(CAMERA_NOT_FOUND)

            return success

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                f"Failed to update camera status",
                extra={
                    "camera_id": camera_id,
                    "status": status,
                    "error": str(e),
                    "operation": "update_camera_status",
                },
            )
            raise RuntimeError(f"Failed to update camera status: {str(e)}") from e

    async def get_camera_health_status(
        self, camera_id: int
    ) -> Optional[CameraHealthStatus]:
        """
        Get camera health status including corruption detection metrics.

        Args:
            camera_id: ID of the camera

        Returns:
            CameraHealthStatus model instance or None if camera not found
        """
        return await self.camera_ops.get_camera_health_status(camera_id)

    async def get_camera_statistics(self, camera_id: int) -> Optional[CameraStatistics]:
        """
        Get comprehensive camera statistics.

        Args:
            camera_id: ID of the camera

        Returns:
            CameraStatistics model instance or None if camera not found
        """
        return await self.camera_ops.get_camera_stats(camera_id)

    async def update_camera_health(
        self, camera_id: int, health_data: Dict[str, Any]
    ) -> bool:
        """
        Update camera health metrics.

        Args:
            camera_id: ID of the camera
            health_data: Dictionary containing health metrics

        Returns:
            True if health data was updated successfully
        """
        return await self.camera_ops.update_camera_health(camera_id, health_data)

    async def start_new_timelapse(
        self, camera_id: int, timelapse_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new timelapse and set it as the active timelapse for the camera."""
        try:
            logger.info(
                f"Starting new timelapse for camera {camera_id} with data: {timelapse_data}"
            )

            # Validate camera exists
            camera = await self.get_camera_by_id(camera_id)
            if not camera:
                raise ValueError(f"Camera {camera_id} not found")

            # Create TimelapseCreate model from the data, filtering out fields not in the model
            timelapse_create_data = timelapse_data.copy() if timelapse_data else {}

            # Remove fields that will be set automatically or aren't part of TimelapseCreate
            timelapse_create_data.pop("camera_id", None)  # Will be set by the method
            timelapse_create_data.pop("status", None)  # Will be set automatically
            timelapse_create_data.pop("created_at", None)  # Will be set automatically

            # Set camera_id and status correctly for TimelapseBase
            timelapse_create_data["camera_id"] = camera_id
            timelapse_create_data["status"] = "running"

            logger.info(
                f"Creating timelapse with cleaned data: {timelapse_create_data}"
            )

            # Create TimelapseCreate model instance (this will apply defaults)
            timelapse_create = TimelapseCreate(**timelapse_create_data)
            logger.info(
                f"TimelapseCreate model created with defaults: {timelapse_create.model_dump()}"
            )

            # Create timelapse using instance timelapse_ops with correct method
            timelapse = await self.timelapse_ops.create_new_timelapse(
                camera_id, timelapse_create
            )

            logger.info(f"Created timelapse: {timelapse.id}")

            # Update the camera's active timelapse
            await self.camera_ops.update_camera(
                camera_id, {"active_timelapse_id": timelapse.id}
            )

            logger.info(
                f"Updated camera {camera_id} active_timelapse_id to {timelapse.id}"
            )

            # Create SSE event for real-time updates
            await self.sse_ops.create_event(
                event_type="timelapse_started",
                event_data={
                    "camera_id": camera_id,
                    "timelapse_id": timelapse.id,
                },
                priority="normal",
                source="api"
            )

            logger.info(
                f"Successfully started timelapse {timelapse.id} for camera {camera_id}"
            )

            return {
                "success": True,
                "timelapse_id": timelapse.id,
                "message": "Timelapse started successfully",
            }

        except Exception as e:
            logger.error(
                f"Failed to start new timelapse for camera {camera_id}",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "start_new_timelapse",
                    "timelapse_data": timelapse_data,
                },
            )
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to start new timelapse",
            }

    async def pause_active_timelapse(self, camera_id: int) -> Dict[str, Any]:
        """Pause the active timelapse for a camera."""
        try:
            logger.info(f"Starting pause operation for camera {camera_id}")

            # Get the camera with its active timelapse
            camera = await self.get_camera_by_id(camera_id)
            if not camera:
                raise ValueError(f"Camera {camera_id} not found")

            logger.info(
                f"Camera {camera_id} found, active_timelapse_id: {camera.active_timelapse_id}"
            )

            if not camera.active_timelapse_id:
                raise ValueError(f"Camera {camera_id} has no active timelapse")

            # Update the timelapse status using instance timelapse_ops
            timelapse_id = camera.active_timelapse_id
            logger.info(f"Attempting to pause timelapse {timelapse_id}")

            # Provide all required fields for TimelapseUpdate
            timelapse_update = TimelapseUpdate(
                status="paused",
                standard_fps=DEFAULT_TIMELAPSE_STANDARD_FPS,
                min_time_seconds=None,
                max_time_seconds=None,
                target_time_seconds=None,
                fps_bounds_min=DEFAULT_TIMELAPSE_FPS_BOUNDS_MIN,
                fps_bounds_max=DEFAULT_TIMELAPSE_FPS_BOUNDS_MAX,
            )
            await self.timelapse_ops.update_timelapse(timelapse_id, timelapse_update)

            logger.info(
                f"Successfully updated timelapse {timelapse_id} to paused status"
            )

            # Create SSE event for real-time updates
            await self.sse_ops.create_event(
                event_type="timelapse_paused",
                event_data={
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "status": "paused"
                },
                priority="normal",
                source="api"
            )

            return {
                "success": True,
                "timelapse_id": timelapse_id,
                "message": "Timelapse paused successfully",
            }

        except Exception as e:
            logger.error(
                f"Failed to pause timelapse: {str(e)}",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "operation": "pause_active_timelapse",
                },
                exc_info=True,
            )
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to pause timelapse",
            }

    async def resume_active_timelapse(self, camera_id: int) -> Dict[str, Any]:
        """Resume the active timelapse for a camera."""
        try:
            # Get the camera with its active timelapse
            camera = await self.get_camera_by_id(camera_id)
            if not camera:
                raise ValueError(f"Camera {camera_id} not found")

            if not camera.active_timelapse_id:
                raise ValueError(f"Camera {camera_id} has no active timelapse")

            # Update the timelapse status using instance timelapse_ops
            timelapse_id = camera.active_timelapse_id
            timelapse_update = TimelapseUpdate(
                status="running",
                standard_fps=DEFAULT_TIMELAPSE_STANDARD_FPS,
                min_time_seconds=None,
                max_time_seconds=None,
                target_time_seconds=None,
                fps_bounds_min=DEFAULT_TIMELAPSE_FPS_BOUNDS_MIN,
                fps_bounds_max=DEFAULT_TIMELAPSE_FPS_BOUNDS_MAX,
            )
            await self.timelapse_ops.update_timelapse(timelapse_id, timelapse_update)

            # Create SSE event for real-time updates
            await self.sse_ops.create_event(
                event_type="timelapse_resumed",
                event_data={
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "status": "running"
                },
                priority="normal",
                source="api"
            )

            return {
                "success": True,
                "timelapse_id": timelapse_id,
                "message": "Timelapse resumed successfully",
            }

        except Exception as e:
            logger.error(
                f"Failed to resume timelapse",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "resume_active_timelapse",
                },
            )
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to resume timelapse",
            }

    async def stop_active_timelapse(self, camera_id: int) -> Dict[str, Any]:
        """Stop the active timelapse for a camera."""
        try:
            # Get the camera with its active timelapse
            camera = await self.get_camera_by_id(camera_id)
            if not camera:
                raise ValueError(f"Camera {camera_id} not found")

            if not camera.active_timelapse_id:
                raise ValueError(f"Camera {camera_id} has no active timelapse")

            # Update the timelapse status using timelapse operations
            timelapse_id = camera.active_timelapse_id
            timelapse_update = TimelapseUpdate(
                status="completed",
                standard_fps=DEFAULT_TIMELAPSE_STANDARD_FPS,
                min_time_seconds=None,
                max_time_seconds=None,
                target_time_seconds=None,
                fps_bounds_min=DEFAULT_TIMELAPSE_FPS_BOUNDS_MIN,
                fps_bounds_max=DEFAULT_TIMELAPSE_FPS_BOUNDS_MAX,
            )
            await self.timelapse_ops.update_timelapse(timelapse_id, timelapse_update)

            # Create SSE event for real-time updates
            await self.sse_ops.create_event(
                event_type="timelapse_stopped",
                event_data={
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "status": "completed"
                },
                priority="normal",
                source="api"
            )

            return {
                "success": True,
                "timelapse_id": timelapse_id,
                "message": "Timelapse stopped successfully",
            }

        except Exception as e:
            logger.error(
                f"Failed to stop timelapse",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "stop_active_timelapse",
                },
            )
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to stop timelapse",
            }

    async def complete_active_timelapse(self, camera_id: int) -> Dict[str, Any]:
        """Complete the active timelapse for a camera, marking it as a historical record."""
        try:
            # Get the camera with its active timelapse
            camera = await self.get_camera_by_id(camera_id)
            if not camera:
                raise ValueError(f"Camera {camera_id} not found")

            if not camera.active_timelapse_id:
                raise ValueError(f"Camera {camera_id} has no active timelapse")

            # Update the timelapse status using instance timelapse_ops
            timelapse_id = camera.active_timelapse_id
            timelapse_update = TimelapseUpdate(
                status="completed",
                standard_fps=DEFAULT_TIMELAPSE_STANDARD_FPS,
                min_time_seconds=None,
                max_time_seconds=None,
                target_time_seconds=None,
                fps_bounds_min=DEFAULT_TIMELAPSE_FPS_BOUNDS_MIN,
                fps_bounds_max=DEFAULT_TIMELAPSE_FPS_BOUNDS_MAX,
            )
            await self.timelapse_ops.update_timelapse(timelapse_id, timelapse_update)

            # Clear the active timelapse from the camera
            await self.camera_ops.update_camera(
                camera_id, {"active_timelapse_id": None}
            )

            # Create SSE event for real-time updates
            await self.sse_ops.create_event(
                event_type="timelapse_completed",
                event_data={
                    "camera_id": camera_id,
                    "timelapse_id": timelapse_id,
                    "status": "completed"
                },
                priority="high",
                source="api"
            )

            return {
                "success": True,
                "timelapse_id": timelapse_id,
                "message": "Timelapse completed successfully",
            }

        except Exception as e:
            logger.error(
                f"Failed to complete timelapse",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "complete_active_timelapse",
                },
            )
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to complete timelapse",
            }

    async def coordinate_health_monitoring(
        self, camera_id: int
    ) -> CameraHealthMonitoringResult:
        """
        Coordinate health monitoring with corruption service.

        Args:
            camera_id: ID of the camera to monitor

        Returns:
            CameraHealthMonitoringResult with health monitoring results

        Raises:
            ValueError: If camera not found
            RuntimeError: If monitoring fails
        """
        try:
            # Get basic camera health
            health_status = await self.get_camera_health_status(camera_id)
            if not health_status:
                raise ValueError(CAMERA_NOT_FOUND)

            # Coordinate with corruption service if available
            corruption_analysis = None
            if self.corruption_service:
                corruption_analysis = (
                    await self.corruption_service.assess_camera_health(camera_id)
                )

            # Generate timezone-aware timestamp for monitoring
            monitoring_timestamp = await get_timezone_aware_timestamp_async(
                self.settings_service
            )

            # Update camera health metrics
            health_data = {
                "basic_health": health_status.model_dump(),
                "corruption_analysis": corruption_analysis,
                "monitoring_timestamp": monitoring_timestamp.isoformat(),
            }
            await self.update_camera_health(camera_id, health_data)

            return CameraHealthMonitoringResult(
                success=True,
                camera_id=camera_id,
                basic_health=health_status,
                corruption_analysis=corruption_analysis,
                monitoring_timestamp=monitoring_timestamp,
            )

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                f"Health monitoring coordination failed",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "coordinate_health_monitoring",
                },
            )

            monitoring_timestamp = await get_timezone_aware_timestamp_async(
                self.settings_service
            )

            return CameraHealthMonitoringResult(
                success=False,
                camera_id=camera_id,
                monitoring_timestamp=monitoring_timestamp,
                error=str(e),
            )

    async def schedule_capture(self, camera_id: int) -> CameraCaptureScheduleResult:
        """
        Schedule image capture coordination with ImageCaptureService.

        Args:
            camera_id: ID of the camera to schedule capture for

        Returns:
            CameraCaptureScheduleResult with scheduling results

        Raises:
            ValueError: If camera not found
            RuntimeError: If scheduling fails
        """
        try:
            # Get camera details for scheduling
            camera = await self.get_camera_by_id(camera_id)
            if not camera:
                raise ValueError(CAMERA_NOT_FOUND)

            current_time = await get_timezone_aware_timestamp_async(
                self.settings_service
            )

            # Coordinate with image capture service if available
            if self.image_capture_service:
                capture_result = await self.image_capture_service.schedule_capture(
                    camera_id, camera.rtsp_url
                )

                # Update next capture time based on global interval setting using timezone utilities
                if capture_result.get("success"):
                    # Get capture interval from global settings
                    capture_interval_str = await self.settings_service.get_setting(
                        "capture_interval"
                    )
                    capture_interval = (
                        int(capture_interval_str)
                        if capture_interval_str
                        else DEFAULT_CAPTURE_INTERVAL_SECONDS
                    )

                    next_capture = current_time + create_time_delta(
                        seconds=capture_interval
                    )
                    await self.camera_ops.update_camera_next_capture_time(
                        camera_id, next_capture
                    )

                    return CameraCaptureScheduleResult(
                        success=True,
                        camera_id=camera_id,
                        scheduled_at=current_time,
                        next_capture_at=next_capture,
                        message="Capture scheduled successfully",
                    )
                else:
                    return CameraCaptureScheduleResult(
                        success=False,
                        camera_id=camera_id,
                        scheduled_at=current_time,
                        message="Failed to schedule capture",
                        error=capture_result.get(
                            "error", "Unknown capture scheduling error"
                        ),
                    )
            else:
                logger.warning(
                    f"ImageCaptureService not available for camera scheduling",
                    extra={"camera_id": camera_id, "operation": "schedule_capture"},
                )
                return CameraCaptureScheduleResult(
                    success=False,
                    camera_id=camera_id,
                    scheduled_at=current_time,
                    message="ImageCaptureService not configured",
                    error="ImageCaptureService not configured",
                )

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                f"Capture scheduling failed",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "schedule_capture",
                },
            )

            current_time = await get_timezone_aware_timestamp_async(
                self.settings_service
            )

            return CameraCaptureScheduleResult(
                success=False,
                camera_id=camera_id,
                scheduled_at=current_time,
                message="Capture scheduling failed",
                error=str(e),
            )

    async def test_connectivity(self, camera_id: int) -> CameraConnectivityTestResult:
        """
        Test RTSP connectivity for camera.

        Args:
            camera_id: ID of the camera to test

        Returns:
            CameraConnectivityTestResult with connectivity test results

        Raises:
            ValueError: If camera not found
            RuntimeError: If test fails
        """
        try:
            # Get camera details
            camera = await self.get_camera_by_id(camera_id)
            if not camera:
                raise ValueError(CAMERA_NOT_FOUND)

            test_timestamp = await get_timezone_aware_timestamp_async(
                self.settings_service
            )

            # Test RTSP connection via image capture service
            if self.image_capture_service:
                connectivity_result = (
                    await self.image_capture_service.test_rtsp_connection(
                        camera_id, camera.rtsp_url
                    )
                )

                success = connectivity_result.success
                response_time = connectivity_result.response_time_ms

                # Update camera status based on connectivity
                if success:
                    await self.update_camera_status(camera_id, "active")
                    connection_status = "connected"
                else:
                    await self.update_camera_status(
                        camera_id,
                        "error",
                        connectivity_result.error or "RTSP connection failed",
                    )
                    connection_status = "failed"

                return CameraConnectivityTestResult(
                    success=success,
                    camera_id=camera_id,
                    rtsp_url=camera.rtsp_url,
                    response_time_ms=response_time,
                    connection_status=connection_status,
                    error=connectivity_result.error if not success else None,
                    test_timestamp=test_timestamp,
                )
            else:
                logger.warning(
                    f"ImageCaptureService not available for connectivity test",
                    extra={"camera_id": camera_id, "operation": "test_connectivity"},
                )
                return CameraConnectivityTestResult(
                    success=False,
                    camera_id=camera_id,
                    rtsp_url=camera.rtsp_url,
                    connection_status="service_unavailable",
                    error="ImageCaptureService not configured",
                    test_timestamp=test_timestamp,
                )

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                f"Connectivity test failed",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "test_connectivity",
                },
            )

            test_timestamp = await get_timezone_aware_timestamp_async(
                self.settings_service
            )
            camera = await self.get_camera_by_id(camera_id)
            rtsp_url = camera.rtsp_url if camera else "unknown"

            return CameraConnectivityTestResult(
                success=False,
                camera_id=camera_id,
                rtsp_url=rtsp_url,
                connection_status="test_failed",
                error=str(e),
                test_timestamp=test_timestamp,
            )

    async def coordinate_capture_workflow(
        self, camera_id: int
    ) -> CameraCaptureWorkflowResult:
        """
        Coordinate complete capture workflow including health checks and scheduling.

        Args:
            camera_id: ID of the camera

        Returns:
            CameraCaptureWorkflowResult with complete workflow results

        Raises:
            ValueError: If camera not found
        """
        try:
            # 1. Test connectivity first
            connectivity = await self.test_connectivity(camera_id)
            if not connectivity.success:
                # Early return if connectivity fails
                monitoring_timestamp = await get_timezone_aware_timestamp_async(
                    self.settings_service
                )
                health_monitoring = CameraHealthMonitoringResult(
                    success=False,
                    camera_id=camera_id,
                    monitoring_timestamp=monitoring_timestamp,
                    error="Skipped due to connectivity failure",
                )
                capture_scheduling = CameraCaptureScheduleResult(
                    success=False,
                    camera_id=camera_id,
                    scheduled_at=monitoring_timestamp,
                    message="Skipped due to connectivity failure",
                    error="Connectivity test failed",
                )

                return CameraCaptureWorkflowResult(
                    workflow_status="failed",
                    camera_id=camera_id,
                    connectivity=connectivity,
                    health_monitoring=health_monitoring,
                    capture_scheduling=capture_scheduling,
                    overall_success=False,
                    error="Connectivity test failed",
                )

            # 2. Coordinate health monitoring
            health_monitoring = await self.coordinate_health_monitoring(camera_id)
            if not health_monitoring.success:
                logger.warning(
                    f"Health monitoring issues for camera",
                    extra={
                        "camera_id": camera_id,
                        "error": health_monitoring.error,
                        "operation": "coordinate_capture_workflow",
                    },
                )

            # 3. Schedule capture if connectivity is good
            capture_scheduling = await self.schedule_capture(camera_id)

            # Determine overall workflow status
            overall_success = connectivity.success and capture_scheduling.success
            workflow_status = "completed" if overall_success else "partial"

            return CameraCaptureWorkflowResult(
                workflow_status=workflow_status,
                camera_id=camera_id,
                connectivity=connectivity,
                health_monitoring=health_monitoring,
                capture_scheduling=capture_scheduling,
                overall_success=overall_success,
            )

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                f"Capture workflow coordination failed",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "coordinate_capture_workflow",
                },
            )

            # Create error result with minimal data
            monitoring_timestamp = await get_timezone_aware_timestamp_async(
                self.settings_service
            )
            error_connectivity = CameraConnectivityTestResult(
                success=False,
                camera_id=camera_id,
                rtsp_url="unknown",
                connection_status="workflow_failed",
                error=str(e),
                test_timestamp=monitoring_timestamp,
            )
            error_health = CameraHealthMonitoringResult(
                success=False,
                camera_id=camera_id,
                monitoring_timestamp=monitoring_timestamp,
                error=str(e),
            )
            error_capture = CameraCaptureScheduleResult(
                success=False,
                camera_id=camera_id,
                scheduled_at=monitoring_timestamp,
                message="Workflow failed",
                error=str(e),
            )

            return CameraCaptureWorkflowResult(
                workflow_status="failed",
                camera_id=camera_id,
                connectivity=error_connectivity,
                health_monitoring=error_health,
                capture_scheduling=error_capture,
                overall_success=False,
                error=str(e),
            )


class SyncCameraService:
    """
    Sync camera service for worker processes using composition pattern.

    This service orchestrates camera-related business logic using
    dependency injection instead of mixin inheritance.
    """

    def __init__(self, db: SyncDatabase, image_capture_service=None):
        """
        Initialize SyncCameraService with sync database instance.

        Args:
            db: SyncDatabase instance
            image_capture_service: Optional ImageCaptureService for RTSP testing
        """
        self.db = db
        self.camera_ops = SyncCameraOperations(db)
        self.timelapse_ops = SyncTimelapseOperations(db)
        self.settings_ops = SyncSettingsOperations(db)
        self.image_capture_service = image_capture_service

    def get_active_cameras(self) -> List[Camera]:
        """
        Retrieve all enabled cameras for worker processing.

        Returns:
            List of enabled Camera model instances
        """
        return self.camera_ops.get_active_cameras()
    
    def get_cameras_with_running_timelapses(self) -> List[Camera]:
        """
        Retrieve cameras that have active running timelapses.
        
        Returns:
            List of Camera model instances with running timelapses
        """
        return self.camera_ops.get_cameras_with_running_timelapses()

    def get_camera_by_id(self, camera_id: int) -> Optional[Camera]:
        """
        Retrieve a specific camera by ID.

        Args:
            camera_id: ID of the camera to retrieve

        Returns:
            Camera model instance or None if not found
        """
        return self.camera_ops.get_camera_by_id(camera_id)

    def update_camera_connectivity(
        self, camera_id: int, is_connected: bool, error_message: Optional[str] = None
    ) -> bool:
        """
        Update camera connectivity status.

        Args:
            camera_id: ID of the camera
            is_connected: Whether camera is currently connected
            error_message: Optional error message if disconnected

        Returns:
            True if update was successful
        """
        return self.camera_ops.update_camera_connectivity(
            camera_id, is_connected, error_message
        )

    def test_connectivity(self, camera_id: int) -> CameraConnectivityTestResult:
        """
        Test RTSP connectivity for camera (sync version for worker).

        Args:
            camera_id: ID of the camera to test

        Returns:
            CameraConnectivityTestResult with connectivity test results

        Raises:
            ValueError: If camera not found
        """
        try:
            # Get camera details
            camera = self.get_camera_by_id(camera_id)
            if not camera:
                raise ValueError(CAMERA_NOT_FOUND)

            test_timestamp = get_timezone_aware_timestamp_sync(self.db)

            # Use ImageCaptureService for actual RTSP testing if available
            if self.image_capture_service:
                return self.image_capture_service.test_camera_connection(camera_id)
            else:
                # Fallback if service not available
                logger.warning(
                    f"ImageCaptureService not available for camera {camera_id} connectivity test"
                )
                return CameraConnectivityTestResult(
                    success=False,
                    camera_id=camera_id,
                    rtsp_url=camera.rtsp_url,
                    response_time_ms=None,
                    connection_status="service_unavailable",
                    error="ImageCaptureService not configured for connectivity testing",
                    test_timestamp=test_timestamp,
                )

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to test connectivity for camera {camera_id}: {e}")
            return CameraConnectivityTestResult(
                success=False,
                camera_id=camera_id,
                rtsp_url="",
                response_time_ms=None,
                connection_status="failed",
                error=str(e),
                test_timestamp=get_timezone_aware_timestamp_sync(self.db),
            )

    def update_next_capture_time(self, camera_id: int) -> bool:
        """
        Update the next capture time for a camera using timezone-aware calculations.

        Args:
            camera_id: ID of the camera

        Returns:
            True if update was successful

        Raises:
            ValueError: If camera not found
            RuntimeError: If database operation fails
        """
        try:
            # Get current timezone-aware timestamp
            current_time = get_timezone_aware_timestamp_sync(self.db)

            # Get capture interval from global settings
            capture_interval_str = self.settings_ops.get_setting(
                "capture_interval", str(DEFAULT_CAPTURE_INTERVAL_SECONDS)
            )
            capture_interval = (
                int(capture_interval_str)
                if capture_interval_str
                else DEFAULT_CAPTURE_INTERVAL_SECONDS
            )

            # Calculate next capture time
            next_capture_at = current_time + create_time_delta(seconds=capture_interval)

            success = self.camera_ops.update_next_capture_time(
                camera_id, next_capture_at
            )
            if not success:
                raise ValueError(CAMERA_NOT_FOUND)

            return success

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                f"Failed to update next capture time",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "update_next_capture_time",
                },
            )
            raise RuntimeError(f"Failed to update next capture time: {str(e)}") from e

    def get_camera_corruption_settings(
        self, camera_id: int
    ) -> Optional[CorruptionSettingsModel]:
        """
        Get camera-specific corruption detection settings.

        Args:
            camera_id: ID of the camera

        Returns:
            CorruptionSettingsModel instance, or None if not found
        """
        return self.camera_ops.get_camera_corruption_settings(camera_id)

    def update_camera_corruption_failure_count(
        self, camera_id: int, increment: bool = True
    ) -> bool:
        """
        Update camera corruption failure counters.

        Args:
            camera_id: ID of the camera
            increment: Whether to increment (True) or reset (False) counters

        Returns:
            True if update was successful
        """
        return self.camera_ops.update_camera_corruption_failure_count(
            camera_id, increment
        )

    def set_camera_degraded_mode(self, camera_id: int, is_degraded: bool) -> bool:
        """
        Set camera degraded mode status.

        Args:
            camera_id: ID of the camera
            is_degraded: Whether camera should be in degraded mode

        Returns:
            True if update was successful
        """
        return self.camera_ops.set_camera_degraded_mode(camera_id, is_degraded)

    def reset_camera_corruption_failures(self, camera_id: int) -> bool:
        """
        Reset camera corruption failure counters.

        Args:
            camera_id: ID of the camera

        Returns:
            True if reset was successful

        Raises:
            ValueError: If camera not found
            RuntimeError: If database operation fails
        """
        try:
            success = self.camera_ops.reset_camera_corruption_failures(camera_id)
            if not success:
                raise ValueError(CAMERA_NOT_FOUND)

            logger.info(
                f"Reset corruption failures for camera",
                extra={
                    "camera_id": camera_id,
                    "operation": "reset_corruption_failures",
                },
            )
            return success

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                f"Failed to reset corruption failures",
                extra={
                    "camera_id": camera_id,
                    "error": str(e),
                    "operation": "reset_corruption_failures",
                },
            )
            raise RuntimeError(f"Failed to reset corruption failures: {str(e)}") from e

    def get_cameras_ready_for_capture(self) -> List[Camera]:
        """
        Get all cameras that are ready for image capture.

        Returns cameras that are:
        - Active status
        - Have running timelapses
        - Are due for capture (next_capture_at <= now)
        - Not in degraded mode or have corruption detection enabled

        Returns:
            List of Camera model instances ready for capture
        """
        try:
            return self.camera_ops.get_cameras_ready_for_capture()
        except Exception as e:
            logger.error(
                f"Failed to get cameras ready for capture",
                extra={"error": str(e), "operation": "get_cameras_ready_for_capture"},
            )
            # Return empty list rather than failing entirely
            return []

    def update_camera_capture_stats(
        self, camera_id: int, success: bool, error_message: Optional[str] = None
    ) -> bool:
        """
        Update camera capture statistics after a capture attempt.

        Args:
            camera_id: ID of the camera
            success: Whether the capture was successful
            error_message: Optional error message if capture failed

        Returns:
            True if stats were updated successfully
        """
        try:
            success_result = self.camera_ops.update_camera_capture_stats(
                camera_id, success, error_message
            )

            if success_result:
                logger.debug(
                    f"Updated capture stats for camera",
                    extra={
                        "camera_id": camera_id,
                        "capture_success": success,
                        "operation": "update_capture_stats",
                    },
                )

            return success_result

        except Exception as e:
            logger.error(
                f"Failed to update capture stats",
                extra={
                    "camera_id": camera_id,
                    "capture_success": success,
                    "error": str(e),
                    "operation": "update_capture_stats",
                },
            )
            # Don't raise exception for stats updates to avoid blocking captures
            return False
