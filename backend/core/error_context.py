"""Structured error context for enhanced logging and debugging.

This module provides utilities for capturing rich context around errors,
enabling better debugging, monitoring, and incident response.

Features:
- ErrorContext dataclass for structured error information
- Exception chain capture for root cause analysis
- Request context extraction
- Service context for external service errors
- Fluent builder API for constructing contexts
- log_error and log_with_context helpers

Usage:
    from backend.core.error_context import ErrorContext, log_error, log_with_context

    # Log an error with full context
    try:
        await risky_operation()
    except DatabaseError as e:
        log_error(e, operation="sync_data", request_id=request_id)

    # Use structured logging helper
    log_with_context("info", "Processing started", camera_id="front_door", event_id=123)

    # Build context programmatically
    ctx = (
        ErrorContextBuilder()
        .from_exception(exc)
        .with_operation("detect_objects")
        .with_request(request_id, path, method)
        .build()
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.core.exceptions import (
    ExternalServiceError,
    SecurityIntelligenceError,
    get_exception_error_code,
    get_exception_status_code,
)
from backend.core.logging import get_logger, redact_sensitive_value

logger = get_logger(__name__)

# Fields that should be redacted when logging
SENSITIVE_FIELDS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "api-key",
        "authorization",
        "auth",
        "credential",
        "private_key",
        "access_token",
        "refresh_token",
    }
)


def _is_sensitive_field(field_name: str) -> bool:
    """Check if a field name indicates sensitive data."""
    field_lower = field_name.lower()
    return field_lower in SENSITIVE_FIELDS or any(
        pattern in field_lower for pattern in ("password", "secret", "key", "token", "credential")
    )


def _sanitize_extra(extra: dict[str, Any]) -> dict[str, Any]:
    """Sanitize extra fields, redacting sensitive values."""
    return {
        key: (redact_sensitive_value(key, value) if _is_sensitive_field(key) else value)
        for key, value in extra.items()
    }


@dataclass
class ErrorContext:
    """Structured context for error logging and debugging.

    Captures comprehensive information about an error including:
    - Error type and code
    - Message and status code
    - Service information (for external services)
    - Request context (ID, path, method)
    - Exception chain information
    - Additional arbitrary context

    Attributes:
        error_type: Exception class name
        error_code: Machine-readable error code
        message: Human-readable error message
        status_code: HTTP status code (default 500)
        service_name: Name of external service (if applicable)
        operation: Operation being performed when error occurred
        request_id: Request ID for correlation
        path: Request path
        method: HTTP method
        cause_type: Type of the causing exception (if chained)
        cause_message: Message from the causing exception
        extra: Additional context fields
        timestamp: When the error occurred
    """

    error_type: str
    error_code: str
    message: str
    status_code: int = 500
    service_name: str | None = None
    operation: str | None = None
    request_id: str | None = None
    path: str | None = None
    method: str | None = None
    cause_type: str | None = None
    cause_message: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_exception(
        cls,
        exc: BaseException,
        *,
        include_chain: bool = False,
        operation: str | None = None,
        request_id: str | None = None,
        path: str | None = None,
        method: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ErrorContext:
        """Create ErrorContext from an exception.

        Args:
            exc: The exception to capture context from
            include_chain: Whether to include cause exception info
            operation: Operation being performed
            request_id: Request ID for correlation
            path: Request path
            method: HTTP method
            extra: Additional context fields

        Returns:
            ErrorContext populated from the exception
        """
        error_type = type(exc).__name__
        # The utility functions expect Exception but work with BaseException
        # Cast to Exception for type checker satisfaction
        if isinstance(exc, Exception):
            error_code = get_exception_error_code(exc)
            status_code = get_exception_status_code(exc)
        else:
            error_code = "INTERNAL_ERROR"
            status_code = 500
        message = str(exc)

        # Extract service name if it's an ExternalServiceError
        service_name = None
        if isinstance(exc, ExternalServiceError):
            service_name = exc.service_name

        # Extract exception chain if requested
        cause_type = None
        cause_message = None
        if include_chain and exc.__cause__ is not None:
            cause_type = type(exc.__cause__).__name__
            cause_message = str(exc.__cause__)

        # Merge any details from SecurityIntelligenceError
        merged_extra = dict(extra or {})
        if isinstance(exc, SecurityIntelligenceError) and exc.details:
            merged_extra.update(exc.details)

        return cls(
            error_type=error_type,
            error_code=error_code,
            message=message,
            status_code=status_code,
            service_name=service_name,
            operation=operation,
            request_id=request_id,
            path=path,
            method=method,
            cause_type=cause_type,
            cause_message=cause_message,
            extra=merged_extra,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize ErrorContext to a dictionary.

        Returns:
            Dictionary with all non-None fields
        """
        result: dict[str, Any] = {
            "error_type": self.error_type,
            "error_code": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "timestamp": self.timestamp.isoformat(),
        }

        # Add optional fields if present
        if self.service_name:
            result["service_name"] = self.service_name
        if self.operation:
            result["operation"] = self.operation
        if self.request_id:
            result["request_id"] = self.request_id
        if self.path:
            result["path"] = self.path
        if self.method:
            result["method"] = self.method
        if self.cause_type:
            result["cause_type"] = self.cause_type
        if self.cause_message:
            result["cause_message"] = self.cause_message
        if self.extra:
            result["extra"] = _sanitize_extra(self.extra)

        return result


