# API Middleware

## Purpose

The `backend/api/middleware/` directory contains 23 HTTP middleware components that handle cross-cutting concerns for the FastAPI application. Middleware processes requests before they reach route handlers and responses before they are sent to clients.

## Files

### `__init__.py`

Package initialization with public exports:

- `AuthMiddleware` - the EXPOSE_LAN auth gate (OD-12): refuses unauthenticated HTTP and WebSocket requests when `EXPOSE_LAN=true`
- `authenticate_websocket` - WebSocket authentication helper
- `validate_websocket_api_key` - WebSocket API key validation
- `IdempotencyMiddleware` - Idempotency-Key header support for mutations (NEM-2018)
- `compute_request_fingerprint` - Fingerprint requests for collision detection
- `RateLimiter` - FastAPI dependency for rate limiting
- `RateLimitTier` - Rate limit tier enum (DEFAULT, MEDIA, WEBSOCKET, SEARCH)
- `check_websocket_rate_limit` - WebSocket connection rate limiting
- `get_client_ip` - Extract client IP from request
- `rate_limit_default`, `rate_limit_media`, `rate_limit_search` - Convenience dependencies
- `SecurityHeadersMiddleware` - Security headers middleware (CSP, X-Frame-Options, etc.)
- `RequestIDMiddleware` - Request ID generation and propagation middleware
- `ObservabilityMiddleware` - Unified timing + request logging + Prometheus metrics middleware (NEM-5558)
- `get_correlation_headers` - Get correlation headers for outgoing requests
- `merge_headers_with_correlation` - Merge headers with correlation IDs
- `get_correlation_id` - Get current correlation ID from context
- `set_correlation_id` - Set correlation ID in context

### `auth.py`

The EXPOSE_LAN auth gate, and the API-key check the WebSocket routes run.

**Classes:**

| Class            | Purpose                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------- |
| `AuthMiddleware` | Pure ASGI gate, outermost in `backend/main.py`; engaged only when `EXPOSE_LAN=true` (OD-12) |

**Functions and constants:**

| Name                                    | Purpose                                                                                                      |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `OPEN_PATHS`                            | The exact paths the gate leaves open: health, setup, login, logout                                           |
| `authenticated_principal(conn)`         | Username, `api-key`, or None — used for audit actors                                                         |
| `require_api_key(x_api_key)`            | HTTP dependency; validates the key against `settings.api_keys` unconditionally (no `api_key_enabled` branch) |
| `validate_websocket_api_key(websocket)` | Validate API key for WebSocket connections (`API_KEY_ENABLED`)                                               |
| `authenticate_websocket(websocket)`     | Authenticate WebSocket and close if invalid                                                                  |
| `_hash_key(key)`                        | Hash API key using SHA-256                                                                                   |
| `_get_valid_key_hashes()`               | Get valid API key hashes from settings                                                                       |

### `request_id.py`

Request ID generation and propagation middleware for request tracing and log correlation.

**Classes:**

| Class                 | Purpose                            |
| --------------------- | ---------------------------------- |
| `RequestIDMiddleware` | Generate and propagate request IDs |

### `rate_limit.py`

Redis-based sliding window rate limiting for API endpoints.

**Classes:**

| Class           | Purpose                              |
| --------------- | ------------------------------------ |
| `RateLimitTier` | Enum for rate limit tiers            |
| `RateLimiter`   | FastAPI dependency for rate limiting |

**Functions:**

| Function                     | Purpose                                    |
| ---------------------------- | ------------------------------------------ |
| `get_tier_limits(tier)`      | Get rate limit settings for a tier         |
| `get_client_ip(request)`     | Extract client IP from request headers     |
| `check_websocket_rate_limit` | Check rate limit for WebSocket connections |
| `rate_limit_default()`       | Get default rate limiter dependency        |
| `rate_limit_media()`         | Get media rate limiter dependency          |
| `rate_limit_search()`        | Get search rate limiter dependency         |

