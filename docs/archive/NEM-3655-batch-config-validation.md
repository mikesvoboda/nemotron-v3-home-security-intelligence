# Discovery: Batch Processing Configuration Lacks Validation Feedback

**Issue:** NEM-3655
**Epic:** NEM-3530 (Platform Integration Gaps & Production Readiness)
**Date:** 2026-01-26

## Summary

Batch configuration changes lack adequate validation feedback. Users editing batch settings receive no real-time feedback about constraints or why values are rejected.

## Current Validation State

### Backend Validation (Pydantic Schemas)

**BatchSettings schema** (`backend/api/schemas/settings_api.py`):

- `window_seconds`: gt=0 (must be > 0)
- `idle_timeout_seconds`: gt=0 (must be > 0)

**BatchSettingsUpdate schema** (for PATCH updates):

- `window_seconds`: gt=0, le=600 (max 10 minutes)
- `idle_timeout_seconds`: gt=0, le=300 (max 5 minutes)

### Backend Endpoint Handling

Settings API (`backend/api/routes/settings_api.py`):

- Validates severity thresholds for ordering
- Returns HTTP 422 errors for Pydantic validation failures
- **No cross-field validation** for batch window vs idle timeout relationship

### Frontend UI

ProcessingSettings component (`frontend/src/components/settings/ProcessingSettings.tsx`):

- Uses range sliders:
  - Batch Window: 30-300 seconds (but backend allows up to 600)
  - Idle Timeout: 10-120 seconds (but backend allows up to 300)
- Uses native HTML range inputs (min/max)
- No inline validation messages
- No constraint documentation

### Error Handling

- Pydantic validation errors return HTTP 422 with basic error detail
- Frontend displays generic error messages
- No field-level validation feedback during editing

## Key Gaps Identified

### 1. No Cross-field Validation

The idle_timeout should logically be less than window_seconds (otherwise timeout is useless). No validation enforces this relationship.

### 2. Inconsistent Constraints

Frontend UI limits values more strictly than backend schema allows:
| Setting | Frontend Limit | Backend Limit |
|---------|---------------|---------------|
| window_seconds | 30-300 | 1-600 |
| idle_timeout_seconds | 10-120 | 1-300 |

### 3. No Inline Validation Feedback

Users receive no real-time feedback about:

- Minimum/maximum constraints
- Why specific values are being rejected
- Relationship between window and idle timeout

### 4. Missing Documentation

Frontend sliders don't show min/max values clearly or explain constraints.

### 5. Generic Error Messages

HTTP 422 responses don't clearly indicate which field failed or why.

## Recommendations

1. **Add cross-field validation** - Ensure idle_timeout < window_seconds with clear error message
2. **Implement inline validation feedback** - Show constraint violations as user types/drags
3. **Standardize constraints** - Align frontend and backend limits
4. **Improve error messages** - Field-specific, actionable error messages
5. **Add constraint documentation** - Display min/max and relationship rules in UI
6. **Validate before submit** - Client-side validation to prevent unnecessary API calls

## Files to Modify

- `backend/api/schemas/settings_api.py` - Add model_validator for cross-field validation
- `backend/api/routes/settings_api.py` - Improve error messages
- `frontend/src/components/settings/ProcessingSettings.tsx` - Add inline validation
- `frontend/src/hooks/useSettingsApi.ts` - Add client-side validation

## Status

**Assessment:** Validation exists but feedback is poor. Requires both backend and frontend improvements.
