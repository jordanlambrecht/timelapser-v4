# backend/app/services/overlay_pipeline/utils/__init__.py
"""
Overlay Utils Module

Contains all overlay utilities including overlay rendering, font caching, template caching, and constants.
"""

from .overlay_utils import OverlayRenderer, create_overlay_context, validate_overlay_configuration
from .overlay_helpers import OverlaySettingsResolver
from .overlay_template_cache import OverlayTemplateManager, OverlayTemplate, get_overlay_template
from .font_cache import GlobalFontCache, get_font_fast, get_text_size_fast
from .constants import *

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
]