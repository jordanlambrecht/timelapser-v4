# backend/app/services/capture_pipeline/rtsp_service.py
"""
Capture Pipeline RTSP Service

Pure RTSP operations and frame capture functionality within the capture pipeline domain.

🎯 SERVICE SCOPE: Core RTSP/OpenCV capture operations only
- RTSP connectivity testing
- Frame capture with retry logic
- Image processing pipeline (crop, rotate, save)
- Resolution detection and validation
- Processing settings testing

📝 KEY ARCHITECTURAL BOUNDARIES:
- NO database operations (delegates to ImageService)
- NO business logic orchestration (delegates to WorkflowOrchestratorService)
- NO job queueing (delegates to JobCoordinationService)
- NO weather integration (delegates to workflow orchestrator)
- NO corruption detection (delegates to corruption pipeline services)

🔧 PURE RTSP OPERATIONS:
This service focuses exclusively on RTSP stream operations and image processing,
providing a clean interface for frame capture without external dependencies.
"""


import asyncio
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from loguru import logger
from urllib.parse import urlparse

from ...utils.time_utils import get_timezone_aware_timestamp_sync
from . import rtsp_utils

from ...database.core import SyncDatabase
from ...models.shared_models import RTSPCaptureResult, CameraConnectivityTestResult
from ...models.camera_model import CropRotationSettings, SourceResolution, Camera
from ...constants import (
    DEFAULT_RTSP_QUALITY,
    DEFAULT_RTSP_TIMEOUT_SECONDS,
    DEFAULT_MAX_RETRIES,
)

from ...database.camera_operations import SyncCameraOperations
from ...database.settings_operations import SyncSettingsOperations


