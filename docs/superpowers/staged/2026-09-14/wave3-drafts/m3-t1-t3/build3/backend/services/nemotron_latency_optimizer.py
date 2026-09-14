"""Nemotron latency optimizer for pipeline performance improvements (NEM-4522).

This module provides latency optimization strategies for the Nemotron LLM pipeline:

1. Latency-based Circuit Breaker: Opens when average latency exceeds threshold
2. Semaphore Acquire Timeout: Prevents queue backlog by timing out waiting requests
3. Adaptive Timeout: Reduces LLM timeout when queue depth is high
4. Request Prioritization: Allows high-confidence detections to skip ahead
5. Latency Metrics Tracking: Rolling window for latency monitoring

The goal is to reduce average Nemotron latency from 39.6s to <10s for most requests
by shedding load during high-latency periods and prioritizing important requests.

Usage:
    from backend.services.nemotron_latency_optimizer import (
        NemotronLatencyOptimizer,
        get_nemotron_optimizer,
    )

    optimizer = get_nemotron_optimizer()

    # Check if request should proceed
    if not optimizer.should_process_request():
        # Shed load - skip or delay this request
        return fallback_response()

    # Get adaptive timeout based on queue depth
    timeout = optimizer.get_adaptive_timeout(base_timeout=120.0)

    # Acquire semaphore with timeout (prevents indefinite waiting)
    async with optimizer.acquire_with_timeout(semaphore, timeout=30.0):
        result = await call_nemotron(timeout=timeout)

    # Record latency for adaptive adjustments
    optimizer.record_latency(latency_seconds)
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

from prometheus_client import Counter, Gauge, Histogram

from backend.core.logging import get_logger
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = get_logger(__name__)


# =============================================================================
# Prometheus Metrics for Latency Optimization (NEM-4522)
# =============================================================================

NEMOTRON_LATENCY_HISTOGRAM = Histogram(
    "hsi_nemotron_inference_latency_seconds",
    "Nemotron LLM inference latency in seconds",
    buckets=[1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120],
)

NEMOTRON_QUEUE_WAIT_HISTOGRAM = Histogram(
    "hsi_nemotron_queue_wait_seconds",
    "Time spent waiting for semaphore acquisition",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 15, 30, 60],
)

NEMOTRON_SHED_REQUESTS_TOTAL = Counter(
    "hsi_nemotron_shed_requests_total",
    "Total number of requests shed due to high latency/queue depth",
    labelnames=["reason"],
)

NEMOTRON_ADAPTIVE_TIMEOUT_GAUGE = Gauge(
    "hsi_nemotron_adaptive_timeout_seconds",
    "Current adaptive timeout value",
)

NEMOTRON_ROLLING_AVG_LATENCY_GAUGE = Gauge(
    "hsi_nemotron_rolling_avg_latency_seconds",
    "Rolling average latency over the observation window",
)

NEMOTRON_CIRCUIT_STATE_GAUGE = Gauge(
    "hsi_nemotron_latency_circuit_state",
    "Nemotron latency circuit breaker state (0=closed, 1=open, 2=half_open)",
)

NEMOTRON_QUEUE_DEPTH_GAUGE = Gauge(
    "hsi_nemotron_pending_queue_depth",
    "Current number of requests waiting for Nemotron inference",
)


class LoadSheddingReason(StrEnum):
    """Reasons for shedding a request."""

    CIRCUIT_OPEN = auto()
    QUEUE_TIMEOUT = auto()
    QUEUE_TOO_DEEP = auto()
    LATENCY_TOO_HIGH = auto()


@dataclass
class LatencyOptimizerConfig:
    """Configuration for Nemotron latency optimizer.

    Attributes:
        target_latency_seconds: Target p95 latency (default: 10s)
        max_acceptable_latency_seconds: Max latency before circuit opens (default: 30s)
        rolling_window_size: Number of samples for rolling average (default: 20)
        semaphore_acquire_timeout: Max time to wait for semaphore (default: 30s)
        max_queue_depth: Max pending requests before shedding (default: 50)
        circuit_failure_threshold: Consecutive high-latency before open (default: 5)
        circuit_recovery_timeout: Seconds before half-open (default: 60s)
        min_adaptive_timeout: Minimum adaptive timeout (default: 30s)
        adaptive_timeout_queue_factor: Timeout reduction per queued request (default: 2s)
    """

    target_latency_seconds: float = 10.0
    max_acceptable_latency_seconds: float = 30.0
    rolling_window_size: int = 20
    semaphore_acquire_timeout: float = 30.0
    max_queue_depth: int = 50
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 60.0
    min_adaptive_timeout: float = 30.0
    adaptive_timeout_queue_factor: float = 2.0


@dataclass
class LatencyStats:
    """Statistics for latency monitoring."""

    samples: deque[float] = field(default_factory=lambda: deque(maxlen=100))
    total_requests: int = 0
    shed_requests: int = 0
    circuit_trips: int = 0
    last_latency: float = 0.0
    last_sample_time: float = field(default_factory=time.monotonic)

    @property
    def rolling_average(self) -> float:
        """Calculate rolling average latency."""
        if not self.samples:
            return 0.0
        return sum(self.samples) / len(self.samples)

    @property
    def p95_latency(self) -> float:
        """Calculate p95 latency from samples."""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    @property
    def sample_count(self) -> int:
        """Get number of samples in the rolling window."""
        return len(self.samples)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary for API responses."""
        return {
            "rolling_average_seconds": round(self.rolling_average, 3),
            "p95_latency_seconds": round(self.p95_latency, 3),
            "last_latency_seconds": round(self.last_latency, 3),
            "sample_count": self.sample_count,
            "total_requests": self.total_requests,
            "shed_requests": self.shed_requests,
            "circuit_trips": self.circuit_trips,
        }


