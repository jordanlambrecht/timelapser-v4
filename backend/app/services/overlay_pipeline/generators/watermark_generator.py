# backend/app/services/overlay_pipeline/generators/watermark_generator.py
"""
Watermark Overlay Generator - Handles image-based overlay content generation.

Supports watermark and logo overlays with scaling and positioning.
"""

from typing import Union
from pathlib import Path
from PIL import Image as PILImage
from loguru import logger

from .base_generator import BaseOverlayGenerator, OverlayGenerationContext
from ....models.overlay_model import OverlayItem, OverlayType
from ....utils.validation_helpers import validate_image_path, validate_image_scale


class WatermarkGenerator(BaseOverlayGenerator):
    """
    Generator for image-based overlay content.
    
    Handles:
    - watermark: Custom image overlays (logos, watermarks, etc.)
    
    Produces static content that can be cached for performance.
    """
    
    @property
    def supported_types(self) -> list[OverlayType]:
        """Watermark generator supports watermark overlays."""
        return ["watermark"]
    
    @property
    def is_static(self) -> bool:
        """Watermark content is static - doesn't change between frames."""
        return True
    
    def generate_content(
        self, 
        overlay_item: OverlayItem, 
        context: OverlayGenerationContext
    ) -> Union[str, PILImage.Image]:
        """
        Generate watermark image content.
        
        Args:
            overlay_item: Watermark overlay configuration
            context: Generation context (not used for watermarks)
            
        Returns:
            PIL Image object for the watermark
            
        Raises:
            ValueError: If overlay type is not supported or image cannot be loaded
        """
        logger.debug(f"🖼️ Starting {overlay_item.type} watermark overlay generation")
        
        try:
            self.validate_overlay_item(overlay_item)
            logger.debug(f"🔍 Watermark overlay validation passed for type: {overlay_item.type}")
            
            if overlay_item.type == "watermark":
                result = self._generate_watermark_image(overlay_item, context)
                logger.debug(f"✅ Generated watermark overlay image: {result.size} pixels")
                return result
            else:
                logger.error(f"❌ Unsupported watermark overlay type: {overlay_item.type}")
                raise ValueError(f"Unsupported overlay type: {overlay_item.type}")
                
        except ValueError as e:
            logger.error(f"❌ Validation error in watermark overlay generation: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to generate watermark overlay content: {e}")
            raise RuntimeError(f"Failed to generate watermark content: {e}")
    
    def _generate_watermark_image(
        self, 
        overlay_item: OverlayItem, 
        context: OverlayGenerationContext
    ) -> PILImage.Image:
        """
        Generate watermark image content.
        
        Args:
            overlay_item: Watermark overlay configuration
            context: Generation context
            
        Returns:
            Processed PIL Image for the watermark
            
        Raises:
            ValueError: If image cannot be loaded or processed
        """
        logger.debug("🖼️ Processing watermark image generation")
        
        if not overlay_item.imageUrl:
            logger.error("❌ Watermark overlay missing imageUrl property")
            raise ValueError("Watermark overlay requires imageUrl property")
        
        logger.debug(f"🖼️ Loading watermark from: {overlay_item.imageUrl}")
        
        # Load the image
        watermark_image = self._load_image(overlay_item.imageUrl)
        logger.debug(f"🖼️ Watermark loaded: {watermark_image.size} pixels, mode: {watermark_image.mode}")
        
        # Apply scaling if specified
        if overlay_item.imageScale != 100:
            logger.debug(f"🔍 Scaling watermark: {overlay_item.imageScale}%")
            watermark_image = self._scale_image(watermark_image, overlay_item.imageScale)
            logger.debug(f"🖼️ Watermark scaled to: {watermark_image.size} pixels")
        else:
            logger.debug("🖼️ No scaling needed, using original size")
        
        # Ensure image has alpha channel for transparency
        if watermark_image.mode != "RGBA":
            logger.debug(f"🔄 Converting watermark mode from {watermark_image.mode} to RGBA")
            watermark_image = watermark_image.convert("RGBA")
        else:
            logger.debug("🖼️ Watermark already has alpha channel")
        
        logger.debug(f"✅ Watermark image generated successfully")
        return watermark_image
    
    def _load_image(self, image_path: str) -> PILImage.Image:
        """
        Load image from file system or URL.
        
        Args:
            image_path: Path or URL to the image
            
        Returns:
            PIL Image object
            
        Raises:
            ValueError: If image cannot be loaded
        """
        logger.debug(f"📂 Loading image from path: {image_path}")
        
        try:
            # Handle different path formats
            if image_path.startswith(('http://', 'https://')):
                logger.error("❌ HTTP URLs not supported for security reasons")
                # For now, don't support HTTP URLs for security
                # Future enhancement: Could support with proper validation
                raise ValueError("HTTP URLs not supported for watermarks")
            
            # Handle local file paths
            if image_path.startswith('/assets/'):
                logger.debug("🔍 Resolving frontend asset path to file system path")
                # Frontend asset path - need to resolve to actual file system path
                # This would need to be configured based on your asset storage setup
                # For now, assume assets are stored in a known directory
                actual_path = self._resolve_asset_path(image_path)
                logger.debug(f"📂 Resolved asset path: {actual_path}")
            else:
                actual_path = Path(image_path)
                logger.debug(f"📂 Using direct file path: {actual_path}")
            
            # Validate path exists and is readable
            if not actual_path.exists():
                logger.error(f"❌ Image file not found: {actual_path}")
                raise ValueError(f"Image file not found: {actual_path}")
            
            if not actual_path.is_file():
                logger.error(f"❌ Path is not a file: {actual_path}")
                raise ValueError(f"Path is not a file: {actual_path}")
            
            logger.debug(f"📂 Image file found, attempting to load")
            
            # Load image
            image = PILImage.open(actual_path)
            logger.debug(f"🖼️ Image loaded: {image.size} pixels, format: {image.format}, mode: {image.mode}")
            
            # Validate image format
            if image.format not in ['PNG', 'JPEG', 'JPG', 'WEBP', 'GIF']:
                logger.error(f"❌ Unsupported image format: {image.format}")
                raise ValueError(f"Unsupported image format: {image.format}")
            
            logger.debug(f"✅ Image loaded successfully")
            return image
            
        except Exception as e:
            logger.error(f"❌ Failed to load watermark image {image_path}: {e}")
            raise ValueError(f"Cannot load watermark image: {e}")
    
    def _resolve_asset_path(self, frontend_path: str) -> Path:
        """
        Resolve frontend asset path to actual file system path.
        
        Args:
            frontend_path: Frontend asset path (e.g., "/assets/logo.png")
            
        Returns:
            Resolved file system path
            
        Note:
            This would need to be configured based on your asset storage setup.
            For now, assuming a basic assets directory structure.
        """
        logger.debug(f"🔍 Resolving frontend asset path: {frontend_path}")
        
        # Remove leading /assets/ and resolve to actual directory
        relative_path = frontend_path.replace('/assets/', '')
        logger.debug(f"📂 Relative path: {relative_path}")
        
        # This path should be configurable via settings
        # For now, assume assets are stored relative to the data directory
        from ....config import get_settings
        settings = get_settings()
        
        # Construct full path to assets
        assets_dir = Path(settings.data_directory) / "assets" / "overlays"
        full_path = assets_dir / relative_path
        
        logger.debug(f"📂 Resolved full path: {full_path}")
        return full_path
    
    def _scale_image(self, image: PILImage.Image, scale_percent: int) -> PILImage.Image:
        """
        Scale image by the specified percentage.
        
        Args:
            image: PIL Image to scale
            scale_percent: Scale percentage (100 = original size)
            
        Returns:
            Scaled PIL Image
        """
        logger.debug(f"🔍 Scaling image: {scale_percent}% (original: {image.size})")
        
        if scale_percent == 100:
            logger.debug("🔍 No scaling needed, returning original")
            return image
        
        # Calculate new dimensions
        original_width, original_height = image.size
        scale_factor = scale_percent / 100.0
        
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        
        logger.debug(f"🔍 Calculated new size: {new_width}x{new_height} (factor: {scale_factor})")
        
        # Ensure minimum size
        if new_width < 1:
            new_width = 1
            logger.debug("🔍 Adjusted width to minimum (1 pixel)")
        if new_height < 1:
            new_height = 1
            logger.debug("🔍 Adjusted height to minimum (1 pixel)")
        
        # Scale using high-quality resampling
        logger.debug("🔍 Applying LANCZOS resampling for high quality")
        scaled_image = image.resize((new_width, new_height), PILImage.Resampling.LANCZOS)
        
        logger.debug(f"✅ Image scaled successfully to {scaled_image.size}")
        return scaled_image
    
    def validate_overlay_item(self, overlay_item: OverlayItem) -> None:
        """
        Validate watermark overlay item configuration.
        
        Args:
            overlay_item: Overlay item to validate
            
        Raises:
            ValueError: If overlay item is invalid for watermark generation
        """
        logger.debug(f"🔍 Validating watermark overlay item of type: {overlay_item.type}")
        
        super().validate_overlay_item(overlay_item)
        
        # Use validation helpers for consistent validation
        try:
            # Validate image path (handles security and format checks)
            validated_path = validate_image_path(overlay_item.imageUrl)
            logger.debug(f"🔍 Validated image path: {validated_path}")
            
            # Validate image scale
            validated_scale = validate_image_scale(overlay_item.imageScale)
            logger.debug(f"🔍 Validated image scale: {validated_scale}%")
            
        except ValueError as e:
            logger.error(f"❌ Watermark validation failed: {e}")
            raise
        
        logger.debug(f"✅ Watermark overlay validation completed for type: {overlay_item.type}")