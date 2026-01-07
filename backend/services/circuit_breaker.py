"""Circuit breaker pattern implementation for external service protection.

This is the canonical circuit breaker implementation for the project. All modules
should import from here rather than from backend.core.circuit_breaker.

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
    - Prometheus metrics integration for monitoring
    - Protected call wrapper and async context manager

Usage:
    from backend.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

    # Method 1: Manual check and record
    breaker = CircuitBreaker(name="ai_service", config=config)
    try:
        result = await breaker.call(async_operation, arg1, arg2)
    except CircuitBreakerError:
        # Handle service unavailable
        pass

    # Method 2: Async context manager
    async with breaker:
        result = await async_operation()

    # Method 3: Protected call wrapper
    result = await breaker.protected_call(async_operation)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any, TypeVar

from prometheus_client import Counter, Gauge

from backend.core.exceptions import CircuitBreakerOpenError as CoreCircuitBreakerOpenError
from backend.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


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

CIRCUIT_BREAKER_CALLS_TOTAL = Counter(
    "circuit_breaker_calls_total",
    "Total number of calls through the circuit breaker",
    labelnames=["service", "result"],
)

CIRCUIT_BREAKER_REJECTED_TOTAL = Counter(
    "circuit_breaker_rejected_total",
    "Total number of calls rejected by the circuit breaker",
    labelnames=["service"],
)


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


@dataclass(slots=True)
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


@dataclass(slots=True)
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
    """Exception raised when circuit breaker is open.

    This is compatible with backend.core.exceptions.CircuitBreakerOpenError
    and provides the same interface for error handling.
    """

    def __init__(
        self,
        service_name: str,
        state: str | CircuitState | None = None,
        *,
        recovery_timeout: float | None = None,
    ) -> None:
        """Initialize circuit breaker error.

        Args:
            service_name: Name of the service with open circuit
            state: Current circuit state (optional, defaults to 'open')
            recovery_timeout: Seconds until recovery attempt (optional)
        """
        self.service_name = service_name
        self.name = service_name  # Alias for compatibility
        self.recovery_timeout = recovery_timeout

        if state is None:
            state_value = "open"
            self.state = CircuitState.OPEN
        elif isinstance(state, CircuitState):
            state_value = state.value
            self.state = state
        else:
            state_value = state
            try:
                self.state = CircuitState(state)
            except ValueError:
                self.state = CircuitState.OPEN

        super().__init__(
            f"Circuit breaker for '{service_name}' is {state_value}. Service is temporarily unavailable."
        )


# Alias for compatibility with code using CircuitBreakerOpenError from core.exceptions
CircuitBreakerOpenError = CircuitBreakerError


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
        *,
        failure_threshold: int | None = None,
        recovery_timeout: float | None = None,
        half_open_max_calls: int | None = None,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            name: Unique name for this circuit breaker
            config: Configuration (uses defaults if not provided)
            failure_threshold: Override config failure threshold (for compatibility)
            recovery_timeout: Override config recovery timeout (for compatibility)
            half_open_max_calls: Override config half_open_max_calls (for compatibility)
        """
        self._name = name

        # Build config from either provided config or individual parameters
        if config is not None:
            self._config = config
        else:
            self._config = CircuitBreakerConfig(
                failure_threshold=failure_threshold if failure_threshold is not None else 5,
                recovery_timeout=recovery_timeout if recovery_timeout is not None else 30.0,
                half_open_max_calls=half_open_max_calls if half_open_max_calls is not None else 3,
            )

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

        # Initialize Prometheus metrics
        CIRCUIT_BREAKER_STATE.labels(service=name).set(0)

        logger.info(
            f"CircuitBreaker '{name}' initialized: "
            f"failure_threshold={self._config.failure_threshold}, "
            f"recovery_timeout={self._config.recovery_timeout}s, "
            f"half_open_max_calls={self._config.half_open_max_calls}"
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

    # =========================================================================
    # Backward Compatibility Properties
    # =========================================================================
    # These properties provide direct access to config values for code that
    # expects _failure_threshold, _recovery_timeout, _half_open_max_calls
    # as instance attributes (e.g., tests accessing internal state).

    @property
    def _failure_threshold(self) -> int:
        """Backward-compatible access to config.failure_threshold."""
        return self._config.failure_threshold

    @property
    def _recovery_timeout(self) -> float:
        """Backward-compatible access to config.recovery_timeout."""
        return self._config.recovery_timeout

    @property
    def _half_open_max_calls(self) -> int:
        """Backward-compatible access to config.half_open_max_calls."""
        return self._config.half_open_max_calls

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
            # Update Prometheus metrics
            CIRCUIT_BREAKER_CALLS_TOTAL.labels(service=self._name, result="success").inc()

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

            # Update Prometheus metrics
            CIRCUIT_BREAKER_FAILURES_TOTAL.labels(service=self._name).inc()
            CIRCUIT_BREAKER_CALLS_TOTAL.labels(service=self._name, result="failure").inc()

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

        # Update Prometheus metrics
        CIRCUIT_BREAKER_STATE.labels(service=self._name).set(1)
        CIRCUIT_BREAKER_STATE_CHANGES_TOTAL.labels(
            service=self._name,
            from_state=prev_state.value,
            to_state="open",
        ).inc()

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

        # Update Prometheus metrics
        CIRCUIT_BREAKER_STATE.labels(service=self._name).set(2)
        CIRCUIT_BREAKER_STATE_CHANGES_TOTAL.labels(
            service=self._name,
            from_state="open",
            to_state="half_open",
        ).inc()

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

        # Update Prometheus metrics
        CIRCUIT_BREAKER_STATE.labels(service=self._name).set(0)
        CIRCUIT_BREAKER_STATE_CHANGES_TOTAL.labels(
            service=self._name,
            from_state="half_open",
            to_state="closed",
        ).inc()

        logger.info(
            f"CircuitBreaker '{self._name}' transitioned HALF_OPEN -> CLOSED (service recovered)"
        )

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state."""
        prev_state = self._state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        self._half_open_calls = 0
        self._last_failure_time = None
        self._last_state_change = datetime.now(UTC)

        # Update Prometheus metrics
        CIRCUIT_BREAKER_STATE.labels(service=self._name).set(0)
        if prev_state != CircuitState.CLOSED:
            CIRCUIT_BREAKER_STATE_CHANGES_TOTAL.labels(
                service=self._name,
                from_state=prev_state.value,
                to_state="closed",
            ).inc()

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

    # =========================================================================
    # Compatibility Methods (for core/circuit_breaker.py interface)
    # =========================================================================

    def get_state(self) -> CircuitState:
        """Get current circuit state (alias for state property).

        Returns:
            Current CircuitState
        """
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should proceed based on current state (sync version).

        This method also handles state transitions from OPEN to HALF_OPEN
        when the recovery timeout has elapsed. It also increments the
        half_open_calls counter when in HALF_OPEN state.

        Returns:
            True if request should proceed, False if it should be rejected
        """
        allowed = self._allow_call_unlocked()
        if allowed and self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
        return allowed

    async def allow_request_async(self) -> bool:
        """Check if a request should proceed (async version with lock).

        Thread-safe version that acquires a lock before checking state
        and potentially transitioning.

        Returns:
            True if request should proceed, False if it should be rejected
        """
        return await self.allow_call()

    def record_success(self) -> None:
        """Record a successful operation (sync version).

        Resets failure count and may transition circuit from HALF_OPEN to CLOSED.
        Note: Prefer using async methods for thread safety.
        """
        # Update Prometheus metrics
        CIRCUIT_BREAKER_CALLS_TOTAL.labels(service=self._name, result="success").inc()

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._config.success_threshold:
                self._transition_to_closed()
        elif self._state == CircuitState.CLOSED and self._failure_count > 0:
            self._failure_count = 0

    async def record_success_async(self) -> None:
        """Record a successful operation (async version with lock)."""
        await self._record_success()

    def record_failure(self) -> None:
        """Record a failed operation (sync version).

        Increments failure count and may transition circuit to OPEN state.
        Note: Prefer using async methods for thread safety.
        """
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        # Update Prometheus metrics
        CIRCUIT_BREAKER_FAILURES_TOTAL.labels(service=self._name).inc()
        CIRCUIT_BREAKER_CALLS_TOTAL.labels(service=self._name, result="failure").inc()

        if self._state == CircuitState.HALF_OPEN or (
            self._state == CircuitState.CLOSED
            and self._failure_count >= self._config.failure_threshold
        ):
            self._transition_to_open()

    async def record_failure_async(self) -> None:
        """Record a failed operation (async version with lock)."""
        await self._record_failure()

    async def reset_async(self) -> None:
        """Manually reset circuit breaker to CLOSED state (async version with lock)."""
        async with self._lock:
            self.reset()

    def check_and_raise(self) -> None:
        """Check circuit state and raise CircuitBreakerOpenError if open.

        Use this method when you want to explicitly check the circuit state
        and raise an exception with full context if the circuit is open.

        Raises:
            CoreCircuitBreakerOpenError: If the circuit is open and not allowing requests
        """
        if not self.allow_request():
            raise CoreCircuitBreakerOpenError(
                service_name=self._name,
                recovery_timeout=self._config.recovery_timeout,
            )

    async def check_and_raise_async(self) -> None:
        """Check circuit state and raise CircuitBreakerOpenError if open (async version).

        Thread-safe version that acquires a lock before checking state.

        Raises:
            CoreCircuitBreakerOpenError: If the circuit is open and not allowing requests
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
        1. Checks if circuit is open (raises CircuitBreakerError if so)
        2. Executes the function
        3. Records success or failure based on the outcome

        Args:
            func: Async function to execute (no arguments)
            record_on: Exception types that should be recorded as failures

        Returns:
            The result of the function call

        Raises:
            CircuitBreakerError: If the circuit is open
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
            CircuitBreakerError: If the circuit is open when entering

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
            Dictionary containing state, config, and timing information.
        """
        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self._config.failure_threshold,
            "recovery_timeout": self._config.recovery_timeout,
            "half_open_max_calls": self._config.half_open_max_calls,
            "half_open_calls": self._half_open_calls,
            "opened_at": self._opened_at,
            "last_state_change": (
                self._last_state_change.isoformat() if self._last_state_change else None
            ),
        }

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
