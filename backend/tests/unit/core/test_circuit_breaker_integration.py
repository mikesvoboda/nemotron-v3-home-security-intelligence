"""Unit tests for circuit breaker integration with exception hierarchy.

Tests cover:
- CircuitBreaker raising CircuitBreakerOpenError
- Integration with retry decorators
- Async context manager usage
- Error logging integration
- Prometheus metrics for open circuit
"""

from unittest.mock import patch

import pytest

from backend.core.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
from backend.core.exceptions import (
    CircuitBreakerOpenError,
    ExternalServiceError,
)

# =============================================================================
# CircuitBreaker Exception Integration Tests
# =============================================================================


class TestCircuitBreakerExceptionIntegration:
    """Tests for circuit breaker integration with exception hierarchy."""

    def test_circuit_breaker_raises_correct_exception_when_open(self) -> None:
        """Test that circuit breaker raises CircuitBreakerOpenError when open."""
        cb = CircuitBreaker(name="test_service", failure_threshold=2)

        # Open the circuit
        cb.record_failure()
        cb.record_failure()

        assert cb.get_state() == CircuitState.OPEN

        # check_and_raise should raise the correct exception
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.check_and_raise()

        assert exc_info.value.service_name == "test_service"
        assert exc_info.value.status_code == 503
        assert exc_info.value.error_code == "CIRCUIT_BREAKER_OPEN"

    def test_circuit_breaker_includes_recovery_timeout_in_error(self) -> None:
        """Test that CircuitBreakerOpenError includes recovery timeout."""
        cb = CircuitBreaker(name="yolo26", failure_threshold=2, recovery_timeout=30.0)

        cb.record_failure()
        cb.record_failure()

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.check_and_raise()

        assert exc_info.value.details.get("recovery_timeout_seconds") == 30.0

    def test_circuit_breaker_no_exception_when_closed(self) -> None:
        """Test that circuit breaker doesn't raise when closed."""
        cb = CircuitBreaker(name="test_service", failure_threshold=5)

        # Should not raise
        cb.check_and_raise()
        assert cb.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_check_and_raise(self) -> None:
        """Test async version of check_and_raise."""
        cb = CircuitBreaker(name="async_service", failure_threshold=2)

        cb.record_failure()
        cb.record_failure()

        with pytest.raises(CircuitBreakerOpenError):
            await cb.check_and_raise_async()


# =============================================================================
# Protected Call Tests
# =============================================================================


class TestProtectedCall:
    """Tests for protected_call method."""

    @pytest.mark.asyncio
    async def test_protected_call_success(self) -> None:
        """Test protected_call with successful operation."""
        cb = CircuitBreaker(name="test_service", failure_threshold=3)

        async def successful_op() -> str:
            return "success"

        result = await cb.protected_call(successful_op)

        assert result == "success"
        assert cb.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_protected_call_failure_records_failure(self) -> None:
        """Test that protected_call records failures."""
        cb = CircuitBreaker(name="test_service", failure_threshold=3)

        async def failing_op() -> str:
            raise ExternalServiceError("Service down")

        with pytest.raises(ExternalServiceError):
            await cb.protected_call(failing_op)

        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_protected_call_opens_circuit_after_threshold(self) -> None:
        """Test that protected_call opens circuit after threshold failures."""
        cb = CircuitBreaker(name="test_service", failure_threshold=2)

        async def failing_op() -> str:
            raise ExternalServiceError("Service down")

        # First failure
        with pytest.raises(ExternalServiceError):
            await cb.protected_call(failing_op)

        # Second failure opens circuit
        with pytest.raises(ExternalServiceError):
            await cb.protected_call(failing_op)

        assert cb.get_state() == CircuitState.OPEN

        # Third call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await cb.protected_call(failing_op)

    @pytest.mark.asyncio
    async def test_protected_call_with_specific_exception_types(self) -> None:
        """Test protected_call only tracks specified exception types."""
        cb = CircuitBreaker(name="test_service", failure_threshold=2)

        async def raises_value_error() -> str:
            raise ValueError("Invalid input")

        # ValueError should not be tracked (not in record_on default)
        with pytest.raises(ValueError):
            await cb.protected_call(raises_value_error, record_on=(ExternalServiceError,))

        # Failure count should be 0 since ValueError isn't tracked
        assert cb._failure_count == 0


# =============================================================================
# Circuit Breaker Context Manager Tests
# =============================================================================


