"""WebSocket circuit breaker pattern for connection resilience.

This module provides a circuit breaker specifically designed for WebSocket connections
in the event and system broadcasters. It tracks connection failures and provides
graceful degradation when connections are unreliable.

States:
    - CLOSED: Normal operation, WebSocket operations proceed normally
    - OPEN: Too many failures, operations are blocked to allow recovery
    - HALF_OPEN: Testing recovery, limited operations allowed

Features:
    - Configurable failure thresholds and recovery timeouts
    - Half-open state for gradual recovery testing
    - Thread-safe with asyncio Lock
    - Metrics tracking for monitoring
    - Integration with broadcaster services
    - Optional Redis persistence for restart recovery
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = get_logger(__name__)


class WebSocketCircuitState(Enum):
    """WebSocket circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Rejecting connections, waiting to recover
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass(slots=True)
class WebSocketCircuitBreakerMetrics:
    """Metrics for WebSocket circuit breaker monitoring.

    Attributes:
        state: Current circuit state
        failure_count: Consecutive failures since last success
        success_count: Consecutive successes in half-open state
        total_failures: Total failures recorded
        total_successes: Total successes recorded
        last_failure_time: Timestamp of last failure (monotonic time)
        last_state_change: Timestamp of last state transition
        opened_at: Timestamp when circuit was last opened (monotonic time)
        consecutive_half_open_failures: Count of consecutive HALF_OPEN failures for backoff
        current_backoff_delay: Current exponential backoff delay in seconds
        backoff_expires_at: Monotonic timestamp when backoff period expires
    """

    state: WebSocketCircuitState
    failure_count: int = 0
    success_count: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_time: float | None = None
    last_state_change: datetime | None = None
    opened_at: float | None = None
    consecutive_half_open_failures: int = 0
    current_backoff_delay: float = 0.0
    backoff_expires_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "last_failure_time": self.last_failure_time,
            "last_state_change": (
                self.last_state_change.isoformat() if self.last_state_change else None
            ),
            "opened_at": self.opened_at,
            "consecutive_half_open_failures": self.consecutive_half_open_failures,
            "current_backoff_delay": self.current_backoff_delay,
            "backoff_expires_at": self.backoff_expires_at,
        }


