# backend/app/services/camera_service.py
"""
Camera Service - Camera Entity Management

🎯 SERVICE SCOPE: Anything that involves MANAGING CAMERA ENTITIES
- Camera CRUD operations (create, read, update, delete)
- Camera status and health management
- Camera metadata and statistics
- Camera connectivity status updates (for entity health)
- Camera scheduling metadata (next_capture_at, intervals)
- Camera business logic orchestration
- SSE event broadcasting for camera changes

📝 KEY DISTINCTION FROM RTSPService:
- CameraService = "MANAGE camera entity" (CRUD/status/metadata)
- RTSPService = "DO something with RTSP/camera" (actions/verbs)

⚠️  NOT responsible for:
- Actual RTSP frame capture operations
- Image processing or file saving
- Direct OpenCV/RTSP interactions
- Capture workflow execution

🔗 COORDINATION: Uses RTSPService for connectivity testing to update camera health status,
but delegates all actual capture actions to RTSPService.

Architecture: Composition-based with dependency injection for type-safe operations.
"""

from typing import Any, Dict, List, Optional

from ..constants import (  # Camera health constants
    CAMERA_CAPTURE_READY_STATUSES,
    CAMERA_HEALTH_DEGRADED,
    CAMERA_HEALTH_DEGRADED_THRESHOLD,
    CAMERA_HEALTH_FAILURE_THRESHOLD,
    CAMERA_HEALTH_OFFLINE,
    CAMERA_HEALTH_ONLINE,
    CAMERA_NOT_FOUND,
    CAMERA_STATUSES,
    CAMERA_TIMELAPSE_READY_STATUSES,
)

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.exceptions import CameraOperationError

from ..enums import (
    JobPriority,
    LoggerName,
    LogSource,
    SSEEvent,
    SSEPriority,
    TimelapseAction,
    TimelapseStatus,
)
from ..models.camera_action_models import TimelapseActionRequest

# SettingsOperations import removed - using injected SettingsService instead
from ..models.camera_model import (
    Camera,
    CameraCreate,
    CameraUpdate,
    CropRotationSettings,
    CropRotationUpdate,
    SourceResolution,
)
from ..models.corruption_model import CorruptionSettingsModel
from ..models.shared_models import (
    CameraCaptureScheduleResult,
    CameraCaptureWorkflowResult,
    CameraConnectivityTestResult,
    CameraHealthMonitoringResult,
    CameraHealthStatus,
    CameraStatistics,
)
from ..models.timelapse_model import TimelapseCreate, TimelapseUpdate
from ..services.logger import get_service_logger
from ..utils.time_utils import (
    get_timezone_aware_timestamp_async,
    get_timezone_aware_timestamp_sync,
)
from ..utils.validation_helpers import (
    validate_camera_exists,
)

# from ..services.capture_pipeline.rtsp_utils import detect_source_resolution


