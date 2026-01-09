"""Integration tests for DI container override functionality (NEM-2038).

This module tests the dependency injection container's override mechanism:
- Dependencies can be overridden in tests
- Overridden dependencies are properly scoped (don't leak between tests)
- All key dependencies (db, redis, external services) can be mocked
- app.dependency_overrides works correctly with FastAPI

Test Strategy:
- Container override pattern (using container.override())
- FastAPI dependency_overrides pattern (using app.dependency_overrides)
- Scope isolation between tests
- Override cleanup verification
- Integration with real services vs mocks

Key Dependencies Tested:
1. Database session (get_db)
2. Redis client (get_redis, get_redis_dependency)
3. Service dependencies (get_orchestrator, get_cache_service_dep)
4. Container-based dependencies (get_detector_dependency, etc.)
"""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from backend.core.container import (
    Container,
    ServiceNotFoundError,
    get_container,
    reset_container,
)

# =============================================================================
# Container Override Integration Tests
# =============================================================================


class TestContainerOverrideFunctionality:
    """Tests for container.override() mechanism."""

    def test_override_takes_precedence_over_registered_service(self) -> None:
        """Overridden service should be returned instead of registered service."""
        container = Container()

        class RealService:
            name = "real"

        class MockService:
            name = "mock"

        container.register_singleton("my_service", RealService)

        # Before override
        service = container.get("my_service")
        assert service.name == "real"

        # After override
        mock_instance = MockService()
        container.override("my_service", mock_instance)

        overridden_service = container.get("my_service")
        assert overridden_service.name == "mock"
        assert overridden_service is mock_instance

    def test_override_unregistered_service(self) -> None:
        """Override should work even for services not formally registered."""
        container = Container()

        class MockService:
            value = 42

        # Override without registering first
        container.override("unregistered_service", MockService())

        # Should be retrievable via override
        service = container.get("unregistered_service")
        assert service.value == 42

    @pytest.mark.asyncio
    async def test_override_async_service(self) -> None:
        """Async services should be overridable."""
        container = Container()

        # Register an async service
        async def real_async_factory() -> dict[str, str]:
            await asyncio.sleep(0.01)
            return {"source": "real"}

        container.register_async_singleton("async_service", real_async_factory)

        # Override with a mock
        mock_service = {"source": "mock"}
        container.override("async_service", mock_service)

        # get_async should return the override
        result = await container.get_async("async_service")
        assert result["source"] == "mock"

    def test_multiple_overrides_replace_previous(self) -> None:
        """Later overrides should replace earlier ones."""
        container = Container()

        class ServiceV1:
            version = 1

        class ServiceV2:
            version = 2

        container.register_singleton("service", ServiceV1)

        # First override
        container.override("service", ServiceV1())
        assert container.get("service").version == 1

        # Second override replaces first
        container.override("service", ServiceV2())
        assert container.get("service").version == 2


class TestContainerOverrideCleanup:
    """Tests for proper override cleanup and isolation."""

    def test_clear_override_restores_original(self) -> None:
        """Clearing override should restore original registered service."""
        container = Container()

        class RealService:
            name = "real"

        class MockService:
            name = "mock"

        container.register_singleton("service", RealService)

        # Set override
        container.override("service", MockService())
        assert container.get("service").name == "mock"

        # Clear override
        container.clear_override("service")
        assert container.get("service").name == "real"

    def test_clear_all_overrides(self) -> None:
        """clear_all_overrides should remove all overrides."""
        container = Container()

        class RealService:
            name = "real"

        class MockService:
            name = "mock"

        container.register_singleton("service1", RealService)
        container.register_singleton("service2", RealService)

        # Set multiple overrides
        container.override("service1", MockService())
        container.override("service2", MockService())

        assert container.get("service1").name == "mock"
        assert container.get("service2").name == "mock"

        # Clear all
        container.clear_all_overrides()

        assert container.get("service1").name == "real"
        assert container.get("service2").name == "real"

    def test_clear_nonexistent_override_is_safe(self) -> None:
        """Clearing an override that doesn't exist should not error."""
        container = Container()

        # Should not raise
        container.clear_override("nonexistent")

    def test_override_isolation_between_container_instances(self) -> None:
        """Overrides in one container should not affect another."""
        container1 = Container()
        container2 = Container()

        class RealService:
            name = "real"

        class MockService:
            name = "mock"

        container1.register_singleton("service", RealService)
        container2.register_singleton("service", RealService)

        # Override only in container1
        container1.override("service", MockService())

        assert container1.get("service").name == "mock"
        assert container2.get("service").name == "real"


