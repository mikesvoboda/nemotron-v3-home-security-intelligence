"""Graceful degradation manager for system resilience.

This module provides graceful degradation capabilities for the home security
system. When dependent services become unavailable, the system continues
operating in a degraded mode rather than failing completely.

Features:
    - Track service health states (Redis, RT-DETRv2, Nemotron)
    - Fallback to disk-based queues when Redis is down
    - In-memory queue fallback when Redis unavailable
    - Automatic recovery detection
    - Integration with circuit breakers
    - Job queueing for later processing

Degradation Modes:
    - NORMAL: All services healthy, full functionality
    - DEGRADED: Some services unavailable, using fallbacks
    - MINIMAL: Critical services down, basic functionality only
    - OFFLINE: All services down, queueing only

Usage:
    manager = get_degradation_manager()

    # Register services for monitoring
    manager.register_service(
        name="ai_detector",
        health_check=detector.health_check,
        critical=True,
    )

    # Queue with automatic fallback
    await manager.queue_with_fallback("detection_queue", item)

    # Check if service is available
    if manager.is_service_healthy("rtdetr"):
        # Proceed with AI analysis
        pass

    # Drain fallback queue when recovered
    await manager.drain_fallback_queue("detection_queue")
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from backend.core.logging import get_logger
from backend.core.redis import QueueOverflowPolicy

logger = get_logger(__name__)

T = TypeVar("T")

# Default timeout for health checks in seconds
DEFAULT_HEALTH_CHECK_TIMEOUT = 10.0


class DegradationMode(Enum):
    """System degradation modes."""

    NORMAL = "normal"
    DEGRADED = "degraded"
    MINIMAL = "minimal"
    OFFLINE = "offline"


class DegradationServiceStatus(Enum):
    """Service health status for degradation manager monitoring."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class ServiceHealth:
    """Health information for a monitored service.

    Attributes:
        name: Service name
        status: Current health status
        last_check: Timestamp of last health check (monotonic time)
        last_success: Timestamp of last successful check
        consecutive_failures: Count of consecutive failed checks
        error_message: Last error message if unhealthy
    """

    name: str
    status: DegradationServiceStatus = DegradationServiceStatus.UNKNOWN
    last_check: float | None = None
    last_success: float | None = None
    consecutive_failures: int = 0
    error_message: str | None = None

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self.status == DegradationServiceStatus.HEALTHY

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


@dataclass(slots=True)
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


@dataclass(slots=True)
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


