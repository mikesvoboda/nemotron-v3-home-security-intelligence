# Frontend Scripts - Agent Guide

## Purpose

This directory contains build-time and development scripts specific to the frontend application. These scripts handle code generation, build validation, and type synchronization between the frontend and backend.

## Directory Contents

```
frontend/scripts/
  AGENTS.md                    # This file
  generate-ws-types.py         # Generate TypeScript types from backend WebSocket schemas
  validate-build-chunks.ts     # Validate production build chunks for circular dependencies
```

## Key Files

### generate-ws-types.py

**Purpose:** Generates TypeScript types from backend Pydantic WebSocket schemas. This ensures the frontend stays in sync with the backend WebSocket message contracts, which are not covered by OpenAPI.

**What It Generates:**
- Enum types (RiskLevel, WebSocketMessageType, WebSocketServiceStatus, etc.)
- Data payload interfaces (WebSocketEventData, WebSocketAlertData, etc.)
- Message envelope interfaces (WebSocketEventMessage, WebSocketPingMessage, etc.)
- Discriminated union types (WebSocketServerMessage, WebSocketClientMessage)
- Type guard functions (isEventMessage, isAlertMessage, etc.)
- Helper utilities (createMessageDispatcher, assertNever)

**Output File:** `frontend/src/types/generated/websocket.ts`

**Usage:**
```bash
# Generate types
./scripts/generate-ws-types.py

# Check if types are current (for CI)
./scripts/generate-ws-types.py --check

# From project root
python frontend/scripts/generate-ws-types.py
```

**Source Schemas:** `backend/api/schemas/websocket.py`

**Type Mapping:**
| Python Type | TypeScript Type |
|-------------|-----------------|
| `str` | `string` |
| `int`, `float` | `number` |
| `bool` | `boolean` |
| `list[T]` | `T[]` |
| `dict[K, V]` | `Record<K, V>` |
| `Optional[T]` | `T \| null` |
| `Literal[...]` | Union of string literals |
| `Enum` | Union of enum values |
| Pydantic BaseModel | TypeScript interface |

**Generated Type Guards:**
```typescript
// Example usage of generated type guards
if (isEventMessage(message)) {
  // message is narrowed to WebSocketEventMessage
  console.log(message.data.risk_score);
}

if (isAlertCreatedMessage(message)) {
  // message is narrowed to WebSocketAlertCreatedMessage
  console.log(message.data.severity);
}
```

### validate-build-chunks.ts

**Purpose:** Analyzes production build chunks for circular dependency patterns that could cause TDZ (Temporal Dead Zone) errors at runtime. This script was created after NEM-3494 where circular import deadlocks between vendor chunks caused production errors.

**What It Detects:**
1. **Self-referencing variable initialization**: `var x = _interopDefault(x)` (TDZ risk)
2. **Circular module initialization patterns**: Functions returning and assigning to the same module
3. **Excessive imports from same module**: >10 imports from one module (possible chunk duplication)
4. **Large chunks**: Files >500KB that may need splitting

**Usage:**
```bash
# Build first, then validate
npm run build
npm run validate:build-chunks

# Or via npx
npx tsx scripts/validate-build-chunks.ts
```

**Exit Codes:**
| Code | Meaning |
|------|---------|
| 0 | No issues detected - safe for deployment |
| 1 | Circular dependency patterns detected |
| 2 | Build directory not found |

**Output:**
```
=== Chunk Analysis Summary ===
Total chunks: 15
Chunks analyzed: 15

Interop helper usage:
  _interopNamespaceDefault: 3 occurrences

Large chunks (>500KB):
  vendor-react.js: 523.45 KB

OK: No circular dependency patterns detected
   Build chunks are safe for production deployment.
```

**Analyzed Patterns:**
- Rollup interop helpers (`_interopNamespaceDefault`, `_interopRequireDefault`)
- Self-referencing patterns in variable declarations
- Circular function initialization
- Import count analysis per module

## Integration Points

### CI Pipeline

Both scripts integrate with CI:

```yaml
# Type generation check
- run: python frontend/scripts/generate-ws-types.py --check

# Build chunk validation (after build step)
- run: npm run build
- run: npm run validate:build-chunks
```

### npm Scripts

From `frontend/package.json`:

```json
{
  "scripts": {
    "validate:build-chunks": "npx tsx scripts/validate-build-chunks.ts"
  }
}
```

## Related Files

| File | Purpose |
|------|---------|
| `backend/api/schemas/websocket.py` | Source Pydantic schemas for WebSocket types |
| `frontend/src/types/generated/websocket.ts` | Generated TypeScript types output |
| `frontend/vite.config.ts` | Vite build configuration with chunk splitting |
| `scripts/generate-ws-types.py` | Root-level symlink (optional) |

## Dependencies

### generate-ws-types.py
- Python 3.11+
- Backend dependencies available (for importing Pydantic schemas)
- Environment variables: `DATABASE_URL`, `REDIS_URL` (can be dummy values)

### validate-build-chunks.ts
- Node.js 22+
- TypeScript (tsx for execution)
- Production build output (run `npm run build` first to generate the dist folder)

## Notes for AI Agents

- **WebSocket types are separate from OpenAPI**: The `generate-ws-types.py` script exists because WebSocket messages are not covered by OpenAPI specification. REST API types are generated separately via `npm run generate-types`.

- **Run after backend schema changes**: When modifying `backend/api/schemas/websocket.py`, regenerate types with `./scripts/generate-ws-types.py` and commit the updated `websocket.ts`.

- **Build chunk validation is informational**: The script catches potential issues but doesn't automatically fix them. Review `vite.config.ts` rollupOptions if issues are detected.

- **CI gates**: Both scripts run in CI - type check failures block PRs, chunk validation provides warnings for review.