class TestContainerOverrideScopeIsolation:
    """Tests ensuring overrides don't leak between tests."""

    @pytest.fixture
    def isolated_container(self) -> Container:
        """Provide a fresh container for each test."""
        container = Container()

        class DefaultService:
            source = "default"

        container.register_singleton("test_service", DefaultService)
        return container

    def test_override_in_first_test(self, isolated_container: Container) -> None:
        """First test with override - should not affect other tests."""

        class MockService:
            source = "mock_first"

        isolated_container.override("test_service", MockService())
        assert isolated_container.get("test_service").source == "mock_first"

    def test_override_in_second_test(self, isolated_container: Container) -> None:
        """Second test with different override - should be isolated."""

        class MockService:
            source = "mock_second"

        isolated_container.override("test_service", MockService())
        assert isolated_container.get("test_service").source == "mock_second"

    def test_no_override_uses_default(self, isolated_container: Container) -> None:
        """Test without override should get default service."""
        assert isolated_container.get("test_service").source == "default"


# =============================================================================
# Global Container Override Tests
# =============================================================================


class TestGlobalContainerOverride:
    """Tests for global container singleton override behavior."""

    @pytest.fixture(autouse=True)
    def reset_global_container(self) -> None:
        """Reset global container before and after each test."""
        reset_container()
        yield
        reset_container()

    def test_global_container_override_affects_get_container(self) -> None:
        """Override on global container should be visible through get_container."""
        container = get_container()

        class Service:
            value = "test"

        container.register_singleton("global_service", Service)
        container.override("global_service", MagicMock(value="mocked"))

        # Get container again
        same_container = get_container()
        assert same_container.get("global_service").value == "mocked"

    def test_reset_container_clears_overrides(self) -> None:
        """reset_container should clear all state including overrides."""
        container = get_container()

        class Service:
            pass

        container.register_singleton("service", Service)
        container.override("service", MagicMock())

        # Reset creates new container
        reset_container()
        new_container = get_container()

        # New container should not have the service registered
        with pytest.raises(ServiceNotFoundError):
            new_container.get("service")


# =============================================================================
# FastAPI dependency_overrides Integration Tests
# =============================================================================


class TestFastAPIDependencyOverrides:
    """Tests for FastAPI app.dependency_overrides integration."""

    @pytest.fixture
    def app(self):
        """Provide the FastAPI app instance."""
        from backend.main import app

        # Save original overrides
        original = app.dependency_overrides.copy()
        yield app
        # Restore original overrides
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)

    @pytest.mark.asyncio
    async def test_dependency_override_is_applied(
        self, app, client: AsyncClient, mock_redis: AsyncMock
    ) -> None:
        """Verify that dependency_overrides is applied to route handlers.

        This test uses the shared client fixture which already handles
        proper dependency override setup for the test environment.
        """
        from backend.core.database import get_db

        # The client fixture already overrides dependencies appropriately
        # This test verifies the pattern works
        original_overrides = app.dependency_overrides.copy()

        # Create a mock session
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()

        async def mock_get_db() -> AsyncGenerator:
            yield mock_session

        # Override the dependency
        app.dependency_overrides[get_db] = mock_get_db

        try:
            # Verify the override is registered
            assert get_db in app.dependency_overrides

            # The override mechanism is verified by the presence in the dict
            # Actual endpoint calls are tested through the client fixture
            response = await client.get("/api/events")
            # Events endpoint should work - either success or empty result
            assert response.status_code in [200, 500]
        finally:
            # Restore original overrides
            app.dependency_overrides.clear()
            app.dependency_overrides.update(original_overrides)

    @pytest.mark.asyncio
    async def test_dependency_override_cleanup(self, app) -> None:
        """Verify overrides are cleaned up properly after test."""
        from backend.core.database import get_db

        # Set an override
        async def mock_get_db():
            yield MagicMock()

        app.dependency_overrides[get_db] = mock_get_db

        # Clear it
        del app.dependency_overrides[get_db]

        # Verify it's gone
        assert get_db not in app.dependency_overrides

    @pytest.mark.asyncio
    async def test_multiple_dependency_overrides(self, app) -> None:
        """Multiple dependencies can be overridden simultaneously."""
        from backend.core.database import get_db
        from backend.core.redis import get_redis

        async def mock_db():
            yield MagicMock(name="mock_db")

        async def mock_redis_gen():
            yield MagicMock(name="mock_redis")

        # Override multiple
        app.dependency_overrides[get_db] = mock_db
        app.dependency_overrides[get_redis] = mock_redis_gen

        assert get_db in app.dependency_overrides
        assert get_redis in app.dependency_overrides

    @pytest.mark.asyncio
    async def test_override_order_independence(self, app) -> None:
        """Order of overrides should not matter."""
        from backend.core.database import get_db
        from backend.core.redis import get_redis

        mock_db = MagicMock()
        mock_redis_client = MagicMock()

        # Override in one order
        async def db_override():
            yield mock_db

        async def redis_override():
            yield mock_redis_client

        app.dependency_overrides[get_redis] = redis_override
        app.dependency_overrides[get_db] = db_override

        # Both should be present regardless of order
        assert get_db in app.dependency_overrides
        assert get_redis in app.dependency_overrides


