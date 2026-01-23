"""Unit tests for structured error context module.

Tests cover:
- ErrorContext building and serialization
- log_error helper function
- Exception chain capture
- Request context extraction
- Service context for external services
- Metrics integration
"""

from unittest.mock import patch

from backend.core.exceptions import (
    DatabaseError,
    DetectorUnavailableError,
    ExternalServiceError,
)

# =============================================================================
# ErrorContext Tests
# =============================================================================


class TestErrorContext:
    """Tests for ErrorContext class."""

    def test_create_error_context(self) -> None:
        """Test creating an ErrorContext."""
        from backend.core.error_context import ErrorContext

        ctx = ErrorContext(
            error_type="DatabaseError",
            error_code="DATABASE_ERROR",
            message="Connection failed",
        )

        assert ctx.error_type == "DatabaseError"
        assert ctx.error_code == "DATABASE_ERROR"
        assert ctx.message == "Connection failed"

    def test_error_context_from_exception(self) -> None:
        """Test creating ErrorContext from an exception."""
        from backend.core.error_context import ErrorContext

        exc = DatabaseError("Connection pool exhausted")
        ctx = ErrorContext.from_exception(exc)

        assert ctx.error_type == "DatabaseError"
        assert ctx.error_code == "DATABASE_ERROR"
        assert ctx.message == "Connection pool exhausted"
        assert ctx.status_code == 503

    def test_error_context_with_service_info(self) -> None:
        """Test ErrorContext with service information."""
        from backend.core.error_context import ErrorContext

        exc = DetectorUnavailableError("RT-DETR timeout")
        ctx = ErrorContext.from_exception(exc)

        assert ctx.service_name == "rtdetr"
        assert ctx.error_type == "DetectorUnavailableError"

    def test_error_context_to_dict(self) -> None:
        """Test serializing ErrorContext to dictionary."""
        from backend.core.error_context import ErrorContext

        ctx = ErrorContext(
            error_type="ExternalServiceError",
            error_code="SERVICE_UNAVAILABLE",
            message="Service down",
            service_name="external_api",
            operation="fetch_data",
        )

        result = ctx.to_dict()

        assert result["error_type"] == "ExternalServiceError"
        assert result["error_code"] == "SERVICE_UNAVAILABLE"
        assert result["message"] == "Service down"
        assert result["service_name"] == "external_api"
        assert result["operation"] == "fetch_data"
        assert "timestamp" in result

    def test_error_context_with_exception_chain(self) -> None:
        """Test ErrorContext captures exception chain."""
        from backend.core.error_context import ErrorContext

        try:
            try:
                raise ConnectionError("TCP connection failed")
            except ConnectionError as e:
                raise DatabaseError("Database unreachable") from e
        except DatabaseError as exc:
            ctx = ErrorContext.from_exception(exc, include_chain=True)

        assert ctx.error_type == "DatabaseError"
        assert ctx.cause_type == "ConnectionError"
        assert ctx.cause_message == "TCP connection failed"

    def test_error_context_with_request_info(self) -> None:
        """Test ErrorContext with request information."""
        from backend.core.error_context import ErrorContext

        ctx = ErrorContext(
            error_type="ValidationError",
            error_code="VALIDATION_ERROR",
            message="Invalid input",
            request_id="req-123-abc",
            path="/api/cameras",
            method="POST",
        )

        result = ctx.to_dict()

        assert result["request_id"] == "req-123-abc"
        assert result["path"] == "/api/cameras"
        assert result["method"] == "POST"

    def test_error_context_with_extra_details(self) -> None:
        """Test ErrorContext with extra details."""
        from backend.core.error_context import ErrorContext

        ctx = ErrorContext(
            error_type="ProcessingError",
            error_code="PROCESSING_ERROR",
            message="Image processing failed",
            extra={"file_path": "/images/test.jpg", "step": "resize"},
        )

        result = ctx.to_dict()

        assert result["extra"]["file_path"] == "/images/test.jpg"
        assert result["extra"]["step"] == "resize"


# =============================================================================
# log_error Helper Tests
# =============================================================================


