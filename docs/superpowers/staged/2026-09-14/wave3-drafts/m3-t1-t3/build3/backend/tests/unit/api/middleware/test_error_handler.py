"""Unit tests for error handler middleware.

Tests cover:
- ErrorResponse schema validation and serialization
- AppException base class and exception hierarchy
- Exception initialization with custom parameters
- Exception to_response conversion
- Default message generation
- Validation, authentication, and authorization errors
- Service unavailable and rate limit errors
- Re-exported exception classes
- Re-exported utility functions

This module achieves comprehensive coverage of backend/api/middleware/error_handler.py
by testing all exception classes, schema validation, and utility function re-exports.

Target: 85%+ coverage
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from backend.api.middleware.error_handler import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    CameraNotFoundError,
    CircuitBreakerOpenError,
    ConflictError,
    CoreValidationError,
    DatabaseError,
    DetectionNotFoundError,
    DetectorUnavailableError,
    DuplicateResourceError,
    ErrorResponse,
    EventNotFoundError,
    ExternalServiceError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    RateLimitExceededError,
    ResourceNotFoundError,
    SecurityIntelligenceError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
    build_error_response,
    get_request_id,
    register_exception_handlers,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# ErrorResponse Schema Tests
# =============================================================================


class TestErrorResponse:
    """Tests for ErrorResponse Pydantic schema."""

    def test_minimal_error_response(self):
        """Test creating error response with required fields only."""
        response = ErrorResponse(
            error="not_found",
            message="Resource not found",
        )
        assert response.error == "not_found"
        assert response.message == "Resource not found"
        assert response.details is None
        assert response.request_id is None
        assert isinstance(response.timestamp, datetime)

    def test_full_error_response(self):
        """Test creating error response with all fields."""
        timestamp = datetime.now(UTC)
        response = ErrorResponse(
            error="validation_error",
            message="Invalid input",
            details={"field": "email", "reason": "invalid format"},
            request_id="req-123-456",
            timestamp=timestamp,
        )
        assert response.error == "validation_error"
        assert response.message == "Invalid input"
        assert response.details == {"field": "email", "reason": "invalid format"}
        assert response.request_id == "req-123-456"
        assert response.timestamp == timestamp

    def test_timestamp_auto_generated(self):
        """Test that timestamp is automatically generated if not provided."""
        with freeze_time("2024-01-15 10:30:00"):
            response = ErrorResponse(
                error="test_error",
                message="Test message",
            )
            expected_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
            assert response.timestamp == expected_time

    def test_error_response_serialization(self):
        """Test that error response serializes to dict correctly."""
        response = ErrorResponse(
            error="not_found",
            message="Camera not found",
            details={"camera_id": "front_door"},
            request_id="req-abc-xyz",
        )
        data = response.model_dump()
        assert data["error"] == "not_found"
        assert data["message"] == "Camera not found"
        assert data["details"]["camera_id"] == "front_door"
        assert data["request_id"] == "req-abc-xyz"
        assert "timestamp" in data

    def test_error_response_json_serialization(self):
        """Test that error response serializes to JSON correctly."""
        response = ErrorResponse(
            error="validation_error",
            message="Invalid date range",
        )
        json_str = response.model_dump_json()
        assert '"error":"validation_error"' in json_str
        assert '"message":"Invalid date range"' in json_str
        assert '"timestamp"' in json_str

    def test_error_response_with_complex_details(self):
        """Test error response with complex nested details."""
        details: dict[str, Any] = {
            "camera_id": "front_door",
            "resource_type": "camera",
            "search_params": {"name": "front*", "status": "active"},
            "attempted_at": "2024-01-15T10:30:00Z",
        }
        response = ErrorResponse(
            error="not_found",
            message="Resource not found",
            details=details,
        )
        assert response.details == details

    def test_model_config_json_schema_extra(self):
        """Test that model config includes example for documentation."""
        schema = ErrorResponse.model_config
        assert "json_schema_extra" in schema
        example = schema["json_schema_extra"]["example"]
        assert example["error"] == "not_found"
        assert example["message"] == "Camera 'front_door' not found"
        assert "camera_id" in example["details"]
        assert example["request_id"] == "req-abc-123"


# =============================================================================
# AppException Base Class Tests
# =============================================================================


class TestAppException:
    """Tests for AppException base class."""

    def test_default_initialization(self):
        """Test AppException with default values."""
        exc = AppException()
        assert exc.status_code == 500
        assert exc.error == "internal_error"
        assert exc.message == "An error occurred: internal_error"
        assert exc.details is None

    def test_initialization_with_message(self):
        """Test AppException with custom message."""
        exc = AppException("Custom error message")
        assert exc.message == "Custom error message"
        assert exc.status_code == 500
        assert exc.error == "internal_error"

    def test_initialization_with_all_parameters(self):
        """Test AppException with all parameters."""
        exc = AppException(
            "Custom message",
            status_code=400,
            error="custom_error",
            details={"field": "value"},
        )
        assert exc.message == "Custom message"
        assert exc.status_code == 400
        assert exc.error == "custom_error"
        assert exc.details == {"field": "value"}

    def test_default_message_generation(self):
        """Test _get_default_message method."""
        exc = AppException()
        default_msg = exc._get_default_message()
        assert default_msg == "An error occurred: internal_error"

    def test_to_response_without_request_id(self):
        """Test converting exception to ErrorResponse without request ID."""
        exc = AppException(
            "Test error",
            error="test_error",
            details={"key": "value"},
        )
        response = exc.to_response()
        assert response.error == "test_error"
        assert response.message == "Test error"
        assert response.details == {"key": "value"}
        assert response.request_id is None

    def test_to_response_with_request_id(self):
        """Test converting exception to ErrorResponse with request ID."""
        exc = AppException(
            "Test error",
            error="test_error",
        )
        response = exc.to_response(request_id="req-123")
        assert response.error == "test_error"
        assert response.message == "Test error"
        assert response.request_id == "req-123"

    def test_exception_str_representation(self):
        """Test that exception string representation uses message."""
        exc = AppException("Test error message")
        assert str(exc) == "Test error message"

    def test_subclass_overrides_defaults(self):
        """Test that subclasses can override default status_code and error."""

        class CustomException(AppException):
            status_code: int = 418
            error: str = "teapot"

        exc = CustomException()
        assert exc.status_code == 418
        assert exc.error == "teapot"

    def test_initialization_without_details(self):
        """Test that details defaults to None when not provided."""
        exc = AppException("Test")
        assert exc.details is None


# =============================================================================
# ValidationError Tests
# =============================================================================


class TestValidationError:
    """Tests for ValidationError exception class."""

    def test_default_values(self):
        """Test ValidationError default status code and error code."""
        exc = ValidationError()
        assert exc.status_code == 422
        assert exc.error == "validation_error"

    def test_default_message(self):
        """Test ValidationError default message generation."""
        exc = ValidationError()
        assert exc.message == "Request validation failed"

    def test_custom_message(self):
        """Test ValidationError with custom message."""
        exc = ValidationError("Invalid date range")
        assert exc.message == "Invalid date range"
        assert exc.status_code == 422

    def test_with_details(self):
        """Test ValidationError with validation details."""
        exc = ValidationError(
            "Invalid input",
            details={"field": "email", "reason": "invalid format"},
        )
        assert exc.message == "Invalid input"
        assert exc.details == {"field": "email", "reason": "invalid format"}

    def test_to_response(self):
        """Test converting ValidationError to ErrorResponse."""
        exc = ValidationError(
            "Validation failed",
            details={"errors": [{"field": "name", "message": "required"}]},
        )
        response = exc.to_response(request_id="req-abc")
        assert response.error == "validation_error"
        assert response.message == "Validation failed"
        assert response.request_id == "req-abc"


# =============================================================================
# UnauthorizedError Tests
# =============================================================================


class TestUnauthorizedError:
    """Tests for UnauthorizedError exception class."""

    def test_default_values(self):
        """Test UnauthorizedError default status code and error code."""
        exc = UnauthorizedError()
        assert exc.status_code == 401
        assert exc.error == "unauthorized"

    def test_default_message(self):
        """Test UnauthorizedError default message generation."""
        exc = UnauthorizedError()
        assert exc.message == "Authentication required"

    def test_custom_message(self):
        """Test UnauthorizedError with custom message."""
        exc = UnauthorizedError("Invalid API key")
        assert exc.message == "Invalid API key"
        assert exc.status_code == 401

    def test_to_response(self):
        """Test converting UnauthorizedError to ErrorResponse."""
        exc = UnauthorizedError("Missing token")
        response = exc.to_response()
        assert response.error == "unauthorized"
        assert response.message == "Missing token"


# =============================================================================
# ForbiddenError Tests
# =============================================================================


class TestForbiddenError:
    """Tests for ForbiddenError exception class."""

    def test_default_values(self):
        """Test ForbiddenError default status code and error code."""
        exc = ForbiddenError()
        assert exc.status_code == 403
        assert exc.error == "forbidden"

    def test_default_message(self):
        """Test ForbiddenError default message generation."""
        exc = ForbiddenError()
        assert exc.message == "Access denied"

    def test_custom_message(self):
        """Test ForbiddenError with custom message."""
        exc = ForbiddenError("Insufficient permissions")
        assert exc.message == "Insufficient permissions"
        assert exc.status_code == 403

    def test_with_details(self):
        """Test ForbiddenError with access details."""
        exc = ForbiddenError(
            "Access denied to camera configuration",
            details={"camera_id": "front_door", "required_role": "admin"},
        )
        assert exc.message == "Access denied to camera configuration"
        assert exc.details["camera_id"] == "front_door"


# =============================================================================
# ServiceUnavailableError Tests
# =============================================================================


class TestServiceUnavailableError:
    """Tests for ServiceUnavailableError exception class."""

    def test_default_values(self):
        """Test ServiceUnavailableError default status code and error code."""
        exc = ServiceUnavailableError()
        assert exc.status_code == 503
        assert exc.error == "service_unavailable"

    def test_default_message(self):
        """Test ServiceUnavailableError default message generation."""
        exc = ServiceUnavailableError()
        assert exc.message == "Service temporarily unavailable"

    def test_custom_message(self):
        """Test ServiceUnavailableError with custom message."""
        exc = ServiceUnavailableError("AI service unavailable")
        assert exc.message == "AI service unavailable"

    def test_with_retry_details(self):
        """Test ServiceUnavailableError with retry information."""
        exc = ServiceUnavailableError(
            "YOLO26 service unavailable",
            details={"service": "yolo26", "retry_after": 30},
        )
        assert exc.message == "YOLO26 service unavailable"
        assert exc.details == {"service": "yolo26", "retry_after": 30}


# =============================================================================
# RateLimitExceededError Tests
# =============================================================================


class TestRateLimitExceededError:
    """Tests for RateLimitExceededError exception class."""

    def test_default_values(self):
        """Test RateLimitExceededError default status code and error code."""
        exc = RateLimitExceededError()
        assert exc.status_code == 429
        assert exc.error == "rate_limit_exceeded"

    def test_default_message(self):
        """Test RateLimitExceededError default message generation."""
        exc = RateLimitExceededError()
        assert exc.message == "Rate limit exceeded"

    def test_custom_message(self):
        """Test RateLimitExceededError with custom message."""
        exc = RateLimitExceededError("Too many requests")
        assert exc.message == "Too many requests"

    def test_with_rate_limit_details(self):
        """Test RateLimitExceededError with rate limit information."""
        exc = RateLimitExceededError(
            "Rate limit exceeded",
            details={"retry_after": 60, "limit": 100, "window": 60},
        )
        assert exc.details == {"retry_after": 60, "limit": 100, "window": 60}


# =============================================================================
# Re-exported Exception Classes Tests
# =============================================================================


class TestReExportedExceptions:
    """Tests for exception classes re-exported from core.exceptions."""

    def test_not_found_error_available(self):
        """Test that NotFoundError is available."""
        exc = NotFoundError("Resource not found")
        assert isinstance(exc, SecurityIntelligenceError)
        assert str(exc) == "Resource not found"

    def test_conflict_error_available(self):
        """Test that ConflictError is available."""
        exc = ConflictError("Resource conflict")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_authentication_error_available(self):
        """Test that AuthenticationError is available."""
        exc = AuthenticationError("Auth failed")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_authorization_error_available(self):
        """Test that AuthorizationError is available."""
        exc = AuthorizationError("Not authorized")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_camera_not_found_error_available(self):
        """Test that CameraNotFoundError is available."""
        exc = CameraNotFoundError("Camera not found")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_detection_not_found_error_available(self):
        """Test that DetectionNotFoundError is available."""
        exc = DetectionNotFoundError("Detection not found")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_event_not_found_error_available(self):
        """Test that EventNotFoundError is available."""
        exc = EventNotFoundError("Event not found")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_circuit_breaker_open_error_available(self):
        """Test that CircuitBreakerOpenError is available."""
        exc = CircuitBreakerOpenError(service_name="test")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_external_service_error_available(self):
        """Test that ExternalServiceError is available."""
        exc = ExternalServiceError("Service error", service_name="test")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_database_error_available(self):
        """Test that DatabaseError is available."""
        exc = DatabaseError("Database error")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_rate_limit_error_available(self):
        """Test that RateLimitError is available."""
        exc = RateLimitError("Rate limited")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_detector_unavailable_error_available(self):
        """Test that DetectorUnavailableError is available."""
        exc = DetectorUnavailableError("Detector down")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_duplicate_resource_error_available(self):
        """Test that DuplicateResourceError is available."""
        exc = DuplicateResourceError("Duplicate resource")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_resource_not_found_error_available(self):
        """Test that ResourceNotFoundError is available."""
        exc = ResourceNotFoundError(resource_type="camera", resource_id="front_door")
        assert isinstance(exc, SecurityIntelligenceError)

    def test_core_validation_error_available(self):
        """Test that CoreValidationError is available."""
        exc = CoreValidationError("Validation failed")
        assert isinstance(exc, SecurityIntelligenceError)


# =============================================================================
# Re-exported Utility Functions Tests
# =============================================================================


class TestReExportedUtilities:
    """Tests for utility functions re-exported from exception_handlers."""

    def test_get_request_id_from_state(self):
        """Test get_request_id extracts from request state."""
        mock_request = MagicMock()
        mock_request.state.request_id = "req-state-123"
        mock_request.headers.get.return_value = "req-header-456"

        request_id = get_request_id(mock_request)
        assert request_id == "req-state-123"

    def test_get_request_id_from_header(self):
        """Test get_request_id falls back to header."""
        mock_request = MagicMock()
        # Simulate missing state attribute
        del mock_request.state.request_id
        mock_request.headers.get.return_value = "req-header-456"

        request_id = get_request_id(mock_request)
        assert request_id == "req-header-456"

    def test_get_request_id_returns_none_when_missing(self):
        """Test get_request_id returns None when no request ID available."""
        mock_request = MagicMock()
        del mock_request.state.request_id
        mock_request.headers.get.return_value = None

        request_id = get_request_id(mock_request)
        assert request_id is None

    def test_build_error_response_minimal(self):
        """Test build_error_response with minimal parameters."""
        response = build_error_response(
            error_code="TEST_ERROR",
            message="Test message",
            status_code=400,
        )
        assert response.status_code == 400
        data = response.body.decode()
        assert "TEST_ERROR" in data
        assert "Test message" in data

    def test_build_error_response_with_details(self):
        """Test build_error_response with details."""
        response = build_error_response(
            error_code="VALIDATION_ERROR",
            message="Invalid input",
            status_code=422,
            details={"field": "email"},
        )
        data = response.body.decode()
        assert "VALIDATION_ERROR" in data
        assert "email" in data

    def test_build_error_response_with_request(self):
        """Test build_error_response extracts request ID from request."""
        mock_request = MagicMock()
        mock_request.state.request_id = "req-789"

        response = build_error_response(
            error_code="ERROR",
            message="Error message",
            status_code=500,
            request=mock_request,
        )
        data = response.body.decode()
        assert "req-789" in data

    def test_build_error_response_with_custom_headers(self):
        """Test build_error_response includes custom headers."""
        response = build_error_response(
            error_code="RATE_LIMIT",
            message="Rate limited",
            status_code=429,
            headers={"Retry-After": "60"},
        )
        assert response.headers.get("Retry-After") == "60"

    def test_register_exception_handlers_callable(self):
        """Test that register_exception_handlers is callable."""
        assert callable(register_exception_handlers)

    def test_register_exception_handlers_with_mock_app(self):
        """Test register_exception_handlers registers handlers on FastAPI app."""
        mock_app = MagicMock()
        mock_app.add_exception_handler = MagicMock()

        with patch("backend.api.exception_handlers.logger"):
            register_exception_handlers(mock_app)

        # Verify that multiple exception handlers were registered
        assert mock_app.add_exception_handler.call_count > 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestExceptionHierarchyIntegration:
    """Integration tests for exception hierarchy and behavior."""

    def test_appexception_subclass_chain(self):
        """Test that AppException subclasses maintain proper inheritance."""
        validation_exc = ValidationError()
        assert isinstance(validation_exc, AppException)
        assert isinstance(validation_exc, Exception)

    def test_exception_details_preserved_in_response(self):
        """Test that exception details are preserved through to_response."""
        exc = ValidationError(
            "Test error",
            details={"field": "test", "value": "invalid"},
        )
        response = exc.to_response(request_id="req-test")

        assert response.error == "validation_error"
        assert response.message == "Test error"
        assert response.details == {"field": "test", "value": "invalid"}
        assert response.request_id == "req-test"

    def test_multiple_exceptions_unique_error_codes(self):
        """Test that different exception types have unique error codes."""
        exceptions = [
            ValidationError(),
            UnauthorizedError(),
            ForbiddenError(),
            ServiceUnavailableError(),
            RateLimitExceededError(),
        ]
        error_codes = [exc.error for exc in exceptions]
        assert len(error_codes) == len(set(error_codes))  # All unique

    def test_multiple_exceptions_correct_status_codes(self):
        """Test that exception types have correct HTTP status codes."""
        test_cases = [
            (ValidationError(), 422),
            (UnauthorizedError(), 401),
            (ForbiddenError(), 403),
            (ServiceUnavailableError(), 503),
            (RateLimitExceededError(), 429),
        ]
        for exc, expected_status in test_cases:
            assert exc.status_code == expected_status

    def test_exception_with_none_details_to_response(self):
        """Test that exception with None details converts properly."""
        exc = AppException("Test", details=None)
        response = exc.to_response()
        assert response.details is None

    def test_error_response_timestamp_timezone_aware(self):
        """Test that ErrorResponse timestamp is timezone-aware."""
        response = ErrorResponse(
            error="test",
            message="Test message",
        )
        assert response.timestamp.tzinfo is not None
        assert response.timestamp.tzinfo == UTC


# =============================================================================
# Edge Cases and Error Conditions
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_message_uses_default(self):
        """Test that empty message string uses default message."""
        exc = AppException("")
        # Empty string is falsy, so default message should be used
        assert exc.message == "An error occurred: internal_error"

    def test_none_message_uses_default(self):
        """Test that None message uses default message."""
        exc = AppException(None)
        assert exc.message == "An error occurred: internal_error"

    def test_very_long_message(self):
        """Test handling of very long error messages."""
        long_message = "x" * 10000
        exc = AppException(long_message)
        assert exc.message == long_message
        assert len(str(exc)) == 10000

    def test_complex_nested_details(self):
        """Test exception with deeply nested details dictionary."""
        complex_details = {
            "level1": {
                "level2": {
                    "level3": {
                        "field": "value",
                        "list": [1, 2, 3],
                    }
                }
            }
        }
        exc = AppException("Test", details=complex_details)
        assert exc.details == complex_details

    def test_details_with_various_types(self):
        """Test exception details with various Python types."""
        details = {
            "string": "value",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }
        exc = AppException("Test", details=details)
        response = exc.to_response()
        assert response.details == details

    def test_override_class_attributes_with_init_params(self):
        """Test that init parameters override class attributes."""

        class CustomError(AppException):
            status_code: int = 400
            error: str = "custom_error"

        exc = CustomError(
            "Test",
            status_code=500,
            error="overridden_error",
        )
        assert exc.status_code == 500
        assert exc.error == "overridden_error"

    def test_exception_equality_not_implemented(self):
        """Test that exceptions are compared by identity, not value."""
        exc1 = AppException("Test", error="test_error")
        exc2 = AppException("Test", error="test_error")
        assert exc1 is not exc2
        assert exc1 != exc2

    def test_error_response_with_special_characters(self):
        """Test ErrorResponse handles special characters in strings."""
        response = ErrorResponse(
            error="test_error",
            message="Error with special chars: <>&\"'",
            details={"field": "value with 日本語"},
        )
        json_str = response.model_dump_json()
        assert "special chars" in json_str
        assert "日本語" in json_str


# =============================================================================
# Module-Level Constants and Exports
# =============================================================================


class TestModuleExports:
    """Tests for module-level constants and __all__ exports."""

    def test_all_exports_defined(self):
        """Test that __all__ is defined and contains expected exports."""
        from backend.api.middleware import error_handler

        assert hasattr(error_handler, "__all__")
        exports = error_handler.__all__
        assert isinstance(exports, list)
        assert len(exports) > 0

    def test_appexception_in_exports(self):
        """Test that AppException is in __all__ exports."""
        from backend.api.middleware import error_handler

        assert "AppException" in error_handler.__all__

    def test_error_response_in_exports(self):
        """Test that ErrorResponse is in __all__ exports."""
        from backend.api.middleware import error_handler

        assert "ErrorResponse" in error_handler.__all__

    def test_exception_classes_in_exports(self):
        """Test that exception classes are in __all__ exports."""
        from backend.api.middleware import error_handler

        expected_exceptions = [
            "ValidationError",
            "UnauthorizedError",
            "ForbiddenError",
            "ServiceUnavailableError",
            "RateLimitExceededError",
            "NotFoundError",
            "ConflictError",
        ]
        for exc_name in expected_exceptions:
            assert exc_name in error_handler.__all__

    def test_utility_functions_in_exports(self):
        """Test that utility functions are in __all__ exports."""
        from backend.api.middleware import error_handler

        expected_utils = [
            "build_error_response",
            "get_request_id",
            "register_exception_handlers",
        ]
        for util_name in expected_utils:
            assert util_name in error_handler.__all__

    def test_all_exported_items_are_importable(self):
        """Test that all items in __all__ can be imported."""
        from backend.api.middleware import error_handler

        for item_name in error_handler.__all__:
            assert hasattr(error_handler, item_name), f"{item_name} not found in module"
