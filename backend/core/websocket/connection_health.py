"""WebSocket connection health tracking and scoring.

This module provides health metrics tracking for WebSocket connections to:
- Track message latency (round-trip time for ping/pong)
- Count message failures and successes
- Calculate health scores for connections
- Identify degraded or unhealthy connections

NEM-3740: Implement connection health scoring.

Health Score Calculation:
- Base score starts at 100
- Message failures reduce score (configurable weight)
- High latency reduces score (configurable threshold)
- Score is clamped between 0 and 100

Example Usage:
    from backend.core.websocket.connection_health import get_health_tracker

    # Get the global health tracker
    tracker = get_health_tracker()

    # Register a new connection
    tracker.register_connection("conn-123")

    # Record a successful message send
    tracker.record_message_success("conn-123")

    # Record a message failure
    tracker.record_message_failure("conn-123")

    # Record latency measurement (in milliseconds)
    tracker.record_latency("conn-123", 45.5)

    # Get health score for a connection
    health = tracker.get_health_score("conn-123")
    print(f"Health score: {health.score}, Status: {health.status}")

    # Get all unhealthy connections
    unhealthy = tracker.get_unhealthy_connections(threshold=50.0)

    # Clean up on disconnect
    tracker.remove_connection("conn-123")
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionHealthStatus(str, Enum):
    """Connection health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class ConnectionMetrics:
    """Metrics for a single WebSocket connection."""

    connection_id: str
    created_at: float = field(default_factory=time.time)

    # Message counters
    messages_sent: int = 0
    messages_failed: int = 0

    # Latency tracking (store last N measurements)
    latency_samples: deque[float] = field(default_factory=lambda: deque(maxlen=10))

    # Last activity timestamps
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_latency_at: float | None = None

    def record_success(self) -> None:
        """Record a successful message send."""
        self.messages_sent += 1
        self.last_success_at = time.time()

    def record_failure(self) -> None:
        """Record a failed message send."""
        self.messages_failed += 1
        self.last_failure_at = time.time()

    def record_latency(self, latency_ms: float) -> None:
        """Record a latency measurement in milliseconds."""
        self.latency_samples.append(latency_ms)
        self.last_latency_at = time.time()

    @property
    def total_messages(self) -> int:
        """Total messages attempted (sent + failed)."""
        return self.messages_sent + self.messages_failed

    @property
    def failure_rate(self) -> float:
        """Calculate message failure rate (0.0 to 1.0)."""
        if self.total_messages == 0:
            return 0.0
        return self.messages_failed / self.total_messages

    @property
    def average_latency(self) -> float | None:
        """Calculate average latency from recent samples."""
        if not self.latency_samples:
            return None
        return sum(self.latency_samples) / len(self.latency_samples)

    @property
    def max_latency(self) -> float | None:
        """Get maximum latency from recent samples."""
        if not self.latency_samples:
            return None
        return max(self.latency_samples)

    @property
    def connection_age_seconds(self) -> float:
        """Get connection age in seconds."""
        return time.time() - self.created_at


