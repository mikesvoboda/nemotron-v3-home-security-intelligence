# WebSocket Connection Deduplication Design

**Bead:** fduf
**Date:** 2026-01-03
**Status:** Ready for implementation

## Problem

Multiple hooks create separate WebSocket connections that all retry simultaneously when connections fail, exceeding the backend rate limit (10/min).

## Solution

Refactor `useWebSocket.ts` to use `webSocketManager` singleton internally, enabling automatic connection deduplication via reference counting.

## Implementation

### Changes to `useWebSocket.ts`

Replace raw WebSocket logic (~320 lines) with delegation to webSocketManager (~80 lines):

```typescript
import { webSocketManager, generateSubscriberId } from "./webSocketManager";

export function useWebSocket(options: WebSocketOptions): UseWebSocketReturn {
  const {
    url,
    protocols, // Note: protocols not yet supported by manager - may need to add
    onMessage,
    onOpen,
    onClose,
    onError,
    onMaxRetriesExhausted,
    onHeartbeat,
    reconnect = true,
    reconnectInterval = 1000,
    reconnectAttempts = 5,
    connectionTimeout = 10000,
    autoRespondToHeartbeat = true,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<unknown>(null);
  const [hasExhaustedRetries, setHasExhaustedRetries] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const [lastHeartbeat, setLastHeartbeat] = useState<Date | null>(null);

  const subscriberIdRef = useRef(generateSubscriberId());
  const unsubscribeRef = useRef<(() => void) | null>(null);

  // Store callbacks in refs to avoid stale closures
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  const onErrorRef = useRef(onError);
  const onMaxRetriesExhaustedRef = useRef(onMaxRetriesExhausted);
  const onHeartbeatRef = useRef(onHeartbeat);

  // Update refs when callbacks change
  useEffect(() => {
    onMessageRef.current = onMessage;
    onOpenRef.current = onOpen;
    onCloseRef.current = onClose;
    onErrorRef.current = onError;
    onMaxRetriesExhaustedRef.current = onMaxRetriesExhausted;
    onHeartbeatRef.current = onHeartbeat;
  });

  const connect = useCallback(() => {
    // Don't reconnect if already subscribed
    if (unsubscribeRef.current) {
      return;
    }

    setHasExhaustedRetries(false);

    unsubscribeRef.current = webSocketManager.subscribe(
      url,
      {
        id: subscriberIdRef.current,
        onMessage: (data) => {
          setLastMessage(data);
          onMessageRef.current?.(data);
        },
        onOpen: () => {
          setIsConnected(true);
          setReconnectCount(0);
          setHasExhaustedRetries(false);
          onOpenRef.current?.();
        },
        onClose: () => {
          setIsConnected(false);
          // Update reconnect count from manager state
          const state = webSocketManager.getConnectionState(url);
          setReconnectCount(state.reconnectCount);
          onCloseRef.current?.();
        },
        onError: (error) => {
          onErrorRef.current?.(error);
        },
        onHeartbeat: () => {
          const state = webSocketManager.getConnectionState(url);
          setLastHeartbeat(state.lastHeartbeat);
          onHeartbeatRef.current?.();
        },
        onMaxRetriesExhausted: () => {
          setHasExhaustedRetries(true);
          onMaxRetriesExhaustedRef.current?.();
        },
      },
      {
        reconnect,
        reconnectInterval,
        maxReconnectAttempts: reconnectAttempts,
        connectionTimeout,
        autoRespondToHeartbeat,
      },
    );
  }, [
    url,
    reconnect,
    reconnectInterval,
    reconnectAttempts,
    connectionTimeout,
    autoRespondToHeartbeat,
  ]);

  const disconnect = useCallback(() => {
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }
  }, []);

  const send = useCallback(
    (data: unknown) => {
      if (!webSocketManager.send(url, data)) {
        console.warn("WebSocket is not connected. Message not sent:", data);
      }
    },
    [url],
  );

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    send,
    connect,
    disconnect,
    hasExhaustedRetries,
    reconnectCount,
    lastHeartbeat,
  };
}

// Keep exports for backward compatibility
export { isHeartbeatMessage, calculateBackoffDelay } from "./webSocketManager";
```

### API Mapping

| useWebSocket API      | webSocketManager equivalent                   |
| --------------------- | --------------------------------------------- |
| `connect()`           | `subscribe()` returns unsubscribe fn          |
| `disconnect()`        | Call the unsubscribe function                 |
| `send(data)`          | `webSocketManager.send(url, data)`            |
| `isConnected`         | `getConnectionState(url).isConnected`         |
| `reconnectCount`      | `getConnectionState(url).reconnectCount`      |
| `hasExhaustedRetries` | `getConnectionState(url).hasExhaustedRetries` |
| `lastHeartbeat`       | `getConnectionState(url).lastHeartbeat`       |

### Files to Modify

| File                                     | Change                                               |
| ---------------------------------------- | ---------------------------------------------------- |
| `frontend/src/hooks/useWebSocket.ts`     | Replace implementation with manager delegation       |
| `frontend/src/hooks/webSocketManager.ts` | Export `isHeartbeatMessage`, `calculateBackoffDelay` |

### Files Unchanged

- All consuming hooks (`useEventStream.ts`, `useSystemStatus.ts`, etc.)
- `webSocketManager.ts` core logic

## Testing

### Update Tests

- `useWebSocket.test.ts` - Mock `webSocketManager` instead of raw WebSocket
- `useWebSocket.timeout.test.ts` - Same approach

### Tests That Should Pass Unchanged

- `webSocketManager.test.ts`
- All consuming hook tests

### New Test

Add test verifying deduplication:

```typescript
it("should share connection for same URL", () => {
  const { result: result1 } = renderHook(() =>
    useWebSocket({ url: "ws://test/events" }),
  );
  const { result: result2 } = renderHook(() =>
    useWebSocket({ url: "ws://test/events" }),
  );

  expect(webSocketManager.getSubscriberCount("ws://test/events")).toBe(2);
  // Only one actual WebSocket connection
});
```

### Manual Verification

1. Clear Redis rate limits: `podman exec <redis> redis-cli DEL rate_limit:websocket:<ip>`
2. Reload dashboard
3. Check backend logs - should see 2 WebSocket connections (`/ws/events`, `/ws/system`) not 6+
4. Verify no 403 rate limit errors

## Acceptance Criteria

- [ ] Page reload doesn't trigger rate limit under normal conditions
- [ ] Multiple components using same WebSocket URL share one connection
- [ ] All existing tests pass
- [ ] New deduplication test added
- [ ] Manual verification confirms 2 connections instead of 6+