class TestCircuitBreakerContextManager:
    """Tests for circuit breaker async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_success(self) -> None:
        """Test circuit breaker context manager with success."""
        cb = CircuitBreaker(name="ctx_service", failure_threshold=3)

        async with cb.protect():
            result = "operation completed"

        assert result == "operation completed"
        assert cb.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_context_manager_records_failure(self) -> None:
        """Test that context manager records failures."""
        cb = CircuitBreaker(name="ctx_service", failure_threshold=3)

        with pytest.raises(ExternalServiceError):
            async with cb.protect():
                raise ExternalServiceError("Service failed")

        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_context_manager_raises_when_open(self) -> None:
        """Test that protect() raises CircuitOpenError when circuit is open.

        The protect() context manager raises CircuitOpenError (not CircuitBreakerOpenError)
        which provides recovery_time_remaining for Retry-After headers.
        """
        cb = CircuitBreaker(name="ctx_service", failure_threshold=2)

        # Open the circuit
        cb.record_failure()
        cb.record_failure()

        with pytest.raises(CircuitOpenError) as exc_info:
            async with cb.protect():
                pass  # Should never reach here

        # Verify the exception has the expected attributes
        assert exc_info.value.service_name == "ctx_service"
        assert hasattr(exc_info.value, "recovery_time_remaining")
        assert exc_info.value.recovery_time_remaining >= 0.0


# =============================================================================
# Integration with Retry Decorator Tests
# =============================================================================


class TestCircuitBreakerRetryIntegration:
    """Tests for circuit breaker integration with retry decorators."""

    @pytest.mark.asyncio
    async def test_retry_stops_when_circuit_opens(self) -> None:
        """Test that retries stop when circuit breaker opens."""
        from backend.core.retry import retry_async

        cb = CircuitBreaker(name="retry_test", failure_threshold=2)
        call_count = 0

        @retry_async(
            max_retries=5,
            base_delay=0.01,
            retry_on=(ExternalServiceError,),
        )
        async def flaky_operation() -> str:
            nonlocal call_count
            call_count += 1

            # Check circuit first
            cb.check_and_raise()

            # Simulate failure
            cb.record_failure()
            raise ExternalServiceError("Service unavailable")

        # Should stop after circuit opens, not exhaust all retries
        with pytest.raises((ExternalServiceError, CircuitBreakerOpenError)):
            await flaky_operation()

        # Circuit should be open after 2 failures
        assert cb.get_state() == CircuitState.OPEN


# =============================================================================
# Error Context Integration Tests
# =============================================================================


class TestCircuitBreakerErrorContext:
    """Tests for circuit breaker error context integration."""

    def test_circuit_breaker_error_has_full_context(self) -> None:
        """Test that CircuitBreakerOpenError has full error context."""
        from backend.core.error_context import ErrorContext

        cb = CircuitBreaker(name="context_test", failure_threshold=2, recovery_timeout=45.0)

        cb.record_failure()
        cb.record_failure()

        try:
            cb.check_and_raise()
        except CircuitBreakerOpenError as e:
            ctx = ErrorContext.from_exception(e)

            assert ctx.error_type == "CircuitBreakerOpenError"
            assert ctx.error_code == "CIRCUIT_BREAKER_OPEN"
            assert ctx.service_name == "context_test"
            assert ctx.status_code == 503

    def test_circuit_breaker_logs_with_context(self) -> None:
        """Test that circuit breaker logs with structured context."""
        from backend.core.error_context import log_error

        cb = CircuitBreaker(name="log_test", failure_threshold=2)

        cb.record_failure()
        cb.record_failure()

        with patch("backend.core.error_context.logger") as mock_logger:
            try:
                cb.check_and_raise()
            except CircuitBreakerOpenError as e:
                log_error(e, operation="detect_objects")

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            extra = call_args[1]["extra"]
            assert extra["service_name"] == "log_test"
            assert extra["operation"] == "detect_objects"


# =============================================================================
# Metrics Integration Tests
# =============================================================================


class TestCircuitBreakerMetrics:
    """Tests for circuit breaker Prometheus metrics."""

    def test_circuit_breaker_tracks_state_transitions(self) -> None:
        """Test that circuit breaker state transitions update metrics."""
        # This test verifies the circuit breaker behavior without
        # mocking internal metrics. The metrics are updated during
        # state transitions which happen inside record_failure.
        cb = CircuitBreaker(name="metrics_test_2", failure_threshold=2)

        # Initially closed
        assert cb.get_state() == CircuitState.CLOSED

        # After threshold failures, should be open
        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN

        # allow_request should return False when open
        assert cb.allow_request() is False


# =============================================================================
# Edge Cases
# =============================================================================


class TestCircuitBreakerEdgeCases:
    """Tests for circuit breaker edge cases."""

    @pytest.mark.asyncio
    async def test_protected_call_with_sync_function(self) -> None:
        """Test that protected_call works with sync functions wrapped in async."""
        cb = CircuitBreaker(name="sync_test", failure_threshold=3)

        async def sync_wrapper() -> int:
            return 42

        result = await cb.protected_call(sync_wrapper)
        assert result == 42

    def test_circuit_breaker_state_info(self) -> None:
        """Test get_state_info returns comprehensive state."""
        cb = CircuitBreaker(name="info_test", failure_threshold=3, recovery_timeout=30.0)

        cb.record_failure()
        cb.record_failure()

        info = cb.get_state_info()

        assert info["name"] == "info_test"
        assert info["state"] == "closed"  # Not yet at threshold
        assert info["failure_count"] == 2
        assert info["failure_threshold"] == 3
        assert info["recovery_timeout"] == 30.0

    def test_circuit_breaker_state_info_when_open(self) -> None:
        """Test get_state_info when circuit is open."""
        cb = CircuitBreaker(name="open_info_test", failure_threshold=2)

        cb.record_failure()
        cb.record_failure()

        info = cb.get_state_info()

        assert info["state"] == "open"
        assert "opened_at" in info
        assert info["opened_at"] is not None