class RTSPService:
    """
    Pure RTSP operations service for the capture pipeline domain.

    Focuses exclusively on RTSP stream operations and image processing
    without external business logic dependencies.

    Responsibilities:
    - RTSP connectivity testing
    - Frame capture with retry logic
    - Image processing (crop, rotation, quality)
    - Resolution detection
    - Processing settings validation
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize RTSP service with database connection.

        Args:
            db: Synchronized database connection for camera data access
        """
        self.db = db
        # Initialize database operations for camera data access

        self.camera_ops = SyncCameraOperations(db)
        self.settings_ops = SyncSettingsOperations(db)

    def test_connection(
        self, camera_id: int, rtsp_url: str
    ) -> CameraConnectivityTestResult:
        """
        Test RTSP connectivity for a camera stream.

        Performs pure connectivity testing without side effects.

        Args:
            camera_id: Camera identifier for result association
            rtsp_url: RTSP URL to test

        Returns:
            CameraConnectivityTestResult with test results and timing
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
                test_timestamp=get_timezone_aware_timestamp_sync(self.settings_ops),
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
                test_timestamp=get_timezone_aware_timestamp_sync(self.settings_ops),
            )

    def capture_frame_raw(
        self, rtsp_url: str, capture_settings: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Capture raw frame from RTSP stream.

        Pure frame capture operation without processing or saving.

        Args:
            rtsp_url: RTSP URL to capture from
            capture_settings: Capture configuration (timeout, quality)

        Returns:
            Raw frame data if successful, None if failed
        """
        try:

            frame = rtsp_utils.capture_with_retry(
                rtsp_url=rtsp_url,
                max_retries=capture_settings.get("max_retries", DEFAULT_MAX_RETRIES),
                timeout_seconds=capture_settings.get(
                    "timeout", DEFAULT_RTSP_TIMEOUT_SECONDS
                ),
            )

            return frame

        except Exception as e:
            logger.error(f"Failed to capture raw frame from {rtsp_url}: {e}")
            return None

    def capture_and_process_frame(
        self, camera: Camera, output_path: Path, capture_settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Capture frame and apply complete processing pipeline.

        Combines capture, processing, and saving into single operation.

        Args:
            camera: Camera configuration with processing settings
            output_path: File path for saving processed frame
            capture_settings: Capture configuration

        Returns:
            Processing result with success status and metadata
        """
        try:
            # Capture raw frame
            frame = self.capture_frame_raw(camera.rtsp_url, capture_settings)
            if frame is None:
                return {"success": False, "error": "Failed to capture raw frame"}

            # Apply processing pipeline
            result = self.apply_image_processing(
                frame,
                camera,
                output_path,
                capture_settings.get("quality", DEFAULT_RTSP_QUALITY),
            )

            return result

        except Exception as e:
            logger.error(
                f"Failed to capture and process frame for camera {camera.id}: {e}"
            )
            return {"success": False, "error": str(e)}

    def apply_image_processing(
        self, raw_frame: Any, camera: Camera, output_path: Path, quality: int = 95
    ) -> Dict[str, Any]:
        """
        Apply image processing pipeline to captured frame.

        Handles cropping, rotation, quality adjustment, and file saving.

        Args:
            raw_frame: Raw frame data from RTSP capture
            camera: Camera with processing settings
            output_path: Target file path for processed image
            quality: JPEG quality setting (1-100)

        Returns:
            Processing result with file size and success status
        """
        try:

            # Get processing settings from camera crop_rotation_settings
            processing_settings = None
            if camera.crop_rotation_enabled:
                crop_settings_data = getattr(camera, "crop_rotation_settings", {}) or {}
                if crop_settings_data:
                    processing_settings = crop_settings_data

            # Fallback to legacy rotation
            legacy_rotation = (
                getattr(camera, "rotation", 0) if processing_settings is None else 0
            )

            # Save frame with processing
            success, file_size = rtsp_utils.save_frame_to_file(
                frame=raw_frame,
                filepath=output_path,
                quality=quality,
                rotation=legacy_rotation,
                processing_settings=processing_settings,
            )

            if not success:
                return {"success": False, "error": "Failed to save processed frame"}

            return {"success": True, "file_size": file_size}

        except Exception as e:
            return {"success": False, "error": f"Image processing failed: {e}"}

    def detect_source_resolution(self, camera_id: int) -> Optional[SourceResolution]:
        """
        Detect native resolution of camera stream.

        Captures frame to determine actual stream resolution.

        Args:
            camera_id: Camera identifier

        Returns:
            SourceResolution if detected successfully, None if failed
        """
        try:

            camera = self._get_camera_with_validation(camera_id)
            if not camera:
                return None

            rtsp_url = camera.rtsp_url
            if not rtsp_url:
                logger.error(f"No RTSP URL for camera {camera_id}")
                return None

            # Capture a frame to detect resolution
            logger.debug(f"Detecting source resolution for camera {camera_id}")
            settings = self._get_capture_settings()
            frame = rtsp_utils.capture_with_retry(
                rtsp_url, max_retries=2, timeout_seconds=settings["timeout"]
            )

            if frame is None:
                logger.warning(
                    f"Failed to capture frame for resolution detection: camera {camera_id}"
                )
                return None

            # Get frame resolution
            width, height = rtsp_utils.get_frame_resolution(frame)
            if width == 0 or height == 0:
                logger.error(f"Invalid resolution detected: {width}x{height}")
                return None

            # Create resolution model
            now = get_timezone_aware_timestamp_sync(self.settings_ops)
            resolution = SourceResolution(width=width, height=height, detected_at=now)

            logger.info(
                f"Detected source resolution for camera {camera_id}: {width}x{height}"
            )
            return resolution

        except Exception as e:
            logger.error(
                f"Error detecting source resolution for camera {camera_id}: {e}"
            )
            return None

    def test_crop_settings(
        self, camera_id: int, settings: CropRotationSettings
    ) -> Optional[Tuple[int, int]]:
        """
        Test crop/rotation settings with live capture.

        Validates processing settings by applying them to test frame.

        Args:
            camera_id: Camera identifier
            settings: Crop/rotation settings to test

        Returns:
            Tuple of (processed_width, processed_height) if successful
        """
        try:

            camera = self._get_camera_with_validation(camera_id)
            if not camera:
                return None

            rtsp_url = camera.rtsp_url
            if not rtsp_url:
                logger.error(f"No RTSP URL for camera {camera_id}")
                return None

            # Capture a test frame
            logger.debug(f"Testing crop settings for camera {camera_id}")
            capture_settings = self._get_capture_settings()
            frame = rtsp_utils.capture_with_retry(
                rtsp_url, max_retries=2, timeout_seconds=capture_settings["timeout"]
            )

            if frame is None:
                logger.warning(f"Failed to capture test frame for camera {camera_id}")
                return None

            # Apply processing pipeline
            settings_dict = settings.model_dump()
            processed_frame = rtsp_utils.apply_processing_pipeline(frame, settings_dict)

            # Get processed resolution
            width, height = rtsp_utils.get_frame_resolution(processed_frame)

            logger.info(
                f"Test successful for camera {camera_id}: processed to {width}x{height}"
            )
            return width, height

        except Exception as e:
            logger.error(f"Error testing crop settings for camera {camera_id}: {e}")
            return None

    def capture_preview(self, camera_id: int) -> RTSPCaptureResult:
        """
        Capture preview frame without saving.

        Lightweight capture for testing and preview purposes.

        Args:
            camera_id: Camera identifier

        Returns:
            RTSPCaptureResult with preview capture status
        """
        camera = self._get_camera_with_validation(camera_id)
        if not camera:
            return RTSPCaptureResult(
                success=False, error=f"Camera {camera_id} not found"
            )

        try:
            # Test connectivity first
            connectivity_result = self.test_connection(camera_id, camera.rtsp_url)
            if not connectivity_result.success:
                return RTSPCaptureResult(
                    success=False,
                    error=f"Connectivity test failed: {connectivity_result.error}",
                )

            # Capture frame without saving to database
            settings = self._get_capture_settings()
            frame = self.capture_frame_raw(camera.rtsp_url, settings)

            if frame is None:
                return RTSPCaptureResult(
                    success=False, error="Failed to capture frame from RTSP stream"
                )

            return RTSPCaptureResult(
                success=True,
                message="Preview frame captured successfully",
                metadata={"preview_mode": True},
            )

        except Exception as e:
            logger.error(f"Error capturing preview for camera {camera_id}: {e}")
            return RTSPCaptureResult(success=False, error=str(e))

    def validate_rtsp_url(self, rtsp_url: str) -> Dict[str, Any]:
        """
        Validate RTSP URL format and accessibility.

        Performs URL validation and basic connectivity check.

        Args:
            rtsp_url: RTSP URL to validate

        Returns:
            Validation result with detailed feedback
        """
        try:

            if not rtsp_url:
                return {"valid": False, "error": "Empty RTSP URL provided"}

            # Parse URL
            parsed = urlparse(rtsp_url)

            # Basic format validation
            if parsed.scheme.lower() not in ["rtsp", "http", "https"]:
                return {
                    "valid": False,
                    "error": f"Invalid scheme: {parsed.scheme}. Expected rtsp, http, or https",
                }

            if not parsed.hostname:
                return {"valid": False, "error": "No hostname found in URL"}

            # Test basic connectivity

            settings = self._get_capture_settings()
            success, message = rtsp_utils.test_rtsp_connection(
                rtsp_url, timeout_seconds=settings["timeout"]
            )

            return {
                "valid": success,
                "accessible": success,
                "scheme": parsed.scheme,
                "hostname": parsed.hostname,
                "port": parsed.port,
                "path": parsed.path,
                "error": None if success else message,
            }

        except Exception as e:
            logger.error(f"RTSP URL validation failed: {e}")
            return {"valid": False, "error": str(e)}

    def get_frame_metadata(self, raw_frame: Any) -> Dict[str, Any]:
        """
        Extract metadata from captured frame.

        Gets technical information about frame (resolution, format, etc.).

        Args:
            raw_frame: Raw frame data

        Returns:
            Frame metadata dictionary
        """
        try:

            if raw_frame is None:
                return {"error": "No frame data provided"}

            width, height = rtsp_utils.get_frame_resolution(raw_frame)

            metadata = {
                "width": width,
                "height": height,
                "resolution": f"{width}x{height}",
                "channels": (
                    getattr(raw_frame, "shape", [0, 0, 0])[-1]
                    if hasattr(raw_frame, "shape")
                    else None
                ),
                "dtype": str(getattr(raw_frame, "dtype", "unknown")),
            }

            return metadata

        except Exception as e:
            logger.error(f"Failed to extract frame metadata: {e}")
            return {"error": str(e)}

    def _get_camera_with_validation(self, camera_id: int) -> Optional[Camera]:
        """
        Get camera configuration with validation.

        Internal helper for camera data access with error handling.

        Args:
            camera_id: Camera identifier

        Returns:
            Camera configuration if found and valid
        """
        try:
            camera = self.camera_ops.get_camera_by_id(camera_id)
            if not camera:
                logger.error(f"Camera {camera_id} not found")
            return camera
        except Exception as e:
            logger.error(f"Database error getting camera {camera_id}: {e}")
            return None

    def _get_capture_settings(self) -> Dict[str, Any]:
        """
        Get capture settings with defaults.

        Internal helper for retrieving capture configuration.

        Returns:
            Capture settings dictionary with defaults
        """
        try:
            quality_setting = self.settings_ops.get_setting("image_quality")
            timeout_setting = self.settings_ops.get_setting("rtsp_timeout_seconds")

            quality = DEFAULT_RTSP_QUALITY
            if quality_setting:
                try:
                    quality = int(quality_setting)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid image_quality setting, using default {DEFAULT_RTSP_QUALITY}"
                    )

            timeout = DEFAULT_RTSP_TIMEOUT_SECONDS
            if timeout_setting:
                try:
                    timeout = int(timeout_setting)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid rtsp_timeout_seconds setting, using default {DEFAULT_RTSP_TIMEOUT_SECONDS}"
                    )

            return {
                "quality": quality,
                "timeout": timeout,
                "max_retries": DEFAULT_MAX_RETRIES,
            }

        except Exception as e:
            logger.warning(f"Failed to get capture settings: {e}")
            return {
                "quality": DEFAULT_RTSP_QUALITY,
                "timeout": DEFAULT_RTSP_TIMEOUT_SECONDS,
                "max_retries": DEFAULT_MAX_RETRIES,
            }

    def _apply_processing_pipeline(
        self, frame: Any, camera: Camera
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Apply complete processing pipeline to frame.

        Internal processing implementation with detailed results.

        Args:
            frame: Raw frame data
            camera: Camera with processing configuration

        Returns:
            Tuple of (processed_frame, processing_metadata)
        """
        try:

            metadata = {}

            # Get processing settings
            processing_settings = None
            if camera.crop_rotation_enabled:
                crop_settings_data = camera.crop_rotation_settings or {}
                if crop_settings_data:
                    processing_settings = crop_settings_data
                    metadata["crop_rotation_applied"] = True

            # Apply processing pipeline
            if processing_settings:
                processed_frame = rtsp_utils.apply_processing_pipeline(
                    frame, processing_settings
                )
            else:
                # Legacy rotation fallback
                legacy_rotation = getattr(camera, "rotation", 0)
                if legacy_rotation != 0:
                    # Apply basic rotation if rtsp_utils has rotate capability
                    if hasattr(rtsp_utils, "rotate_frame"):
                        processed_frame = rtsp_utils.apply_rotation(
                            frame, legacy_rotation
                        )
                        metadata["legacy_rotation_applied"] = legacy_rotation
                    else:
                        processed_frame = frame
                        metadata["legacy_rotation_skipped"] = (
                            "rotate_frame not available"
                        )
                else:
                    processed_frame = frame

            metadata["original_resolution"] = rtsp_utils.get_frame_resolution(frame)
            metadata["processed_resolution"] = rtsp_utils.get_frame_resolution(
                processed_frame
            )

            return processed_frame, metadata

        except Exception as e:
            logger.error(f"Processing pipeline failed: {e}")
            return frame, {"error": str(e)}


class AsyncRTSPService:
    """
    Async wrapper for RTSPService operations.

    Provides async interface while maintaining sync RTSP operations for reliability.
    Used by async components in the capture pipeline.
    """

    def __init__(self, sync_rtsp_service: RTSPService):
        """
        Initialize with sync RTSP service instance.

        Args:
            sync_rtsp_service: Synchronized RTSP service instance
        """
        self.sync_rtsp_service = sync_rtsp_service

    async def test_connection(
        self, camera_id: int, rtsp_url: str
    ) -> CameraConnectivityTestResult:
        """
        Async wrapper for RTSP connection testing.

        Args:
            camera_id: Camera identifier
            rtsp_url: RTSP URL to test

        Returns:
            CameraConnectivityTestResult with test results
        """
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.sync_rtsp_service.test_connection,
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
                test_timestamp=get_timezone_aware_timestamp_sync(
                    self.sync_rtsp_service.settings_ops
                ),
            )

    async def capture_preview(self, camera_id: int) -> RTSPCaptureResult:
        """
        Async wrapper for preview capture.

        Args:
            camera_id: Camera identifier

        Returns:
            RTSPCaptureResult with preview status
        """
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.sync_rtsp_service.capture_preview,
                camera_id,
            )
            return result
        except Exception as e:
            logger.error(f"Async preview capture failed for camera {camera_id}: {e}")
            return RTSPCaptureResult(success=False, error=str(e))

    async def detect_source_resolution(
        self, camera_id: int
    ) -> Optional[SourceResolution]:
        """
        Async wrapper for resolution detection.

        Args:
            camera_id: Camera identifier

        Returns:
            SourceResolution if detected successfully
        """
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.sync_rtsp_service.detect_source_resolution,
                camera_id,
            )
            return result
        except Exception as e:
            logger.error(
                f"Async source resolution detection failed for camera {camera_id}: {e}"
            )
            return None

    async def test_crop_settings(
        self, camera_id: int, settings: CropRotationSettings
    ) -> Optional[Tuple[int, int]]:
        """
        Async wrapper for crop settings testing.

        Args:
            camera_id: Camera identifier
            settings: Crop settings to test

        Returns:
            Processed dimensions if successful
        """
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.sync_rtsp_service.test_crop_settings,
                camera_id,
                settings,
            )
            return result
        except Exception as e:
            logger.error(f"Async crop settings test failed for camera {camera_id}: {e}")
            return None
