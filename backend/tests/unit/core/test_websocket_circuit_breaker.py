"""Unit tests for WebSocket circuit breaker.

Tests cover:
- State machine transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Failure count thresholds
- Recovery timeout behavior
- Success/failure tracking in different states
- Metrics serialization to dict
- Reset functionality
- Thread-safe async operations

Uses time mocking for deterministic timeout testing.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from backend.core.websocket_circuit_breaker import (
    WebSocketCircuitBreaker,
    WebSocketCircuitBreakerMetrics,
    WebSocketCircuitState,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def circuit_breaker() -> WebSocketCircuitBreaker:
    """Create a circuit breaker with default settings."""
    return WebSocketCircuitBreaker(
        failure_threshold=3,
        recovery_timeout=30.0,
        half_open_max_calls=1,
        success_threshold=1,
        name="test_breaker",
    )


@pytest.fixture
def low_threshold_breaker() -> WebSocketCircuitBreaker:
    """Create a circuit breaker with low thresholds for faster testing."""
    return WebSocketCircuitBreaker(
        failure_threshold=2,
        recovery_timeout=5.0,
        half_open_max_calls=2,
        success_threshold=2,
        name="low_threshold",
    )


# =============================================================================
# WebSocketCircuitState Tests
# =============================================================================


class TestWebSocketCircuitState:
    """Tests for WebSocketCircuitState enum."""

    def test_state_values(self) -> None:
        """Test that state enum has correct values."""
        assert WebSocketCircuitState.CLOSED.value == "closed"
        assert WebSocketCircuitState.OPEN.value == "open"
        assert WebSocketCircuitState.HALF_OPEN.value == "half_open"


# =============================================================================
# WebSocketCircuitBreakerMetrics Tests
# =============================================================================


class TestWebSocketCircuitBreakerMetrics:
    """Tests for WebSocketCircuitBreakerMetrics dataclass."""

    def test_metrics_to_dict_basic(self) -> None:
        """Test metrics serialization to dictionary."""
        metrics = WebSocketCircuitBreakerMetrics(
            state=WebSocketCircuitState.CLOSED,
            failure_count=0,
            success_count=0,
            total_failures=5,
            total_successes=100,
            last_failure_time=None,
            last_state_change=None,
            opened_at=None,
        )

        result = metrics.to_dict()

        assert result["state"] == "closed"
        assert result["failure_count"] == 0
        assert result["success_count"] == 0
        assert result["total_failures"] == 5
        assert result["total_successes"] == 100
        assert result["last_failure_time"] is None
        assert result["last_state_change"] is None
        assert result["opened_at"] is None

    def test_metrics_to_dict_with_timestamps(self) -> None:
        """Test metrics serialization with timestamps."""
        now = datetime.now(UTC)
        mono_time = 12345.678

        metrics = WebSocketCircuitBreakerMetrics(
            state=WebSocketCircuitState.OPEN,
            failure_count=3,
            success_count=0,
            total_failures=10,
            total_successes=50,
            last_failure_time=mono_time,
            last_state_change=now,
            opened_at=mono_time,
        )

        result = metrics.to_dict()

        assert result["state"] == "open"
        assert result["failure_count"] == 3
        assert result["last_failure_time"] == mono_time
        assert result["last_state_change"] == now.isoformat()
        assert result["opened_at"] == mono_time


# =============================================================================
# Circuit Breaker Initialization Tests
# =============================================================================


class TestCircuitBreakerInitialization:
    """Tests for circuit breaker initialization."""

    def test_initial_state_is_closed(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that initial state is CLOSED."""
        assert circuit_breaker.get_state() == WebSocketCircuitState.CLOSED

    def test_initial_failure_count_is_zero(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that initial failure count is zero."""
        assert circuit_breaker.failure_count == 0

    def test_properties_return_expected_values(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that properties return configuration values."""
        assert circuit_breaker.name == "test_breaker"
        assert circuit_breaker.failure_threshold == 3
        assert circuit_breaker.recovery_timeout == 30.0

    def test_last_failure_time_initially_none(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that last_failure_time is initially None."""
        assert circuit_breaker.last_failure_time is None


# =============================================================================
# State Transition Tests: CLOSED -> OPEN
# =============================================================================


class TestClosedToOpenTransition:
    """Tests for CLOSED to OPEN state transitions."""

    def test_stays_closed_below_threshold(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that circuit stays CLOSED below failure threshold."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == WebSocketCircuitState.CLOSED
        assert circuit_breaker.failure_count == 2

    def test_transitions_to_open_at_threshold(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that circuit transitions to OPEN at failure threshold."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == WebSocketCircuitState.OPEN
        assert circuit_breaker.failure_count == 3

    def test_success_resets_failure_count_in_closed(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that success resets failure count in CLOSED state."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_success()

        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.get_state() == WebSocketCircuitState.CLOSED

    def test_call_permitted_when_closed(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that calls are permitted in CLOSED state."""
        assert circuit_breaker.is_call_permitted() is True


# =============================================================================
# State Transition Tests: OPEN -> HALF_OPEN
# =============================================================================


class TestOpenToHalfOpenTransition:
    """Tests for OPEN to HALF_OPEN state transitions."""

    def test_call_not_permitted_when_open(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that calls are not permitted in OPEN state."""
        # Trigger OPEN state
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == WebSocketCircuitState.OPEN
        assert circuit_breaker.is_call_permitted() is False

    def test_transitions_to_half_open_after_timeout(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that circuit transitions to HALF_OPEN after recovery timeout."""
        # Trigger OPEN state
        for _ in range(3):
            circuit_breaker.record_failure()

        # Simulate time passing beyond recovery timeout
        with patch("time.monotonic") as mock_time:
            # Set current time to just after recovery timeout
            mock_time.return_value = circuit_breaker._opened_at + 35.0

            # is_call_permitted triggers the transition
            is_permitted = circuit_breaker.is_call_permitted()

        assert is_permitted is True
        assert circuit_breaker.get_state() == WebSocketCircuitState.HALF_OPEN

    def test_stays_open_before_timeout(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that circuit stays OPEN before recovery timeout."""
        # Trigger OPEN state
        for _ in range(3):
            circuit_breaker.record_failure()

        opened_at = circuit_breaker._opened_at

        # Simulate time still within recovery timeout
        with patch("time.monotonic", return_value=opened_at + 15.0):
            is_permitted = circuit_breaker.is_call_permitted()

        assert is_permitted is False
        assert circuit_breaker.get_state() == WebSocketCircuitState.OPEN


# =============================================================================
# State Transition Tests: HALF_OPEN -> CLOSED
# =============================================================================


class TestHalfOpenToClosedTransition:
    """Tests for HALF_OPEN to CLOSED state transitions."""

    def test_success_in_half_open_closes_circuit(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that success in HALF_OPEN transitions to CLOSED."""
        # Get to HALF_OPEN state
        for _ in range(3):
            circuit_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = circuit_breaker._opened_at + 35.0
            circuit_breaker.is_call_permitted()

        assert circuit_breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # Success should close the circuit
        circuit_breaker.record_success()

        assert circuit_breaker.get_state() == WebSocketCircuitState.CLOSED
        assert circuit_breaker.failure_count == 0

    def test_multiple_successes_required_to_close(
        self, low_threshold_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that multiple successes are required when success_threshold > 1."""
        # Get to HALF_OPEN state
        for _ in range(2):
            low_threshold_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = low_threshold_breaker._opened_at + 10.0
            low_threshold_breaker.is_call_permitted()

        assert low_threshold_breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # First success - still in HALF_OPEN
        low_threshold_breaker.record_success()
        assert low_threshold_breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # Second success - transitions to CLOSED
        low_threshold_breaker.record_success()
        assert low_threshold_breaker.get_state() == WebSocketCircuitState.CLOSED


# =============================================================================
# State Transition Tests: HALF_OPEN -> OPEN
# =============================================================================


class TestHalfOpenToOpenTransition:
    """Tests for HALF_OPEN to OPEN state transitions."""

    def test_failure_in_half_open_reopens_circuit(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that failure in HALF_OPEN transitions back to OPEN."""
        # Get to HALF_OPEN state
        for _ in range(3):
            circuit_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = circuit_breaker._opened_at + 35.0
            circuit_breaker.is_call_permitted()

        assert circuit_breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # Failure should reopen the circuit
        circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == WebSocketCircuitState.OPEN


# =============================================================================
# Half-Open Call Limiting Tests
# =============================================================================


class TestHalfOpenCallLimiting:
    """Tests for call limiting in HALF_OPEN state."""

    def test_limited_calls_in_half_open(
        self, low_threshold_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that calls are limited in HALF_OPEN state."""
        # Get to HALF_OPEN state
        for _ in range(2):
            low_threshold_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = low_threshold_breaker._opened_at + 10.0

            # First call is permitted and increments counter
            assert low_threshold_breaker.is_call_permitted() is True
            assert low_threshold_breaker._half_open_calls == 1

            # Second call is permitted (half_open_max_calls=2) and increments counter
            assert low_threshold_breaker.is_call_permitted() is True
            assert low_threshold_breaker._half_open_calls == 2

            # Third call is not permitted (reached max)
            assert low_threshold_breaker.is_call_permitted() is False
            # Counter should NOT increment when call is rejected
            assert low_threshold_breaker._half_open_calls == 2

    def test_half_open_calls_counter_increments_on_permitted_call(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that half_open_calls counter is incremented when call is permitted in HALF_OPEN state."""
        # Get to HALF_OPEN state
        for _ in range(3):
            circuit_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = circuit_breaker._opened_at + 35.0

            # Initial half_open_calls should be 0 after transition
            assert circuit_breaker._half_open_calls == 0

            # First permitted call should increment the counter
            assert circuit_breaker.is_call_permitted() is True
            assert circuit_breaker._half_open_calls == 1

            # Since half_open_max_calls=1, next call should be rejected
            assert circuit_breaker.is_call_permitted() is False
            # Counter should stay at 1 (not increment on rejection)
            assert circuit_breaker._half_open_calls == 1

    def test_half_open_calls_counter_reset_on_transition_to_open(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that half_open_calls counter is reset when transitioning back to OPEN."""
        # Get to HALF_OPEN state
        for _ in range(3):
            circuit_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = circuit_breaker._opened_at + 35.0
            assert circuit_breaker.is_call_permitted() is True
            assert circuit_breaker._half_open_calls == 1

        # Failure in HALF_OPEN transitions back to OPEN
        circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == WebSocketCircuitState.OPEN
        assert circuit_breaker._half_open_calls == 0


# =============================================================================
# Metrics Tracking Tests
# =============================================================================


class TestMetricsTracking:
    """Tests for metrics tracking functionality."""

    def test_total_failures_increments(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that total_failures counter increments on each failure."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_success()  # Reset failure count
        circuit_breaker.record_failure()

        metrics = circuit_breaker.get_metrics()
        assert metrics.total_failures == 3

    def test_total_successes_increments(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that total_successes counter increments on each success."""
        circuit_breaker.record_success()
        circuit_breaker.record_success()
        circuit_breaker.record_success()

        metrics = circuit_breaker.get_metrics()
        assert metrics.total_successes == 3

    def test_last_failure_time_updated(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that last_failure_time is updated on failure."""
        assert circuit_breaker.last_failure_time is None

        circuit_breaker.record_failure()

        assert circuit_breaker.last_failure_time is not None

    def test_get_metrics_returns_correct_state(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that get_metrics returns correct metrics object."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()

        metrics = circuit_breaker.get_metrics()

        assert isinstance(metrics, WebSocketCircuitBreakerMetrics)
        assert metrics.state == WebSocketCircuitState.CLOSED
        assert metrics.failure_count == 2
        assert metrics.total_failures == 2

    def test_get_status_returns_dict(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that get_status returns a dictionary with all info."""
        status = circuit_breaker.get_status()

        assert status["name"] == "test_breaker"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["config"]["failure_threshold"] == 3
        assert status["config"]["recovery_timeout"] == 30.0


# =============================================================================
# Reset Tests
# =============================================================================


class TestReset:
    """Tests for circuit breaker reset functionality."""

    def test_reset_returns_to_closed(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that reset returns circuit to CLOSED state."""
        # Get to OPEN state
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == WebSocketCircuitState.OPEN

        circuit_breaker.reset()

        assert circuit_breaker.get_state() == WebSocketCircuitState.CLOSED

    def test_reset_clears_failure_count(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that reset clears failure count."""
        for _ in range(3):
            circuit_breaker.record_failure()

        circuit_breaker.reset()

        assert circuit_breaker.failure_count == 0

    def test_reset_clears_opened_at(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that reset clears opened_at timestamp."""
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker._opened_at is not None

        circuit_breaker.reset()

        assert circuit_breaker._opened_at is None

    def test_reset_updates_last_state_change(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that reset updates last_state_change timestamp."""
        circuit_breaker.reset()

        assert circuit_breaker._last_state_change is not None


# =============================================================================
# Async Operations Tests
# =============================================================================


class TestAsyncOperations:
    """Tests for async/thread-safe operations."""

    @pytest.mark.asyncio
    async def test_is_call_permitted_async(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test async version of is_call_permitted."""
        result = await circuit_breaker.is_call_permitted_async()

        assert result is True

    @pytest.mark.asyncio
    async def test_record_success_async(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test async version of record_success."""
        await circuit_breaker.record_success_async()

        metrics = circuit_breaker.get_metrics()
        assert metrics.total_successes == 1

    @pytest.mark.asyncio
    async def test_record_failure_async(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test async version of record_failure."""
        await circuit_breaker.record_failure_async()

        assert circuit_breaker.failure_count == 1

    @pytest.mark.asyncio
    async def test_reset_async(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test async version of reset."""
        for _ in range(3):
            circuit_breaker.record_failure()

        await circuit_breaker.reset_async()

        assert circuit_breaker.get_state() == WebSocketCircuitState.CLOSED


# =============================================================================
# String Representation Tests
# =============================================================================


class TestStringRepresentation:
    """Tests for string representation methods."""

    def test_str_representation(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test __str__ method."""
        result = str(circuit_breaker)

        assert "test_breaker" in result
        assert "CLOSED" in result

    def test_repr_representation(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test __repr__ method."""
        result = repr(circuit_breaker)

        assert "test_breaker" in result
        assert "closed" in result
        assert "failures=0" in result

    def test_str_changes_with_state(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that string representation reflects state changes."""
        for _ in range(3):
            circuit_breaker.record_failure()

        result = str(circuit_breaker)

        assert "OPEN" in result


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_success_in_closed_with_no_failures(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that success in CLOSED with no failures is a no-op for count."""
        circuit_breaker.record_success()

        assert circuit_breaker.failure_count == 0

    def test_opened_at_none_before_first_open(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that opened_at is None before circuit opens."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()

        assert circuit_breaker._opened_at is None

    def test_opened_at_set_when_opened(self, circuit_breaker: WebSocketCircuitBreaker) -> None:
        """Test that opened_at is set when circuit opens."""
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker._opened_at is not None

    def test_half_open_success_count_reset_on_open(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that success_count is reset when transitioning to OPEN."""
        # Get to HALF_OPEN and record a success
        for _ in range(3):
            circuit_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = circuit_breaker._opened_at + 35.0
            circuit_breaker.is_call_permitted()

        # Record failure in HALF_OPEN (reopens circuit)
        circuit_breaker.record_failure()

        assert circuit_breaker._success_count == 0

    def test_recovery_not_attempted_when_opened_at_is_none(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that _should_attempt_recovery returns False if opened_at is None."""
        # Manually set state without opened_at
        circuit_breaker._state = WebSocketCircuitState.OPEN
        circuit_breaker._opened_at = None

        result = circuit_breaker._should_attempt_recovery()

        assert result is False

    def test_last_state_change_updated_on_all_transitions(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that last_state_change is updated on all state transitions."""
        # CLOSED -> OPEN
        for _ in range(3):
            circuit_breaker.record_failure()

        open_time = circuit_breaker._last_state_change
        assert open_time is not None

        # OPEN -> HALF_OPEN
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = circuit_breaker._opened_at + 35.0
            circuit_breaker.is_call_permitted()

        half_open_time = circuit_breaker._last_state_change
        assert half_open_time is not None
        assert half_open_time >= open_time

        # HALF_OPEN -> CLOSED
        circuit_breaker.record_success()

        closed_time = circuit_breaker._last_state_change
        assert closed_time is not None
        assert closed_time >= half_open_time


# =============================================================================
# Complete State Machine Cycle Tests
# =============================================================================


class TestCompleteStateMachineCycle:
    """Tests for complete state machine cycles."""

    def test_full_cycle_closed_open_half_open_closed(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test a complete cycle through all states."""
        # Start in CLOSED
        assert circuit_breaker.get_state() == WebSocketCircuitState.CLOSED
        assert circuit_breaker.is_call_permitted() is True

        # Transition to OPEN
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == WebSocketCircuitState.OPEN
        assert circuit_breaker.is_call_permitted() is False

        # Transition to HALF_OPEN after timeout
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = circuit_breaker._opened_at + 35.0
            is_permitted = circuit_breaker.is_call_permitted()

        assert is_permitted is True
        assert circuit_breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # Transition back to CLOSED
        circuit_breaker.record_success()

        assert circuit_breaker.get_state() == WebSocketCircuitState.CLOSED
        assert circuit_breaker.is_call_permitted() is True
        assert circuit_breaker.failure_count == 0

    def test_cycle_with_failure_in_half_open(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test cycle where failure in HALF_OPEN returns to OPEN."""
        # Get to OPEN
        for _ in range(3):
            circuit_breaker.record_failure()

        # Get to HALF_OPEN
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = circuit_breaker._opened_at + 35.0
            circuit_breaker.is_call_permitted()

        assert circuit_breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # Failure returns to OPEN
        circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == WebSocketCircuitState.OPEN

        # Another recovery cycle
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = circuit_breaker._opened_at + 35.0
            circuit_breaker.is_call_permitted()

        assert circuit_breaker.get_state() == WebSocketCircuitState.HALF_OPEN

        # Success closes the circuit
        circuit_breaker.record_success()

        assert circuit_breaker.get_state() == WebSocketCircuitState.CLOSED


# =============================================================================
# Redis Persistence Tests
# =============================================================================


class TestRedisPersistence:
    """Tests for Redis persistence functionality."""

    @pytest.fixture
    def mock_redis(self) -> Any:
        """Create a mock Redis client."""
        from unittest.mock import AsyncMock, MagicMock

        mock = MagicMock()
        mock.set = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=None)
        mock.delete = AsyncMock(return_value=1)
        return mock

    @pytest.fixture
    def breaker_with_redis(self, mock_redis: Any) -> WebSocketCircuitBreaker:
        """Create a circuit breaker with mock Redis client."""
        return WebSocketCircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
            name="test_redis_breaker",
            redis_client=mock_redis,
        )

    def test_redis_key_format(self, breaker_with_redis: WebSocketCircuitBreaker) -> None:
        """Test that Redis key has correct format."""
        key = breaker_with_redis._get_redis_key()
        assert key == "circuit_breaker:test_redis_breaker"

    def test_redis_state_ttl_constant(self) -> None:
        """Test that REDIS_STATE_TTL is 5 minutes (300 seconds)."""
        assert WebSocketCircuitBreaker.REDIS_STATE_TTL == 300

    @pytest.mark.asyncio
    async def test_persist_state_without_redis(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that persist_state is a no-op without Redis."""
        # Should not raise any errors
        await circuit_breaker._persist_state()

    @pytest.mark.asyncio
    async def test_persist_state_with_redis(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that persist_state calls Redis set with correct data."""
        import json

        # Trigger a state to persist
        breaker_with_redis._state = WebSocketCircuitState.OPEN
        breaker_with_redis._failure_count = 3
        breaker_with_redis._opened_at = 12345.0
        breaker_with_redis._consecutive_half_open_failures = 2
        breaker_with_redis._current_backoff_delay = 4.0
        breaker_with_redis._backoff_expires_at = 12349.0

        await breaker_with_redis._persist_state()

        # Verify Redis set was called
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args

        # Check key
        assert call_args[0][0] == "circuit_breaker:test_redis_breaker"

        # Check data
        stored_data = json.loads(call_args[0][1])
        assert stored_data["state"] == "open"
        assert stored_data["failure_count"] == 3
        assert stored_data["opened_at"] == 12345.0
        assert stored_data["consecutive_half_open_failures"] == 2
        assert stored_data["current_backoff_delay"] == 4.0
        assert stored_data["backoff_expires_at"] == 12349.0

        # Check TTL
        assert call_args[1]["expire"] == 300

    @pytest.mark.asyncio
    async def test_persist_state_handles_redis_error(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that persist_state handles Redis errors gracefully."""
        mock_redis.set.side_effect = OSError("Redis connection error")

        # Should not raise, just log warning
        await breaker_with_redis._persist_state()

    @pytest.mark.asyncio
    async def test_restore_state_without_redis(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that restore_state returns False without Redis."""
        result = await circuit_breaker.restore_state_from_redis()
        assert result is False

    @pytest.mark.asyncio
    async def test_restore_state_no_data_in_redis(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that restore_state returns False when no data exists."""
        mock_redis.get.return_value = None

        result = await breaker_with_redis.restore_state_from_redis()

        assert result is False
        assert breaker_with_redis.get_state() == WebSocketCircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_restore_state_from_redis(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that restore_state correctly restores state from Redis."""
        import json

        stored_data = {
            "state": "open",
            "failure_count": 5,
            "opened_at": 12345.0,
            "consecutive_half_open_failures": 3,
            "current_backoff_delay": 8.0,
            "backoff_expires_at": 12353.0,
        }
        mock_redis.get.return_value = json.dumps(stored_data)

        result = await breaker_with_redis.restore_state_from_redis()

        assert result is True
        assert breaker_with_redis.get_state() == WebSocketCircuitState.OPEN
        assert breaker_with_redis._failure_count == 5
        assert breaker_with_redis._consecutive_half_open_failures == 3
        assert breaker_with_redis._current_backoff_delay == 8.0
        # opened_at should be set to current time, not the stored value
        assert breaker_with_redis._opened_at is not None

    @pytest.mark.asyncio
    async def test_restore_state_with_dict_response(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that restore_state handles dict response (pre-parsed JSON)."""
        stored_data = {
            "state": "half_open",
            "failure_count": 2,
            "opened_at": None,
            "consecutive_half_open_failures": 0,
            "current_backoff_delay": 0.0,
            "backoff_expires_at": None,
        }
        mock_redis.get.return_value = stored_data

        result = await breaker_with_redis.restore_state_from_redis()

        assert result is True
        assert breaker_with_redis.get_state() == WebSocketCircuitState.HALF_OPEN
        assert breaker_with_redis._failure_count == 2

    @pytest.mark.asyncio
    async def test_restore_state_handles_invalid_json(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that restore_state handles invalid JSON gracefully."""
        mock_redis.get.return_value = "invalid json {"

        result = await breaker_with_redis.restore_state_from_redis()

        assert result is False
        # Should remain in default CLOSED state
        assert breaker_with_redis.get_state() == WebSocketCircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_restore_state_handles_redis_error(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that restore_state handles Redis errors gracefully."""
        mock_redis.get.side_effect = OSError("Redis connection error")

        result = await breaker_with_redis.restore_state_from_redis()

        assert result is False
        assert breaker_with_redis.get_state() == WebSocketCircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_clear_persisted_state_without_redis(
        self, circuit_breaker: WebSocketCircuitBreaker
    ) -> None:
        """Test that clear_persisted_state returns False without Redis."""
        result = await circuit_breaker.clear_persisted_state()
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_persisted_state_with_redis(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that clear_persisted_state calls Redis delete."""
        result = await breaker_with_redis.clear_persisted_state()

        assert result is True
        mock_redis.delete.assert_called_once_with("circuit_breaker:test_redis_breaker")

    @pytest.mark.asyncio
    async def test_clear_persisted_state_handles_redis_error(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that clear_persisted_state handles Redis errors gracefully."""
        mock_redis.delete.side_effect = OSError("Redis connection error")

        result = await breaker_with_redis.clear_persisted_state()

        assert result is False


class TestRedisPersistenceOnStateTransitions:
    """Tests for automatic Redis persistence on state transitions."""

    @pytest.fixture
    def mock_redis(self) -> Any:
        """Create a mock Redis client."""
        from unittest.mock import AsyncMock, MagicMock

        mock = MagicMock()
        mock.set = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=None)
        mock.delete = AsyncMock(return_value=1)
        return mock

    @pytest.fixture
    def breaker_with_redis(self, mock_redis: Any) -> WebSocketCircuitBreaker:
        """Create a circuit breaker with mock Redis client."""
        return WebSocketCircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
            name="test_persist_breaker",
            redis_client=mock_redis,
        )

    @pytest.mark.asyncio
    async def test_persists_on_closed_to_open_transition(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that state is persisted when transitioning CLOSED -> OPEN."""
        # Record failures to trigger OPEN state
        await breaker_with_redis.record_failure_async()
        await breaker_with_redis.record_failure_async()
        mock_redis.set.reset_mock()  # Clear previous calls

        await breaker_with_redis.record_failure_async()  # Triggers OPEN

        assert breaker_with_redis.get_state() == WebSocketCircuitState.OPEN
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_persists_on_open_to_half_open_transition(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that state is persisted when transitioning OPEN -> HALF_OPEN."""
        # Get to OPEN state
        for _ in range(3):
            await breaker_with_redis.record_failure_async()

        mock_redis.set.reset_mock()

        # Transition to HALF_OPEN
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = breaker_with_redis._opened_at + 35.0
            await breaker_with_redis.is_call_permitted_async()

        assert breaker_with_redis.get_state() == WebSocketCircuitState.HALF_OPEN
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_persists_on_half_open_to_closed_transition(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that state is persisted when transitioning HALF_OPEN -> CLOSED."""
        # Get to HALF_OPEN state
        for _ in range(3):
            await breaker_with_redis.record_failure_async()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = breaker_with_redis._opened_at + 35.0
            await breaker_with_redis.is_call_permitted_async()

        mock_redis.set.reset_mock()

        # Transition to CLOSED
        await breaker_with_redis.record_success_async()

        assert breaker_with_redis.get_state() == WebSocketCircuitState.CLOSED
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_persists_on_half_open_to_open_transition(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that state is persisted when transitioning HALF_OPEN -> OPEN."""
        # Get to HALF_OPEN state
        for _ in range(3):
            await breaker_with_redis.record_failure_async()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = breaker_with_redis._opened_at + 35.0
            await breaker_with_redis.is_call_permitted_async()

        mock_redis.set.reset_mock()

        # Transition back to OPEN
        await breaker_with_redis.record_failure_async()

        assert breaker_with_redis.get_state() == WebSocketCircuitState.OPEN
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_persist_when_state_unchanged(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that state is NOT persisted when no transition occurs."""
        # Record failures without triggering OPEN
        await breaker_with_redis.record_failure_async()
        mock_redis.set.reset_mock()

        await breaker_with_redis.record_failure_async()  # Still in CLOSED

        assert breaker_with_redis.get_state() == WebSocketCircuitState.CLOSED
        mock_redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_reset_async_clears_and_persists(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that reset_async clears persisted state and persists new state."""
        # Get to OPEN state
        for _ in range(3):
            await breaker_with_redis.record_failure_async()

        mock_redis.set.reset_mock()
        mock_redis.delete.reset_mock()

        # Reset
        await breaker_with_redis.reset_async()

        assert breaker_with_redis.get_state() == WebSocketCircuitState.CLOSED
        mock_redis.delete.assert_called_once()
        mock_redis.set.assert_called_once()


class TestRestoreStateTimestampAdjustment:
    """Tests for timestamp adjustment when restoring state from Redis."""

    @pytest.fixture
    def mock_redis(self) -> Any:
        """Create a mock Redis client."""
        from unittest.mock import AsyncMock, MagicMock

        mock = MagicMock()
        mock.set = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=None)
        mock.delete = AsyncMock(return_value=1)
        return mock

    @pytest.fixture
    def breaker_with_redis(self, mock_redis: Any) -> WebSocketCircuitBreaker:
        """Create a circuit breaker with mock Redis client."""
        return WebSocketCircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
            name="test_timestamp_breaker",
            redis_client=mock_redis,
        )

    @pytest.mark.asyncio
    async def test_opened_at_adjusted_to_current_time(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that opened_at is adjusted to current monotonic time on restore."""
        import json

        stored_data = {
            "state": "open",
            "failure_count": 3,
            "opened_at": 1000.0,  # Old timestamp from previous process
            "consecutive_half_open_failures": 0,
            "current_backoff_delay": 0.0,
            "backoff_expires_at": None,
        }
        mock_redis.get.return_value = json.dumps(stored_data)

        with patch("time.monotonic", return_value=5000.0):
            await breaker_with_redis.restore_state_from_redis()

        # opened_at should be set to current time (5000.0), not the stored value
        assert breaker_with_redis._opened_at == 5000.0

    @pytest.mark.asyncio
    async def test_backoff_expires_at_recalculated(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that backoff_expires_at is recalculated on restore."""
        import json

        stored_data = {
            "state": "open",
            "failure_count": 3,
            "opened_at": 1000.0,
            "consecutive_half_open_failures": 2,
            "current_backoff_delay": 4.0,
            "backoff_expires_at": 1010.0,  # Old timestamp
        }
        mock_redis.get.return_value = json.dumps(stored_data)

        with patch("time.monotonic", return_value=5000.0):
            await breaker_with_redis.restore_state_from_redis()

        # backoff_expires_at should be current_time + current_backoff_delay
        assert breaker_with_redis._backoff_expires_at == 5004.0

    @pytest.mark.asyncio
    async def test_opened_at_not_set_for_closed_state(
        self, breaker_with_redis: WebSocketCircuitBreaker, mock_redis: Any
    ) -> None:
        """Test that opened_at is not set when restoring CLOSED state."""
        import json

        stored_data = {
            "state": "closed",
            "failure_count": 0,
            "opened_at": 1000.0,  # Should be ignored for CLOSED state
            "consecutive_half_open_failures": 0,
            "current_backoff_delay": 0.0,
            "backoff_expires_at": None,
        }
        mock_redis.get.return_value = json.dumps(stored_data)

        await breaker_with_redis.restore_state_from_redis()

        # opened_at should remain None for CLOSED state
        assert breaker_with_redis._opened_at is None
