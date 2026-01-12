# Form Validation Audit (NEM-1975)

This document audits frontend form validations against backend Pydantic schema constraints to ensure consistency between client-side and server-side validation.

**Audit Date:** 2026-01-10
**Status:** Validations are aligned - frontend uses centralized validation utilities that match backend schemas

## Executive Summary

The codebase uses a **centralized validation approach** where:

1. Backend defines constraints in Pydantic schemas (`backend/api/schemas/*.py`)
2. Frontend mirrors these constraints in `frontend/src/utils/validation.ts`
3. Form components import and use centralized validation functions

This architecture ensures consistency. The audit confirms all validations are currently aligned.

---

## Camera Form

**Frontend File:** `frontend/src/components/settings/CamerasSettings.tsx`
**Backend Schema:** `backend/api/schemas/camera.py`
**Frontend Validation:** `frontend/src/utils/validation.ts`

| Field         | Frontend Validation            | Backend Validation                     | Match? | Notes                             |
| ------------- | ------------------------------ | -------------------------------------- | ------ | --------------------------------- | ----------------------- |
| `name`        | `minLength: 1, maxLength: 255` | `min_length=1, max_length=255`         | Yes    | Uses `validateCameraName()`       |
| `folder_path` | `minLength: 1, maxLength: 500` | `min_length=1, max_length=500`         | Yes    | Uses `validateCameraFolderPath()` |
| `folder_path` | Path traversal check (`..`)    | `_validate_folder_path()` rejects `..` | Yes    | Security validation aligned       |
| `folder_path` | Forbidden chars check          | `_FORBIDDEN_PATH_CHARS` regex          | Yes    | Rejects `< > : "                  | ? \*` and control chars |
| `status`      | Dropdown: online/offline/error | `CameraStatus` enum                    | Yes    | Enum values match                 |

**HTML Attributes:**

- `maxLength={VALIDATION_LIMITS.camera.name.maxLength}` on name input
- `maxLength={VALIDATION_LIMITS.camera.folderPath.maxLength}` on folder_path input

---

## Zone Form

**Frontend File:** `frontend/src/components/zones/ZoneForm.tsx`
**Backend Schema:** `backend/api/schemas/zone.py`
**Frontend Validation:** `frontend/src/utils/validation.ts`

| Field         | Frontend Validation            | Backend Validation                   | Match? | Notes                                                |
| ------------- | ------------------------------ | ------------------------------------ | ------ | ---------------------------------------------------- |
| `name`        | `minLength: 1, maxLength: 255` | `min_length=1, max_length=255`       | Yes    | Uses `validateZoneName()`                            |
| `color`       | Pattern: `^#[0-9A-Fa-f]{6}$`   | Pattern: `^#[0-9A-Fa-f]{6}$`         | Yes    | Uses `validateZoneColor()`                           |
| `priority`    | `min: 0, max: 100`             | `ge=0, le=100`                       | Yes    | Slider with `min={0} max={100}`                      |
| `zone_type`   | Enum dropdown                  | `ZoneType` enum                      | Yes    | Values: entry_point, driveway, sidewalk, yard, other |
| `shape`       | Enum dropdown                  | `ZoneShape` enum                     | Yes    | Values: rectangle, polygon                           |
| `enabled`     | Boolean toggle                 | `bool` field                         | Yes    | Default: `True`                                      |
| `coordinates` | Not validated in form          | `min_length=3` + geometry validators | N/A    | Coordinates set via canvas, not text input           |

**HTML Attributes:**

- `maxLength={VALIDATION_LIMITS.zone.name.maxLength}` on name input

---

## Alert Rules Form

**Frontend File:** `frontend/src/components/settings/AlertRulesSettings.tsx`
**Backend Schema:** `backend/api/schemas/alerts.py`
**Frontend Validation:** `frontend/src/utils/validation.ts`

| Field                 | Frontend Validation                | Backend Validation                 | Match? | Notes                            |
| --------------------- | ---------------------------------- | ---------------------------------- | ------ | -------------------------------- |
| `name`                | `minLength: 1, maxLength: 255`     | `min_length=1, max_length=255`     | Yes    | Uses `validateAlertRuleName()`   |
| `risk_threshold`      | `min: 0, max: 100`                 | `ge=0, le=100`                     | Yes    | Uses `validateRiskThreshold()`   |
| `min_confidence`      | `min: 0, max: 1`                   | `ge=0.0, le=1.0`                   | Yes    | Uses `validateMinConfidence()`   |
| `cooldown_seconds`    | `min: 0`                           | `ge=0`                             | Yes    | Uses `validateCooldownSeconds()` |
| `severity`            | Dropdown: low/medium/high/critical | `AlertSeverity` enum               | Yes    | Enum values match                |
| `schedule.days`       | Valid day names                    | `VALID_DAYS` frozenset             | Yes    | monday-sunday                    |
| `schedule.start_time` | Pattern: `HH:MM`                   | Pattern + `validate_time_format()` | Yes    | Hours 00-23, minutes 00-59       |
| `schedule.end_time`   | Pattern: `HH:MM`                   | Pattern + `validate_time_format()` | Yes    | Hours 00-23, minutes 00-59       |
| `dedup_key_template`  | `maxLength: 255`                   | `max_length=255`                   | Yes    | Backend uses `DedupKeyStr`       |

