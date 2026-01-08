"""Dependency injection container for service initialization (NEM-1636).

This module provides a lightweight DI container that replaces global singleton
patterns with a centralized dependency management system.

Key Features:
- Singleton and factory service patterns
- Async service initialization
- Dependency resolution with circular dependency detection
- FastAPI Depends() integration
- Thread-safe concurrent access
- Service override for testing
- Graceful shutdown with cleanup

Usage:
    # Get the global container
    container = get_container()

    # Register services
    container.register_singleton("my_service", MyService)
    container.register_async_singleton("async_service", async_factory)

    # Get services
    service = container.get("my_service")
    async_service = await container.get_async("async_service")

    # FastAPI integration
    @app.get("/")
    async def endpoint(service: MyService = Depends(container.get_dependency("my_service"))):
        ...
"""

__all__ = [
    "CircularDependencyError",
    "Container",
    "ServiceAlreadyRegisteredError",
    "ServiceNotFoundError",
    "get_container",
    "reset_container",
    "wire_services",
]

import asyncio
import inspect
from collections.abc import AsyncGenerator, Callable
from typing import Any, TypeVar

from backend.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class ServiceNotFoundError(Exception):
    """Raised when a requested service is not registered."""

    def __init__(self, service_name: str) -> None:
        super().__init__(f"Service '{service_name}' not found in container")
        self.service_name = service_name


