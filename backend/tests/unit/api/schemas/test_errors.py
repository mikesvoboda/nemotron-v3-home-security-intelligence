"""Unit tests for error response schemas.

Tests cover:
- ErrorCode constants and their values
- FlatErrorResponse schema validation
- ErrorResponse schema (nested format)
- raise_http_error helper function
- ValidationErrorResponse schema
- RateLimitErrorResponse schema
- ServiceUnavailableResponse schema

NEM-1597: Implement standardized error response format
"""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.api.schemas.errors import (
    COMMON_ERROR_RESPONSES,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    FlatErrorResponse,
    RateLimitErrorResponse,
    ServiceUnavailableResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
    raise_http_error,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# ErrorCode Tests
# =============================================================================


class TestErrorCode:
    """Tests for ErrorCode constants class."""

    def test_camera_not_found_value(self):
        """Test CAMERA_NOT_FOUND error code value."""
        assert ErrorCode.CAMERA_NOT_FOUND == "CAMERA_NOT_FOUND"

    def test_event_not_found_value(self):
        """Test EVENT_NOT_FOUND error code value."""
        assert ErrorCode.EVENT_NOT_FOUND == "EVENT_NOT_FOUND"

    def test_detection_not_found_value(self):
        """Test DETECTION_NOT_FOUND error code value."""
        assert ErrorCode.DETECTION_NOT_FOUND == "DETECTION_NOT_FOUND"

    def test_validation_error_value(self):
        """Test VALIDATION_ERROR code value."""
        assert ErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"

    def test_invalid_date_range_value(self):
        """Test INVALID_DATE_RANGE code value."""
        assert ErrorCode.INVALID_DATE_RANGE == "INVALID_DATE_RANGE"

    def test_detector_unavailable_value(self):
        """Test DETECTOR_UNAVAILABLE code value."""
        assert ErrorCode.DETECTOR_UNAVAILABLE == "DETECTOR_UNAVAILABLE"

    def test_database_error_value(self):
        """Test DATABASE_ERROR code value."""
        assert ErrorCode.DATABASE_ERROR == "DATABASE_ERROR"

    def test_rate_limit_exceeded_value(self):
        """Test RATE_LIMIT_EXCEEDED code value."""
        assert ErrorCode.RATE_LIMIT_EXCEEDED == "RATE_LIMIT_EXCEEDED"

    def test_authentication_required_value(self):
        """Test AUTHENTICATION_REQUIRED code value."""
        assert ErrorCode.AUTHENTICATION_REQUIRED == "AUTHENTICATION_REQUIRED"

    def test_access_denied_value(self):
        """Test ACCESS_DENIED code value."""
        assert ErrorCode.ACCESS_DENIED == "ACCESS_DENIED"

    def test_internal_error_value(self):
        """Test INTERNAL_ERROR code value."""
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"

    def test_file_not_found_value(self):
        """Test FILE_NOT_FOUND code value."""
        assert ErrorCode.FILE_NOT_FOUND == "FILE_NOT_FOUND"

    def test_ai_service_timeout_value(self):
        """Test AI_SERVICE_TIMEOUT code value."""
        assert ErrorCode.AI_SERVICE_TIMEOUT == "AI_SERVICE_TIMEOUT"

    def test_all_error_codes_are_strings(self):
        """Test that all error codes are string values."""
        # Get all class attributes that are error codes (uppercase names)
        error_codes = [
            attr for attr in dir(ErrorCode) if not attr.startswith("_") and attr.isupper()
        ]
        assert len(error_codes) > 0, "Should have error codes defined"
        for code_name in error_codes:
            code_value = getattr(ErrorCode, code_name)
            assert isinstance(code_value, str), f"{code_name} should be a string"
            assert code_value == code_name, f"{code_name} value should match attribute name"


# =============================================================================
# FlatErrorResponse Tests
# =============================================================================


class TestFlatErrorResponse:
    """Tests for FlatErrorResponse schema (flat format)."""

    def test_minimal_error_response(self):
        """Test creating error response with required fields only."""
        response = FlatErrorResponse(
            error_code=ErrorCode.CAMERA_NOT_FOUND,
            message="Camera not found",
        )
        assert response.error_code == "CAMERA_NOT_FOUND"
        assert response.message == "Camera not found"
        assert response.details is None
        assert response.request_id is None

    def test_full_error_response(self):
        """Test creating error response with all fields."""
        response = FlatErrorResponse(
            error_code=ErrorCode.CAMERA_NOT_FOUND,
            message="Camera 'front_door' not found in database",
            details={"camera_id": "front_door"},
            request_id="req-123-456",
        )
        assert response.error_code == "CAMERA_NOT_FOUND"
        assert response.message == "Camera 'front_door' not found in database"
        assert response.details == {"camera_id": "front_door"}
        assert response.request_id == "req-123-456"

    def test_error_response_with_complex_details(self):
        """Test error response with complex details dict."""
        details = {
            "camera_id": "front_door",
            "resource_type": "camera",
            "attempted_at": "2024-01-15T10:30:00Z",
            "search_params": {"name": "front*", "status": "active"},
        }
        response = FlatErrorResponse(
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Resource not found",
            details=details,
        )
        assert response.details == details

    def test_error_response_serialization(self):
        """Test that error response serializes to dict correctly."""
        response = FlatErrorResponse(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Invalid date range",
            details={"start_date": "2024-01-15", "end_date": "2024-01-10"},
            request_id="req-abc-xyz",
        )
        data = response.model_dump()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert data["message"] == "Invalid date range"
        assert data["details"]["start_date"] == "2024-01-15"
        assert data["request_id"] == "req-abc-xyz"

    def test_error_response_json_serialization(self):
        """Test that error response serializes to JSON correctly."""
        response = FlatErrorResponse(
            error_code=ErrorCode.CAMERA_NOT_FOUND,
            message="Not found",
        )
        json_str = response.model_dump_json()
        assert '"error_code":"CAMERA_NOT_FOUND"' in json_str
        assert '"message":"Not found"' in json_str

    def test_missing_error_code_raises_validation_error(self):
        """Test that missing error_code raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            FlatErrorResponse(message="Error occurred")  # type: ignore
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("error_code",) for e in errors)

    def test_missing_message_raises_validation_error(self):
        """Test that missing message raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            FlatErrorResponse(error_code="TEST_ERROR")  # type: ignore
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("message",) for e in errors)


