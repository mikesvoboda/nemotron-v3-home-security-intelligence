---
title: Validation Alignment Guide
source_refs:
  - backend/api/schemas/AGENTS.md:1
  - backend/api/schemas/camera.py:1
  - frontend/src/schemas/camera.ts:1
  - frontend/src/schemas/camera.test.ts:1
  - frontend/src/hooks/useFormWithApiErrors.ts:1
---

# Validation Alignment Guide

This document describes how to keep frontend Zod validation schemas aligned with backend Pydantic schemas, ensuring consistent validation rules across the full stack.

## Overview

The project uses a dual-layer validation strategy:

| Layer    | Technology | Location                | Purpose                        |
| -------- | ---------- | ----------------------- | ------------------------------ |
| Backend  | Pydantic   | `backend/api/schemas/`  | Authoritative validation rules |
| Frontend | Zod        | `frontend/src/schemas/` | Client-side validation for UX  |

**Key Principle:** Backend Pydantic schemas are the source of truth. Frontend Zod schemas provide early validation feedback to users but must match backend rules exactly.

## Why Validation Alignment Matters

1. **Consistent User Experience** - Users see the same validation errors regardless of whether they come from client or server
2. **Reduced API Calls** - Client-side validation catches errors before submission
3. **Maintainability** - A single source of truth prevents rule drift
4. **Security** - Backend always validates; frontend validation is UX enhancement only

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Input                               │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend Zod Schema (frontend/src/schemas/*.ts)                │
│  - Immediate validation feedback                                 │
│  - Matches backend constraints exactly                          │
│  - Used with react-hook-form via zodResolver                    │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼ (if valid)
┌─────────────────────────────────────────────────────────────────┐
│  Backend Pydantic Schema (backend/api/schemas/*.py)             │
│  - Authoritative validation                                      │
│  - Returns 422 with field errors if invalid                     │
│  - useFormWithApiErrors maps server errors to form fields       │
└─────────────────────────────────────────────────────────────────┘
```

## Adding a New Validated Form

Follow these steps to add frontend validation that matches a backend schema.

### Step 1: Identify the Backend Schema

Find the Pydantic schema in `backend/api/schemas/`. For example, `camera.py`:

```python
# backend/api/schemas/camera.py
class CameraCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Camera name")
    folder_path: str = Field(
        ..., min_length=1, max_length=500, description="File system path"
    )
    status: CameraStatus = Field(
        default=CameraStatus.ONLINE,
        description="Camera status"
    )

    @field_validator("folder_path")
    @classmethod
    def validate_folder_path(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("Path traversal (..) not allowed")
        return v
```

### Step 2: Create the Zod Schema File

Create a corresponding file in `frontend/src/schemas/`. Use the naming convention `{resource}.ts`:

```typescript
// frontend/src/schemas/camera.ts
import { z } from 'zod';

// Document constraints from backend
export const CAMERA_NAME_CONSTRAINTS = {
  minLength: 1,
  maxLength: 255,
} as const;

export const CAMERA_FOLDER_PATH_CONSTRAINTS = {
  minLength: 1,
  maxLength: 500,
} as const;

// Document enum values from backend
export const CAMERA_STATUS_VALUES = ['online', 'offline', 'error', 'unknown'] as const;
```

### Step 3: Create Individual Field Schemas

Mirror each Pydantic field with a Zod schema:

```typescript
// Camera name - matches backend Field(min_length=1, max_length=255)
export const cameraNameSchema = z
  .string()
  .min(CAMERA_NAME_CONSTRAINTS.minLength, { message: 'Name is required' })
  .max(CAMERA_NAME_CONSTRAINTS.maxLength, {
    message: `Name must be at most ${CAMERA_NAME_CONSTRAINTS.maxLength} characters`,
  })
  .transform((val) => val.trim());

// Camera folder path - matches backend Field + custom validator
export const cameraFolderPathSchema = z
  .string()
  .min(CAMERA_FOLDER_PATH_CONSTRAINTS.minLength, { message: 'Folder path is required' })
  .max(CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength, {
    message: `Folder path must be at most ${CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength} characters`,
  })
  .superRefine((val, ctx) => {
    // Match backend _validate_folder_path() validator
    if (val.includes('..')) {
      ctx.addIssue({
        code: 'custom',
        message: 'Path traversal (..) is not allowed in folder path',
      });
    }
  });

// Camera status - matches backend CameraStatus enum
export const cameraStatusSchema = z.enum(CAMERA_STATUS_VALUES, {
  error: 'Invalid camera status. Must be: online, offline, error, or unknown',
});
```

### Step 4: Compose the Object Schema

Combine field schemas into the full form schema:

```typescript
// Matches backend CameraCreate
export const cameraCreateSchema = z.object({
  name: cameraNameSchema,
  folder_path: cameraFolderPathSchema,
  status: cameraStatusSchema.default('online'),
});

// Matches backend CameraUpdate (all optional for partial updates)
export const cameraUpdateSchema = z.object({
  name: cameraNameSchema.optional(),
  folder_path: cameraFolderPathSchema.optional(),
  status: cameraStatusSchema.optional(),
});

// Export types
export type CameraCreateInput = z.input<typeof cameraCreateSchema>;
export type CameraCreateOutput = z.output<typeof cameraCreateSchema>;
```

### Step 5: Export from Index

Add the export to `frontend/src/schemas/index.ts`:

```typescript
export * from './camera';
```

### Step 6: Write Alignment Tests

Create a test file `frontend/src/schemas/{resource}.test.ts` that verifies alignment:

```typescript
// frontend/src/schemas/camera.test.ts
import { describe, expect, it } from 'vitest';
import {
  cameraCreateSchema,
  CAMERA_NAME_CONSTRAINTS,
  CAMERA_FOLDER_PATH_CONSTRAINTS,
  CAMERA_STATUS_VALUES,
} from './camera';

describe('Camera Zod Schemas', () => {
  describe('Constants alignment with backend', () => {
    it('should have correct name constraints (backend min_length=1, max_length=255)', () => {
      expect(CAMERA_NAME_CONSTRAINTS.minLength).toBe(1);
      expect(CAMERA_NAME_CONSTRAINTS.maxLength).toBe(255);
    });

    it('should have correct folder path constraints (backend min_length=1, max_length=500)', () => {
      expect(CAMERA_FOLDER_PATH_CONSTRAINTS.minLength).toBe(1);
      expect(CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength).toBe(500);
    });

    it('should have all status values matching backend CameraStatus enum', () => {
      // Must match backend/models/enums.py CameraStatus values
      expect(CAMERA_STATUS_VALUES).toEqual(['online', 'offline', 'error', 'unknown']);
    });
  });

  describe('cameraCreateSchema', () => {
    it('should reject path traversal attempts (matches backend validator)', () => {
      const result = cameraCreateSchema.safeParse({
        name: 'Test',
        folder_path: '/export/../etc/passwd',
      });
      expect(result.success).toBe(false);
    });
  });
});
```

### Step 7: Use in Forms with react-hook-form

Integrate the schema into your form component:

```tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { cameraCreateSchema, CameraCreateInput } from '@/schemas';
import { useApiMutation } from '@/hooks/useFormWithApiErrors';

function CameraForm() {
  const form = useForm<CameraCreateInput>({
    resolver: zodResolver(cameraCreateSchema),
    defaultValues: {
      name: '',
      folder_path: '',
      status: 'online',
    },
  });

  const mutation = useApiMutation({
    mutationFn: (data) => api.cameras.create(data),
    form,
    onSuccess: () => {
      // Handle success
    },
  });

  return (
    <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
      <input {...form.register('name')} />
      {form.formState.errors.name && (
        <span className="text-red-500">{form.formState.errors.name.message}</span>
      )}
      {/* ... other fields ... */}
    </form>
  );
}
```

## Pydantic to Zod Type Mapping

Use this reference when translating Pydantic fields to Zod schemas.

### Basic Types

| Pydantic Type      | Zod Schema                      | Notes                     |
| ------------------ | ------------------------------- | ------------------------- |
| `str`              | `z.string()`                    |                           |
| `int`              | `z.number().int()`              | Add `.int()` for integers |
| `float`            | `z.number()`                    |                           |
| `bool`             | `z.boolean()`                   |                           |
| `datetime`         | `z.string().datetime()`         | Or `z.coerce.date()`      |
| `date`             | `z.string().date()`             |                           |
| `UUID`             | `z.string().uuid()`             |                           |
| `list[T]`          | `z.array(T_schema)`             |                           |
| `dict`             | `z.record(z.string(), z.any())` |                           |
| `T \| None`        | `T_schema.nullable()`           | For nullable fields       |
| `T \| None = None` | `T_schema.optional()`           | For optional fields       |

### Field Constraints

| Pydantic Field Arg | Zod Equivalent  | Example                        |
| ------------------ | --------------- | ------------------------------ |
| `min_length=N`     | `.min(N)`       | `z.string().min(1)`            |
| `max_length=N`     | `.max(N)`       | `z.string().max(255)`          |
| `ge=N` (>=)        | `.min(N)`       | `z.number().min(0)`            |
| `gt=N` (>)         | `.gt(N)`        | `z.number().gt(0)`             |
| `le=N` (<=)        | `.max(N)`       | `z.number().max(100)`          |
| `lt=N` (<)         | `.lt(N)`        | `z.number().lt(100)`           |
| `pattern=r"..."`   | `.regex(/.../)` | `z.string().regex(/^\d+$/)`    |
| `default=X`        | `.default(X)`   | `z.string().default('online')` |

### Enums

**Pydantic (StrEnum):**

```python
class CameraStatus(StrEnum):
    ONLINE = auto()
    OFFLINE = auto()
    ERROR = auto()
    UNKNOWN = auto()
