# backend/app/services/overlay_pipeline/utils/overlay_utils.py
"""
Overlay Utilities - Pillow-based image composition and text rendering for overlay generation.

This module provides the core image processing functionality for generating overlay images
that will be composited onto timelapse frames. All overlay rendering is done using PIL/Pillow
for high-quality text and image composition.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from PIL import Image, ImageColor, ImageDraw

from ....constants import OVERLAY_TYPE_WATERMARK
from ....enums import LoggerName, LogSource, OverlayGridPosition
from ....models.image_model import Image as ImageModel
from ....models.overlay_model import OverlayConfiguration, OverlayItem
from ....models.timelapse_model import Timelapse as TimelapseModel
from ....services.logger import LogEmoji, get_service_logger
from ....utils.time_utils import utc_now
from ..generators import OverlayGenerationContext, overlay_generator_registry
from .font_cache import get_font_fast, get_text_size_fast
from .overlay_template_cache import get_overlay_template

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)


class OverlayRenderer:
    """
    High-performance overlay rendering using PIL/Pillow.

    Handles text rendering, image composition, and positioning for overlay generation.
    Optimized for timelapse processing with caching and efficient memory usage.
    """

    def __init__(self, config: OverlayConfiguration):
        """
        Initialize overlay renderer with configuration.

        Args:
            config: Overlay configuration containing positions and global options
        """
        self.config = config
        # Note: Font caching now handled by global font cache

    def render_overlay(
        self, base_image_path: str, output_path: str, context_data: Dict[str, Any]
    ) -> bool:
        """
        Render overlay onto base image and save result.

        Args:
            base_image_path: Path to base image (camera capture)
            output_path: Path where overlay image should be saved
            context_data: Dynamic data for overlay content (weather, timestamps, etc.)

        Returns:
            True if overlay was successfully rendered and saved
        """
        try:
            # Load base image
            with Image.open(base_image_path) as base_image:
                # Convert to RGBA if needed for transparency support
                if base_image.mode != "RGBA":
                    base_image = base_image.convert("RGBA")

                # Try template caching, fallback to standard rendering if needed
                try:
                    # Check if we can safely use async template caching
                    try:
                        asyncio.get_running_loop()
                        # We're already in an async context - this shouldn't happen in sync render_overlay
                        logger.warning(
                            "render_overlay called from async context - this may cause issues"
                        )
                        result_image = self._render_overlay_fallback(
                            base_image, context_data
                        )
                    except RuntimeError:
                        # No running event loop, safe to create one for template caching
                        result_image = asyncio.run(
                            self.render_overlay_fast(base_image, context_data)
                        )
                except Exception as e:
                    logger.warning(
                        "Template caching failed, using fallback rendering", exception=e
                    )
                    # Fallback to standard rendering without template caching
                    result_image = self._render_overlay_fallback(
                        base_image, context_data
                    )

                # Save as PNG to preserve transparency
                result_image.save(output_path, "PNG", optimize=True)

                logger.debug(
                    f"Successfully rendered overlay to {output_path}",
                    emoji=LogEmoji.SUCCESS,
                )
                return True

        except Exception as e:
            logger.error("Failed to render overlay", exception=e)
            return False

    async def render_overlay_fast(
        self, base_image: Image.Image, context_data: Dict[str, Any]
    ) -> Image.Image:
        """
        High-performance overlay rendering using template caching.

        Args:
            base_image: Base image (already loaded)
            context_data: Dynamic data for overlay content

        Returns:
            Composited image with overlays applied
        """
        try:
            # Get cached template for this configuration and image size
            template = await get_overlay_template(self.config, base_image.size)

            # Use template's fast rendering
            result_image = template.render_frame_fast(base_image, context_data)

            return result_image

        except Exception as e:
            logger.warning(
                "Template rendering failed, falling back to standard rendering",
                exception=e,
            )
            return self._render_overlay_fallback(base_image, context_data)

    def _render_overlay_fallback(
        self, base_image: Image.Image, context_data: Dict[str, Any]
    ) -> Image.Image:
        """Fallback rendering method without template caching."""

        # Convert to RGBA if needed for transparency support
        if base_image.mode != "RGBA":
            base_image = base_image.convert("RGBA")
        else:
            base_image = base_image.copy()

        # Create overlay layer
        overlay_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay_layer)

        # Render each positioned overlay
        for position, overlay_item in self.config.overlay_positions.items():
            self._render_overlay_item(
                draw, overlay_layer, position, overlay_item, context_data
            )

        # Apply global opacity
        if self.config.global_options.opacity < 100:
            overlay_layer = self._apply_global_opacity(overlay_layer)

        # Composite overlay onto base image
        final_image = Image.alpha_composite(base_image, overlay_layer)

        return final_image

    def _render_overlay_item(
        self,
        draw: ImageDraw.ImageDraw,
        overlay_layer: Image.Image,
        position: OverlayGridPosition,
        overlay_item: OverlayItem,
        context_data: Dict[str, Any],
    ) -> None:
        """Render a single overlay item at the specified position."""

        # Get overlay content text
        content_text = self._get_overlay_content(overlay_item, context_data)
        if not content_text and overlay_item.type != OVERLAY_TYPE_WATERMARK:
            return  # Skip empty text overlays

        # Calculate position coordinates
        x, y = self._calculate_position(position, overlay_layer.size)

        if overlay_item.type == OVERLAY_TYPE_WATERMARK:
            self._render_image_overlay(overlay_layer, overlay_item, x, y)
        else:
            self._render_text_overlay(draw, overlay_item, content_text, x, y)

    def _get_overlay_content(
        self, overlay_item: OverlayItem, context_data: Dict[str, Any]
    ) -> str:
        """Generate content text for overlay based on type using modular generators."""
        try:
            # Create generation context from context_data
            context = self._create_generation_context(context_data)

            # Get appropriate generator for this overlay type
            if not overlay_generator_registry.has_generator(overlay_item.type):
                logger.warning(
                    f"No generator found for overlay type: {overlay_item.type}"
                )
                return ""

            generator = overlay_generator_registry.get_generator(overlay_item.type)

            # Generate content using the appropriate generator
            content = generator.generate_content(overlay_item, context)

            # Handle both text and image content
            if isinstance(content, str):
                return content
            else:
                # For image content (watermarks), we'll handle this in the calling method
                # Store the image in context_data for later use
                context_data["_generated_image"] = content
                return ""  # Return empty string to indicate image content

        except Exception as e:
            logger.error(
                f"Failed to generate overlay content for type {overlay_item.type}",
                exception=e,
            )
            return ""  # Graceful fallback

    def _create_generation_context(
        self, context_data: Dict[str, Any]
    ) -> OverlayGenerationContext:
        """Create OverlayGenerationContext from context_data dict using proper model objects."""

        # Use actual model objects when available, or create minimal model instances
        image_obj = context_data.get("image")
        if image_obj is None:
            # Create ImageModel instance with available data
            image_obj = ImageModel(
                id=context_data.get("image_id", 0),
                camera_id=context_data.get("camera_id", 0),
                timelapse_id=context_data.get("timelapse_id"),
                file_path=context_data.get("file_path", ""),
                day_number=context_data.get("day_number", 1),
                file_size=context_data.get("file_size"),
                corruption_details=context_data.get("corruption_details"),
                weather_temperature=context_data.get("weather_temperature"),
                weather_conditions=context_data.get("weather_conditions"),
                weather_icon=context_data.get("weather_icon"),
                weather_fetched_at=context_data.get("weather_fetched_at"),
                overlay_path=context_data.get("overlay_path"),
                overlay_updated_at=context_data.get("overlay_updated_at"),
                captured_at=context_data.get("timestamp", utc_now()),
                created_at=context_data.get("created_at", utc_now()),
            )

        timelapse_obj = context_data.get("timelapse")
        if timelapse_obj is None:
            # Create TimelapseModel instance with available data
            timelapse_obj = TimelapseModel(
                id=context_data.get("timelapse_id", 0),
                camera_id=context_data.get("camera_id", 0),
                name=context_data.get("timelapse_name", "Timelapse"),
                capture_interval_seconds=context_data.get("interval_seconds", 300),
                created_at=context_data.get("created_at", utc_now()),
                updated_at=context_data.get("updated_at", utc_now()),
            )

        return OverlayGenerationContext(
            image=image_obj,
            image_timestamp=context_data.get("timestamp", utc_now()),
            timelapse=timelapse_obj,
            frame_number=context_data.get("frame_number", 0),
            day_number=context_data.get("day_number", 1),
            temperature=context_data.get("temperature"),
            weather_conditions=context_data.get("weather_conditions"),
            temperature_unit=context_data.get("temperature_unit", "F"),
            settings_service=context_data.get("settings_service"),
            global_font=self.config.global_options.font,
            global_fill_color=getattr(
                self.config.global_options, "fillColor", "#FFFFFF"
            ),
            global_background_color=getattr(
                self.config.global_options, "background_color", "#000000"
            ),
        )

    def _render_text_overlay(
        self,
        draw: ImageDraw.ImageDraw,
        overlay_item: OverlayItem,
        text: str,
        x: int,
        y: int,
    ) -> None:
        """Render text overlay with background and styling."""

        # Get font using global cache
        font = get_font_fast(self.config.global_options.font, overlay_item.text_size)

        # Calculate text dimensions using cached font
        text_width, text_height = get_text_size_fast(
            text, self.config.global_options.font, overlay_item.text_size
        )

        # Adjust position based on text dimensions (for proper positioning)
        adjusted_x, adjusted_y = self._adjust_text_position(
            x, y, text_width, text_height
        )

        # Draw background if specified
        if overlay_item.background_opacity > 0 and overlay_item.background_color:
            self._draw_text_background(
                draw,
                adjusted_x,
                adjusted_y,
                text_width,
                text_height,
                overlay_item.background_color,
                overlay_item.background_opacity,
            )

        # Draw text
        text_color = overlay_item.text_color or "#FFFFFF"
        draw.text((adjusted_x, adjusted_y), text, font=font, fill=text_color)

    def _render_image_overlay(
        self, overlay_layer: Image.Image, overlay_item: OverlayItem, x: int, y: int
    ) -> None:
        """Render image overlay (watermark) at specified position."""

        if not overlay_item.image_url:
            return

        try:
            # Load overlay image
            overlay_image_path = Path(overlay_item.image_url)
            if not overlay_image_path.exists():
                logger.warning(f"Overlay image not found: {overlay_item.image_url}")
                return

            with Image.open(overlay_image_path) as img:
                # Convert to RGBA for transparency
                if img.mode != "RGBA":
                    img = img.convert("RGBA")

                # Scale image if needed
                if overlay_item.image_scale != 100:
                    scale_factor = overlay_item.image_scale / 100.0
                    new_size = (
                        int(img.width * scale_factor),
                        int(img.height * scale_factor),
                    )
                    img = img.resize(new_size, Image.Resampling.LANCZOS)

                # Adjust position for image dimensions
                adjusted_x, adjusted_y = self._adjust_image_position(x, y, img.size)

                # Paste image onto overlay layer
                overlay_layer.paste(img, (adjusted_x, adjusted_y), img)

        except Exception as e:
            logger.error("Failed to render image overlay", exception=e)

    def _calculate_position(
        self, position: OverlayGridPosition, image_size: Tuple[int, int]
    ) -> Tuple[int, int]:
        """Calculate x,y coordinates for grid position."""

        width, height = image_size
        margin_x = self.config.global_options.x_margin
        margin_y = self.config.global_options.y_margin

        # Define grid positions
        positions = {
            "topLeft": (margin_x, margin_y),
            "topCenter": (width // 2, margin_y),
            "topRight": (width - margin_x, margin_y),
            "centerLeft": (margin_x, height // 2),
            "center": (width // 2, height // 2),
            "centerRight": (width - margin_x, height // 2),
            "bottomLeft": (margin_x, height - margin_y),
            "bottomCenter": (width // 2, height - margin_y),
            "bottomRight": (width - margin_x, height - margin_y),
        }

        return positions.get(position, (margin_x, margin_y))

    def _adjust_text_position(
        self, x: int, y: int, text_width: int, text_height: int
    ) -> Tuple[int, int]:
        """Adjust text position based on anchor point (top-left, center, bottom-right, etc.)"""
        # For now, use simple top-left positioning
        # This could be enhanced to support different anchor points
        return x, y

    def _adjust_image_position(
        self, x: int, y: int, image_size: Tuple[int, int]
    ) -> Tuple[int, int]:
        """Adjust image position based on anchor point."""
        # For now, use simple top-left positioning
        # This could be enhanced to support different anchor points
        return x, y

    def _draw_text_background(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int,
        background_color: str,
        opacity: int,
    ) -> None:
        """Draw semi-transparent background rectangle for text."""

        try:
            # Parse color and apply opacity
            color = ImageColor.getrgb(background_color)
            alpha = int(255 * (opacity / 100.0))
            background_rgba = (*color, alpha)

            # Add padding
            padding = 4
            draw.rectangle(
                [x - padding, y - padding, x + width + padding, y + height + padding],
                fill=background_rgba,
            )

        except Exception as e:
            logger.warning("Failed to draw text background", exception=e)

    # Note: Font loading now handled by global font cache (font_cache.py)
    # Previous font loading methods removed in favor of global cache

    def _apply_global_opacity(self, overlay_layer: Image.Image) -> Image.Image:
        """Apply global opacity to the overlay layer."""

        if self.config.global_options.opacity >= 100:
            return overlay_layer

        # Create alpha mask
        alpha = int(255 * (self.config.global_options.opacity / 100.0))

        # Apply opacity
        overlay_array = overlay_layer.split()
        if len(overlay_array) == 4:  # RGBA
            alpha_channel = overlay_array[3].point(lambda p: int(p * alpha / 255))
            overlay_layer = Image.merge("RGBA", overlay_array[:3] + (alpha_channel,))

        return overlay_layer


def create_overlay_context(
    image_data: Dict[str, Any],
    timelapse_data: Dict[str, Any],
    weather_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create context data for overlay rendering.

    Args:
        image_data: Image metadata (timestamp, frame number, etc.)
        timelapse_data: Timelapse information (name, day number, etc.)
        weather_data: Optional weather data (temperature, conditions)

    Returns:
        Context dictionary for overlay rendering
    """
    context = {
        "timestamp": image_data.get("captured_at", utc_now()),
        "frame_number": image_data.get("frame_number", 0),
        "timelapse_name": timelapse_data.get("name", "Timelapse"),
        "day_number": timelapse_data.get("day_number", 1),
    }

    if weather_data:
        context.update(
            {
                "temperature": weather_data.get("temperature"),
                "weather_conditions": weather_data.get("conditions", ""),
            }
        )

    return context


