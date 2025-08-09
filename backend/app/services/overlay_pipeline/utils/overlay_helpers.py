"""
Overlay Helpers - Settings inheritance and configuration management for overlay system.

This module provides utilities for managing overlay configuration inheritance,
merging preset settings with timelapse overrides, and validating overlay configurations.
"""

from typing import Any, Dict, Optional

from ....models.overlay_model import (
    GlobalSettings,
    OverlayConfiguration,
    OverlayItem,
    OverlayPreset,
    TimelapseOverlay,
)


class OverlaySettingsResolver:
    """
    Handles overlay configuration inheritance and merging.

    Provides the logic for combining built-in defaults, preset configurations,
    and timelapse-specific overrides to produce the effective overlay configuration.
    """

    @staticmethod
    def get_effective_configuration(
        preset: Optional[OverlayPreset] = None,
        timelapse_overlay: Optional[TimelapseOverlay] = None,
    ) -> OverlayConfiguration:
        """
        Get the effective overlay configuration by merging preset and timelapse settings.

        Inheritance chain: Built-in defaults → Preset configuration → Timelapse overrides

        Args:
            preset: Selected overlay preset (optional)
            timelapse_overlay: Timelapse-specific overlay configuration (optional)

        Returns:
            Effective overlay configuration ready for rendering
        """
        # Start with default configuration
        effective_config = OverlaySettingsResolver._get_default_configuration()

        # Apply preset configuration if available
        if preset and preset.overlay_config:
            effective_config = OverlaySettingsResolver._merge_configurations(
                effective_config, preset.overlay_config
            )

        # Apply timelapse overrides if available
        if timelapse_overlay and timelapse_overlay.overlay_config:
            effective_config = OverlaySettingsResolver._merge_configurations(
                effective_config, timelapse_overlay.overlay_config
            )

        return effective_config

    @staticmethod
    def _get_default_configuration() -> OverlayConfiguration:
        """Get the built-in default overlay configuration."""
        return OverlayConfiguration(
            overlay_items=[],
            global_settings=GlobalSettings(
                opacity=100,
                font="Arial",
                x_margin=20,
                y_margin=20,
                background_color="#000000",
                background_opacity=50,
                fill_color="#FFFFFF",
                drop_shadow=True,
                preset=None,
            ),
        )

    @staticmethod
    def _merge_configurations(
        base: OverlayConfiguration, override: OverlayConfiguration
    ) -> OverlayConfiguration:
        """
        Merge two overlay configurations, with override taking precedence.

        Args:
            base: Base configuration
            override: Override configuration

        Returns:
            Merged configuration
        """
        # Start with base overlay items
        merged_items = list(base.overlay_items)

        # Override with new items (based on position matching)
        for override_item in override.overlay_items:
            # Find existing item with same position
            existing_index = None
            for i, base_item in enumerate(merged_items):
                if base_item.position == override_item.position:
                    existing_index = i
                    break

            if existing_index is not None:
                # Replace existing item
                merged_items[existing_index] = override_item
            else:
                # Add new item
                merged_items.append(override_item)

        # Merge global settings
        merged_global_settings = GlobalSettings(
            opacity=(
                override.global_settings.opacity
                if override.global_settings.opacity != base.global_settings.opacity
                else base.global_settings.opacity
            ),
            font=(
                override.global_settings.font
                if override.global_settings.font != base.global_settings.font
                else base.global_settings.font
            ),
            x_margin=(
                override.global_settings.x_margin
                if override.global_settings.x_margin != base.global_settings.x_margin
                else base.global_settings.x_margin
            ),
            y_margin=(
                override.global_settings.y_margin
                if override.global_settings.y_margin != base.global_settings.y_margin
                else base.global_settings.y_margin
            ),
            background_color=(
                override.global_settings.background_color
                if override.global_settings.background_color
                != base.global_settings.background_color
                else base.global_settings.background_color
            ),
            background_opacity=(
                override.global_settings.background_opacity
                if override.global_settings.background_opacity
                != base.global_settings.background_opacity
                else base.global_settings.background_opacity
            ),
            fill_color=(
                override.global_settings.fill_color
                if override.global_settings.fill_color
                != base.global_settings.fill_color
                else base.global_settings.fill_color
            ),
            drop_shadow=(
                override.global_settings.drop_shadow
                if override.global_settings.drop_shadow
                != base.global_settings.drop_shadow
                else base.global_settings.drop_shadow
            ),
            preset=(
                override.global_settings.preset
                if override.global_settings.preset != base.global_settings.preset
                else base.global_settings.preset
            ),
        )

        return OverlayConfiguration(
            overlay_items=merged_items, global_settings=merged_global_settings
        )

    @staticmethod
    def validate_configuration_completeness(
        config: OverlayConfiguration,
    ) -> Dict[str, Any]:
        """
        Validate that overlay configuration is complete and ready for rendering.

        Args:
            config: Overlay configuration to validate

        Returns:
            Validation result with status and any issues found
        """
        issues = []
        warnings = []

        # Check if any overlays are defined
        if not config.overlay_items:
            warnings.append("No overlay items defined - overlay will be empty")

        # Validate each overlay item
        for overlay_item in config.overlay_items:
            item_issues = OverlaySettingsResolver._validate_overlay_item(overlay_item)
            issues.extend(item_issues)

        # Validate global settings
        global_issues = OverlaySettingsResolver._validate_global_settings(
            config.global_settings
        )
        issues.extend(global_issues)

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "overlay_count": len(config.overlay_items),
        }

    @staticmethod
    def _validate_overlay_item(overlay_item: OverlayItem) -> list:
        """Validate a single overlay item configuration."""
        issues = []

        # Validate overlay type
        if not overlay_item.type:
            issues.append(f"Position {overlay_item.position}: Missing overlay type")

        # Validate text size
        text_size = overlay_item.settings.get("text_size", 16)
        if text_size < 8 or text_size > 72:
            issues.append(
                f"Position {overlay_item.position}: Text size must be between 8 and 72 pixels"
            )

        # Validate text color format
        text_color = overlay_item.settings.get("text_color")
        if text_color and not text_color.startswith("#"):
            issues.append(
                f"Position {overlay_item.position}: Text color must be in hex format (#RRGGBB)"
            )

        # Validate background opacity
        background_opacity = overlay_item.settings.get("background_opacity", 0)
        if background_opacity < 0 or background_opacity > 100:
            issues.append(
                f"Position {overlay_item.position}: Background opacity must be between 0 and 100"
            )

        # Validate image scale
        image_scale = overlay_item.settings.get("image_scale", 100)
        if image_scale < 10 or image_scale > 500:
            issues.append(
                f"Position {overlay_item.position}: Image scale must be between 10% and 500%"
            )

        # Validate custom text for custom text overlays
        if overlay_item.type == "custom_text":
            custom_text = overlay_item.settings.get("custom_text")
            if not custom_text:
                issues.append(
                    f"Position {overlay_item.position}: Custom text overlay requires text content"
                )

        # Validate image URL for watermark overlays
        if overlay_item.type == "watermark":
            image_url = overlay_item.settings.get("image_url")
            if not image_url:
                issues.append(
                    f"Position {overlay_item.position}: Watermark overlay requires image URL"
                )

        return issues

    @staticmethod
    def _validate_global_settings(global_settings: GlobalSettings) -> list:
        """Validate global overlay settings."""
        issues = []

        # Validate opacity
        if global_settings.opacity < 0 or global_settings.opacity > 100:
            issues.append("Global opacity must be between 0 and 100")

        # Validate margins
        if global_settings.x_margin < 0 or global_settings.x_margin > 200:
            issues.append("X margin must be between 0 and 200 pixels")

        if global_settings.y_margin < 0 or global_settings.y_margin > 200:
            issues.append("Y margin must be between 0 and 200 pixels")

        # Validate font family
        if not global_settings.font:
            issues.append("Font family cannot be empty")

        return issues


