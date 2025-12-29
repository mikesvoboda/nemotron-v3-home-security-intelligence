"""Circuit breaker pattern implementation for service resilience.

This module provides a circuit breaker pattern to prevent cascading failures
when dependent services are unavailable. The circuit breaker monitors failures
and automatically trips to protect the system.

Circuit Breaker States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit tripped, requests are rejected immediately
    - HALF_OPEN: Testing recovery, limited requests allowed

State Transitions:
    CLOSED -> OPEN: When failure count exceeds threshold
    OPEN -> HALF_OPEN: After timeout period expires
    HALF_OPEN -> CLOSED: After success threshold reached
    HALF_OPEN -> OPEN: On any failure during half-open

Usage:
    cb = CircuitBreaker(name="rtdetr", config=CircuitBreakerConfig(
        failure_threshold=5,
        timeout_seconds=30.0,
    ))

    # Using call method
    result = await cb.call(some_async_function, arg1, arg2)

    # Using context manager
    async with cb:
        result = await some_async_function()

    # Check if calls are allowed
    if cb.allow_call():
        # Proceed with call
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeVar

from backend.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker state enumeration."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker rejects a call."""

    def __init__(self, name: str, state: CircuitBreakerState, message: str | None = None):
        self.name = name
        self.state = state
        self.message = message or f"Circuit breaker {name} is {state.value.upper()}"
        super().__init__(self.message)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior.

    Attributes:
        failure_threshold: Number of failures to trigger open state
        success_threshold: Number of successes in half-open to close
        timeout_seconds: Time to wait in open state before testing
        half_open_max_calls: Maximum concurrent calls in half-open state
    """

    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_seconds: float = 30.0
    half_open_max_calls: int = 3


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring.

    Attributes:
        name: Circuit breaker name
        state: Current state
        failure_count: Consecutive failures
        success_count: Consecutive successes in half-open
        total_calls: Total calls attempted
        rejected_calls: Calls rejected due to open circuit
        last_failure_time: Timestamp of last failure
        last_state_change: Timestamp of last state transition
    """

    name: str
    state: CircuitBreakerState
    failure_count: int = 0
    success_count: int = 0
    total_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: datetime | None = None
    last_state_change: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "rejected_calls": self.rejected_calls,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "last_state_change": (
                self.last_state_change.isoformat() if self.last_state_change else None
            ),
        }


