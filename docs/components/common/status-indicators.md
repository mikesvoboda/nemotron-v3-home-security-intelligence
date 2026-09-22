# Status Indicator Components

Components for displaying system, connection, and service status.

## ServiceStatusIndicator

Displays overall service health with expandable details dropdown.

**Location:** `frontend/src/components/common/ServiceStatusIndicator.tsx`

### Props

```typescript
interface ServiceStatusIndicatorProps {
  services: Record<'redis' | 'rtdetr' | 'nemotron', ServiceStatus | null>;
  hasUnhealthy: boolean;
  isAnyRestarting: boolean;
  className?: string;
}
```

### Overall Status States

| Status   | Condition                       | Indicator Color |
| -------- | ------------------------------- | --------------- |
| Online   | All services healthy            | Green (pulsing) |
| Degraded | Some services unhealthy/restart | Yellow          |
| Offline  | All services unhealthy/failed   | Red             |

### Usage Example

```tsx
import { ServiceStatusIndicator } from '@/components/common';
import { useServiceStatus } from '@/hooks/useServiceStatus';

function Header() {
  const { services, hasUnhealthy, isAnyRestarting } = useServiceStatus();

  return (
    <ServiceStatusIndicator
      services={services}
      hasUnhealthy={hasUnhealthy}
      isAnyRestarting={isAnyRestarting}
    />
  );
}
```

### Features

- Compact status dot expands to show individual service status
- Hover/focus reveals dropdown with service details
- Color-coded indicators (WCAG 4.5:1 compliant)
- Accessible with screen reader support

---

## WebSocketStatus

Displays WebSocket connection status for events and system channels.

**Location:** `frontend/src/components/common/WebSocketStatus.tsx`

### Props

```typescript
interface WebSocketStatusProps {
  eventsChannel: ChannelStatus;
  systemChannel: ChannelStatus;
  showDetails?: boolean;
  onRetry?: () => void;
  isPollingFallback?: boolean;
}
```

### Connection States

| State        | Icon     | Color  | Display             |
| ------------ | -------- | ------ | ------------------- |
| Connected    | Wifi     | Green  | Pulsing dot         |
| Reconnecting | Spinning | Yellow | "Reconnecting (N)"  |
| Failed       | Warning  | Orange | "Connection Failed" |
| Disconnected | WifiOff  | Red    | "Disconnected"      |

### Usage Example

`useConnectionStatus()` aggregates both channels; `useWebSocketStatus()` tracks a single channel and is what `useConnectionStatus` builds on.

```tsx
import { WebSocketStatus } from '@/components/common';
import { useConnectionStatus } from '@/hooks/useConnectionStatus';

function StatusBar() {
  const { summary, isPollingFallback, retryConnection } = useConnectionStatus();

  return (
    <WebSocketStatus
      eventsChannel={summary.eventsChannel}
      systemChannel={summary.systemChannel}
      onRetry={retryConnection}
      isPollingFallback={isPollingFallback}
    />
  );
}
```

### Features

- Shows per-channel status in expandable tooltip
- Displays time since last message
- Reconnection attempt counter
- Click-to-retry on failure state
- Polling fallback indicator

---

## OfflineIndicator

Compact offline status indicator with banner, badge, and minimal variants.

**Location:** `frontend/src/components/common/OfflineIndicator.tsx`

### Props

The component is controlled — it renders from props, not from `navigator.onLine`.

```typescript
interface OfflineIndicatorProps {
  isOffline: boolean; // Required - drives rendering
  cachedEventsCount?: number; // Events queued for sync
  lastOnlineAt?: Date | null; // Shows "time since last online"
  position?: OfflineIndicatorPosition;
  variant?: 'banner' | 'badge' | 'minimal'; // default: 'banner'
  dismissible?: boolean; // default: false
  onDismiss?: () => void;
  onRetry?: () => void;
  className?: string;
  show?: boolean; // External visibility override
}
```

### Usage Example

```tsx
import { OfflineIndicator } from '@/components/common';

<OfflineIndicator isOffline={!isOnline} cachedEventsCount={queued.length} variant="banner" />;
```

---

## Badge Components

### RiskBadge

Displays risk level with color-coded badge. Pass `showScore` to render the numeric score alongside the label (hidden by default).

**Location:** `frontend/src/components/common/RiskBadge.tsx`

```tsx
import { RiskBadge } from '@/components/common';

<RiskBadge level="high" score={85} showScore />
<RiskBadge level="medium" />
<RiskBadge level="low" score={15} showScore />
```

### ConfidenceBadge

Displays AI detection confidence level.

**Location:** `frontend/src/components/common/ConfidenceBadge.tsx`

```tsx
import { ConfidenceBadge } from '@/components/common';

<ConfidenceBadge confidence={0.92} />;
```

### ObjectTypeBadge

Displays detected object type with icon.

**Location:** `frontend/src/components/common/ObjectTypeBadge.tsx`

```tsx
import { ObjectTypeBadge } from '@/components/common';

<ObjectTypeBadge type="person" />
<ObjectTypeBadge type="vehicle" />
<ObjectTypeBadge type="animal" />
```

### AlertBadge

Displays alert status/count.

**Location:** `frontend/src/components/common/AlertBadge.tsx`

```tsx
import { AlertBadge } from '@/components/common';

<AlertBadge count={5} />
<AlertBadge count={0} /> {/* Hidden when zero */}
```

---

## Best Practices

1. **Use appropriate indicator granularity** - service-level for admins, simple connected/disconnected for users
2. **Provide context with tooltips** for compact indicators
3. **Include recovery actions** (retry buttons) for error states
4. **Use consistent colors** - green=good, yellow=warning, red=error
5. **Respect WCAG color contrast** - do not rely on color alone, use icons/text
