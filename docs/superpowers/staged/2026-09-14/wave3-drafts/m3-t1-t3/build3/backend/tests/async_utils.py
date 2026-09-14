"""Async testing utilities - backwards compatibility re-exports.

This module has been moved to backend.tests.utils.async_helpers.

For new code, prefer importing from:
    from backend.tests.utils import AsyncClientMock, async_timeout, ...

Or directly from:
    from backend.tests.utils.async_helpers import AsyncClientMock, async_timeout, ...

This file provides backwards-compatible re-exports so existing imports continue to work.
"""

# Re-export everything from the new location for backwards compatibility
from backend.tests.utils.async_helpers import (
    AsyncClientMock,
    AsyncTimeoutError,
    ConcurrentResult,
    async_timeout,
    create_async_mock_client,
    create_async_session_mock,
    create_mock_db_context,
    create_mock_redis_client,
    create_mock_response,
    mock_async_context_manager,
    run_concurrent_tasks,
    simulate_concurrent_requests,
    with_timeout,
)

__all__ = [
    "AsyncClientMock",
    "AsyncTimeoutError",
    "ConcurrentResult",
    "async_timeout",
    "create_async_mock_client",
    "create_async_session_mock",
    "create_mock_db_context",
    "create_mock_redis_client",
    "create_mock_response",
    "mock_async_context_manager",
    "run_concurrent_tasks",
    "simulate_concurrent_requests",
    "with_timeout",
]
