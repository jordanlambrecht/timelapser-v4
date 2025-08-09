# backend/app/services/overlay_pipeline/generators/watermark_generator.py
"""
Watermark Overlay Generator - Adds watermarks/logos to video frames.

Handles image-based overlays with support for:
- Multiple image formats (PNG, JPEG, GIF, WebP)
- Scaling and rotation transformations
- Visual effects (blur, shadow, opacity)
- Flexible positioning system
"""

from typing import List, Union

from PIL import Image as PILImage

from ....enums import LoggerName, LogSource
from ....models.overlay_model import OverlayItem
from ....services.logger import get_service_logger
from ..utils.image_path_utils import load_image_from_path
from ..utils.image_utils import (
    apply_blur,
    apply_drop_shadow,
    apply_opacity,
    ensure_rgba_mode,
    rotate_image,
    scale_image,
)
from .base_generator import BaseOverlayGenerator, OverlayGenerationContext

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)


class WatermarkOverlayGenerator(BaseOverlayGenerator):
    """
    Generator for watermark overlays with image processing capabilities.

    Supports various image formats and processing effects including:
    - Scaling and rotation
    - Blur and drop shadow effects
    - Opacity control (applied last for proper blending)
    """

    @property
    def generator_type(self) -> str:
        """Return the primary generator type."""
        return "watermark"

    @property
    def display_name(self) -> str:
        """Human-readable name for this generator."""
        return "Watermark Overlay"

    @property
    def description(self) -> str:
        """Description of what this generator does."""
        return "Adds image-based watermarks with scaling, rotation, and visual effects"

    @property
    def supported_types(self) -> List[str]:
        """Return list of supported overlay types."""
        return ["watermark"]

    @property
    def is_static(self) -> bool:
        """Watermarks are static content."""
        return True

    def generate_content(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
    ) -> Union[str, PILImage.Image]:
        """
        Generate watermark overlay content for the frame.

        Args:
            overlay_item: Overlay configuration
            context: Generation context with image and timelapse data

        Returns:
            Processed watermark image

        Raises:
            ValueError: If overlay type is not supported or image cannot be loaded
            RuntimeError: If content generation fails
        """
        logger.debug(f"🖼️ Generating watermark overlay for frame {context.frame_number}")

        try:
            # Validate overlay item
            self.validate_overlay_item(overlay_item)

            # Load base image from settings
            image_url = overlay_item.settings.get(
                "imageUrl"
            ) or overlay_item.settings.get("image_path")
            if not image_url:
                logger.error("❌ No image URL provided for watermark")
                raise ValueError("Image URL is required for watermark overlay")

            logger.debug(f"📁 Loading watermark image: {image_url}")
            watermark = load_image_from_path(image_url)

            # Ensure image is in RGBA mode for proper transparency handling
            watermark = ensure_rgba_mode(watermark)

            # Apply transformations in correct order
            # 1. Scale first (affects all subsequent operations)
            scale_factor = overlay_item.settings.get("imageScale", 100) / 100.0
            if scale_factor != 1.0:
                logger.debug(f"🔍 Applying scaling transformation: {scale_factor}")
                watermark = scale_image(watermark, scale_factor)

            # 2. Rotate (affects blur and shadow calculations)
            rotation = overlay_item.settings.get("imageRotation", 0)
            if rotation != 0:
                logger.debug(f"🔄 Applying rotation transformation: {rotation}°")
                watermark = rotate_image(watermark, rotation)

            # 3. Apply blur effect (before shadow for better visual result)
            blur_radius = overlay_item.settings.get("blurRadius", 0)
            if blur_radius > 0:
                logger.debug(f"🌀 Applying blur effect: {blur_radius}px")
                watermark = apply_blur(watermark, blur_radius)

            # 4. Apply drop shadow (before opacity for proper shadow visibility)
            shadow_settings = overlay_item.settings.get("dropShadow")
            if shadow_settings and shadow_settings.get("enabled", False):
                logger.debug("🌑 Applying drop shadow effect")
                watermark = apply_drop_shadow(watermark, shadow_settings)

            # 5. Apply opacity LAST (ensures proper blending with background)
            opacity = overlay_item.settings.get("imageOpacity", 100) / 100.0
            if opacity < 1.0:
                logger.debug(f"🎭 Applying opacity effect: {opacity}")
                watermark = apply_opacity(watermark, opacity)

            logger.debug("✅ Watermark overlay generated successfully")
            return watermark

        except Exception as e:
            logger.error(f"❌ Failed to generate watermark overlay: {e}")
            raise RuntimeError(f"Failed to generate watermark content: {e}")

    def validate_overlay_item(self, overlay_item: OverlayItem) -> None:
        """
        Validate watermark overlay item configuration.

        Args:
            overlay_item: Overlay configuration to validate

        Raises:
            ValueError: If overlay item is invalid for watermark generation
        """
        logger.debug("🔍 Validating watermark overlay item")

        # Call parent validation first
        super().validate_overlay_item(overlay_item)

        # Validate image URL/path exists
        image_url = overlay_item.settings.get("imageUrl") or overlay_item.settings.get(
            "image_path"
        )
        if not image_url or not isinstance(image_url, str):
            raise ValueError(
                "Watermark overlay requires 'imageUrl' or 'image_path' in settings"
            )

        # Validate optional parameters
        scale = overlay_item.settings.get("imageScale", 100)
        if not isinstance(scale, (int, float)) or scale <= 0:
            raise ValueError("imageScale must be a positive number")

        rotation = overlay_item.settings.get("imageRotation", 0)
        if not isinstance(rotation, (int, float)):
            raise ValueError("imageRotation must be a number")

        opacity = overlay_item.settings.get("imageOpacity", 100)
        if not isinstance(opacity, (int, float)) or not (0 <= opacity <= 100):
            raise ValueError("imageOpacity must be between 0 and 100")

        blur_radius = overlay_item.settings.get("blurRadius", 0)
        if not isinstance(blur_radius, (int, float)) or blur_radius < 0:
            raise ValueError("blurRadius must be non-negative")

        logger.debug("✅ Watermark overlay item validation passed")
