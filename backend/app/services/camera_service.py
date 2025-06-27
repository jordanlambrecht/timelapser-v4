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
from ..database.settings_operations import SettingsOperations, SyncSettingsOperations
from ..models.camera_model import (
    Camera,
    CameraWithLastImage,
    CameraWithStats,
    CameraCreate,
    CameraUpdate,
)
from ..models.shared_models import CameraHealthStatus, CameraStatistics
from ..models.corruption_model import CorruptionSettingsModel
from ..utils.timezone_utils import (
    get_timezone_aware_timestamp_async,
    get_timezone_aware_timestamp_sync,
)
from ..utils.time_utils import create_time_delta
from ..utils.file_helpers import validate_file_path, ensure_directory_exists


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
        self, db: AsyncDatabase, image_capture_service=None, corruption_service=None
    ):
        """
        Initialize CameraService with async database instance and service dependencies.

        Args:
            db: AsyncDatabase instance
            image_capture_service: Optional ImageCaptureService for capture coordination
            corruption_service: Optional CorruptionService for health monitoring
        """
        self.db = db
        self.camera_ops = AsyncCameraOperations(db)
        self.settings_ops = SettingsOperations(db)
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
        return await self.camera_ops.get_camera_by_id(camera_id)

    async def get_cameras_with_images(self) -> List[CameraWithLastImage]:
        """
        Get all cameras with their latest image details.

        Returns:
            List of CameraWithLastImage model instances
        """
        return await self.camera_ops.get_cameras_with_images()

    async def create_camera(self, camera_data: CameraCreate) -> Camera:
        """
        Create a new camera with business logic orchestration.

        Args:
            camera_data: CameraCreate model instance

        Returns:
            Created Camera model instance
        """
        # Business Logic: Calculate initial next capture time using timezone-aware utilities
        # Get capture interval from global settings (default 300 seconds = 5 minutes)
        capture_interval_str = await self.settings_ops.get_setting("capture_interval")
        capture_interval = int(capture_interval_str) if capture_interval_str else 300

        current_time = await get_timezone_aware_timestamp_async(self.db)
        next_capture_at = current_time + create_time_delta(seconds=capture_interval)

        # Convert model to dict and add next capture time
        camera_dict = camera_data.model_dump()
        camera_data_with_timing = {**camera_dict, "next_capture_at": next_capture_at}

        # Create camera via database operations (pure CRUD)
        created_camera = await self.camera_ops.create_camera(camera_data_with_timing)

        # Business Logic: Broadcast event after successful creation
        await self.db.broadcast_event(
            "camera_created", {"camera": created_camera.model_dump()}
        )

        logger.info(f"Created camera: {created_camera.name} (ID: {created_camera.id})")
        return created_camera

    async def update_camera(self, camera_id: int, camera_data: CameraUpdate) -> Camera:
        """
        Update an existing camera with business logic orchestration.

        Args:
            camera_id: ID of the camera to update
            camera_data: CameraUpdate model instance

        Returns:
            Updated Camera model instance
        """
        # Convert model to dict for processing
        camera_dict = camera_data.model_dump(exclude_unset=True)

        # Note: capture_interval is a global setting, not a camera attribute
        # If next capture time needs updating, it should be done through schedule_capture method

        # Update camera via database operations (pure CRUD)
        updated_camera = await self.camera_ops.update_camera(camera_id, camera_dict)

        # Business Logic: Broadcast event after successful update
        await self.db.broadcast_event(
            "camera_updated", {"camera": updated_camera.model_dump()}
        )

        logger.info(f"Updated camera: {updated_camera.name} (ID: {camera_id})")
        return updated_camera

    async def delete_camera(self, camera_id: int) -> bool:
        """
        Delete a camera with business logic orchestration.

        Args:
            camera_id: ID of the camera to delete

        Returns:
            True if camera was deleted successfully
        """
        # Business Logic: Get camera details before deletion for event broadcasting
        camera = await self.camera_ops.get_camera_by_id(camera_id)
        if not camera:
            return False

        # Delete camera via database operations (pure CRUD)
        success = await self.camera_ops.delete_camera(camera_id)

        if success:
            # Business Logic: Broadcast event after successful deletion
            await self.db.broadcast_event(
                "camera_deleted", {"camera_id": camera_id, "camera_name": camera.name}
            )

            logger.info(f"Deleted camera: {camera.name} (ID: {camera_id})")

        return success

    async def update_camera_status(
        self, camera_id: int, status: str, error_message: Optional[str] = None
    ) -> bool:
        """
        Update camera status with business logic orchestration.

        Args:
            camera_id: ID of the camera
            status: New status ('active', 'inactive', 'error')
            error_message: Optional error message

        Returns:
            True if status was updated successfully
        """
        # Update status via database operations (pure CRUD)
        success = await self.camera_ops.update_camera_status(
            camera_id, status, error_message
        )

        if success:
            # Business Logic: Broadcast event after successful status update
            await self.db.broadcast_event(
                "camera_status_updated",
                {
                    "camera_id": camera_id,
                    "status": status,
                    "error_message": error_message,
                },
            )

            logger.info(f"Updated camera {camera_id} status to: {status}")

        return success

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

    async def coordinate_health_monitoring(self, camera_id: int) -> Dict[str, Any]:
        """
        Coordinate health monitoring with corruption service.

        Args:
            camera_id: ID of the camera to monitor

        Returns:
            Health monitoring results including corruption analysis
        """
        try:
            # Get basic camera health
            health_status = await self.get_camera_health_status(camera_id)

            # Coordinate with corruption service if available
            corruption_analysis = None
            if self.corruption_service:
                corruption_analysis = (
                    await self.corruption_service.assess_camera_health(camera_id)
                )

            # Generate timezone-aware timestamp for monitoring
            monitoring_timestamp = await get_timezone_aware_timestamp_async(self.db)

            # Combine health data
            health_data = {
                "basic_health": health_status.model_dump() if health_status else None,
                "corruption_analysis": corruption_analysis,
                "monitoring_timestamp": monitoring_timestamp.isoformat(),
            }

            # Update camera health metrics
            await self.update_camera_health(camera_id, health_data)

            return health_data

        except Exception as e:
            logger.error(
                f"Health monitoring coordination failed for camera {camera_id}: {e}"
            )
            return {"error": str(e)}

    async def schedule_capture(self, camera_id: int) -> Dict[str, Any]:
        """
        Schedule image capture coordination with ImageCaptureService.

        Args:
            camera_id: ID of the camera to schedule capture for

        Returns:
            Capture scheduling results
        """
        try:
            # Get camera details for scheduling
            camera = await self.get_camera_by_id(camera_id)
            if not camera:
                return {"error": f"Camera {camera_id} not found"}

            # Coordinate with image capture service if available
            if self.image_capture_service:
                capture_result = await self.image_capture_service.schedule_capture(
                    camera_id, camera.rtsp_url
                )

                # Update next capture time based on global interval setting using timezone utilities
                if capture_result.get("success"):
                    # Get capture interval from global settings (default 300 seconds = 5 minutes)
                    capture_interval_str = await self.settings_ops.get_setting(
                        "capture_interval"
                    )
                    capture_interval = (
                        int(capture_interval_str) if capture_interval_str else 300
                    )

                    current_time = await get_timezone_aware_timestamp_async(self.db)
                    next_capture = current_time + create_time_delta(
                        seconds=capture_interval
                    )
                    await self.camera_ops.update_camera_next_capture_time(
                        camera_id, next_capture
                    )

                return capture_result
            else:
                logger.warning(
                    f"ImageCaptureService not available for camera {camera_id}"
                )
                return {"error": "ImageCaptureService not configured"}

        except Exception as e:
            logger.error(f"Capture scheduling failed for camera {camera_id}: {e}")
            return {"error": str(e)}

    async def test_connectivity(self, camera_id: int) -> Dict[str, Any]:
        """
        Test RTSP connectivity for camera.

        Args:
            camera_id: ID of the camera to test

        Returns:
            Connectivity test results
        """
        try:
            # Get camera details
            camera = await self.get_camera_by_id(camera_id)
            if not camera:
                return {"error": f"Camera {camera_id} not found"}

            # Test RTSP connection via image capture service
            if self.image_capture_service:
                connectivity_result = (
                    await self.image_capture_service.test_rtsp_connection(
                        camera.rtsp_url
                    )
                )

                # Update camera status based on connectivity
                if connectivity_result.get("success"):
                    await self.update_camera_status(camera_id, "active")
                else:
                    await self.update_camera_status(
                        camera_id,
                        "error",
                        connectivity_result.get("error", "RTSP connection failed"),
                    )

                return connectivity_result
            else:
                logger.warning(
                    f"ImageCaptureService not available for connectivity test of camera {camera_id}"
                )
                return {"error": "ImageCaptureService not configured"}

        except Exception as e:
            logger.error(f"Connectivity test failed for camera {camera_id}: {e}")
            return {"error": str(e)}

    async def coordinate_capture_workflow(self, camera_id: int) -> Dict[str, Any]:
        """
        Coordinate complete capture workflow including health checks and scheduling.

        Args:
            camera_id: ID of the camera

        Returns:
            Complete workflow results
        """
        try:
            # 1. Test connectivity first
            connectivity = await self.test_connectivity(camera_id)
            if not connectivity.get("success"):
                return {
                    "workflow": "failed",
                    "step": "connectivity",
                    "result": connectivity,
                }

            # 2. Coordinate health monitoring
            health = await self.coordinate_health_monitoring(camera_id)
            if health.get("error"):
                logger.warning(
                    f"Health monitoring issues for camera {camera_id}: {health}"
                )

            # 3. Schedule capture if connectivity is good
            capture = await self.schedule_capture(camera_id)

            return {
                "workflow": "completed",
                "connectivity": connectivity,
                "health_monitoring": health,
                "capture_scheduling": capture,
            }

        except Exception as e:
            logger.error(
                f"Capture workflow coordination failed for camera {camera_id}: {e}"
            )
            return {"workflow": "failed", "error": str(e)}


