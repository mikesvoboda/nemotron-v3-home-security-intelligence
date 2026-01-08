"""Consolidated exception hierarchy for the Home Security Intelligence system.

This module provides a comprehensive exception hierarchy that:
1. Categorizes errors by domain (database, AI services, validation, etc.)
2. Supports automatic HTTP status code mapping
3. Enables structured error responses
4. Facilitates error tracking and monitoring
"""

from __future__ import annotations

from typing import Any


class SecurityIntelligenceError(Exception):
    """Base exception for all application-specific errors."""

    default_message: str = "An unexpected error occurred"
    default_error_code: str = "INTERNAL_ERROR"
    default_status_code: int = 500

    def __init__(
        self,
        message: str | None = None,
        *,
        error_code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.error_code = error_code or self.default_error_code
        self.status_code = status_code or self.default_status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.error_code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


# Validation Errors (400)
class ValidationError(SecurityIntelligenceError):
    default_message = "Validation failed"
    default_error_code = "VALIDATION_ERROR"
    default_status_code = 400


class InvalidInputError(ValidationError):
    default_message = "Invalid input provided"
    default_error_code = "INVALID_INPUT"

    def __init__(
        self,
        message: str | None = None,
        *,
        field: str | None = None,
        value: Any = None,
        constraint: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {}) or {}
        if field:
            details["field"] = field
        if value is not None:
            str_value = str(value)
            details["value"] = str_value[:100] if len(str_value) > 100 else str_value
        if constraint:
            details["constraint"] = constraint
        super().__init__(message, details=details, **kwargs)


class DateRangeValidationError(ValidationError):
    default_message = "Invalid date range: start_date must be before end_date"
    default_error_code = "INVALID_DATE_RANGE"

    def __init__(
        self,
        message: str | None = None,
        *,
        start_date: Any = None,
        end_date: Any = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {}) or {}
        if start_date is not None:
            details["start_date"] = str(start_date)
        if end_date is not None:
            details["end_date"] = str(end_date)
        super().__init__(message, details=details, **kwargs)


class BoundingBoxValidationError(ValidationError):
    default_message = "Invalid bounding box coordinates"
    default_error_code = "INVALID_BOUNDING_BOX"


# Auth Errors
class AuthenticationError(SecurityIntelligenceError):
    default_message = "Authentication required"
    default_error_code = "AUTHENTICATION_REQUIRED"
    default_status_code = 401


class AuthorizationError(SecurityIntelligenceError):
    default_message = "Access denied"
    default_error_code = "ACCESS_DENIED"
    default_status_code = 403


# Not Found Errors (404)
class NotFoundError(SecurityIntelligenceError):
    default_message = "Resource not found"
    default_error_code = "NOT_FOUND"
    default_status_code = 404


class ResourceNotFoundError(NotFoundError):
    def __init__(
        self,
        resource_type: str,
        resource_id: str | int,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        if message is None:
            message = f"{resource_type.title()} with id '{resource_id}' not found"
        details = kwargs.pop("details", {}) or {}
        details["resource_type"] = resource_type
        details["resource_id"] = str(resource_id)
        super().__init__(message, details=details, **kwargs)


class CameraNotFoundError(NotFoundError):
    default_error_code = "CAMERA_NOT_FOUND"

    def __init__(self, camera_id: str, message: str | None = None, **kwargs: Any) -> None:
        if message is None:
            message = f"Camera with id '{camera_id}' not found"
        details = kwargs.pop("details", {}) or {}
        details["camera_id"] = camera_id
        super().__init__(message, details=details, **kwargs)


class EventNotFoundError(NotFoundError):
    default_error_code = "EVENT_NOT_FOUND"

    def __init__(self, event_id: int, message: str | None = None, **kwargs: Any) -> None:
        if message is None:
            message = f"Event with id '{event_id}' not found"
        details = kwargs.pop("details", {}) or {}
        details["event_id"] = event_id
        super().__init__(message, details=details, **kwargs)


class DetectionNotFoundError(NotFoundError):
    default_error_code = "DETECTION_NOT_FOUND"

    def __init__(self, detection_id: int, message: str | None = None, **kwargs: Any) -> None:
        if message is None:
            message = f"Detection with id '{detection_id}' not found"
        details = kwargs.pop("details", {}) or {}
        details["detection_id"] = detection_id
        super().__init__(message, details=details, **kwargs)


class MediaNotFoundError(NotFoundError):
    default_error_code = "MEDIA_NOT_FOUND"

    def __init__(
        self,
        file_path: str,
        message: str | None = None,
        *,
        media_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        from pathlib import Path

        filename = Path(file_path).name if file_path else "unknown"
        if message is None:
            media_desc = f"{media_type} " if media_type else ""
            message = f"{media_desc.title()}file not found"
        details = kwargs.pop("details", {}) or {}
        details["filename"] = filename
        if media_type:
            details["media_type"] = media_type
        super().__init__(message, details=details, **kwargs)


# Conflict Errors (409)
class ConflictError(SecurityIntelligenceError):
    default_message = "Request conflicts with current state"
    default_error_code = "CONFLICT"
    default_status_code = 409


class DuplicateResourceError(ConflictError):
    default_error_code = "DUPLICATE_RESOURCE"

    def __init__(
        self,
        resource_type: str,
        *,
        field: str | None = None,
        value: str | None = None,
        existing_id: str | None = None,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        if message is None:
            if field and value:
                message = f"{resource_type.title()} with {field} '{value}' already exists"
            else:
                message = f"{resource_type.title()} already exists"
            if existing_id:
                message += f" (id: {existing_id})"
        details = kwargs.pop("details", {}) or {}
        details["resource_type"] = resource_type
        if field:
            details["field"] = field
        if value:
            details["value"] = value
        if existing_id:
            details["existing_id"] = existing_id
        super().__init__(message, details=details, **kwargs)


# Rate Limiting (429)
class RateLimitError(SecurityIntelligenceError):
    default_message = "Rate limit exceeded"
    default_error_code = "RATE_LIMIT_EXCEEDED"
    default_status_code = 429

    def __init__(
        self,
        message: str | None = None,
        *,
        retry_after: int | None = None,
        limit: int | None = None,
        window_seconds: int | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {}) or {}
        if retry_after is not None:
            details["retry_after"] = retry_after
        if limit is not None:
            details["limit"] = limit
        if window_seconds is not None:
            details["window_seconds"] = window_seconds
        super().__init__(message, details=details, **kwargs)


# External Service Errors (503)
class ExternalServiceError(SecurityIntelligenceError):
    default_message = "External service temporarily unavailable"
    default_error_code = "SERVICE_UNAVAILABLE"
    default_status_code = 503

    def __init__(
        self,
        message: str | None = None,
        *,
        service_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.service_name = service_name
        details = kwargs.pop("details", {}) or {}
        if service_name:
            details["service"] = service_name
        super().__init__(message, details=details, **kwargs)


class AIServiceError(ExternalServiceError):
    default_message = "AI service temporarily unavailable"
    default_error_code = "AI_SERVICE_UNAVAILABLE"


class DetectorUnavailableError(AIServiceError):
    """Raised when the RT-DETR object detection service is unavailable.

    This exception is raised when the detector service cannot be reached due to:
    - Connection errors (service down, network issues)
    - Timeout errors (service overloaded, slow response)
    - HTTP 5xx errors (server-side failures)

    This exception signals that the operation should be retried later,
    as the failure is transient and not due to invalid input.
    """

    default_message = "Object detection service temporarily unavailable"
    default_error_code = "DETECTOR_UNAVAILABLE"

    def __init__(
        self,
        message: str | None = None,
        *,
        original_error: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error description
            original_error: The underlying exception that caused this error
            **kwargs: Additional keyword arguments passed to parent
        """
        self.original_error = original_error
        super().__init__(message, service_name="rtdetr", **kwargs)


class AnalyzerUnavailableError(AIServiceError):
    """Raised when the Nemotron risk analysis service is unavailable.

    This exception is raised when the LLM analyzer cannot be reached due to:
    - Connection errors (service down, network issues)
    - Timeout errors (LLM inference taking too long)
    - HTTP 5xx errors (server-side failures)

    This exception signals that the operation should be retried later,
    as the failure is transient and not due to invalid input.
    """

    default_message = "Risk analysis service temporarily unavailable"
    default_error_code = "ANALYZER_UNAVAILABLE"

    def __init__(
        self,
        message: str | None = None,
        *,
        original_error: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error description
            original_error: The underlying exception that caused this error
            **kwargs: Additional keyword arguments passed to parent
        """
        self.original_error = original_error
        super().__init__(message, service_name="nemotron", **kwargs)


class EnrichmentUnavailableError(AIServiceError):
    """Raised when the enrichment service is unavailable.

    This exception is raised when the enrichment service cannot be reached due to:
    - Connection errors (service down, network issues)
    - Timeout errors (service overloaded, slow response)
    - HTTP 5xx errors (server-side failures)

    This exception signals that the operation should be retried later,
    as the failure is transient and not due to invalid input.
    """

    default_message = "Enrichment service temporarily unavailable"
    default_error_code = "ENRICHMENT_UNAVAILABLE"

    def __init__(
        self,
        message: str | None = None,
        *,
        original_error: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error description
            original_error: The underlying exception that caused this error
            **kwargs: Additional keyword arguments passed to parent
        """
        self.original_error = original_error
        super().__init__(message, service_name="enrichment", **kwargs)


class DatabaseError(ExternalServiceError):
    default_message = "Database temporarily unavailable"
    default_error_code = "DATABASE_ERROR"

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        super().__init__(message, service_name="postgresql", **kwargs)


class CacheError(ExternalServiceError):
    default_message = "Cache temporarily unavailable"
    default_error_code = "CACHE_ERROR"

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        super().__init__(message, service_name="redis", **kwargs)


class CircuitBreakerOpenError(ExternalServiceError):
    default_message = "Service temporarily unavailable due to repeated failures"
    default_error_code = "CIRCUIT_BREAKER_OPEN"

    def __init__(
        self,
        service_name: str,
        message: str | None = None,
        *,
        recovery_timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        if message is None:
            message = (
                f"Circuit breaker for '{service_name}' is open. Service is temporarily unavailable."
            )
        details = kwargs.pop("details", {}) or {}
        if recovery_timeout is not None:
            details["recovery_timeout_seconds"] = recovery_timeout
        super().__init__(message, service_name=service_name, details=details, **kwargs)


# Internal Errors (500)
class InternalError(SecurityIntelligenceError):
    default_message = "An internal error occurred"
    default_error_code = "INTERNAL_ERROR"
    default_status_code = 500


class ConfigurationError(InternalError):
    default_message = "Configuration error"
    default_error_code = "CONFIGURATION_ERROR"


class ProcessingError(InternalError):
    default_message = "Processing error occurred"
    default_error_code = "PROCESSING_ERROR"

    def __init__(
        self,
        message: str | None = None,
        *,
        operation: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {}) or {}
        if operation:
            details["operation"] = operation
        super().__init__(message, details=details, **kwargs)


# Resource Exhaustion (503)
class ResourceExhaustedError(SecurityIntelligenceError):
    """Raised when system resources are exhausted.

    This exception is raised when the system cannot process a request due to:
    - GPU memory exhaustion
    - CPU/memory limits reached
    - Connection pool exhaustion
    - Queue capacity exceeded

    This exception signals that the operation should be retried later
    after resources become available.
    """

    default_message = "Resource exhausted"
    default_error_code = "RESOURCE_EXHAUSTED"
    default_status_code = 503

    def __init__(
        self,
        message: str | None = None,
        *,
        resource_type: str | None = None,
        limit: str | None = None,
        current: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error description
            resource_type: Type of resource that was exhausted (e.g., "gpu_memory")
            limit: The resource limit that was reached
            current: Current resource usage
            **kwargs: Additional keyword arguments passed to parent
        """
        details = kwargs.pop("details", {}) or {}
        if resource_type:
            details["resource_type"] = resource_type
        if limit:
            details["limit"] = limit
        if current:
            details["current"] = current
        super().__init__(message, details=details, **kwargs)


# Utility functions
def get_exception_status_code(exc: Exception) -> int:
    if isinstance(exc, SecurityIntelligenceError):
        return exc.status_code
    return 500


def get_exception_error_code(exc: Exception) -> str:
    if isinstance(exc, SecurityIntelligenceError):
        return exc.error_code
    return "INTERNAL_ERROR"
