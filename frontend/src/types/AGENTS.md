# Frontend Types Directory

## Purpose

TypeScript type definitions for the frontend application. Contains:
- Advanced type utilities (branded types, discriminated unions, type guards)
- Auto-generated API types from the backend OpenAPI specification
- Domain-specific types for AI enrichment, performance metrics, and WebSocket messages

## Directory Structure

```
frontend/src/types/
├── AGENTS.md               # This documentation file
├── index.ts                # Centralized exports for all types
├── aiAudit.ts              # AI audit trail and decision types
├── api-endpoints.ts        # API endpoint type definitions
├── api-endpoints.test.ts   # Tests for API endpoint types
├── async.ts                # Async state management types
├── async.test.ts           # Tests for async types
├── branded.ts              # Branded types for entity IDs (type-safe)
├── branded.test.ts         # Tests for branded types
├── constants.ts            # Type-safe constants with const assertions
├── constants.test.ts       # Tests for constants
├── enrichment.ts           # Detection enrichment types with guards
├── enrichment.test.ts      # Tests for enrichment types
├── export.ts               # Export functionality types
├── guards.ts               # Type guards for runtime type checking
├── guards.test.ts          # Tests for type guards
├── notificationPreferences.ts # Notification preference types
├── performance.ts          # Performance metrics type definitions
├── promptManagement.ts     # Prompt management types
├── rate-limit.ts           # Rate limiting types
├── rate-limit.test.ts      # Tests for rate limit types
├── result.ts               # Result/Either monad types
├── result.test.ts          # Tests for result types
├── websocket.ts            # Discriminated unions for WebSocket messages
├── websocket.test.ts       # Tests for WebSocket types
├── websocket-events.ts     # WebSocket event type definitions
├── websocket-events.test.ts # Tests for WebSocket event types
└── generated/              # Auto-generated types from backend OpenAPI
    ├── AGENTS.md           # Generated types documentation
    ├── api.ts              # Full OpenAPI-generated types
    └── index.ts            # Re-exports with convenient type aliases
```

## Key Files

| File                        | Purpose                                                    |
| --------------------------- | ---------------------------------------------------------- |
| `index.ts`                  | Centralized exports for all types                          |
| `aiAudit.ts`                | AI audit trail, decision logging types                     |
| `analytics.ts`              | Analytics data types                                       |
| `api-endpoints.ts`          | API endpoint definitions and request/response types        |
| `async.ts`                  | AsyncState types for loading/error/success state management|
| `branded.ts`                | Branded types for CameraId, EventId, DetectionId, etc.     |
| `constants.ts`              | Type-safe constants (risk levels, health status, etc.)     |
| `enrichment.ts`             | Detection enrichment types (vehicle, pet, person, weather) |
| `export.ts`                 | Event export types (CSV, JSON formats)                     |
| `guards.ts`                 | Type guards for runtime type validation                    |
| `notificationPreferences.ts`| Notification channel and preference types                  |
| `performance.ts`            | Performance alert and AI model metrics types               |
| `promptManagement.ts`       | Prompt template and version types                          |
| `rate-limit.ts`             | Rate limiting state and response types                     |
| `result.ts`                 | Result/Either monad for error handling                     |
| `summary.ts`                | AI summary data types                                      |
| `websocket.ts`              | Discriminated unions for WebSocket message handling        |
| `websocket-events.ts`       | WebSocket event payloads and handlers                      |
| `generated/`                | Auto-generated types from backend OpenAPI spec             |

## Type System Patterns

### Branded Types (`branded.ts`)

Branded types prevent accidentally mixing different ID types:

```typescript
import { createCameraId, createEventId, type CameraId } from '../types';

// These are different types even though both are strings/numbers
const cameraId: CameraId = createCameraId('abc-123');
const eventId = createEventId(456);

// TypeScript error: CameraId is not assignable to EventId
fetchEvent(cameraId); // Error!
```

### Discriminated Unions (`websocket.ts`)

Use the `type` field as discriminant for type narrowing:

