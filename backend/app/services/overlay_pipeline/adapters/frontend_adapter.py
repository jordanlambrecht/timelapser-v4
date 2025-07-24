# backend/app/services/overlay_pipeline/adapters/frontend_adapter.py
"""
Frontend Adapter - Transforms frontend overlay JSON to backend OverlayConfiguration format.

This adapter bridges the gap between frontend and backend data structures:
- Frontend: overlayItems array with position property
- Backend: overlayPositions dict with GridPosition keys

Provides backward compatibility with existing overlay configurations.
"""

from typing import Dict, Any, List, Optional
from loguru import logger

from ....models.overlay_model import (
    OverlayConfiguration,
    OverlayItem, 
    GlobalOverlayOptions,
    GridPosition
)


class FrontendOverlayAdapter:
    """
    Adapter for transforming frontend overlay configurations to backend format.
    
    Handles type differences between frontend and backend overlay data:
    - Frontend overlay type mappings → Backend overlay type constants
    - Frontend unit/display format mappings → Backend property values
    - Validation and error handling for malformed configurations
    """
    
    @staticmethod
    def transform_frontend_config(frontend_data: Dict[str, Any]) -> OverlayConfiguration:
        """
        Transform frontend overlay configuration to backend OverlayConfiguration.
        
        Args:
            frontend_data: Frontend JSON structure with overlayPositions and globalOptions
            
        Returns:
            Backend OverlayConfiguration ready for processing
            
        Example frontend_data:
        {
            "overlayPositions": {
                "topLeft": {
                    "type": "date_time",
                    "textSize": 16,
                    "textColor": "#FFFFFF",
                    "backgroundOpacity": 0,
                    "imageScale": 100,
                    "dateFormat": "MM/dd/yyyy HH:mm"
                }
            },
            "globalOptions": {
                "opacity": 90,
                "dropShadow": 3,
                "font": "Arial", 
                "xMargin": 25,
                "yMargin": 25
            }
        }
        """
        try:
            # Extract global options (frontend sends "globalOptions", not "globalSettings")
            global_options_data = frontend_data.get("globalOptions", {})
            global_options = FrontendOverlayAdapter._transform_global_options(global_options_data)
            
            # Extract and transform overlay positions
            overlay_positions_data = frontend_data.get("overlayPositions", {})
            overlay_positions = FrontendOverlayAdapter._transform_overlay_positions(
                overlay_positions_data, global_options
            )
            
            return OverlayConfiguration(
                overlayPositions=overlay_positions,
                globalOptions=global_options
            )
            
        except Exception as e:
            logger.error(f"Failed to transform frontend overlay configuration: {e}")
            logger.debug(f"Frontend data: {frontend_data}")
            raise ValueError(f"Invalid frontend overlay configuration: {e}")
    
    @staticmethod
    def _transform_global_options(global_options: Dict[str, Any]) -> GlobalOverlayOptions:
        """Transform frontend globalOptions to backend GlobalOverlayOptions."""
        return GlobalOverlayOptions(
            opacity=global_options.get("opacity", 100),
            font=global_options.get("font", "Arial"),
            xMargin=global_options.get("xMargin", 20),
            yMargin=global_options.get("yMargin", 20),
            backgroundColor=global_options.get("backgroundColor", "#000000"),
            backgroundOpacity=global_options.get("backgroundOpacity", 50),
            fillColor=global_options.get("fillColor", "#FFFFFF"),
            dropShadow=global_options.get("dropShadow", 2),
            preset=global_options.get("preset")
        )
    
    @staticmethod
    def _transform_overlay_positions(
        overlay_positions_data: Dict[str, Any], 
        global_options: GlobalOverlayOptions
    ) -> Dict[GridPosition, OverlayItem]:
        """Transform frontend overlayPositions dict to backend overlayPositions dict."""
        overlay_positions = {}
        
        for position_str, item_data in overlay_positions_data.items():
            try:
                # Validate grid position
                if position_str not in ["topLeft", "topCenter", "topRight", 
                                      "centerLeft", "center", "centerRight",
                                      "bottomLeft", "bottomCenter", "bottomRight"]:
                    logger.warning(f"Invalid grid position: {position_str}")
                    continue
                
                grid_position: GridPosition = position_str
                
                # Transform item data
                overlay_item = FrontendOverlayAdapter._transform_overlay_item(
                    item_data, global_options
                )
                
                overlay_positions[grid_position] = overlay_item
                
            except Exception as e:
                logger.error(f"Failed to transform overlay item at {position_str}: {item_data}, error: {e}")
                continue
        
        return overlay_positions
    
    @staticmethod
    def _transform_overlay_item(
        item_data: Dict[str, Any], 
        global_options: GlobalOverlayOptions
    ) -> OverlayItem:
        """Transform individual frontend overlay item to backend OverlayItem."""
        frontend_type = item_data["type"]
        
        # Map frontend overlay types to backend types
        type_mapping = {
            # Frontend differences
            "date_only": "date",           # Frontend "date_only" -> backend "date"
            "time_only": "time",           # Frontend "time_only" -> backend "time"
            # These should map directly (but confirm they match)
            "date_time": "date_time",
            "frame_number": "frame_number", 
            "day_number": "day_number",
            "timelapse_name": "timelapse_name",
            "custom_text": "custom_text",
            "temperature": "temperature",
            "weather_conditions": "weather_conditions",
            "weather_temp_conditions": "weather_temp_conditions",
            "watermark": "watermark"
        }
        
        backend_type = type_mapping.get(frontend_type, frontend_type)
        
        # Handle frontend unit mapping for weather (if frontend sends full names)
        unit = item_data.get("unit")
        unit_mapping = {"Celsius": "C", "Fahrenheit": "F"}
        if unit in unit_mapping:
            unit = unit_mapping[unit]
        
        # Handle frontend display mapping for weather (if frontend uses different names)
        display = item_data.get("display")
        display_mapping = {
            "both": "temp_and_conditions",
            "temp_only": "temp_only", 
            "conditions_only": "conditions_only",
            "temp_and_conditions": "temp_and_conditions"  # Direct mapping
        }
        if display in display_mapping:
            display = display_mapping[display]
        
        # Create overlay item from frontend data
        # Most properties should map directly since frontend mirrors backend structure
        return OverlayItem(
            type=backend_type,
            
            # Required properties (frontend sends these directly)
            textSize=item_data.get("textSize", 16),
            textColor=item_data.get("textColor", global_options.fillColor),
            backgroundOpacity=item_data.get("backgroundOpacity", 0),
            imageScale=item_data.get("imageScale", 100),
            
            # Optional properties that may be present
            customText=item_data.get("customText"),
            backgroundColor=item_data.get("backgroundColor"),
            dateFormat=item_data.get("dateFormat", "MM/dd/yyyy HH:mm"),
            imageUrl=item_data.get("imageUrl"),
            
            # New frontend properties
            enableBackground=item_data.get("enableBackground"),
            unit=unit,
            display=display,
            leadingZeros=item_data.get("leadingZeros"),
            hidePrefix=item_data.get("hidePrefix")
        )
    
    @staticmethod
    def is_legacy_format(config_data: Dict[str, Any]) -> bool:
        """
        Check if the configuration is already in proper backend format.
        
        Frontend format has overlayPositions dict with untransformed types.
        Backend format has overlayPositions dict with transformed types and proper validation.
        """
        # For now, we'll assume we always need to transform since we need type mapping
        # A more sophisticated check could validate if types are already transformed
        return False
    
    @staticmethod
    def handle_legacy_config(config_data: Dict[str, Any]) -> OverlayConfiguration:
        """
        Handle legacy backend configuration format for backward compatibility.
        
        Args:
            config_data: Legacy OverlayConfiguration dict format
            
        Returns:
            OverlayConfiguration object
        """
        try:
            # Direct instantiation from legacy format
            return OverlayConfiguration(**config_data)
        except Exception as e:
            logger.error(f"Failed to parse legacy overlay configuration: {e}")
            raise ValueError(f"Invalid legacy overlay configuration: {e}")


def transform_overlay_config(config_data: Dict[str, Any]) -> OverlayConfiguration:
    """
    Main entry point for overlay configuration transformation.
    
    Automatically detects frontend vs legacy format and transforms accordingly.
    
    Args:
        config_data: Either frontend or legacy backend format
        
    Returns:
        Backend OverlayConfiguration ready for processing
    """
    if FrontendOverlayAdapter.is_legacy_format(config_data):
        logger.debug("Processing legacy overlay configuration format")
        return FrontendOverlayAdapter.handle_legacy_config(config_data)
    else:
        logger.debug("Processing frontend overlay configuration format")
        return FrontendOverlayAdapter.transform_frontend_config(config_data)