class FallbackQueue:
    """Disk-based fallback queue for when Redis is unavailable.

    Stores queue items as JSON files on disk to prevent data loss
    during Redis outages.
    """

    def __init__(
        self,
        queue_name: str,
        fallback_dir: str,
        max_size: int = 10000,
    ):
        """Initialize fallback queue.

        Args:
            queue_name: Name of the queue (used for directory)
            fallback_dir: Base directory for fallback storage
            max_size: Maximum items to store (oldest dropped when exceeded)
        """
        self._queue_name = queue_name
        self._fallback_dir = Path(fallback_dir) / queue_name
        self._max_size = max_size
        self._counter = 0
        self._lock = asyncio.Lock()

        # Ensure directory exists
        self._fallback_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"FallbackQueue '{queue_name}' initialized",
            extra={
                "queue_name": queue_name,
                "fallback_dir": str(self._fallback_dir),
                "max_size": max_size,
            },
        )

    @property
    def queue_name(self) -> str:
        """Get queue name."""
        return self._queue_name

    @property
    def fallback_dir(self) -> Path:
        """Get fallback directory path."""
        return self._fallback_dir

    def count(self) -> int:
        """Count items in the fallback queue."""
        return len(list(self._fallback_dir.glob("*.json")))

    async def add(self, item: dict[str, Any]) -> bool:
        """Add an item to the fallback queue.

        Args:
            item: Dictionary to store

        Returns:
            True if item was stored successfully
        """
        async with self._lock:
            try:
                # Check size limit
                current_count = self.count()
                if current_count >= self._max_size:
                    # Remove oldest files to make room
                    files = sorted(self._fallback_dir.glob("*.json"))
                    for f in files[: current_count - self._max_size + 1]:
                        f.unlink()
                        logger.warning(
                            f"FallbackQueue '{self._queue_name}' dropped oldest item due to size limit"
                        )

                # Generate unique filename
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
                self._counter += 1
                filename = f"{timestamp}_{self._counter:06d}.json"
                filepath = self._fallback_dir / filename

                # Write item to disk
                with open(filepath, "w") as outfile:
                    json.dump(
                        {
                            "item": item,
                            "queued_at": datetime.now(UTC).isoformat(),
                        },
                        outfile,
                    )

                logger.debug(
                    f"FallbackQueue '{self._queue_name}' added item",
                    extra={"file": filename},
                )
                return True

            except Exception as e:
                logger.error(
                    f"FallbackQueue '{self._queue_name}' failed to add item: {e}",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                return False

    async def get(self) -> dict[str, Any] | None:
        """Get the oldest item from the fallback queue.

        Returns:
            The item dictionary, or None if queue is empty
        """
        async with self._lock:
            try:
                # Get oldest file
                files = sorted(self._fallback_dir.glob("*.json"))
                if not files:
                    return None

                oldest = files[0]

                # Read and delete
                with open(oldest) as infile:
                    data = json.load(infile)

                oldest.unlink()

                logger.debug(
                    f"FallbackQueue '{self._queue_name}' retrieved item",
                    extra={"file": oldest.name},
                )
                result: dict[str, Any] | None = data.get("item")
                return result

            except Exception as e:
                logger.error(
                    f"FallbackQueue '{self._queue_name}' failed to get item: {e}",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                return None

    async def peek(self, limit: int = 10) -> list[dict[str, Any]]:
        """Peek at items without removing them.

        Args:
            limit: Maximum items to return

        Returns:
            List of items (oldest first)
        """
        items = []
        files = sorted(self._fallback_dir.glob("*.json"))[:limit]

        for f in files:
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    items.append(data.get("item", {}))
            except Exception:  # noqa: S110
                # Intentionally ignore corrupted/unreadable files during peek operation.
                # Peek is non-destructive and should not fail if individual files are
                # malformed - we simply skip them and continue with remaining files.
                pass

        return items


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
        fallback_dir: str | None = None,
        failure_threshold: int = 3,
        recovery_threshold: int = 2,
        max_memory_queue_size: int = 1000,
        check_interval: float = 15.0,
        health_check_timeout: float = DEFAULT_HEALTH_CHECK_TIMEOUT,
    ) -> None:
        """Initialize degradation manager.

        Args:
            redis_client: Redis client for job queueing
            fallback_dir: Directory for disk-based fallback queues
            failure_threshold: Failures before marking unhealthy
            recovery_threshold: Successes needed to confirm recovery
            max_memory_queue_size: Max jobs to hold in memory queue
            check_interval: Interval between health checks in seconds
            health_check_timeout: Timeout for individual health checks in seconds
        """
        self._redis = redis_client
        self._mode = DegradationMode.NORMAL
        self._services: dict[str, RegisteredService] = {}
        self._memory_queue: deque[QueuedJob] = deque(maxlen=max_memory_queue_size)
        self._lock = asyncio.Lock()
        self._redis_healthy = True
        self._running = False
        self._task: asyncio.Task[None] | None = None

        # Disk-based fallback
        self._fallback_dir = Path(fallback_dir or Path.home() / ".cache" / "hsi_fallback")
        self._fallback_queues: dict[str, FallbackQueue] = {}
        self._fallback_dir.mkdir(parents=True, exist_ok=True)

        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.max_memory_queue_size = max_memory_queue_size
        self._check_interval = check_interval
        self._health_check_timeout = health_check_timeout

        logger.info(
            f"DegradationManager initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_threshold={recovery_threshold}, "
            f"health_check_timeout={health_check_timeout}s, "
            f"fallback_dir={self._fallback_dir}"
        )

    @property
    def mode(self) -> DegradationMode:
        """Get current degradation mode."""
        return self._mode

    @property
    def is_degraded(self) -> bool:
        """Check if system is in any degraded state."""
        return self._mode != DegradationMode.NORMAL

    @property
    def health_check_timeout(self) -> float:
        """Get the health check timeout in seconds."""
        return self._health_check_timeout

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
        return ServiceHealth(name=name, status=DegradationServiceStatus.UNKNOWN)

    def is_service_healthy(self, name: str) -> bool:
        """Check if a service is healthy.

        Args:
            name: Service name

        Returns:
            True if service is healthy
        """
        if name in self._services:
            return self._services[name].health.is_healthy
        return False

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
                health.status = DegradationServiceStatus.HEALTHY
                health.last_success = time.monotonic()
                health.consecutive_failures = 0
                health.error_message = None
                logger.debug(f"Service '{name}' is healthy")
            else:
                health.status = DegradationServiceStatus.UNHEALTHY
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
        """Run health checks for all registered services.

        Each health check is executed with a timeout to prevent hanging
        indefinitely on unresponsive services.
        """
        for service in self._services.values():
            try:
                # Apply timeout to health check to prevent hanging
                is_healthy = await asyncio.wait_for(
                    service.health_check(),
                    timeout=self._health_check_timeout,
                )
                await self.update_service_health(service.name, is_healthy=is_healthy)
            except TimeoutError:
                logger.error(
                    f"Health check timed out for '{service.name}' "
                    f"after {self._health_check_timeout}s",
                    extra={
                        "service_name": service.name,
                        "timeout": self._health_check_timeout,
                    },
                )
                await self.update_service_health(
                    service.name,
                    is_healthy=False,
                    error_message=f"Health check timed out after {self._health_check_timeout}s",
                )
            except Exception as e:
                logger.error(f"Health check failed for '{service.name}': {e}", exc_info=True)
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
                result = await self._redis.add_to_queue_safe(
                    self.DEGRADED_QUEUE,
                    job.to_dict(),
                    overflow_policy=QueueOverflowPolicy.DLQ,
                )
                if result.success:
                    if result.had_backpressure:
                        logger.warning(
                            f"Queue backpressure while queuing {job_type} job",
                            extra={
                                "queue_name": self.DEGRADED_QUEUE,
                                "queue_length": result.queue_length,
                                "moved_to_dlq": result.moved_to_dlq_count,
                            },
                        )
                    logger.debug(f"Queued {job_type} job to Redis")
                    return True
                else:
                    logger.error(
                        f"Failed to queue {job_type} job to Redis: {result.error}",
                        extra={
                            "queue_name": self.DEGRADED_QUEUE,
                            "queue_length": result.queue_length,
                        },
                    )
            except Exception as e:
                logger.warning(f"Failed to queue to Redis, using memory: {e}", exc_info=True)
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
            queue_size_before = len(self._memory_queue)
            queue_at_capacity = queue_size_before >= self.max_memory_queue_size

            if queue_at_capacity:
                # Log that we're about to drop an item due to overflow
                dropped_job = self._memory_queue[0] if self._memory_queue else None
                logger.warning(
                    f"Memory queue overflow: dropping oldest job "
                    f"to make room for {job.job_type} job "
                    f"(queue_size={queue_size_before}, "
                    f"max_size={self.max_memory_queue_size}). "
                    "DATA LOSS: oldest queued job will be discarded.",
                    extra={
                        "queue_size": queue_size_before,
                        "max_size": self.max_memory_queue_size,
                        "new_job_type": job.job_type,
                        "dropped_job_type": dropped_job.job_type if dropped_job else "unknown",
                        "dropped_job_queued_at": (
                            dropped_job.queued_at if dropped_job else "unknown"
                        ),
                    },
                )

            self._memory_queue.append(job)
            logger.debug(f"Queued {job.job_type} job to memory (size={len(self._memory_queue)})")
            return True
        except Exception as e:
            logger.error(f"Failed to queue to memory: {e}", exc_info=True)
            return False

    def _use_memory_queue(self) -> bool:
        """Check if we should use in-memory queue.

        Returns:
            True if Redis is unavailable and we should use memory queue
        """
        return self._redis is None or not self._redis_healthy

    def _get_fallback_queue(self, queue_name: str) -> FallbackQueue:
        """Get or create a disk-based fallback queue.

        Args:
            queue_name: Name of the queue

        Returns:
            FallbackQueue instance
        """
        if queue_name not in self._fallback_queues:
            self._fallback_queues[queue_name] = FallbackQueue(
                queue_name=queue_name,
                fallback_dir=str(self._fallback_dir),
            )
        return self._fallback_queues[queue_name]

    async def queue_with_fallback(
        self,
        queue_name: str,
        item: dict[str, Any],
    ) -> bool:
        """Queue an item with automatic fallback to disk.

        Attempts to queue to Redis first. If Redis is unavailable,
        falls back to disk-based queue.

        Args:
            queue_name: Name of the queue
            item: Item to queue

        Returns:
            True if item was queued (to either Redis or fallback)
        """
        # Try Redis first if available
        if self._redis_healthy and self._redis is not None:
            try:
                result = await self._redis.add_to_queue_safe(
                    queue_name,
                    item,
                    overflow_policy=QueueOverflowPolicy.DLQ,
                )
                if result.success:
                    if result.had_backpressure:
                        logger.warning(
                            f"Queue backpressure while queuing to {queue_name}",
                            extra={
                                "queue_name": queue_name,
                                "queue_length": result.queue_length,
                                "moved_to_dlq": result.moved_to_dlq_count,
                            },
                        )
                    return True
                else:
                    logger.error(
                        f"Failed to queue to {queue_name}: {result.error}",
                        extra={
                            "queue_name": queue_name,
                            "queue_length": result.queue_length,
                        },
                    )
            except Exception as e:
                logger.warning(
                    f"Redis queue failed, falling back to disk: {e}",
                    extra={"queue_name": queue_name, "error": str(e)},
                    exc_info=True,
                )
                self._redis_healthy = False

        # Fallback to disk
        fallback = self._get_fallback_queue(queue_name)
        return await fallback.add(item)

    async def drain_fallback_queue(self, queue_name: str) -> int:
        """Drain items from fallback queue to Redis.

        Args:
            queue_name: Name of the queue to drain

        Returns:
            Number of items drained
        """
        if self._redis is None:
            logger.warning("Cannot drain fallback queue: Redis client not configured")
            return 0

        fallback = self._get_fallback_queue(queue_name)
        drained = 0

        while True:
            item = await fallback.get()
            if item is None:
                break

            try:
                result = await self._redis.add_to_queue_safe(
                    queue_name,
                    item,
                    overflow_policy=QueueOverflowPolicy.DLQ,
                )
                if result.success:
                    drained += 1
                    if result.had_backpressure:
                        logger.warning(
                            f"Queue backpressure while draining fallback to {queue_name}",
                            extra={
                                "queue_name": queue_name,
                                "queue_length": result.queue_length,
                                "moved_to_dlq": result.moved_to_dlq_count,
                            },
                        )
                else:
                    logger.error(
                        f"Failed to drain item to Redis: {result.error}",
                        extra={
                            "queue_name": queue_name,
                            "queue_length": result.queue_length,
                        },
                    )
                    # Put item back
                    await fallback.add(item)
                    break
            except Exception as e:
                logger.error(
                    f"Failed to drain item to Redis, stopping: {e}",
                    extra={"queue_name": queue_name, "error": str(e)},
                    exc_info=True,
                )
                # Put item back
                await fallback.add(item)
                break

        logger.info(
            f"Drained {drained} items from fallback queue '{queue_name}'",
            extra={"queue_name": queue_name, "drained": drained},
        )
        return drained

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
                logger.warning(f"Failed to get Redis queue length: {e}", exc_info=True)

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
                            logger.error(f"Failed to process queued job: {e}", exc_info=True)
                            # Re-queue with incremented retry count
                            job.retry_count += 1
                            result = await self._redis.add_to_queue_safe(
                                self.DEGRADED_QUEUE,
                                job.to_dict(),
                                overflow_policy=QueueOverflowPolicy.DLQ,
                            )
                            if not result.success:
                                logger.error(
                                    f"CRITICAL: Failed to re-queue job: {result.error}",
                                    extra={
                                        "queue_name": self.DEGRADED_QUEUE,
                                        "queue_length": result.queue_length,
                                    },
                                )
                except Exception as e:
                    logger.error(f"Error processing Redis queue: {e}", exc_info=True)
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
                    logger.error(f"Failed to process memory queued job: {e}", exc_info=True)
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
                logger.warning(f"Redis health check failed: {e}", exc_info=True)
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
                result = await self._redis.add_to_queue_safe(
                    self.DEGRADED_QUEUE,
                    job.to_dict(),
                    overflow_policy=QueueOverflowPolicy.DLQ,
                )
                if result.success:
                    drained += 1
                    if result.had_backpressure:
                        logger.warning(
                            "Queue backpressure while draining memory to Redis",
                            extra={
                                "queue_name": self.DEGRADED_QUEUE,
                                "queue_length": result.queue_length,
                                "moved_to_dlq": result.moved_to_dlq_count,
                            },
                        )
                else:
                    logger.error(
                        f"Failed to drain job to Redis: {result.error}",
                        extra={
                            "queue_name": self.DEGRADED_QUEUE,
                            "queue_length": result.queue_length,
                        },
                    )
                    self._memory_queue.appendleft(job)
                    break
            except Exception as e:
                logger.error(f"Failed to drain job to Redis: {e}", exc_info=True)
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

    async def start(self) -> None:
        """Start the health check loop."""
        if self._running:
            logger.warning("DegradationManager already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._health_check_loop())
        logger.info("DegradationManager started")

    async def stop(self) -> None:
        """Stop the health check loop."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass  # Expected when stop() cancels the task; no action needed
            self._task = None

        logger.info("DegradationManager stopped")

    async def _health_check_loop(self) -> None:
        """Main health check loop."""
        while self._running:
            try:
                # Run health checks for all registered services
                await self.run_health_checks()

                # Check Redis health
                await self.check_redis_health()

                # Drain memory queue to Redis if available
                if self._redis_healthy:
                    await self.drain_memory_queue_to_redis()

                await asyncio.sleep(self._check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"Health check loop error: {e}",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                await asyncio.sleep(self._check_interval)

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
            "fallback_queues": {
                name: queue.count() for name, queue in self._fallback_queues.items()
            },
            "services": {
                name: service.health.to_dict() for name, service in self._services.items()
            },
            "available_features": self.get_available_features(),
            "health_check_timeout": self._health_check_timeout,
        }


# Global manager instance
_manager: DegradationManager | None = None


def get_degradation_manager(
    redis_client: Any | None = None,
    fallback_dir: str | None = None,
) -> DegradationManager:
    """Get or create the global degradation manager.

    Args:
        redis_client: Redis client (used on first call)
        fallback_dir: Directory for fallback queues

    Returns:
        DegradationManager instance
    """
    global _manager  # noqa: PLW0603

    if _manager is None:
        _manager = DegradationManager(
            redis_client=redis_client,
            fallback_dir=fallback_dir,
        )
    elif redis_client is not None and _manager._redis is None:
        _manager._redis = redis_client

    return _manager


def reset_degradation_manager() -> None:
    """Reset the global degradation manager (for testing)."""
    global _manager  # noqa: PLW0603
    _manager = None
