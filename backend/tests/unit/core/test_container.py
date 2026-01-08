"""Tests for dependency injection container (NEM-1636).

This module tests the DI container that replaces global singleton patterns
with a centralized dependency management system.

Test Strategy:
- Container initialization and lifecycle
- Service registration and retrieval
- Singleton vs factory patterns
- Dependency resolution for services
- FastAPI integration via Depends()
- Thread safety for concurrent access
"""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Note: These imports will fail until container.py is implemented (RED phase)
# This is expected in TDD - tests are written first


class TestContainerInitialization:
    """Tests for container initialization and lifecycle."""

    def test_container_can_be_created(self) -> None:
        """Container should be instantiable."""
        from backend.core.container import Container

        container = Container()
        assert container is not None

    def test_container_singleton_instance(self) -> None:
        """Global container instance should be a singleton."""
        from backend.core.container import get_container

        container1 = get_container()
        container2 = get_container()
        assert container1 is container2

    def test_container_can_be_reset(self) -> None:
        """Container should support reset for testing."""
        from backend.core.container import get_container, reset_container

        container1 = get_container()
        reset_container()
        container2 = get_container()
        assert container1 is not container2


class TestServiceRegistration:
    """Tests for service registration patterns."""

    def test_register_singleton_service(self) -> None:
        """Container should support registering singleton services."""
        from backend.core.container import Container

        container = Container()

        class MockService:
            pass

        container.register_singleton("mock_service", MockService)
        assert "mock_service" in container.registered_services

    def test_register_factory_service(self) -> None:
        """Container should support registering factory services."""
        from backend.core.container import Container

        container = Container()

        def factory() -> dict[str, str]:
            return {"created": "now"}

        container.register_factory("factory_service", factory)
        assert "factory_service" in container.registered_services

    def test_duplicate_registration_raises_error(self) -> None:
        """Registering the same service twice should raise an error."""
        from backend.core.container import Container, ServiceAlreadyRegisteredError

        container = Container()

        class MockService:
            pass

        container.register_singleton("mock_service", MockService)
        with pytest.raises(ServiceAlreadyRegisteredError):
            container.register_singleton("mock_service", MockService)


class TestServiceRetrieval:
    """Tests for service retrieval patterns."""

    def test_get_singleton_returns_same_instance(self) -> None:
        """Getting a singleton service should return the same instance."""
        from backend.core.container import Container

        container = Container()

        class MockService:
            def __init__(self) -> None:
                self.id = id(self)

        container.register_singleton("mock_service", MockService)

        service1 = container.get("mock_service")
        service2 = container.get("mock_service")
        assert service1 is service2
        assert service1.id == service2.id

    def test_get_factory_returns_new_instance(self) -> None:
        """Getting a factory service should return a new instance each time."""
        from backend.core.container import Container

        container = Container()

        class MockService:
            def __init__(self) -> None:
                self.id = id(self)

        container.register_factory("mock_service", MockService)

        service1 = container.get("mock_service")
        service2 = container.get("mock_service")
        assert service1 is not service2

    def test_get_unregistered_service_raises_error(self) -> None:
        """Getting an unregistered service should raise an error."""
        from backend.core.container import Container, ServiceNotFoundError

        container = Container()
        with pytest.raises(ServiceNotFoundError):
            container.get("nonexistent_service")


class TestAsyncServiceRetrieval:
    """Tests for async service retrieval."""

    @pytest.mark.asyncio
    async def test_get_async_singleton(self) -> None:
        """Container should support async service initialization."""
        from backend.core.container import Container

        container = Container()

        class AsyncService:
            _initialized = False

            async def initialize(self) -> None:
                await asyncio.sleep(0)  # Simulate async work
                self._initialized = True

        async def async_factory() -> AsyncService:
            service = AsyncService()
            await service.initialize()
            return service

        container.register_async_singleton("async_service", async_factory)

        service = await container.get_async("async_service")
        assert service._initialized is True

    @pytest.mark.asyncio
    async def test_get_async_returns_same_instance(self) -> None:
        """Async singleton should return the same instance."""
        from backend.core.container import Container

        container = Container()
        call_count = 0

        async def async_factory() -> dict[str, int]:
            nonlocal call_count
            call_count += 1
            return {"call": call_count}

        container.register_async_singleton("async_service", async_factory)

        service1 = await container.get_async("async_service")
        service2 = await container.get_async("async_service")
        assert service1 is service2
        assert call_count == 1  # Factory only called once