### `correlation.py`

Correlation ID helpers for propagating correlation IDs to outgoing HTTP requests to external services.

**Purpose:**

Provides utilities for propagating correlation IDs from incoming requests to outgoing HTTP requests when calling external services (YOLO26, Nemotron, etc.). Implements NEM-1472 (Correlation ID propagation to AI service HTTP clients).

**Functions:**

| Function                         | Purpose                                         |
| -------------------------------- | ----------------------------------------------- |
| `get_correlation_headers()`      | Get headers for propagating correlation ID      |
| `merge_headers_with_correlation` | Merge existing headers with correlation headers |

**Usage:**

```python
from backend.api.middleware.correlation import get_correlation_headers

headers = {"Content-Type": "application/json"}
headers.update(get_correlation_headers())

async with httpx.AsyncClient() as client:
    response = await client.post(url, headers=headers, json=data)
```

**Headers Propagated:**

- `X-Correlation-ID` - Correlation ID from current request context
- `X-Request-ID` - Request ID from current request (fallback for some services)
- `traceparent` - W3C Trace Context parent header (OpenTelemetry)
- `tracestate` - W3C Trace Context state header (OpenTelemetry)
- `baggage` - W3C Baggage header for cross-service context (NEM-3796)

### `baggage.py`

OpenTelemetry Baggage middleware for cross-service context propagation (NEM-3796).

**Purpose:**

Extracts incoming baggage from W3C Baggage headers and sets application-specific context for propagation across service boundaries in the detection pipeline.

**Classes:**

| Class               | Purpose                                          |
| ------------------- | ------------------------------------------------ |
| `BaggageMiddleware` | Middleware for OpenTelemetry Baggage propagation |

**Functions:**

| Function                            | Purpose                                         |
| ----------------------------------- | ----------------------------------------------- |
| `set_pipeline_baggage()`            | Set pipeline-specific baggage entries           |
| `get_camera_id_from_baggage()`      | Get camera.id from current baggage context      |
| `get_event_priority_from_baggage()` | Get event.priority from current baggage context |
| `get_request_source_from_baggage()` | Get request.source from current baggage context |
| `get_batch_id_from_baggage()`       | Get batch.id from current baggage context       |

**Baggage Keys:**

| Key              | Description                                    | Valid Values                 |
| ---------------- | ---------------------------------------------- | ---------------------------- |
| `camera.id`      | Source camera for detection pipeline           | Camera identifier string     |
| `event.priority` | Priority level for downstream processing       | low, normal, high, critical  |
| `request.source` | Origin of request                              | ui, api, scheduled, internal |
| `batch.id`       | Optional batch identifier for batch processing | Batch identifier string      |

**Usage:**

```python
# Setting baggage at pipeline entry
from backend.api.middleware.baggage import set_pipeline_baggage

set_pipeline_baggage(camera_id="front_door", event_priority="high", request_source="api")

# Reading baggage in downstream services
from backend.api.middleware.baggage import (
    get_camera_id_from_baggage,
    get_event_priority_from_baggage,
)

camera_id = get_camera_id_from_baggage()
if get_event_priority_from_baggage() == "high":
    # Fast-track processing
    pass
```

**Automatic Behavior:**

- Extracts `request.source` from `X-Request-Source` header (defaults to "api")
- Extracts `camera.id` from URL path patterns like `/cameras/{camera_id}/...`
- Preserves incoming baggage from upstream services

### `security_headers.py`

Security headers middleware for HTTP responses.

**Classes:**

| Class                       | Purpose                                     |
| --------------------------- | ------------------------------------------- |
| `SecurityHeadersMiddleware` | Adds security headers to all HTTP responses |

**Security Headers Applied:**

