# backend/app/utils/conversion_utils.py
"""
Conversion and Type Safety Utilities

This module provides safe conversion functions for common data type transformations
with proper error handling and defaults. These utilities help prevent crashes
from invalid data while maintaining clean, readable code.

Features:
- Safe integer conversion with fallback defaults
- Safe float conversion with fallback defaults
- Proper handling of None, empty strings, and invalid types
- Type hints for better development experience
"""

from typing import Optional, Any


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """
    Safely convert a value to int, returning default if conversion fails.

    This utility handles common edge cases like None values, empty strings,
    and invalid types gracefully without raising exceptions.

    Args:
        value: Value to convert to int (any type accepted)
        default: Default value to return if conversion fails

    Returns:
        int or None: Converted integer or default value

    Examples:
        >>> safe_int("123")
        123
        >>> safe_int("invalid", 0)
        0
        >>> safe_int(None)
        None
        >>> safe_int("", 42)
        42
    """
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Safely convert a value to float, returning default if conversion fails.

    Args:
        value: Value to convert to float (any type accepted)
        default: Default value to return if conversion fails

    Returns:
        float or None: Converted float or default value

    Examples:
        >>> safe_float("123.45")
        123.45
        >>> safe_float("invalid", 0.0)
        0.0
        >>> safe_float(None)
        None
    """
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any, default: Optional[bool] = None) -> Optional[bool]:
    """
    Safely convert a value to bool with string handling.

    Recognizes common string representations of boolean values:
    - "true", "yes", "1", "on" -> True
    - "false", "no", "0", "off" -> False

    Args:
        value: Value to convert to bool (any type accepted)
        default: Default value to return if conversion fails

    Returns:
        bool or None: Converted boolean or default value

    Examples:
        >>> safe_bool("true")
        True
        >>> safe_bool("false")
        False
        >>> safe_bool("invalid", False)
        False
    """
    if value is None or value == "":
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value_lower = value.lower().strip()
        if value_lower in ("true", "yes", "1", "on"):
            return True
        elif value_lower in ("false", "no", "0", "off"):
            return False
        else:
            return default

    try:
        # For numeric types, follow Python's bool conversion rules
        return bool(value)
    except (ValueError, TypeError):
        return default


def safe_str(
    value: Any, default: Optional[str] = None, max_length: Optional[int] = None
) -> Optional[str]:
    """
    Safely convert a value to string with optional length limiting.

    Args:
        value: Value to convert to string (any type accepted)
        default: Default value to return if conversion fails or value is None
        max_length: Maximum allowed string length (truncates if exceeded)

    Returns:
        str or None: Converted string or default value

    Examples:
        >>> safe_str(123)
        "123"
        >>> safe_str(None, "default")
        "default"
        >>> safe_str("toolong", None, 3)
        "too"
    """
    if value is None:
        return default

    try:
        result = str(value)
        if max_length is not None and len(result) > max_length:
            result = result[:max_length]
        return result
    except (ValueError, TypeError):
        return default


def sanitize_error_message(error: Exception, context: str = "operation") -> str:
    """
    Sanitize error messages to prevent information leakage.

    Args:
        error: The original exception
        context: Context description for generic error message

    Returns:
        Sanitized error message safe for external consumption
    """
    # List of sensitive patterns to avoid exposing
    sensitive_patterns = [
        "password",
        "secret",
        "key",
        "token",
        "auth",
        "database",
        "connection",
        "host",
        "port",
        "file not found",
        "no such file",
        "permission denied",
    ]

    error_str = str(error).lower()

    # Check if error contains sensitive information
    for pattern in sensitive_patterns:
        if pattern in error_str:
            return f"Internal error during {context}"

    # Return sanitized version of common errors
    if "not found" in error_str:
        return f"Resource not found during {context}"
    elif "permission" in error_str or "access" in error_str:
        return f"Access error during {context}"
    elif "timeout" in error_str:
        return f"Timeout during {context}"
    elif "connection" in error_str:
        return f"Service unavailable during {context}"
    else:
        # For other errors, return generic message
        return f"Error during {context}"
