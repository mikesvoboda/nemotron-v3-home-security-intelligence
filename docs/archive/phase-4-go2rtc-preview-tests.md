# Phase 4 go2rtc Live Preview - TDD Test Suite

**Date:** 2026-01-30
**Status:** RED Phase (Tests Written, Implementation Pending)
**Related Issues:** NEM-4400, NEM-4401
**Design Doc:** `docs/plans/2025-01-30-rtsp-camera-configuration-ui-design.md`

## Overview

This document describes the comprehensive TDD test suite for Phase 4 of the RTSP Camera Configuration UI project. All tests have been written following the RED-GREEN-REFACTOR cycle and are currently in the **RED phase** (failing until implementation is complete).

## Test Files Created

### Backend Tests

1. **Unit Tests: `backend/tests/unit/services/test_go2rtc_client.py`**

   - 25 tests covering go2rtc client service
   - Tests HTTP API integration (health check, register/unregister streams)
   - Tests credential handling and security
   - Tests error handling and timeout behavior
   - Tests session expiry and cleanup

2. **Integration Tests: `backend/tests/integration/test_preview_api.py`**
   - 21 tests covering preview API endpoints
   - Tests POST `/api/cameras/{id}/preview/start`
   - Tests DELETE `/api/cameras/{id}/preview/stop`
   - Tests graceful degradation when go2rtc unavailable
   - Tests multi-camera preview sessions
   - Tests snapshot fallback mechanism

### Frontend Tests

3. **Component Tests: `frontend/src/components/video/__tests__/RTSPPreviewPlayer.test.tsx`**

   - 28 tests covering RTSPPreviewPlayer component
   - Tests WebRTC connection establishment
   - Tests loading states and connection status
   - Tests fallback to snapshot on failure
   - Tests auto-reconnect logic (max 3 retries)
   - Tests session expiry handling
   - Tests connection status indicators

4. **Hook Tests: `frontend/src/hooks/__tests__/useWebRTCStream.test.ts`**
   - 29 tests covering useWebRTCStream hook
   - Tests WebRTC lifecycle (connect, disconnect, reconnect)
   - Tests RTCPeerConnection and WebSocket management
   - Tests error handling and callbacks
   - Tests exponential backoff for reconnection
   - Tests latency measurement
   - Tests resource cleanup

**Total: 103 TDD tests across 4 test files**

## Test Coverage by Acceptance Criteria

### Design Doc Requirements

| Requirement                                                | Tests                                 | Status |
| ---------------------------------------------------------- | ------------------------------------- | ------ |
| Preview start within 2 seconds                             | 1 integration test                    | RED    |
| Fallback to snapshot when go2rtc unavailable               | 3 component tests                     | RED    |
| Session expires after 5 minutes                            | 2 component tests, 1 integration test | RED    |
| Auto-reconnect on disconnect (max 3 retries)               | 5 hook tests, 2 component tests       | RED    |
| Connection status visible (connecting, connected, latency) | 4 component tests, 2 hook tests       | RED    |
| Passwords never logged or in API responses                 | 1 unit test, 1 integration test       | RED    |

### API Endpoints

| Endpoint                                    | Tests    | Coverage                                                            |
| ------------------------------------------- | -------- | ------------------------------------------------------------------- |
| POST `/api/cameras/{id}/preview/start`      | 10 tests | Returns WebRTC URL, credentials, 503 on failure, 404/400 validation |
| DELETE `/api/cameras/{id}/preview/stop`     | 3 tests  | Cleanup, idempotent operation, 404 handling                         |
| GET `/api/cameras/{id}/snapshot` (fallback) | 1 test   | Existence check for fallback                                        |

### go2rtc Client Service

| Feature             | Tests   | Coverage                                                    |
| ------------------- | ------- | ----------------------------------------------------------- |
| Health check        | 4 tests | Success, connection error, timeout, HTTP errors             |
| Register stream     | 8 tests | Success, WebRTC URL format, credentials, errors, validation |
| Unregister stream   | 3 tests | Success, not found, unavailable                             |
| Credential handling | 3 tests | Embedding, encryption, security                             |
| Error handling      | 5 tests | Unavailable, timeout, invalid URL, error messages           |
| Session expiry      | 1 test  | 5-minute expiry tracking                                    |
| Password security   | 1 test  | Never logged or exposed                                     |

### WebRTC Connection

| Feature              | Tests   | Coverage                                                       |
| -------------------- | ------- | -------------------------------------------------------------- |
| Connection lifecycle | 5 tests | Initialize, connect, receive stream, disconnect, cleanup       |
| Reconnection logic   | 5 tests | Auto-reconnect, retry limit, exponential backoff, manual retry |
| Error handling       | 4 tests | WebSocket errors, RTCPeerConnection errors, callbacks          |
| Latency measurement  | 2 tests | Initial measurement, periodic updates                          |
| Callbacks            | 3 tests | onConnected, onDisconnected, onError                           |
| Cleanup              | 1 test  | Resource cleanup on unmount                                    |

### UI Components

| Feature           | Tests   | Coverage                                                 |
| ----------------- | ------- | -------------------------------------------------------- |
| WebRTC connection | 4 tests | Establish, loading state, video display, latency display |
| Snapshot fallback | 2 tests | WebRTC failure, go2rtc 503                               |
| Auto-reconnect    | 4 tests | Trigger, retry message, max retries, manual retry        |
| Session expiry    | 3 tests | Countdown timer, expired message, restart session        |
| Cleanup           | 1 test  | Unmount cleanup                                          |
| Error handling    | 3 tests | API failures, 404, 400 validation                        |
| Connection status | 2 tests | Visual indicator, color changes                          |

