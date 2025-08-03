# backend/app/services/overlay_pipeline/caching/template_cache.py
"""
Static Overlay Template Cache - Caches static overlay elements for performance optimization.

This module implements template caching for static overlay content (watermarks, custom text,
timelapse names) to avoid regenerating them for every frame. Provides significant performance
improvements for long timelapses.
"""

import asyncio
import hashlib
import time
from typing import Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
import json
import threading
from PIL import Image

from ..utils.overlay_utils import OverlayRenderer
from ....services.logger import get_service_logger
from ....enums import LoggerName

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE)

from ....models.overlay_model import (
    OverlayConfiguration,
    OverlayItem,
    OverlayGridPosition,
)
from ..generators import overlay_generator_registry, OverlayGenerationContext


@dataclass
class CacheStatistics:
    """Statistics for cache performance monitoring."""

    cache_hits: int = 0
    cache_misses: int = 0
    template_generations: int = 0
    cache_invalidations: int = 0
    memory_usage_bytes: int = 0
    last_cleanup: float = field(default_factory=time.time)

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total_requests = self.cache_hits + self.cache_misses
        if total_requests == 0:
            return 0.0
        return (self.cache_hits / total_requests) * 100


@dataclass
class StaticOverlayTemplate:
    """
    Cached static overlay template.

    Contains pre-rendered static overlay elements that don't change between frames,
    along with metadata for cache management.
    """

    config_hash: str
    template_image: Image.Image
    creation_time: float
    last_access_time: float
    base_image_dimensions: Tuple[int, int]
    static_overlay_positions: Set[OverlayGridPosition]
    memory_size_bytes: int

    def update_access_time(self) -> None:
        """Update last access time for LRU cache management."""
        self.last_access_time = time.time()

    def is_valid_for_dimensions(self, dimensions: Tuple[int, int]) -> bool:
        """Check if template is valid for the given base image dimensions."""
        return self.base_image_dimensions == dimensions

    def get_age_seconds(self) -> float:
        """Get template age in seconds."""
        return time.time() - self.creation_time


