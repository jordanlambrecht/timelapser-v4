# backend/app/services/rtsp_capture_service.py
"""
RTSP Capture Service - High-level RTSP capture orchestration.

This service coordinates RTSP capture operations using the established
architectural patterns. It orchestrates between utils, other services,
and the database operations layer.

Responsibilities:
- RTSP capture workflow coordination
- Integration with ImageCaptureService
- Coordination with CorruptionService
- File path management using FileHelpers
- Event broadcasting via SSE

Dependencies:
- RTSPUtils for low-level capture operations
- ImageCaptureService for capture workflow
- CorruptionService for quality analysis
- FileHelpers for path operations
- Database operations via composition
"""

import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
from loguru import logger

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.image_operations import SyncImageOperations
from ..database.camera_operations import SyncCameraOperations
from ..database.timelapse_operations import SyncTimelapseOperations
from ..database.settings_operations import SyncSettingsOperations

from ..models.shared_models import (
    RTSPCaptureResult,
    CameraConnectivityTestResult,
    CorruptionDetectionResult,
    ThumbnailGenerationResult,
)
from ..models.image_model import ImageCreate

from ..utils import rtsp_utils, file_helpers, thumbnail_utils, timezone_utils
from ..exceptions import RTSPConnectionError, RTSPCaptureError

from ..constants import (
    DEFAULT_MAX_RETRIES,
    CAMERA_CONNECTION_SUCCESS,
    CAMERA_CONNECTION_FAILED,
    CAMERA_CAPTURE_SUCCESS,
    CAMERA_CAPTURE_FAILED,
    EVENT_IMAGE_CAPTURED,
    CORRUPTION_ACTION_SAVED,
    CORRUPTION_ACTION_DISCARDED,
    DEFAULT_IMAGE_EXTENSION,
    THUMBNAIL_DIMENSIONS,
    DEFAULT_RTSP_QUALITY,
    DEFAULT_RTSP_TIMEOUT_SECONDS,
    DEFAULT_CORRUPTION_SCORE,
    DEFAULT_IS_FLAGGED,
)


