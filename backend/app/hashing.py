# backend/app/utils.py
import hashlib
from typing import Optional


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using SHA-256

    Args:
        api_key: The API key to hash

    Returns:
        The SHA-256 hash of the API key as a hexadecimal string
    """
    if not api_key:
        return ""

    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """
    Verify an API key against a stored hash

    Args:
        api_key: The API key to verify
        stored_hash: The stored hash to compare against

    Returns:
        True if the API key matches the stored hash, False otherwise
    """
    if not api_key or not stored_hash:
        return False

    return hash_api_key(api_key) == stored_hash


def mask_api_key(api_key: str, show_chars: int = 4) -> str:
    """
    Mask an API key for display purposes

    Args:
        api_key: The API key to mask
        show_chars: Number of characters to show at the end

    Returns:
        Masked API key string
    """
    if not api_key:
        return ""

    if len(api_key) <= show_chars:
        return "*" * len(api_key)

    return "*" * (len(api_key) - show_chars) + api_key[-show_chars:]
