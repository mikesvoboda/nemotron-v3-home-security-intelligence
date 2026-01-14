"""Worker Supervisor for auto-recovery of crashed asyncio worker tasks.

This module provides the WorkerSupervisor class that monitors registered asyncio
workers and automatically restarts them if they crash.

Features:
    - Monitor asyncio worker tasks for crashes
    - Implement automatic restart with exponential backoff
    - Track worker health status (RUNNING, STOPPED, CRASHED, RESTARTING, FAILED)
    - Provide interface for registering/unregistering workers
    - Broadcast status changes via WebSocket (service_status events)
    - Configurable max restart limit to prevent restart storms
    - Thread-safe restart handling with asyncio locks

Usage:
    from backend.services.worker_supervisor import (
        WorkerSupervisor,
        WorkerStatus,
        get_worker_supervisor,
    )

    supervisor = get_worker_supervisor()

    # Register a worker
    async def my_worker():
        while True:
            await process_something()

    await supervisor.register_worker("my_worker", my_worker)

    # Start monitoring
    await supervisor.start()

    # Get worker status
    status = supervisor.get_worker_status("my_worker")
    if status == WorkerStatus.CRASHED:
        logger.warning("Worker crashed!")
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from backend.core.logging import get_logger
from backend.core.metrics import (
    record_worker_crash,
    record_worker_max_restarts_exceeded,
    record_worker_restart,
    set_worker_status,
)

if TYPE_CHECKING:
    from backend.services.event_broadcaster import EventBroadcaster

logger = get_logger(__name__)


class WorkerStatus(Enum):
    """Health status of a monitored worker."""

    RUNNING = "running"
    STOPPED = "stopped"
    CRASHED = "crashed"
    RESTARTING = "restarting"
    FAILED = "failed"


@dataclass
class WorkerInfo:
    """Information about a registered worker.

    Attributes:
        name: Unique identifier for the worker.
        factory: Async callable that creates and runs the worker.
        task: The current asyncio.Task running the worker.
        status: Current health status of the worker.
        restart_count: Number of times the worker has been restarted.
        max_restarts: Maximum number of restart attempts before giving up.
        backoff_base: Base backoff time in seconds for restarts.
        backoff_max: Maximum backoff time in seconds.
        last_started_at: When the worker was last started.
        last_crashed_at: When the worker last crashed.
        error: Last error message if crashed.
    """

    name: str
    factory: Callable[[], Awaitable[None]]
    task: asyncio.Task[None] | None = None
    status: WorkerStatus = WorkerStatus.STOPPED
    restart_count: int = 0
    max_restarts: int = 5
    backoff_base: float = 1.0
    backoff_max: float = 60.0
    last_started_at: datetime | None = None
    last_crashed_at: datetime | None = None
    error: str | None = None


@dataclass
class SupervisorConfig:
    """Configuration for the WorkerSupervisor.

    Attributes:
        check_interval: Seconds between health checks.
        default_max_restarts: Default max restarts for workers.
        default_backoff_base: Default base backoff time.
        default_backoff_max: Default max backoff time.
    """

    check_interval: float = 5.0
    default_max_restarts: int = 5
    default_backoff_base: float = 1.0
    default_backoff_max: float = 60.0


class WorkerSupervisor:
    """Supervises asyncio workers and auto-restarts them on crashes.

    This supervisor monitors registered worker tasks and automatically
    restarts them with exponential backoff when they fail.
    """

    def __init__(
        self,
        config: SupervisorConfig | None = None,
        broadcaster: EventBroadcaster | None = None,
    ) -> None:
        """Initialize the WorkerSupervisor.

        Args:
            config: Supervisor configuration. Uses defaults if not provided.
            broadcaster: Optional EventBroadcaster for status updates.
        """
        self._config = config or SupervisorConfig()
        self._broadcaster = broadcaster
        self._workers: dict[str, WorkerInfo] = {}
        self._running = False
        self._monitor_task: asyncio.Task[None] | None = None
        self._restart_locks: dict[str, asyncio.Lock] = {}

        logger.info(f"WorkerSupervisor initialized: check_interval={self._config.check_interval}s")

    async def register_worker(
        self,
        name: str,
        factory: Callable[[], Awaitable[None]],
        max_restarts: int | None = None,
        backoff_base: float | None = None,
        backoff_max: float | None = None,
    ) -> None:
        """Register a worker to be supervised.

        Args:
            name: Unique identifier for the worker.
            factory: Async callable that runs the worker logic.
            max_restarts: Max restart attempts (uses config default if None).
            backoff_base: Base backoff time (uses config default if None).
            backoff_max: Max backoff time (uses config default if None).

        Raises:
            ValueError: If a worker with this name is already registered.
        """
        if name in self._workers:
            raise ValueError(f"Worker '{name}' is already registered")

        worker = WorkerInfo(
            name=name,
            factory=factory,
            max_restarts=max_restarts or self._config.default_max_restarts,
            backoff_base=backoff_base or self._config.default_backoff_base,
            backoff_max=backoff_max or self._config.default_backoff_max,
        )

        self._workers[name] = worker
        self._restart_locks[name] = asyncio.Lock()

        logger.info(
            f"Registered worker '{name}': max_restarts={worker.max_restarts}, "
            f"backoff_base={worker.backoff_base}s"
        )

    async def unregister_worker(self, name: str) -> None:
        """Unregister and stop a worker.

        Args:
            name: Name of the worker to unregister.
        """
        if name not in self._workers:
            logger.warning(f"Cannot unregister unknown worker: {name}")
            return

        worker = self._workers[name]

        # Stop the worker task if running
        if worker.task is not None and not worker.task.done():
            worker.task.cancel()
            try:
                await worker.task
            except asyncio.CancelledError:
                pass

        del self._workers[name]
        del self._restart_locks[name]

        logger.info(f"Unregistered worker '{name}'")

    async def start(self) -> None:
        """Start the supervisor and all registered workers.

        Starts all registered workers and begins monitoring them.
        """
        if self._running:
            logger.warning("WorkerSupervisor already running")
            return

        logger.info("Starting WorkerSupervisor")
        self._running = True

        # Start all workers
        for name in self._workers:
            await self._start_worker(name)

        # Start monitor loop
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info("WorkerSupervisor started")

    async def stop(self) -> None:
        """Stop the supervisor and all workers gracefully."""
        if not self._running:
            logger.debug("WorkerSupervisor not running")
            return

        logger.info("Stopping WorkerSupervisor")
        self._running = False

        # Stop monitor task
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

        # Stop all workers
        for worker_name, worker in self._workers.items():
            if worker.task is not None and not worker.task.done():
                worker.task.cancel()
                try:
                    await worker.task
                except asyncio.CancelledError:
                    pass
            worker.status = WorkerStatus.STOPPED
            worker.task = None

            # Record stopped status metric
            set_worker_status(worker_name, WorkerStatus.STOPPED.value)

        logger.info("WorkerSupervisor stopped")

    async def _start_worker(self, name: str) -> None:
        """Start a single worker.

        Args:
            name: Name of the worker to start.
        """
        if name not in self._workers:
            logger.warning(f"Cannot start unknown worker: {name}")
            return

        worker = self._workers[name]

        # Don't start if already running
        if worker.task is not None and not worker.task.done():
            logger.debug(f"Worker '{name}' already running")
            return

        # Create and start the task
        worker.task = asyncio.create_task(
            self._run_worker(name),
            name=f"worker-{name}",
        )
        worker.status = WorkerStatus.RUNNING
        worker.last_started_at = datetime.now(UTC)
        worker.error = None

        # Record metrics
        set_worker_status(name, WorkerStatus.RUNNING.value)

        await self._broadcast_status(name, WorkerStatus.RUNNING)
        logger.info(f"Started worker '{name}'")

    async def _run_worker(self, name: str) -> None:
        """Run a worker and catch any exceptions.

        Args:
            name: Name of the worker to run.
        """
        worker = self._workers[name]

        try:
            await worker.factory()
        except asyncio.CancelledError:
            # Normal cancellation, not a crash
            raise
        except Exception as e:
            # Worker crashed
            worker.status = WorkerStatus.CRASHED
            worker.last_crashed_at = datetime.now(UTC)
            worker.error = str(e)

            # Record metrics
            record_worker_crash(name)
            set_worker_status(name, WorkerStatus.CRASHED.value)

            logger.error(f"Worker '{name}' crashed: {e}", exc_info=True)
            await self._broadcast_status(name, WorkerStatus.CRASHED, str(e))

    async def _monitor_loop(self) -> None:
        """Main loop that monitors workers and restarts crashed ones."""
        logger.info("Monitor loop started")

        while self._running:
            try:
                for name, worker in list(self._workers.items()):
                    if not self._running:
                        break

                    # Check if worker needs restart
                    if worker.status == WorkerStatus.CRASHED:
                        await self._handle_crashed_worker(name)

                await asyncio.sleep(self._config.check_interval)

            except asyncio.CancelledError:
                logger.info("Monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self._config.check_interval)

        logger.info("Monitor loop stopped")

    async def _handle_crashed_worker(self, name: str) -> None:
        """Handle a crashed worker by attempting restart.

        Args:
            name: Name of the crashed worker.
        """
        async with self._restart_locks[name]:
            worker = self._workers[name]

            # Check if we've exceeded max restarts
            if worker.restart_count >= worker.max_restarts:
                if worker.status != WorkerStatus.FAILED:
                    worker.status = WorkerStatus.FAILED

                    # Record metrics
                    record_worker_max_restarts_exceeded(name)
                    set_worker_status(name, WorkerStatus.FAILED.value)

                    logger.error(
                        f"Worker '{name}' exceeded max restarts ({worker.max_restarts}), giving up"
                    )
                    await self._broadcast_status(
                        name,
                        WorkerStatus.FAILED,
                        f"Exceeded max restarts ({worker.max_restarts})",
                    )
                return

            # Calculate backoff
            backoff = self._calculate_backoff(worker)
            worker.status = WorkerStatus.RESTARTING

            # Record restarting status metric
            set_worker_status(name, WorkerStatus.RESTARTING.value)

            logger.info(
                f"Restarting worker '{name}' in {backoff:.1f}s "
                f"(attempt {worker.restart_count + 1}/{worker.max_restarts})"
            )
            await self._broadcast_status(name, WorkerStatus.RESTARTING)

            # Wait for backoff
            await asyncio.sleep(backoff)

            if not self._running:
                return

            # Increment restart count and start
            worker.restart_count += 1

            # Record restart metric
            record_worker_restart(name)

            await self._start_worker(name)

    def _calculate_backoff(self, worker: WorkerInfo) -> float:
        """Calculate exponential backoff for worker restart.

        Args:
            worker: The worker to calculate backoff for.

        Returns:
            Backoff duration in seconds.
        """
        # Exponential backoff: base * 2^restart_count
        backoff: float = worker.backoff_base * (2**worker.restart_count)
        return float(min(backoff, worker.backoff_max))

    async def _broadcast_status(
        self,
        name: str,
        status: WorkerStatus,
        message: str | None = None,
    ) -> None:
        """Broadcast worker status change via WebSocket.

        Args:
            name: Worker name.
            status: New status.
            message: Optional status message.
        """
        if self._broadcaster is None:
            return

        event_data = {
            "type": "service_status",
            "data": {
                "service": f"worker:{name}",
                "status": status.value,
                "message": message,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

        try:
            await self._broadcaster.broadcast_service_status(event_data)
        except Exception as e:
            logger.warning(f"Failed to broadcast worker status: {e}")

    def get_worker_status(self, name: str) -> WorkerStatus | None:
        """Get the current status of a worker.

        Args:
            name: Name of the worker.

        Returns:
            WorkerStatus or None if worker not found.
        """
        worker = self._workers.get(name)
        return worker.status if worker else None

    def get_worker_info(self, name: str) -> WorkerInfo | None:
        """Get full information about a worker.

        Args:
            name: Name of the worker.

        Returns:
            WorkerInfo or None if worker not found.
        """
        return self._workers.get(name)

    def get_all_workers(self) -> dict[str, WorkerInfo]:
        """Get all registered workers.

        Returns:
            Dictionary mapping worker names to WorkerInfo.
        """
        return dict(self._workers)

    def reset_worker(self, name: str) -> bool:
        """Reset a failed worker's restart count to allow new restarts.

        Args:
            name: Name of the worker to reset.

        Returns:
            True if worker was reset, False if not found.
        """
        worker = self._workers.get(name)
        if worker is None:
            return False

        worker.restart_count = 0
        if worker.status == WorkerStatus.FAILED:
            worker.status = WorkerStatus.STOPPED

        logger.info(f"Reset worker '{name}' restart count")
        return True

    @property
    def is_running(self) -> bool:
        """Check if the supervisor is running."""
        return self._running

    @property
    def worker_count(self) -> int:
        """Get the number of registered workers."""
        return len(self._workers)


# Singleton instance
_supervisor: WorkerSupervisor | None = None


def get_worker_supervisor(
    config: SupervisorConfig | None = None,
    broadcaster: EventBroadcaster | None = None,
) -> WorkerSupervisor:
    """Get the singleton WorkerSupervisor instance.

    Args:
        config: Configuration (only used on first call).
        broadcaster: EventBroadcaster (only used on first call).

    Returns:
        The WorkerSupervisor singleton.
    """
    global _supervisor  # noqa: PLW0603
    if _supervisor is None:
        _supervisor = WorkerSupervisor(config=config, broadcaster=broadcaster)
    return _supervisor


def reset_worker_supervisor() -> None:
    """Reset the singleton instance (for testing)."""
    global _supervisor  # noqa: PLW0603
    _supervisor = None
