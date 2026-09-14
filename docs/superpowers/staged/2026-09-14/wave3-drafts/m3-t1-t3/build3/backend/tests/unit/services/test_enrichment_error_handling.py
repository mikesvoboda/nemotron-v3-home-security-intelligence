"""Unit tests for enrichment pipeline error handling (NEM-2542).

Tests cover:
- EnrichmentError dataclass creation and serialization
- ErrorCategory enum classification
- Exception-to-error mapping for different exception types
- Transient vs permanent error classification
- Structured logging for all error paths
- EnrichmentResult.add_error method
- Error properties on EnrichmentResult
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from backend.core.exceptions import (
    AIServiceError,
    CLIPUnavailableError,
    EnrichmentUnavailableError,
    FlorenceUnavailableError,
)
from backend.services.enrichment_pipeline import (
    EnrichmentError,
    EnrichmentResult,
    ErrorCategory,
)

# =============================================================================
# Test ErrorCategory Enum
# =============================================================================


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_transient_error_categories(self) -> None:
        """Test that transient error categories are correctly defined."""
        transient_categories = [
            ErrorCategory.SERVICE_UNAVAILABLE,
            ErrorCategory.TIMEOUT,
            ErrorCategory.RATE_LIMITED,
            ErrorCategory.SERVER_ERROR,
        ]
        for category in transient_categories:
            assert isinstance(category.value, str)
            assert category in ErrorCategory

    def test_permanent_error_categories(self) -> None:
        """Test that permanent error categories are correctly defined."""
        permanent_categories = [
            ErrorCategory.CLIENT_ERROR,
            ErrorCategory.PARSE_ERROR,
            ErrorCategory.VALIDATION_ERROR,
        ]
        for category in permanent_categories:
            assert isinstance(category.value, str)
            assert category in ErrorCategory

    def test_unexpected_error_category(self) -> None:
        """Test the unexpected error category."""
        assert ErrorCategory.UNEXPECTED in ErrorCategory
        assert ErrorCategory.UNEXPECTED.value == "unexpected"


# =============================================================================
# Test EnrichmentError Dataclass
# =============================================================================


class TestEnrichmentError:
    """Tests for EnrichmentError dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic EnrichmentError creation."""
        error = EnrichmentError(
            operation="test_operation",
            category=ErrorCategory.SERVICE_UNAVAILABLE,
            reason="Test reason",
            error_type="ConnectionError",
            is_transient=True,
        )
        assert error.operation == "test_operation"
        assert error.category == ErrorCategory.SERVICE_UNAVAILABLE
        assert error.reason == "Test reason"
        assert error.error_type == "ConnectionError"
        assert error.is_transient is True
        assert error.details == {}

    def test_creation_with_details(self) -> None:
        """Test EnrichmentError creation with details."""
        details = {"detection_id": "123", "status_code": 500}
        error = EnrichmentError(
            operation="vehicle_classification",
            category=ErrorCategory.SERVER_ERROR,
            reason="Server error",
            error_type="HTTPStatusError",
            is_transient=True,
            details=details,
        )
        assert error.details == details

    def test_to_dict(self) -> None:
        """Test EnrichmentError.to_dict() serialization."""
        error = EnrichmentError(
            operation="face_detection",
            category=ErrorCategory.TIMEOUT,
            reason="Request timed out",
            error_type="TimeoutException",
            is_transient=True,
            details={"duration_ms": 5000},
        )
        result = error.to_dict()

        assert result["operation"] == "face_detection"
        assert result["category"] == "timeout"
        assert result["reason"] == "Request timed out"
        assert result["error_type"] == "TimeoutException"
        assert result["is_transient"] is True
        assert result["details"] == {"duration_ms": 5000}

    def test_to_dict_json_serializable(self) -> None:
        """Test that to_dict() output is JSON serializable."""
        error = EnrichmentError(
            operation="test",
            category=ErrorCategory.PARSE_ERROR,
            reason="Parse failed",
            error_type="ValueError",
            is_transient=False,
        )
        # Should not raise
        json_str = json.dumps(error.to_dict())
        assert isinstance(json_str, str)


# =============================================================================
# Test EnrichmentError.from_exception()
# =============================================================================


class TestEnrichmentErrorFromException:
    """Tests for EnrichmentError.from_exception() class method."""

    def test_from_connect_error(self) -> None:
        """Test classification of httpx.ConnectError."""
        exc = httpx.ConnectError("Connection refused")
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.SERVICE_UNAVAILABLE
        assert error.is_transient is True
        assert error.error_type == "ConnectError"
        assert "Connection refused" in error.reason or "connection" in error.reason.lower()

    def test_from_timeout_exception(self) -> None:
        """Test classification of httpx.TimeoutException."""
        exc = httpx.TimeoutException("Request timed out")
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.TIMEOUT
        assert error.is_transient is True
        assert error.error_type == "TimeoutException"

    def test_from_asyncio_timeout(self) -> None:
        """Test classification of asyncio.TimeoutError."""

        exc = TimeoutError()
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.TIMEOUT
        assert error.is_transient is True

    def test_from_http_429_rate_limited(self) -> None:
        """Test classification of HTTP 429 (rate limited)."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        exc = httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=mock_response)

        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.RATE_LIMITED
        assert error.is_transient is True
        assert error.details.get("status_code") == 429

    def test_from_http_5xx_server_error(self) -> None:
        """Test classification of HTTP 5xx (server error)."""
        for status_code in [500, 502, 503, 504]:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            exc = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)

            error = EnrichmentError.from_exception("test_operation", exc)

            assert error.category == ErrorCategory.SERVER_ERROR, f"Failed for {status_code}"
            assert error.is_transient is True, f"Failed for {status_code}"
            assert error.details.get("status_code") == status_code

    def test_from_http_4xx_client_error(self) -> None:
        """Test classification of HTTP 4xx (client error) - not transient."""
        for status_code in [400, 401, 403, 404, 422]:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            exc = httpx.HTTPStatusError("Client error", request=MagicMock(), response=mock_response)

            error = EnrichmentError.from_exception("test_operation", exc)

            assert error.category == ErrorCategory.CLIENT_ERROR, f"Failed for {status_code}"
            assert error.is_transient is False, f"Failed for {status_code}"  # NOT transient!
            assert error.details.get("status_code") == status_code

    def test_from_ai_service_error(self) -> None:
        """Test classification of AIServiceError."""
        exc = AIServiceError("AI service down")
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.SERVICE_UNAVAILABLE
        assert error.is_transient is True

    def test_from_enrichment_unavailable_error(self) -> None:
        """Test classification of EnrichmentUnavailableError."""
        exc = EnrichmentUnavailableError("Enrichment service unavailable")
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.SERVICE_UNAVAILABLE
        assert error.is_transient is True

    def test_from_florence_unavailable_error(self) -> None:
        """Test classification of FlorenceUnavailableError."""
        exc = FlorenceUnavailableError("Florence unavailable")
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.SERVICE_UNAVAILABLE
        assert error.is_transient is True

    def test_from_clip_unavailable_error(self) -> None:
        """Test classification of CLIPUnavailableError."""
        exc = CLIPUnavailableError("CLIP unavailable")
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.SERVICE_UNAVAILABLE
        assert error.is_transient is True

    def test_from_value_error(self) -> None:
        """Test classification of ValueError (parse error)."""
        exc = ValueError("Invalid JSON")
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.PARSE_ERROR
        assert error.is_transient is False  # Parse errors are NOT transient

    def test_from_key_error(self) -> None:
        """Test classification of KeyError (parse error)."""
        exc = KeyError("missing_key")
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.PARSE_ERROR
        assert error.is_transient is False

    def test_from_type_error(self) -> None:
        """Test classification of TypeError (parse error)."""
        exc = TypeError("Expected int, got str")
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.PARSE_ERROR
        assert error.is_transient is False

    def test_from_json_decode_error(self) -> None:
        """Test classification of json.JSONDecodeError."""
        exc = json.JSONDecodeError("Invalid JSON", "doc", 0)
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.PARSE_ERROR
        assert error.is_transient is False

    def test_from_attribute_error_validation(self) -> None:
        """Test classification of AttributeError (validation error)."""
        exc = AttributeError("'NoneType' has no attribute 'value'")
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.VALIDATION_ERROR
        assert error.is_transient is False

    def test_from_unknown_exception(self) -> None:
        """Test classification of unknown exception types."""
        exc = RuntimeError("Unknown error")
        error = EnrichmentError.from_exception("test_operation", exc)

        assert error.category == ErrorCategory.UNEXPECTED
        assert error.is_transient is True  # Assume transient for unknown

    def test_with_additional_details(self) -> None:
        """Test that additional details are preserved."""
        exc = httpx.TimeoutException("Timeout")
        details = {"detection_id": "123", "camera_id": "front"}
        error = EnrichmentError.from_exception("test_op", exc, details=details)

        assert error.details["detection_id"] == "123"
        assert error.details["camera_id"] == "front"