| Header                    | Default Value                                    | Purpose                            |
| ------------------------- | ------------------------------------------------ | ---------------------------------- |
| `X-Content-Type-Options`  | `nosniff`                                        | Prevents MIME type sniffing        |
| `X-Frame-Options`         | `DENY`                                           | Prevents clickjacking attacks      |
| `X-XSS-Protection`        | `1; mode=block`                                  | Enables browser XSS filtering      |
| `Referrer-Policy`         | `strict-origin-when-cross-origin`                | Controls referrer information      |
| `Content-Security-Policy` | Allows self, inline styles, data URIs, WebSocket | Restricts resource loading sources |
| `Permissions-Policy`      | Restricts camera, mic, geolocation, etc.         | Controls browser feature access    |

**Configuration:**

All headers are configurable via constructor parameters but have secure defaults.

### `body_limit.py`

Request body size limits middleware for DoS protection.

**Purpose:**

Limits the maximum size of request bodies to prevent memory exhaustion and denial-of-service attacks. Returns 413 Payload Too Large for requests exceeding the limit.

**Classes:**

| Class                 | Purpose                            |
| --------------------- | ---------------------------------- |
| `BodyLimitMiddleware` | Enforces maximum request body size |

**Configuration:**

- `max_body_size` - Maximum body size in bytes (default from settings)

### `content_type_validator.py`

Content-Type header validation for request bodies.

**Purpose:**

Ensures that POST/PUT/PATCH requests include proper Content-Type headers and validates that the content type matches expected values (application/json, multipart/form-data, etc.).

**Classes:**

| Class                            | Purpose                        |
| -------------------------------- | ------------------------------ |
| `ContentTypeValidatorMiddleware` | Validates Content-Type headers |

### `idempotency.py`

Idempotency-Key header support for mutation endpoints (NEM-2018).

**Purpose:**

Provides Idempotency-Key header support for POST, PUT, PATCH, and DELETE requests. Implements industry-standard idempotency patterns to prevent duplicate resource creation from retried requests.

**Classes:**

| Class                   | Purpose                                    |
| ----------------------- | ------------------------------------------ |
| `IdempotencyMiddleware` | Caches responses by Idempotency-Key header |

**Functions:**

| Function                      | Purpose                                              |
| ----------------------------- | ---------------------------------------------------- |
| `compute_request_fingerprint` | Generate SHA-256 fingerprint for collision detection |

**Features:**

- Caches responses for requests with Idempotency-Key headers in Redis
- Returns cached response on replay with `Idempotency-Replayed: true` header
- Returns 422 Unprocessable Entity if same key used with different request body
- Configurable TTL (default: 24 hours)
- Fails open (passes through) when Redis is unavailable

**Configuration:**

```python
app.add_middleware(
    IdempotencyMiddleware,
    ttl=86400,  # 24 hours (default from settings)
    key_prefix="idempotency",  # Redis key prefix
)
```

**Environment Variables:**

- `IDEMPOTENCY_ENABLED` - Enable/disable idempotency support (default: true)
- `IDEMPOTENCY_TTL_SECONDS` - TTL for cached responses (default: 86400)

**Usage:**

```bash
# First request - creates resource
curl -X POST http://localhost:8000/api/cameras \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-key-abc123" \
  -d '{"name": "Front Door"}'
# Returns: {"id": "cam-1", "name": "Front Door"}

# Retry with same key and body - returns cached response
curl -X POST http://localhost:8000/api/cameras \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-key-abc123" \
  -d '{"name": "Front Door"}'
# Returns: {"id": "cam-1", "name": "Front Door"}
# Header: Idempotency-Replayed: true

# Same key with different body - returns 422
curl -X POST http://localhost:8000/api/cameras \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-key-abc123" \
  -d '{"name": "Back Door"}'
# Returns: 422 Unprocessable Entity
# Body: {"detail": "Idempotency key collision..."}
```

### `file_validator.py`

File upload validation using magic number detection.

**Purpose:**

Validates uploaded files by checking their magic numbers (file signatures) to ensure the actual file type matches the claimed MIME type. Prevents file type spoofing attacks.

