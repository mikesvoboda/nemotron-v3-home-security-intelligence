"""Unit tests for circuit breaker pattern implementation.

Tests cover:
- CircuitBreakerConfig state transitions
- CircuitBreaker state machine (CLOSED -> OPEN -> HALF_OPEN)
- Failure counting and threshold handling
- Half-open state trial behavior
- Recovery and reset logic
- Circuit breaker registry operations
"""

import asyncio

import pytest

from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker,
    reset_circuit_breaker_registry,
)


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 30.0
        assert config.half_open_max_calls == 3
        assert config.success_threshold == 2
        assert config.excluded_exceptions == ()

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=60.0,
            half_open_max_calls=5,
            success_threshold=3,
            excluded_exceptions=(ValueError,),
        )
        assert config.failure_threshold == 10
        assert config.recovery_timeout == 60.0
        assert config.half_open_max_calls == 5
        assert config.success_threshold == 3
        assert config.excluded_exceptions == (ValueError,)


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_state_values(self) -> None:
        """Test circuit state enum values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.fixture
    def config(self) -> CircuitBreakerConfig:
        """Create a test configuration."""
        return CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=0.1,  # Fast for testing
            half_open_max_calls=2,
            success_threshold=2,
        )

    @pytest.fixture
    def breaker(self, config: CircuitBreakerConfig) -> CircuitBreaker:
        """Create a circuit breaker with test config."""
        return CircuitBreaker(name="test_service", config=config)

    def test_initial_state_is_closed(self, breaker: CircuitBreaker) -> None:
        """Test that initial state is CLOSED."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.is_closed is True
        assert breaker.is_open is False

    def test_name_property(self, breaker: CircuitBreaker) -> None:
        """Test name property."""
        assert breaker.name == "test_service"

    @pytest.mark.asyncio
    async def test_successful_call_stays_closed(self, breaker: CircuitBreaker) -> None:
        """Test that successful calls keep circuit closed."""

        async def success_op() -> str:
            return "success"

        result = await breaker.call(success_op)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_failures_increment_count(self, breaker: CircuitBreaker) -> None:
        """Test that failures increment the failure count."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        assert breaker.failure_count == 1
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_threshold_exceeded_opens_circuit(self, breaker: CircuitBreaker) -> None:
        """Test that exceeding failure threshold opens circuit."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Fail 3 times (threshold is 3)
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open is True
        assert breaker.is_closed is False

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self, breaker: CircuitBreaker) -> None:
        """Test that open circuit rejects calls immediately."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        # Now try another call - should be rejected
        async def should_not_run() -> str:
            return "should not reach"

        with pytest.raises(CircuitBreakerError) as exc_info:
            await breaker.call(should_not_run)

        assert "test_service" in str(exc_info.value)
        assert "open" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_recovery_timeout_transitions_to_half_open(self, breaker: CircuitBreaker) -> None:
        """Test that recovery timeout transitions circuit to half-open."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next call should be allowed (half-open)
        async def success_op() -> str:
            return "success"

        result = await breaker.call(success_op)
        assert result == "success"
        # After one success in half-open, still half-open (need success_threshold)
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self, breaker: CircuitBreaker) -> None:
        """Test that enough successes in half-open closes circuit."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        await asyncio.sleep(0.15)

        async def success_op() -> str:
            return "success"

        # Need 2 successes (success_threshold)
        await breaker.call(success_op)
        assert breaker.state == CircuitState.HALF_OPEN

        await breaker.call(success_op)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self, breaker: CircuitBreaker) -> None:
        """Test that failure in half-open reopens circuit."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        await asyncio.sleep(0.15)

        # Fail in half-open state
        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_excluded_exceptions_not_counted(self) -> None:
        """Test that excluded exceptions don't count as failures."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=0.1,
            excluded_exceptions=(ValueError,),
        )
        breaker = CircuitBreaker(name="test", config=config)

        async def raises_value_error() -> str:
            raise ValueError("Not a failure")

        # These should not count as failures
        for _ in range(5):
            with pytest.raises(ValueError):
                await breaker.call(raises_value_error)

        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_manual_reset(self, breaker: CircuitBreaker) -> None:
        """Test manual circuit reset."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        assert breaker.state == CircuitState.OPEN

        # Manual reset
        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_call_with_args_kwargs(self, breaker: CircuitBreaker) -> None:
        """Test that args and kwargs are passed to operation."""

        async def op_with_args(x: int, y: str, z: bool = False) -> dict:
            return {"x": x, "y": y, "z": z}

        result = await breaker.call(op_with_args, 42, "hello", z=True)
        assert result == {"x": 42, "y": "hello", "z": True}

    def test_get_status(self, breaker: CircuitBreaker) -> None:
        """Test getting circuit breaker status."""
        status = breaker.get_status()
        assert status["name"] == "test_service"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert "last_failure_time" in status
        assert "opened_at" in status

    @pytest.mark.asyncio
    async def test_half_open_max_calls_limit(self, breaker: CircuitBreaker) -> None:
        """Test that half-open limits concurrent trial calls."""

        async def failing_op() -> str:
            raise ConnectionError("Failed")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await breaker.call(failing_op)

        await asyncio.sleep(0.15)

        # In half-open, we should be limited
        call_count = 0

        async def tracked_success() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        # First two calls allowed (half_open_max_calls=2)
        await breaker.call(tracked_success)
        assert call_count == 1

        # After success_threshold successes, circuit closes
        await breaker.call(tracked_success)
        assert call_count == 2
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry class."""

    def setup_method(self) -> None:
        """Reset registry before each test."""
        reset_circuit_breaker_registry()

    def teardown_method(self) -> None:
        """Reset registry after each test."""
        reset_circuit_breaker_registry()

    def test_get_or_create_returns_same_instance(self) -> None:
        """Test that getting same name returns same instance."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig()

        breaker1 = registry.get_or_create("service_a", config)
        breaker2 = registry.get_or_create("service_a", config)

        assert breaker1 is breaker2

    def test_different_names_create_different_instances(self) -> None:
        """Test that different names create different instances."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig()

        breaker1 = registry.get_or_create("service_a", config)
        breaker2 = registry.get_or_create("service_b", config)

        assert breaker1 is not breaker2
        assert breaker1.name == "service_a"
        assert breaker2.name == "service_b"

    def test_get_returns_existing_breaker(self) -> None:
        """Test that get returns existing breaker."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig()

        registry.get_or_create("service_a", config)
        breaker = registry.get("service_a")

        assert breaker is not None
        assert breaker.name == "service_a"

    def test_get_returns_none_for_nonexistent(self) -> None:
        """Test that get returns None for nonexistent service."""
        registry = CircuitBreakerRegistry()
        breaker = registry.get("nonexistent")
        assert breaker is None

    def test_get_all_status(self) -> None:
        """Test getting status of all circuit breakers."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig()

        registry.get_or_create("service_a", config)
        registry.get_or_create("service_b", config)

        status = registry.get_all_status()

        assert "service_a" in status
        assert "service_b" in status
        assert status["service_a"]["state"] == "closed"
        assert status["service_b"]["state"] == "closed"

    def test_reset_all(self) -> None:
        """Test resetting all circuit breakers."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60)

        breaker_a = registry.get_or_create("service_a", config)
        breaker_b = registry.get_or_create("service_b", config)

        # Open both circuits manually
        breaker_a._state = CircuitState.OPEN
        breaker_a._failure_count = 5
        breaker_b._state = CircuitState.OPEN
        breaker_b._failure_count = 3

        registry.reset_all()

        assert breaker_a.state == CircuitState.CLOSED
        assert breaker_a.failure_count == 0
        assert breaker_b.state == CircuitState.CLOSED
        assert breaker_b.failure_count == 0

    def test_list_names(self) -> None:
        """Test listing all circuit breaker names."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig()

        registry.get_or_create("service_a", config)
        registry.get_or_create("service_b", config)
        registry.get_or_create("service_c", config)

        names = registry.list_names()

        assert len(names) == 3
        assert "service_a" in names
        assert "service_b" in names
        assert "service_c" in names


class TestGlobalCircuitBreaker:
    """Tests for global circuit breaker functions."""

    def setup_method(self) -> None:
        """Reset global state before each test."""
        reset_circuit_breaker_registry()

    def teardown_method(self) -> None:
        """Reset global state after each test."""
        reset_circuit_breaker_registry()

    def test_get_circuit_breaker_creates_singleton(self) -> None:
        """Test that get_circuit_breaker returns consistent instance."""
        config = CircuitBreakerConfig()
        breaker1 = get_circuit_breaker("my_service", config)
        breaker2 = get_circuit_breaker("my_service")

        assert breaker1 is breaker2

    def test_get_circuit_breaker_with_default_config(self) -> None:
        """Test getting circuit breaker with default config."""
        breaker = get_circuit_breaker("default_service")
        assert breaker is not None
        assert breaker.name == "default_service"

    def test_reset_clears_all_breakers(self) -> None:
        """Test reset clears all registered breakers."""
        config = CircuitBreakerConfig()
        breaker1 = get_circuit_breaker("service_a", config)

        reset_circuit_breaker_registry()

        breaker2 = get_circuit_breaker("service_a", config)
        # After reset, should be a new instance
        assert breaker1 is not breaker2


class TestCircuitBreakerError:
    """Tests for CircuitBreakerError exception."""

    def test_error_message(self) -> None:
        """Test error message formatting."""
        error = CircuitBreakerError("test_service", "open")
        assert "test_service" in str(error)
        assert "open" in str(error)

    def test_error_attributes(self) -> None:
        """Test error attributes."""
        error = CircuitBreakerError("test_service", "open")
        assert error.service_name == "test_service"
        assert error.state == "open"


class TestCircuitBreakerConcurrency:
    """Tests for circuit breaker thread safety."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_tracked_correctly(self) -> None:
        """Test that concurrent calls are tracked correctly."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=1.0,
        )
        breaker = CircuitBreaker(name="concurrent_test", config=config)

        call_count = 0

        async def tracked_op() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return "success"

        # Run 5 concurrent calls
        tasks = [breaker.call(tracked_op) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert all(r == "success" for r in results)
        assert call_count == 5

    @pytest.mark.asyncio
    async def test_concurrent_failures_open_circuit(self) -> None:
        """Test that concurrent failures correctly open circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
        )
        breaker = CircuitBreaker(name="concurrent_fail_test", config=config)

        async def failing_op() -> str:
            await asyncio.sleep(0.01)
            raise ConnectionError("Concurrent failure")

        # Run 3 concurrent failing calls
        tasks = [breaker.call(failing_op) for _ in range(3)]

        with pytest.raises(ConnectionError):
            await asyncio.gather(*tasks)

        # Circuit should be open after threshold failures
        assert breaker.state == CircuitState.OPEN


class TestCircuitBreakerTimingBehavior:
    """Tests for circuit breaker timing behavior."""

    @pytest.mark.asyncio
    async def test_opened_at_timestamp_set(self) -> None:
        """Test that opened_at timestamp is set when circuit opens."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
        )
        breaker = CircuitBreaker(name="timing_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        assert breaker.state == CircuitState.OPEN
        status = breaker.get_status()
        assert status["opened_at"] is not None

    @pytest.mark.asyncio
    async def test_last_failure_time_updated(self) -> None:
        """Test that last_failure_time is updated on each failure."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
        )
        breaker = CircuitBreaker(name="failure_time_test", config=config)

        async def failing_op() -> str:
            raise ConnectionError("Fail")

        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        status1 = breaker.get_status()
        time1 = status1["last_failure_time"]
        assert time1 is not None

        await asyncio.sleep(0.05)

        with pytest.raises(ConnectionError):
            await breaker.call(failing_op)

        status2 = breaker.get_status()
        time2 = status2["last_failure_time"]
        assert time2 is not None
        assert time2 >= time1
