# backend/app/services/overlay_pipeline/generators/__init__.py
"""
Overlay Generators - Modular content generation for different overlay types.

This module provides specialized generators for each overlay type, replacing
the monolithic if-elif chain approach with maintainable, testable modules.
"""

from .base_generator import (
    BaseOverlayGenerator,
    OverlayGenerationContext,
    overlay_generator_registry,
)
from .datetime_generator import DateTimeGenerator
from .sequence_generator import SequenceGenerator
from .text_generator import TextGenerator
from .watermark_generator import WatermarkOverlayGenerator
from .weather_generator import WeatherGenerator


# Register all generators
def register_all_generators():
    """Register all overlay generators with the global registry."""
    overlay_generator_registry.register(DateTimeGenerator())
    overlay_generator_registry.register(TextGenerator())
    overlay_generator_registry.register(SequenceGenerator())
    overlay_generator_registry.register(WeatherGenerator())
    overlay_generator_registry.register(WatermarkOverlayGenerator())


# Auto-register on import
register_all_generators()


def get_available_generators():
    """Get list of all available generator classes."""
    return [
        DateTimeGenerator,
        TextGenerator,
        SequenceGenerator,
        WeatherGenerator,
        WatermarkOverlayGenerator,
    ]


__all__ = [
    "BaseOverlayGenerator",
    "OverlayGenerationContext",
    "overlay_generator_registry",
    "DateTimeGenerator",
    "TextGenerator",
    "SequenceGenerator",
    "WeatherGenerator",
    "WatermarkOverlayGenerator",
    "get_available_generators",
]
