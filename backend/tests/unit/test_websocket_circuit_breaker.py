"""Unit tests for WebSocket circuit breaker pattern.

Tests the WebSocketCircuitBreaker class which provides resilience for
WebSocket broadcaster services by implementing the circuit breaker pattern.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from backend.core.websocket_circuit_breaker import (
    WebSocketCircuitBreaker,
    WebSocketCircuitBreakerMetrics,
    WebSocketCircuitState,
)


class TestWebSocketCircuitBreakerInit:
    """Tests for WebSocketCircuitBreaker initialization."""

    def test_default_initialization(self) -> None:
        """Test circuit breaker initializes with default values."""
        breaker = WebSocketCircuitBreaker()

        assert breaker.name == "websocket"
        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 30.0
        assert breaker.get_state() == WebSocketCircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_custom_initialization(self) -> None:
        """Test circuit breaker initializes with custom values."""
        breaker = WebSocketCircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            half_open_max_calls=2,
            success_threshold=3,
            name="test_breaker",
        )

        assert breaker.name == "test_breaker"
        assert breaker.failure_threshold == 5
        assert breaker.recovery_timeout == 60.0
        assert breaker.get_state() == WebSocketCircuitState.CLOSED


class TestStateTransitions:
    """Tests for circuit breaker state transitions."""

    def test_closed_to_open_on_failure_threshold(self) -> None:
        """Test circuit opens after reaching failure threshold."""
        breaker = WebSocketCircuitBreaker(failure_threshold=3)

        # Record failures up to threshold
        assert breaker.get_state() == WebSocketCircuitState.CLOSED
        breaker.record_failure()
        assert breaker.get_state() == WebSocketCircuitState.CLOSED
        breaker.record_failure()
        assert breaker.get_state() == WebSocketCircuitState.CLOSED
        breaker.record_failure()

        # Circuit should now be open
        assert breaker.get_state() == WebSocketCircuitState.OPEN
        assert breaker.failure_count == 3

    def test_success_resets_failure_count(self) -> None:
        """Test that success resets failure count in closed state."""
        breaker = WebSocketCircuitBreaker(failure_threshold=3)

        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2

        breaker.record_success()
        assert breaker.failure_count == 0
        assert breaker.get_state() == WebSocketCircuitState.CLOSED

    def test_open_to_half_open_after_timeout(self) -> None:
        """Test circuit transitions to half-open after recovery timeout."""
        breaker = WebSocketCircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,  # Short timeout for testing
        )

        # Open the circuit
        breaker.record_failure()
        assert breaker.get_state() == WebSocketCircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Check if call is permitted - this should transition to half-open
        assert breaker.is_call_permitted() is True
        assert breaker.get_state() == WebSocketCircuitState.HALF_OPEN

    def test_half_open_to_closed_on_success(self) -> None:
        """Test circuit closes after success in half-open state."""
        breaker = WebSocketCircuitBreaker(
            failure_threshold=1, recovery_timeout=0.1, success_threshold=1
        )

        # Open the circuit
        breaker.record_failure()
        assert breaker.get_state() == WebSocketCircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Transition to half-open
        assert breaker.is_call_permitted() is True
        assert breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # Record success to close
        breaker.record_success()
        assert breaker.get_state() == WebSocketCircuitState.CLOSED

    def test_half_open_to_open_on_failure(self) -> None:
        """Test circuit reopens after failure in half-open state."""
        breaker = WebSocketCircuitBreaker(
            failure_threshold=1, recovery_timeout=0.1, success_threshold=2
        )

        # Open the circuit
        breaker.record_failure()
        assert breaker.get_state() == WebSocketCircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Transition to half-open
        assert breaker.is_call_permitted() is True
        assert breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # Record failure to reopen
        breaker.record_failure()
        assert breaker.get_state() == WebSocketCircuitState.OPEN


class TestIsCallPermitted:
    """Tests for is_call_permitted method."""

    def test_call_permitted_when_closed(self) -> None:
        """Test calls are permitted when circuit is closed."""
        breaker = WebSocketCircuitBreaker()
        assert breaker.is_call_permitted() is True

    def test_call_not_permitted_when_open(self) -> None:
        """Test calls are not permitted when circuit is open."""
        breaker = WebSocketCircuitBreaker(
            failure_threshold=1,
            recovery_timeout=30.0,  # Long timeout
        )

        breaker.record_failure()
        assert breaker.get_state() == WebSocketCircuitState.OPEN
        assert breaker.is_call_permitted() is False

    def test_limited_calls_in_half_open(self) -> None:
        """Test only limited calls are permitted in half-open state."""
        breaker = WebSocketCircuitBreaker(
            failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=1
        )

        # Open and wait for half-open
        breaker.record_failure()
        time.sleep(0.15)

        # First call should transition to half-open and be permitted
        assert breaker.is_call_permitted() is True
        assert breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # Simulate a call being made (increment half_open_calls internally)
        breaker._half_open_calls = 1

        # Second call should not be permitted
        assert breaker.is_call_permitted() is False


class TestReset:
    """Tests for manual reset functionality."""

    def test_reset_from_open(self) -> None:
        """Test resetting circuit from open state."""
        breaker = WebSocketCircuitBreaker(failure_threshold=1)

        breaker.record_failure()
        assert breaker.get_state() == WebSocketCircuitState.OPEN

        breaker.reset()
        assert breaker.get_state() == WebSocketCircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_reset_clears_all_counters(self) -> None:
        """Test reset clears all internal counters."""
        breaker = WebSocketCircuitBreaker(failure_threshold=3)

        # Accumulate some failures
        breaker.record_failure()
        breaker.record_failure()

        breaker.reset()

        metrics = breaker.get_metrics()
        assert metrics.failure_count == 0
        assert metrics.success_count == 0
        assert metrics.opened_at is None


class TestAsyncMethods:
    """Tests for async versions of methods."""

    @pytest.mark.asyncio
    async def test_is_call_permitted_async(self) -> None:
        """Test async version of is_call_permitted."""
        breaker = WebSocketCircuitBreaker()
        assert await breaker.is_call_permitted_async() is True

    @pytest.mark.asyncio
    async def test_record_success_async(self) -> None:
        """Test async version of record_success."""
        breaker = WebSocketCircuitBreaker(failure_threshold=2)

        breaker.record_failure()
        assert breaker.failure_count == 1

        await breaker.record_success_async()
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_record_failure_async(self) -> None:
        """Test async version of record_failure."""
        breaker = WebSocketCircuitBreaker(failure_threshold=3)

        await breaker.record_failure_async()
        assert breaker.failure_count == 1

    @pytest.mark.asyncio
    async def test_reset_async(self) -> None:
        """Test async version of reset."""
        breaker = WebSocketCircuitBreaker(failure_threshold=1)

        breaker.record_failure()
        assert breaker.get_state() == WebSocketCircuitState.OPEN

        await breaker.reset_async()
        assert breaker.get_state() == WebSocketCircuitState.CLOSED


class TestConcurrentAccess:
    """Tests for concurrent access safety."""

    @pytest.mark.asyncio
    async def test_concurrent_failures(self) -> None:
        """Test concurrent failure recording is thread-safe."""
        breaker = WebSocketCircuitBreaker(failure_threshold=100)

        async def record_failures(count: int) -> None:
            for _ in range(count):
                await breaker.record_failure_async()

        # Record failures concurrently
        await asyncio.gather(
            record_failures(10),
            record_failures(10),
            record_failures(10),
        )

        # Should have recorded all 30 failures
        assert breaker.failure_count == 30

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self) -> None:
        """Test concurrent mixed operations are thread-safe."""
        breaker = WebSocketCircuitBreaker(failure_threshold=100)

        async def record_operations() -> None:
            for _ in range(5):
                await breaker.record_failure_async()
                await breaker.record_success_async()

        # Run mixed operations concurrently
        await asyncio.gather(
            record_operations(),
            record_operations(),
            record_operations(),
        )

        # Circuit should still be closed (successes reset failures)
        assert breaker.get_state() == WebSocketCircuitState.CLOSED


class TestMetrics:
    """Tests for metrics and status reporting."""

    def test_get_metrics(self) -> None:
        """Test get_metrics returns correct values."""
        breaker = WebSocketCircuitBreaker(failure_threshold=5, name="test_metrics")

        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()  # Resets failure count
        breaker.record_success()

        metrics = breaker.get_metrics()

        assert isinstance(metrics, WebSocketCircuitBreakerMetrics)
        assert metrics.state == WebSocketCircuitState.CLOSED
        assert metrics.failure_count == 0
        assert metrics.total_failures == 2
        assert metrics.total_successes == 2

    def test_get_status(self) -> None:
        """Test get_status returns correct dictionary."""
        breaker = WebSocketCircuitBreaker(
            failure_threshold=3, recovery_timeout=30.0, name="test_status"
        )

        breaker.record_failure()

        status = breaker.get_status()

        assert status["name"] == "test_status"
        assert status["state"] == "closed"
        assert status["failure_count"] == 1
        assert status["config"]["failure_threshold"] == 3
        assert status["config"]["recovery_timeout"] == 30.0

    def test_metrics_to_dict(self) -> None:
        """Test metrics can be serialized to dictionary."""
        breaker = WebSocketCircuitBreaker()
        metrics = breaker.get_metrics()

        metrics_dict = metrics.to_dict()

        assert isinstance(metrics_dict, dict)
        assert "state" in metrics_dict
        assert metrics_dict["state"] == "closed"


class TestStringRepresentation:
    """Tests for string representations."""

    def test_str_representation(self) -> None:
        """Test __str__ returns readable format."""
        breaker = WebSocketCircuitBreaker(name="test_breaker")
        result = str(breaker)

        assert "WebSocketCircuitBreaker" in result
        assert "test_breaker" in result
        assert "CLOSED" in result

    def test_repr_representation(self) -> None:
        """Test __repr__ returns detailed format."""
        breaker = WebSocketCircuitBreaker(name="test_breaker")
        breaker.record_failure()

        result = repr(breaker)

        assert "WebSocketCircuitBreaker" in result
        assert "test_breaker" in result
        assert "failures=1" in result


class TestRecoveryBehavior:
    """Tests for recovery timeout behavior."""

    def test_recovery_timeout_not_elapsed(self) -> None:
        """Test circuit stays open before recovery timeout."""
        breaker = WebSocketCircuitBreaker(
            failure_threshold=1,
            recovery_timeout=30.0,  # Long timeout
        )

        breaker.record_failure()
        assert breaker.get_state() == WebSocketCircuitState.OPEN

        # Should not transition without waiting
        assert breaker.is_call_permitted() is False
        assert breaker.get_state() == WebSocketCircuitState.OPEN

    def test_recovery_timeout_elapsed(self) -> None:
        """Test circuit transitions after recovery timeout."""
        breaker = WebSocketCircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.05,  # Very short timeout
        )

        breaker.record_failure()
        assert breaker.get_state() == WebSocketCircuitState.OPEN

        # Wait for timeout
        time.sleep(0.1)

        # Should transition to half-open
        assert breaker.is_call_permitted() is True
        assert breaker.get_state() == WebSocketCircuitState.HALF_OPEN

    def test_multiple_successes_needed_in_half_open(self) -> None:
        """Test that multiple successes are needed to close from half-open."""
        breaker = WebSocketCircuitBreaker(
            failure_threshold=1, recovery_timeout=0.05, success_threshold=3
        )

        # Open the circuit
        breaker.record_failure()
        time.sleep(0.1)

        # Transition to half-open
        assert breaker.is_call_permitted() is True
        assert breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # First success - still half-open
        breaker.record_success()
        assert breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # Second success - still half-open
        breaker.record_success()
        assert breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # Third success - now closed
        breaker.record_success()
        assert breaker.get_state() == WebSocketCircuitState.CLOSED
