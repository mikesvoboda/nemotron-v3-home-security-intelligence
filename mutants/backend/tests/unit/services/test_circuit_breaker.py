"""Unit tests for circuit breaker pattern implementation.

Tests cover:
- CircuitBreakerConfig initialization and validation
- CircuitBreaker state machine (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- call() and async context manager behavior
- State transition methods (_transition_to_open/half_open/closed)
- reset() method behavior
- get_metrics() accuracy
- Registry management (get_circuit_breaker, CircuitBreakerRegistry)
- Edge cases: failure threshold boundary, recovery timeout, concurrent calls, excluded exceptions
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

import pytest

from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerMetrics,
    CircuitBreakerRegistry,
    CircuitState,
    _get_registry,
    get_circuit_breaker,
    reset_circuit_breaker_registry,
)

# =============================================================================
# Test Configuration and Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_global_registry():
    """Reset global registry before and after each test."""
    reset_circuit_breaker_registry()
    yield
    reset_circuit_breaker_registry()


@pytest.fixture
def default_config() -> CircuitBreakerConfig:
    """Default test configuration with fast timeouts."""
    return CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=0.1,
        half_open_max_calls=2,
        success_threshold=2,
    )


@pytest.fixture
def breaker(default_config: CircuitBreakerConfig) -> CircuitBreaker:
    """Create a circuit breaker with test config."""
    return CircuitBreaker(name="test_service", config=default_config)


# =============================================================================
# CircuitBreakerConfig Tests - __init__() and Config Validation
# =============================================================================


class TestCircuitBreakerConfigInit:
    """Tests for CircuitBreakerConfig initialization and validation."""

    def test_default_configuration(self) -> None:
        """Test that default configuration has expected values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 30.0
        assert config.half_open_max_calls == 3
        assert config.success_threshold == 2
        assert config.excluded_exceptions == ()

    def test_custom_configuration_all_fields(self) -> None:
        """Test custom configuration with all fields specified."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=60.0,
            half_open_max_calls=5,
            success_threshold=3,
            excluded_exceptions=(ValueError, KeyError),
        )
        assert config.failure_threshold == 10
        assert config.recovery_timeout == 60.0
        assert config.half_open_max_calls == 5
        assert config.success_threshold == 3
        assert config.excluded_exceptions == (ValueError, KeyError)

    def test_partial_custom_configuration(self) -> None:
        """Test partial custom configuration uses defaults for unspecified."""
        config = CircuitBreakerConfig(failure_threshold=7)
        assert config.failure_threshold == 7
        assert config.recovery_timeout == 30.0  # default
        assert config.half_open_max_calls == 3  # default
        assert config.success_threshold == 2  # default

    def test_zero_failure_threshold(self) -> None:
        """Test configuration with zero failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=0)
        assert config.failure_threshold == 0

    def test_zero_recovery_timeout(self) -> None:
        """Test configuration with zero recovery timeout."""
        config = CircuitBreakerConfig(recovery_timeout=0.0)
        assert config.recovery_timeout == 0.0

    def test_single_excluded_exception(self) -> None:
        """Test configuration with a single excluded exception."""
        config = CircuitBreakerConfig(excluded_exceptions=(ValueError,))
        assert config.excluded_exceptions == (ValueError,)
        assert isinstance(config.excluded_exceptions, tuple)

    def test_multiple_excluded_exceptions(self) -> None:
        """Test configuration with multiple excluded exceptions."""
        config = CircuitBreakerConfig(
            excluded_exceptions=(ValueError, TypeError, KeyError, RuntimeError)
        )
        assert len(config.excluded_exceptions) == 4
        assert ValueError in config.excluded_exceptions
        assert TypeError in config.excluded_exceptions


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_init_with_default_config(self) -> None:
        """Test initialization with default configuration."""
        breaker = CircuitBreaker(name="default_test")
        assert breaker.name == "default_test"
        assert breaker.config.failure_threshold == 5
        assert breaker.config.recovery_timeout == 30.0

    def test_init_with_custom_config(self, default_config: CircuitBreakerConfig) -> None:
        """Test initialization with custom configuration."""
        breaker = CircuitBreaker(name="custom_test", config=default_config)
        assert breaker.name == "custom_test"
        assert breaker.config.failure_threshold == 3
        assert breaker.config.recovery_timeout == 0.1

    def test_initial_state_is_closed(self) -> None:
        """Test that initial state is CLOSED."""
        breaker = CircuitBreaker(name="closed_test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed is True
        assert breaker.is_open is False
        assert breaker.failure_count == 0
        assert breaker.success_count == 0

    def test_name_property(self, breaker: CircuitBreaker) -> None:
        """Test name property returns correct value."""
        assert breaker.name == "test_service"

    def test_config_property(self, breaker: CircuitBreaker) -> None:
        """Test config property returns the configuration."""
        assert breaker.config.failure_threshold == 3
        assert breaker.config.recovery_timeout == 0.1


# =============================================================================
# State Machine Tests - CLOSED -> OPEN -> HALF_OPEN -> CLOSED
# =============================================================================


class TestCircuitBreakerStateTransitions:
    """Tests for circuit breaker state machine transitions."""

    @pytest.mark.asyncio
    async def test_closed_to_open_on_threshold(self, breaker: CircuitBreaker) -> None:
        """Test transition from CLOSED to OPEN when failure threshold reached."""

        async def failing_op() -> str:
            raise ConnectionError("Service unavailable")

        # Fail exactly threshold times (3)
        for i in range(3):
            assert breaker.state == CircuitState.CLOSED
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)
            if i < 2:
                assert breaker.failure_count == i + 1

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open is True
        assert breaker.is_closed is False

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self, breaker: CircuitBreaker) -> None:
        """Test transition from OPEN to HALF_OPEN after recovery timeout."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        async def success_op() -> str:
            return "success"

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout (0.1s)
        await asyncio.sleep(0.15)

        # Next call should transition to HALF_OPEN
        result = await breaker.call(success_op)
        assert result == "success"
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_to_closed_on_success_threshold(self, breaker: CircuitBreaker) -> None:
        """Test transition from HALF_OPEN to CLOSED when success threshold met."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        async def success_op() -> str:
            return "success"

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        await asyncio.sleep(0.15)

        # Need success_threshold (2) successes to close
        await breaker.call(success_op)
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.success_count == 1

        await breaker.call(success_op)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self, breaker: CircuitBreaker) -> None:
        """Test transition from HALF_OPEN to OPEN on any failure."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        async def success_op() -> str:
            return "success"

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        await asyncio.sleep(0.15)

        # One success in half-open
        await breaker.call(success_op)
        assert breaker.state == CircuitState.HALF_OPEN

        # Any failure in half-open reopens the circuit
        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_full_state_cycle(self) -> None:
        """Test complete cycle: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.05,
            half_open_max_calls=3,
            success_threshold=2,
        )
        breaker = CircuitBreaker(name="cycle_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        async def success_op() -> str:
            return "ok"

        # 1. Start CLOSED
        assert breaker.state == CircuitState.CLOSED

        # 2. Fail to OPEN
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)
        assert breaker.state == CircuitState.OPEN

        # 3. Wait and transition to HALF_OPEN
        await asyncio.sleep(0.1)
        await breaker.call(success_op)
        assert breaker.state == CircuitState.HALF_OPEN

        # 4. Success to CLOSED
        await breaker.call(success_op)
        assert breaker.state == CircuitState.CLOSED


