"""Retry decorators and utilities for handling transient failures.

This module provides reusable retry patterns with exponential backoff and jitter
for operations that may fail transiently (network issues, temporary unavailability).

Features:
- Configurable exponential backoff with jitter
- Retry on specific exception types
- Both async and sync decorators
- Context manager for fine-grained control
- Metrics integration for monitoring retry behavior
- Structured logging of retry attempts

Usage:
    from backend.core.retry import retry_async, retry_sync, RetryContext

    # Decorator for async functions
    @retry_async(max_retries=3, retry_on=(ExternalServiceError,))
    async def call_external_service():
        return await http_client.get(url)

    # Decorator for sync functions
    @retry_sync(max_retries=3, retry_on=(ConnectionError,))
    def sync_operation():
        return requests.get(url)

    # Context manager for fine-grained control
    async with RetryContext(max_retries=3) as retry:
        while retry.should_retry():
            try:
                result = await risky_operation()
                break
            except TransientError as e:
                if not retry.can_retry(e):
                    raise
                await retry.wait()
"""

from __future__ import annotations

import asyncio
import functools
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from prometheus_client import Counter

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = get_logger(__name__)

# =============================================================================
# Prometheus Metrics
# =============================================================================

RETRY_ATTEMPTS_TOTAL = Counter(
    "hsi_retry_attempts_total",
    "Total number of retry attempts",
    labelnames=["operation", "outcome"],  # outcome: success, failure, exhausted
)

RETRY_OPERATIONS_TOTAL = Counter(
    "hsi_retry_operations_total",
    "Total number of operations that required retries",
    labelnames=["operation"],
)


# =============================================================================
# Configuration
# =============================================================================


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts (0 means no retries)
        base_delay: Base delay in seconds before first retry
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Jitter factor (0.0-1.0) for randomizing delays
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: float = 0.1


# Default configurations for common scenarios
DEFAULT_CONFIG = RetryConfig()

AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    jitter=0.2,
)

CONSERVATIVE_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    base_delay=2.0,
    max_delay=10.0,
    jitter=0.1,
)


