"""Comprehensive unit tests for async_context.py (NEM-2759).

This module provides comprehensive unit test coverage for async context management
utilities, ensuring proper context variable management, async context propagation,
context isolation between tasks, and error handling in context operations.

Test Coverage:
    - Context variable management (get/set connection_id)
    - Async context propagation (propagate_log_context)
    - Context isolation between concurrent tasks
    - Task creation with context (create_task_with_context)
    - Context copying decorator (copy_context_to_task)
    - Logger context manager (logger_with_context)
    - Error handling and cleanup in all context operations
    - Edge cases and boundary conditions

Related Files:
    - backend/core/async_context.py: Implementation under test
    - backend/core/logging.py: Logging context utilities
"""

import asyncio
import logging

import pytest

from backend.core.async_context import (
    copy_context_to_task,
    create_task_with_context,
    get_connection_id,
    get_log_context,
    logger_with_context,
    propagate_log_context,
    set_connection_id,
)
from backend.core.logging import get_logger, get_request_id, set_request_id

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Context Variable Management Tests
# =============================================================================


class TestConnectionIdContextVariable:
    """Tests for connection_id context variable management.

    Tests the fundamental get/set operations for the connection_id context
    variable, including default values, token management, and restoration.
    """

    def test_get_connection_id_default_is_none(self) -> None:
        """Verify connection_id defaults to None when not set.

        Given: A fresh context with no connection_id set
        When: get_connection_id() is called
        Then: Returns None
        """
        # Ensure clean state
        set_connection_id(None)
        assert get_connection_id() is None

    def test_set_and_get_connection_id(self) -> None:
        """Verify connection_id can be set and retrieved.

        Given: No connection_id is set
        When: set_connection_id() is called with a value
        Then: get_connection_id() returns that value
        """
        token = set_connection_id("test-conn-123")
        assert get_connection_id() == "test-conn-123"

        # Cleanup
        set_connection_id(None)

    def test_set_connection_id_returns_token(self) -> None:
        """Verify set_connection_id returns a restoration token.

        Given: A connection_id is set
        When: set_connection_id() is called
        Then: A token is returned that can restore previous value
        """
        # Set initial value
        set_connection_id("initial-conn")

        # Set new value and capture token
        token = set_connection_id("new-conn")
        assert get_connection_id() == "new-conn"

        # Token should be a valid token object
        assert token is not None

        # Cleanup
        set_connection_id(None)

    def test_set_connection_id_to_none_clears_value(self) -> None:
        """Verify setting connection_id to None clears it.

        Given: A connection_id is set to a value
        When: set_connection_id(None) is called
        Then: get_connection_id() returns None
        """
        set_connection_id("some-conn")
        assert get_connection_id() == "some-conn"

        set_connection_id(None)
        assert get_connection_id() is None

    def test_connection_id_can_be_updated(self) -> None:
        """Verify connection_id can be updated to a new value.

        Given: A connection_id is already set
        When: set_connection_id() is called with a different value
        Then: The new value replaces the old value
        """
        set_connection_id("old-conn")
        assert get_connection_id() == "old-conn"

        set_connection_id("new-conn")
        assert get_connection_id() == "new-conn"

        # Cleanup
        set_connection_id(None)

    @pytest.mark.asyncio
    async def test_connection_id_isolation_between_tasks(self) -> None:
        """Verify connection_id maintains isolation between concurrent tasks.

        Given: Multiple concurrent async tasks
        When: Each task sets its own connection_id
        Then: Each task sees only its own value, no cross-contamination
        """
        results: dict[str, str | None] = {}

        async def task_with_connection(task_name: str, conn_id: str) -> None:
            set_connection_id(conn_id)
            await asyncio.sleep(0.01)  # Yield to other tasks
            results[task_name] = get_connection_id()

        # Run tasks concurrently
        await asyncio.gather(
            task_with_connection("task1", "conn-1"),
            task_with_connection("task2", "conn-2"),
            task_with_connection("task3", "conn-3"),
        )

        # Each task should see its own connection_id
        assert results["task1"] == "conn-1"
        assert results["task2"] == "conn-2"
        assert results["task3"] == "conn-3"


