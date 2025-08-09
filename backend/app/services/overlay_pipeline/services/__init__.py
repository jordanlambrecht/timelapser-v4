# backend/app/services/overlay_pipeline/services/__init__.py
"""
Overlay Services Module

Contains all overlay service functionality including job management, presets, templates, and integration.
"""

# Re-enabling integration service after fixing legacy format issues
from .integration_service import (
    OverlayIntegrationService,
    SyncOverlayIntegrationService,
)
from .job_service import AsyncOverlayJobService, SyncOverlayJobService
from .preset_service import OverlayPresetService, SyncOverlayPresetService
from .template_service import OverlayTemplateService, SyncOverlayTemplateService

__all__ = [
    "SyncOverlayJobService",
    "AsyncOverlayJobService",
    "OverlayPresetService",
    "SyncOverlayPresetService",
    "OverlayTemplateService",
    "SyncOverlayTemplateService",
    "OverlayIntegrationService",  # Re-enabled
    "SyncOverlayIntegrationService",  # Re-enabled
]