# =============================================================================
# Backoff Calculation
# =============================================================================


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for a retry attempt using exponential backoff with jitter.

    The delay is calculated as:
        delay = base_delay * (exponential_base ^ (attempt - 1))
        delay = min(delay, max_delay)
        delay = delay * (1 - jitter + random(0, 2*jitter))

    Args:
        attempt: The retry attempt number (1-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds before the next retry
    """
    # Calculate base exponential delay
    delay = config.base_delay * (config.exponential_base ** (attempt - 1))

    # Cap at max delay
    delay = min(delay, config.max_delay)

    # Apply jitter if configured
    # Note: Using random.random() is intentional here - this is NOT for cryptographic
    # purposes, just adding timing variation to avoid thundering herd scenarios.
    if config.jitter > 0:
        jitter_range = delay * config.jitter
        delay = delay - jitter_range + (random.random() * 2 * jitter_range)  # noqa: S311  # nosemgrep: insecure-random

    return max(0.0, delay)


# =============================================================================
# Async Retry Decorator
# =============================================================================


def retry_async[**P, T](
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: float = 0.1,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    operation_name: str | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for async functions with retry logic.

    Retries the decorated function on specified exceptions using
    exponential backoff with jitter.

    Args:
        max_retries: Maximum retry attempts (0 means no retries)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential growth
        jitter: Random jitter factor (0.0-1.0)
        retry_on: Tuple of exception types to retry on
        operation_name: Name for metrics/logging (defaults to function name)

    Returns:
        Decorated async function with retry logic

    Example:
        @retry_async(max_retries=3, retry_on=(ConnectionError, TimeoutError))
        async def fetch_data():
            return await client.get(url)
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
    )

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        op_name = operation_name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: BaseException | None = None
            attempt = 0

            while attempt <= config.max_retries:
                attempt += 1
                try:
                    result = await func(*args, **kwargs)

                    # Log successful recovery if we had retries
                    if attempt > 1:
                        logger.info(
                            f"Operation '{op_name}' succeeded after {attempt} attempts",
                            extra={
                                "operation": op_name,
                                "attempts": attempt,
                                "outcome": "success",
                            },
                        )
                        RETRY_ATTEMPTS_TOTAL.labels(operation=op_name, outcome="success").inc()

                    return result

                except retry_on as e:
                    last_exception = e

                    if attempt > config.max_retries:
                        # Exhausted all retries
                        logger.error(
                            f"Operation '{op_name}' failed after {attempt} attempts: {e}",
                            extra={
                                "operation": op_name,
                                "attempts": attempt,
                                "outcome": "exhausted",
                                "error_type": type(e).__name__,
                            },
                        )
                        RETRY_ATTEMPTS_TOTAL.labels(operation=op_name, outcome="exhausted").inc()
                        raise

                    # Calculate delay and wait
                    delay = calculate_delay(attempt, config)
                    logger.warning(
                        f"Operation '{op_name}' failed (attempt {attempt}/{config.max_retries + 1}), "
                        f"retrying in {delay:.2f}s: {e}",
                        extra={
                            "operation": op_name,
                            "attempt": attempt,
                            "max_attempts": config.max_retries + 1,
                            "delay_seconds": delay,
                            "error_type": type(e).__name__,
                        },
                    )
                    RETRY_ATTEMPTS_TOTAL.labels(operation=op_name, outcome="retry").inc()
                    RETRY_OPERATIONS_TOTAL.labels(operation=op_name).inc()

                    await asyncio.sleep(delay)

            # Should not reach here, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper

    return decorator


# =============================================================================
# Sync Retry Decorator
# =============================================================================


def retry_sync[**P, T](
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: float = 0.1,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    operation_name: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for sync functions with retry logic.

    Retries the decorated function on specified exceptions using
    exponential backoff with jitter.

    Args:
        max_retries: Maximum retry attempts (0 means no retries)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential growth
        jitter: Random jitter factor (0.0-1.0)
        retry_on: Tuple of exception types to retry on
        operation_name: Name for metrics/logging (defaults to function name)

    Returns:
        Decorated function with retry logic

    Example:
        @retry_sync(max_retries=3, retry_on=(ConnectionError,))
        def fetch_data():
            return requests.get(url)
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
    )

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        op_name = operation_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: BaseException | None = None
            attempt = 0

            while attempt <= config.max_retries:
                attempt += 1
                try:
                    result = func(*args, **kwargs)

                    # Log successful recovery if we had retries
                    if attempt > 1:
                        logger.info(
                            f"Operation '{op_name}' succeeded after {attempt} attempts",
                            extra={
                                "operation": op_name,
                                "attempts": attempt,
                                "outcome": "success",
                            },
                        )
                        RETRY_ATTEMPTS_TOTAL.labels(operation=op_name, outcome="success").inc()

                    return result

                except retry_on as e:
                    last_exception = e

                    if attempt > config.max_retries:
                        # Exhausted all retries
                        logger.error(
                            f"Operation '{op_name}' failed after {attempt} attempts: {e}",
                            extra={
                                "operation": op_name,
                                "attempts": attempt,
                                "outcome": "exhausted",
                                "error_type": type(e).__name__,
                            },
                        )
                        RETRY_ATTEMPTS_TOTAL.labels(operation=op_name, outcome="exhausted").inc()
                        raise

                    # Calculate delay and wait
                    delay = calculate_delay(attempt, config)
                    logger.warning(
                        f"Operation '{op_name}' failed (attempt {attempt}/{config.max_retries + 1}), "
                        f"retrying in {delay:.2f}s: {e}",
                        extra={
                            "operation": op_name,
                            "attempt": attempt,
                            "max_attempts": config.max_retries + 1,
                            "delay_seconds": delay,
                            "error_type": type(e).__name__,
                        },
                    )
                    RETRY_ATTEMPTS_TOTAL.labels(operation=op_name, outcome="retry").inc()
                    RETRY_OPERATIONS_TOTAL.labels(operation=op_name).inc()

                    time.sleep(delay)

            # Should not reach here, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper

    return decorator


# =============================================================================
# Retry Context Manager
# =============================================================================


class RetryContext:
    """Context manager for fine-grained retry control.

    Provides more control than the decorators for complex retry scenarios.

    Attributes:
        attempts: Current attempt count
        last_error: Last exception caught (if any)

    Example:
        async with RetryContext(max_retries=3) as retry:
            while retry.should_retry():
                try:
                    result = await operation()
                    break
                except TransientError as e:
                    if not retry.can_retry(e):
                        raise
                    await retry.wait()
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: float = 0.1,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
        operation_name: str = "unknown",
    ) -> None:
        """Initialize retry context.

        Args:
            max_retries: Maximum retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay cap in seconds
            exponential_base: Base for exponential growth
            jitter: Random jitter factor
            retry_on: Tuple of exception types to retry on
            operation_name: Name for logging/metrics
        """
        self._config = RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
        )
        self._retry_on = retry_on
        self._operation_name = operation_name
        self._attempts = 0
        self._last_error: BaseException | None = None

    @property
    def attempts(self) -> int:
        """Current attempt count."""
        return self._attempts

    @property
    def last_error(self) -> BaseException | None:
        """Last exception caught."""
        return self._last_error

    def should_retry(self) -> bool:
        """Check if another retry attempt should be made.

        Returns:
            True if more attempts are available
        """
        return self._attempts <= self._config.max_retries

    def can_retry(self, error: BaseException) -> bool:
        """Check if the given error is retryable and retries remain.

        Args:
            error: Exception to check

        Returns:
            True if error is retryable and attempts remain
        """
        self._last_error = error
        self._attempts += 1

        is_retryable = isinstance(error, self._retry_on)
        has_retries = self._attempts <= self._config.max_retries

        if not is_retryable:
            logger.debug(
                f"Error type {type(error).__name__} is not retryable",
                extra={"error_type": type(error).__name__},
            )
            return False

        if not has_retries:
            logger.warning(
                f"Retry attempts exhausted for '{self._operation_name}'",
                extra={
                    "operation": self._operation_name,
                    "attempts": self._attempts,
                },
            )
            return False

        return True

    async def wait(self) -> None:
        """Wait before the next retry attempt (async version)."""
        delay = calculate_delay(self._attempts, self._config)
        logger.info(
            f"Waiting {delay:.2f}s before retry attempt {self._attempts + 1}",
            extra={
                "operation": self._operation_name,
                "attempt": self._attempts,
                "delay_seconds": delay,
            },
        )
        await asyncio.sleep(delay)

    def wait_sync(self) -> None:
        """Wait before the next retry attempt (sync version)."""
        delay = calculate_delay(self._attempts, self._config)
        logger.info(
            f"Waiting {delay:.2f}s before retry attempt {self._attempts + 1}",
            extra={
                "operation": self._operation_name,
                "attempt": self._attempts,
                "delay_seconds": delay,
            },
        )
        time.sleep(delay)

    async def __aenter__(self) -> RetryContext:
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Exit async context."""
        return False

    def __enter__(self) -> RetryContext:
        """Enter sync context."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Exit sync context."""
        return False