class SyncCameraService:
    """
    Sync camera service for worker processes using composition pattern.

    This service orchestrates camera-related business logic using
    dependency injection instead of mixin inheritance.
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize SyncCameraService with sync database instance.

        Args:
            db: SyncDatabase instance
        """
        self.db = db
        self.camera_ops = SyncCameraOperations(db)
        self.settings_ops = SyncSettingsOperations(db)

    def get_active_cameras(self) -> List[Camera]:
        """
        Retrieve all enabled cameras for worker processing.

        Returns:
            List of enabled Camera model instances
        """
        return self.camera_ops.get_active_cameras()

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

    def update_next_capture_time(self, camera_id: int) -> bool:
        """
        Update the next capture time for a camera using timezone-aware calculations.

        Args:
            camera_id: ID of the camera

        Returns:
            True if update was successful
        """
        # Get current timezone-aware timestamp
        current_time = get_timezone_aware_timestamp_sync(self.db)

        # Get capture interval from global settings (default 300 seconds = 5 minutes)
        capture_interval_str = self.settings_ops.get_setting("capture_interval", "300")
        capture_interval = int(capture_interval_str) if capture_interval_str else 300

        # Calculate next capture time
        next_capture_at = current_time + create_time_delta(seconds=capture_interval)

        return self.camera_ops.update_next_capture_time(camera_id, next_capture_at)

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
        """
        return self.camera_ops.reset_camera_corruption_failures(camera_id)
