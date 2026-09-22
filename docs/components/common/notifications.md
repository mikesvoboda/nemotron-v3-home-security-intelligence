# Notification Components

Two mechanisms cover user feedback: **toasts** for transient confirmations (`ToastProvider` + the `useToast` hook) and **banners** for persistent states such as a lost WebSocket connection (`ConnectionStatusBanner`).

## Toasts — ToastProvider and useToast

`ToastProvider` wraps the app in sonner's `Toaster`, pre-styled for the dark theme. Place it near the root of the component tree.

**Location:** `frontend/src/components/common/ToastProvider.tsx`, `frontend/src/hooks/useToast.ts`

```tsx
import { ToastProvider } from '@/components/common';

<ToastProvider>{/* app tree */}</ToastProvider>;
```

Send toasts from any component with `useToast()`:

```tsx
import { useToast } from '@/hooks/useToast';

const { success, error, warning, info, loading, dismiss, promise } = useToast();
success('Settings saved');
```

## ConnectionStatusBanner

Prominent banner displayed when WebSocket connection is lost.

**Location:** `frontend/src/components/common/ConnectionStatusBanner.tsx`

### Props

```typescript
interface ConnectionStatusBannerProps {
  connectionState: 'connected' | 'reconnecting' | 'failed' | 'disconnected';
  disconnectedSince: Date | null;
  reconnectAttempts?: number;
  maxReconnectAttempts?: number; // default: 5
  onRetry: () => void;
  staleThresholdMs?: number; // default: 60000 (1 minute)
  isPollingFallback?: boolean;
}
```

### States

| State        | Appearance        | Actions               |
| ------------ | ----------------- | --------------------- |
| Reconnecting | Yellow background | Shows attempt counter |
| Failed       | Orange background | Shows retry button    |
| Disconnected | Red background    | Shows dismiss button  |

### Usage Example

```tsx
import { ConnectionStatusBanner } from '@/components/common';
import { useConnectionStatus } from '@/hooks/useConnectionStatus';

function LayoutContent() {
  const { summary, isPollingFallback, retryConnection } = useConnectionStatus();

  return (
    <ConnectionStatusBanner
      connectionState={summary.overallState}
      disconnectedSince={summary.disconnectedSince}
      reconnectAttempts={summary.totalReconnectAttempts}
      onRetry={retryConnection}
      isPollingFallback={isPollingFallback}
    />
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
