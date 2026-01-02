"""Redis connection and operations module."""

import asyncio
import contextlib
import json
import random
import ssl
import warnings
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar, cast

from redis.asyncio import ConnectionPool, Redis
from redis.asyncio.client import PubSub
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from backend.core.config import get_settings
from backend.core.constants import get_dlq_overflow_name
from backend.core.logging import get_logger
from backend.core.metrics import (
    record_queue_items_dropped,
    record_queue_items_moved_to_dlq,
    record_queue_items_rejected,
    record_queue_overflow,
)

logger = get_logger(__name__)

T = TypeVar("T")


class QueueOverflowPolicy(str, Enum):
    """Policy for handling queue overflow."""

    REJECT = "reject"  # Return error when queue is full
    DLQ = "dlq"  # Move oldest items to dead-letter queue before adding
    DROP_OLDEST = "drop_oldest"  # Trim oldest with warning (legacy behavior)


@dataclass
class QueueAddResult:
    """Result of adding an item to a queue with backpressure handling."""

    success: bool
    queue_length: int
    dropped_count: int = 0
    moved_to_dlq_count: int = 0
    error: str | None = None
    warning: str | None = None

    @property
    def had_backpressure(self) -> bool:
        """Return True if backpressure was applied."""
        return self.dropped_count > 0 or self.moved_to_dlq_count > 0 or self.error is not None


@dataclass
class QueuePressureMetrics:
    """Metrics about queue pressure and health."""

    queue_name: str
    current_length: int
    max_size: int
    fill_ratio: float
    is_at_pressure_threshold: bool
    is_full: bool
    overflow_policy: str


