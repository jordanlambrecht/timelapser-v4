# backend/app/services/overlay_pipeline/generators/text_generator.py
"""
Text Overlay Generator - Handles static text overlay content generation.

Supports custom user text and timelapse name overlays.
"""

from typing import Union
from PIL import Image as PILImage
from loguru import logger

from .base_generator import BaseOverlayGenerator, OverlayGenerationContext
from ....models.overlay_model import OverlayItem, OverlayType
from ....utils.validation_helpers import validate_custom_text


class TextGenerator(BaseOverlayGenerator):
    """
    Generator for text-based overlay content.
    
    Handles:
    - custom_text: User-defined static text
    - timelapse_name: Current timelapse name
    
    Both types produce static content that can be cached for performance.
    """
    
    @property
    def supported_types(self) -> list[OverlayType]:
        """Text generator supports custom_text and timelapse_name overlays."""
        return ["custom_text", "timelapse_name"]
    
    @property
    def is_static(self) -> bool:
        """Text content is static - doesn't change between frames."""
        return True
    
    def generate_content(
        self, 
        overlay_item: OverlayItem, 
        context: OverlayGenerationContext
    ) -> Union[str, PILImage.Image]:
        """
        Generate text content based on overlay type.
        
        Args:
            overlay_item: Text overlay configuration
            context: Generation context with timelapse information
            
        Returns:
            Text string to be rendered
            
        Raises:
            ValueError: If overlay type is not supported or required data is missing
        """
        logger.debug(f"📝 Starting {overlay_item.type} text overlay generation")
        
        try:
            self.validate_overlay_item(overlay_item)
            logger.debug(f"🔍 Text overlay validation passed for type: {overlay_item.type}")
            
            if overlay_item.type == "custom_text":
                result = self._generate_custom_text(overlay_item, context)
                logger.debug(f"✅ Generated custom text overlay: '{result}'")
            elif overlay_item.type == "timelapse_name":
                result = self._generate_timelapse_name(overlay_item, context)
                logger.debug(f"✅ Generated timelapse name overlay: '{result}'")
            else:
                logger.error(f"❌ Unsupported text overlay type: {overlay_item.type}")
                raise ValueError(f"Unsupported overlay type: {overlay_item.type}")
                
            return result
                
        except ValueError as e:
            logger.error(f"❌ Validation error in text overlay generation: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to generate text overlay content: {e}")
            raise RuntimeError(f"Failed to generate text content: {e}")
    
    def _generate_custom_text(
        self, 
        overlay_item: OverlayItem, 
        context: OverlayGenerationContext
    ) -> str:
        """
        Generate custom text content.
        
        Args:
            overlay_item: Custom text overlay configuration
            context: Generation context (not used for custom text)
            
        Returns:
            User-defined custom text
            
        Raises:
            ValueError: If custom text is not provided
        """
        logger.debug("📝 Processing custom text overlay generation")
        
        if not overlay_item.customText:
            logger.error("❌ Custom text overlay missing customText property")
            raise ValueError("Custom text overlay requires customText property")
        
        logger.debug(f"📝 Custom text content: '{overlay_item.customText[:50]}{'...' if len(overlay_item.customText) > 50 else ''}'")
        
        # Return the text as-is
        # Future enhancement: Could support text templating/variables here
        result = overlay_item.customText.strip()
        logger.debug(f"✅ Custom text overlay generated successfully")
        return result
    
    def _generate_timelapse_name(
        self, 
        overlay_item: OverlayItem, 
        context: OverlayGenerationContext
    ) -> str:
        """
        Generate timelapse name content.
        
        Args:
            overlay_item: Timelapse name overlay configuration
            context: Generation context with timelapse information
            
        Returns:
            Current timelapse name
            
        Raises:
            ValueError: If timelapse information is not available
        """
        logger.debug("📝 Processing timelapse name overlay generation")
        
        if not context.timelapse:
            logger.error("❌ Timelapse name overlay missing timelapse context")
            raise ValueError("Timelapse name overlay requires timelapse context")
        
        if not context.timelapse.name:
            logger.error("❌ Timelapse name is not available in context")
            raise ValueError("Timelapse name is not available")
        
        logger.debug(f"📝 Timelapse name: '{context.timelapse.name}'")
        
        # Return the timelapse name
        # Future enhancement: Could support name formatting/truncation here
        result = context.timelapse.name.strip()
        logger.debug(f"✅ Timelapse name overlay generated successfully")
        return result
    
    def validate_overlay_item(self, overlay_item: OverlayItem) -> None:
        """
        Validate text overlay item configuration.
        
        Args:
            overlay_item: Overlay item to validate
            
        Raises:
            ValueError: If overlay item is invalid for text generation
        """
        logger.debug(f"🔍 Validating text overlay item of type: {overlay_item.type}")
        
        super().validate_overlay_item(overlay_item)
        
        # Type-specific validation using validation helpers
        if overlay_item.type == "custom_text":
            logger.debug("🔍 Validating custom_text overlay configuration")
            
            try:
                # Use validation helper for consistent validation
                validated_text = validate_custom_text(overlay_item.customText)
                logger.debug(f"✅ Custom text overlay validation passed: {len(validated_text)} characters")
            except ValueError as e:
                logger.error(f"❌ Custom text validation failed: {e}")
                raise
        
        elif overlay_item.type == "timelapse_name":
            logger.debug("🔍 Timelapse name overlay - no configuration validation required")
            # No specific validation required for timelapse name
            # Name validation happens at runtime when context is available
            pass
        
        logger.debug(f"✅ Text overlay validation completed for type: {overlay_item.type}")