# =============================================================================
# Propagate Log Context Tests
# =============================================================================


class TestPropagateLogContext:
    """Tests for propagate_log_context async context manager.

    Tests the async context manager that propagates logging context
    (request_id) across async boundaries, including explicit values,
    automatic generation, and restoration on exit.
    """

    @pytest.mark.asyncio
    async def test_propagate_with_explicit_request_id(self) -> None:
        """Verify explicit request_id is set within the context.

        Given: An explicit request_id value
        When: propagate_log_context(request_id=value) is used
        Then: The request_id is set for the duration of the context
        """
        set_request_id("original-id")

        async with propagate_log_context(request_id="explicit-id"):
            assert get_request_id() == "explicit-id"

        # Should restore original after exit
        assert get_request_id() == "original-id"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_propagate_preserves_existing_request_id(self) -> None:
        """Verify existing request_id is preserved when no explicit value given.

        Given: A request_id is already set in context
        When: propagate_log_context() is used without arguments
        Then: The existing request_id is maintained
        """
        set_request_id("existing-id")

        async with propagate_log_context():
            assert get_request_id() == "existing-id"

        assert get_request_id() == "existing-id"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_propagate_generates_id_when_none_exists(self) -> None:
        """Verify a request_id is generated when none exists.

        Given: No request_id is set in context
        When: propagate_log_context() is used
        Then: A new request_id is automatically generated
        """
        set_request_id(None)

        async with propagate_log_context():
            generated_id = get_request_id()
            assert generated_id is not None
            assert len(generated_id) > 0
            # Should be 8 characters (UUID prefix)
            assert len(generated_id) == 8

        # After context, should be None again
        assert get_request_id() is None

    @pytest.mark.asyncio
    async def test_propagate_restores_previous_request_id_on_exit(self) -> None:
        """Verify previous request_id is restored after context exit.

        Given: A request_id is set, then changed within context
        When: The context exits
        Then: The original request_id is restored
        """
        set_request_id("original-id")

        async with propagate_log_context(request_id="temporary-id"):
            assert get_request_id() == "temporary-id"

        assert get_request_id() == "original-id"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_propagate_restores_on_exception(self) -> None:
        """Verify context is restored even when exception occurs.

        Given: A request_id is set in context
        When: An exception is raised within propagate_log_context
        Then: The original request_id is still restored
        """
        set_request_id("original-id")

        with pytest.raises(ValueError, match="test error"):
            async with propagate_log_context(request_id="error-context"):
                assert get_request_id() == "error-context"
                raise ValueError("test error")

        # Should be restored despite exception
        assert get_request_id() == "original-id"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_propagate_nested_contexts(self) -> None:
        """Verify nested contexts work correctly.

        Given: Multiple nested propagate_log_context contexts
        When: Entering and exiting nested contexts
        Then: Each context level maintains its own request_id
        """
        set_request_id("level-0")

        async with propagate_log_context(request_id="level-1"):
            assert get_request_id() == "level-1"

            async with propagate_log_context(request_id="level-2"):
                assert get_request_id() == "level-2"

            # Back to level-1
            assert get_request_id() == "level-1"

        # Back to level-0
        assert get_request_id() == "level-0"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_propagate_in_concurrent_tasks(self) -> None:
        """Verify propagate_log_context works in concurrent tasks.

        Given: Multiple concurrent tasks using propagate_log_context
        When: Tasks run concurrently with different request_ids
        Then: Each task maintains its own isolated request_id
        """
        results: dict[str, list[str | None]] = {}

        async def task_with_propagate(task_name: str, request_id: str) -> None:
            results[task_name] = []
            async with propagate_log_context(request_id=request_id):
                results[task_name].append(get_request_id())
                await asyncio.sleep(0.01)
                results[task_name].append(get_request_id())

        await asyncio.gather(
            task_with_propagate("task1", "req-1"),
            task_with_propagate("task2", "req-2"),
            task_with_propagate("task3", "req-3"),
        )

        assert results["task1"] == ["req-1", "req-1"]
        assert results["task2"] == ["req-2", "req-2"]
        assert results["task3"] == ["req-3", "req-3"]


