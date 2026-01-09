# API Middleware

## Purpose

The `backend/api/middleware/` directory contains HTTP middleware components that handle cross-cutting concerns for the FastAPI application. Middleware processes requests before they reach route handlers and responses before they are sent to clients.

## Files

### `__init__.py`

Package initialization with public exports:

- `AuthMiddleware` - HTTP API key authentication middleware
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
- `RequestTimingMiddleware` - Request timing and slow request logging middleware
- `get_correlation_headers` - Get correlation headers for outgoing requests
- `merge_headers_with_correlation` - Merge headers with correlation IDs
- `get_correlation_id` - Get current correlation ID from context
- `set_correlation_id` - Set correlation ID in context

### `auth.py`

API key authentication middleware for securing HTTP endpoints and WebSocket connections.

**Classes:**

| Class            | Purpose                                            |
| ---------------- | -------------------------------------------------- |
| `AuthMiddleware` | BaseHTTPMiddleware for HTTP API key authentication |

**Functions:**

| Function                                | Purpose                                     |
| --------------------------------------- | ------------------------------------------- |
| `validate_websocket_api_key(websocket)` | Validate API key for WebSocket connections  |
| `authenticate_websocket(websocket)`     | Authenticate WebSocket and close if invalid |
| `_hash_key(key)`                        | Hash API key using SHA-256                  |
| `_get_valid_key_hashes()`               | Get valid API key hashes from settings      |

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

Provides utilities for propagating correlation IDs from incoming requests to outgoing HTTP requests when calling external services (RT-DETR, Nemotron, etc.). Implements NEM-1472 (Correlation ID propagation to AI service HTTP clients).

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

### `request_timing.py`

Request timing middleware for measuring API latency and logging slow requests.

**Purpose:**

Measures request/response duration, adds timing headers to responses, and logs requests that exceed a configurable threshold. Implements NEM-1469 (Request timing middleware).

**Classes:**

| Class                     | Purpose                                     |
| ------------------------- | ------------------------------------------- |
| `RequestTimingMiddleware` | Middleware for request duration measurement |

**Features:**

- High-precision timing using `time.perf_counter()`
- Adds `X-Response-Time` header to all responses (format: "123.45ms")
- Logs slow requests above configurable threshold (default: 500ms)
- Structured logging with method, path, status code, duration, client IP
- Handles exceptions gracefully (still logs timing even on error)

**Configuration:**

```python
app.add_middleware(
    RequestTimingMiddleware,
    slow_request_threshold_ms=500,  # Log requests slower than 500ms
)
```

**Log Format:**

```json
{
  "level": "WARNING",
  "message": "Slow request: GET /api/events - 200 - 523.45ms (threshold: 500ms)",
  "method": "GET",
  "path": "/api/events",
  "status_code": 200,
  "duration_ms": 523.45,
  "threshold_ms": 500,
  "client_ip": "127.0.0.1"
}
```

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
    ttl=86400,           # 24 hours (default from settings)
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

### `request_logging.py`

Structured HTTP request/response logging middleware.

**Purpose:**

Logs HTTP requests and responses with structured JSON output including method, path, status code, duration, and client IP. Supports configurable log levels and sensitive data redaction.

**Classes:**

| Class                      | Purpose                             |
| -------------------------- | ----------------------------------- |
| `RequestLoggingMiddleware` | Structured request/response logging |

**Features:**

- Structured JSON log format
- Request/response duration timing
- Client IP extraction (with proxy support)
- Sensitive header redaction
- Configurable paths to exclude from logging

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

---

## Authentication Middleware (`auth.py`)

### Purpose

Provides optional API key authentication to secure endpoints. Disabled by default for development convenience.

### Configuration

Authentication is controlled via environment variables:

```bash
# Enable authentication (default: false)
export API_KEY_ENABLED=true

# Set valid API keys (JSON array)
export API_KEYS='["your_secret_key_1", "your_secret_key_2"]'
```

Or in `.env` file:

