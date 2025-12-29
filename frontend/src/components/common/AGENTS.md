# Common Components Directory

## Purpose

Contains reusable UI components shared across multiple features. These are low-level building blocks used throughout the application for consistent styling and behavior.

## Files

| File                     | Purpose                                       | Status     |
| ------------------------ | --------------------------------------------- | ---------- |
| `RiskBadge.tsx`          | Risk level badge with icon and optional score | Active     |
| `ObjectTypeBadge.tsx`    | Detection object type badge                   | Active     |
| `ServiceStatusAlert.tsx` | Service health notification banner            | Deprecated |
| `index.ts`               | Barrel exports (only RiskBadge currently)     | Active     |

## Key Components

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
export { default as RiskBadge } from './RiskBadge';
export type { RiskBadgeProps } from './RiskBadge';
```

**Note:** ObjectTypeBadge and ServiceStatusAlert are NOT exported from index.ts. Import directly:

```typescript
import ObjectTypeBadge from '../common/ObjectTypeBadge';
```

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

**Start here:** `RiskBadge.tsx` - Most commonly used badge component
**Also see:** `ObjectTypeBadge.tsx` - Detection object type badge
**Reference:** `ServiceStatusAlert.tsx` - Deprecated but documented for future use

## Dependencies

- `lucide-react` - Icon components
- `clsx` - Conditional class composition
- `../../utils/risk` - Risk utility functions (RiskBadge only)
