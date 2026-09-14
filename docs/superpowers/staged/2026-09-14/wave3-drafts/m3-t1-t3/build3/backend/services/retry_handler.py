"""Retry handler with exponential backoff and dead-letter queue support.

This module provides retry functionality for AI service calls (detector and LLM)
with configurable exponential backoff. Failed jobs that exceed the maximum retry
count are moved to a dead-letter queue (DLQ) for later inspection.

DLQ Structure:
    dlq:detection_queue - Failed detection jobs
    dlq:analysis_queue - Failed LLM analysis jobs

Job Format in DLQ:
    {
        "original_job": {...},      # Original job payload
        "error": "error message",    # Last error message
        "attempt_count": 3,          # Number of attempts made
        "first_failed_at": "...",    # ISO timestamp of first failure
        "last_failed_at": "...",     # ISO timestamp of last failure
        "queue_name": "..."          # Original queue name
    }

Circuit Breaker for DLQ:
    When the DLQ becomes unavailable (full or failing), a circuit breaker
    prevents cascading failures by stopping further DLQ write attempts.
    The circuit breaker transitions through states:
    - CLOSED: Normal operation, DLQ writes proceed
    - OPEN: DLQ failing, writes are skipped to prevent resource exhaustion
    - HALF_OPEN: Testing recovery, limited writes allowed
"""

from __future__ import annotations

import asyncio
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

