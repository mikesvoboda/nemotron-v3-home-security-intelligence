# Common Components Directory

## Purpose

Contains reusable UI components shared across multiple features. These are low-level building blocks used throughout the application for consistent styling and behavior.

## Files

| File                          | Purpose                                                              | Status     |
| ----------------------------- | -------------------------------------------------------------------- | ---------- |
| `ErrorBoundary.tsx`           | React error boundary for catching component errors                   | Active     |
| `ErrorBoundary.test.tsx`      | Test suite for ErrorBoundary                                         | Active     |
| `RiskBadge.tsx`               | Risk level badge with icon and optional score                        | Active     |
| `RiskBadge.test.tsx`          | Test suite for RiskBadge                                             | Active     |
| `ConfidenceBadge.tsx`         | Detection confidence score badge with color coding                   | Active     |
| `ConfidenceBadge.test.tsx`    | Test suite for ConfidenceBadge                                       | Active     |
| `ObjectTypeBadge.tsx`         | Detection object type badge                                          | Active     |
| `ObjectTypeBadge.test.tsx`    | Test suite for ObjectTypeBadge                                       | Active     |
| `Lightbox.tsx`                | Full-size image viewer with navigation                               | Active     |
| `Lightbox.test.tsx`           | Test suite for Lightbox                                              | Active     |
| `WebSocketStatus.tsx`         | WebSocket connection status indicator                                | Active     |
| `WebSocketStatus.test.tsx`    | Test suite for WebSocketStatus                                       | Active     |
| `SecureContextWarning.tsx`    | Banner for insecure context (HTTP) detection                         | Active     |
| `SecureContextWarning.test.tsx`| Test suite for SecureContextWarning                                 | Active     |
| `ScheduleSelector.tsx`        | Time-based schedule configuration for alerts                         | Active     |
| `ScheduleSelector.test.tsx`   | Test suite for ScheduleSelector                                      | Active     |
| `ServiceStatusAlert.tsx`      | Service health notification banner                                   | Deprecated |
| `ServiceStatusAlert.test.tsx` | Test suite for ServiceStatusAlert                                    | Deprecated |
| `index.ts`                    | Barrel exports (ErrorBoundary, RiskBadge, SecureContextWarning, WebSocketStatus) | Active |
| `.gitkeep`                    | Placeholder file                                                     | -          |

## Key Components

### ErrorBoundary.tsx

**Purpose:** React error boundary component that catches JavaScript errors in child components and displays a fallback UI

**Props Interface:**

```typescript
interface ErrorBoundaryProps {
  children: ReactNode; // Child components to wrap
  fallback?: ReactNode; // Optional custom fallback UI
  onError?: (error: Error, errorInfo: ErrorInfo) => void; // Optional error callback
  title?: string; // Optional title for error message
  description?: string; // Optional description for error message
}
```

**Key Features:**

- Catches JavaScript errors anywhere in child component tree
- Implements `getDerivedStateFromError` for error state updates
- Implements `componentDidCatch` for error logging and callbacks
- User-friendly fallback UI with error message display
- "Try Again" button to attempt recovery (re-renders children)
- "Refresh Page" button as fallback recovery option
- Support for custom fallback UI via `fallback` prop
- Full accessibility: `role="alert"` and `aria-live="assertive"`

**Error Handling:**

1. Error occurs in child component
2. `getDerivedStateFromError` updates state with error
3. `componentDidCatch` logs error and calls `onError` callback
4. Fallback UI is rendered instead of crashing

**Recovery Options:**

- **Try Again:** Resets error state and attempts to re-render children
- **Refresh Page:** Calls `window.location.reload()` for full page refresh

**Usage:**

```tsx
import { ErrorBoundary } from '../common';

// Basic usage - wraps Routes in App.tsx
<ErrorBoundary>
  <Layout>
    <Routes>...</Routes>
  </Layout>
</ErrorBoundary>

// With custom title and description
<ErrorBoundary
  title="Application Error"
  description="Please try again or refresh the page."
>
  <MyComponent />
</ErrorBoundary>

// With custom fallback
<ErrorBoundary fallback={<CustomErrorPage />}>
  <MyComponent />
</ErrorBoundary>

// With error callback (e.g., for error reporting)
<ErrorBoundary onError={(error, errorInfo) => {
  reportErrorToService(error, errorInfo);
}}>
  <MyComponent />
</ErrorBoundary>
```