class CircuitBreaker:
    """Circuit breaker implementation for service resilience.

    Monitors failures and automatically trips to prevent cascading failures
    when dependent services are unavailable.
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        """Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker (e.g., service name)
            config: Configuration options (uses defaults if not provided)
        """
        self._name = name
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._total_calls = 0
        self._rejected_calls = 0
        self._half_open_calls = 0
        self._last_failure_time: datetime | None = None
        self._last_state_change: datetime | None = None
        self._lock = asyncio.Lock()

        logger.info(
            f"CircuitBreaker '{name}' initialized",
            extra={
                "circuit_breaker": name,
                "failure_threshold": self._config.failure_threshold,
                "timeout_seconds": self._config.timeout_seconds,
            },
        )

    @property
    def name(self) -> str:
        """Get circuit breaker name."""
        return self._name

    @property
    def config(self) -> CircuitBreakerConfig:
        """Get circuit breaker configuration."""
        return self._config

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    @property
    def success_count(self) -> int:
        """Get current success count (relevant in half-open state)."""
        return self._success_count

    def _transition_to(self, new_state: CircuitBreakerState) -> None:
        """Transition to a new state with logging.

        Args:
            new_state: The state to transition to
        """
        if self._state == new_state:
            return

        old_state = self._state
        self._state = new_state
        self._last_state_change = datetime.now(UTC)

        logger.info(
            f"CircuitBreaker '{self._name}' state changed: {old_state.value} -> {new_state.value}",
            extra={
                "circuit_breaker": self._name,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "failure_count": self._failure_count,
            },
        )

        # Reset counters on state change
        if new_state == CircuitBreakerState.HALF_OPEN:
            self._half_open_calls = 0
            self._success_count = 0
        elif new_state == CircuitBreakerState.CLOSED:
            self._failure_count = 0
            self._success_count = 0

    def _should_transition_to_half_open(self) -> bool:
        """Check if circuit should transition from open to half-open.

        Returns:
            True if timeout has elapsed since last failure
        """
        if self._state != CircuitBreakerState.OPEN:
            return False

        if self._last_failure_time is None:
            return True

        elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()
        return elapsed >= self._config.timeout_seconds

    def allow_call(self) -> bool:
        """Check if a call is allowed based on current state.

        This method handles state transitions from OPEN to HALF_OPEN
        when the timeout has elapsed.

        Returns:
            True if call should proceed, False if it should be rejected
        """
        if self._state == CircuitBreakerState.CLOSED:
            return True

        if self._state == CircuitBreakerState.OPEN:
            if self._should_transition_to_half_open():
                self._transition_to(CircuitBreakerState.HALF_OPEN)
                return True
            return False

        if self._state == CircuitBreakerState.HALF_OPEN:
            # Limit concurrent calls in half-open state
            return self._half_open_calls < self._config.half_open_max_calls

        return False

    def _record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitBreakerState.CLOSED:
            # Reset failure count on success in closed state
            self._failure_count = 0
        elif self._state == CircuitBreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._config.success_threshold:
                self._transition_to(CircuitBreakerState.CLOSED)

    def _record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now(UTC)

        if self._state == CircuitBreakerState.CLOSED:
            if self._failure_count >= self._config.failure_threshold:
                self._transition_to(CircuitBreakerState.OPEN)
        elif self._state == CircuitBreakerState.HALF_OPEN:
            # Any failure in half-open immediately reopens
            self._transition_to(CircuitBreakerState.OPEN)

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute a function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result from the function

        Raises:
            CircuitBreakerError: If circuit is open or half-open limit reached
            Exception: Any exception from the wrapped function
        """
        async with self._lock:
            self._total_calls += 1

            if not self.allow_call():
                self._rejected_calls += 1
                raise CircuitBreakerError(self._name, self._state)

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            async with self._lock:
                self._record_success()
            return result
        except Exception:
            async with self._lock:
                self._record_failure()
            raise

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        logger.info(
            f"CircuitBreaker '{self._name}' manually reset",
            extra={"circuit_breaker": self._name},
        )
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

    def force_open(self) -> None:
        """Force circuit breaker to open state (for maintenance)."""
        logger.warning(
            f"CircuitBreaker '{self._name}' force opened",
            extra={"circuit_breaker": self._name},
        )
        self._transition_to(CircuitBreakerState.OPEN)
        self._last_failure_time = datetime.now(UTC)

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current circuit breaker metrics.

        Returns:
            CircuitBreakerMetrics with current state and counters
        """
        return CircuitBreakerMetrics(
            name=self._name,
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            total_calls=self._total_calls,
            rejected_calls=self._rejected_calls,
            last_failure_time=self._last_failure_time,
            last_state_change=self._last_state_change,
        )

    async def __aenter__(self) -> CircuitBreaker:
        """Async context manager entry.

        Raises:
            CircuitBreakerError: If circuit is open
        """
        async with self._lock:
            self._total_calls += 1

            if not self.allow_call():
                self._rejected_calls += 1
                raise CircuitBreakerError(self._name, self._state)

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._half_open_calls += 1

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit.

        Records success or failure based on exception.
        """
        async with self._lock:
            if exc_type is None:
                self._record_success()
            else:
                self._record_failure()

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


# Global circuit breaker registry
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker:
    """Get or create a circuit breaker by name.

    If a circuit breaker with the given name exists, returns it.
    Otherwise, creates a new one with the provided config.

    Args:
        name: Circuit breaker name
        config: Configuration (only used if creating new)

    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name=name, config=config)
    return _circuit_breakers[name]


def reset_circuit_breakers() -> None:
    """Reset all circuit breakers (for testing)."""
    global _circuit_breakers  # noqa: PLW0603
    _circuit_breakers = {}
