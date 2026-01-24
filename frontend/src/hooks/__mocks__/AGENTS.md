# Hooks Mock Files

This directory contains mock implementations for frontend hooks used in testing.

## Purpose

These mocks provide configurable, test-friendly implementations of hooks that would otherwise require real WebSocket connections, browser APIs, or backend services. They follow factory patterns similar to `backend/tests/mock_utils.py` for consistency.

## Files

| File                  | Mocks                     | Purpose                                         |
| --------------------- | ------------------------- | ----------------------------------------------- |
| `useEventStream.ts`   | `useEventStream` hook     | Security event stream with WebSocket simulation |
| `useSystemStatus.ts`  | `useSystemStatus` hook    | System health and GPU metrics monitoring        |
| `useWebSocket.ts`     | `useWebSocket` hook       | Low-level WebSocket connection management       |
| `webSocketManager.ts` | `webSocketManager` module | WebSocket subscription and lifecycle management |

## Mock Patterns

### Factory Functions

All mocks provide factory functions for creating test data with sensible defaults:

```typescript
// Event stream mocks
createMockSecurityEvent({ risk_level: 'high', risk_score: 85 });
createMockEventStream({ events: [...], isConnected: true });
createConnectedEventStream(5);  // 5 events, connected

// System status mocks
createMockSystemStatus({ health: 'degraded', gpu_utilization: 95 });
createHealthySystemStatus();
createDegradedSystemStatus();
createUnhealthySystemStatus();

// WebSocket mocks
createMockWebSocket({ isConnected: true });
createConnectedWebSocket();
createDisconnectedWebSocket();
createReconnectingWebSocket(3);  // 3 reconnect attempts
```

### Risk Level Helpers

Convenience functions for security event testing:

```typescript
createLowRiskEvent(); // risk_score: 15, risk_level: 'low'
createMediumRiskEvent(); // risk_score: 50, risk_level: 'medium'
createHighRiskEvent(); // risk_score: 80, risk_level: 'high'
createCriticalRiskEvent(); // risk_score: 95, risk_level: 'critical'
```

### Health Status Helpers

Convenience functions for system status testing:

```typescript
createHealthySystemStatus(); // GPU utilization: 45%, temp: 65C
createDegradedSystemStatus(); // GPU utilization: 85%, temp: 78C
createUnhealthySystemStatus(); // GPU utilization: 98%, temp: 92C
createOverheatingSystemStatus(); // High temperature scenario
createLowMemorySystemStatus(); // GPU memory pressure scenario
createNoGpuSystemStatus(); // Null GPU metrics
```

### Hook Mock Functions

Pre-configured mock functions for use with `vi.mock()`:

```typescript
import { mockUseEventStream, mockUseSystemStatus, mockUseWebSocket } from '../__mocks__';

vi.mock('../hooks/useEventStream', () => ({ useEventStream: mockUseEventStream }));
vi.mock('../hooks/useSystemStatus', () => ({ useSystemStatus: mockUseSystemStatus }));
vi.mock('../hooks/useWebSocket', () => ({ useWebSocket: mockUseWebSocket }));
```

## Usage Example

```typescript
import { vi, beforeEach, describe, it, expect } from 'vitest';
import {
  mockUseEventStream,
  createConnectedEventStream,
  createHighRiskEvent,
} from '../__mocks__/useEventStream';

vi.mock('../hooks/useEventStream', () => ({
  useEventStream: mockUseEventStream,
}));

describe('EventList', () => {
  beforeEach(() => {
    mockUseEventStream.mockClear();
    mockUseEventStream.mockReturnValue(createConnectedEventStream(5));
  });

  it('renders high risk events with alert styling', () => {
    mockUseEventStream.mockReturnValue(
      createMockEventStream({
        events: [createHighRiskEvent({ summary: 'Intruder detected' })],
        isConnected: true,
      })
    );
    // ... test component
  });
});
```

## Parameterized Test Helpers

Arrays for use with `describe.each()`:

```typescript
import { RISK_LEVEL_TEST_CASES } from '../__mocks__/useEventStream';
import { HEALTH_STATUS_TEST_CASES, GPU_UTILIZATION_TEST_CASES } from '../__mocks__/useSystemStatus';

describe.each(RISK_LEVEL_TEST_CASES)('Risk level $level', ({ score, level }) => {
  it(`renders correct badge for ${level}`, () => { ... });
});
```

## WebSocket Manager Mock State

The `webSocketManager.ts` mock provides global state for capturing handlers:

```typescript
import { mockState, resetMockState } from '../__mocks__/webSocketManager';

// Access captured lifecycle handlers
mockState.capturedLifecycleHandlers.onOpen?.();
mockState.capturedLifecycleHandlers.onClose?.();

// Simulate camera status events
mockState.capturedCameraStatusHandler?.({ camera_id: 'cam-1', status: 'online' });

// Clean up in afterEach
afterEach(() => {
  resetMockState();
});
```

## Related Files

- `/frontend/src/hooks/useEventStream.ts` - Real event stream hook
- `/frontend/src/hooks/useSystemStatus.ts` - Real system status hook
- `/frontend/src/hooks/useWebSocket.ts` - Real WebSocket hook
- `/frontend/src/hooks/webSocketManager.ts` - Real WebSocket manager
- `/frontend/src/hooks/__tests__/` - Unit tests using these mocks
