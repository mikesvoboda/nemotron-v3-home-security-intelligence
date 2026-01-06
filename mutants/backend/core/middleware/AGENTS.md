# Core Middleware

## Purpose

The `backend/core/middleware/` directory is reserved for core infrastructure middleware that is separate from the API-layer middleware.

## Current Status

**This directory is empty** (no production Python files). All active middleware components are located in the API layer at `backend/api/middleware/`:

- `auth.py` - API key authentication middleware
- `request_id.py` - Request ID generation and propagation
- `rate_limit.py` - Redis-based rate limiting
- `security_headers.py` - Security headers middleware

## Pruning Consideration

This directory could potentially be removed if no core-level middleware is planned. However, keeping it as a placeholder maintains clear architectural separation between:

- **API middleware** (`backend/api/middleware/`) - HTTP request/response processing
- **Core middleware** (`backend/core/middleware/`) - Infrastructure-level concerns (future)

## Future Use Cases

This directory may be used in the future for:

- Database connection middleware (non-API specific)
- Internal service-to-service middleware
- Background task middleware
- Metrics collection middleware

## Related Documentation

- `/backend/api/middleware/AGENTS.md` - Active API middleware documentation
- `/backend/core/AGENTS.md` - Core infrastructure overview
