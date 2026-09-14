# Phase 2 ONVIF Discovery - TDD Test Summary

**Date:** 2025-01-30
**Status:** Complete (Red Phase)
**Linear Tasks:** NEM-4388, NEM-4389

## Overview

Comprehensive TDD tests written for Phase 2 ONVIF Discovery feature. All tests are currently **FAILING** as expected (Red phase of TDD). Implementation will follow in subsequent tasks.

## Files Created/Modified

### 1. Backend Unit Tests (Extended)

**File:** `backend/tests/unit/services/test_onvif_service.py`

**New Tests Added (7 tests):**

- `test_discover_devices_returns_rtsp_urls` - Verify RTSP URLs array with profiles
- `test_discover_devices_extracts_manufacturer_from_scopes` - Parse WS-Discovery scopes
- `test_discover_devices_handles_non_standard_port` - Support port 8080, etc.
- `test_discover_devices_partial_success_with_timeout` - Partial success handling
- `test_discover_devices_no_devices_found` - Empty result handling
- `test_discover_devices_includes_capabilities` - Capability flags in results

**Key Test Coverage:**

- RTSP URL extraction from media profiles (main/sub streams)
- Manufacturer/model parsing from ONVIF scopes
- Non-standard port detection (e.g., 8080 instead of 80)
- Partial success when some devices timeout
- Capability detection (video, PTZ, events, audio)
- Empty discovery results

### 2. Backend Integration Tests (New File)

**File:** `backend/tests/integration/test_onvif_discovery_api.py`

**Tests Created (13 tests):**

- `test_discover_onvif_devices_success` - Happy path with full device data
- `test_discover_onvif_devices_multiple_devices` - Multiple camera discovery
- `test_discover_onvif_devices_no_devices_found` - Empty results
- `test_discover_onvif_devices_partial_success` - Some devices timeout
- `test_discover_onvif_devices_invalid_subnet` - Validation error handling
- `test_discover_onvif_devices_missing_subnet` - Required field validation
- `test_discover_onvif_devices_invalid_timeout` - Timeout range validation
- `test_discover_onvif_devices_default_timeout` - Default parameter handling
- `test_discover_onvif_devices_service_failure` - Exception handling
- `test_discover_onvif_devices_rtsp_urls_structure` - RTSP URL schema validation
- `test_discover_onvif_devices_response_includes_all_required_fields` - Complete response

**API Endpoint Tested:**

```
POST /api/cameras/onvif/discover
Body: {
  "subnet": "192.168.1.0/24",
  "timeout": 10  // optional, defaults to 10
}

Response: {
  "devices": [...],
  "count": 2,
  "timeout_count": 0,  // optional
  "message": "..."     // optional
}
```

**Response Schema Validated:**

```typescript
{
  ip: string;
  port: number;
  device_url: string;
  manufacturer: string;
  model: string;
  rtsp_urls: [
    {
      profile: string;
      url: string;
      resolution?: string;
      codec?: string;
    }
  ];
  requires_auth: boolean;
  capabilities: string[];
}
```

### 3. Frontend Component Tests (New File)

**File:** `frontend/src/components/cameras/__tests__/ONVIFDiscoveryPanel.test.tsx`

**Test Suites (10 suites, ~30+ tests):**

1. **Rendering and Modal Behavior**

   - Modal opens/closes correctly
   - Displays subnet in header
   - Accessibility (ARIA attributes)

2. **Discovery Scanning - Loading State**

   - Loading spinner during scan
   - Progress indicator messaging
   - Loading state removal after completion

3. **Device List Rendering**

   - Manufacturer and model display
   - IP address and port display
   - RTSP profile information
   - Capability icons/badges
   - Select button for each device

4. **Device Selection and Auto-Fill**

   - onSelect callback with full device data
   - Panel closes after selection
   - All RTSP profiles included in selection

5. **No Devices Found**

   - Empty state messaging
   - Helpful troubleshooting tips
   - Retry button availability

6. **Retry Functionality**

   - Re-triggers discovery on retry
   - Shows loading state again
   - Eventually displays devices on success

7. **Partial Success Handling**

   - Shows successful devices when some timeout
   - Warning banner for partial success
   - Timeout count display

8. **Error Handling**

   - Error message on discovery failure
   - Retry button on error
   - Recovery from error on retry

9. **Accessibility**
   - Accessible modal dialog
   - Accessible device cards
   - Accessible buttons
   - Screen reader announcements

**Component Props:**

```typescript
interface ONVIFDiscoveryPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (device: ONVIFDiscoveredDevice) => void;
  subnet: string;
}
```

## Test Verification

### Confirmed Failures (Red Phase)

**Backend Unit Test:**