```

**Zod:**

```typescript
export const CAMERA_STATUS_VALUES = ['online', 'offline', 'error', 'unknown'] as const;
export const cameraStatusSchema = z.enum(CAMERA_STATUS_VALUES);
export type CameraStatus = z.infer<typeof cameraStatusSchema>;
```

### Custom Validators

**Pydantic:**

```python
@field_validator("folder_path")
@classmethod
def validate_folder_path(cls, v: str) -> str:
    if ".." in v:
        raise ValueError("Path traversal (..) not allowed")
    if FORBIDDEN_CHARS.search(v):
        raise ValueError("Contains forbidden characters")
    return v
```

**Zod:**

```typescript
export const cameraFolderPathSchema = z.string().superRefine((val, ctx) => {
  if (val.includes('..')) {
    ctx.addIssue({
      code: 'custom',
      message: 'Path traversal (..) is not allowed',
    });
  }
  if (FORBIDDEN_CHARS.test(val)) {
    ctx.addIssue({
      code: 'custom',
      message: 'Contains forbidden characters',
    });
  }
});
```

### Nested Objects

**Pydantic:**

```python
class AlertRuleSchedule(BaseModel):
    days: list[str] | None = None
    start_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    timezone: str = "UTC"

class AlertRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    schedule: AlertRuleSchedule | None = None
```

**Zod:**

```typescript
const alertRuleScheduleSchema = z.object({
  days: z.array(z.string()).nullable().optional(),
  start_time: z
    .string()
    .regex(/^\d{2}:\d{2}$/)
    .nullable()
    .optional(),
  end_time: z
    .string()
    .regex(/^\d{2}:\d{2}$/)
    .nullable()
    .optional(),
  timezone: z.string().default('UTC'),
});

