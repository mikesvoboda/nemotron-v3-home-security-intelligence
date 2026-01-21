"""Async context propagation utilities for structured logging (NEM-1640).

This module provides utilities for propagating logging context across async
boundaries, ensuring request_id, connection_id, and task_id are maintained when
creating background tasks or handling WebSocket connections.

Key components:
- propagate_log_context: Async context manager for task context propagation
- create_task_with_context: Helper to create tasks with preserved context
- create_tracked_task: Enhanced task creation with automatic task_id generation
- copy_context_to_task: Decorator for context-preserving coroutines
- logger_with_context: Async context manager for adding extra fields to logs
- connection_id: Context variable for WebSocket connection tracking
- task_id: Context variable for async task tracking
- job_id: Context variable for scheduled job tracking

Usage:
    from backend.core.async_context import (
        propagate_log_context,
        create_task_with_context,
        create_tracked_task,
        set_connection_id,
        get_connection_id,
        get_task_id,
        generate_task_id,
    )

    # Propagate context into a background task
    async with propagate_log_context(request_id="req-123"):
        await some_async_operation()

    # Create a task that inherits the current context
    task = create_task_with_context(background_work())

    # Create a tracked task with automatic task_id generation
    task = create_tracked_task(
        process_detection(detection),
        name="process_detection",
        task_prefix="detect"
    )

    # Set connection_id for WebSocket handlers
    set_connection_id("ws-conn-456")
"""

from __future__ import annotations

import asyncio
import functools
import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from typing import Any

# Import log context functions from logging module to avoid duplication
from backend.core.logging import (
    get_log_context,
    get_request_id,
    log_context,
    set_request_id,
)

__all__ = [
    "copy_context_to_task",
    "create_task_with_context",
    "create_tracked_task",
    "generate_task_id",
    "get_connection_id",
    "get_job_id",
    "get_log_context",
    "get_task_id",
    "logger_with_context",
    "propagate_log_context",
    "set_connection_id",
    "set_job_id",
    "set_task_id",
]

# Context variable for WebSocket connection ID
_connection_id: ContextVar[str | None] = ContextVar("connection_id", default=None)

# Context variable for async task ID (for correlating logs from related async operations)
_task_id: ContextVar[str | None] = ContextVar("task_id", default=None)

# Context variable for scheduled job ID (for correlating logs from job execution)
_job_id: ContextVar[str | None] = ContextVar("job_id", default=None)


def get_connection_id() -> str | None:
    """Get the current WebSocket connection ID from context.

    Returns:
        The connection ID if set, None otherwise.
    """
    return _connection_id.get()


def set_connection_id(connection_id: str | None) -> Token[str | None]:
    """Set the WebSocket connection ID in context.

    Args:
        connection_id: The connection ID to set, or None to clear.

    Returns:
        A token that can be used to restore the previous value.
    """
    return _connection_id.set(connection_id)


def get_task_id() -> str | None:
    """Get the current async task ID from context.

    Returns:
        The task ID if set, None otherwise.
    """
    return _task_id.get()


def set_task_id(task_id: str | None) -> Token[str | None]:
    """Set the async task ID in context.

    Args:
        task_id: The task ID to set, or None to clear.

    Returns:
        A token that can be used to restore the previous value.
    """
    return _task_id.set(task_id)


def get_job_id() -> str | None:
    """Get the current scheduled job ID from context.

    Returns:
        The job ID if set, None otherwise.
    """
    return _job_id.get()


def set_job_id(job_id: str | None) -> Token[str | None]:
    """Set the scheduled job ID in context.

    Args:
        job_id: The job ID to set, or None to clear.

    Returns:
        A token that can be used to restore the previous value.
    """
    return _job_id.set(job_id)


def generate_task_id(prefix: str = "task") -> str:
    """Generate a unique task ID with a prefix.

    Args:
        prefix: The prefix for the task ID (e.g., "task", "detect", "analyze").
            Defaults to "task".

    Returns:
        A unique task ID in the format "{prefix}-{uuid_hex[:8]}"

    Example:
        >>> generate_task_id("detect")
        'detect-a1b2c3d4'
        >>> generate_task_id()
        'task-e5f6g7h8'
    """
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@asynccontextmanager
async def propagate_log_context(
    request_id: str | None = None,
) -> AsyncIterator[None]:
    """Async context manager for propagating log context into async operations.

    This context manager ensures that the request_id (and optionally other
    context) is properly propagated when crossing async boundaries, such as
    creating background tasks.

    Args:
        request_id: Optional explicit request_id to set. If not provided,
            uses the current request_id or generates a new one.

    Yields:
        None

    Example:
        async with propagate_log_context(request_id="req-123"):
            # All logs in this context will include request_id
            await some_operation()

        # Or to preserve existing context:
        async with propagate_log_context():
            task = asyncio.create_task(background_work())
            await task
    """
    # Get the request_id to use
    if request_id is not None:
        new_request_id = request_id
    else:
        current_id = get_request_id()
        # Use existing request_id or generate a new one if none exists
        new_request_id = current_id if current_id is not None else str(uuid.uuid4())[:8]

    # Store the previous request_id for restoration
    previous_request_id = get_request_id()

    # Set the new request_id
    set_request_id(new_request_id)

    try:
        yield
    finally:
        # Restore the previous request_id
        set_request_id(previous_request_id)