# =============================================================================
# Test EnrichmentResult Error Methods
# =============================================================================


class TestEnrichmentResultErrorMethods:
    """Tests for EnrichmentResult error handling methods."""

    def test_add_error(self) -> None:
        """Test EnrichmentResult.add_error() method."""
        result = EnrichmentResult()
        exc = httpx.ConnectError("Connection refused")

        error = result.add_error("test_operation", exc)

        assert len(result.structured_errors) == 1
        assert result.structured_errors[0] == error
        # Also check legacy errors list
        assert len(result.errors) == 1
        assert "test_operation failed" in result.errors[0]

    def test_add_error_with_details(self) -> None:
        """Test add_error with additional details."""
        result = EnrichmentResult()
        exc = ValueError("Parse error")
        details = {"detection_id": "42"}

        error = result.add_error("parsing", exc, details=details)

        assert error.details["detection_id"] == "42"

    def test_has_structured_errors(self) -> None:
        """Test has_structured_errors property."""
        result = EnrichmentResult()
        assert result.has_structured_errors is False

        result.add_error("test", ValueError("error"))
        assert result.has_structured_errors is True

    def test_has_transient_errors(self) -> None:
        """Test has_transient_errors property."""
        result = EnrichmentResult()
        assert result.has_transient_errors is False

        # Add a transient error
        result.add_error("test", httpx.TimeoutException("Timeout"))
        assert result.has_transient_errors is True

    def test_has_permanent_errors(self) -> None:
        """Test has_permanent_errors property."""
        result = EnrichmentResult()
        assert result.has_permanent_errors is False

        # Add a permanent error (parse error)
        result.add_error("test", ValueError("Invalid"))
        assert result.has_permanent_errors is True

    def test_transient_error_count(self) -> None:
        """Test transient_error_count property."""
        result = EnrichmentResult()
        assert result.transient_error_count == 0

        result.add_error("test1", httpx.TimeoutException("Timeout"))
        result.add_error("test2", httpx.ConnectError("Connection refused"))
        result.add_error("test3", ValueError("Parse error"))  # Not transient

        assert result.transient_error_count == 2

    def test_permanent_error_count(self) -> None:
        """Test permanent_error_count property."""
        result = EnrichmentResult()
        assert result.permanent_error_count == 0

        result.add_error("test1", httpx.TimeoutException("Timeout"))  # Transient
        result.add_error("test2", ValueError("Parse error"))  # Permanent
        result.add_error("test3", KeyError("missing"))  # Permanent

        assert result.permanent_error_count == 2

    def test_get_errors_by_category(self) -> None:
        """Test get_errors_by_category method."""
        result = EnrichmentResult()

        result.add_error("test1", httpx.TimeoutException("Timeout"))
        result.add_error("test2", httpx.ConnectError("Connection refused"))
        result.add_error("test3", ValueError("Parse error"))

        timeout_errors = result.get_errors_by_category(ErrorCategory.TIMEOUT)
        assert len(timeout_errors) == 1
        assert timeout_errors[0].operation == "test1"

        parse_errors = result.get_errors_by_category(ErrorCategory.PARSE_ERROR)
        assert len(parse_errors) == 1
        assert parse_errors[0].operation == "test3"

    def test_mixed_error_types(self) -> None:
        """Test handling of mixed transient and permanent errors."""
        result = EnrichmentResult()

        # Add various error types
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        mock_response_400 = MagicMock()
        mock_response_400.status_code = 400

        result.add_error("op1", httpx.ConnectError("Connection"))
        result.add_error("op2", httpx.TimeoutException("Timeout"))
        result.add_error(
            "op3",
            httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response_500),
        )
        result.add_error(
            "op4",
            httpx.HTTPStatusError("Client error", request=MagicMock(), response=mock_response_400),
        )
        result.add_error("op5", ValueError("Parse error"))

        # Check counts
        assert result.transient_error_count == 3  # op1, op2, op3
        assert result.permanent_error_count == 2  # op4, op5
        assert result.has_transient_errors is True
        assert result.has_permanent_errors is True