**Functions:**

| Function              | Purpose                                      |
| --------------------- | -------------------------------------------- |
| `validate_file_magic` | Check file magic number against claimed type |
| `get_magic_bytes`     | Get magic number bytes for a file type       |

**Supported Types:**

- Images: JPEG, PNG, GIF, WebP, BMP
- Videos: MP4, AVI, WebM, MKV, MOV

### `accept_header.py`

Accept header content negotiation middleware for HTTP API responses.

**Purpose:**

Validates incoming requests have an Accept header compatible with the API's supported response formats. Implements HTTP content negotiation per RFC 7231.

**Classes:**

| Class                    | Purpose                                    |
| ------------------------ | ------------------------------------------ |
| `AcceptHeaderMiddleware` | Validates Accept header for JSON responses |

**Functions:**

| Function                 | Purpose                                               |
| ------------------------ | ----------------------------------------------------- |
| `parse_accept_header`    | Parse Accept header into (media_type, quality) tuples |
| `select_best_media_type` | Select best matching media type from accepted types   |

**Supported Media Types:**

- `application/json` - Standard JSON responses
- `application/problem+json` - RFC 7807 Problem Details for errors

**Features:**

- RFC 7231 compliant Accept header parsing
- Quality value (q=) support
- Wildcard (_/_) and type wildcard (application/\*) support
- Configurable exempt paths for health checks, WebSocket upgrades
- Returns 406 Not Acceptable for unsupported formats

### `content_negotiation.py`

Content negotiation middleware for HTTP response headers.

**Purpose:**

Handles content negotiation concerns beyond Accept header validation by adding charset declarations and Vary headers for proper caching.

**Classes:**

| Class                          | Purpose                                           |
| ------------------------------ | ------------------------------------------------- |
| `ContentNegotiationMiddleware` | Enhances response headers for content negotiation |

**Features:**

- Adds `charset=utf-8` to Content-Type headers for JSON responses
- Adds `Vary: Accept-Encoding` header for proper caching with compression
- RFC 7231 Section 3.1.1.5 compliant charset handling
- RFC 7231 Section 7.1.4 compliant Vary header handling

### `deprecation.py`

RFC 8594 Deprecation and Sunset headers middleware.

**Purpose:**

Implements HTTP middleware for API endpoint deprecation signaling per RFC 8594. Adds Deprecation and Sunset headers to responses for deprecated endpoints.

**Classes:**

| Class                   | Purpose                                         |
| ----------------------- | ----------------------------------------------- |
| `DeprecatedEndpoint`    | Configuration dataclass for deprecated endpoint |
| `DeprecationConfig`     | Registry for deprecated endpoints with matching |
| `DeprecationMiddleware` | Adds RFC 8594 headers to deprecated responses   |

**Functions:**

| Function                | Purpose                                                  |
| ----------------------- | -------------------------------------------------------- |
| `format_http_date`      | Format datetime as HTTP-date per RFC 7231                |
| `format_unix_timestamp` | Format datetime as Unix timestamp for Deprecation header |

**Headers Added:**

- `Deprecation: true` or `@<unix-timestamp>` - Indicates endpoint is deprecated
- `Sunset: <HTTP-date>` - When endpoint will be removed
- `Link: <url>; rel="deprecation"` - Optional documentation link

**Usage:**

```python
config = DeprecationConfig()
config.register(
    DeprecatedEndpoint(
        path="/api/v1/old-endpoint",
        sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
        replacement="/api/v2/new-endpoint",
    )
)
app.add_middleware(DeprecationMiddleware, config=config)
```

### `deprecation_logger.py`

Deprecation logging middleware for tracking deprecated endpoint usage (NEM-2090).

**Purpose:**

Logs calls to deprecated API endpoints and tracks deprecation metrics via Prometheus for migration tracking.

**Classes:**

| Class                         | Purpose                                   |
| ----------------------------- | ----------------------------------------- |
| `DeprecationLoggerMiddleware` | Logs and tracks deprecated endpoint calls |

