# backend/app/models/overlay_model.py
"""
Overlay system models - Pydantic models for overlay presets, configurations, and job management.

This module provides type-safe interfaces for the overlay generation system including:
- Overlay configuration models
- Preset management models
- Job queue models
- Asset upload models
"""

from typing import Dict, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from ..enums import (
    OverlayJobPriority,
    OverlayJobStatus,
    OverlayJobType,
    OverlayType,
    OverlayGridPosition,
)

# Type definitions for overlay system
# OverlayType now imported from enums.py


# OverlayJobPriority, OverlayJobStatus, OverlayJobType now imported from enums.py


class OverlayItem(BaseModel):
    """Individual overlay item configuration"""

    type: OverlayType = Field(..., description="Type of overlay content")
    customText: Optional[str] = Field(None, description="Custom text for text overlays")
    textSize: int = Field(16, ge=8, le=72, description="Font size in pixels")
    textColor: str = Field("#FFFFFF", description="Text color in hex format")
    backgroundColor: Optional[str] = Field(
        None, description="Background color in hex or rgba format"
    )
    backgroundOpacity: int = Field(
        0, ge=0, le=100, description="Background opacity percentage"
    )
    dateFormat: Optional[str] = Field(
        "MM/dd/yyyy HH:mm", description="Date format for date/time overlays"
    )
    imageUrl: Optional[str] = Field(None, description="URL or path to image asset")
    imageScale: int = Field(100, ge=10, le=500, description="Image scale percentage")

    # New frontend properties
    enableBackground: Optional[bool] = Field(
        None, description="Whether to enable background for this overlay item"
    )
    unit: Optional[Literal["F", "C"]] = Field(
        None, description="Temperature unit for weather overlays"
    )
    display: Optional[
        Literal["temp_only", "with_unit", "conditions_only", "temp_and_conditions"]
    ] = Field(None, description="Display format for weather overlays")
    leadingZeros: Optional[bool] = Field(
        None, description="Whether to use leading zeros for sequence numbers"
    )
    hidePrefix: Optional[bool] = Field(
        None, description="Whether to hide prefix text for sequence overlays"
    )

    model_config = ConfigDict(from_attributes=True)


class GlobalOverlayOptions(BaseModel):
    """Global overlay configuration options"""

    opacity: int = Field(
        100, ge=0, le=100, description="Global overlay opacity percentage"
    )
    font: str = Field("Arial", description="Font family name")
    xMargin: int = Field(
        20, ge=0, le=200, description="Horizontal margin from edge in pixels"
    )
    yMargin: int = Field(
        20, ge=0, le=200, description="Vertical margin from edge in pixels"
    )
    backgroundColor: str = Field(
        "#000000", description="Global background color in hex format"
    )
    backgroundOpacity: int = Field(
        50, ge=0, le=100, description="Global background opacity percentage"
    )
    fillColor: str = Field(
        "#FFFFFF", description="Global text/fill color in hex format"
    )
    dropShadow: int = Field(2, ge=0, le=10, description="Drop shadow size in pixels")
    preset: Optional[str] = Field(None, description="Selected preset name")

    model_config = ConfigDict(from_attributes=True)


def _default_global_overlay_options() -> GlobalOverlayOptions:
    """Default factory for GlobalOverlayOptions"""
    return GlobalOverlayOptions(
        opacity=100,
        font="Arial",
        xMargin=20,
        yMargin=20,
        backgroundColor="#000000",
        backgroundOpacity=50,
        fillColor="#FFFFFF",
        dropShadow=2,
        preset=None,
    )


class OverlayConfiguration(BaseModel):
    """Complete overlay configuration for timelapses"""

    overlayPositions: Dict[OverlayGridPosition, OverlayItem] = Field(
        default_factory=dict, description="Overlay items positioned on 9-position grid"
    )
    globalOptions: GlobalOverlayOptions = Field(
        default_factory=_default_global_overlay_options,
        description="Global overlay settings",
    )

    model_config = ConfigDict(from_attributes=True)


