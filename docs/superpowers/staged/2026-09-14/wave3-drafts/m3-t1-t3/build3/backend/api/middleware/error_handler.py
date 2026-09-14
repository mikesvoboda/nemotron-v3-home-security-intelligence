"""Centralized error handler middleware for consistent API error responses.

This module provides:
1. AppException base class and common exception types for API errors
2. Convenience re-exports from the main exception handling infrastructure

The exception hierarchy follows the pattern specified in NEM-2571:
- AppException: Base class with status_code and error attributes
- NotFoundError: 404 errors for missing resources
- ValidationError: 422 errors for invalid input
- ConflictError: 409 errors for resource conflicts
- UnauthorizedError: 401 errors for authentication failures
- ForbiddenError: 403 errors for authorization failures
- ServiceUnavailableError: 503 errors for external service failures

Usage in routes:
    from backend.api.middleware.error_handler import NotFoundError, ValidationError

    @router.get("/cameras/{camera_id}")
    async def get_camera(camera_id: str) -> Camera:
        camera = await get_camera_by_id(camera_id)
        if not camera:
            raise NotFoundError(
                message=f"Camera '{camera_id}' not found",
                details={"camera_id": camera_id},
            )
        return camera

The exception handlers are registered globally in main.py via
register_exception_handlers(app), ensuring consistent error response format
across all API endpoints.

NEM-2571: Centralize API error response handling with middleware
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

# Re-export the main exception handler registration function
from backend.api.exception_handlers import (
    build_error_response,
    get_request_id,
    register_exception_handlers,
)

# Re-export the existing exception hierarchy for backward compatibility
from backend.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    CameraNotFoundError,
    CircuitBreakerOpenError,
    ConflictError,
    DatabaseError,
    DetectionNotFoundError,
    DetectorUnavailableError,
    DuplicateResourceError,
    EventNotFoundError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ResourceNotFoundError,
    SecurityIntelligenceError,
)
from backend.core.exceptions import ValidationError as CoreValidationError

__all__ = [
    "AppException",
    "AuthenticationError",
    "AuthorizationError",
    "CameraNotFoundError",
    "CircuitBreakerOpenError",
    "ConflictError",
    "CoreValidationError",
    "DatabaseError",
    "DetectionNotFoundError",
    "DetectorUnavailableError",
    "DuplicateResourceError",
    "ErrorResponse",
    "EventNotFoundError",
    "ExternalServiceError",
    "ForbiddenError",
    "NotFoundError",
    "RateLimitError",
    "RateLimitExceededError",
    "ResourceNotFoundError",
    "SecurityIntelligenceError",
    "ServiceUnavailableError",
    "UnauthorizedError",
    "ValidationError",
    "build_error_response",
    "get_request_id",
    "register_exception_handlers",
]


# =============================================================================
# ErrorResponse Schema (NEM-2571)
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response schema for consistent API error handling.

    This schema ensures all API errors return a consistent format that includes:
    - error: Machine-readable error code (e.g., "not_found", "validation_error")
    - message: Human-readable error description
    - details: Optional additional context about the error
    - request_id: Optional request correlation ID for debugging
    - timestamp: When the error occurred (ISO 8601 format)

    Example JSON response:
        {
            "error": "not_found",
            "message": "Camera 'front_door' not found",
            "details": {"camera_id": "front_door"},
            "request_id": "req-abc-123",
            "timestamp": "2024-01-15T10:30:00Z"
        }

    This schema matches the specification in NEM-2571.
    """

    error: str = Field(
        ...,
        description="Machine-readable error code (e.g., 'not_found', 'validation_error')",
        examples=["not_found", "validation_error", "internal_error"],
    )
    message: str = Field(
        ...,
        description="Human-readable error description",
        examples=["Camera 'front_door' not found", "Invalid date range"],
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional context about the error",
        examples=[{"camera_id": "front_door"}, {"field": "start_date"}],
    )
    request_id: str | None = Field(
        default=None,
        description="Request correlation ID for debugging and log tracing",
        examples=["req-abc-123", "550e8400-e29b-41d4-a716-446655440000"],
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the error occurred (ISO 8601 format)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "not_found",
                "message": "Camera 'front_door' not found",
                "details": {"camera_id": "front_door"},
                "request_id": "req-abc-123",
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }
    }


