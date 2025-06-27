# backend/app/utils/video_helpers.py
"""
Video Helper Functions

Business logic and utility functions for video operations.
Contains pure business logic that doesn't directly interact with the database.
"""

from typing import Dict, Any, Optional


class VideoSettingsHelper:
    """
    Helper class for video settings inheritance and business logic.
    """

    @staticmethod
    def get_effective_video_settings(
        timelapse_settings: Optional[Dict[str, Any]],
        camera_settings: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Apply settings inheritance logic for video generation.

        Inheritance order: defaults -> camera -> timelapse

        Args:
            timelapse_settings: Timelapse-specific video settings
            camera_settings: Camera default video settings

        Returns:
            Effective video settings with inheritance applied
        """
        # Default settings
        defaults = {
            "fps": 30,
            "quality": "high",
            "resolution": "original",
            "max_duration": 60,
            "min_duration": 5,
            "overlay_enabled": True,
            "overlay_position": "bottom_right",
            "overlay_font_size": 24,
        }

        # Apply inheritance: defaults -> camera -> timelapse
        effective_settings = defaults.copy()

        if camera_settings:
            effective_settings.update(camera_settings)

        if timelapse_settings:
            effective_settings.update(timelapse_settings)

        return effective_settings

    @staticmethod
    def validate_video_settings(settings: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate video generation settings.

        Args:
            settings: Video settings dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate FPS
        if "fps" in settings:
            try:
                fps = float(settings["fps"])
                if fps <= 0 or fps > 120:
                    return False, "FPS must be between 0 and 120"
            except (ValueError, TypeError):
                return False, "FPS must be a valid number"

        # Validate quality
        if "quality" in settings:
            valid_qualities = {"low", "medium", "high", "ultra"}
            if settings["quality"] not in valid_qualities:
                return False, f"Quality must be one of: {', '.join(valid_qualities)}"

        # Validate resolution
        if "resolution" in settings:
            valid_resolutions = {"original", "1080p", "720p", "480p"}
            if settings["resolution"] not in valid_resolutions:
                return (
                    False,
                    f"Resolution must be one of: {', '.join(valid_resolutions)}",
                )

        # Validate duration limits
        for duration_field in ["max_duration", "min_duration"]:
            if duration_field in settings:
                try:
                    duration = float(settings[duration_field])
                    if duration <= 0:
                        return False, f"{duration_field} must be positive"
                except (ValueError, TypeError):
                    return False, f"{duration_field} must be a valid number"

        # Validate min <= max duration
        if "min_duration" in settings and "max_duration" in settings:
            if settings["min_duration"] > settings["max_duration"]:
                return False, "min_duration cannot be greater than max_duration"

        # Validate overlay settings
        if "overlay_position" in settings:
            valid_positions = {
                "top_left",
                "top_right",
                "bottom_left",
                "bottom_right",
                "center",
            }
            if settings["overlay_position"] not in valid_positions:
                return (
                    False,
                    f"Overlay position must be one of: {', '.join(valid_positions)}",
                )

        if "overlay_font_size" in settings:
            try:
                font_size = int(settings["overlay_font_size"])
                if font_size < 8 or font_size > 72:
                    return False, "Overlay font size must be between 8 and 72"
            except (ValueError, TypeError):
                return False, "Overlay font size must be a valid integer"

        return True, None
