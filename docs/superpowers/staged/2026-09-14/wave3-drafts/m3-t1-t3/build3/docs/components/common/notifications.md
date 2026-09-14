---

## ConnectionStatusBanner

Prominent banner displayed when WebSocket connection is lost.

**Location:** `frontend/src/components/common/ConnectionStatusBanner.tsx`

### Props

```typescript
interface ConnectionStatusBannerProps {
  connectionState: 'connected' | 'reconnecting' | 'failed' | 'disconnected';
  disconnectedSince: Date | null;
  reconnectAttempts?: number;
  maxReconnectAttempts?: number;  // default: 5
  onRetry: () => void;
  staleThresholdMs?: number;      // default: 60000 (1 minute)
  isPollingFallback?: boolean;
}
```

### States

| State         | Appearance                    | Actions                    |
| ------------- | ----------------------------- | -------------------------- |
| Reconnecting  | Yellow background             | Shows attempt counter      |
| Failed        | Orange background             | Shows retry button         |
| Disconnected  | Red background                | Shows dismiss button       |

### Usage Example

```tsx
import { ConnectionStatusBanner } from '@/components/common';
import { useWebSocketStatus } from '@/hooks/useWebSocketStatus';

function Header() {
  const { connectionState, disconnectedSince, reconnectAttempts, retry } = useWebSocketStatus();

  return (
    <>
      {connectionState \!== 'connected' && (
        <ConnectionStatusBanner
          connectionState={connectionState}
          disconnectedSince={disconnectedSince}
          reconnectAttempts={reconnectAttempts}
          onRetry={retry}
        />
      )}
    </>
  );
}
```

### Features

- Auto-dismisses when connection is restored
- Shows duration since disconnection
- Stale data warning after threshold
- Polling fallback indicator
- Screen reader announcements for state changes

---

## Best Practices

1. **Use toasts for transient feedback** (action confirmations, brief errors)
2. **Use banners for persistent states** (connection issues, system status)
3. **Provide actionable options** (retry buttons, dismiss controls)
4. **Include enough context** for users to understand and respond
5. **Do not overuse notifications** - only notify for meaningful events
