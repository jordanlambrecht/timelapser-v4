# backend/app/dependencies/registry.py
"""
Service Registry for managing singleton services.

This replaces the global variables pattern used in the original dependencies.py
with a proper registry system that handles lifecycle management.
"""

from typing import Any, TypeVar, Callable
from threading import Lock

T = TypeVar("T")


class ServiceRegistry:
    """
    Thread-safe singleton service registry.

    This class manages singleton services with proper lifecycle management,
    replacing the global variables pattern from the original dependencies.py.
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}
        self._factories: dict[str, Callable] = {}
        self._lock = Lock()

    def register_factory(self, service_name: str, factory: Callable) -> None:
        """
        Register a factory function for creating a service.

        Args:
            service_name: Unique name for the service
            factory: Factory function that creates the service
        """
        with self._lock:
            self._factories[service_name] = factory

    def get_service(self, service_name: str) -> Any:
        """
        Get a service instance, creating it if necessary.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            Service instance

        Raises:
            KeyError: If no factory is registered for the service
        """
        with self._lock:
            # Return existing instance if available
            if service_name in self._services:
                return self._services[service_name]

            # Create new instance using factory
            if service_name not in self._factories:
                raise KeyError(f"No factory registered for service: {service_name}")

            factory = self._factories[service_name]
            instance = factory()
            self._services[service_name] = instance
            return instance

    async def get_async_service(self, service_name: str) -> Any:
        """
        Get an async service instance, creating it if necessary.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            Service instance

        Raises:
            KeyError: If no factory is registered for the service
        """
        with self._lock:
            # Return existing instance if available
            if service_name in self._services:
                return self._services[service_name]

            # Create new instance using factory
            if service_name not in self._factories:
                raise KeyError(f"No factory registered for service: {service_name}")

            factory = self._factories[service_name]

        # Release lock before awaiting
        instance = await factory()

        with self._lock:
            # Check again in case another thread created it while we were awaiting
            if service_name in self._services:
                return self._services[service_name]

            self._services[service_name] = instance
            return instance

    def clear_service(self, service_name: str) -> None:
        """
        Clear a specific service from the registry.

        Args:
            service_name: Name of the service to clear
        """
        with self._lock:
            self._services.pop(service_name, None)

    def clear_all_services(self) -> None:
        """Clear all services from the registry."""
        with self._lock:
            self._services.clear()

    def is_registered(self, service_name: str) -> bool:
        """
        Check if a service factory is registered.

        Args:
            service_name: Name of the service to check

        Returns:
            True if factory is registered
        """
        with self._lock:
            return service_name in self._factories

    def is_instantiated(self, service_name: str) -> bool:
        """
        Check if a service instance exists.

        Args:
            service_name: Name of the service to check

        Returns:
            True if instance exists
        """
        with self._lock:
            return service_name in self._services

    def get_service_names(self) -> list[str]:
        """Get list of all registered service names."""
        with self._lock:
            return list(self._factories.keys())

    def get_instantiated_service_names(self) -> list[str]:
        """Get list of all instantiated service names."""
        with self._lock:
            return list(self._services.keys())

    def replace_service(self, service_name: str, instance: Any) -> None:
        """
        Replace an existing service instance (useful for testing).

        Args:
            service_name: Name of the service to replace
            instance: New service instance
        """
        with self._lock:
            self._services[service_name] = instance


# Global service registry instance
_service_registry = ServiceRegistry()


def get_registry() -> ServiceRegistry:
    """Get the global service registry instance."""
    return _service_registry


def register_singleton_factory(service_name: str, factory: Callable) -> None:
    """
    Register a factory for a singleton service.

    Args:
        service_name: Unique name for the service
        factory: Factory function that creates the service
    """
    _service_registry.register_factory(service_name, factory)


def get_singleton_service(service_name: str) -> Any:
    """
    Get a singleton service instance.

    Args:
        service_name: Name of the service

    Returns:
        Service instance
    """
    return _service_registry.get_service(service_name)


async def get_async_singleton_service(service_name: str) -> Any:
    """
    Get an async singleton service instance.

    Args:
        service_name: Name of the service

    Returns:
        Service instance
    """
    return await _service_registry.get_async_service(service_name)


def clear_singleton_services() -> None:
    """Clear all singleton services (for testing/restart)."""
    _service_registry.clear_all_services()


# Backwards compatibility with original global state management
_scheduler_worker_instance: Any = None


def set_scheduler_worker(scheduler_worker: Any) -> None:
    """Set the global scheduler worker instance (backwards compatibility)."""
    global _scheduler_worker_instance
    _scheduler_worker_instance = scheduler_worker
    # Also register in the new registry
    _service_registry.replace_service("scheduler_worker", scheduler_worker)


def get_scheduler_worker() -> Any:
    """Get the global scheduler worker instance (backwards compatibility)."""
    return _scheduler_worker_instance


def clear_settings_service_instances() -> None:
    """Clear singleton settings service instances (backwards compatibility)."""
    _service_registry.clear_service("async_settings_service")
    _service_registry.clear_service("sync_settings_service")