# =============================================================================
# call() Tests
# =============================================================================


class TestCircuitBreakerCall:
    """Tests for the call() method."""

    @pytest.mark.asyncio
    async def test_call_passes_args_and_kwargs(self, breaker: CircuitBreaker) -> None:
        """Test that call correctly passes arguments to the operation."""

        async def operation(a: int, b: str, c: bool = False) -> dict:
            return {"a": a, "b": b, "c": c}

        result = await breaker.call(operation, 42, "hello", c=True)
        assert result == {"a": 42, "b": "hello", "c": True}

    @pytest.mark.asyncio
    async def test_call_returns_operation_result(self, breaker: CircuitBreaker) -> None:
        """Test that call returns the operation's result."""

        async def operation() -> str:
            return "expected_result"

        result = await breaker.call(operation)
        assert result == "expected_result"

    @pytest.mark.asyncio
    async def test_call_propagates_operation_exception(self, breaker: CircuitBreaker) -> None:
        """Test that call propagates exceptions from the operation."""

        async def operation() -> str:
            raise ValueError("Operation error")

        with pytest.raises(ValueError, match="Operation error"):
            await breaker.call(operation)

    @pytest.mark.asyncio
    async def test_call_increments_total_calls(self, breaker: CircuitBreaker) -> None:
        """Test that call increments total_calls counter."""

        async def operation() -> str:
            return "ok"

        for i in range(5):
            await breaker.call(operation)

        metrics = breaker.get_metrics()
        assert metrics.total_calls == 5

    @pytest.mark.asyncio
    async def test_call_when_open_raises_circuit_breaker_error(
        self, breaker: CircuitBreaker
    ) -> None:
        """Test that call raises CircuitBreakerError when circuit is open."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        # Immediate call should be rejected
        with pytest.raises(CircuitBreakerError) as exc_info:
            await breaker.call(failing_op)

        assert exc_info.value.service_name == "test_service"
        assert "test_service" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_when_open_increments_rejected_calls(self, breaker: CircuitBreaker) -> None:
        """Test that rejected calls increment the rejected_calls counter."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        # Try to call multiple times while open
        for _ in range(5):
            with pytest.raises(CircuitBreakerError):
                await breaker.call(failing_op)

        metrics = breaker.get_metrics()
        assert metrics.rejected_calls == 5


