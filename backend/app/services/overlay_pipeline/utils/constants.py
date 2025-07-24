# backend/app/services/overlay_pipeline/utils/constants.py
"""
Overlay Pipeline Constants - Additional constants specific to pipeline implementation.

This supplements the main constants.py with pipeline-specific values.
"""

# Import main overlay constants
from ....constants import (
    # Overlay types
    OVERLAY_TYPE_DATE,
    OVERLAY_TYPE_DATE_TIME,
    OVERLAY_TYPE_TIME,
    OVERLAY_TYPE_FRAME_NUMBER,
    OVERLAY_TYPE_DAY_NUMBER,
    OVERLAY_TYPE_CUSTOM_TEXT,
    OVERLAY_TYPE_TIMELAPSE_NAME,
    OVERLAY_TYPE_TEMPERATURE,
    OVERLAY_TYPE_WEATHER_CONDITIONS,
    OVERLAY_TYPE_WEATHER_TEMP_CONDITIONS,
    OVERLAY_TYPE_WATERMARK,
    # Positions
    OVERLAY_POSITION_TOP_LEFT,
    OVERLAY_POSITION_TOP_RIGHT,
    OVERLAY_POSITION_BOTTOM_LEFT,
    OVERLAY_POSITION_BOTTOM_RIGHT,
    OVERLAY_POSITION_CENTER,
)

# Grid position mapping (kebab-case to camelCase for model compatibility)
POSITION_MAPPING = {
    "top-left": "topLeft",
    "top-center": "topCenter",
    "top-right": "topRight",
    "center-left": "centerLeft",
    "center": "center",
    "center-right": "centerRight",
    "bottom-left": "bottomLeft",
    "bottom-center": "bottomCenter",
    "bottom-right": "bottomRight",
}

# Additional positions not in main constants
OVERLAY_POSITION_TOP_CENTER = "top-center"
OVERLAY_POSITION_CENTER_LEFT = "center-left"
OVERLAY_POSITION_CENTER_RIGHT = "center-right"
OVERLAY_POSITION_BOTTOM_CENTER = "bottom-center"

# Default Values
DEFAULT_OVERLAY_OPACITY = 100
DEFAULT_OVERLAY_FONT_SIZE = 24
DEFAULT_OVERLAY_FONT_FAMILY = "Arial"
DEFAULT_OVERLAY_COLOR = "#FFFFFF"
DEFAULT_OVERLAY_X_MARGIN = 20
DEFAULT_OVERLAY_Y_MARGIN = 20

# File Extensions
OVERLAY_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]
OVERLAY_FONT_EXTENSIONS = [".ttf", ".otf"]

# Performance Limits
MAX_OVERLAY_IMAGE_SIZE_MB = 10
MAX_OVERLAY_RESOLUTION = (4096, 4096)
OVERLAY_CACHE_TTL_SECONDS = 300