class TestDependencyResolution:
    """Tests for dependency resolution between services."""

    def test_resolve_service_with_dependencies(self) -> None:
        """Container should resolve service dependencies."""
        from backend.core.container import Container

        container = Container()

        class DatabaseClient:
            pass

        class Repository:
            def __init__(self, db: DatabaseClient) -> None:
                self.db = db

        container.register_singleton("database", DatabaseClient)
        container.register_singleton(
            "repository",
            lambda: Repository(container.get("database")),
        )

        repo = container.get("repository")
        assert isinstance(repo, Repository)
        assert isinstance(repo.db, DatabaseClient)

    def test_resolve_circular_dependency_raises_error(self) -> None:
        """Circular dependencies should raise an error."""
        from backend.core.container import CircularDependencyError, Container

        container = Container()

        # This test verifies that the container detects and prevents
        # circular dependencies during resolution
        container.register_singleton(
            "service_a",
            lambda: {"dep": container.get("service_b")},
        )
        container.register_singleton(
            "service_b",
            lambda: {"dep": container.get("service_a")},
        )

        with pytest.raises(CircularDependencyError):
            container.get("service_a")


class TestRedisClientIntegration:
    """Tests for RedisClient registration and retrieval."""

    @pytest.mark.asyncio
    async def test_redis_client_registered_as_async_singleton(self) -> None:
        """RedisClient should be available as an async singleton."""
        from backend.core.container import get_container, reset_container

        reset_container()
        container = get_container()

        # Mock Redis connection
        with patch("backend.core.redis.RedisClient") as MockRedisClient:
            mock_instance = AsyncMock()
            mock_instance.connect = AsyncMock()
            MockRedisClient.return_value = mock_instance

            # Wire up services
            from backend.core.container import wire_services

            await wire_services(container)

            # Get the service
            redis = await container.get_async("redis_client")
            assert redis is not None


class TestContextEnricherIntegration:
    """Tests for ContextEnricher registration and retrieval."""

    def test_context_enricher_registered_as_singleton(self) -> None:
        """ContextEnricher should be available as a singleton."""
        from backend.core.container import Container

        container = Container()

        with patch("backend.services.context_enricher.ContextEnricher") as MockEnricher:
            mock_instance = MagicMock()
            MockEnricher.return_value = mock_instance

            container.register_singleton("context_enricher", MockEnricher)
            enricher = container.get("context_enricher")
            assert enricher is mock_instance


class TestEnrichmentPipelineIntegration:
    """Tests for EnrichmentPipeline registration and retrieval."""

    @pytest.mark.asyncio
    async def test_enrichment_pipeline_depends_on_redis(self) -> None:
        """EnrichmentPipeline should be wired with RedisClient dependency."""
        from backend.core.container import Container

        container = Container()

        # Mock Redis
        mock_redis = AsyncMock()

        async def redis_factory() -> AsyncMock:
            return mock_redis

        container.register_async_singleton("redis_client", redis_factory)

        # Mock EnrichmentPipeline that depends on Redis
        with patch("backend.services.enrichment_pipeline.EnrichmentPipeline") as MockPipeline:
            mock_pipeline = MagicMock()
            MockPipeline.return_value = mock_pipeline

            async def pipeline_factory() -> MagicMock:
                redis = await container.get_async("redis_client")
                return MockPipeline(redis_client=redis)

            container.register_async_singleton("enrichment_pipeline", pipeline_factory)

            _pipeline = await container.get_async("enrichment_pipeline")
            MockPipeline.assert_called_once_with(redis_client=mock_redis)


class TestNemotronAnalyzerIntegration:
    """Tests for NemotronAnalyzer registration and retrieval."""

    @pytest.mark.asyncio
    async def test_nemotron_analyzer_depends_on_multiple_services(self) -> None:
        """NemotronAnalyzer should be wired with all its dependencies."""
        from backend.core.container import Container

        container = Container()

        # Mock dependencies
        mock_redis = AsyncMock()
        mock_enricher = MagicMock()
        mock_pipeline = MagicMock()

        async def redis_factory() -> AsyncMock:
            return mock_redis

        container.register_async_singleton("redis_client", redis_factory)
        container.register_singleton("context_enricher", lambda: mock_enricher)

        async def pipeline_factory() -> MagicMock:
            return mock_pipeline

        container.register_async_singleton("enrichment_pipeline", pipeline_factory)

        # Mock NemotronAnalyzer
        with patch("backend.services.nemotron_analyzer.NemotronAnalyzer") as MockAnalyzer:
            mock_analyzer = MagicMock()
            MockAnalyzer.return_value = mock_analyzer

            async def analyzer_factory() -> MagicMock:
                redis = await container.get_async("redis_client")
                enricher = container.get("context_enricher")
                pipeline = await container.get_async("enrichment_pipeline")
                return MockAnalyzer(
                    redis_client=redis,
                    context_enricher=enricher,
                    enrichment_pipeline=pipeline,
                )

            container.register_async_singleton("nemotron_analyzer", analyzer_factory)

            _analyzer = await container.get_async("nemotron_analyzer")
            MockAnalyzer.assert_called_once_with(
                redis_client=mock_redis,
                context_enricher=mock_enricher,
                enrichment_pipeline=mock_pipeline,
            )


