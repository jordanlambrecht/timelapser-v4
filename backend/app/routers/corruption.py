"""
Corruption Detection API Routes

Provides endpoints for corruption statistics, logs, and camera health monitoring.
Implements Phase 3 of the corruption detection system.
"""

import tempfile
import os
import time
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
import cv2
import numpy as np
from PIL import Image
import io

from ..database import async_db
from ..models.corruption import (
    CorruptionSystemStats,
    CorruptionStatsResponse,
    CorruptionHistoryResponse,
    CorruptionSettings,
    CorruptionLogEntry,
    CameraCorruptionSettings,
    CorruptionStats,
)

router = APIRouter()


@router.get("/stats", response_model=CorruptionSystemStats)
async def get_system_corruption_stats():
    """Get system-wide corruption detection statistics"""
    try:
        stats = await async_db.get_corruption_stats()

        # Calculate system health score based on various metrics
        total_cameras = stats.get("total_cameras", 0)
        healthy_cameras = stats.get("healthy_cameras", 0)
        degraded_cameras = stats.get("degraded_cameras", 0)

        if total_cameras == 0:
            system_health_score = 100
        else:
            health_ratio = healthy_cameras / total_cameras
            degraded_penalty = (degraded_cameras / total_cameras) * 50
            system_health_score = max(0, int((health_ratio * 100) - degraded_penalty))

        return CorruptionSystemStats(
            total_cameras=total_cameras,
            cameras_healthy=healthy_cameras,
            cameras_monitoring=stats.get("cameras_monitoring", 0),
            cameras_degraded=degraded_cameras,
            images_flagged_today=stats.get("images_flagged_today", 0),
            images_flagged_week=stats.get("images_flagged_week", 0),
            storage_saved_mb=stats.get("storage_saved_mb", 0.0),
            avg_processing_overhead_ms=stats.get("avg_processing_overhead_ms", 0.0),
            system_health_score=system_health_score,
        )

    except Exception as e:
        logger.error(f"Error fetching system corruption stats: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch corruption statistics"
        )


@router.get("/cameras/{camera_id}/stats", response_model=CorruptionStatsResponse)
async def get_camera_corruption_stats(camera_id: int):
    """Get corruption statistics for a specific camera"""
    try:
        # Get camera corruption stats
        camera_stats = await async_db.get_corruption_stats(camera_id=camera_id)

        # Get recent corruption issues
        recent_logs = await async_db.get_corruption_logs(camera_id=camera_id, limit=10)
        recent_issues = []

        for log in recent_logs:
            if log.get("corruption_score", 100) < 70:  # Only include problematic images
                recent_issues.append(
                    {
                        "timestamp": log.get("created_at"),
                        "score": log.get("corruption_score"),
                        "action": log.get("action_taken"),
                        "details": log.get("detection_details", {}),
                    }
                )

        # Generate quality trend data (simplified for now)
        quality_trend = []
        for i in range(24):  # Last 24 hours
            quality_trend.append(
                {
                    "hour": f"{i:02d}:00",
                    "avg_score": 85 + (i % 3) * 5,  # Placeholder trend
                }
            )

        from ..models.corruption import CorruptionStats

        corruption_stats = CorruptionStats(
            lifetime_glitch_count=camera_stats.get("lifetime_glitch_count", 0),
            recent_average_score=camera_stats.get("recent_average_score", 100.0),
            consecutive_corruption_failures=camera_stats.get(
                "consecutive_corruption_failures", 0
            ),
            degraded_mode_active=camera_stats.get("degraded_mode_active", False),
            last_degraded_at=camera_stats.get("last_degraded_at"),
        )

        return CorruptionStatsResponse(
            camera_stats=corruption_stats,
            recent_issues=recent_issues,
            quality_trend=quality_trend,
        )

    except Exception as e:
        logger.error(f"Error fetching camera {camera_id} corruption stats: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch camera corruption statistics"
        )