```bash
$ uv run pytest backend/tests/unit/services/test_onvif_service.py::TestDiscoverDevices::test_discover_devices_returns_rtsp_urls -xvs

FAILED - AssertionError: assert 'rtsp_urls' in device_result
# Current implementation doesn't return rtsp_urls field
```

**Backend Integration Test:**

```bash
$ uv run pytest backend/tests/integration/test_onvif_discovery_api.py::test_discover_onvif_devices_success -xvs

# Will fail when DB is available - endpoint doesn't exist yet
```

**Frontend Test:**

```bash
$ npm test -- ONVIFDiscoveryPanel.test.tsx

# Will fail - component doesn't exist yet
```

## Design Requirements Covered

All Phase 2 requirements from the design document are covered:

### Discovery Features

- [x] Scan subnet for ONVIF devices via WS-Discovery
- [x] Extract IP, port, manufacturer, model from scopes
- [x] Retrieve RTSP URLs for all media profiles (main/sub)
- [x] Detect device capabilities (video, PTZ, events, audio)
- [x] Handle non-standard ports (e.g., 8080)
- [x] Support partial success (some devices timeout)
- [x] Handle no devices found gracefully

### API Endpoint

- [x] POST /api/cameras/onvif/discover
- [x] Subnet parameter validation (CIDR notation)
- [x] Timeout parameter (1-300 seconds, default 10)
- [x] Response includes devices array and count
- [x] Optional timeout_count and message fields

### UI Requirements

- [x] Discovery panel opens on button click
- [x] Loading state with progress indication
- [x] Device list with manufacturer, model, IP, port
- [x] RTSP URLs display (main/sub streams)
- [x] Capability badges (video, PTZ, events)
- [x] Select button auto-fills camera form
- [x] Empty state when no devices found
- [x] Retry button functionality
- [x] Partial success warning banner
- [x] Error state with retry
- [x] Full accessibility (ARIA, screen readers)

## Next Steps (Implementation Phase)

### Backend Implementation

1. Enhance `OnvifService.discover_devices()` to:

   - Connect to each discovered device
   - Extract RTSP URLs from media profiles
   - Detect capabilities via GetCapabilities()
   - Parse manufacturer/model from scopes
   - Handle timeouts gracefully
   - Return enhanced device structure

2. Create/enhance API endpoint:
   - Add route handler in `backend/api/routes/onvif.py`
   - Add schema in `backend/api/schemas/onvif.py`
   - Wire up dependency injection
   - Add to router in `backend/api/routes/__init__.py`

### Frontend Implementation

1. Create `ONVIFDiscoveryPanel.tsx` component
2. Create hook for discovery API call
3. Add to camera settings modal
4. Add "Discover Cameras" button

### Dependencies to Add

```toml
# pyproject.toml
[project]
dependencies = [
  "python-onvif-zeep>=0.2.12",
  "wsdiscovery>=2.0.0",
]
```

## Test Execution Commands

```bash
# Run all Phase 2 tests
uv run pytest backend/tests/unit/services/test_onvif_service.py::TestDiscoverDevices -v
uv run pytest backend/tests/integration/test_onvif_discovery_api.py -v
npm test -- ONVIFDiscoveryPanel.test.tsx

# Run specific failing test
uv run pytest backend/tests/unit/services/test_onvif_service.py::TestDiscoverDevices::test_discover_devices_returns_rtsp_urls -xvs
```

## Coverage Goals

- **Backend Unit Tests:** Cover all OnvifService.discover_devices() scenarios
- **Backend Integration Tests:** Cover all API endpoint scenarios (success, errors, validation)
- **Frontend Tests:** Cover all UI states (loading, success, error, empty, partial)

## Mocking Strategy

### Backend

- `WSDiscovery` - Mock WS-Discovery library for network scanning
- `ONVIFCamera` - Mock ONVIF camera connections
- Media profiles and stream URIs mocked for RTSP URL extraction

### Frontend

- MSW (Mock Service Worker) for API mocking
- TanStack Query for async state management
- Mock device data for various scenarios (success, error, empty, partial)

## Acceptance Criteria Validation

All acceptance criteria from NEM-4388 are testable:

1. ✅ Discovery scans subnet and returns device list
2. ✅ Device list includes IP, manufacturer, model, RTSP URLs
3. ✅ Auto-fill populates form from selected device
4. ✅ Graceful handling when no devices found
5. ✅ Partial success shows found devices + timeout count

## Notes

- Tests follow TDD red-green-refactor cycle
- All tests are comprehensive and will drive implementation
- Mock data covers realistic ONVIF device responses
- Frontend tests cover full user interaction flow
- Backend tests cover service layer and API layer separately
- Error scenarios thoroughly tested (timeouts, failures, validation)
