# Common Components Directory

## Purpose

Contains reusable UI components shared across multiple features. These are low-level building blocks used throughout the application for consistent styling and behavior.

## Key Components

### RiskBadge.tsx

**Purpose:** Display risk level as a colored badge with icon and optional score

**Key Features:**

- Four risk levels: low (green), medium (yellow), high (orange), critical (red)
- Icons from lucide-react: CheckCircle (low), AlertTriangle (medium/high), AlertOctagon (critical)
- Three size variants: sm, md, lg
- Optional risk score display: "High (75)" vs just "High"
- Pulse animation for critical level (animated prop controls this)
- Rounded pill shape with background color at 10% opacity
- Full accessibility with ARIA role="status" and aria-label

**Props:**

- `level: RiskLevel` - 'low' | 'medium' | 'high' | 'critical' (required)
- `score?: number` - Risk score 0-100 (optional)
- `showScore?: boolean` - Display score in badge (default: false)
- `size?: 'sm' | 'md' | 'lg'` - Badge size (default: 'md')
- `animated?: boolean` - Enable pulse animation for critical (default: true)
- `className?: string` - Additional CSS classes

**Size Mappings:**

- sm: text-xs, px-2, py-0.5, icon w-3 h-3
- md: text-sm, px-2.5, py-1, icon w-4 h-4
- lg: text-base, px-3, py-1.5, icon w-5 h-5

**Color Mappings:**

- low: bg-green-500/10, text-green-500
- medium: bg-yellow-500/10, text-yellow-500
- high: bg-orange-500/10, text-orange-500
- critical: bg-red-500/10, text-red-500

**Usage Examples:**

```tsx
// Simple badge
<RiskBadge level="high" />

// With score
<RiskBadge level="critical" score={87} showScore />

// Custom size, no animation
<RiskBadge level="medium" size="lg" animated={false} />
```

**Integration:**
Uses utility functions from `../../utils/risk`:

- `getRiskLabel(level)` - Returns "Low", "Medium", "High", "Critical"
- Type: `RiskLevel` - Union type for risk levels

### ObjectTypeBadge.tsx

**Purpose:** Display detected object type as a colored badge with icon

**Key Features:**

- Maps object types to appropriate icons and colors
- Supports common detection types: person, car, truck, bus, motorcycle, bicycle, dog, cat, bird, package
- Unknown types display with AlertTriangle icon and capitalize the type name
- Three size variants: sm, md, lg
- Full accessibility with ARIA role="status" and aria-label
- Bordered badge style with background at 10% opacity

**Props:**

- `type: string` - Object type label from detection (required)
- `size?: 'sm' | 'md' | 'lg'` - Badge size (default: 'sm')
- `className?: string` - Additional CSS classes

**Object Type Mappings:**

| Type                        | Icon          | Color  | Display Name       |
| --------------------------- | ------------- | ------ | ------------------ |
| person                      | User          | blue   | Person             |
| car, truck, bus, motorcycle | Car           | purple | Vehicle            |
| bicycle                     | Car           | cyan   | Bicycle            |
| dog, cat, bird              | PawPrint      | amber  | Animal             |
| package                     | Package       | green  | Package            |
| unknown                     | AlertTriangle | gray   | (Capitalized type) |

**Size Mappings:**

- sm: text-xs, px-2, py-0.5, icon w-3 h-3
- md: text-sm, px-2.5, py-1, icon w-4 h-4
- lg: text-base, px-3, py-1.5, icon w-5 h-5

**Usage Examples:**

```tsx
// Basic usage
<ObjectTypeBadge type="person" />

// With size
<ObjectTypeBadge type="car" size="md" />

// Unknown type (displays as "Unknown" with capitalized name)
<ObjectTypeBadge type="drone" />
```

### ServiceStatusAlert.tsx

**Purpose:** Dismissible banner for displaying service status notifications (Redis, RT-DETRv2, Nemotron)

**Key Features:**

- Hidden when all services are healthy or null
- Yellow/Warning banner when any service is "restarting" (with spinning icon)
- Red/Error banner when any service is "unhealthy", "restart_failed", or "failed"
- Shows worst status when multiple services are unhealthy
- Animates in/out smoothly with Tailwind transitions
- Dismissible via onDismiss callback
- Full accessibility with ARIA role="alert" and aria-live="polite"

**Props:**

```typescript
interface ServiceStatusAlertProps {
  services: Record<ServiceName, ServiceStatus | null>;
  onDismiss?: () => void;
}
```

**Types:**

```typescript
type ServiceName = 'redis' | 'rtdetr' | 'nemotron';
type ServiceStatusValue = 'healthy' | 'unhealthy' | 'restarting' | 'restart_failed' | 'failed';

interface ServiceStatus {
  service: ServiceName;
  status: ServiceStatusValue;
  message?: string;
  timestamp: string;
}
```

**Status Severity (lowest to highest):**

1. healthy (0) - No alert shown
2. restarting (1) - Yellow banner with spinning RefreshCw icon
3. unhealthy (2) - Red banner with AlertTriangle icon
4. restart_failed (3) - Red banner with XCircle icon
5. failed (4) - Dark red banner with XCircle icon

**Service Name Display:**

- redis -> "Redis"
- rtdetr -> "RT-DETRv2"
- nemotron -> "Nemotron"