class RTSPCaptureService:
    """
    High-level RTSP capture service following architectural patterns.

    Uses composition pattern with dependency injection for database access.
    Coordinates with other services for complete capture workflow.
    """

    def __init__(self, db: SyncDatabase):
        """Initialize service with database dependency injection."""
        self.db = db
        self.image_ops = SyncImageOperations(db)
        self.camera_ops = SyncCameraOperations(db)
        self.timelapse_ops = SyncTimelapseOperations(db)
        self.settings_ops = SyncSettingsOperations(db)

        # Cache commonly used settings
        self._capture_quality = None
        self._timeout_seconds = None

    def _get_capture_settings(self) -> Dict[str, Any]:
        """Get capture settings from database using proper operations layer."""
        try:
            # Use settings operations to get settings
            quality_setting = self.settings_ops.get_setting("image_quality")
            timeout_setting = self.settings_ops.get_setting("rtsp_timeout_seconds")

            # Safe int conversion for quality setting
            quality = DEFAULT_RTSP_QUALITY
            if quality_setting:
                try:
                    quality = int(quality_setting)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid image_quality setting '{quality_setting}', using default {DEFAULT_RTSP_QUALITY}")

            # Safe int conversion for timeout setting
            timeout = DEFAULT_RTSP_TIMEOUT_SECONDS
            if timeout_setting:
                try:
                    timeout = int(timeout_setting)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid rtsp_timeout_seconds setting '{timeout_setting}', using default {DEFAULT_RTSP_TIMEOUT_SECONDS}")

            return {
                "quality": quality,
                "timeout": timeout,
            }
        except Exception as e:
            logger.warning(f"Failed to get capture settings, using defaults: {e}")
            return {
                "quality": DEFAULT_RTSP_QUALITY,
                "timeout": DEFAULT_RTSP_TIMEOUT_SECONDS,
            }

    def test_rtsp_connection(
        self, camera_id: int, rtsp_url: str
    ) -> CameraConnectivityTestResult:
        """
        Test RTSP connection using utilities layer.

        Args:
            camera_id: ID of camera to test
            rtsp_url: RTSP URL to test

        Returns:
            CameraConnectivityTestResult with test results
        """
        try:
            start_time = time.time()

            settings = self._get_capture_settings()
            success, message = rtsp_utils.test_rtsp_connection(
                rtsp_url, timeout_seconds=settings["timeout"]
            )

            response_time_ms = (time.time() - start_time) * 1000

            return CameraConnectivityTestResult(
                success=success,
                camera_id=camera_id,
                rtsp_url=rtsp_url,
                response_time_ms=response_time_ms,
                connection_status="online" if success else "offline",
                error=None if success else message,
                test_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(self.db),
            )

        except Exception as e:
            logger.error(f"Error testing RTSP connection for camera {camera_id}: {e}")
            return CameraConnectivityTestResult(
                success=False,
                camera_id=camera_id,
                rtsp_url=rtsp_url,
                response_time_ms=None,
                connection_status="error",
                error=str(e),
                test_timestamp=timezone_utils.get_timezone_aware_timestamp_sync(self.db),
            )

    def capture_image_entity_based(
        self,
        camera_id: int,
        timelapse_id: int,
        rtsp_url: str,
        camera_name: Optional[str] = None,
    ) -> RTSPCaptureResult:
        """
        Capture image using entity-based file structure.

        Args:
            camera_id: ID of camera
            timelapse_id: ID of active timelapse
            rtsp_url: RTSP stream URL
            camera_name: Optional camera name for logging

        Returns:
            RTSPCaptureResult with capture results
        """
        try:
            logger.info(
                f"Starting entity-based capture for camera {camera_id}, timelapse {timelapse_id}"
            )

            # Get timelapse info for day number calculation
            timelapse = self.timelapse_ops.get_timelapse_by_id(timelapse_id)
            if not timelapse:
                return RTSPCaptureResult(
                    success=False, error=f"Timelapse {timelapse_id} not found"
                )

            # Calculate day number using timezone utilities
            current_date_str = timezone_utils.get_timezone_aware_date_sync(self.db)
            current_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()
            start_date = (
                timelapse.get("start_date")
                if isinstance(timelapse, dict)
                else getattr(timelapse, "start_date", None)
            )
            if not start_date:
                logger.warning(
                    f"Timelapse {timelapse_id} has no start_date, defaulting day_number to 1"
                )
                day_number = 1
            else:
                day_number = (current_date - start_date).days + 1

            # Generate entity-based file paths using file helpers
            frames_dir = file_helpers.ensure_entity_directory(
                camera_id=camera_id, timelapse_id=timelapse_id, subdirectory="frames"
            )

            # Generate filename using timezone utilities
            timestamp_str = timezone_utils.get_timezone_aware_timestamp_string_sync(
                self.db
            )
            filename = f"day{day_number:03d}_{timestamp_str}{DEFAULT_IMAGE_EXTENSION}"
            filepath = frames_dir / filename

            # Capture frame using RTSP utilities
            settings = self._get_capture_settings()
            frame = rtsp_utils.capture_with_retry(
                rtsp_url=rtsp_url,
                max_retries=DEFAULT_MAX_RETRIES,
                timeout_seconds=settings["timeout"],
            )

            if frame is None:
                return RTSPCaptureResult(
                    success=False, error="Failed to capture frame from RTSP stream"
                )

            # Save frame using RTSP utilities
            success, file_size = rtsp_utils.save_frame_to_file(
                frame=frame, filepath=filepath, quality=settings["quality"]
            )

            if not success:
                return RTSPCaptureResult(
                    success=False, error="Failed to save captured frame"
                )

            # Create relative path for database storage
            relative_path = file_helpers.get_relative_path(filepath)

            # Create image record using Pydantic model validation
            image_create = ImageCreate(
                camera_id=camera_id,
                timelapse_id=timelapse_id,
                file_path=str(relative_path),
                day_number=day_number,
                file_size=file_size,
                corruption_score=DEFAULT_CORRUPTION_SCORE,  # Will be updated by corruption service
                is_flagged=DEFAULT_IS_FLAGGED,
            )

            image_record = self.image_ops.record_captured_image(image_create.model_dump())
            image_id = image_record.id

            # SSE broadcasting handled by higher-level service layer

            return RTSPCaptureResult(
                success=True,
                message=CAMERA_CAPTURE_SUCCESS or "",
                image_id=image_id,
                image_path=str(filepath) if filepath else "",
                file_size=file_size,
                metadata={
                    "day_number": day_number,
                    "entity_based": True,
                    "timelapse_id": timelapse_id,
                },
            )

        except Exception as e:
            logger.error(f"Error in entity-based capture for camera {camera_id}: {e}")
            return RTSPCaptureResult(
                success=False, error=str(e) if e else "Unknown error"
            )

    def capture_image_with_thumbnails(
        self,
        camera_id: int,
        rtsp_url: str,
        camera_name: Optional[str] = None,
        generate_thumbnails: bool = True,
    ) -> RTSPCaptureResult:
        """
        Capture image with thumbnail generation (legacy date-based structure).

        Args:
            camera_id: ID of camera
            rtsp_url: RTSP stream URL
            camera_name: Optional camera name for logging
            generate_thumbnails: Whether to generate thumbnails

        Returns:
            RTSPCaptureResult with capture results
        """
        try:
            logger.info(f"Starting capture with thumbnails for camera {camera_id}")

            # Find active timelapse for this camera
            camera = self.camera_ops.get_camera_by_id(camera_id)
            if not camera or not getattr(camera, "active_timelapse_id", None):
                return RTSPCaptureResult(
                    success=False, error="No active timelapse found for camera"
                )
            timelapse_id = getattr(camera, "active_timelapse_id", None)
            # Calculate day number
            current_date_str = timezone_utils.get_timezone_aware_date_sync(self.db)
            current_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()
            start_date = getattr(camera, "timelapse_start_date", None)
            if not start_date:
                logger.warning(
                    f"Camera {camera_id} has no timelapse_start_date, defaulting day_number to 1"
                )
                day_number = 1
            else:
                day_number = (current_date - start_date).days + 1

            # Generate date-based file paths using file helpers
            date_str = timezone_utils.get_timezone_aware_date_sync(self.db)
            directories = file_helpers.ensure_camera_directories(
                camera_id=camera_id, date_str=date_str
            )

            # Generate filename using timezone utilities
            timestamp_str = timezone_utils.get_timezone_aware_timestamp_string_sync(
                self.db
            )
            filename = f"capture_{timestamp_str}{DEFAULT_IMAGE_EXTENSION}"
            filepath = directories["images"] / filename

            # Capture frame using RTSP utilities
            settings = self._get_capture_settings()
            frame = rtsp_utils.capture_with_retry(
                rtsp_url=rtsp_url,
                max_retries=DEFAULT_MAX_RETRIES,
                timeout_seconds=settings["timeout"],
            )

            if frame is None:
                return RTSPCaptureResult(
                    success=False, error="Failed to capture frame from RTSP stream"
                )

            # Save main frame
            success, file_size = rtsp_utils.save_frame_to_file(
                frame=frame, filepath=filepath, quality=settings["quality"]
            )

            if not success:
                return RTSPCaptureResult(
                    success=False, error="Failed to save captured frame"
                )

            # Generate thumbnails if requested - FIXED: use correct function name
            thumbnail_data = {}
            if generate_thumbnails:
                thumbnail_result = thumbnail_utils.generate_thumbnails_from_opencv(
                    cv_frame=frame, base_filename=filename, directories=directories
                )

                thumb = thumbnail_result.get("thumbnail")
                if thumb is not None:
                    thumbnail_data["thumbnail_path"] = thumb[0]
                    thumbnail_data["thumbnail_size"] = thumb[1]

                small = thumbnail_result.get("small")
                if small is not None:
                    thumbnail_data["small_path"] = small[0]
                    thumbnail_data["small_size"] = small[1]

            # Create relative path for database storage
            relative_path = file_helpers.get_relative_path(filepath)

            # Create image record with thumbnail data using Pydantic model validation
            image_create = ImageCreate(
                camera_id=camera_id,
                timelapse_id=timelapse_id,
                file_path=str(relative_path),
                day_number=day_number,
                file_size=file_size,
                corruption_score=DEFAULT_CORRUPTION_SCORE,  # Will be updated by corruption service
                is_flagged=DEFAULT_IS_FLAGGED,
                # Add thumbnail data if available
                thumbnail_path=thumbnail_data.get("thumbnail_path"),
                thumbnail_size=thumbnail_data.get("thumbnail_size"),
                small_path=thumbnail_data.get("small_path"),
                small_size=thumbnail_data.get("small_size"),
            )

            image_record = self.image_ops.record_captured_image(image_create.model_dump())
            image_id = image_record.id

            # SSE broadcasting handled by higher-level service layer

            return RTSPCaptureResult(
                success=True,
                message=CAMERA_CAPTURE_SUCCESS,
                image_id=image_id,
                image_path=str(filepath),
                file_size=file_size,
                metadata={
                    "day_number": day_number,
                    "entity_based": False,
                    "timelapse_id": timelapse_id,
                    "thumbnails_generated": bool(thumbnail_data),
                },
            )

        except Exception as e:
            logger.error(
                f"Error in capture with thumbnails for camera {camera_id}: {e}"
            )
            return RTSPCaptureResult(success=False, error=str(e))

    def capture_image_manual(
        self, camera_id: int, rtsp_url: str, camera_name: Optional[str] = None
    ) -> RTSPCaptureResult:
        """
        Manually triggered image capture.

        Determines capture method based on camera configuration and
        delegates to appropriate capture method.

        Args:
            camera_id: ID of camera
            rtsp_url: RTSP stream URL
            camera_name: Optional camera name for logging

        Returns:
            RTSPCaptureResult with capture results
        """
        try:
            # Get camera configuration to determine capture method
            camera = self.camera_ops.get_camera_by_id(camera_id)
            if not camera:
                return RTSPCaptureResult(
                    success=False, error=f"Camera {camera_id} not found"
                )

            # Check if camera has active timelapse
            active_timelapse_id = (
                camera.get("active_timelapse_id")
                if isinstance(camera, dict)
                else getattr(camera, "active_timelapse_id", None)
            )

            if active_timelapse_id:
                # Use entity-based capture for active timelapse
                return self.capture_image_entity_based(
                    camera_id=camera_id,
                    timelapse_id=active_timelapse_id,
                    rtsp_url=rtsp_url,
                    camera_name=camera_name,
                )
            else:
                # Use legacy capture with thumbnails
                return self.capture_image_with_thumbnails(
                    camera_id=camera_id,
                    rtsp_url=rtsp_url,
                    camera_name=camera_name,
                    generate_thumbnails=True,
                )

        except Exception as e:
            logger.error(f"Error in manual capture for camera {camera_id}: {e}")
            return RTSPCaptureResult(success=False, error=str(e))
