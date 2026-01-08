"""Global exception handlers for FastAPI application.

This module provides centralized exception handling that:
1. Converts all exceptions to standardized error responses
2. Logs errors appropriately (with request context)
3. Sanitizes error messages to prevent information leakage
4. Integrates with request tracing (request IDs)
5. Implements RFC 7807 Problem Details for HTTP API errors

RFC 7807 Support:
    HTTPException errors are returned in RFC 7807 "Problem Details" format
    with media type "application/problem+json". This provides a standardized,
    machine-readable format for error responses.

    Example RFC 7807 response:
        {
            "type": "about:blank",
            "title": "Not Found",
            "status": 404,
            "detail": "Camera 'front_door' does not exist",
            "instance": "/api/cameras/front_door"
        }

Usage:
    In main.py, register the handlers:

    from backend.api.exception_handlers import register_exception_handlers
    app = FastAPI()
    register_exception_handlers(app)
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.schemas.problem_details import ProblemDetail, get_status_phrase
from backend.core.exceptions import (
    CircuitBreakerOpenError,
    ExternalServiceError,
    RateLimitError,
    SecurityIntelligenceError,
)
from backend.core.logging import get_logger
from backend.core.sanitization import sanitize_error_for_response

logger = get_logger(__name__)


def get_request_id(request: Request) -> str | None:
    """Extract request ID from request state or headers.

    Args:
        request: The FastAPI request object

    Returns:
        Request ID if available, None otherwise
    """
    # Try to get from state (set by RequestIDMiddleware)
    if hasattr(request.state, "request_id"):
        request_id: str = request.state.request_id
        return request_id

    # Fallback to header
    return request.headers.get("X-Request-ID")


def build_error_response(
    error_code: str,
    message: str,
    status_code: int,
    request: Request | None = None,
    details: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build a standardized error response.

    Args:
        error_code: Machine-readable error code
        message: Human-readable error message
        status_code: HTTP status code
        request: Optional request for extracting request ID
        details: Optional additional error details
        headers: Optional custom headers to include in response (e.g., Retry-After, Content-Range)

    Returns:
        JSONResponse with standardized error format
    """
    error_body: dict[str, Any] = {
        "code": error_code,
        "message": message,
    }

    if details:
        error_body["details"] = details

    if request:
        request_id = get_request_id(request)
        if request_id:
            error_body["request_id"] = request_id

    error_body["timestamp"] = datetime.now(UTC).isoformat()

    return JSONResponse(
        status_code=status_code,
        content={"error": error_body},
        headers=headers,
    )


