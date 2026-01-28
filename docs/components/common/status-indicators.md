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

```tsx
import { WebSocketStatus } from '@/components/common';
import { useWebSocketStatus } from '@/hooks/useWebSocketStatus';

function StatusBar() {
  const { eventsChannel, systemChannel, retry, isPollingFallback } = useWebSocketStatus();

  return (
    <WebSocketStatus
      eventsChannel={eventsChannel}
      systemChannel={systemChannel}
      onRetry={retry}
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

Displays network offline/online status.

**Location:** `frontend/src/components/common/OfflineIndicator.tsx`

### Usage Example

```tsx
import { OfflineIndicator } from '@/components/common';

// Automatically shows when navigator.onLine is false
<OfflineIndicator />;
```

---

## Badge Components

### RiskBadge

Displays risk level with color-coded badge.

**Location:** `frontend/src/components/common/RiskBadge.tsx`

```tsx
import { RiskBadge } from '@/components/common';

<RiskBadge level="high" score={85} />
<RiskBadge level="medium" />
<RiskBadge level="low" score={15} />
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
