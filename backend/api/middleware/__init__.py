"""API middleware components."""

from .accept_header import (
    SUPPORTED_MEDIA_TYPES,
    AcceptHeaderMiddleware,
    parse_accept_header,
    select_best_media_type,
)
from .auth import AuthMiddleware, authenticate_websocket, validate_websocket_api_key
from .body_limit import BodySizeLimitMiddleware
from .content_type_validator import ContentTypeValidationMiddleware
from .correlation import get_correlation_headers, merge_headers_with_correlation
from .deprecation_logger import (
    DEPRECATED_CALLS_TOTAL,
    DeprecationLoggerMiddleware,
    record_deprecated_call,
)
from .exception_handler import create_safe_error_message
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
from .request_recorder import (
    RequestRecorderMiddleware,
    RequestRecording,
    load_recording,
    redact_request_body,
)
from .request_timing import RequestTimingMiddleware
from .security_headers import SecurityHeadersMiddleware
from .websocket_auth import validate_websocket_token

__all__ = [
    "DEPRECATED_CALLS_TOTAL",
    "MAGIC_SIGNATURES",
    "SUPPORTED_MEDIA_TYPES",
    "AcceptHeaderMiddleware",
    "AuthMiddleware",
    "BodySizeLimitMiddleware",
    "ContentTypeValidationMiddleware",
    "DeprecationLoggerMiddleware",
    "RateLimitTier",
    "RateLimiter",
    "RequestIDMiddleware",
    "RequestLoggingMiddleware",
    "RequestRecorderMiddleware",
    "RequestRecording",
    "RequestTimingMiddleware",
    "SecurityHeadersMiddleware",
    "ValidatedUploadFile",
    "authenticate_websocket",
    "check_websocket_rate_limit",
    "create_safe_error_message",
    "detect_mime_type",
    "format_http_date",
    "format_request_log",
    "format_unix_timestamp",
    "get_client_ip",
    "get_correlation_headers",
    "get_correlation_id",
    "load_recording",
    "merge_headers_with_correlation",
    "parse_accept_header",
    "rate_limit_default",
    "rate_limit_media",
    "rate_limit_search",
    "record_deprecated_call",
    "redact_request_body",
    "select_best_media_type",
    "set_correlation_id",
    "validate_file_magic",
    "validate_file_magic_sync",
    "validate_upload_file",
    "validate_websocket_api_key",
    "validate_websocket_token",
]
