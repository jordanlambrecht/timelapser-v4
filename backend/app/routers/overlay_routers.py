# backend/app/routers/overlay_routers.py
"""
Overlay management HTTP endpoints.

Role: Overlay system HTTP endpoints
Responsibilities: Overlay preset CRUD operations, configuration management, asset upload, preview generation
Interactions: Uses OverlayService for business logic, returns Pydantic models, handles HTTP status codes and error responses

Architecture: API Layer - delegates all business logic to services
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
)
from fastapi import Path as FastAPIPath
from fastapi import (
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

# from ..database.overlay_job_operations import OverlayJobOperations
# from ..database.overlay_operations import OverlayOperations
from ..dependencies import (
    OverlayJobServiceDep,
    OverlayServiceDep,
    SchedulerServiceDep,
)
from ..models.overlay_model import (
    OverlayAsset,
    # OverlayAssetCreate,
    # OverlayConfiguration,
    OverlayPreset,
    OverlayPresetCreate,
    OverlayPresetUpdate,
    OverlayPreviewRequest,
    OverlayPreviewResponse,
    TimelapseOverlay,
    TimelapseOverlayCreate,
    TimelapseOverlayUpdate,
)
from ..utils.file_helpers import (
    validate_file_path,
)
from ..utils.response_helpers import ResponseFormatter
from ..utils.router_helpers import (
    handle_exceptions,
    validate_entity_exists,
)
from ..utils.validation_helpers import process_overlay_asset_upload

router = APIRouter(tags=["overlays"])


# ============================================================================
# PRESET MANAGEMENT ENDPOINTS
# ============================================================================


@router.get("/presets", response_model=List[OverlayPreset])
@handle_exceptions("fetch overlay presets")
async def get_overlay_presets(
    overlay_service: OverlayServiceDep,
    include_builtin: bool = Query(True, description="Include built-in presets"),
    include_custom: bool = Query(True, description="Include custom presets"),
) -> List[OverlayPreset]:
    """
    Get all overlay presets.

    Returns both built-in and custom overlay presets available for use.
    Built-in presets cannot be modified or deleted.
    """
    presets = await overlay_service.get_overlay_presets()

    # Filter based on query parameters
    if not include_builtin:
        presets = [p for p in presets if not p.is_builtin]
    if not include_custom:
        presets = [p for p in presets if p.is_builtin]

    return presets


@router.get("/presets/{preset_id}", response_model=OverlayPreset)
@handle_exceptions("fetch overlay preset")
async def get_overlay_preset(
    overlay_service: OverlayServiceDep,
    preset_id: int = FastAPIPath(..., description="Preset ID", ge=1),
) -> OverlayPreset:
    """Get a specific overlay preset by ID."""
    preset = await validate_entity_exists(
        overlay_service.get_overlay_preset_by_id, preset_id, "Overlay preset not found"
    )
    return preset


@router.post(
    "/presets", response_model=OverlayPreset, status_code=status.HTTP_201_CREATED
)
@handle_exceptions("create overlay preset")
async def create_overlay_preset(
    preset_data: OverlayPresetCreate,
    overlay_service: OverlayServiceDep,
) -> OverlayPreset:
    """
    Create a new custom overlay preset.

    Built-in presets are created during database migration and cannot be
    created through this endpoint.
    """
    # Validate overlay configuration
    if not await overlay_service.validate_overlay_configuration(
        preset_data.overlay_config.model_dump()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid overlay configuration",
        )

    preset = await overlay_service.create_overlay_preset(preset_data)
    if not preset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create overlay preset",
        )

    return preset


@router.put("/presets/{preset_id}", response_model=OverlayPreset)
@handle_exceptions("update overlay preset")
async def update_overlay_preset(
    preset_data: OverlayPresetUpdate,
    overlay_service: OverlayServiceDep,
    preset_id: int = FastAPIPath(..., description="Preset ID", ge=1),
) -> OverlayPreset:
    """
    Update an existing overlay preset.

    Built-in presets cannot be modified and will return a 403 error.
    """
    # Verify preset exists and is not built-in
    existing_preset = await validate_entity_exists(
        overlay_service.get_overlay_preset_by_id, preset_id, "Overlay preset not found"
    )

    if existing_preset.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify built-in overlay presets",
        )

    # Validate overlay configuration if provided
    if (
        preset_data.overlay_config
        and not await overlay_service.validate_overlay_configuration(
            preset_data.overlay_config.model_dump()
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid overlay configuration",
        )

    preset = await overlay_service.update_overlay_preset(preset_id, preset_data)
    if not isinstance(preset, OverlayPreset):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update overlay preset",
        )

    return preset


@router.delete("/presets/{preset_id}")
@handle_exceptions("delete overlay preset")
async def delete_overlay_preset(
    overlay_service: OverlayServiceDep,
    preset_id: int = FastAPIPath(..., description="Preset ID", ge=1),
):
    """
    Delete an overlay preset.

    Built-in presets cannot be deleted and will return a 403 error.
    """
    # Verify preset exists and is not built-in
    existing_preset = await validate_entity_exists(
        overlay_service.get_overlay_preset_by_id, preset_id, "Overlay preset not found"
    )

    if existing_preset.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete built-in overlay presets",
        )

    success = await overlay_service.delete_overlay_preset(preset_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete overlay preset",
        )

    return ResponseFormatter.success("Overlay preset deleted successfully")


# ============================================================================
# TIMELAPSE OVERLAY CONFIGURATION ENDPOINTS
# ============================================================================


@router.get("/config/{timelapse_id}", response_model=TimelapseOverlay)
@handle_exceptions("fetch timelapse overlay configuration")
async def get_timelapse_overlay_config(
    overlay_service: OverlayServiceDep,
    timelapse_id: int = FastAPIPath(..., description="Timelapse ID", ge=1),
) -> TimelapseOverlay:
    """Get overlay configuration for a specific timelapse."""
    config = await overlay_service.get_timelapse_overlay_config(timelapse_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No overlay configuration found for this timelapse",
        )
    return config


@router.post(
    "/config/{timelapse_id}",
    response_model=TimelapseOverlay,
    status_code=status.HTTP_201_CREATED,
)
@handle_exceptions("create timelapse overlay configuration")
async def create_timelapse_overlay_config(
    config_data: TimelapseOverlayCreate,
    overlay_service: OverlayServiceDep,
    timelapse_id: int = FastAPIPath(..., description="Timelapse ID", ge=1),
) -> TimelapseOverlay:
    """
    Create or update overlay configuration for a timelapse.

    If configuration already exists, it will be updated with the new settings.
    """
    # Validate overlay configuration
    if not await overlay_service.validate_overlay_configuration(
        config_data.overlay_config.model_dump()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid overlay configuration",
        )

    # Set timelapse_id from path parameter
    config_data.timelapse_id = timelapse_id

    config = await overlay_service.create_or_update_timelapse_overlay_config(
        config_data
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create overlay configuration",
        )

    return config


@router.put("/config/{timelapse_id}", response_model=TimelapseOverlay)
@handle_exceptions("update timelapse overlay configuration")
async def update_timelapse_overlay_config(
    config_data: TimelapseOverlayUpdate,
    overlay_service: OverlayServiceDep,
    timelapse_id: int = FastAPIPath(..., description="Timelapse ID", ge=1),
) -> TimelapseOverlay:
    """Update overlay configuration for a timelapse."""
    # Verify config exists
    existing_config = await overlay_service.get_timelapse_overlay_config(timelapse_id)
    if not existing_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No overlay configuration found for this timelapse",
        )

    # Validate overlay configuration if provided
    if (
        config_data.overlay_config
        and not await overlay_service.validate_overlay_configuration(
            config_data.overlay_config.model_dump()
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid overlay configuration",
        )

    config = await overlay_service.update_timelapse_overlay_config(
        timelapse_id, config_data
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update overlay configuration",
        )

    return config


@router.delete("/config/{timelapse_id}")
@handle_exceptions("delete timelapse overlay configuration")
async def delete_timelapse_overlay_config(
    overlay_service: OverlayServiceDep,
    timelapse_id: int = FastAPIPath(..., description="Timelapse ID", ge=1),
):
    """Delete overlay configuration for a timelapse."""
    success = await overlay_service.delete_timelapse_overlay_config(timelapse_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No overlay configuration found for this timelapse",
        )

    return ResponseFormatter.success("Overlay configuration deleted successfully")


# ============================================================================
# ASSET MANAGEMENT ENDPOINTS
# ============================================================================


@router.get("/assets", response_model=List[OverlayAsset])
@handle_exceptions("fetch overlay assets")
async def get_overlay_assets(
    overlay_service: OverlayServiceDep,
) -> List[OverlayAsset]:
    """Get all uploaded overlay assets (watermarks, logos, etc.)."""
    return await overlay_service.get_overlay_assets()


@router.post(
    "/assets/upload", response_model=OverlayAsset, status_code=status.HTTP_201_CREATED
)
@handle_exceptions("upload overlay asset")
async def upload_overlay_asset(
    overlay_service: OverlayServiceDep,
    file: UploadFile = File(..., description="Asset file to upload"),
    name: Optional[str] = Form(None, description="Optional custom name for the asset"),
) -> OverlayAsset:
    """
    Upload a new overlay asset (watermark, logo, etc.).

    Supported formats: PNG, JPEG, WebP
    Maximum file size: 100MB
    """
    # Delegate file processing to validation helpers
    processed_data = await process_overlay_asset_upload(
        file, name if name is not None else ""
    )
    # Upload and save asset using processed data
    asset = await overlay_service.upload_overlay_asset(
        processed_data["asset_data"], processed_data["validated_file"]
    )
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to upload overlay asset",
        )

    return asset


@router.get("/assets/{asset_id}", response_class=FileResponse)
@handle_exceptions("serve overlay asset")
async def get_overlay_asset(
    overlay_service: OverlayServiceDep,
    asset_id: int = FastAPIPath(..., description="Asset ID", ge=1),
) -> FileResponse:
    """Serve an overlay asset file."""
    asset = await validate_entity_exists(
        overlay_service.get_overlay_asset_by_id, asset_id, "Overlay asset not found"
    )

    # Validate file path for security
    asset_path = Path(asset.file_path)
    if not validate_file_path(str(asset_path)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to asset file"
        )

    if not asset_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset file not found on disk"
        )

    return FileResponse(
        path=str(asset_path),
        media_type=asset.mime_type,
        filename=asset.original_name,
    )


@router.delete("/assets/{asset_id}")
@handle_exceptions("delete overlay asset")
async def delete_overlay_asset(
    overlay_service: OverlayServiceDep,
    asset_id: int = FastAPIPath(..., description="Asset ID", ge=1),
):
    """Delete an overlay asset and its associated file."""
    await validate_entity_exists(
        overlay_service.get_overlay_asset_by_id, asset_id, "Overlay asset not found"
    )

    success = await overlay_service.delete_overlay_asset(asset_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete overlay asset",
        )

    return ResponseFormatter.success("Overlay asset deleted successfully")


# ============================================================================
# PREVIEW GENERATION ENDPOINTS
# ============================================================================


@router.post("/preview", response_model=OverlayPreviewResponse)
@handle_exceptions("generate overlay preview")
async def generate_overlay_preview(
    preview_request: OverlayPreviewRequest,
    overlay_service: OverlayServiceDep,
    overlay_job_service: OverlayJobServiceDep,
) -> OverlayPreviewResponse:
    """
    Generate a preview of overlay configuration applied to a test image.

    This endpoint captures a fresh image from the specified camera and applies
    the provided overlay configuration to generate a preview.
    """
    # Validate overlay configuration
    if not await overlay_service.validate_overlay_configuration(
        preview_request.overlay_config.model_dump()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid overlay configuration",
        )

    # Generate preview
    preview_result = await overlay_service.generate_overlay_preview(preview_request)
    if not preview_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to generate overlay preview",
        )

    return preview_result


@router.post("/fresh-photo/{camera_id}", response_class=FileResponse)
@handle_exceptions("capture fresh photo for overlay preview")
async def capture_fresh_photo_for_preview(
    overlay_service: OverlayServiceDep,
    scheduler_service: SchedulerServiceDep,
    camera_id: int = FastAPIPath(..., description="Camera ID", ge=1),
) -> FileResponse:
    """
    Capture a fresh photo from the specified camera for overlay preview.

    This endpoint captures a temporary image that is not stored in the database.
    The image is used for overlay preview purposes only.

    Following CEO architecture: Camera capture operations are timing-sensitive
    and must be coordinated through the SchedulerWorker authority.
    """
    # Schedule immediate capture through scheduler authority (CEO architecture)
    # For preview purposes, we use a temporary timelapse context (timelapse_id = -1 indicates preview)
    capture_result = await scheduler_service.schedule_immediate_capture(
        camera_id=camera_id,
        timelapse_id=-1,  # Special ID for preview captures
        priority="high",
    )

    if not capture_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule camera capture: {capture_result.get('error', 'Unknown error')}",
        )

    # After successful capture scheduling, get the captured image for preview
    temp_image_path = await overlay_service.capture_fresh_photo_for_preview(camera_id)
    if not temp_image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to capture fresh photo from camera",
        )

    temp_path = Path(temp_image_path)
    if not temp_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Captured image file not found",
        )

    return FileResponse(
        path=str(temp_path),
        media_type="image/jpeg",
        filename=f"camera_{camera_id}_preview.jpg",
    )


# ============================================================================
# SYSTEM STATUS ENDPOINTS
# ============================================================================


@router.get("/status", response_model=Dict[str, Any])
@handle_exceptions("get overlay system status")
async def get_overlay_system_status(
    overlay_service: OverlayServiceDep,
    overlay_job_service: OverlayJobServiceDep,
) -> Dict[str, Any]:
    """
    Get overlay system status including job queue statistics.

    Provides information about the overlay generation system health,
    queue status, and performance metrics.
    """
    # Get job queue statistics
    job_stats = await overlay_job_service.get_job_statistics()

    # Get preset counts
    presets = await overlay_service.get_overlay_presets()
    builtin_presets = len([p for p in presets if p.is_builtin])
    custom_presets = len([p for p in presets if not p.is_builtin])

    # Get asset counts
    assets = await overlay_service.get_overlay_assets()

    # Provide default values if job_stats is None
    pending_jobs = getattr(job_stats, "pending_jobs", 0) if job_stats else 0
    processing_jobs = getattr(job_stats, "processing_jobs", 0) if job_stats else 0
    completed_jobs_24h = getattr(job_stats, "completed_jobs_24h", 0) if job_stats else 0
    failed_jobs_24h = getattr(job_stats, "failed_jobs_24h", 0) if job_stats else 0

    return {
        "status": "healthy",
        "presets": {
            "total": len(presets),
            "builtin": builtin_presets,
            "custom": custom_presets,
        },
        "assets": {
            "total": len(assets),
        },
        "job_queue": {
            "pending": pending_jobs,
            "processing": processing_jobs,
            "completed_today": completed_jobs_24h,
            "failed_today": failed_jobs_24h,
        },
        "system_health": "operational",
    }
