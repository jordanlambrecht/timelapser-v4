# backend/app/services/overlay_pipeline/generators/base_generator.py
"""
Base Overlay Generator - Abstract interface for all overlay content generators.

Defines the contract that all overlay generators must implement and provides
shared utilities for content generation.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Union, Optional
from datetime import datetime
from PIL import Image as PILImage
from dataclasses import dataclass

from ....models.overlay_model import OverlayItem, OverlayType
from ....models.image_model import Image
from ....models.timelapse_model import Timelapse as TimelapseModel


@dataclass
class OverlayGenerationContext:
    """
    Context information available to overlay generators.

    Provides all the data generators need to create appropriate content
    including image metadata, timelapse information, and weather data.
    """

    # Image information
    image: Image
    image_timestamp: datetime

    # Timelapse information
    timelapse: TimelapseModel
    frame_number: int
    day_number: int

    # Weather information (optional)
    temperature: Optional[float] = None
    weather_conditions: Optional[str] = None
    temperature_unit: str = "F"

    # Settings service for timezone and other settings
    settings_service: Optional[Any] = None

    # Global styling context
    global_font: str = "Arial"
    global_fill_color: str = "#FFFFFF"
    global_background_color: str = "#000000"

    @property
    def is_static_content(self) -> bool:
        """Check if this context represents static content that can be cached."""
        # For now, we'll determine this at the generator level
        # This property can be used for future static detection logic
        return False


class BaseOverlayGenerator(ABC):
    """
    Abstract base class for all overlay content generators.

    Each overlay type (date, weather, watermark, etc.) should have its own
    generator class that inherits from this base class.
    """

    @property
    @abstractmethod
    def supported_types(self) -> list[OverlayType]:
        """Return list of overlay types this generator supports."""
        pass

    @property
    @abstractmethod
    def is_static(self) -> bool:
        """
        Whether this generator produces static content that can be cached.

        Static content doesn't change between frames (e.g., watermarks, custom text).
        Dynamic content changes per frame (e.g., timestamps, frame numbers).
        """
        pass

    @abstractmethod
    def generate_content(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
    ) -> Union[str, PILImage.Image]:
        """
        Generate overlay content for the given item and context.

        Args:
            overlay_item: Configuration for the overlay to generate
            context: Runtime context with image/timelapse/weather data

        Returns:
            Either text content (str) or image content (PIL.Image)

        Raises:
            ValueError: If overlay_item type is not supported by this generator
            RuntimeError: If content generation fails
        """
        pass

    def supports_type(self, overlay_type: OverlayType) -> bool:
        """Check if this generator supports the given overlay type."""
        return overlay_type in self.supported_types

    def validate_overlay_item(self, overlay_item: OverlayItem) -> None:
        """
        Validate that overlay item has required properties for this generator.

        Args:
            overlay_item: Overlay item to validate

        Raises:
            ValueError: If overlay item is missing required properties
        """
        if not self.supports_type(overlay_item.type):
            raise ValueError(
                f"Generator {self.__class__.__name__} does not support type {overlay_item.type}"
            )

    def get_effective_text_color(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
    ) -> str:
        """Get effective text color, preferring item-specific over global."""
        return overlay_item.textColor or context.global_fill_color

    def get_effective_background_color(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
    ) -> str:
        """Get effective background color, preferring item-specific over global."""
        return overlay_item.backgroundColor or context.global_background_color

    def should_render_background(self, overlay_item: OverlayItem) -> bool:
        """Check if background should be rendered for this overlay item."""
        # Use item-specific setting if available, otherwise check if backgroundOpacity > 0
        if overlay_item.enableBackground is not None:
            return overlay_item.enableBackground
        return overlay_item.backgroundOpacity > 0


class OverlayGeneratorRegistry:
    """
    Registry for managing overlay generators.

    Provides a central location to register generators and find the appropriate
    generator for a given overlay type.
    """

    def __init__(self):
        self._generators: Dict[OverlayType, BaseOverlayGenerator] = {}

    def register(self, generator: BaseOverlayGenerator) -> None:
        """Register a generator for its supported overlay types."""
        for overlay_type in generator.supported_types:
            if overlay_type in self._generators:
                raise ValueError(
                    f"Generator for type {overlay_type} already registered"
                )
            self._generators[overlay_type] = generator

    def get_generator(self, overlay_type: OverlayType) -> BaseOverlayGenerator:
        """Get the generator for the given overlay type."""
        if overlay_type not in self._generators:
            raise ValueError(f"No generator registered for overlay type {overlay_type}")
        return self._generators[overlay_type]

    def has_generator(self, overlay_type: OverlayType) -> bool:
        """Check if a generator is registered for the given overlay type."""
        return overlay_type in self._generators

    def get_static_generators(self) -> list[BaseOverlayGenerator]:
        """Get all generators that produce static content."""
        return [gen for gen in self._generators.values() if gen.is_static]

    def get_dynamic_generators(self) -> list[BaseOverlayGenerator]:
        """Get all generators that produce dynamic content."""
        return [gen for gen in self._generators.values() if not gen.is_static]


# Global registry instance
overlay_generator_registry = OverlayGeneratorRegistry()
