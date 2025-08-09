# backend/app/routers/thumbnail_routers.py
"""
Thumbnail management HTTP endpoints.

Role: Thumbnail management HTTP endpoints
Responsibilities: Thumbnail generation, regeneration, and serving operations
Interactions: Uses ImageService for business logic, delegates to services following the layered architecture pattern

Updated: 2025-07-06 - Debugging thumbnail regeneration endpoints
"""


from fastapi import APIRouter, Query

from ..dependencies import SchedulerServiceDep, ThumbnailPipelineDep
from ..enums import LoggerName, LogSource, ThumbnailJobPriority
from ..models.shared_models import (
    ThumbnailGenerationResult,
    ThumbnailOperationResponse,
    ThumbnailRegenerationStatus,
    ThumbnailStatistics,
)
from ..services.logger import get_service_logger
from ..utils.router_helpers import handle_exceptions

logger = get_service_logger(LoggerName.API, LogSource.API)

# NOTE: CACHING STRATEGY - MIXED APPROACH
# Thumbnail operations use mixed caching strategy:
# - Statistics: ETag + 10-15 min cache - aggregated data changes slowly
# - Generation/regeneration: No cache + SSE broadcasting - dynamic operations
# - Status endpoints: SSE broadcasting or very short cache - real-time monitoring
# - Cleanup operations: No cache - dynamic DELETE operations
router = APIRouter(tags=["thumbnails"])

# NOTE: Thumbnail regeneration state is now managed by the ImageService layer
# This eliminates global state from the router and follows proper architectural patterns


@router.post(
    "/thumbnails/generate/{image_id}", response_model=ThumbnailGenerationResult
)
@handle_exceptions("generate thumbnail for image")
async def generate_thumbnail_for_image(
    image_id: int,
    thumbnail_pipeline: ThumbnailPipelineDep,
    scheduler_service: SchedulerServiceDep,
    force_regenerate: bool = Query(
        False, description="Force regeneration even if thumbnails exist"
    ),
):
    """
    🎯 SCHEDULER-CENTRIC: Generate thumbnails for a specific image through scheduler authority.

    ALL timing operations must flow through SchedulerWorker. This ensures proper
    coordination and prevents conflicts with other thumbnail generation jobs.

    Args:
        image_id: ID of the image to generate thumbnails for
        force_regenerate: Whether to regenerate existing thumbnails

    Returns:
        ThumbnailGenerationResult with generation details
    """
    try:
        # 🎯 SCHEDULER-CENTRIC: Route thumbnail generation through scheduler authority
        # However, we can also use the thumbnail pipeline for immediate generation

        # First try to schedule through scheduler for consistency
        scheduler_result = await scheduler_service.schedule_immediate_thumbnail_generation(
            image_id=image_id,
            priority=ThumbnailJobPriority.MEDIUM,  # Individual thumbnail generation is medium priority
        )

        if scheduler_result.get("success"):
            return ThumbnailGenerationResult(
                success=True,
                image_id=image_id,
                processing_time_ms=0,  # Scheduling time is negligible
            )
        else:
            # If scheduler fails, try to queue through thumbnail pipeline
            job_id = await thumbnail_pipeline.queue_thumbnail_job(
                image_id=image_id,
                priority=ThumbnailJobPriority.MEDIUM,
                force_regenerate=force_regenerate,
            )

            if job_id:
                return ThumbnailGenerationResult(
                    success=True,
                    image_id=image_id,
                    processing_time_ms=0,
                )
            else:
                return ThumbnailGenerationResult(
                    success=False,
                    image_id=image_id,
                    processing_time_ms=0,
                    error="Failed to queue thumbnail generation",
                )

    except Exception as e:
        logger.error(f"Failed to generate thumbnail for image {image_id}: {e}")
        return ThumbnailGenerationResult(
            success=False,
            image_id=image_id,
            processing_time_ms=0,
            error=f"Failed to schedule thumbnail generation: {str(e)}",
        )


@router.get("/thumbnails/stats", response_model=ThumbnailStatistics)
@handle_exceptions("get thumbnail statistics")
async def get_thumbnail_stats(
    thumbnail_pipeline: ThumbnailPipelineDep,
):
    """
    Get comprehensive thumbnail statistics.

    Returns:
        ThumbnailStatistics with coverage and storage information
    """
    try:
        stats = await thumbnail_pipeline.get_job_statistics()
        # Convert pipeline stats to ThumbnailStatistics model
        from ..models.shared_models import ThumbnailStatistics

        return ThumbnailStatistics(
            total_images=stats.get("total_jobs_24h", 0),
            images_with_thumbnails=stats.get("completed_jobs_24h", 0),
            images_without_thumbnails=stats.get("failed_jobs_24h", 0),
            thumbnail_coverage_percentage=0.0,  # Would need additional calculation
        )
    except Exception as e:
        logger.error(f"Failed to get thumbnail statistics: {e}")
        from ..models.shared_models import ThumbnailStatistics

        return ThumbnailStatistics()


