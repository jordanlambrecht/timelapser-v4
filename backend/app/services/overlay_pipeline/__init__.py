# backend/app/services/overlay_pipeline/__init__.py
"""
Overlay Pipeline Module

Provides overlay generation pipeline following the established corruption/thumbnail pattern.
Supports both sync (worker) and async (API) interfaces with clean separation of concerns.
"""

from .overlay_pipeline import (
    OverlayPipeline,
    create_overlay_pipeline,
    create_sync_overlay_pipeline,
    get_overlay_pipeline_health,
)
from .services.integration_service import (
    OverlayIntegrationService as AsyncOverlayService,
)
from .services.integration_service import (
    SyncOverlayIntegrationService as OverlayService,
)

__all__ = [
    "OverlayPipeline",
    "create_overlay_pipeline",
    "create_sync_overlay_pipeline",
    "get_overlay_pipeline_health",
    "OverlayService",  # Backward compatibility
    "AsyncOverlayService",  # Backward compatibility
]
