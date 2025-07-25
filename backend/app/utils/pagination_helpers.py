# backend/app/utils/pagination_helpers.py
"""
Pagination helper utilities for API responses.

Provides standardized pagination metadata creation to ensure
consistent pagination structure across all API endpoints.
"""

from typing import Dict, Any


def create_pagination_metadata(
    page: int, limit: int, total_pages: int, total_count: int
) -> Dict[str, Any]:
    """
    Create standardized pagination metadata for API responses.
    
    Args:
        page: Current page number (1-based)
        limit: Number of items per page
        total_pages: Total number of pages available
        total_count: Total number of items across all pages
        
    Returns:
        Dictionary with standardized pagination fields
    """
    return {
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "total_items": total_count,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


def calculate_pagination_params(page: int, page_size: int, total_count: int) -> Dict[str, Any]:
    """
    Calculate pagination parameters from input values.
    
    Args:
        page: Current page number (1-based)
        page_size: Number of items per page
        total_count: Total number of items
        
    Returns:
        Dictionary with calculated pagination parameters
    """
    total_pages = max(1, (total_count + page_size - 1) // page_size)  # Ceiling division
    offset = (page - 1) * page_size
    
    return {
        "total_pages": total_pages,
        "offset": offset,
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }