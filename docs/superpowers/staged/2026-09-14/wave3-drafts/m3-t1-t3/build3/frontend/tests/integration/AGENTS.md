# Integration Tests Directory

## Purpose

Integration tests that verify interactions between multiple components, hooks, or systems. These tests use Vitest (not Playwright) but test more complex scenarios than unit tests, such as WebSocket message flow and state management across components.

## Key Files

| File                            | Description                                    |
| ------------------------------- | ---------------------------------------------- |
| `websocket-performance.test.ts` | WebSocket performance metrics integration test |

## websocket-performance.test.ts

Tests the full WebSocket flow for performance metrics:

### Test Coverage

1. **Connection Lifecycle**

   - Hook initializes without active data
   - Connects to WebSocket on mount
   - Handles disconnection gracefully
   - Reconnects after connection loss

2. **Data Flow**

   - WebSocket message parsing
   - State updates from messages
   - Type-safe message handling

3. **History Accumulation**

   - GPU history accumulates over time
   - History respects maximum length
   - Oldest entries dropped when limit reached

4. **Error Handling**
   - Invalid message format handling
   - Missing required fields
   - Malformed JSON recovery
   - Connection timeout handling

### Test Structure

```typescript
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { usePerformanceMetrics } from '../../src/hooks/usePerformanceMetrics';
import * as useWebSocketModule from '../../src/hooks/useWebSocket';

describe('WebSocket Performance Integration', () => {
  // Mock the useWebSocket hook
  beforeEach(() => {
    vi.spyOn(useWebSocketModule, 'useWebSocket').mockReturnValue({
      lastMessage: null,
      connectionStatus: 'disconnected',
      // ... other WebSocket state
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('processes performance updates correctly', async () => {
    const { result } = renderHook(() => usePerformanceMetrics());
    // Simulate WebSocket message
    // Assert state updates
  });
});
```

### Helper Functions

```typescript
// Wrap performance update in backend envelope format
function wrapInEnvelope(update: PerformanceUpdate): {
  type: 'performance_update';
  data: PerformanceUpdate;
};

// Create a valid performance update with optional overrides
function createTestPerformanceUpdate(overrides?: Partial): PerformanceUpdate;

// Create a full performance update with all metrics populated
function createFullPerformanceUpdate(): PerformanceUpdate;
```

### PerformanceUpdate Structure

```typescript
interface PerformanceUpdate {
  timestamp: string;
  gpu: GPUMetrics | null;
  ai_models: Record;
  nemotron: NemotronStatus | null;
  inference: InferenceMetrics | null;
  databases: Record;
  host: HostMetrics | null;
  containers: ContainerStatus[];
  alerts: PerformanceAlert[];
}
```

## Running Integration Tests

Integration tests run with the regular Vitest test suite:

```bash
# Run all tests (unit + integration)
npm test

# Run only integration tests
npm test -- tests/integration/

# Run with coverage
npm run test:coverage

# Watch mode for development
npm test -- --watch tests/integration/
```

## Difference from E2E Tests

| Aspect          | Integration Tests              | E2E Tests                  |
| --------------- | ------------------------------ | -------------------------- |
| **Framework**   | Vitest + React Testing Library | Playwright                 |
| **Environment** | jsdom                          | Real browser               |
| **Scope**       | Hook/component interactions    | Full user workflows        |
| **Speed**       | Fast (~ms per test)            | Slower (~seconds per test) |
| **Mocking**     | Module-level mocks             | Route interception         |
| **Location**    | This directory                 | `../e2e/specs/`            |

## When to Use Integration Tests

Use integration tests when testing:

1. **Hook-to-hook interactions** - How hooks work together
2. **WebSocket message flow** - Message parsing and state updates
3. **State management** - Cross-component state changes
4. **Event propagation** - Custom events and handlers
5. **Timer/interval logic** - Polling and refresh behavior

Use E2E tests for:

1. **User workflows** - Complete user journeys
2. **Visual verification** - Layout and styling
3. **Navigation** - Page routing and history
4. **Browser APIs** - localStorage, notifications, etc.

## Test Patterns

### Testing Hooks with Mocked Dependencies

```typescript
import { renderHook, act } from '@testing-library/react';
import { vi } from 'vitest';

// Mock the dependency
vi.mock('../../src/hooks/useWebSocket', () => ({
  useWebSocket: vi.fn(),
}));

// Import after mocking
import { useMyHook } from '../../src/hooks/useMyHook';
import * as useWebSocketModule from '../../src/hooks/useWebSocket';

it('updates state on message', async () => {
  // Setup mock return value
  const mockUseWebSocket = vi.spyOn(useWebSocketModule, 'useWebSocket');
  mockUseWebSocket.mockReturnValue({
    lastMessage: { type: 'update', data: {...} },
    connectionStatus: 'connected',
  });

  // Render the hook
  const { result, rerender } = renderHook(() => useMyHook());

  // Trigger update by changing mock
  mockUseWebSocket.mockReturnValue({
    lastMessage: { type: 'update', data: { newValue: 42 } },
    connectionStatus: 'connected',
  });
  rerender();

  // Assert state changed
  expect(result.current.value).toBe(42);
});
```

### Testing Async State Updates

```typescript
import { waitFor } from '@testing-library/react';

it('handles async updates', async () => {
  const { result } = renderHook(() => useMyHook());

  act(() => {
    result.current.triggerUpdate();
  });

  await waitFor(() => {
    expect(result.current.loading).toBe(false);
  });

  expect(result.current.data).toBeDefined();
});
```

## Notes for AI Agents

- Integration tests test hook/component interactions, not full browser flows
- Use `vi.mock()` for module-level mocking
- Use `vi.spyOn()` for selective function mocking
- Always restore mocks in `afterEach`
- Use `renderHook` from React Testing Library for hook tests
- Use `act()` when triggering state updates
- Use `waitFor()` for async assertions
- These tests are included in the regular `npm test` run

## Entry Points

1. **Start here**: `websocket-performance.test.ts` - Main integration test
2. **Hook source**: `../../src/hooks/usePerformanceMetrics.ts` - Hook under test
3. **WebSocket hook**: `../../src/hooks/useWebSocket.ts` - Mocked dependency
4. **Test setup**: `../../src/test/setup.ts` - Vitest configuration
