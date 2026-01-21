# Common Components Directory

## Purpose

Contains reusable UI components shared across multiple features. These are low-level building blocks used throughout the application for consistent styling and behavior.

## Files

| File                              | Purpose                                                              | Status     |
| --------------------------------- | -------------------------------------------------------------------- | ---------- |
| `AlertBadge.tsx`                  | Alert status badge component                                         | Active     |
| `AlertBadge.test.tsx`             | Test suite for AlertBadge                                            | Active     |
| `AlertDrawer.tsx`                 | Slide-out drawer for alert details                                   | Active     |
| `AlertDrawer.test.tsx`            | Test suite for AlertDrawer                                           | Active     |
| `AmbientBackground.tsx`           | Ambient background effects with visual status cues                   | Active     |
| `AmbientBackground.test.tsx`      | Test suite for AmbientBackground                                     | Active     |
| `AmbientStatusProvider.tsx`       | Context provider for ambient status state                            | Active     |
| `AnimatedList.tsx`                | Animated list with enter/exit transitions                            | Active     |
| `AnimatedList.test.tsx`           | Test suite for AnimatedList                                          | Active     |
| `AnimatedModal.tsx`               | Modal with entrance/exit animations                                  | Active     |
| `AnimatedModal.test.tsx`          | Test suite for AnimatedModal                                         | Active     |
| `BottomSheet.tsx`                 | Mobile-friendly bottom sheet modal                                   | Active     |
| `BottomSheet.test.tsx`            | Test suite for BottomSheet                                           | Active     |
| `Button.tsx`                      | Styled button component                                              | Active     |
| `Button.test.tsx`                 | Test suite for Button                                                | Active     |
| `ChartLegend.tsx`                 | Legend component for charts                                          | Active     |
| `ChartLegend.test.tsx`            | Test suite for ChartLegend                                           | Active     |
| `ChunkLoadErrorBoundary.tsx`      | Error boundary for dynamic import/chunk loading failures             | Active     |
| `ChunkLoadErrorBoundary.test.tsx` | Test suite for ChunkLoadErrorBoundary                                | Active     |
| `CommandPalette.tsx`              | Command palette (Cmd+K) for quick navigation                         | Active     |
| `CommandPalette.test.tsx`         | Test suite for CommandPalette                                        | Active     |
| `ConfidenceBadge.tsx`             | Detection confidence score badge with color coding                   | Active     |
| `ConfidenceBadge.test.tsx`        | Test suite for ConfidenceBadge                                       | Active     |
| `EmptyState.tsx`                  | Reusable empty state component with icon and actions                 | Active     |
| `EmptyState.test.tsx`             | Test suite for EmptyState                                            | Active     |
| `ErrorBoundary.tsx`               | React error boundary for catching component errors                   | Active     |
| `ErrorBoundary.test.tsx`          | Test suite for ErrorBoundary                                         | Active     |
| `FaviconBadge.tsx`                | Dynamic favicon badge for notification counts                        | Active     |
| `FaviconBadge.test.tsx`           | Test suite for FaviconBadge                                          | Active     |
| `FeatureErrorBoundary.tsx`        | Feature-specific error isolation boundary                            | Active     |
| `FeatureErrorBoundary.test.tsx`   | Test suite for FeatureErrorBoundary                                  | Active     |
| `IconButton.tsx`                  | Icon-only button component                                           | Active     |
| `IconButton.test.tsx`             | Test suite for IconButton                                            | Active     |
| `InfiniteScrollStatus.tsx`        | Status indicator for infinite scroll loading                         | Active     |
| `InfiniteScrollStatus.test.tsx`   | Test suite for InfiniteScrollStatus                                  | Active     |
| `Lightbox.tsx`                    | Full-size image viewer with navigation                               | Active     |
| `Lightbox.test.tsx`               | Test suite for Lightbox                                              | Active     |
| `LiveRegion.tsx`                  | ARIA live region for screen reader announcements                     | Active     |
| `LiveRegion.test.tsx`             | Test suite for LiveRegion                                            | Active     |
| `LoadingSpinner.tsx`              | Simple loading spinner for Suspense fallbacks                        | Active     |
| `LoadingSpinner.test.tsx`         | Test suite for LoadingSpinner                                        | Active     |
| `NavigationTracker.tsx`           | Navigation tracking for analytics                                    | Active     |
| `NavigationTracker.test.tsx`      | Test suite for NavigationTracker                                     | Active     |
| `ObjectTypeBadge.tsx`             | Detection object type badge                                          | Active     |
| `ObjectTypeBadge.test.tsx`        | Test suite for ObjectTypeBadge                                       | Active     |
| `OfflineFallback.tsx`             | Offline state display component                                      | Active     |
| `OfflineFallback.test.tsx`        | Test suite for OfflineFallback                                       | Active     |
| `PageTransition.tsx`              | Animated page transitions                                            | Active     |
| `PageTransition.test.tsx`         | Test suite for PageTransition                                        | Active     |
| `ProductTour.tsx`                 | Interactive onboarding tour for first-time users                     | Active     |
| `ProductTour.test.tsx`            | Test suite for ProductTour                                           | Active     |
| `ProfiledComponent.tsx`           | React Profiler wrapper for performance monitoring                    | Active     |
| `ProfiledComponent.test.tsx`      | Test suite for ProfiledComponent                                     | Active     |
| `PullToRefresh.tsx`               | Pull-to-refresh component for mobile                                 | Active     |
| `PullToRefresh.test.tsx`          | Test suite for PullToRefresh                                         | Active     |
| `RateLimitIndicator.tsx`          | API rate limit status indicator                                      | Active     |
| `RateLimitIndicator.test.tsx`     | Test suite for RateLimitIndicator                                    | Active     |
| `ResponsiveChart.tsx`             | Responsive chart wrapper component                                   | Active     |
| `ResponsiveChart.test.tsx`        | Test suite for ResponsiveChart                                       | Active     |
| `ResponsiveModal.tsx`             | Responsive modal that adapts to screen size                          | Active     |
| `RiskBadge.tsx`                   | Risk level badge with icon and optional score                        | Active     |
| `RiskBadge.test.tsx`              | Test suite for RiskBadge                                             | Active     |
| `RouteLoadingFallback.tsx`        | Loading indicator for lazy-loaded routes                             | Active     |
| `RouteLoadingFallback.test.tsx`   | Test suite for RouteLoadingFallback                                  | Active     |
| `SafeErrorMessage.tsx`            | Safe error message display without sensitive data                    | Active     |
| `SafeErrorMessage.test.tsx`       | Test suite for SafeErrorMessage                                      | Active     |
| `SceneChangeAlert.tsx`            | Alert component for camera scene changes                             | Active     |
| `SceneChangeAlert.test.tsx`       | Test suite for SceneChangeAlert                                      | Active     |
| `ScheduleSelector.tsx`            | Time-based schedule configuration for alerts                         | Active     |
| `ScheduleSelector.test.tsx`       | Test suite for ScheduleSelector                                      | Active     |
| `SecureContextWarning.tsx`        | Banner for insecure context (HTTP) detection                         | Active     |
| `SecureContextWarning.test.tsx`   | Test suite for SecureContextWarning                                  | Active     |
| `ServiceStatusAlert.tsx`          | Service health notification banner                                   | Deprecated |
| `ServiceStatusAlert.test.tsx`     | Test suite for ServiceStatusAlert                                    | Deprecated |
| `ServiceStatusIndicator.tsx`      | Service health status indicator dot                                  | Active     |
| `ServiceStatusIndicator.test.tsx` | Test suite for ServiceStatusIndicator                                | Active     |
| `ShortcutsHelpModal.tsx`          | Keyboard shortcuts help dialog                                       | Active     |
| `ShortcutsHelpModal.test.tsx`     | Test suite for ShortcutsHelpModal                                    | Active     |
| `Skeleton.tsx`                    | Content placeholder during loading                                   | Active     |
| `Skeleton.test.tsx`               | Test suite for Skeleton                                              | Active     |
| `SkipLink.tsx`                    | Skip to content link for accessibility                               | Active     |
| `SkipLink.test.tsx`               | Test suite for SkipLink                                              | Active     |
| `ThumbnailImage.tsx`              | Optimized thumbnail image component                                  | Active     |
| `ThumbnailImage.test.tsx`         | Test suite for ThumbnailImage                                        | Active     |
| `ToastProvider.tsx`               | Global toast notification system                                     | Active     |
| `ToastProvider.test.tsx`          | Test suite for ToastProvider                                         | Active     |
| `Tooltip.tsx`                     | Tooltip component for hover hints                                    | Active     |
| `Tooltip.test.tsx`                | Test suite for Tooltip                                               | Active     |
| `TruncatedText.tsx`               | Text truncation with expand/collapse functionality                   | Active     |
| `TruncatedText.test.tsx`          | Test suite for TruncatedText                                         | Active     |
| `WebSocketStatus.tsx`             | WebSocket connection status indicator                                | Active     |
| `WebSocketStatus.test.tsx`        | Test suite for WebSocketStatus                                       | Active     |
| `WorkerStatusIndicator.tsx`       | Background worker status indicator                                   | Active     |
| `WorkerStatusIndicator.test.tsx`  | Test suite for WorkerStatusIndicator                                 | Active     |
| `index.ts`                        | Barrel exports for common components                                 | Active     |
| `.gitkeep`                        | Placeholder file                                                     | -          |