def create_task_with_context[T](
    coro: Coroutine[Any, Any, T],
    *,
    request_id: str | None = None,
    connection_id: str | None = None,
    name: str | None = None,
) -> asyncio.Task[T]:
    """Create an asyncio task with propagated logging context.

    This function creates a task that inherits the current logging context
    (request_id, connection_id) or uses explicitly provided values.

    Args:
        coro: The coroutine to run as a task.
        request_id: Optional explicit request_id. If not provided,
            inherits from current context.
        connection_id: Optional explicit connection_id. If not provided,
            inherits from current context.
        name: Optional name for the task.

    Returns:
        The created Task object.

    Example:
        set_request_id("parent-request")

        async def background_work():
            # request_id will be "parent-request"
            logger.info("Working in background")

        task = create_task_with_context(background_work())
        await task
    """
    # Capture current context values
    current_request_id = request_id if request_id is not None else get_request_id()
    current_connection_id = connection_id if connection_id is not None else get_connection_id()
    current_log_context = get_log_context()

    async def wrapped_coro() -> T:
        # Set the context in the new task
        set_request_id(current_request_id)
        set_connection_id(current_connection_id)

        # Apply log context using the synchronous context manager
        # We need to manually enter the context since we're in an async wrapper
        if current_log_context:
            with log_context(**current_log_context):
                return await coro
        else:
            return await coro

    return asyncio.create_task(wrapped_coro(), name=name)


def create_tracked_task[T](
    coro: Coroutine[Any, Any, T],
    *,
    name: str | None = None,
    task_prefix: str = "task",
    request_id: str | None = None,
    connection_id: str | None = None,
) -> asyncio.Task[T]:
    """Create an asyncio task with automatic task_id generation and tracking.

    This function creates a task with:
    - Automatic unique task_id generation for log correlation
    - Inherited or explicit request_id and connection_id
    - Automatic logging of task start and completion
    - Proper context propagation for structured logging

    The task_id is automatically added to all logs within the task, enabling
    correlation of related log messages from the same async operation.

    Args:
        coro: The coroutine to run as a task.
        name: Optional name for the task. Used in logs and task.get_name().
        task_prefix: Prefix for the generated task_id (e.g., "detect", "analyze").
            Defaults to "task".
        request_id: Optional explicit request_id. If not provided,
            inherits from current context.
        connection_id: Optional explicit connection_id. If not provided,
            inherits from current context.

    Returns:
        The created Task object with tracking context.

    Example:
        # Create a tracked detection task
        task = create_tracked_task(
            process_detection(detection),
            name="process_detection",
            task_prefix="detect"
        )
        # All logs within process_detection will include task_id="detect-a1b2c3d4"

        # Create a tracked analysis task
        task = create_tracked_task(
            analyze_batch(batch),
            name="analyze_batch",
            task_prefix="analyze"
        )
    """
    # Import logger lazily to avoid circular imports
    from backend.core.logging import get_logger

    logger = get_logger(__name__)

    # Generate unique task_id for this task
    task_id = generate_task_id(task_prefix)

    # Capture current context values
    current_request_id = request_id if request_id is not None else get_request_id()
    current_connection_id = connection_id if connection_id is not None else get_connection_id()
    current_log_context = get_log_context()

    # Build context for the task including task_id
    task_context = {**current_log_context, "task_id": task_id}
    if name:
        task_context["task_name"] = name

    async def wrapped_coro() -> T:
        # Set the context in the new task
        set_request_id(current_request_id)
        set_connection_id(current_connection_id)
        set_task_id(task_id)

        with log_context(**task_context):
            logger.debug(f"Task started: {name or 'unnamed'}")
            try:
                return await coro
            finally:
                logger.debug(f"Task completed: {name or 'unnamed'}")

    return asyncio.create_task(wrapped_coro(), name=name)


def copy_context_to_task[**P, R](
    func: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Decorator that ensures coroutines preserve logging context.

    When the decorated coroutine is scheduled as a task, it will
    automatically inherit the logging context (request_id, connection_id)
    from the caller.

    This decorator is useful for background tasks that should maintain
    context for debugging and tracing purposes.

    Usage:
        @copy_context_to_task
        async def background_work():
            # Will have the same request_id as the caller
            logger.info("Processing in background")

        set_request_id("caller-request")
        task = asyncio.create_task(background_work())
        await task

    Note:
        This decorator captures context at decoration time, which happens
        when the coroutine is called (not when the function is defined).
    """

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        # Capture current context at call time
        current_request_id = get_request_id()
        current_connection_id = get_connection_id()
        current_log_context = get_log_context()

        # Set context in the current execution
        set_request_id(current_request_id)
        set_connection_id(current_connection_id)

        # Apply log context if available
        if current_log_context:
            with log_context(**current_log_context):
                return await func(*args, **kwargs)
        else:
            return await func(*args, **kwargs)

    return wrapper


@asynccontextmanager
async def logger_with_context(**context_fields: Any) -> AsyncIterator[None]:
    """Async context manager for adding extra fields to all log messages.

    This context manager adds the specified fields to all log messages
    emitted within its scope. Useful for adding camera_id, operation,
    or other context to a series of related log messages.

    Args:
        **context_fields: Key-value pairs to add to log context.

    Yields:
        None

    Example:
        async with logger_with_context(camera_id="front_door", operation="detection"):
            logger.info("Starting detection")  # Includes camera_id and operation
            await process()
            logger.info("Detection complete")  # Also includes camera_id and operation
    """
    # Use the synchronous log_context from logging module
    with log_context(**context_fields):
        yield