# =============================================================================
# Create Task With Context Tests
# =============================================================================


class TestCreateTaskWithContext:
    """Tests for create_task_with_context helper function.

    Tests the function that creates asyncio tasks with preserved logging
    context, including request_id, connection_id, and log context fields.
    """

    @pytest.mark.asyncio
    async def test_create_task_inherits_request_id(self) -> None:
        """Verify created task inherits current request_id.

        Given: A request_id is set in the parent context
        When: create_task_with_context() is called
        Then: The task executes with the parent's request_id
        """
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
    async def test_create_task_inherits_connection_id(self) -> None:
        """Verify created task inherits current connection_id.

        Given: A connection_id is set in the parent context
        When: create_task_with_context() is called
        Then: The task executes with the parent's connection_id
        """
        captured_conn_id: str | None = None

        async def capture_connection_id() -> None:
            nonlocal captured_conn_id
            captured_conn_id = get_connection_id()

        set_connection_id("parent-conn-id")

        task = create_task_with_context(capture_connection_id())
        await task

        assert captured_conn_id == "parent-conn-id"

        # Cleanup
        set_connection_id(None)

    @pytest.mark.asyncio
    async def test_create_task_with_explicit_request_id(self) -> None:
        """Verify explicit request_id overrides parent context.

        Given: A request_id is set in parent context
        When: create_task_with_context(request_id=value) is called
        Then: The task uses the explicit value, not the parent's
        """
        captured_id: str | None = None

        async def capture_request_id() -> None:
            nonlocal captured_id
            captured_id = get_request_id()

        set_request_id("parent-id")

        task = create_task_with_context(capture_request_id(), request_id="explicit-id")
        await task

        assert captured_id == "explicit-id"
        # Parent context unchanged
        assert get_request_id() == "parent-id"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_create_task_with_explicit_connection_id(self) -> None:
        """Verify explicit connection_id overrides parent context.

        Given: A connection_id is set in parent context
        When: create_task_with_context(connection_id=value) is called
        Then: The task uses the explicit value, not the parent's
        """
        captured_conn_id: str | None = None

        async def capture_connection_id() -> None:
            nonlocal captured_conn_id
            captured_conn_id = get_connection_id()

        set_connection_id("parent-conn")

        task = create_task_with_context(capture_connection_id(), connection_id="explicit-conn")
        await task

        assert captured_conn_id == "explicit-conn"
        # Parent context unchanged
        assert get_connection_id() == "parent-conn"

        # Cleanup
        set_connection_id(None)

    @pytest.mark.asyncio
    async def test_create_task_with_name(self) -> None:
        """Verify task name is set when provided.

        Given: A name parameter is provided
        When: create_task_with_context() is called
        Then: The created task has the specified name
        """

        async def dummy_coro() -> None:
            await asyncio.sleep(0.001)

        task = create_task_with_context(dummy_coro(), name="test-task")

        assert task.get_name() == "test-task"

        await task

    @pytest.mark.asyncio
    async def test_create_task_isolation_between_tasks(self) -> None:
        """Verify multiple tasks maintain isolated contexts.

        Given: Multiple tasks created with different contexts
        When: Tasks run concurrently
        Then: Each task sees only its own context values
        """
        results: dict[str, tuple[str | None, str | None]] = {}

        async def capture_context(task_id: str) -> None:
            await asyncio.sleep(0.01)  # Yield to other tasks
            results[task_id] = (get_request_id(), get_connection_id())

        set_request_id("main-request")
        set_connection_id("main-conn")

        task1 = create_task_with_context(
            capture_context("task1"), request_id="req-1", connection_id="conn-1"
        )
        task2 = create_task_with_context(
            capture_context("task2"), request_id="req-2", connection_id="conn-2"
        )
        task3 = create_task_with_context(
            capture_context("task3"), request_id="req-3", connection_id="conn-3"
        )

        await asyncio.gather(task1, task2, task3)

        assert results["task1"] == ("req-1", "conn-1")
        assert results["task2"] == ("req-2", "conn-2")
        assert results["task3"] == ("req-3", "conn-3")

        # Main context unchanged
        assert get_request_id() == "main-request"
        assert get_connection_id() == "main-conn"

        # Cleanup
        set_request_id(None)
        set_connection_id(None)

    @pytest.mark.asyncio
    async def test_create_task_with_log_context(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log context is propagated to created tasks.

        Given: Log context fields are set in parent
        When: A task is created with create_task_with_context
        Then: The task inherits the log context fields
        """
        from backend.core.logging import log_context

        logger = get_logger("test.task_context")

        async def log_in_task() -> None:
            with caplog.at_level(logging.INFO):
                logger.info("Message from task")

        with log_context(camera_id="front_door", operation="detection"):
            task = create_task_with_context(log_in_task())
            await task

        # Verify the log record has the context fields
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "camera_id")
        assert record.camera_id == "front_door"
        assert hasattr(record, "operation")
        assert record.operation == "detection"

    @pytest.mark.asyncio
    async def test_create_task_handles_none_context_values(self) -> None:
        """Verify task creation works when context values are None.

        Given: No request_id or connection_id is set
        When: create_task_with_context() is called
        Then: Task is created successfully with None values
        """
        captured_request_id: str | None = "not-set"
        captured_conn_id: str | None = "not-set"

        async def capture_context() -> None:
            nonlocal captured_request_id, captured_conn_id
            captured_request_id = get_request_id()
            captured_conn_id = get_connection_id()

        set_request_id(None)
        set_connection_id(None)

        task = create_task_with_context(capture_context())
        await task

        assert captured_request_id is None
        assert captured_conn_id is None

    @pytest.mark.asyncio
    async def test_create_task_returns_task_result(self) -> None:
        """Verify task return value is preserved.

        Given: A coroutine that returns a value
        When: Wrapped in create_task_with_context
        Then: The task result is the coroutine's return value
        """

        async def return_value() -> str:
            return "test-result"

        task = create_task_with_context(return_value())
        result = await task

        assert result == "test-result"


# =============================================================================
# Copy Context To Task Decorator Tests
# =============================================================================


class TestCopyContextToTaskDecorator:
    """Tests for copy_context_to_task decorator.

    Tests the decorator that automatically captures and propagates logging
    context when a decorated coroutine is scheduled as a task.
    """

    @pytest.mark.asyncio
    async def test_decorator_preserves_request_id(self) -> None:
        """Verify decorated function preserves request_id.

        Given: A function decorated with @copy_context_to_task
        When: The function is called as a task
        Then: It executes with the caller's request_id
        """
        captured_id: str | None = None

        @copy_context_to_task
        async def decorated_func() -> None:
            nonlocal captured_id
            captured_id = get_request_id()

        set_request_id("caller-request")

        task = asyncio.create_task(decorated_func())
        await task

        assert captured_id == "caller-request"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_decorator_preserves_connection_id(self) -> None:
        """Verify decorated function preserves connection_id.

        Given: A function decorated with @copy_context_to_task
        When: The function is called as a task
        Then: It executes with the caller's connection_id
        """
        captured_conn_id: str | None = None

        @copy_context_to_task
        async def decorated_func() -> None:
            nonlocal captured_conn_id
            captured_conn_id = get_connection_id()

        set_connection_id("caller-conn")

        task = asyncio.create_task(decorated_func())
        await task

        assert captured_conn_id == "caller-conn"

        # Cleanup
        set_connection_id(None)

    @pytest.mark.asyncio
    async def test_decorator_with_function_arguments(self) -> None:
        """Verify decorator works with function parameters.

        Given: A decorated function with parameters
        When: Called with arguments
        Then: Arguments are passed through correctly
        """
        results: list[tuple[str, int, str | None]] = []

        @copy_context_to_task
        async def decorated_func(name: str, value: int) -> None:
            results.append((name, value, get_request_id()))

        set_request_id("args-context")

        task = asyncio.create_task(decorated_func("test", 42))
        await task

        assert results == [("test", 42, "args-context")]

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_decorator_with_return_value(self) -> None:
        """Verify decorator preserves function return value.

        Given: A decorated function that returns a value
        When: Called and awaited
        Then: The return value is preserved
        """

        @copy_context_to_task
        async def decorated_func(x: int, y: int) -> int:
            return x + y

        task = asyncio.create_task(decorated_func(3, 4))
        result = await task

        assert result == 7

    @pytest.mark.asyncio
    async def test_decorator_with_log_context(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify decorator preserves log context fields.

        Given: Log context fields are set in caller
        When: Decorated function is called as a task
        Then: Log context fields are preserved
        """
        from backend.core.logging import log_context

        logger = get_logger("test.decorator_context")

        @copy_context_to_task
        async def decorated_func() -> None:
            with caplog.at_level(logging.INFO):
                logger.info("Message from decorated task")

        with log_context(camera_id="back_door", operation="monitoring"):
            task = asyncio.create_task(decorated_func())
            await task

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "camera_id")
        assert record.camera_id == "back_door"
        assert hasattr(record, "operation")
        assert record.operation == "monitoring"

    @pytest.mark.asyncio
    async def test_decorator_isolation_between_tasks(self) -> None:
        """Verify decorated tasks maintain isolated contexts.

        Given: Multiple tasks using decorated function
        When: Each called with different context
        Then: Each maintains its own isolated context
        """
        results: dict[str, str | None] = {}

        @copy_context_to_task
        async def decorated_func(task_id: str) -> None:
            await asyncio.sleep(0.01)
            results[task_id] = get_request_id()

        set_request_id("req-1")
        task1 = asyncio.create_task(decorated_func("task1"))

        set_request_id("req-2")
        task2 = asyncio.create_task(decorated_func("task2"))

        set_request_id("req-3")
        task3 = asyncio.create_task(decorated_func("task3"))

        await asyncio.gather(task1, task2, task3)

        assert results["task1"] == "req-1"
        assert results["task2"] == "req-2"
        assert results["task3"] == "req-3"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_decorator_handles_none_context(self) -> None:
        """Verify decorator works when context values are None.

        Given: No context values are set
        When: Decorated function is called
        Then: Function executes successfully with None values
        """
        captured_request_id: str | None = "not-set"
        captured_conn_id: str | None = "not-set"

        @copy_context_to_task
        async def decorated_func() -> None:
            nonlocal captured_request_id, captured_conn_id
            captured_request_id = get_request_id()
            captured_conn_id = get_connection_id()

        set_request_id(None)
        set_connection_id(None)

        task = asyncio.create_task(decorated_func())
        await task

        assert captured_request_id is None
        assert captured_conn_id is None

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self) -> None:
        """Verify decorator preserves function name and docstring.

        Given: A function with name and docstring
        When: Decorated with @copy_context_to_task
        Then: Function metadata is preserved via functools.wraps
        """

        @copy_context_to_task
        async def my_function() -> None:
            """This is my function."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "This is my function."


# =============================================================================
# Logger With Context Tests
# =============================================================================


class TestLoggerWithContext:
    """Tests for logger_with_context async context manager.

    Tests the async context manager that adds extra fields to all log
    messages within its scope, useful for structured logging.
    """

    @pytest.mark.asyncio
    async def test_logger_with_context_adds_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify logger_with_context adds fields to log records.

        Given: A logger_with_context with extra fields
        When: Log messages are emitted within the context
        Then: All messages include the extra fields
        """
        logger = get_logger("test.logger_context")

        with caplog.at_level(logging.INFO):
            async with logger_with_context(camera_id="front_door", operation="detection"):
                logger.info("First message")
                logger.info("Second message")

        assert len(caplog.records) == 2
        for record in caplog.records:
            assert hasattr(record, "camera_id")
            assert record.camera_id == "front_door"
            assert hasattr(record, "operation")
            assert record.operation == "detection"

    @pytest.mark.asyncio
    async def test_logger_with_context_removes_fields_on_exit(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify context fields are removed after exiting.

        Given: logger_with_context adds fields within a scope
        When: The context exits
        Then: Fields are no longer present in subsequent logs
        """
        logger = get_logger("test.logger_exit")

        with caplog.at_level(logging.INFO):
            async with logger_with_context(camera_id="test_camera"):
                logger.info("Inside context")

            logger.info("Outside context")

        assert len(caplog.records) == 2
        inside_record = caplog.records[0]
        outside_record = caplog.records[1]

        assert hasattr(inside_record, "camera_id")
        assert inside_record.camera_id == "test_camera"

        # Outside record should not have camera_id or it should be None
        if hasattr(outside_record, "camera_id"):
            assert outside_record.camera_id is None

    @pytest.mark.asyncio
    async def test_logger_with_context_restores_on_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify context is restored even when exception occurs.

        Given: logger_with_context is active
        When: An exception is raised within the context
        Then: Context fields are still cleaned up properly
        """

        initial_context = get_log_context()

        with pytest.raises(RuntimeError, match="test error"):
            async with logger_with_context(camera_id="error_camera"):
                context_inside = get_log_context()
                assert "camera_id" in context_inside
                raise RuntimeError("test error")

        final_context = get_log_context()
        assert final_context == initial_context

    @pytest.mark.asyncio
    async def test_logger_with_context_multiple_fields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify multiple context fields can be added.

        Given: logger_with_context with multiple key-value pairs
        When: Log messages are emitted
        Then: All fields are present in log records
        """
        logger = get_logger("test.multi_fields")

        with caplog.at_level(logging.INFO):
            async with logger_with_context(
                camera_id="kitchen",
                operation="scan",
                batch_id="batch-123",
                user_id=42,
            ):
                logger.info("Multi-field log")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "camera_id")
        assert record.camera_id == "kitchen"
        assert hasattr(record, "operation")
        assert record.operation == "scan"
        assert hasattr(record, "batch_id")
        assert record.batch_id == "batch-123"
        assert hasattr(record, "user_id")
        assert record.user_id == 42

    @pytest.mark.asyncio
    async def test_logger_with_context_nested(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify nested logger_with_context contexts work correctly.

        Given: Nested logger_with_context calls
        When: Log messages are emitted at each level
        Then: Fields accumulate in inner contexts and restore properly
        """
        logger = get_logger("test.nested")

        with caplog.at_level(logging.INFO):
            async with logger_with_context(level="outer"):
                logger.info("Outer context")

                async with logger_with_context(sublevel="inner"):
                    logger.info("Inner context")

                logger.info("Back to outer")

        assert len(caplog.records) == 3

        outer1 = caplog.records[0]
        assert hasattr(outer1, "level")
        assert outer1.level == "outer"

        inner = caplog.records[1]
        assert hasattr(inner, "level")
        assert inner.level == "outer"
        assert hasattr(inner, "sublevel")
        assert inner.sublevel == "inner"

        outer2 = caplog.records[2]
        assert hasattr(outer2, "level")
        assert outer2.level == "outer"

    @pytest.mark.asyncio
    async def test_logger_with_context_empty(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify logger_with_context works with no fields.

        Given: logger_with_context called with no arguments
        When: Used as a context manager
        Then: No errors occur, behaves as no-op
        """
        logger = get_logger("test.empty_context")

        with caplog.at_level(logging.INFO):
            async with logger_with_context():
                logger.info("Log with empty context")

        assert len(caplog.records) == 1
        # Should just log normally without extra fields


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling across all async context utilities.

    Ensures all context managers and functions properly handle errors,
    exceptions, and edge cases without leaking context or resources.
    """

    @pytest.mark.asyncio
    async def test_propagate_log_context_handles_asyncio_cancel(self) -> None:
        """Verify propagate_log_context handles task cancellation.

        Given: A task using propagate_log_context
        When: The task is cancelled
        Then: Context is still properly restored
        """
        set_request_id("original-id")

        async def cancellable_task() -> None:
            async with propagate_log_context(request_id="task-id"):
                await asyncio.sleep(10)  # cancelled immediately below

        task = asyncio.create_task(cancellable_task())
        await asyncio.sleep(0.01)  # Let it start
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Original context should be preserved
        assert get_request_id() == "original-id"

        # Cleanup
        set_request_id(None)

    @pytest.mark.asyncio
    async def test_create_task_with_context_handles_exception_in_task(self) -> None:
        """Verify create_task_with_context doesn't suppress task exceptions.

        Given: A task created with create_task_with_context
        When: The task raises an exception
        Then: The exception is propagated to the awaiter
        """

        async def failing_task() -> None:
            raise ValueError("Task failed")

        task = create_task_with_context(failing_task())

        with pytest.raises(ValueError, match="Task failed"):
            await task

    @pytest.mark.asyncio
    async def test_logger_with_context_handles_keyboard_interrupt(self) -> None:
        """Verify logger_with_context handles KeyboardInterrupt.

        Given: logger_with_context is active
        When: KeyboardInterrupt is raised
        Then: Exception propagates and context is cleaned up
        """

        initial_context = get_log_context()

        with pytest.raises(KeyboardInterrupt):
            async with logger_with_context(camera_id="interrupt_test"):
                raise KeyboardInterrupt

        final_context = get_log_context()
        assert final_context == initial_context

    @pytest.mark.asyncio
    async def test_context_isolation_with_exception(self) -> None:
        """Verify context isolation is maintained when one task fails.

        Given: Multiple concurrent tasks, one raises an exception
        When: Tasks are executed with gather(return_exceptions=True)
        Then: Other tasks' contexts remain isolated and correct
        """
        results: dict[str, str | None] = {}

        async def task_that_succeeds(task_id: str, request_id: str) -> None:
            set_request_id(request_id)
            await asyncio.sleep(0.01)
            results[task_id] = get_request_id()

        async def task_that_fails() -> None:
            set_request_id("failing-task")
            raise ValueError("Task failed")

        outcomes = await asyncio.gather(
            task_that_succeeds("task1", "req-1"),
            task_that_fails(),
            task_that_succeeds("task2", "req-2"),
            return_exceptions=True,
        )

        # First task succeeds
        assert results["task1"] == "req-1"
        # Second task raises exception
        assert isinstance(outcomes[1], ValueError)
        # Third task still succeeds with correct context
        assert results["task2"] == "req-2"


# =============================================================================
# Integration Tests
# =============================================================================


class TestAsyncContextIntegration:
    """Integration tests combining multiple async context utilities.

    Tests realistic scenarios where multiple context management features
    are used together, ensuring they compose correctly.
    """

    @pytest.mark.asyncio
    async def test_full_context_propagation_chain(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify full context propagation through multiple layers.

        Given: A chain of async operations with various context utilities
        When: Context flows from parent through tasks
        Then: All context (request_id, connection_id, log fields) propagates
        """
        from backend.core.logging import log_context

        logger = get_logger("test.full_chain")
        results: list[str] = []

        async def level_3() -> None:
            """Innermost level - should have all context."""
            request_id = get_request_id()
            conn_id = get_connection_id()
            results.append(f"L3: req={request_id}, conn={conn_id}")

            with caplog.at_level(logging.INFO):
                logger.info("Level 3 log")

        async def level_2() -> None:
            """Middle level - creates a task for level 3."""
            request_id = get_request_id()
            conn_id = get_connection_id()
            results.append(f"L2: req={request_id}, conn={conn_id}")

            task = create_task_with_context(level_3())
            await task

        async def level_1() -> None:
            """Top level - uses propagate_log_context."""
            async with propagate_log_context(request_id="chain-req"):
                set_connection_id("chain-conn")
                request_id = get_request_id()
                conn_id = get_connection_id()
                results.append(f"L1: req={request_id}, conn={conn_id}")

                await level_2()

        with log_context(operation="full_chain_test"):
            await level_1()

        # Verify all levels saw correct context
        assert results[0] == "L1: req=chain-req, conn=chain-conn"
        assert results[1] == "L2: req=chain-req, conn=chain-conn"
        assert results[2] == "L3: req=chain-req, conn=chain-conn"

        # Verify log context was propagated
        log_records = [r for r in caplog.records if r.name == "test.full_chain"]
        assert len(log_records) == 1
        assert hasattr(log_records[0], "operation")
        assert log_records[0].operation == "full_chain_test"

        # Cleanup
        set_request_id(None)
        set_connection_id(None)

    @pytest.mark.asyncio
    async def test_context_in_task_group(self) -> None:
        """Verify context works with asyncio task groups (Python 3.11+).

        Given: Multiple tasks in an asyncio.TaskGroup
        When: Each task has different context
        Then: Contexts remain isolated within the group
        """
        results: dict[str, str | None] = {}

        async def task_with_context(task_id: str, request_id: str) -> None:
            set_request_id(request_id)
            await asyncio.sleep(0.01)
            results[task_id] = get_request_id()

        # Python 3.11+ has TaskGroup
        if hasattr(asyncio, "TaskGroup"):
            async with asyncio.TaskGroup() as tg:  # type: ignore
                tg.create_task(task_with_context("task1", "req-1"))
                tg.create_task(task_with_context("task2", "req-2"))
                tg.create_task(task_with_context("task3", "req-3"))

            assert results["task1"] == "req-1"
            assert results["task2"] == "req-2"
            assert results["task3"] == "req-3"
        else:
            # Fallback for Python < 3.11
            await asyncio.gather(
                task_with_context("task1", "req-1"),
                task_with_context("task2", "req-2"),
                task_with_context("task3", "req-3"),
            )

            assert results["task1"] == "req-1"
            assert results["task2"] == "req-2"
            assert results["task3"] == "req-3"

    @pytest.mark.asyncio
    async def test_context_with_concurrent_background_tasks(self) -> None:
        """Verify context in realistic concurrent background task scenario.

        Given: Multiple concurrent background tasks with context
        When: Tasks complete at different times
        Then: Each maintains correct isolated context throughout
        """
        results: dict[str, list[str | None]] = {}

        async def background_work(task_id: str, request_id: str, duration: float) -> None:
            results[task_id] = []
            results[task_id].append(get_request_id())

            await asyncio.sleep(duration)

            results[task_id].append(get_request_id())

        # Create background tasks with different durations and contexts
        tasks = [
            create_task_with_context(background_work("task1", "req-1", 0.03), request_id="req-1"),
            create_task_with_context(background_work("task2", "req-2", 0.01), request_id="req-2"),
            create_task_with_context(background_work("task3", "req-3", 0.02), request_id="req-3"),
        ]

        await asyncio.gather(*tasks)

        # Each task should have consistent context throughout its lifetime
        assert results["task1"] == ["req-1", "req-1"]
        assert results["task2"] == ["req-2", "req-2"]
        assert results["task3"] == ["req-3", "req-3"]
