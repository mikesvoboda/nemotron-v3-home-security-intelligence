# Frontend Types Directory

## Purpose

TypeScript type definitions for the frontend application. Contains auto-generated API types from the backend OpenAPI specification and any custom type definitions.

## Directory Structure

```
frontend/src/types/
├── AGENTS.md           # This documentation file
└── generated/          # Auto-generated types from backend OpenAPI
    ├── AGENTS.md       # Generated types documentation
    ├── api.ts          # Full OpenAPI-generated types (4133 lines)
    └── index.ts        # Re-exports with convenient type aliases
```

## Generated Types

All API types are auto-generated from the backend FastAPI OpenAPI specification using `openapi-typescript`. Do NOT manually edit files in `generated/`.

### Regenerating Types

```bash
# From project root
./scripts/generate-types.sh           # Generate types
./scripts/generate-types.sh --check   # Check if types are current (CI)
```

The script:

1. Extracts OpenAPI spec from FastAPI backend
2. Runs `openapi-typescript` to generate TypeScript types
3. Outputs to `frontend/src/types/generated/api.ts`

## Using Generated Types

Import from the re-export module for convenient access:

```typescript
import type { Camera, Event, GPUStats, SystemConfig } from '@/types/generated';
```

Or import the raw OpenAPI types:

```typescript
import type { paths, components, operations } from '@/types/generated/api';
```

## Coverage Exclusion

Generated types are excluded from test coverage (see `vite.config.ts`):

```typescript
coverage: {
  exclude: ['src/types/generated/**'],
}
```

## Related Files

- `/scripts/generate-types.sh` - Type generation script
- `/backend/api/schemas/` - Backend Pydantic schemas (source of truth)

## Notes for AI Agents

- Never manually edit files in `generated/`
- Regenerate types after backend schema changes
- Use `index.ts` re-exports for cleaner imports
- Types are excluded from test coverage
- CI runs `--check` mode to ensure types are current

## Entry Points

1. **Start with `generated/index.ts`** - Convenient type aliases matching backend schemas
2. **Raw types**: `generated/api.ts` contains full OpenAPI types (paths, components, operations)
3. **Import pattern**: `import type { Camera, Event } from '@/types/generated'`