# =============================================================================
# Transition Method Tests
# =============================================================================


class TestTransitionMethods:
    """Tests for state transition methods."""

    def test_transition_to_open_updates_state(self, breaker: CircuitBreaker) -> None:
        """Test _transition_to_open updates state correctly."""
        assert breaker.state == CircuitState.CLOSED

        breaker._transition_to_open()

        assert breaker.state == CircuitState.OPEN
        assert breaker._opened_at is not None
        assert breaker._success_count == 0
        assert breaker._half_open_calls == 0
        assert breaker._last_state_change is not None

    def test_transition_to_half_open_updates_state(self, breaker: CircuitBreaker) -> None:
        """Test _transition_to_half_open updates state correctly."""
        breaker._state = CircuitState.OPEN
        breaker._opened_at = time.monotonic()

        breaker._transition_to_half_open()

        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker._success_count == 0
        assert breaker._half_open_calls == 0
        assert breaker._last_state_change is not None

    def test_transition_to_closed_updates_state(self, breaker: CircuitBreaker) -> None:
        """Test _transition_to_closed updates state correctly."""
        breaker._state = CircuitState.HALF_OPEN
        breaker._failure_count = 5
        breaker._success_count = 2
        breaker._opened_at = time.monotonic()

        breaker._transition_to_closed()

        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0
        assert breaker._success_count == 0
        assert breaker._opened_at is None
        assert breaker._half_open_calls == 0
        assert breaker._last_state_change is not None

    def test_transition_to_open_resets_half_open_calls(self, breaker: CircuitBreaker) -> None:
        """Test _transition_to_open resets half_open_calls."""
        breaker._half_open_calls = 5

        breaker._transition_to_open()

        assert breaker._half_open_calls == 0


# =============================================================================
# reset() Tests
# =============================================================================


class TestReset:
    """Tests for the reset() method."""

    def test_reset_from_closed(self, breaker: CircuitBreaker) -> None:
        """Test reset from CLOSED state."""
        breaker._failure_count = 2

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_reset_from_open(self, breaker: CircuitBreaker) -> None:
        """Test reset from OPEN state."""
        breaker._state = CircuitState.OPEN
        breaker._failure_count = 5
        breaker._opened_at = time.monotonic()

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker._opened_at is None

    def test_reset_from_half_open(self, breaker: CircuitBreaker) -> None:
        """Test reset from HALF_OPEN state."""
        breaker._state = CircuitState.HALF_OPEN
        breaker._failure_count = 3
        breaker._success_count = 1
        breaker._half_open_calls = 2

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
        assert breaker._half_open_calls == 0

    def test_reset_clears_last_failure_time(self, breaker: CircuitBreaker) -> None:
        """Test reset clears last_failure_time."""
        breaker._last_failure_time = time.monotonic()

        breaker.reset()

        assert breaker._last_failure_time is None

    def test_reset_updates_last_state_change(self, breaker: CircuitBreaker) -> None:
        """Test reset updates last_state_change timestamp."""
        before = breaker._last_state_change

        breaker.reset()

        assert breaker._last_state_change is not None
        assert breaker._last_state_change != before


# =============================================================================
# get_metrics() Tests
# =============================================================================