async def problem_details_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handle HTTPException using RFC 7807 Problem Details format.

    This handler converts standard HTTP exceptions to RFC 7807 "Problem Details"
    format, which provides a standardized, machine-readable error response format.

    RFC 7807 specifies these members:
    - type: A URI reference identifying the problem type (default: "about:blank")
    - title: A short, human-readable summary (uses HTTP status phrase)
    - status: The HTTP status code
    - detail: A human-readable explanation specific to this occurrence
    - instance: A URI reference identifying the specific occurrence (request path)

    The response uses media type "application/problem+json" per RFC 7807.

    Args:
        request: The FastAPI request
        exc: The HTTPException

    Returns:
        JSONResponse with RFC 7807 Problem Details format

    References:
        - RFC 7807: https://tools.ietf.org/html/rfc7807
    """
    # Get the standard HTTP status phrase for the title
    title = get_status_phrase(exc.status_code)

    # Determine the detail message
    # Fall back to status phrase if detail is None or empty
    detail = str(exc.detail) if exc.detail else title

    # Log appropriately based on status code
    log_context = {
        "status_code": exc.status_code,
        "path": str(request.url.path),
        "method": request.method,
    }

    request_id = get_request_id(request)
    if request_id:
        log_context["request_id"] = request_id

    if exc.status_code >= 500:
        logger.error(f"HTTP error: {detail}", extra=log_context)
    elif exc.status_code == 429:
        logger.warning(f"Rate limit: {detail}", extra=log_context)
    elif exc.status_code >= 400:
        logger.info(f"Client error: {detail}", extra=log_context)

    # Create RFC 7807 Problem Detail object
    # Sanitize the instance path to prevent XSS attacks
    # The path could contain user-supplied input (e.g., /api/cameras/<script>alert('XSS')</script>)
    sanitized_instance = html.escape(str(request.url.path))
    problem = ProblemDetail(
        type="about:blank",
        title=title,
        status=exc.status_code,
        detail=detail,
        instance=sanitized_instance,
    )

    # Build response with proper media type
    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
        headers=exc.headers,
    )


async def security_intelligence_exception_handler(
    request: Request,
    exc: SecurityIntelligenceError,
) -> JSONResponse:
    """Handle SecurityIntelligenceError and its subclasses.

    Converts application-specific exceptions to standardized error responses.

    Args:
        request: The FastAPI request
        exc: The exception that was raised

    Returns:
        Standardized JSON error response
    """
    # Log with appropriate level based on status code
    log_context = {
        "error_code": exc.error_code,
        "status_code": exc.status_code,
        "path": str(request.url.path),
        "method": request.method,
    }

    request_id = get_request_id(request)
    if request_id:
        log_context["request_id"] = request_id

    if exc.details:
        log_context["details"] = exc.details

    if exc.status_code >= 500:
        logger.error(f"Internal error: {exc.message}", extra=log_context, exc_info=True)
    elif exc.status_code == 429:
        logger.warning(f"Rate limit exceeded: {exc.message}", extra=log_context)
    elif exc.status_code >= 400:
        logger.info(f"Client error: {exc.message}", extra=log_context)
    else:
        logger.debug(f"Exception handled: {exc.message}", extra=log_context)

    return build_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        request=request,
        details=exc.details if exc.details else None,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handle standard HTTPException from FastAPI/Starlette.

    Converts HTTPException to standardized error format while preserving
    the original detail message.

    Args:
        request: The FastAPI request
        exc: The HTTPException

    Returns:
        Standardized JSON error response
    """
    # Map status codes to error codes
    status_to_code = {
        400: "BAD_REQUEST",
        401: "AUTHENTICATION_REQUIRED",
        403: "ACCESS_DENIED",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }

    error_code = status_to_code.get(exc.status_code, "ERROR")
    message = str(exc.detail) if exc.detail else "An error occurred"

    # Log appropriately
    log_context = {
        "status_code": exc.status_code,
        "path": str(request.url.path),
        "method": request.method,
    }

    request_id = get_request_id(request)
    if request_id:
        log_context["request_id"] = request_id

    if exc.status_code >= 500:
        logger.error(f"HTTP error: {message}", extra=log_context)
    elif exc.status_code == 429:
        logger.warning(f"Rate limit: {message}", extra=log_context)
    elif exc.status_code >= 400:
        logger.info(f"Client error: {message}", extra=log_context)

    return build_error_response(
        error_code=error_code,
        message=message,
        status_code=exc.status_code,
        request=request,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle Pydantic validation errors from request parsing.

    Converts validation errors to a structured format with field-level details.

    Args:
        request: The FastAPI request
        exc: The validation error

    Returns:
        Standardized JSON error response with validation details
    """
    errors = []
    for error in exc.errors():
        # Build field path (e.g., "body.name", "query.limit")
        loc = error.get("loc", ())
        field_parts = [str(part) for part in loc]
        field = ".".join(field_parts) if field_parts else "unknown"

        # Get message and sanitize
        msg = error.get("msg", "Validation error")

        # Get the invalid value (truncate for security)
        input_value = error.get("input")
        value = None
        if input_value is not None:
            str_value = str(input_value)
            value = str_value[:100] if len(str_value) > 100 else str_value

        errors.append(
            {
                "field": field,
                "message": msg,
                "value": value,
            }
        )

    # Log validation failure
    log_context = {
        "path": str(request.url.path),
        "method": request.method,
        "error_count": len(errors),
    }

    request_id = get_request_id(request)
    if request_id:
        log_context["request_id"] = request_id

    logger.info("Request validation failed", extra=log_context)

    response_body: dict[str, Any] = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "errors": errors,
        }
    }

    if request_id:
        response_body["error"]["request_id"] = request_id

    response_body["error"]["timestamp"] = datetime.now(UTC).isoformat()

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response_body,
    )


async def pydantic_validation_handler(
    request: Request,
    exc: PydanticValidationError,
) -> JSONResponse:
    """Handle Pydantic validation errors that occur during response serialization.

    These errors typically indicate a bug in the application code.

    Args:
        request: The FastAPI request
        exc: The Pydantic validation error

    Returns:
        Standardized JSON error response
    """
    log_context = {
        "path": str(request.url.path),
        "method": request.method,
        "error_count": exc.error_count(),
    }

    request_id = get_request_id(request)
    if request_id:
        log_context["request_id"] = request_id

    # This is a server-side issue, log as error
    logger.error(
        "Response serialization failed (likely a bug)",
        extra=log_context,
        exc_info=True,
    )

    return build_error_response(
        error_code="INTERNAL_ERROR",
        message="An internal error occurred while processing the response",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request=request,
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle any unhandled exceptions.

    This is the catch-all handler that ensures all exceptions return
    a standardized error response and are properly logged.

    Args:
        request: The FastAPI request
        exc: The unhandled exception

    Returns:
        Standardized JSON error response
    """
    # Sanitize the error message to prevent information leakage
    safe_message = sanitize_error_for_response(exc)

    log_context = {
        "path": str(request.url.path),
        "method": request.method,
        "exception_type": type(exc).__name__,
    }

    request_id = get_request_id(request)
    if request_id:
        log_context["request_id"] = request_id

    # Log the full exception with traceback
    logger.error(
        f"Unhandled exception: {exc!s}",
        extra=log_context,
        exc_info=True,
    )

    return build_error_response(
        error_code="INTERNAL_ERROR",
        message=safe_message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request=request,
    )


async def circuit_breaker_exception_handler(
    request: Request,
    exc: CircuitBreakerOpenError,
) -> JSONResponse:
    """Handle circuit breaker open errors specifically.

    Provides appropriate retry-after hints and service information.

    Args:
        request: The FastAPI request
        exc: The circuit breaker error

    Returns:
        Service unavailable response with retry information
    """
    log_context = {
        "service": exc.service_name,
        "path": str(request.url.path),
        "method": request.method,
    }

    request_id = get_request_id(request)
    if request_id:
        log_context["request_id"] = request_id

    logger.warning(f"Circuit breaker open for {exc.service_name}", extra=log_context)

    details = exc.details.copy() if exc.details else {}
    details["service"] = exc.service_name

    response = build_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        request=request,
        details=details,
    )

    # Add Retry-After header if we have recovery timeout
    if exc.details and "recovery_timeout_seconds" in exc.details:
        response.headers["Retry-After"] = str(int(exc.details["recovery_timeout_seconds"]))

    return response