@dataclass
class ConnectionHealth:
    """Health assessment for a WebSocket connection."""

    connection_id: str
    score: float  # 0.0 to 100.0
    status: ConnectionHealthStatus
    metrics: ConnectionMetrics

    # Breakdown of score components
    failure_penalty: float = 0.0
    latency_penalty: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert health assessment to dictionary."""
        return {
            "connection_id": self.connection_id,
            "score": round(self.score, 2),
            "status": self.status.value,
            "messages_sent": self.metrics.messages_sent,
            "messages_failed": self.metrics.messages_failed,
            "failure_rate": round(self.metrics.failure_rate, 4),
            "average_latency_ms": (
                round(self.metrics.average_latency, 2)
                if self.metrics.average_latency is not None
                else None
            ),
            "max_latency_ms": (
                round(self.metrics.max_latency, 2) if self.metrics.max_latency is not None else None
            ),
            "connection_age_seconds": round(self.metrics.connection_age_seconds, 2),
            "failure_penalty": round(self.failure_penalty, 2),
            "latency_penalty": round(self.latency_penalty, 2),
        }


class ConnectionHealthTracker:
    """Tracks health metrics for WebSocket connections.

    Thread Safety:
    - Uses threading.RLock for thread-safe operations
    - Safe to use from multiple async tasks

    Configuration:
    - failure_weight: How much each failure affects the score (default: 20)
    - latency_threshold_ms: Latency above this starts penalizing (default: 100ms)
    - latency_penalty_per_100ms: Score reduction per 100ms above threshold (default: 10)
    - healthy_threshold: Score above this is considered healthy (default: 80)
    - degraded_threshold: Score above this but below healthy is degraded (default: 50)
    - critical_threshold: Score below this is critical (default: 20)
    """

    def __init__(
        self,
        failure_weight: float = 20.0,
        latency_threshold_ms: float = 100.0,
        latency_penalty_per_100ms: float = 10.0,
        healthy_threshold: float = 80.0,
        degraded_threshold: float = 50.0,
        critical_threshold: float = 20.0,
    ) -> None:
        """Initialize the health tracker with configurable thresholds."""
        self._metrics: dict[str, ConnectionMetrics] = {}
        self._lock = threading.RLock()

        # Configuration
        self.failure_weight = failure_weight
        self.latency_threshold_ms = latency_threshold_ms
        self.latency_penalty_per_100ms = latency_penalty_per_100ms
        self.healthy_threshold = healthy_threshold
        self.degraded_threshold = degraded_threshold
        self.critical_threshold = critical_threshold

    def register_connection(self, connection_id: str) -> None:
        """Register a new connection for health tracking.

        Args:
            connection_id: Unique identifier for the WebSocket connection.
        """
        with self._lock:
            if connection_id not in self._metrics:
                self._metrics[connection_id] = ConnectionMetrics(connection_id=connection_id)
                logger.debug(
                    f"Registered connection for health tracking: {connection_id}",
                    extra={"connection_id": connection_id},
                )

    def remove_connection(self, connection_id: str) -> ConnectionMetrics | None:
        """Remove a connection and return its final metrics.

        Args:
            connection_id: Unique identifier for the WebSocket connection.

        Returns:
            The final metrics for the connection, or None if not found.
        """
        with self._lock:
            metrics = self._metrics.pop(connection_id, None)
            if metrics:
                logger.debug(
                    f"Removed connection from health tracking: {connection_id}",
                    extra={
                        "connection_id": connection_id,
                        "messages_sent": metrics.messages_sent,
                        "messages_failed": metrics.messages_failed,
                    },
                )
            return metrics

    def record_message_success(self, connection_id: str) -> None:
        """Record a successful message send.

        Args:
            connection_id: Unique identifier for the WebSocket connection.
        """
        with self._lock:
            if connection_id not in self._metrics:
                self.register_connection(connection_id)
            self._metrics[connection_id].record_success()

    def record_message_failure(self, connection_id: str) -> None:
        """Record a failed message send.

        Args:
            connection_id: Unique identifier for the WebSocket connection.
        """
        with self._lock:
            if connection_id not in self._metrics:
                self.register_connection(connection_id)
            self._metrics[connection_id].record_failure()
            logger.debug(
                f"Connection {connection_id} message failure recorded",
                extra={"connection_id": connection_id},
            )

    def record_latency(self, connection_id: str, latency_ms: float) -> None:
        """Record a latency measurement.

        Args:
            connection_id: Unique identifier for the WebSocket connection.
            latency_ms: Round-trip latency in milliseconds.
        """
        with self._lock:
            if connection_id not in self._metrics:
                self.register_connection(connection_id)
            self._metrics[connection_id].record_latency(latency_ms)

    def _calculate_health_score(self, metrics: ConnectionMetrics) -> tuple[float, float, float]:
        """Calculate health score from metrics.

        Returns:
            Tuple of (score, failure_penalty, latency_penalty)
        """
        score = 100.0
        failure_penalty = 0.0
        latency_penalty = 0.0

        # Penalty for message failures
        if metrics.failure_rate > 0:
            # Scale penalty based on failure rate
            # 10% failure rate = 20 points, 50% = 100 points (capped)
            failure_penalty = min(metrics.failure_rate * self.failure_weight * 5, 100.0)
            score -= failure_penalty

        # Penalty for high latency
        avg_latency = metrics.average_latency
        if avg_latency is not None and avg_latency > self.latency_threshold_ms:
            # Penalty increases for every 100ms above threshold
            excess_latency = avg_latency - self.latency_threshold_ms
            latency_penalty = min((excess_latency / 100.0) * self.latency_penalty_per_100ms, 50.0)
            score -= latency_penalty

        # Clamp score to valid range
        score = max(0.0, min(100.0, score))

        return score, failure_penalty, latency_penalty

    def _get_status_from_score(self, score: float) -> ConnectionHealthStatus:
        """Determine health status from score."""
        if score >= self.healthy_threshold:
            return ConnectionHealthStatus.HEALTHY
        elif score >= self.degraded_threshold:
            return ConnectionHealthStatus.DEGRADED
        elif score >= self.critical_threshold:
            return ConnectionHealthStatus.UNHEALTHY
        else:
            return ConnectionHealthStatus.CRITICAL

    def get_health_score(self, connection_id: str) -> ConnectionHealth | None:
        """Get health assessment for a connection.

        Args:
            connection_id: Unique identifier for the WebSocket connection.

        Returns:
            ConnectionHealth assessment, or None if connection not found.
        """
        with self._lock:
            metrics = self._metrics.get(connection_id)
            if metrics is None:
                return None

            score, failure_penalty, latency_penalty = self._calculate_health_score(metrics)
            status = self._get_status_from_score(score)

            return ConnectionHealth(
                connection_id=connection_id,
                score=score,
                status=status,
                metrics=metrics,
                failure_penalty=failure_penalty,
                latency_penalty=latency_penalty,
            )

    def get_all_health_scores(self) -> list[ConnectionHealth]:
        """Get health assessments for all tracked connections.

        Returns:
            List of ConnectionHealth assessments.
        """
        with self._lock:
            results = []
            for connection_id in self._metrics:
                health = self.get_health_score(connection_id)
                if health:
                    results.append(health)
            return results

    def get_unhealthy_connections(self, threshold: float | None = None) -> list[ConnectionHealth]:
        """Get all connections below a health threshold.

        Args:
            threshold: Score threshold (default: degraded_threshold)

        Returns:
            List of unhealthy ConnectionHealth assessments.
        """
        if threshold is None:
            threshold = self.degraded_threshold

        all_health = self.get_all_health_scores()
        return [h for h in all_health if h.score < threshold]

    def get_connection_count(self) -> int:
        """Get number of tracked connections."""
        with self._lock:
            return len(self._metrics)

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate health statistics.

        Returns:
            Dictionary with aggregate stats.
        """
        with self._lock:
            if not self._metrics:
                return {
                    "total_connections": 0,
                    "healthy_count": 0,
                    "degraded_count": 0,
                    "unhealthy_count": 0,
                    "critical_count": 0,
                    "average_score": None,
                    "total_messages_sent": 0,
                    "total_messages_failed": 0,
                }

            all_health = self.get_all_health_scores()
            scores = [h.score for h in all_health]

            status_counts = {
                ConnectionHealthStatus.HEALTHY: 0,
                ConnectionHealthStatus.DEGRADED: 0,
                ConnectionHealthStatus.UNHEALTHY: 0,
                ConnectionHealthStatus.CRITICAL: 0,
            }
            for h in all_health:
                status_counts[h.status] += 1

            total_sent = sum(m.messages_sent for m in self._metrics.values())
            total_failed = sum(m.messages_failed for m in self._metrics.values())

            return {
                "total_connections": len(self._metrics),
                "healthy_count": status_counts[ConnectionHealthStatus.HEALTHY],
                "degraded_count": status_counts[ConnectionHealthStatus.DEGRADED],
                "unhealthy_count": status_counts[ConnectionHealthStatus.UNHEALTHY],
                "critical_count": status_counts[ConnectionHealthStatus.CRITICAL],
                "average_score": round(sum(scores) / len(scores), 2) if scores else None,
                "total_messages_sent": total_sent,
                "total_messages_failed": total_failed,
            }


# =============================================================================
# Global Singleton Instance
# =============================================================================

_health_tracker: ConnectionHealthTracker | None = None
_tracker_lock = threading.Lock()


def get_health_tracker() -> ConnectionHealthTracker:
    """Get or create the global health tracker instance.

    This function provides a thread-safe singleton pattern for the
    ConnectionHealthTracker.

    Returns:
        ConnectionHealthTracker instance.

    Example:
        tracker = get_health_tracker()
        tracker.record_message_success("conn-123")
    """
    global _health_tracker  # noqa: PLW0603

    # Fast path: tracker already exists
    if _health_tracker is not None:
        return _health_tracker

    # Slow path: need to initialize with lock
    with _tracker_lock:
        # Double-check after acquiring lock
        if _health_tracker is None:
            _health_tracker = ConnectionHealthTracker()
            logger.info("Global connection health tracker initialized")

    return _health_tracker


def reset_health_tracker_state() -> None:
    """Reset the global health tracker state for testing purposes.

    Warning: Only use this in test teardown, never in production code.
    """
    global _health_tracker  # noqa: PLW0603
    _health_tracker = None
