"""Integration tests for CircuitBreaker with HTTP clients.

Tests cover real-world HTTP client integration scenarios:
- Integration with actual HTTP client calls (httpx)
- State persistence across requests
- Circuit open/half-open/closed transitions
- Failure threshold triggering
- Recovery after success threshold
- State shared across request handlers
- HTTP-specific error handling (timeouts, connection errors, 5xx responses)

Note: These tests require DATABASE_URL and REDIS_URL environment variables to be set.
This is handled automatically when running integration tests via pytest with proper
fixtures or when running with the local development environment.
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest

# Set minimal environment before importing modules that require settings.
# This allows the test module to be collected even when env vars are not set.
# Tests will be skipped at runtime if the actual services are not available.
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = (
        "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"
    )
if not os.environ.get("REDIS_URL"):
    os.environ["REDIS_URL"] = "redis://localhost:6379/15"

# Now we can safely import the circuit breaker module
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    get_circuit_breaker,
    reset_circuit_breaker_registry,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_global_registry() -> None:
    """Reset global circuit breaker registry before and after each test."""
    reset_circuit_breaker_registry()
    yield  # type: ignore[misc]
    reset_circuit_breaker_registry()


@pytest.fixture
def fast_circuit_config() -> CircuitBreakerConfig:
    """Fast circuit breaker config for integration testing."""
    return CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=0.1,  # 100ms for fast tests
        half_open_max_calls=2,
        success_threshold=2,
    )


@pytest.fixture
def circuit_breaker(fast_circuit_config: CircuitBreakerConfig) -> CircuitBreaker:
    """Create a circuit breaker with fast test config."""
    return CircuitBreaker(name="http_service_test", config=fast_circuit_config)


class MockHTTPService:
    """Mock HTTP service that simulates failures and successes."""

    def __init__(self) -> None:
        self.call_count = 0
        self.should_fail = False
        self.fail_with_timeout = False
        self.fail_with_connection_error = False
        self.fail_with_server_error = False
        self.response_data: dict = {"status": "ok"}

    async def make_request(self, url: str) -> dict:
        """Simulate an HTTP request."""
        self.call_count += 1

        if self.fail_with_timeout:
            raise httpx.TimeoutException("Request timed out")

        if self.fail_with_connection_error:
            raise httpx.ConnectError("Connection refused")

        if self.fail_with_server_error:
            raise httpx.HTTPStatusError(
                "Internal Server Error",
                request=httpx.Request("GET", url),
                response=httpx.Response(500),
            )

        if self.should_fail:
            raise ConnectionError("Service unavailable")

        return self.response_data


@pytest.fixture
def mock_http_service() -> MockHTTPService:
    """Provide a mock HTTP service."""
    return MockHTTPService()


# =============================================================================
# Test: HTTP Client Integration
# =============================================================================


class TestCircuitBreakerHTTPIntegration:
    """Tests for circuit breaker integration with HTTP clients."""

    @pytest.mark.asyncio
    async def test_successful_http_calls_keep_circuit_closed(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that successful HTTP calls keep the circuit closed."""

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Make multiple successful calls
        for _ in range(5):
            result = await circuit_breaker.call(http_call)
            assert result == {"status": "ok"}

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert mock_http_service.call_count == 5

    @pytest.mark.asyncio
    async def test_http_timeout_counted_as_failure(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that HTTP timeout exceptions count as circuit breaker failures."""
        mock_http_service.fail_with_timeout = True

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Timeout should count as failure
        with pytest.raises(httpx.TimeoutException):
            await circuit_breaker.call(http_call)

        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_http_connection_error_counted_as_failure(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that HTTP connection errors count as circuit breaker failures."""
        mock_http_service.fail_with_connection_error = True

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Connection error should count as failure
        with pytest.raises(httpx.ConnectError):
            await circuit_breaker.call(http_call)

        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_http_server_error_counted_as_failure(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that HTTP 5xx errors count as circuit breaker failures."""
        mock_http_service.fail_with_server_error = True

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Server error should count as failure
        with pytest.raises(httpx.HTTPStatusError):
            await circuit_breaker.call(http_call)

        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_consecutive_http_failures_open_circuit(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that consecutive HTTP failures open the circuit."""
        mock_http_service.should_fail = True

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Fail 3 times (threshold is 3)
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await circuit_breaker.call(http_call)

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.is_open is True
        assert mock_http_service.call_count == 3

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_http_calls_immediately(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that open circuit rejects HTTP calls without making actual requests."""
        mock_http_service.should_fail = True

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await circuit_breaker.call(http_call)

        assert circuit_breaker.state == CircuitState.OPEN
        initial_call_count = mock_http_service.call_count

        # Now circuit is open - calls should be rejected without hitting the service
        mock_http_service.should_fail = False  # Service is "recovered" but circuit is open

        with pytest.raises(CircuitBreakerError) as exc_info:
            await circuit_breaker.call(http_call)

        assert exc_info.value.service_name == "http_service_test"
        # Call count should not increase - circuit rejected the call
        assert mock_http_service.call_count == initial_call_count


# =============================================================================
# Test: State Transitions
# =============================================================================


class TestCircuitBreakerStateTransitions:
    """Tests for circuit breaker state transitions with HTTP clients."""

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open_after_timeout(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test circuit transitions from OPEN to HALF_OPEN after recovery timeout."""
        mock_http_service.should_fail = True

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await circuit_breaker.call(http_call)

        assert circuit_breaker.state == CircuitState.OPEN

        # Wait for recovery timeout (100ms + buffer)
        await asyncio.sleep(0.15)

        # Service has recovered
        mock_http_service.should_fail = False

        # Next call should be allowed (half-open trial)
        result = await circuit_breaker.call(http_call)
        assert result == {"status": "ok"}
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that enough successes in HALF_OPEN state close the circuit."""
        mock_http_service.should_fail = True

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await circuit_breaker.call(http_call)

        await asyncio.sleep(0.15)

        # Service recovered
        mock_http_service.should_fail = False

        # Need success_threshold (2) successes to close
        result1 = await circuit_breaker.call(http_call)
        assert result1 == {"status": "ok"}
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        assert circuit_breaker.success_count == 1

        result2 = await circuit_breaker.call(http_call)
        assert result2 == {"status": "ok"}
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that failure in HALF_OPEN state reopens the circuit."""
        mock_http_service.should_fail = True

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await circuit_breaker.call(http_call)

        await asyncio.sleep(0.15)

        # Service temporarily recovered
        mock_http_service.should_fail = False
        await circuit_breaker.call(http_call)
        assert circuit_breaker.state == CircuitState.HALF_OPEN

        # Service fails again
        mock_http_service.should_fail = True
        with pytest.raises(ConnectionError):
            await circuit_breaker.call(http_call)

        # Circuit should reopen
        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_full_circuit_lifecycle(
        self,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test complete circuit lifecycle: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.05,
            half_open_max_calls=3,
            success_threshold=2,
        )
        breaker = CircuitBreaker(name="lifecycle_test", config=config)

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # 1. Start CLOSED - successful calls
        assert breaker.state == CircuitState.CLOSED
        result = await breaker.call(http_call)
        assert result == {"status": "ok"}
        assert breaker.state == CircuitState.CLOSED

        # 2. Fail to OPEN
        mock_http_service.should_fail = True
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await breaker.call(http_call)
        assert breaker.state == CircuitState.OPEN

        # 3. Wait and transition to HALF_OPEN
        await asyncio.sleep(0.1)
        mock_http_service.should_fail = False
        result = await breaker.call(http_call)
        assert result == {"status": "ok"}
        assert breaker.state == CircuitState.HALF_OPEN

        # 4. Success to CLOSED
        result = await breaker.call(http_call)
        assert result == {"status": "ok"}
        assert breaker.state == CircuitState.CLOSED


# =============================================================================
# Test: State Persistence Across Requests
# =============================================================================


class TestStatePersistenceAcrossRequests:
    """Tests for circuit breaker state persistence across request handlers."""

    @pytest.mark.asyncio
    async def test_state_shared_via_registry(
        self,
        fast_circuit_config: CircuitBreakerConfig,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that circuit state is shared via the global registry."""

        async def handler_a() -> dict:
            """Simulates first request handler."""
            breaker = get_circuit_breaker("shared_service", fast_circuit_config)
            return await breaker.call(mock_http_service.make_request, "http://test-service/api")

        async def handler_b() -> dict:
            """Simulates second request handler."""
            breaker = get_circuit_breaker("shared_service", fast_circuit_config)
            return await breaker.call(mock_http_service.make_request, "http://test-service/api")

        # Handler A makes successful call
        result = await handler_a()
        assert result == {"status": "ok"}

        # Handler B gets the same circuit breaker instance
        breaker_a = get_circuit_breaker("shared_service")
        breaker_b = get_circuit_breaker("shared_service")
        assert breaker_a is breaker_b

        # Fail through handler A
        mock_http_service.should_fail = True
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await handler_a()

        # Handler B should see circuit is open
        with pytest.raises(CircuitBreakerError):
            await handler_b()

    @pytest.mark.asyncio
    async def test_separate_circuits_for_different_services(
        self,
        fast_circuit_config: CircuitBreakerConfig,
    ) -> None:
        """Test that different services have independent circuits."""
        service_a = MockHTTPService()
        service_b = MockHTTPService()

        async def call_service_a() -> dict:
            breaker = get_circuit_breaker("service_a", fast_circuit_config)
            return await breaker.call(service_a.make_request, "http://service-a/api")

        async def call_service_b() -> dict:
            breaker = get_circuit_breaker("service_b", fast_circuit_config)
            return await breaker.call(service_b.make_request, "http://service-b/api")

        # Fail service A
        service_a.should_fail = True
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await call_service_a()

        breaker_a = get_circuit_breaker("service_a")
        breaker_b = get_circuit_breaker("service_b")

        # Service A circuit is open
        assert breaker_a.state == CircuitState.OPEN

        # Service B circuit is still closed
        assert breaker_b.state == CircuitState.CLOSED

        # Service B calls should still work
        result = await call_service_b()
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_registry_reset_clears_all_state(
        self,
        fast_circuit_config: CircuitBreakerConfig,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that registry reset clears all circuit breaker state."""
        # Create and open a circuit
        breaker = get_circuit_breaker("test_service", fast_circuit_config)
        mock_http_service.should_fail = True

        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(mock_http_service.make_request, "http://test-service/api")

        assert breaker.state == CircuitState.OPEN

        # Reset registry
        reset_circuit_breaker_registry()

        # Get circuit breaker again - should be a new instance
        new_breaker = get_circuit_breaker("test_service", fast_circuit_config)
        assert new_breaker is not breaker
        assert new_breaker.state == CircuitState.CLOSED


# =============================================================================
# Test: Failure Threshold Behavior
# =============================================================================


class TestFailureThresholdBehavior:
    """Tests for failure threshold triggering behavior."""

    @pytest.mark.asyncio
    async def test_exact_threshold_opens_circuit(
        self,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test circuit opens exactly when threshold is reached."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
        )
        breaker = CircuitBreaker(name="threshold_test", config=config)
        mock_http_service.should_fail = True

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # First 4 failures - circuit stays closed
        for i in range(4):
            with pytest.raises(ConnectionError):
                await breaker.call(http_call)
            assert breaker.state == CircuitState.CLOSED
            assert breaker.failure_count == i + 1

        # 5th failure - circuit opens
        with pytest.raises(ConnectionError):
            await breaker.call(http_call)
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(
        self,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that success resets failure count before threshold."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
        )
        breaker = CircuitBreaker(name="reset_test", config=config)

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Accumulate some failures
        mock_http_service.should_fail = True
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(http_call)

        assert breaker.failure_count == 3
        assert breaker.state == CircuitState.CLOSED

        # Success should reset failure count
        mock_http_service.should_fail = False
        result = await breaker.call(http_call)
        assert result == {"status": "ok"}
        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_intermittent_failures_dont_open_circuit(
        self,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that intermittent failures with successes don't open circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
        )
        breaker = CircuitBreaker(name="intermittent_test", config=config)

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Pattern: fail, fail, success, fail, fail, success
        for pattern in [True, True, False, True, True, False]:
            mock_http_service.should_fail = pattern
            if pattern:
                with pytest.raises(ConnectionError):
                    await breaker.call(http_call)
            else:
                await breaker.call(http_call)

        # Circuit should still be closed because successes reset the count
        assert breaker.state == CircuitState.CLOSED


# =============================================================================
# Test: Recovery Behavior
# =============================================================================


class TestRecoveryBehavior:
    """Tests for circuit breaker recovery behavior."""

    @pytest.mark.asyncio
    async def test_recovery_after_service_restored(
        self,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test full recovery when service is restored."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.05,
            success_threshold=2,
        )
        breaker = CircuitBreaker(name="recovery_test", config=config)

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Service fails
        mock_http_service.should_fail = True
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await breaker.call(http_call)

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.1)

        # Service is restored
        mock_http_service.should_fail = False

        # Recovery: 2 successful calls in half-open
        result1 = await breaker.call(http_call)
        assert result1 == {"status": "ok"}
        assert breaker.state == CircuitState.HALF_OPEN

        result2 = await breaker.call(http_call)
        assert result2 == {"status": "ok"}
        assert breaker.state == CircuitState.CLOSED

        # Verify service is back to normal
        for _ in range(5):
            result = await breaker.call(http_call)
            assert result == {"status": "ok"}

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_max_calls_respected(
        self,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that half-open state limits concurrent trial calls."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.05,
            half_open_max_calls=1,
            success_threshold=3,  # Higher than max_calls
        )
        breaker = CircuitBreaker(name="half_open_limit_test", config=config)

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Open circuit
        mock_http_service.should_fail = True
        with pytest.raises(ConnectionError):
            await breaker.call(http_call)

        await asyncio.sleep(0.1)

        # Service recovered but slow
        mock_http_service.should_fail = False

        # First call in half-open - allowed
        result = await breaker.call(http_call)
        assert result == {"status": "ok"}
        assert breaker.state == CircuitState.HALF_OPEN

        # Manually set half_open_calls to max to simulate concurrent calls
        breaker._half_open_calls = 1

        # Second call should be rejected (at limit)
        with pytest.raises(CircuitBreakerError):
            await breaker.call(http_call)


# =============================================================================
# Test: Concurrent HTTP Requests
# =============================================================================


class TestConcurrentHTTPRequests:
    """Tests for concurrent HTTP request handling."""

    @pytest.mark.asyncio
    async def test_concurrent_successful_requests(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test concurrent successful HTTP requests."""

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Run 10 concurrent calls
        tasks = [circuit_breaker.call(http_call) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r == {"status": "ok"} for r in results)
        assert circuit_breaker.state == CircuitState.CLOSED
        assert mock_http_service.call_count == 10

    @pytest.mark.asyncio
    async def test_concurrent_failures_open_circuit(
        self,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test concurrent failures properly open the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
        )
        breaker = CircuitBreaker(name="concurrent_fail_test", config=config)
        mock_http_service.should_fail = True

        async def http_call() -> dict:
            await asyncio.sleep(0.01)  # Small delay to simulate network
            return await mock_http_service.make_request("http://test-service/api")

        # Run 5 concurrent failing calls
        tasks = [breaker.call(http_call) for _ in range(5)]

        # Gather all results, expecting some to fail with ConnectionError
        # and possibly some with CircuitBreakerError after circuit opens
        with pytest.raises(ConnectionError):
            await asyncio.gather(*tasks)

        # Circuit should be open after threshold failures
        assert breaker.state == CircuitState.OPEN


# =============================================================================
# Test: HTTP-Specific Error Types
# =============================================================================


class TestHTTPSpecificErrors:
    """Tests for HTTP-specific error handling."""

    @pytest.mark.asyncio
    async def test_excluded_http_errors_not_counted(
        self,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that excluded HTTP errors don't count as failures."""
        # Exclude client errors (4xx)
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            excluded_exceptions=(httpx.HTTPStatusError,),  # Exclude HTTP errors
        )
        breaker = CircuitBreaker(name="excluded_http_test", config=config)

        async def http_call_with_server_error() -> dict:
            mock_http_service.fail_with_server_error = True
            return await mock_http_service.make_request("http://test-service/api")

        # HTTP errors should not count as failures (excluded)
        for _ in range(5):
            with pytest.raises(httpx.HTTPStatusError):
                await breaker.call(http_call_with_server_error)

        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_mixed_error_types(
        self,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test circuit handles mixed error types correctly."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
        )
        breaker = CircuitBreaker(name="mixed_errors_test", config=config)

        # Timeout
        mock_http_service.fail_with_timeout = True
        with pytest.raises(httpx.TimeoutException):
            await breaker.call(mock_http_service.make_request, "http://test-service/api")
        assert breaker.failure_count == 1

        # Connection error
        mock_http_service.fail_with_timeout = False
        mock_http_service.fail_with_connection_error = True
        with pytest.raises(httpx.ConnectError):
            await breaker.call(mock_http_service.make_request, "http://test-service/api")
        assert breaker.failure_count == 2

        # Server error
        mock_http_service.fail_with_connection_error = False
        mock_http_service.fail_with_server_error = True
        with pytest.raises(httpx.HTTPStatusError):
            await breaker.call(mock_http_service.make_request, "http://test-service/api")

        # Circuit should now be open (3 different error types)
        assert breaker.state == CircuitState.OPEN


# =============================================================================
# Test: Circuit Breaker Metrics During HTTP Operations
# =============================================================================


class TestCircuitBreakerMetricsDuringHTTP:
    """Tests for circuit breaker metrics during HTTP operations."""

    @pytest.mark.asyncio
    async def test_total_calls_tracked(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that total calls are tracked correctly."""

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        for _ in range(5):
            await circuit_breaker.call(http_call)

        metrics = circuit_breaker.get_metrics()
        assert metrics.total_calls == 5
        assert metrics.rejected_calls == 0

    @pytest.mark.asyncio
    async def test_rejected_calls_tracked(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that rejected calls are tracked correctly."""
        mock_http_service.should_fail = True

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await circuit_breaker.call(http_call)

        # Try more calls - should be rejected
        for _ in range(5):
            with pytest.raises(CircuitBreakerError):
                await circuit_breaker.call(http_call)

        metrics = circuit_breaker.get_metrics()
        assert metrics.total_calls == 8  # 3 failures + 5 rejected
        assert metrics.rejected_calls == 5

    @pytest.mark.asyncio
    async def test_status_reflects_http_failures(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test that status correctly reflects HTTP failures."""
        mock_http_service.should_fail = True

        async def http_call() -> dict:
            return await mock_http_service.make_request("http://test-service/api")

        for _ in range(2):
            with pytest.raises(ConnectionError):
                await circuit_breaker.call(http_call)

        status = circuit_breaker.get_status()
        assert status["state"] == "closed"
        assert status["failure_count"] == 2
        assert status["config"]["failure_threshold"] == 3


# =============================================================================
# Test: Real HTTP Client with Mock Server (using respx)
# =============================================================================


class TestRealHTTPClientIntegration:
    """Tests using real httpx client with mocked responses."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_httpx_client(
        self,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        """Test circuit breaker with actual httpx.AsyncClient."""

        async def make_http_request() -> dict:
            async with httpx.AsyncClient() as client:
                # Mock the transport to avoid actual network calls
                mock_response = httpx.Response(200, json={"result": "success"})
                with patch.object(
                    client, "get", new_callable=AsyncMock, return_value=mock_response
                ):
                    response = await client.get("http://test-service/api")
                    return response.json()

        # Execute through circuit breaker
        result = await circuit_breaker.call(make_http_request)
        assert result == {"result": "success"}
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_httpx_failure(
        self,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        """Test circuit breaker handles httpx failures correctly."""

        async def make_failing_request() -> dict:
            async with httpx.AsyncClient() as client:
                with patch.object(
                    client,
                    "get",
                    new_callable=AsyncMock,
                    side_effect=httpx.ConnectError("Connection refused"),
                ):
                    response = await client.get("http://test-service/api")
                    return response.json()

        # Execute failing requests through circuit breaker
        for _ in range(3):
            with pytest.raises(httpx.ConnectError):
                await circuit_breaker.call(make_failing_request)

        assert circuit_breaker.state == CircuitState.OPEN


# =============================================================================
# Test: Context Manager with HTTP Operations
# =============================================================================


class TestContextManagerWithHTTP:
    """Tests for circuit breaker context manager with HTTP operations."""

    @pytest.mark.asyncio
    async def test_context_manager_successful_http(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test context manager with successful HTTP call."""
        async with circuit_breaker:
            result = await mock_http_service.make_request("http://test-service/api")

        assert result == {"status": "ok"}
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_context_manager_http_failure(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test context manager records HTTP failures."""
        mock_http_service.should_fail = True

        for _ in range(3):
            with pytest.raises(ConnectionError):
                async with circuit_breaker:
                    await mock_http_service.make_request("http://test-service/api")

        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_context_manager_rejects_when_open(
        self,
        circuit_breaker: CircuitBreaker,
        mock_http_service: MockHTTPService,
    ) -> None:
        """Test context manager rejects entry when circuit is open."""
        mock_http_service.should_fail = True

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                async with circuit_breaker:
                    await mock_http_service.make_request("http://test-service/api")

        # Now entry should be rejected
        mock_http_service.should_fail = False
        with pytest.raises(CircuitBreakerError):
            async with circuit_breaker:
                await mock_http_service.make_request("http://test-service/api")
