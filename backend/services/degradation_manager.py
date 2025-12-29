"""Graceful degradation manager for system resilience.

This module provides graceful degradation capabilities for the home security
system. When dependent services become unavailable, the system continues
operating in a degraded mode rather than failing completely.

Features:
    - Track service health states (Redis, RT-DETRv2, Nemotron)
    - Fallback to disk-based queues when Redis is down
    - Automatic recovery detection
    - Integration with circuit breakers
    - Exponential backoff for reconnection attempts

Degradation Modes:
    - NORMAL: All services healthy, full functionality
    - DEGRADED: Some services unavailable, using fallbacks
    - MAINTENANCE: Planned downtime, minimal operations

Usage:
    manager = get_degradation_manager()

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
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

from backend.core.logging import get_logger
from backend.services.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)


class DegradationMode(Enum):
    """System degradation mode."""

    NORMAL = "normal"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"


class ServiceStatus(Enum):
    """Health status of a service."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceState:
    """Current state of a monitored service.

    Attributes:
        name: Service identifier
        status: Current health status
        last_check: Timestamp of last health check
        consecutive_failures: Number of consecutive failed checks
        last_error: Most recent error message
    """

    name: str
    status: ServiceStatus
    last_check: datetime | None = None
    consecutive_failures: int = 0
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
        }


@dataclass
class ServiceDependency:
    """Configuration for a service dependency.

    Attributes:
        name: Service identifier
        health_check_url: URL for health check endpoint
        required: Whether service is required for normal operation
        timeout: Health check timeout in seconds
    """

    name: str
    health_check_url: str
    required: bool = True
    timeout: float = 5.0


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
                pass

        return items


