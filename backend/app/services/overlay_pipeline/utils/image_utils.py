# backend/app/services/overlay_pipeline/utils/image_utils.py
"""
Image Utilities - Reusable image processing functions for overlay generation.

Provides common image operations like scaling, rotation, blur, opacity, and effects
that can be used across different overlay generators.
"""

from typing import Any, Dict

from PIL import Image as PILImage, ImageFilter

from ....enums import LoggerName, LogSource
from ....services.logger import get_service_logger


def get_logger():
    """Get logger safely for testing environments."""
    try:
        return get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)
    except RuntimeError:
        # Logger not initialized - create a null logger for tests
        import logging

        logger = logging.getLogger("test_image_utils")
        logger.addHandler(logging.NullHandler())
        return logger


def safe_log(level: str, message: str) -> None:
    """Safe logging that handles uninitialized logger for tests."""
    try:
        logger = get_logger()
        getattr(logger, level)(message)
    except Exception:
        # Silently fail in test environments
        pass


def scale_image(image: PILImage.Image, scale_factor: float) -> PILImage.Image:
    """
    Scale image by the specified factor.

    Args:
        image: PIL Image to scale
        scale_factor: Scale factor (1.0 = original size)

    Returns:
        Scaled PIL Image
    """
    safe_log(
        "debug", f"🔧 Scaling image by factor: {scale_factor} (original: {image.size})"
    )

    if scale_factor == 1.0:
        safe_log("debug", "No scaling needed, returning original")
        return image

    # Calculate new dimensions
    original_width, original_height = image.size
    new_width = int(original_width * scale_factor)
    new_height = int(original_height * scale_factor)

    safe_log("debug", f"🔢 Calculated new size: {new_width}x{new_height}")

    # Ensure minimum size
    if new_width < 1:
        new_width = 1
        safe_log("debug", "Adjusted width to minimum (1 pixel)")
    if new_height < 1:
        new_height = 1
        safe_log("debug", "Adjusted height to minimum (1 pixel)")

    # Scale using high-quality resampling
    safe_log("debug", "Applying LANCZOS resampling for high quality")
    scaled_image = image.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

    safe_log("debug", f"✅ Image scaled successfully to {scaled_image.size}")
    return scaled_image


def rotate_image(image: PILImage.Image, rotation_degrees: float) -> PILImage.Image:
    """
    Rotate image by specified degrees.

    Args:
        image: PIL Image to rotate
        rotation_degrees: Rotation angle in degrees (positive = clockwise)

    Returns:
        Rotated PIL Image with transparent background
    """
    safe_log("debug", f"🔄 Rotating image: {rotation_degrees} degrees")

    if rotation_degrees == 0:
        safe_log("debug", "No rotation needed")
        return image

    # Ensure image has alpha channel for transparency
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    # Rotate with transparent background
    rotated_image = image.rotate(
        -rotation_degrees,  # PIL rotates counter-clockwise
        expand=True,  # Expand canvas to fit rotated image
        fillcolor=(0, 0, 0, 0),  # Transparent background
    )

    safe_log("debug", f"✅ Image rotated successfully: {rotated_image.size}")
    return rotated_image


def apply_blur(image: PILImage.Image, blur_radius: float) -> PILImage.Image:
    """
    Apply Gaussian blur to image.

    Args:
        image: PIL Image to blur
        blur_radius: Blur radius in pixels

    Returns:
        Blurred PIL Image
    """
    safe_log("debug", f"💫 Applying blur with radius: {blur_radius}px")

    if blur_radius <= 0:
        safe_log("debug", "No blur needed")
        return image

    # Apply Gaussian blur
    blurred_image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    safe_log("debug", "✅ Blur applied successfully")
    return blurred_image


def apply_opacity(image: PILImage.Image, opacity: float) -> PILImage.Image:
    """
    Apply opacity to image by modifying alpha channel.

    Args:
        image: PIL Image to apply opacity to
        opacity: Opacity value (0.0 = transparent, 1.0 = opaque)

    Returns:
        PIL Image with applied opacity
    """
    safe_log("debug", f"🎨 Applying opacity: {opacity}")

    if opacity >= 1.0:
        safe_log("debug", "No opacity adjustment needed")
        return image

    # Ensure image has alpha channel
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    # Apply opacity to alpha channel
    r, g, b, a = image.split()
    a = a.point(lambda p: int(p * opacity))

    # Reconstruct image with new alpha
    result_image = PILImage.merge("RGBA", (r, g, b, a))

    safe_log("debug", f"✅ Opacity applied successfully: {opacity}")
    return result_image


