"""WebSocket broadcaster for system status updates.

This module manages WebSocket connections and broadcasts real-time system
status updates to connected clients. It handles:

- Connection lifecycle management
- Periodic system status broadcasting via Redis pub/sub
- GPU statistics
- Camera status
- Processing queue status

Redis Pub/Sub Integration:
    The SystemBroadcaster uses Redis pub/sub to enable multi-instance deployments.
    System status updates are published to a dedicated Redis channel, and all
    instances subscribe to receive updates for their connected WebSocket clients.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import WebSocket
from sqlalchemy import func, select

from backend.api.schemas.performance import PerformanceUpdate, TimeRange
from backend.core import get_session
from backend.core.config import get_settings
from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.core.logging import get_logger
from backend.core.websocket_circuit_breaker import (
    WebSocketCircuitBreaker,
    WebSocketCircuitState,
)
from backend.models import Camera, CameraStatus, GPUStats

# Timeout for AI service health checks in seconds
# Keep this short to avoid blocking the broadcast loop
AI_HEALTH_CHECK_TIMEOUT = 1.0  # Short timeout to avoid blocking broadcast loop

if TYPE_CHECKING:
    from redis.asyncio.client import PubSub
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.core.redis import RedisClient
    from backend.services.performance_collector import PerformanceCollector

logger = get_logger(__name__)

# Redis channel for system status updates
SYSTEM_STATUS_CHANNEL = "system_status"

# Redis channel for performance updates
PERFORMANCE_UPDATE_CHANNEL = "performance_update"


class SystemBroadcaster:
    """Manages WebSocket connections for system status broadcasts.

    This class maintains a set of active WebSocket connections and provides
    methods to broadcast system status updates to all connected clients.
    Uses Redis pub/sub to enable multi-instance deployments where any instance
    can publish status updates and all instances forward them to their clients.

    Attributes:
        connections: Set of active WebSocket connections
        _broadcast_task: Background task for periodic status updates
        _listener_task: Background task for listening to Redis pub/sub
        _running: Flag indicating if broadcaster is running
        _redis_client: Injected Redis client instance (optional)
        _redis_getter: Callable that returns Redis client (alternative to direct injection)
        _pubsub: Redis pub/sub instance for receiving updates
        _performance_collector: Optional PerformanceCollector for detailed system metrics
    """

    # Maximum number of consecutive recovery attempts before giving up
    # Prevents unbounded recursion / stack overflow on repeated failures
    MAX_RECOVERY_ATTEMPTS = 5

    def __init__(
        self,
        redis_client: RedisClient | None = None,
        redis_getter: Callable[[], RedisClient | None] | None = None,
    ) -> None:
        """Initialize the SystemBroadcaster.

        Args:
            redis_client: Optional Redis client instance. If provided, takes precedence
                over redis_getter.
            redis_getter: Optional callable that returns a Redis client or None.
                Useful for lazy initialization when Redis may not be immediately available.
        """
        import uuid

        self.connections: set[WebSocket] = set()
        self._broadcast_task: asyncio.Task[None] | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._running = False
        self._redis_client = redis_client
        self._redis_getter = redis_getter
        self._pubsub: PubSub | None = None
        self._pubsub_listening = False
        self._recovery_attempts = 0
        self._performance_collector: PerformanceCollector | None = None
        # Unique instance ID to filter out messages from self in pub/sub
        self._instance_id = str(uuid.uuid4())

        # Circuit breaker for WebSocket connection resilience
        self._circuit_breaker = WebSocketCircuitBreaker(
            failure_threshold=self.MAX_RECOVERY_ATTEMPTS,
            recovery_timeout=30.0,
            half_open_max_calls=1,
            success_threshold=1,
            name="system_broadcaster",
        )

        # Degraded mode flag - set when all recovery attempts have been exhausted
        self._is_degraded = False

        # Performance history buffer for historical data
        # 60 minutes at 5-second intervals = 720 snapshots
        # This allows serving 5m, 15m, and 60m time ranges
        self._performance_history: deque[PerformanceUpdate] = deque(maxlen=720)

    def _get_redis(self) -> RedisClient | None:
        """Get the Redis client instance.

        Returns the directly injected redis_client if available, otherwise
        calls redis_getter if provided.

        Returns:
            RedisClient instance or None if unavailable
        """
        if self._redis_client is not None:
            return self._redis_client
        if self._redis_getter is not None:
            return self._redis_getter()
        return None

    def set_redis_client(self, redis_client: RedisClient | None) -> None:
        """Set the Redis client after initialization.

        This allows updating the Redis client after the broadcaster is created,
        useful when Redis initialization happens asynchronously.

        Args:
            redis_client: Redis client instance or None
        """
        self._redis_client = redis_client

    def set_performance_collector(self, collector: PerformanceCollector | None) -> None:
        """Set the PerformanceCollector after initialization.

        This allows the broadcaster to collect and broadcast detailed performance
        metrics from GPU, AI models, databases, and host system.

        Args:
            collector: PerformanceCollector instance or None
        """
        self._performance_collector = collector

    def _store_performance_snapshot(self, snapshot: PerformanceUpdate) -> None:
        """Store a performance snapshot in the history buffer.

        Snapshots are stored in chronological order (oldest first, newest last).
        The buffer automatically evicts the oldest entries when full.

        Args:
            snapshot: PerformanceUpdate to store
        """
        self._performance_history.append(snapshot)

    def get_performance_history(self, time_range: TimeRange) -> list[PerformanceUpdate]:
        """Get historical performance snapshots for the requested time range.

        Returns performance snapshots filtered and sampled based on the time range:
        - 5m: Returns all snapshots from the last 5 minutes (up to 60 points)
        - 15m: Returns sampled snapshots from last 15 minutes (~60 points, every 3rd)
        - 60m: Returns sampled snapshots from last 60 minutes (~60 points, every 12th)

        Args:
            time_range: TimeRange enum value (FIVE_MIN, FIFTEEN_MIN, SIXTY_MIN)

        Returns:
            List of PerformanceUpdate snapshots in chronological order (oldest first)
        """
        if not self._performance_history:
            return []

        now = datetime.now(UTC)

        # Determine time window and sampling rate based on time range
        if time_range == TimeRange.FIVE_MIN:
            window_start = now - timedelta(minutes=5)
            sample_interval = 1  # Every snapshot
            max_points = 60
        elif time_range == TimeRange.FIFTEEN_MIN:
            window_start = now - timedelta(minutes=15)
            sample_interval = 3  # Every 3rd snapshot
            max_points = 60
        else:  # SIXTY_MIN
            window_start = now - timedelta(minutes=60)
            sample_interval = 12  # Every 12th snapshot
            max_points = 60

        # Filter snapshots within the time window
        filtered = [s for s in self._performance_history if s.timestamp >= window_start]

        if not filtered:
            return []

        # Sample at the appropriate interval
        if sample_interval == 1:
            # For 5m range, take all snapshots up to max_points
            return filtered[-max_points:] if len(filtered) > max_points else filtered
        else:
            # For 15m and 60m, sample every Nth snapshot
            sampled = filtered[::sample_interval]
            return sampled[-max_points:] if len(sampled) > max_points else sampled

    @property
    def circuit_breaker(self) -> WebSocketCircuitBreaker:
        """Get the circuit breaker instance for this broadcaster."""
        return self._circuit_breaker

    def get_circuit_state(self) -> WebSocketCircuitState:
        """Get current circuit breaker state.

        Returns:
            Current WebSocketCircuitState (CLOSED, OPEN, or HALF_OPEN)
        """
        return self._circuit_breaker.get_state()

    def is_degraded(self) -> bool:
        """Check if the broadcaster is in degraded mode.

        Degraded mode is entered when all recovery attempts have been exhausted.
        In this state, the broadcaster cannot reliably broadcast real-time updates
        but may still accept WebSocket connections.

        Returns:
            True if broadcaster is in degraded mode, False otherwise
        """
        return self._is_degraded

    async def connect(self, websocket: WebSocket) -> None:
        """Add a WebSocket connection to the broadcaster.

        Args:
            websocket: WebSocket connection to add
        """
        await websocket.accept()
        self.connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.connections)}")

        # Send initial status immediately after connection
        try:
            status_data = await self._get_system_status()
            await websocket.send_json(status_data)
        except (ConnectionError, RuntimeError, OSError) as e:
            # ConnectionError: WebSocket connection issues
            # RuntimeError: event loop or asyncio issues
            # OSError: network-level failures
            logger.error(f"Failed to send initial status: {e}", exc_info=True)

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the broadcaster.

        Args:
            websocket: WebSocket connection to remove
        """
        self.connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.connections)}")

    async def broadcast_status(self, status_data: dict) -> None:
        """Broadcast system status to all connected clients.

        Always sends to local WebSocket clients directly for immediate delivery.
        Additionally publishes to Redis pub/sub for multi-instance support,
        but local clients receive updates even if Redis is unavailable or slow.

        Args:
            status_data: System status data to broadcast
        """
        # ALWAYS send to local clients first for immediate delivery
        # This ensures clients get updates even if Redis pub/sub has issues
        await self._send_to_local_clients(status_data)

        # Additionally publish via Redis for multi-instance support
        # Remote instances will receive this and forward to their local clients
        # Include instance_id so listener can filter out messages from self
        redis_client = self._get_redis()
        if redis_client is not None:
            try:
                pubsub_message = {
                    "_origin_instance": self._instance_id,
                    "payload": status_data,
                }
                await redis_client.publish(SYSTEM_STATUS_CHANNEL, pubsub_message)
                logger.debug("Published system status via Redis pub/sub")
            except (ConnectionError, TimeoutError, OSError) as e:
                # Redis connection failures and network issues
                logger.warning(f"Failed to publish via Redis: {e}", exc_info=True)

    async def broadcast_performance(self) -> None:
        """Broadcast detailed performance metrics to all connected clients.

        Uses the PerformanceCollector to gather comprehensive system metrics
        including GPU, AI models, databases, and host metrics. Broadcasts
        as message type "performance_update" via WebSocket.

        Always sends to local WebSocket clients directly for immediate delivery.
        Additionally publishes to Redis pub/sub for multi-instance support.

        If no PerformanceCollector is configured, this method returns early
        without broadcasting.
        """
        if self._performance_collector is None:
            logger.debug("No PerformanceCollector configured, skipping performance broadcast")
            return

        try:
            # Collect all performance metrics
            performance_update = await self._performance_collector.collect_all()

            # Store snapshot in history buffer for historical data endpoint
            self._store_performance_snapshot(performance_update)

            # Build the broadcast message
            performance_data = {
                "type": "performance_update",
                "data": performance_update.model_dump(mode="json"),
            }

            # ALWAYS send to local clients first for immediate delivery
            # This ensures clients get updates even if Redis pub/sub has issues
            await self._send_to_local_clients(performance_data)

            # Additionally publish via Redis for multi-instance support
            # Remote instances will receive this and forward to their local clients
            # Include instance_id so listener can filter out messages from self
            redis_client = self._get_redis()
            if redis_client is not None:
                try:
                    pubsub_message = {
                        "_origin_instance": self._instance_id,
                        "payload": performance_data,
                    }
                    await redis_client.publish(PERFORMANCE_UPDATE_CHANNEL, pubsub_message)
                    logger.debug("Published performance update via Redis pub/sub")
                except (ConnectionError, TimeoutError, OSError) as e:
                    # Redis connection failures and network issues
                    logger.warning(f"Failed to publish performance via Redis: {e}", exc_info=True)

        except (ValueError, RuntimeError, OSError) as e:
            # ValueError: serialization errors, RuntimeError: collector issues, OSError: IO errors
            logger.error(f"Error broadcasting performance metrics: {e}", exc_info=True)

    async def _send_to_local_clients(self, status_data: dict | Any) -> None:
        """Send status data directly to all locally connected WebSocket clients.

        This is the primary method for delivering updates to clients connected
        to this instance. It is called:
        1. From broadcast_status/broadcast_performance for immediate local delivery
        2. From the Redis pub/sub listener to receive updates from other instances

        Args:
            status_data: System status data to send
        """
        if not self.connections:
            return

        # Convert to JSON string if needed
        message = json.dumps(status_data) if not isinstance(status_data, str) else status_data

        failed_connections = set()

        for websocket in self.connections:
            try:
                await websocket.send_text(message)
            except (ConnectionError, RuntimeError, OSError) as e:
                # ConnectionError: WebSocket closed/disconnected
                # RuntimeError: asyncio issues, OSError: network failures
                logger.warning(f"Failed to send to WebSocket: {e}")
                failed_connections.add(websocket)

        # Remove failed connections
        self.connections -= failed_connections
        if failed_connections:
            logger.info(
                f"Removed {len(failed_connections)} failed connections. "
                f"Active connections: {len(self.connections)}"
            )

    async def _broadcast_degraded_state(self) -> None:
        """Broadcast degraded state notification to all connected clients.

        This method is called when the circuit breaker opens or when the broadcaster
        enters a failed state. It notifies connected clients that system status
        updates may not be delivered reliably.
        """
        if not self.connections:
            return

        degraded_message = {
            "type": "service_status",
            "data": {
                "service": "system_broadcaster",
                "status": "degraded",
                "message": "System status broadcasting is degraded. Updates may be delayed or unavailable.",
                "circuit_state": self._circuit_breaker.get_state().value,
            },
        }

        try:
            await self._send_to_local_clients(degraded_message)
            logger.info("Broadcast degraded state notification to connected clients")
        except (ConnectionError, RuntimeError, OSError) as e:
            # WebSocket broadcast failures
            logger.warning(f"Failed to broadcast degraded state: {e}", exc_info=True)

    async def broadcast_circuit_breaker_states(self) -> None:
        """Broadcast all circuit breaker states to connected clients (NEM-1582).

        This method collects the state of all registered circuit breakers and
        broadcasts them to WebSocket clients. It's useful for frontend dashboards
        to display service degradation status.

        The message format:
        {
            "type": "circuit_breaker_update",
            "data": {
                "timestamp": "2026-01-08T10:30:00Z",
                "summary": {
                    "total": 5,
                    "open": 0,
                    "half_open": 0,
                    "closed": 5
                },
                "breakers": {
                    "rtdetr": {"state": "closed", "failure_count": 0},
                    "nemotron": {"state": "closed", "failure_count": 0},
                    ...
                }
            }
        }
        """
        from backend.services.circuit_breaker import _get_registry

        try:
            registry = _get_registry()
            all_status = registry.get_all_status()

            # Calculate summary counts
            open_count = 0
            half_open_count = 0
            closed_count = 0
            breakers_data = {}

            for name, status in all_status.items():
                state_value = status.get("state", "closed")
                if state_value == "open":
                    open_count += 1
                elif state_value == "half_open":
                    half_open_count += 1
                else:
                    closed_count += 1

                breakers_data[name] = {
                    "state": state_value,
                    "failure_count": status.get("failure_count", 0),
                    "success_count": status.get("success_count", 0),
                    "last_failure_time": status.get("last_failure_time"),
                }

            circuit_breaker_message = {
                "type": "circuit_breaker_update",
                "data": {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "summary": {
                        "total": len(all_status),
                        "open": open_count,
                        "half_open": half_open_count,
                        "closed": closed_count,
                    },
                    "breakers": breakers_data,
                },
            }

            # Send to local clients
            await self._send_to_local_clients(circuit_breaker_message)

            # Publish via Redis for multi-instance support
            redis_client = self._get_redis()
            if redis_client is not None:
                try:
                    pubsub_message = {
                        "_origin_instance": self._instance_id,
                        "payload": circuit_breaker_message,
                    }
                    await redis_client.publish(SYSTEM_STATUS_CHANNEL, pubsub_message)
                except Exception as e:
                    logger.warning(f"Failed to publish circuit breaker update via Redis: {e}")

            logger.debug(
                f"Broadcast circuit breaker update: "
                f"{closed_count} closed, {open_count} open, {half_open_count} half-open"
            )

        except Exception as e:
            logger.warning(f"Failed to broadcast circuit breaker states: {e}")

    async def _start_pubsub_listener(self) -> None:
        """Start the Redis pub/sub listener for receiving system status updates.

        This enables multi-instance support where status updates published by
        any instance are received and forwarded to local WebSocket clients.

        Subscribes to both system_status and performance_update channels to
        receive all types of updates.

        Uses a dedicated pub/sub connection to avoid concurrency issues with
        other Redis operations (prevents 'readuntil() called while another
        coroutine is already waiting' errors).
        """
        redis_client = self._get_redis()
        if redis_client is None:
            logger.warning("Redis not available, pub/sub listener not started")
            return

        if self._pubsub_listening:
            logger.warning("Pub/sub listener already running")
            return

        try:
            # Use subscribe_dedicated() to get a dedicated connection that
            # won't conflict with other Redis operations
            # Subscribe to both system status and performance update channels
            self._pubsub = await redis_client.subscribe_dedicated(
                SYSTEM_STATUS_CHANNEL, PERFORMANCE_UPDATE_CHANNEL
            )
            self._pubsub_listening = True
            self._recovery_attempts = 0  # Reset recovery attempts on successful start
            self._circuit_breaker.reset()  # Reset circuit breaker on successful start
            self._is_degraded = False  # Clear degraded mode on successful start
            self._listener_task = asyncio.create_task(self._listen_for_updates())
            logger.info(
                f"Started pub/sub listener on channels: {SYSTEM_STATUS_CHANNEL}, "
                f"{PERFORMANCE_UPDATE_CHANNEL}"
            )
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Redis connection failures and asyncio issues
            logger.error(f"Failed to start pub/sub listener: {e}", exc_info=True)
            self._circuit_breaker.record_failure()

    async def _stop_pubsub_listener(self) -> None:
        """Stop the Redis pub/sub listener and close dedicated connection."""
        self._pubsub_listening = False

        if self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
            self._listener_task = None

        if self._pubsub:
            try:
                # Unsubscribe from both channels
                await self._pubsub.unsubscribe(SYSTEM_STATUS_CHANNEL, PERFORMANCE_UPDATE_CHANNEL)
            except (ConnectionError, TimeoutError, OSError) as e:
                # Redis connection issues during cleanup
                logger.warning(f"Error unsubscribing: {e}")
            try:
                # Close the dedicated pubsub connection
                await self._pubsub.close()
            except (ConnectionError, TimeoutError, OSError) as e:
                # Redis connection issues during cleanup
                logger.warning(f"Error closing pubsub connection: {e}")
            self._pubsub = None

        logger.info("Stopped pub/sub listener")

    async def _reset_pubsub_connection(self) -> None:
        """Reset the pub/sub connection by closing old and creating new subscription.

        This is used to recover from errors where the connection enters an invalid
        state. Creates a new dedicated connection for the listener.
        """
        redis_client = self._get_redis()
        if not redis_client:
            logger.error("Cannot reset pub/sub: Redis client not available")
            self._pubsub = None
            return

        # Close old dedicated pubsub connection if exists
        if self._pubsub:
            try:
                await self._pubsub.unsubscribe(SYSTEM_STATUS_CHANNEL, PERFORMANCE_UPDATE_CHANNEL)
            except (ConnectionError, TimeoutError, OSError) as e:
                # Redis connection issues during cleanup (expected during reset)
                logger.debug(f"Error unsubscribing during reset (expected): {e}")
            try:
                await self._pubsub.close()
            except (ConnectionError, TimeoutError, OSError) as e:
                # Redis connection issues during cleanup (expected during reset)
                logger.debug(f"Error closing pubsub during reset (expected): {e}")
            self._pubsub = None

        # Create fresh dedicated subscription to both channels
        try:
            self._pubsub = await redis_client.subscribe_dedicated(
                SYSTEM_STATUS_CHANNEL, PERFORMANCE_UPDATE_CHANNEL
            )
            logger.info(
                f"Re-established pub/sub subscription on channels: {SYSTEM_STATUS_CHANNEL}, "
                f"{PERFORMANCE_UPDATE_CHANNEL}"
            )
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Redis connection failures and asyncio issues
            logger.error(f"Failed to re-subscribe during reset: {e}", exc_info=True)
            self._pubsub = None

    async def _listen_for_updates(self) -> None:
        """Listen for system status updates from Redis pub/sub.

        Forwards received messages to all locally connected WebSocket clients.

        Recovery from errors is bounded to MAX_RECOVERY_ATTEMPTS to prevent
        unbounded recursion and stack overflow.
        """
        if not self._pubsub:
            logger.error("Cannot listen: pubsub not initialized")
            return

        redis_client = self._get_redis()
        if not redis_client:
            logger.error("Cannot listen: Redis client not available")
            return

        logger.info("Starting pub/sub listener loop")

        try:
            async for message in redis_client.listen(self._pubsub):
                if not self._pubsub_listening:
                    break

                # Reset recovery attempts and record success on message processing
                self._recovery_attempts = 0
                self._circuit_breaker.record_success()

                # Extract the wrapped message data
                wrapped_data = message.get("data")
                if not wrapped_data:
                    continue

                # Check if this message originated from this instance
                # If so, skip it (we already sent directly to local clients)
                if isinstance(wrapped_data, dict):
                    origin_instance = wrapped_data.get("_origin_instance")
                    if origin_instance == self._instance_id:
                        logger.debug("Skipping message from self (already sent directly)")
                        continue

                    # Extract the actual payload
                    status_data = wrapped_data.get("payload")
                    if not status_data:
                        # Handle legacy format (no wrapper)
                        status_data = wrapped_data
                else:
                    # Handle non-dict data (legacy format)
                    status_data = wrapped_data

                logger.debug(f"Received update from Redis (remote instance): {type(status_data)}")

                # Forward to local WebSocket clients (from remote instance)
                await self._send_to_local_clients(status_data)

        except asyncio.CancelledError:
            logger.info("Pub/sub listener cancelled")
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Redis connection failures and asyncio issues
            logger.error(f"Error in pub/sub listener: {e}", exc_info=True)
            # Record failure in circuit breaker
            self._circuit_breaker.record_failure()
            await self._attempt_listener_recovery()

    async def _attempt_listener_recovery(self) -> None:
        """Attempt to recover the pub/sub listener with exponential backoff and jitter.

        This helper method is extracted to reduce branch complexity in
        _listen_for_updates(). Recovery is bounded to MAX_RECOVERY_ATTEMPTS
        to prevent unbounded recursion and stack overflow. Also checks
        circuit breaker state before attempting recovery.

        Uses exponential backoff with jitter to prevent thundering herd problems
        when multiple instances attempt to recover simultaneously.
        """
        if not self._pubsub_listening:
            return

        self._recovery_attempts += 1

        # Check circuit breaker before attempting recovery
        if not self._circuit_breaker.is_call_permitted():
            logger.error(
                "Pub/sub listener circuit breaker is OPEN - "
                "recovery blocked to allow system stabilization"
            )
            self._pubsub_listening = False
            self._is_degraded = True  # Enter degraded mode
            # Broadcast degraded state to connected clients
            await self._broadcast_degraded_state()
            return

        if self._recovery_attempts > self.MAX_RECOVERY_ATTEMPTS:
            logger.error(
                f"Pub/sub listener recovery failed after {self.MAX_RECOVERY_ATTEMPTS} "
                "attempts. Giving up - manual restart required."
            )
            self._pubsub_listening = False
            self._is_degraded = True  # Enter degraded mode
            # Broadcast degraded state to connected clients
            await self._broadcast_degraded_state()
            return

        # Calculate exponential backoff with jitter to prevent thundering herd
        # Base delay starts at 1 second, doubles each attempt, capped at 60 seconds
        base_delay = 1.0
        max_delay = 60.0
        delay = min(base_delay * (2 ** (self._recovery_attempts - 1)), max_delay)
        # Add 10-30% jitter to prevent synchronized recovery attempts
        # Using random.uniform is fine here - this is timing jitter, not cryptographic
        jitter = delay * random.uniform(0.1, 0.3)  # noqa: S311
        actual_delay = delay + jitter

        logger.info(
            f"Restarting pub/sub listener after error "
            f"(attempt {self._recovery_attempts}/{self.MAX_RECOVERY_ATTEMPTS}) "
            f"in {actual_delay:.1f}s"
        )
        await asyncio.sleep(actual_delay)

        if not self._pubsub_listening:
            return

        # Clean up old pubsub and create fresh subscription
        await self._reset_pubsub_connection()
        if self._pubsub:
            self._circuit_breaker.record_success()
            self._listener_task = asyncio.create_task(self._listen_for_updates())
        else:
            logger.error("Failed to re-establish pub/sub connection")
            self._circuit_breaker.record_failure()
            self._pubsub_listening = False
            self._is_degraded = True  # Enter degraded mode
            await self._broadcast_degraded_state()

    async def _get_system_status(self) -> dict:
        """Gather current system status data.

        Uses a single database session for all queries to avoid connection pool
        exhaustion. This is critical for high-frequency status broadcasts.

        Returns:
            Dictionary containing system status information:
            - type: "system_status"
            - data: System metrics (GPU, cameras, queue, health)
            - timestamp: ISO format timestamp
        """
        # Use a single database session for all queries to prevent connection
        # pool exhaustion when broadcasting at high frequency
        try:
            async with get_session() as session:
                gpu_stats = await self._get_latest_gpu_stats_with_session(session)
                camera_stats = await self._get_camera_stats_with_session(session)
                health_status = "healthy"  # Database is healthy if we got here
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Database connection failures and query errors
            logger.error(f"Failed to get system status from database: {e}", exc_info=True)
            gpu_stats = {
                "utilization": None,
                "memory_used": None,
                "memory_total": None,
                "temperature": None,
                "inference_fps": None,
            }
            camera_stats = {"active": 0, "total": 0}
            health_status = "unhealthy"

        # Get queue stats (Redis, not database)
        queue_stats = await self._get_queue_stats()

        # Check Redis health separately
        redis_healthy = await self._check_redis_health()
        if health_status == "healthy" and not redis_healthy:
            health_status = "degraded"

        # Check AI services health - this is critical for accurate status reporting
        # If Nemotron is unhealthy, events will show "LLM service error"
        ai_health = await self._check_ai_health()

        # Determine AI status string for the health response
        if ai_health["all_healthy"]:
            ai_status = "healthy"
        elif ai_health["any_healthy"]:
            ai_status = "degraded"
        else:
            ai_status = "unhealthy"

        # If AI services are not all healthy and overall is currently healthy,
        # degrade the overall status to reflect AI issues
        if health_status == "healthy" and not ai_health["all_healthy"]:
            health_status = "degraded"

        return {
            "type": "system_status",
            "data": {
                "gpu": gpu_stats,
                "cameras": camera_stats,
                "queue": queue_stats,
                "health": health_status,
                "ai": {
                    "status": ai_status,
                    "rtdetr": "healthy" if ai_health["rtdetr"] else "unhealthy",
                    "nemotron": "healthy" if ai_health["nemotron"] else "unhealthy",
                },
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def _get_latest_gpu_stats_with_session(self, session: AsyncSession) -> dict:
        """Get latest GPU statistics using provided database session.

        Args:
            session: Active database session

        Returns:
            Dictionary with GPU stats (utilization, memory, etc.)
            Returns null values if no data available.
        """
        try:
            stmt = select(GPUStats).order_by(GPUStats.recorded_at.desc()).limit(1)
            result = await session.execute(stmt)
            gpu_stat = result.scalar_one_or_none()

            if gpu_stat is None:
                return {
                    "utilization": None,
                    "memory_used": None,
                    "memory_total": None,
                    "temperature": None,
                    "inference_fps": None,
                }

            return {
                "utilization": gpu_stat.gpu_utilization,
                "memory_used": gpu_stat.memory_used,
                "memory_total": gpu_stat.memory_total,
                "temperature": gpu_stat.temperature,
                "inference_fps": gpu_stat.inference_fps,
            }
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Database query failures
            logger.error(f"Failed to get GPU stats: {e}", exc_info=True)
            return {
                "utilization": None,
                "memory_used": None,
                "memory_total": None,
                "temperature": None,
                "inference_fps": None,
            }

    async def _get_latest_gpu_stats(self) -> dict:
        """Get latest GPU statistics from database.

        Deprecated: Use _get_latest_gpu_stats_with_session() with a shared session.

        Returns:
            Dictionary with GPU stats (utilization, memory, etc.)
            Returns null values if no data available.
        """
        try:
            async with get_session() as session:
                return await self._get_latest_gpu_stats_with_session(session)
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Database connection failures
            logger.error(f"Failed to get GPU stats: {e}", exc_info=True)
            return {
                "utilization": None,
                "memory_used": None,
                "memory_total": None,
                "temperature": None,
                "inference_fps": None,
            }

    async def _get_camera_stats_with_session(self, session: AsyncSession) -> dict:
        """Get camera statistics using provided database session.

        Args:
            session: Active database session

        Returns:
            Dictionary with camera counts (active, total)
        """
        try:
            # Count total cameras
            total_stmt = select(func.count()).select_from(Camera)
            total_result = await session.execute(total_stmt)
            total_cameras = total_result.scalar_one()

            # Count active cameras (status = 'online')
            active_stmt = (
                select(func.count())
                .select_from(Camera)
                .where(Camera.status == CameraStatus.ONLINE.value)
            )
            active_result = await session.execute(active_stmt)
            active_cameras = active_result.scalar_one()

            return {
                "active": active_cameras,
                "total": total_cameras,
            }
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Database query failures
            logger.error(f"Failed to get camera stats: {e}", exc_info=True)
            return {
                "active": 0,
                "total": 0,
            }

    async def _get_camera_stats(self) -> dict:
        """Get camera statistics from database.

        Deprecated: Use _get_camera_stats_with_session() with a shared session.

        Returns:
            Dictionary with camera counts (active, total)
        """
        try:
            async with get_session() as session:
                return await self._get_camera_stats_with_session(session)
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Database connection failures
            logger.error(f"Failed to get camera stats: {e}", exc_info=True)
            return {
                "active": 0,
                "total": 0,
            }

    async def _get_queue_stats(self) -> dict:
        """Get processing queue statistics from Redis.

        Returns:
            Dictionary with queue counts (pending, processing)
        """
        try:
            redis_client = self._get_redis()
            if redis_client is None:
                return {"pending": 0, "processing": 0}

            # Get detection queue length
            detection_queue_len = await redis_client.get_queue_length(DETECTION_QUEUE)

            # Get analysis queue length
            analysis_queue_len = await redis_client.get_queue_length(ANALYSIS_QUEUE)

            return {
                "pending": detection_queue_len,
                "processing": analysis_queue_len,
            }
        except (ConnectionError, TimeoutError, OSError) as e:
            # Redis connection failures
            logger.error(f"Failed to get queue stats: {e}", exc_info=True)
            return {
                "pending": 0,
                "processing": 0,
            }

    async def _check_redis_health(self) -> bool:
        """Check Redis connection health.

        Returns:
            True if Redis is healthy, False otherwise
        """
        try:
            redis_client = self._get_redis()
            if redis_client:
                await redis_client.health_check()
                return True
        except (ConnectionError, TimeoutError, OSError) as e:
            # Redis connection failures
            logger.debug(f"Redis health check failed: {e}")
        return False

    async def _check_ai_health(self) -> dict[str, bool]:
        """Check AI services (RT-DETRv2 and Nemotron) health.

        Performs concurrent health checks on both AI services to minimize
        latency in the broadcast loop. Uses a short timeout to avoid blocking.

        Returns:
            Dictionary with:
            - rtdetr: True if RT-DETRv2 is healthy
            - nemotron: True if Nemotron is healthy
            - any_healthy: True if at least one AI service is healthy
            - all_healthy: True if all AI services are healthy
        """
        settings = get_settings()
        rtdetr_healthy = False
        nemotron_healthy = False

        async def check_rtdetr() -> bool:
            try:
                async with httpx.AsyncClient(timeout=AI_HEALTH_CHECK_TIMEOUT) as client:
                    response = await client.get(f"{settings.rtdetr_url}/health")
                    return bool(response.status_code == 200)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError, OSError):
                # Network errors, timeouts, HTTP errors, and OS-level socket errors
                return False

        async def check_nemotron() -> bool:
            try:
                async with httpx.AsyncClient(timeout=AI_HEALTH_CHECK_TIMEOUT) as client:
                    response = await client.get(f"{settings.nemotron_url}/health")
                    return bool(response.status_code == 200)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError, OSError):
                # Network errors, timeouts, HTTP errors, and OS-level socket errors
                return False

        # Check both services concurrently for efficiency (NEM-1656)
        # Note: Using asyncio.gather instead of TaskGroup here because:
        # 1. These are independent operations - we want partial results even if one fails
        # 2. Each check function handles its own exceptions and returns bool
        # 3. TaskGroup would cancel the other check if one fails, which is undesirable
        try:
            rtdetr_healthy, nemotron_healthy = await asyncio.gather(
                check_rtdetr(),
                check_nemotron(),
            )
        except (asyncio.CancelledError, RuntimeError) as e:
            # asyncio.CancelledError: task cancellation during shutdown
            # RuntimeError: event loop issues
            logger.warning(f"Error during AI health check: {e}", exc_info=True)

        return {
            "rtdetr": rtdetr_healthy,
            "nemotron": nemotron_healthy,
            "any_healthy": rtdetr_healthy or nemotron_healthy,
            "all_healthy": rtdetr_healthy and nemotron_healthy,
        }

    async def _get_health_status(self) -> str:
        """Determine overall system health status.

        Deprecated: Health is now determined in _get_system_status() using
        a single database session.

        Returns:
            Health status: "healthy", "degraded", or "unhealthy"
        """
        try:
            # Check database health
            async with get_session() as session:
                await session.execute(select(func.count()).select_from(Camera))

            # Check Redis health
            redis_healthy = await self._check_redis_health()

            # Determine overall health
            if redis_healthy:
                return "healthy"
            else:
                return "degraded"

        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Database/Redis connection failures
            logger.error(f"Failed to check health status: {e}", exc_info=True)
            return "unhealthy"

    async def start_broadcasting(self, interval: float = 5.0) -> None:
        """Start periodic broadcasting of system status.

        Starts both the broadcast loop (for publishing status updates) and
        the pub/sub listener (for receiving updates from other instances).

        Args:
            interval: Seconds between broadcasts (default: 5.0)
        """
        if self._running:
            logger.warning("Broadcasting already running")
            return

        self._running = True

        # Start the pub/sub listener for multi-instance support
        await self._start_pubsub_listener()

        # Start the broadcast loop
        self._broadcast_task = asyncio.create_task(self._broadcast_loop(interval))
        logger.info(f"Started system status broadcasting (interval: {interval}s)")

    async def stop_broadcasting(self) -> None:
        """Stop periodic broadcasting of system status.

        Stops both the broadcast loop and the pub/sub listener.
        """
        self._running = False

        # Stop the broadcast loop
        if self._broadcast_task:
            self._broadcast_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._broadcast_task
            self._broadcast_task = None

        # Stop the pub/sub listener
        await self._stop_pubsub_listener()

        logger.info("Stopped system status broadcasting")

    # Aliases for context manager compatibility
    async def start(self, interval: float = 5.0) -> None:
        """Start the system broadcaster (alias for start_broadcasting).

        This alias provides a consistent interface with other services
        for use with async context managers.

        Args:
            interval: Seconds between broadcasts (default: 5.0)
        """
        await self.start_broadcasting(interval)

    async def stop(self) -> None:
        """Stop the system broadcaster (alias for stop_broadcasting).

        This alias provides a consistent interface with other services
        for use with async context managers.
        """
        await self.stop_broadcasting()

    async def __aenter__(self) -> SystemBroadcaster:
        """Async context manager entry.

        Starts the system broadcaster and returns self for use in async with statements.

        Returns:
            Self for use in the context manager block.

        Example:
            async with SystemBroadcaster(redis_client=redis) as broadcaster:
                # broadcaster is started and periodically broadcasting
                await broadcaster.connect(websocket)
            # broadcaster is automatically stopped when exiting the block
        """
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit.

        Stops the system broadcaster, ensuring cleanup even if an exception occurred.

        Args:
            exc_type: Exception type if an exception was raised, None otherwise.
            exc_val: Exception value if an exception was raised, None otherwise.
            exc_tb: Exception traceback if an exception was raised, None otherwise.
        """
        await self.stop()

    async def _broadcast_loop(self, interval: float) -> None:
        """Background task that periodically broadcasts system status and performance.

        Broadcasts two message types:
        - system_status: Basic system health information
        - performance_update: Detailed performance metrics (if PerformanceCollector configured)

        Args:
            interval: Seconds between broadcasts
        """
        while self._running:
            try:
                # Only broadcast if there are active connections
                if self.connections:
                    status_data = await self._get_system_status()
                    await self.broadcast_status(status_data)

                    # Also broadcast detailed performance metrics if collector is configured
                    await self.broadcast_performance()

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
                # Broadcast failures - continue after sleep
                logger.error(f"Error in broadcast loop: {e}", exc_info=True)
                await asyncio.sleep(interval)


# Global broadcaster instance and initialization lock
_system_broadcaster: SystemBroadcaster | None = None
_broadcaster_lock: asyncio.Lock | None = None
# Thread lock to protect initialization of _broadcaster_lock itself
_init_lock = threading.Lock()


def _get_broadcaster_lock() -> asyncio.Lock:
    """Get the broadcaster initialization lock (lazy initialization).

    This ensures the lock is created in a thread-safe manner and in the
    correct event loop context. Uses a threading lock to protect the
    initial creation of the asyncio lock, preventing race conditions
    when multiple coroutines attempt to initialize concurrently.

    Must be called from within an async context.

    Returns:
        asyncio.Lock for broadcaster initialization
    """
    global _broadcaster_lock  # noqa: PLW0603
    if _broadcaster_lock is None:
        with _init_lock:
            # Double-check after acquiring thread lock
            if _broadcaster_lock is None:
                _broadcaster_lock = asyncio.Lock()
    return _broadcaster_lock


def get_system_broadcaster(
    redis_client: RedisClient | None = None,
    redis_getter: Callable[[], RedisClient | None] | None = None,
) -> SystemBroadcaster:
    """Get the global SystemBroadcaster instance (synchronous version).

    On first call, creates a new SystemBroadcaster with the provided Redis client
    or getter. Subsequent calls return the existing singleton but will also update
    the Redis client if provided.

    Note: This is a synchronous function that does NOT start the broadcaster.
    Call start_broadcasting() separately, or use get_system_broadcaster_async()
    for automatic initialization with Redis pub/sub.

    Args:
        redis_client: Optional Redis client instance. If the singleton exists and
            this is provided, it will update the singleton's Redis client.
        redis_getter: Optional callable that returns a Redis client or None.
            Only used during initial creation of the singleton.

    Returns:
        SystemBroadcaster instance (not started)
    """
    global _system_broadcaster  # noqa: PLW0603
    if _system_broadcaster is None:
        _system_broadcaster = SystemBroadcaster(
            redis_client=redis_client,
            redis_getter=redis_getter,
        )
    elif redis_client is not None:
        # Update Redis client on existing singleton
        _system_broadcaster.set_redis_client(redis_client)
    return _system_broadcaster


async def get_system_broadcaster_async(
    redis_client: RedisClient | None = None,
    redis_getter: Callable[[], RedisClient | None] | None = None,
    interval: float = 5.0,
) -> SystemBroadcaster:
    """Get or create the global SystemBroadcaster instance (async version).

    This function is thread-safe and handles concurrent initialization
    attempts using an async lock to prevent race conditions. It also
    starts the broadcaster if not already running.

    Args:
        redis_client: Optional Redis client instance. If the singleton exists and
            this is provided, it will update the singleton's Redis client.
        redis_getter: Optional callable that returns a Redis client or None.
            Only used during initial creation of the singleton.
        interval: Seconds between status broadcasts (default: 5.0)

    Returns:
        SystemBroadcaster instance (started)
    """
    global _system_broadcaster  # noqa: PLW0603

    # Fast path: broadcaster already exists and is running
    if _system_broadcaster is not None and _system_broadcaster._running:
        if redis_client is not None:
            _system_broadcaster.set_redis_client(redis_client)
        return _system_broadcaster

    # Slow path: need to initialize with lock
    lock = _get_broadcaster_lock()
    async with lock:
        # Double-check after acquiring lock (another coroutine may have initialized)
        if _system_broadcaster is None:
            _system_broadcaster = SystemBroadcaster(
                redis_client=redis_client,
                redis_getter=redis_getter,
            )
        elif redis_client is not None:
            _system_broadcaster.set_redis_client(redis_client)

        # Start if not running
        if not _system_broadcaster._running:
            await _system_broadcaster.start_broadcasting(interval)
            logger.info("Global system broadcaster initialized and started")

    return _system_broadcaster


async def stop_system_broadcaster() -> None:
    """Stop the global system broadcaster instance.

    This function is thread-safe and handles concurrent stop attempts.
    """
    global _system_broadcaster  # noqa: PLW0603

    lock = _get_broadcaster_lock()
    async with lock:
        if _system_broadcaster:
            await _system_broadcaster.stop_broadcasting()
            _system_broadcaster = None
            logger.info("Global system broadcaster stopped")


def reset_broadcaster_state() -> None:
    """Reset the global broadcaster state for testing purposes.

    This function is NOT thread-safe and should only be used in test
    fixtures to ensure clean state between tests. It resets both the
    broadcaster instance and the asyncio lock.

    Warning: Only use this in test teardown, never in production code.
    """
    global _system_broadcaster, _broadcaster_lock  # noqa: PLW0603
    _system_broadcaster = None
    _broadcaster_lock = None


# Alias for explicit sync usage in tests and imports
get_system_broadcaster_sync = get_system_broadcaster