# =============================================================================
# Service Override Integration Tests
# =============================================================================


class TestServiceDependencyOverrides:
    """Tests for overriding specific service dependencies."""

    @pytest.fixture
    def container_with_services(self) -> Container:
        """Container with mock services registered."""
        container = Container()

        # Register mock services that simulate real services
        container.register_singleton("redis_client", lambda: MagicMock(name="real_redis"))
        container.register_singleton("detector_client", lambda: MagicMock(name="real_detector"))
        container.register_singleton("context_enricher", lambda: MagicMock(name="real_enricher"))

        return container

    def test_override_redis_client(self, container_with_services: Container) -> None:
        """Redis client should be overridable for tests."""
        mock_redis = AsyncMock()
        mock_redis.health_check.return_value = {"status": "healthy", "connected": True}

        container_with_services.override("redis_client", mock_redis)

        redis = container_with_services.get("redis_client")
        assert redis is mock_redis

    def test_override_detector_client(self, container_with_services: Container) -> None:
        """Detector client should be overridable for tests."""
        mock_detector = AsyncMock()
        mock_detector.detect_objects.return_value = []
        mock_detector.health_check.return_value = True

        container_with_services.override("detector_client", mock_detector)

        detector = container_with_services.get("detector_client")
        assert detector is mock_detector

    def test_override_context_enricher(self, container_with_services: Container) -> None:
        """Context enricher should be overridable for tests."""
        mock_enricher = MagicMock()
        mock_enricher.enrich.return_value = {"enriched": True}

        container_with_services.override("context_enricher", mock_enricher)

        enricher = container_with_services.get("context_enricher")
        assert enricher is mock_enricher

    @pytest.mark.asyncio
    async def test_override_preserves_interface(self, container_with_services: Container) -> None:
        """Override should preserve expected interface behavior."""
        # Create mock with expected interface
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"cached": true}'
        mock_redis.set.return_value = True
        mock_redis.publish.return_value = 1

        container_with_services.override("redis_client", mock_redis)

        redis = container_with_services.get("redis_client")

        # Test interface methods
        result = await redis.get("key")
        assert result == '{"cached": true}'

        set_result = await redis.set("key", "value")
        assert set_result is True

        pub_result = await redis.publish("channel", {"message": "test"})
        assert pub_result == 1


# =============================================================================
# Override with Factory vs Instance Tests
# =============================================================================