**Functions:**

| Function                 | Purpose                                    |
| ------------------------ | ------------------------------------------ |
| `record_deprecated_call` | Manually record a deprecated endpoint call |

**Prometheus Metrics:**

- `hsi_api_deprecated_calls_total` - Counter for deprecated endpoint calls (labels: endpoint, client_id)

**Features:**

- Logs warning with client identification (X-Client-ID header)
- Increments Prometheus counter for deprecation tracking
- Adds RFC 7234 Warning header (code 299) to responses
- Supports sunset date display in warning message

### `error_handler.py`

Centralized error handler middleware for consistent API error responses (NEM-2571).

**Purpose:**

Provides AppException base class and common exception types for standardized API error responses. Re-exports exception hierarchy for convenient imports.

**Classes:**

| Class                     | Status Code | Purpose                             |
| ------------------------- | ----------- | ----------------------------------- |
| `AppException`            | 500         | Base exception for API errors       |
| `ErrorResponse`           | -           | Pydantic schema for error responses |
| `ValidationError`         | 422         | Request validation failures         |
| `UnauthorizedError`       | 401         | Authentication failures             |
| `ForbiddenError`          | 403         | Authorization failures              |
| `ServiceUnavailableError` | 503         | External service failures           |
| `RateLimitExceededError`  | 429         | Rate limit exceeded errors          |

**Re-exported from `backend.core.exceptions`:**

- `NotFoundError`, `ConflictError`, `DatabaseError`
- `CameraNotFoundError`, `EventNotFoundError`, `DetectionNotFoundError`
- `AuthenticationError`, `AuthorizationError`
- `ExternalServiceError`, `CircuitBreakerOpenError`
- `DuplicateResourceError`, `RateLimitError`

**Functions:**

| Function                      | Purpose                             |
| ----------------------------- | ----------------------------------- |
| `build_error_response`        | Build ErrorResponse from exception  |
| `get_request_id`              | Get request ID from current context |
| `register_exception_handlers` | Register global exception handlers  |

### `request_recorder.py`

Request recording middleware for replay debugging (NEM-1646).

**Purpose:**

Records HTTP requests for later replay during debugging. Useful for reproducing issues in development without needing to recreate the exact request conditions.

**Classes:**

| Class                       | Purpose                     |
| --------------------------- | --------------------------- |
| `RequestRecorderMiddleware` | Records requests for replay |

**Features:**

- Configurable recording trigger (header or query param)
- Request body capture
- Headers capture (with sensitive redaction)
- Replay endpoint for recorded requests

### `websocket_auth.py`

WebSocket-specific token authentication.

**Purpose:**

Provides WebSocket authentication separate from the main API key authentication. Supports token-based authentication via query parameters or Sec-WebSocket-Protocol header.

**Functions:**

| Function                       | Purpose                             |
| ------------------------------ | ----------------------------------- |
| `validate_websocket_token`     | Validate WebSocket connection token |
| `authenticate_websocket_token` | Authenticate and close if invalid   |

### `exception_handler.py`

Exception handling utilities with data minimization.

**Purpose:**

Provides utilities for safely handling exceptions with sensitive data minimization. Ensures error responses don't leak internal implementation details or sensitive information.

**Functions:**

| Function                  | Purpose                                      |
| ------------------------- | -------------------------------------------- |
| `minimize_error_response` | Remove sensitive details from error response |
| `safe_error_message`      | Generate safe error message for clients      |

### `observability.py`

Unified observability middleware combining request timing, structured logging, and Prometheus metrics in one ASGI layer (NEM-5558). It is registered in `backend/main.py` and is the only path for timing, request logging, and HTTP metrics — the former `request_timing.py`, `request_logging.py`, and standalone `PrometheusMiddleware` passes it replaces were deleted.

### `etag.py`