def apply_drop_shadow(
    image: PILImage.Image, shadow_settings: Dict[str, Any]
) -> PILImage.Image:
    """
    Apply drop shadow effect to image.

    Args:
        image: PIL Image to add shadow to
        shadow_settings: Shadow configuration dict with keys:
            - offset_x: Horizontal shadow offset (default: 3)
            - offset_y: Vertical shadow offset (default: 3)
            - blur: Shadow blur radius (default: 2)
            - color: Shadow color as hex (default: "#000000")
            - opacity: Shadow opacity 0-1 (default: 0.5)

    Returns:
        PIL Image with drop shadow effect
    """
    safe_log("debug", "🌑 Creating drop shadow effect")

    # Extract shadow settings with defaults
    offset_x = shadow_settings.get("offset_x", 3)
    offset_y = shadow_settings.get("offset_y", 3)
    blur_radius = shadow_settings.get("blur", 2)
    shadow_color = shadow_settings.get("color", "#000000")
    shadow_opacity = shadow_settings.get("opacity", 0.5)

    safe_log(
        "debug",
        f"🎛️ Shadow settings: offset=({offset_x}, {offset_y}), "
        f"blur={blur_radius}px, color={shadow_color}, opacity={shadow_opacity}",
    )

    # Ensure image has alpha channel
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    # Calculate expanded canvas size
    shadow_padding = max(abs(offset_x), abs(offset_y)) + blur_radius + 5
    new_width = image.width + (shadow_padding * 2)
    new_height = image.height + (shadow_padding * 2)

    # Create shadow canvas
    shadow_canvas = PILImage.new("RGBA", (new_width, new_height), (0, 0, 0, 0))

    # Convert hex color to RGB
    if shadow_color.startswith("#"):
        shadow_rgb = tuple(
            int(shadow_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)
        )
    else:
        shadow_rgb = (0, 0, 0)  # Default to black

    shadow_alpha = int(255 * shadow_opacity)

    # Create shadow mask from original image alpha
    shadow_mask = PILImage.new("RGBA", image.size, shadow_rgb + (shadow_alpha,))
    shadow_mask.putalpha(image.split()[3])  # Use original alpha as mask

    # Position shadow on canvas
    shadow_x = shadow_padding + offset_x
    shadow_y = shadow_padding + offset_y
    shadow_canvas.paste(shadow_mask, (shadow_x, shadow_y), shadow_mask)

    # Apply blur to shadow
    if blur_radius > 0:
        shadow_canvas = shadow_canvas.filter(
            ImageFilter.GaussianBlur(radius=blur_radius)
        )

    # Position original image on top
    image_x = shadow_padding
    image_y = shadow_padding
    shadow_canvas.paste(image, (image_x, image_y), image)

    safe_log("debug", f"✅ Drop shadow applied successfully: {shadow_canvas.size}")
    return shadow_canvas


def ensure_rgba_mode(image: PILImage.Image) -> PILImage.Image:
    """
    Ensure image is in RGBA mode for proper transparency handling.

    Args:
        image: Source image

    Returns:
        Image in RGBA mode
    """
    if image.mode != "RGBA":
        safe_log("debug", f"🔄 Converting image from {image.mode} to RGBA mode")
        image = image.convert("RGBA")
    else:
        safe_log("debug", "✅ Image already in RGBA mode")
    return image


def validate_image_format(image: PILImage.Image) -> None:
    """
    Validate that the image format is supported.

    Args:
        image: PIL Image to validate

    Raises:
        ValueError: If format is not supported
    """
    supported_formats = {"PNG", "JPEG", "JPG", "GIF", "WEBP"}

    if image.format not in supported_formats:
        safe_log("error", f"❌ Unsupported image format: {image.format}")
        raise ValueError(
            f"Unsupported image format: {image.format}. "
            f"Supported formats: {', '.join(supported_formats)}"
        )

    safe_log("debug", f"✅ Image format validated: {image.format}")
