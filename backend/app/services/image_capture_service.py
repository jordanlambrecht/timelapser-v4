# backend/app/services/image_capture_service.py
"""
Image Capture Service - RTSP capture coordination business logic.

Responsibilities:
- Capture workflow orchestration
- Corruption detection integration
- Retry logic
- Health status updates
- Thumbnail generation coordination

Interactions:
- Uses rtsp_utils for capture
- CorruptionService for quality analysis
- ImageService for metadata
- thumbnail_utils for processing
"""

import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.camera_operations import SyncCameraOperations
from ..database.image_operations import SyncImageOperations
from ..database.settings_operations import SyncSettingsOperations
from ..models.image_model import Image, ImageCreate
from ..models.camera_model import Camera
from ..models.shared_models import (
    ImageCapturedEvent,
    CameraConnectivityTestResult,
    CameraCaptureWorkflowResult,
    CameraHealthMonitoringResult,
    CameraCaptureScheduleResult,
    ThumbnailGenerationResult,
    RTSPCaptureResult,
    CorruptionDetectionResult,
    BulkCaptureResult,
)
from ..utils import timezone_utils

from ..constants import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_IMAGE_EXTENSION,
    GENERATE_ALL_THUMBNAIL_SIZES,
    IMAGE_SIZE_VARIANTS,
    THUMBNAIL_DIMENSIONS,
    RETRY_BACKOFF_BASE,
    CAMERA_CAPTURE_SUCCESS,
    CAMERA_CAPTURE_FAILED,
    CAMERA_CONNECTION_FAILED,
    CAMERA_OFFLINE,
    EVENT_IMAGE_CAPTURED,
    CORRUPTION_ACTION_SAVED,
    CORRUPTION_ACTION_DISCARDED,
    CORRUPTION_ACTION_RETRIED,
    CAMERA_NOT_FOUND,
    IMAGE_NOT_FOUND,
    FILE_NOT_FOUND,
)
from .rtsp_capture_service import RTSPCaptureService