ETag support for conditional GET requests (NEM-3743): computes weak ETags for cacheable responses and handles `If-None-Match` with 304 responses.

### `prometheus.py`

Prometheus HTTP request metrics middleware (NEM-4149): records request count, duration histogram, and in-progress gauge per route/method/status.

### `profiling.py`

Profiling middleware for trace-context correlation: attaches profiling spans and correlates them with the request correlation ID.

### `setup_guard.py`

Setup guard middleware (`SetupGuardMiddleware`): returns 503 for API endpoints until the first admin user registers (single-user bootstrap gate).

---

## Authentication Middleware (`auth.py`)

### Purpose

`AuthMiddleware` is the gate the owner ruled in OD-12 (built by uplevel `B1.5`). With
`EXPOSE_LAN` unset the backend requires no credential, as before; the frontend
now binds to 127.0.0.1 only (`O1.6` landed). With `EXPOSE_LAN=true` it refuses every HTTP request and WebSocket handshake that
presents no valid credential — whatever the path, including routes added later — except
`OPEN_PATHS`.

### Credentials

- the `session_id` cookie `POST /api/auth/login` sets (HttpOnly, SameSite=Lax, Secure), looked
  up in Redis on each request; browsers send it on every same-origin fetch, media load and
  WebSocket handshake;
- an API key from `API_KEYS`: the `X-API-Key` header over HTTP; on a WebSocket, an
  `api-key.<key>` subprotocol (preferred) or the `api_key` query parameter, which reaches access
  logs. HTTP never takes a key from the URL.

### Open paths (exact matches)

`/health`, `/ready`, `/api/system/health`, `/api/system/health/ready` (healthchecks and probes);
`/api/auth/setup-status`, `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`.
Monitoring (`/api/metrics`, `/api/system/{gpu,stats,telemetry}`) needs a credential like every
other path (owner ruling UR-33); `O1.11` gives Prometheus, Alertmanager and Grafana one.
CORS preflights that carry `Origin` also pass (CORSMiddleware answers those itself). Everything
else, `/docs` and media included, needs a credential.

### Refusals

- HTTP: `401 {"detail": "Authentication required"}`.
- WebSocket: accepted, then closed with `4001`, so a client can tell refusal from a dropped network.
- Log: every refusal is a `WARNING` security event — `event_type="auth_required"`, `security_event=True`,
  `path`, `method`, and `client_ip` masked by `mask_ip`.
- An admitted, authenticated HTTP response is marked `Cache-Control: private` (replacing `public`),
  so a caching tunnel or CDN never stores footage the gate protected.

### Placement

Added last in `backend/main.py`, so it runs first: `IdempotencyMiddleware` replays stored
responses by key alone, and nothing may answer before the gate. The per-route guards
(`verify_api_key`, `require_admin_access`, `get_current_admin_user`, `WEBSOCKET_TOKEN`) still
run after it.

---

## Request ID Middleware (`request_id.py`)

### Purpose

Generates unique request IDs for each HTTP request and propagates them through the logging context. This enables:

- Request tracing across log entries
- Correlation of logs from the same request
- Debugging distributed operations

### Implementation

**Class:** `RequestIDMiddleware(BaseHTTPMiddleware)`

**Flow:**

1. Check for existing `X-Request-ID` header (allows client-provided IDs)
2. If no header, generate new 8-character UUID
3. Set request ID in logging context via `set_request_id()`
4. Process request through route handler
5. Add `X-Request-ID` header to response
6. Clear logging context

### Usage

Request IDs appear in:

- Log entries with `request_id` field
- Response headers as `X-Request-ID`
- Can be used to trace requests in distributed systems

**Example Log Entry:**

```json
{
  "timestamp": "2025-12-23T10:30:00Z",
  "level": "INFO",
  "message": "Processing detection",
  "request_id": "a1b2c3d4"
}
```

**Response Header:**

```
X-Request-ID: a1b2c3d4
```

---