class OverlayPresetCreate(BaseModel):
    """Model for creating overlay presets"""

    name: str = Field(..., min_length=1, max_length=255, description="Preset name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Preset description"
    )
    overlay_config: OverlayConfiguration = Field(
        ..., description="Complete overlay configuration"
    )
    is_builtin: bool = Field(
        False, description="Whether this is a built-in system preset"
    )

    model_config = ConfigDict(from_attributes=True)


class OverlayPreset(BaseModel):
    """Complete overlay preset model"""

    id: int
    name: str
    description: Optional[str] = None
    overlay_config: OverlayConfiguration
    is_builtin: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OverlayPresetUpdate(BaseModel):
    """Model for updating overlay presets"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    overlay_config: Optional[OverlayConfiguration] = None

    model_config = ConfigDict(from_attributes=True)


class TimelapseOverlayCreate(BaseModel):
    """Model for creating timelapse overlay configurations"""

    timelapse_id: int = Field(..., description="ID of the timelapse")
    preset_id: Optional[int] = Field(None, description="ID of selected preset")
    overlay_config: OverlayConfiguration = Field(
        ..., description="Overlay configuration"
    )
    enabled: bool = Field(
        True, description="Whether overlays are enabled for this timelapse"
    )

    model_config = ConfigDict(from_attributes=True)


class TimelapseOverlay(BaseModel):
    """Complete timelapse overlay configuration model"""

    id: int
    timelapse_id: int
    preset_id: Optional[int] = None
    overlay_config: OverlayConfiguration
    enabled: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimelapseOverlayUpdate(BaseModel):
    """Model for updating timelapse overlay configurations"""

    preset_id: Optional[int] = None
    overlay_config: Optional[OverlayConfiguration] = None
    enabled: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class OverlayAssetCreate(BaseModel):
    """Model for creating overlay assets"""

    filename: str = Field(..., max_length=255, description="Generated filename")
    original_name: str = Field(
        ..., max_length=255, description="Original uploaded filename"
    )
    file_path: str = Field(..., description="Path to stored file")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    mime_type: str = Field(..., max_length=100, description="MIME type of file")

    model_config = ConfigDict(from_attributes=True)


class OverlayAsset(BaseModel):
    """Complete overlay asset model"""

    id: int
    filename: str
    original_name: str
    file_path: str
    file_size: int
    mime_type: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OverlayGenerationJobCreate(BaseModel):
    """Model for creating overlay generation jobs"""

    image_id: int = Field(..., description="ID of the image to generate overlay for")
    priority: OverlayJobPriority = Field(
        default=OverlayJobPriority.MEDIUM,
        description="Job priority: high, medium, low",
    )
    status: OverlayJobStatus = Field(
        default=OverlayJobStatus.PENDING, description="Initial job status"
    )
    job_type: OverlayJobType = Field(
        default=OverlayJobType.SINGLE, description="Job type: single, batch, priority"
    )

    model_config = ConfigDict(from_attributes=True)


class OverlayGenerationJob(BaseModel):
    """Complete overlay generation job model"""

    id: int
    image_id: int
    priority: OverlayJobPriority
    status: OverlayJobStatus
    job_type: OverlayJobType
    retry_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OverlayJobStatistics(BaseModel):
    """Statistics for overlay job queue monitoring"""

    total_jobs_24h: int = 0
    pending_jobs: int = 0
    processing_jobs: int = 0
    completed_jobs_24h: int = 0
    failed_jobs_24h: int = 0
    cancelled_jobs_24h: int = 0
    avg_processing_time_ms: int = 0
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class OverlayPreviewRequest(BaseModel):
    """Model for requesting overlay preview generation"""

    camera_id: int = Field(..., description="Camera ID to capture test image from")
    overlay_config: OverlayConfiguration = Field(
        ..., description="Overlay configuration to preview"
    )

    model_config = ConfigDict(from_attributes=True)


class OverlayPreviewResponse(BaseModel):
    """Model for overlay preview response"""

    image_path: str = Field(..., description="Path to generated preview image")
    test_image_path: str = Field(..., description="Path to test image used")
    success: bool = Field(..., description="Whether preview generation succeeded")
    error_message: Optional[str] = Field(
        None, description="Error message if generation failed"
    )

    model_config = ConfigDict(from_attributes=True)
