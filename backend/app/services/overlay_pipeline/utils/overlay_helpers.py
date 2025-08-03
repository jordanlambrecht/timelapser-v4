# backend/app/services/overlay_pipeline/utils/overlay_helpers.py
"""
Overlay Helpers - Settings inheritance and configuration management for overlay system.

This module provides utilities for managing overlay configuration inheritance,
merging preset settings with timelapse overrides, and validating overlay configurations.
"""

from typing import Dict, Any, Optional


from ....models.overlay_model import (
    OverlayConfiguration,
    OverlayPreset,
    TimelapseOverlay,
    OverlayItem,
    GlobalOverlayOptions,
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
            overlayPositions={},
            globalOptions=GlobalOverlayOptions(
                opacity=100,
                font="Arial",
                xMargin=20,
                yMargin=20,
                backgroundColor="#000000",
                backgroundOpacity=50,
                fillColor="#FFFFFF",
                dropShadow=True,
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
        # Start with base configuration
        merged_positions = dict(base.overlayPositions)

        # Override with new positions
        merged_positions.update(override.overlayPositions)

        # Merge global options
        merged_global_options = GlobalOverlayOptions(
            opacity=(
                override.globalOptions.opacity
                if override.globalOptions.opacity != base.globalOptions.opacity
                else base.globalOptions.opacity
            ),
            font=(
                override.globalOptions.font
                if override.globalOptions.font != base.globalOptions.font
                else base.globalOptions.font
            ),
            xMargin=(
                override.globalOptions.xMargin
                if override.globalOptions.xMargin != base.globalOptions.xMargin
                else base.globalOptions.xMargin
            ),
            yMargin=(
                override.globalOptions.yMargin
                if override.globalOptions.yMargin != base.globalOptions.yMargin
                else base.globalOptions.yMargin
            ),
            backgroundColor=(
                override.globalOptions.backgroundColor
                if override.globalOptions.backgroundColor
                != base.globalOptions.backgroundColor
                else base.globalOptions.backgroundColor
            ),
            backgroundOpacity=(
                override.globalOptions.backgroundOpacity
                if override.globalOptions.backgroundOpacity
                != base.globalOptions.backgroundOpacity
                else base.globalOptions.backgroundOpacity
            ),
            fillColor=(
                override.globalOptions.fillColor
                if override.globalOptions.fillColor != base.globalOptions.fillColor
                else base.globalOptions.fillColor
            ),
            dropShadow=(
                override.globalOptions.dropShadow
                if override.globalOptions.dropShadow != base.globalOptions.dropShadow
                else base.globalOptions.dropShadow
            ),
            preset=(
                override.globalOptions.preset
                if override.globalOptions.preset != base.globalOptions.preset
                else base.globalOptions.preset
            ),
        )

        return OverlayConfiguration(
            overlayPositions=merged_positions, globalOptions=merged_global_options
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
        if not config.overlayPositions:
            warnings.append("No overlay positions defined - overlay will be empty")

        # Validate each overlay item
        for position, overlay_item in config.overlayPositions.items():
            position_issues = OverlaySettingsResolver._validate_overlay_item(
                position, overlay_item
            )
            issues.extend(position_issues)

        # Validate global options
        global_issues = OverlaySettingsResolver._validate_global_options(
            config.globalOptions
        )
        issues.extend(global_issues)

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "overlay_count": len(config.overlayPositions),
        }

    @staticmethod
    def _validate_overlay_item(position: str, overlay_item: OverlayItem) -> list:
        """Validate a single overlay item configuration."""
        issues = []

        # Validate overlay type
        if not overlay_item.type:
            issues.append(f"Position {position}: Missing overlay type")

        # Validate text size
        if overlay_item.textSize < 8 or overlay_item.textSize > 72:
            issues.append(
                f"Position {position}: Text size must be between 8 and 72 pixels"
            )

        # Validate text color format
        if overlay_item.textColor and not overlay_item.textColor.startswith("#"):
            issues.append(
                f"Position {position}: Text color must be in hex format (#RRGGBB)"
            )

        # Validate background opacity
        if overlay_item.backgroundOpacity < 0 or overlay_item.backgroundOpacity > 100:
            issues.append(
                f"Position {position}: Background opacity must be between 0 and 100"
            )

        # Validate image scale
        if overlay_item.imageScale < 10 or overlay_item.imageScale > 500:
            issues.append(
                f"Position {position}: Image scale must be between 10% and 500%"
            )

        # Validate custom text for custom text overlays
        if overlay_item.type == "custom_text" and not overlay_item.customText:
            issues.append(
                f"Position {position}: Custom text overlay requires text content"
            )

        # Validate image URL for watermark overlays
        if overlay_item.type == "watermark" and not overlay_item.imageUrl:
            issues.append(f"Position {position}: Watermark overlay requires image URL")

        return issues

    @staticmethod
    def _validate_global_options(global_options: GlobalOverlayOptions) -> list:
        """Validate global overlay options."""
        issues = []

        # Validate opacity
        if global_options.opacity < 0 or global_options.opacity > 100:
            issues.append("Global opacity must be between 0 and 100")

        # Validate margins
        if global_options.xMargin < 0 or global_options.xMargin > 200:
            issues.append("X margin must be between 0 and 200 pixels")

        if global_options.yMargin < 0 or global_options.yMargin > 200:
            issues.append("Y margin must be between 0 and 200 pixels")

        # Validate font family
        if not global_options.font:
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
        overlay_count = len(preset.overlay_config.overlayPositions)

        # Categorize overlay types
        text_overlays = []
        weather_overlays = []
        image_overlays = []

        for position, overlay_item in preset.overlay_config.overlayPositions.items():
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
                "weather_temp_conditions",
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
            "global_opacity": preset.overlay_config.globalOptions.opacity,
            "font_family": preset.overlay_config.globalOptions.font,
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
        "weather_temp_conditions": {
            "label": "Temperature & Conditions",
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
