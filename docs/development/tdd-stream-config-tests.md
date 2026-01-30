# TDD Tests for Phase 3: Stream Settings Control

**Date:** 2025-01-30
**Related Tasks:** NEM-4394 (Backend), NEM-4395 (Frontend)
**Design Document:** [RTSP Camera Configuration UI Design](../plans/2025-01-30-rtsp-camera-configuration-ui-design.md)
**Status:** RED Phase Complete (Tests Written, All Failing)

## Overview

This document summarizes the TDD tests written for Phase 3: Stream Settings Control of the RTSP Camera Configuration UI feature. All tests follow the RED-GREEN-REFACTOR cycle and are currently in the RED phase (failing by design).

## Test Coverage Summary

| Test Type               | File                              | Test Count | Lines |
| ----------------------- | --------------------------------- | ---------- | ----- |
| Backend Schema Tests    | `test_stream_config.py` (schemas) | 45         | 614   |
| Backend Service Tests   | `test_stream_config_service.py`   | 20         | 480   |
| Backend Integration API | `test_stream_config_api.py`       | 20         | 516   |
| Frontend Component      | `StreamSettingsForm.test.tsx`     | 31         | 642   |
| **Total**               | **4 test files**                  | **116**    | 2,252 |

## Test Files Created

### 1. Backend Schema Tests

**File:** `/home/msvoboda/.claude-squad/worktrees/msvoboda/fine6_188f60b28b5145a6/backend/tests/unit/api/schemas/test_stream_config.py`

**Purpose:** Validate Pydantic schemas for stream configuration API requests/responses.

**Test Classes:**

- `TestResolution` (8 tests)
  - Valid resolutions (4K, 1080p, 720p, VGA, QVGA)
  - Validation: zero/negative/excessive width/height
- `TestEncoderSettings` (14 tests)
  - Valid H264/H265 codec configurations
  - GOP (Group of Pictures) handling
  - Bitrate validation (0, negative, excessive >100Mbps)
  - FPS validation (0, negative, excessive >120)
  - Low FPS support for timelapse (1 fps minimum)
- `TestStreamProfile` (6 tests)
  - Profile token and name requirements
  - Encoder settings integration
  - Multiple profiles (main/sub streams)
  - Optional quality field
- `TestStreamCapabilities` (7 tests)
  - Available resolutions/codecs lists
  - Bitrate/FPS ranges with min/max validation
  - Resolution format validation (widthxheight)
- `TestStreamConfigResponse` (4 tests)
  - Single and multiple profiles
  - Read-only mode flag
  - Capabilities integration
- `TestStreamConfigUpdate` (6 tests)
  - Full and partial updates
  - Profile token requirement
  - Field validation (bitrate, FPS, codec enum)

**Key Acceptance Criteria Tested:**

- Resolution, codec, bitrate, and FPS validation
- Bitrate range enforcement (512 Kbps - 100 Mbps)
- FPS range enforcement (1-120)
- Codec enum validation (H264, H265 only)
- Read-only camera detection

### 2. Backend Service Tests

**File:** `/home/msvoboda/.claude-squad/worktrees/msvoboda/fine6_188f60b28b5145a6/backend/tests/unit/services/test_stream_config_service.py`

**Purpose:** Test stream configuration service logic that interacts with ONVIF cameras.

**Test Classes:**

- `TestStreamConfigServiceGetConfig` (6 tests)
  - Current settings retrieval from ONVIF
  - Multiple profiles (main/sub) handling
  - Read-only camera detection
  - ONVIF connection/timeout failures
  - Missing video encoder handling
- `TestStreamConfigServiceSetConfig` (9 tests)
  - Full and partial setting updates
  - Validation against camera capabilities
  - Resolution/codec/bitrate/FPS range checks
  - Read-only camera rejection (409 CONFLICT)
  - ONVIF command failures
  - Invalid profile token handling
- `TestStreamConfigServiceValidation` (5 tests)
  - Valid settings acceptance
  - Below-minimum rejection (bitrate/FPS)
  - Above-maximum rejection (bitrate/FPS)
  - None values for partial updates

**Key Acceptance Criteria Tested:**

- GET returns resolution, codec, bitrate, fps + available options
- PUT applies settings via ONVIF
- Read-only cameras show settings but disable modification
- Bitrate validation prevents exceeding camera limits
- Unsupported codec returns helpful error message

### 3. Backend Integration Tests

**File:** `/home/msvoboda/.claude-squad/worktrees/msvoboda/fine6_188f60b28b5145a6/backend/tests/integration/test_stream_config_api.py`

**Purpose:** Test complete API flow with FastAPI endpoints and database.

**Test Coverage:**

- GET `/api/cameras/{id}/stream-config` (5 tests)
  - Success with profiles and capabilities
  - Camera not found (404)
  - Non-ONVIF camera rejection (400)
  - Connection failure (503)
  - Read-only camera flag
- PUT `/api/cameras/{id}/stream-config` (15 tests)
  - Full and partial updates
  - Bitrate validation (exceeds max, below min)
  - Unsupported resolution rejection
  - Unsupported codec rejection
  - FPS exceeds max rejection
  - Read-only camera conflict (409)
  - Camera not found (404)
  - Missing/invalid profile token (422/400)
  - ONVIF command failure (503)
  - Pydantic schema validation (422)

**Key Acceptance Criteria Tested:**