```env
API_KEY_ENABLED=true
API_KEYS=["your_secret_key_1", "your_secret_key_2"]
```

### HTTP Authentication

**Header Authentication (Recommended):**

```bash
curl -H "X-API-Key: your_secret_key_1" http://localhost:8000/api/cameras
```

**Query Parameter Authentication:**

```bash
curl http://localhost:8000/api/cameras?api_key=your_secret_key_1
```

**Priority:** Header `X-API-Key` takes precedence over `api_key` query parameter.

### WebSocket Authentication

When API key authentication is enabled, WebSocket connections must authenticate via:

**Query Parameter:**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/events?api_key=YOUR_KEY');
```

**Sec-WebSocket-Protocol Header:**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/events', ['api-key.YOUR_KEY']);
```

Unauthenticated WebSocket connections are closed with code 1008 (Policy Violation).

### Exempt Endpoints

The following paths bypass HTTP authentication:

- `/` - Root endpoint
- `/health` - Health check endpoint
- `/api/system/health` - System health check
- `/docs` - Swagger UI documentation
- `/redoc` - ReDoc documentation
- `/openapi.json` - OpenAPI schema

Any path starting with `/docs` or `/redoc` is also exempt.

### Security Features

1. **Key Hashing:** API keys are hashed using SHA-256 before validation
2. **No Plaintext Storage:** Keys are not stored in plaintext in memory
3. **Header Priority:** Header authentication preferred over query parameters
4. **Development Mode:** Authentication disabled by default
5. **Configurable Keys:** Keys loaded from environment variables

### Error Responses

**Missing API Key:**

```json
HTTP 401 Unauthorized
{
  "detail": "API key required. Provide via X-API-Key header or api_key query parameter."
}
```

**Invalid API Key:**

```json
HTTP 401 Unauthorized
{
  "detail": "Invalid API key"
}
```

### Implementation Details

**Class:** `AuthMiddleware(BaseHTTPMiddleware)`

**Constructor Parameters:**

- `app: ASGIApp` - FastAPI application
- `valid_key_hashes: set[str] | None` - Set of SHA-256 hashed API keys (optional, loads from settings if None)

**Methods:**

- `_load_key_hashes() -> set[str]` - Load and hash API keys from settings
- `_hash_key(key: str) -> str` - Hash API key using SHA-256
- `_is_exempt_path(path: str) -> bool` - Check if path bypasses authentication
- `dispatch(request, call_next) -> Response` - Process request and validate API key

**Flow:**

1. Check if authentication is enabled (`API_KEY_ENABLED`)
2. If disabled, pass through to next handler
3. Check if path is exempt from authentication
4. If exempt, pass through to next handler
5. Extract API key from `X-API-Key` header or `api_key` query parameter
6. If no API key provided, return 401 error
7. Hash the provided API key using SHA-256
8. Compare hash against valid key hashes
9. If invalid, return 401 error
10. If valid, pass through to next handler

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

Middleware is registered in the FastAPI application during startup:

```python
from backend.api.middleware import AuthMiddleware

app = FastAPI()
app.add_middleware(AuthMiddleware)
app.add_middleware(RequestIDMiddleware)
```

**Order matters:** Middleware is executed in reverse order of registration. For typical setups:

1. Register `AuthMiddleware` first (runs last, after request ID is set)
2. Register `RequestIDMiddleware` second (runs first, sets context for all handlers)

---

## Testing

Unit tests are located at:

```
backend/tests/unit/test_auth_middleware.py
```

**Test Coverage:**

- Authentication enabled/disabled scenarios
- Valid/invalid API keys
- Missing API keys
- Exempt paths
- Header vs query parameter authentication
- SHA-256 hash validation
- WebSocket authentication
- Request ID generation and propagation
- Rate limit enforcement
- Rate limit bypass when disabled
- Different rate limit tiers
- WebSocket rate limiting

**Run Tests:**

```bash
pytest backend/tests/unit/test_auth_middleware.py -v
pytest backend/tests/unit/test_rate_limit.py -v
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
