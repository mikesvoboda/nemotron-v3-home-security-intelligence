# API Documentation Directory - Agent Guide

## Purpose

This directory contains API governance documentation including deprecation policies, migration guides, and versioning standards. It complements the `docs/developer/api/` directory which contains endpoint-specific documentation.

## Directory Structure

```
docs/api/
  AGENTS.md                    # This file - directory guide
  DEPRECATION_POLICY.md        # Deprecation timeline, headers, tombstones, migration template
  analytics-endpoints.md       # /api/analytics reference + baseline configuration routes
  migrations/                  # Migration guides for deprecated endpoints
```

## Files

| File                     | Purpose                                                      |
| ------------------------ | ------------------------------------------------------------ |
| `DEPRECATION_POLICY.md`  | How to deprecate an endpoint, and what the backend enforces  |
| `analytics-endpoints.md` | Analytics API plus the per-camera baseline configuration API |

## Key Directories

| Directory     | Purpose                                       |
| ------------- | --------------------------------------------- |
| `migrations/` | Migration guides for deprecated API endpoints |

## When to Use This Directory

- **Creating a migration guide**: Place in `migrations/`
- **Adding new API governance docs**: Place standards documents here
- **API endpoint documentation**: See `docs/developer/api/` for endpoint docs

## Related Documentation

- `docs/developer/api/` - Endpoint-specific API documentation
- `docs/developer/api/README.md` - API overview and conventions
- `docs/architecture/api-reference/cameras-api.md` - Cameras API with RTSP/ONVIF documentation
- `CHANGELOG.md` - Project change history (deprecation entries go here)

## Entry Points

1. **API endpoint docs**: See `docs/developer/api/` for complete API documentation
2. **Cameras API**: See `docs/architecture/api-reference/cameras-api.md` for camera management including RTSP/ONVIF
3. **Migration guides**: `migrations/` for endpoint-specific upgrade instructions
4. **OpenAPI spec**: `docs/openapi.json` for machine-readable API specification
