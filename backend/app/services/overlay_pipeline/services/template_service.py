# backend/app/services/overlay_pipeline/services/template_service.py
"""
Overlay Template Service - Read-only access to built-in overlay templates.

Templates are just built-in presets (is_builtin = true) that users can't delete.
"""

from typing import List, Optional

from ....enums import LoggerName, LogSource
from ....services.logger import get_service_logger


from ....database.core import AsyncDatabase, SyncDatabase
from ....database.overlay_operations import OverlayOperations, SyncOverlayOperations
from ....models.overlay_model import OverlayPreset

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)


class SyncOverlayTemplateService:
    """Read-only access to built-in overlay templates."""

    def __init__(self, db: SyncDatabase):
        self.overlay_ops = SyncOverlayOperations(db)

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
            logger.error(f"Failed to get template '{template_name}'", exception=e)
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

    def __init__(self, db: AsyncDatabase):
        self.overlay_ops = OverlayOperations(db)

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
