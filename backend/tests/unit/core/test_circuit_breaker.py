"""Unit tests for the shared Circuit Breaker utility.

NOTE: These tests import from backend.core.circuit_breaker which re-exports
from backend.services.circuit_breaker. The canonical implementation is in
backend.services.circuit_breaker.

Tests cover:
- State machine transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Failure count thresholds
- Recovery timeout behavior
- Success/failure tracking in different states
- Prometheus metrics integration
- Reset functionality
- Thread-safe async operations
- Concurrent access patterns

Uses time mocking for deterministic timeout testing.
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    """Create a circuit breaker with default settings."""
    return CircuitBreaker(
        name="test_service",
        failure_threshold=5,
        recovery_timeout=60.0,
        half_open_max_calls=3,
    )


@pytest.fixture
def low_threshold_breaker() -> CircuitBreaker:
    """Create a circuit breaker with low thresholds for faster testing."""
    return CircuitBreaker(
        name="low_threshold",
        failure_threshold=2,
        recovery_timeout=5.0,
        half_open_max_calls=2,
    )


@pytest.fixture
def florence_breaker() -> CircuitBreaker:
    """Create a circuit breaker configured like the Florence client example."""
    return CircuitBreaker(
        name="florence",
        failure_threshold=5,
        recovery_timeout=60,
        half_open_max_calls=3,
    )


# =============================================================================
# CircuitState Enum Tests
# =============================================================================


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_state_values(self) -> None:
        """Test that state enum has correct values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_states_are_distinct(self) -> None:
        """Test that all states are distinct."""
        states = [CircuitState.CLOSED, CircuitState.OPEN, CircuitState.HALF_OPEN]
        assert len(states) == len(set(states))


# =============================================================================
# Circuit Breaker Initialization Tests
# =============================================================================


