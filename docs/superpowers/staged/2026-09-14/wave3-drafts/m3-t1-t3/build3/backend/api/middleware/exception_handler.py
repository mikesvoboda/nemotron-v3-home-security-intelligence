"""Exception handling utilities for API response data minimization.

This module provides centralized error handling with data minimization to prevent
sensitive information leakage in API responses. It works in conjunction with
the global exception handlers registered in backend/api/exception_handlers.py.

Architecture Note:
    FastAPI exception handlers (registered via app.add_exception_handler) are
    the idiomatic way to handle exceptions in FastAPI/Starlette applications.
    This is preferred over ASGI middleware because:

    1. Exception handlers have access to the Request object and exception details
    2. They integrate properly with FastAPI's dependency injection
    3. They're registered per-exception-type for precise handling
    4. The response format is fully controllable

    The actual exception handling is implemented in backend/api/exception_handlers.py
    and registered in backend/main.py via register_exception_handlers(app).

Security Features (NEM-1649):
    - File path sanitization (removes directory structure, keeps filename only)
    - URL credential redaction (user:password@host patterns)
    - IP address redaction
    - API key and token redaction
    - Password value redaction (in JSON and key=value formats)
    - Bearer token redaction
    - Error message truncation (prevents extremely long messages)
    - Windows and Unix path handling

Usage:
    The sanitization is automatically applied to all unhandled exceptions via
    the generic_exception_handler in exception_handlers.py. For explicit
    sanitization in custom error handling, use:

        from backend.core.sanitization import sanitize_error_for_response

        try:
            # operation that might fail
        except SomeException as e:
            safe_message = sanitize_error_for_response(e, context="processing request")
            # return sanitized message to client

Related:
    - backend/api/exception_handlers.py - Global exception handlers
    - backend/core/sanitization.py - Sanitization utilities
    - backend/tests/unit/api/middleware/test_exception_handler.py - Tests

Linear Issue: NEM-1649
"""

from __future__ import annotations

from backend.core.sanitization import sanitize_error_for_response

__all__ = [
    "create_safe_error_message",
    "sanitize_error_for_response",
]


def create_safe_error_message(
    error: Exception,
    *,
    context: str = "",
    include_exception_type: bool = False,
) -> str:
    """Create a safe error message for API responses.

    This function wraps sanitize_error_for_response with additional options
    for API response formatting.

    Args:
        error: The exception to sanitize
        context: Optional context string (e.g., "processing image")
        include_exception_type: If True, prefix message with exception type name

    Returns:
        A sanitized error message safe for inclusion in API responses

    Examples:
        >>> error = FileNotFoundError("/home/user/secret/config.yaml not found")
        >>> create_safe_error_message(error)
        'config.yaml not found'

        >>> create_safe_error_message(error, context="loading configuration")
        'Error loading configuration: config.yaml not found'

        >>> create_safe_error_message(error, include_exception_type=True)
        'FileNotFoundError: config.yaml not found'
    """
    safe_message = sanitize_error_for_response(error, context=context)

    if include_exception_type:
        exception_type = type(error).__name__
        if context:
            # Context already added by sanitize_error_for_response
            return safe_message
        return f"{exception_type}: {safe_message}"

    return safe_message
