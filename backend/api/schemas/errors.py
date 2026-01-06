"""Standardized error response schemas for consistent API error handling.

This module defines Pydantic models for error responses that ensure all API
endpoints return errors in a consistent format, regardless of the error source.

Standard Error Response Format:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable error description",
            "details": {
                "field": "value",
                ...
            },
            "request_id": "uuid-for-tracing"
        }
    }

Usage in routes:
    @router.get("/{id}")
    async def get_item(id: int) -> Item:
        '''
        responses={
            404: {"model": ErrorResponse, "description": "Item not found"},
            500: {"model": ErrorResponse, "description": "Internal server error"}
        }
        '''
        ...
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detailed error information.

    This is the inner error object that contains the actual error data.

    Attributes:
        code: Machine-readable error code for programmatic handling
        message: Human-readable error description
        details: Additional context about the error (optional)
        request_id: Unique request identifier for tracing (optional)
        timestamp: When the error occurred (optional)
    """

    code: str = Field(
        ...,
        description="Machine-readable error code (e.g., 'CAMERA_NOT_FOUND', 'VALIDATION_ERROR')",
        examples=["CAMERA_NOT_FOUND", "VALIDATION_ERROR", "RATE_LIMIT_EXCEEDED"],
    )
    message: str = Field(
        ...,
        description="Human-readable error description",
        examples=["Camera with id 'front_door' not found"],
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional context about the error",
        examples=[{"camera_id": "front_door", "resource_type": "camera"}],
    )
    request_id: str | None = Field(
        default=None,
        description="Unique request identifier for log correlation",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    timestamp: datetime | None = Field(
        default=None,
        description="When the error occurred (ISO 8601 format)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "CAMERA_NOT_FOUND",
                "message": "Camera with id 'front_door' not found",
                "details": {"camera_id": "front_door"},
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standard error response wrapper.

    All API error responses should use this format for consistency.

    Attributes:
        error: The error detail object
    """

    error: ErrorDetail = Field(
        ...,
        description="Error details",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "CAMERA_NOT_FOUND",
                    "message": "Camera with id 'front_door' not found",
                    "details": {"camera_id": "front_door"},
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                }
            }
        }
    }


class ValidationErrorDetail(BaseModel):
    """Detail for a single validation error.

    Used when multiple validation errors occur in a request.

    Attributes:
        field: The field that failed validation
        message: Description of the validation failure
        value: The invalid value (sanitized)
    """

    field: str = Field(
        ...,
        description="Field path that failed validation (e.g., 'body.email', 'query.limit')",
    )
    message: str = Field(
        ...,
        description="Description of the validation failure",
    )
    value: Any | None = Field(
        default=None,
        description="The invalid value (may be truncated for security)",
    )


class ValidationErrorResponse(BaseModel):
    """Error response for validation failures with multiple errors.

    This format is used when request validation fails with multiple issues.

    Attributes:
        error: The error detail object with validation-specific fields
    """

    class ValidationErrorInfo(BaseModel):
        """Validation-specific error information."""

        code: str = Field(default="VALIDATION_ERROR")
        message: str = Field(default="Request validation failed")
        errors: list[ValidationErrorDetail] = Field(
            ...,
            description="List of validation errors",
        )
        request_id: str | None = Field(default=None)

    error: ValidationErrorInfo

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "errors": [
                        {
                            "field": "body.start_date",
                            "message": "start_date must be before end_date",
                            "value": "2024-12-01",
                        },
                        {
                            "field": "body.limit",
                            "message": "ensure this value is less than or equal to 1000",
                            "value": 5000,
                        },
                    ],
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                }
            }
        }
    }


class RateLimitErrorResponse(BaseModel):
    """Error response for rate limit exceeded.

    Includes retry-after information for clients.

    Attributes:
        error: The error detail with rate limit information
    """

    class RateLimitErrorInfo(BaseModel):
        """Rate limit specific error information."""

        code: str = Field(default="RATE_LIMIT_EXCEEDED")
        message: str = Field(default="Rate limit exceeded")
        retry_after: int | None = Field(
            default=None,
            description="Seconds until rate limit resets",
        )
        limit: int | None = Field(
            default=None,
            description="The rate limit that was exceeded",
        )
        window_seconds: int | None = Field(
            default=None,
            description="The time window for the rate limit",
        )
        request_id: str | None = Field(default=None)

    error: RateLimitErrorInfo

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Rate limit exceeded. Please wait before retrying.",
                    "retry_after": 60,
                    "limit": 100,
                    "window_seconds": 60,
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                }
            }
        }
    }


class ServiceUnavailableResponse(BaseModel):
    """Error response for service unavailability.

    Used when external services (AI, database, cache) are unavailable.

    Attributes:
        error: The error detail with service information
    """

    class ServiceErrorInfo(BaseModel):
        """Service unavailability specific information."""

        code: str = Field(default="SERVICE_UNAVAILABLE")
        message: str = Field(default="Service temporarily unavailable")
        service: str | None = Field(
            default=None,
            description="Name of the unavailable service",
        )
        retry_after: int | None = Field(
            default=None,
            description="Suggested seconds to wait before retrying",
        )
        request_id: str | None = Field(default=None)

    error: ServiceErrorInfo

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "AI_SERVICE_UNAVAILABLE",
                    "message": "Object detection service temporarily unavailable",
                    "service": "rtdetr",
                    "retry_after": 30,
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                }
            }
        }
    }


# Common error responses for OpenAPI documentation
COMMON_ERROR_RESPONSES = {
    400: {
        "model": ValidationErrorResponse,
        "description": "Validation error - request data is invalid",
    },
    401: {
        "model": ErrorResponse,
        "description": "Authentication required",
    },
    403: {
        "model": ErrorResponse,
        "description": "Access denied",
    },
    404: {
        "model": ErrorResponse,
        "description": "Resource not found",
    },
    409: {
        "model": ErrorResponse,
        "description": "Conflict - resource already exists",
    },
    429: {
        "model": RateLimitErrorResponse,
        "description": "Rate limit exceeded",
    },
    500: {
        "model": ErrorResponse,
        "description": "Internal server error",
    },
    502: {
        "model": ServiceUnavailableResponse,
        "description": "Bad gateway - upstream service error",
    },
    503: {
        "model": ServiceUnavailableResponse,
        "description": "Service unavailable",
    },
}