# =============================================================================
# raise_http_error Tests
# =============================================================================


class TestRaiseHttpError:
    """Tests for raise_http_error helper function."""

    def test_raises_http_exception(self):
        """Test that raise_http_error raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=404,
                error_code=ErrorCode.CAMERA_NOT_FOUND,
                message="Camera not found",
            )
        assert exc_info.value.status_code == 404

    def test_exception_detail_contains_error_code(self):
        """Test that exception detail contains error_code."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=404,
                error_code=ErrorCode.CAMERA_NOT_FOUND,
                message="Camera not found",
            )
        assert exc_info.value.detail["error_code"] == "CAMERA_NOT_FOUND"

    def test_exception_detail_contains_message(self):
        """Test that exception detail contains message."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=400,
                error_code=ErrorCode.VALIDATION_ERROR,
                message="Invalid request body",
            )
        assert exc_info.value.detail["message"] == "Invalid request body"

    def test_exception_detail_with_details(self):
        """Test that exception detail includes details when provided."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=404,
                error_code=ErrorCode.CAMERA_NOT_FOUND,
                message="Camera not found",
                details={"camera_id": "front_door"},
            )
        assert exc_info.value.detail["details"] == {"camera_id": "front_door"}

    def test_exception_detail_with_request_id(self):
        """Test that exception detail includes request_id when provided."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=500,
                error_code=ErrorCode.INTERNAL_ERROR,
                message="Internal error",
                request_id="req-123",
            )
        assert exc_info.value.detail["request_id"] == "req-123"

    def test_exception_detail_without_optional_fields(self):
        """Test that exception detail excludes optional fields when not provided."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=404,
                error_code=ErrorCode.EVENT_NOT_FOUND,
                message="Event not found",
            )
        detail = exc_info.value.detail
        assert "details" not in detail
        assert "request_id" not in detail

    def test_400_validation_error(self):
        """Test 400 validation error."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=400,
                error_code=ErrorCode.INVALID_DATE_RANGE,
                message="Start date must be before end date",
                details={"start_date": "2024-01-15", "end_date": "2024-01-10"},
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error_code"] == "INVALID_DATE_RANGE"

    def test_401_authentication_error(self):
        """Test 401 authentication error."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=401,
                error_code=ErrorCode.AUTHENTICATION_REQUIRED,
                message="API key required",
            )
        assert exc_info.value.status_code == 401

    def test_403_access_denied_error(self):
        """Test 403 access denied error."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=403,
                error_code=ErrorCode.ACCESS_DENIED,
                message="Insufficient permissions",
            )
        assert exc_info.value.status_code == 403

    def test_409_conflict_error(self):
        """Test 409 conflict error."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=409,
                error_code=ErrorCode.CAMERA_ALREADY_EXISTS,
                message="Camera already exists",
                details={"camera_id": "front_door"},
            )
        assert exc_info.value.status_code == 409

    def test_429_rate_limit_error(self):
        """Test 429 rate limit error."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=429,
                error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
                message="Rate limit exceeded",
                details={"retry_after": 60},
            )
        assert exc_info.value.status_code == 429

    def test_500_internal_error(self):
        """Test 500 internal error."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=500,
                error_code=ErrorCode.INTERNAL_ERROR,
                message="Unexpected error occurred",
                request_id="req-abc-123",
            )
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail["request_id"] == "req-abc-123"

    def test_503_service_unavailable(self):
        """Test 503 service unavailable error."""
        with pytest.raises(HTTPException) as exc_info:
            raise_http_error(
                status_code=503,
                error_code=ErrorCode.DETECTOR_UNAVAILABLE,
                message="RT-DETR service unavailable",
                details={"service": "rtdetr", "retry_after": 30},
            )
        assert exc_info.value.status_code == 503