## Subdirectories

### animations/

Animation utilities and components.

| File       | Purpose                          |
| ---------- | -------------------------------- |
| `index.ts` | Barrel exports for animations    |

### skeletons/

Loading skeleton components for various UI elements.

| File                          | Purpose                                    |
| ----------------------------- | ------------------------------------------ |
| `AlertCardSkeleton.tsx`       | Loading skeleton for alert cards           |
| `AlertCardSkeleton.test.tsx`  | Test suite for AlertCardSkeleton           |
| `CameraCardSkeleton.tsx`      | Loading skeleton for camera cards          |
| `CameraCardSkeleton.test.tsx` | Test suite for CameraCardSkeleton          |
| `ChartSkeleton.tsx`           | Loading skeleton for charts                |
| `ChartSkeleton.test.tsx`      | Test suite for ChartSkeleton               |
| `EntityCardSkeleton.tsx`      | Loading skeleton for entity cards          |
| `EntityCardSkeleton.test.tsx` | Test suite for EntityCardSkeleton          |
| `EventCardSkeleton.tsx`       | Loading skeleton for event cards           |
| `EventCardSkeleton.test.tsx`  | Test suite for EventCardSkeleton           |
| `StatsCardSkeleton.tsx`       | Loading skeleton for stats cards           |
| `StatsCardSkeleton.test.tsx`  | Test suite for StatsCardSkeleton           |
| `TableRowSkeleton.tsx`        | Loading skeleton for table rows            |
| `TableRowSkeleton.test.tsx`   | Test suite for TableRowSkeleton            |
| `index.ts`                    | Barrel exports for skeleton components     |

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

