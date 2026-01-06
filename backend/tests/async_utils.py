"""Async testing utilities for the backend test suite.

This module provides standardized patterns and helpers for async testing,
addressing common challenges with mocking async context managers, handling
timeouts, and testing concurrent operations.

Decision: pytest-asyncio vs pytest-anyio
=========================================

After evaluation, this project continues to use **pytest-asyncio** for the following reasons:

1. **Existing Infrastructure**: The project has extensive pytest-asyncio integration
   with `asyncio_mode = "auto"` and 7000+ tests using this pattern.

2. **Backend-specific**: This project only uses asyncio (no trio support needed).
   pytest-anyio's multi-backend support adds complexity without benefit.

3. **Module-scoped fixtures**: pytest-anyio's fixture scope handling is more complex.
   Our integration tests use function-scoped fixtures with testcontainers, which
   works well with pytest-asyncio's current implementation.

4. **Migration cost**: Converting to pytest-anyio would require updating fixtures
   in conftest.py and potentially all async test functions.

5. **Maturity**: pytest-asyncio has better documentation and community support
   for our specific use case (FastAPI + SQLAlchemy + httpx).

Instead, we improve our async testing patterns within pytest-asyncio by:
- Standardizing async context manager mocking
- Providing timeout utilities for flaky tests
- Adding helpers for concurrent test execution

Usage Examples
==============

Mock an async client with context manager support:

    >>> async with create_async_mock_client(get_response={"status": "ok"}) as mock:
    ...     result = await mock.get("/health")
    ...     assert result.json() == {"status": "ok"}

Use timeout protection for flaky operations:

    >>> async with async_timeout(5.0):
    ...     await some_flaky_operation()

Test concurrent operations:

    >>> results = await run_concurrent_tasks(
    ...     task1_coro,
    ...     task2_coro,
    ...     task3_coro,
    ... )
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine, Sequence

# =============================================================================
# Async Context Manager Helpers
# =============================================================================


@asynccontextmanager
async def mock_async_context_manager[T](
    return_value: T | None = None,
    enter_side_effect: Exception | None = None,
    exit_side_effect: Exception | None = None,
) -> AsyncGenerator[T | MagicMock]:
    """Create a mock async context manager that can be used with `async with`.

    This helper simplifies the verbose pattern of setting up __aenter__ and __aexit__
    on AsyncMock objects.

    Args:
        return_value: Value to return when entering the context. If None, returns
            an AsyncMock instance.
        enter_side_effect: Exception to raise when entering the context.
        exit_side_effect: Exception to raise when exiting the context.

    Yields:
        The return_value or a new AsyncMock if return_value is None.

    Example:
        >>> async with mock_async_context_manager(return_value=mock_session) as session:
        ...     await session.execute(query)

    Replaces the verbose pattern:
        >>> mock_client = AsyncMock()
        >>> mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        >>> mock_client.__aexit__ = AsyncMock(return_value=None)
    """
    if enter_side_effect:
        raise enter_side_effect

    result = return_value if return_value is not None else MagicMock()
    try:
        yield result
    finally:
        if exit_side_effect:
            raise exit_side_effect


@dataclass
class AsyncClientMock:
    """A pre-configured mock for async HTTP clients (httpx.AsyncClient).

    Provides a realistic mock that supports:
    - Async context manager protocol (__aenter__/__aexit__)
    - Common HTTP methods (get, post, put, delete, patch)
    - Response customization
    - Call tracking

    Example:
        >>> mock = AsyncClientMock(
        ...     get_responses={"/health": {"status": "healthy"}},
        ...     post_responses={"/api/detect": {"detections": []}},
        ... )
        >>> async with mock.client() as client:
        ...     response = await client.get("/health")
        ...     assert response.json() == {"status": "healthy"}
    """

    get_responses: dict[str, Any] = field(default_factory=dict)
    post_responses: dict[str, Any] = field(default_factory=dict)
    put_responses: dict[str, Any] = field(default_factory=dict)
    delete_responses: dict[str, Any] = field(default_factory=dict)
    patch_responses: dict[str, Any] = field(default_factory=dict)
    default_status_code: int = 200
    raise_on_missing: bool = False
    calls: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def _create_response(self, data: Any, status_code: int | None = None) -> MagicMock:
        """Create a mock response object."""
        response = MagicMock()
        response.json.return_value = data
        response.status_code = status_code or self.default_status_code
        response.raise_for_status = MagicMock()
        response.text = str(data)
        response.content = str(data).encode()
        return response

    async def _handle_request(
        self,
        method: str,
        url: str,
        responses: dict[str, Any],
        **kwargs: Any,
    ) -> MagicMock:
        """Handle a mock HTTP request."""
        self.calls.append((method, url, kwargs))

        # Check for matching URL pattern
        for pattern, response_data in responses.items():
            if pattern in url or url.endswith(pattern):
                if isinstance(response_data, Exception):
                    raise response_data
                return self._create_response(response_data)

        if self.raise_on_missing:
            raise KeyError(f"No mock response configured for {method} {url}")

        return self._create_response({})

    def _create_mock_client(self) -> AsyncMock:
        """Create the mock client with all HTTP methods configured."""
        mock = AsyncMock()

        async def mock_get(url: str, **kwargs: Any) -> MagicMock:
            return await self._handle_request("GET", url, self.get_responses, **kwargs)

        async def mock_post(url: str, **kwargs: Any) -> MagicMock:
            return await self._handle_request("POST", url, self.post_responses, **kwargs)

        async def mock_put(url: str, **kwargs: Any) -> MagicMock:
            return await self._handle_request("PUT", url, self.put_responses, **kwargs)

        async def mock_delete(url: str, **kwargs: Any) -> MagicMock:
            return await self._handle_request("DELETE", url, self.delete_responses, **kwargs)

        async def mock_patch(url: str, **kwargs: Any) -> MagicMock:
            return await self._handle_request("PATCH", url, self.patch_responses, **kwargs)

        mock.get = mock_get
        mock.post = mock_post
        mock.put = mock_put
        mock.delete = mock_delete
        mock.patch = mock_patch

        return mock

    @asynccontextmanager
    async def client(self) -> AsyncGenerator[AsyncMock]:
        """Get the mock client as an async context manager.

        This is the primary way to use AsyncClientMock, matching the
        typical httpx.AsyncClient usage pattern.

        Example:
            >>> mock = AsyncClientMock(get_responses={"/health": {"status": "ok"}})
            >>> async with mock.client() as client:
            ...     response = await client.get("/health")
        """
        yield self._create_mock_client()


def create_async_mock_client(
    get_responses: dict[str, Any] | None = None,
    post_responses: dict[str, Any] | None = None,
    default_status_code: int = 200,
) -> AsyncClientMock:
    """Factory function to create an AsyncClientMock with common defaults.

    This is a convenience wrapper around AsyncClientMock for simple cases.

    Args:
        get_responses: Map of URL patterns to response data for GET requests.
        post_responses: Map of URL patterns to response data for POST requests.
        default_status_code: Default HTTP status code for all responses.

    Returns:
        Configured AsyncClientMock instance.

    Example:
        >>> mock = create_async_mock_client(
        ...     get_responses={"/health": {"status": "healthy"}},
        ...     post_responses={"/detect": {"detections": []}},
        ... )
    """
    return AsyncClientMock(
        get_responses=get_responses or {},
        post_responses=post_responses or {},
        default_status_code=default_status_code,
    )


# =============================================================================
# Improved AsyncMock Patterns
# =============================================================================


def create_async_session_mock(
    execute_results: Sequence[Any] | None = None,
    scalar_results: Sequence[Any] | None = None,
) -> AsyncMock:
    """Create a mock SQLAlchemy async session with common operations configured.

    This helper creates a mock session that behaves like a real AsyncSession,
    with configurable return values for execute() and scalar() operations.

    Args:
        execute_results: Sequence of results to return from execute() calls.
            Each call to execute() returns the next result in sequence.
        scalar_results: Sequence of results to return from scalar_one_or_none() calls.

    Returns:
        Configured AsyncMock that can be used as an async session.

    Example:
        >>> mock_session = create_async_session_mock(
        ...     execute_results=[mock_camera_result, mock_detection_result],
        ... )
        >>> result = await mock_session.execute(query)
    """
    mock_session = AsyncMock()

    # Configure execute() to return results in sequence
    if execute_results:
        results_iter = iter(execute_results)

        async def mock_execute(query: Any) -> Any:
            try:
                return next(results_iter)
            except StopIteration:
                return MagicMock()

        mock_session.execute = mock_execute
    else:
        mock_session.execute = AsyncMock(return_value=MagicMock())

    # Configure scalar operations
    if scalar_results:
        scalar_iter = iter(scalar_results)

        def create_scalar_result() -> MagicMock:
            result = MagicMock()
            try:
                result.scalar_one_or_none.return_value = next(scalar_iter)
            except StopIteration:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = AsyncMock(side_effect=lambda _query: create_scalar_result())

    # Configure common session operations
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.flush = AsyncMock()

    return mock_session


def create_mock_db_context(session: AsyncMock) -> AsyncMock:
    """Create a mock database context manager that yields the given session.

    This simplifies testing code that uses `async with get_session() as session:`.

    Args:
        session: The mock session to yield from the context manager.

    Returns:
        AsyncMock configured as an async context manager.

    Example:
        >>> mock_session = create_async_session_mock()
        >>> mock_context = create_mock_db_context(mock_session)
        >>> with patch("backend.core.database.get_session", return_value=mock_context):
        ...     async with get_session() as session:
        ...         # session is mock_session
    """
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=session)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    return mock_context


# =============================================================================
# Timeout Utilities
# =============================================================================


class AsyncTimeoutError(TimeoutError):
    """Custom timeout error for async operations in tests."""

    def __init__(self, timeout: float, operation: str | None = None):
        self.timeout = timeout
        self.operation = operation
        message = f"Operation timed out after {timeout}s"
        if operation:
            message = f"{operation} timed out after {timeout}s"
        super().__init__(message)


@asynccontextmanager
async def async_timeout(
    seconds: float,
    operation: str | None = None,
) -> AsyncGenerator[None]:
    """Context manager for timing out async operations in tests.

    Provides better error messages than bare asyncio.timeout() and allows
    specifying an operation name for debugging.

    Args:
        seconds: Maximum time to wait before raising AsyncTimeoutError.
        operation: Optional description of the operation (for error messages).

    Raises:
        AsyncTimeoutError: If the operation takes longer than the specified timeout.

    Example:
        >>> async with async_timeout(5.0, operation="health check"):
        ...     await client.health_check()
    """
    try:
        async with asyncio.timeout(seconds):
            yield
    except TimeoutError as e:
        raise AsyncTimeoutError(seconds, operation) from e


async def with_timeout[T](
    coro: Coroutine[Any, Any, T],
    timeout: float,
    operation: str | None = None,
) -> T:
    """Execute a coroutine with a timeout.

    This is a convenience function for cases where you don't need a context
    manager but want timeout protection on a single operation.

    Args:
        coro: The coroutine to execute.
        timeout: Maximum time to wait in seconds.
        operation: Optional description for error messages.

    Returns:
        The result of the coroutine.

    Raises:
        AsyncTimeoutError: If the coroutine takes longer than the timeout.

    Example:
        >>> result = await with_timeout(
        ...     client.get_data(),
        ...     timeout=5.0,
        ...     operation="fetching data",
        ... )
    """
    async with async_timeout(timeout, operation):
        return await coro


# =============================================================================
# Concurrent Testing Utilities
# =============================================================================


@dataclass
class ConcurrentResult:
    """Result from concurrent task execution."""

    results: list[Any]
    errors: list[Exception]
    duration_seconds: float

    @property
    def all_succeeded(self) -> bool:
        """Check if all tasks completed without errors."""
        return len(self.errors) == 0

    @property
    def success_count(self) -> int:
        """Number of tasks that succeeded."""
        return len(self.results) - len(self.errors)


async def run_concurrent_tasks[T](
    *coros: Coroutine[Any, Any, T],
    return_exceptions: bool = True,
) -> ConcurrentResult:
    """Run multiple coroutines concurrently and collect results.

    This helper properly tests concurrent operations using asyncio.TaskGroup
    (Python 3.11+) for structured concurrency.

    Args:
        *coros: Coroutines to run concurrently.
        return_exceptions: If True, exceptions are returned in the errors list
            instead of being raised immediately.

    Returns:
        ConcurrentResult containing results, errors, and timing information.

    Example:
        >>> result = await run_concurrent_tasks(
        ...     client.get("/endpoint1"),
        ...     client.get("/endpoint2"),
        ...     client.get("/endpoint3"),
        ... )
        >>> assert result.all_succeeded
        >>> assert len(result.results) == 3
    """
    import time

    start_time = time.monotonic()
    results: list[Any] = []
    errors: list[Exception] = []

    if return_exceptions:
        # Use gather with return_exceptions for non-blocking collection
        gathered = await asyncio.gather(*coros, return_exceptions=True)
        for item in gathered:
            if isinstance(item, Exception):
                errors.append(item)
            results.append(item)
    else:
        # Use TaskGroup for strict error handling
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(coro) for coro in coros]
        results = [task.result() for task in tasks]

    duration = time.monotonic() - start_time
    return ConcurrentResult(results=results, errors=errors, duration_seconds=duration)


async def simulate_concurrent_requests[T](
    request_fn: Callable[[], Awaitable[T]],
    count: int,
    delay_between: float = 0.0,
) -> ConcurrentResult:
    """Simulate multiple concurrent requests to test rate limiting, connection pooling, etc.

    Args:
        request_fn: Async function that makes a request.
        count: Number of concurrent requests to make.
        delay_between: Optional delay between starting each request.

    Returns:
        ConcurrentResult with all request results.

    Example:
        >>> result = await simulate_concurrent_requests(
        ...     lambda: client.get("/api/health"),
        ...     count=10,
        ...     delay_between=0.01,
        ... )
        >>> assert result.all_succeeded
    """

    async def make_request(index: int) -> T:
        if delay_between > 0 and index > 0:
            await asyncio.sleep(delay_between * index)
        return await request_fn()

    coros = [make_request(i) for i in range(count)]
    return await run_concurrent_tasks(*coros)


# =============================================================================
# Test Data Factories
# =============================================================================


def create_mock_response(
    json_data: dict[str, Any] | None = None,
    status_code: int = 200,
    text: str = "",
    raise_for_status_error: Exception | None = None,
) -> MagicMock:
    """Create a mock HTTP response object.

    Args:
        json_data: Data to return from response.json().
        status_code: HTTP status code.
        text: Response text content.
        raise_for_status_error: Exception to raise when raise_for_status() is called.

    Returns:
        MagicMock configured as an HTTP response.

    Example:
        >>> response = create_mock_response(
        ...     json_data={"status": "ok"},
        ...     status_code=200,
        ... )
        >>> assert response.json() == {"status": "ok"}
    """
    mock = MagicMock()
    mock.json.return_value = json_data or {}
    mock.status_code = status_code
    mock.text = text or str(json_data)
    mock.content = mock.text.encode()

    if raise_for_status_error:
        mock.raise_for_status.side_effect = raise_for_status_error
    else:
        mock.raise_for_status = MagicMock()

    return mock


# =============================================================================
# Redis Mock Helpers
# =============================================================================


def create_mock_redis_client(
    get_values: dict[str, Any] | None = None,
    publish_return: int = 1,
) -> AsyncMock:
    """Create a mock Redis client with common operations pre-configured.

    Args:
        get_values: Map of keys to values for get() operations.
        publish_return: Return value for publish() calls (number of subscribers).

    Returns:
        AsyncMock configured as a Redis client.

    Example:
        >>> mock_redis = create_mock_redis_client(
        ...     get_values={"batch:123:camera_id": "front_door"},
        ... )
    """
    mock = AsyncMock()

    # Configure get() to return values from dict
    if get_values:

        async def mock_get(key: str) -> Any | None:
            return get_values.get(key)

        mock.get = mock_get
    else:
        mock.get = AsyncMock(return_value=None)

    # Configure common operations
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.publish = AsyncMock(return_value=publish_return)
    mock.health_check = AsyncMock(
        return_value={"status": "healthy", "connected": True, "redis_version": "7.0.0"}
    )

    return mock
