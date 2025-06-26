# backend/app/services/camera_service.py
"""
Camera Service - Composition-based architecture.

This service handles camera-related business logic using dependency injection
for database operations, providing type-safe Pydantic model interfaces.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.camera_operations import AsyncCameraOperations, SyncCameraOperations
from ..models.camera_model import Camera, CameraWithLastImage, CameraWithStats
from ..models.shared_models import CameraHealthStatus, CameraStatistics


class CameraService:
    """
    Async camera service using composition pattern for database operations.

    This service orchestrates camera-related business logic using
    dependency injection instead of mixin inheritance.
    """

    def __init__(self, db: AsyncDatabase):
        """
        Initialize CameraService with async database instance.

        Args:
            db: AsyncDatabase instance
        """
        self.db = db
        self.camera_ops = AsyncCameraOperations(db)

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

    async def create_camera(self, camera_data: Dict[str, Any]) -> Camera:
        """
        Create a new camera with business logic orchestration.

        Args:
            camera_data: Dictionary containing camera configuration

        Returns:
            Created Camera model instance
        """
        # Business Logic: Calculate initial next capture time
        capture_interval = camera_data.get("capture_interval", 300)  # default 5 minutes
        from datetime import datetime, timedelta

        next_capture_at = datetime.now() + timedelta(seconds=capture_interval)

        # Add next capture time to camera data
        camera_data_with_timing = {**camera_data, "next_capture_at": next_capture_at}

        # Create camera via database operations (pure CRUD)
        created_camera = await self.camera_ops.create_camera(camera_data_with_timing)

        # Business Logic: Broadcast event after successful creation
        await self.db.broadcast_event(
            "camera_created", {"camera": created_camera.model_dump()}
        )

        logger.info(f"Created camera: {created_camera.name} (ID: {created_camera.id})")
        return created_camera

    async def update_camera(
        self, camera_id: int, camera_data: Dict[str, Any]
    ) -> Camera:
        """
        Update an existing camera with business logic orchestration.

        Args:
            camera_id: ID of the camera to update
            camera_data: Dictionary containing updated camera data

        Returns:
            Updated Camera model instance
        """
        # Business Logic: If capture interval changed, update next capture time
        if "capture_interval" in camera_data:
            from datetime import datetime, timedelta

            capture_interval = camera_data["capture_interval"]
            next_capture_at = datetime.now() + timedelta(seconds=capture_interval)
            camera_data = {**camera_data, "next_capture_at": next_capture_at}

        # Update camera via database operations (pure CRUD)
        updated_camera = await self.camera_ops.update_camera(camera_id, camera_data)

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

    def update_next_capture_time(
        self, camera_id: int, next_capture_at: datetime
    ) -> bool:
        """
        Update the next capture time for a camera.

        Args:
            camera_id: ID of the camera
            next_capture_at: Next capture timestamp

        Returns:
            True if update was successful
        """
        return self.camera_ops.update_next_capture_time(camera_id, next_capture_at)

    def get_camera_corruption_settings(
        self, camera_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get camera-specific corruption detection settings.

        Args:
            camera_id: ID of the camera

        Returns:
            Dictionary containing corruption settings, or None if not found
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