# =============================================================================
# ErrorResponse Tests (Legacy Nested Format)
# =============================================================================


class TestErrorResponse:
    """Tests for ErrorResponse schema (nested format)."""

    def test_create_error_response(self):
        """Test creating nested error response."""
        response = ErrorResponse(
            error=ErrorDetail(
                code="CAMERA_NOT_FOUND",
                message="Camera not found",
            )
        )
        assert response.error.code == "CAMERA_NOT_FOUND"
        assert response.error.message == "Camera not found"

    def test_error_response_serialization(self):
        """Test nested error response serializes with wrapper."""
        response = ErrorResponse(
            error=ErrorDetail(
                code="TEST_ERROR",
                message="Test message",
                details={"key": "value"},
            )
        )
        data = response.model_dump()
        assert "error" in data
        assert data["error"]["code"] == "TEST_ERROR"
        assert data["error"]["details"] == {"key": "value"}


# =============================================================================
# ValidationErrorResponse Tests
# =============================================================================


class TestValidationErrorResponse:
    """Tests for ValidationErrorResponse schema."""

    def test_create_validation_error_response(self):
        """Test creating validation error response."""
        response = ValidationErrorResponse(
            error=ValidationErrorResponse.ValidationErrorInfo(
                errors=[
                    ValidationErrorDetail(
                        field="body.start_date",
                        message="Invalid date format",
                        value="invalid-date",
                    )
                ]
            )
        )
        assert response.error.code == "VALIDATION_ERROR"
        assert len(response.error.errors) == 1
        assert response.error.errors[0].field == "body.start_date"

    def test_validation_error_with_multiple_errors(self):
        """Test validation error with multiple field errors."""
        response = ValidationErrorResponse(
            error=ValidationErrorResponse.ValidationErrorInfo(
                errors=[
                    ValidationErrorDetail(
                        field="body.email",
                        message="Invalid email format",
                    ),
                    ValidationErrorDetail(
                        field="body.limit",
                        message="Value must be positive",
                        value=-5,
                    ),
                ],
                request_id="req-123",
            )
        )
        assert len(response.error.errors) == 2
        assert response.error.request_id == "req-123"


