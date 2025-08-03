# backend/app/services/overlay_pipeline/adapters/frontend_adapter.py
"""
Frontend Adapter - Transforms frontend overlay JSON to backend OverlayConfiguration format.

This adapter bridges the gap between frontend and backend data structures:
- Frontend: overlayItems array with position property
- Backend: overlayPositions dict with GridPosition keys

Provides backward compatibility with existing overlay configurations.
"""

from typing import Dict, Any

from ....services.logger import get_service_logger
from ....enums import LoggerName, LogSource, OverlayGridPosition
from ....utils.enum_helpers import parse_enum

logger = get_service_logger(LoggerName.OVERLAY_PIPELINE, LogSource.PIPELINE)

from ....models.overlay_model import (
    OverlayConfiguration,
    OverlayItem,
    GlobalOverlayOptions,
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
    def transform_frontend_config(
        frontend_data: Dict[str, Any],
    ) -> OverlayConfiguration:
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
            global_options = FrontendOverlayAdapter._transform_global_options(
                global_options_data
            )

            # Extract and transform overlay positions
            overlay_positions_data = frontend_data.get("overlayPositions", {})
            overlay_positions = FrontendOverlayAdapter._transform_overlay_positions(
                overlay_positions_data, global_options
            )

            return OverlayConfiguration(
                overlayPositions=overlay_positions, globalOptions=global_options
            )

        except Exception as e:
            logger.error(
                "Failed to transform frontend overlay configuration", exception=e
            )
            logger.debug(f"Frontend data: {frontend_data}")
            raise ValueError(f"Invalid frontend overlay configuration: {e}")

    @staticmethod
    def _transform_global_options(
        global_options: Dict[str, Any],
    ) -> GlobalOverlayOptions:
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
            preset=global_options.get("preset"),
        )

    @staticmethod
    def _transform_overlay_positions(
        overlay_positions_data: Dict[str, Any], global_options: GlobalOverlayOptions
    ) -> Dict[OverlayGridPosition, OverlayItem]:
        """Transform frontend overlayPositions dict to backend overlayPositions dict."""
        overlay_positions = {}
        for position_str, item_data in overlay_positions_data.items():
            # Safely parse position string to GridPosition enum with fallback
            grid_position = parse_enum(
                OverlayGridPosition, position_str, default=OverlayGridPosition.TOP_LEFT
            )

            # Log if position needed fallback
            if grid_position.value != position_str:
                logger.warning(
                    f"Invalid grid position '{position_str}' converted to '{grid_position.value}'"
                )

            overlay_item = FrontendOverlayAdapter._transform_overlay_item(
                item_data, global_options
            )
            overlay_positions[grid_position] = overlay_item
        return overlay_positions

    @staticmethod
    def _transform_overlay_item(
        item_data: Dict[str, Any], global_options: GlobalOverlayOptions
    ) -> OverlayItem:
        """Transform individual frontend overlay item to backend OverlayItem."""
        # Directly assign frontend values, trusting input
        return OverlayItem(
            type=item_data["type"],
            textSize=item_data.get("textSize", 16),
            textColor=item_data.get("textColor", global_options.fillColor),
            backgroundOpacity=item_data.get("backgroundOpacity", 0),
            imageScale=item_data.get("imageScale", 100),
            customText=item_data.get("customText"),
            backgroundColor=item_data.get("backgroundColor"),
            dateFormat=item_data.get("dateFormat", "MM/dd/yyyy HH:mm"),
            imageUrl=item_data.get("imageUrl"),
            enableBackground=item_data.get("enableBackground"),
            unit=item_data.get("unit"),
            display=item_data.get("display"),
            leadingZeros=item_data.get("leadingZeros"),
            hidePrefix=item_data.get("hidePrefix"),
        )

    # @staticmethod
    # def handle_legacy_config(config_data: Dict[str, Any]) -> OverlayConfiguration:
    #     """
    #     Handle legacy backend configuration format for backward compatibility.

    #     Args:
    #         config_data: Legacy OverlayConfiguration dict format

    #     Returns:
    #         OverlayConfiguration object
    #     """
    #     try:
    #         # Direct instantiation from legacy format
    #         return OverlayConfiguration(**config_data)
    #     except Exception as e:
    #         logger.error("Failed to parse legacy overlay configuration", exception=e)
    #         raise ValueError(f"Invalid legacy overlay configuration: {e}")


def transform_overlay_config(config_data: Dict[str, Any]) -> OverlayConfiguration:
    """
    Main entry point for overlay configuration transformation.

    Automatically detects frontend vs legacy format and transforms accordingly.

    Args:
        config_data: Either frontend or legacy backend format

    Returns:
        Backend OverlayConfiguration ready for processing
    """
    # if FrontendOverlayAdapter.is_legacy_format(config_data):
    #     logger.debug("Processing legacy overlay configuration format")
    #     return FrontendOverlayAdapter.handle_legacy_config(config_data)
    # else:
    logger.debug("Processing frontend overlay configuration format")
    return FrontendOverlayAdapter.transform_frontend_config(config_data)