class TestGetMetrics:
    """Tests for the get_metrics() method."""

    def test_get_metrics_returns_correct_type(self, breaker: CircuitBreaker) -> None:
        """Test get_metrics returns CircuitBreakerMetrics."""
        metrics = breaker.get_metrics()
        assert isinstance(metrics, CircuitBreakerMetrics)

    def test_get_metrics_reflects_name(self, breaker: CircuitBreaker) -> None:
        """Test get_metrics returns correct name."""
        metrics = breaker.get_metrics()
        assert metrics.name == "test_service"

    def test_get_metrics_reflects_state(self, breaker: CircuitBreaker) -> None:
        """Test get_metrics returns current state."""
        assert breaker.get_metrics().state == CircuitState.CLOSED

        breaker._state = CircuitState.OPEN
        assert breaker.get_metrics().state == CircuitState.OPEN

        breaker._state = CircuitState.HALF_OPEN
        assert breaker.get_metrics().state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_get_metrics_failure_count_accurate(self, breaker: CircuitBreaker) -> None:
        """Test get_metrics returns accurate failure count."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        for i in range(2):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)
            assert breaker.get_metrics().failure_count == i + 1

    @pytest.mark.asyncio
    async def test_get_metrics_total_calls_accurate(self, breaker: CircuitBreaker) -> None:
        """Test get_metrics returns accurate total calls."""

        async def success_op() -> str:
            return "ok"

        for i in range(5):
            await breaker.call(success_op)
            assert breaker.get_metrics().total_calls == i + 1

    @pytest.mark.asyncio
    async def test_get_metrics_rejected_calls_accurate(self, breaker: CircuitBreaker) -> None:
        """Test get_metrics returns accurate rejected calls."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        initial_rejected = breaker.get_metrics().rejected_calls
        assert initial_rejected == 0

        # Now calls should be rejected
        for i in range(3):
            with pytest.raises(CircuitBreakerError):
                await breaker.call(failing_op)
            assert breaker.get_metrics().rejected_calls == i + 1

    @pytest.mark.asyncio
    async def test_get_metrics_last_failure_time_set(self, breaker: CircuitBreaker) -> None:
        """Test get_metrics includes last_failure_time after failure."""
        assert breaker.get_metrics().last_failure_time is None

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        metrics = breaker.get_metrics()
        assert metrics.last_failure_time is not None
        assert isinstance(metrics.last_failure_time, datetime)

    def test_get_metrics_to_dict(self, breaker: CircuitBreaker) -> None:
        """Test metrics to_dict serialization."""
        breaker._failure_count = 2
        breaker._total_calls = 10
        breaker._rejected_calls = 3

        metrics = breaker.get_metrics()
        result = metrics.to_dict()

        assert result["name"] == "test_service"
        assert result["state"] == "closed"
        assert result["failure_count"] == 2
        assert result["total_calls"] == 10
        assert result["rejected_calls"] == 3


