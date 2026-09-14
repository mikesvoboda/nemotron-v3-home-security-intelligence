"""Tests for async context propagation (NEM-1640).

This module tests structured logging context propagation across async boundaries,
ensuring request_id and connection_id are properly maintained in background tasks
and WebSocket connections.
"""

import asyncio
import logging

import pytest

from backend.core.logging import (
    get_logger,
    get_request_id,
    set_request_id,
)


class TestPropagateLogContext:
    """Tests for the propagate_log_context async context manager."""

    @pytest.mark.asyncio
    async def test_propagate_context_preserves_request_id(self) -> None:
        """Verify context is propagated within the async context manager."""
        from backend.core.async_context import propagate_log_context

        set_request_id("original-id")

        async with propagate_log_context():
            assert get_request_id() == "original-id"

        # After context exit, should still be the original
        assert get_request_id() == "original-id"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_propagate_context_with_explicit_request_id(self) -> None:
        """Verify explicit request_id can be set in the context."""
        from backend.core.async_context import propagate_log_context

        set_request_id("original-id")

        async with propagate_log_context(request_id="explicit-id"):
            assert get_request_id() == "explicit-id"

        # After context exit, should restore the original
        assert get_request_id() == "original-id"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_propagate_context_generates_id_when_none(self) -> None:
        """Verify a request_id is generated when none exists."""
        from backend.core.async_context import propagate_log_context

        set_request_id(None)

        async with propagate_log_context():
            current_id = get_request_id()
            # Should have generated a new ID
            assert current_id is not None
            assert len(current_id) > 0

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_propagate_context_in_background_task(self) -> None:
        """Verify context propagates correctly into background tasks."""
        from backend.core.async_context import propagate_log_context

        captured_ids: list[str | None] = []

        async def background_work() -> None:
            async with propagate_log_context(request_id="task-id"):
                captured_ids.append(get_request_id())
                await asyncio.sleep(0.01)
                captured_ids.append(get_request_id())

        task = asyncio.create_task(background_work())
        await task

        assert captured_ids == ["task-id", "task-id"]

    @pytest.mark.asyncio
    async def test_propagate_context_restores_on_exception(self) -> None:
        """Verify context is restored even when exception occurs."""
        from backend.core.async_context import propagate_log_context

        set_request_id("original-id")

        with pytest.raises(ValueError, match="test error"):
            async with propagate_log_context(request_id="error-context"):
                assert get_request_id() == "error-context"
                raise ValueError("test error")

        # Should be restored after exception
        assert get_request_id() == "original-id"

        # Cleanup
        set_request_id(None)


class TestCreateTaskWithContext:
    """Tests for the create_task_with_context helper function."""

    @pytest.mark.asyncio
    async def test_create_task_preserves_request_id(self) -> None:
        """Verify create_task_with_context preserves the request_id."""
        from backend.core.async_context import create_task_with_context

        captured_id: str | None = None

        async def capture_request_id() -> None:
            nonlocal captured_id
            captured_id = get_request_id()

        set_request_id("parent-request-id")

        task = create_task_with_context(capture_request_id())
        await task

        assert captured_id == "parent-request-id"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_create_task_with_explicit_context(self) -> None:
        """Verify create_task_with_context can override request_id."""
        from backend.core.async_context import create_task_with_context

        captured_ids: list[str | None] = []

        async def capture_request_id() -> None:
            captured_ids.append(get_request_id())

        set_request_id("original-id")

        task = create_task_with_context(capture_request_id(), request_id="overridden-id")
        await task

        assert captured_ids == ["overridden-id"]
        # Main context should be unchanged
        assert get_request_id() == "original-id"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_multiple_tasks_have_isolated_contexts(self) -> None:
        """Verify multiple concurrent tasks maintain isolated contexts."""
        from backend.core.async_context import create_task_with_context

        results: dict[str, str | None] = {}

        async def task_with_delay(task_id: str, delay: float) -> None:
            await asyncio.sleep(delay)
            results[task_id] = get_request_id()

        set_request_id("main-context")

        # Create tasks with different request IDs
        task1 = create_task_with_context(task_with_delay("task1", 0.02), request_id="req-1")
        task2 = create_task_with_context(task_with_delay("task2", 0.01), request_id="req-2")
        task3 = create_task_with_context(task_with_delay("task3", 0.03), request_id="req-3")

        await asyncio.gather(task1, task2, task3)

        assert results["task1"] == "req-1"
        assert results["task2"] == "req-2"
        assert results["task3"] == "req-3"

        # Main context unchanged
        assert get_request_id() == "main-context"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_create_task_propagates_current_context(self) -> None:
        """Verify task inherits current context when no explicit override."""
        from backend.core.async_context import create_task_with_context

        captured_ids: list[str | None] = []

        async def nested_task() -> None:
            captured_ids.append(get_request_id())

        async def outer_task() -> None:
            captured_ids.append(get_request_id())
            # Create nested task without explicit context - should inherit
            inner = create_task_with_context(nested_task())
            await inner

        set_request_id("inherited-id")

        task = create_task_with_context(outer_task())
        await task

        assert captured_ids == ["inherited-id", "inherited-id"]

        # Cleanup
        set_request_id(None)


