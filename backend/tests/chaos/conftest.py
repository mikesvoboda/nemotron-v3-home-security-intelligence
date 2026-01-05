"""Chaos testing fixtures and fault injection framework.

This module provides a framework for injecting faults into system components
to test graceful degradation behavior. It works alongside the existing
circuit breaker and degradation manager patterns.

Fault Types:
    - TIMEOUT: Service doesn't respond within expected time
    - CONNECTION_ERROR: Cannot establish connection to service
    - SERVER_ERROR: Service returns 5xx HTTP errors
    - INTERMITTENT: Random failures with configurable rate
    - LATENCY: Artificial delay added to operations

Usage:
    @pytest.mark.chaos
    async def test_detector_timeout(fault_injector, rtdetr_timeout):
        # The rtdetr_timeout fixture injects a timeout fault
        # Test that the system handles this gracefully
        ...
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy.exc import OperationalError

T = TypeVar("T")


class FaultType(Enum):
    """Types of faults that can be injected."""

    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    SERVER_ERROR = "server_error"
    INTERMITTENT = "intermittent"
    LATENCY = "latency"
    UNAVAILABLE = "unavailable"


@dataclass
class FaultConfig:
    """Configuration for an injected fault.

    Attributes:
        fault_type: Type of fault to inject
        delay_seconds: Delay for TIMEOUT/LATENCY faults
        failure_rate: Rate for INTERMITTENT faults (0.0-1.0)
        error_code: HTTP status code for SERVER_ERROR faults
        error_message: Custom error message
    """

    fault_type: FaultType
    delay_seconds: float = 30.0
    failure_rate: float = 0.5
    error_code: int = 500
    error_message: str = "Injected fault"


@dataclass
class FaultStats:
    """Statistics about injected faults.

    Attributes:
        total_calls: Total number of calls made
        faults_injected: Number of faults that were triggered
        last_fault_time: Timestamp of last injected fault
    """

    total_calls: int = 0
    faults_injected: int = 0
    last_fault_time: float | None = None


class FaultInjector:
    """Context manager for injecting faults into services.

    This class provides a central point for managing fault injection across
    multiple services. It tracks which faults are active and provides
    statistics about fault injection.

    Usage:
        injector = FaultInjector()

        # Add a fault
        injector.inject("rtdetr", FaultConfig(FaultType.TIMEOUT))

        # Check if fault is active
        if injector.is_active("rtdetr"):
            # Handle degraded path

        # Clear all faults
        injector.clear()
    """

    def __init__(self) -> None:
        """Initialize the fault injector."""
        self._faults: dict[str, FaultConfig] = {}
        self._stats: dict[str, FaultStats] = {}
        self._patches: list[Any] = []

    def inject(self, service: str, config: FaultConfig) -> FaultInjector:
        """Inject a fault for a service.

        Args:
            service: Name of the service (e.g., "rtdetr", "redis", "database")
            config: Fault configuration

        Returns:
            Self for method chaining
        """
        self._faults[service] = config
        if service not in self._stats:
            self._stats[service] = FaultStats()
        return self

    def remove(self, service: str) -> None:
        """Remove fault injection for a service.

        Args:
            service: Name of the service
        """
        self._faults.pop(service, None)

    def is_active(self, service: str) -> bool:
        """Check if fault injection is active for a service.

        Args:
            service: Name of the service

        Returns:
            True if fault is configured for the service
        """
        return service in self._faults

    def get_config(self, service: str) -> FaultConfig | None:
        """Get fault configuration for a service.

        Args:
            service: Name of the service

        Returns:
            FaultConfig if configured, None otherwise
        """
        return self._faults.get(service)

    def get_stats(self, service: str) -> FaultStats:
        """Get fault statistics for a service.

        Args:
            service: Name of the service

        Returns:
            FaultStats for the service
        """
        if service not in self._stats:
            self._stats[service] = FaultStats()
        return self._stats[service]

    def record_call(self, service: str, fault_triggered: bool) -> None:
        """Record a call to a service.

        Args:
            service: Name of the service
            fault_triggered: Whether the fault was triggered
        """
        stats = self.get_stats(service)
        stats.total_calls += 1
        if fault_triggered:
            stats.faults_injected += 1
            import time

            stats.last_fault_time = time.time()

    def should_inject(self, service: str) -> bool:
        """Determine if a fault should be injected for this call.

        For INTERMITTENT faults, uses the failure_rate to randomly decide.
        For other faults, always injects.

        Args:
            service: Name of the service

        Returns:
            True if fault should be injected
        """
        config = self._faults.get(service)
        if not config:
            return False

        if config.fault_type == FaultType.INTERMITTENT:
            # Random failure based on rate - not cryptographic, just for testing
            return random.random() < config.failure_rate  # noqa: S311

        return True

    def clear(self) -> None:
        """Clear all active faults."""
        self._faults.clear()

    def reset_stats(self) -> None:
        """Reset all statistics."""
        for stats in self._stats.values():
            stats.total_calls = 0
            stats.faults_injected = 0
            stats.last_fault_time = None

    def list_active_faults(self) -> list[str]:
        """List all services with active faults.

        Returns:
            List of service names with active faults
        """
        return list(self._faults.keys())


# =============================================================================
# Global Fault Injector Fixture
# =============================================================================


@pytest.fixture
def fault_injector() -> Generator[FaultInjector]:
    """Provide a fault injector instance for tests.

    The fault injector is cleared after each test to prevent state leakage.
    """
    injector = FaultInjector()
    yield injector
    injector.clear()
    injector.reset_stats()


# =============================================================================
# RT-DETR Service Fault Fixtures
# =============================================================================


@pytest.fixture
def rtdetr_timeout(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate RT-DETR detection service timeout.

    The detector will hang for 30 seconds then raise TimeoutError.
    """
    fault_injector.inject("rtdetr", FaultConfig(FaultType.TIMEOUT, delay_seconds=30.0))

    async def slow_detect(*args: Any, **kwargs: Any) -> None:
        fault_injector.record_call("rtdetr", True)
        await asyncio.sleep(0.1)  # Short delay for tests, actual timeout from httpx
        raise httpx.TimeoutException("RT-DETR timeout")

    with patch("httpx.AsyncClient.post", side_effect=slow_detect):
        yield fault_injector