class ImageCaptureService:
    """
    RTSP capture coordination business logic using dependency injection.

    Follows layered architecture: Service Layer -> Data Layer -> Database
    """

    def __init__(
        self,
        db: SyncDatabase,
        camera_ops: SyncCameraOperations,
        image_ops: SyncImageOperations,
        settings_ops: SyncSettingsOperations,
        corruption_service=None,
        image_service=None,
    ):
        """Initialize with all dependencies injected (no direct instantiation)."""
        self.db = db
        self.camera_ops = camera_ops
        self.image_ops = image_ops
        self.settings_ops = settings_ops
        self.corruption_service = corruption_service
        self.image_service = image_service

        self.rtsp_capture = RTSPCaptureService(self.db)

    def test_camera_connection(self, camera_id: int) -> CameraConnectivityTestResult:
        """
        Test RTSP connectivity for a camera by ID and return a Pydantic model.

        Args:
            camera_id: ID of the camera to test

        Returns:
            CameraConnectivityTestResult
        """
        camera = self._get_camera_with_validation(camera_id)
        if not camera:
            return CameraConnectivityTestResult(
                success=False,
                camera_id=camera_id,
                rtsp_url="",
                connection_status="not_found",
                error=CAMERA_NOT_FOUND,
                test_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                    self.db
                ),
            )

        rtsp_url = getattr(camera, "rtsp_url", None)
        if not rtsp_url:
            return CameraConnectivityTestResult(
                success=False,
                camera_id=camera_id,
                rtsp_url="",
                connection_status="no_rtsp_url",
                error=CAMERA_CONNECTION_FAILED,
                test_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                    self.db
                ),
            )

        result = self.test_rtsp_connection(camera_id, rtsp_url)
        return result

    def capture_and_process_image(self, camera_id: int) -> CameraCaptureWorkflowResult:
        """
        Capture and process a single image with full workflow orchestration.

        Returns:
            CameraCaptureWorkflowResult with structured capture results
        """
        camera = self._get_camera_with_validation(camera_id)
        if not camera:
            connectivity = CameraConnectivityTestResult(
                success=False,
                camera_id=camera_id,
                rtsp_url="",
                connection_status="camera_not_found",
                error=CAMERA_NOT_FOUND,
                test_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                    self.db
                ),
            )
            return CameraCaptureWorkflowResult(
                workflow_status="failed",
                camera_id=camera_id,
                connectivity=connectivity,
                health_monitoring=CameraHealthMonitoringResult(
                    success=False,
                    camera_id=camera_id,
                    monitoring_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                        self.db
                    ),
                    error=CAMERA_NOT_FOUND,
                ),
                capture_scheduling=CameraCaptureScheduleResult(
                    success=False, camera_id=camera_id, error=CAMERA_NOT_FOUND
                ),
                overall_success=False,
                error=CAMERA_NOT_FOUND,
            )

        logger.info(f"📸 Starting capture workflow for camera {camera.name}")

        # Test RTSP connectivity first
        connectivity_result = self.test_rtsp_connection(camera_id, camera.rtsp_url)
        if not connectivity_result.success:
            logger.warning(
                f"RTSP connectivity failed for camera {camera_id}: {connectivity_result.error}"
            )
            self._update_camera_connectivity(
                camera_id, False, connectivity_result.error
            )

            return CameraCaptureWorkflowResult(
                workflow_status="failed",
                camera_id=camera_id,
                connectivity=connectivity_result,
                health_monitoring=CameraHealthMonitoringResult(
                    success=False,
                    camera_id=camera_id,
                    monitoring_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                        self.db
                    ),
                    error=CAMERA_CONNECTION_FAILED,
                ),
                capture_scheduling=CameraCaptureScheduleResult(
                    success=False, camera_id=camera_id, error=CAMERA_CONNECTION_FAILED
                ),
                overall_success=False,
                error=CAMERA_CONNECTION_FAILED,
            )

        # Perform actual image capture
        capture_result = self._coordinate_rtsp_capture(camera_id, camera.rtsp_url)
        if not capture_result.success:
            logger.error(
                f"Image capture failed for camera {camera_id}: {capture_result.error}"
            )
            return CameraCaptureWorkflowResult(
                workflow_status="failed",
                camera_id=camera_id,
                connectivity=connectivity_result,
                health_monitoring=CameraHealthMonitoringResult(
                    success=False,
                    camera_id=camera_id,
                    monitoring_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                        self.db
                    ),
                    error=CAMERA_CAPTURE_FAILED,
                ),
                capture_scheduling=CameraCaptureScheduleResult(
                    success=False, camera_id=camera_id, error=CAMERA_CAPTURE_FAILED
                ),
                overall_success=False,
                error=CAMERA_CAPTURE_FAILED,
            )

        # Coordinate corruption detection if enabled and image path exists
        quality_result = None
        if (
            getattr(camera, "corruption_detection_enabled", False)
            and self.corruption_service
            and capture_result.image_path
        ):
            quality_result = self._coordinate_corruption_detection(
                camera_id, capture_result.image_path
            )

        # Coordinate thumbnail generation
        thumbnail_result = None
        if capture_result.image_id:
            thumbnail_result = self._coordinate_thumbnail_generation(
                capture_result.image_id
            )

        # Update camera health status
        self._update_camera_connectivity(camera_id, True)

        logger.info(f"✅ Capture workflow completed for camera {camera_id}")

        return CameraCaptureWorkflowResult(
            workflow_status="completed",
            camera_id=camera_id,
            connectivity=connectivity_result,
            health_monitoring=CameraHealthMonitoringResult(
                success=True,
                camera_id=camera_id,
                monitoring_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                    self.db
                ),
            ),
            capture_scheduling=CameraCaptureScheduleResult(
                success=True,
                camera_id=camera_id,
                scheduled_at=timezone_utils.get_timezone_aware_timestamp_sync(self.db),
                message="Image captured and processed successfully",
            ),
            overall_success=True,
        )

    def test_rtsp_connection(
        self, camera_id: int, rtsp_url: str
    ) -> CameraConnectivityTestResult:
        """Test RTSP connectivity by attempting to capture a frame."""
        try:
            # Use RTSPCapture to test actual RTSP connection
            result = self.rtsp_capture.test_rtsp_connection(camera_id, rtsp_url)
            return result

        except Exception as e:
            logger.error(f"Failed to test RTSP connection for {rtsp_url}: {e}")
            return CameraConnectivityTestResult(
                success=False,
                camera_id=camera_id,
                rtsp_url=rtsp_url,
                response_time_ms=None,
                connection_status="error",
                error=str(e),
                test_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                    self.db
                ),
            )

    def capture_images_for_active_cameras(self) -> BulkCaptureResult:
        """Capture images for all active cameras with proper workflow orchestration."""
        active_cameras = self._get_active_cameras()
        capture_results = []
        successful_captures = 0
        failed_captures = 0
        start_time = time.time()

        logger.info(f"Starting capture cycle for {len(active_cameras)} active cameras")

        for camera in active_cameras:
            if camera.active_timelapse_id:
                result = self.capture_and_process_image(camera.id)
                if result.overall_success:
                    successful_captures += 1
                    capture_results.append(
                        {
                            "camera_id": camera.id,
                            "camera_name": camera.name,
                            "status": "success",
                            "workflow_status": result.workflow_status,
                        }
                    )
                else:
                    failed_captures += 1
                    capture_results.append(
                        {
                            "camera_id": camera.id,
                            "camera_name": camera.name,
                            "status": "failed",
                            "error": result.error,
                        }
                    )
            else:
                logger.debug(f"Skipping camera {camera.id} - no active timelapse")
                capture_results.append(
                    {
                        "camera_id": camera.id,
                        "camera_name": camera.name,
                        "status": "skipped",
                        "reason": "no active timelapse",
                    }
                )

        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"📸 Completed capture cycle: {successful_captures} successful, {failed_captures} failed"
        )

        return BulkCaptureResult(
            total_cameras=len(active_cameras),
            successful_captures=successful_captures,
            failed_captures=failed_captures,
            capture_results=capture_results,
            processing_time_ms=processing_time_ms,
            message=f"Bulk capture completed: {successful_captures}/{len(active_cameras)} successful",
        )

    def retry_failed_capture(
        self, camera_id: int, max_retries: int = DEFAULT_MAX_RETRIES
    ) -> CameraCaptureWorkflowResult:
        """Retry logic for failed captures with exponential backoff."""
        last_result = None

        for attempt in range(max_retries):
            logger.info(
                f"Capture attempt {attempt + 1}/{max_retries} for camera {camera_id}"
            )

            result = self.capture_and_process_image(camera_id)
            if result.overall_success:
                logger.info(
                    f"Capture succeeded on attempt {attempt + 1} for camera {camera_id}"
                )
                return result

            last_result = result
            if attempt < max_retries - 1:
                wait_time = RETRY_BACKOFF_BASE**attempt
                logger.info(f"Capture failed, waiting {wait_time}s before retry")
                time.sleep(wait_time)

        logger.error(f"All capture attempts failed for camera {camera_id}")

        # Return the last failed result with updated error message
        if last_result:
            last_result.error = (
                f"Failed after {max_retries} attempts: {last_result.error}"
            )
            last_result.workflow_status = "failed_after_retries"
            return last_result
        else:
            # Fallback if no result was captured
            return CameraCaptureWorkflowResult(
                workflow_status="failed_after_retries",
                camera_id=camera_id,
                connectivity=CameraConnectivityTestResult(
                    success=False,
                    camera_id=camera_id,
                    rtsp_url="",
                    connection_status="retry_failed",
                    error=f"Failed after {max_retries} attempts",
                    test_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                        self.db
                    ),
                ),
                health_monitoring=CameraHealthMonitoringResult(
                    success=False,
                    camera_id=camera_id,
                    monitoring_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                        self.db
                    ),
                    error=f"Failed after {max_retries} attempts",
                ),
                capture_scheduling=CameraCaptureScheduleResult(
                    success=False,
                    camera_id=camera_id,
                    error=f"Failed after {max_retries} attempts",
                ),
                overall_success=False,
                error=f"Failed after {max_retries} attempts",
            )

    def schedule_capture(
        self, camera_id: int, rtsp_url: str
    ) -> CameraCaptureWorkflowResult:
        """Schedule image capture for coordination with CameraService."""
        logger.info(f"Scheduling immediate capture for camera {camera_id}")
        return self.capture_and_process_image(camera_id)

    def _coordinate_rtsp_capture(
        self, camera_id: int, rtsp_url: str
    ) -> RTSPCaptureResult:
        """Coordinate RTSP capture using actual RTSP service."""
        try:
            logger.info(
                f"Attempting RTSP capture for camera {camera_id} from {rtsp_url}"
            )

            # Get camera and timelapse info
            camera = self.camera_ops.get_camera_by_id(camera_id)
            if not camera or not camera.active_timelapse_id:
                return RTSPCaptureResult(
                    success=False, error=f"Camera {camera_id} has no active timelapse"
                )

            # Use RTSPCaptureService to capture actual frame (entity-based)
            capture_result = self.rtsp_capture.capture_image_entity_based(
                camera_id=camera_id,
                timelapse_id=camera.active_timelapse_id,
                rtsp_url=rtsp_url,
                camera_name=camera.name,
            )

            success = capture_result.success
            message = getattr(capture_result, "message", None)
            filepath = getattr(capture_result, "image_path", None)

            if success and filepath:
                # Create ImageCreate model for validation
                image_create_data = ImageCreate(
                    camera_id=camera_id,
                    timelapse_id=camera.active_timelapse_id,
                    file_path=filepath,
                    day_number=self._calculate_day_number(
                        camera_id,
                        timezone_utils.get_timezone_aware_timestamp_sync(self.db),
                    ),
                    file_size=None,  # File size will be calculated by database
                    corruption_score=100,  # Default perfect score
                    is_flagged=False,  # Default not flagged
                    corruption_details=None,  # No corruption details initially
                )

                try:
                    image_record = self.image_ops.record_captured_image(
                        image_create_data.model_dump()
                    )
                    return RTSPCaptureResult(
                        success=True,
                        message=message,
                        image_id=image_record.id,
                        image_path=image_record.file_path,
                        file_size=image_record.file_size,
                        metadata={
                            "format": "JPEG",
                            "capture_method": "rtsp_capture",
                            "rtsp_url": rtsp_url,
                            "timelapse_id": camera.active_timelapse_id,
                            "day_number": image_record.day_number,
                        },
                    )
                except Exception as save_error:
                    logger.error(
                        f"Failed to save captured image for camera {camera_id}: {save_error}"
                    )
                    return RTSPCaptureResult(
                        success=False, error=f"Image save failed: {str(save_error)}"
                    )
            else:
                # RTSP capture failed or no filepath provided
                error_msg = (
                    message if not success else "No file path returned from capture"
                )
                return RTSPCaptureResult(success=False, error=error_msg)

        except Exception as e:
            logger.error(
                f"RTSP capture coordination failed for camera {camera_id}: {e}"
            )
            return RTSPCaptureResult(success=False, error=str(e))

    def _coordinate_corruption_detection(
        self, camera_id: int, image_path: Optional[str]
    ) -> CorruptionDetectionResult:
        """Coordinate corruption detection via CorruptionService."""
        if not image_path:
            return CorruptionDetectionResult(
                success=False,
                camera_id=camera_id,
                image_path="",
                error="No image path provided for corruption detection",
            )

        try:
            if self.corruption_service:
                # Call corruption service and convert result to CorruptionDetectionResult
                detection_result = self.corruption_service.analyze_image_quality(
                    camera_id=camera_id, image_path=image_path
                )

                # Extract data from service result (assuming it returns a dict)
                quality_score = detection_result.get("quality_score")
                is_corrupted = detection_result.get(
                    "is_corrupted", quality_score < 70 if quality_score else None
                )
                action_taken = detection_result.get("action_taken", "saved")
                detection_details = detection_result.get("detection_details")
                processing_time_ms = detection_result.get("processing_time_ms")

                logger.info(
                    f"Corruption detection completed for camera {camera_id}: {quality_score}"
                )

                return CorruptionDetectionResult(
                    success=detection_result.get("success", True),
                    camera_id=camera_id,
                    image_path=image_path,
                    quality_score=quality_score,
                    is_corrupted=is_corrupted,
                    action_taken=action_taken,
                    detection_details=detection_details,
                    processing_time_ms=processing_time_ms,
                    error=detection_result.get("error"),
                )

            logger.warning(f"CorruptionService not available for camera {camera_id}")
            return CorruptionDetectionResult(
                success=False,
                camera_id=camera_id,
                image_path=image_path,
                error="CorruptionService not configured",
            )

        except Exception as e:
            logger.error(
                f"Corruption detection coordination failed for camera {camera_id}: {e}"
            )
            return CorruptionDetectionResult(
                success=False,
                camera_id=camera_id,
                image_path=image_path or "",
                error=str(e),
            )

    def _coordinate_thumbnail_generation(
        self, image_id: int
    ) -> ThumbnailGenerationResult:
        """Coordinate thumbnail generation using basic implementation."""
        from PIL import Image
        from ..utils.file_helpers import validate_file_path, ensure_directory_exists

        # Get image record from database
        image_record = self.image_ops.get_image_by_id(image_id)
        if not image_record:
            return ThumbnailGenerationResult(
                success=False,
                image_id=image_id,
                error=IMAGE_NOT_FOUND,
            )

        # Construct full image path using settings from database
        camera_id = image_record.camera_id
        data_directory = self.settings_ops.get_setting("data_directory")
        if not data_directory:
            return ThumbnailGenerationResult(
                success=False,
                image_id=image_id,
                error="Data directory setting not configured",
            )
        
        image_path = (
            Path(data_directory)
            / "cameras"
            / f"camera-{camera_id}"
            / "images"
            / image_record.file_path
        )

        if not image_path.exists():
            return ThumbnailGenerationResult(
                success=False,
                image_id=image_id,
                error=FILE_NOT_FOUND,
            )

        # Generate thumbnails using constants
        thumbnail_results = {}

        with Image.open(image_path) as img:
            for size_name in IMAGE_SIZE_VARIANTS:
                if size_name == "full":
                    continue  # Skip full, as it's the original image
                dimensions = THUMBNAIL_DIMENSIONS.get(size_name)
                if not dimensions:
                    logger.warning(
                        f"No dimensions defined for thumbnail size '{size_name}'"
                    )
                    continue
                try:
                    # Create thumbnail directory
                    thumbnail_dir = (
                        Path(data_directory)
                        / "cameras"
                        / f"camera-{camera_id}"
                        / "thumbnails"
                        / size_name
                    )
                    ensure_directory_exists(str(thumbnail_dir))

                    # Generate thumbnail filename
                    base_name = Path(image_record.file_path).stem
                    thumbnail_filename = f"{base_name}_{size_name}.jpg"
                    thumbnail_path = thumbnail_dir / thumbnail_filename

                    # Create thumbnail with proper aspect ratio
                    img_copy = img.copy()
                    img_copy.thumbnail(dimensions, Image.Resampling.LANCZOS)

                    # Save thumbnail
                    img_copy.save(thumbnail_path, "JPEG", quality=85, optimize=True)

                    # Calculate relative path for database
                    relative_thumbnail_path = str(
                        thumbnail_path.relative_to(
                            Path(data_directory) / "cameras" / f"camera-{camera_id}"
                        )
                    )

                    thumbnail_results[size_name] = {
                        "path": str(thumbnail_path),
                        "relative_path": relative_thumbnail_path,
                        "size_bytes": thumbnail_path.stat().st_size,
                        "dimensions": img_copy.size,
                    }

                except Exception as thumb_error:
                    logger.error(
                        f"Failed to generate {size_name} thumbnail for image {image_id}: {thumb_error}"
                    )
                    thumbnail_results[size_name] = {"error": str(thumb_error)}

        # Update image record with thumbnail paths
        update_data = {}
        if (
            "thumbnail" in thumbnail_results
            and "path" in thumbnail_results["thumbnail"]
        ):
            update_data["thumbnail_path"] = thumbnail_results["thumbnail"][
                "relative_path"
            ]
            update_data["thumbnail_size"] = thumbnail_results["thumbnail"]["size_bytes"]

        if "small" in thumbnail_results and "path" in thumbnail_results["small"]:
            update_data["small_path"] = thumbnail_results["small"]["relative_path"]
            update_data["small_size"] = thumbnail_results["small"]["size_bytes"]

        if update_data:
            try:
                self.image_ops.update_image_thumbnails(image_id, update_data)
            except Exception as update_error:
                logger.error(
                    f"Failed to update image thumbnails in database: {update_error}"
                )

        logger.info(
            f"Generated thumbnails for image {image_id}: {list(thumbnail_results.keys())}"
        )

        # Extract thumbnail paths for ThumbnailGenerationResult
        thumbnail_path = None
        small_path = None
        thumbnail_size = None
        small_size = None

        if (
            "thumbnail" in thumbnail_results
            and "path" in thumbnail_results["thumbnail"]
        ):
            thumbnail_path = thumbnail_results["thumbnail"]["relative_path"]
            thumbnail_size = thumbnail_results["thumbnail"]["size_bytes"]

        if "small" in thumbnail_results and "path" in thumbnail_results["small"]:
            small_path = thumbnail_results["small"]["relative_path"]
            small_size = thumbnail_results["small"]["size_bytes"]

        return ThumbnailGenerationResult(
            success=True,
            image_id=image_id,
            thumbnail_path=thumbnail_path,
            small_path=small_path,
            thumbnail_size=thumbnail_size,
            small_size=small_size,
        )

    def _save_captured_image(
        self, camera_id: int, image_data: bytes, metadata: Dict[str, Any]
    ) -> Image:
        """Save captured image to filesystem and database using timezone-aware timestamps."""
        # Get timezone-aware timestamp using database settings (cache-backed)
        timezone_str = timezone_utils.get_timezone_from_cache_sync(self.db)
        timestamp = timezone_utils.create_timezone_aware_datetime(timezone_str)

        # Generate file paths using file_helpers
        filename = f"{timestamp.strftime('%H-%M-%S')}{DEFAULT_IMAGE_EXTENSION}"

        # Get data directory from database settings
        data_directory = self.settings_ops.get_setting("data_directory")
        if not data_directory:
            raise ValueError("Data directory setting not configured")
        
        camera_dir = (
            Path(data_directory)
            / "cameras"
            / f"camera-{camera_id}"
            / "images"
            / timestamp.strftime("%Y-%m-%d")
        )

        # Create directory structure
        camera_dir.mkdir(parents=True, exist_ok=True)

        # Save image file
        image_path = camera_dir / filename
        with open(image_path, "wb") as f:
            f.write(image_data)

        # Create relative path for database
        relative_path = str(
            image_path.relative_to(
                Path(data_directory) / "cameras" / f"camera-{camera_id}" / "images"
            )
        )

        # Create image record using Pydantic model for validation
        image_create_data = ImageCreate(
            camera_id=camera_id,
            timelapse_id=self._get_active_timelapse_id(camera_id),
            file_path=relative_path,
            day_number=self._calculate_day_number(camera_id, timestamp),
            file_size=len(image_data),
            corruption_score=100,  # Default perfect score
            is_flagged=False,  # Default not flagged
            corruption_details=None,  # No corruption details initially
        )

        # Convert to dict for database operation
        image_record = self.image_ops.record_captured_image(
            image_create_data.model_dump()
        )
        logger.info(f"Saved image {image_record.id} to {relative_path}")
        return image_record

    def _get_camera_with_validation(self, camera_id: int) -> Optional[Camera]:
        """Get camera details with error handling."""
        try:
            camera = self.camera_ops.get_camera_by_id(camera_id)
            if not camera:
                logger.error(f"Camera {camera_id} not found")
            return camera
        except Exception as e:
            logger.error(f"Database error getting camera {camera_id}: {e}")
            return None

    def _get_active_cameras(self) -> List[Camera]:
        """Get active cameras with error handling."""
        try:
            return self.camera_ops.get_active_cameras()
        except Exception as e:
            logger.error(f"Database error getting active cameras: {e}")
            return []

    def _update_camera_connectivity(
        self, camera_id: int, success: bool, error: Optional[str] = None
    ):
        """Update camera connectivity status with error handling."""
        try:
            self.camera_ops.update_camera_connectivity(camera_id, success, error)
        except Exception as e:
            logger.error(
                f"Database error updating camera {camera_id} connectivity: {e}"
            )

    def _get_active_timelapse_id(self, camera_id: int) -> int:
        """Get active timelapse ID for camera with error handling."""
        try:
            camera = self.camera_ops.get_camera_by_id(camera_id)
            if camera and camera.active_timelapse_id:
                return camera.active_timelapse_id
            return 1  # Default fallback value
        except Exception as e:
            logger.error(
                f"Database error getting active timelapse for camera {camera_id}: {e}"
            )
            return 1  # Default fallback value

    def _calculate_day_number(self, camera_id: int, timestamp) -> int:
        """Calculate day number for timelapse sequence."""
        # This could be enhanced with actual business logic
        # For now, return a simple day-based calculation
        return 1