# =============================================================================
# Registry Management Tests
# =============================================================================


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry class."""

    def test_get_or_create_returns_new_breaker(self) -> None:
        """Test get_or_create creates new breaker when none exists."""
        registry = CircuitBreakerRegistry()
        breaker = registry.get_or_create("new_service")

        assert breaker is not None
        assert breaker.name == "new_service"

    def test_get_or_create_returns_same_instance(self) -> None:
        """Test get_or_create returns same instance for same name."""
        registry = CircuitBreakerRegistry()
        breaker1 = registry.get_or_create("service_a")
        breaker2 = registry.get_or_create("service_a")

        assert breaker1 is breaker2

    def test_get_or_create_different_names_different_instances(self) -> None:
        """Test get_or_create returns different instances for different names."""
        registry = CircuitBreakerRegistry()
        breaker1 = registry.get_or_create("service_a")
        breaker2 = registry.get_or_create("service_b")

        assert breaker1 is not breaker2
        assert breaker1.name == "service_a"
        assert breaker2.name == "service_b"

    def test_get_or_create_uses_provided_config(self) -> None:
        """Test get_or_create uses provided configuration."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(failure_threshold=10, recovery_timeout=120.0)

        breaker = registry.get_or_create("custom_config", config)

        assert breaker.config.failure_threshold == 10
        assert breaker.config.recovery_timeout == 120.0

    def test_get_returns_existing_breaker(self) -> None:
        """Test get returns existing breaker."""
        registry = CircuitBreakerRegistry()
        registry.get_or_create("existing_service")

        breaker = registry.get("existing_service")
        assert breaker is not None
        assert breaker.name == "existing_service"

    def test_get_returns_none_for_nonexistent(self) -> None:
        """Test get returns None for nonexistent breaker."""
        registry = CircuitBreakerRegistry()
        assert registry.get("nonexistent") is None

    def test_get_all_status(self) -> None:
        """Test get_all_status returns status of all breakers."""
        registry = CircuitBreakerRegistry()
        registry.get_or_create("service_a")
        registry.get_or_create("service_b")

        status = registry.get_all_status()

        assert len(status) == 2
        assert "service_a" in status
        assert "service_b" in status
        assert status["service_a"]["state"] == "closed"
        assert status["service_b"]["state"] == "closed"

    def test_reset_all(self) -> None:
        """Test reset_all resets all breakers to CLOSED."""
        registry = CircuitBreakerRegistry()
        breaker_a = registry.get_or_create("service_a")
        breaker_b = registry.get_or_create("service_b")

        # Open both
        breaker_a._state = CircuitState.OPEN
        breaker_a._failure_count = 5
        breaker_b._state = CircuitState.HALF_OPEN
        breaker_b._failure_count = 3

        registry.reset_all()

        assert breaker_a.state == CircuitState.CLOSED
        assert breaker_a.failure_count == 0
        assert breaker_b.state == CircuitState.CLOSED
        assert breaker_b.failure_count == 0

    def test_list_names(self) -> None:
        """Test list_names returns all registered names."""
        registry = CircuitBreakerRegistry()
        registry.get_or_create("alpha")
        registry.get_or_create("beta")
        registry.get_or_create("gamma")

        names = registry.list_names()

        assert len(names) == 3
        assert set(names) == {"alpha", "beta", "gamma"}

    def test_clear(self) -> None:
        """Test clear removes all registered breakers."""
        registry = CircuitBreakerRegistry()
        registry.get_or_create("service_a")
        registry.get_or_create("service_b")

        assert len(registry.list_names()) == 2

        registry.clear()

        assert len(registry.list_names()) == 0


class TestGlobalCircuitBreakerFunctions:
    """Tests for global circuit breaker functions."""

    def test_get_circuit_breaker_creates_new(self) -> None:
        """Test get_circuit_breaker creates new breaker."""
        breaker = get_circuit_breaker("global_test")

        assert breaker is not None
        assert breaker.name == "global_test"

    def test_get_circuit_breaker_returns_same_instance(self) -> None:
        """Test get_circuit_breaker returns same instance for same name."""
        breaker1 = get_circuit_breaker("singleton_test")
        breaker2 = get_circuit_breaker("singleton_test")

        assert breaker1 is breaker2

    def test_get_circuit_breaker_with_config(self) -> None:
        """Test get_circuit_breaker with custom config."""
        config = CircuitBreakerConfig(failure_threshold=15)
        breaker = get_circuit_breaker("config_test", config)

        assert breaker.config.failure_threshold == 15

    def test_reset_circuit_breaker_registry_clears_all(self) -> None:
        """Test reset_circuit_breaker_registry clears global registry."""
        breaker1 = get_circuit_breaker("before_reset")

        reset_circuit_breaker_registry()

        breaker2 = get_circuit_breaker("before_reset")

        assert breaker1 is not breaker2

    def test_get_registry_creates_singleton(self) -> None:
        """Test _get_registry returns same instance."""
        registry1 = _get_registry()
        registry2 = _get_registry()

        assert registry1 is registry2


# =============================================================================
# Edge Cases
# =============================================================================


