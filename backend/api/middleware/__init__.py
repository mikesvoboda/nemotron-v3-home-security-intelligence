"""API middleware components."""

from .auth import AuthMiddleware, authenticate_websocket, validate_websocket_api_key
from .baggage import (
    VALID_PRIORITIES,
    VALID_REQUEST_SOURCES,
    BaggageMiddleware,
    get_batch_id_from_baggage,
    get_camera_id_from_baggage,
    get_event_priority_from_baggage,
    get_request_source_from_baggage,
    set_pipeline_baggage,
)
from .body_limit import BodySizeLimitMiddleware
from .content_type_validator import ContentTypeValidationMiddleware
from .correlation import get_correlation_headers, merge_headers_with_correlation
from .idempotency import (
    IdempotencyMiddleware,
    compute_request_fingerprint,
)
from .observability import ObservabilityMiddleware
from .profiling import ProfilingMiddleware
from .prometheus import (
    EXCLUDED_PATHS,
    HTTP_REQUEST_DURATION_BUCKETS,
    PrometheusMiddleware,
    http_request_duration_seconds,
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
from .request_recorder import (
    RequestRecorderMiddleware,
    RequestRecording,
    load_recording,
    redact_request_body,
)
from .security_headers import SecurityHeadersMiddleware
from .setup_guard import (
    SETUP_WHITELIST_EXACT,
    SETUP_WHITELIST_PREFIXES,
    SetupGuardMiddleware,
    reset_setup_guard_state,
)
from .websocket_auth import validate_websocket_token

__all__ = [
    "EXCLUDED_PATHS",
    "HTTP_REQUEST_DURATION_BUCKETS",
    "SETUP_WHITELIST_EXACT",
    "SETUP_WHITELIST_PREFIXES",
    "VALID_PRIORITIES",
    "VALID_REQUEST_SOURCES",
    "AuthMiddleware",
    "BaggageMiddleware",
    "BodySizeLimitMiddleware",
    "ContentTypeValidationMiddleware",
    "IdempotencyMiddleware",
    "ObservabilityMiddleware",
    "ProfilingMiddleware",
    "PrometheusMiddleware",
    "RateLimitTier",
    "RateLimiter",
    "RequestIDMiddleware",
    "RequestRecorderMiddleware",
    "RequestRecording",
    "SecurityHeadersMiddleware",
    "SetupGuardMiddleware",
    "authenticate_websocket",
    "check_websocket_rate_limit",
    "compute_request_fingerprint",
    "get_batch_id_from_baggage",
    "get_camera_id_from_baggage",
    "get_client_ip",
    "get_correlation_headers",
    "get_correlation_id",
    "get_event_priority_from_baggage",
    "get_request_source_from_baggage",
    "http_request_duration_seconds",
    "load_recording",
    "merge_headers_with_correlation",
    "rate_limit_default",
    "rate_limit_media",
    "rate_limit_search",
    "redact_request_body",
    "reset_setup_guard_state",
    "set_correlation_id",
    "set_pipeline_baggage",
    "validate_websocket_api_key",
    "validate_websocket_token",
]
