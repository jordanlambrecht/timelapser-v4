# backend/app/services/overlay_pipeline/utils/__init__.py
"""
Overlay Utils Module

Contains all overlay utilities including overlay rendering, font caching, template caching, and constants.
"""

from .font_cache import GlobalFontCache, get_font_fast, get_text_size_fast
from .image_path_utils import load_image_from_path
from .image_utils import (
    apply_blur,
    apply_drop_shadow,
    apply_opacity,
    ensure_rgba_mode,
    rotate_image,
    scale_image,
    validate_image_format,
)
from .overlay_helpers import OverlaySettingsResolver
from .overlay_template_cache import (
    OverlayTemplate,
    OverlayTemplateManager,
    get_overlay_template,
)
from .overlay_utils import (
    OverlayRenderer,
    create_overlay_context,
    validate_overlay_configuration,
)

# Star import removed due to unused imports

__all__ = [
    "OverlayRenderer",
    "create_overlay_context",
    "validate_overlay_configuration",
    "OverlaySettingsResolver",
    "OverlayTemplateManager",
    "OverlayTemplate",
    "get_overlay_template",
    "GlobalFontCache",
    "get_font_fast",
    "get_text_size_fast",
    # Image processing utilities
    "load_image_from_path",
    "apply_blur",
    "apply_drop_shadow",
    "apply_opacity",
    "ensure_rgba_mode",
    "rotate_image",
    "scale_image",
    "validate_image_format",
]