# =============================================================================
# Parametrized Exception Classification Tests
# =============================================================================


@pytest.mark.parametrize(
    "exc_type,exc_args,expected_category,expected_transient",
    [
        # Transient network errors
        (httpx.ConnectError, ("Connection refused",), ErrorCategory.SERVICE_UNAVAILABLE, True),
        (httpx.TimeoutException, ("Request timed out",), ErrorCategory.TIMEOUT, True),
        # Parsing errors (not transient)
        (ValueError, ("Invalid value",), ErrorCategory.PARSE_ERROR, False),
        (KeyError, ("missing_key",), ErrorCategory.PARSE_ERROR, False),
        (TypeError, ("Wrong type",), ErrorCategory.PARSE_ERROR, False),
        # Validation errors (not transient)
        (AttributeError, ("No attribute",), ErrorCategory.VALIDATION_ERROR, False),
        # AI service errors (transient)
        (AIServiceError, ("AI down",), ErrorCategory.SERVICE_UNAVAILABLE, True),
        (EnrichmentUnavailableError, ("Unavailable",), ErrorCategory.SERVICE_UNAVAILABLE, True),
        (FlorenceUnavailableError, ("Florence down",), ErrorCategory.SERVICE_UNAVAILABLE, True),
        (CLIPUnavailableError, ("CLIP down",), ErrorCategory.SERVICE_UNAVAILABLE, True),
        # Unknown errors (assume transient)
        (RuntimeError, ("Unknown",), ErrorCategory.UNEXPECTED, True),
        (IOError, ("IO error",), ErrorCategory.UNEXPECTED, True),
    ],
)
def test_exception_classification(
    exc_type: type,
    exc_args: tuple[str, ...],
    expected_category: ErrorCategory,
    expected_transient: bool,
) -> None:
    """Parametrized test for exception classification."""
    exc = exc_type(*exc_args)
    error = EnrichmentError.from_exception("test_operation", exc)

    assert error.category == expected_category
    assert error.is_transient == expected_transient