from backend.core.config import get_settings
from backend.core.constants import (
    DLQ_ANALYSIS_QUEUE as _DLQ_ANALYSIS_QUEUE,
)
from backend.core.constants import (
    DLQ_DETECTION_QUEUE as _DLQ_DETECTION_QUEUE,
)
from backend.core.constants import (
    DLQ_PREFIX as _DLQ_PREFIX,
)
from backend.core.constants import (
    get_dlq_name as _get_dlq_name,
)
from backend.core.logging import get_logger, sanitize_error
from backend.core.redis import QueueOverflowPolicy, RedisClient
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass(slots=True)
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number.

        Uses exponential backoff with optional jitter.

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in seconds before next retry
        """
        import random

        # Calculate exponential delay: base * (exponential_base ^ (attempt - 1))
        delay = self.base_delay_seconds * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay_seconds)

        if self.jitter:
            # Add random jitter between 0 and 25% of the delay
            jitter_amount = delay * 0.25 * random.random()  # noqa: S311
            delay = delay + jitter_amount

        return delay


@dataclass(slots=True)
class JobFailure:
    """Record of a failed job with enriched error context.

    Error context fields (NEM-1474):
    - error_type: Exception class name for categorization
    - stack_trace: Truncated stack trace for debugging
    - http_status: HTTP status code (for network errors)
    - response_body: Truncated AI service response (for debugging)
    - retry_delays: Delays applied between retry attempts
    - context: System state snapshot at failure time (queue depths, circuit breaker states)
    """

    original_job: dict[str, Any]
    error: str
    attempt_count: int
    first_failed_at: str
    last_failed_at: str
    queue_name: str
    # Error context enrichment fields (NEM-1474)
    error_type: str | None = None
    stack_trace: str | None = None
    http_status: int | None = None
    response_body: str | None = None
    retry_delays: list[float] | None = None
    context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "original_job": self.original_job,
            "error": self.error,
            "attempt_count": self.attempt_count,
            "first_failed_at": self.first_failed_at,
            "last_failed_at": self.last_failed_at,
            "queue_name": self.queue_name,
            # Error context fields
            "error_type": self.error_type,
            "stack_trace": self.stack_trace,
            "http_status": self.http_status,
            "response_body": self.response_body,
            "retry_delays": self.retry_delays,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobFailure:
        """Create from dictionary."""
        return cls(
            original_job=data["original_job"],
            error=data["error"],
            attempt_count=data["attempt_count"],
            first_failed_at=data["first_failed_at"],
            last_failed_at=data["last_failed_at"],
            queue_name=data["queue_name"],
            # Error context fields (with defaults for backward compatibility)
            error_type=data.get("error_type"),
            stack_trace=data.get("stack_trace"),
            http_status=data.get("http_status"),
            response_body=data.get("response_body"),
            retry_delays=data.get("retry_delays"),
            context=data.get("context"),
        )


@dataclass(slots=True)
class RetryResult:
    """Result of a retry operation."""

    success: bool
    result: Any = None
    error: str | None = None
    attempts: int = 0
    moved_to_dlq: bool = False


@dataclass(slots=True)
class DLQStats:
    """Statistics about dead-letter queues."""

    detection_queue_count: int = 0
    analysis_queue_count: int = 0
    total_count: int = 0


class RetryHandler:
    """Handles retries with exponential backoff and DLQ management.

    This class provides:
    - Exponential backoff for failed operations
    - Dead-letter queue for poison jobs
    - DLQ inspection and management
    - Circuit breaker for DLQ overflow protection

    Usage:
        handler = RetryHandler(redis_client)

        # Retry an operation
        result = await handler.with_retry(
            operation=some_async_func,
            job_data={"file_path": "...", "camera_id": "..."},
            queue_name="detection_queue",
        )

        # Check DLQ
        stats = await handler.get_dlq_stats()
        jobs = await handler.get_dlq_jobs("dlq:detection_queue")

        # Check DLQ circuit breaker status
        status = handler.get_dlq_circuit_breaker_status()
    """

    # DLQ key prefixes (re-exported from constants for backward compatibility)
    DLQ_PREFIX = _DLQ_PREFIX
    DLQ_DETECTION_QUEUE = _DLQ_DETECTION_QUEUE
    DLQ_ANALYSIS_QUEUE = _DLQ_ANALYSIS_QUEUE

    def __init__(
        self,
        redis_client: RedisClient | None = None,
        config: RetryConfig | None = None,
        dlq_circuit_breaker: CircuitBreaker | None = None,
    ):
        """Initialize retry handler.

        Args:
            redis_client: Redis client for DLQ operations
            config: Retry configuration (uses defaults if not provided)
            dlq_circuit_breaker: Circuit breaker for DLQ operations (auto-configured if not provided)
        """
        self._redis = redis_client
        self._config = config or RetryConfig()

        # Initialize DLQ circuit breaker
        if dlq_circuit_breaker is not None:
            self._dlq_circuit_breaker = dlq_circuit_breaker
        else:
            settings = get_settings()
            cb_config = CircuitBreakerConfig(
                failure_threshold=settings.dlq_circuit_breaker_failure_threshold,
                recovery_timeout=settings.dlq_circuit_breaker_recovery_timeout,
                half_open_max_calls=settings.dlq_circuit_breaker_half_open_max_calls,
                success_threshold=settings.dlq_circuit_breaker_success_threshold,
            )
            self._dlq_circuit_breaker = CircuitBreaker(
                name="dlq_overflow",
                config=cb_config,
            )

    @property
    def config(self) -> RetryConfig:
        """Get the retry configuration."""
        return self._config

    def _get_dlq_name(self, queue_name: str) -> str:
        """Get the DLQ name for a given queue.

        Args:
            queue_name: Original queue name

        Returns:
            DLQ queue name
        """
        return _get_dlq_name(queue_name)

    async def with_retry(
        self,
        operation: Callable[..., Any],
        job_data: dict[str, Any],
        queue_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> RetryResult:
        """Execute an operation with retry logic.

        Retries the operation with exponential backoff. If all retries fail,
        the job is moved to the dead-letter queue with enriched error context.

        Args:
            operation: Async callable to execute
            job_data: Original job data (stored in DLQ on failure)
            queue_name: Name of the source queue (used for DLQ naming)
            *args: Arguments to pass to the operation
            **kwargs: Keyword arguments to pass to the operation

        Returns:
            RetryResult with success status and result or error info
        """
        last_error: str | None = None
        last_exception: BaseException | None = None
        first_failed_at: str | None = None
        retry_delays: list[float] = []

        for attempt in range(1, self._config.max_retries + 1):
            try:
                logger.debug(
                    f"Attempt {attempt}/{self._config.max_retries} for {queue_name}",
                    extra={
                        "attempt": attempt,
                        "max_retries": self._config.max_retries,
                        "queue_name": queue_name,
                    },
                )

                result = await operation(*args, **kwargs)

                logger.info(
                    f"Operation succeeded on attempt {attempt} for {queue_name}",
                    extra={
                        "attempt": attempt,
                        "queue_name": queue_name,
                    },
                )

                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt,
                )

            except Exception as e:
                last_error = str(e)
                last_exception = e
                if first_failed_at is None:
                    first_failed_at = datetime.now(UTC).isoformat()

                logger.warning(
                    f"Attempt {attempt}/{self._config.max_retries} failed for {queue_name}: {e}",
                    extra={
                        "attempt": attempt,
                        "max_retries": self._config.max_retries,
                        "queue_name": queue_name,
                        "error": str(e),
                    },
                )

                if attempt < self._config.max_retries:
                    delay = self._config.get_delay(attempt)
                    retry_delays.append(delay)
                    logger.debug(
                        f"Waiting {delay:.2f}s before retry {attempt + 1}",
                        extra={
                            "delay_seconds": delay,
                            "next_attempt": attempt + 1,
                        },
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted - move to DLQ with enriched error context
        moved_to_dlq = False
        if self._redis and first_failed_at:
            # Extract error context from the last exception
            error_context = self._extract_error_context(last_exception)

            moved_to_dlq = await self._move_to_dlq(
                job_data=job_data,
                error=last_error or "Unknown error",
                attempt_count=self._config.max_retries,
                first_failed_at=first_failed_at,
                queue_name=queue_name,
                error_type=error_context.get("error_type"),
                stack_trace=error_context.get("stack_trace"),
                http_status=error_context.get("http_status"),
                response_body=error_context.get("response_body"),
                retry_delays=retry_delays if retry_delays else None,
            )

        logger.error(
            f"All {self._config.max_retries} retries exhausted for {queue_name}",
            extra={
                "queue_name": queue_name,
                "error": last_error,
                "moved_to_dlq": moved_to_dlq,
            },
        )

        return RetryResult(
            success=False,
            error=last_error,
            attempts=self._config.max_retries,
            moved_to_dlq=moved_to_dlq,
        )

    def _extract_error_context(self, exc: BaseException | None) -> dict[str, Any]:
        """Extract error context from an exception for DLQ enrichment.

        Args:
            exc: The exception to extract context from

        Returns:
            Dictionary containing error context fields
        """
        if exc is None:
            return {}

        # Maximum lengths for truncation
        max_stack_trace_length = 4096
        max_response_body_length = 2048

        context: dict[str, Any] = {}

        # Extract error type (exception class name)
        context["error_type"] = type(exc).__name__

        # Truncation suffixes
        stack_trace_suffix = "\n... [truncated]"
        response_body_suffix = "... [truncated]"

        # Extract stack trace
        try:
            stack_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            if len(stack_trace) > max_stack_trace_length:
                # Truncate, accounting for suffix length
                truncate_at = max_stack_trace_length - len(stack_trace_suffix)
                stack_trace = stack_trace[:truncate_at] + stack_trace_suffix
            context["stack_trace"] = stack_trace
        except Exception:
            context["stack_trace"] = None

        # Extract HTTP status and response body from httpx errors
        try:
            import httpx

            if isinstance(exc, httpx.HTTPStatusError):
                context["http_status"] = exc.response.status_code
                response_text = exc.response.text
                if len(response_text) > max_response_body_length:
                    # Truncate, accounting for suffix length
                    truncate_at = max_response_body_length - len(response_body_suffix)
                    response_text = response_text[:truncate_at] + response_body_suffix
                context["response_body"] = response_text
        except ImportError:
            # httpx not installed - HTTP context extraction not available.
            # Retry handling continues without HTTP-specific error details.
            # See: NEM-2540 for rationale
            pass
        except Exception as e:
            logger.debug(f"Failed to extract HTTP context from exception: {e}")

        return context

    async def _capture_system_context(self) -> dict[str, Any]:
        """Capture system state at failure time for debugging.

        Returns:
            Dictionary containing system state snapshot:
            - detection_queue_depth: Number of jobs in detection queue
            - analysis_queue_depth: Number of jobs in analysis queue
            - dlq_circuit_breaker_state: Current circuit breaker state
        """
        context: dict[str, Any] = {}

        # Capture queue depths
        try:
            if self._redis:
                from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE

                detection_depth = await self._redis.get_queue_length(DETECTION_QUEUE)
                analysis_depth = await self._redis.get_queue_length(ANALYSIS_QUEUE)
                context["detection_queue_depth"] = detection_depth
                context["analysis_queue_depth"] = analysis_depth
        except Exception as e:
            logger.debug(f"Failed to capture queue depths for error context: {e}")

        # Capture circuit breaker state
        try:
            context["dlq_circuit_breaker_state"] = self._dlq_circuit_breaker.state.value
        except Exception as e:
            logger.debug(f"Failed to capture circuit breaker state for error context: {e}")

        return context

    async def _move_to_dlq(
        self,
        job_data: dict[str, Any],
        error: str,
        attempt_count: int,
        first_failed_at: str,
        queue_name: str,
        error_type: str | None = None,
        stack_trace: str | None = None,
        http_status: int | None = None,
        response_body: str | None = None,
        retry_delays: list[float] | None = None,
    ) -> bool:
        """Move a failed job to the dead-letter queue with enriched error context.

        Uses a circuit breaker to prevent cascading failures when the DLQ
        is unavailable or overflowing. When the circuit is open, DLQ writes
        are skipped to allow the system to recover.

        Args:
            job_data: Original job data
            error: Error message from the last failure
            attempt_count: Number of attempts made
            first_failed_at: ISO timestamp of first failure
            queue_name: Original queue name
            error_type: Exception class name (for categorization)
            stack_trace: Truncated stack trace (for debugging)
            http_status: HTTP status code (for network errors)
            response_body: Truncated AI service response (for debugging)
            retry_delays: Delays applied between retry attempts

        Returns:
            True if job was moved successfully
        """
        if not self._redis:
            logger.warning("Cannot move job to DLQ: Redis client not initialized")
            return False

        # Check circuit breaker state before attempting DLQ write
        if not await self._dlq_circuit_breaker.allow_call():
            # CRITICAL: Job is being permanently lost due to open circuit breaker
            # Log at ERROR level with full job context for audit trail
            logger.error(
                f"CRITICAL DATA LOSS: DLQ circuit breaker is {self._dlq_circuit_breaker.state.value}, "
                f"job from {queue_name} will be PERMANENTLY LOST. "
                f"Original error: {error}. "
                f"Circuit breaker will recover after timeout or manual reset.",
                extra={
                    "queue_name": queue_name,
                    "circuit_state": self._dlq_circuit_breaker.state.value,
                    "circuit_failures": self._dlq_circuit_breaker.failure_count,
                    "circuit_threshold": self._dlq_circuit_breaker.config.failure_threshold,
                    "circuit_recovery_timeout": self._dlq_circuit_breaker.config.recovery_timeout,
                    "lost_job_data": job_data,
                    "lost_job_error": error,
                    "lost_job_attempt_count": attempt_count,
                    "lost_job_first_failed_at": first_failed_at,
                    "data_loss": True,
                },
            )
            return False

        try:
            dlq_name = self._get_dlq_name(queue_name)

            # Capture system context at failure time
            system_context = await self._capture_system_context()

            failure = JobFailure(
                original_job=job_data,
                error=error,
                attempt_count=attempt_count,
                first_failed_at=first_failed_at,
                last_failed_at=datetime.now(UTC).isoformat(),
                queue_name=queue_name,
                # Error context enrichment (NEM-1474)
                error_type=error_type,
                stack_trace=stack_trace,
                http_status=http_status,
                response_body=response_body,
                retry_delays=retry_delays,
                context=system_context,
            )

            # Use add_to_queue_safe to prevent silent data loss
            # DLQ uses REJECT policy - if DLQ is full, we must not silently lose the failed job
            result = await self._redis.add_to_queue_safe(
                dlq_name,
                failure.to_dict(),
                overflow_policy=QueueOverflowPolicy.REJECT,
            )

            if not result.success:
                # Record failure with circuit breaker
                await self._dlq_circuit_breaker._record_failure()
                logger.error(
                    f"CRITICAL: Failed to move job to DLQ (queue full): {dlq_name}. "
                    f"Circuit breaker failures: {self._dlq_circuit_breaker.failure_count}/"
                    f"{self._dlq_circuit_breaker.config.failure_threshold}",
                    extra={
                        "dlq_name": dlq_name,
                        "original_queue": queue_name,
                        "attempt_count": attempt_count,
                        "error": error,
                        "dlq_error": result.error,
                        "queue_length": result.queue_length,
                        "circuit_state": self._dlq_circuit_breaker.state.value,
                        "circuit_failures": self._dlq_circuit_breaker.failure_count,
                    },
                )
                return False

            # Record success with circuit breaker (helps recover from half-open)
            await self._dlq_circuit_breaker._record_success()

            logger.info(
                f"Moved job to DLQ: {dlq_name}",
                extra={
                    "dlq_name": dlq_name,
                    "original_queue": queue_name,
                    "attempt_count": attempt_count,
                    "error": error,
                },
            )
            return True

        except Exception as e:
            # Record failure with circuit breaker for unexpected exceptions
            await self._dlq_circuit_breaker._record_failure()
            logger.error(
                f"Failed to move job to DLQ: {sanitize_error(e)}. "
                f"Circuit breaker failures: {self._dlq_circuit_breaker.failure_count}/"
                f"{self._dlq_circuit_breaker.config.failure_threshold}",
                extra={
                    "queue_name": queue_name,
                    "circuit_state": self._dlq_circuit_breaker.state.value,
                    "circuit_failures": self._dlq_circuit_breaker.failure_count,
                },
            )
            return False

    async def get_dlq_stats(self) -> DLQStats:
        """Get statistics about dead-letter queues.

        Returns:
            DLQStats with counts for each DLQ
        """
        if not self._redis:
            return DLQStats()

        try:
            detection_count = await self._redis.get_queue_length(self.DLQ_DETECTION_QUEUE)
            analysis_count = await self._redis.get_queue_length(self.DLQ_ANALYSIS_QUEUE)

            return DLQStats(
                detection_queue_count=detection_count,
                analysis_queue_count=analysis_count,
                total_count=detection_count + analysis_count,
            )
        except Exception as e:
            logger.error(f"Failed to get DLQ stats: {sanitize_error(e)}")
            return DLQStats()

    def get_dlq_circuit_breaker_status(self) -> dict[str, Any]:
        """Get status of the DLQ circuit breaker.

        Returns:
            Dictionary containing circuit breaker status including:
            - name: Circuit breaker name
            - state: Current state (closed, open, half_open)
            - failure_count: Current consecutive failure count
            - is_open: Whether circuit is currently open (rejecting writes)
            - config: Circuit breaker configuration
        """
        return self._dlq_circuit_breaker.get_status()

    def is_dlq_circuit_open(self) -> bool:
        """Check if DLQ circuit breaker is open.

        Returns:
            True if circuit is open and DLQ writes are being rejected
        """
        return self._dlq_circuit_breaker.is_open

    def reset_dlq_circuit_breaker(self) -> None:
        """Reset the DLQ circuit breaker to closed state.

        This should be called after manually draining/clearing the DLQ
        to allow normal operation to resume.
        """
        self._dlq_circuit_breaker.reset()
        logger.info(
            "DLQ circuit breaker reset to CLOSED state",
            extra={"circuit_name": self._dlq_circuit_breaker.name},
        )

    async def get_dlq_jobs(
        self,
        dlq_name: str,
        start: int = 0,
        end: int = -1,
    ) -> list[JobFailure]:
        """Get jobs from a dead-letter queue without removing them.

        Args:
            dlq_name: Name of the DLQ (e.g., "dlq:detection_queue")
            start: Start index (0-based)
            end: End index (-1 for all)

        Returns:
            List of JobFailure objects
        """
        if not self._redis:
            return []

        try:
            items = await self._redis.peek_queue(dlq_name, start, end)
            return [JobFailure.from_dict(item) for item in items]
        except Exception as e:
            logger.error(f"Failed to get DLQ jobs: {sanitize_error(e)}")
            return []

    async def requeue_dlq_job(self, dlq_name: str) -> dict[str, Any] | None:
        """Remove and return the oldest job from a DLQ for reprocessing.

        Args:
            dlq_name: Name of the DLQ

        Returns:
            Original job data if available, None otherwise
        """
        if not self._redis:
            return None

        try:
            # Use non-blocking pop (LPOP) for instant response
            item = await self._redis.pop_from_queue_nonblocking(dlq_name)
            if item:
                failure = JobFailure.from_dict(item)
                logger.info(
                    f"Requeued job from {dlq_name}",
                    extra={
                        "dlq_name": dlq_name,
                        "original_queue": failure.queue_name,
                    },
                )
                return failure.original_job
            return None
        except Exception as e:
            logger.error(f"Failed to requeue DLQ job: {sanitize_error(e)}")
            return None

    async def clear_dlq(self, dlq_name: str) -> bool:
        """Clear all jobs from a dead-letter queue.

        Args:
            dlq_name: Name of the DLQ to clear

        Returns:
            True if cleared successfully
        """
        if not self._redis:
            return False

        try:
            await self._redis.clear_queue(dlq_name)
            logger.info(f"Cleared DLQ: {dlq_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear DLQ: {sanitize_error(e)}")
            return False

    async def move_dlq_job_to_queue(
        self,
        dlq_name: str,
        target_queue: str,
    ) -> bool:
        """Move a job from DLQ back to a processing queue.

        Args:
            dlq_name: Name of the DLQ
            target_queue: Target queue to move the job to

        Returns:
            True if moved successfully
        """
        if not self._redis:
            return False

        try:
            job = await self.requeue_dlq_job(dlq_name)
            if job:
                # Use add_to_queue_safe to prevent silent data loss when requeuing
                result = await self._redis.add_to_queue_safe(
                    target_queue,
                    job,
                    overflow_policy=QueueOverflowPolicy.DLQ,
                )

                if not result.success:
                    logger.error(
                        f"Failed to move job from {dlq_name} to {target_queue}: {result.error}",
                        extra={
                            "dlq_name": dlq_name,
                            "target_queue": target_queue,
                            "queue_length": result.queue_length,
                        },
                    )
                    return False

                if result.had_backpressure:
                    logger.warning(
                        f"Queue backpressure while moving job from {dlq_name} to {target_queue}",
                        extra={
                            "dlq_name": dlq_name,
                            "target_queue": target_queue,
                            "queue_length": result.queue_length,
                            "moved_to_dlq": result.moved_to_dlq_count,
                        },
                    )

                logger.info(
                    f"Moved job from {dlq_name} to {target_queue}",
                    extra={
                        "dlq_name": dlq_name,
                        "target_queue": target_queue,
                    },
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to move DLQ job: {sanitize_error(e)}")
            return False


# Global retry handler instance
_retry_handler: RetryHandler | None = None


def get_retry_handler(redis_client: RedisClient | None = None) -> RetryHandler:
    """Get or create the global retry handler instance.

    Args:
        redis_client: Redis client (required on first call)

    Returns:
        RetryHandler instance
    """
    global _retry_handler  # noqa: PLW0603

    if _retry_handler is None:
        _retry_handler = RetryHandler(redis_client=redis_client)
    elif redis_client is not None and _retry_handler._redis is None:
        _retry_handler._redis = redis_client

    return _retry_handler


def reset_retry_handler() -> None:
    """Reset the global retry handler (for testing)."""
    global _retry_handler  # noqa: PLW0603
    _retry_handler = None