class RedisClient:
    """Async Redis client with connection pooling, SSL/TLS support, and helper methods."""

    def __init__(
        self,
        redis_url: str | None = None,
        ssl_enabled: bool | None = None,
        ssl_cert_reqs: str | None = None,
        ssl_ca_certs: str | None = None,
        ssl_certfile: str | None = None,
        ssl_keyfile: str | None = None,
        ssl_check_hostname: bool | None = None,
    ):
        """Initialize Redis client with connection pool and optional SSL/TLS.

        Args:
            redis_url: Redis connection URL. If not provided, uses settings.
            ssl_enabled: Enable SSL/TLS encryption. If None, uses settings.
            ssl_cert_reqs: SSL certificate verification mode ('none', 'optional', 'required').
                If None, uses settings.
            ssl_ca_certs: Path to CA certificate file for server verification.
                If None, uses settings.
            ssl_certfile: Path to client certificate file for mTLS. If None, uses settings.
            ssl_keyfile: Path to client key file for mTLS. If None, uses settings.
            ssl_check_hostname: Verify server certificate hostname. If None, uses settings.
        """
        settings = get_settings()
        self._redis_url = redis_url or settings.redis_url
        self._pool: ConnectionPool | None = None
        self._client: Redis | None = None
        self._pubsub: PubSub | None = None
        self._max_retries = 3
        # Exponential backoff settings
        self._base_delay = 1.0  # Base delay in seconds
        self._max_delay = 30.0  # Maximum delay cap in seconds
        self._jitter_factor = 0.25  # Random jitter 0-25% of delay

        # SSL/TLS settings - use provided values or fall back to settings
        self._ssl_enabled = ssl_enabled if ssl_enabled is not None else settings.redis_ssl_enabled
        self._ssl_cert_reqs = (
            ssl_cert_reqs if ssl_cert_reqs is not None else settings.redis_ssl_cert_reqs
        )
        self._ssl_ca_certs = (
            ssl_ca_certs if ssl_ca_certs is not None else settings.redis_ssl_ca_certs
        )
        self._ssl_certfile = (
            ssl_certfile if ssl_certfile is not None else settings.redis_ssl_certfile
        )
        self._ssl_keyfile = ssl_keyfile if ssl_keyfile is not None else settings.redis_ssl_keyfile
        self._ssl_check_hostname = (
            ssl_check_hostname
            if ssl_check_hostname is not None
            else settings.redis_ssl_check_hostname
        )

    def _create_ssl_context(self) -> ssl.SSLContext | None:
        """Create an SSL context for Redis connection if SSL is enabled.

        Returns:
            ssl.SSLContext if SSL is enabled, None otherwise.

        Raises:
            FileNotFoundError: If specified certificate files don't exist.
            ssl.SSLError: If there's an error creating the SSL context.
        """
        if not self._ssl_enabled:
            return None

        # Map cert_reqs string to ssl constant
        cert_reqs_map = {
            "none": ssl.CERT_NONE,
            "optional": ssl.CERT_OPTIONAL,
            "required": ssl.CERT_REQUIRED,
        }
        cert_reqs = cert_reqs_map.get(self._ssl_cert_reqs, ssl.CERT_REQUIRED)

        # Create SSL context
        ssl_context = ssl.create_default_context()

        # Important: check_hostname must be set before verify_mode when using CERT_NONE
        # because Python's ssl module doesn't allow check_hostname=True with CERT_NONE
        if cert_reqs == ssl.CERT_NONE:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = cert_reqs
        else:
            ssl_context.check_hostname = self._ssl_check_hostname
            ssl_context.verify_mode = cert_reqs

        # Load CA certificates for server verification
        if self._ssl_ca_certs:
            ca_path = Path(self._ssl_ca_certs)
            if not ca_path.exists():
                raise FileNotFoundError(
                    f"Redis SSL CA certificate file not found: {self._ssl_ca_certs}"
                )
            ssl_context.load_verify_locations(cafile=str(ca_path))
            logger.debug(f"Loaded Redis SSL CA certificate from: {self._ssl_ca_certs}")

        # Load client certificate for mutual TLS (mTLS)
        if self._ssl_certfile:
            cert_path = Path(self._ssl_certfile)
            if not cert_path.exists():
                raise FileNotFoundError(
                    f"Redis SSL client certificate file not found: {self._ssl_certfile}"
                )

            key_path = None
            if self._ssl_keyfile:
                key_path_obj = Path(self._ssl_keyfile)
                if not key_path_obj.exists():
                    raise FileNotFoundError(
                        f"Redis SSL client key file not found: {self._ssl_keyfile}"
                    )
                key_path = str(key_path_obj)

            ssl_context.load_cert_chain(certfile=str(cert_path), keyfile=key_path)
            logger.debug(f"Loaded Redis SSL client certificate from: {self._ssl_certfile}")

        return ssl_context

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter.

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in seconds with exponential backoff and random jitter
        """
        # Exponential backoff: base_delay * 2^(attempt-1), capped at max_delay
        delay: float = min(self._base_delay * (2 ** (attempt - 1)), self._max_delay)
        # Add random jitter (0-25% of delay) - not cryptographic, just for retry timing
        jitter: float = delay * random.uniform(0, self._jitter_factor)  # noqa: S311
        return delay + jitter

    async def with_retry(
        self,
        operation: Callable[[], Awaitable[T]],
        operation_name: str = "redis_operation",
        max_retries: int | None = None,
    ) -> T:
        """Execute a Redis operation with exponential backoff retry logic.

        This method handles transient Redis failures (connection errors, timeouts)
        by retrying with exponential backoff. It should be used for critical Redis
        operations in pipeline workers to handle connection failures gracefully.

        Args:
            operation: Async callable that performs the Redis operation
            operation_name: Name of the operation for logging
            max_retries: Maximum retry attempts (default: self._max_retries)

        Returns:
            The result of the operation

        Raises:
            ConnectionError: If all retries are exhausted due to connection failure
            TimeoutError: If all retries are exhausted due to timeout
            RedisError: If all retries are exhausted due to Redis error
        """
        retries = max_retries if max_retries is not None else self._max_retries
        last_error: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                return await operation()
            except (ConnectionError, TimeoutError, RedisError) as e:
                last_error = e
                logger.warning(
                    f"Redis {operation_name} attempt {attempt}/{retries} failed: {e}",
                    extra={
                        "operation": operation_name,
                        "attempt": attempt,
                        "max_retries": retries,
                        "error_type": type(e).__name__,
                    },
                )
                if attempt < retries:
                    backoff_delay = self._calculate_backoff_delay(attempt)
                    logger.debug(
                        f"Retrying {operation_name} in {backoff_delay:.2f} seconds...",
                        extra={
                            "operation": operation_name,
                            "delay_seconds": backoff_delay,
                            "next_attempt": attempt + 1,
                        },
                    )
                    await asyncio.sleep(backoff_delay)

        # All retries exhausted
        logger.error(
            f"Redis {operation_name} failed after {retries} retries",
            extra={
                "operation": operation_name,
                "max_retries": retries,
                "error": str(last_error),
            },
        )
        if last_error:
            raise last_error
        raise RuntimeError(f"Redis {operation_name} failed without error (should not happen)")

    async def get_from_queue_with_retry(
        self,
        queue_name: str,
        timeout: int = 0,
        max_retries: int | None = None,
    ) -> Any | None:
        """Get item from queue with retry logic for Redis failures.

        This is a retry-enabled version of get_from_queue() that handles
        transient Redis connection failures with exponential backoff.

        Args:
            queue_name: Name of the queue (Redis list key)
            timeout: Timeout in seconds for BLPOP. If 0 or less than minimum (5s),
                the minimum timeout is used to prevent indefinite blocking.
            max_retries: Maximum retry attempts (default: self._max_retries)

        Returns:
            Deserialized item from the queue, or None if timeout

        Raises:
            ConnectionError: If all retries are exhausted due to connection failure
            TimeoutError: If all retries are exhausted due to timeout
            RedisError: If all retries are exhausted due to Redis error
        """
        return await self.with_retry(
            operation=lambda: self.get_from_queue(queue_name, timeout),
            operation_name=f"get_from_queue({queue_name})",
            max_retries=max_retries,
        )

    async def get_queue_length_with_retry(
        self,
        queue_name: str,
        max_retries: int | None = None,
    ) -> int:
        """Get queue length with retry logic for Redis failures.

        This is a retry-enabled version of get_queue_length() that handles
        transient Redis connection failures with exponential backoff.

        Args:
            queue_name: Name of the queue (Redis list key)
            max_retries: Maximum retry attempts (default: self._max_retries)

        Returns:
            Number of items in the queue

        Raises:
            ConnectionError: If all retries are exhausted due to connection failure
            TimeoutError: If all retries are exhausted due to timeout
            RedisError: If all retries are exhausted due to Redis error
        """
        return await self.with_retry(
            operation=lambda: self.get_queue_length(queue_name),
            operation_name=f"get_queue_length({queue_name})",
            max_retries=max_retries,
        )

    async def get_with_retry(
        self,
        key: str,
        max_retries: int | None = None,
    ) -> Any | None:
        """Get value from Redis with retry logic for failures.

        This is a retry-enabled version of get() that handles
        transient Redis connection failures with exponential backoff.

        Args:
            key: Cache key
            max_retries: Maximum retry attempts (default: self._max_retries)

        Returns:
            Deserialized value or None if key doesn't exist

        Raises:
            ConnectionError: If all retries are exhausted due to connection failure
            TimeoutError: If all retries are exhausted due to timeout
            RedisError: If all retries are exhausted due to Redis error
        """
        return await self.with_retry(
            operation=lambda: self.get(key),
            operation_name=f"get({key})",
            max_retries=max_retries,
        )

    async def set_with_retry(
        self,
        key: str,
        value: Any,
        expire: int | None = None,
        max_retries: int | None = None,
    ) -> bool:
        """Set value in Redis with retry logic for failures.

        This is a retry-enabled version of set() that handles
        transient Redis connection failures with exponential backoff.

        Args:
            key: Cache key
            value: Value to store
            expire: Expiration time in seconds (optional)
            max_retries: Maximum retry attempts (default: self._max_retries)

        Returns:
            True if successful

        Raises:
            ConnectionError: If all retries are exhausted due to connection failure
            TimeoutError: If all retries are exhausted due to timeout
            RedisError: If all retries are exhausted due to Redis error
        """
        return await self.with_retry(
            operation=lambda: self.set(key, value, expire),
            operation_name=f"set({key})",
            max_retries=max_retries,
        )

    async def add_to_queue_safe_with_retry(
        self,
        queue_name: str,
        data: Any,
        max_size: int | None = None,
        overflow_policy: QueueOverflowPolicy | str | None = None,
        dlq_name: str | None = None,
        max_retries: int | None = None,
    ) -> QueueAddResult:
        """Add item to queue with retry logic for Redis failures.

        This is a retry-enabled version of add_to_queue_safe() that handles
        transient Redis connection failures with exponential backoff.

        Args:
            queue_name: Name of the queue (Redis list key)
            data: Data to add
            max_size: Maximum queue size
            overflow_policy: Policy for handling overflow
            dlq_name: DLQ name for 'dlq' policy
            max_retries: Maximum retry attempts (default: self._max_retries)

        Returns:
            QueueAddResult with success status and metrics

        Raises:
            ConnectionError: If all retries are exhausted due to connection failure
            TimeoutError: If all retries are exhausted due to timeout
            RedisError: If all retries are exhausted due to Redis error
        """
        return await self.with_retry(
            operation=lambda: self.add_to_queue_safe(
                queue_name, data, max_size, overflow_policy, dlq_name
            ),
            operation_name=f"add_to_queue_safe({queue_name})",
            max_retries=max_retries,
        )

    async def connect(self) -> None:
        """Establish Redis connection with exponential backoff retry logic and optional SSL/TLS."""
        # Create SSL context if SSL is enabled
        ssl_context = self._create_ssl_context()

        # Log SSL status
        if ssl_context:
            logger.info(
                "Redis SSL/TLS enabled",
                extra={
                    "ssl_cert_reqs": self._ssl_cert_reqs,
                    "ssl_check_hostname": self._ssl_check_hostname,
                    "ssl_ca_certs": self._ssl_ca_certs is not None,
                    "ssl_client_cert": self._ssl_certfile is not None,
                },
            )

        for attempt in range(1, self._max_retries + 1):
            try:
                # Build connection pool kwargs
                pool_kwargs: dict[str, Any] = {
                    "encoding": "utf-8",
                    "decode_responses": True,
                    "socket_connect_timeout": 5,
                    "socket_keepalive": True,
                    "health_check_interval": 30,
                    "max_connections": 10,
                }

                # Add SSL context if enabled
                if ssl_context:
                    pool_kwargs["ssl"] = ssl_context

                self._pool = ConnectionPool.from_url(
                    self._redis_url,
                    **pool_kwargs,
                )
                self._client = Redis(connection_pool=self._pool)
                # Test connection
                await self._client.ping()  # type: ignore
                ssl_msg = " with SSL/TLS" if ssl_context else ""
                logger.info(f"Successfully connected to Redis{ssl_msg}")
                return
            except (ConnectionError, TimeoutError) as e:
                logger.warning(
                    f"Redis connection attempt {attempt}/{self._max_retries} failed: {e}"
                )
                if attempt < self._max_retries:
                    backoff_delay = self._calculate_backoff_delay(attempt)
                    logger.info(f"Retrying in {backoff_delay:.2f} seconds...")
                    await asyncio.sleep(backoff_delay)
                else:
                    logger.error("Failed to connect to Redis after all retries")
                    raise

    async def disconnect(self) -> None:
        """Close Redis connection and cleanup resources."""
        with contextlib.suppress(Exception):
            if self._pubsub:
                await self._pubsub.aclose()
                self._pubsub = None

            if self._client:
                await self._client.aclose()
                self._client = None

            if self._pool:
                await self._pool.disconnect()
                self._pool = None

            logger.info("Redis connection closed")

    def _ensure_connected(self) -> Redis:
        """Ensure Redis client is connected.

        Returns:
            Redis client instance

        Raises:
            RuntimeError: If client is not connected
        """
        if not self._client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    async def health_check(self) -> dict[str, Any]:
        """Check Redis connection health.

        Returns:
            Dictionary with health status information
        """
        try:
            client = self._ensure_connected()
            await client.ping()  # type: ignore
            info = await client.info("server")  # type: ignore
            return {
                "status": "healthy",
                "connected": True,
                "redis_version": info.get("redis_version", "unknown"),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
            }

    # Queue operations

    async def add_to_queue(self, queue_name: str, data: Any, max_size: int = 10000) -> int:
        """Add item to the end of a queue (RPUSH) with optional size limit.

        .. deprecated:: 1.0.0
            This method uses legacy behavior that can silently drop items.
            Use :meth:`add_to_queue_safe` instead for proper backpressure handling.

        Args:
            queue_name: Name of the queue (Redis list key)
            data: Data to add (will be JSON-serialized if not a string)
            max_size: Maximum queue size (default 10000). After RPUSH, queue is
                trimmed to keep only the last max_size items (newest). Set to 0
                to disable trimming.

        Returns:
            Length of the queue after adding the item

        Note:
            This method is deprecated and will be removed in a future version.
            Migrate to add_to_queue_safe() for production use.
        """
        warnings.warn(
            "add_to_queue() is deprecated and can silently drop data. "
            "Use add_to_queue_safe() with an explicit overflow_policy instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        client = self._ensure_connected()
        serialized = json.dumps(data) if not isinstance(data, str) else data
        result = cast("int", await client.rpush(queue_name, serialized))  # type: ignore[misc]
        # Trim to max_size (keep newest items)
        if max_size > 0:
            # Calculate and log any dropped items
            if result > max_size:
                dropped_count = result - max_size
                logger.warning(
                    f"Queue '{queue_name}' overflow: trimming {dropped_count} oldest items "
                    f"(queue size {result} exceeds max {max_size}). "
                    "Consider using add_to_queue_safe() for proper backpressure handling.",
                    extra={
                        "queue_name": queue_name,
                        "queue_length": result,
                        "max_size": max_size,
                        "dropped_count": dropped_count,
                    },
                )
            await client.ltrim(queue_name, -max_size, -1)  # type: ignore[misc]
        return result

    async def add_to_queue_safe(  # noqa: PLR0912
        self,
        queue_name: str,
        data: Any,
        max_size: int | None = None,
        overflow_policy: QueueOverflowPolicy | str | None = None,
        dlq_name: str | None = None,
    ) -> QueueAddResult:
        """Add item to queue with proper backpressure handling.

        This method never silently drops data. Based on the overflow policy:
        - REJECT: Returns error if queue is full, item is NOT added
        - DLQ: Moves oldest items to dead-letter queue before adding
        - DROP_OLDEST: Logs warning and trims (legacy behavior with visibility)

        Args:
            queue_name: Name of the queue (Redis list key)
            data: Data to add (will be JSON-serialized if not a string)
            max_size: Maximum queue size. If None, uses settings.queue_max_size
            overflow_policy: Policy for handling overflow. If None, uses settings
            dlq_name: DLQ name for 'dlq' policy. Defaults to f"dlq:overflow:{queue_name}"

        Returns:
            QueueAddResult with success status and metrics
        """
        settings = get_settings()
        client = self._ensure_connected()

        # Apply defaults from settings
        if max_size is None:
            max_size = settings.queue_max_size
        if overflow_policy is None:
            overflow_policy = settings.queue_overflow_policy

        # Normalize policy to enum
        if isinstance(overflow_policy, str):
            try:
                overflow_policy = QueueOverflowPolicy(overflow_policy.lower())
            except ValueError:
                overflow_policy = QueueOverflowPolicy.REJECT

        # Default DLQ name
        if dlq_name is None:
            dlq_name = get_dlq_overflow_name(queue_name)

        serialized = json.dumps(data) if not isinstance(data, str) else data

        # Check current queue length
        current_length = cast("int", await client.llen(queue_name))  # type: ignore[misc]

        # Log warning if approaching threshold
        pressure_threshold = settings.queue_backpressure_threshold
        fill_ratio = current_length / max_size if max_size > 0 else 0
        if fill_ratio >= pressure_threshold:
            logger.warning(
                f"Queue '{queue_name}' pressure warning: {fill_ratio:.1%} full "
                f"({current_length}/{max_size})",
                extra={
                    "queue_name": queue_name,
                    "current_length": current_length,
                    "max_size": max_size,
                    "fill_ratio": fill_ratio,
                    "threshold": pressure_threshold,
                },
            )

        # Handle overflow based on policy
        if current_length >= max_size > 0:
            if overflow_policy == QueueOverflowPolicy.REJECT:
                error_msg = (
                    f"Queue '{queue_name}' is full ({current_length}/{max_size}). "
                    "Item rejected to prevent data loss."
                )
                logger.error(
                    error_msg,
                    extra={
                        "queue_name": queue_name,
                        "current_length": current_length,
                        "max_size": max_size,
                        "policy": overflow_policy.value,
                    },
                )
                # Record metrics for queue overflow
                record_queue_overflow(queue_name, overflow_policy.value)
                record_queue_items_rejected(queue_name)
                return QueueAddResult(
                    success=False,
                    queue_length=current_length,
                    error=error_msg,
                )

            elif overflow_policy == QueueOverflowPolicy.DLQ:
                # Move oldest item to DLQ before adding new one
                moved_count = 0
                items_to_move = (current_length - max_size) + 1  # +1 for the new item

                for _ in range(items_to_move):
                    # Pop from front of queue (oldest item)
                    oldest_item = await client.lpop(queue_name)  # type: ignore[misc]
                    if oldest_item:
                        # Add to DLQ with metadata
                        dlq_entry = {
                            "original_queue": queue_name,
                            "data": oldest_item,
                            "reason": "queue_overflow",
                            "overflow_policy": overflow_policy.value,
                        }
                        await client.rpush(dlq_name, json.dumps(dlq_entry))  # type: ignore[misc]
                        moved_count += 1

                if moved_count > 0:
                    logger.warning(
                        f"Queue '{queue_name}' overflow: moved {moved_count} oldest items "
                        f"to DLQ '{dlq_name}'",
                        extra={
                            "queue_name": queue_name,
                            "dlq_name": dlq_name,
                            "moved_count": moved_count,
                            "policy": overflow_policy.value,
                        },
                    )
                    # Record metrics for queue overflow
                    record_queue_overflow(queue_name, overflow_policy.value)
                    record_queue_items_moved_to_dlq(queue_name, moved_count)

                # Now add the new item
                new_length = cast("int", await client.rpush(queue_name, serialized))  # type: ignore[misc]

                return QueueAddResult(
                    success=True,
                    queue_length=new_length,
                    moved_to_dlq_count=moved_count,
                    warning=f"Moved {moved_count} items to DLQ due to overflow",
                )

            elif overflow_policy == QueueOverflowPolicy.DROP_OLDEST:
                # Add item then trim with explicit warning
                result = cast("int", await client.rpush(queue_name, serialized))  # type: ignore[misc]
                dropped_count = max(0, result - max_size)

                if dropped_count > 0:
                    logger.warning(
                        f"Queue '{queue_name}' overflow: dropping {dropped_count} oldest items "
                        f"(policy: {overflow_policy.value})",
                        extra={
                            "queue_name": queue_name,
                            "queue_length": result,
                            "max_size": max_size,
                            "dropped_count": dropped_count,
                            "policy": overflow_policy.value,
                        },
                    )
                    await client.ltrim(queue_name, -max_size, -1)  # type: ignore[misc]
                    # Record metrics for queue overflow
                    record_queue_overflow(queue_name, overflow_policy.value)
                    record_queue_items_dropped(queue_name, dropped_count)

                return QueueAddResult(
                    success=True,
                    queue_length=min(result, max_size),
                    dropped_count=dropped_count,
                    warning=f"Dropped {dropped_count} oldest items due to overflow"
                    if dropped_count > 0
                    else None,
                )

        # Normal case: queue has space
        new_length = cast("int", await client.rpush(queue_name, serialized))  # type: ignore[misc]

        return QueueAddResult(
            success=True,
            queue_length=new_length,
        )

    # Default timeout for monitoring operations (5 seconds)
    # Prevents indefinite hangs if Redis is slow or unresponsive
    _MONITORING_TIMEOUT: float = 5.0

    async def get_queue_pressure(
        self,
        queue_name: str,
        max_size: int | None = None,
        timeout: float | None = None,
    ) -> QueuePressureMetrics:
        """Get metrics about queue pressure and health.

        Wraps the queue length check in a timeout to prevent hangs if Redis
        is slow or unresponsive.

        Args:
            queue_name: Name of the queue to check
            max_size: Maximum queue size. If None, uses settings.queue_max_size
            timeout: Timeout in seconds for the Redis operation.
                If None, uses _MONITORING_TIMEOUT (5s).

        Returns:
            QueuePressureMetrics with current queue status

        Raises:
            asyncio.TimeoutError: If the queue length check exceeds the timeout
        """
        settings = get_settings()
        effective_timeout = timeout if timeout is not None else self._MONITORING_TIMEOUT

        if max_size is None:
            max_size = settings.queue_max_size

        # Wrap in asyncio.wait_for to prevent indefinite hangs
        current_length = await asyncio.wait_for(
            self.get_queue_length(queue_name),
            timeout=effective_timeout,
        )
        fill_ratio = current_length / max_size if max_size > 0 else 0

        return QueuePressureMetrics(
            queue_name=queue_name,
            current_length=current_length,
            max_size=max_size,
            fill_ratio=fill_ratio,
            is_at_pressure_threshold=fill_ratio >= settings.queue_backpressure_threshold,
            is_full=current_length >= max_size,
            overflow_policy=settings.queue_overflow_policy,
        )

    # Minimum timeout for BLPOP to prevent indefinite blocking
    # This ensures workers can check their shutdown flags periodically
    _MIN_BLPOP_TIMEOUT: int = 5

    async def get_from_queue(self, queue_name: str, timeout: int = 0) -> Any | None:
        """Get item from the front of a queue (BLPOP).

        Args:
            queue_name: Name of the queue (Redis list key)
            timeout: Timeout in seconds. If 0 or less than minimum (5s),
                the minimum timeout is used to prevent indefinite blocking.
                This ensures workers can periodically check their shutdown flags.

        Returns:
            Deserialized item from the queue, or None if timeout
        """
        client = self._ensure_connected()
        # Enforce minimum timeout to prevent indefinite blocking
        # This is critical for graceful shutdown - workers need to periodically
        # check their _running flag even when the queue is empty
        effective_timeout = max(timeout, self._MIN_BLPOP_TIMEOUT) if timeout <= 0 else timeout
        effective_timeout = max(effective_timeout, self._MIN_BLPOP_TIMEOUT)
        result = await client.blpop([queue_name], timeout=effective_timeout)  # type: ignore[misc]
        if result:
            _, value = result
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def pop_from_queue_nonblocking(self, queue_name: str) -> Any | None:
        """Non-blocking pop from the front of a queue (LPOP).

        Unlike get_from_queue() which uses BLPOP with a minimum timeout,
        this method returns immediately if the queue is empty.

        Use this for operations that need instant response without blocking,
        such as DLQ requeue operations.

        Args:
            queue_name: Name of the queue (Redis list key)

        Returns:
            Deserialized item from the queue, or None if queue is empty
        """
        client = self._ensure_connected()
        result = await client.lpop(queue_name)  # type: ignore[misc]
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return result
        return None

    async def get_queue_length(self, queue_name: str) -> int:
        """Get the length of a queue (LLEN).

        Args:
            queue_name: Name of the queue (Redis list key)

        Returns:
            Number of items in the queue
        """
        client = self._ensure_connected()
        return cast("int", await client.llen(queue_name))  # type: ignore[misc]

    async def peek_queue(
        self,
        queue_name: str,
        start: int = 0,
        end: int = 100,
        max_items: int = 1000,
    ) -> list[Any]:
        """Peek at items in a queue without removing them (LRANGE).

        Args:
            queue_name: Name of the queue (Redis list key)
            start: Start index (0-based)
            end: End index (default 100, use -1 for all up to max_items)
            max_items: Hard cap on items returned (default 1000)

        Returns:
            List of deserialized items
        """
        end = max_items - 1 if end == -1 else min(end, start + max_items - 1)

        client = self._ensure_connected()
        items = cast("list[str]", await client.lrange(queue_name, start, end))  # type: ignore[misc]
        result = []
        for item in items:
            try:
                result.append(json.loads(item))
            except json.JSONDecodeError:
                result.append(item)
        return result

    async def clear_queue(self, queue_name: str) -> bool:
        """Clear all items from a queue (DELETE).

        Args:
            queue_name: Name of the queue (Redis list key)

        Returns:
            True if queue was deleted, False if it didn't exist
        """
        client = self._ensure_connected()
        result = cast("int", await client.delete(queue_name))
        return result > 0

    # Pub/Sub operations

    def get_pubsub(self) -> PubSub:
        """Get or create the shared Pub/Sub instance.

        WARNING: This returns a shared PubSub instance. For listeners that need
        a dedicated connection (to avoid 'readuntil() called while another
        coroutine is already waiting' errors), use create_pubsub() instead.

        Returns:
            Shared PubSub instance for subscribing to channels
        """
        client = self._ensure_connected()
        if not self._pubsub:
            self._pubsub = client.pubsub()
        return self._pubsub

    def create_pubsub(self) -> PubSub:
        """Create a new, dedicated PubSub instance.

        Use this method when you need a dedicated pub/sub connection that won't
        conflict with other subscribers. This is necessary when:
        - Running long-lived listeners (async iteration)
        - Multiple components need independent pub/sub connections
        - Avoiding 'readuntil() called while another coroutine is waiting' errors

        The caller is responsible for closing the returned PubSub instance
        when done (using pubsub.close()).

        Returns:
            New PubSub instance (caller owns this and must close it)
        """
        client = self._ensure_connected()
        return client.pubsub()

    async def publish(self, channel: str, message: Any) -> int:
        """Publish a message to a channel.

        Args:
            channel: Channel name
            message: Message to publish (will be JSON-serialized if not a string)

        Returns:
            Number of subscribers that received the message
        """
        client = self._ensure_connected()
        serialized = json.dumps(message) if not isinstance(message, str) else message
        return cast("int", await client.publish(channel, serialized))

    async def subscribe(self, *channels: str) -> PubSub:
        """Subscribe to one or more channels using the shared PubSub instance.

        WARNING: This uses a shared PubSub instance. If you need to run a
        long-lived listener, use subscribe_dedicated() instead to get a
        dedicated connection that won't conflict with other subscribers.

        Args:
            *channels: Channel names to subscribe to

        Returns:
            Shared PubSub instance for receiving messages
        """
        pubsub = self.get_pubsub()
        await pubsub.subscribe(*channels)
        return pubsub

    async def subscribe_dedicated(self, *channels: str) -> PubSub:
        """Subscribe to channels with a dedicated PubSub connection.

        Creates a new PubSub instance that won't conflict with other
        subscribers. Use this for long-lived listeners to avoid the
        'readuntil() called while another coroutine is waiting' error.

        The caller is responsible for:
        1. Keeping track of the returned PubSub instance
        2. Unsubscribing when done: await pubsub.unsubscribe(*channels)
        3. Closing the connection: await pubsub.close()

        Args:
            *channels: Channel names to subscribe to

        Returns:
            New dedicated PubSub instance (caller owns and must close)
        """
        pubsub = self.create_pubsub()
        await pubsub.subscribe(*channels)
        return pubsub

    async def unsubscribe(self, *channels: str) -> None:
        """Unsubscribe from one or more channels.

        Args:
            *channels: Channel names to unsubscribe from
        """
        if self._pubsub:
            await self._pubsub.unsubscribe(*channels)

    async def listen(self, pubsub: PubSub) -> AsyncGenerator[dict[str, Any]]:
        """Listen for messages from subscribed channels.

        Args:
            pubsub: PubSub instance to listen on

        Yields:
            Messages from subscribed channels
        """
        async for message in pubsub.listen():
            if message["type"] == "message":
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    message["data"] = json.loads(message["data"])
                yield message

    # Cache operations

    async def get(self, key: str) -> Any | None:
        """Get a value from Redis cache.

        Args:
            key: Cache key

        Returns:
            Deserialized value or None if key doesn't exist
        """
        client = self._ensure_connected()
        value = await client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        """Set a value in Redis cache.

        Args:
            key: Cache key
            value: Value to store (will be JSON-serialized if not a string)
            expire: Expiration time in seconds (optional)

        Returns:
            True if successful
        """
        client = self._ensure_connected()
        serialized = json.dumps(value) if not isinstance(value, str) else value
        return cast("bool", await client.set(key, serialized, ex=expire))

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys from Redis.

        Args:
            *keys: Keys to delete

        Returns:
            Number of keys deleted
        """
        client = self._ensure_connected()
        return cast("int", await client.delete(*keys))

    async def exists(self, *keys: str) -> int:
        """Check if one or more keys exist.

        Args:
            *keys: Keys to check

        Returns:
            Number of keys that exist
        """
        client = self._ensure_connected()
        return cast("int", await client.exists(*keys))

    async def expire(self, key: str, seconds: int) -> bool:
        """Set a TTL (time-to-live) on a key.

        Args:
            key: Key to set TTL on
            seconds: TTL in seconds

        Returns:
            True if the timeout was set, False if key doesn't exist
        """
        client = self._ensure_connected()
        return cast("bool", await client.expire(key, seconds))


# Global Redis client instance
_redis_client: RedisClient | None = None
# Lock for thread-safe initialization (prevents race conditions)
_redis_init_lock: asyncio.Lock | None = None


def _get_redis_init_lock() -> asyncio.Lock:
    """Get the Redis initialization lock (lazy initialization).

    Creates the asyncio.Lock lazily to ensure it's created in the correct
    event loop context. This function is not itself thread-safe but the
    lock usage pattern (double-check locking) ensures correct behavior.

    Returns:
        asyncio.Lock for Redis client initialization
    """
    global _redis_init_lock  # noqa: PLW0603
    if _redis_init_lock is None:
        _redis_init_lock = asyncio.Lock()
    return _redis_init_lock


async def get_redis() -> AsyncGenerator[RedisClient]:
    """FastAPI dependency for Redis client.

    Uses double-check locking pattern to prevent race conditions when
    multiple coroutines attempt to initialize the Redis client concurrently.

    Yields:
        RedisClient instance
    """
    global _redis_client  # noqa: PLW0603

    # Fast path: client already initialized
    if _redis_client is not None:
        yield _redis_client
        return

    # Slow path: acquire lock and check again
    lock = _get_redis_init_lock()
    async with lock:
        # Double-check after acquiring lock
        if _redis_client is None:
            client = RedisClient()
            await client.connect()
            _redis_client = client

    yield _redis_client


async def get_redis_optional() -> AsyncGenerator[RedisClient | None]:
    """FastAPI dependency for optional Redis client.

    This dependency is fail-soft: it returns None instead of raising an exception
    when Redis is unavailable. Use this for health check endpoints where you want
    to report Redis status rather than fail the request.

    Uses double-check locking pattern to prevent race conditions.

    Yields:
        RedisClient instance if connected, None if Redis is unavailable
    """
    global _redis_client  # noqa: PLW0603

    try:
        # Fast path: client already initialized
        if _redis_client is not None:
            yield _redis_client
            return

        # Slow path: acquire lock and check again
        lock = _get_redis_init_lock()
        async with lock:
            # Double-check after acquiring lock
            if _redis_client is None:
                client = RedisClient()
                await client.connect()
                _redis_client = client

        yield _redis_client
    except (ConnectionError, TimeoutError) as e:
        logger.warning(f"Redis unavailable (will report degraded status): {e}")
        yield None
    except Exception as e:
        # Catch any other Redis connection errors
        logger.warning(f"Redis connection error (will report degraded status): {e}")
        yield None


async def init_redis() -> RedisClient:
    """Initialize Redis client for application startup.

    Uses double-check locking pattern to prevent race conditions when
    multiple coroutines attempt to initialize the Redis client concurrently.

    Returns:
        Connected RedisClient instance
    """
    global _redis_client  # noqa: PLW0603

    # Fast path: client already initialized
    if _redis_client is not None:
        return _redis_client

    # Slow path: acquire lock and check again
    lock = _get_redis_init_lock()
    async with lock:
        # Double-check after acquiring lock
        if _redis_client is None:
            client = RedisClient()
            await client.connect()
            _redis_client = client

    return _redis_client


async def close_redis() -> None:
    """Close Redis client for application shutdown."""
    global _redis_client, _redis_init_lock  # noqa: PLW0603

    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None
    # Reset lock so it can be recreated in correct event loop on next startup
    _redis_init_lock = None
