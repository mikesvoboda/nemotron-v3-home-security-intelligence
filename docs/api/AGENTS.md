# API Documentation Directory - Agent Guide

## Purpose

This directory contains API governance documentation including deprecation policies, migration guides, and versioning standards. It complements the `docs/developer/api/` directory which contains endpoint-specific documentation.

## Directory Structure

```
docs/api/
  AGENTS.md                    # This file - directory guide
  migrations/                  # Migration guides for deprecated endpoints
```

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
- `CHANGELOG.md` - Project change history (deprecation entries go here)

## Entry Points

1. **API endpoint docs**: See `docs/developer/api/` for complete API documentation
2. **Migration guides**: `migrations/` for endpoint-specific upgrade instructions
3. **OpenAPI spec**: `docs/openapi.json` for machine-readable API specification