# Use recommended service logger factory pattern
logger = get_service_logger(LoggerName.CAMERA_SERVICE, LogSource.SYSTEM)


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
    - Uses RTSPService for RTSP connectivity testing
    - Broadcasts events via database SSE
    """

    def __init__(
        self,
        db: AsyncDatabase,
        sync_db: SyncDatabase,
        settings_service,
        camera_ops,
        timelapse_ops,
        sse_ops,
        rtsp_service=None,
        # corruption_service=None,  # Removed - using corruption_pipeline
        scheduling_service=None,
        timelapse_service=None,
        scheduler_authority_service=None,
    ):
        """
        Initialize CameraService with injected dependencies.

        Args:
            db: AsyncDatabase instance
            sync_db: SyncDatabase instance
            settings_service: SettingsService instance
            camera_ops: Injected AsyncCameraOperations singleton
            timelapse_ops: Injected TimelapseOperations singleton
            sse_ops: Injected SSEEventsOperations singleton
            rtsp_service: Optional AsyncRTSPService for RTSP operations
            # corruption_service: Optional CorruptionService for health monitoring (removed)
            scheduling_service: Optional SchedulingService for capture scheduling
            timelapse_service: Optional TimelapseService for timelapse operations
        """
        self.db = db
        self.settings_service = settings_service
        self.camera_ops = camera_ops
        self.timelapse_ops = timelapse_ops
        self.sse_ops = sse_ops
        self.rtsp_service = rtsp_service
        # self.corruption_service = corruption_service  # Removed
        self.scheduling_service = scheduling_service
        self.scheduler_authority_service = scheduler_authority_service
        self.timelapse_service = timelapse_service

    # ====================================================================
    # BUSINESS LOGIC HELPER METHODS
    # ====================================================================

    def determine_camera_health_status(self, consecutive_failures: int) -> str:
        """
        Determine camera health status based on consecutive failures.

        Business logic moved from database layer to service layer.

        Args:
            consecutive_failures: Number of consecutive capture failures

        Returns:
            Health status string (online, degraded, offline)
        """
        if consecutive_failures == 0:
            return CAMERA_HEALTH_ONLINE
        elif consecutive_failures < CAMERA_HEALTH_FAILURE_THRESHOLD:
            return CAMERA_HEALTH_DEGRADED
        else:
            return CAMERA_HEALTH_OFFLINE

    def is_camera_capture_ready(
        self,
        camera_status: str,
        timelapse_status: Optional[str],
        degraded_mode_active: bool,
        corruption_detection_heavy: bool,
    ) -> bool:
        """
        Determine if camera is ready for capture based on business rules.

        Business logic moved from database layer to service layer.

        Args:
            camera_status: Camera status (active, inactive, etc.)
            timelapse_status: Timelapse status (running, paused, etc.)
            degraded_mode_active: Whether camera is in degraded mode
            corruption_detection_heavy: Whether corruption detection is enabled

        Returns:
            True if camera is ready for capture
        """
        # Check basic status requirements
        if camera_status not in CAMERA_CAPTURE_READY_STATUSES:
            return False

        if timelapse_status not in CAMERA_TIMELAPSE_READY_STATUSES:
            return False

        # Check degraded mode requirements
        if degraded_mode_active and not corruption_detection_heavy:
            return False

        return True

    def should_update_health_to_degraded(self, consecutive_failures: int) -> bool:
        """
        Determine if camera health should be updated to degraded status.

        Args:
            consecutive_failures: Current consecutive failure count

        Returns:
            True if health should be marked as degraded
        """
        return consecutive_failures >= CAMERA_HEALTH_DEGRADED_THRESHOLD

    def should_update_health_to_offline(self, consecutive_failures: int) -> bool:
        """
        Determine if camera health should be updated to offline status.

        Args:
            consecutive_failures: Current consecutive failure count

        Returns:
            True if health should be marked as offline
        """
        return consecutive_failures >= CAMERA_HEALTH_FAILURE_THRESHOLD

    # ====================================================================
    # CAMERA CRUD OPERATIONS
    # ====================================================================

    async def get_cameras(self) -> List[Camera]:
        """
        Retrieve all cameras with their current status and statistics.

        Returns:
            List of Camera model instances (unified camera model with stats)
        """
        try:
            return await self.camera_ops.get_cameras()
        except CameraOperationError as e:
            logger.error(f"Database error retrieving cameras: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving cameras: {e}")
            raise

    async def get_active_cameras(self) -> List[Camera]:
        """
        Retrieve all active/enabled cameras for health monitoring.

        Returns:
            List of active Camera model instances
        """
        try:
            all_cameras = await self.camera_ops.get_cameras()
            # Filter for active cameras only
            active_cameras = [
                camera for camera in all_cameras if camera.status == "active"
            ]
            return active_cameras
        except CameraOperationError as e:
            logger.error(f"Database error retrieving active cameras: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving active cameras: {e}")
            raise

    async def get_camera_by_id(self, camera_id: int) -> Optional[Camera]:
        """
        Retrieve a specific camera by ID.

        Args:
            camera_id: ID of the camera to retrieve

        Returns:
            Camera model instance (unified camera model with stats), or None if not found
        """
        try:
            camera = await self.camera_ops.get_camera_by_id(camera_id)
        except CameraOperationError as e:
            logger.error(f"Database error retrieving camera {camera_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving camera {camera_id}: {e}")
            raise
        if camera is None:
            logger.warning(
                "Camera not found",
                extra_context={"camera_id": camera_id, "operation": "get_camera_by_id"},
            )
        else:
            logger.info(
                "Camera retrieved successfully",
                extra_context={"camera_id": camera_id, "operation": "get_camera_by_id"},
            )
        return camera

    # Private helper methods for common patterns
    async def _broadcast_camera_event(
        self, event_type: str, camera_id: int, **event_data
    ):
        """Helper method to broadcast camera-related SSE events with consistent structure."""
        await self.sse_ops.create_event(
            event_type=event_type,
            event_data={"camera_id": camera_id, **event_data},
        )

    async def _broadcast_timelapse_status_event(
        self, timelapse_id: int, camera_id: int, status: str, **extra_data
    ):
        """Helper method to broadcast timelapse status change events."""
        event_data = {
            "timelapse_id": timelapse_id,
            "camera_id": camera_id,
            "status": status,
            **extra_data,
        }
        await self.sse_ops.create_event(
            event_type=SSEEvent.TIMELAPSE_STATUS_UPDATED,
            event_data=event_data,
        )

    async def _broadcast_scheduler_event(
        self, event_data: dict, priority: str = JobPriority.MEDIUM
    ):
        """Helper method to broadcast scheduler-related events."""
        await self.sse_ops.create_event(
            event_type=SSEEvent.SYSTEM_INFO,
            event_data=event_data,
            priority=priority,
        )

    async def _get_current_timestamp(self):
        """Helper method to get timezone-aware current timestamp."""
        return await get_timezone_aware_timestamp_async(self.settings_service)

    async def get_comprehensive_status(
        self, camera_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive camera status including connectivity test results.
        This method uses the existing database operation and adds real-time connectivity.

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary with comprehensive status information, or None if camera not found
        """
        # Use existing database method for comprehensive status
        return await self.camera_ops.get_camera_comprehensive_status(camera_id)

    async def create_camera(self, camera_data: CameraCreate) -> Camera:
        # If source_resolution is not provided, fetch it from RTSP
        # if not getattr(camera_data, "source_resolution", None):

        #     width, height = detect_source_resolution(camera_data.rtsp_url)
        #     if width > 0 and height > 0:
        #         camera_data.source_resolution = {"width": width, "height": height}
        #         await self.log.log_system(
        #             f"📷 Detected source resolution for camera '{camera_data.name}': {width}x{height}",
        #             level=LogLevel.INFO,
        #
        #             logger_name=LoggerName.CAMERA_SERVICE
        #         )
        #     else:
        #         await self.log.log_error(
        #             f"Could not detect source resolution for camera: {camera_data.name} ({camera_data.rtsp_url})",
        #             level=LogLevel.ERROR,
        #
        #             logger_name=LoggerName.CAMERA_SERVICE
        #         )
        #         camera_data.source_resolution = {"width": 0, "height": 0}

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
            # Business Logic: Initial next capture time will be set when timelapse is created
            # No need to calculate here since intervals are timelapse-specific
            next_capture_at = None

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

            # Broadcast SSE event for camera creation
            await self._broadcast_camera_event(
                SSEEvent.CAMERA_CREATED,
                created_camera.id,
                camera_name=created_camera.name,
                rtsp_url=created_camera.rtsp_url,
            )

            logger.info(
                "Created camera successfully",
                extra_context={
                    "camera_id": created_camera.id,
                    "camera_name": created_camera.name,
                    "operation": "create_camera",
                },
            )
            return created_camera

        except CameraOperationError as e:
            logger.error(
                f"Database error creating camera '{camera_data.name}': {e}",
                error_context={
                    "camera_name": camera_data.name,
                    "operation": "create_camera",
                },
            )
            raise
        except Exception as e:
            logger.error(
                "Failed to create camera",
                error_context={
                    "camera_name": camera_data.name,
                    "operation": "create_camera",
                },
                exception=e,
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

            # Note: capture intervals are now timelapse-specific, not camera or global settings

            # Update camera via database operations (pure CRUD)
            updated_camera = await self.camera_ops.update_camera(camera_id, camera_dict)
            if not updated_camera:
                raise ValueError(CAMERA_NOT_FOUND)

            # Broadcast SSE event for camera update
            await self._broadcast_camera_event(
                SSEEvent.CAMERA_UPDATED,
                camera_id,
                changes=camera_data.model_dump(exclude_unset=True),
            )

            logger.info(
                "Updated camera successfully",
                extra_context={
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
                "Failed to update camera",
                error_context={
                    "camera_id": camera_id,
                    "operation": "update_camera",
                },
                exception=e,
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
            validate_camera_exists(camera, camera_id)
            # After validation, we know camera is not None
            assert camera is not None, "Camera should not be None after validation"

            # Delete camera via database operations (pure CRUD)
            success = await self.camera_ops.delete_camera(camera_id)

            if success:
                # Broadcast SSE event for camera deletion
                await self._broadcast_camera_event(
                    SSEEvent.CAMERA_DELETED,
                    camera_id,
                    operation="delete",
                )

                logger.info(
                    "Deleted camera successfully",
                    extra_context={
                        "camera_id": camera_id,
                        "camera_name": camera.name,
                        "operation": "delete_camera",
                    },
                    source=LogSource.SYSTEM,
                    logger_name=LoggerName.CAMERA_SERVICE,
                )

            return success

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                "Failed to delete camera",
                error_context={
                    "camera_id": camera_id,
                    "operation": "delete_camera",
                },
                exception=e,
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
                # Broadcast SSE event for camera status update
                event_data = {
                    "camera_id": camera_id,
                    "status": status,
                }
                if error_message:
                    event_data["error_message"] = error_message

                await self.sse_ops.create_event(
                    event_type=SSEEvent.CAMERA_UPDATED,
                    event_data=event_data,
                    priority=SSEPriority.HIGH,
                    source="system",
                )

                logger.info(
                    "Updated camera status successfully",
                    extra_context={
                        "camera_id": camera_id,
                        "new_status": status,
                        "operation": "update_camera_status",
                    },
                    source=LogSource.SYSTEM,
                    logger_name=LoggerName.CAMERA_SERVICE,
                )
            else:
                raise ValueError(CAMERA_NOT_FOUND)

            return success

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                "Failed to update camera status",
                error_context={
                    "camera_id": camera_id,
                    "status": status,
                    "operation": "update_camera_status",
                },
                exception=e,
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
        try:
            health_status = await self.camera_ops.get_camera_health_status(camera_id)
            if health_status:
                logger.debug(
                    f"Retrieved health status for camera {camera_id}",
                    extra_context={
                        "camera_id": camera_id,
                        "degraded_mode_active": health_status.degraded_mode_active,
                        "operation": "get_camera_health_status",
                    },
                    source=LogSource.SYSTEM,
                    logger_name=LoggerName.CAMERA_SERVICE,
                )
            return health_status

        except Exception as e:
            logger.error(
                f"Failed to get health status for camera {camera_id}",
                error_context={
                    "camera_id": camera_id,
                    "operation": "get_camera_health_status",
                },
                exception=e,
            )
            raise

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
        try:
            success = await self.camera_ops.update_camera_health(camera_id, health_data)

            if success:
                logger.info(
                    f"Updated health data for camera {camera_id}",
                    extra_context={
                        "camera_id": camera_id,
                        "health_data": health_data,
                        "operation": "update_camera_health",
                    },
                    source=LogSource.SYSTEM,
                    logger_name=LoggerName.CAMERA_SERVICE,
                )

                # Broadcast SSE event for health update
                await self.sse_ops.create_event(
                    event_type=SSEEvent.CAMERA_HEALTH_CHANGED,
                    event_data={
                        "camera_id": camera_id,
                        "health_data": health_data,
                    },
                    priority=SSEPriority.NORMAL,
                    source="camera_service",
                )

            return success

        except Exception as e:
            logger.error(
                f"Failed to update health for camera {camera_id}",
                error_context={
                    "camera_id": camera_id,
                    "operation": "update_camera_health",
                },
                exception=e,
            )
            raise

    async def execute_timelapse_action(
        self, camera_id: int, request: "TimelapseActionRequest"
    ) -> Dict[str, Any]:
        """
        Unified timelapse action handler that delegates to TimelapseService for business logic.

        Args:
            camera_id: ID of the camera
            request: TimelapseActionRequest with action and optional data

        Returns:
            Dictionary with action result

        Raises:
            ValueError: If action is invalid or camera not found
        """
        try:
            # Validate camera exists for all actions
            camera = await self.get_camera_by_id(camera_id)
            validate_camera_exists(camera, camera_id)
            # After validation, we know camera is not None
            assert camera is not None, "Camera should not be None after validation"

            if request.action == TimelapseAction.CREATE:
                return await self._handle_create_action(camera_id, request)
            elif request.action == TimelapseAction.PAUSE:
                return await self._handle_pause_action(camera_id, camera)
            elif request.action == TimelapseAction.RESUME:
                return await self._handle_resume_action(camera_id, camera)
            elif request.action == TimelapseAction.END:
                return await self._handle_end_action(camera_id, camera)
            else:
                raise ValueError(f"Invalid timelapse action: {request.action}")

        except Exception as e:
            logger.error(
                f"Failed to execute timelapse action '{request.action}' for camera {camera_id}",
                error_context={
                    "camera_id": camera_id,
                    "action": request.action,
                    "operation": "execute_timelapse_action",
                    "timelapse_data": getattr(request, "timelapse_data", None),
                },
                exception=e,
            )
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to {request.action} timelapse",
            }

    async def _handle_create_action(
        self, camera_id: int, request: "TimelapseActionRequest"
    ) -> Dict[str, Any]:
        """
        Handle CREATE timelapse action.

        Args:
            camera_id: ID of the camera
            request: TimelapseActionRequest with timelapse data

        Returns:
            Dictionary with action result
        """
        logger.info(
            f"Starting new timelapse for camera {camera_id} with data: {request.timelapse_data}",
            source=LogSource.SYSTEM,
            logger_name=LoggerName.CAMERA_SERVICE,
        )

        # Create TimelapseCreate model from the data, filtering out fields not in the model
        timelapse_data = request.timelapse_data or {}
        timelapse_create_data = timelapse_data.copy()

        # Remove fields that will be set automatically or aren't part of TimelapseCreate
        timelapse_create_data.pop("camera_id", None)  # Will be set by the method
        timelapse_create_data.pop("status", None)  # Will be set automatically
        timelapse_create_data.pop("created_at", None)  # Will be set automatically

        # Set camera_id and status correctly for TimelapseBase
        timelapse_create_data["camera_id"] = camera_id
        timelapse_create_data["status"] = TimelapseStatus.RUNNING

        logger.info(
            f"Creating timelapse with cleaned data: {timelapse_create_data}",
            source=LogSource.SYSTEM,
            logger_name=LoggerName.CAMERA_SERVICE,
        )

        # Create TimelapseCreate model instance (this will apply defaults)
        timelapse_create = TimelapseCreate(**timelapse_create_data)
        logger.info(
            f"TimelapseCreate model created with defaults: {timelapse_create.model_dump()}",
            source=LogSource.SYSTEM,
            logger_name=LoggerName.CAMERA_SERVICE,
        )

        # Create timelapse using instance timelapse_ops with correct method
        timelapse = await self.timelapse_ops.create_new_timelapse(
            camera_id, timelapse_create
        )
        logger.info(
            f"Created timelapse: {timelapse.id}",
            source=LogSource.SYSTEM,
            logger_name=LoggerName.CAMERA_SERVICE,
        )

        # Update the camera's active timelapse
        await self.camera_ops.update_camera(
            camera_id, {"active_timelapse_id": timelapse.id}
        )
        logger.info(
            f"Updated camera {camera_id} active_timelapse_id to {timelapse.id}",
            source=LogSource.SYSTEM,
            logger_name=LoggerName.CAMERA_SERVICE,
        )

        # Create SSE event for real-time updates
        logger.info(
            f"🔄 Creating timelapse_status_changed SSE event for start: camera_id={camera_id}, timelapse_id={timelapse.id}",
            source=LogSource.SYSTEM,
            logger_name=LoggerName.CAMERA_SERVICE,
        )
        await self._broadcast_timelapse_status_event(
            timelapse.id,
            camera_id,
            TimelapseStatus.RUNNING,
            action="start",
        )

        # Reset capture timing fields for new timelapse - let scheduler handle timing
        logger.info(
            f"🕐 Resetting capture timing for camera {camera_id} - new timelapse starts with clean state",
            source=LogSource.SYSTEM,
            logger_name=LoggerName.CAMERA_SERVICE,
        )
        try:
            update_result = await self.camera_ops.update_camera(
                camera_id,
                {
                    "last_capture_at": None,
                    "next_capture_at": None,  # Clean state - scheduler will set proper timing
                },
            )
            logger.info(
                f"✅ Capture timing reset successful: last_capture_at={update_result.last_capture_at}, next_capture_at={update_result.next_capture_at}",
            )
        except Exception as e:
            logger.error(
                f"Failed to reset capture timing for camera {camera_id}",
                error_context={"camera_id": camera_id},
                exception=e,
            )
            # Continue with timelapse creation even if timing reset fails

        # Trigger immediate scheduler sync for the new timelapse
        logger.info(
            f"🔄 Triggering immediate scheduler sync for new timelapse {timelapse.id}",
            source=LogSource.SYSTEM,
            logger_name=LoggerName.CAMERA_SERVICE,
        )
        await self._broadcast_scheduler_event(
            {
                "timelapse_id": timelapse.id,
                "camera_id": camera_id,
                "trigger": "new_timelapse_created",
            },
            priority=SSEPriority.HIGH,
        )

        # Schedule immediate first capture using scheduler authority service
        if self.scheduler_authority_service:
            logger.info(
                f"🎯 Scheduling immediate first capture for timelapse {timelapse.id}",
            )
            try:
                capture_result = (
                    await self.scheduler_authority_service.schedule_immediate_capture(
                        camera_id=camera_id, timelapse_id=timelapse.id
                    )
                )
                if capture_result:
                    logger.info(
                        f"✅ Immediate capture scheduled successfully for timelapse {timelapse.id}",
                        source=LogSource.SYSTEM,
                        logger_name=LoggerName.CAMERA_SERVICE,
                    )
                else:
                    logger.warning(
                        f"⚠️ Failed to schedule immediate capture for timelapse {timelapse.id}",
                        source=LogSource.SYSTEM,
                        logger_name=LoggerName.CAMERA_SERVICE,
                    )
            except Exception as e:
                logger.error(
                    f"Error scheduling immediate capture for timelapse {timelapse.id}",
                    error_context={"timelapse_id": timelapse.id},
                    source=LogSource.SYSTEM,
                    logger_name=LoggerName.CAMERA_SERVICE,
                    exception=e,
                )
        else:
            logger.warning(
                "⚠️ Scheduler authority service not available - immediate capture skipped",
            )

        # 🎯 SCHEDULER-CENTRIC: Add recurring capture job for ongoing captures
        if self.scheduler_authority_service:
            logger.info(
                f"🔄 Adding recurring capture job for timelapse {timelapse.id} (interval: {timelapse.capture_interval_seconds}s)",
            )
            try:
                job_result = await self.scheduler_authority_service.add_timelapse_job(
                    timelapse_id=timelapse.id,
                    capture_interval_seconds=timelapse.capture_interval_seconds,
                )
                if job_result.get("success"):
                    logger.info(
                        f"✅ Recurring capture job added successfully for timelapse {timelapse.id}",
                        source=LogSource.SYSTEM,
                        logger_name=LoggerName.CAMERA_SERVICE,
                    )
                else:
                    logger.error(
                        f"❌ Failed to add recurring capture job for timelapse {timelapse.id}: {job_result.get('error', 'Unknown error')}",
                        source=LogSource.SYSTEM,
                        logger_name=LoggerName.CAMERA_SERVICE,
                    )
            except Exception as e:
                logger.error(
                    f"Error adding recurring capture job for timelapse {timelapse.id}",
                    error_context={"timelapse_id": timelapse.id},
                    source=LogSource.SYSTEM,
                    logger_name=LoggerName.CAMERA_SERVICE,
                    exception=e,
                )
        else:
            logger.warning(
                "⚠️ Scheduler authority service not available - recurring captures will not be scheduled",
            )

        # Note: First capture scheduled immediately, then will follow normal scheduled interval

        logger.info(
            f"Successfully started timelapse {timelapse.id} for camera {camera_id}",
            source=LogSource.SYSTEM,
            logger_name=LoggerName.CAMERA_SERVICE,
        )

        return {
            "success": True,
            "timelapse_id": timelapse.id,
            "timelapse_status": TimelapseStatus.RUNNING,
            "message": "Timelapse started successfully",
        }

    async def _handle_pause_action(
        self, camera_id: int, camera: Camera
    ) -> Dict[str, Any]:
        """
        Handle PAUSE timelapse action.

        Args:
            camera_id: ID of the camera
            camera: Camera instance (unified camera model with stats)

        Returns:
            Dictionary with action result
        """
        logger.info(
            f"Starting pause operation for camera {camera_id}",
            source=LogSource.SYSTEM,
            logger_name=LoggerName.CAMERA_SERVICE,
        )

        if not camera.active_timelapse_id:
            raise ValueError(f"Camera {camera_id} has no active timelapse")

        timelapse_id = camera.active_timelapse_id
        logger.info(f"Attempting to pause timelapse {timelapse_id}")

        # Delegate to TimelapseService if available, otherwise use direct database operations
        if self.timelapse_service:
            await self.timelapse_service.pause_timelapse(timelapse_id)
            logger.info(
                f"Successfully paused timelapse {timelapse_id} via TimelapseService"
            )
        else:
            # Fallback to direct database operations
            timelapse_update = TimelapseUpdate(status=TimelapseStatus.PAUSED)
            await self.timelapse_ops.update_timelapse(timelapse_id, timelapse_update)
            logger.info(
                f"Successfully updated timelapse {timelapse_id} to paused status"
            )

        # Create SSE event for real-time updates
        await self._broadcast_timelapse_status_event(
            timelapse_id,
            camera_id,
            TimelapseStatus.PAUSED,
            action="pause",
        )

        return {
            "success": True,
            "timelapse_id": timelapse_id,
            "timelapse_status": TimelapseStatus.PAUSED,
            "message": "Timelapse paused successfully",
        }

    async def _handle_resume_action(
        self, camera_id: int, camera: Camera
    ) -> Dict[str, Any]:
        """
        Handle RESUME timelapse action.

        Args:
            camera_id: ID of the camera
            camera: Camera instance (unified camera model with stats)
            camera: Camera instance

        Returns:
            Dictionary with action result
        """
        if not camera.active_timelapse_id:
            raise ValueError(f"Camera {camera_id} has no active timelapse")

        timelapse_id = camera.active_timelapse_id

        # Delegate to TimelapseService if available, otherwise use direct database operations
        if self.timelapse_service:
            await self.timelapse_service.start_timelapse(timelapse_id)
            logger.info(
                f"Successfully resumed timelapse {timelapse_id} via TimelapseService"
            )
        else:
            # Fallback to direct database operations
            timelapse_update = TimelapseUpdate(status=TimelapseStatus.RUNNING)
            await self.timelapse_ops.update_timelapse(timelapse_id, timelapse_update)
            logger.info(
                f"Successfully updated timelapse {timelapse_id} to running status"
            )

        # Create SSE event for real-time updates
        await self._broadcast_timelapse_status_event(
            timelapse_id,
            camera_id,
            TimelapseStatus.RUNNING,
            action="resume",
        )

        return {
            "success": True,
            "timelapse_id": timelapse_id,
            "timelapse_status": TimelapseStatus.RUNNING,
            "message": "Timelapse resumed successfully",
        }

    async def _handle_end_action(
        self, camera_id: int, camera: Camera
    ) -> Dict[str, Any]:
        """
        Handle END timelapse action.

        Args:
            camera_id: ID of the camera
            camera: Camera instance (unified camera model with stats)

        Returns:
            Dictionary with action result
        """
        if not camera.active_timelapse_id:
            raise ValueError(f"Camera {camera_id} has no active timelapse")

        timelapse_id = camera.active_timelapse_id

        # Delegate to TimelapseService if available, otherwise use direct database operations
        if self.timelapse_service:
            await self.timelapse_service.complete_timelapse(timelapse_id)
            logger.info(
                f"Successfully completed timelapse {timelapse_id} via TimelapseService"
            )
        else:
            # Fallback to direct database operations
            timelapse_update = TimelapseUpdate(status=TimelapseStatus.COMPLETED)
            await self.timelapse_ops.update_timelapse(timelapse_id, timelapse_update)
            logger.info(
                f"Successfully updated timelapse {timelapse_id} to completed status"
            )

        # Clear the active timelapse from the camera
        await self.camera_ops.update_camera(camera_id, {"active_timelapse_id": None})

        # Create SSE event for real-time updates (only if fallback is used)
        if not self.timelapse_service:
            logger.info(
                f"🔄 Creating timelapse_status_changed SSE event for completion: camera_id={camera_id}, timelapse_id={timelapse_id}"
            )
            await self._broadcast_timelapse_status_event(
                timelapse_id,
                camera_id,
                TimelapseStatus.COMPLETED,
                action="complete",
            )

        return {
            "success": True,
            "timelapse_id": timelapse_id,
            "timelapse_status": TimelapseStatus.COMPLETED,
            "message": "Timelapse completed successfully",
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
            # Get current health status
            health_status = await self.get_camera_health_status(camera_id)
            if not health_status:
                raise ValueError(f"Camera {camera_id} not found")

            monitoring_timestamp = await get_timezone_aware_timestamp_async(
                self.settings_service
            )

            # Note: Enhanced corruption health monitoring will be provided by corruption_pipeline when needed

            return CameraHealthMonitoringResult(
                success=True,
                camera_id=camera_id,
                monitoring_timestamp=monitoring_timestamp,
                basic_health=health_status,
                error=None,
            )

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                "Health monitoring coordination failed",
                extra_context={
                    "camera_id": camera_id,
                    "operation": "coordinate_health_monitoring",
                },
                exception=e,
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
        Schedule image capture coordination (simplified for separation of concerns).

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
            camera = validate_camera_exists(camera, camera_id)

            current_time = await self._get_current_timestamp()

            # NOTE: Direct capture scheduling moved to CaptureWorker for proper separation of concerns
            # CameraService focuses on camera lifecycle, not capture execution
            capture_result = {"success": True}  # Simplified for now

            # Note: Next capture time should be managed by scheduler worker based on timelapse intervals
            if capture_result.get("success"):
                # Scheduler worker will handle next capture time based on active timelapse intervals
                next_capture = None

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
                    error="Capture scheduling failed",
                )

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                "Capture scheduling failed",
                extra_context={
                    "camera_id": camera_id,
                    "operation": "schedule_capture",
                },
                exception=e,
            )

            current_time = await self._get_current_timestamp()

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
            camera = await self.camera_ops.get_camera_by_id(camera_id)
            if not camera:
                raise ValueError(f"Camera {camera_id} not found")

            test_timestamp = await get_timezone_aware_timestamp_async(
                self.settings_service
            )

            # Test RTSP connection via unified RTSP service
            if self.rtsp_service:
                try:
                    rtsp_result = await self.rtsp_service.test_connection(
                        camera_id, camera.rtsp_url
                    )

                    # Update camera connectivity based on test results
                    await self.update_camera_connectivity(
                        camera_id,
                        rtsp_result.success,
                        rtsp_result.error if not rtsp_result.success else None,
                    )

                    logger.info(
                        "Connectivity test completed",
                        extra_context={
                            "camera_id": camera_id,
                            "success": rtsp_result.success,
                            "response_time": getattr(
                                rtsp_result, "response_time_ms", None
                            ),
                            "operation": "test_connectivity",
                        },
                    )

                    return rtsp_result

                except Exception as rtsp_error:
                    logger.error(
                        "RTSP connectivity test failed",
                        extra_context={
                            "camera_id": camera_id,
                            "operation": "test_connectivity",
                        },
                        exception=rtsp_error,
                    )

                    # Update connectivity as failed
                    await self.update_camera_connectivity(
                        camera_id, False, str(rtsp_error)
                    )

                    return CameraConnectivityTestResult(
                        success=False,
                        camera_id=camera_id,
                        rtsp_url=camera.rtsp_url,
                        connection_status="test_failed",
                        error=str(rtsp_error),
                        test_timestamp=test_timestamp,
                    )
            else:
                logger.warning(
                    "RTSPService not configured, cannot test connectivity",
                    extra_context={
                        "camera_id": camera_id,
                        "operation": "test_connectivity",
                    },
                )
                return CameraConnectivityTestResult(
                    success=False,
                    camera_id=camera_id,
                    rtsp_url=camera.rtsp_url,
                    connection_status="service_unavailable",
                    error="RTSPService not configured",
                    test_timestamp=test_timestamp,
                )

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                "Connectivity test failed",
                extra_context={
                    "camera_id": camera_id,
                    "operation": "test_connectivity",
                },
                exception=e,
            )

            test_timestamp = await get_timezone_aware_timestamp_async(
                self.settings_service
            )

            return CameraConnectivityTestResult(
                success=False,
                camera_id=camera_id,
                rtsp_url="unknown",
                connection_status="test_failed",
                error=str(e),
                test_timestamp=test_timestamp,
            )

    async def update_camera_connectivity(
        self, camera_id: int, is_connected: bool, error_message: Optional[str] = None
    ) -> bool:
        """
        Update camera connectivity status.

        Args:
            camera_id: ID of the camera
            is_connected: Whether camera is connected
            error_message: Optional error message if connection failed

        Returns:
            True if update was successful
        """
        try:
            updated_camera = await self.camera_ops.update_camera(
                camera_id, {"health_status": "online" if is_connected else "offline"}
            )
            success = updated_camera is not None

            if success:
                logger.debug(
                    f"Updated connectivity status for camera {camera_id}. is_connected: {is_connected}",
                    extra_context={
                        "camera_id": camera_id,
                        "is_connected": is_connected,
                        "error_message": error_message,
                        "operation": "update_camera_connectivity",
                    },
                )

            return success

        except Exception as e:
            logger.error(
                f"Failed to update connectivity for camera {camera_id}",
                extra_context={
                    "camera_id": camera_id,
                    "operation": "update_camera_connectivity",
                },
                exception=e,
            )
            raise

    # Note: capture_temporary_image() removed - RTSP capture actions now handled directly by RTSPService

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
                    "Health monitoring issues for camera",
                    extra_context={
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
                "Capture workflow coordination failed",
                exception=e,
                extra_context={
                    "camera_id": camera_id,
                    "operation": "coordinate_capture_workflow",
                },
            )

            # Create error result with minimal data
            monitoring_timestamp = await self._get_current_timestamp()
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

    # ========================================
    # Crop/Rotation Settings Management
    # (Migrated from CameraCropService)
    # ========================================

    async def get_crop_settings(self, camera_id: int) -> Optional[CropRotationSettings]:
        """
        Get crop/rotation settings for a camera.

        Args:
            camera_id: Camera ID

        Returns:
            CropRotationSettings or None if no custom settings

        Raises:
            ValueError: If camera doesn't exist
        """
        try:
            # Get camera record
            camera = await self.get_camera_by_id(camera_id)
            camera = validate_camera_exists(camera, camera_id)

            # Check if crop/rotation is enabled
            if not getattr(camera, "crop_rotation_enabled", False):
                logger.debug(
                    f"Crop/rotation not enabled for camera {camera_id}",
                )
                return None

            # Parse settings from JSONB
            settings_data = getattr(camera, "crop_rotation_settings", {}) or {}
            if not settings_data:
                logger.debug(
                    f"No crop/rotation settings found for camera {camera_id}",
                )
                return None

            # Validate and return as Pydantic model
            return CropRotationSettings(**settings_data)

        except Exception as e:
            logger.error(
                f"Error getting crop settings for camera {camera_id}",
                exception=e,
                extra_context={
                    "operation": "get_crop_settings",
                    "camera_id": camera_id,
                },
            )
            raise

    async def update_crop_settings(
        self, camera_id: int, settings_update: CropRotationUpdate
    ) -> CropRotationSettings:
        """
        Update crop/rotation settings for a camera.

        Args:
            camera_id: Camera ID
            settings_update: Settings to update

        Returns:
            Updated CropRotationSettings

        Raises:
            ValueError: If camera doesn't exist
        """
        try:
            # Get existing settings
            existing_settings = await self.get_crop_settings(camera_id)

            # If no existing settings, create defaults
            if existing_settings is None:
                existing_data = {
                    "rotation": 0,
                    "crop": None,
                    "aspect_ratio": None,
                    "processing_order": ["crop", "rotate", "aspect_ratio"],
                    "preview_enabled": True,
                }
            else:
                existing_data = existing_settings.model_dump()

            # Apply updates (only non-None values)
            update_data = settings_update.model_dump(exclude_none=True)
            existing_data.update(update_data)

            # Validate the complete settings
            validated_settings = CropRotationSettings(**existing_data)

            # Update database
            await self.camera_ops.update_camera_crop_settings(
                camera_id,
                validated_settings.model_dump(),
                enabled=True,  # Enable crop/rotation when settings are updated
            )

            logger.info(f"Updated crop/rotation settings for camera {camera_id}")
            return validated_settings

        except Exception as e:
            logger.error(
                f"Error updating crop settings for camera {camera_id}", exception=e
            )
            raise

    async def disable_crop_settings(self, camera_id: int) -> bool:
        """
        Disable crop/rotation settings for a camera.

        Args:
            camera_id: Camera ID

        Returns:
            True if successful

        Raises:
            ValueError: If camera doesn't exist
        """
        try:
            # Verify camera exists
            camera = await self.get_camera_by_id(camera_id)
            camera = validate_camera_exists(camera, camera_id)

            # Disable crop/rotation
            await self.camera_ops.update_camera_crop_settings(
                camera_id, settings={}, enabled=False  # Clear settings
            )

            logger.info(f"Disabled crop/rotation settings for camera {camera_id}")
            return True

        except Exception as e:
            logger.error(
                f"Error disabling crop settings for camera {camera_id}", exception=e
            )
            raise

    async def get_source_resolution(self, camera_id: int) -> Optional[SourceResolution]:
        """
        Get stored source resolution for a camera.

        Args:
            camera_id: Camera ID

        Returns:
            SourceResolution if available, None otherwise

        Raises:
            ValueError: If camera doesn't exist
        """
        try:
            camera = await self.get_camera_by_id(camera_id)
            camera = validate_camera_exists(camera, camera_id)

            resolution_data = getattr(camera, "source_resolution", {}) or {}
            if not resolution_data:
                logger.debug(
                    f"No source resolution stored for camera {camera_id}",
                )
                return None

            return SourceResolution(**resolution_data)

        except Exception as e:
            logger.error(
                f"Error getting source resolution for camera {camera_id}",
                exception=e,
                extra_context={
                    "operation": "get_source_resolution",
                    "camera_id": camera_id,
                },
            )
            raise

    async def get_cameras_ready_for_capture(self) -> List[Camera]:
        """
        Get all cameras that are ready for image capture using business logic.

        Applies business rules for capture readiness:
        - Active status
        - Have running timelapses
        - Are due for capture (next_capture_at <= now)
        - Not in degraded mode or have corruption detection enabled

        Returns:
            List of Camera model instances ready for capture
        """
        try:
            # Get cameras due for capture (no business logic filtering)
            due_cameras = await self.camera_ops.get_cameras_due_for_capture()

            # Apply business logic filtering in service layer
            ready_cameras = []
            for camera in due_cameras:
                if self.is_camera_capture_ready(
                    camera.status,
                    camera.timelapse_status,
                    camera.degraded_mode_active,
                    camera.corruption_detection_heavy,
                ):
                    ready_cameras.append(camera)

            logger.debug(
                f"Found {len(ready_cameras)} cameras ready for capture out of {len(due_cameras)} due",
                extra_context={"operation": "get_cameras_ready_for_capture"},
            )

            return ready_cameras
        except Exception as e:
            logger.error(
                "Failed to get cameras ready for capture",
                exception=e,
                extra_context={"operation": "get_cameras_ready_for_capture"},
            )
            # Return empty list rather than failing entirely
            return []

    async def update_camera_capture_stats(
        self,
        camera_id: int,
        success: bool,
        consecutive_failures: int = 0,
    ) -> bool:
        """
        Update camera capture statistics using business logic for health determination.

        Args:
            camera_id: ID of the camera
            success: Whether the capture was successful
            consecutive_failures: Current consecutive failure count (for health determination)

        Returns:
            True if stats were updated successfully
        """
        try:
            # Use business logic to determine health status
            health_status = self.determine_camera_health_status(
                consecutive_failures + (0 if success else 1)
            )

            # Update database with determined health status
            result = await self.camera_ops.update_camera_capture_stats(
                camera_id, success, health_status
            )

            if result:
                logger.debug(
                    "Updated capture stats for camera",
                    extra_context={
                        "camera_id": camera_id,
                        "capture_success": success,
                        "health_status": health_status,
                        "operation": "update_capture_stats",
                    },
                )

            return result
        except Exception as e:
            logger.error(
                "Failed to update camera capture stats",
                exception=e,
                extra_context={
                    "camera_id": camera_id,
                    "operation": "update_capture_stats",
                },
            )
            return False

    async def get_status(self) -> Dict[str, Any]:
        """
        Get CameraService status (STANDARDIZED METHOD NAME).

        Returns:
            Dict[str, Any]: Service status information
        """
        try:
            # Get basic counts
            cameras = await self.get_cameras()
            active_cameras = [c for c in cameras if c.status == "active"]

            # Get cameras with running timelapses
            running_timelapses = [c for c in cameras if c.timelapse_status == "running"]

            # Get health status distribution
            health_status_counts = {}
            for camera in cameras:
                health = getattr(camera, "health_status", "unknown")
                health_status_counts[health] = health_status_counts.get(health, 0) + 1

            return {
                "service": "camera_service",
                "database_connected": self.db is not None,
                "total_cameras": len(cameras),
                "active_cameras": len(active_cameras),
                "cameras_with_running_timelapses": len(running_timelapses),
                "health_status_distribution": health_status_counts,
                "dependencies": {
                    "rtsp_service": self.rtsp_service is not None,
                    "scheduling_service": self.scheduling_service is not None,
                    "timelapse_service": self.timelapse_service is not None,
                    "scheduler_authority_service": self.scheduler_authority_service
                    is not None,
                },
                "error": None,
            }
        except Exception as e:
            logger.error(f"Camera service status check failed: {e}")
            return {
                "service": "camera_service",
                "database_connected": False,
                "error": str(e),
            }