- All acceptance criteria from design document
- HTTP status codes match specification
- Error messages are helpful and specific
- Validation occurs before ONVIF commands

### 4. Frontend Component Tests

**File:** `/home/msvoboda/.claude-squad/worktrees/msvoboda/fine6_188f60b28b5145a6/frontend/src/components/settings/__tests__/StreamSettingsForm.test.tsx`

**Purpose:** Test StreamSettingsForm React component UI and user interactions.

**Test Groups:**

- Component Rendering (3 tests)
  - Loading state
  - Error state
  - Form controls (resolution, codec, bitrate, FPS, apply button)
- Resolution Dropdown (3 tests)
  - Available resolutions from camera
  - Pre-selected current resolution
  - Change resolution
- Codec Dropdown (4 tests)
  - Available codecs from camera
  - Pre-selected current codec
  - Change codec
  - Single codec support
- Bitrate Slider (6 tests)
  - Min/max from camera capabilities
  - Current value display
  - Change within range
  - Prevent below minimum
  - Prevent above maximum
  - Display in Kbps units
- FPS Slider (4 tests)
  - Min/max from camera capabilities
  - Current value display
  - Change within range
  - Low FPS support (timelapse mode)
- Read-only Mode (3 tests)
  - Disable all controls
  - Display read-only notice
  - Show current settings (disabled)
- Apply Button (7 tests)
  - Trigger API call
  - Send only changed fields
  - Disable during request
  - Success message
  - Error message
  - Disabled when pristine
  - Enabled when dirty
- Multiple Profiles (1 test)
  - Select between main/sub streams

**Key Acceptance Criteria Tested:**

- Resolution dropdown renders available options
- Codec dropdown renders available options
- Bitrate slider with min/max from camera
- FPS slider with valid range
- Read-only mode disables all controls
- Apply button triggers API call

## Running the Tests

### Backend Schema Tests

```bash
uv run pytest backend/tests/unit/api/schemas/test_stream_config.py -v
```

**Expected Result (RED Phase):** All tests SKIPPED (schemas not implemented)

### Backend Service Tests

```bash
uv run pytest backend/tests/unit/services/test_stream_config_service.py -v
```

**Expected Result (RED Phase):** All tests SKIPPED (service not implemented)

### Backend Integration Tests

```bash
uv run pytest backend/tests/integration/test_stream_config_api.py -v -n0
```

**Expected Result (RED Phase):** All tests ERROR (API endpoints not implemented)

### Frontend Component Tests

```bash
cd frontend && npm test -- --run --testPathPattern=StreamSettingsForm
```

**Expected Result (RED Phase):** All 31 tests FAILED (component not implemented)

## Test Design Patterns

### Backend

- **Schema Tests:** Use Pydantic ValidationError assertions
- **Service Tests:** Mock ONVIF client with AsyncMock
- **Integration Tests:** Use httpx test client with database fixtures
- **Error Handling:** Specific error types with helpful messages

### Frontend

- **Component Tests:** React Testing Library with userEvent
- **API Mocking:** vi.mock() for API client functions
- **Async Handling:** waitFor() for async state updates
- **Accessibility:** getByLabelText() for form controls

## Next Steps (GREEN Phase)

1. **Backend Schemas** (`backend/api/schemas/stream_config.py`)
   - Implement Resolution, EncoderSettings, StreamProfile
   - Implement StreamCapabilities, StreamConfigResponse, StreamConfigUpdate
   - Add field validators for ranges and enums
2. **Backend Service** (`backend/services/stream_config_service.py`)
   - Implement StreamConfigService with get/set methods
   - Integrate with ONVIF Media service
   - Add capability detection and validation
3. **Backend API Routes** (`backend/api/routes/cameras.py` or new file)
   - Add GET `/api/cameras/{id}/stream-config`
   - Add PUT `/api/cameras/{id}/stream-config`
   - Wire up service and schemas
4. **Frontend Component** (`frontend/src/components/settings/StreamSettingsForm.tsx`)
   - Create StreamSettingsForm component
   - Add resolution/codec dropdowns
   - Add bitrate/FPS sliders with camera ranges
   - Implement read-only mode
   - Add apply button with optimistic updates
5. **Frontend API Client** (`frontend/src/services/gpuConfigApi.ts` or new file)
   - Add fetchStreamConfig()
   - Add updateStreamConfig()

## Research Findings Used

From completed NEM-4393:

- Existing slider pattern from `motion_sensitivity` in CamerasSettings.tsx
- ONVIF Media service methods: `GetVideoEncoderConfigurationOptions`, `SetVideoEncoderConfiguration`
- Graceful degradation for read-only cameras
- Camera model needs: `stream_capabilities` (JSON), `onvif_port`, `last_connection_test`, `connection_status`

## Coverage Requirements

| Test Type       | Target Coverage  | Tests Written |
| --------------- | ---------------- | ------------- |
| Backend Schema  | 100%             | 45            |
| Backend Service | 85%+             | 20            |
| Backend API     | 95%+             | 20            |
| Frontend        | 83%+             | 31            |
| **Total**       | **~90% overall** | **116**       |

## Notes

- All tests use `@pytest.mark.skipif` with import error handling (backend)
- Frontend tests check for component existence before running
- Integration tests require ONVIF mocking to avoid real camera dependencies
- Tests validate both happy path and error cases comprehensively
- Error messages are tested for specificity and helpfulness
- All tests follow TDD RED-GREEN-REFACTOR cycle
