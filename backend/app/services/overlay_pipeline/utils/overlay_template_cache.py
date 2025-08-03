# backend/app/services/overlay_pipeline/utils/overlay_template_cache.py
"""
Overlay Template Cache - Advanced performance optimization for overlay rendering.

Provides template-based overlay generation that pre-renders static elements and
caches them for reuse across multiple frames. Uses the existing cache infrastructure
for consistent caching behavior across the application.
"""

import hashlib
import json
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from PIL import Image, ImageDraw

from ....utils.time_utils import utc_now
from ....services.logger import get_service_logger
from ....enums import LoggerName

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE)

from ....models.overlay_model import OverlayConfiguration, OverlayItem
from ....utils.cache_manager import cached_response
from .font_cache import get_font_fast, get_text_size_fast
from ..constants import (
    OVERLAY_TYPE_WATERMARK,
    OVERLAY_TYPE_CUSTOM_TEXT,
    OVERLAY_TYPE_TIMELAPSE_NAME,
)


@dataclass
class OverlayTemplateStats:
    """Statistics for overlay template performance monitoring."""

    template_cache_hits: int = 0
    template_cache_misses: int = 0
    templates_generated: int = 0
    avg_generation_time_ms: float = 0.0

    @property
    def cache_hit_ratio(self) -> float:
        """Calculate template cache hit ratio as percentage."""
        total = self.template_cache_hits + self.template_cache_misses
        if total == 0:
            return 0.0
        return (self.template_cache_hits / total) * 100.0


