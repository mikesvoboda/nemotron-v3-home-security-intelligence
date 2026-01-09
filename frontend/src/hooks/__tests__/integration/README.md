# Frontend State Integration Tests

This directory contains integration tests for frontend state management, focusing on the interaction between React Query, WebSocket, and cross-component state synchronization.

## Test Files

| File | Description | Coverage Target |
|------|-------------|-----------------|
| `websocket-react-query.integration.test.ts` | WebSocket event -> cache invalidation | Cross-hook integration |
| `optimistic-updates.integration.test.ts` | Mutation failure -> rollback | Optimistic update patterns |
| `cross-tab-sync.integration.test.ts` | localStorage sync between tabs | Cross-tab state sync |
| `race-conditions.integration.test.ts` | API vs WebSocket timing | Concurrent update handling |
| `offline-mutations.integration.test.ts` | Offline mutation queuing | PWA/offline support |
| `memory-leak-prevention.integration.test.ts` | Event listener cleanup | Memory management |

## Running Tests

```bash
# Run all integration tests
cd frontend && npm test -- --run src/hooks/__tests__/integration/

# Run a specific test file
cd frontend && npm test -- --run src/hooks/__tests__/integration/websocket-react-query.integration.test.ts

# Run with coverage
cd frontend && npm test -- --coverage src/hooks/__tests__/integration/
```

## Coverage Targets

| Test Type | Target |
|-----------|--------|
| Cross-hook integration | 80% |
| Cross-tab sync | 80% |
| Offline mutations | 80% |
| Race conditions | 80% |
| Optimistic updates | 80% |

## Test Patterns

### WebSocket Mocking

Tests mock the `WebSocket` global with a controllable implementation:

```typescript
class MockWebSocket {
  static instances: MockWebSocket[] = [];

  simulateMessage(data: unknown) {
    this.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify(data),
    }));
  }
}

global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
```

### React Query Testing

Tests use the `createQueryWrapper` utility to provide `QueryClientProvider`:

```typescript
import { createQueryWrapper } from '../../../test-utils/renderWithProviders';

const { result } = renderHook(() => useCamerasQuery(), {
  wrapper: createQueryWrapper(),
});
```

### Storage Event Simulation

Cross-tab tests simulate storage events:

```typescript
const event = new StorageEvent('storage', {
  key: 'my-key',
  newValue: JSON.stringify(newData),
  oldValue: JSON.stringify(oldData),
});
window.dispatchEvent(event);
```

## Key Testing Scenarios

### 1. WebSocket -> Cache Invalidation

```typescript
// WebSocket receives event
wsInstance.simulateMessage({ type: 'event', data: {...} });

// Verify cache updated
await waitFor(() => {
  expect(result.current.events).toHaveLength(1);
});
```

### 2. Optimistic Update Rollback

```typescript
// Start mutation with deferred promise
const promise = result.current.mutation.mutateAsync({...});

// Verify optimistic update applied
expect(queryClient.getQueryData(['cameras'])).toEqual([...]);

// Reject the promise
reject(new Error('Network error'));

// Verify rollback
await waitFor(() => {
  expect(queryClient.getQueryData(['cameras'])).toEqual(originalData);
});
```

### 3. Cross-Tab Sync

```typescript
// Tab A updates localStorage
localStorage.setItem('key', JSON.stringify(newData));

// Fire storage event (simulating Tab B receiving it)
window.dispatchEvent(new StorageEvent('storage', {...}));

// Verify state updated
expect(result.current.data).toEqual(newData);
```

### 4. Race Condition Handling

```typescript
// Start slow API request
const apiPromise = new Promise(resolve => { apiResolve = resolve; });

// WebSocket delivers update first
wsInstance.simulateMessage({...});

// Resolve API later
apiResolve(staleData);

// Verify correct final state
```

## Related Files

- `/frontend/src/test-utils/renderWithProviders.tsx` - Test utilities
- `/frontend/src/test-utils/factories.ts` - Test data factories
- `/frontend/src/services/queryClient.ts` - Query client configuration
- `/frontend/src/hooks/webSocketManager.ts` - WebSocket manager