class DegradationManager:
    """Manages graceful degradation for the security system.

    Tracks service health, provides fallback behaviors, and manages
    recovery when services become available again.
    """

    def __init__(
        self,
        fallback_dir: str | None = None,
        redis_client: Any = None,
        check_interval: float = 15.0,
    ):
        """Initialize degradation manager.

        Args:
            fallback_dir: Directory for fallback queues
            redis_client: Redis client instance
            check_interval: Interval between health checks in seconds
        """
        self._mode = DegradationMode.NORMAL
        self._fallback_dir = Path(fallback_dir or Path.home() / ".cache" / "hsi_fallback")
        self._redis_client = redis_client
        self._check_interval = check_interval

        self._service_states: dict[str, ServiceState] = {}
        self._dependencies: dict[str, ServiceDependency] = {}
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._fallback_queues: dict[str, FallbackQueue] = {}
        self._degradation_reason: str | None = None
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

        # Ensure fallback directory exists
        self._fallback_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "DegradationManager initialized",
            extra={
                "fallback_dir": str(self._fallback_dir),
                "check_interval": check_interval,
            },
        )

    @property
    def mode(self) -> DegradationMode:
        """Get current degradation mode."""
        return self._mode

    @property
    def service_states(self) -> dict[str, ServiceState]:
        """Get all service states."""
        return self._service_states.copy()

    def register_dependency(self, dependency: ServiceDependency) -> None:
        """Register a service dependency.

        Args:
            dependency: Service dependency configuration
        """
        self._dependencies[dependency.name] = dependency
        self._service_states[dependency.name] = ServiceState(
            name=dependency.name,
            status=ServiceStatus.UNKNOWN,
        )
        logger.info(
            f"Registered dependency: {dependency.name}",
            extra={
                "service": dependency.name,
                "required": dependency.required,
            },
        )

    def register_circuit_breaker(self, circuit_breaker: CircuitBreaker) -> None:
        """Register a circuit breaker for monitoring.

        Args:
            circuit_breaker: CircuitBreaker instance
        """
        self._circuit_breakers[circuit_breaker.name] = circuit_breaker
        logger.info(
            f"Registered circuit breaker: {circuit_breaker.name}",
            extra={"circuit_breaker": circuit_breaker.name},
        )

    def _get_fallback_queue(self, queue_name: str) -> FallbackQueue:
        """Get or create a fallback queue.

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

    async def enter_degraded_mode(self, reason: str) -> None:
        """Enter degraded mode.

        Args:
            reason: Description of why degraded mode is needed
        """
        async with self._lock:
            if self._mode == DegradationMode.MAINTENANCE:
                logger.info("Cannot enter degraded mode during maintenance")
                return

            old_mode = self._mode
            self._mode = DegradationMode.DEGRADED
            self._degradation_reason = reason

            logger.warning(
                f"Entering degraded mode: {reason}",
                extra={
                    "old_mode": old_mode.value,
                    "new_mode": self._mode.value,
                    "reason": reason,
                },
            )

    async def enter_normal_mode(self) -> None:
        """Return to normal mode."""
        async with self._lock:
            if self._mode == DegradationMode.MAINTENANCE:
                logger.info("Cannot enter normal mode during maintenance")
                return

            old_mode = self._mode
            self._mode = DegradationMode.NORMAL
            self._degradation_reason = None

            logger.info(
                "Returning to normal mode",
                extra={
                    "old_mode": old_mode.value,
                    "new_mode": self._mode.value,
                },
            )

    async def enter_maintenance_mode(self, reason: str) -> None:
        """Enter maintenance mode.

        Args:
            reason: Description of maintenance activity
        """
        async with self._lock:
            old_mode = self._mode
            self._mode = DegradationMode.MAINTENANCE
            self._degradation_reason = reason

            logger.warning(
                f"Entering maintenance mode: {reason}",
                extra={
                    "old_mode": old_mode.value,
                    "new_mode": self._mode.value,
                    "reason": reason,
                },
            )

    async def exit_maintenance_mode(self) -> None:
        """Exit maintenance mode and return to normal."""
        async with self._lock:
            old_mode = self._mode
            self._mode = DegradationMode.NORMAL
            self._degradation_reason = None

            logger.info(
                "Exiting maintenance mode",
                extra={
                    "old_mode": old_mode.value,
                    "new_mode": self._mode.value,
                },
            )

    async def update_service_state(
        self,
        name: str,
        status: ServiceStatus,
        error: str | None = None,
    ) -> None:
        """Update the state of a service.

        Args:
            name: Service name
            status: New health status
            error: Error message if unhealthy
        """
        async with self._lock:
            if name not in self._service_states:
                self._service_states[name] = ServiceState(
                    name=name,
                    status=status,
                )

            state = self._service_states[name]
            old_status = state.status
            state.status = status
            state.last_check = datetime.now(UTC)

            if status == ServiceStatus.HEALTHY:
                state.consecutive_failures = 0
                state.last_error = None
            else:
                state.consecutive_failures += 1
                state.last_error = error

            if old_status != status:
                logger.info(
                    f"Service '{name}' status changed: {old_status.value} -> {status.value}",
                    extra={
                        "service": name,
                        "old_status": old_status.value,
                        "new_status": status.value,
                        "error": error,
                    },
                )

    def get_service_state(self, name: str) -> ServiceState | None:
        """Get the state of a service.

        Args:
            name: Service name

        Returns:
            ServiceState or None if not found
        """
        return self._service_states.get(name)

    def is_service_healthy(self, name: str) -> bool:
        """Check if a service is healthy.

        Args:
            name: Service name

        Returns:
            True if service is healthy
        """
        state = self._service_states.get(name)
        return state is not None and state.status == ServiceStatus.HEALTHY

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
        # Check if Redis is healthy
        redis_state = self._service_states.get("redis")
        redis_healthy = redis_state is not None and redis_state.status == ServiceStatus.HEALTHY

        # Try Redis first if available
        if redis_healthy and self._redis_client is not None:
            try:
                await self._redis_client.add_to_queue(queue_name, item)
                return True
            except Exception as e:
                logger.warning(
                    f"Redis queue failed, falling back to disk: {e}",
                    extra={"queue_name": queue_name, "error": str(e)},
                )
                # Update Redis state
                await self.update_service_state(
                    "redis",
                    ServiceStatus.UNHEALTHY,
                    str(e),
                )

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
        if self._redis_client is None:
            logger.warning("Cannot drain fallback queue: Redis client not configured")
            return 0

        fallback = self._get_fallback_queue(queue_name)
        drained = 0

        while True:
            item = await fallback.get()
            if item is None:
                break

            try:
                await self._redis_client.add_to_queue(queue_name, item)
                drained += 1
            except Exception as e:
                logger.error(
                    f"Failed to drain item to Redis, stopping: {e}",
                    extra={"queue_name": queue_name, "error": str(e)},
                )
                # Put item back
                await fallback.add(item)
                break

        logger.info(
            f"Drained {drained} items from fallback queue '{queue_name}'",
            extra={"queue_name": queue_name, "drained": drained},
        )
        return drained

    async def check_recovery(self) -> None:
        """Check if system can recover to normal mode.

        Examines all required dependencies and transitions to normal
        mode if all are healthy.
        """
        if self._mode == DegradationMode.MAINTENANCE:
            return

        # Check all required dependencies
        all_healthy = True
        for name, dep in self._dependencies.items():
            if dep.required:
                state = self._service_states.get(name)
                if state is None or state.status != ServiceStatus.HEALTHY:
                    all_healthy = False
                    break

        if all_healthy and self._mode == DegradationMode.DEGRADED:
            await self.enter_normal_mode()

            # Drain fallback queues
            for queue_name in self._fallback_queues:
                await self.drain_fallback_queue(queue_name)

    async def on_circuit_opened(self, name: str) -> None:
        """Handle circuit breaker opening.

        Args:
            name: Name of the circuit breaker that opened
        """
        logger.warning(
            f"Circuit breaker '{name}' opened",
            extra={"circuit_breaker": name},
        )

        # Mark service as unhealthy
        await self.update_service_state(name, ServiceStatus.UNHEALTHY)

        # Enter degraded mode if this is a required service
        dep = self._dependencies.get(name)
        if dep is not None and dep.required:
            await self.enter_degraded_mode(f"Circuit breaker '{name}' opened")

    async def on_circuit_closed(self, name: str) -> None:
        """Handle circuit breaker closing.

        Args:
            name: Name of the circuit breaker that closed
        """
        logger.info(
            f"Circuit breaker '{name}' closed",
            extra={"circuit_breaker": name},
        )

        # Mark service as healthy
        await self.update_service_state(name, ServiceStatus.HEALTHY)

        # Check if we can recover
        await self.check_recovery()

    async def _check_dependency(self, dep: ServiceDependency) -> None:
        """Check health of a single dependency.

        Args:
            dep: Service dependency to check
        """
        try:
            async with httpx.AsyncClient(timeout=dep.timeout) as client:
                response = await client.get(dep.health_check_url)
                response.raise_for_status()

            await self.update_service_state(dep.name, ServiceStatus.HEALTHY)

        except Exception as e:
            await self.update_service_state(
                dep.name,
                ServiceStatus.UNHEALTHY,
                str(e),
            )

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
                pass
            self._task = None

        logger.info("DegradationManager stopped")

    async def _health_check_loop(self) -> None:
        """Main health check loop."""
        while self._running:
            try:
                # Check all dependencies
                for dep in self._dependencies.values():
                    await self._check_dependency(dep)

                # Check Redis if configured
                if self._redis_client is not None:
                    try:
                        health = await self._redis_client.health_check()
                        if health.get("status") == "healthy":
                            await self.update_service_state("redis", ServiceStatus.HEALTHY)
                        else:
                            await self.update_service_state(
                                "redis",
                                ServiceStatus.UNHEALTHY,
                                health.get("error"),
                            )
                    except Exception as e:
                        await self.update_service_state(
                            "redis",
                            ServiceStatus.UNHEALTHY,
                            str(e),
                        )

                # Check for recovery
                await self.check_recovery()

                await asyncio.sleep(self._check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"Health check loop error: {e}",
                    extra={"error": str(e)},
                )
                await asyncio.sleep(self._check_interval)

    def get_status(self) -> dict[str, Any]:
        """Get current system status.

        Returns:
            Dictionary with mode and service states
        """
        return {
            "mode": self._mode.value,
            "degradation_reason": self._degradation_reason,
            "services": {name: state.to_dict() for name, state in self._service_states.items()},
            "fallback_queues": {
                name: queue.count() for name, queue in self._fallback_queues.items()
            },
        }


# Global degradation manager instance
_degradation_manager: DegradationManager | None = None


def get_degradation_manager(
    fallback_dir: str | None = None,
    redis_client: Any = None,
) -> DegradationManager:
    """Get or create the global degradation manager.

    Args:
        fallback_dir: Directory for fallback queues
        redis_client: Redis client instance

    Returns:
        DegradationManager instance
    """
    global _degradation_manager  # noqa: PLW0603

    if _degradation_manager is None:
        _degradation_manager = DegradationManager(
            fallback_dir=fallback_dir,
            redis_client=redis_client,
        )
    elif redis_client is not None and _degradation_manager._redis_client is None:
        _degradation_manager._redis_client = redis_client

    return _degradation_manager


def reset_degradation_manager() -> None:
    """Reset the global degradation manager (for testing)."""
    global _degradation_manager  # noqa: PLW0603
    _degradation_manager = None
