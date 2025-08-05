# backend/app/dependencies/base.py
"""
Base dependency factory classes that eliminate repetitive patterns.

These base classes provide common patterns used across all dependency injection
functions, reducing code duplication and ensuring consistency.
"""

from typing import TypeVar, Generic, Callable, Any, Optional, Dict, Type, Union
from abc import ABC, abstractmethod

T = TypeVar("T")


class BaseDependencyFactory(Generic[T], ABC):
    """
    Base factory for creating service dependencies with common patterns.

    This eliminates the repetitive patterns found in the original dependencies.py:
    - Inline imports to avoid circular dependencies
    - Singleton pattern management
    - Database dependency injection
    - Settings service integration
    - Error handling for missing dependencies
    """

    def __init__(
        self, service_module: str, service_class: str, singleton: bool = False
    ) -> None:
        """
        Initialize the dependency factory.

        Args:
            service_module: Module path for inline import (e.g., 'app.services.camera_service')
            service_class: Class name to import (e.g., 'CameraService')
            singleton: Whether to use singleton pattern
        """
        self.service_module = service_module
        self.service_class = service_class
        self.singleton = singleton
        self._instance: Optional[T] = None

    def _import_service_class(self) -> Union[Type[T], Callable]:
        """
        Import service class using inline imports to avoid circular dependencies.

        Returns:
            The imported service class or factory function
        """
        # Use __import__ for dynamic imports
        module = __import__(self.service_module, fromlist=[self.service_class])
        return getattr(module, self.service_class)

    def clear_singleton(self) -> None:
        """Clear singleton instance (for testing/restart)."""
        self._instance = None


class SyncDependencyFactory(BaseDependencyFactory[T], ABC):
    """Sync-specific dependency factory."""

    @abstractmethod
    def _create_service_instance(self, service_class: Union[Type[T], Callable]) -> T:
        """Create a sync service instance."""
        pass

    def get_service(self) -> T:
        """Get sync service instance, using singleton pattern if configured."""
        if self.singleton and self._instance is not None:
            return self._instance

        service_class = self._import_service_class()
        instance = self._create_service_instance(service_class)

        if self.singleton:
            self._instance = instance

        return instance


class AsyncDependencyFactory(BaseDependencyFactory[T], ABC):
    """Async-specific dependency factory."""

    @abstractmethod
    async def _create_service_instance(
        self, service_class: Union[Type[T], Callable]
    ) -> T:
        """Create an async service instance."""
        pass

    async def get_service(self) -> T:
        """Get async service instance, using singleton pattern if configured."""
        if self.singleton and self._instance is not None:
            return self._instance

        service_class = self._import_service_class()
        instance = await self._create_service_instance(service_class)

        if self.singleton:
            self._instance = instance

        return instance


class AsyncServiceFactory(AsyncDependencyFactory[T]):
    """
    Factory for async services that commonly need:
    - Async database dependency
    - Async settings service
    - Other async service dependencies
    """

    def __init__(
        self,
        service_module: str,
        service_class: str,
        singleton: bool = False,
        needs_settings: bool = True,
        needs_sync_db: bool = False,
        additional_deps: Optional[Dict[str, Callable]] = None,
    ) -> None:
        super().__init__(service_module, service_class, singleton)
        self.needs_settings = needs_settings
        self.needs_sync_db = needs_sync_db
        self.additional_deps = additional_deps or {}

    async def _create_service_instance(
        self, service_class: Union[Type[T], Callable]
    ) -> T:
        """Create async service with standard dependencies."""
        from ..database import async_db, sync_db

        kwargs: Dict[str, Any] = {"async_db": async_db}

        if self.needs_sync_db:
            kwargs["sync_db"] = sync_db

        if self.needs_settings:
            from .async_services import get_settings_service

            kwargs["settings_service"] = await get_settings_service()

        # Add any additional dependencies
        for dep_name, dep_factory in self.additional_deps.items():
            if callable(dep_factory):
                kwargs[dep_name] = await dep_factory()
            else:
                kwargs[dep_name] = dep_factory

        return service_class(**kwargs)


class SyncServiceFactory(SyncDependencyFactory[T]):
    """
    Factory for sync services that commonly need:
    - Sync database dependency
    - Sync settings service
    - Other sync service dependencies
    """

    def __init__(
        self,
        service_module: str,
        service_class: str,
        singleton: bool = False,
        needs_settings: bool = True,
        needs_async_db: bool = False,
        additional_deps: Optional[Dict[str, Callable]] = None,
    ) -> None:
        super().__init__(service_module, service_class, singleton)
        self.needs_settings = needs_settings
        self.needs_async_db = needs_async_db
        self.additional_deps = additional_deps or {}

    def _create_service_instance(self, service_class: Union[Type[T], Callable]) -> T:
        """Create sync service with standard dependencies."""
        from ..database import async_db, sync_db

        kwargs: Dict[str, Any] = {"sync_db": sync_db}

        if self.needs_async_db:
            kwargs["async_db"] = async_db

        if self.needs_settings:
            from .sync_services import get_sync_settings_service

            kwargs["settings_service"] = get_sync_settings_service()

        # Add any additional dependencies
        for dep_name, dep_factory in self.additional_deps.items():
            if callable(dep_factory):
                kwargs[dep_name] = dep_factory()
            else:
                kwargs[dep_name] = dep_factory

        return service_class(**kwargs)


class PipelineFactory(SyncDependencyFactory[T]):
    """
    Factory for pipeline services that use factory functions instead of direct instantiation.
    """

    def __init__(
        self,
        factory_module: str,
        factory_function: str,
        factory_args: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Use the factory function name as service_class for consistency
        super().__init__(factory_module, factory_function, singleton=False)
        self.factory_args = factory_args or {}

    def _create_service_instance(self, service_class: Union[Type[T], Callable]) -> T:
        """Create service using factory function."""
        from ..database import async_db, sync_db

        # Cast service_class to Callable since PipelineFactory uses factory functions
        factory_function = service_class

        # Common factory arguments
        kwargs = self.factory_args.copy()

        # Add database arguments if not already specified
        if "async_database" not in kwargs and "sync_db" not in kwargs:
            # Determine which database to use based on factory function name
            if "async" in self.service_class.lower():
                kwargs["async_database"] = async_db
            else:
                kwargs["sync_db"] = sync_db

        return factory_function(**kwargs)

    def _import_service_class(self) -> Union[Type[T], Callable]:
        """Import factory function instead of class."""
        module = __import__(self.service_module, fromlist=[self.service_class])
        return getattr(module, self.service_class)