class SyncCameraService:
    """
    Sync camera service for worker processes using composition pattern.

    This service orchestrates camera-related business logic using
    dependency injection instead of mixin inheritance.
    """

    def __init__(
        self,
        db: SyncDatabase,
        async_db,
        rtsp_service=None,
        scheduling_service=None,
        settings_service=None,
        camera_ops=None,
        timelapse_ops=None,
    ):
        """
        Initialize SyncCameraService with injected dependencies.

        Args:
            db: SyncDatabase instance
            async_db: AsyncDatabase instance (for operations that need async)
            rtsp_service: Optional RTSPService for RTSP operations
            scheduling_service: Optional SyncSchedulingService for capture scheduling
            settings_service: Optional SyncSettingsService for timezone operations
            camera_ops: Optional SyncCameraOperations instance
            timelapse_ops: Optional SyncTimelapseOperations instance
        """
        self.db = db
        self.async_db = async_db
        # Use dependency injection for Operations
        self.camera_ops = camera_ops or self._get_default_camera_ops()
        self.timelapse_ops = timelapse_ops or self._get_default_timelapse_ops()
        # Direct SettingsOperations removed - use injected settings_service instead
        self.rtsp_service = rtsp_service
        self.scheduling_service = scheduling_service
        self.settings_service = settings_service

    def _get_default_camera_ops(self):
        """Fallback to get SyncCameraOperations singleton"""
        from ..dependencies.specialized import get_sync_camera_operations

        return get_sync_camera_operations()

    def _get_default_timelapse_ops(self):
        """Fallback to get SyncTimelapseOperations singleton"""
        from ..dependencies.specialized import get_sync_timelapse_operations

        return get_sync_timelapse_operations()

    # ====================================================================
    # BUSINESS LOGIC HELPER METHODS (SYNC)
    # ====================================================================

    def determine_camera_health_status(self, consecutive_failures: int) -> str:
        """
        Determine camera health status based on consecutive failures.

        Business logic moved from database layer to service layer.

        Args:
            consecutive_failures: Number of consecutive capture failures

        Returns:
            Health status string (online, degraded, offline)
        """
        if consecutive_failures == 0:
            return CAMERA_HEALTH_ONLINE
        elif consecutive_failures < CAMERA_HEALTH_FAILURE_THRESHOLD:
            return CAMERA_HEALTH_DEGRADED
        else:
            return CAMERA_HEALTH_OFFLINE

    def is_camera_capture_ready(
        self,
        camera_status: str,
        timelapse_status: Optional[str],
        degraded_mode_active: bool,
        corruption_detection_heavy: bool,
    ) -> bool:
        """
        Determine if camera is ready for capture based on business rules.

        Business logic moved from database layer to service layer.

        Args:
            camera_status: Camera status (active, inactive, etc.)
            timelapse_status: Timelapse status (running, paused, etc.)
            degraded_mode_active: Whether camera is in degraded mode
            corruption_detection_heavy: Whether corruption detection is enabled

        Returns:
            True if camera is ready for capture
        """
        # Check basic status requirements
        if camera_status not in CAMERA_CAPTURE_READY_STATUSES:
            return False

        if timelapse_status not in CAMERA_TIMELAPSE_READY_STATUSES:
            return False

        # Check degraded mode requirements
        if degraded_mode_active and not corruption_detection_heavy:
            return False

        return True

    def should_update_health_to_degraded(self, consecutive_failures: int) -> bool:
        """
        Determine if camera health should be updated to degraded status.

        Args:
            consecutive_failures: Current consecutive failure count

        Returns:
            True if health should be marked as degraded
        """
        return consecutive_failures >= CAMERA_HEALTH_DEGRADED_THRESHOLD

    def should_update_health_to_offline(self, consecutive_failures: int) -> bool:
        """
        Determine if camera health should be updated to offline status.

        Args:
            consecutive_failures: Current consecutive failure count

        Returns:
            True if health should be marked as offline
        """
        return consecutive_failures >= CAMERA_HEALTH_FAILURE_THRESHOLD

    # ====================================================================
    # SYNC CAMERA CRUD OPERATIONS
    # ====================================================================

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
        try:
            return self.camera_ops.update_camera_connectivity(
                camera_id, is_connected, error_message
            )
        except Exception as e:
            logger.error(
                f"Failed to update sync connectivity for camera {camera_id}",
                exception=e,
                extra_context={"camera_id": camera_id},
            )
            raise

    def test_connectivity(self, camera_id: int) -> CameraConnectivityTestResult:
        """
        Test RTSP connectivity for camera (sync version for worker).

        Args:
            camera_id: ID of the camera to test

        Returns:
            CameraConnectivityTestResult with connectivity test details
        """
        try:
            # Get camera details
            camera = self.camera_ops.get_camera_by_id(camera_id)
            if not camera:
                raise ValueError(f"Camera {camera_id} not found")

            test_timestamp = get_timezone_aware_timestamp_sync(
                settings_service=self.settings_service
            )

            # Test RTSP connection
            if self.rtsp_service:
                try:
                    rtsp_result = self.rtsp_service.test_connection(
                        camera_id, camera.rtsp_url
                    )

                    # Update connectivity status
                    self.update_camera_connectivity(
                        camera_id,
                        rtsp_result.success,
                        rtsp_result.error if not rtsp_result.success else None,
                    )

                    return rtsp_result

                except Exception as rtsp_error:
                    logger.error(
                        "RTSP connectivity test failed",
                        exception=rtsp_error,
                        extra_context={
                            "camera_id": camera_id,
                        },
                    )

                    return CameraConnectivityTestResult(
                        success=False,
                        camera_id=camera_id,
                        rtsp_url=camera.rtsp_url,
                        connection_status="test_failed",
                        error=str(rtsp_error),
                        test_timestamp=test_timestamp,
                    )
            else:
                return CameraConnectivityTestResult(
                    success=False,
                    camera_id=camera_id,
                    rtsp_url=camera.rtsp_url,
                    connection_status="service_unavailable",
                    error="RTSPService not configured",
                    test_timestamp=test_timestamp,
                )

        except Exception as e:
            logger.error(
                f"Sync connectivity test failed for camera {camera_id}",
                exception=e,
                extra_context={"camera_id": camera_id},
            )

            test_timestamp = get_timezone_aware_timestamp_sync(self.settings_service)

            return CameraConnectivityTestResult(
                success=False,
                camera_id=camera_id,
                rtsp_url="unknown",
                connection_status="test_failed",
                error=str(e),
                test_timestamp=test_timestamp,
            )

    def update_next_capture_time(self, camera_id: int) -> bool:
        """
        Update the next capture time for a camera using SchedulingService.

        Args:
            camera_id: ID of the camera

        Returns:
            True if update was successful

        Raises:
            ValueError: If camera not found
            RuntimeError: If database operation fails
        """
        try:
            # Note: Next capture time should be managed by scheduler worker based on active timelapse intervals
            # This sync method should not update next capture time directly
            success = True  # Always succeed since we're not doing anything
            if not success:
                raise ValueError(CAMERA_NOT_FOUND)

            return success

        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logger.error(
                "Failed to update next capture time",
                exception=e,
                extra_context={
                    "camera_id": camera_id,
                    "operation": "update_next_capture_time",
                },
            )
            raise RuntimeError(f"Failed to update next capture time: {str(e)}") from e

    def get_camera_corruption_settings(
        self, camera_id: int
    ) -> Optional[CorruptionSettingsModel]:
        """
        Get camera-specific corruption detection settings.

        Note: This method still delegates to camera_ops since it's a data retrieval
        operation rather than a health monitoring operation.

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

        Note: This method still delegates to camera_ops since SyncCameraHealthService
        doesn't have this method yet. This could be moved to health service later.

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

        Note: This method still delegates to camera_ops since SyncCameraHealthService
        doesn't have this method yet. This could be moved to health service later.

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

        Note: This method still delegates to camera_ops since SyncCameraHealthService
        doesn't have this method yet. This could be moved to health service later.

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
                "Reset corruption failures for camera",
                extra_context={
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
                "Failed to reset corruption failures",
                exception=e,
                extra_context={
                    "camera_id": camera_id,
                    "operation": "reset_corruption_failures",
                },
            )
            raise RuntimeError(f"Failed to reset corruption failures: {str(e)}") from e

    def get_cameras_ready_for_capture(self) -> List[Camera]:
        """
        Sync version: Get all cameras that are ready for image capture using business logic.

        Applies business rules for capture readiness:
        - Active status
        - Have running timelapses
        - Are due for capture (next_capture_at <= now)
        - Not in degraded mode or have corruption detection enabled

        Returns:
            List of Camera model instances ready for capture
        """
        try:
            # Get cameras due for capture (no business logic filtering)
            due_cameras = self.camera_ops.get_cameras_due_for_capture()

            # Apply business logic filtering in service layer
            ready_cameras = []
            for camera in due_cameras:
                if self.is_camera_capture_ready(
                    camera.status,
                    camera.timelapse_status,
                    camera.degraded_mode_active,
                    camera.corruption_detection_heavy,
                ):
                    ready_cameras.append(camera)

            logger.debug(
                f"Found {len(ready_cameras)} cameras ready for capture out of {len(due_cameras)} due",
                extra_context={"operation": "get_cameras_ready_for_capture"},
            )

            return ready_cameras
        except Exception as e:
            logger.error(
                "Failed to get cameras ready for capture",
                exception=e,
                extra_context={"operation": "get_cameras_ready_for_capture"},
            )
            # Return empty list rather than failing entirely
            return []

    def get_cameras_ready_for_capture_sync(self) -> List[Camera]:
        """
        Sync version: Get all cameras that are ready for image capture using business logic.

        Applies business rules for capture readiness:
        - Active status
        - Have running timelapses
        - Are due for capture (next_capture_at <= now)
        - Not in degraded mode or have corruption detection enabled

        Returns:
            List of Camera model instances ready for capture
        """
        try:
            # Get cameras due for capture (no business logic filtering)
            due_cameras = self.camera_ops.get_cameras_due_for_capture()

            # Apply business logic filtering in service layer
            ready_cameras = []
            for camera in due_cameras:
                if self.is_camera_capture_ready(
                    camera.status,
                    camera.timelapse_status,
                    camera.degraded_mode_active,
                    camera.corruption_detection_heavy,
                ):
                    ready_cameras.append(camera)

            logger.debug(
                f"Found {len(ready_cameras)} cameras ready for capture out of {len(due_cameras)} due",
                extra_context={"operation": "get_cameras_ready_for_capture_sync"},
            )

            return ready_cameras
        except Exception as e:
            logger.error(
                "Failed to get cameras ready for capture",
                exception=e,
                extra_context={
                    "operation": "get_cameras_ready_for_capture_sync",
                },
            )
            # Return empty list rather than failing entirely
            return []

    def update_camera_capture_stats(self, camera_id: int, success: bool) -> bool:
        """
        Update camera capture statistics after a capture attempt.

        Args:
            camera_id: ID of the camera
            success: Whether the capture was successful

        Returns:
            True if stats were updated successfully
        """
        try:
            # Get current camera to determine consecutive failures
            camera = self.get_camera_by_id(camera_id)
            if not camera:
                logger.error(
                    f"Camera {camera_id} not found when updating capture stats",
                    extra_context={"camera_id": camera_id},
                )
                return False

            # Determine new consecutive failures count
            if success:
                new_consecutive_failures = 0
            else:
                new_consecutive_failures = camera.consecutive_failures + 1

            # Determine health status using business logic
            health_status = self.determine_camera_health_status(
                new_consecutive_failures
            )

            success_result = self.camera_ops.update_camera_capture_stats(
                camera_id, success, health_status
            )

            if success_result:
                logger.debug(
                    "Updated capture stats for camera",
                    extra_context={
                        "camera_id": camera_id,
                        "capture_success": success,
                        "operation": "update_capture_stats",
                    },
                )

            return success_result

        except Exception as e:
            logger.error(
                "Failed to update capture stats",
                exception=e,
                extra_context={
                    "camera_id": camera_id,
                    "capture_success": success,
                    "operation": "update_capture_stats",
                },
            )
            # Don't raise exception for stats updates to avoid blocking captures
            return False

    # ========================================
    # Crop/Rotation Settings Management (Sync)
    # (Migrated from SyncCameraCropService)
    # ========================================

    def get_crop_settings(self, camera_id: int) -> Optional[CropRotationSettings]:
        """Synchronous version of get_crop_settings"""
        try:
            camera = self.get_camera_by_id(camera_id)
            camera = validate_camera_exists(camera, camera_id)

            if not getattr(camera, "crop_rotation_enabled", False):
                return None

            settings_data = getattr(camera, "crop_rotation_settings", {}) or {}
            if not settings_data:
                return None

            return CropRotationSettings(**settings_data)

        except Exception as e:
            logger.error(
                f"Error getting crop settings for camera {camera_id}",
                exception=e,
                extra_context={"camera_id": camera_id},
            )
            raise

    def get_status(self) -> Dict[str, Any]:
        """
        Get SyncCameraService status (STANDARDIZED METHOD NAME).

        Returns:
            Dict[str, Any]: Service status information
        """
        try:
            # Get basic counts
            active_cameras = self.get_active_cameras()
            cameras_with_timelapses = self.get_cameras_with_running_timelapses()

            # Get health status distribution
            health_status_counts = {}
            for camera in active_cameras:
                health = getattr(camera, "health_status", "unknown")
                health_status_counts[health] = health_status_counts.get(health, 0) + 1

            return {
                "service": "sync_camera_service",
                "database_connected": self.db is not None,
                "active_cameras": len(active_cameras),
                "cameras_with_running_timelapses": len(cameras_with_timelapses),
                "health_status_distribution": health_status_counts,
                "dependencies": {
                    "rtsp_service": self.rtsp_service is not None,
                    "scheduling_service": self.scheduling_service is not None,
                },
                "error": None,
            }
        except Exception as e:
            logger.error(f"Sync camera service status check failed: {e}")
            return {
                "service": "sync_camera_service",
                "database_connected": False,
                "error": str(e),
            }