class OverlayTemplate:
    """
    Pre-rendered overlay template for high-performance frame generation.

    Templates cache static elements like backgrounds, positions, and fonts
    while allowing dynamic content to be efficiently composited per frame.
    """

    def __init__(
        self,
        config: OverlayConfiguration,
        image_size: Tuple[int, int],
        template_id: str,
    ):
        """
        Initialize overlay template with configuration.

        Args:
            config: Overlay configuration
            image_size: Target image dimensions (width, height)
            template_id: Unique identifier for this template
        """
        self.config = config
        self.image_size = image_size
        self.template_id = template_id

        # Pre-computed data for performance
        self.static_positions = {}
        self.dynamic_positions = {}
        self.background_layer = None

        # Performance tracking
        self.render_count = 0
        self.total_render_time_ms = 0.0

        # Initialize template components
        self._analyze_overlay_elements()
        self._pre_render_static_elements()

    def _analyze_overlay_elements(self) -> None:
        """Analyze overlay configuration to separate static and dynamic elements."""

        for position, overlay_item in self.config.overlayPositions.items():
            if self._is_static_overlay(overlay_item):
                self.static_positions[position] = overlay_item
            else:
                self.dynamic_positions[position] = overlay_item

        logger.debug(
            f"Template {self.template_id}: {len(self.static_positions)} static, "
            f"{len(self.dynamic_positions)} dynamic overlays"
        )

    def _is_static_overlay(self, overlay_item: OverlayItem) -> bool:
        """Determine if an overlay item is static (doesn't change per frame)."""

        # Watermarks and custom text are static
        if overlay_item.type in [OVERLAY_TYPE_WATERMARK, OVERLAY_TYPE_CUSTOM_TEXT]:
            return True

        # Timelapse name is static within a timelapse
        if overlay_item.type == OVERLAY_TYPE_TIMELAPSE_NAME:
            return True

        # All other types (timestamps, weather, frame numbers) are dynamic
        return False

    def _pre_render_static_elements(self) -> None:
        """Pre-render static overlay elements into a background layer."""

        if not self.static_positions:
            logger.debug(
                f"Template {self.template_id}: No static elements to pre-render"
            )
            return

        # Create background layer for static elements
        self.background_layer = Image.new("RGBA", self.image_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(self.background_layer)

        # Render each static overlay
        for position, overlay_item in self.static_positions.items():
            try:
                x, y = self._calculate_position(position)

                if overlay_item.type == OVERLAY_TYPE_WATERMARK:
                    self._render_static_image_overlay(overlay_item, x, y)
                else:
                    self._render_static_text_overlay(draw, overlay_item, x, y)

            except Exception as e:
                logger.warning(
                    f"Failed to pre-render static overlay at {position}: {e}"
                )

        logger.debug(
            f"Template {self.template_id}: Pre-rendered {len(self.static_positions)} static elements"
        )

    def _calculate_position(self, position: str) -> Tuple[int, int]:
        """Calculate x,y coordinates for grid position."""

        width, height = self.image_size
        margin_x = self.config.globalOptions.xMargin
        margin_y = self.config.globalOptions.yMargin

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

    def _render_static_text_overlay(
        self, draw: ImageDraw.ImageDraw, overlay_item: OverlayItem, x: int, y: int
    ) -> None:
        """Render static text overlay (custom text, timelapse name)."""

        # Get overlay text content
        if overlay_item.type == OVERLAY_TYPE_CUSTOM_TEXT:
            text = overlay_item.customText or ""
        elif overlay_item.type == OVERLAY_TYPE_TIMELAPSE_NAME:
            text = "Timelapse"  # Placeholder - will be updated during frame rendering
        else:
            return

        if not text:
            return

        # Get font using global cache
        font = get_font_fast(self.config.globalOptions.font, overlay_item.textSize)

        # Calculate text dimensions
        text_width, text_height = get_text_size_fast(
            text, self.config.globalOptions.font, overlay_item.textSize
        )

        # Draw background if specified
        if overlay_item.backgroundOpacity > 0 and overlay_item.backgroundColor:
            self._draw_text_background(
                draw,
                x,
                y,
                text_width,
                text_height,
                overlay_item.backgroundColor,
                overlay_item.backgroundOpacity,
            )

        # Draw text
        text_color = overlay_item.textColor or "#FFFFFF"
        draw.text((x, y), text, font=font, fill=text_color)

    def _render_static_image_overlay(
        self, overlay_item: OverlayItem, x: int, y: int
    ) -> None:
        """Render static image overlay (watermarks)."""

        if not overlay_item.imageUrl:
            return

        try:
            # Ensure background_layer is initialized
            if self.background_layer is None:
                self.background_layer = Image.new("RGBA", self.image_size, (0, 0, 0, 0))

            # Load overlay image
            overlay_image_path = Path(overlay_item.imageUrl)
            if not overlay_image_path.exists():
                logger.warning(f"Overlay image not found: {overlay_item.imageUrl}")
                return

            with Image.open(overlay_image_path) as img:
                # Convert to RGBA for transparency
                if img.mode != "RGBA":
                    img = img.convert("RGBA")

                # Scale image if needed
                if overlay_item.imageScale != 100:
                    scale_factor = overlay_item.imageScale / 100.0
                    new_size = (
                        int(img.width * scale_factor),
                        int(img.height * scale_factor),
                    )
                    img = img.resize(new_size, Image.Resampling.LANCZOS)

                # Paste image onto background layer
                self.background_layer.paste(img, (x, y), img)

        except Exception as e:
            logger.error(f"Failed to render static image overlay: {e}")

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
            from PIL import ImageColor

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
            logger.warning(f"Failed to draw text background: {e}")

    def render_frame_fast(
        self, base_image: Image.Image, context_data: Dict[str, Any]
    ) -> Image.Image:
        """
        Fast frame rendering using pre-computed template.

        Args:
            base_image: Base camera image
            context_data: Dynamic overlay context (timestamps, weather, etc.)

        Returns:
            Composited image with overlays applied
        """
        import time

        start_time = time.time()

        try:
            # Start with base image
            if base_image.mode != "RGBA":
                result_image = base_image.convert("RGBA")
            else:
                result_image = base_image.copy()

            # Apply pre-rendered static background if available
            if self.background_layer:
                result_image = Image.alpha_composite(
                    result_image, self.background_layer
                )

            # Render dynamic overlays
            if self.dynamic_positions:
                dynamic_layer = Image.new("RGBA", self.image_size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(dynamic_layer)

                for position, overlay_item in self.dynamic_positions.items():
                    self._render_dynamic_overlay(
                        draw, overlay_item, position, context_data
                    )

                # Composite dynamic layer
                result_image = Image.alpha_composite(result_image, dynamic_layer)

            # Apply global opacity if needed
            if self.config.globalOptions.opacity < 100:
                result_image = self._apply_global_opacity(result_image)

            # Update performance tracking
            render_time_ms = (time.time() - start_time) * 1000
            self.render_count += 1
            self.total_render_time_ms += render_time_ms

            return result_image

        except Exception as e:
            logger.error(f"Template {self.template_id} fast rendering failed: {e}")
            raise

    def _render_dynamic_overlay(
        self,
        draw: ImageDraw.ImageDraw,
        overlay_item: OverlayItem,
        position: str,
        context_data: Dict[str, Any],
    ) -> None:
        """Render dynamic overlay content that changes per frame."""

        # Get dynamic content text
        content_text = self._get_dynamic_content(overlay_item, context_data)
        if not content_text:
            return

        # Calculate position
        x, y = self._calculate_position(position)

        # Get font using global cache
        font = get_font_fast(self.config.globalOptions.font, overlay_item.textSize)

        # Calculate text dimensions
        text_width, text_height = get_text_size_fast(
            content_text, self.config.globalOptions.font, overlay_item.textSize
        )

        # Draw background if specified
        if overlay_item.backgroundOpacity > 0 and overlay_item.backgroundColor:
            self._draw_text_background(
                draw,
                x,
                y,
                text_width,
                text_height,
                overlay_item.backgroundColor,
                overlay_item.backgroundOpacity,
            )

        # Draw text
        text_color = overlay_item.textColor or "#FFFFFF"
        draw.text((x, y), content_text, font=font, fill=text_color)

    def _get_dynamic_content(
        self, overlay_item: OverlayItem, context_data: Dict[str, Any]
    ) -> str:
        """Generate dynamic content text based on overlay type and context."""

        from ..constants import (
            OVERLAY_TYPE_DATE,
            OVERLAY_TYPE_DATE_TIME,
            OVERLAY_TYPE_TIME,
            OVERLAY_TYPE_FRAME_NUMBER,
            OVERLAY_TYPE_DAY_NUMBER,
            OVERLAY_TYPE_TEMPERATURE,
            OVERLAY_TYPE_WEATHER_CONDITIONS,
            OVERLAY_TYPE_WEATHER_TEMP_CONDITIONS,
        )

        overlay_type = overlay_item.type

        if overlay_type == OVERLAY_TYPE_DATE:
            timestamp = context_data.get("timestamp", utc_now())
            return timestamp.strftime(overlay_item.dateFormat or "%m/%d/%Y")

        elif overlay_type == OVERLAY_TYPE_TIME:
            timestamp = context_data.get("timestamp", utc_now())
            return timestamp.strftime("%H:%M:%S")

        elif overlay_type == OVERLAY_TYPE_DATE_TIME:
            timestamp = context_data.get("timestamp", utc_now())
            return timestamp.strftime(overlay_item.dateFormat or "%m/%d/%Y %H:%M:%S")

        elif overlay_type == OVERLAY_TYPE_FRAME_NUMBER:
            frame_number = context_data.get("frame_number", 0)
            return f"Frame {frame_number}"

        elif overlay_type == OVERLAY_TYPE_DAY_NUMBER:
            day_number = context_data.get("day_number", 1)
            return f"Day {day_number}"

        elif overlay_type == OVERLAY_TYPE_TEMPERATURE:
            temperature = context_data.get("temperature")
            if temperature is not None:
                return f"{temperature:.1f}°C"
            return ""

        elif overlay_type == OVERLAY_TYPE_WEATHER_CONDITIONS:
            conditions = context_data.get("weather_conditions", "")
            return conditions

        elif overlay_type == OVERLAY_TYPE_WEATHER_TEMP_CONDITIONS:
            temperature = context_data.get("temperature")
            conditions = context_data.get("weather_conditions", "")
            if temperature is not None and conditions:
                return f"{temperature:.1f}°C, {conditions}"
            elif temperature is not None:
                return f"{temperature:.1f}°C"
            elif conditions:
                return conditions
            return ""

        return ""

    def _apply_global_opacity(self, image: Image.Image) -> Image.Image:
        """Apply global opacity to the overlay layers."""

        if self.config.globalOptions.opacity >= 100:
            return image

        # Create alpha mask
        alpha = int(255 * (self.config.globalOptions.opacity / 100.0))

        # Apply opacity
        image_array = image.split()
        if len(image_array) == 4:  # RGBA
            alpha_channel = image_array[3].point(lambda p: int(p * alpha / 255))
            image = Image.merge("RGBA", image_array[:3] + (alpha_channel,))

        return image

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for this template."""

        avg_render_time = 0.0
        if self.render_count > 0:
            avg_render_time = self.total_render_time_ms / self.render_count

        return {
            "template_id": self.template_id,
            "render_count": self.render_count,
            "avg_render_time_ms": round(avg_render_time, 2),
            "total_render_time_ms": round(self.total_render_time_ms, 2),
            "static_overlays": len(self.static_positions),
            "dynamic_overlays": len(self.dynamic_positions),
            "has_background_layer": self.background_layer is not None,
        }


class OverlayTemplateManager:
    """
    Manager for overlay templates with caching integration.

    Uses the existing cache infrastructure to store and retrieve templates
    efficiently across multiple overlay generation requests.
    """

    def __init__(self):
        """Initialize template manager."""
        self.stats = OverlayTemplateStats()

    @cached_response(ttl_seconds=1800, key_prefix="overlay_template")  # 30 minutes TTL
    async def get_template(
        self, config: OverlayConfiguration, image_size: Tuple[int, int]
    ) -> OverlayTemplate:
        """
        Get or create overlay template with caching.

        Args:
            config: Overlay configuration
            image_size: Target image dimensions

        Returns:
            Cached or newly created overlay template
        """
        # Generate template ID based on config and size
        template_id = self._generate_template_id(config, image_size)

        # Create new template (will be cached by decorator)
        self.stats.templates_generated += 1
        self.stats.template_cache_misses += 1

        logger.debug(f"Creating new overlay template: {template_id}")
        return OverlayTemplate(config, image_size, template_id)

    def _generate_template_id(
        self, config: OverlayConfiguration, image_size: Tuple[int, int]
    ) -> str:
        """Generate unique template ID based on configuration and image size."""

        # Create hashable representation of config
        config_dict = {
            "overlayPositions": {
                pos: {
                    "type": item.type,
                    "textSize": item.textSize,
                    "textColor": item.textColor,
                    "backgroundColor": item.backgroundColor,
                    "backgroundOpacity": item.backgroundOpacity,
                    "imageUrl": item.imageUrl,
                    "imageScale": item.imageScale,
                    "customText": item.customText,
                    "dateFormat": item.dateFormat,
                }
                for pos, item in config.overlayPositions.items()
            },
            "globalOptions": {
                "opacity": config.globalOptions.opacity,
                "font": config.globalOptions.font,
                "xMargin": config.globalOptions.xMargin,
                "yMargin": config.globalOptions.yMargin,
            },
            "imageSize": image_size,
        }

        # Generate stable hash
        config_json = json.dumps(config_dict, sort_keys=True)
        return hashlib.md5(config_json.encode()).hexdigest()

    def get_cache_stats(self) -> OverlayTemplateStats:
        """Get template cache performance statistics."""
        return self.stats


# Global template manager instance
template_manager = OverlayTemplateManager()


async def get_overlay_template(
    config: OverlayConfiguration, image_size: Tuple[int, int]
) -> OverlayTemplate:
    """
    Convenience function to get overlay template with caching.

    Args:
        config: Overlay configuration
        image_size: Target image dimensions

    Returns:
        Cached or newly created overlay template
    """
    return await template_manager.get_template(config, image_size)