## Verification: Tests Are Failing (RED Phase)

All tests correctly fail because the implementation doesn't exist yet:

```bash
# Backend unit tests
$ uv run pytest backend/tests/unit/services/test_go2rtc_client.py
ERROR: ModuleNotFoundError: No module named 'backend.services.go2rtc_client'

# Backend integration tests
$ uv run pytest backend/tests/integration/test_preview_api.py
ERROR: 17 errors (module import failures)

# Frontend tests (will fail similarly when run)
$ cd frontend && npm test -- RTSPPreviewPlayer.test.tsx
ERROR: Cannot find module '../RTSPPreviewPlayer'

$ cd frontend && npm test -- useWebRTCStream.test.ts
ERROR: Cannot find module '../useWebRTCStream'
```

This confirms we are in the **RED phase** of TDD. Implementation should now proceed to make these tests pass (GREEN phase).

## Implementation Roadmap (To Make Tests Pass)

### Phase 1: Backend Service Layer

1. **Create `backend/services/go2rtc_client.py`**

   - Implement `Go2RTCClient` class
   - Add `health_check()` method
   - Add `register_stream()` method
   - Add `unregister_stream()` method
   - Add exception classes: `Go2RTCUnavailableError`, `StreamRegistrationError`

2. **Create preview API endpoints**
   - Add route: POST `/api/cameras/{id}/preview/start`
   - Add route: DELETE `/api/cameras/{id}/preview/stop`
   - Integrate with credential service for password decryption
   - Add 503 error handling for go2rtc unavailability

### Phase 2: Frontend Hook

3. **Create `frontend/src/hooks/useWebRTCStream.ts`**
   - Implement WebRTC connection logic
   - Add RTCPeerConnection management
   - Add WebSocket signaling
   - Implement reconnection with exponential backoff
   - Add latency measurement
   - Implement callbacks (onConnected, onDisconnected, onError)

### Phase 3: Frontend Component

4. **Create `frontend/src/components/video/RTSPPreviewPlayer.tsx`**

   - Implement WebRTC video player
   - Add connection status UI
   - Add snapshot fallback
   - Add session expiry countdown
   - Add manual retry button
   - Add connection status indicator

5. **Create API service methods**
   - Add `startCameraPreview()` to `frontend/src/services/api.ts`
   - Add `stopCameraPreview()` to `frontend/src/services/api.ts`
   - Update `fetchCameraSnapshot()` for fallback

### Phase 4: Integration & Refinement

6. **Run tests and iterate**
   - Run each test file as implementation progresses
   - Fix failing tests (turn RED to GREEN)
   - Refactor code while keeping tests green (REFACTOR phase)
   - Achieve 100% test pass rate

## Test Execution Commands

```bash
# Backend unit tests
uv run pytest backend/tests/unit/services/test_go2rtc_client.py -v

# Backend integration tests (requires PostgreSQL)
uv run pytest backend/tests/integration/test_preview_api.py -v

# Frontend component tests
cd frontend && npm test -- RTSPPreviewPlayer.test.tsx

# Frontend hook tests
cd frontend && npm test -- useWebRTCStream.test.ts

# Run all Phase 4 tests
uv run pytest backend/tests/unit/services/test_go2rtc_client.py backend/tests/integration/test_preview_api.py -v
cd frontend && npm test -- -t "RTSPPreviewPlayer|useWebRTCStream"
```

## Test Patterns Used

### Backend (pytest)

- **AsyncMock** for async functions and context managers
- **patch()** for dependency injection
- **pytest.mark.asyncio** for async test functions
- **pytest.fixture** for test data and mocks
- **pytest.raises** for exception testing
- **caplog** for log verification (password sanitization)

### Frontend (vitest + React Testing Library)

- **renderHook()** for custom hook testing
- **render()** for component testing
- **waitFor()** for async assertions
- **screen.getByRole() / screen.getByText()** for DOM queries
- **vi.useFakeTimers()** for time-based testing
- **vi.fn()** for mock functions
- **Mock WebSocket / RTCPeerConnection** for WebRTC testing

## Key Testing Principles Applied

1. **Tests written FIRST** (TDD RED phase)
2. **Tests MUST FAIL initially** (verified above)
3. **Comprehensive coverage** of acceptance criteria
4. **Isolated unit tests** with all dependencies mocked
5. **Integration tests** with real database for API endpoints
6. **Error handling** for all failure scenarios
7. **Security testing** (passwords never logged/exposed)
8. **Performance testing** (2-second preview start requirement)
9. **Cleanup testing** (no resource leaks)
10. **User-facing error messages** (friendly, actionable)

## Next Steps

1. **Start implementation** to turn tests from RED to GREEN
2. **Run tests frequently** during development
3. **Commit after each GREEN milestone** (feature works)
4. **Refactor code** while keeping tests green
5. **Update Linear tasks** (NEM-4400, NEM-4401) when tests pass
6. **Create PR** when all 103 tests pass

## Success Criteria

- All 25 backend unit tests passing
- All 21 backend integration tests passing
- All 28 frontend component tests passing
- All 29 frontend hook tests passing
- **Total: 103/103 tests passing**
- Code coverage meets project thresholds (85% backend unit, 95% combined)
- Preview demo works end-to-end with real go2rtc instance

## References

- Design Doc: `/docs/plans/2025-01-30-rtsp-camera-configuration-ui-design.md`
- TDD Workflow: `/docs/development/testing-workflow.md`
- Testing Guide: `/docs/development/testing.md`
- Backend Test Patterns: `/backend/tests/AGENTS.md`
- Frontend Test Setup: `/frontend/vitest.config.ts`
