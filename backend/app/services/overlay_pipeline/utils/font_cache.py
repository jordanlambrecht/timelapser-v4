# backend/app/services/overlay_pipeline/utils/font_cache.py
"""
Global Font Cache - High-performance font caching system for overlay generation.

Provides centralized font loading and caching to eliminate repeated font file system
lookups and improve overlay rendering performance. Designed for multi-worker scenarios
with memory-efficient caching.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple

from PIL import ImageFont

from ....enums import LoggerName
from ....services.logger import get_service_logger

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE)


@dataclass
class FontCacheStats:
    """Statistics for font cache performance monitoring."""

    cache_hits: int = 0
    cache_misses: int = 0
    fonts_loaded: int = 0
    total_requests: int = 0

    @property
    def hit_ratio(self) -> float:
        """Calculate cache hit ratio as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100.0


class GlobalFontCache:
    """
    Global font cache with preloading and performance optimization.

    Features:
    - Thread-safe font caching across multiple workers
    - Preloading of common font/size combinations
    - Automatic fallback handling for missing fonts
    - Performance statistics and monitoring
    - Memory-efficient storage of font objects
    """

    # Class-level cache shared across all instances
    _font_cache: Dict[str, ImageFont.FreeTypeFont] = {}
    _cache_lock = Lock()
    _stats = FontCacheStats()
    _preloaded = False

    # Common font sizes for overlay rendering
    COMMON_SIZES = [12, 14, 16, 18, 20, 22, 24, 28, 32, 36, 40, 48, 56, 64, 72]

    # Font fallback hierarchy
    FONT_FALLBACKS = {
        "Arial": [
            "/System/Library/Fonts/Arial.ttf",  # macOS
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Linux
            "C:\\Windows\\Fonts\\arial.ttf",  # Windows
        ],
        "Helvetica": [
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Linux
            "C:\\Windows\\Fonts\\arial.ttf",  # Windows fallback
        ],
        "Times New Roman": [
            "/System/Library/Fonts/Times.ttc",  # macOS
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",  # Linux
            "C:\\Windows\\Fonts\\times.ttf",  # Windows
        ],
        "Courier": [
            "/System/Library/Fonts/Courier.ttc",  # macOS
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",  # Linux
            "C:\\Windows\\Fonts\\cour.ttf",  # Windows
        ],
    }

    @classmethod
    def preload_fonts(cls, font_families: Optional[List[str]] = None) -> None:
        """
        Preload common font/size combinations for optimal performance.

        Args:
            font_families: List of font families to preload. If None, preloads all common fonts.
        """
        if cls._preloaded:
            logger.debug("Fonts already preloaded, skipping")
            return

        if font_families is None:
            font_families = list(cls.FONT_FALLBACKS.keys())

        logger.info(
            f"Preloading fonts: {font_families} in sizes: {cls.COMMON_SIZES}",
            send_to_database=False,
        )
        start_time = time.time()

        preloaded_count = 0
        for family in font_families:
            for size in cls.COMMON_SIZES:
                try:
                    cls.get_font(family, size)
                    preloaded_count += 1
                except Exception as e:
                    logger.warning(f"Failed to preload font {family}:{size}: {e}")

        cls._preloaded = True
        elapsed = time.time() - start_time
        logger.debug(
            f"Preloaded {preloaded_count} font combinations in {elapsed:.2f}s",
            send_to_database=False,
        )

    @classmethod
    def get_font(cls, font_family: str, size: int) -> ImageFont.FreeTypeFont:
        """
        Get font with high-performance caching.

        Args:
            font_family: Font family name (e.g., 'Arial', 'Helvetica')
            size: Font size in pixels

        Returns:
            Loaded font object, with fallback if requested font unavailable
        """
        cache_key = f"{font_family}_{size}"

        with cls._cache_lock:
            cls._stats.total_requests += 1

            # Check cache first
            if cache_key in cls._font_cache:
                cls._stats.cache_hits += 1
                return cls._font_cache[cache_key]

            # Cache miss - load font
            cls._stats.cache_misses += 1
            font = cls._load_font_with_fallback(font_family, size)
            cls._font_cache[cache_key] = font
            cls._stats.fonts_loaded += 1

            return font

    @classmethod
    def _load_font_with_fallback(
        cls, font_family: str, size: int
    ) -> ImageFont.FreeTypeFont:
        """Load font with intelligent fallback handling."""

        # Get font paths for this family
        font_paths = cls.FONT_FALLBACKS.get(font_family, [])

        # Try each path in order
        for font_path in font_paths:
            if Path(font_path).exists():
                try:
                    logger.debug(f"Loading font {font_family}:{size} from {font_path}")
                    return ImageFont.truetype(font_path, size)
                except (OSError, IOError) as e:
                    logger.warning(f"Failed to load font from {font_path}: {e}")
                    continue

        # Try system font discovery as fallback
        try:
            return ImageFont.truetype(font_family, size)
        except (OSError, IOError):
            pass

        # Final fallback to default font
        # TODO: Add fonts to asset library for guaranteed availability
        logger.warning(f"Font {font_family}:{size} not found, using default font")
        # Use a bundled or system TrueType font for guaranteed FreeTypeFont type
        default_font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        if Path(default_font_path).exists():
            return ImageFont.truetype(default_font_path, size)
        # As a last resort, raise an error to ensure type consistency
        logger.error(
            "Default TrueType font not found, cannot return FreeTypeFont instance"
        )
        raise RuntimeError(
            f"Could not load a TrueType font for family '{font_family}' and size '{size}'."
        )

    @classmethod
    def get_stats(cls) -> FontCacheStats:
        """Get current cache performance statistics."""
        with cls._cache_lock:
            return FontCacheStats(
                cache_hits=cls._stats.cache_hits,
                cache_misses=cls._stats.cache_misses,
                fonts_loaded=cls._stats.fonts_loaded,
                total_requests=cls._stats.total_requests,
            )

    @classmethod
    def clear_cache(cls) -> None:
        """Clear font cache (useful for testing or memory management)."""
        with cls._cache_lock:
            cls._font_cache.clear()
            cls._stats = FontCacheStats()
            cls._preloaded = False
            logger.info("Font cache cleared")

    @classmethod
    def get_cache_size(cls) -> int:
        """Get number of cached font objects."""
        with cls._cache_lock:
            return len(cls._font_cache)

    @classmethod
    def get_text_metrics(
        cls, text: str, font_family: str, size: int
    ) -> Tuple[int, int]:
        """
        Get text dimensions with font caching.

        Args:
            text: Text to measure
            font_family: Font family name
            size: Font size

        Returns:
            Tuple of (width, height) in pixels
        """
        font = cls.get_font(font_family, size)

        # Use textbbox for accurate measurements
        bbox = font.getbbox(text)
        width = int(bbox[2] - bbox[0])
        height = int(bbox[3] - bbox[1])

        return width, height


# Singleton instance for easy access
font_cache = GlobalFontCache()


def preload_overlay_fonts() -> None:
    """Convenience function to preload fonts commonly used in overlays."""
    # Preload fonts that are commonly used in overlay configurations
    common_overlay_fonts = ["Arial", "Helvetica", "Times New Roman"]
    font_cache.preload_fonts(common_overlay_fonts)


def get_font_fast(font_family: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Fast font retrieval using global cache.

    This is the main function that overlay renderers should use.
    """
    return font_cache.get_font(font_family, size)


def get_text_size_fast(text: str, font_family: str, size: int) -> Tuple[int, int]:
    """
    Fast text size calculation using cached fonts.

    Returns:
        Tuple of (width, height) in pixels
    """
    return font_cache.get_text_metrics(text, font_family, size)