```typescript
import { type WebSocketMessage } from '../types';

function handleMessage(message: WebSocketMessage) {
  switch (message.type) {
    case 'event':
      console.log(message.data.risk_score); // TypeScript knows the type
      break;
    case 'system_status':
      console.log(message.data.gpu.utilization);
      break;
  }
}
```

### Async State (`async.ts`)

Type-safe state management for async operations:

```typescript
import { idle, loading, success, failure, matchState, type AsyncState } from '../types';

const [state, setState] = useState<AsyncState<Event[]>>(idle());

// Pattern matching with exhaustive handling
return matchState(state, {
  idle: () => <EmptyState />,
  loading: (prev) => prev ? <EventList events={prev} loading /> : <Spinner />,
  error: (err, retry) => <ErrorMessage error={err} onRetry={retry} />,
  success: (data) => <EventList events={data} />,
});
```

### Type Guards (`guards.ts`)

Replace unsafe `as` casts with runtime type validation:

```typescript
import { isPlainObject, hasPropertyOfType, isNumber } from '../types';

function processData(data: unknown) {
  if (isPlainObject(data) && hasPropertyOfType(data, 'id', isNumber)) {
    console.log(data.id); // TypeScript knows data.id is number
  }
}
```

### Constants (`constants.ts`)

Type-safe constants with exhaustiveness checking:

```typescript
import { RISK_LEVELS, isRiskLevel, assertNever, type RiskLevel } from '../types';

function getRiskColor(level: RiskLevel): string {
  switch (level) {
    case 'low': return 'green';
    case 'medium': return 'yellow';
    case 'high': return 'orange';
    case 'critical': return 'red';
    default: return assertNever(level); // TypeScript error if case is missing
  }
}
```

## Performance Types (`performance.ts`)

Manual type definitions for the System Performance Dashboard. These types correspond to backend schemas in `backend/api/schemas/performance.py`.

```typescript
// Performance alert for threshold breaches
interface PerformanceAlert {
  severity: 'warning' | 'critical';
  metric: string;
  value: number;
  threshold: number;
  message: string;
}

// RT-DETRv2 object detection model metrics
interface AiModelMetrics {
  status: string;
  vram_gb: number;
  model: string;
  device: string;
}

// Nemotron LLM model metrics
interface NemotronMetrics {
  status: string;
  slots_active: number;
  slots_total: number;
  context_size: number;
}

// Time range options for historical metrics
type TimeRange = '5m' | '15m' | '60m';
```

**Note:** These types are manually maintained (not auto-generated) because they support the real-time WebSocket performance monitoring feature.

## Enrichment Types (`enrichment.ts`)

Manual type definitions for AI-powered detection enrichment data. These types represent additional AI analysis computed by the backend enrichment pipeline.

```typescript
// Vehicle classification
interface VehicleEnrichment {
  type: string;       // sedan, SUV, pickup, van, truck
  color: string;
  damage?: string[];  // cracks, dents, glass_shatter, etc.
  commercial?: boolean;
  confidence: number;
}

// Pet identification
interface PetEnrichment {
  type: 'cat' | 'dog';
  breed?: string;
  confidence: number;
}

// Person attributes
interface PersonEnrichment {
  clothing?: string;
  action?: string;           // walking, standing, crouching
  carrying?: string;         // backpack, package
  suspicious_attire?: boolean;
  service_uniform?: boolean;
  confidence: number;
}

// Additional enrichment types
interface LicensePlateEnrichment { text: string; confidence: number; }
interface WeatherEnrichment { condition: string; confidence: number; }
interface ImageQualityEnrichment { score: number; issues: string[]; }

// Combined enrichment data (all fields optional)
interface EnrichmentData {
  vehicle?: VehicleEnrichment;
  pet?: PetEnrichment;
  person?: PersonEnrichment;
  license_plate?: LicensePlateEnrichment;
  weather?: WeatherEnrichment;
  image_quality?: ImageQualityEnrichment;
}
```

**Note:** These types correspond to backend `backend/services/enrichment_service.py`.

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