**Dependencies:**

- `lucide-react` - AlertOctagon, RefreshCw icons
- `react` - Component, ErrorInfo, ReactNode

---

### RiskBadge.tsx

**Purpose:** Display risk level as a colored badge with icon and optional score

**Props Interface:**

```typescript
interface RiskBadgeProps {
  level: RiskLevel; // 'low' | 'medium' | 'high' | 'critical'
  score?: number; // Risk score 0-100
  showScore?: boolean; // Display score in badge (default: false)
  size?: 'sm' | 'md' | 'lg'; // Badge size (default: 'md')
  animated?: boolean; // Enable pulse animation for critical (default: true)
  className?: string; // Additional CSS classes
}
```

**Key Features:**

- Four risk levels with distinct colors and icons
- Icons: CheckCircle (low), AlertTriangle (medium/high), AlertOctagon (critical)
- Three size variants with corresponding text/padding/icon sizes
- Optional risk score display: "High (75)" vs just "High"
- Pulse animation for critical level (controllable via `animated` prop)
- Full accessibility: `role="status"` and descriptive `aria-label`

**Color Mapping:**

| Level    | Background        | Text             | Icon          |
| -------- | ----------------- | ---------------- | ------------- |
| low      | bg-risk-low/10    | text-risk-low    | CheckCircle   |
| medium   | bg-risk-medium/10 | text-risk-medium | AlertTriangle |
| high     | bg-risk-high/10   | text-risk-high   | AlertTriangle |
| critical | bg-red-500/10     | text-red-500     | AlertOctagon  |

**Size Mapping:**

| Size | Text      | Padding     | Icon    |
| ---- | --------- | ----------- | ------- |
| sm   | text-xs   | px-2 py-0.5 | w-3 h-3 |
| md   | text-sm   | px-2.5 py-1 | w-4 h-4 |
| lg   | text-base | px-3 py-1.5 | w-5 h-5 |

**Usage:**

```tsx
import RiskBadge from '../common/RiskBadge';
// or
import { RiskBadge } from '../common';

<RiskBadge level="high" />
<RiskBadge level="critical" score={87} showScore />
<RiskBadge level="medium" size="lg" animated={false} />
```

**Dependencies:**

- `lucide-react` - CheckCircle, AlertTriangle, AlertOctagon
- `clsx` - Conditional class composition
- `../../utils/risk` - getRiskLabel, RiskLevel type

---

### ObjectTypeBadge.tsx

**Purpose:** Display detected object type as a colored badge with icon

**Props Interface:**

```typescript
interface ObjectTypeBadgeProps {
  type: string; // Object type from detection (e.g., "person", "car")
  size?: 'sm' | 'md' | 'lg'; // Badge size (default: 'sm')
  className?: string; // Additional CSS classes
}
```

**Key Features:**

- Maps detection labels to semantic categories (person, vehicle, animal, package)
- Unknown types display with AlertTriangle icon and capitalized name
- Bordered badge style with background at 10% opacity
- Full accessibility: `role="status"` and descriptive `aria-label`

**Object Type Mapping:**

| Input Types                 | Icon          | Color  | Display Name  |
| --------------------------- | ------------- | ------ | ------------- |
| person                      | User          | blue   | Person        |
| car, truck, bus, motorcycle | Car           | purple | Vehicle       |
| bicycle                     | Car           | cyan   | Bicycle       |
| dog, cat, bird              | PawPrint      | amber  | Animal        |
| package                     | Package       | green  | Package       |
| (unknown)                   | AlertTriangle | gray   | (Capitalized) |

**Usage:**

```tsx
import ObjectTypeBadge from '../common/ObjectTypeBadge';

<ObjectTypeBadge type="person" />
<ObjectTypeBadge type="car" size="md" />
<ObjectTypeBadge type="drone" /> // Shows "Drone" with gray styling
```

**Dependencies:**

- `lucide-react` - User, Car, PawPrint, Package, AlertTriangle
- `clsx` - Conditional class composition

---

### ServiceStatusAlert.tsx

**Status: DEPRECATED**

This component is NOT currently used in the application. The `useServiceStatus` hook that would provide data for this component is not wired up on the backend.

