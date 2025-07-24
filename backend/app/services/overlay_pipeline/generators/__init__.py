# backend/app/services/overlay_pipeline/generators/__init__.py
"""
Overlay Generators - Modular content generation for different overlay types.

This module provides specialized generators for each overlay type, replacing
the monolithic if-elif chain approach with maintainable, testable modules.
"""

from .base_generator import BaseOverlayGenerator, OverlayGenerationContext, overlay_generator_registry
from .datetime_generator import DateTimeGenerator
from .text_generator import TextGenerator
from .sequence_generator import SequenceGenerator
from .weather_generator import WeatherGenerator
from .watermark_generator import WatermarkGenerator

# Register all generators
def register_all_generators():
    """Register all overlay generators with the global registry."""
    overlay_generator_registry.register(DateTimeGenerator())
    overlay_generator_registry.register(TextGenerator())
    overlay_generator_registry.register(SequenceGenerator())
    overlay_generator_registry.register(WeatherGenerator())
    overlay_generator_registry.register(WatermarkGenerator())

# Auto-register on import
register_all_generators()

__all__ = [
    "BaseOverlayGenerator",
    "OverlayGenerationContext",
    "overlay_generator_registry",
    "DateTimeGenerator",
    "TextGenerator", 
    "SequenceGenerator",
    "WeatherGenerator",
    "WatermarkGenerator",
]