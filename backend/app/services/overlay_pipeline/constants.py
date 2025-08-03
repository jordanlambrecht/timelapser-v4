# backend/app/services/overlay_pipeline/constants.py
"""
Overlay Pipeline Constants - Re-export from utils for cleaner imports.

This provides a convenient import path for overlay generators to access
constants without needing to know the utils structure.
"""

# Re-export all constants from utils for backwards compatibility
from .utils.constants import *

# Additional overlay pipeline constants
OVERLAY_PIPELINE_VERSION = "1.0.0"
OVERLAY_PIPELINE_NAME = "timelapser-overlay-pipeline"
