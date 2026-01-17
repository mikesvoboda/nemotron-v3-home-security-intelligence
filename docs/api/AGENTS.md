# API Documentation Directory - Agent Guide

## Purpose

This directory contains API governance documentation including deprecation policies, migration guides, and versioning standards. It complements the `docs/api-reference/` directory which contains endpoint-specific documentation.

## Directory Structure

```
docs/api/
  AGENTS.md                    # This file - directory guide
  DEPRECATION_POLICY.md        # API deprecation process and standards
  migrations/                  # Migration guides for deprecated endpoints
    README.md                  # Migration guide template and index
```

## Key Documents

| Document                | Purpose                                                                                                    |
| ----------------------- | ---------------------------------------------------------------------------------------------------------- |
| `DEPRECATION_POLICY.md` | Complete API deprecation process: timeline, OpenAPI extensions, changelog format, migration guide template |

## When to Use This Directory

- **Deprecating an endpoint**: Follow the process in `DEPRECATION_POLICY.md`
- **Creating a migration guide**: Use the template and place in `migrations/`
- **Adding new API governance docs**: Place standards documents here

## Related Documentation

- `docs/api-reference/` - Endpoint-specific API documentation
- `docs/api-reference/overview.md` - API overview and conventions
- `CHANGELOG.md` - Project change history (deprecation entries go here)

## Entry Points

1. **Start here**: `DEPRECATION_POLICY.md` for the complete deprecation process
2. **Migration guides**: `migrations/` for endpoint-specific upgrade instructions
