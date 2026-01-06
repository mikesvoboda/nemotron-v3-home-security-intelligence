"""Tests for the consolidated exception hierarchy."""

from backend.core.exceptions import (
    CameraNotFoundError,
    CircuitBreakerOpenError,
    DatabaseError,
    DetectorUnavailableError,
    RateLimitError,
    SecurityIntelligenceError,
    ValidationError,
    get_exception_error_code,
    get_exception_status_code,
)


class TestSecurityIntelligenceError:
    def test_default_values(self) -> None:
        exc = SecurityIntelligenceError()
        assert exc.message == "An unexpected error occurred"
        assert exc.error_code == "INTERNAL_ERROR"
        assert exc.status_code == 500
        assert exc.details == {}

    def test_custom_message(self) -> None:
        exc = SecurityIntelligenceError("Custom error message")
        assert exc.message == "Custom error message"
        assert str(exc) == "Custom error message"


class TestValidationErrors:
    def test_validation_error_defaults(self) -> None:
        exc = ValidationError()
        assert exc.status_code == 400
        assert exc.error_code == "VALIDATION_ERROR"


class TestNotFoundErrors:
    def test_camera_not_found_error(self) -> None:
        exc = CameraNotFoundError(camera_id="backyard")
        assert exc.status_code == 404
        assert exc.error_code == "CAMERA_NOT_FOUND"
        assert "backyard" in exc.message


class TestRateLimitError:
    def test_rate_limit_error_defaults(self) -> None:
        exc = RateLimitError()
        assert exc.status_code == 429
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"


class TestExternalServiceErrors:
    def test_detector_unavailable_error(self) -> None:
        exc = DetectorUnavailableError()
        assert exc.error_code == "DETECTOR_UNAVAILABLE"
        assert exc.service_name == "rtdetr"

    def test_database_error(self) -> None:
        exc = DatabaseError()
        assert exc.status_code == 503
        assert exc.error_code == "DATABASE_ERROR"

    def test_circuit_breaker_open_error(self) -> None:
        exc = CircuitBreakerOpenError(service_name="rtdetr", recovery_timeout=30.0)
        assert exc.status_code == 503
        assert exc.error_code == "CIRCUIT_BREAKER_OPEN"
        assert exc.details["recovery_timeout_seconds"] == 30.0


class TestUtilityFunctions:
    def test_get_exception_status_code_custom(self) -> None:
        exc = CameraNotFoundError(camera_id="test")
        assert get_exception_status_code(exc) == 404

    def test_get_exception_error_code_custom(self) -> None:
        exc = RateLimitError()
        assert get_exception_error_code(exc) == "RATE_LIMIT_EXCEEDED"
