# Centralized Mock Directory

This directory contains centralized mock implementations for commonly-mocked modules in frontend tests.

## Quick Start

```typescript
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock modules - must be at top level
vi.mock('../../hooks/useEventStream');
vi.mock('../../hooks/useSystemStatus');
vi.mock('../../services/api');

// Import mock utilities
import {
  setMockEvents,
  setMockSystemStatus,
  setMockCameras,
  resetAllMocks,
} from '../../__mocks__';

beforeEach(() => {
  resetAllMocks();
});

it('displays events', () => {
  setMockEvents([{ id: 'event-1', risk_score: 75, ... }]);
  // render and test
});
```

## Available Mocks

### useEventStream
- `setMockEvents()` - Configure events array
- `addMockEvent()` - Add single event
- `createMockSecurityEvent()` - Factory function
- `setMockConnectionState()` - Set connection state

### useSystemStatus
- `setMockSystemStatus()` - Configure status
- `createMockStatusWithHealth()` - Factory for health states
- `createHighLoadStatus()` - Factory for high GPU load
- `createNoGpuStatus()` - Factory for GPU unavailable

### useWebSocket
- `setMockConnectionState()` - Configure connection
- `triggerMessage()` - Simulate incoming message
- `triggerOpen()`, `triggerClose()`, `triggerError()` - Lifecycle events
- `mockSend`, `mockConnect`, `mockDisconnect` - vi.fn() for assertions

### API Client
- `setMockCameras()`, `setMockEvents()`, etc. - Configure data
- `setMockFetchCamerasError()`, etc. - Configure errors
- `createMockCamera()`, `createMockEvent()` - Factory functions

## Reset Functions

- `resetAllMocks()` - Reset all mocks (call in beforeEach)
- `resetWebSocketMocks()` - Reset WebSocket mock only
- `resetEventStreamMocks()` - Reset event stream mock only
- `resetSystemStatusMocks()` - Reset system status mock only
- `resetApiMocks()` - Reset API mock only