**Why deprecated:**

- Backend's `ServiceHealthMonitor` exists but is not initialized in `main.py`
- No `service_status` WebSocket messages are broadcast
- Application uses `useSystemStatus` instead (receives `system_status` messages with overall health)

**If re-enabling in the future:**

1. Wire `ServiceHealthMonitor` in `backend/main.py`
2. Create `useServiceStatus` hook to consume the WebSocket messages
3. Use this component with the hook data

**Props Interface (for reference):**

```typescript
interface ServiceStatusAlertProps {
  services: Record;
  onDismiss?: () => void;
}

type ServiceName = 'redis' | 'rtdetr' | 'nemotron';
type ServiceStatusValue = 'healthy' | 'unhealthy' | 'restarting' | 'restart_failed' | 'failed';

interface ServiceStatus {
  service: ServiceName;
  status: ServiceStatusValue;
  message?: string;
  timestamp: string;
}
```

---

### index.ts

**Purpose:** Barrel export file for common components

**Current Exports:**

```typescript
export { default as ErrorBoundary } from './ErrorBoundary';
export { default as RiskBadge } from './RiskBadge';
export { default as SecureContextWarning } from './SecureContextWarning';
export { default as WebSocketStatus } from './WebSocketStatus';
```

**Note:** ConfidenceBadge, ObjectTypeBadge, Lightbox, ScheduleSelector, and ServiceStatusAlert are NOT exported from index.ts. Import directly:

```typescript
import ObjectTypeBadge from '../common/ObjectTypeBadge';
import ConfidenceBadge from '../common/ConfidenceBadge';
import Lightbox from '../common/Lightbox';
import ScheduleSelector from '../common/ScheduleSelector';
```

---

### SecureContextWarning.tsx

**Purpose:** Display a warning banner when the application is not running in a secure context (HTTPS)

**Props Interface:**

```typescript
interface SecureContextWarningProps {
  forceShow?: boolean;    // Show even in secure contexts (for testing)
  dismissible?: boolean;  // Allow dismissing the warning (default: true)
  onDismiss?: () => void; // Callback when dismissed
  className?: string;     // Additional CSS classes
}
```

**Key Features:**

- Auto-hides when in secure context (HTTPS or localhost)
- Displays information about affected browser APIs (WebCodecs)
- Dismissible with X button
- Shows current context and required context
- Uses `getWebCodecsStatus()` utility for status message

**Usage:**

```tsx
import SecureContextWarning from '../common/SecureContextWarning';
// or
import { SecureContextWarning } from '../common';

<SecureContextWarning />
<SecureContextWarning dismissible={false} />
<SecureContextWarning onDismiss={() => console.log('Dismissed')} />
```

**Dependencies:**

- `lucide-react` - AlertTriangle, Shield, X icons
- `../../utils/webcodecs` - getWebCodecsStatus, isSecureContext

---

### ScheduleSelector.tsx

**Purpose:** Configure time-based schedules for alert rules with day, time, and timezone selection

**Props Interface:**

```typescript
interface ScheduleSelectorProps {
  value: AlertRuleSchedule | null;  // Current schedule, null = always active
  onChange: (schedule: AlertRuleSchedule | null) => void;  // Callback on change
  disabled?: boolean;               // Disable all inputs
  className?: string;               // Additional CSS classes
}

interface AlertRuleSchedule {
  days: string[] | null;    // ['monday', 'tuesday', ...] or null for all days
  start_time: string | null; // '22:00' format
  end_time: string | null;   // '06:00' format
  timezone: string;          // 'America/New_York', 'UTC', etc.
}
```

**Key Features:**

- Enable/disable schedule toggle
- Day of week checkboxes (Mon-Sun)
- Quick options: All Days, Weekdays, Weekends
- Start and end time pickers
- All Day quick option
- Timezone selector with auto-detection
- Supports overnight schedules (e.g., 22:00-06:00)

**Usage:**

```tsx
import ScheduleSelector from '../common/ScheduleSelector';

<ScheduleSelector
  value={schedule}
  onChange={setSchedule}
  disabled={isSubmitting}
/>
```

**Dependencies:**

- `@headlessui/react` - Switch component
- `clsx` - Conditional class composition
- `lucide-react` - Calendar, Clock, Globe icons
- `../../services/api` - AlertRuleSchedule type

