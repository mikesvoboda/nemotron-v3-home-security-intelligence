# Hooks Integration Tests

This directory contains integration tests for frontend state management, focusing on cross-hook interactions, concurrent operations, and browser API integration.

## Purpose

Test complex interactions between multiple hooks and systems:

- WebSocket events triggering React Query cache updates
- Optimistic updates with rollback on failure
- localStorage synchronization between browser tabs
- Race conditions between API and WebSocket updates
- Offline mutation queuing and recovery
- Memory leak prevention through proper cleanup

## Test Files

| File                                         | Coverage Focus                  | Key Scenarios                                        |
| -------------------------------------------- | ------------------------------- | ---------------------------------------------------- |
| `websocket-react-query.integration.test.ts`  | WebSocket -> cache invalidation | Event buffering, deduplication, connection state     |
| `optimistic-updates.integration.test.ts`     | Mutation rollback               | Update, delete, create with rollback on failure      |
| `cross-tab-sync.integration.test.ts`         | localStorage sync               | StorageEvent handling, concurrent writes             |
| `race-conditions.integration.test.ts`        | Concurrent updates              | API vs WebSocket timing, stale data prevention       |
| `offline-mutations.integration.test.ts`      | PWA/offline support             | Network status, mutation queuing, cache persistence  |
| `memory-leak-prevention.integration.test.ts` | Cleanup verification            | Listener removal, subscription cleanup, ref tracking |

## Coverage Targets

| Test Type              | Target |
| ---------------------- | ------ |
| Cross-hook integration | 80%    |
| Cross-tab sync         | 80%    |
| Offline mutations      | 80%    |
| Race conditions        | 80%    |
| Optimistic updates     | 80%    |

## Test Patterns

### WebSocket Mocking

```typescript
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onmessage?: (event: MessageEvent) => void;

  simulateMessage(data: unknown) {
    this.onmessage?.(
      new MessageEvent('message', {
        data: JSON.stringify(data),
      })
    );
  }
}

global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
```

### Subscriber Capture Pattern

```typescript
let lastSubscriber: Subscriber | null = null;

(webSocketManager.subscribe as Mock).mockImplementation(
  (_url: string, subscriber: Subscriber) => {
    lastSubscriber = subscriber;
    setTimeout(() => subscriber.onOpen?.(), 0);
    return mockUnsubscribe;
  }
);

// Simulate WebSocket event
act(() => {
  lastSubscriber?.onMessage?.({
    type: 'event',
    data: { event_id: 1, risk_score: 85, ... },
  });
});
```

### Deferred Promise Pattern (Race Conditions)

```typescript
let resolveApi: (value: Camera[]) => void;
const apiPromise = new Promise<Camera[]>((resolve) => {
  resolveApi = resolve;
});
(api.fetchCameras as Mock).mockReturnValue(apiPromise);

// WebSocket delivers update first
act(() => {
  lastSubscriber?.onMessage?.({ type: 'event', data: {...} });
});

// Resolve API later with stale data
act(() => {
  resolveApi(staleData);
});

// Verify correct final state
```

### Optimistic Update with Rollback

```typescript
const useOptimisticCameraUpdate = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }) => api.updateCamera(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.cameras.all });
      const previousCameras = queryClient.getQueryData(queryKeys.cameras.list());
      queryClient.setQueryData(queryKeys.cameras.list(), (old) =>
        old?.map((c) => (c.id === id ? { ...c, ...data } : c))
      );
      return { previousCameras };
    },
    onError: (_err, _vars, context) => {
      if (context?.previousCameras) {
        queryClient.setQueryData(queryKeys.cameras.list(), context.previousCameras);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
    },
  });
};
```

### Storage Event Simulation (Cross-Tab)

```typescript
const createLocalStorageMock = () => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key) => store[key] ?? null),
    setItem: vi.fn((key, value) => {
      store[key] = value;
    }),
    _triggerStorageEvent: (key, newValue, oldValue) => {
      const event = new StorageEvent('storage', {
        key,
        newValue,
        oldValue,
        url: window.location.href,
      });
      window.dispatchEvent(event);
    },
  };
};

// Simulate another tab updating localStorage
act(() => {
  localStorageMock._triggerStorageEvent(STORAGE_KEY, newValue, oldValue);
});
```

### Network Status Simulation (Offline)

```typescript
Object.defineProperty(navigator, 'onLine', {
  value: false,
  configurable: true,
});

// Go offline
act(() => {
  Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
  window.dispatchEvent(new Event('offline'));
});

// Go back online
act(() => {
  Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
  window.dispatchEvent(new Event('online'));
});
```

### Memory Leak Detection

```typescript
const addEventListenerSpy = vi.spyOn(window, 'addEventListener');
const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

// Mount and unmount multiple times
for (let i = 0; i < 5; i++) {
  const { unmount } = renderHook(() => useSavedSearches());
  unmount();
}

// Verify balanced add/remove calls
const addCalls = addEventListenerSpy.mock.calls.filter(([e]) => e === 'storage');
const removeCalls = removeEventListenerSpy.mock.calls.filter(([e]) => e === 'storage');
expect(addCalls.length).toBe(removeCalls.length);
```

## Key Testing Scenarios

### WebSocket + React Query

1. Event arrives before API response
2. API response arrives before WebSocket event
3. Event buffering and deduplication (MAX_EVENTS: 100)
4. Event clearing resets seen IDs
5. Connection state coordination

### Optimistic Updates

1. Immediate UI update before API response
2. Rollback on mutation failure
3. Concurrent mutations to same resource
4. Delete with restore on failure
5. Create with temporary ID replacement

### Cross-Tab Sync

1. LocalStorage update from another tab
2. Ignore events for different keys
3. Handle corrupted data gracefully
4. Handle null newValue (key removed)
5. Rapid successive updates

### Race Conditions

1. WebSocket update arrives before slow API response
2. Concurrent mutations with out-of-order completion
3. Stale data prevention with timestamps
4. Request cancellation on rapid navigation
5. Events arriving during query refetch

### Offline Mutations

1. Detect online/offline status
2. Track wasOffline flag for reconnection notifications
3. Use cached data when offline
4. Refetch on reconnection
5. Cache persistence across component remounts

### Memory Leak Prevention

1. Event listener cleanup on unmount
2. WebSocket subscription cleanup
3. Timer/interval cleanup
4. No state updates after unmount
5. Subscription deduplication

## Running Tests

```bash
# Run all integration tests
cd frontend && npm test -- --run src/hooks/__tests__/integration/

# Run a specific test file
cd frontend && npm test -- --run src/hooks/__tests__/integration/websocket-react-query.integration.test.ts

# Run with coverage
cd frontend && npm test -- --coverage src/hooks/__tests__/integration/
```

## Related Files

- `/frontend/src/hooks/__mocks__/` - Mock implementations
- `/frontend/src/test-utils/renderWithProviders.tsx` - Test utilities
- `/frontend/src/services/queryClient.ts` - Query client configuration
- `/frontend/src/hooks/webSocketManager.ts` - WebSocket manager
- `/frontend/src/hooks/useEventStream.ts` - Event stream hook
- `/frontend/src/hooks/useSavedSearches.ts` - Saved searches with localStorage
- `/frontend/src/hooks/useLocalStorage.ts` - LocalStorage hook
- `/frontend/src/hooks/useNetworkStatus.ts` - Network status detection
- `/frontend/src/hooks/useCachedEvents.ts` - IndexedDB event caching
