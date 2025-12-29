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
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
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


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, service_name: str, state: str) -> None:
        """Initialize circuit breaker error.

        Args:
            service_name: Name of the service with open circuit
            state: Current circuit state
        """
        self.service_name = service_name
        self.state = state
        super().__init__(
            f"Circuit breaker for '{service_name}' is {state}. Service is temporarily unavailable."
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
        self._last_failure_time: float | None = None
        self._opened_at: float | None = None
        self._half_open_calls = 0
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
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting calls)."""
        return self._state == CircuitState.OPEN

    async def call(
        self,
        operation: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
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
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self._transition_to_half_open()
                else:
                    raise CircuitBreakerError(self._name, self._state.value)

            # In HALF_OPEN, check if we've exceeded max trial calls
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self._config.half_open_max_calls:
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

        logger.info(f"CircuitBreaker '{self._name}' manually reset to CLOSED")

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
            "last_failure_time": self._last_failure_time,
            "opened_at": self._opened_at,
            "config": {
                "failure_threshold": self._config.failure_threshold,
                "recovery_timeout": self._config.recovery_timeout,
                "half_open_max_calls": self._config.half_open_max_calls,
                "success_threshold": self._config.success_threshold,
            },
        }


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
