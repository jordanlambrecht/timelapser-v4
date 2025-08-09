# backend/app/services/overlay_pipeline/generators/sequence_generator.py
"""
Sequence Overlay Generator - Handles frame and day number overlay content generation.

Supports sequence-based overlays with formatting options.
"""

from datetime import datetime
from typing import Union

from PIL import Image as PILImage

from ....enums import LogEmoji, LoggerName, LogSource
from ....models.overlay_model import OverlayItem
from ....services.logger import get_service_logger
from ....utils.validation_helpers import validate_boolean_property
from .base_generator import BaseOverlayGenerator, OverlayGenerationContext

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)


class SequenceGenerator(BaseOverlayGenerator):
    """
    Generator for sequence-based overlay content.

    Handles:
    - frame_number: Sequential frame number in timelapse
    - day_number: Day count since timelapse started

    Both types produce dynamic content that changes with each frame.
    """

    @property
    def generator_type(self) -> str:
        """Return the primary generator type."""
        return "frame_number"

    @property
    def display_name(self) -> str:
        """Human-readable name for this generator."""
        return "Sequence Numbers"

    @property
    def description(self) -> str:
        """Description of what this generator does."""
        return "Displays frame numbers and day counts with formatting options"

    @property
    def supported_types(self) -> list[str]:
        """Return list of overlay types this generator supports."""
        return ["frame_number", "day_number"]

    @property
    def is_static(self) -> bool:
        """Sequence content is dynamic - changes with each frame."""
        return False

    def generate_content(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
    ) -> Union[str, PILImage.Image]:
        """
        Generate sequence content based on overlay type.

        Args:
            overlay_item: Sequence overlay configuration
            context: Generation context with sequence information

        Returns:
            Formatted sequence number string

        Raises:
            ValueError: If overlay type is not supported or required data is missing
        """
        logger.debug(f"Starting {overlay_item.type} sequence overlay generation")

        try:
            self.validate_overlay_item(overlay_item)
            logger.debug(
                f"Sequence overlay validation passed for type: {overlay_item.type}"
            )

            if overlay_item.type == "frame_number":
                result = self._generate_frame_number(overlay_item, context)
                logger.debug(f"Generated frame number overlay: '{result}'")
            elif overlay_item.type == "day_number":
                result = self._generate_day_number(overlay_item, context)
                logger.debug(f"Generated day number overlay: '{result}'")
            else:
                logger.error(f"Unsupported sequence overlay type: {overlay_item.type}")
                raise ValueError(f"Unsupported overlay type: {overlay_item.type}")

            return result

        except ValueError as e:
            logger.error("Validation error in sequence overlay generation", exception=e)
            raise
        except Exception as e:
            logger.error("Failed to generate sequence overlay content", exception=e)
            raise RuntimeError(f"Failed to generate sequence content: {e}")

    def _generate_frame_number(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
    ) -> str:
        """
        Generate frame number content.

        Args:
            overlay_item: Frame number overlay configuration
            context: Generation context with frame information

        Returns:
            Formatted frame number string
        """
        logger.debug("🔢 Processing frame number overlay generation")

        frame_number = context.frame_number
        logger.debug(f"🔢 Current frame number: {frame_number}")

        # Apply leading zeros if requested
        leading_zeros = overlay_item.settings.get("leading_zeros", False)
        if leading_zeros:
            logger.debug("🔢 Applying leading zeros (6-digit padding)")
            # Estimate total frames for proper padding
            # For now, use 6 digits which handles up to 999,999 frames
            formatted_number = f"{frame_number:06d}"
        else:
            formatted_number = str(frame_number)

        # Add prefix unless hidden
        hide_prefix = overlay_item.settings.get("hide_prefix", False)
        if hide_prefix:
            logger.debug("Prefix hidden, returning number only")
            result = formatted_number
        else:
            logger.debug("🔢 Including 'Frame' prefix")
            result = f"Frame {formatted_number}"

        logger.debug("✅ Frame number overlay generated successfully")
        return result

    def _generate_day_number(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
    ) -> str:
        """
        Generate day number content.

        Args:
            overlay_item: Day number overlay configuration
            context: Generation context with day information

        Returns:
            Formatted day number string
        """
        logger.debug("🔢 Processing day number overlay generation")

        day_number = context.day_number
        logger.debug(f"🔢 Current day number: {day_number}")

        # Apply leading zeros if requested
        leading_zeros = overlay_item.settings.get("leading_zeros", False)
        if leading_zeros:
            logger.debug("🔢 Applying leading zeros (3-digit padding)")
            # Most timelapses won't exceed 999 days, so use 3 digits
            formatted_number = f"{day_number:03d}"
        else:
            formatted_number = str(day_number)

        # Add prefix unless hidden
        hide_prefix = overlay_item.settings.get("hide_prefix", False)
        if hide_prefix:
            logger.debug("Prefix hidden, returning number only")
            result = formatted_number
        else:
            logger.debug("🔢 Including 'Day' prefix")
            # Use appropriate singular/plural form
            if day_number == 1:
                result = f"Day {formatted_number}"
            else:
                result = f"Day {formatted_number}"

        logger.debug(
            "Day number overlay generated successfully", emoji=LogEmoji.SUCCESS
        )
        return result

    def _calculate_day_number_from_dates(
        self, start_date: datetime, current_date: datetime
    ) -> int:
        """
        Calculate day number based on start and current dates.

        Args:
            start_date: When the timelapse started
            current_date: Current image timestamp

        Returns:
            Day number (1-based)
        """
        logger.debug(
            f"🔢 Calculating day number from dates: start={start_date.date()}, current={current_date.date()}"
        )

        # Calculate the difference in days
        delta = current_date.date() - start_date.date()

        # Return 1-based day number
        day_number = delta.days + 1
        logger.debug(
            f"🔢 Day number calculated: {day_number} (delta: {delta.days} days)"
        )
        return day_number

    def validate_overlay_item(self, overlay_item: OverlayItem) -> None:
        """
        Validate sequence overlay item configuration.

        Args:
            overlay_item: Overlay item to validate

        Raises:
            ValueError: If overlay item is invalid for sequence generation
        """
        logger.debug(
            f"🔍 Validating sequence overlay item of type: {overlay_item.type}"
        )

        super().validate_overlay_item(overlay_item)

        # Use validation helpers for consistent boolean validation
        try:
            # Validate boolean properties from settings
            leading_zeros = overlay_item.settings.get("leading_zeros", False)
            hide_prefix = overlay_item.settings.get("hide_prefix", False)

            validated_leading_zeros = validate_boolean_property(
                leading_zeros, "leading_zeros"
            )
            validated_hide_prefix = validate_boolean_property(
                hide_prefix, "hide_prefix"
            )

            if validated_leading_zeros is not None:
                logger.debug(f"🔢 Validated leading_zeros: {validated_leading_zeros}")
            if validated_hide_prefix is not None:
                logger.debug(f"🔢 Validated hide_prefix: {validated_hide_prefix}")

        except ValueError as e:
            logger.error("Sequence validation failed", exception=e)
            raise

        logger.debug(
            f"Sequence overlay validation completed for type: {overlay_item.type}",
            emoji=LogEmoji.SUCCESS,
        )
        if overlay_item.settings.get("leading_zeros", False):
            logger.debug("Leading zeros enabled")
        if overlay_item.settings.get("hide_prefix", False):
            logger.debug("Prefix hiding enabled")