class TestFailureThresholdBoundary:
    """Tests for failure threshold boundary conditions."""

    @pytest.mark.asyncio
    async def test_exactly_at_threshold_opens(self) -> None:
        """Test circuit opens exactly when threshold is reached."""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60.0)
        breaker = CircuitBreaker(name="threshold_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # First failure - still closed
        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)
        assert breaker.state == CircuitState.CLOSED

        # Second failure - still closed
        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)
        assert breaker.state == CircuitState.CLOSED

        # Third failure - opens (threshold = 3)
        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_below_threshold_stays_closed(self) -> None:
        """Test circuit stays closed below threshold."""
        config = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0)
        breaker = CircuitBreaker(name="below_threshold_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # 4 failures (threshold is 5) - should stay closed
        for _ in range(4):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 4

    @pytest.mark.asyncio
    async def test_threshold_of_one(self) -> None:
        """Test circuit with threshold of 1 opens immediately."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60.0)
        breaker = CircuitBreaker(name="threshold_one_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_success_resets_failure_count_below_threshold(self) -> None:
        """Test success resets failure count when below threshold."""
        config = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0)
        breaker = CircuitBreaker(name="reset_below_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        async def success_op() -> str:
            return "ok"

        # Accumulate some failures
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        assert breaker.failure_count == 3

        # Success should reset
        await breaker.call(success_op)
        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED


class TestRecoveryTimeoutEdgeCases:
    """Tests for recovery timeout edge cases."""

    @pytest.mark.asyncio
    async def test_exactly_at_timeout(self) -> None:
        """Test behavior exactly at recovery timeout."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        breaker = CircuitBreaker(name="exact_timeout_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        async def success_op() -> str:
            return "ok"

        # Open circuit
        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        # Wait exactly the timeout
        await asyncio.sleep(0.1)

        # Should be able to call now
        result = await breaker.call(success_op)
        assert result == "ok"
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_before_timeout_rejects(self) -> None:
        """Test calls before timeout are rejected."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.5)
        breaker = CircuitBreaker(name="before_timeout_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Open circuit
        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        # Don't wait long enough
        await asyncio.sleep(0.05)

        # Should still reject
        with pytest.raises(CircuitBreakerError):
            await breaker.call(failing_op)

    @pytest.mark.asyncio
    async def test_zero_timeout_immediate_recovery(self) -> None:
        """Test zero timeout allows immediate recovery attempt."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.0)
        breaker = CircuitBreaker(name="zero_timeout_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        async def success_op() -> str:
            return "ok"

        # Open circuit
        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        assert breaker.state == CircuitState.OPEN

        # Should immediately allow trial call
        result = await breaker.call(success_op)
        assert result == "ok"


class TestConcurrentCalls:
    """Tests for concurrent call handling."""

    @pytest.mark.asyncio
    async def test_concurrent_successes(self) -> None:
        """Test concurrent successful calls are tracked correctly."""
        config = CircuitBreakerConfig(failure_threshold=10, recovery_timeout=60.0)
        breaker = CircuitBreaker(name="concurrent_success_test", config=config)

        call_count = 0

        async def tracked_op() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return "ok"

        tasks = [breaker.call(tracked_op) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r == "ok" for r in results)
        assert call_count == 10
        assert breaker.get_metrics().total_calls == 10

    @pytest.mark.asyncio
    async def test_concurrent_failures(self) -> None:
        """Test concurrent failures properly trigger threshold."""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60.0)
        breaker = CircuitBreaker(name="concurrent_failure_test", config=config)

        async def failing_op() -> str:
            await asyncio.sleep(0.01)
            raise ConnectionError("Failed")

        tasks = [breaker.call(failing_op) for _ in range(5)]

        # At least one should raise ConnectionError, and circuit should open
        with pytest.raises(ConnectionError):
            await asyncio.gather(*tasks)

        # Circuit should be open after failures
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_max_calls_limits_concurrent(self) -> None:
        """Test half-open state limits concurrent trial calls."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.05,
            half_open_max_calls=2,
            success_threshold=5,  # Higher than max to not close circuit
        )
        breaker = CircuitBreaker(name="half_open_concurrent_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Open circuit
        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        await asyncio.sleep(0.1)

        # Manually set half-open state with max calls reached
        breaker._state = CircuitState.HALF_OPEN
        breaker._half_open_calls = 2

        # Should reject additional calls
        with pytest.raises(CircuitBreakerError):

            async def success_op() -> str:
                return "ok"

            await breaker.call(success_op)


class TestExcludedExceptions:
    """Tests for excluded exceptions handling."""

    @pytest.mark.asyncio
    async def test_excluded_exception_not_counted_as_failure(self) -> None:
        """Test excluded exceptions don't increment failure count."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            excluded_exceptions=(ValueError,),
        )
        breaker = CircuitBreaker(name="excluded_test", config=config)

        async def raises_value_error() -> str:
            raise ValueError("Excluded error")

        # Many excluded exceptions should not count
        for _ in range(10):
            with pytest.raises(ValueError):
                await breaker.call(raises_value_error)

        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_non_excluded_exception_counted(self) -> None:
        """Test non-excluded exceptions are counted."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            excluded_exceptions=(ValueError,),
        )
        breaker = CircuitBreaker(name="counted_test", config=config)

        async def raises_type_error() -> str:
            raise TypeError("Not excluded")

        with pytest.raises(TypeError):
            await breaker.call(raises_type_error)

        assert breaker.failure_count == 1

    @pytest.mark.asyncio
    async def test_multiple_excluded_exceptions(self) -> None:
        """Test multiple types of excluded exceptions."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            excluded_exceptions=(ValueError, KeyError, AttributeError),
        )
        breaker = CircuitBreaker(name="multi_excluded_test", config=config)

        async def raises_value_error() -> str:
            raise ValueError("Excluded")

        async def raises_key_error() -> str:
            raise KeyError("Excluded")

        async def raises_attribute_error() -> str:
            raise AttributeError("Excluded")

        # All should be excluded
        with pytest.raises(ValueError):
            await breaker.call(raises_value_error)
        with pytest.raises(KeyError):
            await breaker.call(raises_key_error)
        with pytest.raises(AttributeError):
            await breaker.call(raises_attribute_error)

        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_excluded_exception_in_context_manager(self) -> None:
        """Test excluded exceptions in async context manager."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            excluded_exceptions=(ValueError,),
        )
        breaker = CircuitBreaker(name="ctx_excluded_test", config=config)

        for _ in range(5):
            with pytest.raises(ValueError):
                async with breaker:
                    raise ValueError("Excluded")

        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED


# =============================================================================
# Async Context Manager Tests
# =============================================================================


class TestAsyncContextManager:
    """Tests for async context manager functionality."""

    @pytest.mark.asyncio
    async def test_context_manager_success(self, breaker: CircuitBreaker) -> None:
        """Test successful execution in context manager."""
        result = None
        async with breaker:
            result = "executed"

        assert result == "executed"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_context_manager_failure_counted(self, breaker: CircuitBreaker) -> None:
        """Test failures in context manager are counted."""
        with pytest.raises(RuntimeError):
            async with breaker:
                raise RuntimeError("Failed")

        assert breaker.failure_count == 1

    @pytest.mark.asyncio
    async def test_context_manager_opens_circuit(self, breaker: CircuitBreaker) -> None:
        """Test context manager opens circuit after threshold."""
        for _ in range(3):
            with pytest.raises(ConnectionError):
                async with breaker:
                    raise ConnectionError("Failed")

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_context_manager_rejects_when_open(self, breaker: CircuitBreaker) -> None:
        """Test context manager rejects entry when circuit open."""
        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                async with breaker:
                    raise ConnectionError("Failed")

        # Now should reject entry
        with pytest.raises(CircuitBreakerError):
            async with breaker:
                pass  # Should not reach

    @pytest.mark.asyncio
    async def test_context_manager_half_open_recovery(self, breaker: CircuitBreaker) -> None:
        """Test context manager allows recovery in half-open."""
        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                async with breaker:
                    raise ConnectionError("Failed")

        await asyncio.sleep(0.15)

        # Should now allow entry and transition to half-open
        async with breaker:
            pass

        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_context_manager_increments_total_calls(self, breaker: CircuitBreaker) -> None:
        """Test context manager increments total_calls."""
        for i in range(5):
            async with breaker:
                pass
            assert breaker.get_metrics().total_calls == i + 1


# =============================================================================
# CircuitBreakerError Tests
# =============================================================================


class TestCircuitBreakerError:
    """Tests for CircuitBreakerError exception."""

    def test_error_message_with_string_state(self) -> None:
        """Test error message with string state."""
        error = CircuitBreakerError("my_service", "open")

        assert "my_service" in str(error)
        assert "open" in str(error)
        assert error.service_name == "my_service"
        assert error.name == "my_service"  # Alias
        assert error.state == "open"

    def test_error_message_with_enum_state(self) -> None:
        """Test error message with CircuitState enum."""
        error = CircuitBreakerError("my_service", CircuitState.OPEN)

        assert "my_service" in str(error)
        assert "open" in str(error)
        assert error.service_name == "my_service"
        assert error.state == CircuitState.OPEN

    def test_error_message_with_half_open_state(self) -> None:
        """Test error message with half-open state."""
        error = CircuitBreakerError("test_svc", CircuitState.HALF_OPEN)

        assert "test_svc" in str(error)
        assert "half_open" in str(error)

    def test_error_is_exception(self) -> None:
        """Test CircuitBreakerError is an Exception."""
        error = CircuitBreakerError("test", "open")
        assert isinstance(error, Exception)


# =============================================================================
# Additional Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for additional helper methods."""

    def test_force_open(self, breaker: CircuitBreaker) -> None:
        """Test force_open transitions to open state."""
        assert breaker.state == CircuitState.CLOSED

        breaker.force_open()

        assert breaker.state == CircuitState.OPEN
        assert breaker._last_failure_time is not None

    def test_get_status(self, breaker: CircuitBreaker) -> None:
        """Test get_status returns comprehensive status."""
        breaker._failure_count = 2
        breaker._total_calls = 10

        status = breaker.get_status()

        assert status["name"] == "test_service"
        assert status["state"] == "closed"
        assert status["failure_count"] == 2
        assert status["total_calls"] == 10
        assert "config" in status
        assert status["config"]["failure_threshold"] == 3
        assert status["config"]["recovery_timeout"] == 0.1

    def test_str_representation(self, breaker: CircuitBreaker) -> None:
        """Test __str__ representation."""
        result = str(breaker)

        assert "CircuitBreaker" in result
        assert "test_service" in result
        assert "CLOSED" in result

    def test_repr_representation(self, breaker: CircuitBreaker) -> None:
        """Test __repr__ representation."""
        result = repr(breaker)

        assert "CircuitBreaker" in result
        assert "test_service" in result
        assert "closed" in result

    @pytest.mark.asyncio
    async def test_allow_call_closed(self, breaker: CircuitBreaker) -> None:
        """Test allow_call returns True when closed."""
        assert await breaker.allow_call() is True

    @pytest.mark.asyncio
    async def test_allow_call_open_without_timeout(self) -> None:
        """Test allow_call returns False when open without timeout elapsed."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60.0)
        breaker = CircuitBreaker(name="allow_open_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        # Immediately check - should be False
        assert await breaker.allow_call() is False

    @pytest.mark.asyncio
    async def test_allow_call_open_with_timeout_elapsed(self) -> None:
        """Test allow_call transitions to half-open when timeout elapsed."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.05)
        breaker = CircuitBreaker(name="allow_timeout_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        await asyncio.sleep(0.1)

        # Should transition to half-open and return True
        assert await breaker.allow_call() is True
        assert breaker.state == CircuitState.HALF_OPEN


# =============================================================================
# CircuitState Enum Tests
# =============================================================================


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_closed_value(self) -> None:
        """Test CLOSED state value."""
        assert CircuitState.CLOSED.value == "closed"

    def test_open_value(self) -> None:
        """Test OPEN state value."""
        assert CircuitState.OPEN.value == "open"

    def test_half_open_value(self) -> None:
        """Test HALF_OPEN state value."""
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_all_states_exist(self) -> None:
        """Test all expected states exist."""
        states = list(CircuitState)
        assert len(states) == 3
        assert CircuitState.CLOSED in states
        assert CircuitState.OPEN in states
        assert CircuitState.HALF_OPEN in states


# =============================================================================
# CircuitBreakerMetrics Tests
# =============================================================================


class TestCircuitBreakerMetricsDataclass:
    """Tests for CircuitBreakerMetrics dataclass."""

    def test_to_dict_no_timestamps(self) -> None:
        """Test to_dict with no timestamps set."""
        metrics = CircuitBreakerMetrics(
            name="test",
            state=CircuitState.CLOSED,
            failure_count=0,
            success_count=0,
            total_calls=5,
            rejected_calls=0,
        )

        result = metrics.to_dict()

        assert result["name"] == "test"
        assert result["state"] == "closed"
        assert result["failure_count"] == 0
        assert result["success_count"] == 0
        assert result["total_calls"] == 5
        assert result["rejected_calls"] == 0
        assert result["last_failure_time"] is None
        assert result["last_state_change"] is None

    def test_to_dict_with_timestamps(self) -> None:
        """Test to_dict with timestamps set."""
        now = datetime.now(UTC)
        metrics = CircuitBreakerMetrics(
            name="test",
            state=CircuitState.OPEN,
            failure_count=5,
            success_count=0,
            total_calls=100,
            rejected_calls=50,
            last_failure_time=now,
            last_state_change=now,
        )

        result = metrics.to_dict()

        assert result["state"] == "open"
        assert result["last_failure_time"] == now.isoformat()
        assert result["last_state_change"] == now.isoformat()

    def test_metrics_defaults(self) -> None:
        """Test metrics default values."""
        metrics = CircuitBreakerMetrics(name="test", state=CircuitState.CLOSED)

        assert metrics.failure_count == 0
        assert metrics.success_count == 0
        assert metrics.total_calls == 0
        assert metrics.rejected_calls == 0
        assert metrics.last_failure_time is None
        assert metrics.last_state_change is None