---

### ConfidenceBadge.tsx

**Purpose:** Display detection confidence score as a colored badge with optional progress bar

**Props Interface:**

```typescript
interface ConfidenceBadgeProps {
  confidence: number; // Confidence score 0-1
  size?: 'sm' | 'md' | 'lg'; // Badge size (default: 'sm')
  showBar?: boolean; // Show progress bar (default: false)
  className?: string; // Additional CSS classes
}
```

**Key Features:**

- Three confidence levels with distinct colors based on thresholds
- Formats confidence as percentage (e.g., "85%")
- Optional progress bar showing confidence visually
- Full accessibility: `role="status"` and descriptive `aria-label`
- Uses utility functions from `../../utils/confidence`

**Confidence Level Mapping:**

| Confidence Range | Level  | Color  |
| ---------------- | ------ | ------ |
| < 70%            | low    | red    |
| 70-85%           | medium | yellow |
| > 85%            | high   | green  |

**Size Mapping:**

| Size | Text      | Padding     | Bar Height |
| ---- | --------- | ----------- | ---------- |
| sm   | text-xs   | px-2 py-0.5 | h-1        |
| md   | text-sm   | px-2.5 py-1 | h-1.5      |
| lg   | text-base | px-3 py-1.5 | h-2        |

**Usage:**

```tsx
import ConfidenceBadge from '../common/ConfidenceBadge';

<ConfidenceBadge confidence={0.85} />
<ConfidenceBadge confidence={0.92} size="md" showBar />
<ConfidenceBadge confidence={0.65} size="lg" />
```

**Dependencies:**

- `clsx` - Conditional class composition
- `../../utils/confidence` - formatConfidencePercent, getConfidenceLevel, getConfidenceLabel, color class utilities

---

### WebSocketStatus.tsx

**Purpose:** Display WebSocket connection status with channel-level details in a tooltip

**Props Interface:**

```typescript
interface WebSocketStatusProps {
  eventsChannel: ChannelStatus;
  systemChannel: ChannelStatus;
  showDetails?: boolean; // Show label text (default: false)
}

// From ../../hooks/useWebSocketStatus
interface ChannelStatus {
  name: string;
  state: ConnectionState; // 'connected' | 'reconnecting' | 'disconnected'
  lastMessageTime: Date | null;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
}
```

**Key Features:**

- Overall connection status from multiple WebSocket channels
- Hover tooltip showing per-channel status details
- Color-coded indicators: green (connected), yellow (reconnecting), red (disconnected)
- Shows reconnection attempts counter during reconnection
- Time since last message per channel ("Just now", "5s ago", "2m ago")
- Pulse animation on green dot when connected

**State Colors:**

| State        | Icon Color      | Dot Color     | Icon                 |
| ------------ | --------------- | ------------- | -------------------- |
| connected    | text-green-400  | bg-green-500  | Wifi                 |
| reconnecting | text-yellow-400 | bg-yellow-500 | RefreshCw (spinning) |
| disconnected | text-red-400    | bg-red-500    | WifiOff              |

**Subcomponents:**

- `ChannelIndicator` - Per-channel status row in tooltip
- `WebSocketTooltip` - Hover tooltip with channel details

**Usage:**

```tsx
import WebSocketStatus from '../common/WebSocketStatus';

<WebSocketStatus
  eventsChannel={eventsChannelStatus}
  systemChannel={systemChannelStatus}
  showDetails={true}
/>;
```

**Dependencies:**

- `lucide-react` - RefreshCw, Wifi, WifiOff
- `react` - useState, useEffect, useRef
- `../../hooks/useWebSocketStatus` - ChannelStatus, ConnectionState types

---

## Important Patterns

### Consistent Size Variants

All badge components follow the same sizing pattern (sm/md/lg) for consistency across the UI.

### Accessibility

- All badges use `role="status"` for screen reader announcements
- Descriptive `aria-label` attributes provide context
- Icons have `aria-hidden="true"` when text provides the same information

### Composability

- All components accept `className` prop for custom styling
- No layout constraints (inline-flex) - can be placed anywhere
- Pure presentational components with no side effects

### Color Strategy

- Background: Color at 10% opacity (e.g., `bg-green-500/10`)
- Text: Full color (e.g., `text-green-500`)
- Creates subtle, accessible contrast on dark backgrounds