@pytest.mark.parametrize(
    "status_code,expected_category,expected_transient",
    [
        # Rate limiting
        (429, ErrorCategory.RATE_LIMITED, True),
        # Server errors (transient)
        (500, ErrorCategory.SERVER_ERROR, True),
        (502, ErrorCategory.SERVER_ERROR, True),
        (503, ErrorCategory.SERVER_ERROR, True),
        (504, ErrorCategory.SERVER_ERROR, True),
        # Client errors (NOT transient - likely bugs)
        (400, ErrorCategory.CLIENT_ERROR, False),
        (401, ErrorCategory.CLIENT_ERROR, False),
        (403, ErrorCategory.CLIENT_ERROR, False),
        (404, ErrorCategory.CLIENT_ERROR, False),
        (422, ErrorCategory.CLIENT_ERROR, False),
    ],
)
def test_http_status_error_classification(
    status_code: int,
    expected_category: ErrorCategory,
    expected_transient: bool,
) -> None:
    """Parametrized test for HTTP status error classification."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    exc = httpx.HTTPStatusError("HTTP error", request=MagicMock(), response=mock_response)

    error = EnrichmentError.from_exception("test_operation", exc)

    assert error.category == expected_category
    assert error.is_transient == expected_transient
    assert error.details.get("status_code") == status_code


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestErrorHandlingIntegration:
    """Integration-style tests for error handling in enrichment pipeline context."""

    def test_multiple_operations_different_errors(self) -> None:
        """Test handling errors from multiple operations."""
        result = EnrichmentResult()

        # Simulate errors from different pipeline stages
        result.add_error("license_plate_detection", httpx.ConnectError("Connection refused"))
        result.add_error("face_detection", httpx.TimeoutException("Timeout"))
        result.add_error("vision_extraction", ValueError("Invalid response format"))

        mock_response = MagicMock()
        mock_response.status_code = 400
        result.add_error(
            "clothing_classification",
            httpx.HTTPStatusError("Bad request", request=MagicMock(), response=mock_response),
        )

        # Verify error tracking
        assert len(result.structured_errors) == 4
        assert len(result.errors) == 4  # Legacy compatibility

        # Verify categorization
        assert result.transient_error_count == 2  # connect, timeout
        assert result.permanent_error_count == 2  # parse, client error

        # Verify category filtering
        timeout_errors = result.get_errors_by_category(ErrorCategory.TIMEOUT)
        assert len(timeout_errors) == 1
        assert timeout_errors[0].operation == "face_detection"

    def test_error_serialization_for_logging(self) -> None:
        """Test that errors can be serialized for structured logging."""
        result = EnrichmentResult()

        mock_response = MagicMock()
        mock_response.status_code = 500
        result.add_error(
            "vehicle_classification",
            httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response),
            details={"detection_id": "123"},
        )

        # Get error dict for logging
        error = result.structured_errors[0]
        error_dict = error.to_dict()

        # Verify it's JSON-serializable (would raise if not)
        json_str = json.dumps(error_dict)
        assert "vehicle_classification" in json_str
        assert "server_error" in json_str
        assert "123" in json_str

    def test_empty_result_no_errors(self) -> None:
        """Test that a fresh EnrichmentResult has no errors."""
        result = EnrichmentResult()

        assert result.has_structured_errors is False
        assert result.has_transient_errors is False
        assert result.has_permanent_errors is False
        assert result.transient_error_count == 0
        assert result.permanent_error_count == 0
        assert len(result.structured_errors) == 0
        assert len(result.errors) == 0
