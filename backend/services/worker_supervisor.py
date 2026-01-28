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
    - Callback support for on_restart and on_failure events (NEM-2460)

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
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger
from backend.core.metrics import (
    record_pipeline_worker_restart,
    record_worker_crash,
    record_worker_heartbeat_missed,
    record_worker_max_restarts_exceeded,
    record_worker_restart,
    set_pipeline_worker_consecutive_failures,
    set_pipeline_worker_state,
    set_pipeline_worker_uptime,
    set_worker_status,
    update_worker_pool_metrics,
)

if TYPE_CHECKING:
    from backend.services.event_broadcaster import EventBroadcaster

logger = get_logger(__name__)

# Type aliases for callbacks (NEM-2460)
OnRestartCallback = Callable[[str, int, str | None], Awaitable[None]]
OnFailureCallback = Callable[[str, str | None], Awaitable[None]]


class WorkerStatus(Enum):
    """Health status of a monitored worker."""

    RUNNING = "running"
    STOPPED = "stopped"
    CRASHED = "crashed"
    RESTARTING = "restarting"
    FAILED = "failed"


class WorkerState(Enum):
    """State machine states for worker lifecycle (NEM-2492).

    This enum provides a more detailed state machine for workers,
    complementing WorkerStatus for richer state tracking.
    """

    IDLE = "idle"
    RUNNING = "running"
    RESTARTING = "restarting"
    FAILED = "failed"
    STOPPED = "stopped"


class RestartPolicy(Enum):
    """Restart policy for workers (NEM-2492).

    Determines when a worker should be automatically restarted.
    """

    ALWAYS = "always"
    ON_FAILURE = "on_failure"
    NEVER = "never"


@dataclass
class WorkerConfig:
    """Configuration for a supervised worker (NEM-2492).

    Attributes:
        name: Unique identifier for the worker.
        coroutine_factory: Async callable that creates and runs the worker.
        restart_policy: When to restart the worker.
        max_restarts: Maximum number of restart attempts.
        restart_delay_base: Base delay for exponential backoff.
        health_check_interval: Interval between health checks.
    """

    name: str
    coroutine_factory: Callable[[], Awaitable[None]]
    restart_policy: RestartPolicy = RestartPolicy.ON_FAILURE
    max_restarts: int = 5
    restart_delay_base: float = 1.0
    health_check_interval: float = 30.0


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
        circuit_open: Whether the circuit breaker is open (NEM-2492).
        last_heartbeat_at: When the last heartbeat was received (NEM-4148).
        heartbeat_timeout: Seconds before a heartbeat is considered missed (NEM-4148).
        missed_heartbeat_count: Number of consecutive missed heartbeats (NEM-4148).
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
    circuit_open: bool = False  # NEM-2492: Circuit breaker state
    last_heartbeat_at: datetime | None = None  # NEM-4148: Heartbeat tracking
    heartbeat_timeout: float = 30.0  # NEM-4148: Heartbeat timeout in seconds
    missed_heartbeat_count: int = 0  # NEM-4148: Consecutive missed heartbeats

    def to_dict(self) -> dict[str, Any]:
        """Convert WorkerInfo to a dictionary for serialization (NEM-2492, NEM-4148).

        Returns:
            Dictionary representation of the worker info.
        """
        return {
            "name": self.name,
            "status": self.status.value,
            "restart_count": self.restart_count,
            "max_restarts": self.max_restarts,
            "backoff_base": self.backoff_base,
            "backoff_max": self.backoff_max,
            "last_started_at": self.last_started_at.isoformat() if self.last_started_at else None,
            "last_crashed_at": self.last_crashed_at.isoformat() if self.last_crashed_at else None,
            "error": self.error,
            "circuit_open": self.circuit_open,
            "last_heartbeat_at": (
                self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None
            ),
            "heartbeat_timeout": self.heartbeat_timeout,
            "missed_heartbeat_count": self.missed_heartbeat_count,
        }


