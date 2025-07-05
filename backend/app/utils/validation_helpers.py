"""
Validation Helper Utilities

Centralized validation functions to eliminate code duplication and ensure
consistent validation across the application.
"""

import re
from typing import Optional

from ..constants import (
    DANGEROUS_CHARS,
    RTSP_URL_PATTERN,
    TIME_WINDOW_PATTERN,
    MIN_FPS,
    MAX_FPS,
    MAX_TIME_BOUNDS_SECONDS,
)


def validate_rtsp_url(url: Optional[str], allow_none: bool = False) -> Optional[str]:
    """
    Validate RTSP URL format and prevent injection attacks.
    
    Args:
        url: The RTSP URL to validate
        allow_none: Whether to allow None values (for optional fields)
        
    Returns:
        The validated URL string, or None if allow_none=True and url is None
        
    Raises:
        ValueError: If the URL is invalid or contains dangerous characters
    """
    if url is None:
        if allow_none:
            return None
        raise ValueError("RTSP URL cannot be None")
    
    if not url:
        raise ValueError("RTSP URL cannot be empty")

    # Must start with rtsp:// or rtsps://
    if not url.startswith(("rtsp://", "rtsps://")):
        raise ValueError("URL must start with rtsp:// or rtsps://")

    # Prevent injection attacks - no dangerous characters
    if any(char in url for char in DANGEROUS_CHARS):
        raise ValueError("RTSP URL contains invalid characters")

    # Basic URL format validation
    if not re.match(RTSP_URL_PATTERN, url):
        raise ValueError("Invalid RTSP URL format")

    return url


def validate_camera_name(name: Optional[str], allow_none: bool = False) -> Optional[str]:
    """
    Validate camera name is not empty or just whitespace.
    
    Args:
        name: The camera name to validate
        allow_none: Whether to allow None values (for optional fields)
        
    Returns:
        The validated and stripped name, or None if allow_none=True and name is None
        
    Raises:
        ValueError: If the name is invalid
    """
    if name is None:
        if allow_none:
            return None
        raise ValueError("Camera name cannot be None")
    
    if not name.strip():
        raise ValueError("Camera name cannot be empty or just whitespace")
    
    return name.strip()


def validate_time_window_format(time_str: Optional[str]) -> Optional[str]:
    """
    Validate time window format (HH:MM:SS).
    
    Args:
        time_str: Time string to validate
        
    Returns:
        The validated time string, or None if input is None
        
    Raises:
        ValueError: If the time format is invalid
    """
    if time_str is None:
        return None

    # Check format using regex - 24-hour format
    if not re.match(TIME_WINDOW_PATTERN, time_str):
        raise ValueError("Time must be in HH:MM:SS format (24-hour)")

    return time_str


def validate_fps_bounds(fps: int, min_fps: int = MIN_FPS, max_fps: int = MAX_FPS) -> int:
    """
    Validate FPS values are within reasonable bounds.
    
    Args:
        fps: FPS value to validate
        min_fps: Minimum allowed FPS
        max_fps: Maximum allowed FPS
        
    Returns:
        The validated FPS value
        
    Raises:
        ValueError: If FPS is outside allowed bounds
    """
    if fps < min_fps or fps > max_fps:
        raise ValueError(f"FPS must be between {min_fps} and {max_fps}")
    
    return fps


def validate_time_bounds(seconds: Optional[int], max_seconds: int = MAX_TIME_BOUNDS_SECONDS) -> Optional[int]:
    """
    Validate time bounds are reasonable.
    
    Args:
        seconds: Time value in seconds to validate
        max_seconds: Maximum allowed seconds
        
    Returns:
        The validated time value, or None if input is None
        
    Raises:
        ValueError: If time exceeds maximum
    """
    if seconds is not None and seconds > max_seconds:
        max_hours = max_seconds // 3600
        raise ValueError(f"Time limit cannot exceed {max_seconds} seconds ({max_hours} hour{'s' if max_hours != 1 else ''})")
    
    return seconds