@pytest.fixture
def rtdetr_connection_error(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate RT-DETR connection failure.

    The detector service is unreachable (connection refused).
    """
    fault_injector.inject(
        "rtdetr",
        FaultConfig(
            FaultType.CONNECTION_ERROR, error_message="Connection refused: RT-DETR unreachable"
        ),
    )

    async def connection_refused(*args: Any, **kwargs: Any) -> None:
        fault_injector.record_call("rtdetr", True)
        raise httpx.ConnectError("Connection refused")

    with patch("httpx.AsyncClient.post", side_effect=connection_refused):
        yield fault_injector


@pytest.fixture
def rtdetr_server_error(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate RT-DETR server error (500).

    The detector service returns HTTP 500 errors.
    """
    fault_injector.inject(
        "rtdetr",
        FaultConfig(FaultType.SERVER_ERROR, error_code=500, error_message="Internal error"),
    )

    async def server_error(*args: Any, **kwargs: Any) -> None:
        fault_injector.record_call("rtdetr", True)
        response = httpx.Response(500, json={"error": "Internal server error"})
        raise httpx.HTTPStatusError("Server error", request=MagicMock(), response=response)

    with patch("httpx.AsyncClient.post", side_effect=server_error):
        yield fault_injector


@pytest.fixture
def rtdetr_intermittent(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate intermittent RT-DETR failures (50% failure rate).

    Half of the requests will fail randomly.
    """
    fault_injector.inject("rtdetr", FaultConfig(FaultType.INTERMITTENT, failure_rate=0.5))

    original_post = httpx.AsyncClient.post

    async def maybe_fail(self: Any, *args: Any, **kwargs: Any) -> Any:
        if fault_injector.should_inject("rtdetr"):
            fault_injector.record_call("rtdetr", True)
            raise httpx.TimeoutException("Intermittent timeout")
        fault_injector.record_call("rtdetr", False)
        return await original_post(self, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "post", maybe_fail):
        yield fault_injector


# =============================================================================
# Redis Service Fault Fixtures
# =============================================================================


@pytest.fixture
def redis_unavailable(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate Redis connection failure.

    All Redis operations will raise ConnectionError.
    """
    fault_injector.inject(
        "redis", FaultConfig(FaultType.UNAVAILABLE, error_message="Redis unavailable")
    )

    def connection_error(*args: Any, **kwargs: Any) -> None:
        fault_injector.record_call("redis", True)
        raise RedisConnectionError("Connection refused")

    async def async_connection_error(*args: Any, **kwargs: Any) -> None:
        fault_injector.record_call("redis", True)
        raise RedisConnectionError("Connection refused")

    with (
        patch("backend.core.redis.RedisClient.get", side_effect=async_connection_error),
        patch("backend.core.redis.RedisClient.set", side_effect=async_connection_error),
        patch("backend.core.redis.RedisClient.get_from_queue", side_effect=async_connection_error),
        patch(
            "backend.core.redis.RedisClient.add_to_queue_safe", side_effect=async_connection_error
        ),
        patch("backend.core.redis.RedisClient.publish", side_effect=async_connection_error),
        patch("backend.core.redis.RedisClient.health_check", side_effect=async_connection_error),
    ):
        yield fault_injector


@pytest.fixture
def redis_timeout(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate Redis timeout.

    All Redis operations will hang then timeout.
    """
    fault_injector.inject("redis", FaultConfig(FaultType.TIMEOUT, delay_seconds=10.0))

    async def timeout_error(*args: Any, **kwargs: Any) -> None:
        fault_injector.record_call("redis", True)
        await asyncio.sleep(0.1)  # Short delay for tests
        raise RedisTimeoutError("Operation timed out")

    with (
        patch("backend.core.redis.RedisClient.get", side_effect=timeout_error),
        patch("backend.core.redis.RedisClient.set", side_effect=timeout_error),
        patch("backend.core.redis.RedisClient.get_from_queue", side_effect=timeout_error),
        patch("backend.core.redis.RedisClient.add_to_queue_safe", side_effect=timeout_error),
    ):
        yield fault_injector


@pytest.fixture
def redis_intermittent(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate intermittent Redis failures (30% failure rate).

    Some Redis operations will fail randomly.
    """
    fault_injector.inject("redis", FaultConfig(FaultType.INTERMITTENT, failure_rate=0.3))

    # Store original methods for fallback
    _original_methods: dict[str, Any] = {}

    def create_maybe_fail_async(
        method_name: str,
    ) -> Callable[..., Awaitable[Any]]:
        async def maybe_fail(*args: Any, **kwargs: Any) -> Any:
            if fault_injector.should_inject("redis"):
                fault_injector.record_call("redis", True)
                raise RedisConnectionError("Intermittent Redis failure")
            fault_injector.record_call("redis", False)
            # Return a sensible default for the operation
            if method_name == "get":
                return None
            if method_name == "set":
                return True
            if method_name == "get_from_queue":
                return None
            return None

        return maybe_fail

    with (
        patch("backend.core.redis.RedisClient.get", side_effect=create_maybe_fail_async("get")),
        patch("backend.core.redis.RedisClient.set", side_effect=create_maybe_fail_async("set")),
        patch(
            "backend.core.redis.RedisClient.get_from_queue",
            side_effect=create_maybe_fail_async("get_from_queue"),
        ),
    ):
        yield fault_injector


# =============================================================================
# Database Fault Fixtures
# =============================================================================


@pytest.fixture
def database_unavailable(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate database connection failure.

    All database operations will raise OperationalError.
    """
    fault_injector.inject(
        "database", FaultConfig(FaultType.UNAVAILABLE, error_message="Database unavailable")
    )

    async def db_error(*args: Any, **kwargs: Any) -> None:
        fault_injector.record_call("database", True)
        raise OperationalError("statement", {}, Exception("Connection refused"))

    with patch("backend.core.database.get_session") as mock_session:
        mock_session.side_effect = db_error
        yield fault_injector


@pytest.fixture
def database_slow(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate slow database queries.

    All queries will have a 2-second latency added.
    """
    fault_injector.inject("database", FaultConfig(FaultType.LATENCY, delay_seconds=2.0))

    @asynccontextmanager
    async def slow_session() -> AsyncGenerator[AsyncMock]:
        fault_injector.record_call("database", True)
        await asyncio.sleep(0.1)  # Short delay for tests
        mock = AsyncMock()
        yield mock

    with patch("backend.core.database.get_session", slow_session):
        yield fault_injector


@pytest.fixture
def database_intermittent(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate intermittent database failures (20% failure rate).

    Some database operations will fail randomly.
    """
    fault_injector.inject("database", FaultConfig(FaultType.INTERMITTENT, failure_rate=0.2))

    yield fault_injector


# =============================================================================
# Nemotron LLM Service Fault Fixtures
# =============================================================================


@pytest.fixture
def nemotron_timeout(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate Nemotron LLM timeout.

    The LLM service will hang for extended period then timeout.
    """
    fault_injector.inject("nemotron", FaultConfig(FaultType.TIMEOUT, delay_seconds=120.0))

    async def slow_completion(*args: Any, **kwargs: Any) -> None:
        fault_injector.record_call("nemotron", True)
        await asyncio.sleep(0.1)  # Short delay for tests
        raise httpx.TimeoutException("Nemotron timeout")

    with patch("httpx.AsyncClient.post", side_effect=slow_completion):
        yield fault_injector


@pytest.fixture
def nemotron_unavailable(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate Nemotron service unavailable.

    The LLM service is completely unreachable.
    """
    fault_injector.inject(
        "nemotron", FaultConfig(FaultType.UNAVAILABLE, error_message="Nemotron unreachable")
    )

    async def connection_error(*args: Any, **kwargs: Any) -> None:
        fault_injector.record_call("nemotron", True)
        raise httpx.ConnectError("Nemotron connection refused")

    with patch("httpx.AsyncClient.post", side_effect=connection_error):
        yield fault_injector


@pytest.fixture
def nemotron_malformed_response(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate Nemotron returning malformed/invalid JSON.

    The LLM returns responses that cannot be parsed.
    """
    fault_injector.inject(
        "nemotron", FaultConfig(FaultType.SERVER_ERROR, error_message="Malformed response")
    )

    async def malformed_response(*args: Any, **kwargs: Any) -> httpx.Response:
        fault_injector.record_call("nemotron", True)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": "Invalid JSON {not valid}"}
        mock_response.raise_for_status = MagicMock()
        return mock_response

    with patch("httpx.AsyncClient.post", side_effect=malformed_response):
        yield fault_injector


# =============================================================================
# Network Condition Fault Fixtures
# =============================================================================


@pytest.fixture
def high_latency(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate high network latency (500ms added to all external calls).

    All HTTP requests will have artificial latency added.
    """
    fault_injector.inject("network", FaultConfig(FaultType.LATENCY, delay_seconds=0.5))

    original_post = httpx.AsyncClient.post
    original_get = httpx.AsyncClient.get

    async def slow_post(self: Any, *args: Any, **kwargs: Any) -> Any:
        fault_injector.record_call("network", True)
        await asyncio.sleep(0.5)
        return await original_post(self, *args, **kwargs)

    async def slow_get(self: Any, *args: Any, **kwargs: Any) -> Any:
        fault_injector.record_call("network", True)
        await asyncio.sleep(0.5)
        return await original_get(self, *args, **kwargs)

    with (
        patch.object(httpx.AsyncClient, "post", slow_post),
        patch.object(httpx.AsyncClient, "get", slow_get),
    ):
        yield fault_injector


@pytest.fixture
def packet_loss(fault_injector: FaultInjector) -> Generator[FaultInjector]:
    """Simulate packet loss (10% of requests fail).

    Random HTTP requests will fail as if packets were dropped.
    """
    fault_injector.inject("network", FaultConfig(FaultType.INTERMITTENT, failure_rate=0.1))

    original_post = httpx.AsyncClient.post
    original_get = httpx.AsyncClient.get

    async def maybe_fail_post(self: Any, *args: Any, **kwargs: Any) -> Any:
        if fault_injector.should_inject("network"):
            fault_injector.record_call("network", True)
            raise httpx.ConnectError("Connection reset (simulated packet loss)")
        fault_injector.record_call("network", False)
        return await original_post(self, *args, **kwargs)

    async def maybe_fail_get(self: Any, *args: Any, **kwargs: Any) -> Any:
        if fault_injector.should_inject("network"):
            fault_injector.record_call("network", True)
            raise httpx.ConnectError("Connection reset (simulated packet loss)")
        fault_injector.record_call("network", False)
        return await original_get(self, *args, **kwargs)

    with (
        patch.object(httpx.AsyncClient, "post", maybe_fail_post),
        patch.object(httpx.AsyncClient, "get", maybe_fail_get),
    ):
        yield fault_injector


# =============================================================================
# Compound Fault Fixtures (Multiple Services)
# =============================================================================


@pytest.fixture
def all_ai_services_down(
    fault_injector: FaultInjector,
) -> Generator[FaultInjector]:
    """Simulate all AI services being unavailable.

    Both RT-DETR and Nemotron services are unreachable.
    """
    fault_injector.inject(
        "rtdetr", FaultConfig(FaultType.UNAVAILABLE, error_message="RT-DETR unavailable")
    )
    fault_injector.inject(
        "nemotron", FaultConfig(FaultType.UNAVAILABLE, error_message="Nemotron unavailable")
    )

    async def ai_error(*args: Any, **kwargs: Any) -> None:
        # Determine which service based on URL
        url = args[0] if args else kwargs.get("url", "")
        if "detect" in str(url) or "rtdetr" in str(url).lower():
            fault_injector.record_call("rtdetr", True)
        else:
            fault_injector.record_call("nemotron", True)
        raise httpx.ConnectError("AI service unavailable")

    with patch("httpx.AsyncClient.post", side_effect=ai_error):
        yield fault_injector


@pytest.fixture
def cache_and_ai_down(
    fault_injector: FaultInjector,
) -> Generator[FaultInjector]:
    """Simulate Redis cache and AI services being unavailable.

    Both caching layer and AI inference are down.
    """
    fault_injector.inject(
        "redis", FaultConfig(FaultType.UNAVAILABLE, error_message="Redis unavailable")
    )
    fault_injector.inject(
        "rtdetr", FaultConfig(FaultType.UNAVAILABLE, error_message="RT-DETR unavailable")
    )

    async def redis_error(*args: Any, **kwargs: Any) -> None:
        fault_injector.record_call("redis", True)
        raise RedisConnectionError("Redis unavailable")

    async def ai_error(*args: Any, **kwargs: Any) -> None:
        fault_injector.record_call("rtdetr", True)
        raise httpx.ConnectError("RT-DETR unavailable")

    with (
        patch("backend.core.redis.RedisClient.get", side_effect=redis_error),
        patch("backend.core.redis.RedisClient.set", side_effect=redis_error),
        patch("httpx.AsyncClient.post", side_effect=ai_error),
    ):
        yield fault_injector


# =============================================================================
# Helper Functions
# =============================================================================


def assert_degraded_response(response: Any, _expected_warnings: list[str] | None = None) -> None:
    """Assert that a response indicates degraded operation.

    Args:
        response: HTTP response to check
        expected_warnings: Optional list of expected warning strings
    """
    assert response.status_code in (200, 503), f"Expected 200 or 503, got {response.status_code}"

    if response.status_code == 200:
        data = response.json()
        # Check for degraded indicators
        assert data.get("status") == "degraded" or "warnings" in data or "error" not in data


def assert_circuit_breaker_open(status: dict[str, Any], service: str) -> None:
    """Assert that a circuit breaker is open for a service.

    Args:
        status: Status dictionary from health endpoint
        service: Name of the service to check
    """
    services = status.get("services", {})
    service_status = services.get(service, {})
    assert service_status.get("circuit_breaker") == "open" or service_status.get("state") == "open"


def assert_circuit_breaker_closed(status: dict[str, Any], service: str) -> None:
    """Assert that a circuit breaker is closed for a service.

    Args:
        status: Status dictionary from health endpoint
        service: Name of the service to check
    """
    services = status.get("services", {})
    service_status = services.get(service, {})
    assert (
        service_status.get("circuit_breaker") == "closed" or service_status.get("state") == "closed"
    )