class ServiceAlreadyRegisteredError(Exception):
    """Raised when attempting to register a service that already exists."""

    def __init__(self, service_name: str) -> None:
        super().__init__(f"Service '{service_name}' is already registered")
        self.service_name = service_name


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected during resolution."""

    def __init__(self, service_name: str, resolution_stack: list[str]) -> None:
        chain = " -> ".join([*resolution_stack, service_name])
        super().__init__(f"Circular dependency detected: {chain}")
        self.service_name = service_name
        self.resolution_stack = resolution_stack


class ServiceRegistration:
    """Holds registration information for a service."""

    def __init__(
        self,
        factory: Callable[[], Any],
        *,
        is_singleton: bool = True,
        is_async: bool = False,
    ) -> None:
        self.factory = factory
        self.is_singleton = is_singleton
        self.is_async = is_async
        self.instance: Any = None


class Container:
    """Dependency injection container for managing service lifecycles.

    This container provides centralized service management with support for:
    - Singleton services (created once, reused)
    - Factory services (new instance each time)
    - Async service initialization
    - FastAPI dependency injection integration
    - Thread-safe concurrent access
    - Service override for testing
    """

    def __init__(self) -> None:
        """Initialize the container."""
        self._registrations: dict[str, ServiceRegistration] = {}
        self._overrides: dict[str, Any] = {}
        self._resolution_stack: list[str] = []
        self._async_locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    @property
    def registered_services(self) -> list[str]:
        """Return list of registered service names."""
        return list(self._registrations.keys())

    def register_singleton(
        self,
        name: str,
        factory: Callable[[], T] | type[T],
    ) -> None:
        """Register a singleton service.

        The factory is called once on first access, and the same instance
        is returned for all subsequent requests.

        Args:
            name: Unique name for the service
            factory: Callable that creates the service instance, or a class

        Raises:
            ServiceAlreadyRegisteredError: If service name is already registered
        """
        if name in self._registrations:
            raise ServiceAlreadyRegisteredError(name)

        self._registrations[name] = ServiceRegistration(
            factory=factory,
            is_singleton=True,
            is_async=False,
        )
        logger.debug(f"Registered singleton service: {name}")

    def register_factory(
        self,
        name: str,
        factory: Callable[[], T],
    ) -> None:
        """Register a factory service.

        The factory is called on every access, creating a new instance each time.

        Args:
            name: Unique name for the service
            factory: Callable that creates new service instances

        Raises:
            ServiceAlreadyRegisteredError: If service name is already registered
        """
        if name in self._registrations:
            raise ServiceAlreadyRegisteredError(name)

        self._registrations[name] = ServiceRegistration(
            factory=factory,
            is_singleton=False,
            is_async=False,
        )
        logger.debug(f"Registered factory service: {name}")

    def register_async_singleton(
        self,
        name: str,
        factory: Callable[[], Any],
    ) -> None:
        """Register an async singleton service.

        The async factory is awaited once on first access, and the same instance
        is returned for all subsequent requests.

        Args:
            name: Unique name for the service
            factory: Async callable that creates the service instance

        Raises:
            ServiceAlreadyRegisteredError: If service name is already registered
        """
        if name in self._registrations:
            raise ServiceAlreadyRegisteredError(name)

        self._registrations[name] = ServiceRegistration(
            factory=factory,
            is_singleton=True,
            is_async=True,
        )
        self._async_locks[name] = asyncio.Lock()
        logger.debug(f"Registered async singleton service: {name}")

    def _check_circular_dependency(self, name: str) -> None:
        """Check for circular dependencies during resolution.

        Args:
            name: Service name being resolved

        Raises:
            CircularDependencyError: If circular dependency detected
        """
        if name in self._resolution_stack:
            raise CircularDependencyError(name, self._resolution_stack.copy())

    def get(self, name: str) -> Any:
        """Get a synchronous service by name.

        Args:
            name: Service name to retrieve

        Returns:
            Service instance

        Raises:
            ServiceNotFoundError: If service is not registered
            CircularDependencyError: If circular dependency detected
        """
        # Check for override first
        if name in self._overrides:
            return self._overrides[name]

        if name not in self._registrations:
            raise ServiceNotFoundError(name)

        registration = self._registrations[name]

        if registration.is_async:
            raise RuntimeError(f"Service '{name}' is async. Use get_async() instead.")

        # Check for circular dependencies
        self._check_circular_dependency(name)

        # For singletons, return existing instance if available
        if registration.is_singleton and registration.instance is not None:
            return registration.instance

        # Track resolution for circular dependency detection
        self._resolution_stack.append(name)
        try:
            instance = registration.factory()

            # Store singleton instance
            if registration.is_singleton:
                registration.instance = instance

            return instance
        finally:
            self._resolution_stack.pop()

    async def get_async(self, name: str) -> Any:
        """Get an async service by name.

        Thread-safe: Uses asyncio.Lock to ensure singleton is only
        created once even with concurrent access.

        Args:
            name: Service name to retrieve

        Returns:
            Service instance

        Raises:
            ServiceNotFoundError: If service is not registered
            CircularDependencyError: If circular dependency detected
        """
        # Check for override first
        if name in self._overrides:
            return self._overrides[name]

        if name not in self._registrations:
            raise ServiceNotFoundError(name)

        registration = self._registrations[name]

        # For singletons, return existing instance if available (fast path)
        if registration.is_singleton and registration.instance is not None:
            return registration.instance

        # Use lock for thread-safe singleton initialization
        lock = self._async_locks.get(name)
        if lock is None:
            async with self._global_lock:
                if name not in self._async_locks:
                    self._async_locks[name] = asyncio.Lock()
                lock = self._async_locks[name]

        async with lock:
            # Double-check after acquiring lock
            if registration.is_singleton and registration.instance is not None:
                return registration.instance

            # Check for circular dependencies
            self._check_circular_dependency(name)

            # Track resolution for circular dependency detection
            self._resolution_stack.append(name)
            try:
                if registration.is_async:
                    instance = await registration.factory()
                else:
                    instance = registration.factory()

                # Store singleton instance
                if registration.is_singleton:
                    registration.instance = instance

                return instance
            finally:
                self._resolution_stack.pop()

    def get_dependency(
        self,
        name: str,
    ) -> Callable[[], AsyncGenerator[Any]]:
        """Get a FastAPI-compatible dependency factory.

        Returns an async generator function that yields the service,
        compatible with FastAPI's Depends() pattern.

        Args:
            name: Service name to create dependency for

        Returns:
            Async generator factory for FastAPI Depends()
        """

        async def dependency() -> AsyncGenerator[Any]:
            registration = self._registrations.get(name)
            if registration is not None and registration.is_async:
                service = await self.get_async(name)
            else:
                service = self.get(name)
            yield service

        return dependency

    def override(self, name: str, instance: Any) -> None:
        """Override a service with a specific instance.

        Useful for testing - the override takes precedence over
        the registered service.

        Args:
            name: Service name to override
            instance: Instance to return instead of creating
        """
        self._overrides[name] = instance
        logger.debug(f"Service override set: {name}")

    def clear_override(self, name: str) -> None:
        """Clear an override, restoring the original service.

        Args:
            name: Service name to restore
        """
        if name in self._overrides:
            del self._overrides[name]
            logger.debug(f"Service override cleared: {name}")

    def clear_all_overrides(self) -> None:
        """Clear all service overrides."""
        self._overrides.clear()
        logger.debug("All service overrides cleared")

    async def shutdown(self) -> None:
        """Shutdown all services gracefully.

        Calls close() or disconnect() on services that have these methods.
        Useful for cleanup during application shutdown.
        """
        logger.info("Container shutdown initiated")
        for name, registration in self._registrations.items():
            if registration.instance is not None:
                instance = registration.instance
                # Try close() method (common pattern)
                if hasattr(instance, "close"):
                    try:
                        if inspect.iscoroutinefunction(instance.close):
                            await instance.close()
                        else:
                            instance.close()
                        logger.debug(f"Closed service: {name}")
                    except Exception as e:
                        logger.warning(f"Error closing service {name}: {e}")
                # Try disconnect() method (Redis pattern)
                elif hasattr(instance, "disconnect"):
                    try:
                        if inspect.iscoroutinefunction(instance.disconnect):
                            await instance.disconnect()
                        else:
                            instance.disconnect()
                        logger.debug(f"Disconnected service: {name}")
                    except Exception as e:
                        logger.warning(f"Error disconnecting service {name}: {e}")

                # Clear the instance
                registration.instance = None

        logger.info("Container shutdown complete")


# Global container instance
_container: Container | None = None


def get_container() -> Container:
    """Get the global container instance.

    Creates the container on first call (lazy initialization).

    Returns:
        Global Container instance
    """
    global _container  # noqa: PLW0603
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Reset the global container.

    Creates a new container instance, useful for testing.
    """
    global _container  # noqa: PLW0603
    _container = None