**Usage Example:**

```tsx
<ServiceStatusAlert
  services={{
    redis: { service: 'redis', status: 'healthy', timestamp: '...' },
    rtdetr: { service: 'rtdetr', status: 'restarting', message: 'Loading model...', timestamp: '...' },
    nemotron: null,
  }}
  onDismiss={() => setDismissed(true)}
/>
```

### index.ts

**Purpose:** Barrel export file for easy imports

**Exports:**

```typescript
export { default as RiskBadge } from './RiskBadge';
export type { RiskBadgeProps } from './RiskBadge';
```

**Note:** ObjectTypeBadge and ServiceStatusAlert are not yet exported from index.ts. Import directly:

```tsx
import ObjectTypeBadge from '../common/ObjectTypeBadge';
import { ServiceStatusAlert } from '../common/ServiceStatusAlert';
```

## Important Patterns

### Consistent Risk Level Display

RiskBadge provides a single source of truth for risk level visualization:

- Used in: EventCard, EventDetailModal, ActivityFeed, EventTimeline
- Ensures consistent colors, icons, and labels across all features
- Centralized logic for risk level styling

### Size Variants

Components follow a consistent sizing pattern:

- Small: Compact display for dense lists
- Medium (default): Standard display for most use cases
- Large: Prominent display in headers or focus areas

### Accessibility First

- Proper ARIA roles and labels
- Screen reader friendly (reads "Risk level: Critical, score 87")
- Visual and semantic information combined
- ServiceStatusAlert uses role="alert" and aria-live="polite" for screen reader announcements

### Composability

- Accepts className prop for custom styling
- Can be composed with other components
- No layout constraints (inline-flex)

## Styling Conventions

### Badge Structure

```tsx
<span className="inline-flex items-center gap-1 rounded-full font-medium">
  <Icon />
  {label}
</span>
```

### Color Strategy

- Background: Color at 10% opacity (e.g., bg-green-500/10)
- Text: Full color (e.g., text-green-500)
- Creates subtle, accessible contrast

### Animation

- Only critical level animates by default in RiskBadge
- Uses Tailwind's `animate-pulse` class
- Can be disabled with `animated={false}`
- ServiceStatusAlert uses `animate-spin` for restarting status

## Testing

### RiskBadge.test.tsx

Comprehensive test coverage includes:

- Renders all risk levels correctly
- Displays correct icons per level
- Shows/hides score based on showScore prop
- Applies correct size classes
- Animation on critical level
- ARIA attributes for accessibility
- Custom className application

### ObjectTypeBadge.test.tsx

Comprehensive test coverage includes:

- Renders all known object types correctly
- Displays correct icons and colors per type
- Handles unknown types gracefully
- Applies correct size classes
- ARIA attributes for accessibility

### ServiceStatusAlert.test.tsx

Comprehensive test coverage includes:

- Returns null when all services healthy
- Shows yellow banner for restarting status
- Shows red banner for unhealthy/failed statuses
- Displays worst status when multiple services affected
- Dismiss button functionality
- Accessible alert role and aria-live

## Entry Points

**Start here:** `RiskBadge.tsx` - Risk level badge with score display
**Also see:** `ObjectTypeBadge.tsx` - Detection object type badge
**Service alerts:** `ServiceStatusAlert.tsx` - Service health notification banner

## Dependencies

- `lucide-react` - Icon components (CheckCircle, AlertTriangle, AlertOctagon, User, Car, PawPrint, Package, RefreshCw, X, XCircle)
- `clsx` - Conditional class name composition
- `../../utils/risk` - getRiskLabel, RiskLevel type (RiskBadge only)

## Design Decisions

### Why Separate from utils/risk?

- `utils/risk` contains pure logic (getRiskLevel, getRiskColor, getRiskLabel)
- `RiskBadge` is a UI component with React dependencies
- Separation allows logic reuse in non-component contexts

### Why Three Sizes?

- sm: Dense lists (ActivityFeed items)
- md: Standard cards (EventCard)
- lg: Prominent displays (EventDetailModal header)

### Why Optional Animation?

- Critical events should draw attention
- But in some contexts (static screenshots, PDFs) animation is undesirable
- Opt-out via `animated={false}`

### Why Severity Ranking for ServiceStatusAlert?

- Multiple services can have issues simultaneously
- User needs to see the most critical issue first
- Severity ranking ensures the worst problem is highlighted

## Future Enhancements

As the common components directory grows, consider adding:

- **Button** - Consistent button styles (primary, secondary, danger)
- **Input** - Form input with validation states
- **Select** - Dropdown select with custom styling
- **Modal** - Reusable modal wrapper (consider extracting from EventDetailModal)
- **Card** - Consistent card container
- **Badge** - Generic badge (not just risk levels)
- **Tooltip** - Hover tooltips for additional info
- **Skeleton** - Loading skeleton components

### Organization Strategy

Once common components grow beyond 5-10 files, consider subdirectories:

```
common/
  badges/
    RiskBadge.tsx
    ObjectTypeBadge.tsx
    Badge.tsx
  alerts/
    ServiceStatusAlert.tsx
  inputs/
    Input.tsx
    Select.tsx
  feedback/
    Modal.tsx
    Tooltip.tsx
```