**HTML Attributes:**

- `maxLength={VALIDATION_LIMITS.alertRule.name.maxLength}` on name input
- `min={0} max={100}` on risk_threshold input
- `min={0} max={1} step={0.1}` on min_confidence input
- `min={0}` on cooldown_seconds input

---

## Notification Preferences

**Backend Schema:** `backend/api/schemas/notification_preferences.py`
**Frontend Validation:** `frontend/src/utils/validation.ts`

| Field               | Frontend Validation            | Backend Validation             | Match? | Notes                            |
| ------------------- | ------------------------------ | ------------------------------ | ------ | -------------------------------- |
| `risk_threshold`    | `min: 0, max: 100`             | `ge=0, le=100`                 | Yes    | Camera notification threshold    |
| `quiet_hours.label` | `minLength: 1, maxLength: 255` | `min_length=1, max_length=255` | Yes    | Uses `validateQuietHoursLabel()` |

---

## Prompt Management

**Backend Schema:** `backend/api/schemas/prompt_management.py`
**Frontend Validation:** `frontend/src/utils/validation.ts`

| Field                  | Frontend Validation                  | Backend Validation         | Match? | Notes                           |
| ---------------------- | ------------------------------------ | -------------------------- | ------ | ------------------------------- |
| `temperature`          | `min: 0, max: 2`                     | `ge=0.0, le=2.0`           | Yes    | Uses `validateTemperature()`    |
| `max_tokens`           | `min: 1, max: 16384`                 | `ge=1, le=16384`           | Yes    | Uses `validateMaxTokens()`      |
| `system_prompt`        | `minLength: 1` (not whitespace only) | `min_length=1` + validator | Yes    | Backend rejects whitespace-only |
| `vqa_queries`          | `minLength: 1`                       | `min_length=1`             | Yes    | Florence2 config                |
| `object_classes`       | `minLength: 1`                       | `min_length=1`             | Yes    | YoloWorld config                |
| `confidence_threshold` | `min: 0, max: 1`                     | `ge=0.0, le=1.0`           | Yes    | YoloWorld config                |
| `action_classes`       | `minLength: 1`                       | `min_length=1`             | Yes    | XClip config                    |
| `clothing_categories`  | `minLength: 1`                       | `min_length=1`             | Yes    | FashionClip config              |

---

## Validation Architecture

### Centralized Validation Constants

```typescript
// frontend/src/utils/validation.ts
export const VALIDATION_LIMITS = {
  zone: {
    name: { minLength: 1, maxLength: 255 },
    priority: { min: 0, max: 100 },
    coordinates: { minPoints: 3 },
    colorPattern: /^#[0-9A-Fa-f]{6}$/,
  },
  camera: {
    name: { minLength: 1, maxLength: 255 },
    folderPath: { minLength: 1, maxLength: 500 },
  },
  alertRule: {
    name: { minLength: 1, maxLength: 255 },
    riskThreshold: { min: 0, max: 100 },
    minConfidence: { min: 0, max: 1 },
    cooldownSeconds: { min: 0 },
    dedupKeyTemplate: { maxLength: 255 },
  },
  notificationPreferences: {
    riskThreshold: { min: 0, max: 100 },
    quietHoursLabel: { minLength: 1, maxLength: 255 },
  },
  promptConfig: {
    temperature: { min: 0, max: 2 },
    maxTokens: { min: 1, max: 16384 },
  },
};
```

### How Forms Use Validation

1. **Import validation functions:**

   ```typescript
   import {
     validateCameraName,
     validateCameraFolderPath,
     VALIDATION_LIMITS,
   } from '../../utils/validation';
   ```

2. **Apply maxLength to inputs:**

   ```tsx
   <input maxLength={VALIDATION_LIMITS.camera.name.maxLength} />
   ```

3. **Call validators on submit:**
   ```typescript
   const nameResult = validateCameraName(data.name);
   if (!nameResult.isValid) {
     errors.name = nameResult.error;
   }
   ```

---

## Recommendations

### Current State

All form validations are aligned with backend schemas. The centralized validation approach in `frontend/src/utils/validation.ts` provides:

- Single source of truth for validation limits
- Consistent error messages
- Easy maintenance when backend constraints change

### Best Practices Going Forward

1. **When adding new fields:** Always update both:

   - Backend Pydantic schema
   - `VALIDATION_LIMITS` in `frontend/src/utils/validation.ts`

2. **When modifying constraints:**

   - Update backend schema first
   - Run `scripts/extract_pydantic_constraints.py` to verify
   - Update frontend validation constants to match

3. **Documentation:**
   - Add docstrings referencing backend schema location
   - Keep this audit document updated

---

## Automated Verification

Use the extraction script to verify alignment:

```bash
# Extract backend constraints
uv run python scripts/extract_pydantic_constraints.py

# Compare with frontend VALIDATION_LIMITS
```

See `scripts/extract_pydantic_constraints.py` for implementation.