## Testing

### ErrorBoundary.test.tsx

- Renders children when no error (normal operation)
- Catches errors and displays fallback UI
- Displays error message in fallback
- Logs error to console
- Calls onError callback when error is caught
- Displays custom title and description when provided
- Renders custom fallback when provided
- Try Again button resets error state and re-renders
- Refresh Page button calls window.location.reload
- Nested error boundaries work correctly
- Accessible alert role and aria-live attributes
- Icons hidden from screen readers

### RiskBadge.test.tsx

- Renders all risk levels with correct styling
- Displays correct icons per level
- Shows/hides score based on showScore prop
- Applies correct size classes
- Pulse animation on critical level
- ARIA attributes for accessibility

### ObjectTypeBadge.test.tsx

- Renders all known object types correctly
- Displays correct icons and colors per type
- Handles unknown types gracefully (capitalizes and shows gray)
- Applies correct size classes
- ARIA attributes for accessibility

### ServiceStatusAlert.test.tsx

- Returns null when all services healthy
- Shows yellow banner for restarting status
- Shows red banner for unhealthy/failed statuses
- Displays worst status when multiple services affected
- Dismiss button functionality
- Accessible alert role and aria-live

## Entry Points

**Start here:** `ErrorBoundary.tsx` - App-level error handling (wraps Routes in App.tsx)
**Also see:** `RiskBadge.tsx` - Most commonly used badge component
**Also see:** `ConfidenceBadge.tsx` - Detection confidence scoring badge
**Also see:** `ObjectTypeBadge.tsx` - Detection object type badge
**Also see:** `WebSocketStatus.tsx` - Connection status indicator
**Also see:** `Lightbox.tsx` - Full-size image viewing modal
**Also see:** `SecureContextWarning.tsx` - HTTPS requirement warning banner
**Also see:** `ScheduleSelector.tsx` - Alert schedule configuration
**Reference:** `ServiceStatusAlert.tsx` - Deprecated but documented for future use

---

### Lightbox.tsx

**Purpose:** Display full-size images in a modal overlay with optional multi-image navigation

**Props Interface:**

```typescript
interface LightboxImage {
  src: string;
  alt: string;
  caption?: string;
}

interface LightboxProps {
  images: LightboxImage | LightboxImage[];
  initialIndex?: number;
  isOpen: boolean;
  onClose: () => void;
  onIndexChange?: (index: number) => void;
  showNavigation?: boolean;
  showCounter?: boolean;
  className?: string;
}
```

**Key Features:**

- Single image or multi-image gallery support
- Keyboard navigation (Escape, ArrowLeft, ArrowRight)
- Image counter (e.g., "1 / 5")
- Optional caption display
- Backdrop click to close
- Smooth enter/exit transitions
- Prevents body scroll when open

**Usage:**

```tsx
import Lightbox from '../common/Lightbox';

<Lightbox
  images={[
    { src: '/img1.jpg', alt: 'Detection 1', caption: 'Front door' },
    { src: '/img2.jpg', alt: 'Detection 2' },
  ]}
  isOpen={isOpen}
  onClose={() => setIsOpen(false)}
  showNavigation={true}
  showCounter={true}
/>;
```

**Dependencies:**

- `@headlessui/react` - Dialog, Transition
- `lucide-react` - ChevronLeft, ChevronRight, X

---

### ConfidenceBadge.test.tsx

- Renders with correct percentage text
- Applies correct colors per confidence level
- Shows/hides progress bar based on showBar prop
- Applies correct size classes
- ARIA attributes for accessibility

### WebSocketStatus.test.tsx

- Shows correct overall status based on channel states
- Displays tooltip on hover with channel details
- Shows reconnect attempts when reconnecting
- Updates time since last message
- Correct icons and colors per state
- Accessible status role and aria-label

## Dependencies

- `lucide-react` - Icon components
- `clsx` - Conditional class composition
- `@headlessui/react` - Dialog, Transition (Lightbox only)
- `../../utils/risk` - Risk utility functions (RiskBadge only)
- `../../utils/confidence` - Confidence utility functions (ConfidenceBadge only)
- `../../hooks/useWebSocketStatus` - WebSocket types (WebSocketStatus only)