# =============================================================================
# AppException Hierarchy (NEM-2571)
# =============================================================================


class AppException(Exception):
    """Base exception for application-specific API errors.

    This class provides the foundation for all application exceptions with:
    - status_code: HTTP status code to return
    - error: Machine-readable error code
    - message: Human-readable error description
    - details: Optional additional context

    Subclass this for specific error types (not_found, validation_error, etc.).

    The exception handlers in backend/api/exception_handlers.py convert these
    exceptions to standardized ErrorResponse format automatically.

    Example:
        raise AppException(
            status_code=400,
            error="bad_request",
            message="Invalid request format",
            details={"reason": "Missing required field"},
        )
    """

    status_code: int = 500
    error: str = "internal_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        status_code: int | None = None,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description
            status_code: HTTP status code (default: class attribute)
            error: Machine-readable error code (default: class attribute)
            details: Optional additional context about the error
        """
        self.message = message or self._get_default_message()
        if status_code is not None:
            self.status_code = status_code
        if error is not None:
            self.error = error
        self.details = details
        super().__init__(self.message)

    def _get_default_message(self) -> str:
        """Get the default message based on error code."""
        return f"An error occurred: {self.error}"

    def to_response(self, request_id: str | None = None) -> ErrorResponse:
        """Convert exception to ErrorResponse schema.

        Args:
            request_id: Optional request ID for correlation

        Returns:
            ErrorResponse instance
        """
        return ErrorResponse(
            error=self.error,
            message=self.message,
            details=self.details,
            request_id=request_id,
        )


# Alias for backward compatibility - SecurityIntelligenceError is the existing base
# AppException is the interface specified in NEM-2571
# Both serve the same purpose; use whichever fits your needs


class ValidationError(AppException):
    """Exception for validation errors (HTTP 422).

    Raised when request data fails validation, such as:
    - Invalid field values
    - Missing required fields
    - Constraint violations
    - Invalid date ranges

    Example:
        raise ValidationError(
            message="Invalid date range: start_date must be before end_date",
            details={"start_date": "2024-01-15", "end_date": "2024-01-10"},
        )
    """

    status_code: int = 422
    error: str = "validation_error"

    def _get_default_message(self) -> str:
        return "Request validation failed"


class UnauthorizedError(AppException):
    """Exception for authentication errors (HTTP 401).

    Raised when authentication is required but not provided or invalid:
    - Missing API key
    - Invalid API key
    - Expired token

    Example:
        raise UnauthorizedError(message="Invalid API key")
    """

    status_code: int = 401
    error: str = "unauthorized"

    def _get_default_message(self) -> str:
        return "Authentication required"


class ForbiddenError(AppException):
    """Exception for authorization errors (HTTP 403).

    Raised when the user is authenticated but lacks permission:
    - Insufficient permissions
    - Resource access denied
    - Operation not allowed

    Example:
        raise ForbiddenError(
            message="Access denied to camera configuration",
            details={"camera_id": "front_door"},
        )
    """

    status_code: int = 403
    error: str = "forbidden"

    def _get_default_message(self) -> str:
        return "Access denied"


class ServiceUnavailableError(AppException):
    """Exception for external service errors (HTTP 503).

    Raised when an external dependency is unavailable:
    - AI service (YOLO26v2, Nemotron) unavailable
    - Database connection failure
    - Redis unavailable

    Example:
        raise ServiceUnavailableError(
            message="Object detection service temporarily unavailable",
            details={"service": "yolo26", "retry_after": 30},
        )
    """

    status_code: int = 503
    error: str = "service_unavailable"

    def _get_default_message(self) -> str:
        return "Service temporarily unavailable"


class RateLimitExceededError(AppException):
    """Exception for rate limit errors (HTTP 429).

    Raised when a client exceeds the rate limit:
    - Too many requests per minute
    - Quota exceeded

    Example:
        raise RateLimitExceededError(
            message="Rate limit exceeded. Please wait before retrying.",
            details={"retry_after": 60, "limit": 100},
        )
    """

    status_code: int = 429
    error: str = "rate_limit_exceeded"

    def _get_default_message(self) -> str:
        return "Rate limit exceeded"


# Note: NotFoundError and ConflictError are already defined in backend.core.exceptions
# and are re-exported above. They follow the same pattern as AppException but are
# implemented as SecurityIntelligenceError subclasses for consistency with the
# existing codebase.
