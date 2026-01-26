"""Tests for structured error context logging (NEM-1468, NEM-1645, NEM-1487).

This module tests the enhanced exception logging with structured context
including request_id, operation context, error metadata, the log_context
context manager for enriched logging, and the log_error helper function.
"""

import asyncio
import logging

import pytest

from backend.core.logging import (
    get_log_context,
    get_logger,
    get_request_id,
    log_context,
    log_error,
    set_request_id,
)


class TestStructuredErrorContext:
    """Tests for structured error context in exception logging."""

    def test_log_exception_with_context_includes_request_id(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify exception logs include request_id from context."""
        # Set a request ID in context
        set_request_id("test-req-123")

        logger = get_logger("test.context")

        with caplog.at_level(logging.ERROR):
            try:
                raise ValueError("Test error")
            except ValueError as e:
                logger.error(
                    "Operation failed",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )

        # Verify request_id is in the log record
        assert len(caplog.records) == 1
        record = caplog.records[0]
        # Request ID is added by ContextFilter
        assert hasattr(record, "request_id")
        assert record.request_id == "test-req-123"
        assert "Operation failed" in record.message

        # Clean up
        set_request_id(None)

    def test_log_exception_with_extra_context_fields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify extra context fields are preserved in log records."""
        logger = get_logger("test.context")

        with caplog.at_level(logging.ERROR):
            logger.error(
                "Detection failed",
                extra={
                    "camera_id": "front_door",
                    "operation": "object_detection",
                    "error_type": "TimeoutError",
                    "retry_count": 3,
                },
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.camera_id == "front_door"
        assert record.operation == "object_detection"
        assert record.error_type == "TimeoutError"
        assert record.retry_count == 3

    def test_log_exception_without_context_still_works(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify logging works when no context is set."""
        # Ensure no request ID is set
        set_request_id(None)

        logger = get_logger("test.no_context")

        with caplog.at_level(logging.ERROR):
            logger.error("Error without context")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.request_id is None

    def test_log_with_nested_extra_dict(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify nested dictionaries in extra are preserved."""
        logger = get_logger("test.nested")

        with caplog.at_level(logging.INFO):
            logger.info(
                "Detection completed",
                extra={
                    "camera_id": "backyard",
                    "detection_metadata": {
                        "object_count": 3,
                        "confidence_avg": 0.85,
                    },
                },
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.camera_id == "backyard"
        assert record.detection_metadata == {
            "object_count": 3,
            "confidence_avg": 0.85,
        }


class TestLogExceptionWithContext:
    """Tests for the log_exception_with_context helper function."""

    def test_log_exception_with_context_captures_error_type(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify error type is captured correctly."""
        from backend.core.logging import log_exception_with_context

        logger = get_logger("test.helper")

        with caplog.at_level(logging.ERROR):
            try:
                raise ConnectionError("Connection refused")
            except ConnectionError as e:
                log_exception_with_context(
                    logger,
                    e,
                    "Failed to connect to AI service",
                    camera_id="front_door",
                    service="yolo26",
                )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "Failed to connect to AI service" in record.message
        assert record.error_type == "ConnectionError"
        assert record.camera_id == "front_door"
        assert record.service == "yolo26"

    def test_log_exception_with_context_captures_stack_trace(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify stack trace is included when exc_info=True."""
        from backend.core.logging import log_exception_with_context

        logger = get_logger("test.stack")

        with caplog.at_level(logging.ERROR):
            try:
                raise RuntimeError("Test runtime error")
            except RuntimeError as e:
                log_exception_with_context(
                    logger,
                    e,
                    "Runtime error occurred",
                    include_traceback=True,
                )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.exc_info is not None

    def test_log_exception_with_context_sanitizes_sensitive_data(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify sensitive data is sanitized in error messages."""
        from backend.core.logging import log_exception_with_context

        logger = get_logger("test.sanitize")

        with caplog.at_level(logging.ERROR):
            # Error message contains a sensitive path
            try:
                raise FileNotFoundError("/home/user/secrets/password.txt not found")
            except FileNotFoundError as e:
                log_exception_with_context(
                    logger,
                    e,
                    "File operation failed",
                )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        # The error message should be sanitized
        assert record.error_message_sanitized is not None
        # Full path should not appear
        assert "/home/user/secrets" not in record.error_message_sanitized

    def test_log_exception_preserves_request_id_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify request_id from context is included."""
        from backend.core.logging import log_exception_with_context

        set_request_id("req-456")
        logger = get_logger("test.request_id")

        with caplog.at_level(logging.ERROR):
            try:
                raise ValueError("Invalid value")
            except ValueError as e:
                log_exception_with_context(
                    logger,
                    e,
                    "Validation failed",
                )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.request_id == "req-456"

        # Clean up
        set_request_id(None)


class TestRequestIdContext:
    """Tests for request ID context management."""

    def test_set_and_get_request_id(self) -> None:
        """Verify request ID can be set and retrieved."""
        set_request_id("test-id-123")
        assert get_request_id() == "test-id-123"

        set_request_id(None)
        assert get_request_id() is None

    def test_request_id_isolation_between_contexts(self) -> None:
        """Verify request IDs don't leak between different contexts."""
        import asyncio

        async def task_with_request_id(request_id: str) -> str | None:
            set_request_id(request_id)
            await asyncio.sleep(0.01)  # Simulate async work
            return get_request_id()

        async def run_concurrent_tasks() -> tuple[str | None, str | None]:
            # Run two concurrent tasks with different request IDs
            results = await asyncio.gather(
                task_with_request_id("task-1"),
                task_with_request_id("task-2"),
            )
            return results[0], results[1]

        # Note: With contextvars, each task has its own context
        # so they won't interfere with each other
        result1, result2 = asyncio.run(run_concurrent_tasks())
        assert result1 == "task-1"
        assert result2 == "task-2"

        # Clean up
        set_request_id(None)


class TestLogContext:
    """Tests for log_context context manager (NEM-1645).

    The log_context context manager enriches all logs within its scope
    with additional context fields, making them available via contextvars.
    """

    def test_log_context_adds_fields_to_log_record(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_context adds context fields to log records."""
        logger = get_logger("test.log_context")

        with caplog.at_level(logging.INFO):
            with log_context(camera_id="front_door", operation="detect"):
                logger.info("Processing detection")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.camera_id == "front_door"
        assert record.operation == "detect"

    def test_log_context_clears_after_exit(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_context clears fields after exiting the context."""
        logger = get_logger("test.log_context_clear")

        with log_context(camera_id="front_door"):
            pass  # Context is set here

        # Now context should be cleared
        context = get_log_context()
        assert context == {}

        # Log outside context should not have camera_id
        with caplog.at_level(logging.INFO):
            logger.info("Outside context")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert not hasattr(record, "camera_id") or record.camera_id is None

    def test_log_context_nesting(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify nested log_context works correctly."""
        logger = get_logger("test.log_context_nested")

        with caplog.at_level(logging.INFO), log_context(camera_id="front_door"):
            with log_context(operation="detect", retry_count=1):
                logger.info("Inner context")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        # Should have fields from both contexts
        assert record.camera_id == "front_door"
        assert record.operation == "detect"
        assert record.retry_count == 1

    def test_log_context_nested_override(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify inner log_context can override outer fields."""
        logger = get_logger("test.log_context_override")

        with caplog.at_level(logging.INFO):
            with log_context(camera_id="front_door", retry_count=0):
                with log_context(retry_count=2):
                    logger.info("Overridden context")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.camera_id == "front_door"  # From outer context
        assert record.retry_count == 2  # Overridden by inner context

    def test_log_context_restores_after_nested_exit(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify outer context is restored after inner context exits."""
        logger = get_logger("test.log_context_restore")

        with caplog.at_level(logging.INFO):
            with log_context(camera_id="front_door", retry_count=0):
                with log_context(retry_count=2):
                    pass  # Inner context exits here

                # Should be back to outer context
                logger.info("After inner context")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.camera_id == "front_door"
        assert record.retry_count == 0  # Back to outer value

    def test_log_context_with_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_context works correctly when exception is raised."""
        logger = get_logger("test.log_context_exception")

        with caplog.at_level(logging.ERROR):
            try:
                with log_context(camera_id="front_door", operation="detect"):
                    logger.error("Error occurred")
                    raise ValueError("Test error")
            except ValueError:
                pass  # Expected

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.camera_id == "front_door"
        assert record.operation == "detect"

        # Context should be cleared after exception
        context = get_log_context()
        assert context == {}

    def test_log_context_with_various_types(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_context handles various value types."""
        logger = get_logger("test.log_context_types")

        with (
            caplog.at_level(logging.INFO),
            log_context(
                camera_id="front_door",
                retry_count=3,
                confidence=0.95,
                enabled=True,
                labels=["person", "car"],
            ),
        ):
            logger.info("Various types")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.camera_id == "front_door"
        assert record.retry_count == 3
        assert record.confidence == 0.95
        assert record.enabled is True
        assert record.labels == ["person", "car"]

    def test_get_log_context_returns_current_context(self) -> None:
        """Verify get_log_context returns the current context dict."""
        with log_context(camera_id="front_door", operation="detect"):
            context = get_log_context()
            assert context == {"camera_id": "front_door", "operation": "detect"}

        # After exiting context
        context = get_log_context()
        assert context == {}

    def test_log_context_isolation_between_async_tasks(self) -> None:
        """Verify log_context is isolated between concurrent async tasks."""

        async def task_with_context(task_id: str) -> dict:
            with log_context(task_id=task_id):
                await asyncio.sleep(0.01)  # Simulate async work
                return get_log_context()

        async def run_concurrent_tasks():
            # Run two concurrent tasks with different contexts
            results = await asyncio.gather(
                task_with_context("task-1"),
                task_with_context("task-2"),
            )
            return results

        result1, result2 = asyncio.run(run_concurrent_tasks())
        # Each task should have its own context
        assert result1 == {"task_id": "task-1"}
        assert result2 == {"task_id": "task-2"}

    def test_log_context_empty_context_is_valid(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify empty log_context works (no-op)."""
        logger = get_logger("test.log_context_empty")

        with caplog.at_level(logging.INFO), log_context():
            logger.info("Empty context")

        assert len(caplog.records) == 1
        # Should not fail, just no extra fields added
        context = get_log_context()
        assert context == {}

    def test_log_context_combines_with_extra_param(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_context combines with explicit extra= parameter."""
        logger = get_logger("test.log_context_combine")

        with caplog.at_level(logging.INFO), log_context(camera_id="front_door"):
            logger.info("Combined context", extra={"detection_id": 123, "score": 0.95})

        assert len(caplog.records) == 1
        record = caplog.records[0]
        # Should have fields from both log_context and extra
        assert record.camera_id == "front_door"
        assert record.detection_id == 123
        assert record.score == 0.95

    def test_log_context_extra_param_overrides_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify explicit extra= parameter overrides log_context values."""
        logger = get_logger("test.log_context_extra_override")

        with caplog.at_level(logging.INFO):
            with log_context(camera_id="front_door", retry_count=1):
                logger.info("Extra overrides context", extra={"retry_count": 5})

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.camera_id == "front_door"  # From log_context
        assert record.retry_count == 5  # Overridden by extra


class TestLogError:
    """Tests for log_error helper function (NEM-1487).

    The log_error function provides a simplified interface for logging errors
    with consistent structure, automatic request ID inclusion, and optional
    exception handling.
    """

    def test_log_error_basic_message(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_error logs basic error message."""
        logger = get_logger("test.log_error")

        with caplog.at_level(logging.ERROR):
            log_error(logger, "Database connection failed")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.message == "Database connection failed"
        assert record.levelname == "ERROR"

    def test_log_error_includes_request_id_from_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify log_error includes request_id from context automatically."""
        set_request_id("req-test-123")

        try:
            logger = get_logger("test.log_error_ctx")

            with caplog.at_level(logging.ERROR):
                log_error(logger, "Operation failed")

            assert len(caplog.records) == 1
            record = caplog.records[0]
            assert record.request_id == "req-test-123"
        finally:
            set_request_id(None)

    def test_log_error_explicit_request_id_overrides_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify explicit request_id parameter overrides context value."""
        set_request_id("ctx-request-id")

        try:
            logger = get_logger("test.log_error_override")

            with caplog.at_level(logging.ERROR):
                log_error(
                    logger,
                    "Validation error",
                    request_id="explicit-request-id",
                )

            assert len(caplog.records) == 1
            record = caplog.records[0]
            # Explicit request_id should override context
            assert record.request_id == "explicit-request-id"
        finally:
            set_request_id(None)

    def test_log_error_with_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_error handles exception parameter correctly."""
        logger = get_logger("test.log_error_exc")

        with caplog.at_level(logging.ERROR):
            try:
                raise ValueError("Invalid input data")
            except ValueError as e:
                log_error(logger, "Input validation failed", error=e)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.message == "Input validation failed"
        assert record.error_type == "ValueError"
        assert record.error_message_sanitized is not None
        assert "Invalid input data" in record.error_message_sanitized

    def test_log_error_without_exception_has_none_error_type(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify log_error without exception has None error_type."""
        logger = get_logger("test.log_error_no_exc")

        with caplog.at_level(logging.ERROR):
            log_error(logger, "Generic error occurred")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.error_type is None

    def test_log_error_with_extra_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_error includes extra fields in log record."""
        logger = get_logger("test.log_error_extra")

        with caplog.at_level(logging.ERROR):
            log_error(
                logger,
                "Camera processing failed",
                extra={
                    "camera_id": "front_door",
                    "timeout_ms": 5000,
                    "retry_count": 3,
                },
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.camera_id == "front_door"
        assert record.timeout_ms == 5000
        assert record.retry_count == 3

    def test_log_error_with_exc_info_includes_traceback(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify log_error includes traceback when exc_info=True."""
        logger = get_logger("test.log_error_traceback")

        with caplog.at_level(logging.ERROR):
            try:
                raise RuntimeError("Test error with traceback")
            except RuntimeError as e:
                log_error(logger, "Error with traceback", error=e, exc_info=True)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.exc_info is not None

    def test_log_error_without_exc_info_no_traceback(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify log_error without exc_info has no traceback."""
        logger = get_logger("test.log_error_no_traceback")

        with caplog.at_level(logging.ERROR):
            try:
                raise RuntimeError("Test error without traceback")
            except RuntimeError as e:
                log_error(logger, "Error without traceback", error=e, exc_info=False)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        # When exc_info=False is passed, the record's exc_info is falsy (False or None)
        assert not record.exc_info

    def test_log_error_sanitizes_exception_message(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_error sanitizes sensitive data in exception messages."""
        logger = get_logger("test.log_error_sanitize")

        with caplog.at_level(logging.ERROR):
            try:
                raise FileNotFoundError("/home/user/secrets/credentials.txt not found")
            except FileNotFoundError as e:
                log_error(logger, "File operation failed", error=e)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        # Full path should be sanitized
        assert "/home/user/secrets" not in record.error_message_sanitized
        # But we should still know it's about a file
        assert "credentials.txt" in record.error_message_sanitized

    def test_log_error_works_without_context_set(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify log_error works when no request context is set."""
        # Ensure no context is set
        set_request_id(None)

        logger = get_logger("test.log_error_no_ctx")

        with caplog.at_level(logging.ERROR):
            log_error(logger, "Error without context")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.request_id is None

    def test_log_error_extra_merges_with_base_fields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify extra dict merges with base fields (request_id, error_type)."""
        set_request_id("merge-test-id")

        try:
            logger = get_logger("test.log_error_merge")

            with caplog.at_level(logging.ERROR):
                try:
                    raise ConnectionError("Connection refused")
                except ConnectionError as e:
                    log_error(
                        logger,
                        "Service unavailable",
                        error=e,
                        extra={"service": "yolo26", "host": "localhost:8080"},
                    )

            assert len(caplog.records) == 1
            record = caplog.records[0]
            # Base fields
            assert record.request_id == "merge-test-id"
            assert record.error_type == "ConnectionError"
            # Extra fields
            assert record.service == "yolo26"
            assert record.host == "localhost:8080"
        finally:
            set_request_id(None)

    def test_log_error_with_log_context_includes_context_fields(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify log_error works with log_context context manager."""
        logger = get_logger("test.log_error_with_context")

        with (
            caplog.at_level(logging.ERROR),
            log_context(camera_id="backyard", operation="motion_detect"),
        ):
            log_error(logger, "Motion detection failed")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        # Fields from log_context should be present
        assert record.camera_id == "backyard"
        assert record.operation == "motion_detect"

    def test_log_error_extra_overrides_log_context(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify extra parameter in log_error overrides log_context fields."""
        logger = get_logger("test.log_error_override_ctx")

        with caplog.at_level(logging.ERROR), log_context(camera_id="front_door", retry_count=0):
            log_error(
                logger,
                "Retry limit exceeded",
                extra={"retry_count": 5},  # Override log_context value
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.camera_id == "front_door"  # From log_context
        assert record.retry_count == 5  # Overridden by extra
