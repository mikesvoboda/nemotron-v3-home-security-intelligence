# API Middleware

## Purpose

The `backend/api/middleware/` directory contains HTTP middleware components that handle cross-cutting concerns for the FastAPI application. Middleware processes requests before they reach route handlers and responses before they are sent to clients.

## Files

### `__init__.py`

Package initialization with public exports:

- `AuthMiddleware` - HTTP API key authentication middleware
- `authenticate_websocket` - WebSocket authentication helper
- `validate_websocket_api_key` - WebSocket API key validation
- `RateLimiter` - FastAPI dependency for rate limiting
- `RateLimitTier` - Rate limit tier enum (DEFAULT, MEDIA, WEBSOCKET, SEARCH)
- `check_websocket_rate_limit` - WebSocket connection rate limiting
- `get_client_ip` - Extract client IP from request
- `rate_limit_default`, `rate_limit_media`, `rate_limit_search` - Convenience dependencies

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
const ws = new WebSocket("ws://localhost:8000/ws/events?api_key=YOUR_KEY");
```

**Sec-WebSocket-Protocol Header:**

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/events", ["api-key.YOUR_KEY"]);
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