class TestLogError:
    """Tests for log_error helper function."""

    def test_log_error_basic(self) -> None:
        """Test basic error logging."""
        from backend.core.error_context import log_error

        exc = DatabaseError("Connection failed")

        with patch("backend.core.error_context.logger") as mock_logger:
            log_error(exc)

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "Connection failed" in call_args[0][0]
            assert "extra" in call_args[1]

    def test_log_error_with_context(self) -> None:
        """Test error logging with additional context."""
        from backend.core.error_context import log_error

        exc = ExternalServiceError("API timeout", service_name="payment_gateway")

        with patch("backend.core.error_context.logger") as mock_logger:
            log_error(exc, operation="process_payment", request_id="req-456")

            call_args = mock_logger.error.call_args
            extra = call_args[1]["extra"]
            assert extra["operation"] == "process_payment"
            assert extra["request_id"] == "req-456"
            assert extra["service_name"] == "payment_gateway"

    def test_log_error_warning_for_client_errors(self) -> None:
        """Test that client errors (4xx) are logged as warnings."""
        from backend.core.error_context import log_error
        from backend.core.exceptions import ValidationError

        exc = ValidationError("Invalid email format")

        with patch("backend.core.error_context.logger") as mock_logger:
            log_error(exc)

            # 400 errors should use warning level
            mock_logger.warning.assert_called_once()
            mock_logger.error.assert_not_called()

    def test_log_error_includes_traceback(self) -> None:
        """Test that error logging includes traceback for 5xx errors."""
        from backend.core.error_context import log_error

        exc = DatabaseError("Query failed")

        with patch("backend.core.error_context.logger") as mock_logger:
            log_error(exc, include_traceback=True)

            call_args = mock_logger.error.call_args
            assert call_args[1].get("exc_info") is True


# =============================================================================
# log_with_context Helper Tests
# =============================================================================


class TestLogWithContext:
    """Tests for log_with_context helper function."""

    def test_log_with_context_adds_structured_fields(self) -> None:
        """Test that log_with_context adds structured fields."""
        from backend.core.error_context import log_with_context

        with patch("backend.core.error_context.logger") as mock_logger:
            log_with_context(
                "info",
                "Processing started",
                camera_id="front_door",
                event_id=123,
            )

            call_args = mock_logger.info.call_args
            extra = call_args[1]["extra"]
            assert extra["camera_id"] == "front_door"
            assert extra["event_id"] == 123

    def test_log_with_context_sanitizes_values(self) -> None:
        """Test that sensitive values are sanitized."""
        from backend.core.error_context import log_with_context

        with patch("backend.core.error_context.logger") as mock_logger:
            log_with_context(
                "debug",
                "Request received",
                api_key="secret-key-12345",  # pragma: allowlist secret
                password="user_password",  # pragma: allowlist secret
            )

            call_args = mock_logger.debug.call_args
            extra = call_args[1]["extra"]
            # Sensitive fields should be redacted
            assert extra["api_key"] == "[REDACTED]"
            assert extra["password"] == "[REDACTED]"


# =============================================================================
# ErrorContextBuilder Tests
# =============================================================================


class TestErrorContextBuilder:
    """Tests for ErrorContextBuilder fluent API."""

    def test_builder_fluent_api(self) -> None:
        """Test fluent builder API."""
        from backend.core.error_context import ErrorContextBuilder

        ctx = (
            ErrorContextBuilder()
            .with_error("DatabaseError", "DATABASE_ERROR", "Connection failed")
            .with_status(503)
            .with_service("postgresql")
            .with_operation("execute_query")
            .with_request("req-123", "/api/data", "GET")
            .build()
        )

        assert ctx.error_type == "DatabaseError"
        assert ctx.status_code == 503
        assert ctx.service_name == "postgresql"
        assert ctx.operation == "execute_query"
        assert ctx.request_id == "req-123"

    def test_builder_from_exception(self) -> None:
        """Test building context from exception."""
        from backend.core.error_context import ErrorContextBuilder

        exc = DetectorUnavailableError("Detection timeout")

        ctx = (
            ErrorContextBuilder()
            .from_exception(exc)
            .with_operation("detect_objects")
            .with_extra(image_path="/images/test.jpg")
            .build()
        )

        assert ctx.error_type == "DetectorUnavailableError"
        assert ctx.operation == "detect_objects"
        assert ctx.extra["image_path"] == "/images/test.jpg"


# =============================================================================
# Integration Tests
# =============================================================================


class TestErrorContextIntegration:
    """Integration tests for error context with exception handlers."""

    def test_context_integrates_with_exception_handler(self) -> None:
        """Test that ErrorContext integrates with exception handlers."""
        from backend.core.error_context import ErrorContext

        exc = ExternalServiceError("Service unavailable", service_name="ai_service")
        ctx = ErrorContext.from_exception(exc)

        # Context should have all fields needed by exception handler
        result = ctx.to_dict()
        assert "error_type" in result
        assert "error_code" in result
        assert "message" in result
        assert "timestamp" in result

    def test_error_context_with_standard_exception(self) -> None:
        """Test ErrorContext with standard Python exceptions."""
        from backend.core.error_context import ErrorContext

        exc = ValueError("Invalid value")
        ctx = ErrorContext.from_exception(exc)

        assert ctx.error_type == "ValueError"
        assert ctx.error_code == "INTERNAL_ERROR"
        assert ctx.message == "Invalid value"
        assert ctx.status_code == 500