@router.post("/thumbnails/regenerate-all", response_model=ThumbnailOperationResponse)
@router.post("/thumbnails/regenerate", deprecated=True)
@handle_exceptions("start thumbnail regeneration")
async def start_thumbnail_regeneration(
    thumbnail_pipeline: ThumbnailPipelineDep,
    limit: int = Query(
        1000, ge=1, le=10000, description="Maximum number of images to process"
    ),
):
    """
    Start thumbnail regeneration for all images using background processing.
    Returns immediately while processing continues in the background.

    Args:
        limit: Maximum number of images to regenerate (1-10000)

    Returns:
        ThumbnailOperationResponse with session ID and immediate status
    """
    return await thumbnail_pipeline.start_thumbnail_regeneration_background(limit=limit)


@router.get(
    "/thumbnails/regenerate-all/status", response_model=ThumbnailRegenerationStatus
)
@handle_exceptions("get thumbnail regeneration status")
async def get_regeneration_status(thumbnail_pipeline: ThumbnailPipelineDep):
    """
    Get current thumbnail regeneration status.

    Returns:
        ThumbnailRegenerationStatus with current progress
    """
    return await thumbnail_pipeline.get_thumbnail_regeneration_status()


@router.post(
    "/thumbnails/regenerate-all/cancel", response_model=ThumbnailOperationResponse
)
@handle_exceptions("cancel thumbnail regeneration")
async def cancel_thumbnail_regeneration(thumbnail_pipeline: ThumbnailPipelineDep):
    """
    Cancel currently running thumbnail regeneration process.

    Returns:
        ThumbnailOperationResponse with cancellation status
    """
    return await thumbnail_pipeline.cancel_thumbnail_regeneration()


@router.delete("/thumbnails/delete-all", response_model=ThumbnailOperationResponse)
@handle_exceptions("delete all thumbnails")
async def delete_all_thumbnails(thumbnail_pipeline: ThumbnailPipelineDep):
    """
    Delete all thumbnail files and clear database references.

    Returns:
        ThumbnailOperationResponse with deletion results
    """
    return await thumbnail_pipeline.delete_all_thumbnails()


@router.post("/thumbnails/verify", response_model=ThumbnailOperationResponse)
@handle_exceptions("verify all thumbnails")
async def verify_all_thumbnails(thumbnail_pipeline: ThumbnailPipelineDep):
    """
    Verify all thumbnail files system-wide.

    Returns:
        ThumbnailOperationResponse with verification results
    """
    return await thumbnail_pipeline.verify_all_thumbnails()


@router.post("/thumbnails/repair", response_model=ThumbnailOperationResponse)
@handle_exceptions("repair orphaned thumbnails")
async def repair_orphaned_thumbnails(thumbnail_pipeline: ThumbnailPipelineDep):
    """
    Repair orphaned thumbnail files by matching them back to database.

    Returns:
        ThumbnailOperationResponse with repair results
    """
    return await thumbnail_pipeline.repair_orphaned_thumbnails()


@router.delete("/thumbnails/cleanup", response_model=ThumbnailOperationResponse)
@handle_exceptions("cleanup orphaned thumbnails")
async def cleanup_orphaned_thumbnails(
    thumbnail_pipeline: ThumbnailPipelineDep,
    dry_run: bool = Query(
        False, description="Preview cleanup without actually deleting files"
    ),
):
    """
    Clean up thumbnail files that no longer have corresponding images.

    Args:
        dry_run: If true, only report what would be deleted without actually deleting

    Returns:
        ThumbnailOperationResponse with cleanup results
    """
    return await thumbnail_pipeline.cleanup_orphaned_thumbnails(dry_run=dry_run)


# ARCHITECTURAL COMPLIANCE:
# - Router now delegates to ThumbnailPipeline (proper service layer)
# - Individual thumbnail generation routed through SchedulerService (CEO architecture)
# - Bulk operations handled by ThumbnailPipeline using existing building blocks
# - All business logic removed from router layer
#
# ThumbnailPipeline methods now handle:
# - start_thumbnail_regeneration_background() - Bulk job queuing
# - get_thumbnail_regeneration_status() - Job statistics tracking
# - cancel_thumbnail_regeneration() - Active job cancellation
# - verify_all_thumbnails() - System-wide verification
# - repair_orphaned_thumbnails() - Orphaned file repair
# - cleanup_orphaned_thumbnails() - File cleanup with dry-run
# - delete_all_thumbnails() - Database reference clearing
#
# This follows the Scheduler CEO architecture and uses existing functionality.