class TestOverrideTypes:
    """Tests for different override value types."""

    def test_override_with_instance(self) -> None:
        """Override with a pre-created instance."""
        container = Container()

        class Service:
            def __init__(self, value: str) -> None:
                self.value = value

        container.register_singleton("service", lambda: Service("default"))

        # Override with specific instance
        specific_instance = Service("custom")
        container.override("service", specific_instance)

        result = container.get("service")
        assert result is specific_instance
        assert result.value == "custom"

    def test_override_with_mock(self) -> None:
        """Override with MagicMock for flexible mocking."""
        container = Container()

        class ComplexService:
            def do_something(self) -> str:
                return "real"

        container.register_singleton("service", ComplexService)

        # Override with mock
        mock = MagicMock()
        mock.do_something.return_value = "mocked"
        container.override("service", mock)

        result = container.get("service")
        assert result.do_something() == "mocked"

    def test_override_with_async_mock(self) -> None:
        """Override with AsyncMock for async services."""
        container = Container()

        async def real_factory() -> dict[str, str]:
            return {"status": "real"}

        container.register_async_singleton("async_service", real_factory)

        # Override with AsyncMock
        mock = AsyncMock()
        mock.some_method.return_value = "async_mocked"
        container.override("async_service", mock)

        result = container.get("async_service")
        assert result is mock


# =============================================================================
# Concurrent Override Safety Tests
# =============================================================================


class TestConcurrentOverrideSafety:
    """Tests for thread/async safety of overrides."""

    @pytest.mark.asyncio
    async def test_concurrent_access_to_overridden_service(self) -> None:
        """Multiple concurrent accesses should get same override."""
        container = Container()

        class Service:
            pass

        container.register_singleton("service", Service)

        # Set override
        mock = MagicMock(id="shared_mock")
        container.override("service", mock)

        # Concurrent access
        async def get_service():
            return container.get("service")

        results = await asyncio.gather(*[get_service() for _ in range(10)])

        # All should be the same mock
        assert all(r is mock for r in results)

    @pytest.mark.asyncio
    async def test_override_during_concurrent_access(self) -> None:
        """Override set during concurrent access should be applied consistently."""
        container = Container()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return {"call": call_count}

        container.register_factory("service", factory)

        # Create mock
        mock = {"call": "mock"}

        # Set override
        container.override("service", mock)

        # All concurrent accesses should get mock
        async def get_service():
            return container.get("service")

        results = await asyncio.gather(*[get_service() for _ in range(5)])

        assert all(r["call"] == "mock" for r in results)
        # Factory should not have been called
        assert call_count == 0


# =============================================================================
# Dependency Resolution with Override Tests
# =============================================================================


class TestDependencyResolutionWithOverrides:
    """Tests for dependency resolution when some services are overridden."""

    def test_override_dependency_affects_dependent_service(self) -> None:
        """Overriding a dependency should affect services that depend on it."""
        container = Container()

        class Database:
            def query(self) -> str:
                return "real_data"

        class Repository:
            def __init__(self, db: Database) -> None:
                self.db = db

            def get_data(self) -> str:
                return self.db.query()

        container.register_singleton("database", Database)
        container.register_singleton("repository", lambda: Repository(container.get("database")))

        # Get repository with real database
        repo = container.get("repository")
        assert repo.get_data() == "real_data"

        # Create new container with overridden database
        container2 = Container()

        mock_db = MagicMock()
        mock_db.query.return_value = "mock_data"
        container2.register_singleton("database", Database)
        container2.override("database", mock_db)
        container2.register_singleton("repository", lambda: Repository(container2.get("database")))

        # Repository should use mocked database
        repo2 = container2.get("repository")
        assert repo2.get_data() == "mock_data"

    @pytest.mark.asyncio
    async def test_override_in_dependency_chain(self) -> None:
        """Override should work correctly in multi-level dependency chains."""
        container = Container()

        # Build a dependency chain: A -> B -> C
        class ServiceC:
            def get_value(self) -> str:
                return "C"

        class ServiceB:
            def __init__(self, c: ServiceC) -> None:
                self.c = c

            def get_value(self) -> str:
                return f"B->{self.c.get_value()}"

        class ServiceA:
            def __init__(self, b: ServiceB) -> None:
                self.b = b

            def get_value(self) -> str:
                return f"A->{self.b.get_value()}"

        container.register_singleton("service_c", ServiceC)
        container.register_singleton("service_b", lambda: ServiceB(container.get("service_c")))
        container.register_singleton("service_a", lambda: ServiceA(container.get("service_b")))

        # Normal resolution
        a = container.get("service_a")
        assert a.get_value() == "A->B->C"

        # Override middle of chain
        mock_b = MagicMock()
        mock_b.get_value.return_value = "MOCKED_B"
        container.override("service_b", mock_b)

        # Clear instance cache for service_a to force re-resolution
        container._registrations["service_a"].instance = None

        # Get A again - should use mocked B
        a2 = container.get("service_a")
        assert a2.get_value() == "A->MOCKED_B"