class StaticOverlayTemplateCache:
    """
    Cache manager for static overlay templates.

    Provides intelligent caching of static overlay content to improve performance
    for long timelapses with repetitive static elements.
    """

    def __init__(self, max_cache_size_mb: int = 100, max_template_age_hours: int = 24):
        """
        Initialize template cache.

        Args:
            max_cache_size_mb: Maximum cache size in megabytes
            max_template_age_hours: Maximum template age before expiration
        """
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        self.max_template_age_seconds = max_template_age_hours * 3600

        self._cache: Dict[str, StaticOverlayTemplate] = {}
        self._lock = threading.RLock()
        self._stats = CacheStatistics()

        logger.info(
            f"StaticOverlayTemplateCache initialized: max_size={max_cache_size_mb}MB, max_age={max_template_age_hours}h"
        )

    def get_template(
        self,
        config: OverlayConfiguration,
        base_image_dimensions: Tuple[int, int],
        context: OverlayGenerationContext,
    ) -> Optional[StaticOverlayTemplate]:
        """
        Get cached static template if available and valid.

        Args:
            config: Overlay configuration
            base_image_dimensions: Base image dimensions for validation
            context: Generation context for static content

        Returns:
            Cached template if available and valid, None otherwise
        """
        with self._lock:
            # Generate cache key
            cache_key = self._generate_cache_key(config, base_image_dimensions)

            # Check if template exists
            if cache_key not in self._cache:
                self._stats.cache_misses += 1
                return None

            template = self._cache[cache_key]

            # Validate template
            if not self._is_template_valid(template, base_image_dimensions):
                logger.debug(f"Template {cache_key} is invalid, removing from cache")
                del self._cache[cache_key]
                self._stats.cache_invalidations += 1
                self._stats.cache_misses += 1
                return None

            # Update access time and stats
            template.update_access_time()
            self._stats.cache_hits += 1

            logger.debug(f"Cache hit for template {cache_key}")
            return template

    def create_template(
        self,
        config: OverlayConfiguration,
        base_image_dimensions: Tuple[int, int],
        context: OverlayGenerationContext,
    ) -> StaticOverlayTemplate:
        """
        Create new static template and add to cache.

        Args:
            config: Overlay configuration
            base_image_dimensions: Base image dimensions
            context: Generation context for static content

        Returns:
            Newly created template
        """
        with self._lock:
            cache_key = self._generate_cache_key(config, base_image_dimensions)

            logger.debug(f"Creating new template {cache_key}")

            # Identify static overlay positions
            static_positions = self._identify_static_positions(config)

            # Generate static template image
            template_image = self._generate_static_template(
                config, base_image_dimensions, context, static_positions
            )

            # Calculate memory usage
            memory_size = self._calculate_image_memory_size(template_image)

            # Create template object
            template = StaticOverlayTemplate(
                config_hash=cache_key,
                template_image=template_image,
                creation_time=time.time(),
                last_access_time=time.time(),
                base_image_dimensions=base_image_dimensions,
                static_overlay_positions=static_positions,
                memory_size_bytes=memory_size,
            )

            # Add to cache
            self._cache[cache_key] = template
            self._stats.template_generations += 1
            self._stats.memory_usage_bytes += memory_size

            # Cleanup if needed
            self._cleanup_if_needed()

            logger.debug(
                f"Created template {cache_key}, cache size: {len(self._cache)} templates"
            )
            return template

    def invalidate_all(self) -> None:
        """Clear all cached templates."""
        with self._lock:
            template_count = len(self._cache)
            self._cache.clear()
            self._stats.memory_usage_bytes = 0
            self._stats.cache_invalidations += template_count
            logger.info(f"Invalidated all {template_count} cached templates")

    def get_statistics(self) -> CacheStatistics:
        """Get cache performance statistics."""
        with self._lock:
            # Update memory usage
            self._stats.memory_usage_bytes = sum(
                template.memory_size_bytes for template in self._cache.values()
            )
            return self._stats

    def _generate_cache_key(
        self, config: OverlayConfiguration, base_image_dimensions: Tuple[int, int]
    ) -> str:
        """
        Generate cache key from overlay configuration and image dimensions.

        Only includes static overlay elements in the hash to avoid cache misses
        for dynamic content changes.
        """
        # Extract only static overlay positions and their configurations
        static_config = {}

        for position, overlay_item in config.overlayPositions.items():
            # Check if this overlay type is static
            if overlay_generator_registry.has_generator(overlay_item.type):
                generator = overlay_generator_registry.get_generator(overlay_item.type)
                if generator.is_static:
                    # Include only properties that affect static rendering
                    static_item_config = {
                        "type": overlay_item.type,
                        "customText": overlay_item.customText,
                        "textSize": overlay_item.textSize,
                        "textColor": overlay_item.textColor,
                        "backgroundColor": overlay_item.backgroundColor,
                        "backgroundOpacity": overlay_item.backgroundOpacity,
                        "enableBackground": overlay_item.enableBackground,
                        "imageUrl": overlay_item.imageUrl,
                        "imageScale": overlay_item.imageScale,
                    }
                    static_config[position] = static_item_config

        # Include global options that affect static rendering
        global_config = {
            "font": config.globalOptions.font,
            "xMargin": config.globalOptions.xMargin,
            "yMargin": config.globalOptions.yMargin,
            "backgroundColor": getattr(
                config.globalOptions, "backgroundColor", "#000000"
            ),
            "backgroundOpacity": getattr(config.globalOptions, "backgroundOpacity", 50),
            "fillColor": getattr(config.globalOptions, "fillColor", "#FFFFFF"),
            "dropShadow": getattr(config.globalOptions, "dropShadow", 2),
        }

        # Include base image dimensions
        cache_data = {
            "static_overlays": static_config,
            "global_options": global_config,
            "base_dimensions": base_image_dimensions,
        }

        # Generate hash
        cache_json = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_json.encode()).hexdigest()[:16]

    def _identify_static_positions(
        self, config: OverlayConfiguration
    ) -> Set[OverlayGridPosition]:
        """Identify which overlay positions contain static content."""
        static_positions = set()

        for position, overlay_item in config.overlayPositions.items():
            if overlay_generator_registry.has_generator(overlay_item.type):
                generator = overlay_generator_registry.get_generator(overlay_item.type)
                if generator.is_static:
                    static_positions.add(position)

        return static_positions

    def _generate_static_template(
        self,
        config: OverlayConfiguration,
        base_image_dimensions: Tuple[int, int],
        context: OverlayGenerationContext,
        static_positions: Set[OverlayGridPosition],
    ) -> Image.Image:
        """
        Generate static template image with only static overlay elements.

        Creates a transparent image with static overlays pre-rendered.
        """
        width, height = base_image_dimensions

        # Create transparent template image
        template_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        # Create temporary config with only static overlays
        static_config_positions = dict()
        for pos, item in config.overlayPositions.items():
            if pos in static_positions:
                static_config_positions[pos] = item

        if not static_config_positions:
            logger.debug("No static overlays to render in template")
            return template_image

        static_config = OverlayConfiguration(
            overlayPositions=static_config_positions, globalOptions=config.globalOptions
        )

        # Render static overlays onto template
        renderer = OverlayRenderer(static_config)

        # Convert context to context_data format expected by OverlayRenderer
        context_data = {
            "timestamp": context.image_timestamp,
            "timelapse_name": (
                context.timelapse.name if context.timelapse else "Timelapse"
            ),
            "temperature": context.temperature,
            "weather_conditions": context.weather_conditions,
            "temperature_unit": context.temperature_unit,
        }

        try:
            # Use the renderer's internal methods to render onto our template
            # This is a bit of a hack but avoids code duplication

            async def render_template():
                return await renderer.render_overlay_fast(template_image, context_data)

            # Run the async rendering
            try:
                loop = asyncio.get_event_loop()
                result_image = loop.run_until_complete(render_template())
            except RuntimeError:
                result_image = asyncio.run(render_template())

            return result_image

        except Exception as e:
            logger.error(f"Failed to generate static template: {e}")
            return template_image

    def _is_template_valid(
        self, template: StaticOverlayTemplate, base_image_dimensions: Tuple[int, int]
    ) -> bool:
        """Check if cached template is still valid."""

        # Check image dimensions
        if not template.is_valid_for_dimensions(base_image_dimensions):
            return False

        # Check age
        if template.get_age_seconds() > self.max_template_age_seconds:
            return False

        # Check if template image is still valid
        if template.template_image is None:
            return False

        return True

    def _calculate_image_memory_size(self, image: Image.Image) -> int:
        """Calculate approximate memory usage of PIL image."""
        width, height = image.size
        channels = len(image.getbands())
        return width * height * channels  # Rough estimate in bytes

    def _cleanup_if_needed(self) -> None:
        """Clean up cache if memory usage exceeds limits."""
        current_size = sum(
            template.memory_size_bytes for template in self._cache.values()
        )

        if current_size <= self.max_cache_size_bytes:
            return

        logger.info(
            f"Cache cleanup needed: {current_size} bytes > {self.max_cache_size_bytes} bytes"
        )

        # Sort templates by last access time (LRU)
        templates_by_access = sorted(
            self._cache.items(), key=lambda item: item[1].last_access_time
        )

        # Remove least recently used templates
        removed_count = 0
        for cache_key, template in templates_by_access:
            if current_size <= self.max_cache_size_bytes * 0.8:  # Target 80% of max
                break

            del self._cache[cache_key]
            current_size -= template.memory_size_bytes
            removed_count += 1

        self._stats.cache_invalidations += removed_count
        self._stats.last_cleanup = time.time()

        logger.info(
            f"Removed {removed_count} templates from cache, new size: {current_size} bytes"
        )


# Global cache instance
static_overlay_cache = StaticOverlayTemplateCache()