async def rate_limit_exception_handler(
    request: Request,
    exc: RateLimitError,
) -> JSONResponse:
    """Handle rate limit errors specifically.

    Provides appropriate retry-after headers.

    Args:
        request: The FastAPI request
        exc: The rate limit error

    Returns:
        Rate limit error response with retry information
    """
    log_context = {
        "path": str(request.url.path),
        "method": request.method,
    }

    request_id = get_request_id(request)
    if request_id:
        log_context["request_id"] = request_id

    if exc.details:
        log_context.update(exc.details)

    logger.warning("Rate limit exceeded", extra=log_context)

    response = build_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        request=request,
        details=exc.details,
    )

    # Add Retry-After header if available
    if exc.details and "retry_after" in exc.details:
        response.headers["Retry-After"] = str(exc.details["retry_after"])

    return response


async def external_service_exception_handler(
    request: Request,
    exc: ExternalServiceError,
) -> JSONResponse:
    """Handle external service errors specifically.

    Logs service failures for monitoring and provides appropriate response.

    Args:
        request: The FastAPI request
        exc: The external service error

    Returns:
        Service unavailable response
    """
    log_context = {
        "service": exc.service_name,
        "error_code": exc.error_code,
        "path": str(request.url.path),
        "method": request.method,
    }

    request_id = get_request_id(request)
    if request_id:
        log_context["request_id"] = request_id

    logger.error(
        f"External service error ({exc.service_name}): {exc.message}",
        extra=log_context,
        exc_info=True,
    )

    return build_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        request=request,
        details=exc.details,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI application.

    This function should be called after creating the FastAPI app to
    set up global exception handling.

    Args:
        app: The FastAPI application instance

    Example:
        app = FastAPI()
        register_exception_handlers(app)
    """
    # Register handlers in order of specificity (most specific first)
    # Note: type ignores needed due to Starlette's overly strict handler typing
    # that doesn't account for exception subclass handlers

    # Circuit breaker errors (specific external service error)
    app.add_exception_handler(
        CircuitBreakerOpenError,
        circuit_breaker_exception_handler,  # type: ignore[arg-type]
    )

    # Rate limit errors
    app.add_exception_handler(
        RateLimitError,
        rate_limit_exception_handler,  # type: ignore[arg-type]
    )

    # External service errors (includes AI services, database, cache)
    app.add_exception_handler(
        ExternalServiceError,
        external_service_exception_handler,  # type: ignore[arg-type]
    )

    # Application-specific errors (includes validation, not found, etc.)
    app.add_exception_handler(
        SecurityIntelligenceError,
        security_intelligence_exception_handler,  # type: ignore[arg-type]
    )

    # FastAPI request validation errors
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,  # type: ignore[arg-type]
    )

    # Pydantic validation errors (response serialization)
    app.add_exception_handler(
        PydanticValidationError,
        pydantic_validation_handler,  # type: ignore[arg-type]
    )

    # Standard HTTP exceptions - RFC 7807 Problem Details format
    app.add_exception_handler(
        StarletteHTTPException,
        problem_details_exception_handler,  # type: ignore[arg-type]
    )

    # Catch-all for any unhandled exceptions
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Exception handlers registered")
