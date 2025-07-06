"""
Utility functions for Timelapser V4

This module provides utility functions for various system components including
corruption detection, file management, conversion utilities, and other helper functions.
"""

# Corruption detection utilities are in corruption_detection_utils.py
# Conversion utilities for safe type conversions
from .conversion_utils import safe_int, safe_float, safe_bool, safe_str

# Make commonly used utilities easily available
__all__ = [
    'safe_int',
    'safe_float', 
    'safe_bool',
    'safe_str'
]
