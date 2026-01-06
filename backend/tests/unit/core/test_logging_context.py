"""Tests for structured error context logging (NEM-1468).

This module tests the enhanced exception logging with structured context
including request_id, operation context, and error metadata.
"""

import logging

import pytest

from backend.core.logging import (
    get_logger,
    get_request_id,
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
                    service="rtdetr",
                )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "Failed to connect to AI service" in record.message
        assert record.error_type == "ConnectionError"
        assert record.camera_id == "front_door"
        assert record.service == "rtdetr"

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