class WebSocketCircuitBreaker:
    """Circuit breaker for WebSocket connections.

    Implements the circuit breaker pattern specifically for WebSocket broadcaster
    services. When a broadcaster experiences repeated failures (e.g., Redis
    disconnections), the circuit breaker opens to prevent further failed attempts
    and allows time for recovery.

    Usage:
        breaker = WebSocketCircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
        )

        # Check if operation is permitted
        if breaker.is_call_permitted():
            try:
                await some_websocket_operation()
                breaker.record_success()
            except Exception:
                breaker.record_failure()
        else:
            # Handle circuit open state (degraded mode)
            pass
    """

    # Redis persistence TTL in seconds (5 minutes)
    REDIS_STATE_TTL: int = 300

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
        success_threshold: int = 1,
        name: str = "websocket",
        backoff_base_delay: float = 1.0,
        backoff_max_delay: float = 60.0,
        redis_client: RedisClient | None = None,
    ) -> None:
        """Initialize WebSocket circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before transitioning to half-open
            half_open_max_calls: Maximum calls allowed in half-open state
            success_threshold: Successes needed in half-open to close circuit
            name: Name identifier for this circuit breaker
            backoff_base_delay: Base delay for exponential backoff in HALF_OPEN state (seconds)
            backoff_max_delay: Maximum delay for exponential backoff in HALF_OPEN state (seconds)
            redis_client: Optional Redis client for state persistence across restarts.
                If not provided, state is stored in-memory only.
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        self._success_threshold = success_threshold
        self._backoff_base_delay = backoff_base_delay
        self._backoff_max_delay = backoff_max_delay
        self._redis: RedisClient | None = redis_client

        # State tracking
        self._state = WebSocketCircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

        # Exponential backoff tracking for HALF_OPEN failures
        self._consecutive_half_open_failures = 0
        self._current_backoff_delay: float = 0.0
        self._backoff_expires_at: float | None = None

        # Metrics tracking
        self._total_failures = 0
        self._total_successes = 0
        self._last_failure_time: float | None = None
        self._opened_at: float | None = None
        self._last_state_change: datetime | None = None

        # Thread safety
        self._lock = asyncio.Lock()

        logger.info(
            f"WebSocketCircuitBreaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s, "
            f"backoff_base_delay={backoff_base_delay}s, "
            f"backoff_max_delay={backoff_max_delay}s, "
            f"redis_persistence={'enabled' if redis_client else 'disabled'}"
        )

    @property
    def name(self) -> str:
        """Get circuit breaker name."""
        return self._name

    @property
    def failure_threshold(self) -> int:
        """Get failure threshold."""
        return self._failure_threshold

    @property
    def recovery_timeout(self) -> float:
        """Get recovery timeout in seconds."""
        return self._recovery_timeout

    @property
    def failure_count(self) -> int:
        """Get current consecutive failure count."""
        return self._failure_count

    @property
    def last_failure_time(self) -> float | None:
        """Get last failure time (monotonic)."""
        return self._last_failure_time

    @property
    def backoff_base_delay(self) -> float:
        """Get base delay for exponential backoff in seconds."""
        return self._backoff_base_delay

    @property
    def backoff_max_delay(self) -> float:
        """Get maximum delay for exponential backoff in seconds."""
        return self._backoff_max_delay

    @property
    def consecutive_half_open_failures(self) -> int:
        """Get count of consecutive HALF_OPEN failures for backoff calculation."""
        return self._consecutive_half_open_failures

    @property
    def current_backoff_delay(self) -> float:
        """Get current exponential backoff delay in seconds."""
        return self._current_backoff_delay

    @property
    def backoff_expires_at(self) -> float | None:
        """Get monotonic timestamp when backoff period expires."""
        return self._backoff_expires_at

    def get_state(self) -> WebSocketCircuitState:
        """Get current circuit state.

        Note: This method checks if we should transition from OPEN to HALF_OPEN
        based on the recovery timeout, but does NOT acquire a lock. For thread-safe
        state checks with potential transitions, use is_call_permitted().

        Returns:
            Current WebSocketCircuitState
        """
        # Check if we should transition from OPEN to HALF_OPEN
        # Note: Don't transition here without lock - just report current state
        # The actual transition happens in is_call_permitted()
        return self._state

    def is_call_permitted(self) -> bool:
        """Check if a call should proceed based on current state.

        This is a synchronous check that also handles state transitions from
        OPEN to HALF_OPEN when the recovery timeout has elapsed.

        Returns:
            True if call should proceed, False if it should be rejected
        """
        if self._state == WebSocketCircuitState.CLOSED:
            return True

        if self._state == WebSocketCircuitState.OPEN:
            if self._should_attempt_recovery():
                self._transition_to_half_open()
                # Increment counter for this first call in half-open state
                self._half_open_calls += 1
                return True
            return False

        if self._state == WebSocketCircuitState.HALF_OPEN:
            # Limit concurrent calls in half-open state
            if self._half_open_calls < self._half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        return False

    async def is_call_permitted_async(self) -> bool:
        """Check if a call should proceed (async version with lock).

        Thread-safe version that acquires a lock before checking state
        and potentially transitioning. Also persists state to Redis if
        configured and a state transition occurred (OPEN -> HALF_OPEN).

        Returns:
            True if call should proceed, False if it should be rejected
        """
        prev_state = self._state
        async with self._lock:
            result = self.is_call_permitted()
        # Persist if state changed (OPEN -> HALF_OPEN transition)
        if self._state != prev_state:
            await self._persist_state()
        return result

    def record_success(self) -> None:
        """Record a successful operation.

        Resets failure count and may transition circuit from HALF_OPEN to CLOSED.
        """
        self._total_successes += 1

        if self._state == WebSocketCircuitState.HALF_OPEN:
            self._success_count += 1
            logger.debug(
                f"WebSocketCircuitBreaker '{self._name}' half-open success: "
                f"{self._success_count}/{self._success_threshold}"
            )

            if self._success_count >= self._success_threshold:
                self._transition_to_closed()
        elif self._state == WebSocketCircuitState.CLOSED:
            # Reset failure count on success in closed state
            if self._failure_count > 0:
                logger.debug(
                    f"WebSocketCircuitBreaker '{self._name}' resetting failure count on success"
                )
                self._failure_count = 0

    async def record_success_async(self) -> None:
        """Record a successful operation (async version with lock).

        Also persists state to Redis if configured and a state transition occurred.
        """
        prev_state = self._state
        async with self._lock:
            self.record_success()
        # Persist if state changed (HALF_OPEN -> CLOSED transition)
        if self._state != prev_state:
            await self._persist_state()

    def record_failure(self) -> None:
        """Record a failed operation.

        Increments failure count and may transition circuit to OPEN state.
        """
        self._failure_count += 1
        self._total_failures += 1
        self._last_failure_time = time.monotonic()

        logger.warning(
            f"WebSocketCircuitBreaker '{self._name}' failure recorded: "
            f"{self._failure_count}/{self._failure_threshold}"
        )

        if self._state == WebSocketCircuitState.HALF_OPEN:
            # Any failure in half-open reopens the circuit
            self._transition_to_open()
        elif (
            self._state == WebSocketCircuitState.CLOSED
            and self._failure_count >= self._failure_threshold
        ):
            self._transition_to_open()

    async def record_failure_async(self) -> None:
        """Record a failed operation (async version with lock).

        Also persists state to Redis if configured and a state transition occurred.
        """
        prev_state = self._state
        async with self._lock:
            self.record_failure()
        # Persist if state changed (CLOSED -> OPEN or HALF_OPEN -> OPEN transition)
        if self._state != prev_state:
            await self._persist_state()

    def _should_attempt_recovery(self) -> bool:
        """Check if recovery timeout and backoff period have elapsed.

        Recovery is only attempted when:
        1. The recovery_timeout has elapsed since the circuit opened
        2. Any exponential backoff period (from previous HALF_OPEN failures) has expired

        Returns:
            True if recovery can be attempted, False otherwise
        """
        if self._opened_at is None:
            return False

        current_time = time.monotonic()

        # Check base recovery timeout
        elapsed = current_time - self._opened_at
        if elapsed < self._recovery_timeout:
            return False

        # Check exponential backoff if we have previous HALF_OPEN failures
        return self._backoff_expires_at is None or current_time >= self._backoff_expires_at

    def _calculate_backoff_delay(self) -> float:
        """Calculate exponential backoff delay based on consecutive HALF_OPEN failures.

        Formula: min(base_delay * 2^failures, max_delay)

        Returns:
            Backoff delay in seconds
        """
        if self._consecutive_half_open_failures == 0:
            return 0.0
        delay: float = self._backoff_base_delay * (2**self._consecutive_half_open_failures)
        return min(delay, self._backoff_max_delay)

    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state.

        When transitioning from HALF_OPEN (indicating a failed recovery attempt),
        increment the consecutive HALF_OPEN failure count and calculate exponential
        backoff for the next recovery attempt.
        """
        prev_state = self._state
        current_time = time.monotonic()

        # If transitioning from HALF_OPEN, apply exponential backoff
        if prev_state == WebSocketCircuitState.HALF_OPEN:
            self._consecutive_half_open_failures += 1
            self._current_backoff_delay = self._calculate_backoff_delay()
            self._backoff_expires_at = current_time + self._current_backoff_delay

            logger.warning(
                f"WebSocketCircuitBreaker '{self._name}' HALF_OPEN failed, "
                f"applying backoff: {self._current_backoff_delay:.2f}s "
                f"(consecutive failures: {self._consecutive_half_open_failures})"
            )

        self._state = WebSocketCircuitState.OPEN
        self._opened_at = current_time
        self._success_count = 0
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

        logger.warning(
            f"WebSocketCircuitBreaker '{self._name}' transitioned {prev_state.value} -> OPEN "
            f"(failures={self._failure_count}, threshold={self._failure_threshold})"
        )

    def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        self._state = WebSocketCircuitState.HALF_OPEN
        self._success_count = 0
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

        logger.info(
            f"WebSocketCircuitBreaker '{self._name}' transitioned OPEN -> HALF_OPEN "
            f"(testing recovery after {self._recovery_timeout}s)"
        )

    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state.

        Resets all state including exponential backoff counters, as successful
        recovery indicates the service is healthy again.
        """
        self._state = WebSocketCircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

        # Reset backoff on successful connection
        self._consecutive_half_open_failures = 0
        self._current_backoff_delay = 0.0
        self._backoff_expires_at = None

        logger.info(
            f"WebSocketCircuitBreaker '{self._name}' transitioned HALF_OPEN -> CLOSED "
            "(service recovered, backoff reset)"
        )

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED state.

        This clears all failure counts, backoff state, and returns the circuit
        to normal operation. Use this after fixing underlying issues or for maintenance.
        """
        self._state = WebSocketCircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        self._half_open_calls = 0
        self._last_state_change = datetime.now(UTC)

        # Reset backoff state
        self._consecutive_half_open_failures = 0
        self._current_backoff_delay = 0.0
        self._backoff_expires_at = None

        logger.info(f"WebSocketCircuitBreaker '{self._name}' manually reset to CLOSED")

    async def reset_async(self) -> None:
        """Manually reset circuit breaker to CLOSED state (async version with lock).

        Also clears persisted state from Redis if configured.
        """
        async with self._lock:
            self.reset()
        # Clear persisted state and persist new CLOSED state
        await self.clear_persisted_state()
        await self._persist_state()

    def get_metrics(self) -> WebSocketCircuitBreakerMetrics:
        """Get current circuit breaker metrics.

        Returns:
            WebSocketCircuitBreakerMetrics with current state and counters
        """
        return WebSocketCircuitBreakerMetrics(
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            total_failures=self._total_failures,
            total_successes=self._total_successes,
            last_failure_time=self._last_failure_time,
            last_state_change=self._last_state_change,
            opened_at=self._opened_at,
            consecutive_half_open_failures=self._consecutive_half_open_failures,
            current_backoff_delay=self._current_backoff_delay,
            backoff_expires_at=self._backoff_expires_at,
        )

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status as a dictionary.

        Returns:
            Dictionary with status information for API responses
        """
        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
            "last_failure_time": self._last_failure_time,
            "opened_at": self._opened_at,
            "last_state_change": (
                self._last_state_change.isoformat() if self._last_state_change else None
            ),
            "backoff": {
                "consecutive_half_open_failures": self._consecutive_half_open_failures,
                "current_backoff_delay": self._current_backoff_delay,
                "backoff_expires_at": self._backoff_expires_at,
            },
            "config": {
                "failure_threshold": self._failure_threshold,
                "recovery_timeout": self._recovery_timeout,
                "half_open_max_calls": self._half_open_max_calls,
                "success_threshold": self._success_threshold,
                "backoff_base_delay": self._backoff_base_delay,
                "backoff_max_delay": self._backoff_max_delay,
            },
        }

    def __str__(self) -> str:
        """String representation of circuit breaker."""
        return f"WebSocketCircuitBreaker({self._name}, state={self._state.value.upper()})"

    def __repr__(self) -> str:
        """Detailed representation of circuit breaker."""
        return (
            f"WebSocketCircuitBreaker(name={self._name!r}, "
            f"state={self._state.value}, "
            f"failures={self._failure_count})"
        )

    # =========================================================================
    # Redis Persistence Methods
    # =========================================================================

    def _get_redis_key(self) -> str:
        """Get the Redis key for this circuit breaker's state.

        Returns:
            Redis key string in format 'circuit_breaker:{name}'
        """
        return f"circuit_breaker:{self._name}"

    async def _persist_state(self) -> None:
        """Persist current circuit breaker state to Redis.

        This method is called after state transitions to enable restart recovery.
        State is stored with a TTL to automatically expire if not refreshed.

        If Redis is not configured, this method returns without doing anything.
        If Redis operations fail, the error is logged but not raised to avoid
        disrupting circuit breaker operations.
        """
        if self._redis is None:
            return

        try:
            state_data = {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "opened_at": self._opened_at,
                "consecutive_half_open_failures": self._consecutive_half_open_failures,
                "current_backoff_delay": self._current_backoff_delay,
                "backoff_expires_at": self._backoff_expires_at,
            }
            await self._redis.set(
                self._get_redis_key(),
                json.dumps(state_data),
                expire=self.REDIS_STATE_TTL,
            )
            logger.debug(
                f"WebSocketCircuitBreaker '{self._name}' state persisted to Redis: "
                f"state={self._state.value}"
            )
        except Exception as e:
            # Log but don't raise - persistence failure shouldn't break circuit breaker
            logger.warning(
                f"WebSocketCircuitBreaker '{self._name}' failed to persist state to Redis: {e}"
            )

    async def restore_state_from_redis(self) -> bool:
        """Restore circuit breaker state from Redis.

        This method should be called after initialization to restore state
        from a previous run. It enables the circuit breaker to survive service
        restarts while maintaining its state (e.g., staying OPEN if it was OPEN
        before the restart).

        The restoration adjusts opened_at and backoff_expires_at timestamps
        relative to the current monotonic time since these are monotonic timestamps
        that are not meaningful across process restarts.

        Returns:
            True if state was successfully restored from Redis, False otherwise.
            Returns False if:
            - Redis is not configured
            - No state exists in Redis (first start or expired)
            - Redis operation fails
            - State data is invalid

        Note:
            If restoration fails, the circuit breaker remains in its default
            CLOSED state, which is a safe fallback behavior.
        """
        if self._redis is None:
            return False

        try:
            state_data = await self._redis.get(self._get_redis_key())
            if state_data is None:
                logger.debug(f"WebSocketCircuitBreaker '{self._name}' no state found in Redis")
                return False

            # Parse state data
            data = json.loads(state_data) if isinstance(state_data, str) else state_data

            # Restore state
            state_value = data.get("state")
            if state_value:
                self._state = WebSocketCircuitState(state_value)

            self._failure_count = data.get("failure_count", 0)
            self._consecutive_half_open_failures = data.get("consecutive_half_open_failures", 0)
            self._current_backoff_delay = data.get("current_backoff_delay", 0.0)

            # For opened_at and backoff_expires_at, we need to adjust based on
            # current monotonic time since the original values are from a previous
            # process and not meaningful anymore. We assume the state was just
            # persisted, so we set opened_at to now and recalculate backoff_expires_at.
            current_time = time.monotonic()
            if data.get("opened_at") is not None and self._state != WebSocketCircuitState.CLOSED:
                # Set opened_at to current time - the recovery timeout will start fresh
                # This is conservative but safe - it gives the system time to stabilize
                self._opened_at = current_time

            if data.get("backoff_expires_at") is not None and self._current_backoff_delay > 0:
                # Recalculate backoff expiry based on current time and stored delay
                self._backoff_expires_at = current_time + self._current_backoff_delay

            logger.info(
                f"WebSocketCircuitBreaker '{self._name}' state restored from Redis: "
                f"state={self._state.value}, failure_count={self._failure_count}, "
                f"consecutive_half_open_failures={self._consecutive_half_open_failures}"
            )
            return True

        except json.JSONDecodeError as e:
            logger.warning(
                f"WebSocketCircuitBreaker '{self._name}' failed to decode state from Redis: {e}"
            )
            return False
        except Exception as e:
            logger.warning(
                f"WebSocketCircuitBreaker '{self._name}' failed to restore state from Redis: {e}"
            )
            return False

    async def clear_persisted_state(self) -> bool:
        """Clear the persisted state from Redis.

        This is useful when performing a manual reset or during testing.

        Returns:
            True if state was cleared, False if Redis is not configured or deletion failed.
        """
        if self._redis is None:
            return False

        try:
            await self._redis.delete(self._get_redis_key())
            logger.debug(
                f"WebSocketCircuitBreaker '{self._name}' cleared persisted state from Redis"
            )
            return True
        except Exception as e:
            logger.warning(
                f"WebSocketCircuitBreaker '{self._name}' failed to clear state from Redis: {e}"
            )
            return False