class ErrorContextBuilder:
    """Fluent builder for ErrorContext.

    Provides a chainable API for constructing ErrorContext objects.

    Example:
        ctx = (
            ErrorContextBuilder()
            .with_error("DatabaseError", "DATABASE_ERROR", "Connection failed")
            .with_status(503)
            .with_service("postgresql")
            .with_operation("execute_query")
            .build()
        )
    """

    def __init__(self) -> None:
        """Initialize the builder with default values."""
        self._error_type: str = "UnknownError"
        self._error_code: str = "INTERNAL_ERROR"
        self._message: str = "An error occurred"
        self._status_code: int = 500
        self._service_name: str | None = None
        self._operation: str | None = None
        self._request_id: str | None = None
        self._path: str | None = None
        self._method: str | None = None
        self._cause_type: str | None = None
        self._cause_message: str | None = None
        self._extra: dict[str, Any] = {}

    def with_error(self, error_type: str, error_code: str, message: str) -> ErrorContextBuilder:
        """Set the error type, code, and message.

        Args:
            error_type: Exception class name
            error_code: Machine-readable error code
            message: Human-readable message

        Returns:
            Self for chaining
        """
        self._error_type = error_type
        self._error_code = error_code
        self._message = message
        return self

    def with_status(self, status_code: int) -> ErrorContextBuilder:
        """Set the HTTP status code.

        Args:
            status_code: HTTP status code

        Returns:
            Self for chaining
        """
        self._status_code = status_code
        return self

    def with_service(self, service_name: str) -> ErrorContextBuilder:
        """Set the service name.

        Args:
            service_name: External service name

        Returns:
            Self for chaining
        """
        self._service_name = service_name
        return self

    def with_operation(self, operation: str) -> ErrorContextBuilder:
        """Set the operation name.

        Args:
            operation: Operation being performed

        Returns:
            Self for chaining
        """
        self._operation = operation
        return self

    def with_request(
        self,
        request_id: str | None = None,
        path: str | None = None,
        method: str | None = None,
    ) -> ErrorContextBuilder:
        """Set request context.

        Args:
            request_id: Request ID for correlation
            path: Request path
            method: HTTP method

        Returns:
            Self for chaining
        """
        self._request_id = request_id
        self._path = path
        self._method = method
        return self

    def with_cause(self, cause: BaseException) -> ErrorContextBuilder:
        """Set the causing exception.

        Args:
            cause: The exception that caused this error

        Returns:
            Self for chaining
        """
        self._cause_type = type(cause).__name__
        self._cause_message = str(cause)
        return self

    def with_extra(self, **kwargs: Any) -> ErrorContextBuilder:
        """Add extra context fields.

        Args:
            **kwargs: Additional context fields

        Returns:
            Self for chaining
        """
        self._extra.update(kwargs)
        return self

    def from_exception(self, exc: BaseException) -> ErrorContextBuilder:
        """Populate from an exception.

        Args:
            exc: Exception to extract context from

        Returns:
            Self for chaining
        """
        self._error_type = type(exc).__name__
        # The utility functions expect Exception but work with BaseException
        if isinstance(exc, Exception):
            self._error_code = get_exception_error_code(exc)
            self._status_code = get_exception_status_code(exc)
        else:
            self._error_code = "INTERNAL_ERROR"
            self._status_code = 500
        self._message = str(exc)

        if isinstance(exc, ExternalServiceError):
            self._service_name = exc.service_name

        if isinstance(exc, SecurityIntelligenceError) and exc.details:
            self._extra.update(exc.details)

        if exc.__cause__ is not None:
            self._cause_type = type(exc.__cause__).__name__
            self._cause_message = str(exc.__cause__)

        return self

    def build(self) -> ErrorContext:
        """Build the ErrorContext.

        Returns:
            Constructed ErrorContext
        """
        return ErrorContext(
            error_type=self._error_type,
            error_code=self._error_code,
            message=self._message,
            status_code=self._status_code,
            service_name=self._service_name,
            operation=self._operation,
            request_id=self._request_id,
            path=self._path,
            method=self._method,
            cause_type=self._cause_type,
            cause_message=self._cause_message,
            extra=self._extra,
        )


def log_error(
    exc: BaseException,
    *,
    operation: str | None = None,
    request_id: str | None = None,
    path: str | None = None,
    method: str | None = None,
    include_traceback: bool = False,
    **extra: Any,
) -> None:
    """Log an error with structured context.

    Uses appropriate log level based on error severity:
    - 5xx errors: ERROR level
    - 4xx errors: WARNING level

    Args:
        exc: The exception to log
        operation: Operation being performed
        request_id: Request ID for correlation
        path: Request path
        method: HTTP method
        include_traceback: Whether to include traceback (for 5xx errors)
        **extra: Additional context fields
    """
    ctx = ErrorContext.from_exception(
        exc,
        include_chain=True,
        operation=operation,
        request_id=request_id,
        path=path,
        method=method,
        extra=extra,
    )

    log_extra = ctx.to_dict()

    message = f"[{ctx.error_code}] {ctx.message}"

    # Choose log level based on status code
    if ctx.status_code >= 500:
        logger.error(message, extra=log_extra, exc_info=include_traceback)
    elif ctx.status_code >= 400:
        logger.warning(message, extra=log_extra)
    else:
        logger.info(message, extra=log_extra)


def log_with_context(
    level: str,
    message: str,
    **context: Any,
) -> None:
    """Log a message with structured context.

    Automatically sanitizes sensitive fields in the context.

    Args:
        level: Log level ("debug", "info", "warning", "error")
        message: Log message
        **context: Context fields to include
    """
    # Sanitize sensitive fields
    sanitized = _sanitize_extra(context)

    # Get the appropriate logging method
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, extra=sanitized)
