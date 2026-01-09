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
    from fastapi import status
    from backend.api.schemas.errors import ErrorCode, raise_http_error

    @router.get("/{id}")
    async def get_item(id: int) -> Item:
        if not item:
            raise_http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code=ErrorCode.ITEM_NOT_FOUND,
                message=f"Item with id {id} not found",
                details={"item_id": id},
            )
        return item
"""

from datetime import datetime
from typing import Any, NoReturn

from fastapi import HTTPException
from pydantic import BaseModel, Field


class ErrorCode:
    """Machine-readable error codes for consistent API error handling.

    These codes are designed to be used by clients for programmatic error handling.
    They follow the pattern: RESOURCE_ACTION or CATEGORY_DESCRIPTION.

    Usage:
        from fastapi import status
        from backend.api.schemas.errors import ErrorCode, raise_http_error

        raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.CAMERA_NOT_FOUND,
            message="Camera 'front_door' not found",
        )
    """

    # Resource not found errors (404)
    CAMERA_NOT_FOUND = "CAMERA_NOT_FOUND"
    EVENT_NOT_FOUND = "EVENT_NOT_FOUND"
    DETECTION_NOT_FOUND = "DETECTION_NOT_FOUND"
    ZONE_NOT_FOUND = "ZONE_NOT_FOUND"
    ALERT_NOT_FOUND = "ALERT_NOT_FOUND"
    ALERT_RULE_NOT_FOUND = "ALERT_RULE_NOT_FOUND"
    SCENE_CHANGE_NOT_FOUND = "SCENE_CHANGE_NOT_FOUND"
    LOG_NOT_FOUND = "LOG_NOT_FOUND"
    AUDIT_LOG_NOT_FOUND = "AUDIT_LOG_NOT_FOUND"
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    CLIP_NOT_FOUND = "CLIP_NOT_FOUND"
    PROMPT_NOT_FOUND = "PROMPT_NOT_FOUND"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"  # Generic fallback

    # Validation errors (400, 422)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    INVALID_PAGINATION = "INVALID_PAGINATION"
    INVALID_FILTER = "INVALID_FILTER"
    INVALID_REQUEST_BODY = "INVALID_REQUEST_BODY"
    INVALID_QUERY_PARAMETER = "INVALID_QUERY_PARAMETER"
    INVALID_PATH_PARAMETER = "INVALID_PATH_PARAMETER"
    INVALID_CAMERA_ID = "INVALID_CAMERA_ID"
    INVALID_COORDINATES = "INVALID_COORDINATES"
    INVALID_CONFIDENCE_THRESHOLD = "INVALID_CONFIDENCE_THRESHOLD"

    # Conflict errors (409)
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    CAMERA_ALREADY_EXISTS = "CAMERA_ALREADY_EXISTS"
    ZONE_ALREADY_EXISTS = "ZONE_ALREADY_EXISTS"
    ALERT_RULE_ALREADY_EXISTS = "ALERT_RULE_ALREADY_EXISTS"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"

    # Authentication/Authorization errors (401, 403)
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_API_KEY = "INVALID_API_KEY"  # pragma: allowlist secret
    EXPIRED_TOKEN = "EXPIRED_TOKEN"  # noqa: S105  # pragma: allowlist secret
    ACCESS_DENIED = "ACCESS_DENIED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"

    # Rate limiting errors (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"

    # Service/Infrastructure errors (500, 502, 503)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    CACHE_ERROR = "CACHE_ERROR"
    QUEUE_ERROR = "QUEUE_ERROR"

    # AI/ML Service errors (502, 503)
    DETECTOR_UNAVAILABLE = "DETECTOR_UNAVAILABLE"
    RTDETR_UNAVAILABLE = "RTDETR_UNAVAILABLE"
    NEMOTRON_UNAVAILABLE = "NEMOTRON_UNAVAILABLE"
    FLORENCE_UNAVAILABLE = "FLORENCE_UNAVAILABLE"
    ENRICHMENT_SERVICE_UNAVAILABLE = "ENRICHMENT_SERVICE_UNAVAILABLE"
    AI_SERVICE_TIMEOUT = "AI_SERVICE_TIMEOUT"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    INFERENCE_FAILED = "INFERENCE_FAILED"

    # File/Media errors
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_ACCESS_DENIED = "FILE_ACCESS_DENIED"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    MEDIA_PROCESSING_FAILED = "MEDIA_PROCESSING_FAILED"
    THUMBNAIL_GENERATION_FAILED = "THUMBNAIL_GENERATION_FAILED"
    CLIP_GENERATION_FAILED = "CLIP_GENERATION_FAILED"

    # WebSocket errors
    WEBSOCKET_CONNECTION_FAILED = "WEBSOCKET_CONNECTION_FAILED"
    INVALID_WEBSOCKET_MESSAGE = "INVALID_WEBSOCKET_MESSAGE"
    SUBSCRIPTION_FAILED = "SUBSCRIPTION_FAILED"

    # Configuration errors
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    CONFIGURATION_UPDATE_FAILED = "CONFIGURATION_UPDATE_FAILED"

    # Operation errors
    OPERATION_FAILED = "OPERATION_FAILED"
    OPERATION_TIMEOUT = "OPERATION_TIMEOUT"
    OPERATION_CANCELLED = "OPERATION_CANCELLED"


def raise_http_error(
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> NoReturn:
    """Raise an HTTPException with a standardized error response format.

    This helper function ensures consistent error responses across all API endpoints.
    It constructs an ErrorResponse-compatible detail payload and raises HTTPException.

    Args:
        status_code: HTTP status code (e.g., 400, 404, 500)
        error_code: Machine-readable error code from ErrorCode class
        message: Human-readable error description
        details: Optional dict with additional context about the error
        request_id: Optional request correlation ID for debugging

    Raises:
        HTTPException: Always raises with the provided status code and error details

    Example:
        from fastapi import status
        from backend.api.schemas.errors import ErrorCode, raise_http_error

        # Simple 404 error
        raise_http_error(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=ErrorCode.CAMERA_NOT_FOUND,
            message="Camera 'front_door' not found in database",
        )

        # Error with details and request_id
        raise_http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=ErrorCode.INVALID_DATE_RANGE,
            message="Start date must be before end date",
            details={"start_date": "2024-01-15", "end_date": "2024-01-10"},
            request_id="req-123-456",
        )
    """
    error_response: dict[str, Any] = {
        "error_code": error_code,
        "message": message,
    }
    if details is not None:
        error_response["details"] = details
    if request_id is not None:
        error_response["request_id"] = request_id

    raise HTTPException(status_code=status_code, detail=error_response)


class FlatErrorResponse(BaseModel):
    """Flat error response schema for use with raise_http_error helper.

    This schema matches the flat format produced by raise_http_error() and is
    suitable for OpenAPI documentation of endpoints using standardized errors.

    Note: This differs from ErrorResponse which uses a nested {"error": {...}} format.
    Use FlatErrorResponse when documenting endpoints that use raise_http_error().

    Attributes:
        error_code: Machine-readable error code from ErrorCode class
        message: Human-readable error description
        details: Optional dict with additional context
        request_id: Optional correlation ID for debugging

    Example JSON response:
        {
            "error_code": "CAMERA_NOT_FOUND",
            "message": "Camera 'front_door' not found in database",
            "details": {"camera_id": "front_door"},
            "request_id": "req-123-456"
        }
    """

    error_code: str = Field(
        ...,
        description="Machine-readable error code (e.g., 'CAMERA_NOT_FOUND')",
        examples=["CAMERA_NOT_FOUND", "VALIDATION_ERROR", "DETECTOR_UNAVAILABLE"],
    )
    message: str = Field(
        ...,
        description="Human-readable error description",
        examples=["Camera 'front_door' not found in database"],
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional context about the error",
        examples=[{"camera_id": "front_door"}],
    )
    request_id: str | None = Field(
        default=None,
        description="Correlation ID for debugging and log tracing",
        examples=["req-123-456"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "error_code": "CAMERA_NOT_FOUND",
                "message": "Camera 'front_door' not found in database",
                "details": {"camera_id": "front_door"},
                "request_id": "req-123-456",
            }
        }
    }


class ErrorDetail(BaseModel):
    """Detailed error information (legacy nested format).

    This is the inner error object used with the nested ErrorResponse format.
    For new endpoints, prefer using FlatErrorResponse with raise_http_error().

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
    """Standard error response wrapper (legacy nested format).

    This format uses a nested {"error": {...}} structure for backward compatibility.
    For new endpoints using raise_http_error(), prefer FlatErrorResponse for OpenAPI docs.

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
