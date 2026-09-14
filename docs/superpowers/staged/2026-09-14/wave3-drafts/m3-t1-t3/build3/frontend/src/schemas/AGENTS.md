# Schemas Directory - AI Agent Guide

## Purpose

This directory contains Zod validation schemas that mirror backend Pydantic models. These schemas provide:

1. **Client-side form validation** matching server-side rules exactly
2. **API response validation** for runtime type checking
3. **Reusable primitives** for consistent validation patterns

## Key Files

| File                  | Purpose                                           | Lines |
| --------------------- | ------------------------------------------------- | ----- |
| `index.ts`            | Re-exports all schemas for convenient imports     | ~250  |
| `primitives.ts`       | Reusable schema primitives (IDs, scores, etc.)    | ~350  |
| `primitives.test.ts`  | Tests for schema primitives                       | ~500  |
| `camera.ts`           | Camera CRUD validation schemas                    | ~178  |
| `camera.test.ts`      | Tests for camera validation                       | ~250  |
| `alertRule.ts`        | Alert rule validation schemas                     | ~331  |
| `alertRule.test.ts`   | Tests for alert rule validation                   | ~690  |
| `api.ts`              | API response validation schemas                   | ~500  |
| `api.test.ts`         | Tests for API response validation                 | ~600  |
| `alert.ts`            | Alert-related schemas (placeholder)               | ~1    |

## Architecture

```
schemas/
  |-- primitives.ts     # Base building blocks (IDs, scores, timestamps)
  |-- camera.ts         # Form validation (uses primitives)
  |-- alertRule.ts      # Form validation (uses primitives)
  |-- api.ts            # API response validation (uses primitives)
  |-- index.ts          # Central exports
```

## Key Exports

### primitives.ts (NEM-3819)

Reusable schema primitives for consistency across all schemas.

#### ID Primitives

| Export          | Description                              |
| --------------- | ---------------------------------------- |
| `uuid`          | Generic UUID validator                   |
| `cameraId`      | Camera ID (UUID)                         |
| `eventId`       | Event ID (UUID)                          |
| `detectionId`   | Detection ID (UUID)                      |
| `zoneId`        | Zone ID (UUID)                           |
| `alertRuleId`   | Alert Rule ID (UUID)                     |
| `entityId`      | Entity ID (UUID)                         |
| `batchId`       | Batch ID (UUID)                          |

#### Risk Assessment Primitives

| Export              | Description                              |
| ------------------- | ---------------------------------------- |
| `riskScore`         | Integer 0-100                            |
| `optionalRiskScore` | Nullable risk score                      |
| `riskLevel`         | Enum: low, medium, high, critical        |
| `optionalRiskLevel` | Nullable risk level                      |
| `confidence`        | Float 0-1                                |
| `optionalConfidence`| Nullable confidence                      |

#### Timestamp Primitives

| Export              | Description                              |
| ------------------- | ---------------------------------------- |
| `timestamp`         | Coerces to Date (accepts ISO, Date, ms)  |
| `optionalTimestamp` | Nullable timestamp                       |
| `isoDateString`     | Validates ISO 8601 format                |
| `timeString`        | Validates HH:MM format                   |

#### Enum Primitives

| Export              | Values                                   |
| ------------------- | ---------------------------------------- |
| `objectType`        | person, vehicle, animal, package         |
| `cameraStatus`      | online, offline, error, unknown          |
| `alertSeverity`     | low, medium, high, critical              |
| `dayOfWeek`         | monday...sunday                          |

#### Utility Primitives

| Export                  | Description                          |
| ----------------------- | ------------------------------------ |
| `boundingBox`           | Tuple [x1, y1, x2, y2] (0-1)         |
| `pageNumber`            | Integer >= 1                         |
| `pageSize`              | Integer 1-100                        |
| `totalCount`            | Non-negative integer                 |
| `nonEmptyString`        | String with min length 1             |
| `stringWithLength()`    | Factory for constrained strings      |

### api.ts (NEM-3824)

API response validation schemas for runtime type checking.

#### Response Schemas

| Export                    | Backend Model                        |
| ------------------------- | ------------------------------------ |
| `cameraResponseSchema`    | CameraResponse                       |
| `cameraListResponseSchema`| CameraListResponse                   |
| `detectionResponseSchema` | DetectionResponse                    |
| `eventResponseSchema`     | EventResponse                        |
| `eventListResponseSchema` | EventListResponse                    |
| `alertRuleResponseSchema` | AlertRuleResponse                    |
| `alertResponseSchema`     | AlertResponse                        |
| `zoneResponseSchema`      | ZoneResponse                         |
| `entityResponseSchema`    | EntityResponse                       |
| `healthResponseSchema`    | HealthResponse                       |
| `gpuStatsResponseSchema`  | GPUStatsResponse                     |

#### Helper Functions

| Export                    | Purpose                              |
| ------------------------- | ------------------------------------ |
| `paginatedResponse()`     | Creates paginated response schema    |
| `cursorPaginatedResponse()`| Creates cursor-paginated schema     |
| `parseApiResponse()`      | Parse and validate, throws on error  |
| `safeParseApiResponse()`  | Parse and validate, returns null     |

### camera.ts

Camera form validation schemas.

| Export               | Purpose                                    |
| -------------------- | ------------------------------------------ |
| `cameraStatusSchema` | Validates camera status enum               |
| `cameraNameSchema`   | Validates camera name (length, trim)       |
| `cameraFolderPathSchema` | Validates folder path (security checks)|
| `cameraCreateSchema` | Full schema for camera creation            |
| `cameraUpdateSchema` | Partial schema for camera updates          |
| `cameraFormSchema`   | Form-specific schema with required fields  |

### alertRule.ts

Alert rule form validation schemas.