@router.get("/logs", response_model=CorruptionHistoryResponse)
async def get_corruption_logs(
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
    limit: int = Query(50, ge=1, le=1000, description="Number of logs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Get corruption detection logs with pagination"""
    try:
        logs = await async_db.get_corruption_logs(
            camera_id=camera_id, limit=limit, offset=offset
        )

        # Convert to CorruptionLogEntry objects
        log_entries = []
        for log in logs:
            entry = CorruptionLogEntry(
                id=log.get("id", 0),
                camera_id=log.get("camera_id", 0),
                image_id=log.get("image_id"),
                corruption_score=log.get("corruption_score", 0),
                fast_score=log.get("fast_score"),
                heavy_score=log.get("heavy_score"),
                detection_details=log.get("detection_details", {}),
                action_taken=log.get("action_taken", "unknown"),
                processing_time_ms=log.get("processing_time_ms"),
                created_at=log.get("created_at"),
            )
            log_entries.append(entry)

        # Get total count for pagination
        total_count = len(logs)  # Simplified - in real implementation, get actual count
        page = (offset // limit) + 1

        return CorruptionHistoryResponse(
            logs=log_entries, total_count=total_count, page=page, limit=limit
        )

    except Exception as e:
        logger.error(f"Error fetching corruption logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch corruption logs")


@router.get("/settings")
async def get_corruption_settings():
    """Get current corruption detection settings"""
    try:
        # Get global settings
        global_settings = await async_db.get_corruption_settings()

        # Get all cameras for camera-specific settings
        cameras = await async_db.get_cameras()
        camera_settings = {}

        for camera in cameras:
            camera_corruption_settings = await async_db.get_camera_corruption_settings(
                camera["id"]
            )
            camera_settings[camera["id"]] = CameraCorruptionSettings(
                corruption_detection_heavy=camera_corruption_settings.get(
                    "corruption_detection_heavy", False
                )
            )

        corruption_settings = CorruptionSettings(
            corruption_detection_enabled=global_settings.get(
                "corruption_detection_enabled", True
            ),
            corruption_score_threshold=global_settings.get(
                "corruption_score_threshold", 70
            ),
            corruption_auto_discard_enabled=global_settings.get(
                "corruption_auto_discard_enabled", False
            ),
            corruption_auto_disable_degraded=global_settings.get(
                "corruption_auto_disable_degraded", False
            ),
            corruption_degraded_consecutive_threshold=global_settings.get(
                "corruption_degraded_consecutive_threshold", 10
            ),
            corruption_degraded_time_window_minutes=global_settings.get(
                "corruption_degraded_time_window_minutes", 30
            ),
            corruption_degraded_failure_percentage=global_settings.get(
                "corruption_degraded_failure_percentage", 50
            ),
        )

        return {
            "global_settings": corruption_settings,
            "camera_settings": camera_settings,
        }

    except Exception as e:
        logger.error(f"Error fetching corruption settings: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch corruption settings"
        )


@router.put("/settings")
async def update_corruption_settings(settings_data: dict):
    """Update corruption detection settings"""
    try:
        logger.info(f"Corruption settings update requested: {settings_data}")

        # Extract global settings from the request
        global_settings = settings_data.get("global_settings", {})
        camera_settings = settings_data.get("camera_settings", {})

        # Update global corruption settings in the settings table
        settings_to_update = [
            (
                "corruption_detection_enabled",
                str(global_settings.get("corruption_detection_enabled", True)).lower(),
            ),
            (
                "corruption_score_threshold",
                str(global_settings.get("corruption_score_threshold", 70)),
            ),
            (
                "corruption_auto_discard_enabled",
                str(
                    global_settings.get("corruption_auto_discard_enabled", False)
                ).lower(),
            ),
            (
                "corruption_auto_disable_degraded",
                str(
                    global_settings.get("corruption_auto_disable_degraded", False)
                ).lower(),
            ),
            (
                "corruption_degraded_consecutive_threshold",
                str(
                    global_settings.get("corruption_degraded_consecutive_threshold", 10)
                ),
            ),
            (
                "corruption_degraded_time_window_minutes",
                str(global_settings.get("corruption_degraded_time_window_minutes", 30)),
            ),
            (
                "corruption_degraded_failure_percentage",
                str(global_settings.get("corruption_degraded_failure_percentage", 50)),
            ),
        ]

        # Update each setting in the database
        for key, value in settings_to_update:
            await async_db.create_or_update_setting(key, value)

        # Handle camera-specific settings (heavy detection)
        if camera_settings and "heavy_detection_enabled" in camera_settings:
            heavy_detection_enabled = camera_settings["heavy_detection_enabled"]

            # For now, apply to all cameras
            # This could be enhanced later to be more granular
            cameras = await async_db.get_cameras()
            for camera in cameras:
                await async_db.update_camera(
                    camera["id"],
                    {"corruption_detection_heavy": heavy_detection_enabled},
                )

        # Broadcast settings change event
        async_db.broadcast_event(
            {
                "type": "corruption_settings_updated",
                "data": {
                    "global_settings": global_settings,
                    "camera_settings": camera_settings,
                    "updated_at": datetime.now().isoformat(),
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

        return {"success": True, "message": "Corruption settings updated successfully"}

    except Exception as e:
        logger.error(f"Error updating corruption settings: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to update corruption settings"
        )


@router.post("/cameras/{camera_id}/reset-degraded")
async def reset_camera_degraded_mode(camera_id: int):
    """Reset a camera's degraded mode status"""
    try:
        # Reset degraded mode using update_camera method
        update_data = {
            "degraded_mode_active": False,
            "consecutive_corruption_failures": 0,
        }
        success = await async_db.update_camera(camera_id, update_data)

        if not success:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Broadcast event via SSE
        async_db.broadcast_event(
            {
                "type": "camera_corruption_reset",
                "data": {
                    "camera_id": camera_id,
                    "message": f"Camera {camera_id} degraded mode reset successfully",
                    "reset_at": datetime.now().isoformat(),
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

        return {
            "success": True,
            "camera_id": camera_id,
            "message": f"Camera {camera_id} degraded mode reset successfully",
            "reset_at": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting degraded mode for camera {camera_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to reset camera degraded mode"
        )


@router.get("/health-summary")
async def get_corruption_health_summary():
    """Get a quick summary of corruption detection system health"""
    try:
        stats = await async_db.get_corruption_stats()

        return {
            "system_operational": True,
            "cameras_monitored": stats.get("cameras_monitoring", 0),
            "degraded_cameras": stats.get("degraded_cameras", 0),
            "recent_detections": stats.get("images_flagged_today", 0),
            "avg_overhead_ms": stats.get("avg_processing_overhead_ms", 0.0),
        }

    except Exception as e:
        logger.error(f"Error fetching corruption health summary: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch corruption health summary"
        )


@router.post("/test-image")
async def test_image_corruption(image: UploadFile = File(...)):
    """
    Test corruption detection on an uploaded image.
    Image is analyzed and discarded - not saved to filesystem or database.
    """
    try:
        # Validate file type
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid file type")

        # Read image data
        image_data = await image.read()

        if len(image_data) == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        # Create temporary file for OpenCV processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(image_data)
            temp_file.flush()
            temp_path = temp_file.name

        try:
            # Load image with OpenCV
            frame = cv2.imread(temp_path)
            if frame is None:
                raise HTTPException(status_code=400, detail="Could not read image")

            # Initialize mock corruption detection components
            start_time = time.time()

            # Run fast detection (always enabled)
            fast_result = analyze_fast_detection(frame, image_data)

            # Run heavy detection (simulate per-camera setting - default enabled for testing)
            heavy_result = analyze_heavy_detection(frame)

            # Calculate combined scores
            final_score = calculate_combined_score(
                fast_result, heavy_result, heavy_enabled=True
            )

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Determine action based on score (using default threshold of 70)
            threshold = 70
            action_taken = "saved" if final_score >= threshold else "flagged_for_review"
            if final_score < 30:
                action_taken = "would_be_discarded"

            # Collect failed checks
            failed_checks = []
            for check_name, check_result in fast_result.get("checks", {}).items():
                if not check_result.get("passed", True):
                    failed_checks.append(f"Fast: {check_name}")

            for check_name, check_result in heavy_result.get("checks", {}).items():
                if not check_result.get("passed", True):
                    failed_checks.append(f"Heavy: {check_name}")

            # Build response with proper JSON serialization
            response = {
                "corruption_score": int(final_score),
                "fast_score": int(fast_result.get("score", 100)),
                "heavy_score": int(heavy_result.get("score", 100)),
                "processing_time_ms": int(processing_time_ms),
                "action_taken": str(action_taken),
                "detection_details": {
                    "fast_detection": convert_checks_to_json(
                        fast_result.get("checks", {})
                    ),
                    "heavy_detection": convert_checks_to_json(
                        heavy_result.get("checks", {})
                    ),
                },
                "failed_checks": [str(check) for check in failed_checks],
            }

            return response  # FastAPI will handle JSON serialization

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in test-image endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def convert_checks_to_json(checks: Dict[str, Any]) -> Dict[str, Any]:
    """Convert check results to JSON-serializable format"""
    json_checks = {}
    for key, value in checks.items():
        if isinstance(value, dict):
            json_checks[key] = {
                "passed": bool(value.get("passed", True)),
                "reason": str(value.get("reason", "")),
            }
        else:
            json_checks[key] = {"passed": bool(value), "reason": ""}
    return json_checks


def analyze_fast_detection(frame: np.ndarray, image_data: bytes) -> Dict[str, Any]:
    """Mock fast detection analysis - replace with actual implementation"""
    height, width = frame.shape[:2]
    file_size = len(image_data)

    # Basic file size check
    file_size_ok = 25000 <= file_size <= 10485760  # 25KB to 10MB

    # Basic pixel statistics
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    mean_intensity = float(np.mean(gray))
    pixel_variance = float(np.var(gray))

    # Pixel statistics checks with realistic thresholds
    intensity_ok = 5 <= mean_intensity <= 250  # Keep this - catches pure black/white
    variance_ok = (
        pixel_variance >= 100
    )  # Much higher - even bland images have >100 variance

    # Check for extremely low contrast (corruption indicator)
    pixel_range = float(np.max(gray) - np.min(gray))
    contrast_ok = pixel_range >= 30  # At least 30 grey levels difference

    # Uniformity check (detect overly uniform/flat images)
    unique_values = int(len(np.unique(gray)))
    total_pixels = int(width * height)

    # More realistic thresholds for uniformity detection
    # Check for extremely uniform images (corruption indicators)
    min_unique_threshold = max(
        256, total_pixels * 0.001
    )  # At least 256 unique values OR 0.1% of pixels
    uniformity_ok = unique_values >= min_unique_threshold

    # Additional check: detect if >90% of pixels are identical (major corruption sign)
    most_common_value = np.bincount(gray.flatten()).max()
    identical_pixel_ratio = float(most_common_value / total_pixels)
    extreme_uniformity_ok = (
        identical_pixel_ratio <= 0.9
    )  # Less than 90% identical pixels

    # Pass if either check passes
    final_uniformity_ok = uniformity_ok and extreme_uniformity_ok

    # Basic validity
    validity_ok = width > 0 and height > 0 and len(frame.shape) in [2, 3]

    # Calculate score with penalties
    score = 100
    checks = {
        "file_size_check": {
            "passed": bool(file_size_ok),
            "reason": f"File size: {file_size} bytes",
        },
        "pixel_statistics": {
            "passed": bool(intensity_ok and variance_ok and contrast_ok),
            "reason": f"Mean: {mean_intensity:.1f}, Var: {pixel_variance:.0f}, Range: {pixel_range:.0f}",
        },
        "uniformity_check": {
            "passed": bool(final_uniformity_ok),
            "reason": f"Unique values: {unique_values} (min: {int(min_unique_threshold)}), Identical pixels: {identical_pixel_ratio:.1%}",
        },
        "basic_validity": {
            "passed": bool(validity_ok),
            "reason": f"Dimensions: {width}x{height}",
        },
    }

    if not file_size_ok:
        score -= 20
    if not intensity_ok:
        score -= 15
    if not variance_ok:
        score -= 25  # Increased penalty for low variance
    if not contrast_ok:
        score -= 20  # New penalty for low contrast
    if not final_uniformity_ok:
        score -= 20
    if not validity_ok:
        score -= 100

    return {"score": max(0, score), "checks": checks}


def analyze_heavy_detection(frame: np.ndarray) -> Dict[str, Any]:
    """Mock heavy detection analysis - replace with actual implementation"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame

    # Blur detection using Laplacian variance
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    blur_ok = laplacian_var >= 100

    # Edge analysis with realistic thresholds
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.sum(edges > 0) / edges.size)
    edge_ok = (
        0.005 <= edge_density <= 0.15
    )  # 0.5%-15% edge pixels (much more realistic)

    # Noise detection with stricter threshold
    median_filtered = cv2.medianBlur(gray, 5)
    noise_ratio = float(
        np.mean(np.abs(gray.astype(np.float32) - median_filtered.astype(np.float32)))
        / 255
    )
    noise_ok = noise_ratio <= 0.15  # 15% max noise (was 30%)

    # Histogram analysis with additional checks
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    hist_normalized = hist / np.sum(hist)
    entropy = float(-np.sum(hist_normalized * np.log2(hist_normalized + 1e-7)))

    # Multiple histogram checks
    entropy_ok = entropy >= 3.0  # Keep existing threshold
    hist_spread_ok = float(np.std(hist_normalized)) >= 0.001  # Not too concentrated
    histogram_ok = entropy_ok and hist_spread_ok

    # Additional histogram statistics for reporting
    non_zero_bins = int(np.count_nonzero(hist))
    hist_peak = float(np.max(hist_normalized))
    dominant_range = f"{int(np.argmax(np.cumsum(hist_normalized) >= 0.1))}-{int(np.argmax(np.cumsum(hist_normalized) >= 0.9))}"

    # Pattern detection with much stricter threshold
    block_size = 8
    blocks_uniform = 0
    total_blocks = 0
    uniform_threshold = 50  # Increased from 10 - blocks with variance <50 are "uniform"

    for y in range(0, gray.shape[0] - block_size, block_size):
        for x in range(0, gray.shape[1] - block_size, block_size):
            block = gray[y : y + block_size, x : x + block_size]
            if float(np.var(block)) < uniform_threshold:
                blocks_uniform += 1
            total_blocks += 1

    uniform_ratio = float(blocks_uniform / max(total_blocks, 1))
    pattern_ok = uniform_ratio <= 0.4  # 40% max uniform blocks (was 80%)

    # Calculate score with penalties
    score = 100
    checks = {
        "blur_detection": {
            "passed": bool(blur_ok),
            "reason": f"Laplacian variance: {laplacian_var:.1f} (min: 100)",
        },
        "edge_analysis": {
            "passed": bool(edge_ok),
            "reason": f"Edge density: {edge_density:.3f} (0.5%-15%)",
        },
        "noise_detection": {
            "passed": bool(noise_ok),
            "reason": f"Noise ratio: {noise_ratio:.3f} (max: 15%)",
        },
        "histogram_analysis": {
            "passed": bool(histogram_ok),
            "reason": f"Entropy: {entropy:.2f} (min: 3.0), Bins: {non_zero_bins}/256, Range: {dominant_range}, Peak: {hist_peak:.1%}",
        },
        "pattern_detection": {
            "passed": bool(pattern_ok),
            "reason": f"Uniform blocks: {uniform_ratio:.1%} (max: 40%)",
        },
    }

    if not blur_ok:
        score -= 30
    if not edge_ok:
        score -= 25
    if not noise_ok:
        score -= 20
    if not histogram_ok:
        score -= 15
    if not pattern_ok:
        score -= 40  # Heavy penalty for excessive uniform patterns

    return {"score": max(0, score), "checks": checks}


def calculate_combined_score(
    fast_result: Dict, heavy_result: Dict, heavy_enabled: bool = True
) -> int:
    """Calculate final corruption score using weighted combination"""
    fast_score = fast_result.get("score", 100)
    heavy_score = heavy_result.get("score", 100)

    if not heavy_enabled:
        return fast_score

    # Weighted combination: 30% fast, 70% heavy
    combined = (fast_score * 0.3) + (heavy_score * 0.7)

    # Take worst case for complete failures
    if fast_score == 0 or heavy_score == 0:
        return 0

    return max(0, min(100, int(combined)))