@dataclass
class RestartEvent:
    """Record of a worker restart event (NEM-2462).

    Attributes:
        worker_name: Name of the worker that was restarted.
        timestamp: When the restart occurred.
        attempt: Restart attempt number (1-indexed).
        status: Result of the restart: 'success' or 'failed'.
        error: Error message that triggered the restart, if any.
    """

    worker_name: str
    timestamp: datetime
    attempt: int
    status: str  # 'success' or 'failed'
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert RestartEvent to a dictionary for serialization."""
        return {
            "worker_name": self.worker_name,
            "timestamp": self.timestamp.isoformat(),
            "attempt": self.attempt,
            "status": self.status,
            "error": self.error,
        }


@dataclass
class SupervisorConfig:
    """Configuration for the WorkerSupervisor.

    Attributes:
        check_interval: Seconds between health checks.
        default_max_restarts: Default max restarts for workers.
        default_backoff_base: Default base backoff time.
        default_backoff_max: Default max backoff time.
        max_restart_history: Maximum number of restart events to keep in history.
        default_heartbeat_timeout: Default heartbeat timeout for workers (NEM-4148).
        heartbeat_check_enabled: Whether to check for missed heartbeats (NEM-4148).
    """

    check_interval: float = 5.0
    default_max_restarts: int = 5
    default_backoff_base: float = 1.0
    default_backoff_max: float = 60.0
    max_restart_history: int = 100
    default_heartbeat_timeout: float = 30.0  # NEM-4148
    heartbeat_check_enabled: bool = True  # NEM-4148


class WorkerSupervisor:
    """Supervises asyncio workers and auto-restarts them on crashes.

    This supervisor monitors registered worker tasks and automatically
    restarts them with exponential backoff when they fail.

    Callbacks (NEM-2460):
        on_restart: Called when a worker is about to be restarted with (name, attempt, error).
        on_failure: Called when a worker exceeds max restarts with (name, error).
    """

    def __init__(
        self,
        config: SupervisorConfig | None = None,
        broadcaster: EventBroadcaster | None = None,
        on_restart: OnRestartCallback | None = None,
        on_failure: OnFailureCallback | None = None,
    ) -> None:
        """Initialize the WorkerSupervisor.

        Args:
            config: Supervisor configuration. Uses defaults if not provided.
            broadcaster: Optional EventBroadcaster for status updates.
            on_restart: Optional async callback called when a worker is restarted.
                Signature: async def on_restart(name: str, attempt: int, error: str | None)
            on_failure: Optional async callback called when a worker exceeds max restarts.
                Signature: async def on_failure(name: str, error: str | None)
        """
        self._config = config or SupervisorConfig()
        self._broadcaster = broadcaster
        self._on_restart = on_restart
        self._on_failure = on_failure
        self._workers: dict[str, WorkerInfo] = {}
        self._running = False
        self._monitor_task: asyncio.Task[None] | None = None
        self._restart_locks: dict[str, asyncio.Lock] = {}
        self._restart_history: list[RestartEvent] = []  # NEM-2462: Restart history

        logger.info(f"WorkerSupervisor initialized: check_interval={self._config.check_interval}s")

    async def register_worker(
        self,
        name: str,
        factory: Callable[[], Awaitable[None]],
        max_restarts: int | None = None,
        backoff_base: float | None = None,
        backoff_max: float | None = None,
        heartbeat_timeout: float | None = None,
    ) -> None:
        """Register a worker to be supervised.

        Args:
            name: Unique identifier for the worker.
            factory: Async callable that runs the worker logic.
            max_restarts: Max restart attempts (uses config default if None).
            backoff_base: Base backoff time (uses config default if None).
            backoff_max: Max backoff time (uses config default if None).
            heartbeat_timeout: Heartbeat timeout in seconds (uses config default if None).
                Workers should call record_heartbeat() within this interval (NEM-4148).

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
            heartbeat_timeout=heartbeat_timeout or self._config.default_heartbeat_timeout,
        )

        self._workers[name] = worker
        self._restart_locks[name] = asyncio.Lock()

        logger.info(
            f"Registered worker '{name}': max_restarts={worker.max_restarts}, "
            f"backoff_base={worker.backoff_base}s, heartbeat_timeout={worker.heartbeat_timeout}s"
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

        # Initialize worker pool metrics
        self._update_worker_pool_metrics()

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

            # Record stopped status metrics (NEM-2457, NEM-2459)
            set_worker_status(worker_name, WorkerStatus.STOPPED.value)
            set_pipeline_worker_state(worker_name, "stopped")
            set_pipeline_worker_uptime(worker_name, -1.0)  # Not running

        # Update worker pool metrics to show all workers stopped
        self._update_worker_pool_metrics()

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
        worker.last_heartbeat_at = datetime.now(UTC)  # NEM-4148: Initialize heartbeat
        worker.missed_heartbeat_count = 0  # NEM-4148: Reset missed heartbeat count
        worker.error = None

        # Record metrics (NEM-2457, NEM-2459)
        set_worker_status(name, WorkerStatus.RUNNING.value)
        set_pipeline_worker_state(name, "running")
        set_pipeline_worker_consecutive_failures(name, worker.restart_count)
        set_pipeline_worker_uptime(name, 0.0)  # Just started

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

            # Record metrics (NEM-2457, NEM-2459, NEM-4148)
            record_worker_crash(name, error=str(e))
            set_worker_status(name, WorkerStatus.CRASHED.value)
            set_pipeline_worker_state(name, "stopped")
            set_pipeline_worker_consecutive_failures(name, worker.restart_count + 1)
            set_pipeline_worker_uptime(name, -1.0)  # Not running

            logger.error(f"Worker '{name}' crashed: {e}", exc_info=True)
            await self._broadcast_status(name, WorkerStatus.CRASHED, str(e))

    async def _monitor_loop(self) -> None:
        """Main loop that monitors workers and restarts crashed ones."""
        logger.info("Monitor loop started")

        while self._running:
            try:
                # Update worker pool metrics for Grafana dashboard
                self._update_worker_pool_metrics()

                for name, worker in list(self._workers.items()):
                    if not self._running:
                        break

                    # Check if worker needs restart
                    if worker.status == WorkerStatus.CRASHED:
                        await self._handle_crashed_worker(name)

                    # NEM-4148: Check for missed heartbeats
                    elif worker.status == WorkerStatus.RUNNING:
                        self._check_worker_heartbeat(name)

                await asyncio.sleep(self._config.check_interval)

            except asyncio.CancelledError:
                logger.info("Monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                await asyncio.sleep(self._config.check_interval)

        logger.info("Monitor loop stopped")

    def _check_worker_heartbeat(self, name: str) -> None:
        """Check if a worker has missed its heartbeat deadline (NEM-4148).

        Args:
            name: Name of the worker to check.
        """
        if not self._config.heartbeat_check_enabled:
            return

        worker = self._workers.get(name)
        if worker is None or worker.last_heartbeat_at is None:
            return

        # Calculate time since last heartbeat
        now = datetime.now(UTC)
        seconds_since_heartbeat = (now - worker.last_heartbeat_at).total_seconds()

        # Check if heartbeat is overdue
        if seconds_since_heartbeat > worker.heartbeat_timeout:
            worker.missed_heartbeat_count += 1
            record_worker_heartbeat_missed(name)
            logger.warning(
                f"Worker '{name}' missed heartbeat #{worker.missed_heartbeat_count} "
                f"(last: {seconds_since_heartbeat:.1f}s ago, timeout: {worker.heartbeat_timeout}s)"
            )

    async def _handle_crashed_worker(self, name: str) -> None:
        """Handle a crashed worker by attempting restart.

        Args:
            name: Name of the crashed worker.
        """
        import time

        async with self._restart_locks[name]:
            worker = self._workers[name]

            # Check if we've exceeded max restarts
            if worker.restart_count >= worker.max_restarts:
                if worker.status != WorkerStatus.FAILED:
                    worker.status = WorkerStatus.FAILED
                    worker.circuit_open = True  # Open circuit breaker (NEM-2492)

                    # Record metrics (NEM-2457, NEM-2459)
                    record_worker_max_restarts_exceeded(name)
                    set_worker_status(name, WorkerStatus.FAILED.value)
                    set_pipeline_worker_state(name, "failed")
                    set_pipeline_worker_consecutive_failures(name, worker.restart_count)
                    set_pipeline_worker_uptime(name, -1.0)  # Not running

                    logger.error(
                        f"Worker '{name}' exceeded max restarts ({worker.max_restarts}), giving up"
                    )
                    await self._broadcast_status(
                        name,
                        WorkerStatus.FAILED,
                        f"Exceeded max restarts ({worker.max_restarts})",
                    )

                    # Record failed restart in history (NEM-2462)
                    self._record_restart_event(
                        worker_name=name,
                        attempt=worker.restart_count,
                        status="failed",
                        error=f"Exceeded max restarts ({worker.max_restarts})",
                    )

                    # Invoke on_failure callback (NEM-2460)
                    if self._on_failure is not None:
                        try:
                            await self._on_failure(name, worker.error)
                        except Exception as cb_err:
                            logger.warning(f"on_failure callback raised exception: {cb_err}")
                return

            # Calculate backoff
            backoff = self._calculate_backoff(worker)
            worker.status = WorkerStatus.RESTARTING

            # Record restarting status metric (NEM-2457, NEM-2459)
            set_worker_status(name, WorkerStatus.RESTARTING.value)
            set_pipeline_worker_state(name, "restarting")

            logger.info(
                f"Restarting worker '{name}' in {backoff:.1f}s "
                f"(attempt {worker.restart_count + 1}/{worker.max_restarts})"
            )
            await self._broadcast_status(name, WorkerStatus.RESTARTING)

            # Invoke on_restart callback (NEM-2460)
            if self._on_restart is not None:
                try:
                    await self._on_restart(name, worker.restart_count + 1, worker.error)
                except Exception as cb_err:
                    logger.warning(f"on_restart callback raised exception: {cb_err}")

            # Track restart duration (NEM-2459)
            restart_start_time = time.monotonic()

            # Wait for backoff
            await asyncio.sleep(backoff)

            if not self._running:
                return

            # Increment restart count and start
            worker.restart_count += 1

            # Record restart metrics (NEM-2457, NEM-2459, NEM-4148)
            record_worker_restart(name, reason=worker.error)
            restart_duration = time.monotonic() - restart_start_time
            record_pipeline_worker_restart(
                name, reason=worker.error, duration_seconds=restart_duration
            )

            await self._start_worker(name)

            # Record restart event in history (NEM-2462)
            self._record_restart_event(
                worker_name=name,
                attempt=worker.restart_count,
                status="success",
                error=worker.error,
            )

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

    def record_heartbeat(self, name: str) -> bool:
        """Record a heartbeat from a worker (NEM-4148).

        Workers should call this method periodically to indicate they are
        still alive and processing. If a worker fails to send heartbeats
        within its configured timeout, it will be flagged as having missed
        a heartbeat and the metric will be recorded.

        Args:
            name: Name of the worker sending the heartbeat.

        Returns:
            True if heartbeat was recorded, False if worker not found.
        """
        worker = self._workers.get(name)
        if worker is None:
            logger.warning(f"Cannot record heartbeat for unknown worker: {name}")
            return False

        worker.last_heartbeat_at = datetime.now(UTC)
        worker.missed_heartbeat_count = 0  # Reset on successful heartbeat

        logger.debug(f"Heartbeat recorded for worker '{name}'")
        return True

    def get_missed_heartbeat_count(self, name: str) -> int:
        """Get the number of consecutive missed heartbeats for a worker (NEM-4148).

        Args:
            name: Name of the worker.

        Returns:
            Number of consecutive missed heartbeats, or 0 if worker not found.
        """
        worker = self._workers.get(name)
        if worker is None:
            return 0
        return worker.missed_heartbeat_count

    @property
    def is_running(self) -> bool:
        """Check if the supervisor is running."""
        return self._running

    @property
    def worker_count(self) -> int:
        """Get the number of registered workers."""
        return len(self._workers)

    def get_worker_pool_counts(self) -> tuple[int, int, int]:
        """Get counts of active, busy, and idle workers.

        Active workers are those with status RUNNING.
        Busy workers are RUNNING workers with a currently executing task.
        Idle workers are RUNNING workers without current task execution.

        Note: In this supervisor model, workers are always "busy" when running
        because each worker runs a continuous loop. The distinction between
        busy and idle is made based on whether the task is actively processing
        vs waiting for work (e.g., waiting on a queue).

        Returns:
            Tuple of (active_count, busy_count, idle_count)
        """
        active = 0
        busy = 0

        for worker in self._workers.values():
            if worker.status == WorkerStatus.RUNNING:
                active += 1
                # A running worker is considered "busy" if it has an active task
                # that is not done. In practice, all running workers are busy
                # since they run continuous loops.
                if worker.task is not None and not worker.task.done():
                    busy += 1

        idle = active - busy
        return active, busy, idle

    def _update_worker_pool_metrics(self) -> None:
        """Update Prometheus worker pool metrics.

        Called periodically by the monitor loop to update:
        - hsi_worker_active_count
        - hsi_worker_busy_count
        - hsi_worker_idle_count
        """
        active, busy, idle = self.get_worker_pool_counts()
        update_worker_pool_metrics(active, busy, idle)

    def get_all_statuses(self) -> dict[str, dict[str, Any]]:
        """Get status dictionaries for all workers (NEM-2492).

        Returns:
            Dictionary mapping worker names to their status dictionaries.
        """
        return {name: worker.to_dict() for name, worker in self._workers.items()}

    def reset_circuit_breaker(self, name: str) -> bool:
        """Reset the circuit breaker for a worker (NEM-2492).

        This clears the circuit_open flag and resets the restart count,
        allowing the worker to be restarted again.

        Args:
            name: Name of the worker to reset.

        Returns:
            True if worker was reset, False if not found.
        """
        worker = self._workers.get(name)
        if worker is None:
            logger.warning(f"Cannot reset circuit breaker for unknown worker: {name}")
            return False

        worker.circuit_open = False
        worker.restart_count = 0
        if worker.status == WorkerStatus.FAILED:
            worker.status = WorkerStatus.STOPPED

        logger.info(f"Reset circuit breaker for worker '{name}'")
        return True

    @staticmethod
    def _calculate_backoff_static(restart_count: int, base: float, max_backoff: float) -> float:
        """Calculate exponential backoff (static version) (NEM-2492).

        This is a static method that can be called without an instance,
        useful for testing and external calculations.

        Args:
            restart_count: Number of restarts so far.
            base: Base backoff time in seconds.
            max_backoff: Maximum backoff time in seconds.

        Returns:
            Backoff duration in seconds.
        """
        if restart_count <= 0:
            return base
        delay = base * (2 ** (restart_count - 1))
        return float(min(delay, max_backoff))

    # =========================================================================
    # Restart History Methods (NEM-2462)
    # =========================================================================

    def _record_restart_event(
        self,
        worker_name: str,
        attempt: int,
        status: str,
        error: str | None = None,
    ) -> None:
        """Record a restart event in the history.

        Args:
            worker_name: Name of the worker.
            attempt: Restart attempt number.
            status: Result status ('success' or 'failed').
            error: Error message, if any.
        """
        event = RestartEvent(
            worker_name=worker_name,
            timestamp=datetime.now(UTC),
            attempt=attempt,
            status=status,
            error=error,
        )
        self._restart_history.append(event)

        # Trim history if it exceeds max size
        if len(self._restart_history) > self._config.max_restart_history:
            self._restart_history = self._restart_history[-self._config.max_restart_history :]

        logger.debug(f"Recorded restart event: {worker_name} attempt={attempt} status={status}")

    def get_restart_history(
        self,
        worker_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get restart history with optional filtering and pagination (NEM-2462).

        Args:
            worker_name: Optional filter by worker name.
            limit: Maximum number of events to return.
            offset: Number of events to skip.

        Returns:
            List of restart event dictionaries, newest first.
        """
        # Filter by worker name if specified
        if worker_name:
            events = [e for e in self._restart_history if e.worker_name == worker_name]
        else:
            events = list(self._restart_history)

        # Sort by timestamp descending (newest first)
        events.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply pagination
        paginated = events[offset : offset + limit]

        return [e.to_dict() for e in paginated]

    def get_restart_history_count(self, worker_name: str | None = None) -> int:
        """Get total count of restart history events (NEM-2462).

        Args:
            worker_name: Optional filter by worker name.

        Returns:
            Total count of restart events.
        """
        if worker_name:
            return sum(1 for e in self._restart_history if e.worker_name == worker_name)
        return len(self._restart_history)

    # =========================================================================
    # Manual Worker Control Methods (NEM-2462)
    # =========================================================================

    async def start_worker(self, name: str) -> bool:
        """Manually start a stopped worker (NEM-2462).

        Args:
            name: Name of the worker to start.

        Returns:
            True if worker was started, False if not found or already running.
        """
        worker = self._workers.get(name)
        if worker is None:
            logger.warning(f"Cannot start unknown worker: {name}")
            return False

        if worker.status == WorkerStatus.RUNNING:
            logger.info(f"Worker '{name}' is already running")
            return True  # Idempotent - already running is success

        # Reset if failed
        if worker.status == WorkerStatus.FAILED:
            worker.restart_count = 0
            worker.circuit_open = False

        await self._start_worker(name)
        logger.info(f"Manually started worker '{name}'")
        return True

    async def stop_worker(self, name: str) -> bool:
        """Manually stop a running worker (NEM-2462).

        Args:
            name: Name of the worker to stop.

        Returns:
            True if worker was stopped, False if not found.
        """
        worker = self._workers.get(name)
        if worker is None:
            logger.warning(f"Cannot stop unknown worker: {name}")
            return False

        if worker.task is not None and not worker.task.done():
            worker.task.cancel()
            try:
                await worker.task
            except asyncio.CancelledError:
                pass

        worker.status = WorkerStatus.STOPPED
        worker.task = None

        # Record stopped status metric
        set_worker_status(name, WorkerStatus.STOPPED.value)

        await self._broadcast_status(name, WorkerStatus.STOPPED, "Manually stopped")
        logger.info(f"Manually stopped worker '{name}'")
        return True

    async def restart_worker_task(self, name: str) -> bool:
        """Manually restart a worker (stop then start) (NEM-2462).

        This is different from the automatic restart which happens on crashes.
        This method allows manual intervention to restart a worker.

        Args:
            name: Name of the worker to restart.

        Returns:
            True if worker was restarted, False if not found.
        """
        worker = self._workers.get(name)
        if worker is None:
            logger.warning(f"Cannot restart unknown worker: {name}")
            return False

        # Stop if running
        if worker.task is not None and not worker.task.done():
            worker.task.cancel()
            try:
                await worker.task
            except asyncio.CancelledError:
                pass

        # Reset state for manual restart
        worker.restart_count = 0
        worker.circuit_open = False
        worker.error = None

        # Start the worker
        await self._start_worker(name)

        # Record manual restart in history
        self._record_restart_event(
            worker_name=name,
            attempt=0,  # Manual restart, not auto-restart
            status="success",
            error="Manual restart requested",
        )

        logger.info(f"Manually restarted worker '{name}'")
        return True


# Singleton instance
_supervisor: WorkerSupervisor | None = None


def get_worker_supervisor(
    config: SupervisorConfig | None = None,
    broadcaster: EventBroadcaster | None = None,
    on_restart: OnRestartCallback | None = None,
    on_failure: OnFailureCallback | None = None,
) -> WorkerSupervisor:
    """Get the singleton WorkerSupervisor instance.

    Args:
        config: Configuration (only used on first call).
        broadcaster: EventBroadcaster (only used on first call).
        on_restart: Optional callback for worker restarts (only used on first call).
        on_failure: Optional callback for worker failures (only used on first call).

    Returns:
        The WorkerSupervisor singleton.
    """
    global _supervisor  # noqa: PLW0603
    if _supervisor is None:
        _supervisor = WorkerSupervisor(
            config=config,
            broadcaster=broadcaster,
            on_restart=on_restart,
            on_failure=on_failure,
        )
    return _supervisor


def reset_worker_supervisor() -> None:
    """Reset the singleton instance (for testing)."""
    global _supervisor  # noqa: PLW0603
    _supervisor = None
