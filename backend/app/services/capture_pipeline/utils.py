# backend/app/services/capture_pipeline/utils.py
"""
Capture Pipeline Domain Utilities

Capture pipeline specific utilities for workflow coordination, error handling,
and capture operation support. Only utilities specific to the capture pipeline
domain should be placed here.

Key Features:
- Workflow context management and validation
- RTSP connection pool configuration and optimization
- Error handling and file cleanup utilities
- Performance monitoring and metrics collection

Example Usage:
    # Create optimized RTSP configuration for 10 cameras
    rtsp_config = get_optimized_rtsp_config_for_camera_count(10)

    # Apply settings to OpenCV VideoCapture
    import cv2
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    apply_opencv_settings_from_config(cap, rtsp_config)

    # Create workflow context
    context = create_workflow_context(camera_id=1, timelapse_id=5)

    # Validate prerequisites
    if validate_capture_prerequisites(camera_info, timelapse_info):
        # Proceed with capture workflow
        pass
"""

import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2

from ...enums import LoggerName
from ...models.capture_pipeline_models import (
    CameraInfo,
    TimelapseInfo,
)
from ...services.logger import get_service_logger
from ...utils.file_helpers import clean_filename
from ...utils.time_utils import format_filename_timestamp, utc_now
from .constants import (
    DEFAULT_CAPTURE_RETRIES,
    DEFAULT_RTSP_TIMEOUT_SECONDS,
    STEP_CAPTURE_COMPLETE,
    STEP_CORRUPTION_EVALUATION,
    STEP_CORRUPTION_FAST,
    STEP_CORRUPTION_HEAVY,
    STEP_OVERLAY_GENERATION,
    STEP_RECORD_CREATION,
    STEP_RTSP_CAPTURE,
    STEP_SCHEDULER_TRIGGER,
    STEP_SSE_BROADCASTING,
    STEP_THUMBNAIL_QUEUEING,
    STEP_VIDEO_AUTOMATION,
    STEP_WORKER_RECEIVES,
    WORKFLOW_STEP_TIMEOUT_SECONDS,
    WORKFLOW_TOTAL_STEPS,
    WORKFLOW_VERSION,
)

logger = get_service_logger(LoggerName.CAPTURE_PIPELINE)