class TestConnectionIdContext:
    """Tests for WebSocket connection_id context management."""

    @pytest.mark.asyncio
    async def test_set_and_get_connection_id(self) -> None:
        """Verify connection_id can be set and retrieved."""
        from backend.core.async_context import get_connection_id, set_connection_id

        set_connection_id("ws-conn-123")
        assert get_connection_id() == "ws-conn-123"

        set_connection_id(None)
        assert get_connection_id() is None

    @pytest.mark.asyncio
    async def test_connection_id_isolation_between_tasks(self) -> None:
        """Verify connection_ids don't leak between concurrent tasks."""
        from backend.core.async_context import get_connection_id, set_connection_id

        results: dict[str, str | None] = {}

        async def task_with_connection(task_id: str, conn_id: str) -> None:
            set_connection_id(conn_id)
            await asyncio.sleep(0.01)
            results[task_id] = get_connection_id()

        # Run concurrent tasks with different connection IDs
        await asyncio.gather(
            task_with_connection("task1", "conn-1"),
            task_with_connection("task2", "conn-2"),
        )

        assert results["task1"] == "conn-1"
        assert results["task2"] == "conn-2"

    @pytest.mark.asyncio
    async def test_connection_id_in_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify connection_id appears in log records."""
        from backend.core.async_context import set_connection_id

        set_connection_id("ws-test-conn")

        logger = get_logger("test.connection")

        with caplog.at_level(logging.INFO):
            logger.info("WebSocket message received")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "connection_id")
        assert record.connection_id == "ws-test-conn"

        # Cleanup
        set_connection_id(None)


class TestContextFilterEnhanced:
    """Tests for enhanced ContextFilter with connection_id support."""

    def test_context_filter_adds_connection_id(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify ContextFilter adds connection_id to log records."""
        from backend.core.async_context import set_connection_id

        set_connection_id("filter-test-conn")
        set_request_id("filter-test-req")

        logger = get_logger("test.filter")

        with caplog.at_level(logging.INFO):
            logger.info("Test message")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "request_id")
        assert hasattr(record, "connection_id")
        assert record.request_id == "filter-test-req"
        assert record.connection_id == "filter-test-conn"

        # Cleanup
        set_request_id(None)
        set_connection_id(None)


class TestCopyContextToTask:
    """Tests for copy_context_to_task decorator."""

    @pytest.mark.asyncio
    async def test_copy_context_decorator(self) -> None:
        """Verify copy_context_to_task decorator preserves context."""
        from backend.core.async_context import copy_context_to_task

        captured_id: str | None = None

        @copy_context_to_task
        async def decorated_task() -> None:
            nonlocal captured_id
            captured_id = get_request_id()

        set_request_id("decorated-context")

        task = asyncio.create_task(decorated_task())
        await task

        assert captured_id == "decorated-context"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_copy_context_decorator_with_args(self) -> None:
        """Verify copy_context_to_task works with function arguments."""
        from backend.core.async_context import copy_context_to_task

        results: list[tuple[str, str | None]] = []

        @copy_context_to_task
        async def decorated_task(name: str, value: int) -> None:
            results.append((f"{name}={value}", get_request_id()))

        set_request_id("args-context")

        task = asyncio.create_task(decorated_task("test", 42))
        await task

        assert results == [("test=42", "args-context")]

        # Cleanup
        set_request_id(None)


class TestLoggerWithContext:
    """Tests for logger_with_context context manager."""

    @pytest.mark.asyncio
    async def test_logger_with_context_adds_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify logger_with_context adds extra fields to all logs."""
        from backend.core.async_context import logger_with_context

        logger = get_logger("test.logger_context")

        with caplog.at_level(logging.INFO):
            async with logger_with_context(camera_id="front_door", operation="detection"):
                logger.info("Detection started")
                logger.info("Detection completed")

        assert len(caplog.records) == 2
        for record in caplog.records:
            assert hasattr(record, "camera_id")
            assert record.camera_id == "front_door"
            assert hasattr(record, "operation")
            assert record.operation == "detection"

    @pytest.mark.asyncio
    async def test_logger_with_context_restores_on_exit(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify context fields are removed after exiting the context."""
        from backend.core.async_context import (
            get_log_context,
            logger_with_context,
        )

        initial_context = get_log_context()

        async with logger_with_context(camera_id="test_camera"):
            context_inside = get_log_context()
            assert "camera_id" in context_inside

        final_context = get_log_context()
        assert final_context == initial_context
