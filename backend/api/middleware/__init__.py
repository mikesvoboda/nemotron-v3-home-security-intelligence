"""API middleware components."""

from .auth import AuthMiddleware, authenticate_websocket, validate_websocket_api_key
from .body_limit import BodySizeLimitMiddleware
from .content_type_validator import ContentTypeValidationMiddleware
from .correlation import get_correlation_headers, merge_headers_with_correlation
from .file_validator import (
    MAGIC_SIGNATURES,
    ValidatedUploadFile,
    detect_mime_type,
    validate_file_magic,
    validate_file_magic_sync,
    validate_upload_file,
)
from .rate_limit import (
    RateLimiter,
    RateLimitTier,
    check_websocket_rate_limit,
    get_client_ip,
    rate_limit_default,
    rate_limit_media,
    rate_limit_search,
)
from .request_id import (
    RequestIDMiddleware,
    get_correlation_id,
    set_correlation_id,
)
from .request_logging import (
    RequestLoggingMiddleware,
    format_request_log,
)
from .request_timing import RequestTimingMiddleware
from .security_headers import SecurityHeadersMiddleware

__all__ = [
    "MAGIC_SIGNATURES",
    "AuthMiddleware",
    "BodySizeLimitMiddleware",
    "ContentTypeValidationMiddleware",
    "RateLimitTier",
    "RateLimiter",
    "RequestIDMiddleware",
    "RequestLoggingMiddleware",
    "RequestTimingMiddleware",
    "SecurityHeadersMiddleware",
    "ValidatedUploadFile",
    "authenticate_websocket",
    "check_websocket_rate_limit",
    "detect_mime_type",
    "format_request_log",
    "get_client_ip",
    "get_correlation_headers",
    "get_correlation_id",
    "merge_headers_with_correlation",
    "rate_limit_default",
    "rate_limit_media",
    "rate_limit_search",
    "set_correlation_id",
    "validate_file_magic",
    "validate_file_magic_sync",
    "validate_upload_file",
    "validate_websocket_api_key",
]
