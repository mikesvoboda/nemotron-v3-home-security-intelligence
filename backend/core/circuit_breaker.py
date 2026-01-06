"""Shared circuit breaker utility for AI services.

This module provides a reusable CircuitBreaker class that implements the circuit
breaker pattern for protecting AI service calls. It prevents cascading failures
by temporarily stopping requests to failing services and allowing them time to
recover.

States:
    - CLOSED: Normal operation, requests proceed normally
    - OPEN: Too many failures, requests are blocked to allow recovery
    - HALF_OPEN: Testing recovery, limited requests allowed

Features:
    - Configurable failure thresholds and recovery timeouts
    - Half-open state for gradual recovery testing
    - Thread-safe with asyncio Lock
    - Prometheus metrics integration for monitoring
    - Logging of state transitions
    - Integration with exception hierarchy (CircuitBreakerOpenError)
    - Protected call wrapper for automatic failure tracking
    - Async context manager for scoped protection

Usage:
    from backend.core.circuit_breaker import CircuitBreaker

    # Method 1: Manual check and record
    class FlorenceClient:
        def __init__(self):
            self.circuit_breaker = CircuitBreaker(
                name="florence",
                failure_threshold=5,
                recovery_timeout=60,
                half_open_max_calls=3
            )

        async def call_api(self):
            self.circuit_breaker.check_and_raise()  # Raises CircuitBreakerOpenError if open
            try:
                result = await self._make_request()
                self.circuit_breaker.record_success()
                return result
            except Exception as e:
                self.circuit_breaker.record_failure()
                raise

    # Method 2: Protected call wrapper
    async def call_api(self):
        return await self.circuit_breaker.protected_call(self._make_request)

    # Method 3: Context manager
    async def call_api(self):
        async with self.circuit_breaker.protect():
            return await self._make_request()
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeVar

from prometheus_client import Counter, Gauge

from backend.core.exceptions import CircuitBreakerOpenError
from backend.core.logging import get_logger

T = TypeVar("T")

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Rejecting requests, waiting to recover
    HALF_OPEN = "half_open"  # Testing recovery


# =============================================================================
# Prometheus Metrics
# =============================================================================

CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Current state of the circuit breaker (0=closed, 1=open, 2=half_open)",
    labelnames=["service"],
)

CIRCUIT_BREAKER_FAILURES_TOTAL = Counter(
    "circuit_breaker_failures_total",
    "Total number of failures recorded by the circuit breaker",
    labelnames=["service"],
)

CIRCUIT_BREAKER_STATE_CHANGES_TOTAL = Counter(
    "circuit_breaker_state_changes_total",
    "Total number of state transitions",
    labelnames=["service", "from_state", "to_state"],
)


class CircuitBreaker:
    """Circuit breaker for AI service calls.

    Implements the circuit breaker pattern to protect against cascading failures
    when calling external AI services like Florence, RT-DETR, or Nemotron.

    When a service experiences repeated failures, the circuit breaker opens to
    prevent further failed attempts and allows time for recovery.

    Attributes:
        name: Service identifier for metrics and logging
        failure_threshold: Number of consecutive failures before opening circuit
        recovery_timeout: Seconds to wait before attempting half-open state
        half_open_max_calls: Maximum calls allowed in half-open state
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            name: Service identifier for metrics and logging
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before transitioning to half-open
            half_open_max_calls: Maximum calls allowed in half-open state
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

        # Timing tracking
        self._opened_at: float | None = None
        self._last_state_change: datetime | None = None

        # Thread safety
        self._lock = asyncio.Lock()

        # Initialize metrics
        CIRCUIT_BREAKER_STATE.labels(service=name).set(0)

        logger.info(
            f"CircuitBreaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s, "
            f"half_open_max_calls={half_open_max_calls}"
        )

    def get_state(self) -> CircuitState:
        """Get current circuit state.

        Returns:
            Current CircuitState
        """
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should proceed based on current state.

        This method also handles state transitions from OPEN to HALF_OPEN
        when the recovery timeout has elapsed.

        Returns:
            True if request should proceed, False if it should be rejected
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._transition_to_half_open()
                self._half_open_calls += 1
                return True
            return False

        if self._state == CircuitState.HALF_OPEN:
            # Limit concurrent calls in half-open state
            if self._half_open_calls < self._half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        return False

    async def allow_request_async(self) -> bool:
        """Check if a request should proceed (async version with lock).

        Thread-safe version that acquires a lock before checking state
        and potentially transitioning.

        Returns:
            True if request should proceed, False if it should be rejected
        """
        async with self._lock:
            return self.allow_request()

    def record_success(self) -> None:
        """Record a successful operation.

        Resets failure count and may transition circuit from HALF_OPEN to CLOSED.
        """
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            logger.debug(
                f"CircuitBreaker '{self._name}' half-open success: {self._success_count}/1"
            )

            # Any success in half-open closes the circuit
            self._transition_to_closed()

        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success in closed state
            if self._failure_count > 0:
                logger.debug(f"CircuitBreaker '{self._name}' resetting failure count on success")
                self._failure_count = 0

    async def record_success_async(self) -> None:
        """Record a successful operation (async version with lock)."""
        async with self._lock:
            self.record_success()

    def record_failure(self) -> None:
        """Record a failed operation.

        Increments failure count and may transition circuit to OPEN state.
        """
        self._failure_count += 1
        CIRCUIT_BREAKER_FAILURES_TOTAL.labels(service=self._name).inc()

        logger.warning(
            f"CircuitBreaker '{self._name}' failure recorded: "
            f"{self._failure_count}/{self._failure_threshold}"
        )

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open reopens the circuit
            self._transition_to_open()
        elif self._state == CircuitState.CLOSED and self._failure_count >= self._failure_threshold:
            self._transition_to_open()

    async def record_failure_async(self) -> None:
        """Record a failed operation (async version with lock)."""
        async with self._lock:
            self.record_failure()

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state.

        This clears all failure counts and returns the circuit to normal operation.
        Use this after fixing underlying issues or for maintenance.
        """
        prev_state = self._state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

        # Update metrics
        CIRCUIT_BREAKER_STATE.labels(service=self._name).set(0)
        if prev_state != CircuitState.CLOSED:
            CIRCUIT_BREAKER_STATE_CHANGES_TOTAL.labels(
                service=self._name,
                from_state=prev_state.value,
                to_state="closed",
            ).inc()

        logger.info(f"CircuitBreaker '{self._name}' manually reset to CLOSED")

    async def reset_async(self) -> None:
        """Manually reset circuit breaker to CLOSED state (async version with lock)."""
        async with self._lock:
            self.reset()

    def _should_attempt_recovery(self) -> bool:
        """Check if recovery timeout has elapsed."""
        if self._opened_at is None:
            return False
        elapsed = time.monotonic() - self._opened_at
        return elapsed >= self._recovery_timeout

    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        prev_state = self._state
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._success_count = 0
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

        # Update metrics
        CIRCUIT_BREAKER_STATE.labels(service=self._name).set(1)
        CIRCUIT_BREAKER_STATE_CHANGES_TOTAL.labels(
            service=self._name,
            from_state=prev_state.value,
            to_state="open",
        ).inc()

        logger.warning(
            f"CircuitBreaker '{self._name}' transitioned {prev_state.value} -> OPEN "
            f"(failures={self._failure_count}, threshold={self._failure_threshold})"
        )

    def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

        # Update metrics
        CIRCUIT_BREAKER_STATE.labels(service=self._name).set(2)
        CIRCUIT_BREAKER_STATE_CHANGES_TOTAL.labels(
            service=self._name,
            from_state="open",
            to_state="half_open",
        ).inc()

        logger.info(
            f"CircuitBreaker '{self._name}' transitioned OPEN -> HALF_OPEN "
            f"(testing recovery after {self._recovery_timeout}s)"
        )

    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

        # Update metrics
        CIRCUIT_BREAKER_STATE.labels(service=self._name).set(0)
        CIRCUIT_BREAKER_STATE_CHANGES_TOTAL.labels(
            service=self._name,
            from_state="half_open",
            to_state="closed",
        ).inc()

        logger.info(
            f"CircuitBreaker '{self._name}' transitioned HALF_OPEN -> CLOSED (service recovered)"
        )

    def check_and_raise(self) -> None:
        """Check circuit state and raise CircuitBreakerOpenError if open.

        Use this method when you want to explicitly check the circuit state
        and raise an exception with full context if the circuit is open.

        Raises:
            CircuitBreakerOpenError: If the circuit is open and not allowing requests
        """
        if not self.allow_request():
            raise CircuitBreakerOpenError(
                service_name=self._name,
                recovery_timeout=self._recovery_timeout,
            )

    async def check_and_raise_async(self) -> None:
        """Check circuit state and raise CircuitBreakerOpenError if open (async version).

        Thread-safe version that acquires a lock before checking state.

        Raises:
            CircuitBreakerOpenError: If the circuit is open and not allowing requests
        """
        async with self._lock:
            self.check_and_raise()

    async def protected_call(
        self,
        func: Callable[[], Awaitable[T]],
        record_on: tuple[type[BaseException], ...] = (Exception,),
    ) -> T:
        """Execute an async function with circuit breaker protection.

        This method provides a convenient way to wrap async calls with full
        circuit breaker protection:
        1. Checks if circuit is open (raises CircuitBreakerOpenError if so)
        2. Executes the function
        3. Records success or failure based on the outcome

        Args:
            func: Async function to execute
            record_on: Exception types that should be recorded as failures

        Returns:
            The result of the function call

        Raises:
            CircuitBreakerOpenError: If the circuit is open
            Any exception raised by the function

        Example:
            result = await circuit_breaker.protected_call(
                lambda: client.fetch_data(),
                record_on=(ConnectionError, TimeoutError),
            )
        """
        async with self._lock:
            self.check_and_raise()

        try:
            result = await func()
            await self.record_success_async()
            return result
        except record_on:
            await self.record_failure_async()
            raise

    @asynccontextmanager
    async def protect(
        self,
        record_on: tuple[type[BaseException], ...] = (Exception,),
    ) -> Any:
        """Async context manager for circuit breaker protection.

        Provides a scoped way to protect code blocks with the circuit breaker.
        Automatically records success or failure when exiting the context.

        Args:
            record_on: Exception types that should be recorded as failures

        Yields:
            None

        Raises:
            CircuitBreakerOpenError: If the circuit is open when entering

        Example:
            async with circuit_breaker.protect():
                result = await risky_operation()
                return result
        """
        await self.check_and_raise_async()

        try:
            yield
            await self.record_success_async()
        except record_on:
            await self.record_failure_async()
            raise

    def get_state_info(self) -> dict[str, Any]:
        """Get comprehensive state information for monitoring/debugging.

        Returns:
            Dictionary containing:
            - name: Service name
            - state: Current state (closed, open, half_open)
            - failure_count: Current failure count
            - failure_threshold: Threshold for opening circuit
            - recovery_timeout: Timeout before attempting recovery
            - half_open_max_calls: Max calls allowed in half-open state
            - half_open_calls: Current calls in half-open state
            - opened_at: Timestamp when circuit was opened (if applicable)
            - last_state_change: Timestamp of last state change
        """
        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self._failure_threshold,
            "recovery_timeout": self._recovery_timeout,
            "half_open_max_calls": self._half_open_max_calls,
            "half_open_calls": self._half_open_calls,
            "opened_at": self._opened_at,
            "last_state_change": (
                self._last_state_change.isoformat() if self._last_state_change else None
            ),
        }

    def __str__(self) -> str:
        """String representation of circuit breaker."""
        return f"CircuitBreaker({self._name}, state={self._state.value.upper()})"

    def __repr__(self) -> str:
        """Detailed representation of circuit breaker."""
        return (
            f"CircuitBreaker(name={self._name!r}, "
            f"state={self._state.value}, "
            f"failures={self._failure_count})"
        )