async def wire_services(container: Container) -> None:
    """Wire up all application services in the container.

    This function registers all services with their dependencies:
    - RedisClient (async singleton)
    - ContextEnricher (singleton)
    - EnrichmentPipeline (async singleton, depends on Redis)
    - NemotronAnalyzer (async singleton, depends on Redis, ContextEnricher, EnrichmentPipeline)
    - DetectorClient (singleton)

    Args:
        container: Container to wire services into
    """
    from backend.core.redis import RedisClient
    from backend.services.context_enricher import ContextEnricher
    from backend.services.detector_client import DetectorClient
    from backend.services.enrichment_pipeline import EnrichmentPipeline
    from backend.services.nemotron_analyzer import NemotronAnalyzer

    # RedisClient - async singleton (needs connect())
    async def redis_factory() -> RedisClient:
        client = RedisClient()
        await client.connect()
        return client

    container.register_async_singleton("redis_client", redis_factory)

    # ContextEnricher - sync singleton (no dependencies)
    container.register_singleton("context_enricher", ContextEnricher)

    # EnrichmentPipeline - async singleton (depends on Redis)
    async def pipeline_factory() -> EnrichmentPipeline:
        redis = await container.get_async("redis_client")
        return EnrichmentPipeline(redis_client=redis)

    container.register_async_singleton("enrichment_pipeline", pipeline_factory)

    # NemotronAnalyzer - async singleton (depends on Redis, ContextEnricher, EnrichmentPipeline)
    async def analyzer_factory() -> NemotronAnalyzer:
        redis = await container.get_async("redis_client")
        enricher = container.get("context_enricher")
        pipeline = await container.get_async("enrichment_pipeline")
        return NemotronAnalyzer(
            redis_client=redis,
            context_enricher=enricher,
            enrichment_pipeline=pipeline,
        )

    container.register_async_singleton("nemotron_analyzer", analyzer_factory)

    # DetectorClient - sync singleton (no dependencies that need injection)
    container.register_singleton("detector_client", DetectorClient)

    logger.info("All services wired in container")