export const alertRuleCreateSchema = z.object({
  name: z.string().min(1).max(255),
  schedule: alertRuleScheduleSchema.nullable().optional(),
});
```

### Arrays with Constraints

**Pydantic:**

```python
coordinates: list[list[float]] = Field(
    ...,
    min_length=3,  # Minimum 3 points for a polygon
    description="Array of normalized [x, y] points"
)
```

**Zod:**

```typescript
const coordinatesSchema = z
  .array(
    z.array(z.number().min(0).max(1)).length(2) // Each point is [x, y]
  )
  .min(3); // Minimum 3 points
```

## Common Validation Patterns

### Required vs Optional Fields

**Create schemas** - required fields use `Field(...)`:

```python
name: str = Field(..., min_length=1)  # Required (...)
```

```typescript
name: z.string().min(1); // Required by default
```

**Update schemas** - all fields optional for partial updates:

```python
name: str | None = Field(None, min_length=1)  # Optional (None default)
```

```typescript
name: z.string().min(1).optional(); // .optional() for partial updates
```

### Default Values

```python
status: CameraStatus = Field(default=CameraStatus.ONLINE)
```

```typescript
status: cameraStatusSchema.default('online');
```

### Transforms

Pydantic uses validators for transforms; Zod uses `.transform()`:

```python
@field_validator("name")
@classmethod
def normalize_name(cls, v: str) -> str:
    return v.strip()
