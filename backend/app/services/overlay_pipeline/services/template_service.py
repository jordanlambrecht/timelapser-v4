# backend/app/services/overlay_pipeline/services/template_service.py
"""
Overlay Template Service - Read-only access to built-in overlay templates.

Templates are just built-in presets (is_builtin = true) that users can't delete.
"""

from typing import List, Optional

from ....database.core import AsyncDatabase, SyncDatabase
from ....database.overlay_operations import OverlayOperations, SyncOverlayOperations
from ....enums import LoggerName, LogSource
from ....models.overlay_model import OverlayPreset
from ....services.logger import get_service_logger

logger = get_service_logger(LoggerName.OVERLAY_PRESET_SERVICE, LogSource.PIPELINE)


class SyncOverlayTemplateService:
    """Read-only access to built-in overlay templates."""

    def __init__(self, db: SyncDatabase, overlay_ops=None):
        self.overlay_ops = overlay_ops or self._get_default_overlay_ops()
        
    def _get_default_overlay_ops(self):
        """Fallback to create SyncOverlayOperations directly if not injected"""
        # Using injected SyncOverlayOperations singleton
        from ....dependencies.specialized import get_sync_overlay_operations
        return get_sync_overlay_operations()

    def get_template_by_name(self, template_name: str) -> Optional[OverlayPreset]:
        """Get built-in template by name."""
        if not template_name or not template_name.strip():
            logger.warning("Template name cannot be empty")
            return None

        try:
            # Get only builtin presets, then find by name
            presets = self.overlay_ops.get_all_presets(include_builtin=True)
            for preset in presets:
                if preset.name == template_name and preset.is_builtin:
                    logger.debug(f"Found template: {template_name}")
                    return preset

            logger.debug(f"Template not found: {template_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to get template '{template_name}': {e}")
            return None

    def list_templates(self) -> List[OverlayPreset]:
        """Get all built-in templates."""
        try:
            # Get all presets and filter for builtin ones
            presets = self.overlay_ops.get_all_presets(include_builtin=True)
            templates = [p for p in presets if p.is_builtin]
            logger.debug(f"Found {len(templates)} built-in templates")
            return templates
        except Exception as e:
            logger.error("Failed to list templates", exception=e)
            return []


class OverlayTemplateService:
    """Async read-only access to built-in overlay templates."""

    def __init__(self, db: AsyncDatabase, overlay_ops=None):
        self.db = db
        self.overlay_ops = overlay_ops or self._get_default_overlay_ops()
        
    def _get_default_overlay_ops(self):
        """Fallback to get OverlayOperations singleton"""
        # This is a sync method in an async class, use direct instantiation
        from ....database.overlay_operations import OverlayOperations
        return OverlayOperations(self.db)

    async def get_template_by_name(self, template_name: str) -> Optional[OverlayPreset]:
        """Get built-in template by name (async)."""
        if not template_name or not template_name.strip():
            logger.warning("Template name cannot be empty")
            return None

        try:
            # Get only builtin presets, then find by name
            presets = await self.overlay_ops.get_all_presets(include_builtin=True)
            for preset in presets:
                if preset.name == template_name and preset.is_builtin:
                    logger.debug(f"Found template: {template_name}")
                    return preset

            logger.debug(f"Template not found: {template_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to get template '{template_name}'", exception=e)
            return None

    async def list_templates(self) -> List[OverlayPreset]:
        """Get all built-in templates (async)."""
        try:
            # Get all presets and filter for builtin ones
            presets = await self.overlay_ops.get_all_presets(include_builtin=True)
            templates = [p for p in presets if p.is_builtin]
            logger.debug(f"Found {len(templates)} built-in templates")
            return templates
        except Exception as e:
            logger.error("Failed to list templates", exception=e)
            return []
