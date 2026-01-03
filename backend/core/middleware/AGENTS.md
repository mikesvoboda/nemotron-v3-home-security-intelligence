# Core Middleware

## Purpose

The `backend/core/middleware/` directory is reserved for core infrastructure middleware that is separate from the API-layer middleware. Currently, this directory contains only cached Python files from previous implementations.

## Current Status

This directory is **empty** (no production Python files). All active middleware components are located in the API layer at `backend/api/middleware/`:

- `auth.py` - API key authentication middleware
- `request_id.py` - Request ID generation and propagation
- `rate_limit.py` - Redis-based rate limiting
- `security_headers.py` - Security headers middleware

## Future Use

This directory may be used in the future for:

- Core infrastructure middleware (non-API specific)
- Database connection middleware
- Metrics collection middleware
- Request timing middleware

## Related Documentation

- `/backend/api/middleware/AGENTS.md` - Active API middleware documentation
- `/backend/core/AGENTS.md` - Core infrastructure overview
