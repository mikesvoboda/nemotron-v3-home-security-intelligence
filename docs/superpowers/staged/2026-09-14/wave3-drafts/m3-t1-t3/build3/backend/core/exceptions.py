"""Consolidated exception hierarchy for the Home Security Intelligence system.

This module provides a comprehensive exception hierarchy that:
1. Categorizes errors by domain (database, AI services, validation, etc.)
2. Supports automatic HTTP status code mapping
3. Enables structured error responses
4. Facilitates error tracking and monitoring

NEM-1446: Adds ServiceRequestContext for operational debugging context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ServiceRequestContext:
    """Operational context for service unavailable exceptions.

    This dataclass captures debugging information about failed service requests,
    including timing, retry attempts, and circuit breaker state. It enables
    structured logging and easier debugging of transient service failures.

    Attributes:
        service_name: Name of the service (e.g., "yolo26", "nemotron", "enrichment")
        endpoint: API endpoint that was called (e.g., "/detect", "/completion")
        method: HTTP method used (e.g., "POST", "GET")
        duration_ms: Total duration of the request in milliseconds
        attempt_number: Current attempt number (1-indexed)
        max_attempts: Maximum number of retry attempts configured
        circuit_state: Current circuit breaker state (e.g., "closed", "open", "half_open")
    """

    service_name: str
    endpoint: str
    method: str
    duration_ms: float
    attempt_number: int
    max_attempts: int
    circuit_state: str | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for structured logging.

        Returns:
            Dictionary containing all context fields
        """
        return {
            "service_name": self.service_name,
            "endpoint": self.endpoint,
            "method": self.method,
            "duration_ms": self.duration_ms,
            "attempt_number": self.attempt_number,
            "max_attempts": self.max_attempts,
            "circuit_state": self.circuit_state,
        }


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