def create_workflow_context(
    camera_id: int,
    timelapse_id: int,
    additional_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create workflow context for capture pipeline execution.

    Args:
        camera_id: ID of camera to capture from
        timelapse_id: ID of timelapse being captured for
        additional_context: Optional additional context data

    Returns:
        Workflow context dictionary with metadata
    """
    context = {
        "camera_id": camera_id,
        "timelapse_id": timelapse_id,
        "workflow_id": f"wf_{camera_id}_{timelapse_id}_{format_filename_timestamp()}",
        "workflow_version": WORKFLOW_VERSION,
        "total_steps": WORKFLOW_TOTAL_STEPS,
        "started_at": utc_now().isoformat(),
        "current_step": 0,
        "step_results": [],
        "errors": [],
        "timing": {},
    }

    if additional_context:
        context.update(additional_context)

    return context


def validate_capture_prerequisites(camera_info: Dict, timelapse_info: Dict) -> bool:
    """
    Validate that capture prerequisites are met before starting workflow.

    Args:
        camera_info: Camera information dictionary
        timelapse_info: Timelapse information dictionary

    Returns:
        True if prerequisites are met, False otherwise
    """
    try:
        # Validate camera information
        if not camera_info:
            logger.error("Camera information is missing")
            return False

        # Convert to typed models for type safety
        camera = CameraInfo.from_dict(camera_info)

        if not camera.id:
            logger.error("Camera ID is missing")
            return False

        if not camera.rtsp_url:
            logger.error("Camera RTSP URL is missing")
            return False

        # Validate timelapse information
        if not timelapse_info:
            logger.error("Timelapse information is missing")
            return False

        timelapse = TimelapseInfo.from_dict(timelapse_info)

        if not timelapse.id:
            logger.error("Timelapse ID is missing")
            return False

        # Check camera health status if available
        if not camera.is_online:
            logger.warning(f"Camera {camera.id} is marked as offline")
            # Don't fail here - let capture workflow handle connectivity

        # Check timelapse status
        if not timelapse.is_running:
            logger.error(
                f"Timelapse {timelapse.id} is not in running state: {timelapse.status}"
            )
            return False

        # Basic disk space check (if data directory is available)
        data_dir = camera.data_directory
        if data_dir and Path(data_dir).exists():
            stat = os.statvfs(data_dir)
            free_bytes = stat.f_frsize * stat.f_bavail
            # Require at least 100MB free space
            if free_bytes < 100 * 1024 * 1024:
                logger.error(
                    f"Insufficient disk space: {free_bytes / 1024 / 1024:.1f}MB free"
                )
                return False

        return True

    except Exception as e:
        logger.error(f"Error validating capture prerequisites: {e}")
        return False


def generate_capture_filename(timelapse_id: int, timestamp: datetime) -> str:
    """
    Generate standardized filename for captured image following FILE_STRUCTURE_GUIDE.md.

    Args:
        timelapse_id: ID of timelapse
        timestamp: Capture timestamp

    Returns:
        Standardized filename string in format: timelapse-{id}_{YYYYMMDD}_{HHMMSS}.jpg
    """
    # Format: timelapse-{id}_{YYYYMMDD}_{HHMMSS}.jpg (per FILE_STRUCTURE_GUIDE.md)
    timestamp_str = format_filename_timestamp(timestamp)
    filename = f"timelapse-{timelapse_id}_{timestamp_str}.jpg"
    return clean_filename(filename)


def calculate_workflow_step_timeout(step_name: str) -> int:
    """
    Calculate appropriate timeout for specific workflow step.

    Args:
        step_name: Name of workflow step

    Returns:
        Timeout in seconds for the step
    """
    # Step-specific timeouts based on expected complexity
    step_timeouts = {
        STEP_SCHEDULER_TRIGGER: 5,
        STEP_WORKER_RECEIVES: 5,
        STEP_RTSP_CAPTURE: DEFAULT_RTSP_TIMEOUT_SECONDS,
        STEP_CORRUPTION_FAST: 10,
        STEP_CORRUPTION_HEAVY: 30,
        STEP_CORRUPTION_EVALUATION: 10,
        STEP_RECORD_CREATION: 15,
        STEP_OVERLAY_GENERATION: 20,
        STEP_THUMBNAIL_QUEUEING: 10,
        STEP_VIDEO_AUTOMATION: 15,
        STEP_SSE_BROADCASTING: 5,
        STEP_CAPTURE_COMPLETE: 5,
    }

    return step_timeouts.get(
        step_name, WORKFLOW_STEP_TIMEOUT_SECONDS
    )  # Acceptable: dictionary lookup with fallback


def create_error_context(
    step_name: str, error: Exception, context: Dict
) -> Dict[str, Any]:
    """
    Create standardized error context for workflow failures.

    Args:
        step_name: Name of step where error occurred
        error: Exception that occurred
        context: Workflow context

    Returns:
        Error context dictionary for logging and debugging
    """
    error_context = {
        "step_name": step_name,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "error_traceback": traceback.format_exc(),
        "workflow_id": context.get("workflow_id", "unknown"),
        "camera_id": context.get("camera_id"),
        "timelapse_id": context.get("timelapse_id"),
        "step_number": context.get("current_step", 0),
        "total_steps": context.get("total_steps", WORKFLOW_TOTAL_STEPS),
        "workflow_version": context.get("workflow_version", WORKFLOW_VERSION),
        "timestamp": utc_now().isoformat(),
        "previous_steps": [
            result.get("step_name") for result in context.get("step_results", [])
        ],
        "timing_data": context.get("timing", {}),
    }

    # Add any additional context data that might be useful for debugging
    if hasattr(error, "__dict__"):
        error_context["error_attributes"] = {
            k: str(v) for k, v in error.__dict__.items()
        }

    return error_context


def cleanup_partial_capture_files(file_paths: List[str]) -> None:
    """
    Clean up partial capture files on workflow failure.

    Args:
        file_paths: List of file paths to clean up
    """
    if not file_paths:
        return

    logger.info(f"🧹 Cleaning up {len(file_paths)} partial capture files")

    cleaned = 0
    errors = 0

    for file_path in file_paths:
        try:
            if file_path and Path(file_path).exists():
                Path(file_path).unlink()
                cleaned += 1
                logger.debug(f"Cleaned up partial file: {file_path}")
        except Exception as e:
            errors += 1
            logger.error(f"Failed to clean up partial file {file_path}: {e}")

    if cleaned > 0:
        logger.info(f"✅ Cleaned up {cleaned} partial files")
    if errors > 0:
        logger.warning(f"⚠️ Failed to clean up {errors} files")


def merge_workflow_results(step_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge results from multiple workflow steps into final result.

    Args:
        step_results: List of results from individual workflow steps

    Returns:
        Merged workflow result dictionary
    """
    if not step_results:
        return {
            "success": False,
            "message": "No workflow steps completed",
            "total_steps": 0,
            "completed_steps": 0,
            "failed_steps": 0,
            "step_details": [],
        }

    total_steps = len(step_results)

    successful_steps = sum(1 for result in step_results if result.get("success", False))
    failed_steps = total_steps - successful_steps

    # Determine overall success
    overall_success = failed_steps == 0

    # Calculate total execution time
    total_duration = sum(result.get("duration_ms", 0) for result in step_results)

    # Collect data from successful steps
    image_path = None
    image_id = None
    corruption_score = None

    for result in step_results:
        if result.get("success"):
            if result.get("image_path"):
                image_path = result["image_path"]
            if result.get("image_id"):
                image_id = result["image_id"]
            if result.get("corruption_score") is not None:
                corruption_score = result["corruption_score"]

    # Create summary message
    if overall_success:
        message = (
            f"Workflow completed successfully: {successful_steps}/{total_steps} steps"
        )
    else:
        message = f"Workflow failed: {failed_steps}/{total_steps} steps failed"

    merged_result = {
        "success": overall_success,
        "message": message,
        "total_steps": total_steps,
        "completed_steps": successful_steps,
        "failed_steps": failed_steps,
        "total_duration_ms": total_duration,
        "step_details": step_results,
    }

    # Add workflow data if available
    if image_path:
        merged_result["image_path"] = image_path
    if image_id:
        merged_result["image_id"] = image_id
    if corruption_score is not None:
        merged_result["corruption_score"] = corruption_score

    return merged_result


def log_workflow_metrics(workflow_context: Dict, step_timings: Dict) -> None:
    """
    Log performance metrics for workflow execution.

    Args:
        workflow_context: Original workflow context
        step_timings: Dictionary of step names to execution times
    """
    try:
        workflow_id = workflow_context.get("workflow_id", "unknown")
        camera_id = workflow_context.get("camera_id")
        timelapse_id = workflow_context.get("timelapse_id")

        total_time = sum(step_timings.values()) if step_timings else 0
        step_count = len(step_timings)

        logger.info(
            f"📊 Workflow metrics - ID: {workflow_id}, "
            f"Camera: {camera_id}, Timelapse: {timelapse_id}, "
            f"Steps: {step_count}, Total: {total_time:.2f}ms"
        )

        # Log individual step timings for performance analysis
        if step_timings:
            sorted_steps = sorted(
                step_timings.items(), key=lambda x: x[1], reverse=True
            )
            logger.debug("Step timing breakdown:")
            for step_name, timing_ms in sorted_steps:
                percentage = (timing_ms / total_time * 100) if total_time > 0 else 0
                logger.debug(f"  {step_name}: {timing_ms:.2f}ms ({percentage:.1f}%)")

        # Log warnings for slow operations
        slow_threshold = 5000  # 5 seconds
        if total_time > slow_threshold:
            logger.warning(
                f"⚠️ Slow workflow detected: {total_time:.2f}ms > {slow_threshold}ms threshold"
            )

        # Log warnings for individual slow steps
        for step_name, timing_ms in step_timings.items():
            step_threshold = (
                calculate_workflow_step_timeout(step_name) * 500
            )  # 50% of timeout
            if timing_ms > step_threshold:
                logger.warning(
                    f"⚠️ Slow step detected: {step_name} took {timing_ms:.2f}ms "
                    f"(>{step_threshold:.0f}ms threshold)"
                )

    except Exception as e:
        logger.error(f"Error logging workflow metrics: {e}")


def create_rtsp_connection_pool_config(
    camera_count: Optional[int] = None,
    concurrent_captures: Optional[int] = None,
    environment: str = "production",
) -> Dict[str, Any]:
    """
    Create comprehensive configuration for RTSP connection pooling and optimization.

    This configuration is designed for production-grade RTSP capture workflows,
    considering OpenCV VideoCapture limitations, network conditions, and resource management.

    Args:
        camera_count: Number of cameras in the system (affects pool sizing)
        concurrent_captures: Maximum concurrent capture operations
        environment: Environment mode ('production', 'development', 'testing')

    Returns:
        Comprehensive RTSP connection pool and optimization configuration
    """
    # Base configuration from existing patterns
    base_config = {
        # ====================================================================
        # CONNECTION POOL MANAGEMENT
        # ====================================================================
        # Pool sizing based on camera count and concurrency
        "max_connections_per_camera": 1,  # OpenCV VideoCapture is not thread-safe
        "connection_pool_max_size": min(camera_count * 2, 50) if camera_count else 20,
        "connection_pool_min_size": 2,
        "connection_pool_idle_timeout_seconds": 300,  # 5 minutes
        "connection_pool_cleanup_interval_seconds": 60,  # 1 minute
        # Connection lifecycle management
        "connection_max_age_seconds": 3600,  # 1 hour - prevent stale connections
        "connection_max_uses": 1000,  # Recycle connections after 1000 uses
        "connection_validation_enabled": True,
        "connection_validation_interval_seconds": 30,
        # ====================================================================
        # OPENCV VIDEOCAPTURE CONFIGURATION
        # ====================================================================
        # Timeout settings (OpenCV specific)
        "opencv_open_timeout_ms": DEFAULT_RTSP_TIMEOUT_SECONDS * 1000,
        "opencv_read_timeout_ms": DEFAULT_RTSP_TIMEOUT_SECONDS * 1000,
        "opencv_buffer_size": 1,  # Minimize latency - critical for real-time
        # Video codec and format optimization
        "opencv_backend": "cv2.CAP_FFMPEG",  # Use FFmpeg backend for RTSP
        "opencv_codec_pixel_format": -1,  # Auto-detect best format
        "opencv_frame_width": 1920,  # Suggest optimal resolution
        "opencv_frame_height": 1080,
        "opencv_fps": 5,  # Conservative FPS for stability
        # ====================================================================
        # NETWORK AND PROTOCOL OPTIMIZATION
        # ====================================================================
        # RTSP protocol settings
        "rtsp_transport": "tcp",  # TCP more reliable than UDP for automation
        "rtsp_tcp_nodelay": True,  # Reduce latency
        "rtsp_keep_alive_enabled": True,
        "rtsp_keep_alive_interval_seconds": 30,
        # Network buffer management
        "socket_recv_buffer_size": 262144,  # 256KB - larger for video streams
        "socket_send_buffer_size": 32768,  # 32KB - sufficient for RTSP commands
        "network_buffer_timeout_ms": 5000,  # 5 seconds for network operations
        # ====================================================================
        # CAPTURE OPTIMIZATION
        # ====================================================================
        # Frame skipping and quality management
        "skip_frames_on_connect": 3,  # Skip initial frames (codec warmup)
        "skip_frames_on_delay": True,
        "frame_skip_threshold_ms": 100,  # Skip if frame takes >100ms
        "max_consecutive_failures": 5,  # Disconnect after 5 failures
        # Quality and performance tuning
        "enable_hardware_acceleration": True,  # Use GPU if available
        "prefer_codec_order": ["h265", "h264", "mjpeg"],  # Codec preference
        "auto_retry_on_codec_error": True,
        "codec_probe_timeout_ms": 2000,  # 2 seconds to probe codec
        # ====================================================================
        # RETRY AND RESILIENCE
        # ====================================================================
        # Connection retry logic
        "max_retry_attempts": DEFAULT_CAPTURE_RETRIES,
        "retry_delay_base_seconds": 1,
        "retry_delay_max_seconds": 30,
        "retry_exponential_backoff": True,
        "retry_jitter_enabled": True,  # Prevent thundering herd
        # Circuit breaker pattern
        "circuit_breaker_enabled": True,
        "circuit_breaker_failure_threshold": 10,
        "circuit_breaker_recovery_timeout_seconds": 60,
        "circuit_breaker_half_open_max_calls": 3,
        # ====================================================================
        # MONITORING AND DIAGNOSTICS
        # ====================================================================
        # Performance monitoring
        "enable_performance_metrics": True,
        "metrics_collection_interval_seconds": 60,
        "slow_operation_threshold_ms": 3000,  # Log slow operations
        "connection_health_check_enabled": True,
        # Diagnostic logging
        "enable_debug_logging": environment != "production",
        "log_connection_events": environment == "development",
        "log_frame_timing": environment == "development",
        "opencv_log_level": 3 if environment == "production" else 2,  # ERROR vs WARNING
        # ====================================================================
        # RESOURCE MANAGEMENT
        # ====================================================================
        # Memory management
        "frame_buffer_pool_size": (
            concurrent_captures * 2 if concurrent_captures else 10
        ),
        "max_memory_per_connection_mb": 50,  # 50MB per connection
        "garbage_collection_interval_seconds": 120,  # 2 minutes
        "memory_pressure_threshold_percent": 80,  # Scale back at 80% memory
        # CPU and thread management
        "max_concurrent_connections": concurrent_captures or 4,
        "connection_thread_pool_size": (
            min(concurrent_captures * 2, 20) if concurrent_captures else 8
        ),
        "capture_timeout_total_seconds": WORKFLOW_STEP_TIMEOUT_SECONDS,
        # ====================================================================
        # ENVIRONMENT-SPECIFIC TUNING
        # ====================================================================
        # Production optimizations
        "production_mode_enabled": environment == "production",
        "aggressive_timeout_enabled": environment == "production",
        "conservative_retry_enabled": environment == "production",
        # Development and testing aids
        "mock_connections_enabled": environment == "testing",
        "connection_simulation_delay_ms": 100 if environment == "testing" else 0,
        "force_connection_errors": False,  # Testing flag
    }

    # Environment-specific adjustments
    if environment == "development":
        base_config.update(
            {
                "opencv_open_timeout_ms": 10000,  # Longer timeouts for debugging
                "opencv_read_timeout_ms": 10000,
                "max_retry_attempts": 1,  # Fail fast in development
                "enable_debug_logging": True,
                "log_connection_events": True,
                "log_frame_timing": True,
            }
        )

    elif environment == "testing":
        base_config.update(
            {
                "connection_pool_max_size": 5,  # Smaller pools for testing
                "opencv_open_timeout_ms": 2000,  # Faster timeouts
                "opencv_read_timeout_ms": 2000,
                "max_retry_attempts": 0,  # No retries in tests
                "circuit_breaker_enabled": False,  # Disable for predictable tests
            }
        )

    elif environment == "production":
        base_config.update(
            {
                "connection_validation_enabled": True,
                "aggressive_timeout_enabled": True,
                "enable_performance_metrics": True,
                "circuit_breaker_enabled": True,
                "memory_pressure_threshold_percent": 75,  # More conservative
            }
        )

    # Camera count optimizations
    if camera_count:
        if camera_count > 20:  # Large installations
            base_config.update(
                {
                    "connection_pool_max_size": min(camera_count, 100),
                    "connection_pool_cleanup_interval_seconds": 30,  # More frequent cleanup
                    "socket_recv_buffer_size": 524288,  # 512KB for high throughput
                    "max_concurrent_connections": min(camera_count // 2, 25),
                }
            )
        elif camera_count <= 5:  # Small installations
            base_config.update(
                {
                    "connection_pool_max_size": 10,
                    "connection_pool_cleanup_interval_seconds": 120,  # Less frequent cleanup
                    "max_concurrent_connections": camera_count,
                }
            )

    logger.debug(
        f"🔧 RTSP connection pool config created: "
        f"cameras={camera_count}, concurrent={concurrent_captures}, env={environment}"
    )

    return base_config


def get_opencv_capture_settings(pool_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract OpenCV-specific settings from RTSP pool configuration.

    Args:
        pool_config: Full RTSP connection pool configuration

    Returns:
        Dictionary of OpenCV VideoCapture settings ready to apply
    """
    return {
        "CAP_PROP_OPEN_TIMEOUT_MSEC": pool_config.get("opencv_open_timeout_ms", 30000),
        "CAP_PROP_READ_TIMEOUT_MSEC": pool_config.get("opencv_read_timeout_ms", 30000),
        "CAP_PROP_BUFFERSIZE": pool_config.get("opencv_buffer_size", 1),
        "CAP_PROP_CODEC_PIXEL_FORMAT": pool_config.get("opencv_codec_pixel_format", -1),
        "CAP_PROP_FRAME_WIDTH": pool_config.get("opencv_frame_width", 1920),
        "CAP_PROP_FRAME_HEIGHT": pool_config.get("opencv_frame_height", 1080),
        "CAP_PROP_FPS": pool_config.get("opencv_fps", 5),
    }


def apply_opencv_settings_from_config(cap: Any, pool_config: Dict[str, Any]) -> None:
    """
    Apply OpenCV VideoCapture settings from RTSP pool configuration.

    Args:
        cap: OpenCV VideoCapture object
        pool_config: RTSP connection pool configuration
    """

    settings = get_opencv_capture_settings(pool_config)

    for setting_name, value in settings.items():
        try:
            opencv_constant = getattr(cv2, setting_name)
            cap.set(opencv_constant, value)
            logger.debug(f"Applied OpenCV setting {setting_name}={value}")
        except AttributeError:
            logger.warning(f"Unknown OpenCV setting: {setting_name}")
        except Exception as e:
            logger.error(f"Failed to apply OpenCV setting {setting_name}={value}: {e}")


def get_optimized_rtsp_config_for_camera_count(camera_count: int) -> Dict[str, Any]:
    """
    Get optimized RTSP configuration for a specific number of cameras.

    Convenience function that automatically determines the best configuration
    based on the number of cameras in the system.

    Args:
        camera_count: Number of cameras in the system

    Returns:
        Optimized RTSP connection pool configuration
    """
    # Determine concurrent capture capacity based on camera count
    if camera_count <= 5:
        concurrent_captures = camera_count
        environment = "development"  # Likely small installation
    elif camera_count <= 20:
        concurrent_captures = min(camera_count // 2, 10)
        environment = "production"
    else:
        concurrent_captures = min(camera_count // 3, 25)
        environment = "production"

    return create_rtsp_connection_pool_config(
        camera_count=camera_count,
        concurrent_captures=concurrent_captures,
        environment=environment,
    )


def validate_workflow_step_result(step_name: str, result: Any) -> bool:
    """
    Validate that a workflow step result meets expected criteria.

    Args:
        step_name: Name of workflow step
        result: Result from the step

    Returns:
        True if result is valid, False otherwise
    """
    if not result or not isinstance(result, dict):
        logger.error(
            f"Invalid result format for step {step_name}: expected dict, got {type(result)}"
        )
        return False

    # All steps should have success and message fields
    if "success" not in result:
        logger.error(f"Step {step_name} result missing 'success' field")
        return False

    if "message" not in result:
        logger.error(f"Step {step_name} result missing 'message' field")
        return False

    # Step-specific validations
    if step_name == STEP_RTSP_CAPTURE:
        if result.get("success") and not result.get("image_path"):
            logger.error("RTSP capture step succeeded but no image_path provided")
            return False

    elif step_name == STEP_CORRUPTION_EVALUATION:
        if result.get("success") and "corruption_score" not in result:
            logger.error(
                "Corruption evaluation step succeeded but no corruption_score provided"
            )
            return False

    elif step_name == STEP_RECORD_CREATION:
        if result.get("success") and not result.get("image_id"):
            logger.error("Record creation step succeeded but no image_id provided")
            return False

    elif step_name == STEP_OVERLAY_GENERATION:
        if result.get("success") and result.get("overlay_enabled", False):
            if not result.get("overlay_path"):
                logger.error(
                    "Overlay generation step succeeded but no overlay_path provided"
                )
                return False

    # Validate timing information if present
    if "duration_ms" in result:
        duration = result["duration_ms"]
        if not isinstance(duration, (int, float)) or duration < 0:
            logger.error(f"Invalid duration_ms for step {step_name}: {duration}")
            return False

        # Check if step took longer than expected timeout
        expected_timeout_ms = calculate_workflow_step_timeout(step_name) * 1000
        if duration > expected_timeout_ms * 2:  # Allow 2x timeout for warnings
            logger.warning(
                f"Step {step_name} took {duration:.0f}ms, "
                f"much longer than expected {expected_timeout_ms:.0f}ms"
            )

    return True
