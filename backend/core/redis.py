"""Redis connection and operations module."""

__all__ = [
    # Classes
    "QueueAddResult",
    "QueueOverflowPolicy",
    "QueuePressureMetrics",
    "RedisClient",
    # Functions
    "close_redis",
    "get_redis",
    "get_redis_client_sync",
    "get_redis_optional",
    "init_redis",
]

import asyncio
import base64
import contextlib
import json
import random
import ssl
from collections.abc import AsyncGenerator, Awaitable, Callable
from compression import zstd
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


@dataclass(slots=True)
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


@dataclass(slots=True)
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

    # Compression prefix marker for identifying compressed data
    # String prefix "Z:" to identify Zstd-compressed payloads (base64 encoded)
    # Uses string prefix since Redis connection uses decode_responses=True
    COMPRESSION_PREFIX: str = "Z:"

    def _compress_payload(self, data: str) -> str:
        """Compress a string payload using Zstd if it exceeds the compression threshold.

        Uses Python 3.14's native compression.zstd module for efficient compression.
        Payloads below the threshold are returned uncompressed to avoid overhead.

        Compression is done in the following steps:
        1. Encode string to UTF-8 bytes
        2. Compress with Zstd
        3. Base64 encode (for string storage compatibility)
        4. Prepend COMPRESSION_PREFIX marker

        Args:
            data: JSON string to potentially compress

        Returns:
            Compressed data string with COMPRESSION_PREFIX if compressed,
            or original string if below threshold, compression disabled,
            or compression doesn't reduce size
        """
        settings = get_settings()

        # Skip compression if disabled
        if not settings.redis_compression_enabled:
            return data

        # Skip compression if data is below threshold
        data_bytes = data.encode("utf-8")
        if len(data_bytes) <= settings.redis_compression_threshold:
            return data

        # Compress with Zstd
        compressed = zstd.compress(data_bytes)

        # Base64 encode for string storage compatibility
        compressed_b64 = base64.b64encode(compressed).decode("ascii")

        # Build final compressed string with prefix
        compressed_str = self.COMPRESSION_PREFIX + compressed_b64

        # Only use compression if it actually reduces size
        # (Zstd is efficient, but very small or already-compressed data may not benefit)
        if len(compressed_str) < len(data):
            return compressed_str

        return data

    def _decompress_payload(self, data: str) -> str:
        """Decompress a payload string if it has the compression prefix.

        Provides backward compatibility by detecting compressed vs uncompressed data
        using the COMPRESSION_PREFIX marker.

        Decompression is done in the following steps:
        1. Check for COMPRESSION_PREFIX marker
        2. Strip prefix and base64 decode
        3. Decompress with Zstd
        4. Decode UTF-8 to string

        Args:
            data: String data that may or may not be compressed

        Returns:
            Decompressed string if it was compressed, or original string otherwise
        """
        if data.startswith(self.COMPRESSION_PREFIX):
            # Strip prefix, base64 decode, and decompress
            compressed_b64 = data[len(self.COMPRESSION_PREFIX) :]
            compressed = base64.b64decode(compressed_b64)
            decompressed = zstd.decompress(compressed)
            return decompressed.decode("utf-8")
        return data

    def __init__(
        self,
        redis_url: str | None = None,
        password: str | None = None,
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
            password: Redis password for authentication. If not provided, uses settings.
                Set to None for no authentication (local development).
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

        # Password authentication - use provided value or fall back to settings
        # Note: password=None means "use settings", to explicitly disable, use password=""
        self._password = password if password is not None else settings.redis_password

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
                # Pool size is configurable via settings.redis_pool_size (default: 50)
                # to handle burst loads from bulk file operations
                from backend.core.config import get_settings

                settings = get_settings()
                pool_kwargs: dict[str, Any] = {
                    "encoding": "utf-8",
                    "decode_responses": True,
                    "socket_connect_timeout": 5,
                    "socket_keepalive": True,
                    "health_check_interval": 30,
                    "max_connections": settings.redis_pool_size,
                }

                # Add password if configured (non-empty string)
                # Empty string is treated as no password for backward compatibility
                # Support both str and SecretStr for password
                if self._password:
                    password_value = (
                        self._password.get_secret_value()
                        if hasattr(self._password, "get_secret_value")
                        else self._password
                    )
                    pool_kwargs["password"] = password_value

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
                auth_msg = " with authentication" if self._password else ""
                logger.info(f"Successfully connected to Redis{ssl_msg}{auth_msg}")
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

    async def add_to_queue_safe(
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
        # Apply compression if payload exceeds threshold
        payload = self._compress_payload(serialized)

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
                new_length = cast("int", await client.rpush(queue_name, payload))  # type: ignore[misc]

                return QueueAddResult(
                    success=True,
                    queue_length=new_length,
                    moved_to_dlq_count=moved_count,
                    warning=f"Moved {moved_count} items to DLQ due to overflow",
                )

            elif overflow_policy == QueueOverflowPolicy.DROP_OLDEST:
                # Add item then trim with explicit warning
                result = cast("int", await client.rpush(queue_name, payload))  # type: ignore[misc]
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
        new_length = cast("int", await client.rpush(queue_name, payload))  # type: ignore[misc]

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

        Supports both compressed and uncompressed payloads for backward compatibility.
        Compressed payloads are identified by the COMPRESSION_PREFIX marker.

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
            # Decompress if payload is compressed (backward compatible)
            decompressed = self._decompress_payload(value)
            try:
                return json.loads(decompressed)
            except json.JSONDecodeError:
                return decompressed
        return None

    async def pop_from_queue_nonblocking(self, queue_name: str) -> Any | None:
        """Non-blocking pop from the front of a queue (LPOP).

        Unlike get_from_queue() which uses BLPOP with a minimum timeout,
        this method returns immediately if the queue is empty.

        Supports both compressed and uncompressed payloads for backward compatibility.
        Compressed payloads are identified by the COMPRESSION_PREFIX marker.

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
            # Decompress if payload is compressed (backward compatible)
            decompressed = self._decompress_payload(result)
            try:
                return json.loads(decompressed)
            except json.JSONDecodeError:
                return decompressed
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

        Supports both compressed and uncompressed payloads for backward compatibility.
        Compressed payloads are identified by the COMPRESSION_PREFIX marker.

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
            # Decompress if payload is compressed (backward compatible)
            decompressed = self._decompress_payload(item)
            try:
                result.append(json.loads(decompressed))
            except json.JSONDecodeError:
                result.append(decompressed)
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
        if value is not None:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        """Set a value in Redis cache.

        Args:
            key: Cache key
            value: Value to store (will be JSON-serialized)
            expire: Expiration time in seconds (optional)

        Returns:
            True if successful
        """
        client = self._ensure_connected()
        # Always JSON-serialize for consistent deserialization in get()
        serialized = json.dumps(value)
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

    # Sorted set operations for priority queues

    async def zadd(self, key: str, mapping: dict[str, float | int]) -> int:
        """Add members to a sorted set with scores.

        Args:
            key: Sorted set key
            mapping: Dictionary of {member: score} pairs

        Returns:
            Number of new elements added (not counting score updates)
        """
        client = self._ensure_connected()
        return cast("int", await client.zadd(key, mapping))

    async def zpopmax(self, key: str, count: int = 1) -> list[tuple[str, float]]:
        """Remove and return the member(s) with highest score(s).

        Args:
            key: Sorted set key
            count: Number of elements to pop (default: 1)

        Returns:
            List of (member, score) tuples
        """
        client = self._ensure_connected()
        result = await client.zpopmax(key, count)
        return cast("list[tuple[str, float]]", result)

    async def zcard(self, key: str) -> int:
        """Return the number of elements in a sorted set.

        Args:
            key: Sorted set key

        Returns:
            Number of elements in the sorted set
        """
        client = self._ensure_connected()
        return cast("int", await client.zcard(key))

    async def zrange(self, key: str, start: int, stop: int) -> list[str]:
        """Return elements in a sorted set by index range.

        Args:
            key: Sorted set key
            start: Start index (0-based)
            stop: Stop index (inclusive, -1 for last)

        Returns:
            List of members in the specified range
        """
        client = self._ensure_connected()
        result = await client.zrange(key, start, stop)
        return cast("list[str]", result)

    async def zrem(self, key: str, *members: str) -> int:
        """Remove members from a sorted set.

        Args:
            key: Sorted set key
            *members: Members to remove

        Returns:
            Number of members removed
        """
        client = self._ensure_connected()
        return cast("int", await client.zrem(key, *members))

    async def zremrangebyrank(self, key: str, start: int, stop: int) -> int:
        """Remove members from a sorted set by rank (index).

        Removes all elements in the sorted set stored at key with rank between
        start and stop (inclusive). Both start and stop are 0-based indexes with
        0 being the element with the lowest score. Negative numbers can be used
        to indicate offsets from the end (-1 is the last element).

        Useful for keeping a sorted set bounded by removing oldest entries:
        - To keep only the 1000 most recent (highest score): zremrangebyrank(key, 0, -1001)
        - To remove the 100 oldest: zremrangebyrank(key, 0, 99)

        Args:
            key: Sorted set key
            start: Start rank (0-based, inclusive)
            stop: Stop rank (inclusive, negative for offset from end)

        Returns:
            Number of members removed
        """
        client = self._ensure_connected()
        return cast("int", await client.zremrangebyrank(key, start, stop))

    async def zscore(self, key: str, member: str) -> float | None:
        """Get the score of a member in a sorted set.

        Args:
            key: Sorted set key
            member: Member to get score for

        Returns:
            Score of the member, or None if member doesn't exist
        """
        client = self._ensure_connected()
        result = await client.zscore(key, member)
        return cast("float | None", result)

    async def zrangebyscore(
        self,
        key: str,
        min_score: float | int | str,
        max_score: float | int | str,
        start: int | None = None,
        num: int | None = None,
    ) -> list[str]:
        """Return elements in a sorted set with scores within the given range.

        Args:
            key: Sorted set key
            min_score: Minimum score (inclusive). Use '-inf' for no minimum.
            max_score: Maximum score (inclusive). Use '+inf' for no maximum.
            start: Optional start offset for pagination
            num: Optional number of elements to return (requires start)

        Returns:
            List of members with scores in the specified range
        """
        client = self._ensure_connected()
        if start is not None and num is not None:
            result = await client.zrangebyscore(key, min_score, max_score, start=start, num=num)
        else:
            result = await client.zrangebyscore(key, min_score, max_score)
        return cast("list[str]", result)

    async def zremrangebyscore(
        self,
        key: str,
        min_score: float | int | str,
        max_score: float | int | str,
    ) -> int:
        """Remove elements in a sorted set with scores within the given range.

        Args:
            key: Sorted set key
            min_score: Minimum score (inclusive). Use '-inf' for no minimum.
            max_score: Maximum score (inclusive). Use '+inf' for no maximum.

        Returns:
            Number of elements removed
        """
        client = self._ensure_connected()
        return cast("int", await client.zremrangebyscore(key, min_score, max_score))

    async def llen(self, key: str) -> int:
        """Get the length of a list.

        Args:
            key: List key

        Returns:
            Length of the list
        """
        client = self._ensure_connected()
        return cast("int", await client.llen(key))  # type: ignore[misc]

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        """Set a key with an expiration time (atomic SET + EXPIRE).

        This is equivalent to calling SET key value EX seconds atomically.
        Useful for cache entries and temporary data that should auto-expire.

        Args:
            key: Redis key to set
            seconds: Time-to-live in seconds
            value: String value to store (should be pre-serialized if JSON)

        Returns:
            True if the operation was successful
        """
        client = self._ensure_connected()
        return cast("bool", await client.setex(key, seconds, value))

    async def lpush(self, key: str, *values: str) -> int:
        """Push values to the head of a list.

        Args:
            key: Redis list key
            *values: Values to push (will be added left-to-right)

        Returns:
            Length of the list after push
        """
        client = self._ensure_connected()
        return cast("int", await client.lpush(key, *values))  # type: ignore[misc]

    async def rpush(self, key: str, *values: str) -> int:
        """Push values to the tail of a list.

        Args:
            key: Redis list key
            *values: Values to push (will be added to the end)

        Returns:
            Length of the list after push
        """
        client = self._ensure_connected()
        return cast("int", await client.rpush(key, *values))  # type: ignore[misc]

    async def ltrim(self, key: str, start: int, stop: int) -> bool:
        """Trim a list to the specified range.

        Args:
            key: Redis list key
            start: Start index (0-based)
            stop: Stop index (inclusive, -1 for last element)

        Returns:
            True if successful
        """
        client = self._ensure_connected()
        result = await client.ltrim(key, start, stop)  # type: ignore[misc]
        return result is True or result == "OK"

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        """Get a range of elements from a list.

        Args:
            key: Redis list key
            start: Start index (0-based)
            stop: Stop index (inclusive, -1 for last element)

        Returns:
            List of elements in the range
        """
        client = self._ensure_connected()
        result = await client.lrange(key, start, stop)  # type: ignore[misc]
        return cast("list[str]", result)

    # Server info operations (for debug endpoints)

    async def info(self, section: str | None = None) -> dict[str, Any]:
        """Get Redis server information.

        Args:
            section: Optional section to retrieve (e.g., 'server', 'memory', 'stats').
                If None, returns all sections.

        Returns:
            Dictionary containing server information
        """
        client = self._ensure_connected()
        if section:
            return cast("dict[str, Any]", await client.info(section))
        return cast("dict[str, Any]", await client.info())

    async def pubsub_channels(self, pattern: str = "*") -> list[bytes | str]:
        """List active pub/sub channels.

        Args:
            pattern: Glob-style pattern to filter channels (default: "*" for all)

        Returns:
            List of active channel names
        """
        client = self._ensure_connected()
        return cast("list[bytes | str]", await client.pubsub_channels(pattern))

    async def pubsub_numsub(self, *channels: str) -> list[tuple[bytes | str, int]]:
        """Get the number of subscribers for specified channels.

        Args:
            *channels: Channel names to check

        Returns:
            List of (channel, subscriber_count) tuples
        """
        client = self._ensure_connected()
        return cast("list[tuple[bytes | str, int]]", await client.pubsub_numsub(*channels))

    # HyperLogLog operations (NEM-3414)
    # HyperLogLog is a probabilistic data structure for cardinality estimation
    # with ~0.81% standard error using only ~12KB of memory regardless of set size

    async def pfadd(self, key: str, *values: str) -> int:
        """Add elements to a HyperLogLog structure for unique counting.

        HyperLogLog provides probabilistic cardinality estimation with:
        - ~0.81% standard error (very accurate for analytics)
        - Constant memory (~12KB) regardless of cardinality
        - O(1) time complexity for both add and count

        Use cases in this project:
        - Count unique cameras that detected activity
        - Count unique events in a time window
        - Count unique detection types (person, vehicle, etc.)
        - Count unique entity IDs for tracking

        Args:
            key: HyperLogLog key
            *values: Elements to add (will be deduplicated internally)

        Returns:
            1 if the cardinality estimate changed, 0 otherwise
        """
        client = self._ensure_connected()
        return cast("int", await client.pfadd(key, *values))

    async def pfcount(self, *keys: str) -> int:
        """Get the approximate cardinality (unique count) of a HyperLogLog.

        When called with a single key, returns the approximate cardinality.
        When called with multiple keys, returns the cardinality of the union.

        Args:
            *keys: One or more HyperLogLog keys

        Returns:
            Approximate number of unique elements
        """
        client = self._ensure_connected()
        return cast("int", await client.pfcount(*keys))

    async def pfmerge(self, dest_key: str, *source_keys: str) -> bool:
        """Merge multiple HyperLogLogs into a single destination.

        Creates a new HyperLogLog that represents the union of all source HLLs.
        Useful for combining counts across time windows or partitions.

        Args:
            dest_key: Destination key for the merged HyperLogLog
            *source_keys: Source HyperLogLog keys to merge

        Returns:
            True if successful
        """
        client = self._ensure_connected()
        result = await client.pfmerge(dest_key, *source_keys)
        return result is True or result == "OK"

    # Memory management operations (NEM-3416)

    async def config_get(self, pattern: str) -> dict[str, str]:
        """Get Redis server configuration values.

        Args:
            pattern: Configuration parameter pattern (e.g., "maxmemory*")

        Returns:
            Dictionary of configuration key-value pairs
        """
        client = self._ensure_connected()
        result = await client.config_get(pattern)
        return cast("dict[str, str]", result)

    async def config_set(self, name: str, value: str) -> bool:
        """Set a Redis server configuration value at runtime.

        Note: Not all configuration values can be changed at runtime.
        Commonly used for:
        - maxmemory: Maximum memory limit
        - maxmemory-policy: Eviction policy when limit is reached

        Args:
            name: Configuration parameter name
            value: Value to set

        Returns:
            True if successful
        """
        client = self._ensure_connected()
        result = await client.config_set(name, value)
        return result is True or result == "OK"

    async def memory_stats(self) -> dict[str, Any]:
        """Get detailed memory statistics from Redis.

        Returns comprehensive memory information including:
        - peak.allocated: Peak memory consumption
        - total.allocated: Total allocated memory
        - keys.count: Number of keys
        - fragmentation.ratio: Memory fragmentation
        - overhead.*: Memory overhead for various structures

        Returns:
            Dictionary containing memory statistics
        """
        client = self._ensure_connected()
        result = await client.memory_stats()
        return cast("dict[str, Any]", result)

    async def memory_usage(self, key: str, samples: int = 5) -> int | None:
        """Get memory usage of a specific key in bytes.

        Args:
            key: Key to check memory usage for
            samples: Number of samples for aggregate types (default: 5)

        Returns:
            Memory usage in bytes, or None if key doesn't exist
        """
        client = self._ensure_connected()
        result = await client.memory_usage(key, samples=samples)
        return cast("int | None", result)

    async def dbsize(self) -> int:
        """Get the number of keys in the current database.

        Returns:
            Number of keys in the database
        """
        client = self._ensure_connected()
        return cast("int", await client.dbsize())

    async def scan_keys(
        self,
        pattern: str = "*",
        count: int = 100,
        max_keys: int = 10000,
    ) -> list[str]:
        """Scan for keys matching a pattern without blocking.

        Uses SCAN command for non-blocking iteration. Useful for:
        - Finding keys to analyze memory usage
        - Identifying keys for cleanup
        - Pattern-based key discovery

        Args:
            pattern: Glob-style pattern to match keys
            count: Hint for number of keys per iteration (default: 100)
            max_keys: Maximum total keys to return (default: 10000)

        Returns:
            List of matching key names
        """
        client = self._ensure_connected()
        keys: list[str] = []
        async for key in client.scan_iter(match=pattern, count=count):
            keys.append(key)
            if len(keys) >= max_keys:
                break
        return keys


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

    # Determine the client to yield (compute before yield for proper cleanup)
    client_to_yield: RedisClient | None = None
    try:
        # Fast path: client already initialized
        if _redis_client is not None:
            client_to_yield = _redis_client
        else:
            # Slow path: acquire lock and check again
            lock = _get_redis_init_lock()
            async with lock:
                # Double-check after acquiring lock
                if _redis_client is None:
                    client = RedisClient()
                    await client.connect()
                    _redis_client = client
            client_to_yield = _redis_client
    except (ConnectionError, TimeoutError) as e:
        logger.warning(f"Redis unavailable (will report degraded status): {e}")
        client_to_yield = None
    except Exception as e:
        # Catch any other Redis connection errors
        logger.warning(f"Redis connection error (will report degraded status): {e}")
        client_to_yield = None

    # Single yield point - proper pattern for FastAPI dependencies with Python 3.14+
    yield client_to_yield


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


def get_redis_client_sync() -> RedisClient | None:
    """Get the global Redis client synchronously.

    This function returns the already-initialized Redis client without
    awaiting connection. Use this when you need Redis access from synchronous
    code and the client has already been initialized during app startup.

    Returns:
        RedisClient if already initialized, None otherwise

    Note:
        This is designed for singleton initializers like get_enrichment_pipeline()
        that need Redis access but are called synchronously. The Redis client
        should already be initialized via init_redis() during app startup.
    """
    return _redis_client


async def close_redis() -> None:
    """Close Redis client for application shutdown."""
    global _redis_client, _redis_init_lock  # noqa: PLW0603

    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None
    # Reset lock so it can be recreated in correct event loop on next startup
    _redis_init_lock = None