```

```typescript
const nameSchema = z.string().transform((val) => val.trim());
```

## Testing Validation Alignment

### Unit Tests for Schemas

Each Zod schema file should have a corresponding test file:

```
frontend/src/schemas/
  camera.ts           # Schema definitions
  camera.test.ts      # Alignment tests
  zone.ts
  zone.test.ts
  index.ts
```

### Test Categories

1. **Constraint Alignment** - Verify constants match backend
2. **Valid Input** - Test that valid data passes
3. **Invalid Input** - Test that invalid data fails with correct messages
4. **Custom Validators** - Test that custom validation logic matches backend

### Example Test Structure

```typescript
describe('Zod Schema Alignment', () => {
  describe('Constants alignment with backend', () => {
    it('should match backend Field constraints', () => {
      // Document what backend has and verify frontend matches
    });
  });

  describe('Valid inputs', () => {
    it('should accept valid complete input', () => {
      const result = schema.safeParse(validInput);
      expect(result.success).toBe(true);
    });
  });

  describe('Invalid inputs', () => {
    it('should reject input violating min_length', () => {
      const result = schema.safeParse({ name: '' });
      expect(result.success).toBe(false);
    });
  });

  describe('Custom validators', () => {
    it('should reject path traversal (matches backend validator)', () => {
      // Test custom validation logic
    });
  });
});
```

## Server Error Handling

Even with frontend validation, always handle server errors gracefully.

### Using useFormWithApiErrors

The `useFormWithApiErrors` hook automatically maps 422 validation errors to form fields:

```tsx
import { useApiMutation } from '@/hooks/useFormWithApiErrors';

const mutation = useApiMutation({
  mutationFn: submitForm,
  form,
});

// After mutation.isError:
// - mutation.hasFieldErrors is true if server returned field errors
// - form.formState.errors contains both client and server errors
```

### Error Format Support

The hook supports both formats:

1. **Custom format:**

   ```json
   { "validation_errors": [{ "field": "email", "message": "Invalid email" }] }
   ```

2. **FastAPI HTTPValidationError:**
   ```json
   { "detail": [{ "loc": ["body", "email"], "msg": "Invalid email", "type": "value_error" }] }
   ```

## Zod Generation Script (NEM-2345)

A future enhancement will automatically generate Zod schemas from Pydantic schemas. See [NEM-2345](https://linear.app/nemotron-v3-home-security/issue/NEM-2345) for details.

**Current Status:** Manual alignment required

**Planned Approach:**

- Generate Zod schemas from OpenAPI spec during build
- Or use a Pydantic-to-Zod conversion tool

Until automated generation is available, follow the manual alignment process documented above.

## Directory Structure

```
backend/api/schemas/
  __init__.py           # Schema exports
  camera.py             # CameraCreate, CameraUpdate, CameraResponse
  zone.py               # ZoneCreate, ZoneUpdate, ZoneResponse
  alerts.py             # AlertRuleCreate, AlertRuleUpdate
  ...                   # Other resource schemas

frontend/src/schemas/
  index.ts              # Re-exports all schemas
  camera.ts             # Zod schemas matching camera.py
  camera.test.ts        # Alignment tests
  zone.ts               # Zod schemas matching zone.py (future)
  zone.test.ts          # Alignment tests (future)
  ...                   # Other resource schemas
```

## Checklist for New Schemas

When adding validation for a new form:

- [ ] Identify backend Pydantic schema in `backend/api/schemas/`
- [ ] Create Zod schema file in `frontend/src/schemas/`
- [ ] Document constraints as constants with comments referencing backend
- [ ] Mirror all field validators and custom validators
- [ ] Export from `frontend/src/schemas/index.ts`
- [ ] Write alignment tests in `*.test.ts`
- [ ] Verify tests pass: `cd frontend && npm test -- --run src/schemas/`
- [ ] Use schema in form with `zodResolver`
- [ ] Handle server errors with `useFormWithApiErrors`

## Related Documentation

- **[Backend Schemas AGENTS.md](../../backend/api/schemas/AGENTS.md)** - Comprehensive Pydantic schema documentation
- **[Testing Guide](./testing.md)** - Testing infrastructure and patterns
- **[Patterns](./patterns.md)** - Code patterns and conventions
- **[useFormWithApiErrors Hook](../../frontend/src/hooks/useFormWithApiErrors.ts)** - Server error handling