## Rate Limiting Middleware (`rate_limit.py`)

### Purpose

Provides Redis-based sliding window rate limiting to prevent API abuse. Uses a sliding window counter algorithm for smoother rate limiting compared to fixed windows.

### Configuration

Rate limiting is controlled via environment variables:

```bash
# Enable rate limiting (default: false)
export RATE_LIMIT_ENABLED=true

# Default requests per minute
export RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Media endpoint requests per minute
export RATE_LIMIT_MEDIA_REQUESTS_PER_MINUTE=120

# Search endpoint requests per minute
export RATE_LIMIT_SEARCH_REQUESTS_PER_MINUTE=30

# WebSocket connections per minute
export RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE=10

# Burst allowance
export RATE_LIMIT_BURST=10
```

### Rate Limit Tiers

| Tier      | Purpose               | Default Limit |
| --------- | --------------------- | ------------- |
| DEFAULT   | General API endpoints | 60/min        |
| MEDIA     | Media file serving    | 120/min       |
| SEARCH    | Search endpoints      | 30/min        |
| WEBSOCKET | WebSocket connections | 10/min        |

### Usage as FastAPI Dependency

```python
from backend.api.middleware import RateLimiter, RateLimitTier


@router.get("/endpoint")
async def endpoint(
    _: None = Depends(RateLimiter(tier=RateLimitTier.DEFAULT)),
):
    return {"data": "value"}


# Or use convenience functions
@router.get("/search")
async def search(_: None = Depends(rate_limit_search())):
    return {"results": []}
```

### WebSocket Rate Limiting

```python
from backend.api.middleware import check_websocket_rate_limit


async def websocket_handler(websocket: WebSocket):
    if not await check_websocket_rate_limit(websocket, redis_client):
        await websocket.close(code=1008)  # Policy Violation
        return
    # ... handle connection
```

### Implementation Details

**Algorithm:** Sliding window counter using Redis sorted sets

**Flow:**

1. Check if rate limiting is enabled
2. Extract client IP from request (supports X-Forwarded-For, X-Real-IP)
3. Create Redis key: `{prefix}:{tier}:{client_ip}`
4. Remove expired entries outside the sliding window
5. Count current requests in window
6. Add current request with timestamp
7. Compare count against limit + burst
8. If exceeded, return 429 with Retry-After header

**Redis Operations (atomic pipeline):**

- `ZREMRANGEBYSCORE` - Remove expired entries
- `ZCARD` - Count current requests
- `ZADD` - Add new request with timestamp
- `EXPIRE` - Set key expiry

### Error Response (429 Too Many Requests)

```json
{
  "error": "Too many requests",
  "message": "Rate limit exceeded. Maximum 60 requests per minute.",
  "retry_after_seconds": 60,
  "tier": "default"
}
```

**Response Headers:**

- `Retry-After: 60`
- `X-RateLimit-Limit: 60`
- `X-RateLimit-Remaining: 0`
- `X-RateLimit-Reset: 1703779200`

### Fail-Open Behavior

On Redis errors, the rate limiter fails open (allows the request) to prevent service disruption.

---

## Integration with FastAPI

Middleware is registered in `backend/main.py` during application startup, in this `add_middleware()` order (Starlette runs them in reverse — the last registered is the outermost layer):

```python
# backend/main.py registration order
app.add_middleware(SetupGuardMiddleware)  # 503 until first admin (NEM-5312)
app.add_middleware(ContentTypeValidationMiddleware)  # NEM-1617
app.add_middleware(RequestIDMiddleware)  # log correlation
app.add_middleware(BaggageMiddleware)  # W3C Baggage (NEM-3796)
app.add_middleware(ProfilingMiddleware)  # trace-to-profile (NEM-4127)
app.add_middleware(  # one pass: timing + logging + metrics
    ObservabilityMiddleware,  # (NEM-5558)
    enable_request_logging=get_settings().request_logging_enabled,
)
if get_settings().request_recording_enabled:  # off by default
    app.add_middleware(RequestRecorderMiddleware)
app.add_middleware(CORSMiddleware, ...)  # explicit header allowlist (NEM-5059)
app.add_middleware(SecurityHeadersMiddleware, hsts_preload=get_settings().hsts_preload)
app.add_middleware(BodySizeLimitMiddleware, max_body_size=10 * 1024 * 1024)  # NEM-1614
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)  # NEM-3741
if get_settings().idempotency_enabled:
    app.add_middleware(IdempotencyMiddleware)
app.add_middleware(AuthMiddleware)  # the EXPOSE_LAN gate (OD-12, B1.5): outermost
```