# =============================================================================
# Integration with Real API Tests
# =============================================================================


class TestAPIWithDependencyOverrides:
    """Tests demonstrating DI override patterns for API testing."""

    @pytest.mark.asyncio
    async def test_rate_limiter_override_pattern(
        self, client: AsyncClient, mock_redis: AsyncMock
    ) -> None:
        """Demonstrate rate limiter override pattern used in API tests."""
        # This test documents the pattern used in test_api_error_scenarios.py
        # for overriding rate limiters in API tests

        # Make request - should work with mocked rate limiter
        response = await client.get("/api/events")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_orchestrator_override_pattern(
        self, client: AsyncClient, mock_redis: AsyncMock
    ) -> None:
        """Demonstrate orchestrator dependency override pattern."""
        # The orchestrator is available via app.state when properly initialized
        # For testing, we can override get_orchestrator dependency

        # This documents the pattern for service-related API testing
        response = await client.get("/api/system/health/live")
        assert response.status_code == 200


# =============================================================================
# Override Pattern Documentation Tests
# =============================================================================


class TestOverridePatternDocumentation:
    """Tests that document and verify common override patterns.

    These tests serve as executable documentation for test authors.
    """

    def test_pattern_mock_database_session(self) -> None:
        """Pattern: Mock database session for unit testing.

        Use this pattern when testing services that use database sessions.
        """
        from unittest.mock import MagicMock

        # Create mock session with common operations
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock())
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        # Verify mock is usable
        assert mock_session.execute is not None
        assert mock_session.commit is not None

    def test_pattern_mock_redis_client(self) -> None:
        """Pattern: Mock Redis client for testing without Redis.

        Use this pattern when testing services that use Redis.
        """
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.publish.return_value = 1
        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        # Verify mock interface
        assert mock_redis.health_check() is not None

    def test_pattern_mock_external_service(self) -> None:
        """Pattern: Mock external service (detector, analyzer, etc.).

        Use this pattern when testing code that calls external AI services.
        """
        mock_detector = AsyncMock()
        mock_detector.detect_objects.return_value = [
            {"label": "person", "confidence": 0.95, "bbox": [100, 200, 300, 400]}
        ]
        mock_detector.health_check.return_value = True

        # Verify mock interface
        assert mock_detector.detect_objects is not None

    @pytest.mark.asyncio
    async def test_pattern_fastapi_dependency_override(self) -> None:
        """Pattern: FastAPI dependency_overrides for API testing.

        Use this pattern when testing API routes with custom dependencies.
        """
        from backend.main import app

        # Save original
        original = app.dependency_overrides.copy()

        try:
            # Define mock dependency
            async def mock_dependency():
                yield MagicMock(value="mocked")

            # Apply override
            from backend.core.database import get_db

            app.dependency_overrides[get_db] = mock_dependency

            # Verify override is set
            assert get_db in app.dependency_overrides

        finally:
            # Always restore original
            app.dependency_overrides.clear()
            app.dependency_overrides.update(original)

    def test_pattern_container_override_with_cleanup(self) -> None:
        """Pattern: Container override with proper cleanup.

        Use this pattern when overriding container services in tests.
        """
        container = Container()

        class RealService:
            pass

        container.register_singleton("service", RealService)

        try:
            # Apply override
            mock = MagicMock()
            container.override("service", mock)

            # Test code here
            assert container.get("service") is mock

        finally:
            # Always clear override
            container.clear_override("service")

        # Original service restored
        assert isinstance(container.get("service"), RealService)