**Color Mapping (WCAG 2.1 AA Compliant):**

| Level    | Background            | Text                 | Icon          |
| -------- | --------------------- | -------------------- | ------------- |
| low      | bg-risk-low/10        | text-risk-low        | CheckCircle   |
| medium   | bg-risk-medium/10     | text-risk-medium     | AlertTriangle |
| high     | bg-risk-high/10       | text-risk-high       | AlertTriangle |
| critical | bg-risk-critical/10   | text-risk-critical   | AlertOctagon  |

**Note:** Risk colors in `tailwind.config.js` are calibrated to achieve 4.5:1 contrast ratio when text is displayed over semi-transparent backgrounds (bg-{color}/10). The browser blends text color with background, so text colors are brightened to compensate.

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
**Also see:** `TruncatedText.tsx` - Text truncation with expand/collapse
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

### TruncatedText.tsx

**Purpose:** Display text with optional truncation and expand/collapse functionality for long descriptions

**Props Interface:**

```typescript
interface TruncatedTextProps {
  text: string;             // The text to display (and potentially truncate)
  maxLength?: number;       // Maximum chars before truncation (default: 200)
  maxLines?: number;        // Maximum lines before truncation (CSS-based)
  initialExpanded?: boolean; // Start expanded (default: false)
  showMoreLabel?: string;   // Custom "Show more" label
  showLessLabel?: string;   // Custom "Show less" label
  onToggle?: (isExpanded: boolean) => void; // Callback on expand/collapse
  className?: string;       // Additional CSS classes
}
```