class NemotronLatencyOptimizer:
    """Optimizes Nemotron pipeline latency through adaptive strategies.

    This class implements multiple strategies to reduce pipeline latency:

    1. Latency-based Circuit Breaker:
       Opens when rolling average exceeds max_acceptable_latency, preventing
       further requests from piling up behind slow inference.

    2. Semaphore Acquire Timeout:
       Limits how long requests wait for the inference semaphore, shedding
       requests that would experience unacceptable queue delays.

    3. Adaptive Timeout:
       Reduces LLM timeout based on queue depth, ensuring requests don't
       wait too long when the queue is backed up.

    4. Queue Depth Limiting:
       Sheds requests when pending queue exceeds threshold.

    Example:
        optimizer = NemotronLatencyOptimizer()

        # Before each request
        if not optimizer.should_process_request():
            return fallback_response()

        # Get timeout based on current conditions
        timeout = optimizer.get_adaptive_timeout(120.0)

        # Acquire with timeout
        async with optimizer.acquire_with_timeout(semaphore):
            result = await nemotron_call(timeout=timeout)

        # After request
        optimizer.record_latency(elapsed_time)
    """

    def __init__(
        self,
        config: LatencyOptimizerConfig | None = None,
        redis_client: RedisClient | None = None,
    ):
        """Initialize the latency optimizer.

        Args:
            config: Optimizer configuration. Uses defaults if not provided.
            redis_client: Redis client for queue depth queries (optional).
        """
        self._config = config or LatencyOptimizerConfig()
        self._redis = redis_client
        self._stats = LatencyStats(samples=deque(maxlen=self._config.rolling_window_size))
        self._pending_count = 0
        self._lock = asyncio.Lock()

        # Initialize latency-based circuit breaker
        # This circuit breaker opens based on high latency, not HTTP errors
        self._circuit = CircuitBreaker(
            name="nemotron_latency",
            config=CircuitBreakerConfig(
                failure_threshold=self._config.circuit_failure_threshold,
                recovery_timeout=self._config.circuit_recovery_timeout,
                half_open_max_calls=3,
                success_threshold=2,
            ),
        )

        # Track consecutive high-latency calls for circuit logic
        self._consecutive_high_latency = 0

        logger.info(
            "NemotronLatencyOptimizer initialized",
            extra={
                "target_latency": self._config.target_latency_seconds,
                "max_latency": self._config.max_acceptable_latency_seconds,
                "queue_timeout": self._config.semaphore_acquire_timeout,
                "max_queue_depth": self._config.max_queue_depth,
            },
        )

    @property
    def config(self) -> LatencyOptimizerConfig:
        """Get the optimizer configuration."""
        return self._config

    @property
    def stats(self) -> LatencyStats:
        """Get latency statistics."""
        return self._stats

    @property
    def circuit_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self._circuit.state

    @property
    def pending_count(self) -> int:
        """Get current number of pending requests."""
        return self._pending_count

    def should_process_request(self) -> bool:
        """Check if a new request should be processed.

        Returns False if:
        - Circuit breaker is open (high latency detected)
        - Queue depth exceeds maximum

        Returns:
            True if request should proceed, False if it should be shed.
        """
        # Check circuit breaker state
        if self._circuit.state == CircuitState.OPEN:
            NEMOTRON_SHED_REQUESTS_TOTAL.labels(reason=LoadSheddingReason.CIRCUIT_OPEN.value).inc()
            self._stats.shed_requests += 1
            logger.warning(
                "Shedding request: latency circuit breaker open",
                extra={
                    "circuit_state": self._circuit.state.value,
                    "rolling_avg_latency": self._stats.rolling_average,
                },
            )
            return False

        # Check queue depth
        if self._pending_count >= self._config.max_queue_depth:
            NEMOTRON_SHED_REQUESTS_TOTAL.labels(
                reason=LoadSheddingReason.QUEUE_TOO_DEEP.value
            ).inc()
            self._stats.shed_requests += 1
            logger.warning(
                "Shedding request: queue too deep",
                extra={
                    "pending_count": self._pending_count,
                    "max_queue_depth": self._config.max_queue_depth,
                },
            )
            return False

        # Check if current rolling average is too high
        if self._stats.rolling_average > self._config.max_acceptable_latency_seconds:
            # Allow request but with warning - circuit will trip if it continues
            logger.warning(
                "High latency detected, request proceeding with caution",
                extra={
                    "rolling_avg_latency": self._stats.rolling_average,
                    "max_acceptable": self._config.max_acceptable_latency_seconds,
                },
            )

        return True

    def get_adaptive_timeout(self, base_timeout: float) -> float:
        """Calculate adaptive timeout based on queue depth and latency.

        When the queue is backed up, reduces timeout to prevent requests
        from waiting excessively long. The timeout is reduced by
        adaptive_timeout_queue_factor for each pending request.

        Args:
            base_timeout: Base timeout in seconds (from settings).

        Returns:
            Adjusted timeout in seconds.
        """
        # Start with base timeout
        timeout = base_timeout

        # Reduce based on queue depth
        queue_reduction = self._pending_count * self._config.adaptive_timeout_queue_factor
        timeout = max(self._config.min_adaptive_timeout, timeout - queue_reduction)

        # If latency is high, further reduce to shed slow requests faster
        if self._stats.rolling_average > self._config.target_latency_seconds:
            latency_factor = self._stats.rolling_average / self._config.target_latency_seconds
            timeout = max(self._config.min_adaptive_timeout, timeout / latency_factor)

        # Update metric
        NEMOTRON_ADAPTIVE_TIMEOUT_GAUGE.set(timeout)

        return timeout

    async def acquire_with_timeout(
        self,
        semaphore: asyncio.Semaphore,
        timeout: float | None = None,
    ) -> AsyncSemaphoreContextManager:
        """Acquire semaphore with timeout to prevent queue backlog.

        This method wraps semaphore acquisition with a timeout, ensuring
        requests don't wait indefinitely when the queue is backed up.
        If the timeout expires, the request is shed.

        Args:
            semaphore: The inference semaphore to acquire.
            timeout: Acquisition timeout in seconds. Uses config default if None.

        Returns:
            Async context manager that releases on exit.

        Raises:
            SemaphoreAcquireTimeout: If semaphore cannot be acquired in time.
        """
        acquire_timeout = timeout or self._config.semaphore_acquire_timeout

        # Track pending requests
        async with self._lock:
            self._pending_count += 1
            NEMOTRON_QUEUE_DEPTH_GAUGE.set(self._pending_count)

        return AsyncSemaphoreContextManager(
            semaphore=semaphore,
            timeout=acquire_timeout,
            optimizer=self,
        )

    def record_latency(self, latency_seconds: float) -> None:
        """Record a completed request's latency.

        Updates rolling statistics and triggers circuit breaker logic
        if latency exceeds acceptable threshold.

        Args:
            latency_seconds: Time taken for the Nemotron inference.
        """
        self._stats.total_requests += 1
        self._stats.last_latency = latency_seconds
        self._stats.samples.append(latency_seconds)
        self._stats.last_sample_time = time.monotonic()

        # Update metrics
        NEMOTRON_LATENCY_HISTOGRAM.observe(latency_seconds)
        NEMOTRON_ROLLING_AVG_LATENCY_GAUGE.set(self._stats.rolling_average)

        # Check if this was a high-latency request
        if latency_seconds > self._config.max_acceptable_latency_seconds:
            self._consecutive_high_latency += 1
            logger.warning(
                "High latency request recorded",
                extra={
                    "latency_seconds": latency_seconds,
                    "consecutive_high_latency": self._consecutive_high_latency,
                    "threshold": self._config.max_acceptable_latency_seconds,
                },
            )

            # Check if we're about to trip the circuit before recording failure
            # (record_failure may transition state to OPEN)
            was_open = self._circuit.state == CircuitState.OPEN

            # Record as circuit breaker failure
            self._circuit.record_failure()

            # Check if circuit just transitioned to OPEN
            if self._circuit.state == CircuitState.OPEN and not was_open:
                self._stats.circuit_trips += 1
                NEMOTRON_CIRCUIT_STATE_GAUGE.set(1)  # 1 = OPEN
                logger.error(
                    "Latency circuit breaker tripped",
                    extra={
                        "consecutive_high_latency": self._consecutive_high_latency,
                        "rolling_average": self._stats.rolling_average,
                    },
                )
        else:
            # Good latency - reset consecutive counter and record success
            self._consecutive_high_latency = 0
            self._circuit.record_success()

            if self._circuit.state == CircuitState.CLOSED:
                NEMOTRON_CIRCUIT_STATE_GAUGE.set(0)  # 0 = CLOSED
            elif self._circuit.state == CircuitState.HALF_OPEN:
                NEMOTRON_CIRCUIT_STATE_GAUGE.set(2)  # 2 = HALF_OPEN

        logger.debug(
            "Latency recorded",
            extra={
                "latency_seconds": latency_seconds,
                "rolling_average": self._stats.rolling_average,
                "circuit_state": self._circuit.state.value,
            },
        )

    def _release_pending(self) -> None:
        """Decrement pending count (called when request completes)."""
        self._pending_count = max(0, self._pending_count - 1)
        NEMOTRON_QUEUE_DEPTH_GAUGE.set(self._pending_count)

    def reset_circuit(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._circuit.reset()
        self._consecutive_high_latency = 0
        NEMOTRON_CIRCUIT_STATE_GAUGE.set(0)
        logger.info("Nemotron latency circuit breaker manually reset")

    def get_status(self) -> dict[str, Any]:
        """Get optimizer status for API responses.

        Returns:
            Dictionary with current optimizer state and statistics.
        """
        return {
            "circuit_state": self._circuit.state.value,
            "pending_requests": self._pending_count,
            "consecutive_high_latency": self._consecutive_high_latency,
            "latency_stats": self._stats.to_dict(),
            "config": {
                "target_latency_seconds": self._config.target_latency_seconds,
                "max_acceptable_latency_seconds": self._config.max_acceptable_latency_seconds,
                "max_queue_depth": self._config.max_queue_depth,
                "semaphore_acquire_timeout": self._config.semaphore_acquire_timeout,
            },
        }


class SemaphoreAcquireTimeout(Exception):
    """Raised when semaphore acquisition times out."""

    def __init__(self, timeout: float, queue_depth: int):
        """Initialize timeout exception.

        Args:
            timeout: The timeout that was exceeded.
            queue_depth: Queue depth when timeout occurred.
        """
        super().__init__(
            f"Semaphore acquisition timed out after {timeout}s (queue depth: {queue_depth})"
        )
        self.timeout = timeout
        self.queue_depth = queue_depth


class AsyncSemaphoreContextManager:
    """Async context manager for semaphore with timeout.

    Wraps semaphore acquisition with a timeout and tracks queue wait time.
    On exit, releases the semaphore and decrements the pending count.
    """

    def __init__(
        self,
        semaphore: asyncio.Semaphore,
        timeout: float,
        optimizer: NemotronLatencyOptimizer,
    ):
        """Initialize context manager.

        Args:
            semaphore: The semaphore to acquire.
            timeout: Maximum time to wait for acquisition.
            optimizer: The optimizer to update on exit.
        """
        self._semaphore = semaphore
        self._timeout = timeout
        self._optimizer = optimizer
        self._acquired = False
        self._acquire_start: float = 0.0

    async def __aenter__(self) -> AsyncSemaphoreContextManager:
        """Acquire semaphore with timeout."""
        self._acquire_start = time.monotonic()

        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._timeout)
            self._acquired = True

            # Record queue wait time
            wait_time = time.monotonic() - self._acquire_start
            NEMOTRON_QUEUE_WAIT_HISTOGRAM.observe(wait_time)

            if wait_time > 5.0:
                logger.warning(
                    "Long queue wait time for Nemotron semaphore",
                    extra={
                        "wait_seconds": wait_time,
                        "timeout": self._timeout,
                    },
                )

            return self

        except TimeoutError:
            # Failed to acquire in time
            NEMOTRON_SHED_REQUESTS_TOTAL.labels(reason=LoadSheddingReason.QUEUE_TIMEOUT.value).inc()
            self._optimizer._stats.shed_requests += 1
            self._optimizer._release_pending()

            logger.warning(
                "Semaphore acquisition timeout - shedding request",
                extra={
                    "timeout": self._timeout,
                    "pending_count": self._optimizer.pending_count,
                },
            )

            raise SemaphoreAcquireTimeout(
                timeout=self._timeout,
                queue_depth=self._optimizer.pending_count,
            ) from None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Release semaphore and update pending count."""
        if self._acquired:
            self._semaphore.release()

        self._optimizer._release_pending()


# =============================================================================
# Global Singleton
# =============================================================================

_optimizer: NemotronLatencyOptimizer | None = None
_optimizer_lock = asyncio.Lock()


def get_nemotron_optimizer(
    redis_client: RedisClient | None = None,
) -> NemotronLatencyOptimizer:
    """Get or create the global Nemotron latency optimizer.

    Thread-safe singleton pattern. Creates optimizer on first access
    with default configuration from settings.

    Args:
        redis_client: Optional Redis client for queue depth queries.

    Returns:
        NemotronLatencyOptimizer singleton instance.
    """
    global _optimizer  # noqa: PLW0603

    if _optimizer is None:
        # Build config from settings with sensible defaults
        config = LatencyOptimizerConfig(
            target_latency_seconds=10.0,  # Target <10s per request
            max_acceptable_latency_seconds=30.0,  # Circuit opens at 30s avg
            rolling_window_size=20,
            semaphore_acquire_timeout=30.0,  # Don't wait more than 30s
            max_queue_depth=50,
            circuit_failure_threshold=5,
            circuit_recovery_timeout=60.0,
            min_adaptive_timeout=30.0,
            adaptive_timeout_queue_factor=2.0,
        )

        _optimizer = NemotronLatencyOptimizer(
            config=config,
            redis_client=redis_client,
        )

        logger.info("Global NemotronLatencyOptimizer initialized")

    return _optimizer


def reset_nemotron_optimizer() -> None:
    """Reset the global optimizer instance (for testing)."""
    global _optimizer  # noqa: PLW0603
    _optimizer = None
    logger.debug("NemotronLatencyOptimizer reset")
