# NEM-4191: TDD Phase 1 - Camera Model Extension Tests

## Summary

Comprehensive test suite for Camera model RTSP/ONVIF streaming extension following Test-Driven Development (TDD) methodology.

**Status:** RED phase (tests written and failing as expected)
**Total Tests:** 68 tests across 3 test files
**Next Step:** Implementation phase (GREEN) - NEM-4192

## Test Coverage

### 1. Backend Unit Tests - Camera Model (23 tests)

**File:** `backend/tests/unit/models/test_camera.py`

#### TestCameraRTSPFields (6 tests)

- ✗ `test_camera_has_ingestion_mode_field` - Verify ingestion_mode field exists
- ✗ `test_camera_has_rtsp_url_field` - Verify rtsp_url field exists
- ✗ `test_camera_has_rtsp_username_field` - Verify rtsp_username field exists
- ✗ `test_camera_has_rtsp_password_field` - Verify rtsp_password field exists
- ✗ `test_camera_has_stream_profile_field` - Verify stream_profile field exists
- ✗ `test_camera_has_motion_sensitivity_field` - Verify motion_sensitivity field exists

#### TestCameraIngestionModeDefaults (4 tests)

- ✗ `test_ingestion_mode_defaults_to_ftp` - Default value is 'ftp'
- ✗ `test_ingestion_mode_column_has_ftp_default` - Database column default
- ✗ `test_ingestion_mode_accepts_rtsp` - Accepts 'rtsp' value
- ✗ `test_ingestion_mode_accepts_onvif` - Accepts 'onvif' value

#### TestCameraMotionSensitivityDefaults (5 tests)

- ✗ `test_motion_sensitivity_defaults_to_0_5` - Default value is 0.5
- ✗ `test_motion_sensitivity_column_has_default` - Database column default
- ✗ `test_motion_sensitivity_accepts_custom_value` - Custom values accepted
- ✗ `test_motion_sensitivity_accepts_minimum_value` - 0.0 minimum accepted
- ✗ `test_motion_sensitivity_accepts_maximum_value` - 1.0 maximum accepted

#### TestCameraRTSPFieldsNullability (8 tests)

- ✗ `test_rtsp_url_is_nullable` - rtsp_url can be None
- ✗ `test_rtsp_url_defaults_to_none` - rtsp_url defaults to None
- ✗ `test_rtsp_username_is_nullable` - rtsp_username can be None
- ✗ `test_rtsp_username_defaults_to_none` - rtsp_username defaults to None
- ✗ `test_rtsp_password_is_nullable` - rtsp_password can be None
- ✗ `test_rtsp_password_defaults_to_none` - rtsp_password defaults to None
- ✗ `test_stream_profile_is_nullable` - stream_profile can be None
- ✗ `test_stream_profile_defaults_to_none` - stream_profile defaults to None

### 2. Backend Schema Tests (31 tests)

**File:** `backend/tests/unit/api/schemas/test_camera_validation.py`

#### TestCameraCreateRTSPFields (6 tests)

- ✗ `test_create_camera_with_rtsp_mode` - RTSP mode creation
- ✗ `test_create_camera_with_onvif_mode` - ONVIF mode creation
- ✗ `test_create_camera_defaults_to_ftp_mode` - Default FTP mode
- ✗ `test_create_camera_with_complete_rtsp_config` - All RTSP fields
- ✗ `test_create_camera_rtsp_fields_optional` - Optional for FTP cameras
- ✗ `test_motion_sensitivity_defaults_to_0_5` - Default motion sensitivity

#### TestCameraCreateRTSPURLValidation (8 tests)

- ✗ `test_valid_rtsp_url_basic` - Basic RTSP URL validation
- ✗ `test_valid_rtsp_url_with_auth` - URL with embedded auth
- ✗ `test_valid_rtsps_url` - Secure RTSPS URLs
- ✗ `test_valid_rtsp_url_with_hostname` - Hostname-based URLs
- ✗ `test_invalid_rtsp_url_wrong_scheme` - Reject wrong URL scheme
- ✗ `test_invalid_rtsp_url_malformed` - Reject malformed URLs
- ✗ `test_rtsp_url_none_allowed` - Allow None for FTP cameras

#### TestCameraCreateStreamProfileValidation (5 tests)

- ✗ `test_stream_profile_main_accepted` - Accept 'main' profile
- ✗ `test_stream_profile_sub_accepted` - Accept 'sub' profile
- ✗ `test_stream_profile_both_accepted` - Accept 'both' profile
- ✗ `test_stream_profile_invalid_rejected` - Reject invalid profiles
- ✗ `test_stream_profile_none_allowed` - Allow None value

#### TestCameraCreateMotionSensitivityValidation (5 tests)

- ✗ `test_motion_sensitivity_valid_mid_range` - Mid-range values
- ✗ `test_motion_sensitivity_minimum_value` - 0.0 minimum
- ✗ `test_motion_sensitivity_maximum_value` - 1.0 maximum
- ✗ `test_motion_sensitivity_below_minimum_rejected` - Reject < 0.0
- ✗ `test_motion_sensitivity_above_maximum_rejected` - Reject > 1.0

#### TestCameraCreateIngestionModeValidation (4 tests)

- ✗ `test_ingestion_mode_ftp_accepted` - Accept 'ftp'
- ✗ `test_ingestion_mode_rtsp_accepted` - Accept 'rtsp'
- ✗ `test_ingestion_mode_onvif_accepted` - Accept 'onvif'
- ✗ `test_ingestion_mode_invalid_rejected` - Reject invalid modes

#### TestCameraCreateConditionalValidation (3 tests)