| Export                    | Purpose                                |
| ------------------------- | -------------------------------------- |
| `alertSeveritySchema`     | Validates severity enum                |
| `riskThresholdSchema`     | Validates risk threshold (0-100)       |
| `minConfidenceSchema`     | Validates confidence (0.0-1.0)         |
| `cooldownSecondsSchema`   | Validates cooldown (non-negative)      |
| `timeStringSchema`        | Validates HH:MM time format            |
| `alertRuleCreateSchema`   | Full schema for rule creation          |
| `alertRuleUpdateSchema`   | Partial schema for rule updates        |
| `alertRuleFormSchema`     | Form-specific schema with defaults     |

## Usage Patterns

### Using Primitives

```typescript
import { cameraId, riskScore, riskLevel, timestamp } from '@/schemas';

// Build custom schemas with primitives
const eventSchema = z.object({
  camera_id: cameraId,
  risk_score: riskScore,
  risk_level: riskLevel,
  started_at: timestamp
});
```

### API Response Validation

```typescript
import { eventResponseSchema, parseApiResponse } from '@/schemas';

// Validate API response with runtime type checking
export async function getEvent(id: string): Promise<EventResponse> {
  const response = await fetch(`/api/events/${id}`);
  const data = await response.json();
  return parseApiResponse(eventResponseSchema, data, 'getEvent');
}

// Or use safe parsing that returns null on failure
const event = safeParseApiResponse(eventResponseSchema, data);
if (!event) {
  console.error('Invalid event data');
}
```

### Form Validation with React Hook Form

```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { cameraFormSchema, CameraFormInput } from '@/schemas';

function CameraForm() {
  const { register, handleSubmit, formState: { errors } } = useForm<CameraFormInput>({
    resolver: zodResolver(cameraFormSchema),
    defaultValues: {
      name: '',
      folder_path: '',
      status: 'online',
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('name')} />
      {errors.name && <span>{errors.name.message}</span>}
    </form>
  );
}
```

### Type Extraction

```typescript
import { z } from 'zod';
import { alertRuleCreateSchema } from '@/schemas';

// Extract types from schema
type AlertRuleCreate = z.infer<typeof alertRuleCreateSchema>;

// Or use the pre-exported types
import type { AlertRuleCreateOutput } from '@/schemas';
```

## Zod 4 Error Parameter Syntax (NEM-3818)

This codebase uses Zod 4's `{error:}` parameter for custom error messages:

```typescript
// Zod 4 syntax (what we use)
z.string().min(1, { error: 'Required' })
z.number().int({ error: 'Must be a whole number' })

// Dynamic error messages with function
z.string().min(5, { error: (issue) => `Min length is ${issue.minimum}` })
```

**DO NOT** use the old `{message:}` syntax.

## Backend Schema Alignment

**IMPORTANT**: These schemas must match the backend Pydantic schemas exactly.

### Backend Schema Locations

| Frontend Schema            | Backend Schema Location            |
| -------------------------- | ---------------------------------- |
| `cameraCreateSchema`       | `backend/api/schemas/camera.py`    |
| `cameraResponseSchema`     | `backend/api/schemas/camera.py`    |
| `alertRuleCreateSchema`    | `backend/api/schemas/alerts.py`    |
| `alertRuleResponseSchema`  | `backend/api/schemas/alerts.py`    |
| `eventResponseSchema`      | `backend/api/schemas/events.py`    |
| `detectionResponseSchema`  | `backend/api/schemas/detections.py`|
| `zoneResponseSchema`       | `backend/api/schemas/zone.py`      |

### Validation Rules Mapping

| Frontend Zod             | Backend Pydantic           | Example            |
| ------------------------ | -------------------------- | ------------------ |
| `.min(n)`                | `min_length=n`             | Name min length    |
| `.max(n)`                | `max_length=n`             | Name max length    |
| `.int().min(0).max(100)` | `ge=0, le=100`             | Risk threshold     |
| `.superRefine()`         | `@field_validator`         | Custom validation  |
| `.default()`             | `Field(default=...)`       | Default values     |
| `z.coerce.date()`        | `datetime`                 | Timestamp fields   |

### When to Update

Update frontend schemas when:

1. Backend Pydantic schema changes
2. Validation rules are modified
3. New fields are added
4. Field constraints change

Always run validation tests after backend changes:

```bash
cd frontend && npm test src/schemas/
```

## Security Validations

### Folder Path Security (camera.ts)

The `cameraFolderPathSchema` includes security validations:

1. **Path Traversal Prevention**: Rejects paths containing `..`
2. **Forbidden Characters**: Rejects `< > : " | ? *` and control characters
3. **Length Limits**: Max 500 characters

These match backend `_validate_folder_path()` exactly.

### Time Format Validation

The `timeStringSchema` validates HH:MM format:

1. **Pattern Match**: Must be `\d{2}:\d{2}`
2. **Hour Range**: 00-23
3. **Minute Range**: 00-59

This matches backend `validate_time_format()` exactly.

## Notes for AI Agents

- **Backend is authoritative**: Frontend schemas provide UX feedback; backend validates
- **Keep in sync**: Update frontend when backend schemas change
- **Use primitives**: Always use primitives from `primitives.ts` for common types
- **Use exported types**: Prefer `CameraFormInput` over `z.infer<typeof ...>`
- **Validate API responses**: Use `parseApiResponse()` for runtime validation
- **Test validation**: Always test edge cases for custom validators
- **Form defaults**: Use `*FormSchema` variants for forms with sensible defaults
- **Partial updates**: Use `*UpdateSchema` for PATCH requests with optional fields
- **Transform data**: Use `.transform()` for data normalization (trim, lowercase)
- **Error syntax**: Use `{error:}` not `{message:}` for Zod 4 compatibility
