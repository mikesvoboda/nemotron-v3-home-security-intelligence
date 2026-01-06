"""Circuit breaker pattern implementation for external service protection.

This module provides a circuit breaker implementation that protects external services
from cascading failures. When a service experiences repeated failures, the circuit
breaker "opens" to prevent further calls, allowing the service time to recover.

States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Circuit tripped, calls are rejected immediately
    - HALF_OPEN: Recovery testing, limited calls allowed to test service health

Features:
    - Configurable failure thresholds and recovery timeouts
    - Half-open state for gradual recovery testing
    - Excluded exceptions that don't count as failures
    - Thread-safe async implementation
    - Registry for managing multiple circuit breakers
    - Async context manager support
    - Metrics and monitoring support
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeVar

from backend.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior.

    Attributes:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before transitioning to half-open
        half_open_max_calls: Maximum calls allowed in half-open state
        success_threshold: Successes needed in half-open to close circuit
        excluded_exceptions: Exception types that don't count as failures
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3
    success_threshold: int = 2
    excluded_exceptions: tuple[type[Exception], ...] = ()


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
    state: CircuitState
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


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, service_name: str, state: str | CircuitState) -> None:
        """Initialize circuit breaker error.

        Args:
            service_name: Name of the service with open circuit
            state: Current circuit state
        """
        self.service_name = service_name
        self.name = service_name  # Alias for compatibility
        state_value = state.value if isinstance(state, CircuitState) else state
        self.state = state
        super().__init__(
            f"Circuit breaker for '{service_name}' is {state_value}. Service is temporarily unavailable."
        )


class CircuitBreaker:
    """Circuit breaker for protecting external service calls.

    Implements the circuit breaker pattern with three states:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Service failing, calls rejected immediately
    - HALF_OPEN: Testing recovery, limited calls allowed

    Usage:
        breaker = CircuitBreaker(name="ai_service", config=config)

        try:
            result = await breaker.call(async_operation, arg1, arg2)
        except CircuitBreakerError:
            # Handle service unavailable
            pass

        # Or use as async context manager
        async with breaker:
            result = await async_operation()
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            name: Unique name for this circuit breaker
            config: Configuration (uses defaults if not provided)
        """
        self._name = name
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._total_calls = 0
        self._rejected_calls = 0
        self._half_open_calls = 0
        self._last_failure_time: float | None = None
        self._opened_at: float | None = None
        self._last_state_change: datetime | None = None
        self._lock = asyncio.Lock()

        logger.info(
            f"CircuitBreaker '{name}' initialized: "
            f"failure_threshold={self._config.failure_threshold}, "
            f"recovery_timeout={self._config.recovery_timeout}s"
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
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    @property
    def success_count(self) -> int:
        """Get current success count (relevant in half-open state)."""
        return self._success_count

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting calls)."""
        return self._state == CircuitState.OPEN

    async def allow_call(self) -> bool:
        """Check if a call is allowed based on current state.

        This method handles state transitions from OPEN to HALF_OPEN
        when the timeout has elapsed. It acquires the lock to ensure
        thread-safe state transitions.

        Returns:
            True if call should proceed, False if it should be rejected
        """
        async with self._lock:
            return self._allow_call_unlocked()

    def _allow_call_unlocked(self) -> bool:
        """Check if a call is allowed (must be called with lock held).

        Internal method that performs the actual allow_call logic without
        acquiring the lock. Used by __aenter__ which already holds the lock.

        Returns:
            True if call should proceed, False if it should be rejected
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._transition_to_half_open()
                return True
            return False

        if self._state == CircuitState.HALF_OPEN:
            # Limit concurrent calls in half-open state
            return self._half_open_calls < self._config.half_open_max_calls

        return False

    async def call(
        self,
        operation: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute operation through the circuit breaker.

        Args:
            operation: Async callable to execute
            *args: Arguments to pass to operation
            **kwargs: Keyword arguments to pass to operation

        Returns:
            Result from the operation

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Any exception from the operation (may trip circuit)
        """
        async with self._lock:
            self._total_calls += 1

            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self._transition_to_half_open()
                else:
                    self._rejected_calls += 1
                    raise CircuitBreakerError(self._name, self._state.value)

            # In HALF_OPEN, check if we've exceeded max trial calls
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self._config.half_open_max_calls:
                    self._rejected_calls += 1
                    raise CircuitBreakerError(self._name, self._state.value)
                self._half_open_calls += 1

        try:
            result = await operation(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            # Check if this exception should be excluded
            if isinstance(e, self._config.excluded_exceptions):
                raise

            await self._record_failure()
            raise

    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.debug(
                    f"CircuitBreaker '{self._name}' half-open success: "
                    f"{self._success_count}/{self._config.success_threshold}"
                )

                if self._success_count >= self._config.success_threshold:
                    self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                if self._failure_count > 0:
                    logger.debug(
                        f"CircuitBreaker '{self._name}' resetting failure count on success"
                    )
                    self._failure_count = 0

    async def _record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            logger.warning(
                f"CircuitBreaker '{self._name}' failure recorded: "
                f"{self._failure_count}/{self._config.failure_threshold}"
            )

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                self._transition_to_open()
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self._config.failure_threshold
            ):
                self._transition_to_open()

    def _should_attempt_recovery(self) -> bool:
        """Check if recovery timeout has elapsed."""
        if self._opened_at is None:
            return False
        elapsed = time.monotonic() - self._opened_at
        return elapsed >= self._config.recovery_timeout

    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        prev_state = self._state
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._success_count = 0
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

        logger.warning(
            f"CircuitBreaker '{self._name}' transitioned {prev_state.value} -> OPEN "
            f"(failures={self._failure_count}, "
            f"threshold={self._config.failure_threshold})"
        )

    def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

        logger.info(
            f"CircuitBreaker '{self._name}' transitioned OPEN -> HALF_OPEN "
            f"(testing recovery after {self._config.recovery_timeout}s)"
        )

    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

        logger.info(
            f"CircuitBreaker '{self._name}' transitioned HALF_OPEN -> CLOSED (service recovered)"
        )

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        self._half_open_calls = 0
        self._last_failure_time = None
        self._last_state_change = datetime.now(UTC)

        logger.info(f"CircuitBreaker '{self._name}' manually reset to CLOSED")

    def force_open(self) -> None:
        """Force circuit breaker to open state (for maintenance)."""
        logger.warning(
            f"CircuitBreaker '{self._name}' force opened",
        )
        self._transition_to_open()
        self._last_failure_time = time.monotonic()

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status.

        Returns:
            Dictionary with status information
        """
        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_calls": self._total_calls,
            "rejected_calls": self._rejected_calls,
            "last_failure_time": self._last_failure_time,
            "opened_at": self._opened_at,
            "config": {
                "failure_threshold": self._config.failure_threshold,
                "recovery_timeout": self._config.recovery_timeout,
                "half_open_max_calls": self._config.half_open_max_calls,
                "success_threshold": self._config.success_threshold,
            },
        }

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current circuit breaker metrics.

        Returns:
            CircuitBreakerMetrics with current state and counters
        """
        last_failure_dt = None
        if self._last_failure_time is not None:
            # Convert monotonic time to datetime (approximate)
            elapsed = time.monotonic() - self._last_failure_time
            last_failure_dt = datetime.now(UTC)
            # Adjust for elapsed time
            from datetime import timedelta

            last_failure_dt = last_failure_dt - timedelta(seconds=elapsed)

        return CircuitBreakerMetrics(
            name=self._name,
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            total_calls=self._total_calls,
            rejected_calls=self._rejected_calls,
            last_failure_time=last_failure_dt,
            last_state_change=self._last_state_change,
        )

    async def __aenter__(self) -> CircuitBreaker:
        """Async context manager entry.

        Raises:
            CircuitBreakerError: If circuit is open
        """
        async with self._lock:
            self._total_calls += 1

            if not self._allow_call_unlocked():
                self._rejected_calls += 1
                raise CircuitBreakerError(self._name, self._state)

            if self._state == CircuitState.HALF_OPEN:
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
        if exc_type is None:
            await self._record_success()
        elif not isinstance(exc_val, self._config.excluded_exceptions):
            await self._record_failure()

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


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers.

    Provides centralized management of circuit breakers for different services.

    Usage:
        registry = CircuitBreakerRegistry()
        breaker = registry.get_or_create("ai_service", config)
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one.

        Args:
            name: Unique name for the circuit breaker
            config: Configuration (uses defaults if not provided)

        Returns:
            CircuitBreaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                config=config or CircuitBreakerConfig(),
            )
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """Get existing circuit breaker by name.

        Args:
            name: Name of the circuit breaker

        Returns:
            CircuitBreaker if found, None otherwise
        """
        return self._breakers.get(name)

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all circuit breakers.

        Returns:
            Dictionary mapping names to status dictionaries
        """
        return {name: breaker.get_status() for name, breaker in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED state."""
        for breaker in self._breakers.values():
            breaker.reset()
        logger.info(f"Reset all {len(self._breakers)} circuit breakers")

    def list_names(self) -> list[str]:
        """List all registered circuit breaker names.

        Returns:
            List of circuit breaker names
        """
        return list(self._breakers.keys())

    def clear(self) -> None:
        """Clear all registered circuit breakers."""
        self._breakers.clear()


# Global registry instance
_registry: CircuitBreakerRegistry | None = None


def _get_registry() -> CircuitBreakerRegistry:
    """Get or create the global registry."""
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = CircuitBreakerRegistry()
    return _registry


def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker:
    """Get or create a circuit breaker from the global registry.

    Args:
        name: Unique name for the circuit breaker
        config: Configuration (uses defaults if not provided)

    Returns:
        CircuitBreaker instance
    """
    return _get_registry().get_or_create(name, config)


def reset_circuit_breaker_registry() -> None:
    """Reset the global circuit breaker registry (for testing)."""
    global _registry  # noqa: PLW0603
    if _registry is not None:
        _registry.clear()
    _registry = None
