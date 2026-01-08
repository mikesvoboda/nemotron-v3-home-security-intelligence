# Centralized Mock Infrastructure

This directory contains centralized mock implementations for commonly-mocked modules in frontend tests.

## Purpose

Provide consistent, reusable mock implementations that:
- Match real module interfaces with TypeScript types
- Include factory functions for creating test data
- Support easy configuration and reset between tests
- Reduce boilerplate in test files

## Directory Structure

```
frontend/src/__mocks__/
  index.ts          - Re-exports all mocks for convenient imports
  README.md         - Comprehensive usage documentation
  AGENTS.md         - This file
  example.test.tsx  - Example test demonstrating mock usage

frontend/src/hooks/__mocks__/
  useWebSocket.ts   - WebSocket connection mock
  useEventStream.ts - Security event stream mock
  useSystemStatus.ts - System status/health mock

frontend/src/services/__mocks__/
  api.ts            - API client mock (all REST endpoints)
```

## Key Files

### index.ts
Re-exports all mock utilities for convenient single-import usage:
```typescript
import {
  setMockEvents,
  setMockSystemStatus,
  setMockCameras,
  resetAllMocks,
} from '../__mocks__';
```

### hooks/__mocks__/useEventStream.ts
Mock for real-time security event streaming:
- `setMockEvents()` - Configure events array
- `addMockEvent()` - Add single event
- `createMockSecurityEvent()` - Factory function
- `mockClearEvents` - vi.fn() for verifying clearEvents calls

### hooks/__mocks__/useSystemStatus.ts
Mock for system health and GPU status:
- `setMockSystemStatus()` - Configure status object
- `createMockStatusWithHealth()` - Factory for health states
- `createHighLoadStatus()` - Factory for high GPU load scenario
- `createNoGpuStatus()` - Factory for GPU unavailable scenario

### hooks/__mocks__/useWebSocket.ts
Low-level WebSocket mock with event triggers:
- `setMockConnectionState()` - Configure connection state
- `triggerMessage()` - Simulate incoming message
- `triggerOpen()`, `triggerClose()`, `triggerError()` - Lifecycle events
- `mockSend`, `mockConnect`, `mockDisconnect` - vi.fn() for assertions

### services/__mocks__/api.ts
Mock for all REST API endpoints:
- `setMockCameras()`, `setMockEvents()`, etc. - Configure return data
- `setMockFetchCamerasError()`, etc. - Configure error states
- `createMockCamera()`, `createMockEvent()` - Factory functions
- All API functions as vi.fn() for call verification

## Usage Pattern

```typescript
// 1. Mock modules at top of file
vi.mock('../../hooks/useEventStream');
vi.mock('../../services/api');

// 2. Import mock utilities
import { setMockEvents, setMockCameras, resetAllMocks } from '../../__mocks__';

// 3. Reset in beforeEach
beforeEach(() => {
  resetAllMocks();
});

// 4. Configure per test
it('test case', () => {
  setMockEvents([...]);
  setMockCameras([...]);
  // render and assert
});
```

## Entry Points

- **For test setup**: Import from `../__mocks__/index.ts`
- **For understanding mock behavior**: Read `README.md`
- **For examples**: See `example.test.tsx`

## Conventions

1. **Naming**: `setMock*` for configuration, `mock*` for vi.fn(), `createMock*` for factories
2. **Reset**: Every mock module exports a `resetMocks()` function
3. **Types**: All mocks match their real module TypeScript interfaces
4. **Defaults**: Factory functions provide sensible defaults, accept partial overrides

## Related

- MSW handlers: `frontend/src/mocks/handlers.ts` (network-level API mocking)
- Test utilities: `frontend/src/test-utils/` (render helpers, providers)
- Component tests: `frontend/src/components/**/*.test.tsx`
