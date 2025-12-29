"""Graceful degradation manager for handling partial outages.

This module orchestrates graceful degradation when external services experience
outages. It provides:
- Service health tracking with automatic mode transitions
- Job queueing for later processing when services are unavailable
- Redis fallback to in-memory queue when Redis is down
- Recovery handling to reprocess queued jobs

Degradation Modes:
    - NORMAL: All services healthy, full functionality
    - DEGRADED: Some services down, limited functionality
    - MINIMAL: Critical services down, basic functionality only
    - OFFLINE: All services down, queueing only

Features:
    - Automatic mode transitions based on service health
    - Configurable failure and recovery thresholds
    - In-memory queue fallback when Redis unavailable
    - Job reprocessing on service recovery
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeVar

from backend.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class DegradationMode(Enum):
    """System degradation modes."""

    NORMAL = "normal"
    DEGRADED = "degraded"
    MINIMAL = "minimal"
    OFFLINE = "offline"


class ServiceStatus(Enum):
    """Service health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """Health information for a monitored service.

    Attributes:
        name: Service name
        status: Current health status
        last_check: Timestamp of last health check
        last_success: Timestamp of last successful check
        consecutive_failures: Count of consecutive failed checks
        error_message: Last error message if unhealthy
    """

    name: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_check: float | None = None
    last_success: float | None = None
    consecutive_failures: int = 0
    error_message: str | None = None

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.status == ServiceStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_check": self.last_check,
            "last_success": self.last_success,
            "consecutive_failures": self.consecutive_failures,
            "error_message": self.error_message,
        }


@dataclass
class QueuedJob:
    """A job queued for later processing.

    Attributes:
        job_type: Type of job (e.g., "detection", "analysis")
        data: Job data payload
        queued_at: ISO timestamp when queued
        retry_count: Number of retry attempts
    """

    job_type: str
    data: dict[str, Any]
    queued_at: str
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "job_type": self.job_type,
            "data": self.data,
            "queued_at": self.queued_at,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueuedJob:
        """Create from dictionary."""
        return cls(
            job_type=data["job_type"],
            data=data["data"],
            queued_at=data["queued_at"],
            retry_count=data.get("retry_count", 0),
        )


@dataclass
class RegisteredService:
    """A registered service for health monitoring.

    Attributes:
        name: Service name
        health_check: Async callable returning bool for health
        critical: Whether service is critical for operation
        health: Current health state
    """

    name: str
    health_check: Callable[[], Any]
    critical: bool = False
    health: ServiceHealth = field(default_factory=lambda: ServiceHealth(name=""))

    def __post_init__(self) -> None:
        """Initialize health with correct name."""
        if self.health.name == "":
            self.health = ServiceHealth(name=self.name)