def validate_overlay_configuration(config: OverlayConfiguration) -> bool:
    """
    Validate overlay configuration for rendering.

    Args:
        config: Overlay configuration to validate

    Returns:
        True if configuration is valid for rendering
    """
    try:
        # Check for at least one overlay position
        if not config.overlay_positions:
            return False

        # Validate each overlay item
        for position, overlay_item in config.overlay_positions.items():
            if not overlay_item.type:
                return False

            # Validate text size range
            if not (8 <= overlay_item.text_size <= 72):
                return False

            # Validate opacity range
            if not (0 <= overlay_item.background_opacity <= 100):
                return False

            # Validate image scale range
            if not (10 <= overlay_item.image_scale <= 500):
                return False

        # Validate global options
        if not (0 <= config.global_options.opacity <= 100):
            return False

        if not (0 <= config.global_options.x_margin <= 200):
            return False

        if not (0 <= config.global_options.y_margin <= 200):
            return False

        return True

    except Exception as e:
        logger.error("Failed to validate overlay configuration", exception=e)
        return False


async def render_overlay_with_caching(
    config: OverlayConfiguration,
    base_image_path: str,
    output_path: str,
    context_data: Dict[str, Any],
) -> bool:
    """
    High-performance overlay rendering with template caching.

    This is a convenience function that combines OverlayRenderer with template caching
    for optimal performance. Uses the global template cache to pre-render static
    elements and cache them for reuse across multiple frames.

    Args:
        config: Overlay configuration
        base_image_path: Path to base image (camera capture)
        output_path: Path where overlay image should be saved
        context_data: Dynamic data for overlay content

    Returns:
        True if overlay was successfully rendered and saved

    Performance Notes:
        - Static elements (watermarks, custom text) are pre-rendered and cached
        - Dynamic elements (timestamps, weather) are rendered per frame
        - Font loading is cached globally for 40-60% performance improvement
        - Template cache has 30-minute TTL for efficient memory usage
    """
    try:
        # Load base image
        with Image.open(base_image_path) as base_image:
            # Convert to RGBA if needed for transparency support
            if base_image.mode != "RGBA":
                base_image = base_image.convert("RGBA")

            # Get cached template for this configuration and image size
            template = await get_overlay_template(config, base_image.size)

            # Use template's fast rendering
            result_image = template.render_frame_fast(base_image, context_data)

            # Save as PNG to preserve transparency
            result_image.save(output_path, "PNG", optimize=True)

            logger.debug(
                f"Successfully rendered overlay with caching to {output_path}",
                emoji=LogEmoji.SUCCESS,
            )
            return True

    except Exception as e:
        logger.error("Failed to render overlay with caching", exception=e)
        # Fallback to standard rendering
        renderer = OverlayRenderer(config)
        return renderer.render_overlay(base_image_path, output_path, context_data)