- ✗ `test_rtsp_mode_requires_rtsp_url` - RTSP requires URL
- ✗ `test_onvif_mode_requires_rtsp_url` - ONVIF requires URL
- ✗ `test_ftp_mode_allows_missing_rtsp_url` - FTP allows missing URL

### 3. Backend Integration Tests (14 tests)

**File:** `backend/tests/integration/test_cameras_api.py`

#### RTSP/ONVIF API Integration Tests

- ✗ `test_create_camera_with_rtsp_mode` - POST with RTSP mode
- ✗ `test_create_camera_with_onvif_mode` - POST with ONVIF mode
- ✗ `test_create_camera_ftp_mode_defaults` - POST with FTP defaults
- ✗ `test_create_camera_rtsp_mode_requires_url` - Validation on POST
- ✗ `test_update_camera_to_rtsp_mode` - PATCH FTP to RTSP migration
- ✗ `test_update_camera_rtsp_credentials_only` - PATCH credentials
- ✗ `test_update_camera_stream_profile` - PATCH stream profile
- ✗ `test_update_camera_motion_sensitivity` - PATCH motion sensitivity
- ✗ `test_update_camera_motion_sensitivity_out_of_range` - Validation on PATCH
- ✗ `test_get_camera_returns_rtsp_fields` - GET includes RTSP fields
- ✗ `test_list_cameras_includes_rtsp_fields` - List includes RTSP fields
- ✗ `test_create_camera_invalid_rtsp_url_format` - URL format validation
- ✗ `test_create_camera_invalid_stream_profile` - Stream profile validation
- ✗ `test_create_camera_invalid_ingestion_mode` - Ingestion mode validation

## New Fields Specification

### Camera Model Fields

| Field                | Type          | Nullable | Default | Description                            |
| -------------------- | ------------- | -------- | ------- | -------------------------------------- |
| `ingestion_mode`     | String (enum) | No       | `'ftp'` | Ingestion mode: 'ftp', 'rtsp', 'onvif' |
| `rtsp_url`           | String        | Yes      | `None`  | RTSP/ONVIF stream URL                  |
| `rtsp_username`      | String        | Yes      | `None`  | Authentication username                |
| `rtsp_password`      | String        | Yes      | `None`  | Authentication password (encrypted)    |
| `stream_profile`     | String (enum) | Yes      | `None`  | Stream profile: 'main', 'sub', 'both'  |
| `motion_sensitivity` | Float         | No       | `0.5`   | Motion detection sensitivity (0.0-1.0) |

### Validation Rules

1. **ingestion_mode**: Must be one of 'ftp', 'rtsp', 'onvif'
2. **rtsp_url**:
   - Must be valid RTSP/RTSPS URL format
   - Required when ingestion_mode is 'rtsp' or 'onvif'
   - Optional for 'ftp' mode
3. **stream_profile**: Must be one of 'main', 'sub', 'both' or None
4. **motion_sensitivity**: Must be between 0.0 and 1.0 (inclusive)
5. **rtsp_username/password**: Optional authentication credentials

## Test Execution

### Run All RTSP Tests

```bash
# Unit tests - Model
uv run pytest backend/tests/unit/models/test_camera.py -k "RTSP" -v

# Unit tests - Schema
uv run pytest backend/tests/unit/api/schemas/test_camera_validation.py -k "RTSP" -v

# Integration tests
uv run pytest backend/tests/integration/test_cameras_api.py -k "rtsp or onvif or motion" -v
```

### Expected Results (RED Phase)

All tests should FAIL with errors like:

- `TypeError: 'ingestion_mode' is an invalid keyword argument for Camera`
- `AttributeError: 'CameraCreate' object has no attribute 'ingestion_mode'`
- `TypeError: 'rtsp_url' is an invalid keyword argument for Camera`

This confirms we're in the RED phase of TDD - tests define expected behavior before implementation.

## Test Organization

### Test Pattern Coverage

1. **Field Existence Tests** - Verify model has new fields
2. **Default Value Tests** - Verify correct default values
3. **Nullability Tests** - Verify fields can be None when appropriate
4. **Validation Tests** - Verify field constraints
5. **Enum Tests** - Verify enum values are accepted/rejected
6. **Conditional Tests** - Verify cross-field validation rules
7. **Integration Tests** - Verify API endpoints work end-to-end

### Test Quality Metrics

- **Coverage:** Comprehensive coverage of all new fields and validation rules
- **Edge Cases:** Boundary values (0.0, 1.0), None values, empty strings
- **Error Cases:** Invalid enum values, out-of-range numbers, malformed URLs
- **Happy Path:** Valid RTSP/ONVIF/FTP configurations
- **Integration:** Complete API workflow (CREATE, READ, UPDATE)

## Next Steps

### Phase 2: Implementation (NEM-4192)

1. Add enum for IngestionMode to `backend/models/enums.py`
2. Update Camera model in `backend/models/camera.py`
3. Update CameraCreate schema in `backend/api/schemas/camera.py`
4. Update CameraUpdate schema in `backend/api/schemas/camera.py`
5. Update CameraResponse schema in `backend/api/schemas/camera.py`
6. Create database migration for new columns
7. Run tests to verify GREEN phase

### Phase 3: Database Migration (NEM-4193)

1. Generate Alembic migration
2. Test migration up/down
3. Verify database constraints

### Phase 4: Frontend Integration (NEM-4194)

1. Update TypeScript types
2. Add RTSP configuration UI
3. Frontend tests

## References

- **Linear Issue:** NEM-4191
- **Design Doc:** Phase 1 TDD approach for RTSP/ONVIF camera extension
- **Related Issues:**
  - NEM-4192 (Implementation)
  - NEM-4193 (Database Migration)
  - NEM-4194 (Frontend Integration)