class TestDetectorClientIntegration:
    """Tests for DetectorClient registration and retrieval."""

    def test_detector_client_registered_as_singleton(self) -> None:
        """DetectorClient should be available as a singleton."""
        from backend.core.container import Container

        container = Container()

        with patch("backend.services.detector_client.DetectorClient") as MockDetector:
            mock_instance = MagicMock()
            MockDetector.return_value = mock_instance

            container.register_singleton("detector_client", MockDetector)
            detector = container.get("detector_client")
            assert detector is mock_instance


class TestFastAPIDependencyIntegration:
    """Tests for FastAPI Depends() integration."""

    @pytest.mark.asyncio
    async def test_container_provides_fastapi_dependency(self) -> None:
        """Container should provide FastAPI-compatible dependencies."""
        from backend.core.container import Container

        container = Container()

        class MockService:
            value = "test"

        container.register_singleton("mock_service", MockService)

        # Simulate FastAPI Depends pattern
        async def get_mock_service() -> AsyncGenerator[MockService]:
            yield container.get("mock_service")

        # Verify the dependency works
        async for service in get_mock_service():
            assert service.value == "test"

    @pytest.mark.asyncio
    async def test_container_dependency_factory(self) -> None:
        """Container should provide dependency factory for FastAPI."""
        from backend.core.container import Container

        container = Container()

        class MockService:
            pass

        container.register_singleton("mock_service", MockService)

        # Get a dependency callable
        dep_factory = container.get_dependency("mock_service")

        # Use as FastAPI would
        async for service in dep_factory():
            assert isinstance(service, MockService)


class TestContainerShutdown:
    """Tests for container shutdown and cleanup."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_async_services(self) -> None:
        """Shutdown should close services with close/disconnect methods."""
        from backend.core.container import Container

        container = Container()

        mock_service = AsyncMock()
        mock_service.close = AsyncMock()

        async def factory() -> AsyncMock:
            return mock_service

        container.register_async_singleton("closeable_service", factory)

        # Initialize the service
        await container.get_async("closeable_service")

        # Shutdown
        await container.shutdown()

        mock_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_disconnect_method(self) -> None:
        """Shutdown should also handle disconnect() method (Redis pattern)."""
        from backend.core.container import Container

        container = Container()

        # Create a mock that only has disconnect (not close)
        # This simulates services that use disconnect() pattern like Redis
        class RedisLikeService:
            disconnect = AsyncMock()

        mock_service = RedisLikeService()

        async def factory() -> RedisLikeService:
            return mock_service

        container.register_async_singleton("redis_like_service", factory)

        # Initialize
        await container.get_async("redis_like_service")

        # Shutdown
        await container.shutdown()

        mock_service.disconnect.assert_called_once()


class TestThreadSafety:
    """Tests for thread-safe container access."""

    @pytest.mark.asyncio
    async def test_concurrent_singleton_access(self) -> None:
        """Concurrent access to singleton should return same instance."""
        from backend.core.container import Container

        container = Container()
        call_count = 0

        async def slow_factory() -> dict[str, int]:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate slow initialization
            return {"id": call_count}

        container.register_async_singleton("slow_service", slow_factory)

        # Concurrent access
        results = await asyncio.gather(
            container.get_async("slow_service"),
            container.get_async("slow_service"),
            container.get_async("slow_service"),
        )

        # All should be the same instance
        assert results[0] is results[1]
        assert results[1] is results[2]
        # Factory should only be called once
        assert call_count == 1


class TestContainerOverride:
    """Tests for service override (useful for testing)."""

    def test_override_singleton_for_testing(self) -> None:
        """Container should allow overriding services for testing."""
        from backend.core.container import Container

        container = Container()

        class RealService:
            name = "real"

        class MockService:
            name = "mock"

        container.register_singleton("service", RealService)

        # Override for testing
        container.override("service", MockService())

        service = container.get("service")
        assert service.name == "mock"

    def test_clear_override_restores_original(self) -> None:
        """Clearing override should restore original service."""
        from backend.core.container import Container

        container = Container()

        class RealService:
            name = "real"

        class MockService:
            name = "mock"

        container.register_singleton("service", RealService)
        container.override("service", MockService())

        # Clear override
        container.clear_override("service")

        service = container.get("service")
        assert service.name == "real"