`AuthMiddleware` passes everything unless `EXPOSE_LAN=true` (see above). `DeprecationMiddleware` and `DeprecationLoggerMiddleware` are not registered (NEM-5558: zero deprecated endpoints).

---

## Testing

Unit tests are located at:

```
backend/tests/unit/api/middleware/test_auth.py
backend/tests/unit/api/middleware/test_rate_limit.py
```

**Test Coverage:**

- The EXPOSE_LAN gate: off on loopback; refusals; open paths; API keys; login sessions; CORS preflight
- Every mounted route refused when exposed: `backend/tests/unit/api/test_expose_lan_routes.py`
- WebSocket API-key validation logging
- Request ID generation and propagation
- Rate limit enforcement
- Rate limit bypass when disabled
- Different rate limit tiers
- WebSocket rate limiting

**Run Tests:**

```bash
pytest backend/tests/unit/api/middleware/test_auth.py -v
pytest backend/tests/unit/api/middleware/test_rate_limit.py -v
```

---

## Common Patterns

### Middleware Pattern

FastAPI middleware follows the ASGI middleware pattern:

```python
async def dispatch(self, request: Request, call_next: Callable) -> Response:
    # Pre-processing: runs before route handler
    # ... validate request ...

    # Call next middleware/route handler
    response = await call_next(request)

    # Post-processing: runs after route handler
    # ... modify response ...

    return response
```

### Dependency Injection Alternative

For simpler authentication needs, FastAPI dependencies can be used instead:

```python
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not validate_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


@router.get("/protected")
async def protected_endpoint(api_key: str = Depends(verify_api_key)):
    return {"message": "Protected data"}
```

**Middleware is better for:**

- Global authentication across all routes
- Complex pre/post-processing logic
- Performance (no per-route overhead)

**Dependencies are better for:**

- Route-specific authentication
- Multiple authentication schemes
- Easier testing (can mock dependencies)

---

## Best Practices

1. **Environment Variables:** Never hardcode API keys in source code
2. **HTTPS Only:** Always use HTTPS in production to prevent key interception
3. **Key Rotation:** Regularly rotate API keys
4. **Monitoring:** Monitor for suspicious authentication patterns
5. **Logging:** Log authentication failures for security auditing
6. **Documentation:** Keep API key documentation updated for consumers
7. **Request IDs:** Always include request IDs in error reports

---

## Future Enhancements

Potential improvements for production deployments:

1. **Database Storage** - Store API keys in database with metadata:

   - Key name/description
   - Created timestamp
   - Last used timestamp
   - Is active flag
   - Associated user/service

2. **Key Rotation** - Support key expiration and rotation:

   - Expiration timestamps
   - Automatic key rotation schedules
   - Grace periods for old keys

3. **Rate Limiting** - Per-API key rate limits:

   - Request count per time window
   - Different limits per key
   - Burst allowance

4. **Audit Logging** - Log API key usage:

   - Request timestamp
   - Endpoint accessed
   - Source IP address
   - Response status

5. **Key Permissions** - Scope-based access control:

   - Read-only vs read-write keys
   - Resource-specific permissions
   - Role-based access control

6. **Multiple Authentication Methods** - Support additional auth:
   - JWT tokens
   - OAuth2
   - Session-based authentication
