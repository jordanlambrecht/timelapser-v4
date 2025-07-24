# backend/app/services/overlay_pipeline/services/template_service.py
"""
Overlay Template Service - Management of overlay templates and caching.
"""

from typing import Dict, Any, Optional, List
from loguru import logger

from ....database.core import SyncDatabase, AsyncDatabase
from ..utils.overlay_template_cache import OverlayTemplateManager


class SyncOverlayTemplateService:
    """
    Synchronous service for overlay template management.
    Handles template caching, validation, and configuration resolution.
    """

    def __init__(self, db: SyncDatabase):
        """Initialize with sync database."""
        self.db = db
        self.template_cache = OverlayTemplateCache()

    def get_template_by_name(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        Get overlay template configuration by name.

        Args:
            template_name: Name of the template to retrieve

        Returns:
            Template configuration dict or None if not found
        """
        try:
            return self.template_cache.get_template(template_name)
        except Exception as e:
            logger.error(f"Failed to get template '{template_name}': {e}")
            return None

    def create_template(self, name: str, configuration: Dict[str, Any]) -> bool:
        """
        Create a new overlay template.

        Args:
            name: Template name
            configuration: Template configuration

        Returns:
            True if template was created successfully
        """
        try:
            return self.template_cache.set_template(name, configuration)
        except Exception as e:
            logger.error(f"Failed to create template '{name}': {e}")
            return False

    def update_template(self, name: str, configuration: Dict[str, Any]) -> bool:
        """
        Update an existing overlay template.

        Args:
            name: Template name
            configuration: Updated template configuration

        Returns:
            True if template was updated successfully
        """
        try:
            return self.template_cache.update_template(name, configuration)
        except Exception as e:
            logger.error(f"Failed to update template '{name}': {e}")
            return False

    def delete_template(self, name: str) -> bool:
        """
        Delete an overlay template.

        Args:
            name: Template name to delete

        Returns:
            True if template was deleted successfully
        """
        try:
            return self.template_cache.delete_template(name)
        except Exception as e:
            logger.error(f"Failed to delete template '{name}': {e}")
            return False

    def list_templates(self) -> List[str]:
        """
        Get list of all available template names.

        Returns:
            List of template names
        """
        try:
            return self.template_cache.list_templates()
        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
            return []

    def validate_template(self, configuration: Dict[str, Any]) -> bool:
        """
        Validate overlay template configuration.

        Args:
            configuration: Template configuration to validate

        Returns:
            True if configuration is valid
        """
        try:
            # Basic validation
            if not isinstance(configuration, dict):
                return False

            # Check required fields
            required_fields = ["overlays"]
            for field in required_fields:
                if field not in configuration:
                    logger.error(f"Template missing required field: {field}")
                    return False

            # Validate overlays array
            overlays = configuration["overlays"]
            if not isinstance(overlays, list):
                logger.error("Template overlays must be a list")
                return False

            # Validate each overlay
            for i, overlay in enumerate(overlays):
                if not self._validate_overlay_config(overlay):
                    logger.error(f"Invalid overlay configuration at index {i}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Failed to validate template: {e}")
            return False

    def resolve_template_inheritance(
        self, base_template: str, overrides: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve template inheritance by applying overrides to base template.

        Args:
            base_template: Name of base template
            overrides: Configuration overrides to apply

        Returns:
            Resolved configuration or None if base template not found
        """
        try:
            # Get base template
            base_config = self.get_template_by_name(base_template)
            if not base_config:
                logger.error(f"Base template '{base_template}' not found")
                return None

            # Apply overrides
            resolved_config = self._merge_configurations(base_config, overrides)
            
            # Validate resolved configuration
            if not self.validate_template(resolved_config):
                logger.error("Resolved template configuration is invalid")
                return None

            return resolved_config

        except Exception as e:
            logger.error(f"Failed to resolve template inheritance: {e}")
            return None

    def clear_cache(self) -> bool:
        """
        Clear the template cache.

        Returns:
            True if cache was cleared successfully
        """
        try:
            return self.template_cache.clear()
        except Exception as e:
            logger.error(f"Failed to clear template cache: {e}")
            return False

    def _validate_overlay_config(self, overlay: Dict[str, Any]) -> bool:
        """Validate individual overlay configuration."""
        if not isinstance(overlay, dict):
            return False

        # Check required fields
        if "type" not in overlay:
            logger.error("Overlay missing required 'type' field")
            return False

        overlay_type = overlay["type"]
        valid_types = ["text", "timestamp", "weather", "image", "frame_number", "day_number"]
        if overlay_type not in valid_types:
            logger.error(f"Invalid overlay type: {overlay_type}")
            return False

        # Type-specific validation
        if overlay_type == "image" and "image_path" not in overlay:
            logger.error("Image overlay missing 'image_path' field")
            return False

        return True

    def _merge_configurations(
        self, base: Dict[str, Any], overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge configuration overrides with base configuration."""
        result = base.copy()
        
        for key, value in overrides.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                # Recursively merge dictionaries
                result[key] = self._merge_configurations(result[key], value)
            else:
                # Override value
                result[key] = value
        
        return result


class OverlayTemplateService:
    """
    Asynchronous service for overlay template management.
    Provides async versions for use in API endpoints.
    """

    def __init__(self, db: AsyncDatabase):
        """Initialize with async database."""
        self.db = db
        self.template_cache = OverlayTemplateCache()

    async def get_template_by_name(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get overlay template configuration by name (async)."""
        try:
            return self.template_cache.get_template(template_name)
        except Exception as e:
            logger.error(f"Failed to get template '{template_name}': {e}")
            return None

    async def create_template(self, name: str, configuration: Dict[str, Any]) -> bool:
        """Create a new overlay template (async)."""
        try:
            return self.template_cache.set_template(name, configuration)
        except Exception as e:
            logger.error(f"Failed to create template '{name}': {e}")
            return False

    async def update_template(self, name: str, configuration: Dict[str, Any]) -> bool:
        """Update an existing overlay template (async)."""
        try:
            return self.template_cache.update_template(name, configuration)
        except Exception as e:
            logger.error(f"Failed to update template '{name}': {e}")
            return False

    async def delete_template(self, name: str) -> bool:
        """Delete an overlay template (async)."""
        try:
            return self.template_cache.delete_template(name)
        except Exception as e:
            logger.error(f"Failed to delete template '{name}': {e}")
            return False

    async def list_templates(self) -> List[str]:
        """Get list of all available template names (async)."""
        try:
            return self.template_cache.list_templates()
        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
            return []

    async def validate_template(self, configuration: Dict[str, Any]) -> bool:
        """Validate overlay template configuration (async)."""
        # Reuse sync validation logic
        sync_service = SyncOverlayTemplateService(None)
        return sync_service.validate_template(configuration)

    async def clear_cache(self) -> bool:
        """Clear the template cache (async)."""
        try:
            return self.template_cache.clear()
        except Exception as e:
            logger.error(f"Failed to clear template cache: {e}")
            return False