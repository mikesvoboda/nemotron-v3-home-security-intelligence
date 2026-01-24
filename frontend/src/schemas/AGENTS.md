# Schemas Directory - AI Agent Guide

## Purpose

This directory contains Zod validation schemas that mirror backend Pydantic models. These schemas provide client-side form validation that matches server-side validation rules exactly, ensuring consistent validation UX before data is sent to the backend.

## Key Files

| File                | Purpose                                      | Lines |
| ------------------- | -------------------------------------------- | ----- |
| `index.ts`          | Re-exports all schemas for convenient imports | ~10   |
| `camera.ts`         | Camera CRUD validation schemas               | ~178  |
| `camera.test.ts`    | Tests for camera validation                  | -     |
| `alertRule.ts`      | Alert rule validation schemas                | ~331  |
| `alertRule.test.ts` | Tests for alert rule validation              | -     |
| `alert.ts`          | Alert-related schemas (placeholder)          | ~1    |

## Key Exports

### camera.ts

#### Constants

| Export                         | Value                  | Description                           |
| ------------------------------ | ---------------------- | ------------------------------------- |
| `CAMERA_NAME_CONSTRAINTS`      | `{min: 1, max: 255}`   | Name length limits                    |
| `CAMERA_FOLDER_PATH_CONSTRAINTS` | `{min: 1, max: 500}` | Folder path length limits             |
| `CAMERA_STATUS_VALUES`         | `['online', ...]`      | Valid camera status enum values       |

#### Schemas

| Export               | Purpose                                    |
| -------------------- | ------------------------------------------ |
| `cameraStatusSchema` | Validates camera status enum               |
| `cameraNameSchema`   | Validates camera name (length, trim)       |
| `cameraFolderPathSchema` | Validates folder path (no traversal, no forbidden chars) |
| `cameraCreateSchema` | Full schema for camera creation            |
| `cameraUpdateSchema` | Partial schema for camera updates          |
| `cameraFormSchema`   | Form-specific schema with required fields  |

#### Types

| Export               | Description                                |
| -------------------- | ------------------------------------------ |
| `CameraStatusValue`  | Type for camera status enum                |
| `CameraCreateInput`  | Input type for camera creation             |
| `CameraCreateOutput` | Output type after validation               |
| `CameraUpdateInput`  | Input type for camera updates              |
| `CameraUpdateOutput` | Output type after validation               |
| `CameraFormInput`    | Form input type                            |
| `CameraFormOutput`   | Form output type                           |

### alertRule.ts

#### Constants

| Export                          | Value                  | Description                           |
| ------------------------------- | ---------------------- | ------------------------------------- |
| `ALERT_RULE_NAME_CONSTRAINTS`   | `{min: 1, max: 255}`   | Rule name length limits               |
| `RISK_THRESHOLD_CONSTRAINTS`    | `{min: 0, max: 100}`   | Risk threshold range                  |
| `MIN_CONFIDENCE_CONSTRAINTS`    | `{min: 0, max: 1}`     | Confidence range (0.0-1.0)            |
| `COOLDOWN_SECONDS_CONSTRAINTS`  | `{min: 0}`             | Minimum cooldown seconds              |
| `DEDUP_KEY_TEMPLATE_CONSTRAINTS`| `{max: 255}`           | Dedup key length limit                |
| `ALERT_SEVERITY_VALUES`         | `['low', 'medium', ...]` | Valid severity enum                 |
| `VALID_DAYS`                    | `['monday', ...]`      | Valid days of week                    |

#### Schemas

