# Middleware Hub

> Request processing pipeline and cross-cutting concerns for the Home Security Intelligence API

## Overview

The middleware stack in this application processes all incoming HTTP requests before they reach route handlers, and all outgoing responses before they're sent to clients. This hub documents each middleware component, their execution order, and how they work together to provide logging, error handling, security, and request validation.

Middleware components in FastAPI/Starlette are executed in a specific order determined by their registration sequence in `backend/main.py`. The order matters because each middleware can modify the request before passing it to the next middleware, and modify the response on the way back. Understanding this execution order is critical for debugging and extending the middleware stack.

The middleware architecture follows defense-in-depth principles, with multiple layers of validation, security headers, and error handling. Each middleware is designed to be independent and testable, with clear responsibilities and minimal coupling to other components.

## Documents

| Document                                         | Description                                           | Key Files                                                                                       |
| ------------------------------------------------ | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [request-logging.md](./request-logging.md)       | Structured request/response logging for observability | `backend/api/middleware/request_logging.py`                                                     |
| [error-handling.md](./error-handling.md)         | Global exception handlers and error response formats  | `backend/api/exception_handlers.py`, `backend/api/middleware/error_handler.py`                  |
| [cors-configuration.md](./cors-configuration.md) | CORS settings for frontend integration                | `backend/main.py:1041-1053`, `backend/core/config.py:572-585`                                   |
| [request-validation.md](./request-validation.md) | Pydantic validation, path parameter parsing           | `backend/api/middleware/content_type_validator.py`, `backend/api/exception_handlers.py:305-374` |
| [rate-limiting.md](./rate-limiting.md)           | Rate limit configuration and tiers                    | `backend/api/middleware/rate_limit.py`                                                          |

## Architecture Diagram

```mermaid
graph TD
    subgraph "Incoming Request"
        REQ[HTTP Request] --> AUTH
    end

    subgraph "Middleware Stack (Execution Order)"
        AUTH[AuthMiddleware<br/>backend/api/middleware/auth.py:129] --> CT
        CT[ContentTypeValidationMiddleware<br/>backend/api/middleware/content_type_validator.py:28] --> RID
        RID[RequestIDMiddleware<br/>backend/api/middleware/request_id.py:45] --> RT
        RT[RequestTimingMiddleware<br/>backend/api/middleware/request_timing.py:26] --> RL
        RL[RequestLoggingMiddleware<br/>backend/api/middleware/request_logging.py:136] --> RR
        RR[RequestRecorderMiddleware<br/>backend/api/middleware/request_recorder.py] --> DEP
        DEP[DeprecationMiddleware<br/>backend/api/middleware/deprecation.py] --> DEPL
        DEPL[DeprecationLoggerMiddleware<br/>backend/api/middleware/deprecation_logger.py] --> CORS
        CORS[CORSMiddleware<br/>FastAPI builtin] --> SEC
        SEC[SecurityHeadersMiddleware<br/>backend/api/middleware/security_headers.py:23] --> BL
        BL[BodySizeLimitMiddleware<br/>backend/api/middleware/body_limit.py:40] --> IDEM
        IDEM[IdempotencyMiddleware<br/>backend/api/middleware/idempotency.py:107] --> ROUTE
    end

    subgraph "Route Processing"
        ROUTE[Route Handler] --> EH
        EH[Exception Handlers<br/>backend/api/exception_handlers.py:695]
    end

    subgraph "Response"
        EH --> RESP[HTTP Response]
    end

    style AUTH fill:#f9f,stroke:#333
    style CORS fill:#bbf,stroke:#333
    style SEC fill:#bfb,stroke:#333
    style EH fill:#fbb,stroke:#333
```

## Quick Reference