# =============================================================================
# RateLimitErrorResponse Tests
# =============================================================================


class TestRateLimitErrorResponse:
    """Tests for RateLimitErrorResponse schema."""

    def test_create_rate_limit_error(self):
        """Test creating rate limit error response."""
        response = RateLimitErrorResponse(
            error=RateLimitErrorResponse.RateLimitErrorInfo(
                retry_after=60,
                limit=100,
                window_seconds=60,
            )
        )
        assert response.error.code == "RATE_LIMIT_EXCEEDED"
        assert response.error.retry_after == 60
        assert response.error.limit == 100
        assert response.error.window_seconds == 60


# =============================================================================
# ServiceUnavailableResponse Tests
# =============================================================================


class TestServiceUnavailableResponse:
    """Tests for ServiceUnavailableResponse schema."""

    def test_create_service_unavailable_error(self):
        """Test creating service unavailable error response."""
        response = ServiceUnavailableResponse(
            error=ServiceUnavailableResponse.ServiceErrorInfo(
                message="AI service unavailable",
                service="rtdetr",
                retry_after=30,
            )
        )
        assert response.error.code == "SERVICE_UNAVAILABLE"
        assert response.error.service == "rtdetr"
        assert response.error.retry_after == 30


# =============================================================================
# COMMON_ERROR_RESPONSES Tests
# =============================================================================


class TestCommonErrorResponses:
    """Tests for COMMON_ERROR_RESPONSES dictionary."""

    def test_400_response_defined(self):
        """Test 400 response is defined."""
        assert 400 in COMMON_ERROR_RESPONSES
        assert COMMON_ERROR_RESPONSES[400]["model"] == ValidationErrorResponse

    def test_401_response_defined(self):
        """Test 401 response is defined."""
        assert 401 in COMMON_ERROR_RESPONSES
        assert COMMON_ERROR_RESPONSES[401]["model"] == ErrorResponse

    def test_403_response_defined(self):
        """Test 403 response is defined."""
        assert 403 in COMMON_ERROR_RESPONSES
        assert COMMON_ERROR_RESPONSES[403]["model"] == ErrorResponse

    def test_404_response_defined(self):
        """Test 404 response is defined."""
        assert 404 in COMMON_ERROR_RESPONSES
        assert COMMON_ERROR_RESPONSES[404]["model"] == ErrorResponse

    def test_409_response_defined(self):
        """Test 409 response is defined."""
        assert 409 in COMMON_ERROR_RESPONSES
        assert COMMON_ERROR_RESPONSES[409]["model"] == ErrorResponse

    def test_429_response_defined(self):
        """Test 429 response is defined."""
        assert 429 in COMMON_ERROR_RESPONSES
        assert COMMON_ERROR_RESPONSES[429]["model"] == RateLimitErrorResponse

    def test_500_response_defined(self):
        """Test 500 response is defined."""
        assert 500 in COMMON_ERROR_RESPONSES
        assert COMMON_ERROR_RESPONSES[500]["model"] == ErrorResponse

    def test_502_response_defined(self):
        """Test 502 response is defined."""
        assert 502 in COMMON_ERROR_RESPONSES
        assert COMMON_ERROR_RESPONSES[502]["model"] == ServiceUnavailableResponse

    def test_503_response_defined(self):
        """Test 503 response is defined."""
        assert 503 in COMMON_ERROR_RESPONSES
        assert COMMON_ERROR_RESPONSES[503]["model"] == ServiceUnavailableResponse

    def test_all_responses_have_description(self):
        """Test all error responses have descriptions."""
        for status_code, config in COMMON_ERROR_RESPONSES.items():
            assert "description" in config, f"Status {status_code} missing description"
            assert isinstance(config["description"], str)
            assert len(config["description"]) > 0