class AsyncImageCaptureService:
    """
    Async wrapper for ImageCaptureService coordination.

    Provides async interface while maintaining sync capture operations for reliability.
    """

    def __init__(self, db: AsyncDatabase, sync_capture_service: ImageCaptureService):
        """Initialize with async database and sync capture service."""
        self.db = db
        self.sync_capture_service = sync_capture_service

    async def schedule_capture(
        self, camera_id: int, rtsp_url: str
    ) -> CameraCaptureWorkflowResult:
        """Async coordination interface for capture scheduling."""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.sync_capture_service.capture_and_process_image, camera_id
            )

            # SSE broadcasting handled by higher-level service layer

            return result

        except Exception as e:
            logger.error(f"Async capture scheduling failed for camera {camera_id}: {e}")
            # Return a failed workflow result
            return CameraCaptureWorkflowResult(
                workflow_status="failed",
                camera_id=camera_id,
                connectivity=CameraConnectivityTestResult(
                    success=False,
                    camera_id=camera_id,
                    rtsp_url="",
                    connection_status="async_error",
                    error=str(e),
                    test_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                        self.sync_capture_service.db
                    ),
                ),
                health_monitoring=CameraHealthMonitoringResult(
                    success=False,
                    camera_id=camera_id,
                    monitoring_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                        self.sync_capture_service.db
                    ),
                    error=str(e),
                ),
                capture_scheduling=CameraCaptureScheduleResult(
                    success=False, camera_id=camera_id, error=str(e)
                ),
                overall_success=False,
                error=str(e),
            )

    async def test_rtsp_connection(
        self, camera_id: int, rtsp_url: str
    ) -> CameraConnectivityTestResult:
        """Async coordination interface for RTSP connection testing."""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.sync_capture_service.test_rtsp_connection,
                camera_id,
                rtsp_url,
            )
            return result
        except Exception as e:
            logger.error(f"Async RTSP connection test failed for {rtsp_url}: {e}")
            return CameraConnectivityTestResult(
                success=False,
                camera_id=camera_id,
                rtsp_url=rtsp_url,
                response_time_ms=None,
                connection_status="async_error",
                error=str(e),
                test_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(
                    self.sync_capture_service.db
                ),
            )