class OverlayPresetManager:
    """
    Manager for overlay preset operations and utilities.

    Provides higher-level operations for working with overlay presets,
    including duplication, validation, and conversion utilities.
    """

    @staticmethod
    def duplicate_preset_configuration(
        source_preset: OverlayPreset,
        new_name: str,
        new_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a duplicate configuration from an existing preset.

        Args:
            source_preset: Preset to duplicate
            new_name: Name for the new preset
            new_description: Optional description for the new preset

        Returns:
            Dictionary ready for OverlayPresetCreate model
        """
        return {
            "name": new_name,
            "description": new_description or f"Copy of {source_preset.name}",
            "overlay_config": source_preset.overlay_config,
            "is_builtin": False,  # Duplicated presets are always custom
        }

    @staticmethod
    def extract_preset_summary(preset: OverlayPreset) -> Dict[str, Any]:
        """
        Extract summary information from preset for UI display.

        Args:
            preset: Preset to summarize

        Returns:
            Summary dictionary with key preset information
        """
        overlay_count = len(preset.overlay_config.overlay_items)

        # Categorize overlay types
        text_overlays = []
        weather_overlays = []
        image_overlays = []

        for overlay_item in preset.overlay_config.overlay_items:
            if overlay_item.type in [
                "date",
                "date_time",
                "time",
                "frame_number",
                "day_number",
                "custom_text",
                "timelapse_name",
            ]:
                text_overlays.append(overlay_item.type)
            elif overlay_item.type in [
                "temperature",
                "weather_conditions",
                "weather",  # Unified weather type
            ]:
                weather_overlays.append(overlay_item.type)
            elif overlay_item.type == "watermark":
                image_overlays.append(overlay_item.type)

        return {
            "id": preset.id,
            "name": preset.name,
            "description": preset.description,
            "is_builtin": preset.is_builtin,
            "overlay_count": overlay_count,
            "has_text_overlays": len(text_overlays) > 0,
            "has_weather_overlays": len(weather_overlays) > 0,
            "has_image_overlays": len(image_overlays) > 0,
            "text_overlay_types": text_overlays,
            "weather_overlay_types": weather_overlays,
            "image_overlay_types": image_overlays,
            "global_opacity": preset.overlay_config.global_settings.opacity,
            "font_family": preset.overlay_config.global_settings.font,
            "created_at": preset.created_at,
            "updated_at": preset.updated_at,
        }

    @staticmethod
    def get_builtin_preset_names() -> list:
        """Get list of built-in preset names that should not be deleted."""
        return ["Basic Timestamp", "Weather + Time", "Minimal", "Complete Info"]

    @staticmethod
    def is_preset_deletable(preset: OverlayPreset) -> bool:
        """Check if a preset can be deleted (only custom presets)."""
        return not preset.is_builtin

    @staticmethod
    def sanitize_preset_name(name: str) -> str:
        """Sanitize preset name for safe storage."""
        # Remove or replace invalid characters
        sanitized = name.strip()

        # Ensure reasonable length
        if len(sanitized) > 255:
            sanitized = sanitized[:255]

        # Ensure not empty
        if not sanitized:
            sanitized = "Untitled Preset"

        return sanitized


def get_overlay_type_metadata() -> Dict[str, Dict[str, Any]]:
    """
    Get metadata for all supported overlay types.

    Returns:
        Dictionary mapping overlay types to their metadata (labels, descriptions, etc.)
    """
    return {
        "date": {
            "label": "Date",
            "description": "Current date",
            "category": "time",
            "requires_format": True,
            "default_format": "MM/dd/yyyy",
        },
        "date_time": {
            "label": "Date & Time",
            "description": "Current date and time",
            "category": "time",
            "requires_format": True,
            "default_format": "MM/dd/yyyy HH:mm",
        },
        "time": {
            "label": "Time",
            "description": "Current time",
            "category": "time",
            "requires_format": False,
        },
        "frame_number": {
            "label": "Frame Number",
            "description": "Current frame number in sequence",
            "category": "sequence",
            "requires_format": False,
        },
        "day_number": {
            "label": "Day Number",
            "description": "Current day of timelapse",
            "category": "sequence",
            "requires_format": False,
        },
        "custom_text": {
            "label": "Custom Text",
            "description": "User-defined static text",
            "category": "text",
            "requires_format": False,
            "requires_custom_text": True,
        },
        "timelapse_name": {
            "label": "Timelapse Name",
            "description": "Name of the current timelapse",
            "category": "text",
            "requires_format": False,
        },
        "temperature": {
            "label": "Temperature",
            "description": "Current temperature",
            "category": "weather",
            "requires_format": False,
            "requires_weather": True,
        },
        "weather_conditions": {
            "label": "Weather Conditions",
            "description": "Current weather description",
            "category": "weather",
            "requires_format": False,
            "requires_weather": True,
        },
        "weather": {
            "label": "Weather (Temperature & Conditions)",
            "description": "Combined temperature and weather",
            "category": "weather",
            "requires_format": False,
            "requires_weather": True,
        },
        "watermark": {
            "label": "Watermark/Logo",
            "description": "Custom image overlay",
            "category": "image",
            "requires_format": False,
            "requires_image": True,
        },
    }