class DegradationManager:
    """Manages graceful degradation during partial outages.

    This class monitors service health and orchestrates graceful degradation
    when services become unavailable. It provides job queueing for later
    processing and automatic recovery handling.

    Usage:
        manager = DegradationManager(redis_client=redis)

        # Register services for monitoring
        manager.register_service(
            name="ai_detector",
            health_check=detector.health_check,
            critical=True,
        )

        # Check if we should queue instead of process
        if manager.should_queue_job("detection"):
            await manager.queue_job_for_later("detection", job_data)
        else:
            await process_job(job_data)
    """

    # Default queue name for degraded jobs
    DEGRADED_QUEUE = "degraded:jobs"

    def __init__(
        self,
        redis_client: Any | None = None,
        failure_threshold: int = 3,
        recovery_threshold: int = 2,
        max_memory_queue_size: int = 1000,
    ) -> None:
        """Initialize degradation manager.

        Args:
            redis_client: Redis client for job queueing
            failure_threshold: Failures before marking unhealthy
            recovery_threshold: Successes needed to confirm recovery
            max_memory_queue_size: Max jobs to hold in memory queue
        """
        self._redis = redis_client
        self._mode = DegradationMode.NORMAL
        self._services: dict[str, RegisteredService] = {}
        self._memory_queue: deque[QueuedJob] = deque(maxlen=max_memory_queue_size)
        self._lock = asyncio.Lock()
        self._redis_healthy = True

        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.max_memory_queue_size = max_memory_queue_size

        logger.info(
            f"DegradationManager initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_threshold={recovery_threshold}"
        )

    @property
    def mode(self) -> DegradationMode:
        """Get current degradation mode."""
        return self._mode

    @property
    def is_degraded(self) -> bool:
        """Check if system is in any degraded state."""
        return self._mode != DegradationMode.NORMAL

    def register_service(
        self,
        name: str,
        health_check: Callable[[], Any],
        critical: bool = False,
    ) -> None:
        """Register a service for health monitoring.

        Args:
            name: Unique service name
            health_check: Async callable that returns True if healthy
            critical: Whether this service is critical for operation
        """
        self._services[name] = RegisteredService(
            name=name,
            health_check=health_check,
            critical=critical,
        )
        logger.info(f"Registered service '{name}' (critical={critical})")

    def get_service_health(self, name: str) -> ServiceHealth:
        """Get health information for a service.

        Args:
            name: Service name

        Returns:
            ServiceHealth object
        """
        if name in self._services:
            return self._services[name].health
        return ServiceHealth(name=name, status=ServiceStatus.UNKNOWN)

    async def update_service_health(
        self,
        name: str,
        is_healthy: bool,
        error_message: str | None = None,
    ) -> None:
        """Update health status for a service.

        Args:
            name: Service name
            is_healthy: Whether service is healthy
            error_message: Error message if unhealthy
        """
        async with self._lock:
            if name not in self._services:
                logger.warning(f"Service '{name}' not registered")
                return

            service = self._services[name]
            health = service.health
            health.last_check = time.monotonic()

            if is_healthy:
                health.status = ServiceStatus.HEALTHY
                health.last_success = time.monotonic()
                health.consecutive_failures = 0
                health.error_message = None
                logger.debug(f"Service '{name}' is healthy")
            else:
                health.status = ServiceStatus.UNHEALTHY
                health.consecutive_failures += 1
                health.error_message = error_message
                logger.warning(
                    f"Service '{name}' unhealthy: "
                    f"failures={health.consecutive_failures}, "
                    f"error={error_message}"
                )

            # Check if we need to transition modes
            await self._evaluate_mode_transition()

    async def _evaluate_mode_transition(self) -> None:
        """Evaluate and perform mode transitions based on service health."""
        critical_unhealthy = 0
        total_unhealthy = 0

        for service in self._services.values():
            if service.health.consecutive_failures >= self.failure_threshold:
                total_unhealthy += 1
                if service.critical:
                    critical_unhealthy += 1

        old_mode = self._mode

        # Determine new mode based on health
        if critical_unhealthy == 0 and total_unhealthy == 0:
            self._mode = DegradationMode.NORMAL
        elif critical_unhealthy == 0:
            self._mode = DegradationMode.DEGRADED
        elif critical_unhealthy < len([s for s in self._services.values() if s.critical]):
            self._mode = DegradationMode.MINIMAL
        else:
            self._mode = DegradationMode.OFFLINE

        if self._mode != old_mode:
            logger.warning(f"Degradation mode changed: {old_mode.value} -> {self._mode.value}")

    async def run_health_checks(self) -> None:
        """Run health checks for all registered services."""
        for service in self._services.values():
            try:
                is_healthy = await service.health_check()
                await self.update_service_health(service.name, is_healthy=is_healthy)
            except Exception as e:
                logger.error(f"Health check failed for '{service.name}': {e}")
                await self.update_service_health(
                    service.name,
                    is_healthy=False,
                    error_message=str(e),
                )

    def should_queue_job(self, job_type: str) -> bool:
        """Determine if a job should be queued instead of processed.

        Args:
            job_type: Type of job (e.g., "detection", "analysis")

        Returns:
            True if job should be queued for later
        """
        # job_type can be used for fine-grained control in future
        _ = job_type  # Reserved for future per-job-type degradation rules
        if self._mode == DegradationMode.NORMAL:
            return False
        if self._mode == DegradationMode.OFFLINE:
            return True
        if self._mode == DegradationMode.MINIMAL:
            return True
        # In DEGRADED mode, queue based on job type and service availability
        return self._mode == DegradationMode.DEGRADED

    async def queue_job_for_later(
        self,
        job_type: str,
        data: dict[str, Any],
    ) -> bool:
        """Queue a job for later processing.

        Args:
            job_type: Type of job
            data: Job data payload

        Returns:
            True if job was queued successfully
        """
        job = QueuedJob(
            job_type=job_type,
            data=data,
            queued_at=datetime.now(UTC).isoformat(),
            retry_count=0,
        )

        # Try Redis first
        if self._redis and self._redis_healthy:
            try:
                await self._redis.add_to_queue(self.DEGRADED_QUEUE, job.to_dict())
                logger.debug(f"Queued {job_type} job to Redis")
                return True
            except Exception as e:
                logger.warning(f"Failed to queue to Redis, using memory: {e}")
                self._redis_healthy = False

        # Fall back to in-memory queue
        return self._queue_to_memory(job)

    def _queue_to_memory(self, job: QueuedJob) -> bool:
        """Queue job to in-memory fallback queue.

        Args:
            job: Job to queue

        Returns:
            True if queued successfully
        """
        try:
            self._memory_queue.append(job)
            logger.debug(f"Queued {job.job_type} job to memory (size={len(self._memory_queue)})")
            return True
        except Exception as e:
            logger.error(f"Failed to queue to memory: {e}")
            return False

    def _use_memory_queue(self) -> bool:
        """Check if we should use in-memory queue."""
        return self._redis is None or not self._redis_healthy

    def get_queued_job_count(self) -> int:
        """Get count of jobs in memory queue.

        Returns:
            Number of jobs in memory queue
        """
        return len(self._memory_queue)

    async def get_pending_job_count(self) -> int:
        """Get total count of pending jobs.

        Returns:
            Total pending jobs (Redis + memory)
        """
        memory_count = len(self._memory_queue)

        if self._redis and self._redis_healthy:
            try:
                redis_count: int = await self._redis.get_queue_length(self.DEGRADED_QUEUE)
                return redis_count + memory_count
            except Exception as e:
                logger.warning(f"Failed to get Redis queue length: {e}")

        return memory_count

    async def process_queued_jobs(
        self,
        job_type: str,
        processor: Callable[[dict[str, Any]], Any],
        max_jobs: int = 100,
    ) -> int:
        """Process queued jobs of a specific type.

        Args:
            job_type: Type of jobs to process
            processor: Async callable to process each job
            max_jobs: Maximum jobs to process in one batch

        Returns:
            Number of jobs processed
        """
        processed = 0

        # Process from Redis queue
        if self._redis and self._redis_healthy:
            while processed < max_jobs:
                try:
                    job_data = await self._redis.get_from_queue(
                        self.DEGRADED_QUEUE,
                        timeout=0,
                    )
                    if job_data is None:
                        break

                    job = QueuedJob.from_dict(job_data)
                    if job.job_type == job_type:
                        try:
                            await processor(job.data)
                            processed += 1
                            logger.debug(f"Processed queued {job_type} job")
                        except Exception as e:
                            logger.error(f"Failed to process queued job: {e}")
                            # Re-queue with incremented retry count
                            job.retry_count += 1
                            await self._redis.add_to_queue(
                                self.DEGRADED_QUEUE,
                                job.to_dict(),
                            )
                except Exception as e:
                    logger.error(f"Error processing Redis queue: {e}")
                    break

        # Process from memory queue
        memory_jobs = list(self._memory_queue)
        self._memory_queue.clear()

        for job in memory_jobs:
            if job.job_type == job_type and processed < max_jobs:
                try:
                    await processor(job.data)
                    processed += 1
                except Exception as e:
                    logger.error(f"Failed to process memory queued job: {e}")
                    job.retry_count += 1
                    self._memory_queue.append(job)
            else:
                # Keep jobs that don't match type
                self._memory_queue.append(job)

        return processed

    async def check_redis_health(self) -> bool:
        """Check if Redis is healthy.

        Returns:
            True if Redis is healthy
        """
        if self._redis is None:
            return False

        try:
            await self._redis.ping()
            if not self._redis_healthy:
                logger.info("Redis connection restored")
                self._redis_healthy = True
            return True
        except Exception as e:
            if self._redis_healthy:
                logger.warning(f"Redis health check failed: {e}")
                self._redis_healthy = False
            return False

    async def handle_redis_unavailable(self) -> None:
        """Handle Redis becoming unavailable."""
        self._redis_healthy = False
        logger.warning(
            "Redis unavailable, falling back to in-memory queue "
            f"(max_size={self.max_memory_queue_size})"
        )

    async def drain_memory_queue_to_redis(self) -> int:
        """Drain in-memory queue to Redis when available.

        Returns:
            Number of jobs drained
        """
        if not self._redis or not self._redis_healthy:
            return 0

        drained = 0
        while self._memory_queue:
            job = self._memory_queue.popleft()
            try:
                await self._redis.add_to_queue(self.DEGRADED_QUEUE, job.to_dict())
                drained += 1
            except Exception as e:
                logger.error(f"Failed to drain job to Redis: {e}")
                self._memory_queue.appendleft(job)
                break

        if drained > 0:
            logger.info(f"Drained {drained} jobs from memory to Redis")

        return drained

    def is_accepting_jobs(self) -> bool:
        """Check if manager is accepting new jobs.

        Returns:
            True if jobs can be accepted (even for queueing)
        """
        return self._mode != DegradationMode.OFFLINE

    def get_available_features(self) -> list[str]:
        """Get list of available features based on current mode.

        Returns:
            List of available feature names
        """
        all_features = ["detection", "analysis", "events", "media"]

        if self._mode == DegradationMode.NORMAL:
            return all_features
        elif self._mode == DegradationMode.DEGRADED:
            return ["events", "media"]  # Read-only features
        elif self._mode == DegradationMode.MINIMAL:
            return ["media"]  # Basic media serving only
        else:
            return []

    def list_services(self) -> list[str]:
        """List all registered service names.

        Returns:
            List of service names
        """
        return list(self._services.keys())

    def get_status(self) -> dict[str, Any]:
        """Get overall degradation status.

        Returns:
            Status dictionary
        """
        return {
            "mode": self._mode.value,
            "is_degraded": self.is_degraded,
            "redis_healthy": self._redis_healthy,
            "memory_queue_size": len(self._memory_queue),
            "services": {
                name: service.health.to_dict() for name, service in self._services.items()
            },
            "available_features": self.get_available_features(),
        }


# Global manager instance
_manager: DegradationManager | None = None


def get_degradation_manager(
    redis_client: Any | None = None,
) -> DegradationManager:
    """Get or create the global degradation manager.

    Args:
        redis_client: Redis client (used on first call)

    Returns:
        DegradationManager instance
    """
    global _manager  # noqa: PLW0603

    if _manager is None:
        _manager = DegradationManager(redis_client=redis_client)
    elif redis_client is not None and _manager._redis is None:
        _manager._redis = redis_client

    return _manager


def reset_degradation_manager() -> None:
    """Reset the global degradation manager (for testing)."""
    global _manager  # noqa: PLW0603
    _manager = None
