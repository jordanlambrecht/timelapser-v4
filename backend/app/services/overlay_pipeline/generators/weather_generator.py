# backend/app/services/overlay_pipeline/generators/weather_generator.py
"""
Weather Overlay Generator - Handles weather-related overlay content generation.

Supports temperature and weather condition overlays with formatting options.
"""

from typing import Union

from PIL import Image as PILImage

from ....enums import LoggerName, LogSource
from ....models.overlay_model import OverlayItem
from ....services.logger import get_service_logger
from ....utils.validation_helpers import (
    validate_display_format,
    validate_temperature_unit,
)
from .base_generator import BaseOverlayGenerator, OverlayGenerationContext

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)


class WeatherGenerator(BaseOverlayGenerator):
    """
    Generator for weather-based overlay content.

    Handles:
    - temperature: Current temperature reading
    - weather_conditions: Weather description (sunny, cloudy, etc.)
    - weather: Combined temperature and conditions (unified weather type)

    All types produce dynamic content that changes based on weather data.
    """

    @property
    def generator_type(self) -> str:
        """Return the primary generator type."""
        return "weather"

    @property
    def display_name(self) -> str:
        """Human-readable name for this generator."""
        return "Weather Data"

    @property
    def description(self) -> str:
        """Description of what this generator does."""
        return "Displays temperature and weather conditions with icon support"

    @property
    def supported_types(self) -> list[str]:
        """Weather generator supports temperature and weather condition overlays."""
        return [
            "temperature",
            "weather_conditions",
            "weather",  # Unified weather type
        ]

    def supports_type(self, overlay_type: str) -> bool:
        """Check if this generator supports the given overlay type."""
        # Since supported_types now returns strings, we can directly check
        return overlay_type in self.supported_types

    @property
    def is_static(self) -> bool:
        """Weather content is dynamic - changes based on weather updates."""
        return False

    def generate_content(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
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
        logger.debug(f"Starting {overlay_item.type} weather overlay generation")

        try:
            self.validate_overlay_item(overlay_item)
            logger.debug(
                f"Weather overlay type '{overlay_item.type}' processed successfully"
            )

            if overlay_item.type == "temperature":
                result = self._generate_temperature(overlay_item, context)
                logger.debug(f"Generated temperature overlay: '{result}'")
            elif overlay_item.type == "weather_conditions":
                result = self._generate_weather_conditions(overlay_item, context)
                logger.debug(f"Generated weather conditions overlay: '{result}'")
            elif overlay_item.type in ["weather", "weather_temp_conditions"]:
                # Support both unified and legacy weather types
                result = self._generate_temp_and_conditions(overlay_item, context)
                logger.debug(f"Generated unified weather overlay: '{result}'")
            else:
                logger.error(f"Unsupported weather overlay type: {overlay_item.type}")
                raise ValueError(f"Unsupported overlay type: {overlay_item.type}")

            return result

        except ValueError as e:
            logger.error(f"Validation error in weather overlay generation: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to generate weather overlay content: {e}")
            raise RuntimeError(f"Failed to generate weather content: {e}")

    def _generate_temperature(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
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
        logger.debug("Processing temperature overlay generation")

        if context.temperature is None:
            logger.warning("Temperature data not available, using fallback")
            return "N/A"  # Graceful fallback instead of error

        logger.debug(
            f"Raw temperature: {context.temperature}°{context.temperature_unit or 'unknown'}"
        )

        # Get temperature unit preference
        unit = overlay_item.settings.get("unit") or context.temperature_unit or "F"
        logger.debug(f"Target unit: {unit}")

        # Convert temperature if needed
        temp_value = self._convert_temperature(
            context.temperature, context.temperature_unit, unit
        )
        logger.debug(f"Converted temperature: {temp_value}°{unit}")

        # Format based on display preference
        display = overlay_item.settings.get("display", "with_unit")
        logger.debug(f"Display format: {display}")

        if display == "temp_only":
            result = f"{temp_value:.0f}°"
        elif display == "with_unit":
            result = f"{temp_value:.0f}°{unit}"
        else:
            # Default to with_unit for unknown display types
            logger.debug(f"Unknown display format '{display}', using with_unit")
            result = f"{temp_value:.0f}°{unit}"

        logger.debug("Temperature overlay generated successfully")
        return result

    def _generate_weather_conditions(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
    ) -> str:
        """
        Generate weather conditions content.

        Args:
            overlay_item: Weather conditions overlay configuration
            context: Generation context with weather condition data

        Returns:
            Weather conditions string or icon based on settings
        """
        logger.debug("Processing weather conditions overlay generation")

        # Check display preference - default to icon if weather_icon is available
        display_mode = overlay_item.settings.get(
            "conditions_display", "icon"
        )  # "icon" or "text"

        # Try to use weather icon first if available and preferred
        if display_mode == "icon" and context.weather_icon:
            logger.debug(f"Using weather icon: {context.weather_icon}")
            icon = self._get_weather_icon_emoji(context.weather_icon)
            if icon:
                logger.debug("Weather conditions icon overlay generated successfully")
                return icon

        # Fall back to text conditions
        if not context.weather_conditions:
            logger.warning("Weather conditions data not available, using fallback")
            return "N/A"  # Graceful fallback

        logger.debug(f"Raw weather conditions: '{context.weather_conditions}'")

        # Return conditions as-is, with basic cleanup
        conditions = context.weather_conditions.strip()

        # Capitalize first letter if needed
        if conditions and conditions[0].islower():
            logger.debug("Capitalizing first letter of conditions")
            conditions = conditions[0].upper() + conditions[1:]

        logger.debug("Weather conditions text overlay generated successfully")
        return conditions

    def _get_weather_icon_emoji(self, icon_code: str) -> str:
        """
        Convert OpenWeather icon code to emoji.

        Args:
            icon_code: OpenWeather icon code (e.g., "01d", "02n")

        Returns:
            Weather emoji string
        """
        # OpenWeather icon codes mapping to emoji
        icon_map = {
            "01d": "☀️",  # clear sky day
            "01n": "🌙",  # clear sky night
            "02d": "⛅",  # few clouds day
            "02n": "☁️",  # few clouds night
            "03d": "☁️",  # scattered clouds
            "03n": "☁️",  # scattered clouds
            "04d": "☁️",  # broken clouds
            "04n": "☁️",  # broken clouds
            "09d": "🌧️",  # shower rain
            "09n": "🌧️",  # shower rain
            "10d": "🌦️",  # rain day
            "10n": "🌧️",  # rain night
            "11d": "⛈️",  # thunderstorm
            "11n": "⛈️",  # thunderstorm
            "13d": "❄️",  # snow
            "13n": "❄️",  # snow
            "50d": "🌫️",  # mist
            "50n": "🌫️",  # mist
        }

        emoji = icon_map.get(icon_code, "🌤️")  # default to partly sunny
        logger.debug(f"Mapped icon code '{icon_code}' to emoji '{emoji}'")
        return emoji

    def _generate_temp_and_conditions(
        self, overlay_item: OverlayItem, context: OverlayGenerationContext
    ) -> str:
        """
        Generate combined temperature and conditions content.

        Args:
            overlay_item: Combined weather overlay configuration
            context: Generation context with weather data

        Returns:
            Combined temperature and conditions string
        """
        logger.debug(
            "🌤️ Processing combined temperature and conditions overlay generation"
        )

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

        logger.debug("✅ Combined weather overlay generated successfully")
        return result

    def _convert_temperature(
        self, temperature: float, from_unit: str, to_unit: str
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
            converted = (temperature * 9 / 5) + 32
            logger.debug(f"🌡️ Celsius to Fahrenheit: {temperature}°C → {converted}°F")
            return converted
        elif from_unit == "F" and to_unit == "C":
            # Fahrenheit to Celsius: C = (F - 32) × 5/9
            converted = (temperature - 32) * 5 / 9
            logger.debug(f"🌡️ Fahrenheit to Celsius: {temperature}°F → {converted}°C")
            return converted
        else:
            # Unknown unit conversion, return original
            logger.warning(
                f"Unknown unit conversion {from_unit} → {to_unit}, returning original value"
            )
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
            unit = overlay_item.settings.get("unit")
            if unit:
                validated_unit = validate_temperature_unit(unit)
                if validated_unit:
                    logger.debug(f"🌡️ Validated temperature unit: {validated_unit}")

            # Validate display format
            display = overlay_item.settings.get("display")
            if display:
                validated_display = validate_display_format(display)
                if validated_display:
                    logger.debug(f"🎨 Validated display format: {validated_display}")

        except ValueError as e:
            logger.error(f"Weather validation failed: {e}")
            raise

        # Type-specific validation
        if overlay_item.type in ["temperature", "weather"]:
            logger.debug("🌡️ Temperature-based overlay validation")
            # These types should have unit preference
            unit = overlay_item.settings.get("unit")
            if not unit and overlay_item.type == "temperature":
                logger.debug("🌡️ No unit specified, will use default from context")
                # Will use default from context, no error needed
                pass
            elif unit:
                logger.debug(f"🌡️ Unit specified: {unit}")

        if overlay_item.type in ["weather_conditions", "weather"]:
            logger.debug("🌤️ Weather conditions overlay validation")
            # These types require weather conditions data at runtime
            # Can't validate here without context, will check at generation time
            pass

        logger.debug(
            f"✅ Weather overlay validation completed for type: {overlay_item.type}"
        )
        unit = overlay_item.settings.get("unit")
        display = overlay_item.settings.get("display")
        if unit:
            logger.debug(f"🌡️ Temperature unit: {unit}")
        if display:
            logger.debug(f"🎨 Display format: {display}")