| Export                    | Purpose                                    |
| ------------------------- | ------------------------------------------ |
| `alertSeveritySchema`     | Validates severity enum                    |
| `dayOfWeekSchema`         | Validates day of week                      |
| `alertRuleNameSchema`     | Validates rule name (length, trim)         |
| `riskThresholdSchema`     | Validates risk threshold (0-100, integer)  |
| `minConfidenceSchema`     | Validates confidence (0.0-1.0)             |
| `cooldownSecondsSchema`   | Validates cooldown (non-negative integer)  |
| `dedupKeyTemplateSchema`  | Validates dedup key template               |
| `timeStringSchema`        | Validates HH:MM time format                |
| `daysArraySchema`         | Validates array of days                    |
| `alertRuleScheduleSchema` | Validates schedule object                  |
| `alertRuleCreateSchema`   | Full schema for rule creation              |
| `alertRuleUpdateSchema`   | Partial schema for rule updates            |
| `alertRuleFormSchema`     | Form-specific schema with defaults         |

#### Types

| Export                    | Description                                |
| ------------------------- | ------------------------------------------ |
| `AlertSeverityValue`      | Type for severity enum                     |
| `DayOfWeekValue`          | Type for day of week                       |
| `AlertRuleCreateInput`    | Input type for rule creation               |
| `AlertRuleCreateOutput`   | Output type after validation               |
| `AlertRuleUpdateInput`    | Input type for rule updates                |
| `AlertRuleUpdateOutput`   | Output type after validation               |
| `AlertRuleFormInput`      | Form input type                            |
| `AlertRuleFormOutput`     | Form output type                           |

## Usage Patterns

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

### Manual Validation

```typescript
import { cameraCreateSchema, CameraCreateInput } from '@/schemas';

function validateCamera(input: unknown): CameraCreateInput | null {
  const result = cameraCreateSchema.safeParse(input);
  if (result.success) {
    return result.data;
  }
  console.error('Validation errors:', result.error.issues);
  return null;
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

### Custom Validation

```typescript
import { cameraFolderPathSchema } from '@/schemas';

// Reuse field schemas in custom schemas
const mySchema = z.object({
  primaryPath: cameraFolderPathSchema,
  backupPath: cameraFolderPathSchema.optional(),
});
```

## Backend Schema Alignment

**IMPORTANT**: These schemas must match the backend Pydantic schemas exactly.

### Backend Schema Locations

| Frontend Schema       | Backend Schema Location            |
| --------------------- | ---------------------------------- |
| `cameraCreateSchema`  | `backend/api/schemas/camera.py`    |
| `cameraUpdateSchema`  | `backend/api/schemas/camera.py`    |
| `alertRuleCreateSchema` | `backend/api/schemas/alerts.py`  |
| `alertRuleUpdateSchema` | `backend/api/schemas/alerts.py`  |

### Validation Rules Mapping

| Frontend Zod          | Backend Pydantic           | Example                    |
| --------------------- | -------------------------- | -------------------------- |
| `.min(n)`             | `min_length=n`             | Name min length            |
| `.max(n)`             | `max_length=n`             | Name max length            |
| `.int().min(0).max(100)` | `ge=0, le=100`          | Risk threshold             |
| `.superRefine()`      | `@field_validator`         | Custom validation          |
| `.default()`          | `Field(default=...)`       | Default values             |

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

### Time Format Validation (alertRule.ts)

The `timeStringSchema` validates HH:MM format:

1. **Pattern Match**: Must be `\d{2}:\d{2}`
2. **Hour Range**: 00-23
3. **Minute Range**: 00-59

This matches backend `validate_time_format()` exactly.

## Notes for AI Agents

- **Backend is authoritative**: Frontend schemas provide UX feedback; backend validates
- **Keep in sync**: Update frontend when backend schemas change
- **Use exported types**: Prefer `CameraFormInput` over `z.infer<typeof ...>`
- **Reuse field schemas**: Compose schemas from individual field validators
- **Test validation**: Always test edge cases for custom validators
- **Form defaults**: Use `*FormSchema` variants for forms with sensible defaults
- **Partial updates**: Use `*UpdateSchema` for PATCH requests with optional fields
- **Transform data**: Use `.transform()` for data normalization (trim, lowercase)
