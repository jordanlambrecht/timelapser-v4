# backend/app/dependencies/global_state.py
"""
Global state management for backwards compatibility.

This module provides backwards compatibility with the original global state
management while transitioning to the new service registry system.
"""

# Re-export the functions from registry for backwards compatibility
from .registry import (
    clear_settings_service_instances,
    get_scheduler_worker,
    set_scheduler_worker,
)

__all__ = [
    "set_scheduler_worker",
    "get_scheduler_worker",
    "clear_settings_service_instances",
]
