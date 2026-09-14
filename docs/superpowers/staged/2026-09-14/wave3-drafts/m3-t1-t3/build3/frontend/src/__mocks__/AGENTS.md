# Frontend Mock Directory

## Purpose

Centralized mock infrastructure for frontend unit and integration tests. This directory provides configurable factory functions and type-safe mocks that follow the same patterns as `backend/tests/mock_utils.py`.

## Directory Structure

```
frontend/src/__mocks__/
  index.ts                       # Central re-export hub for all mocks
  AGENTS.md                      # This documentation file

# Related mock directories (siblings, not subdirectories):
frontend/src/hooks/__mocks__/
  useWebSocket.ts                # Mock for useWebSocket hook
  useEventStream.ts              # Mock for useEventStream hook
  useSystemStatus.ts             # Mock for useSystemStatus hook
  webSocketManager.ts            # Mock for WebSocket manager

frontend/src/services/__mocks__/
  api.ts                         # Comprehensive API mock with factory functions
```

## Key Files

| File | Purpose | Exports |
|------|---------|---------|
| `index.ts` | Central re-export point for all mocks | All mock factories and utilities |
| `../hooks/__mocks__/useWebSocket.ts` | Mock WebSocket connection state and callbacks | `createMockWebSocket`, `mockUseWebSocket` |
| `../hooks/__mocks__/useEventStream.ts` | Mock security event stream | `createMockEventStream`, `mockUseEventStream` |
| `../hooks/__mocks__/useSystemStatus.ts` | Mock system status updates | `createMockSystemStatus`, `mockUseSystemStatus` |
| `../services/__mocks__/api.ts` | Mock API client functions | All API mock factories |

## Usage Patterns

### Factory Function Pattern

All mocks use configurable factory functions that allow tests to specify custom return values:

```typescript
import { createMockWebSocket, createMockSecurityEvent } from '../__mocks__';

// Create mock with defaults
const mockWs = createMockWebSocket();

// Create mock with custom configuration
const mockWsConnected = createMockWebSocket({
  isConnected: true,
  hasExhaustedRetries: false,
  reconnectCount: 0,
});

// Create mock event data
const mockEvent = createMockSecurityEvent({
  risk_score: 85,
  risk_level: 'high',
  camera_id: 'front_door',
});
```

### Jest/Vitest Mock Module Pattern

Mocks can be used with Jest/Vitest's `vi.mock()` for automatic module replacement:

```typescript
import { vi, describe, it, expect } from 'vitest';
import { mockUseWebSocket } from '../__mocks__';

// Mock the hook module
vi.mock('../hooks/useWebSocket', () => ({
  useWebSocket: mockUseWebSocket,
}));

describe('Component using WebSocket', () => {
  it('renders connected state', () => {
    // Configure mock for this test
    mockUseWebSocket.mockReturnValue(
      createMockWebSocket({ isConnected: true })
    );

    // ... test component
  });
});
```

### API Mock Pattern

The API mock provides factory functions for each endpoint:

```typescript
import {
  createMockApi,
  createMockCamerasResponse,
  createMockHealthResponse,
} from '../__mocks__';

// Create full API mock
const api = createMockApi();

// Create specific response mocks
const cameras = createMockCamerasResponse([
  { id: 'front_door', name: 'Front Door' },
  { id: 'backyard', name: 'Backyard' },
]);

const health = createMockHealthResponse({ status: 'healthy' });
```

## Mock Types

### WebSocket Mock Types

```typescript
interface MockWebSocketReturn {
  isConnected: boolean;
  lastMessage: unknown;
  send: vi.Mock;
  connect: vi.Mock;
  disconnect: vi.Mock;
  hasExhaustedRetries: boolean;
  reconnectCount: number;
  lastHeartbeat: Date | null;
}

interface MockWebSocketOptions {
  isConnected?: boolean;
  lastMessage?: unknown;
  hasExhaustedRetries?: boolean;
  reconnectCount?: number;
  lastHeartbeat?: Date | null;
}
```

### Event Stream Mock Types

```typescript
interface MockEventStreamReturn {
  events: SecurityEvent[];
  isConnected: boolean;
  latestEvent: SecurityEvent | null;
  clearEvents: vi.Mock;
}

interface MockEventStreamOptions {
  events?: SecurityEvent[];
  isConnected?: boolean;
}
```

### System Status Mock Types

```typescript
interface MockSystemStatusReturn {
  status: SystemStatus | null;
  isConnected: boolean;
}

interface MockSystemStatusOptions {
  status?: Partial<SystemStatus>;
  isConnected?: boolean;
}
```

## Integration with Backend Patterns

These mocks follow the same patterns as `backend/tests/mock_utils.py`:

| Backend Pattern | Frontend Equivalent |
|-----------------|---------------------|
| `create_mock_redis()` | `createMockApi()` |
| `create_mock_http_client()` | `createMockFetch()` |
| `parametrize_risk_levels()` | `RISK_LEVEL_TEST_CASES` |
| `parametrize_object_types()` | `OBJECT_TYPE_TEST_CASES` |

## Test Data Factories

The mocks include factory functions for creating test data:

```typescript
// Security event factory
createMockSecurityEvent({
  id: 'evt-123',
  camera_id: 'front_door',
  risk_score: 75,
  risk_level: 'high',
  summary: 'Person detected at front door',
});

// System status factory
createMockSystemStatus({
  health: 'healthy',
  gpu_utilization: 45,
  gpu_temperature: 65,
  active_cameras: 4,
});

// Camera factory
createMockCamera({
  id: 'front_door',
  name: 'Front Door',
  location: 'Front Entrance',
  status: 'online',
});
```

## Parameterized Test Helpers

For parameterized testing, use the provided test case arrays:

```typescript
import { RISK_LEVEL_TEST_CASES, OBJECT_TYPE_TEST_CASES } from '../__mocks__';

describe.each(RISK_LEVEL_TEST_CASES)(
  'Risk level $riskLevel',
  ({ score, level }) => {
    it(`maps score ${score} to level ${level}`, () => {
      // ... test implementation
    });
  }
);
```

## Best Practices

1. **Use factories over inline objects**: Always use factory functions to ensure consistent structure
2. **Reset mocks between tests**: Call `vi.clearAllMocks()` in `beforeEach`
3. **Type safety**: All mocks are fully typed with TypeScript interfaces
4. **Minimal overrides**: Only override the properties you need for each test
5. **Document custom mocks**: Add JSDoc comments for test-specific mock configurations

## Entry Points

For AI agents exploring this codebase:

1. **Start with `index.ts`** - Central export point for all mocks
2. **Hook mocks**: `../hooks/__mocks__/` contains WebSocket and stream mocks
3. **API mocks**: `../services/__mocks__/api.ts` provides endpoint mocks
4. **Test examples**: See existing test files for usage patterns