class InvalidImageSizeError(ValidationError):
    """Raised when image_size parameter is invalid.

    This exception is raised when image dimensions are invalid:
    - None value
    - Not a 2-tuple
    - Negative dimensions
    - Zero dimensions
    """

    default_message = "Invalid image size"
    default_error_code = "INVALID_IMAGE_SIZE"

    def __init__(
        self,
        message: str | None = None,
        *,
        image_size: tuple[int, int] | None = None,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.image_size = image_size
        self.reason = reason
        details = kwargs.pop("details", {}) or {}
        if image_size is not None:
            details["image_size"] = (
                list(image_size) if hasattr(image_size, "__iter__") else str(image_size)
            )  # type: ignore[arg-type]
        if reason is not None:
            details["reason"] = reason
        super().__init__(message, details=details, **kwargs)


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
    """Raised when the YOLO26 object detection service is unavailable.

    This exception is raised when the detector service cannot be reached due to:
    - Connection errors (service down, network issues)
    - Timeout errors (service overloaded, slow response)
    - HTTP 5xx errors (server-side failures)

    This exception signals that the operation should be retried later,
    as the failure is transient and not due to invalid input.

    NEM-1446: Supports ServiceRequestContext for operational debugging.
    """

    default_message = "Object detection service temporarily unavailable"
    default_error_code = "DETECTOR_UNAVAILABLE"

    def __init__(
        self,
        message: str | None = None,
        *,
        original_error: Exception | None = None,
        context: ServiceRequestContext | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error description
            original_error: The underlying exception that caused this error
            context: ServiceRequestContext with operational debugging info (NEM-1446)
            **kwargs: Additional keyword arguments passed to parent
        """
        self.original_error = original_error
        self.context = context
        super().__init__(message, service_name="yolo26", **kwargs)

    def to_log_dict(self) -> dict[str, Any]:
        """Convert to dictionary for structured logging.

        Returns:
            Dictionary containing exception details, context, and original error info
        """
        result: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
            "service_name": self.service_name,
            "status_code": self.status_code,
            "context": self.context.to_dict() if self.context else None,
            "original_error": None,
        }
        if self.original_error:
            result["original_error"] = {
                "type": type(self.original_error).__name__,
                "message": str(self.original_error),
            }
        return result


class AnalyzerUnavailableError(AIServiceError):
    """Raised when the Nemotron risk analysis service is unavailable.

    This exception is raised when the LLM analyzer cannot be reached due to:
    - Connection errors (service down, network issues)
    - Timeout errors (LLM inference taking too long)
    - HTTP 5xx errors (server-side failures)

    This exception signals that the operation should be retried later,
    as the failure is transient and not due to invalid input.

    NEM-1446: Supports ServiceRequestContext for operational debugging.
    """

    default_message = "Risk analysis service temporarily unavailable"
    default_error_code = "ANALYZER_UNAVAILABLE"

    def __init__(
        self,
        message: str | None = None,
        *,
        original_error: Exception | None = None,
        context: ServiceRequestContext | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error description
            original_error: The underlying exception that caused this error
            context: ServiceRequestContext with operational debugging info (NEM-1446)
            **kwargs: Additional keyword arguments passed to parent
        """
        self.original_error = original_error
        self.context = context
        super().__init__(message, service_name="nemotron", **kwargs)

    def to_log_dict(self) -> dict[str, Any]:
        """Convert to dictionary for structured logging.

        Returns:
            Dictionary containing exception details, context, and original error info
        """
        result: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
            "service_name": self.service_name,
            "status_code": self.status_code,
            "context": self.context.to_dict() if self.context else None,
            "original_error": None,
        }
        if self.original_error:
            result["original_error"] = {
                "type": type(self.original_error).__name__,
                "message": str(self.original_error),
            }
        return result


class EnrichmentUnavailableError(AIServiceError):
    """Raised when the enrichment service is unavailable.

    This exception is raised when the enrichment service cannot be reached due to:
    - Connection errors (service down, network issues)
    - Timeout errors (service overloaded, slow response)
    - HTTP 5xx errors (server-side failures)

    This exception signals that the operation should be retried later,
    as the failure is transient and not due to invalid input.

    NEM-1446: Supports ServiceRequestContext for operational debugging.
    """

    default_message = "Enrichment service temporarily unavailable"
    default_error_code = "ENRICHMENT_UNAVAILABLE"

    def __init__(
        self,
        message: str | None = None,
        *,
        original_error: Exception | None = None,
        context: ServiceRequestContext | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error description
            original_error: The underlying exception that caused this error
            context: ServiceRequestContext with operational debugging info (NEM-1446)
            **kwargs: Additional keyword arguments passed to parent
        """
        self.original_error = original_error
        self.context = context
        super().__init__(message, service_name="enrichment", **kwargs)

    def to_log_dict(self) -> dict[str, Any]:
        """Convert to dictionary for structured logging.

        Returns:
            Dictionary containing exception details, context, and original error info
        """
        result: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
            "service_name": self.service_name,
            "status_code": self.status_code,
            "context": self.context.to_dict() if self.context else None,
            "original_error": None,
        }
        if self.original_error:
            result["original_error"] = {
                "type": type(self.original_error).__name__,
                "message": str(self.original_error),
            }
        return result


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


class CacheUnavailableError(CacheError):
    """Raised when cache is required but Redis is unavailable.

    This exception is raised when:
    - Redis connection fails and degraded mode is not allowed
    - Critical cache operations fail without fallback

    For non-critical paths, use allow_degraded=True to get NullCache fallback.

    NEM-2538: Adds graceful degradation support for cache dependencies.
    """

    default_message = "Cache service unavailable and degraded mode not allowed"
    default_error_code = "CACHE_UNAVAILABLE"

    def __init__(
        self,
        message: str | None = None,
        *,
        original_error: Exception | None = None,
        allow_degraded: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error description
            original_error: The underlying exception that caused this error
            allow_degraded: Whether degraded mode was requested but failed anyway
            **kwargs: Additional keyword arguments passed to parent
        """
        self.original_error = original_error
        self.allow_degraded = allow_degraded
        details = kwargs.pop("details", {}) or {}
        details["allow_degraded"] = allow_degraded
        if original_error:
            details["original_error_type"] = type(original_error).__name__
        super().__init__(message, details=details, **kwargs)


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


# =============================================================================
# Consolidated Exceptions (NEM-1441)
# =============================================================================


# BoundingBox Validation Errors
class InvalidBoundingBoxError(BoundingBoxValidationError):
    """Raised when bounding box has invalid format or dimensions."""

    default_message = "Invalid bounding box format or dimensions"
    default_error_code = "INVALID_BOUNDING_BOX_FORMAT"

    def __init__(
        self,
        message: str | None = None,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        **kwargs: Any,
    ) -> None:
        self.bbox = bbox
        details = kwargs.pop("details", {}) or {}
        if bbox is not None:
            details["bbox"] = list(bbox)
        super().__init__(message, details=details, **kwargs)


class BoundingBoxOutOfBoundsError(BoundingBoxValidationError):
    """Raised when bounding box extends beyond image boundaries."""

    default_message = "Bounding box extends beyond image boundaries"
    default_error_code = "BOUNDING_BOX_OUT_OF_BOUNDS"

    def __init__(
        self,
        message: str | None = None,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        image_size: tuple[int, int] | None = None,
        **kwargs: Any,
    ) -> None:
        self.bbox = bbox
        self.image_size = image_size
        details = kwargs.pop("details", {}) or {}
        if bbox is not None:
            details["bbox"] = list(bbox)
        if image_size is not None:
            details["image_size"] = list(image_size)
        super().__init__(message, details=details, **kwargs)


# URL/Security Validation Errors
class URLValidationError(ValidationError):
    """Raised when URL validation fails."""

    default_message = "Invalid URL"
    default_error_code = "INVALID_URL"

    def __init__(
        self,
        message: str | None = None,
        *,
        url: str | None = None,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.url = url
        self.reason = reason
        details = kwargs.pop("details", {}) or {}
        if url is not None:
            # Truncate URL for safety
            details["url"] = url[:200] if len(url) > 200 else url
        if reason is not None:
            details["reason"] = reason
        super().__init__(message, details=details, **kwargs)


class SSRFValidationError(URLValidationError):
    """Raised when URL fails SSRF (Server-Side Request Forgery) validation."""

    default_message = "URL blocked due to security policy"
    default_error_code = "SSRF_BLOCKED"


# Additional AI Service Errors
class FlorenceUnavailableError(AIServiceError):
    """Raised when the Florence scene analysis service is unavailable."""

    default_message = "Florence scene analysis service temporarily unavailable"
    default_error_code = "FLORENCE_UNAVAILABLE"

    def __init__(
        self,
        message: str | None = None,
        *,
        original_error: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        self.original_error = original_error
        super().__init__(message, service_name="florence", **kwargs)


class CLIPUnavailableError(AIServiceError):
    """Raised when the CLIP embedding service is unavailable."""

    default_message = "CLIP embedding service temporarily unavailable"
    default_error_code = "CLIP_UNAVAILABLE"

    def __init__(
        self,
        message: str | None = None,
        *,
        original_error: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        self.original_error = original_error
        super().__init__(message, service_name="clip", **kwargs)


# TLS/Certificate Errors
class TLSError(ConfigurationError):
    """Base class for TLS-related errors."""

    default_message = "TLS error"
    default_error_code = "TLS_ERROR"


class TLSConfigurationError(TLSError):
    """Raised when TLS configuration is invalid."""

    default_message = "TLS configuration error"
    default_error_code = "TLS_CONFIGURATION_ERROR"


class CertificateNotFoundError(TLSError):
    """Raised when a required certificate file is not found."""

    default_message = "Certificate file not found"
    default_error_code = "CERTIFICATE_NOT_FOUND"

    def __init__(
        self,
        message: str | None = None,
        *,
        cert_path: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.cert_path = cert_path
        details = kwargs.pop("details", {}) or {}
        if cert_path is not None:
            details["cert_path"] = cert_path
        super().__init__(message, details=details, **kwargs)


class CertificateValidationError(TLSError):
    """Raised when certificate validation fails."""

    default_message = "Certificate validation failed"
    default_error_code = "CERTIFICATE_VALIDATION_ERROR"

    def __init__(
        self,
        message: str | None = None,
        *,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.reason = reason
        details = kwargs.pop("details", {}) or {}
        if reason is not None:
            details["reason"] = reason
        super().__init__(message, details=details, **kwargs)


# Scene Baseline Errors
class SceneBaselineError(ProcessingError):
    """Base class for scene baseline errors."""

    default_message = "Scene baseline error"
    default_error_code = "SCENE_BASELINE_ERROR"


class BaselineNotFoundError(SceneBaselineError):
    """Raised when a required scene baseline is not found."""

    default_message = "Scene baseline not found"
    default_error_code = "BASELINE_NOT_FOUND"

    def __init__(
        self,
        message: str | None = None,
        *,
        camera_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.camera_id = camera_id
        details = kwargs.pop("details", {}) or {}
        if camera_id is not None:
            details["camera_id"] = camera_id
        super().__init__(message, details=details, **kwargs)


class InvalidEmbeddingError(SceneBaselineError):
    """Raised when an embedding is invalid or corrupted."""

    default_message = "Invalid embedding data"
    default_error_code = "INVALID_EMBEDDING"

    def __init__(
        self,
        message: str | None = None,
        *,
        expected_dim: int | None = None,
        actual_dim: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.expected_dim = expected_dim
        self.actual_dim = actual_dim
        details = kwargs.pop("details", {}) or {}
        if expected_dim is not None:
            details["expected_dim"] = expected_dim
        if actual_dim is not None:
            details["actual_dim"] = actual_dim
        super().__init__(message, details=details, **kwargs)


# Media Processing Errors
class VideoProcessingError(ProcessingError):
    """Raised when video processing fails."""

    default_message = "Video processing error"
    default_error_code = "VIDEO_PROCESSING_ERROR"

    def __init__(
        self,
        message: str | None = None,
        *,
        video_path: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.video_path = video_path
        details = kwargs.pop("details", {}) or {}
        if video_path is not None:
            from pathlib import Path

            details["filename"] = Path(video_path).name
        super().__init__(message, details=details, **kwargs)


class ClipGenerationError(ProcessingError):
    """Raised when video clip generation fails."""

    default_message = "Clip generation error"
    default_error_code = "CLIP_GENERATION_ERROR"

    def __init__(
        self,
        message: str | None = None,
        *,
        event_id: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.event_id = event_id
        details = kwargs.pop("details", {}) or {}
        if event_id is not None:
            details["event_id"] = event_id
        super().__init__(message, details=details, **kwargs)


# Alert Errors
class AlertCreationError(ProcessingError):
    """Raised when alert creation fails."""

    default_message = "Alert creation error"
    default_error_code = "ALERT_CREATION_ERROR"

    def __init__(
        self,
        message: str | None = None,
        *,
        event_id: int | None = None,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.event_id = event_id
        self.reason = reason
        details = kwargs.pop("details", {}) or {}
        if event_id is not None:
            details["event_id"] = event_id
        if reason is not None:
            details["reason"] = reason
        super().__init__(message, details=details, **kwargs)


# LLM Response Errors
class LLMResponseParseError(ProcessingError):
    """Raised when LLM response parsing fails."""

    default_message = "Failed to parse LLM response"
    default_error_code = "LLM_RESPONSE_PARSE_ERROR"

    def __init__(
        self,
        message: str | None = None,
        *,
        raw_response: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.raw_response = raw_response
        details = kwargs.pop("details", {}) or {}
        if raw_response is not None:
            # Truncate raw response for safety
            truncated = raw_response[:500] if len(raw_response) > 500 else raw_response
            details["raw_response_preview"] = truncated
        super().__init__(message, details=details, **kwargs)


# Conflict Errors
class InvalidStateTransition(ConflictError):
    """Raised when an invalid job state transition is attempted.

    This exception is raised when trying to transition a job to an invalid state.
    For example, attempting to transition from "completed" to "running" is invalid
    because "completed" is a terminal state.
    """

    default_message = "Invalid job state transition"
    default_error_code = "INVALID_STATE_TRANSITION"

    def __init__(
        self,
        message: str | None = None,
        *,
        from_status: str | None = None,
        to_status: str | None = None,
        job_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable error description
            from_status: The current job status
            to_status: The target status that was rejected
            job_id: The job ID involved in the transition
            **kwargs: Additional keyword arguments passed to parent
        """
        if message is None and from_status and to_status:
            message = f"Cannot transition from '{from_status}' to '{to_status}'"
        self.from_status = from_status
        self.to_status = to_status
        self.job_id = job_id
        details = kwargs.pop("details", {}) or {}
        if from_status is not None:
            details["from_status"] = from_status
        if to_status is not None:
            details["to_status"] = to_status
        if job_id is not None:
            details["job_id"] = job_id
        super().__init__(message, details=details, **kwargs)


class PromptVersionConflictError(ConflictError):
    """Raised when prompt version conflicts with stored version."""

    default_message = "Prompt version conflict"
    default_error_code = "PROMPT_VERSION_CONFLICT"

    def __init__(
        self,
        message: str | None = None,
        *,
        expected_version: int | None = None,
        actual_version: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.expected_version = expected_version
        self.actual_version = actual_version
        details = kwargs.pop("details", {}) or {}
        if expected_version is not None:
            details["expected_version"] = expected_version
        if actual_version is not None:
            details["actual_version"] = actual_version
        super().__init__(message, details=details, **kwargs)


# =============================================================================
# Bounding Box Validation Helpers (NEM-2605)
# =============================================================================


def validate_bounding_box(
    bbox: tuple[float, float, float, float],
    image_size: tuple[int, int] | None = None,
    allow_negative: bool = False,
) -> None:
    """Validate a bounding box and optionally its relationship to image size.

    This function validates:
    1. Bounding box has positive area (x1 < x2 and y1 < y2)
    2. Optionally: coordinates are non-negative
    3. Optionally: image_size is valid (2-tuple with positive dimensions)
    4. Optionally: bbox is within image bounds

    Args:
        bbox: Bounding box as (x1, y1, x2, y2)
        image_size: Optional image dimensions as (width, height)
        allow_negative: If False, negative coordinates raise InvalidBoundingBoxError

    Raises:
        InvalidBoundingBoxError: If bbox has zero or negative area, or invalid coordinates
        InvalidImageSizeError: If image_size is provided but invalid

    Example:
        >>> validate_bounding_box((10, 20, 100, 200))  # Valid
        >>> validate_bounding_box((100, 200, 10, 20))  # Raises InvalidBoundingBoxError
        >>> validate_bounding_box((10, 20, 100, 200), image_size=(0, 100))  # Raises InvalidImageSizeError
    """
    x1, y1, x2, y2 = bbox

    # Check for zero-area or inverted boxes
    if x1 >= x2:
        raise InvalidBoundingBoxError(
            f"Bounding box has zero or negative width: x1={x1}, x2={x2}",
            bbox=bbox,
        )

    if y1 >= y2:
        raise InvalidBoundingBoxError(
            f"Bounding box has zero or negative height: y1={y1}, y2={y2}",
            bbox=bbox,
        )

    # Check for negative coordinates if not allowed
    if not allow_negative and (x1 < 0 or y1 < 0 or x2 < 0 or y2 < 0):
        raise InvalidBoundingBoxError(
            f"Bounding box has negative coordinates: ({x1}, {y1}, {x2}, {y2})",
            bbox=bbox,
        )

    # Validate image_size if provided
    if image_size is not None:
        validate_image_size(image_size)


def validate_image_size(image_size: tuple[int, int] | None) -> None:
    """Validate that image_size is a valid 2-tuple with positive dimensions.

    Args:
        image_size: Image dimensions as (width, height)

    Raises:
        InvalidImageSizeError: If image_size is None, not a 2-tuple,
            or has non-positive dimensions

    Example:
        >>> validate_image_size((640, 480))  # Valid
        >>> validate_image_size((0, 480))    # Raises InvalidImageSizeError
        >>> validate_image_size((-1, 480))   # Raises InvalidImageSizeError
        >>> validate_image_size(None)        # Raises InvalidImageSizeError
    """
    if image_size is None:
        raise InvalidImageSizeError(
            "Image size cannot be None",
            reason="image_size is required",
        )

    try:
        if len(image_size) != 2:
            raise InvalidImageSizeError(
                f"Image size must be a 2-tuple (width, height), got {len(image_size)} elements",
                image_size=image_size,  # type: ignore[arg-type]
                reason="must be 2-tuple",
            )
    except TypeError:
        # image_size is not iterable
        raise InvalidImageSizeError(
            f"Image size must be a 2-tuple, got {type(image_size).__name__}",
            reason="not iterable",
        ) from None

    width, height = image_size

    if width <= 0:
        raise InvalidImageSizeError(
            f"Image width must be positive, got {width}",
            image_size=image_size,
            reason="non-positive width",
        )

    if height <= 0:
        raise InvalidImageSizeError(
            f"Image height must be positive, got {height}",
            image_size=image_size,
            reason="non-positive height",
        )


# Utility functions
def get_exception_status_code(exc: Exception) -> int:
    if isinstance(exc, SecurityIntelligenceError):
        return exc.status_code
    return 500


def get_exception_error_code(exc: Exception) -> str:
    if isinstance(exc, SecurityIntelligenceError):
        return exc.error_code
    return "INTERNAL_ERROR"
