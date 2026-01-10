"""Integration tests for health check endpoints with real DB/Redis.

These tests verify the health check endpoints work correctly with actual
database and Redis connectivity, including failure scenarios.

Test coverage:
- /api/system/health/ready with live DB connection
- /api/system/health/ready with live Redis connection
- Health check failure scenarios (DB down, Redis down)
- Response time verification under load
- Response structure validation

Uses real_redis fixture for actual Redis connections and integration_db
for actual database connections.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from backend.api.routes.system import (
    check_database_health,
    check_redis_health,
)
from backend.api.schemas.system import HealthCheckServiceStatus

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.core.redis import RedisClient

# Mark as integration tests
pytestmark = pytest.mark.integration


class TestHealthReadyWithRealDB:
    """Test /health/ready endpoint with real database connectivity."""

    @pytest.mark.asyncio
    async def test_health_ready_with_live_db(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Test /health/ready endpoint with actual database connection.

        Verifies that the health check correctly reports database as healthy
        when connected to a real PostgreSQL database.
        """
        # Configure mock Redis to return healthy status
        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        response = await client.get("/api/system/health/ready")

        # Response should be valid (may be 503 due to pipeline workers not running in tests)
        assert response.status_code in [200, 503]

        data = response.json()

        # Verify response structure
        assert "ready" in data
        assert "status" in data
        assert "services" in data
        assert "workers" in data
        assert "timestamp" in data

        # Verify services structure
        services = data["services"]
        assert "database" in services
        assert "redis" in services
        assert "ai" in services

        # Database should be healthy with real connection
        db_service = services["database"]
        assert db_service["status"] == "healthy"
        assert db_service["message"] == "Database operational"

        # Database should include pool details
        if db_service["details"] is not None:
            assert "pool" in db_service["details"]

    @pytest.mark.asyncio
    async def test_database_health_check_function_with_real_db(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test check_database_health function directly with real database.

        Verifies the helper function returns correct status when querying
        a real PostgreSQL database.
        """
        result = await check_database_health(db_session)

        assert result.status == "healthy"
        assert result.message == "Database operational"
        assert result.details is not None
        assert "pool" in result.details

    @pytest.mark.asyncio
    async def test_health_ready_database_query_timing(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that database health check completes within acceptable time.

        The health check should complete quickly to not delay readiness probes.
        """
        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        start_time = time.monotonic()
        response = await client.get("/api/system/health/ready")
        elapsed_time = time.monotonic() - start_time

        assert response.status_code in [200, 503]
        # Health check should complete within 5 seconds (the configured timeout)
        assert elapsed_time < 5.0


class TestHealthReadyWithRealRedis:
    """Test /health/ready endpoint with real Redis connectivity."""

    @pytest.mark.asyncio
    async def test_redis_health_check_function_with_real_redis(
        self,
        real_redis: RedisClient,
    ) -> None:
        """Test check_redis_health function directly with real Redis.

        Verifies the helper function returns correct status when connected
        to a real Redis instance.
        """
        result = await check_redis_health(real_redis)

        assert result.status == "healthy"
        assert result.message == "Redis connected"
        assert result.details is not None
        assert "redis_version" in result.details

    @pytest.mark.asyncio
    async def test_redis_health_check_returns_version_info(
        self,
        real_redis: RedisClient,
    ) -> None:
        """Test that Redis health check includes version information."""
        result = await check_redis_health(real_redis)

        assert result.status == "healthy"
        assert result.details is not None
        # Redis version should be a non-empty string
        redis_version = result.details.get("redis_version")
        assert redis_version is not None
        assert isinstance(redis_version, str)
        assert len(redis_version) > 0


class TestHealthCheckFailureScenarios:
    """Test health check behavior when services fail."""

    @pytest.mark.asyncio
    async def test_health_ready_with_db_connection_error(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Test /health/ready when database connection fails.

        Simulates a database connection error and verifies the endpoint
        correctly reports database as unhealthy.
        """
        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        # Create an async mock that returns the proper schema object
        async def mock_db_health_check(*args, **kwargs):
            return HealthCheckServiceStatus(
                status="unhealthy",
                message="Database error: connection refused",
                details=None,
            )

        # Mock database health check to simulate connection error
        with patch(
            "backend.api.routes.system.check_database_health",
            side_effect=mock_db_health_check,
        ):
            response = await client.get("/api/system/health/ready")

            # Should return 503 when database is unhealthy
            assert response.status_code == 503

            data = response.json()
            assert data["ready"] is False
            assert data["status"] == "not_ready"
            assert data["services"]["database"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_ready_with_redis_connection_error(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Test /health/ready when Redis connection fails.

        Simulates a Redis connection error and verifies the endpoint
        correctly reports Redis as unhealthy and system as degraded.
        """
        # Mock Redis health check to simulate connection error
        mock_redis.health_check.side_effect = ConnectionError("Redis connection refused")

        response = await client.get("/api/system/health/ready")

        # Should return 503 when Redis is unhealthy
        assert response.status_code == 503

        data = response.json()
        assert data["ready"] is False
        # Status should be degraded (DB is up but Redis is down)
        assert data["status"] in ["degraded", "not_ready"]

    @pytest.mark.asyncio
    async def test_health_ready_with_both_services_down(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Test /health/ready when both database and Redis fail.

        Verifies the system correctly reports not_ready when both
        critical infrastructure services are unavailable.
        """
        # Mock Redis to fail
        mock_redis.health_check.side_effect = ConnectionError("Redis connection refused")

        # Create an async mock that returns the proper schema object
        async def mock_db_health_check(*args, **kwargs):
            return HealthCheckServiceStatus(
                status="unhealthy",
                message="Database error: connection refused",
                details=None,
            )

        # Mock database health check to fail
        with patch(
            "backend.api.routes.system.check_database_health",
            side_effect=mock_db_health_check,
        ):
            response = await client.get("/api/system/health/ready")

            # Should return 503 when both services are down
            assert response.status_code == 503

            data = response.json()
            assert data["ready"] is False
            assert data["status"] == "not_ready"
            assert data["services"]["database"]["status"] == "unhealthy"
            assert data["services"]["redis"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_redis_health_check_with_none_client(self) -> None:
        """Test check_redis_health when Redis client is None.

        Verifies the function handles None client gracefully (connection
        failed during dependency injection).
        """
        result = await check_redis_health(None)

        assert result.status == "unhealthy"
        assert "Redis unavailable" in result.message
        assert result.details is None

    @pytest.mark.asyncio
    @pytest.mark.timeout(15)  # Extend timeout for this specific test
    async def test_health_check_timeout_handling(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that health checks handle slow services with timeout.

        Simulates a slow database query and verifies the health check
        times out appropriately. The health check timeout is 5 seconds.
        """
        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        # Mock database health check to be slow (longer than HEALTH_CHECK_TIMEOUT_SECONDS=5)
        async def slow_db_check(*args, **kwargs):
            await asyncio.sleep(7)  # Longer than health check timeout (5s) but within test timeout
            return HealthCheckServiceStatus(
                status="healthy", message="Database operational", details=None
            )

        with patch(
            "backend.api.routes.system.check_database_health",
            side_effect=slow_db_check,
        ):
            start_time = time.monotonic()
            response = await client.get("/api/system/health/ready")
            elapsed_time = time.monotonic() - start_time

            # Should return within timeout (5 seconds + some buffer for other checks)
            assert elapsed_time < 12.0

            # Should return 503 due to timeout
            assert response.status_code == 503

            data = response.json()
            assert data["services"]["database"]["status"] == "unhealthy"
            assert "timed out" in data["services"]["database"]["message"]


class TestHealthCheckResponseTimes:
    """Test health check response times under various conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that multiple concurrent health checks complete successfully.

        Verifies the system can handle multiple health check requests
        simultaneously without errors.
        """
        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        # Make 10 concurrent requests
        tasks = [client.get("/api/system/health/ready") for _ in range(10)]

        start_time = time.monotonic()
        responses = await asyncio.gather(*tasks)
        elapsed_time = time.monotonic() - start_time

        # All requests should complete
        for response in responses:
            assert response.status_code in [200, 503]
            data = response.json()
            assert "ready" in data
            assert "services" in data

        # Concurrent requests should not take 10x longer than a single request
        # They should complete in roughly the same time due to parallelism
        assert elapsed_time < 15.0  # Should complete well under this

    @pytest.mark.asyncio
    async def test_health_check_under_simulated_load(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Test health check performance under simulated load.

        Makes rapid sequential health check requests to verify consistent
        response times.
        """
        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        response_times: list[float] = []

        # Make 20 sequential requests
        for _ in range(20):
            start = time.monotonic()
            response = await client.get("/api/system/health/ready")
            elapsed = time.monotonic() - start
            response_times.append(elapsed)

            assert response.status_code in [200, 503]

        # Calculate statistics
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)

        # Average response time should be reasonable
        assert avg_time < 1.0, f"Average response time {avg_time}s exceeds threshold"

        # No single request should be extremely slow
        assert max_time < 5.0, f"Max response time {max_time}s exceeds threshold"


class TestHealthCheckResponseStructure:
    """Test that health check responses have correct structure."""

    @pytest.mark.asyncio
    async def test_readiness_response_timestamp_format(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that readiness response includes valid timestamp.

        Verifies the timestamp is a valid ISO format datetime.
        """
        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        response = await client.get("/api/system/health/ready")
        assert response.status_code in [200, 503]

        data = response.json()
        timestamp_str = data["timestamp"]

        # Should be parseable as ISO format datetime
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        assert isinstance(timestamp, datetime)

    @pytest.mark.asyncio
    async def test_readiness_response_workers_list(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that readiness response includes workers list.

        Verifies the workers field is a list with valid worker status objects.
        """
        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        response = await client.get("/api/system/health/ready")
        assert response.status_code in [200, 503]

        data = response.json()
        workers = data["workers"]

        assert isinstance(workers, list)

        # Each worker should have required fields
        for worker in workers:
            assert "name" in worker
            assert "running" in worker
            assert isinstance(worker["name"], str)
            assert isinstance(worker["running"], bool)

    @pytest.mark.asyncio
    async def test_health_check_service_status_fields(
        self,
        client: AsyncClient,
        integration_db: str,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that each service status has required fields.

        Verifies the service status objects have status, message, and details.
        """
        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        response = await client.get("/api/system/health/ready")
        assert response.status_code in [200, 503]

        data = response.json()
        services = data["services"]

        for service_name, service_status in services.items():
            assert "status" in service_status, f"{service_name} missing 'status' field"
            assert "message" in service_status, f"{service_name} missing 'message' field"
            # details can be None or a dict
            assert "details" in service_status, f"{service_name} missing 'details' field"
            assert service_status["status"] in ["healthy", "unhealthy", "degraded"]


class TestHealthCheckWithRealServices:
    """Test health checks that use both real DB and Redis."""

    @pytest.mark.asyncio
    async def test_full_health_check_with_real_services(
        self,
        integration_db: str,
        real_redis: RedisClient,
        db_session: AsyncSession,
    ) -> None:
        """Test health check functions with both real DB and Redis.

        Verifies both check_database_health and check_redis_health work
        correctly with real service connections.
        """
        # Test database health
        db_result = await check_database_health(db_session)
        assert db_result.status == "healthy"
        assert "Database operational" in db_result.message

        # Test Redis health
        redis_result = await check_redis_health(real_redis)
        assert redis_result.status == "healthy"
        assert "Redis connected" in redis_result.message

    @pytest.mark.asyncio
    async def test_database_health_check_returns_pool_stats(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test that database health check returns connection pool statistics.

        Verifies the pool details include size, overflow, and connection counts.
        """
        result = await check_database_health(db_session)

        assert result.status == "healthy"
        assert result.details is not None
        assert "pool" in result.details

        pool_stats = result.details["pool"]
        expected_keys = ["size", "overflow", "checkedin", "checkedout", "total_connections"]

        for key in expected_keys:
            assert key in pool_stats, f"Missing pool stat: {key}"
            assert isinstance(pool_stats[key], int), f"Pool stat {key} should be int"
