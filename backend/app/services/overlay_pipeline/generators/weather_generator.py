# backend/app/services/overlay_pipeline/generators/weather_generator.py
"""
Weather Overlay Generator - Handles weather-related overlay content generation.

Supports temperature and weather condition overlays with formatting options.
"""

from typing import Union, Optional
from PIL import Image as PILImage
from loguru import logger

from .base_generator import BaseOverlayGenerator, OverlayGenerationContext
from ....models.overlay_model import OverlayItem, OverlayType
from ....utils.validation_helpers import validate_temperature_unit, validate_display_format


class WeatherGenerator(BaseOverlayGenerator):
    """
    Generator for weather-based overlay content.
    
    Handles:
    - temperature: Current temperature reading
    - weather_conditions: Weather description (sunny, cloudy, etc.)
    - weather_temp_conditions: Combined temperature and conditions
    
    All types produce dynamic content that changes based on weather data.
    """
    
    @property
    def supported_types(self) -> list[OverlayType]:
        """Weather generator supports temperature and weather condition overlays."""
        return ["temperature", "weather_conditions", "weather_temp_conditions"]
    
    @property
    def is_static(self) -> bool:
        """Weather content is dynamic - changes based on weather updates."""
        return False
    
    def generate_content(
        self, 
        overlay_item: OverlayItem, 
        context: OverlayGenerationContext
    ) -> Union[str, PILImage.Image]:
        """
        Generate weather content based on overlay type.
        
        Args:
            overlay_item: Weather overlay configuration
            context: Generation context with weather information
            
        Returns:
            Formatted weather information string
            
        Raises:
            ValueError: If overlay type is not supported or weather data is missing
        """
        logger.debug(f"🌤️ Starting {overlay_item.type} weather overlay generation")
        
        try:
            self.validate_overlay_item(overlay_item)
            logger.debug(f"🔍 Weather overlay validation passed for type: {overlay_item.type}")
            
            if overlay_item.type == "temperature":
                result = self._generate_temperature(overlay_item, context)
                logger.debug(f"✅ Generated temperature overlay: '{result}'")
            elif overlay_item.type == "weather_conditions":
                result = self._generate_weather_conditions(overlay_item, context)
                logger.debug(f"✅ Generated weather conditions overlay: '{result}'")
            elif overlay_item.type == "weather_temp_conditions":
                result = self._generate_temp_and_conditions(overlay_item, context)
                logger.debug(f"✅ Generated combined weather overlay: '{result}'")
            else:
                logger.error(f"❌ Unsupported weather overlay type: {overlay_item.type}")
                raise ValueError(f"Unsupported overlay type: {overlay_item.type}")
                
            return result
                
        except ValueError as e:
            logger.error(f"❌ Validation error in weather overlay generation: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to generate weather overlay content: {e}")
            raise RuntimeError(f"Failed to generate weather content: {e}")
    
    def _generate_temperature(
        self, 
        overlay_item: OverlayItem, 
        context: OverlayGenerationContext
    ) -> str:
        """
        Generate temperature content.
        
        Args:
            overlay_item: Temperature overlay configuration
            context: Generation context with temperature data
            
        Returns:
            Formatted temperature string
            
        Raises:
            ValueError: If temperature data is not available
        """
        logger.debug("🌡️ Processing temperature overlay generation")
        
        if context.temperature is None:
            logger.warning("⚠️ Temperature data not available, using fallback")
            return "N/A"  # Graceful fallback instead of error
        
        logger.debug(f"🌡️ Raw temperature: {context.temperature}°{context.temperature_unit or 'unknown'}")
        
        # Get temperature unit preference
        unit = overlay_item.unit or context.temperature_unit or "F"
        logger.debug(f"🌡️ Target unit: {unit}")
        
        # Convert temperature if needed
        temp_value = self._convert_temperature(context.temperature, context.temperature_unit, unit)
        logger.debug(f"🌡️ Converted temperature: {temp_value}°{unit}")
        
        # Format based on display preference
        display = overlay_item.display or "with_unit"
        logger.debug(f"🌡️ Display format: {display}")
        
        if display == "temp_only":
            result = f"{temp_value:.0f}°"
        elif display == "with_unit":
            result = f"{temp_value:.0f}°{unit}"
        else:
            # Default to with_unit for unknown display types
            logger.debug(f"🌡️ Unknown display format '{display}', using with_unit")
            result = f"{temp_value:.0f}°{unit}"
        
        logger.debug(f"✅ Temperature overlay generated successfully")
        return result
    
    def _generate_weather_conditions(
        self, 
        overlay_item: OverlayItem, 
        context: OverlayGenerationContext
    ) -> str:
        """
        Generate weather conditions content.
        
        Args:
            overlay_item: Weather conditions overlay configuration
            context: Generation context with weather condition data
            
        Returns:
            Weather conditions string
        """
        logger.debug("🌤️ Processing weather conditions overlay generation")
        
        if not context.weather_conditions:
            logger.warning("⚠️ Weather conditions data not available, using fallback")
            return "N/A"  # Graceful fallback
        
        logger.debug(f"🌤️ Raw weather conditions: '{context.weather_conditions}'")
        
        # Return conditions as-is, with basic cleanup
        conditions = context.weather_conditions.strip()
        
        # Capitalize first letter if needed
        if conditions and conditions[0].islower():
            logger.debug("🌤️ Capitalizing first letter of conditions")
            conditions = conditions[0].upper() + conditions[1:]
        
        logger.debug(f"✅ Weather conditions overlay generated successfully")
        return conditions
    
    def _generate_temp_and_conditions(
        self, 
        overlay_item: OverlayItem, 
        context: OverlayGenerationContext
    ) -> str:
        """
        Generate combined temperature and conditions content.
        
        Args:
            overlay_item: Combined weather overlay configuration
            context: Generation context with weather data
            
        Returns:
            Combined temperature and conditions string
        """
        logger.debug("🌤️ Processing combined temperature and conditions overlay generation")
        
        # Generate temperature component
        if context.temperature is not None:
            logger.debug("🌡️ Generating temperature component")
            temp_str = self._generate_temperature(overlay_item, context)
        else:
            logger.debug("🌡️ Temperature unavailable for combined overlay")
            temp_str = "N/A"
        
        # Generate conditions component
        logger.debug("🌤️ Generating conditions component")
        conditions_str = self._generate_weather_conditions(overlay_item, context)
        
        # Combine with appropriate separator
        if temp_str == "N/A" and conditions_str == "N/A":
            logger.debug("🌤️ Both components unavailable, using general fallback")
            result = "Weather N/A"
        elif temp_str == "N/A":
            logger.debug("🌤️ Only conditions available")
            result = conditions_str
        elif conditions_str == "N/A":
            logger.debug("🌤️ Only temperature available")
            result = temp_str
        else:
            logger.debug("🌤️ Both components available, combining")
            result = f"{temp_str}, {conditions_str}"
        
        logger.debug(f"✅ Combined weather overlay generated successfully")
        return result
    
    def _convert_temperature(
        self, 
        temperature: float, 
        from_unit: str, 
        to_unit: str
    ) -> float:
        """
        Convert temperature between Fahrenheit and Celsius.
        
        Args:
            temperature: Temperature value to convert
            from_unit: Source unit ("F" or "C")
            to_unit: Target unit ("F" or "C")
            
        Returns:
            Converted temperature value
        """
        logger.debug(f"🌡️ Converting temperature: {temperature}°{from_unit} → {to_unit}")
        
        if from_unit == to_unit:
            logger.debug("🌡️ No conversion needed, same unit")
            return temperature
        
        if from_unit == "C" and to_unit == "F":
            # Celsius to Fahrenheit: F = (C × 9/5) + 32
            converted = (temperature * 9/5) + 32
            logger.debug(f"🌡️ Celsius to Fahrenheit: {temperature}°C → {converted}°F")
            return converted
        elif from_unit == "F" and to_unit == "C":
            # Fahrenheit to Celsius: C = (F - 32) × 5/9
            converted = (temperature - 32) * 5/9
            logger.debug(f"🌡️ Fahrenheit to Celsius: {temperature}°F → {converted}°C")
            return converted
        else:
            # Unknown unit conversion, return original
            logger.warning(f"⚠️ Unknown unit conversion {from_unit} → {to_unit}, returning original value")
            return temperature
    
    def validate_overlay_item(self, overlay_item: OverlayItem) -> None:
        """
        Validate weather overlay item configuration.
        
        Args:
            overlay_item: Overlay item to validate
            
        Raises:
            ValueError: If overlay item is invalid for weather generation
        """
        logger.debug(f"🔍 Validating weather overlay item of type: {overlay_item.type}")
        
        super().validate_overlay_item(overlay_item)
        
        # Use validation helpers for consistent validation
        try:
            # Validate temperature unit
            validated_unit = validate_temperature_unit(overlay_item.unit)
            if validated_unit:
                logger.debug(f"🌡️ Validated temperature unit: {validated_unit}")
            
            # Validate display format
            validated_display = validate_display_format(overlay_item.display)
            if validated_display:
                logger.debug(f"🎨 Validated display format: {validated_display}")
                
        except ValueError as e:
            logger.error(f"❌ Weather validation failed: {e}")
            raise
        
        # Type-specific validation
        if overlay_item.type in ["temperature", "weather_temp_conditions"]:
            logger.debug("🌡️ Temperature-based overlay validation")
            # These types should have unit preference
            if not overlay_item.unit and overlay_item.type == "temperature":
                logger.debug("🌡️ No unit specified, will use default from context")
                # Will use default from context, no error needed
                pass
            elif overlay_item.unit:
                logger.debug(f"🌡️ Unit specified: {overlay_item.unit}")
        
        if overlay_item.type in ["weather_conditions", "weather_temp_conditions"]:
            logger.debug("🌤️ Weather conditions overlay validation")
            # These types require weather conditions data at runtime
            # Can't validate here without context, will check at generation time
            pass
        
        logger.debug(f"✅ Weather overlay validation completed for type: {overlay_item.type}")
        if overlay_item.unit:
            logger.debug(f"🌡️ Temperature unit: {overlay_item.unit}")
        if overlay_item.display:
            logger.debug(f"🎨 Display format: {overlay_item.display}")