| Component                       | File                                                      | Purpose                        |
| ------------------------------- | --------------------------------------------------------- | ------------------------------ |
| AuthMiddleware                  | `backend/api/middleware/auth.py:129-307`                  | API key authentication         |
| ContentTypeValidationMiddleware | `backend/api/middleware/content_type_validator.py:28-195` | Validate Content-Type headers  |
| RequestIDMiddleware             | `backend/api/middleware/request_id.py:45-90`              | Generate/propagate request IDs |
| RequestTimingMiddleware         | `backend/api/middleware/request_timing.py:26-156`         | Measure request duration       |
| RequestLoggingMiddleware        | `backend/api/middleware/request_logging.py:136-321`       | Structured request logging     |
| DeprecationMiddleware           | `backend/api/middleware/deprecation.py`                   | RFC 8594 deprecation headers   |
| CORSMiddleware                  | FastAPI builtin                                           | Cross-Origin Resource Sharing  |
| SecurityHeadersMiddleware       | `backend/api/middleware/security_headers.py:23-176`       | Security response headers      |
| BodySizeLimitMiddleware         | `backend/api/middleware/body_limit.py:40-103`             | Request body size limits       |
| IdempotencyMiddleware           | `backend/api/middleware/idempotency.py:107-593`           | Idempotency-Key support        |
| RateLimiter                     | `backend/api/middleware/rate_limit.py:266-435`            | Rate limiting (dependency)     |

## Key Concepts

### Middleware Execution Order

![Middleware Processing Chain - Request and response flow through middleware stack](../../images/architecture/middleware-chain.png)

Middleware in Starlette/FastAPI executes in **reverse registration order** for requests and **registration order** for responses. The middleware registered first wraps all subsequent middleware:

```
Request:  Client -> Last Registered -> ... -> First Registered -> Route
Response: Route -> First Registered -> ... -> Last Registered -> Client
```

This means `AuthMiddleware` (registered first in `backend/main.py:1003`) processes requests first and responses last.

### Exception Handlers vs Middleware

Exception handlers (`backend/api/exception_handlers.py`) are distinct from middleware. They catch exceptions raised during request processing and convert them to HTTP responses. They're registered separately via `app.add_exception_handler()` and process exceptions based on type hierarchy.

### Context Variables

Several middleware components use Python context variables to share state across the request lifecycle:

- `request_id` - Request correlation ID
- `correlation_id` - Distributed tracing ID
- `trace_id` / `span_id` - OpenTelemetry context

## Configuration

| Setting                          | Location                         | Default             | Description                   |
| -------------------------------- | -------------------------------- | ------------------- | ----------------------------- |
| `api_key_enabled`                | `backend/core/config.py`         | `false`             | Enable API key authentication |
| `cors_origins`                   | `backend/core/config.py:575-585` | Development origins | Allowed CORS origins          |
| `rate_limit_enabled`             | `backend/core/config.py:1328`    | `true`              | Enable rate limiting          |
| `rate_limit_requests_per_minute` | `backend/core/config.py:1332`    | `60`                | Default rate limit            |
| `request_logging_enabled`        | `backend/core/config.py:1821`    | `true`              | Enable request logging        |
| `request_recording_enabled`      | `backend/core/config.py`         | `false`             | Enable request recording      |
| `idempotency_enabled`            | `backend/core/config.py`         | `false`             | Enable idempotency middleware |
| `hsts_preload`                   | `backend/core/config.py`         | `false`             | HSTS preload directive        |

## Middleware Registration

Middleware is registered in `backend/main.py:1003-1070`:

```python
# From backend/main.py:1003-1070
app.add_middleware(AuthMiddleware)
app.add_middleware(ContentTypeValidationMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestTimingMiddleware)
if get_settings().request_logging_enabled:
    app.add_middleware(RequestLoggingMiddleware)
if get_settings().request_recording_enabled:
    app.add_middleware(RequestRecorderMiddleware)
app.add_middleware(DeprecationMiddleware, config=_get_deprecation_config())
app.add_middleware(DeprecationLoggerMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware, hsts_preload=get_settings().hsts_preload)
app.add_middleware(BodySizeLimitMiddleware, max_body_size=10 * 1024 * 1024)
if get_settings().idempotency_enabled:
    app.add_middleware(IdempotencyMiddleware)
```

## Related Hubs

- [API Reference](../api-reference/README.md) - Endpoint documentation
- [Observability](../observability/README.md) - Logging and tracing integration
- [Security](../security/README.md) - Security middleware and authentication
- [Resilience Patterns](../resilience-patterns/README.md) - Circuit breakers and retry logic

---

_Last updated: 2025-01-24 - Complete middleware hub documentation for NEM-3461_