class TestCircuitBreakerInitialization:
    """Tests for circuit breaker initialization."""

    def test_initial_state_is_closed(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that initial state is CLOSED."""
        assert circuit_breaker.get_state() == CircuitState.CLOSED

    def test_initial_failure_count_is_zero(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that initial failure count is zero."""
        assert circuit_breaker._failure_count == 0

    def test_constructor_parameters(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that constructor parameters are stored correctly."""
        assert circuit_breaker._name == "test_service"
        assert circuit_breaker._config.failure_threshold == 5
        assert circuit_breaker._config.recovery_timeout == 60.0
        assert circuit_breaker._config.half_open_max_calls == 3

    def test_default_parameters(self) -> None:
        """Test default parameter values."""
        cb = CircuitBreaker(name="default_test")
        assert cb._config.failure_threshold == 5
        assert cb._config.recovery_timeout == 30.0  # Default is 30.0
        assert cb._config.half_open_max_calls == 3

    def test_custom_parameters(self) -> None:
        """Test custom parameter values."""
        cb = CircuitBreaker(
            name="custom",
            failure_threshold=10,
            recovery_timeout=120.0,
            half_open_max_calls=5,
        )
        assert cb._config.failure_threshold == 10
        assert cb._config.recovery_timeout == 120.0
        assert cb._config.half_open_max_calls == 5


# =============================================================================
# State Transition Tests: CLOSED -> OPEN
# =============================================================================


class TestClosedToOpenTransition:
    """Tests for CLOSED to OPEN state transitions."""

    def test_stays_closed_below_threshold(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that circuit stays CLOSED below failure threshold."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker._failure_count == 4

    def test_transitions_to_open_at_threshold(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that circuit transitions to OPEN at failure threshold."""
        for _ in range(5):
            circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == CircuitState.OPEN
        assert circuit_breaker._failure_count == 5

    def test_success_resets_failure_count_in_closed(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that success resets failure count in CLOSED state."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_success()

        assert circuit_breaker._failure_count == 0
        assert circuit_breaker.get_state() == CircuitState.CLOSED

    def test_allow_request_true_when_closed(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that allow_request returns True in CLOSED state."""
        assert circuit_breaker.allow_request() is True


# =============================================================================
# State Transition Tests: OPEN State Behavior
# =============================================================================


class TestOpenStateBehavior:
    """Tests for behavior in OPEN state."""

    def test_allow_request_false_when_open(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that allow_request returns False in OPEN state."""
        # Trigger OPEN state
        for _ in range(5):
            circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == CircuitState.OPEN
        assert circuit_breaker.allow_request() is False

    def test_multiple_requests_rejected_when_open(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that multiple requests are rejected in OPEN state."""
        for _ in range(5):
            circuit_breaker.record_failure()

        # All subsequent requests should be rejected
        for _ in range(10):
            assert circuit_breaker.allow_request() is False


# =============================================================================
# State Transition Tests: OPEN -> HALF_OPEN
# =============================================================================


class TestOpenToHalfOpenTransition:
    """Tests for OPEN to HALF_OPEN state transitions."""

    def test_transitions_to_half_open_after_timeout(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that circuit transitions to HALF_OPEN after recovery timeout."""
        # Trigger OPEN state
        for _ in range(5):
            circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == CircuitState.OPEN

        # Simulate time passing beyond recovery timeout
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = circuit_breaker._opened_at + 65.0

            # allow_request triggers the transition
            is_permitted = circuit_breaker.allow_request()

        assert is_permitted is True
        assert circuit_breaker.get_state() == CircuitState.HALF_OPEN

    def test_stays_open_before_timeout(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that circuit stays OPEN before recovery timeout."""
        # Trigger OPEN state
        for _ in range(5):
            circuit_breaker.record_failure()

        opened_at = circuit_breaker._opened_at

        # Simulate time still within recovery timeout
        with patch("time.monotonic", return_value=opened_at + 30.0):
            is_permitted = circuit_breaker.allow_request()

        assert is_permitted is False
        assert circuit_breaker.get_state() == CircuitState.OPEN


# =============================================================================
# State Transition Tests: HALF_OPEN -> CLOSED
# =============================================================================


class TestHalfOpenToClosedTransition:
    """Tests for HALF_OPEN to CLOSED state transitions."""

    def test_success_in_half_open_closes_circuit(
        self, low_threshold_breaker: CircuitBreaker
    ) -> None:
        """Test that enough successes in HALF_OPEN transitions to CLOSED."""
        # Get to HALF_OPEN state
        for _ in range(2):
            low_threshold_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = low_threshold_breaker._opened_at + 10.0
            low_threshold_breaker.allow_request()

        assert low_threshold_breaker.get_state() == CircuitState.HALF_OPEN

        # Need enough successes to close (success_threshold defaults to 2)
        low_threshold_breaker.record_success()
        low_threshold_breaker.record_success()

        assert low_threshold_breaker.get_state() == CircuitState.CLOSED
        assert low_threshold_breaker._failure_count == 0


# =============================================================================
# State Transition Tests: HALF_OPEN -> OPEN
# =============================================================================


class TestHalfOpenToOpenTransition:
    """Tests for HALF_OPEN to OPEN state transitions."""

    def test_failure_in_half_open_reopens_circuit(
        self, low_threshold_breaker: CircuitBreaker
    ) -> None:
        """Test that failure in HALF_OPEN transitions back to OPEN."""
        # Get to HALF_OPEN state
        for _ in range(2):
            low_threshold_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = low_threshold_breaker._opened_at + 10.0
            low_threshold_breaker.allow_request()

        assert low_threshold_breaker.get_state() == CircuitState.HALF_OPEN

        # Failure should reopen the circuit
        low_threshold_breaker.record_failure()

        assert low_threshold_breaker.get_state() == CircuitState.OPEN


# =============================================================================
# Half-Open Call Limiting Tests
# =============================================================================


class TestHalfOpenCallLimiting:
    """Tests for call limiting in HALF_OPEN state."""

    def test_limited_calls_in_half_open(self, low_threshold_breaker: CircuitBreaker) -> None:
        """Test that calls are limited in HALF_OPEN state."""
        # Get to HALF_OPEN state
        for _ in range(2):
            low_threshold_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = low_threshold_breaker._opened_at + 10.0

            # First call is permitted and transitions to HALF_OPEN
            assert low_threshold_breaker.allow_request() is True
            assert low_threshold_breaker.get_state() == CircuitState.HALF_OPEN

            # Second call is permitted (half_open_max_calls=2)
            assert low_threshold_breaker.allow_request() is True

            # Third call is not permitted (reached max)
            assert low_threshold_breaker.allow_request() is False

    def test_half_open_calls_counter_resets_on_transition(
        self, low_threshold_breaker: CircuitBreaker
    ) -> None:
        """Test that half_open_calls counter resets when transitioning back to OPEN."""
        # Get to HALF_OPEN state
        for _ in range(2):
            low_threshold_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = low_threshold_breaker._opened_at + 10.0
            low_threshold_breaker.allow_request()

        # Failure in HALF_OPEN transitions back to OPEN
        low_threshold_breaker.record_failure()

        assert low_threshold_breaker.get_state() == CircuitState.OPEN
        assert low_threshold_breaker._half_open_calls == 0


# =============================================================================
# Reset Functionality Tests
# =============================================================================


class TestResetFunctionality:
    """Tests for circuit breaker reset functionality."""

    def test_reset_returns_to_closed(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that reset returns circuit to CLOSED state."""
        # Get to OPEN state
        for _ in range(5):
            circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == CircuitState.OPEN

        circuit_breaker.reset()

        assert circuit_breaker.get_state() == CircuitState.CLOSED

    def test_reset_clears_failure_count(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that reset clears failure count."""
        for _ in range(5):
            circuit_breaker.record_failure()

        circuit_breaker.reset()

        assert circuit_breaker._failure_count == 0

    def test_reset_clears_opened_at(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that reset clears opened_at timestamp."""
        for _ in range(5):
            circuit_breaker.record_failure()

        assert circuit_breaker._opened_at is not None

        circuit_breaker.reset()

        assert circuit_breaker._opened_at is None

    def test_reset_from_half_open(self, low_threshold_breaker: CircuitBreaker) -> None:
        """Test that reset works from HALF_OPEN state."""
        # Get to HALF_OPEN state
        for _ in range(2):
            low_threshold_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = low_threshold_breaker._opened_at + 10.0
            low_threshold_breaker.allow_request()

        assert low_threshold_breaker.get_state() == CircuitState.HALF_OPEN

        low_threshold_breaker.reset()

        assert low_threshold_breaker.get_state() == CircuitState.CLOSED


# =============================================================================
# get_state Method Tests
# =============================================================================


class TestGetStateMethod:
    """Tests for the get_state method."""

    def test_get_state_returns_closed_initially(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that get_state returns CLOSED initially."""
        assert circuit_breaker.get_state() == CircuitState.CLOSED

    def test_get_state_returns_open_after_failures(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that get_state returns OPEN after threshold failures."""
        for _ in range(5):
            circuit_breaker.record_failure()

        assert circuit_breaker.get_state() == CircuitState.OPEN

    def test_get_state_returns_half_open_after_timeout(
        self, low_threshold_breaker: CircuitBreaker
    ) -> None:
        """Test that get_state returns HALF_OPEN after recovery timeout."""
        for _ in range(2):
            low_threshold_breaker.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = low_threshold_breaker._opened_at + 10.0
            low_threshold_breaker.allow_request()

        assert low_threshold_breaker.get_state() == CircuitState.HALF_OPEN


# =============================================================================
# Prometheus Metrics Tests
# =============================================================================


class TestPrometheusMetrics:
    """Tests for Prometheus metrics integration."""

    def test_state_gauge_updated_on_open(self) -> None:
        """Test that state gauge is updated when circuit opens."""
        with patch("backend.services.circuit_breaker.CIRCUIT_BREAKER_STATE") as mock_gauge:
            mock_labels = MagicMock()
            mock_gauge.labels.return_value = mock_labels

            cb = CircuitBreaker(name="test_metrics", failure_threshold=3)
            for _ in range(3):
                cb.record_failure()

            # Verify gauge was set with correct value (1 for OPEN)
            mock_gauge.labels.assert_called_with(service="test_metrics")
            mock_labels.set.assert_called_with(1)

    def test_state_gauge_updated_on_close(self) -> None:
        """Test that state gauge is updated when circuit closes."""
        cb = CircuitBreaker(name="test_close", failure_threshold=2, recovery_timeout=5.0)

        # Get to OPEN then HALF_OPEN then CLOSED
        for _ in range(2):
            cb.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = cb._opened_at + 10.0
            cb.allow_request()

        with patch("backend.services.circuit_breaker.CIRCUIT_BREAKER_STATE") as mock_gauge:
            mock_labels = MagicMock()
            mock_gauge.labels.return_value = mock_labels

            cb.record_success()
            cb.record_success()  # Need 2 successes for success_threshold

            # Verify gauge was set with correct value (0 for CLOSED)
            mock_labels.set.assert_called_with(0)

    def test_state_gauge_updated_on_half_open(self) -> None:
        """Test that state gauge is updated when entering HALF_OPEN."""
        cb = CircuitBreaker(name="test_half", failure_threshold=2, recovery_timeout=5.0)

        for _ in range(2):
            cb.record_failure()

        with (
            patch("time.monotonic") as mock_time,
            patch("backend.services.circuit_breaker.CIRCUIT_BREAKER_STATE") as mock_gauge,
        ):
            mock_labels = MagicMock()
            mock_gauge.labels.return_value = mock_labels
            mock_time.return_value = cb._opened_at + 10.0

            cb.allow_request()

            # Verify gauge was set with correct value (2 for HALF_OPEN)
            mock_labels.set.assert_called_with(2)

    def test_failures_counter_incremented(self) -> None:
        """Test that failures counter is incremented on failure."""
        with patch(
            "backend.services.circuit_breaker.CIRCUIT_BREAKER_FAILURES_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            cb = CircuitBreaker(name="test_failures")
            cb.record_failure()

            mock_counter.labels.assert_called_with(service="test_failures")
            mock_labels.inc.assert_called_once()

    def test_state_changes_counter_incremented_on_transition(self) -> None:
        """Test that state changes counter is incremented on state transitions."""
        with patch(
            "backend.services.circuit_breaker.CIRCUIT_BREAKER_STATE_CHANGES_TOTAL"
        ) as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            cb = CircuitBreaker(name="test_transitions", failure_threshold=2)

            # Trigger CLOSED -> OPEN transition
            for _ in range(2):
                cb.record_failure()

            mock_counter.labels.assert_called_with(
                service="test_transitions", from_state="closed", to_state="open"
            )
            mock_labels.inc.assert_called()


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestThreadSafety:
    """Tests for thread-safe async operations."""

    @pytest.mark.asyncio
    async def test_allow_request_async(self, circuit_breaker: CircuitBreaker) -> None:
        """Test async version of allow_request."""
        result = await circuit_breaker.allow_request_async()

        assert result is True

    @pytest.mark.asyncio
    async def test_record_success_async(self, circuit_breaker: CircuitBreaker) -> None:
        """Test async version of record_success."""
        await circuit_breaker.record_success_async()

        # Should still be in CLOSED state
        assert circuit_breaker.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_record_failure_async(self, circuit_breaker: CircuitBreaker) -> None:
        """Test async version of record_failure."""
        await circuit_breaker.record_failure_async()

        assert circuit_breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_reset_async(self, circuit_breaker: CircuitBreaker) -> None:
        """Test async version of reset."""
        for _ in range(5):
            circuit_breaker.record_failure()

        await circuit_breaker.reset_async()

        assert circuit_breaker.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_concurrent_failures(self, circuit_breaker: CircuitBreaker) -> None:
        """Test concurrent failure recording."""
        import asyncio

        async def record_failures():
            for _ in range(2):
                await circuit_breaker.record_failure_async()

        # Run multiple concurrent failure recordings
        await asyncio.gather(
            record_failures(),
            record_failures(),
            record_failures(),
        )

        # Should have recorded all failures
        assert circuit_breaker._failure_count >= 5  # May be 5 or 6 depending on timing


# =============================================================================
# Logging Tests
# =============================================================================


class TestLogging:
    """Tests for logging behavior."""

    def test_logs_state_transition_to_open(self) -> None:
        """Test that state transition to OPEN is logged."""
        with patch("backend.services.circuit_breaker.logger") as mock_logger:
            cb = CircuitBreaker(name="log_test", failure_threshold=2)
            for _ in range(2):
                cb.record_failure()

            # Verify warning was logged
            mock_logger.warning.assert_called()
            call_args = str(mock_logger.warning.call_args)
            assert "log_test" in call_args
            assert "OPEN" in call_args

    def test_logs_state_transition_to_half_open(self) -> None:
        """Test that state transition to HALF_OPEN is logged."""
        cb = CircuitBreaker(name="log_half", failure_threshold=2, recovery_timeout=5.0)

        for _ in range(2):
            cb.record_failure()

        with (
            patch("time.monotonic") as mock_time,
            patch("backend.services.circuit_breaker.logger") as mock_logger,
        ):
            mock_time.return_value = cb._opened_at + 10.0
            cb.allow_request()

            # Verify info was logged
            mock_logger.info.assert_called()
            call_args = str(mock_logger.info.call_args)
            assert "log_half" in call_args
            assert "HALF_OPEN" in call_args

    def test_logs_state_transition_to_closed(self) -> None:
        """Test that state transition to CLOSED is logged."""
        cb = CircuitBreaker(name="log_closed", failure_threshold=2, recovery_timeout=5.0)

        for _ in range(2):
            cb.record_failure()

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = cb._opened_at + 10.0
            cb.allow_request()

        with patch("backend.services.circuit_breaker.logger") as mock_logger:
            cb.record_success()
            cb.record_success()  # Need 2 successes

            # Verify info was logged
            mock_logger.info.assert_called()
            call_args = str(mock_logger.info.call_args)
            assert "log_closed" in call_args
            assert "CLOSED" in call_args


# =============================================================================
# Complete State Machine Cycle Tests
# =============================================================================


class TestCompleteStateMachineCycle:
    """Tests for complete state machine cycles."""

    def test_full_cycle_closed_open_half_open_closed(
        self, low_threshold_breaker: CircuitBreaker
    ) -> None:
        """Test a complete cycle through all states."""
        # Start in CLOSED
        assert low_threshold_breaker.get_state() == CircuitState.CLOSED
        assert low_threshold_breaker.allow_request() is True

        # Transition to OPEN
        for _ in range(2):
            low_threshold_breaker.record_failure()

        assert low_threshold_breaker.get_state() == CircuitState.OPEN
        assert low_threshold_breaker.allow_request() is False

        # Transition to HALF_OPEN after timeout
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = low_threshold_breaker._opened_at + 10.0
            is_permitted = low_threshold_breaker.allow_request()

        assert is_permitted is True
        assert low_threshold_breaker.get_state() == CircuitState.HALF_OPEN

        # Transition back to CLOSED (need 2 successes for success_threshold)
        low_threshold_breaker.record_success()
        low_threshold_breaker.record_success()

        assert low_threshold_breaker.get_state() == CircuitState.CLOSED
        assert low_threshold_breaker.allow_request() is True
        assert low_threshold_breaker._failure_count == 0

    def test_cycle_with_failure_in_half_open(self, low_threshold_breaker: CircuitBreaker) -> None:
        """Test cycle where failure in HALF_OPEN returns to OPEN."""
        # Get to OPEN
        for _ in range(2):
            low_threshold_breaker.record_failure()

        # Get to HALF_OPEN
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = low_threshold_breaker._opened_at + 10.0
            low_threshold_breaker.allow_request()

        assert low_threshold_breaker.get_state() == CircuitState.HALF_OPEN

        # Failure returns to OPEN
        low_threshold_breaker.record_failure()

        assert low_threshold_breaker.get_state() == CircuitState.OPEN

        # Another recovery cycle
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = low_threshold_breaker._opened_at + 10.0
            low_threshold_breaker.allow_request()

        assert low_threshold_breaker.get_state() == CircuitState.HALF_OPEN

        # Success closes the circuit (need 2 successes)
        low_threshold_breaker.record_success()
        low_threshold_breaker.record_success()

        assert low_threshold_breaker.get_state() == CircuitState.CLOSED


# =============================================================================
# Florence Client Example Usage Tests
# =============================================================================


class TestFlorenceClientExample:
    """Tests based on the Florence client example from the issue."""

    def test_florence_breaker_allows_requests_initially(
        self, florence_breaker: CircuitBreaker
    ) -> None:
        """Test that Florence breaker allows requests initially."""
        assert florence_breaker.allow_request() is True

    def test_florence_breaker_opens_after_5_failures(
        self, florence_breaker: CircuitBreaker
    ) -> None:
        """Test that Florence breaker opens after 5 failures."""
        for _ in range(5):
            florence_breaker.record_failure()

        assert florence_breaker.get_state() == CircuitState.OPEN
        assert florence_breaker.allow_request() is False

    def test_florence_breaker_recovers_after_60_seconds(
        self, florence_breaker: CircuitBreaker
    ) -> None:
        """Test that Florence breaker attempts recovery after 60 seconds."""
        # Open the circuit
        for _ in range(5):
            florence_breaker.record_failure()

        # Simulate 60+ seconds passing
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = florence_breaker._opened_at + 65.0
            is_permitted = florence_breaker.allow_request()

        assert is_permitted is True
        assert florence_breaker.get_state() == CircuitState.HALF_OPEN

    def test_florence_breaker_allows_3_half_open_calls(
        self, florence_breaker: CircuitBreaker
    ) -> None:
        """Test that Florence breaker allows 3 calls in half-open state."""
        # Open the circuit
        for _ in range(5):
            florence_breaker.record_failure()

        # Simulate timeout and enter half-open
        with patch("time.monotonic") as mock_time:
            mock_time.return_value = florence_breaker._opened_at + 65.0

            # Should allow exactly 3 calls
            assert florence_breaker.allow_request() is True  # First call transitions to HALF_OPEN
            assert florence_breaker.allow_request() is True  # Second call in HALF_OPEN
            assert florence_breaker.allow_request() is True  # Third call in HALF_OPEN
            # Fourth should be rejected
            assert florence_breaker.allow_request() is False


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_success_in_closed_with_no_failures(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that success in CLOSED with no failures is a no-op for count."""
        circuit_breaker.record_success()

        assert circuit_breaker._failure_count == 0

    def test_opened_at_none_before_first_open(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that opened_at is None before circuit opens."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()

        assert circuit_breaker._opened_at is None

    def test_opened_at_set_when_opened(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that opened_at is set when circuit opens."""
        for _ in range(5):
            circuit_breaker.record_failure()

        assert circuit_breaker._opened_at is not None

    def test_recovery_not_attempted_when_opened_at_is_none(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that recovery is not attempted if opened_at is None."""
        # Manually set state without opened_at
        circuit_breaker._state = CircuitState.OPEN
        circuit_breaker._opened_at = None

        result = circuit_breaker._should_attempt_recovery()

        assert result is False

    def test_multiple_reset_calls_are_idempotent(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that multiple reset calls are idempotent."""
        for _ in range(5):
            circuit_breaker.record_failure()

        circuit_breaker.reset()
        circuit_breaker.reset()
        circuit_breaker.reset()

        assert circuit_breaker.get_state() == CircuitState.CLOSED
        assert circuit_breaker._failure_count == 0


# =============================================================================
# String Representation Tests
# =============================================================================


class TestStringRepresentation:
    """Tests for string representation methods."""

    def test_str_representation(self, circuit_breaker: CircuitBreaker) -> None:
        """Test __str__ method."""
        result = str(circuit_breaker)

        assert "test_service" in result
        assert "CLOSED" in result

    def test_repr_representation(self, circuit_breaker: CircuitBreaker) -> None:
        """Test __repr__ method."""
        result = repr(circuit_breaker)

        assert "test_service" in result
        assert "closed" in result
        assert "failures=0" in result

    def test_str_changes_with_state(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that string representation reflects state changes."""
        for _ in range(5):
            circuit_breaker.record_failure()

        result = str(circuit_breaker)

        assert "OPEN" in result