**Key Features:**

- Character-based truncation with word boundary awareness
- Line-based truncation via CSS `-webkit-line-clamp`
- Smooth expand/collapse animation with transition classes
- "Show more" / "Show less" toggle button
- ChevronDown/ChevronUp icons for visual affordance
- Full accessibility: `aria-expanded` attribute on toggle button
- NVIDIA green (#76B900) styling for toggle button
- Dark theme compatible text styling

**Truncation Modes:**

| Mode      | Prop       | Behavior                                      |
| --------- | ---------- | --------------------------------------------- |
| Character | maxLength  | Truncates at character limit (word boundary)  |
| Line      | maxLines   | Uses CSS line-clamp (takes precedence)        |
| Combined  | Both       | Shows toggle if either limit is exceeded      |

**Usage:**

```tsx
import TruncatedText from '../common/TruncatedText';
// or
import { TruncatedText } from '../common';

// Basic usage with character limit
<TruncatedText text={longDescription} maxLength={200} />

// Line-based truncation
<TruncatedText text={longDescription} maxLines={3} />

// Custom labels
<TruncatedText
  text={longDescription}
  maxLength={150}
  showMoreLabel="Read more"
  showLessLabel="Read less"
/>

// With callback
<TruncatedText
  text={longDescription}
  maxLength={200}
  onToggle={(expanded) => console.log('Expanded:', expanded)}
/>
```

**Used By:**

- `EventCard.tsx` - AI summary truncation in security event cards
- `AlertsPage.tsx` - Alert descriptions via EventCard

**Dependencies:**

- `lucide-react` - ChevronDown, ChevronUp icons
- `react` - memo, useCallback, useMemo, useState

---

### TruncatedText.test.tsx

**Test Coverage (34 tests):**

- Basic rendering (text content, short text, className, element type)
- Truncation behavior (toggle visibility, maxLength, word boundaries)
- Expand/collapse functionality (click handlers, state management)
- Accessibility (aria-expanded, accessible button names, data-testid)
- Styling (text classes, button styling, transition animation)
- Edge cases (empty string, exact maxLength, whitespace, newlines, special chars)
- maxLines mode (CSS truncation, precedence over maxLength)
- Custom labels (showMoreLabel, showLessLabel)
- Callback support (onToggle called on expand/collapse)

---

### ChunkLoadErrorBoundary.tsx

**Purpose:** Specialized error boundary for handling dynamic import and code-splitting chunk loading failures

**Props Interface:**

```typescript
interface ChunkLoadErrorBoundaryProps {
  children: ReactNode;                      // Child components to wrap
  onError?: (error: Error, errorInfo: ErrorInfo) => void; // Optional error callback
}
```

**Key Features:**

- Detects chunk load errors (ChunkLoadError, module fetch failures)
- Provides user-friendly reload UI specifically for chunk errors
- Re-throws non-chunk errors to parent error boundaries
- Automatic error classification via `isChunkLoadError()` helper
- Full accessibility with ARIA labels

**Common Chunk Load Error Patterns:**

- `"loading chunk"` - Webpack/Vite chunk fetch failure
- `"failed to fetch dynamically imported module"` - Module not found
- `"dynamically imported module"` - General import failure
- `ChunkLoadError` - Named error type

**Usage:**

```tsx
import ChunkLoadErrorBoundary from '../common/ChunkLoadErrorBoundary';

<ChunkLoadErrorBoundary>
  <Suspense fallback={<RouteLoadingFallback />}>
    <LazyComponent />
  </Suspense>
</ChunkLoadErrorBoundary>
```

**Dependencies:**

- `lucide-react` - AlertTriangle, RefreshCw icons
- `react` - Component, ErrorInfo, ReactNode

---

### EmptyState.tsx

**Purpose:** Reusable empty state component with icon, title, description, and optional actions

**Props Interface:**

```typescript
interface EmptyStateProps {
  icon: LucideIcon;                         // Lucide icon component to display
  title: string;                            // Main title text
  description: string | ReactNode;          // Description or instructions
  actions?: EmptyStateAction[];             // Optional action buttons
  children?: ReactNode;                     // Optional additional content
  className?: string;                       // Additional CSS classes
}

interface EmptyStateAction {
  label: string;                            // Button label
  onClick: () => void;                      // Click handler
  variant?: 'primary' | 'secondary';        // Button style variant
}
```

**Key Features:**

- Consistent empty state styling across application
- Support for primary and secondary action buttons
- Flexible content with children prop
- Icon with NVIDIA green accent
- Dark theme compatible
- Responsive layout

**Usage:**

```tsx
import EmptyState from '../common/EmptyState';
import { Camera } from 'lucide-react';

<EmptyState
  icon={Camera}
  title="No Cameras Found"
  description="Add cameras to start monitoring your property"
  actions={[
    { label: 'Add Camera', onClick: handleAddCamera, variant: 'primary' },
    { label: 'Learn More', onClick: handleLearnMore, variant: 'secondary' }
  ]}
/>
```

**Used By:**

- `AlertsPage.tsx` - No alerts state
- `EventTimeline.tsx` - No events state
- Various pages for empty data states

**Dependencies:**

- `lucide-react` - Icon components
- `clsx` - Conditional class composition

---

### LoadingSpinner.tsx

**Purpose:** Simple loading spinner for React Suspense fallbacks

**Props:**

- None (stateless component)

**Key Features:**

- Centered full-screen layout
- Animated spinning border with NVIDIA green accent
- "Loading..." text with accessible styling
- Dark theme background (#121212)
- Minimal implementation for fast loading

**Usage:**

```tsx
import LoadingSpinner from '../common/LoadingSpinner';

<Suspense fallback={<LoadingSpinner />}>
  <LazyComponent />
</Suspense>
```

**Dependencies:**

- None (pure Tailwind CSS)

---

### RouteLoadingFallback.tsx

**Purpose:** Loading indicator specifically designed for lazy-loaded routes with better accessibility

**Props Interface:**

```typescript
interface RouteLoadingFallbackProps {
  message?: string;                         // Custom message (default: "Loading...")
}
```

**Key Features:**

- Accessible loading status with ARIA attributes
- `role="status"`, `aria-busy="true"`, `aria-live="polite"`
- Animated Loader2 icon from lucide-react
- Customizable message text
- Smaller min-height (400px) vs full-screen LoadingSpinner
- Better suited for route transitions than full-page loads

**Usage:**

```tsx
import RouteLoadingFallback from '../common/RouteLoadingFallback';

<Suspense fallback={<RouteLoadingFallback message="Loading dashboard..." />}>
  <LazyDashboardPage />
</Suspense>
```

**Used By:**

- `App.tsx` - Route-level Suspense boundaries
- `ChunkLoadErrorBoundary.tsx` - Combined pattern

**Dependencies:**

- `lucide-react` - Loader2 icon

---

## Dependencies

- `lucide-react` - Icon components
- `clsx` - Conditional class composition
- `@headlessui/react` - Dialog, Transition (Lightbox only)
- `../../utils/risk` - Risk utility functions (RiskBadge only)
- `../../utils/confidence` - Confidence utility functions (ConfidenceBadge only)
- `../../hooks/useWebSocketStatus` - WebSocket types (WebSocketStatus only)
