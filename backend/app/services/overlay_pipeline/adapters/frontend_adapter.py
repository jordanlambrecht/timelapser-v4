#!/usr/bin/env python3
# backend/app/services/overlay_pipeline/adapters/frontend_adapter.py

"""
Frontend adapter for overlay pipeline - transforms frontend data to backend format.
Handles the modern unified overlay format with overlayItems array structure.
"""

from typing import Dict, Any
from app.models.overlay_model import OverlayConfiguration, OverlayItem, GlobalSettings


class FrontendAdapter:
    """Adapter to transform frontend overlay data to backend pipeline format."""

    @staticmethod
    def transform_overlay_config(config: OverlayConfiguration) -> Dict[str, Any]:
        """
        Transform modern OverlayConfiguration to backend pipeline format.

        Args:
            config: Modern OverlayConfiguration with overlay_items array

        Returns:
            Dict formatted for backend overlay pipeline processing
        """
        # Transform overlay items array to processing format
        overlay_items = []
        for item in config.overlay_items:
            if item.enabled:  # Only include enabled items
                overlay_items.append(
                    {
                        "id": item.id,
                        "type": item.type,
                        "position": item.position,
                        "settings": item.settings or {},
                    }
                )

        # Create backend processing format
        return {
            "global_settings": {
                "opacity": config.global_settings.opacity,
                "font": config.global_settings.font,
                "x_margin": config.global_settings.x_margin,
                "y_margin": config.global_settings.y_margin,
                "background_color": config.global_settings.background_color,
                "background_opacity": config.global_settings.background_opacity,
                "fill_color": config.global_settings.fill_color,
                "drop_shadow": config.global_settings.drop_shadow,
            },
            "overlay_items": overlay_items,
        }

    @staticmethod
    def validate_overlay_config(config: OverlayConfiguration) -> bool:
        """
        Validate that the overlay configuration is properly formatted.

        Args:
            config: OverlayConfiguration to validate

        Returns:
            bool: True if valid, False otherwise
        """
        if not isinstance(config, OverlayConfiguration):
            return False

        if not config.global_settings or not isinstance(
            config.global_settings, GlobalSettings
        ):
            return False

        if not hasattr(config, "overlay_items") or not isinstance(
            config.overlay_items, list
        ):
            return False

        # Validate each overlay item
        for item in config.overlay_items:
            if not isinstance(item, OverlayItem):
                return False
            if not all(
                hasattr(item, attr) for attr in ["id", "type", "position", "enabled"]
            ):
                return False

        return True
