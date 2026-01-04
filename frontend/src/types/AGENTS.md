# Frontend Types Directory

## Purpose

TypeScript type definitions for the frontend application. Contains auto-generated API types from the backend OpenAPI specification. All types are generated from backend Pydantic schemas.

## Directory Structure

```
frontend/src/types/
├── AGENTS.md           # This documentation file
├── performance.ts      # Performance metrics type definitions
└── generated/          # Auto-generated types from backend OpenAPI
    ├── AGENTS.md       # Generated types documentation
    ├── api.ts          # Full OpenAPI-generated types
    └── index.ts        # Re-exports with convenient type aliases
```

## Key Files

| File             | Purpose                                                        |
| ---------------- | -------------------------------------------------------------- |
| `performance.ts` | Performance alert and AI model metrics types                   |
| `enrichment.ts`  | Detection enrichment types (vehicle, pet, person, weather)     |
| `generated/`     | Auto-generated types from backend OpenAPI spec                 |

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
