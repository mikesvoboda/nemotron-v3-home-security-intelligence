"""Service health monitor for automatic recovery of dependent services.

This service monitors the health of dependent services (Redis, RT-DETRv2, Nemotron)
and automatically attempts recovery with exponential backoff when failures are detected.

Features:
    - Periodic health checks for all configured services
    - Automatic restart with exponential backoff on failure
    - Configurable max retries before giving up
    - WebSocket broadcast of service status changes
    - Graceful shutdown support
"""

import asyncio
import contextlib
from datetime import UTC, datetime

from backend.core.logging import get_logger
from backend.services.event_broadcaster import EventBroadcaster
from backend.services.service_managers import ServiceConfig, ServiceManager

logger = get_logger(__name__)


class ServiceHealthMonitor:
    """Monitors service health and orchestrates automatic recovery.

    This class periodically checks the health of all configured services
    and attempts automatic restarts with exponential backoff when failures
    are detected. Status changes are broadcast via WebSocket.

    Status values:
        - healthy: Service responding normally
        - unhealthy: Health check failed
        - restarting: Restart in progress
        - restart_failed: Restart attempt failed
        - failed: Max retries exceeded, giving up
    """

    def __init__(
        self,
        manager: ServiceManager,
        services: list[ServiceConfig],
        broadcaster: EventBroadcaster | None = None,
        check_interval: float = 15.0,
    ) -> None:
        """Initialize the health monitor.

        Args:
            manager: ServiceManager implementation for health checks and restarts
            services: List of service configurations to monitor
            broadcaster: Optional EventBroadcaster for WebSocket status updates
            check_interval: Seconds between health check cycles (default: 15.0)
        """
        self._manager = manager
        self._services = services
        self._broadcaster = broadcaster
        self._check_interval = check_interval
        self._failure_counts: dict[str, int] = {}
        self._running = False
        self._task: asyncio.Task[None] | None = None

        logger.info(
            f"ServiceHealthMonitor initialized: "
            f"services={[s.name for s in services]}, "
            f"check_interval={check_interval}s"
        )

    async def start(self) -> None:
        """Start the health check loop.

        This method is idempotent - calling it when already running has no effect.
        """
        if self._running:
            logger.warning("ServiceHealthMonitor already running")
            return

        logger.info("Starting ServiceHealthMonitor")
        self._running = True
        self._failure_counts.clear()

        # Start health check loop in background
        self._task = asyncio.create_task(self._health_check_loop())

        logger.info("ServiceHealthMonitor started successfully")

    async def stop(self) -> None:
        """Stop the health check loop gracefully.

        Cancels the background task and waits for it to complete.
        """
        if not self._running:
            logger.debug("ServiceHealthMonitor not running, nothing to stop")
            return

        logger.info("Stopping ServiceHealthMonitor")
        self._running = False

        # Cancel health check task
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        logger.info("ServiceHealthMonitor stopped")

    async def _health_check_loop(self) -> None:
        """Main loop - check all services every N seconds.

        Runs continuously until stopped, checking the health of each
        configured service and handling failures appropriately.
        """
        logger.info("Health check loop started")

        while self._running:
            try:
                # Check health of all services
                for service in self._services:
                    if not self._running:
                        break

                    try:
                        is_healthy = await self._manager.check_health(service)

                        if is_healthy:
                            # Service recovered or still healthy
                            if (
                                service.name in self._failure_counts
                                and self._failure_counts[service.name] > 0
                            ):
                                logger.info(f"Service {service.name} recovered")
                                self._failure_counts[service.name] = 0
                                await self._broadcast_status(
                                    service, "healthy", "Service recovered"
                                )
                        else:
                            # Service is unhealthy
                            logger.warning(f"Health check failed for {service.name}")
                            await self._broadcast_status(
                                service, "unhealthy", "Health check failed"
                            )
                            await self._handle_failure(service)

                    except Exception as e:
                        logger.error(f"Error checking health of {service.name}: {e}")
                        await self._broadcast_status(
                            service, "unhealthy", f"Health check error: {e}"
                        )
                        await self._handle_failure(service)

                # Wait for next check cycle
                await asyncio.sleep(self._check_interval)

            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)
                # Continue running even after errors, wait before retrying
                await asyncio.sleep(self._check_interval)

        logger.info("Health check loop stopped")

    async def _handle_failure(self, service: ServiceConfig) -> None:
        """Handle service failure with exponential backoff restart.

        Increments failure count, calculates backoff delay, and attempts
        restart if max retries have not been exceeded.

        Args:
            service: Configuration of the failed service
        """
        # Increment failure count
        current_failures = self._failure_counts.get(service.name, 0) + 1
        self._failure_counts[service.name] = current_failures

        # Check if max retries exceeded
        if current_failures > service.max_retries:
            logger.error(
                f"Service {service.name} exceeded max retries ({service.max_retries}), giving up"
            )
            await self._broadcast_status(
                service,
                "failed",
                f"Max retries ({service.max_retries}) exceeded, manual intervention required",
            )
            return

        # Calculate exponential backoff: backoff_base * 2^(failures-1)
        # e.g., with backoff_base=5: 5s, 10s, 20s, 40s, ...
        backoff_delay = service.backoff_base * (2 ** (current_failures - 1))

        logger.info(
            f"Attempting restart of {service.name} "
            f"(attempt {current_failures}/{service.max_retries}) "
            f"after {backoff_delay}s backoff"
        )

        # Wait for backoff period
        await asyncio.sleep(backoff_delay)

        # Check if still running after backoff
        if not self._running:
            return

        # Broadcast restarting status
        await self._broadcast_status(
            service,
            "restarting",
            f"Attempting restart (attempt {current_failures}/{service.max_retries})",
        )

        # Attempt restart
        try:
            restart_success = await self._manager.restart(service)

            if restart_success:
                logger.info(f"Restart of {service.name} succeeded")
                # Verify health after restart
                await asyncio.sleep(2)  # Brief pause before health check
                is_healthy = await self._manager.check_health(service)

                if is_healthy:
                    logger.info(f"Service {service.name} is healthy after restart")
                    self._failure_counts[service.name] = 0
                    await self._broadcast_status(
                        service, "healthy", "Service restarted successfully"
                    )
                else:
                    logger.warning(f"Service {service.name} restarted but health check failed")
                    await self._broadcast_status(
                        service,
                        "restart_failed",
                        "Service restarted but health check failed",
                    )
            else:
                logger.warning(f"Restart of {service.name} failed")
                await self._broadcast_status(
                    service,
                    "restart_failed",
                    f"Restart command failed (attempt {current_failures}/{service.max_retries})",
                )

        except Exception as e:
            logger.error(f"Error during restart of {service.name}: {e}")
            await self._broadcast_status(
                service,
                "restart_failed",
                f"Restart error: {e}",
            )

    async def _broadcast_status(
        self,
        service: ServiceConfig,
        status: str,
        message: str | None = None,
    ) -> None:
        """Broadcast service status via WebSocket and log.

        Args:
            service: Service configuration
            status: Status value (healthy, unhealthy, restarting, restart_failed, failed)
            message: Optional descriptive message
        """
        # Always log status changes
        log_level = "info" if status == "healthy" else "warning"
        log_msg = f"Service {service.name} status: {status}"
        if message:
            log_msg += f" - {message}"
        getattr(logger, log_level)(log_msg)

        # Broadcast via WebSocket if broadcaster available
        if self._broadcaster is None:
            return

        event_data = {
            "type": "service_status",
            "service": service.name,
            "status": status,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        try:
            await self._broadcaster.broadcast_event(event_data)
        except Exception as e:
            # Don't let broadcast failures crash the monitor
            logger.warning(f"Failed to broadcast service status for {service.name}: {e}")

    def get_status(self) -> dict[str, dict[str, int | str]]:
        """Get current status of all monitored services.

        Returns:
            Dictionary mapping service names to their current failure counts
        """
        return {
            service.name: {
                "failure_count": self._failure_counts.get(service.name, 0),
                "max_retries": service.max_retries,
            }
            for service in self._services
        }

    @property
    def is_running(self) -> bool:
        """Check if the health monitor is running."""
        return self._running
